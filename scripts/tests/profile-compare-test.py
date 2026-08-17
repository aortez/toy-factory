#!/usr/bin/env python3

"""Native tests for device physics-profile output parsing."""

import importlib.util
from pathlib import Path
import sys
import unittest


sys.dont_write_bytecode = True
CONTAINER_DIR = Path(__file__).parents[1] / "container"
sys.path.insert(0, str(CONTAINER_DIR))
MODULE_PATH = CONTAINER_DIR / "profile_compare.py"
MODULE_SPEC = importlib.util.spec_from_file_location("profile_compare", MODULE_PATH)
if MODULE_SPEC is None or MODULE_SPEC.loader is None:
    raise RuntimeError(f"could not load {MODULE_PATH}")

profile_compare = importlib.util.module_from_spec(MODULE_SPEC)
MODULE_SPEC.loader.exec_module(profile_compare)


def profile_output(*, states_match: str = "yes") -> str:
    lines = [
        "PROFILE_BEGIN schema=1 ticks=2000 warmup=120 clock_hz=125000000 "
        "histogram_fine_bin_us=32 histogram_fine_bins=64 "
        "histogram_coarse_bin_us=128 histogram_coarse_bins=64 clock_delta_cycles=4"
    ]
    for mode, final_hash, total_mean in (
        ("grid", "1234abcd", 400),
        ("reference", "1234abcd", 800),
    ):
        lines.append(
            f"PROFILE_MODE mode={mode} hash={final_hash} "
            "clock_reads_min=46 clock_reads_max=46"
        )
        for stage in sorted(profile_compare.STAGE_NAMES):
            mean = total_mean if stage == "total" else 20
            lines.append(
                f"PROFILE_STAGE mode={mode} stage={stage} samples=2000 "
                f"mean_us={mean} min_us=10 p50_us=32 p95_us=64 p99_us=96 "
                "max_us=120 budget_violations=0"
            )
        for metric in sorted(profile_compare.WORK_NAMES):
            total = 152000 if metric == "possible_pairs" else 30000
            lines.append(
                f"PROFILE_WORK mode={mode} metric={metric} total={total} max=76"
            )
    lines.append("PROFILE_RESOURCE shell_stack_used_bytes=2704 shell_stack_size_bytes=4096")
    lines.append(f"PROFILE_END hashes_match=yes states_match={states_match}")
    return "\n".join(lines)


class ProfileCompareTest(unittest.TestCase):
    def test_parses_complete_versioned_profile(self) -> None:
        result = profile_compare.parse_profile(profile_output())

        self.assertEqual(result["schema_version"], 1)
        self.assertEqual(result["measured_ticks_per_mode"], 2000)
        self.assertEqual(result["modes"]["grid"]["stages"]["total"]["mean_us"], 400)
        self.assertEqual(
            result["modes"]["grid"]["work"]["possible_pairs"]["mean_per_tick"],
            76.0,
        )
        self.assertEqual(result["clock"]["estimated_read_overhead_us_per_step"], 1.472)
        self.assertEqual(result["resources"]["shell_stack_used_bytes"], 2704)
        self.assertTrue(result["verification"]["states_match"])

    def test_rejects_missing_stage(self) -> None:
        output = "\n".join(
            line
            for line in profile_output().splitlines()
            if not ("mode=grid stage=other " in line)
        )
        with self.assertRaisesRegex(profile_compare.ProfileError, "every timing stage"):
            profile_compare.parse_profile(output)

    def test_rejects_state_mismatch(self) -> None:
        with self.assertRaisesRegex(profile_compare.ProfileError, "identical authoritative state"):
            profile_compare.parse_profile(profile_output(states_match="no"))

    def test_parses_game_mode_amid_other_lines(self) -> None:
        output = "noise\nmode=paused tick=45 hash=1234abcd\ninput_source=remote"
        self.assertEqual(profile_compare.parse_game_mode(output), "paused")


if __name__ == "__main__":
    unittest.main()
