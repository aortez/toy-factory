#!/usr/bin/env python3
"""Check shard coverage, real CTest execution, and the workflow's merge gate."""

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import yaml

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("ctest_shard", ROOT / "scripts/container/ctest-shard.py")
sharder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sharder)


class PartitionTests(unittest.TestCase):
    def test_every_test_occurs_exactly_once_including_new_tests(self):
        for count in (1, 7, 166, 238, 239):
            names = [f"test-{index}" for index in range(count)]
            for shards in range(1, min(count, 8) + 1):
                parts = [sharder.partition(names, shard, shards)
                         for shard in range(1, shards + 1)]
                self.assertTrue(all(parts))
                combined = [name for part in parts for name in part]
                self.assertCountEqual(combined, names)
                self.assertEqual(len(set(combined)), count)

    def test_invalid_or_empty_partitions_fail(self):
        for names, shard, shards in (([], 1, 1), (["a", "a"], 1, 1),
                                     (["a"], 0, 1), (["a"], 2, 1),
                                     (["a"], 1, 0), (["a"], 1, 2)):
            with self.subTest(names=names, shard=shard, shards=shards):
                with self.assertRaises(ValueError):
                    sharder.partition(names, shard, shards)

    def test_disabled_tests_are_not_silently_ignored(self):
        value = {"tests": [{"name": "hidden", "properties": [
            {"name": "DISABLED", "value": True}]}]}
        with patch.object(sharder.subprocess, "check_output", return_value=json.dumps(value)):
            with self.assertRaisesRegex(ValueError, "disabled"):
                sharder.inventory(Path("build"))

    def test_unexpected_ctest_selection_fails_before_execution(self):
        with patch.object(sharder, "inventory", side_effect=[["a", "b"], ["b"]]), \
                patch.object(sharder.subprocess, "run") as execute:
            with self.assertRaisesRegex(ValueError, "index selection"):
                sharder.run(Path("build"), 1, 2, Path("unused-output"))
            execute.assert_not_called()


class ExecutionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="ctest shard ")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.build = self.root / "build"

    def configure(self, fail=False):
        source = self.root / "source"
        source.mkdir()
        lines = ["cmake_minimum_required(VERSION 3.20)", "project(shard_fixture NONE)",
                 "enable_testing()"]
        for index, name in enumerate(("case one", "case[2]", "case-three", "case-four")):
            code = 7 if fail and index == 2 else 0
            lines.append(f'add_test(NAME "{name}" COMMAND "{sys.executable}" '
                         f'"-c" "raise SystemExit({code})")')
        (source / "CMakeLists.txt").write_text("\n".join(lines) + "\n")
        subprocess.run(["cmake", "-S", str(source), "-B", str(self.build)],
                       check=True, capture_output=True, text=True)

    def test_real_ctest_shards_cover_inventory_and_record_timings(self):
        self.configure()
        found = []
        for index in (1, 2):
            output = self.root / f"reports-{index}"
            self.assertEqual(sharder.run(self.build, index, 2, output), 0)
            receipt = json.loads((output / "inventory.json").read_text())
            self.assertFalse(receipt["dry_run"])
            found += receipt["selected"]
            sharder.verify_report(output / "results.xml", receipt["selected"])
        self.assertCountEqual(found, sharder.inventory(self.build))

    def test_real_failure_is_propagated_and_report_retained(self):
        self.configure(fail=True)
        output = self.root / "failure"
        self.assertNotEqual(sharder.run(self.build, 1, 2, output), 0)
        self.assertTrue((output / "results.xml").exists())

    def test_dry_run_does_not_execute_tests(self):
        self.configure(fail=True)
        output = self.root / "dry"
        self.assertEqual(sharder.run(self.build, 1, 2, output, dry_run=True), 0)
        self.assertFalse((output / "results.xml").exists())
        self.assertTrue(json.loads((output / "inventory.json").read_text())["dry_run"])

    def test_previous_report_cannot_mask_missing_execution(self):
        self.configure()
        output = self.root / "stale"
        self.assertEqual(sharder.run(self.build, 1, 2, output), 0)
        names = sharder.inventory(self.build)
        with patch.object(sharder, "inventory", side_effect=[names, names[::2]]), \
                patch.object(sharder.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)):
            with self.assertRaises(FileNotFoundError):
                sharder.run(self.build, 1, 2, output)

    def test_bad_reports_fail(self):
        report = self.root / "bad.xml"
        for body in ('<testcase name="other"/>', '<testcase name="a"/><testcase name="a"/>',
                     '<testcase name="a"><skipped/></testcase>',
                     '<testcase name="a"><failure/></testcase>',
                     '<testcase name="a"><error/></testcase>',
                     '<testcase name="a" status="notrun"/>', ''):
            report.write_text(f"<testsuite>{body}</testsuite>")
            with self.subTest(body=body), self.assertRaises(ValueError):
                sharder.verify_report(report, ["a"])


class WorkflowTests(unittest.TestCase):
    def test_every_matrix_shard_is_required_and_keeps_failure_evidence(self):
        jobs = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text())["jobs"]
        for name, shards in (("native-tests", 6), ("garden-research", 3)):
            job = jobs[name]
            self.assertFalse(job["strategy"]["fail-fast"])
            self.assertEqual(job["strategy"]["matrix"]["shard"], list(range(1, shards + 1)))
            commands = [step.get("run", "") for step in job["steps"]]
            runners = [command for command in commands if "ctest-shard.py" in command]
            self.assertEqual(len(runners), 1)
            self.assertIn(f"--shards {shards}", runners[0])
            self.assertIn("--shard ${{ matrix.shard }}", runners[0])
            self.assertNotIn("--dry-run", runners[0])
            self.assertFalse(any(step.get("continue-on-error") for step in job["steps"]))
            uploads = [step for step in job["steps"] if "actions/upload-artifact@" in step.get("uses", "")]
            self.assertEqual(len(uploads), 1)
            self.assertEqual(uploads[0]["if"], "always()")
        gate = jobs["complete"]
        self.assertEqual(gate["if"], "always()")
        self.assertCountEqual(gate["needs"], set(jobs) - {"complete"})
        self.assertIn('job["result"] != "success"', gate["steps"][0]["run"])
        self.assertIn("sys.exit(1)", gate["steps"][0]["run"])

    def test_gate_rejects_failure_cancellation_skips_and_missing_results(self):
        jobs = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text())["jobs"]
        command = jobs["complete"]["steps"][0]["run"]
        green = {name: {"result": "success"} for name in jobs["complete"]["needs"]}
        cases = [(green, 0), ({}, 1)]
        for status in ("failure", "cancelled", "skipped"):
            cases.append(({**green, "native-tests": {"result": status}}, 1))
        for results, expected in cases:
            process = subprocess.run(["bash", "-e", "-c", command], capture_output=True,
                                     text=True, env={**os.environ, "RESULTS": json.dumps(results)})
            self.assertEqual(process.returncode, expected, process.stdout + process.stderr)

    @unittest.skipUnless(ROOT == Path("/workspace/app"), "container wrapper uses /workspace/app")
    def test_research_build_only_keeps_the_build_but_does_not_run_ctest(self):
        with tempfile.TemporaryDirectory(prefix="research-wrapper-") as tmp:
            for tool in ("cmake", "ctest"):
                stub = Path(tmp) / tool
                stub.write_text(f"#!{sys.executable}\nimport json,sys\nprint(json.dumps(sys.argv))\n")
                stub.chmod(0o755)
            env = {**os.environ, "PATH": tmp + os.pathsep + os.environ["PATH"]}
            for args in ([], ["--build-only"], ["--unknown"]):
                result = subprocess.run(["bash", str(ROOT / "scripts/container/host-research-check.sh"),
                                         *args], env=env, capture_output=True, text=True)
                if args == ["--unknown"]:
                    self.assertEqual(result.returncode, 2)
                    self.assertEqual(result.stdout, "")
                    continue
                self.assertEqual(result.returncode, 0, result.stderr)
                commands = [json.loads(line) for line in result.stdout.splitlines()]
                self.assertEqual(len(commands), 2 if args else 3)
                self.assertEqual(Path(commands[0][0]).name, "cmake")
                self.assertEqual(commands[1][1], "--build")
                if not args:
                    self.assertEqual(Path(commands[2][0]).name, "ctest")
                    self.assertEqual(commands[2][-2:], ["--parallel", "2"])


if __name__ == "__main__":
    unittest.main()
