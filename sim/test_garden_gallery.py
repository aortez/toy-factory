#!/usr/bin/env python3
"""Check exact saved-model visual replay, PNGs, frozen galleries, and failure handling."""

import argparse
import copy
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib

import garden_gallery as gallery


def run(command, expected=0):
    result = subprocess.run([str(v) for v in command], capture_output=True, text=True)
    if result.returncode != expected:
        raise RuntimeError(f"{command}: {result.returncode}, expected {expected}\n{result.stderr}")
    return result.stdout


def json_run(command):
    return json.loads(run(command))


def decode_png(path):
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    offset, compressed = 8, b""
    width = height = 0
    while offset < len(data):
        size = struct.unpack_from(">I", data, offset)[0]
        kind = data[offset + 4:offset + 8]
        value = data[offset + 8:offset + 8 + size]
        crc = struct.unpack_from(">I", data, offset + 8 + size)[0]
        assert zlib.crc32(kind + value) == crc
        if kind == b"IHDR":
            width, height, depth, color, comp, filt, interlace = struct.unpack(">IIBBBBB", value)
            assert (depth, color, comp, filt, interlace) == (8, 2, 0, 0, 0)
        elif kind == b"IDAT":
            compressed += value
        offset += 12 + size
    scanlines = zlib.decompress(compressed)
    stride = width * 3 + 1
    assert len(scanlines) == stride * height
    assert all(scanlines[y * stride] == 0 for y in range(height))
    return width, height, b"".join(scanlines[y * stride + 1:(y + 1) * stride] for y in range(height))


class UnitTests(unittest.TestCase):
    def test_checkpoint_bounds(self):
        self.assertEqual(gallery.checkpoints(92160, []), [480, 2880, 92160])
        self.assertEqual(gallery.checkpoints(120, []), [120])
        self.assertEqual(gallery.checkpoints(3840, [0, 60, 60]), [0, 60])
        for requested in ([-1], [3841], list(range(7))):
            with self.assertRaises(RuntimeError):
                gallery.checkpoints(3840, requested)

    def test_unsafe_artifact_paths(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = {"artifacts": {"../escape": "irrelevant", "/etc/passwd": "irrelevant"}}
            for name in manifest["artifacts"]:
                with self.assertRaises(RuntimeError):
                    gallery.artifact(root, manifest, name)


def integration(args):
    with tempfile.TemporaryDirectory(prefix="garden-visual-test-") as temporary:
        root = Path(temporary)
        model = root / "model.tgm"
        run([args.trainer, "--generations", "0", "--trials", "1", "--ticks", "60",
             "--seed", "0x1234", "--output", model, "--c-output", root / "model.c"])
        model_before = model.read_bytes()
        native = [args.replayer, "-", "rainfed", "adaptive", "0x1234", "--ticks", "17"]
        result = json_run(native)
        assert result["tick"] == 17 and result["framebuffer_crc32"] is None
        run([args.replayer, "--help"])
        for bad in ("", "0", "-1", "+1", " 1", "4294967296", "1junk"):
            command = native.copy()
            command[4] = bad
            run(command, 2)
        for bad in ("-1", "983041", "4294967296", "1x", ""):
            run([*native[:-1], bad], 2)
        run([*native, "--ticks", "17"], 2)
        run([*native, "--unknown", "foo"], 2)
        run(native[:-1], 2)
        run([*native[:2], "unknown", *native[3:]], 2)
        run([native[0], model, *native[2:]], 2)
        run([native[0], "-", native[2], "unknown", *native[4:]], 2)
        assert json_run([*native[:-1], "100000"])["tick"] == 100000

        for policy in ("adaptive", "baseline", "neural-reference", "neural-candidate"):
            for scenario in ("rainfed", "rainfed-crowded"):
                for tick in (0, 17, 2880):
                    command = [args.replayer, model if policy == "neural-candidate" else "-",
                               scenario, policy, "0x1234", "--ticks", str(tick)]
                    plain = json_run(command)
                    path = root / f"{policy}-{scenario}-{tick}.raw"
                    captured = json_run([*command, "--framebuffer", path])
                    raw = path.read_bytes()
                    assert len(raw) == gallery.FRAME_BYTES
                    assert captured["framebuffer_crc32"] == f"{zlib.crc32(raw):08x}"
                    assert {**captured, "framebuffer_crc32": None} == plain
                    again = root / "again.raw"
                    repeated = json_run([*command, "--framebuffer", again])
                    assert repeated == captured and again.read_bytes() == raw
                    again.unlink()
                    run([*command, "--framebuffer", path], 1)
                    assert path.read_bytes() == raw
        assert model.read_bytes() == model_before
        run([*native, "--framebuffer", root / "absent" / "frame.raw"], 1)
        run([*native, "--framebuffer", ""], 2)
        corrupt = root / "corrupt.tgm"
        corrupt.write_bytes(model_before[:-1] + bytes([model_before[-1] ^ 1]))
        target = root / "should-not-exist.raw"
        run([args.replayer, corrupt, "rainfed", "neural-candidate", "1", "--ticks", "60",
             "--framebuffer", target], 1)
        assert not target.exists()

        # Use the maintained collector, not a hand-authored report or expected hash.
        bundle = root / "experiment"
        run([sys.executable, gallery.ROOT / "sim/garden_experiments.py", "--output", bundle,
             "--candidate-model", model, "--cycles", "1", "--trials", "1", "--trace-pairs", "1",
             "--evaluator", args.evaluator, "--inspector", args.inspector])
        original = {p.relative_to(bundle): hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in bundle.rglob("*") if p.is_file()}
        script = gallery.ROOT / "sim/garden_gallery.py"
        output = root / "gallery"
        command = [sys.executable, script, "--bundle", bundle, "--output", output,
                   "--replayer", args.replayer]
        run(command)
        run([sys.executable, output / "tools/garden_gallery.py", "--verify", output])
        manifest = json.loads((output / "manifest.json").read_text())
        frames = json.loads((output / "frames.json").read_text())
        assert manifest["status"] == "complete" and len(frames["frames"]) == 12
        assert manifest["panel_selection"].startswith("first recorded seed")
        assert frames["contact_sheet"]["width"] == 752 and frames["contact_sheet"]["height"] == 1000
        sw, sh, sheet = decode_png(output / "contact-sheet.png")
        assert (sw, sh) == (752, 1000)
        for index, frame in enumerate(frames["frames"]):
            raw = (output / frame["framebuffer"]).read_bytes()
            width, height, rgb = decode_png(output / frame["png"])
            assert (width, height) == (240, 240) and rgb == gallery.rgb565be_to_rgb888(raw)
            row, column = divmod(index, 3)
            for y in range(240):
                start = ((8 + row * 248 + y) * sw + 8 + column * 248) * 3
                assert sheet[start:start + 720] == rgb[y * 720:(y + 1) * 720]
        assert {p.relative_to(bundle): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in bundle.rglob("*") if p.is_file()} == original
        before = (output / "manifest.json").read_bytes()
        run(command, 1)
        assert before == (output / "manifest.json").read_bytes()

        # Native replay must reject a changed model, CRC, or timeline identity.
        frame = frames["frames"][0]
        bad = copy.deepcopy(frame["reference"])
        bad["hash"] = "ffffffff"
        with unittest.TestCase().assertRaises(RuntimeError):
            gallery.check_frame(frame["result"], bad, frame["model_crc32"],
                                (output / frame["framebuffer"]).read_bytes())
        with unittest.TestCase().assertRaises(RuntimeError):
            gallery.check_frame(frame["result"], frame["reference"], frame["model_crc32"], b"")
        with unittest.TestCase().assertRaises(RuntimeError):
            gallery.check_frame(frame["result"], frame["reference"], "bad",
                                (output / frame["framebuffer"]).read_bytes())

        for index, options in enumerate((["--checkpoint", "17"], ["--seed", "ffffffff"])):
            invalid = root / f"invalid-panel-{index}"
            run([sys.executable, script, "--bundle", bundle, "--output", invalid,
                 "--replayer", args.replayer, *options], 1)
            assert not invalid.exists()
        missing = root / "missing-checkpoint"
        run([sys.executable, script, "--bundle", bundle, "--output", missing,
             "--checkpoint", "17"], 1)
        assert not missing.exists()
        failed = root / "failed"
        run([sys.executable, script, "--bundle", bundle, "--output", failed,
             "--replayer", args.evaluator], 1)
        assert (failed / "failure.json").exists() and not (failed / "manifest.json").exists()
        png = output / frames["frames"][0]["png"]
        png.write_bytes(png.read_bytes() + b"tampered")
        run([sys.executable, script, "--verify", output], 1)
        source_manifest = bundle / "manifest.json"
        doc = json.loads(source_manifest.read_text())
        doc["split"] = "test"
        source_manifest.write_text(json.dumps(doc))
        forbidden = root / "untouched-test"
        run([sys.executable, script, "--bundle", bundle, "--output", forbidden], 1)
        assert not forbidden.exists()

    print("Saved-model capture, evaluator hashes, exact PNG pixels, frozen replay and failures passed")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("replayer", "evaluator", "trainer", "inspector"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    for name in ("replayer", "evaluator", "trainer", "inspector"):
        setattr(args, name, getattr(args, name).resolve())
    result = unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromTestCase(UnitTests))
    if not result.wasSuccessful():
        return 1
    integration(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
