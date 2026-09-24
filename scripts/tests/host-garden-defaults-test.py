#!/usr/bin/env python3
"""Keep ordinary host builds free of stale Garden research options."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
HELPER = ROOT / "scripts/container/host-garden-defaults.sh"


def default_options():
    return subprocess.check_output(
        ["bash", "-eu", "-c", 'source "$1"; printf "%s\\n" "${garden_default_cmake_options[@]}"',
         "garden-defaults", str(HELPER)], text=True).splitlines()


class HostGardenDefaultsTest(unittest.TestCase):
    def test_defaults_cover_every_declared_research_switch(self):
        declared = re.findall(r'^option\((TOY_FACTORY_GARDEN_\w+) "[^"]*" (ON|OFF)\)',
                              (ROOT / "sim/CMakeLists.txt").read_text(), re.MULTILINE)
        self.assertTrue(declared)
        self.assertTrue(all(value == "OFF" for _, value in declared))
        expected = {f"-D{name}=OFF" for name, _ in declared}
        options = default_options()
        self.assertEqual(set(options), expected)
        self.assertEqual(len(options), len(expected))

    @unittest.skipUnless(ROOT == Path("/workspace/app"), "container build wrappers use /workspace/app")
    def test_all_three_wrappers_pass_the_complete_reset(self):
        with tempfile.TemporaryDirectory(prefix="garden-build-wrapper-") as tmp:
            stub = Path(tmp) / "cmake"
            stub.write_text(f"#!{sys.executable}\nimport json,sys\nprint(json.dumps(sys.argv[1:]))\n")
            stub.chmod(0o755)
            env = {**os.environ, "PATH": tmp + os.pathsep + os.environ["PATH"]}
            for script in ("host-build.sh", "host-player-build.sh", "host-profile-build.sh"):
                result = subprocess.run(["bash", str(ROOT / "scripts/container" / script)],
                                        env=env, cwd=ROOT, capture_output=True, text=True, timeout=20)
                self.assertEqual(result.returncode, 0, result.stderr)
                commands = [json.loads(line) for line in result.stdout.splitlines()]
                self.assertEqual(len(commands), 2)
                self.assertEqual([arg for arg in commands[0] if arg.startswith("-DTOY_FACTORY_GARDEN_")],
                                 default_options())
                self.assertEqual(commands[1][0], "--build")

    def test_real_cached_research_configuration_is_cleared(self):
        # No compile, training or removal of the user's ordinary build trees.
        with tempfile.TemporaryDirectory(prefix="garden-build-cache-") as tmp:
            command = ["cmake", "-S", str(ROOT / "sim"), "-B", tmp, "-G", "Ninja"]
            enabled = ["WIDE_DISPERSAL", "WATER_HEADROOM", "COMBINED_EXPERIMENT",
                       "LARGE_POOL", "LEAF_MAINTENANCE"]
            for options in ([f"-DTOY_FACTORY_GARDEN_{name}=ON" for name in enabled], default_options()):
                result = subprocess.run([*command, *options], capture_output=True, text=True, timeout=60)
                self.assertEqual(result.returncode, 0, result.stderr)
            flags = re.findall(r"^(TOY_FACTORY_GARDEN_\w+):BOOL=(\w+)$",
                               (Path(tmp) / "CMakeCache.txt").read_text(), re.MULTILINE)
            self.assertEqual({f"-D{name}={value}" for name, value in flags}, set(default_options()))


if __name__ == "__main__":
    unittest.main()
