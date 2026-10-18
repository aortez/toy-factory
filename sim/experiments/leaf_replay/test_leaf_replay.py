#!/usr/bin/env python3
"""Saved-model replay smoke fixtures, not controller selection or a research panel."""

from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import zlib


def model(action):
    payload = struct.pack('<4sHHBBBB', b'LFN1', 1, 1, 0, 0, 0, 0)
    payload += bytes(8 * 4 + 88)
    payload += struct.pack('<2i', int(action == 0), int(action == 1)) + bytes(16)
    return struct.pack('<4sHHII', b'TLF1', 1, 16, len(payload), zlib.crc32(payload)) + payload


def main(binary, growth):
    with tempfile.TemporaryDirectory(prefix='toy-factory-leaf-replay-') as folder:
        root = Path(folder)
        paths = [root / 'wait.tlf', root / 'renew.tlf']
        for action, path in enumerate(paths):
            path.write_bytes(model(action))

        def invoke(leaf=paths[0], seed='3c308d3b', scenario='rainfed', ticks='0', frame=None,
                   growth_path=growth, valid=True):
            args = [binary, str(growth_path), str(leaf), seed, scenario, ticks]
            if frame is not None:
                args.append(str(frame))
            result = subprocess.run(args, capture_output=True, timeout=40)
            if not valid:
                assert result.returncode != 0 and result.stdout == b'', result
                return None
            assert result.returncode == 0, result.stderr.decode()
            value = json.loads(result.stdout)
            assert value['schema'] == 'garden-leaf-neural-replay-v1' and value['complete'] is True
            assert value['controller_assignment'] == 'shared-diagnostic' and value['objective'] is None
            assert value['seed'] == seed and value['ticks'] == int(ticks) and value['scenario'] == scenario
            assert value['climate'] == 'seasonal' and value['gardener'] is False
            leaf_data = leaf.read_bytes()
            assert value['leaf_model_hex'] == leaf_data.hex()
            state = bytes.fromhex(value['state_hex'])
            assert len(state) == 5293 and state[:4] == b'TLR1' and state[4:176] == leaf_data
            assert state[176:181] == b'GMR1\x01' and state[193:197] == b'GMS1'
            assert (frame is None) == (value['framebuffer_crc32'] is None)
            if frame is not None:
                pixels = frame.read_bytes()
                assert len(pixels) == 115200 and value['framebuffer_crc32'] == f'{zlib.crc32(pixels):08x}'
            return value

        # Match the archived scenario labels, rejecting guessed aliases.
        labels = ('rainfed', 'rainfed-crowded')
        for label in labels:
            reset = invoke(scenario=label)
            other = invoke(leaf=paths[1], scenario=label)
            assert reset['state_hex'][352:] == other['state_hex'][352:]
            assert reset['lineages'] == other['lineages']

        # A short real-W2 smoke prefix. Rendering and process concurrency may not
        # change biology, memory, identity or lifetime/seed ledgers.
        def prefix(action, frame=None):
            return invoke(leaf=paths[action], ticks='7680', frame=frame)
        serial = [prefix(action) for action in (0, 1)]
        with ThreadPoolExecutor(max_workers=2) as pool:
            concurrent = list(pool.map(prefix, (1, 0)))
        assert concurrent == list(reversed(serial))
        captured = prefix(1, root / 'frame.raw')
        assert captured | {'framebuffer_crc32': None} == serial[1]
        assert serial[0]['state_hex'][352:] != serial[1]['state_hex'][352:]

        for seed in ('', '00000000', '0x3c308d3b', '3C308D3B', '123', 'fffffffff'):
            invoke(seed=seed, valid=False)
        for ticks in ('', '-1', '+1', '01', '2334721', '999999999999', '1.0'):
            invoke(ticks=ticks, valid=False)
        invoke(scenario='unknown', valid=False)
        for data in (b'', model(0)[:-1], model(0) + b'\0', model(0)[:20] + b'\xff' + model(0)[21:]):
            bad = root / 'bad.tlf'
            bad.write_bytes(data)
            invoke(leaf=bad, valid=False)
        invoke(leaf=root / 'missing', valid=False)
        invoke(leaf=root, valid=False)
        link = root / 'link.tlf'
        link.symlink_to(paths[0])
        invoke(leaf=link, valid=False)
        fifo = root / 'fifo.tlf'
        os.mkfifo(fifo)
        invoke(leaf=fifo, valid=False)
        bad_growth = root / 'bad.tgl'
        changed = bytearray(growth.read_bytes())
        changed[-1] ^= 1
        bad_growth.write_bytes(changed)
        invoke(growth_path=bad_growth, valid=False)
        protected = root / 'protected.raw'
        protected.write_bytes(b'preserve')
        invoke(frame=protected, valid=False)
        assert protected.read_bytes() == b'preserve'
        frame_link = root / 'frame-link.raw'
        frame_link.symlink_to(protected)
        invoke(frame=frame_link, valid=False)
        assert protected.read_bytes() == b'preserve'
    print('Leaf replay CLI: exact model/state identity, W2 prefixes, capture/concurrency equivalence, invalid inputs and no-overwrite passed.')


if __name__ == '__main__':
    main(str(Path(sys.argv[1]).resolve()), Path(sys.argv[2]).resolve())
