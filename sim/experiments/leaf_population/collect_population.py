#!/usr/bin/env python3
"""Fixed 48-call whole-population comparison; no search, retry or model promotion."""

import argparse
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import time
import zlib

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'sim/research_player'))
import prepare
import population_score as score

WORKERS, CALL_SECONDS, COLLECTION_SECONDS = 4, 180, 45 * 60
STOP = score.DAYS[-1] * score.DAY
ADAPTER = ROOT / 'sim/research_player'


def save(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write('\n')


def write(path, raw):
    with path.open('xb') as stream:
        stream.write(raw)


def roster():
    return [dict(id=f'{model}-{seed}-{layout}-{phase}', model=model, seed=seed,
                 layout=layout, phase=phase, ticks=STOP)
            for phase in ('primary', 'repeat') for model in score.MODELS
            for seed in score.SEEDS for layout in score.LAYOUTS]


def sources():
    paths = [p for folder in (ADAPTER, Path(__file__).parent) for p in folder.iterdir()
             if p.suffix in ('.py', '.c', '.h', '.txt', '.cmake')]
    paths.append(ROOT / 'docs/garden-population-comparison.md')
    return {str(p.relative_to(ROOT)): prepare.sha(p.read_bytes()) for p in sorted(paths)}


def archive_inputs():
    bundle = prepare.load_archive()
    models = {m: prepare.blob(bundle, f'models/{m}.tlf') for m in score.MODELS}
    ref = json.loads(prepare.blob(bundle, 'runs/' + next(c['id'] for c in
        json.loads(prepare.blob(bundle, 'started.json'))['plan'] if c['phase'] == 'panel') + '/stdout.json'))
    size = len(bytes.fromhex(ref['state_hex'])) - 12 - len(ref['lineages'])
    return bundle, models, size


def check_parity(folder, binary_hash):
    started = json.loads((folder / 'started.json').read_bytes())
    result = json.loads((folder / 'result.json').read_bytes())
    current = {p.name: prepare.sha(p.read_bytes()) for p in ADAPTER.iterdir()
               if p.suffix in ('.py', '.c', '.h', '.txt')}
    expected = [f'{phase}-{model}{suffix}' for phase, suffix in
                (('anchor', ''), ('late', ''), ('late', '-rendered')) for model in score.MODELS]
    # The parity runner's order follows the archive, so compare the complete unique roster.
    score.require(started['binary_sha256'] == binary_hash and started['sources'] == current and
                  started['archive_sha256'] == prepare.ARCHIVE_SHA and started['calls'] == 9 and
                  result.get('complete') is True and len(result['exact_replays']) == 9 and
                  set(result['exact_replays']) == set(expected), 'current nine-replay parity required')
    score.require(not (folder / 'failure.json').exists(), 'failed parity attempt')
    return started, result


def process_call(args, folder, timeout, *, allow_stderr=False):
    """Keep stdout/stderr on disk even if interrupted or killed by the timeout."""
    folder.mkdir()
    began = time.monotonic()
    receipt = dict(args=args, timeout_seconds=timeout,
                   started_utc=datetime.now(timezone.utc).isoformat())
    try:
        with (folder / 'stdout.json').open('xb') as stdout, (folder / 'stderr.txt').open('xb') as stderr:
            p = subprocess.run(args, stdout=stdout, stderr=stderr, timeout=timeout, check=False)
        receipt.update(returncode=p.returncode, timed_out=False)
    except BaseException as error:
        receipt.update(error=repr(error), timed_out=isinstance(error, subprocess.TimeoutExpired))
        raise
    finally:
        receipt['elapsed_seconds'] = time.monotonic() - began
        save(folder / 'process.json', receipt)
    score.require(receipt['returncode'] == 0 and
                  (allow_stderr or (folder / 'stderr.txt').stat().st_size == 0),
                  f'process failed: {folder.name}')
    return (folder / 'stdout.json').read_bytes()


def verified_call(call, binary, out, models, size, deadline):
    remaining = deadline - time.monotonic()
    score.require(remaining > 0, 'collection time budget exhausted')
    folder = out / 'runs' / call['id']
    args = [str(binary), call['model'], call['seed'], call['layout'], str(STOP), 'all']
    if call['phase'] == 'primary':
        args += ['--timeline', str(folder / 'timeline')]
    stdout = process_call(args, folder, min(CALL_SECONDS, remaining))
    validate_output(call, out, models, size)
    save(folder / 'verified.json', dict(complete=True, stdout_sha256=prepare.sha(stdout)))
    return call['id']


def validate_output(call, out, models, size):
    """Validate retained output without executing a simulator or archived program."""
    folder = out / 'runs' / call['id']
    stdout = (folder / 'stdout.json').read_bytes()
    value = json.loads(stdout)
    validate = lambda v, tick: score.validate_record(v, models[call['model']],
        seed=call['seed'], layout=call['layout'], ticks=tick, uniform_bytes=size)
    validate(value, STOP)
    if call['phase'] == 'primary':
        timeline = folder / 'timeline'
        expected = {f'tick-{d * score.DAY:010d}.{ext}' for d in score.DAYS for ext in ('raw', 'json')}
        score.require({p.name for p in timeline.iterdir()} == expected, 'capture roster differs')
        for day in score.DAYS:
            prefix = timeline / f'tick-{day * score.DAY:010d}'
            snapshot = json.loads(prefix.with_suffix('.json').read_bytes())
            validate(snapshot, day * score.DAY)
            raw = prefix.with_suffix('.raw').read_bytes()
            score.require(len(raw) == 115200 and snapshot['framebuffer_crc32'] ==
                          f'{zlib.crc32(raw):08x}', 'capture size/CRC differs')
            score.require(score.history_prefix(value, day * score.DAY) ==
                          score.history_prefix(snapshot, day * score.DAY), 'checkpoint history differs')
        score.require(prefix.with_suffix('.json').read_bytes() == stdout,
                      'final stdout differs from capture')
        score.analyze_world(value)
    else:
        score.require(value['framebuffer_crc32'] is None, 'repeat unexpectedly rendered')
        primary = out / 'runs' / call['id'].removesuffix('-repeat')
        primary = primary.with_name(primary.name + '-primary')
        reference = json.loads((primary / 'stdout.json').read_bytes())
        score.require({k: v for k, v in value.items() if k != 'framebuffer_crc32'} ==
                      {k: v for k, v in reference.items() if k != 'framebuffer_crc32'},
                      'complete rendered/unrendered replay differs')
    return value


def bounded_phase(calls, worker):
    """Submit no more than four calls; stop submitting after any observed failure."""
    iterator = iter(calls)
    completed = []
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        active = {pool.submit(worker, call) for call in [next(iterator) for _ in range(min(WORKERS, len(calls)))]}
        while active:
            done, active = wait(active, return_when=FIRST_COMPLETED)
            # Inspect every completion before replenishing, including simultaneous failures.
            for future in done:
                completed.append(future.result())
                print(f'Verified {completed[-1]}', flush=True)
            for _ in done:
                call = next(iterator, None)
                if call is not None:
                    active.add(pool.submit(worker, call))
    return completed


def check_initial_conditions(out):
    for seed in score.SEEDS:
        for layout in score.LAYOUTS:
            normalized = []
            for model in score.MODELS:
                record = json.loads((out / 'runs' / f'{model}-{seed}-{layout}-primary' /
                    'timeline/tick-0000000000.json').read_bytes())
                state = bytearray.fromhex(record.pop('state_hex'))
                offset = 16 + len(record['lineages'])
                state[offset:offset + 172] = bytes(172)
                record.pop('leaf_model_hex')
                normalized.append(record | dict(state_hex=state.hex()))
            score.require(normalized[0] == normalized[1] == normalized[2], 'initial conditions differ')


def preflight(binary, out):
    build = binary.parent
    discovered = subprocess.run(['ctest', '--test-dir', str(build), '--show-only=json-v1',
                                 '-R', '^research-'], capture_output=True, check=True, timeout=30)
    names = {t['name'] for t in json.loads(discovered.stdout)['tests']}
    score.require(names == {'research-session', 'research-population', 'research-population-cli',
        'research-population-analysis', 'research-player-smoke', 'research-player-controls',
        'research-player-parity'}, 'full host session/viewer test roster required')
    process_call(['ctest', '--test-dir', str(build), '--output-on-failure', '-R', '^research-'],
                 out / 'session-tests', 240)
    process_call([sys.executable, '-B', '-m', 'unittest', 'discover', '-s', str(ADAPTER),
                  '-p', 'test_prepare.py'], out / 'prepare-tests', 60, allow_stderr=True)


def run(binary, runtime, parity, out):
    score.require(not out.exists() and not out.is_symlink(), 'fresh output directory required')
    bundle, models, size = archive_inputs()
    prepare.check(runtime, prepare.expected_files(bundle))
    binary_hash, pinned = prepare.sha(binary.read_bytes()), sources()
    parity_start, parity_result = check_parity(parity, binary_hash)
    out.mkdir(parents=True)
    plan = roster()
    save(out / 'started.json', dict(schema='garden-population-collection-v1', plan=plan,
        workers=WORKERS, timeout_per_call=CALL_SECONDS, collection_seconds=COLLECTION_SECONDS,
        archive_sha256=prepare.ARCHIVE_SHA, binary_sha256=binary_hash, sources=pinned,
        models={m: prepare.sha(raw) for m, raw in models.items()}, uniform_bytes=size,
        started_utc=datetime.now(timezone.utc).isoformat(), training=False,
        parity_started=parity_start, parity_result=parity_result))
    try:
        for name in pinned:
            path = out / 'source' / name
            path.parent.mkdir(parents=True, exist_ok=True)
            write(path, (ROOT / name).read_bytes())
        preflight(binary, out)
        began = time.monotonic()
        deadline = began + COLLECTION_SECONDS
        (out / 'runs').mkdir()
        completed = []
        for phase in ('primary', 'repeat'):
            calls = [call for call in plan if call['phase'] == phase]
            completed += bounded_phase(calls, lambda call: verified_call(
                call, binary, out, models, size, deadline))
            if phase == 'primary':
                check_initial_conditions(out)
        score.require(len(completed) == 48 and time.monotonic() <= deadline, 'collection budget differs')
        prepare.check(runtime, prepare.expected_files(bundle))
        score.require(binary_hash == prepare.sha(binary.read_bytes()) and pinned == sources(),
                      'binary or sources changed during collection')
        worlds = {(c['model'], c['seed'], c['layout']): score.analyze_world(json.loads(
            (out / 'runs' / c['id'] / 'stdout.json').read_bytes())) for c in plan if c['phase'] == 'primary'}
        result = dict(schema='garden-population-results-v1', complete=True, calls=48,
            elapsed_seconds=time.monotonic() - began, analysis=score.aggregate(worlds),
            worlds=[dict(model=m, seed=s, layout=l, **w) for (m, s, l), w in worlds.items()])
        save(out / 'result.json', result)
        files = {str(p.relative_to(out)): prepare.sha(p.read_bytes()) for p in sorted(out.rglob('*'))
                 if p.is_file()}
        save(out / 'manifest.json', dict(schema='garden-population-files-v1', files=files))
        print(json.dumps(dict(complete=True, calls=48, elapsed_seconds=result['elapsed_seconds'])), flush=True)
    except BaseException as error:
        save(out / 'failure.json', dict(error=repr(error)))
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--runtime', type=Path, default=prepare.DEFAULT)
    parser.add_argument('--parity', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    # Do not resolve the destination: a symlink must be rejected, not followed.
    run(args.binary.resolve(), args.runtime.resolve(), args.parity.resolve(), args.out.absolute())
