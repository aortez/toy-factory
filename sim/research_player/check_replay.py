#!/usr/bin/env python3
"""Nine fixed archive/render parity checks; no search, scoring or policy selection."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import time

import prepare


def save(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')


def run(binary, runtime, out):
    prepare.require(not out.exists() and not out.is_symlink(), 'fresh parity directory required')
    bundle = prepare.load_archive()
    prepare.check(runtime, prepare.expected_files(bundle))
    references = json.loads((runtime / 'references.json').read_bytes())
    sources = {path.name: prepare.sha(path.read_bytes()) for path in Path(__file__).parent.iterdir()
               if path.suffix in ('.py', '.c', '.h', '.txt')}
    identity = prepare.sha(binary.read_bytes())
    out.mkdir(parents=True)
    save(out / 'started.json', dict(archive_sha256=prepare.ARCHIVE_SHA, binary_sha256=identity,
         sources=sources, calls=9, timeout_per_call=180, training=False,
         started_utc=datetime.now(timezone.utc).isoformat()))
    completed = []
    started = time.monotonic()
    try:
        calls = [(ref, 0) for ref in references] + [(ref, 3840) for ref in references
                                                    if ref['label'].startswith('late-')]
        for ref, render_every in calls:
            label = ref['label'] + ('-rendered' if render_every else '')
            frame = out / f'{label}.raw'
            args = [str(binary), ref['model'], ref['seed'], ref['layout'], str(ref['days'] * 3840),
                    str(ref['founder']), str(frame), str(render_every)]
            print(f'Parity {len(completed) + 1}/9: {label}', flush=True)
            process = subprocess.run(args, capture_output=True, timeout=180)
            (out / f'{label}.json').write_bytes(process.stdout)
            save(out / f'{label}.process.json', dict(args=args, returncode=process.returncode,
                stderr=process.stderr.decode(errors='replace')))
            prepare.require(process.returncode == 0 and process.stderr == b'', 'replay failed')
            expected = (runtime / f"references/{ref['label']}.json").read_bytes()
            prepare.require(process.stdout == expected, 'complete stdout differs: ' + label)
            prepare.require(frame.read_bytes() == (runtime / f"references/{ref['label']}.raw").read_bytes(),
                            'raw pixels differ: ' + label)
            completed.append(label)
        prepare.check(runtime, prepare.expected_files(bundle))
        prepare.require(prepare.sha(binary.read_bytes()) == identity, 'binary changed')
        prepare.require(sources == {path.name: prepare.sha(path.read_bytes())
            for path in Path(__file__).parent.iterdir() if path.suffix in ('.py', '.c', '.h', '.txt')},
            'adapter sources changed during verification')
        result = dict(complete=True, exact_replays=completed, elapsed_seconds=time.monotonic() - started)
        save(out / 'result.json', result)
        print(json.dumps(result, indent=2))
    except BaseException as error:
        save(out / 'failure.json', dict(error=repr(error), completed=completed))
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--runtime', type=Path, default=prepare.DEFAULT)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    run(args.binary.resolve(), args.runtime.resolve(), args.out.resolve())
