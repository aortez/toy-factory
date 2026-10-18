#!/usr/bin/env python3
"""Portable matched-control evidence and independent score/pixel verification."""

import argparse
import gzip
import hashlib
import json
import math
from pathlib import Path
import struct
import zlib

import run_leaf_controls as panel

SCHEMA = 'garden-leaf-family-controls-evidence-v1'
require = panel.require


def sha(data):
    return hashlib.sha256(data).hexdigest()


def png_rgb(data, width, height):
    """Decode the fixed RGB8/no-filter PNGs made by the repository renderer."""
    require(0 < width <= 2048 and 0 < height <= 2048 and data[:8] == b'\x89PNG\r\n\x1a\n', 'invalid PNG')
    chunks, offset = [], 8
    while offset < len(data):
        require(offset + 12 <= len(data), 'truncated PNG chunk')
        length, = struct.unpack_from('>I', data, offset)
        require(offset + 12 + length <= len(data), 'truncated PNG payload')
        kind = data[offset + 4:offset + 8]
        payload = data[offset + 8:offset + 8 + length]
        crc, = struct.unpack_from('>I', data, offset + 8 + length)
        require(crc == zlib.crc32(kind + payload), 'PNG CRC mismatch')
        chunks.append((kind, payload))
        offset += length + 12
    require([kind for kind, _ in chunks] == [b'IHDR', b'IDAT', b'IEND'] and chunks[2][1] == b'',
            'unsupported PNG chunks')
    require(chunks[0][1] == struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0), 'PNG dimensions/format differ')
    expected = height * (1 + width * 3)
    decoder = zlib.decompressobj()
    pixels = decoder.decompress(chunks[1][1], expected + 1)
    require(decoder.eof and not decoder.unused_data and not decoder.unconsumed_tail and len(pixels) == expected,
            'PNG scanline size differs')
    stride = 1 + width * 3
    require(all(pixels[y * stride] == 0 for y in range(height)), 'unsupported PNG filter')
    return b''.join(pixels[y * stride + 1:(y + 1) * stride] for y in range(height))


def expected_sheet(rows, rgb):
    width, height = 752, len(rows) * 248 + 8
    result = bytearray(bytes((32, 36, 42)) * width * height)
    for row, labels in enumerate(rows):
        require(len(labels) == 3, 'wrong sheet columns')
        for column, label in enumerate(labels):
            for y in range(240):
                start = ((8 + row * 248 + y) * width + 8 + column * 248) * 3
                result[start:start + 720] = rgb[label][y * 720:(y + 1) * 720]
    return bytes(result)


def verify(bundle):
    require(bundle['schema'] == SCHEMA, 'wrong evidence schema')
    result, runs = bundle['result'], bundle['runs']
    scope, calls = result['scope'], panel.plan()
    require(scope['rule'] == panel.RULE and scope['calls'] == calls and scope['maximum_native_calls'] == 48 and
            scope['maximum_parallel_processes'] == 2 and scope['timeout_seconds'] == 180 and
            scope['automatic_retry'] is False and scope['training_runs'] == 0 and scope['selected_model'] is None,
            'scope differs')
    require(result['training_runs'] == 0 and result['selected_model'] is None and result['exact_prior_anchors'] is True,
            'incomplete diagnostic')
    require(scope['baseline_sha256'] == panel.BASELINE_SHA == panel.digest(panel.BASELINE) and
            scope['followup_test_build_sha256'] == panel.TEST_BUILD_SHA, 'baseline/test identity differs')
    baseline = panel.evidence.verify(json.loads(gzip.decompress(panel.BASELINE.read_bytes())))
    identities = scope['identities']
    require(identities == baseline['result']['scope']['identities'], 'runtime identity differs')
    require(set(bundle['source_text']) == set(scope['source_sha256']) and
            all(sha(text.encode()) == scope['source_sha256'][path] for path, text in bundle['source_text'].items()),
            'source snapshot differs')
    require(set(runs) == set(result['receipts']) == {c['label'] for c in calls}, 'missing or extra runs')
    values, rgb, used_frames, used_pngs = {}, {}, set(), set()
    gallery = result['gallery']
    require(gallery['columns'] == list(panel.MODELS) and set(gallery['frames']) == set(runs), 'gallery roster differs')
    for call in calls:
        label, case = call['label'], call['case']
        row, checked = runs[label], result['receipts'][label]
        started, process = row['started'], row['process']
        require(started['call'] == call and started['binary_sha256'] == identities['owned_binary_sha256'],
                'call binding differs')
        args = started['args']
        root = Path(args[1]).parent
        require(Path(args[0]).name == 'leaf-family-owned' and args[1] == str(root / 'growth.tgl') and
                args[2] == str(root / (case['model'] + '.tlf')) and args[3:] ==
                [case['seed'], case['scenario'], str(608 * panel.replay.DAY), str(case['founder']),
                 panel.replay.RESIDENT, str(root / label / 'frame.raw')], 'command differs')
        stdout, stderr = row['stdout'].encode(), row['stderr'].encode()
        require(process['returncode'] == 0 and process['timed_out'] is False and not stderr and
                process['stdout_sha256'] == sha(stdout) and process['stdout_bytes'] == len(stdout) and
                process['stderr_sha256'] == sha(stderr) and process['stderr_bytes'] == 0 and
                all(checked.get(k) == v for k, v in process.items()), 'process receipt differs')
        elapsed = process['elapsed_seconds']
        require(type(elapsed) in (int, float) and math.isfinite(elapsed) and elapsed > 0, 'invalid timing')
        frame_sha = checked['framebuffer_sha256']
        pixels = bytes.fromhex(bundle['frames'][frame_sha])
        require(sha(pixels) == frame_sha, 'raw frame differs')
        value = panel.replay.check_output(json.loads(stdout), call, identities['growth_model_sha256'], pixels)
        require(checked['logic_ticks_per_second'] == value['ticks'] / elapsed and
                checked['lineages'] == len(value['lineages']) and checked['seeds'] == len(value['seeds']),
                'derived receipt differs')
        values[label] = value
        used_frames.add(frame_sha)
        frame = gallery['frames'][label]
        require(frame['png'] == label + '/frame.png' and frame['framebuffer_sha256'] == frame_sha,
                'PNG/frame binding differs')
        png = bytes.fromhex(bundle['pngs'][frame['sha256']])
        require(sha(png) == frame['sha256'], 'PNG hash differs')
        rgb[label] = png_rgb(png, 240, 240)
        require(rgb[label] == panel.rgb565be_to_rgb888(pixels), 'PNG does not render recorded pixels')
        used_pngs.add(frame['sha256'])
    require(result['analysis'] == panel.analyze(values), 'scores or diagnostics differ')
    expected_keys = {seed + '-' + layout for seed in panel.SEEDS for layout, _ in panel.LAYOUTS}
    require(set(gallery['sheets']) == expected_keys, 'sheet roster differs')
    for seed in panel.SEEDS:
        for layout, count in panel.LAYOUTS:
            key = seed + '-' + layout
            sheet = gallery['sheets'][key]
            rows = [[f'{key}-f{founder}-{model}' for model in panel.MODELS] for founder in range(1, count + 1)]
            require(sheet['rows'] == rows and sheet['width'] == 752 and sheet['height'] == count * 248 + 8 and
                    sheet['gap'] == 8 and sheet['path'] == f'gallery/{key}/contact-sheet.png', 'sheet layout differs')
            png = bytes.fromhex(bundle['pngs'][sheet['sha256']])
            require(sha(png) == sheet['sha256'] and
                    png_rgb(png, sheet['width'], sheet['height']) == expected_sheet(rows, rgb), 'sheet pixels differ')
            used_pngs.add(sheet['sha256'])
    require(set(bundle['frames']) == used_frames and set(bundle['pngs']) == used_pngs, 'unreferenced images')
    for case in panel.replay.CASES:
        label = f'{case["seed"]}-{case["scenario"]}-f{case["founder"]}-{case["model"]}'
        old = 'owned-' + case['name']
        require(runs[label]['stdout'] == baseline['runs'][old]['stdout'] and
                result['receipts'][label]['framebuffer_sha256'] == baseline['result']['receipts'][old]['framebuffer_sha256'],
                'prior exact anchor differs')
    return bundle


def collect(root):
    require(not (root / 'failure.json').exists(), 'failed attempt cannot publish success')
    result = panel.read(root / 'result.json')
    require(result['scope'] == panel.read(root / 'started.json'), 'scope changed')
    source = {}
    for name, expected in result['scope']['source_sha256'].items():
        path = Path(name)
        require(not path.is_absolute() and '..' not in path.parts, 'unsafe source path')
        raw = (root / 'source' / path).read_bytes()
        require(sha(raw) == expected, 'frozen source changed')
        source[name] = raw.decode()
    runs, frames, pngs = {}, {}, {}
    for call in result['scope']['calls']:
        folder, label = root / call['label'], call['label']
        require(panel.read(folder / 'checked.json') == result['receipts'][label], 'checked receipt changed')
        runs[label] = dict(started=panel.read(folder / 'started.json'), process=panel.read(folder / 'process.json'),
                           stdout=(folder / 'stdout.json').read_text(), stderr=(folder / 'stderr.txt').read_text())
        raw = (folder / 'frame.raw').read_bytes()
        frames[sha(raw)] = raw.hex()
        png = (folder / 'frame.png').read_bytes()
        pngs[sha(png)] = png.hex()
    for seed in panel.SEEDS:
        for layout, _ in panel.LAYOUTS:
            path = root / 'gallery' / (seed + '-' + layout) / 'contact-sheet.png'
            png = path.read_bytes()
            pngs[sha(png)] = png.hex()
    return verify(dict(schema=SCHEMA, result=result, runs=runs, frames=frames, pngs=pngs, source_text=source))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--check', type=Path)
    args = parser.parse_args()
    if args.check is not None:
        require(args.source is None and args.out is None, 'check cannot collect')
        verify(json.loads(gzip.decompress(args.check.read_bytes())))
    else:
        require(args.source is not None and args.out is not None, 'source and fresh output required')
        value = collect(args.source)
        raw = (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode()
        with args.out.open('xb') as stream:
            stream.write(gzip.compress(raw, mtime=0))
    print('All 48 match bindings, exact scores, anchors, native PNGs and gallery pixels verify without simulation.')


if __name__ == '__main__':
    main()
