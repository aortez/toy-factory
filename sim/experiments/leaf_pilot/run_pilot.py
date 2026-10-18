#!/usr/bin/env python3
"""Approved bounded family repair pilot. Fresh directory only; never resume/retry."""

import argparse
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import datetime, timezone
from fractions import Fraction
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import threading
import time
import zlib

import pilot_model as model

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE.parent / 'leaf_controls'))
import run_leaf_controls as controls
import collect_leaf_controls as control_evidence
from family_fitness import aggregate, score_family

require, save, read, digest = controls.require, controls.save, controls.read, controls.digest
DAY = 3840
TRAIN = ('3c308d3b', '97806ca5')
REVIEW = ('8272b256',)
VALIDATE = ('17922dd0', 'db49e58a')
LAYOUTS = (('rainfed', 3), ('rainfed-crowded', 5))
CHECKPOINTS = (16, 256, 608)
MAX_CALLS, MAX_SECONDS, TIMEOUT = 704, 7200, 180
MAX_BYTES, MIN_FREE = 1024**3, 2 * 1024**3
PROTOCOL = ROOT / 'benchmarks/garden-seasons/leaf-family-pilot-proposal.md'
BASELINE = ROOT / 'benchmarks/garden-seasons/leaf-family-controls-results.json.gz'
BASELINE_SHA = '5c3a36f85a9a4b2c14670dd807c51a4f5f08de555f8b978b27bfb8aa718c4048'
RULE = 'garden-leaf-family-pilot-v1'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def utc():
    return datetime.now(timezone.utc).isoformat()


def roles(seeds):
    return [(seed, layout, founder) for seed in seeds for layout, count in LAYOUTS
            for founder in range(1, count + 1)]


def call_key(repair_sha, seed, layout, founder, days, capture):
    # Runtime and W2 are fixed for the entire run and checked before every call.
    return (repair_sha, seed, layout, founder, days, capture)


def parity_value(value):
    """Remove only the two explicit repair identities, preserving every other byte."""
    state = bytes.fromhex(value['state_hex'])
    require(len(state) >= 12 and state[:4] == b'TFR1', 'wrong family state')
    count, = struct.unpack_from('<I', state, 8)
    require(3 <= count <= 4096 and len(state) == 12 + count + 5293 and
            state[12 + count:16 + count] == b'TLR1', 'wrong nested state')
    require(state[16 + count:188 + count].hex() == value['leaf_model_hex'], 'repair identities differ')
    return value | dict(leaf_model_hex=None,
        state_hex=(state[:16 + count] + bytes(172) + state[188 + count:]).hex())


def validate_output(value, call, growth_sha, repair, pixels):
    require(value['schema'] == 'garden-leaf-family-replay-v1' and value['complete'] is True and
            value['controller_assignment'] == 'founder-family' and value['objective'] is None,
            'incomplete or wrong replay')
    expected = dict(seed=call['seed'], scenario=call['layout'], ticks=call['days'] * DAY,
        candidate_founder=call['founder'], resident_policy='selective', climate='seasonal',
        growth_model_sha256=growth_sha, leaf_model_hex=repair.hex())
    require(all(value.get(k) == v for k, v in expected.items()) and value['gardener'] is False and
            type(value['ticks']) is int and type(value['candidate_founder']) is int and
            type(value.get('ledger_start_tick')) is int and value['ledger_start_tick'] == 0,
            'condition/model/history binding differs')
    model.decode(repair)
    if call['capture']:
        require(pixels is not None and len(pixels) == 115200 and
                value['framebuffer_crc32'] == f'{zlib.crc32(pixels):08x}', 'frame differs')
    else:
        require(pixels is None and value['framebuffer_crc32'] is None, 'unexpected frame')
    founders = dict(LAYOUTS)[call['layout']]
    state = bytes.fromhex(value['state_hex'])
    require(len(state) >= 12, 'truncated state')
    count, = struct.unpack_from('<I', state, 8)
    require(state[:8] == b'TFR1' + bytes((call['founder'], 3, founders, 0)) and
            founders <= count <= 4096 and len(state) == 12 + count + 5293 and
            count == len(value['lineages']) == len(value['family_roots']), 'invalid family state')
    require(state[12:12 + count] == bytes(value['family_roots']) and
            state[12 + count:16 + count] == b'TLR1' and state[16 + count:188 + count] == repair,
            'state/model binding differs')
    require([p['id'] for p in value['lineages']] == list(range(1, count + 1)) and
            all(type(p['id']) is int for p in value['lineages']), 'lineage ordering differs')
    roots = {}
    for p in value['lineages']:
        identity, parent = p['id'], p['parent']
        require(type(parent) is int and 0 <= parent < identity and
                ((identity <= founders) == (parent == 0)), 'invalid parent')
        roots[identity] = roots[parent] if parent else identity
        require(roots[identity] == value['family_roots'][identity - 1], 'ownership differs')
    if call['days'] == 608:
        score_family(value | {'tick': value['ticks']}, call['founder'], start_day=192, window_count=6)
    else:
        # The shared ledger validator accepts short horizons without scoring them.
        from garden_descendants import index_records
        index_records(value['lineages'], value['seeds'], 0, value['ticks'])
    return value


def score_values(values, seeds):
    expected = {seed + '-' + layout: tuple(range(1, count + 1))
                for seed in seeds for layout, count in LAYOUTS}
    require(len(values) == len(roles(seeds)), 'wrong match count')
    scores = {condition: {} for condition in expected}
    details = []
    for value, (seed, layout, founder) in zip(values, roles(seeds)):
        require((value['seed'], value['scenario'], value['candidate_founder'], value['ticks']) ==
                (seed, layout, founder, 608 * DAY), 'score roster/order differs')
        score = score_family(value | {'tick': value['ticks']}, founder, start_day=192, window_count=6)
        scores[seed + '-' + layout][founder] = score
        family = [p for p in value['lineages'] if value['family_roots'][p['id'] - 1] == founder]
        living = [p for p in family if p['death_tick'] is None]
        pending = [s for s in value['seeds'] if s.get('end_tick') is None and
                   value['family_roots'][s['parent'] - 1] == founder]
        last_birth = max(p['birth_tick'] for p in family)
        details.append(dict(seed=seed, layout=layout, founder=founder, score=score.record(),
            species=family[0]['species'], end_alive=len(living), max_generation=max(p['generation'] for p in family),
            last_birth_tick=last_birth, closing_birth_gap_ticks=value['ticks'] - last_birth,
            pending_seed_records=len(pending)))
    key = aggregate(scores, expected_roles=expected)
    return dict(key=controls.rational_key(key), matches=details,
                roles_with_renewal=sum(row['score']['key'][0][0] > 0 for row in details))


def exact_key(record):
    return tuple(Fraction(*part) for part in record['key'])


class Limits:
    def __init__(self, root, clock=time.monotonic):
        self.root, self.clock = root, clock
        self.first = None
        self.first_utc = None
        self.count = 0

    def size(self):
        return sum(p.stat().st_size for p in self.root.rglob('*') if p.is_file())

    def submit(self):
        now = self.clock()
        require(self.count < MAX_CALLS, 'native call ceiling reached')
        require(self.first is None or now - self.first < MAX_SECONDS, 'two-hour submission deadline reached')
        require(self.size() < MAX_BYTES, 'run directory reached 1 GiB')
        require(shutil.disk_usage(self.root).free >= MIN_FREE, 'less than 2 GiB free')
        if self.first is None:
            self.first, self.first_utc = now, utc()
        self.count += 1
        return self.count, now - self.first


def bounded(calls, execute, submit, *, workers=2, stopped=None):
    """Never queue beyond the active workers; completed failure precedes refill."""
    require(workers in (1, 2), 'one or two workers required')
    stopped = stopped or threading.Event()
    pending, result, iterator = {}, {}, iter(calls)
    def guarded(call):
        try:
            return execute(call)
        except BaseException:
            stopped.set()
            raise
    with ThreadPoolExecutor(max_workers=workers) as pool:
        def enqueue():
            call = next(iterator, None)
            if call is not None:
                require(not stopped.is_set(), 'another native call failed')
                submit(call)
                pending[pool.submit(guarded, call)] = call
        for _ in range(workers):
            enqueue()
        while pending:
            done, _ = wait(pending, return_when=FIRST_COMPLETED)
            ordered = sorted(done, key=lambda f: pending[f]['id'])
            completed = [(pending[f], f.result()) for f in ordered]
            for f in ordered:
                del pending[f]
            for call, value in completed:
                result[call['id']] = value
            for _ in completed:
                enqueue()
    return result


class Pilot:
    def __init__(self, out, identities):
        self.out, self.identities = out, identities
        self.limits, self.stopped = Limits(out), threading.Event()
        self.cache, self.calls, self.models, self.evaluations = {}, {}, {}, {}
        self.reuse = []
        self.binary = controls.replay.NEW / 'native/leaf-family-owned'

    def put_model(self, name, raw, provenance):
        model.decode(raw)
        require(name not in self.models, 'duplicate logical model')
        (self.out / 'models' / (name + '.tlf')).write_bytes(raw)
        record = dict(name=name, sha256=sha(raw), provenance=provenance)
        save(self.out / 'models' / (name + '.json'), record)
        self.models[name] = record
        return name

    def submit(self, call):
        number, elapsed = self.limits.submit()
        require(number == int(call['id'][4:]), 'call numbering differs')
        folder = self.out / 'runs' / call['id']
        folder.mkdir()
        require(digest(self.binary) == self.identities['owned_binary_sha256'] and
                digest(self.out / 'growth.tgl') == self.identities['growth_model_sha256'] and
                digest(self.out / 'models' / (call['model'] + '.tlf')) == call['model_sha256'],
                'runtime or model identity changed')
        args = list(map(str, (self.binary, self.out / 'growth.tgl', self.out / 'models' / (call['model'] + '.tlf'),
            call['seed'], call['layout'], call['days'] * DAY, call['founder'], 'selective')))
        if call['capture']:
            args.append(str(folder / 'frame.raw'))
        save(folder / 'started.json', dict(call=call, args=args, submitted_utc=utc(),
            since_first_seconds=elapsed, binary_sha256=self.identities['owned_binary_sha256'],
            growth_sha256=self.identities['growth_model_sha256']))
        self.calls[call['id']] = call

    def execute(self, call):
        folder = self.out / 'runs' / call['id']
        started = read(folder / 'started.json')
        before = time.monotonic()
        try:
            process = subprocess.run(started['args'], capture_output=True, timeout=TIMEOUT)
            stdout, stderr, code, timeout = process.stdout, process.stderr, process.returncode, False
        except subprocess.TimeoutExpired as error:
            stdout, stderr, code, timeout = error.stdout or b'', error.stderr or b'', None, True
        elapsed = time.monotonic() - before
        (folder / 'stdout.json').write_bytes(stdout)
        (folder / 'stderr.txt').write_bytes(stderr)
        receipt = dict(returncode=code, timed_out=timeout, elapsed_seconds=elapsed, finished_utc=utc(),
            stdout_bytes=len(stdout), stdout_sha256=sha(stdout), stderr_bytes=len(stderr), stderr_sha256=sha(stderr))
        save(folder / 'process.json', receipt)
        require(code == 0 and not timeout and not stderr and len(stdout) < 8 * 1024**2,
                'failed bounded native call: ' + call['id'])
        raw = (self.out / 'models' / (call['model'] + '.tlf')).read_bytes()
        pixels = (folder / 'frame.raw').read_bytes() if call['capture'] else None
        value = validate_output(json.loads(stdout), call, self.identities['growth_model_sha256'], raw, pixels)
        if pixels is not None:
            controls.write_png(folder / 'frame.png', 240, 240, controls.rgb565be_to_rgb888(pixels))
        save(folder / 'checked.json', receipt | dict(frame_sha256=sha(pixels) if pixels else None,
            png_sha256=digest(folder / 'frame.png') if pixels else None,
            lineages=len(value['lineages']), seeds=len(value['seeds'])))
        print(f"{call['id']} {call['phase']} {call['model']} {call['seed']} {call['layout']} "
              f"f{call['founder']} day{call['days']}: {elapsed:.2f}s", flush=True)
        return value

    def matches(self, name, seeds, *, phase, days=608, capture=False, workers=2, force=False):
        references, todo, pending_keys = [], [], {}
        for seed, layout, founder in roles(seeds):
            key = call_key(self.models[name]['sha256'], seed, layout, founder, days, capture)
            if not force and key in self.cache:
                identity = self.cache[key]
                self.reuse.append(dict(phase=phase, model=name, call=identity, key=list(key)))
            else:
                identity = f'call{len(self.calls) + len(todo) + 1:04d}'
                call = dict(id=identity, phase=phase, model=name, model_sha256=self.models[name]['sha256'],
                    seed=seed, layout=layout, founder=founder, days=days, capture=capture)
                todo.append(call)
                pending_keys[identity] = key
            references.append(identity)
        bounded(todo, self.execute, self.submit, workers=workers, stopped=self.stopped)
        for call in todo:
            self.cache[pending_keys[call['id']]] = call['id']
        # Cache hits are verified again against retained process receipts/bytes.
        values = [load_call(self.out, identity, self.identities)[1] for identity in references]
        return references, values

    def evaluate(self, name, seeds, *, phase, capture=False):
        refs, values = self.matches(name, seeds, phase=phase, capture=capture)
        report = dict(model=name, model_sha256=self.models[name]['sha256'], seeds=list(seeds), calls=refs,
                      analysis=score_values(values, seeds))
        save(self.out / 'evaluations' / (phase + '-' + name + '.json'), report)
        self.evaluations[phase + '-' + name] = report
        return report

    def gallery(self, search, generation, champion):
        refs = []
        for days in CHECKPOINTS:
            calls, _ = self.matches(champion, REVIEW, phase=f'review-s{search}-g{generation}',
                                   days=days, capture=True)
            refs.append(calls)
        groups = [[dict(id=refs[column][row], framebuffer=f'../../runs/{refs[column][row]}/frame.raw')
                   for column in range(3)] for row in range(8)]
        folder = self.out / 'gallery' / f's{search}-g{generation}'
        folder.mkdir()
        metadata = controls.contact_sheet(folder, groups)
        save(folder / 'gallery.json', metadata | dict(search=search, generation=generation, champion=champion,
            model_sha256=self.models[champion]['sha256'], seed=REVIEW[0], days=list(CHECKPOINTS),
            row_roles=[list(role) for role in roles(REVIEW)], png_sha256=digest(folder / 'contact-sheet.png')))


def load_call(out, identity, identities):
    require(type(identity) is str and len(identity) == 8 and identity.startswith('call') and
            identity[4:].isdigit(), 'unsafe call reference')
    folder = out / 'runs' / identity
    start, receipt, checked = (read(folder / name) for name in ('started.json', 'process.json', 'checked.json'))
    call = start['call']
    require(call['id'] == identity and start['binary_sha256'] == identities['owned_binary_sha256'] and
            start['growth_sha256'] == identities['growth_model_sha256'], 'call identity differs')
    raw = (out / 'models' / (call['model'] + '.tlf')).read_bytes()
    stdout, stderr = (folder / 'stdout.json').read_bytes(), (folder / 'stderr.txt').read_bytes()
    require(sha(raw) == call['model_sha256'] and receipt['returncode'] == 0 and receipt['timed_out'] is False and
            not stderr and receipt['stderr_bytes'] == 0 and receipt['stderr_sha256'] == sha(stderr) and
            receipt['stdout_bytes'] == len(stdout) and receipt['stdout_sha256'] == sha(stdout) and
            all(checked.get(k) == v for k, v in receipt.items()), 'process/model receipt differs')
    require(type(receipt['elapsed_seconds']) in (float, int) and 0 < receipt['elapsed_seconds'] < TIMEOUT + 5 and
            checked['lineages'] == len(json.loads(stdout)['lineages']) and
            checked['seeds'] == len(json.loads(stdout)['seeds']), 'derived receipt differs')
    args = start['args']
    run_root = Path(args[1]).parent
    expected = [str(run_root / 'models' / (call['model'] + '.tlf')), call['seed'], call['layout'],
                str(call['days'] * DAY), str(call['founder']), 'selective']
    if call['capture']:
        expected.append(str(run_root / 'runs' / identity / 'frame.raw'))
    require(Path(args[0]).name == 'leaf-family-owned' and Path(args[1]).name == 'growth.tgl' and
            args[2:] == expected, 'native command differs')
    pixels = (folder / 'frame.raw').read_bytes() if call['capture'] else None
    require(checked['frame_sha256'] == (sha(pixels) if pixels else None), 'frame hash differs')
    value = validate_output(json.loads(stdout), call, identities['growth_model_sha256'], raw, pixels)
    if pixels is not None:
        png = (folder / 'frame.png').read_bytes()
        require(sha(png) == checked['png_sha256'] and
                control_evidence.png_rgb(png, 240, 240) == controls.rgb565be_to_rgb888(pixels), 'PNG pixels differ')
    return call, value


def source_pins():
    paths = {PROTOCOL, *HERE.glob('*.py'), *(HERE.parent / 'leaf_model_tools').glob('*.py')}
    for module in tuple(sys.modules.values()):
        filename = getattr(module, '__file__', None)
        if filename:
            path = Path(filename).resolve()
            if path.suffix == '.py' and path.is_relative_to(ROOT):
                paths.add(path)
    return {str(p.relative_to(ROOT)): digest(p) for p in sorted(paths)}


def baseline():
    require(digest(BASELINE) == BASELINE_SHA, 'fixed controls bundle changed')
    return control_evidence.verify(json.loads(gzip.decompress(BASELINE.read_bytes())))


def check_initializer(values, bundle, out, refs):
    for value, role, ref in zip(values, roles(TRAIN), refs):
        seed, layout, founder = role
        label = f'{seed}-{layout}-f{founder}-light'
        old = json.loads(bundle['runs'][label]['stdout'])
        require(parity_value(value) == parity_value(old), 'initializer biological parity differs: ' + label)
        pixels = bytes.fromhex(bundle['frames'][bundle['result']['receipts'][label]['framebuffer_sha256']])
        require((out / 'runs' / ref / 'frame.raw').read_bytes() == pixels, 'initializer pixels differ: ' + label)


def main(out):
    require(out.parent == ROOT / 'artifacts' and not out.exists() and not out.is_symlink(), 'fresh artifacts output required')
    identities, _ = controls.verify_inputs()
    fixed = baseline()
    pins = source_pins()
    scope = dict(schema=RULE, approved='2026-10-17: run the pilot', maximum_native_calls=MAX_CALLS,
        workers=2, timeout_seconds=TIMEOUT, submission_seconds=MAX_SECONDS, maximum_bytes=MAX_BYTES,
        minimum_free_bytes=MIN_FREE, automatic_retry=False, identities=identities,
        baseline_sha256=BASELINE_SHA, source_sha256=pins, created_utc=utc(),
        training_seeds=list(TRAIN), review_seeds=list(REVIEW), validation_seeds=list(VALIDATE),
        search_seeds=list(model.SEARCH_SEEDS), generations=3, offspring=4)
    out.mkdir()
    for name in ('models', 'runs', 'evaluations', 'generations', 'gallery', 'source'):
        (out / name).mkdir()
    save(out / 'started.json', scope)
    pilot = Pilot(out, identities)
    try:
        for name in pins:
            target = out / 'source' / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / name, target)
            require(digest(target) == pins[name], 'source changed while copying')
        shutil.copy2(controls.replay.NEW / 'model.tgl', out / 'growth.tgl')
        for name, raw in controls.replay.models().items():
            pilot.put_model(name, raw, dict(kind='fixed-control'))
        pilot.put_model('initial', model.encode(model.initial_model()), dict(kind='equivalent-light'))
        initial = pilot.evaluate('initial', TRAIN, phase='train', capture=True)
        check_initializer([load_call(out, ref, identities)[1] for ref in initial['calls']], fixed, out, initial['calls'])
        save(out / 'initializer-parity.json', dict(exact_histories_state_pixels=True, calls=initial['calls']))
        champions, finals = [], []
        for search, seed in enumerate(model.SEARCH_SEEDS, 1):
            parent, state = 'initial', seed
            scores = {'initial': exact_key(initial['analysis'])}
            row = dict(search=search, generation=0, parent=None, children=[], champion=parent, rng_state=state)
            save(out / 'generations' / f's{search}-g0.json', row)
            champions.append(row)
            for generation in range(1, 4):
                children = []
                parent_model = model.decode((out / 'models' / (parent + '.tlf')).read_bytes())
                # Generate all mutations before evaluating any child.
                for child_index in range(1, 5):
                    child, state, receipt = model.mutate(parent_model, state)
                    name = f's{search}-g{generation}-c{child_index}'
                    pilot.put_model(name, model.encode(child), dict(kind='mutation', search=search,
                        generation=generation, child_index=child_index, parent_name=parent, **receipt))
                    children.append(name)
                for name in children:
                    result = pilot.evaluate(name, TRAIN, phase='train')
                    scores[name] = exact_key(result['analysis'])
                champion = model.select(parent, children, scores)
                row = dict(search=search, generation=generation, parent=parent, children=children,
                    champion=champion, rng_state=state, key=controls.rational_key(scores[champion]))
                save(out / 'generations' / f's{search}-g{generation}.json', row)
                champions.append(row)
                print(f'SEARCH {search} GENERATION {generation}: {champion} {row["key"]}', flush=True)
                parent = champion
            finals.append(parent)
        # Selection is now closed. Review never feeds back into the search.
        for row in champions:
            pilot.gallery(row['search'], row['generation'], row['champion'])
        validation = []
        for logical, name in zip(('search1', 'search2', 'wait', 'renew', 'light'), finals + ['wait', 'renew', 'light']):
            result = pilot.evaluate(name, VALIDATE, phase='validation-' + logical, capture=True)
            validation.append(dict(logical=logical, evaluation='validation-' + logical + '-' + name))
        confirmation = []
        for search, name in enumerate(finals, 1):
            training = pilot.evaluations['train-' + name]
            original_capture = pilot.calls[training['calls'][0]]['capture']
            refs, values = pilot.matches(name, TRAIN, phase=f'confirmation-s{search}',
                                        capture=not original_capture, workers=1, force=True)
            for old_ref, value in zip(training['calls'], values):
                old = load_call(out, old_ref, identities)[1]
                require(old | {'framebuffer_crc32': None} == value | {'framebuffer_crc32': None},
                        'serial opposite-capture parity differs')
            confirmation.append(dict(search=search, model=name, training=training['calls'], repeats=refs))
        require(controls.verify_inputs()[0] == identities and source_pins() == pins, 'pilot inputs changed')
        result = dict(scope=scope, completed_utc=utc(), native_calls=pilot.limits.count,
            first_call_utc=pilot.limits.first_utc, seconds_since_first=time.monotonic() - pilot.limits.first,
            finals=finals, validation=validation, confirmation=confirmation, reuse=pilot.reuse,
            models=pilot.models, evaluations=pilot.evaluations, champions=champions)
        save(out / 'result.json', result)
        print(f'PILOT COMPLETE: {pilot.limits.count} native calls, finals {finals}', flush=True)
    except BaseException as error:
        save(out / 'failure.json', dict(error=repr(error), native_calls=pilot.limits.count,
            first_call_utc=pilot.limits.first_utc, stopped_utc=utc(), automatic_retry=False,
            reuse=pilot.reuse, completed_evaluations=list(pilot.evaluations)))
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    main(parser.parse_args().out.resolve())
