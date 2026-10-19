"""Headless SDL interaction, capture safety, and speed-independent simulation."""

import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib

PLAYER, REPLAY = map(lambda p: str(Path(p).resolve()), sys.argv[1:3])
del sys.argv[1:3]


def decode_png(raw):
    """Independent RGB/RGBA8 PNG check, including all five scanline filters."""
    if raw[:8] != b'\x89PNG\r\n\x1a\n':
        raise ValueError('not PNG')
    offset, chunks = 8, []
    while offset < len(raw):
        size, = struct.unpack_from('>I', raw, offset)
        kind, data = raw[offset + 4:offset + 8], raw[offset + 8:offset + 8 + size]
        crc, = struct.unpack_from('>I', raw, offset + 8 + size)
        if zlib.crc32(kind + data) != crc:
            raise ValueError('PNG CRC differs')
        chunks.append((kind, data))
        offset += 12 + size
    width, height, bits, color, compression, filtering, interlaced = struct.unpack('>IIBBBBB', chunks[0][1])
    if (width, height, bits, compression, filtering, interlaced) != (240, 240, 8, 0, 0, 0) or color not in (2, 6):
        raise ValueError('unexpected PNG format')
    channels = 3 if color == 2 else 4
    stride = width * channels
    data = zlib.decompress(b''.join(data for kind, data in chunks if kind == b'IDAT'))
    if len(data) != height * (stride + 1):
        raise ValueError('PNG size differs')
    previous, output = bytearray(stride), bytearray()
    for row in range(height):
        filter_type = data[row * (stride + 1)]
        current = bytearray(data[row * (stride + 1) + 1:(row + 1) * (stride + 1)])
        for i in range(stride):
            left = current[i - channels] if i >= channels else 0
            above = previous[i]
            corner = previous[i - channels] if i >= channels else 0
            prediction = left + above - corner
            paeth = min((left, above, corner), key=lambda v: abs(prediction - v))
            correction = (0, left, above, (left + above) // 2, paeth)[filter_type]
            current[i] = (current[i] + correction) & 255
        for i in range(0, stride, channels):
            output.extend(current[i:i + 3])
            if channels == 4 and current[i + 3] != 255:
                raise ValueError('unexpected transparency')
        previous = current
    return bytes(output)


def rgb(raw):
    result = bytearray()
    for value, in struct.iter_unpack('>H', raw):
        r, g, b = value >> 11, (value >> 5) & 63, value & 31
        result.extend(((r << 3) | (r >> 2), (g << 2) | (g >> 4), (b << 3) | (b >> 2)))
    return bytes(result)


class PlayerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='research-player-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def run_player(self, *args, success=True):
        process = subprocess.run([PLAYER, *map(str, args)], capture_output=True,
            env=os.environ | {'SDL_VIDEODRIVER': 'dummy'}, timeout=20)
        self.assertEqual(process.returncode == 0, success, process.stderr)
        return process

    def reference(self, model, ticks, founder=1, layout='rainfed'):
        path = self.root / f'{model}-{ticks}-{founder}.raw'
        result = subprocess.run([REPLAY, model, '58d7d6ca', layout, str(ticks), str(founder), str(path)],
                                capture_output=True, check=True, timeout=20)
        return result.stdout, path.read_bytes()

    def verify_capture(self, folder, stdout, raw):
        self.assertEqual((folder / 'frame.raw').read_bytes(), raw)
        self.assertEqual((folder / 'state.json').read_bytes(), stdout)
        self.assertEqual(decode_png((folder / 'frame.png').read_bytes()), rgb(raw))
        manifest = json.loads((folder / 'manifest.json').read_bytes())
        self.assertEqual(manifest['framebuffer_crc32'], f'{zlib.crc32(raw):08x}')
        self.assertEqual(manifest['archive_sha256'],
            '5dc495ec0e33f83c121b1c6eaa09603033bd824476e175c8a72f347ef272744f')

    def test_paused_capture_and_no_overwrite(self):
        reference, pixels = self.reference('initial', 0)
        for _ in range(2):
            result = self.run_player('--paused', '--frames', 1, '--capture-on-exit', '--capture-dir', self.root)
            self.assertEqual(result.stdout, reference)
        captures = list(self.root.glob('shot-*'))
        self.assertEqual(len(captures), 2)
        for folder in captures:
            self.verify_capture(folder, reference, pixels)

    def test_actual_event_controls_and_reset(self):
        reference, _ = self.reference('initial', 0)
        view = self.root / 'viewer.png'
        result = self.run_player('--test-controls', '--test-view', view)
        self.assertEqual(result.stdout, reference)
        before = view.read_bytes()
        self.assertEqual(struct.unpack_from('>II', before, 16), (720, 942))
        result = self.run_player('--test-controls', '--test-view', view, success=False)
        self.assertEqual(result.stdout, b'')
        self.assertEqual(view.read_bytes(), before)

    def test_highlight_preserves_every_policy_capture(self):
        for model in ('initial', 's1-g3-c4', 's2-g3-c1'):
            with self.subTest(model=model):
                reference, pixels = self.reference(model, 61440, 4, 'rainfed-crowded')
                for highlight in (False, True):
                    folder = self.root / f'{model}-{highlight}'
                    extra = ('--highlight-family',) if highlight else ()
                    result = self.run_player('--policy', model, '--layout', 'rainfed-crowded',
                        '--founder', 4, '--speed', 'max', '--stop-tick', 61440,
                        '--capture-on-exit', '--capture-dir', folder, *extra)
                    self.assertEqual(result.stdout, reference)
                    self.verify_capture(next(folder.glob('shot-*')), reference, pixels)

    def test_every_policy_and_speed_matches_headless(self):
        for model in ('initial', 's1-g3-c4', 's2-g3-c1'):
            reference, _ = self.reference(model, 3840)
            for speed in ('16', '256', 'max'):
                with self.subTest(model=model, speed=speed):
                    result = self.run_player('--policy', model, '--speed', speed, '--stop-tick', 3840)
                    self.assertEqual(result.stdout, reference)

    def test_normal_speed_matches_headless(self):
        reference, _ = self.reference('initial', 30)
        result = self.run_player('--speed', 1, '--stop-tick', 30)
        self.assertEqual(result.stdout, reference)

    def test_crowded_founder_and_mature_png(self):
        reference, pixels = self.reference('s1-g3-c4', 61440, 4, 'rainfed-crowded')
        result = self.run_player('--policy', 's1-g3-c4', '--layout', 'rainfed-crowded', '--founder', 4,
            '--speed', 'max', '--stop-tick', 61440, '--capture-on-exit', '--capture-dir', self.root)
        self.assertEqual(result.stdout, reference)
        self.verify_capture(next(self.root.glob('shot-*')), reference, pixels)

    def test_invalid_conditions_and_horizon(self):
        for args in (('--seed', '00000001'), ('--founder', '4'), ('--founder', '0'),
                     ('--policy', 'anything'), ('--speed', '2'), ('--stop-tick', '5283841'),
                     ('--frames', '-1'), ('--seed',), ('--unexpected', '1'),
                     ('--test-view', str(self.root / 'not-created.png'))):
            with self.subTest(args=args):
                self.run_player(*args, success=False)

    def test_whole_population_capture_and_overlay(self):
        for model in ('initial', 's1-g3-c4', 's2-g3-c1'):
            reference, pixels = self.reference(model, 61440, 'all', 'rainfed-crowded')
            record = json.loads(reference)
            self.assertEqual(record['controller_assignment'], 'whole-population')
            self.assertIsNone(record['candidate_founder'])
            self.assertIsNone(record['resident_policy'])
            for highlight in (False, True):
                folder = self.root / f'population-{model}-{highlight}'
                extra = ('--highlight-family',) if highlight else ()
                result = self.run_player('--policy', model, '--layout', 'rainfed-crowded',
                    '--founder', 'all', '--speed', 'max', '--stop-tick', 61440,
                    '--capture-on-exit', '--capture-dir', folder, *extra)
                self.assertEqual(result.stdout, reference)
                self.verify_capture(next(folder.glob('shot-*')), reference, pixels)

    def test_capture_rejects_symlink_directory(self):
        target = self.root / 'target'
        target.mkdir()
        alias = self.root / 'alias'
        alias.symlink_to(target, target_is_directory=True)
        result = self.run_player('--paused', '--frames', 1, '--capture-on-exit', '--capture-dir', alias,
                                 success=False)
        self.assertEqual(result.stdout, b'')
        self.assertEqual(list(target.iterdir()), [])


if __name__ == '__main__':
    unittest.main()
