#!/usr/bin/env python3
"""Checked/owned equivalence across models, founder roles, captures and archives."""

from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import zlib

from test_leaf_replay import model
from test_leaf_family import main as family_contract


def light_model():
    data = bytearray(model(0))
    struct.pack_into('<i', data, 28, -63)
    data[61] = 1  # First hidden unit's LIGHT weight.
    data[164] = 1  # RENEW reads that unit; WAIT retains bias one.
    struct.pack_into('<I', data, 12, zlib.crc32(data[16:]))
    return bytes(data)


def main(owned, checked, shared, growth, reference):
    family_contract(owned, shared, growth)
    with tempfile.TemporaryDirectory(prefix='toy-factory-leaf-owned-') as folder:
        root = Path(folder)
        models = [root / f'model-{i}.tlf' for i in range(3)]
        for path, data in zip(models, (model(0), model(1), light_model()), strict=True):
            path.write_bytes(data)

        def invoke(binary, action, layout, founder, ticks=7680, frame=None):
            args = [binary, growth, str(models[action]), '3c308d3b', layout,
                    str(ticks), str(founder), 'selective']
            if frame is not None:
                args.append(str(frame))
            child = subprocess.run(args, capture_output=True, timeout=40)
            assert child.returncode == 0 and not child.stderr, child.stderr.decode()
            value = json.loads(child.stdout)
            assert value['complete'] is True and value['ticks'] == ticks
            return child.stdout

        expected = {}
        for layout, count in (('rainfed', 3), ('rainfed-crowded', 5)):
            for founder in range(1, count + 1):
                for action in range(3):
                    key = action, layout, founder
                    expected[key] = invoke(checked, *key)
                    assert invoke(owned, *key) == expected[key], key
        choices = ((0, 'rainfed', 1), (2, 'rainfed-crowded', 5))
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda key: invoke(owned, *key), reversed(choices)))
        assert results == [expected[key] for key in reversed(choices)]
        frame = root / 'owned.raw'
        key = choices[1]
        captured = json.loads(invoke(owned, *key, frame=frame))
        pixels = frame.read_bytes()
        assert len(pixels) == 115200
        assert captured['framebuffer_crc32'] == f'{zlib.crc32(pixels):08x}'
        assert captured | {'framebuffer_crc32': None} == json.loads(expected[key])
        checked_frame = root / 'checked.raw'
        assert json.loads(invoke(checked, *key, frame=checked_frame)) == captured
        assert checked_frame.read_bytes() == pixels
        archived = json.loads(Path(reference).read_text())['prefix_stdout']
        assert invoke(owned, 0, 'rainfed', 1, ticks=61440).decode() == archived['wait-normal']
        assert invoke(owned, 1, 'rainfed-crowded', 5, ticks=61440).decode() == archived['renew-crowded']
    print('Owned CLI: inherited family contract, 24 checked pairs, nonconstant model, all roles, '
          'concurrency, exact pixels and both archived 16-day prefixes passed.')


if __name__ == '__main__':
    main(*(str(Path(arg).resolve()) for arg in sys.argv[1:]))
