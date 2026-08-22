#!/usr/bin/env python3

"""Native tests for device physics-profile output parsing."""

import contextlib
import importlib.util
import io
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


def profile_output(
    *,
    schema: int = 10,
    fixture: str = "canonical",
    chain_links: int = 0,
    states_match: str = "yes",
) -> str:
    fixture_fields = (
        f" fixture={fixture} chain_links={chain_links}" if schema >= 4 else ""
    )
    lines = [
        f"PROFILE_BEGIN schema={schema}{fixture_fields} "
        "ticks=2000 warmup=120 clock_hz=125000000 "
        "histogram_fine_bin_us=32 histogram_fine_bins=64 "
        "histogram_coarse_bin_us=128 histogram_coarse_bins=64 clock_delta_cycles=4"
    ]
    for mode, final_hash, total_mean in (
        ("grid", "1234abcd", 400),
        ("reference", "1234abcd", 800),
    ):
        if schema >= 5:
            quality_field = (
                " max_revolute_anchor_error_q16=98304"
                " max_revolute_limit_violation_q16=4096"
            )
            if schema >= 6:
                quality_field += (
                    " max_prismatic_lateral_error_q16=32768"
                    " max_prismatic_angular_error_q16=2048"
                    " max_prismatic_limit_violation_q16=1024"
                )
            if schema >= 10:
                quality_field += " max_rope_segment_error_q16=16384"
        elif schema == 4:
            quality_field = " max_revolute_error_q16=98304"
        else:
            quality_field = ""
        lines.append(
            f"PROFILE_MODE mode={mode} hash={final_hash} "
            f"clock_reads_min=56 clock_reads_max=56{quality_field}"
        )
        for stage in sorted(profile_compare.STAGE_NAMES_BY_SCHEMA[schema]):
            mean = total_mean if stage == "total" else 20
            lines.append(
                f"PROFILE_STAGE mode={mode} stage={stage} samples=2000 "
                f"mean_us={mean} min_us=10 p50_us=32 p95_us=64 p99_us=96 "
                "max_us=120 budget_violations=0"
            )
        for metric in sorted(profile_compare.WORK_NAMES_BY_SCHEMA[schema]):
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

        self.assertEqual(result["schema_version"], 10)
        self.assertEqual(result["fixture"], "canonical")
        self.assertEqual(result["chain_link_count"], 0)
        self.assertEqual(result["measured_ticks_per_mode"], 2000)
        self.assertEqual(result["modes"]["grid"]["stages"]["total"]["mean_us"], 400)
        self.assertEqual(
            result["modes"]["grid"]["work"]["possible_pairs"]["mean_per_tick"],
            76.0,
        )
        self.assertEqual(result["clock"]["estimated_read_overhead_us_per_step"], 1.792)
        self.assertEqual(result["resources"]["shell_stack_used_bytes"], 2704)
        self.assertEqual(
            result["modes"]["grid"]["quality"]["maximum_revolute_anchor_error_pixels"],
            1.5,
        )
        self.assertEqual(
            result["modes"]["grid"]["quality"][
                "maximum_revolute_limit_violation_radians"
            ],
            0.0625,
        )
        self.assertEqual(
            result["modes"]["grid"]["quality"]["maximum_prismatic_lateral_error_pixels"],
            0.5,
        )
        self.assertEqual(
            result["modes"]["grid"]["quality"]["maximum_prismatic_angular_error_radians"],
            0.03125,
        )
        self.assertEqual(
            result["modes"]["grid"]["quality"][
                "maximum_prismatic_limit_violation_pixels"
            ],
            0.015625,
        )
        self.assertEqual(
            result["modes"]["grid"]["quality"]["maximum_rope_segment_error_pixels"],
            0.25,
        )
        self.assertTrue(result["verification"]["states_match"])

    def test_accepts_legacy_schema_two_profile(self) -> None:
        result = profile_compare.parse_profile(profile_output(schema=2))

        self.assertEqual(result["schema_version"], 2)
        self.assertNotIn("revolute_joints", result["modes"]["grid"]["work"])
        self.assertNotIn("solver_cached_contacts", result["modes"]["grid"]["work"])

    def test_accepts_legacy_schema_three_profile(self) -> None:
        result = profile_compare.parse_profile(profile_output(schema=3))

        self.assertEqual(result["schema_version"], 3)
        self.assertEqual(result["fixture"], "canonical")
        self.assertIn("revolute_joints", result["modes"]["grid"]["work"])

    def test_accepts_legacy_schema_four_profile(self) -> None:
        result = profile_compare.parse_profile(profile_output(schema=4))

        self.assertEqual(result["schema_version"], 4)
        self.assertNotIn("revolute_motors", result["modes"]["grid"]["work"])

    def test_schema_five_includes_motor_and_limit_work(self) -> None:
        result = profile_compare.parse_profile(profile_output(schema=5))

        work = result["modes"]["grid"]["work"]
        self.assertIn("revolute_motors", work)
        self.assertIn("joint_motor_solver_visits", work)
        self.assertIn("joint_limit_solver_visits", work)

    def test_schema_six_includes_prismatic_work(self) -> None:
        result = profile_compare.parse_profile(profile_output(schema=6))

        work = result["modes"]["grid"]["work"]
        self.assertIn("prismatic_joints", work)
        self.assertIn("prismatic_motors", work)
        self.assertIn("prismatic_limits", work)
        self.assertIn("solver_cached_contacts", work)

    def test_schema_seven_includes_sensor_and_event_work(self) -> None:
        result = profile_compare.parse_profile(profile_output(schema=7))

        work = result["modes"]["grid"]["work"]
        self.assertIn("body_sensor_tests", work)
        self.assertIn("active_contact_pairs", work)
        self.assertIn("sensor_overlaps", work)
        self.assertIn("contact_begin_events", work)
        self.assertIn("contact_stay_events", work)
        self.assertIn("contact_end_events", work)
        self.assertIn("narrow_body_sensor", result["modes"]["grid"]["stages"])

    def test_schema_eight_includes_sleep_work(self) -> None:
        result = profile_compare.parse_profile(profile_output(schema=8))

        work = result["modes"]["grid"]["work"]
        self.assertIn("awake_bodies", work)
        self.assertIn("sleeping_bodies", work)
        self.assertIn("body_sleep_transitions", work)
        self.assertIn("body_wake_transitions", work)
        self.assertIn("sleeping_contacts", work)
        self.assertIn("sleeping_joints", work)

    def test_schema_nine_includes_spring_and_conveyor_work(self) -> None:
        result = profile_compare.parse_profile(profile_output(schema=9))

        work = result["modes"]["grid"]["work"]
        self.assertIn("spring_joints", work)
        self.assertIn("spring_solver_visits", work)
        self.assertIn("spring_solver_changes", work)
        self.assertIn("conveyor_contacts", work)
        self.assertIn("conveyor_solver_visits", work)
        self.assertIn("conveyor_solver_changes", work)

    def test_schema_ten_includes_rope_stage_and_work(self) -> None:
        result = profile_compare.parse_profile(profile_output())

        work = result["modes"]["grid"]["work"]
        self.assertIn("rope", result["modes"]["grid"]["stages"])
        self.assertIn("ropes", work)
        self.assertIn("rope_particles", work)
        self.assertIn("rope_solver_iterations", work)
        self.assertIn("rope_constraint_visits", work)
        self.assertIn("rope_constraint_changes", work)

    def test_parses_revolute_chain_fixture(self) -> None:
        result = profile_compare.parse_profile(
            profile_output(fixture="revolute_chain", chain_links=8)
        )

        self.assertEqual(result["fixture"], "revolute_chain")
        self.assertEqual(result["chain_link_count"], 8)

    def test_parses_neutral_canonical_fixture(self) -> None:
        result = profile_compare.parse_profile(profile_output(fixture="canonical_neutral"))

        self.assertEqual(result["fixture"], "canonical_neutral")
        self.assertEqual(result["chain_link_count"], 0)

    def test_rejects_invalid_fixture_metadata(self) -> None:
        with self.assertRaisesRegex(profile_compare.ProfileError, "zero chain links"):
            profile_compare.parse_profile(profile_output(chain_links=4))

    def test_parses_chain_link_list_and_builds_scaling_result(self) -> None:
        link_counts = profile_compare.parse_chain_link_counts("4,6,8")
        cases = {
            str(link_count): profile_compare.parse_profile(
                profile_output(fixture="revolute_chain", chain_links=link_count)
            )
            for link_count in link_counts
        }
        result = profile_compare.chain_scaling_result(link_counts, 2000, cases)

        self.assertEqual(result["link_counts"], [4, 6, 8])
        self.assertEqual(result["cases"]["8"]["chain_link_count"], 8)

    def test_chain_summary_reports_position_and_velocity_visits(self) -> None:
        case = profile_compare.parse_profile(
            profile_output(fixture="revolute_chain", chain_links=4)
        )
        result = profile_compare.chain_scaling_result([4], 2000, {"4": case})
        output = io.StringIO()

        with contextlib.redirect_stdout(output):
            profile_compare.print_chain_summary(result, Path("profile.json"))

        self.assertIn("pos/vel visits", output.getvalue())
        self.assertIn("15/15", output.getvalue())

    def test_rejects_duplicate_chain_link_count(self) -> None:
        with self.assertRaisesRegex(profile_compare.ProfileError, "duplicates"):
            profile_compare.parse_chain_link_counts("4,4")

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
