#!/usr/bin/env python3

"""Native tests for device dense-render-profile output parsing."""

import importlib.util
from pathlib import Path
import sys
import unittest


sys.dont_write_bytecode = True
CONTAINER_DIR = Path(__file__).parents[1] / "container"
sys.path.insert(0, str(CONTAINER_DIR))
MODULE_PATH = CONTAINER_DIR / "render_profile.py"
MODULE_SPEC = importlib.util.spec_from_file_location("render_profile", MODULE_PATH)
if MODULE_SPEC is None or MODULE_SPEC.loader is None:
    raise RuntimeError(f"could not load {MODULE_PATH}")

render_profile = importlib.util.module_from_spec(MODULE_SPEC)
MODULE_SPEC.loader.exec_module(render_profile)


def profile_output(*, restored_crc32: str = "1234abcd", include_total: bool = True) -> str:
    lines = [
        "DISPLAY_PROFILE_BEGIN schema=2 samples=16 warmup=2 clock_hz=125000000 "
        "configured_spi_hz=20000000 width=240 height=240 bpp=2 transport=pio-dma cases=12"
    ]
    for name in sorted(render_profile.CASE_NAMES):
        coverage = int(name.split("-")[1])
        payload = 240 * 240 * 2 * coverage // 100
        regions = coverage if name.startswith("tiles") else 1
        writes = (
            regions
            if name.startswith(("tiles", "full", "dense"))
            else coverage // 4 + 1
        )
        lines.append(
            f"DISPLAY_PROFILE_CASE name={name} coverage={coverage} "
            f"payload_bytes={payload} regions={regions} writes={writes} synchronized=16 "
            "crc32=89abcdef"
        )
        for stage in sorted(render_profile.STAGE_NAMES):
            if stage == "total" and not include_total and name == "band-10":
                continue
            mean = 3000 if stage == "total" else 800
            lines.append(
                f"DISPLAY_PROFILE_STAGE name={name} stage={stage} samples=16 "
                f"mean_us={mean} min_us=500 p50_us=700 p95_us=900 p99_us=1000 "
                "max_us=3500"
            )
    for stage in sorted(render_profile.DENSE_STAGE_NAMES):
        lines.append(
            f"DISPLAY_PROFILE_DENSE_STAGE stage={stage} samples=16 "
            "mean_us=200 min_us=100 p50_us=150 p95_us=250 p99_us=300 max_us=350"
        )
    lines.extend(
        [
            "DISPLAY_PROFILE_VERIFY original_crc32=1234abcd "
            f"restored_crc32={restored_crc32} framebuffer_restored=yes",
            "DISPLAY_PROFILE_RESOURCE shell_stack_used_bytes=3000 shell_stack_size_bytes=4096",
            "DISPLAY_PROFILE_END status=ok",
        ]
    )
    return "\n".join(lines)


class RenderProfileTest(unittest.TestCase):
    def test_parses_complete_versioned_profile(self) -> None:
        result = render_profile.parse_profile(profile_output())

        self.assertEqual(result["schema_version"], 2)
        self.assertEqual(result["samples_per_case"], 16)
        self.assertEqual(result["display"]["transport"], "pio-dma")
        self.assertEqual(result["cases"]["full-100"]["payload_bytes"], 115200)
        self.assertEqual(result["cases"]["dense-100"]["display_writes_per_frame"], 1)
        self.assertEqual(result["cases"]["dense-100"]["final_framebuffer_crc32"], "89abcdef")
        self.assertEqual(
            result["cases"]["full-100"]["derived"][
                "configured_bus_ideal_payload_time_us"
            ],
            46080,
        )
        self.assertTrue(result["verification"]["framebuffer_restored"])
        self.assertTrue(
            result["cases"]["dense-100"]["derived"]["frame_rate_budgets"]["30_hz"][
                "meets_mean_budget"
            ]
        )
        self.assertEqual(
            result["dense_raster_breakdown"]["stages"]["boxes"]["mean_us"], 200
        )

    def test_accepts_pl022_dma_transport(self) -> None:
        output = profile_output().replace("transport=pio-dma", "transport=pl022-dma")

        result = render_profile.parse_profile(output)

        self.assertEqual(result["display"]["transport"], "pl022-dma")

    def test_rejects_missing_stage(self) -> None:
        with self.assertRaisesRegex(render_profile.RenderProfileError, "every timing stage"):
            render_profile.parse_profile(profile_output(include_total=False))

    def test_rejects_missing_dense_stage(self) -> None:
        output = "\n".join(
            line
            for line in profile_output().splitlines()
            if not line.startswith("DISPLAY_PROFILE_DENSE_STAGE stage=background ")
        )

        with self.assertRaisesRegex(render_profile.RenderProfileError, "every dense-render stage"):
            render_profile.parse_profile(output)

    def test_rejects_restore_checksum_mismatch(self) -> None:
        with self.assertRaisesRegex(render_profile.RenderProfileError, "does not match"):
            render_profile.parse_profile(profile_output(restored_crc32="76543210"))

    def test_parses_game_mode_amid_other_lines(self) -> None:
        output = "noise\nmode=paused tick=45 hash=1234abcd\ninput_source=remote"
        self.assertEqual(render_profile.parse_game_mode(output), "paused")


if __name__ == "__main__":
    unittest.main()
