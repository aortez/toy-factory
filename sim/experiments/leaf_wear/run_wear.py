#!/usr/bin/env python3
"""One fixed, 40-call wear-aware comparison; fresh output only, no retries."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import gzip
import json
from pathlib import Path
import shutil
import subprocess
import sys

import wear_model as wear
import run_pilot as pilot

HERE, ROOT = Path(__file__).resolve().parent, pilot.ROOT
require, read, save, digest, sha = pilot.require, pilot.read, pilot.save, pilot.digest, pilot.sha
PROTOCOL = ROOT / 'benchmarks/garden-seasons/leaf-family-wear-protocol.md'
PILOT_ARCHIVE = ROOT / 'benchmarks/garden-seasons/leaf-family-pilot-results.json.gz'
PILOT_SHA = '8cf389c49f81495cdb04c662ada3ec4925c2003a165ae7a15214509674b0db86'
SEEDS = pilot.TRAIN + pilot.VALIDATE
ANCHORS = (('3c308d3b', 'rainfed', 1), ('97806ca5', 'rainfed-crowded', 3),
           ('17922dd0', 'rainfed', 2), ('db49e58a', 'rainfed-crowded', 3))
MAX_CALLS, MAX_SECONDS, MAX_BYTES = 40, 1800, 256 * 1024**2
SCHEMA = 'garden-leaf-family-wear-v1'


def label(role):
    seed, layout, founder = role
    return f'{seed}-{layout}-f{founder}'


def models():
    return dict(light=pilot.controls.replay.models()['light'], wear=wear.model.encode(wear.initializer()))


def plan():
    result = []
    for phase, name, roles, capture in (('anchor', 'light', ANCHORS, True),
            ('panel', 'wear', pilot.roles(SEEDS), True), ('confirm', 'wear', ANCHORS, False)):
        for seed, layout, founder in roles:
            result.append(dict(id=f'call{len(result) + 1:04d}', phase=phase, model=name,
                model_sha256=sha(models()[name]), seed=seed, layout=layout, founder=founder,
                days=608, capture=capture))
    return result


def load_baselines():
    """Exact-byte bindings into two already-verified, hash-pinned repo archives.

    Offline checking needs these companion archives, but no raw artifact folders
    or native binaries. Do not duplicate the entire closed search in this bundle.
    """
    require(digest(pilot.BASELINE) == pilot.BASELINE_SHA and digest(PILOT_ARCHIVE) == PILOT_SHA,
            'closed evidence archive changed')
    control = json.loads(gzip.decompress(pilot.BASELINE.read_bytes()))
    prior = json.loads(gzip.decompress(PILOT_ARCHIVE.read_bytes()))
    def pilot_bytes(path):
        identity = prior['files'][path]
        data = bytes.fromhex(prior['blobs'][identity])
        require(sha(data) == identity, 'closed pilot blob differs')
        return data
    evaluation = json.loads(pilot_bytes('evaluations/validation-light-light.json'))
    require(evaluation['calls'] == [f'call{i:04d}' for i in range(537, 553)], 'old validation roster differs')
    identities = control['result']['scope']['identities']
    require(json.loads(pilot_bytes('started.json'))['identities'] == identities, 'old runtime identities differ')
    rows = []
    for index, role in enumerate(pilot.roles(SEEDS)):
        key = label(role)
        if index < 16:
            source = key + '-light'
            stdout = control['runs'][source]['stdout'].encode()
            frame_sha = control['result']['receipts'][source]['framebuffer_sha256']
            pixels = bytes.fromhex(control['frames'][frame_sha])
            origin = dict(archive='controls', archive_sha256=pilot.BASELINE_SHA, run=source)
        else:
            source = evaluation['calls'][index - 16]
            stdout = pilot_bytes(f'runs/{source}/stdout.json')
            pixels = pilot_bytes(f'runs/{source}/frame.raw')
            origin = dict(archive='pilot', archive_sha256=PILOT_SHA, run=source)
        value = json.loads(stdout)
        call = dict(seed=role[0], layout=role[1], founder=role[2], days=608, capture=True)
        pilot.validate_output(value, call, identities['growth_model_sha256'], models()['light'], pixels)
        rows.append(dict(label=key, origin=origin, stdout=stdout, pixels=pixels, value=value))
    return identities, rows


def save_baselines(out, rows):
    for row in rows:
        folder = out / 'baseline' / row['label']
        folder.mkdir()
        (folder / 'stdout.json').write_bytes(row['stdout'])
        (folder / 'frame.raw').write_bytes(row['pixels'])
        pilot.controls.write_png(folder / 'frame.png', 240, 240,
                                 pilot.controls.rgb565be_to_rgb888(row['pixels']))
        save(folder / 'origin.json', row['origin'])


class Limits(pilot.Limits):
    def submit(self):
        now = self.clock()
        require(self.count < MAX_CALLS, '40-call ceiling reached')
        require(self.first is None or now - self.first < MAX_SECONDS, '30-minute submission deadline reached')
        require(self.size() < MAX_BYTES, 'run folder reached 256 MiB')
        require(shutil.disk_usage(self.root).free >= pilot.MIN_FREE, 'less than 2 GiB free')
        if self.first is None:
            self.first, self.first_utc = now, pilot.utc()
        self.count += 1
        return self.count, now - self.first


def batches(calls, submit, execute, validate, workers=2):
    """Complete and check an entire batch before submitting its successor."""
    require(workers in (1, 2), 'invalid batch width')
    results = {}
    for offset in range(0, len(calls), workers):
        batch = calls[offset:offset + workers]
        for call in batch:
            submit(call)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(execute, call) for call in batch]
            for call, future in zip(batch, futures):
                value = future.result()
                validate(call, value)
                results[call['id']] = value
    return results


def diagnostics(value):
    founder = value['candidate_founder']
    family = [p for p in value['lineages'] if value['family_roots'][p['id'] - 1] == founder]
    parent = family[0]
    score = pilot.score_family(value | {'tick': value['ticks']}, founder, start_day=192, window_count=6)
    return dict(founder_death_tick=parent['death_tick'],
        founder_alive_day1=parent['death_tick'] is None or parent['death_tick'] > pilot.DAY,
        founder_alive_day32=parent['death_tick'] is None or parent['death_tick'] > 32 * pilot.DAY,
        founder_children=sum(p['parent'] == founder for p in family),
        actual_descendants=len(family) - 1,
        living_descendants=sum(p['id'] != founder and p['death_tick'] is None for p in family),
        garden_end_alive=sum(p['death_tick'] is None for p in value['lineages']),
        closing_window_renewal=score.renewal_children[-1])


def analyze(values):
    result = {}
    for name in ('light', 'wear'):
        rows = values[name]
        panels = {key: pilot.score_values([v for v in rows if v['seed'] in seeds], seeds)
                  for key, seeds in (('original_training', pilot.TRAIN),
                                     ('examined_validation', pilot.VALIDATE), ('combined', SEEDS))}
        conditions = {}
        for seed in SEEDS:
            for layout, count in pilot.LAYOUTS:
                scores = {v['candidate_founder']: pilot.score_family(v | {'tick': v['ticks']},
                    v['candidate_founder'], start_day=192, window_count=6)
                    for v in rows if (v['seed'], v['scenario']) == (seed, layout)}
                key = seed + '-' + layout
                conditions[key] = pilot.controls.rational_key(pilot.aggregate({key: scores},
                    expected_roles={key: tuple(range(1, count + 1))}))
        details = {label((v['seed'], v['scenario'], v['candidate_founder'])): diagnostics(v) for v in rows}
        result[name] = dict(panels=panels, conditions=conditions, diagnostics=details,
            founder_day1_survivors=sum(d['founder_alive_day1'] for d in details.values()),
            founder_day32_survivors=sum(d['founder_alive_day32'] for d in details.values()),
            families_with_descendants=sum(d['actual_descendants'] > 0 for d in details.values()))
    return result


def render_gallery(out):
    calls = plan()[4:36]
    for seed in SEEDS:
        folder = out / 'gallery' / seed
        folder.mkdir()
        groups = [[dict(id='light-' + label(role), framebuffer=f'../../baseline/{label(role)}/frame.raw'),
                   dict(id=call['id'], framebuffer=f"../../runs/{call['id']}/frame.raw")]
                  for role, call in zip(pilot.roles(SEEDS), calls) if role[0] == seed]
        metadata = pilot.controls.contact_sheet(folder, groups)
        save(folder / 'gallery.json', metadata | dict(seed=seed, columns=['light', 'wear'],
            roles=[list(r) for r in pilot.roles((seed,))], png_sha256=digest(folder / 'contact-sheet.png')))


def source_pins():
    paths = {PROTOCOL, *HERE.glob('*.py')}
    for module in tuple(sys.modules.values()):
        name = getattr(module, '__file__', None)
        if name:
            path = Path(name).resolve()
            if path.suffix == '.py' and path.is_relative_to(ROOT):
                paths.add(path)
    return {str(p.relative_to(ROOT)): digest(p) for p in sorted(paths)}


def check(out):
    """Recompute every result without invoking native programs."""
    require(not (out / 'failure.json').exists(), 'failed attempt is not a complete comparison')
    scope = read(out / 'started.json')
    require(scope['schema'] == SCHEMA and scope['maximum_native_calls'] == MAX_CALLS and
            scope['maximum_seconds'] == MAX_SECONDS and scope['maximum_bytes'] == MAX_BYTES and
            scope['minimum_free_bytes'] == pilot.MIN_FREE and scope['workers'] == 2 and
            scope['timeout_seconds'] == 180 and scope['automatic_retry'] is False and
            scope['plan'] == plan(), 'protocol/budget differs')
    for name, expected in scope['source_sha256'].items():
        path = Path(name)
        require(not path.is_absolute() and '..' not in path.parts, 'unsafe source path')
        require(digest(out / 'source' / path) == expected and digest(ROOT / path) == expected,
                'source snapshot/checker differs')
    require(str(PROTOCOL.relative_to(ROOT)) in scope['source_sha256'] and
            str((HERE / 'run_wear.py').relative_to(ROOT)) in scope['source_sha256'], 'missing source binding')
    tests = read(out / 'tests.json')
    require(tests['returncode'] == 0 and 'Ran 10 tests' in tests['stderr'] and
            tests['stderr'].endswith('OK\n') and tests['stdout'] == '', 'preflight tests did not pass')
    identities, old = load_baselines()
    require(scope['identities'] == identities and digest(out / 'growth.tgl') == identities['growth_model_sha256'],
            'runtime/W2 identity differs')
    for name, raw in models().items():
        require((out / 'models' / (name + '.tlf')).read_bytes() == raw, 'model differs')
        metadata = read(out / 'models' / (name + '.json'))
        require(metadata == dict(name=name, sha256=sha(raw), provenance=dict(kind='fixed-policy')),
                'model provenance differs')
    require({p.name for p in (out / 'baseline').iterdir()} == {r['label'] for r in old}, 'old roster differs')
    for row in old:
        folder = out / 'baseline' / row['label']
        require(read(folder / 'origin.json') == row['origin'] and
                (folder / 'stdout.json').read_bytes() == row['stdout'] and
                (folder / 'frame.raw').read_bytes() == row['pixels'] and
                pilot.control_evidence.png_rgb((folder / 'frame.png').read_bytes(), 240, 240) ==
                pilot.controls.rgb565be_to_rgb888(row['pixels']), 'reused control differs')
    require({p.name for p in (out / 'runs').iterdir()} == {c['id'] for c in plan()}, 'new call roster differs')
    values, intervals = {}, []
    for expected in plan():
        ref = expected['id']
        call, values[ref] = pilot.load_call(out, ref, identities)
        require(call == expected, 'call differs from frozen roster')
        started, process = (read(out / 'runs' / ref / name) for name in ('started.json', 'process.json'))
        require(0 <= started['since_first_seconds'] < MAX_SECONDS, 'submission deadline exceeded')
        begin, end = (datetime.fromisoformat(x).timestamp() for x in
                      (started['submitted_utc'], process['finished_utc']))
        require(end > begin, 'invalid process times')
        intervals.append((begin, end))
    previous_end = 0
    for offset in range(0, 36, 2):
        batch = intervals[offset:offset + 2]
        require(min(x[0] for x in batch) >= previous_end, 'batch overlap exceeded two calls')
        previous_end = max(x[1] for x in batch)
    for begin, end in intervals[36:]:
        require(begin >= previous_end, 'confirmation is not serial')
        previous_end = end
    by_role = {r['label']: r for r in old}
    for call in plan()[:4]:
        row = by_role[label((call['seed'], call['layout'], call['founder']))]
        folder = out / 'runs' / call['id']
        require((folder / 'stdout.json').read_bytes() == row['stdout'] and
                (folder / 'frame.raw').read_bytes() == row['pixels'], 'anchor replay differs')
    panel = {label((c['seed'], c['layout'], c['founder'])): c['id'] for c in plan()[4:36]}
    for call in plan()[36:]:
        ref = panel[label((call['seed'], call['layout'], call['founder']))]
        require(values[ref] | dict(framebuffer_crc32=None) == values[call['id']], 'serial capture parity differs')
    for seed in SEEDS:
        folder = out / 'gallery' / seed
        metadata = read(folder / 'gallery.json')
        roles = pilot.roles((seed,))
        rows = [['light-' + label(role), panel[label(role)]] for role in roles]
        require(metadata == dict(width=504, height=1992, gap=8, rows=rows, seed=seed,
            columns=['light', 'wear'], roles=[list(r) for r in roles],
            png_sha256=digest(folder / 'contact-sheet.png')), 'gallery binding differs')
        expected = bytearray(bytes((32, 36, 42)) * 504 * 1992)
        for y, role in enumerate(roles):
            pixels = [by_role[label(role)]['pixels'],
                      (out / 'runs' / panel[label(role)] / 'frame.raw').read_bytes()]
            for x, raw in enumerate(pixels):
                rgb = pilot.controls.rgb565be_to_rgb888(raw)
                for line in range(240):
                    start = ((8 + 248 * y + line) * 504 + 8 + 248 * x) * 3
                    expected[start:start + 720] = rgb[line * 720:(line + 1) * 720]
        require(pilot.control_evidence.png_rgb((folder / 'contact-sheet.png').read_bytes(), 504, 1992) ==
                bytes(expected), 'gallery pixels differ')
    return dict(schema=SCHEMA, scope=scope, native_calls=40, reused_controls=32,
        exact_anchors=4, exact_serial_capture_checks=4, selected_model=None,
        analysis=analyze(dict(light=[r['value'] for r in old],
                             wear=[values[c['id']] for c in plan()[4:36]])))


def main(out):
    require(out.parent == ROOT / 'artifacts' and not out.exists() and not out.is_symlink(), 'fresh output required')
    identities, _ = pilot.controls.verify_inputs()
    # These closed archives were fully checked when collected. Verify the controls
    # again and authenticate exact archived pilot bytes before reusing any output.
    pilot.baseline()
    old_identities, old = load_baselines()
    require(old_identities == identities, 'closed/current runtime differs')
    pins, calls = source_pins(), plan()
    scope = dict(schema=SCHEMA, maximum_native_calls=MAX_CALLS, maximum_seconds=MAX_SECONDS,
        maximum_bytes=MAX_BYTES, minimum_free_bytes=pilot.MIN_FREE, timeout_seconds=180,
        workers=2, automatic_retry=False, identities=identities, source_sha256=pins,
        plan=calls, created_utc=pilot.utc())
    out.mkdir()
    for name in ('models', 'runs', 'baseline', 'gallery', 'source'):
        (out / name).mkdir()
    save(out / 'started.json', scope)
    runner = pilot.Pilot(out, identities)
    runner.limits = Limits(out)
    try:
        for name, identity in pins.items():
            target = out / 'source' / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / name, target)
            require(digest(target) == identity, 'source changed during snapshot')
        tests = subprocess.run([sys.executable, str(HERE / 'test_wear.py'), '-v'],
                               capture_output=True, text=True, timeout=45)
        save(out / 'tests.json', dict(returncode=tests.returncode, stdout=tests.stdout, stderr=tests.stderr))
        require(tests.returncode == 0, tests.stdout + tests.stderr)
        print('10 preflight tests passed; starting the fixed 40-call panel.', flush=True)
        shutil.copy2(pilot.controls.replay.NEW / 'model.tgl', out / 'growth.tgl')
        for name, raw in models().items():
            runner.put_model(name, raw, dict(kind='fixed-policy'))
        save_baselines(out, old)
        lookup = {r['label']: r for r in old}
        def anchor(call, value):
            row = lookup[label((call['seed'], call['layout'], call['founder']))]
            folder = out / 'runs' / call['id']
            require(value == row['value'] and (folder / 'stdout.json').read_bytes() == row['stdout'] and
                    (folder / 'frame.raw').read_bytes() == row['pixels'], 'anchor differs: ' + call['id'])
        batches(calls[:4], runner.submit, runner.execute, anchor)
        captured = batches(calls[4:36], runner.submit, runner.execute, lambda call, value: None)
        panel = {label((c['seed'], c['layout'], c['founder'])): c['id'] for c in calls[4:36]}
        def confirmation(call, value):
            ref = panel[label((call['seed'], call['layout'], call['founder']))]
            require(captured[ref] | dict(framebuffer_crc32=None) == value, 'capture-free replay differs')
        batches(calls[36:], runner.submit, runner.execute, confirmation, workers=1)
        render_gallery(out)
        require(runner.limits.size() < MAX_BYTES, 'run folder exceeded ceiling')
        result = check(out)
        save(out / 'result.json', result)
        print(json.dumps(dict(native_calls=40, keys={name: {key: panel['key']
              for key, panel in data['panels'].items()} for name, data in result['analysis'].items()})), flush=True)
    except BaseException as error:
        save(out / 'failure.json', dict(error=str(error), submitted_calls=runner.limits.count,
                                      failed_utc=pilot.utc()))
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--check', type=Path)
    args = parser.parse_args()
    if args.check:
        require(args.out is None, 'check cannot run a comparison')
        result = check(args.check.resolve())
        require(result == read(args.check / 'result.json'), 'saved result differs')
        print('40 calls, 32 reused controls, anchors, parity, scores and pixels verified.')
    else:
        require(args.out is not None, 'fresh output required')
        main(args.out.resolve())
