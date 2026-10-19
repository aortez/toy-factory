#!/usr/bin/env python3
"""Verify and package population evidence offline, without replaying any native code."""

import argparse
import gzip
import html
import io
import json
from pathlib import Path
import struct
import zlib

import collect_population as collect
import population_score as score
import prepare


def verify(out):
    manifest = json.loads((out / 'manifest.json').read_bytes())
    score.require(manifest['schema'] == 'garden-population-files-v1', 'wrong manifest schema')
    actual = {}
    for path in out.rglob('*'):
        score.require(not path.is_symlink(), 'symlink in evidence')
        if path.is_file() and path != out / 'manifest.json':
            actual[str(path.relative_to(out))] = prepare.sha(path.read_bytes())
    score.require(actual == manifest['files'] and 'failure.json' not in actual, 'evidence files differ')
    started = json.loads((out / 'started.json').read_bytes())
    result = json.loads((out / 'result.json').read_bytes())
    _, models, size = collect.archive_inputs()
    score.require(started['plan'] == collect.roster() and started['uniform_bytes'] == size and
                  started['archive_sha256'] == prepare.ARCHIVE_SHA and started['training'] is False and
                  started['models'] == {m: prepare.sha(raw) for m, raw in models.items()} and
                  started['workers'] == 4 and started['timeout_per_call'] == 180 and
                  started['collection_seconds'] == 2700, 'protocol differs')
    score.require({p.name for p in (out / 'runs').iterdir()} ==
                  {c['id'] for c in collect.roster()}, 'run directory roster differs')
    parity, parity_result = started['parity_started'], started['parity_result']
    expected_parity = {f'{phase}-{model}{suffix}' for phase, suffix in
        (('anchor', ''), ('late', ''), ('late', '-rendered')) for model in score.MODELS}
    score.require(parity['binary_sha256'] == started['binary_sha256'] and
                  parity['archive_sha256'] == prepare.ARCHIVE_SHA and parity['calls'] == 9 and
                  parity_result['complete'] is True and len(parity_result['exact_replays']) == 9 and
                  set(parity_result['exact_replays']) == expected_parity, 'parity receipt differs')
    for name, digest in parity['sources'].items():
        score.require(started['sources']['sim/research_player/' + name] == digest,
                      'parity source identity differs')
    for name, marker in (('session-tests', '100% tests passed, 0 tests failed out of 7'),
                         ('prepare-tests', 'Ran 10 tests')):
        folder = out / name
        receipt = json.loads((folder / 'process.json').read_bytes())
        output = (folder / 'stdout.json').read_text() + (folder / 'stderr.txt').read_text()
        score.require(receipt.get('returncode') == 0 and receipt.get('timed_out') is False and
                      marker in output, 'preflight tests did not pass')
    for name, digest in started['sources'].items():
        prepare.relative(name)
        score.require(actual['source/' + name] == digest, 'source copy differs')
    worlds = {}
    for call in started['plan']:
        folder = out / 'runs' / call['id']
        receipt = json.loads((folder / 'process.json').read_bytes())
        verified = json.loads((folder / 'verified.json').read_bytes())
        score.require(receipt.get('returncode') == 0 and receipt.get('timed_out') is False and
                      0 < receipt['timeout_seconds'] <= 180 and
                      (folder / 'stderr.txt').read_bytes() == b'' and verified.get('complete') is True and
                      verified['stdout_sha256'] == prepare.sha((folder / 'stdout.json').read_bytes()),
                      'process receipt differs')
        expected_args = [call['model'], call['seed'], call['layout'], str(collect.STOP), 'all']
        args = receipt['args']
        score.require(args[1:6] == expected_args and
                      (len(args) == 6 if call['phase'] == 'repeat' else
                       len(args) == 8 and args[6] == '--timeline' and
                       Path(args[7]).parts[-3:] == ('runs', call['id'], 'timeline')),
                      'recorded process arguments differ')
        value = collect.validate_output(call, out, models, size)
        if call['phase'] == 'primary':
            worlds[call['model'], call['seed'], call['layout']] = score.analyze_world(value)
    collect.check_initial_conditions(out)
    expected_worlds = [dict(model=m, seed=s, layout=l, **w) for (m, s, l), w in worlds.items()]
    score.require(result['schema'] == 'garden-population-results-v1' and result['complete'] is True and
                  result['calls'] == 48 and 0 < result['elapsed_seconds'] <= 2700 and
                  result['analysis'] == score.aggregate(worlds) and result['worlds'] == expected_worlds,
                  'recomputed results differ')
    return result


def package(out, target):
    verify(out)
    files, blobs = {}, {}
    for path in sorted(out.rglob('*')):
        if not path.is_file():
            continue
        raw = path.read_bytes()
        digest = prepare.sha(raw)
        files[str(path.relative_to(out))] = digest
        blobs[digest] = raw.hex()
    raw = json.dumps(dict(schema='garden-population-evidence-v1', files=files, blobs=blobs),
                     sort_keys=True, separators=(',', ':')).encode()
    # gzip.compress(..., mtime=0) used a platform-specific OS header byte in
    # Python 3.11/3.12. GzipFile emits the same neutral header across versions.
    compressed = io.BytesIO()
    with gzip.GzipFile(fileobj=compressed, mode='wb', filename='', compresslevel=9, mtime=0) as stream:
        stream.write(raw)
    collect.write(target, compressed.getvalue())
    return prepare.sha(target.read_bytes())


def unpack(archive, target):
    score.require(not target.exists() and not target.is_symlink(), 'fresh unpack directory required')
    bundle = json.loads(gzip.decompress(archive.read_bytes()))
    score.require(bundle['schema'] == 'garden-population-evidence-v1', 'wrong evidence schema')
    # Validate every path and blob before creating anything. Never execute or import archived code.
    files = {}
    for name, digest in bundle['files'].items():
        prepare.relative(name)
        raw = bytes.fromhex(bundle['blobs'][digest])
        score.require(prepare.sha(raw) == digest, 'archive blob differs')
        files[name] = raw
    target.mkdir(parents=True)
    for name, raw in files.items():
        path = target / name
        path.parent.mkdir(parents=True, exist_ok=True)
        collect.write(path, raw)
    return verify(target)


def rgb565(raw):
    score.require(len(raw) == 115200, 'wrong framebuffer size')
    rgb = bytearray()
    for pixel, in struct.iter_unpack('>H', raw):
        r, g, b = pixel >> 11, (pixel >> 5) & 63, pixel & 31
        rgb.extend(((r << 3) | (r >> 2), (g << 2) | (g >> 4), (b << 3) | (b >> 2)))
    return bytes(rgb)


def png(rgb, width=240, height=240):
    score.require(len(rgb) == width * height * 3, 'wrong RGB size')
    def chunk(tag, payload):
        return struct.pack('>I', len(payload)) + tag + payload + struct.pack('>I', zlib.crc32(tag + payload))
    rows = b''.join(b'\0' + rgb[i:i + width * 3] for i in range(0, len(rgb), width * 3))
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)) +
            chunk(b'IDAT', zlib.compress(rows, 9)) + chunk(b'IEND', b''))


def gallery(out, target, *, sheets_only=False):
    verify(out)
    score.require(not target.exists() and not target.is_symlink(), 'fresh gallery directory required')
    target.mkdir(parents=True)
    page = ['<!doctype html><meta charset="utf-8"><title>Garden population comparison</title>',
            '<style>body{background:#222;color:#eee;font:16px sans-serif}td,th{padding:5px}',
            'img{image-rendering:pixelated}table{border-collapse:collapse}caption{text-align:left}</style>',
            '<h1>Garden population comparison</h1><p>All 144 native captures; no selection. ',
            'Each table holds weather and layout fixed. Columns are frozen repair policies.</p>']
    for seed in score.SEEDS:
        for layout in score.LAYOUTS:
            page.append(f'<h2>{html.escape(seed)} — {html.escape(layout)}</h2><table><tr><th>Day</th>')
            page += [f'<th>{model}</th>' for model in score.MODELS]
            page.append('</tr>')
            sheet_rows = []
            for day in score.DAYS:
                page.append(f'<tr><th>{day}</th>')
                images = []
                for model in score.MODELS:
                    name = f'{model}-{seed}-{layout}-day{day}.png'
                    raw = (out / 'runs' / f'{model}-{seed}-{layout}-primary' / 'timeline' /
                           f'tick-{day * score.DAY:010d}.raw').read_bytes()
                    rgb = rgb565(raw)
                    images.append(rgb)
                    if not sheets_only:
                        collect.write(target / name, png(rgb))
                    page.append(f'<td><img src="{name}" width="240" height="240" alt="{model} day {day}"></td>')
                sheet_rows += [b''.join(im[row * 720:(row + 1) * 720] for im in images) for row in range(240)]
                page.append('</tr>')
            collect.write(target / f'{seed}-{layout}-sheet.png', png(b''.join(sheet_rows), 720, 1440))
            page.append('</table>')
    if not sheets_only:
        collect.write(target / 'index.html', '\n'.join(page).encode())


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ('verify', 'pack', 'unpack', 'gallery'):
        p = commands.add_parser(name)
        p.add_argument('source', type=Path)
        if name != 'verify':
            p.add_argument('target', type=Path)
        if name == 'gallery':
            p.add_argument('--sheets-only', action='store_true')
    args = parser.parse_args()
    if args.command == 'verify':
        verify(args.source)
    elif args.command == 'pack':
        print(package(args.source, args.target))
    elif args.command == 'unpack':
        unpack(args.source, args.target)
    else:
        gallery(args.source, args.target, sheets_only=args.sheets_only)
    print('Verified population evidence; no simulator execution.')
