#!/usr/bin/env python3
"""Bounded learning from the frozen wear initializer; no retries or promotion."""

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'leaf_wear_report'))
import collect_wear as evidence

wear, pilot = evidence.wear, evidence.wear.pilot
ROOT = pilot.ROOT
require, read, save, digest, sha = pilot.require, pilot.read, pilot.save, pilot.digest, pilot.sha
RULE = 'garden-leaf-family-wear-pilot-v1'
PROTOCOL = ROOT / 'benchmarks/garden-seasons/leaf-family-wear-pilot-protocol.md'
BASELINE = ROOT / 'benchmarks/garden-seasons/leaf-family-wear-results.json.gz'
BASELINE_SHA = 'adfd32bc0cbc05926d475482bf3980fffbb4949cbc5c7699df9e0609b313f134'
MAX_CALLS, MAX_SECONDS, MAX_BYTES, MIN_FREE = 688, 7200, 1024**3, 2 * 1024**3
TRAIN, REVIEW = pilot.TRAIN, pilot.REVIEW
VALIDATE = ('98a89374', '2e42e011')
CONTROL_NAMES = ('light', 'initial')


def baseline(full=False):
    require(digest(BASELINE) == BASELINE_SHA, 'fixed wear evidence changed')
    bundle = json.loads(gzip.decompress(BASELINE.read_bytes()))
    if full:
        evidence.verify(bundle)
    return bundle


def blob(bundle, path):
    identity = bundle['files'][path]
    raw = bytes.fromhex(bundle['blobs'][identity])
    require(sha(raw) == identity, 'fixed evidence blob differs')
    return raw


def check_initializer(values, bundle, out, refs):
    for value, ref, index in zip(values, refs, range(5, 21)):
        source = f'runs/call{index:04d}/'
        stdout, pixels = blob(bundle, source + 'stdout.json'), blob(bundle, source + 'frame.raw')
        require(value == json.loads(stdout) and (out / 'runs' / ref / 'stdout.json').read_bytes() == stdout and
                (out / 'runs' / ref / 'frame.raw').read_bytes() == pixels, 'wear initializer replay differs')
    require(len(values) == len(refs) == 16, 'incomplete initializer panel')


def seed_occurs(content, tokens):
    hexadecimal = b'0123456789abcdefABCDEF'
    for token in tokens:
        position = content.find(token)
        while position >= 0:
            end = position + len(token)
            if (position == 0 or content[position - 1] not in hexadecimal) and \
                    (end == len(content) or content[end] not in hexadecimal):
                return True
            position = content.find(token, position + 1)
    return False


def seed_audit():
    """Scan the published corpus, never running candidate weather to select it."""
    derived = tuple(format(int.from_bytes(hashlib.sha256(
        ('toy-factory/leaf-family-wear-pilot-v1/validation-' + str(i)).encode()).digest()[:4], 'little'), '08x')
        for i in (1, 2))
    require(derived == VALIDATE and not (set(VALIDATE) & set(TRAIN + REVIEW + pilot.VALIDATE)),
            'fresh seed derivation/split differs')
    try:
        listing = subprocess.run(['rg', '--files', 'benchmarks', 'docs', 'sim', '-g', '*.json',
            '-g', '*.json.gz', '-g', '*.md', '-g', '*.py'], cwd=ROOT, capture_output=True, text=True, check=True)
        names = listing.stdout.splitlines()
    except FileNotFoundError:
        # The existing builder has Git but not ripgrep. Preserve ignore rules
        # without installing a new tool just for this read-only audit.
        listing = subprocess.run(['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z',
            '--', 'benchmarks', 'docs', 'sim'], cwd=ROOT, capture_output=True, text=True, check=True)
        names = [name for name in listing.stdout.split('\0') if name.endswith(('.json', '.json.gz', '.md', '.py'))]
    tokens = tuple(token.encode() for seed in VALIDATE
                   for token in (seed, seed.upper(), str(int(seed, 16))))
    files, matches = {}, []
    for name in sorted(set(names)):
        if name.startswith(('sim/experiments/leaf_wear_pilot/', 'sim/experiments/leaf_wear_pilot_report/')) or \
                name.startswith('benchmarks/garden-seasons/leaf-family-wear-pilot'):
            continue
        raw = (ROOT / name).read_bytes()
        files[name] = sha(raw)
        content = gzip.decompress(raw) if name.endswith('.gz') else raw
        # Byte search skips encoded payloads without a per-byte Python regex
        # boundary test; check boundaries only at actual substring matches.
        if seed_occurs(content, tokens):
            matches.append(name)
    return dict(seeds=list(VALIDATE), checked_utc=pilot.utc(), matches=matches, files=files)


class Limits(pilot.Limits):
    def submit(self):
        now = self.clock()
        require(self.count < MAX_CALLS, '688-call ceiling reached')
        require(self.first is None or now - self.first < MAX_SECONDS, 'two-hour submission deadline reached')
        require(self.size() < MAX_BYTES, 'run folder reached 1 GiB')
        require(shutil.disk_usage(self.root).free >= MIN_FREE, 'less than 2 GiB free')
        if self.first is None:
            self.first, self.first_utc = now, pilot.utc()
        self.count += 1
        return self.count, now - self.first


class Search(pilot.Pilot):
    def __init__(self, out, identities):
        super().__init__(out, identities)
        self.limits, self.batch_log = Limits(out), []

    def matches(self, name, seeds, *, phase, days=608, capture=False, workers=2, force=False):
        refs, todo, pending = [], [], {}
        for seed, layout, founder in pilot.roles(seeds):
            key = pilot.call_key(self.models[name]['sha256'], seed, layout, founder, days, capture)
            if not force and key in self.cache:
                ref = self.cache[key]
                self.reuse.append(dict(phase=phase, model=name, call=ref, key=list(key)))
            else:
                ref = f'call{len(self.calls) + len(todo) + 1:04d}'
                todo.append(dict(id=ref, phase=phase, model=name, model_sha256=self.models[name]['sha256'],
                    seed=seed, layout=layout, founder=founder, days=days, capture=capture))
                pending[ref] = key
            refs.append(ref)
        for offset in range(0, len(todo), workers):
            batch = todo[offset:offset + workers]
            entry = dict(index=len(self.batch_log) + 1, workers=workers, calls=[c['id'] for c in batch])
            save(self.out / 'batches' / f"batch{entry['index']:04d}.json", entry)
            self.batch_log.append(entry)
            wear.batches(batch, self.submit, self.execute, lambda call, value: None, workers=workers)
        for call in todo:
            self.cache[pending[call['id']]] = call['id']
        return refs, [pilot.load_call(self.out, ref, self.identities)[1] for ref in refs]


def source_pins():
    paths = {PROTOCOL, pilot.PROTOCOL, wear.PROTOCOL, *HERE.glob('*.py')}
    for module in tuple(sys.modules.values()):
        name = getattr(module, '__file__', None)
        if name:
            path = Path(name).resolve()
            if path.suffix == '.py' and path.is_relative_to(ROOT):
                paths.add(path)
    return {str(path.relative_to(ROOT)): digest(path) for path in sorted(paths)}


def main(out):
    require(out.parent == ROOT / 'artifacts' and not out.exists() and not out.is_symlink(), 'fresh artifacts required')
    identities, _ = pilot.controls.verify_inputs()
    fixed = baseline(full=True)
    require(fixed['summary']['scope']['identities'] == identities, 'wear/runtime identity differs')
    audit = seed_audit()
    require(not audit['matches'], 'validation seed already appears: ' + ', '.join(audit['matches']))
    pins = source_pins()
    scope = dict(schema=RULE, maximum_native_calls=MAX_CALLS, workers=2, timeout_seconds=180,
        submission_seconds=MAX_SECONDS, maximum_bytes=MAX_BYTES, minimum_free_bytes=MIN_FREE,
        automatic_retry=False, identities=identities, baseline_sha256=BASELINE_SHA,
        source_sha256=pins, created_utc=pilot.utc(), training_seeds=list(TRAIN), review_seeds=list(REVIEW),
        validation_seeds=list(VALIDATE), search_seeds=list(pilot.model.SEARCH_SEEDS), generations=3, offspring=4)
    out.mkdir()
    for name in ('models', 'runs', 'evaluations', 'generations', 'gallery', 'source', 'batches'):
        (out / name).mkdir()
    save(out / 'started.json', scope)
    save(out / 'seed-audit.json', audit)
    runner = Search(out, identities)
    try:
        for name, identity in pins.items():
            target = out / 'source' / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(pilot.ROOT / name, target)
            require(digest(target) == identity, 'source changed during snapshot')
        shutil.copy2(pilot.controls.replay.NEW / 'model.tgl', out / 'growth.tgl')
        runner.put_model('light', wear.models()['light'], dict(kind='fixed-light'))
        runner.put_model('initial', wear.models()['wear'], dict(kind='fixed-wear'))
        initial = runner.evaluate('initial', TRAIN, phase='train', capture=True)
        check_initializer([pilot.load_call(out, ref, identities)[1] for ref in initial['calls']],
                          fixed, out, initial['calls'])
        save(out / 'initializer-parity.json', dict(exact_histories_state_pixels=True, calls=initial['calls']))
        champions, finals = [], []
        for search, seed in enumerate(pilot.model.SEARCH_SEEDS, 1):
            parent, state = 'initial', seed
            scores = {'initial': pilot.exact_key(initial['analysis'])}
            row = dict(search=search, generation=0, parent=None, children=[], champion=parent, rng_state=state)
            save(out / 'generations' / f's{search}-g0.json', row)
            champions.append(row)
            for generation in range(1, 4):
                children = []
                parent_model = pilot.model.decode((out / 'models' / (parent + '.tlf')).read_bytes())
                for index in range(1, 5):
                    child, state, receipt = pilot.model.mutate(parent_model, state)
                    name = f's{search}-g{generation}-c{index}'
                    runner.put_model(name, pilot.model.encode(child), dict(kind='mutation', search=search,
                        generation=generation, child_index=index, parent_name=parent, **receipt))
                    children.append(name)
                for name in children:
                    evaluation = runner.evaluate(name, TRAIN, phase='train')
                    scores[name] = pilot.exact_key(evaluation['analysis'])
                champion = pilot.model.select(parent, children, scores)
                row = dict(search=search, generation=generation, parent=parent, children=children,
                    champion=champion, rng_state=state, key=pilot.controls.rational_key(scores[champion]))
                save(out / 'generations' / f's{search}-g{generation}.json', row)
                champions.append(row)
                print(f'SEARCH {search} GENERATION {generation}: {champion} {row["key"]}', flush=True)
                parent = champion
            finals.append(parent)
        # Freeze both finalists before inspecting review or fresh validation.
        save(out / 'selection-closed.json', dict(finals=finals, closed_utc=pilot.utc()))
        for row in champions:
            runner.gallery(row['search'], row['generation'], row['champion'])
        validation = []
        for logical, name in zip(('search1', 'search2', 'light', 'wear'), finals + list(CONTROL_NAMES)):
            runner.evaluate(name, VALIDATE, phase='validation-' + logical, capture=True)
            validation.append(dict(logical=logical, evaluation='validation-' + logical + '-' + name))
        confirmation = []
        for search, name in enumerate(finals, 1):
            original = runner.evaluations['train-' + name]['calls']
            refs, values = runner.matches(name, TRAIN, phase=f'confirmation-s{search}',
                capture=not runner.calls[original[0]]['capture'], workers=1, force=True)
            for old_ref, value in zip(original, values):
                previous = pilot.load_call(out, old_ref, identities)[1]
                require(previous | dict(framebuffer_crc32=None) == value | dict(framebuffer_crc32=None),
                        'serial opposite-capture replay differs')
            confirmation.append(dict(search=search, model=name, training=original, repeats=refs))
        require(pilot.controls.verify_inputs()[0] == identities and source_pins() == pins,
                'pilot inputs changed')
        require(runner.limits.size() < MAX_BYTES, 'run folder exceeded 1 GiB')
        result = dict(scope=scope, completed_utc=pilot.utc(), native_calls=runner.limits.count,
            first_call_utc=runner.limits.first_utc, seconds_since_first=time.monotonic() - runner.limits.first,
            finals=finals, validation=validation, confirmation=confirmation, reuse=runner.reuse,
            models=runner.models, evaluations=runner.evaluations, champions=champions, batches=runner.batch_log)
        save(out / 'result.json', result)
        print(f'PILOT COMPLETE: {runner.limits.count} native calls; finalists {finals}', flush=True)
    except BaseException as error:
        save(out / 'failure.json', dict(error=repr(error), submitted_calls=runner.limits.count,
            first_call_utc=runner.limits.first_utc, stopped_utc=pilot.utc(), automatic_retry=False,
            reuse=runner.reuse, completed_evaluations=list(runner.evaluations)))
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    main(parser.parse_args().out.resolve())
