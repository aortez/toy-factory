#!/usr/bin/env python3
"""Family-routing integration fixtures; no fitness, search or research panel."""

from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import zlib

from test_leaf_replay import model


def main(binary, shared, growth):
    with tempfile.TemporaryDirectory(prefix='toy-factory-leaf-family-') as folder:
        root = Path(folder)
        models = [root / 'wait.tlf', root / 'renew.tlf']
        for action, path in enumerate(models):
            path.write_bytes(model(action))

        modes = {'none': 1, 'all': 2, 'selective': 3, 'reserve-only': 4, 'productive': 5}

        def invoke(action=0, founder='1', resident='none', scenario='rainfed',
                   ticks='0', frame=None, valid=True, leaf=None):
            leaf = models[action] if leaf is None else leaf
            args = [binary, str(growth), str(leaf), '3c308d3b', scenario, ticks, founder, resident]
            if frame is not None:
                args.append(str(frame))
            result = subprocess.run(args, capture_output=True, timeout=40)
            if not valid:
                assert result.returncode != 0 and result.stdout == b'', result
                return None
            assert result.returncode == 0, result.stderr.decode()
            value = json.loads(result.stdout)
            assert value['schema'] == 'garden-leaf-family-replay-v1'
            assert value['controller_assignment'] == 'founder-family'
            assert value['objective'] is None and value['complete'] is True
            assert value['candidate_founder'] == int(founder) and value['resident_policy'] == resident
            assert value['ticks'] == int(ticks) and value['scenario'] == scenario
            assert value['seed'] == '3c308d3b' and value['gardener'] is False
            assert value['climate'] == 'seasonal'
            data = bytes.fromhex(value['state_hex'])
            founders = 3 if scenario == 'rainfed' else 5
            assert data[:8] == b'TFR1' + bytes((int(founder), modes[resident], founders, 0))
            count, = struct.unpack_from('<I', data, 8)
            assert data[12:12 + count] == bytes(value['family_roots'])
            assert len(data) == 12 + count + 5293
            nested = data[12 + count:]
            assert nested[:4] == b'TLR1' and nested[4:176] == model(action)
            assert value['leaf_model_hex'] == model(action).hex()
            roots = {lineage: lineage for lineage in range(1, founders + 1)}
            assert len(value['lineages']) == count
            for record in value['lineages']:
                lineage, parent = record['id'], record['parent']
                if parent != 0:
                    assert 0 < parent < lineage
                    roots[lineage] = roots[parent]
                else:
                    assert lineage <= founders
                assert value['family_roots'][lineage - 1] == roots[lineage]
            if frame is None:
                assert value['framebuffer_crc32'] is None
            else:
                pixels = frame.read_bytes()
                assert len(pixels) == 115200
                assert value['framebuffer_crc32'] == f'{zlib.crc32(pixels):08x}'
            return value

        for scenario in ('rainfed', 'rainfed-crowded'):
            # All legal founder roles are explicit, never inferred from species/slot.
            founders = 3 if scenario == 'rainfed' else 5
            states = [invoke(founder=str(i), scenario=scenario) for i in range(1, founders + 1)]
            for value in states:
                assert value['lineages'] == states[0]['lineages']
                assert value['state_hex'][10:] == states[0]['state_hex'][10:]
            invoke(founder=str(founders + 1), scenario=scenario, valid=False)
        for resident in modes:
            invoke(resident=resident)

        def prefix(action, frame=None):
            return invoke(action=action, ticks='7680', founder='2', frame=frame)

        serial = [prefix(action) for action in (0, 1)]
        with ThreadPoolExecutor(max_workers=2) as pool:
            concurrent = list(pool.map(prefix, (1, 0)))
        assert concurrent == list(reversed(serial))
        captured = prefix(1, root / 'frame.raw')
        assert captured | {'framebuffer_crc32': None} == serial[1]
        assert serial[0]['state_hex'] != serial[1]['state_hex']
        # Neutral family routing must be exactly the shared WAIT run, including
        # W2 memory, rendering-independent state, and complete lifetime/seed ledgers.
        result = subprocess.run([shared, str(growth), str(models[0]), '3c308d3b',
            'rainfed', '7680'], capture_output=True, timeout=40)
        assert result.returncode == 0, result.stderr.decode()
        expected = json.loads(result.stdout)
        family = serial[0].copy()
        count = len(family.pop('family_roots'))
        family['state_hex'] = family['state_hex'][(12 + count) * 2:]
        family['schema'] = expected['schema']
        family['controller_assignment'] = expected['controller_assignment']
        del family['candidate_founder'], family['resident_policy']
        assert family == expected

        for founder in ('', '0', '-1', '+1', '01', '1.0', '256', '99999999'):
            invoke(founder=founder, valid=False)
        for resident in ('', 'NONE', 'unknown', '5'):
            invoke(resident=resident, valid=False)
        invoke(scenario='unknown', valid=False)
        invoke(ticks='2334721', valid=False)
        bad = root / 'bad.tlf'
        bad.write_bytes(model(0)[:-1])
        invoke(leaf=bad, valid=False)
        protected = root / 'protected.raw'
        protected.write_bytes(b'preserve')
        invoke(frame=protected, valid=False)
        assert protected.read_bytes() == b'preserve'
        link = root / 'link.raw'
        link.symlink_to(protected)
        invoke(frame=link, valid=False)
        assert protected.read_bytes() == b'preserve'
    print('Family CLI: founder/resident identity, ancestry ledger, neutral biology, capture/concurrency and rejection checks passed.')


if __name__ == '__main__':
    main(str(Path(sys.argv[1]).resolve()), str(Path(sys.argv[2]).resolve()), Path(sys.argv[3]).resolve())
