#!/usr/bin/env python3
"""Run an exact, disjoint slice of the configured CTest inventory.

Sharding changes scheduling only. No test-name allowlist or historical timing
file can silently omit a newly registered test. Each runner executes serially
because some archive-corruption tests use several GiB of memory.
"""

import argparse
from collections import Counter
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET


def partition(names, shard, shards):
    if not names or len(set(names)) != len(names):
        raise ValueError("CTest inventory must be nonempty with unique names")
    if not 1 <= shard <= shards <= len(names):
        raise ValueError("require 1 <= shard <= shards <= number of tests")
    return names[shard - 1::shards]


def inventory(build_dir, selection=None):
    command = ["ctest", "--test-dir", str(build_dir), "--show-only=json-v1"]
    if selection is not None:
        command += ["--tests-information", selection]
    value = json.loads(subprocess.check_output(command, text=True))
    tests = value["tests"]
    for test in tests:
        if any(prop["name"] == "DISABLED" and prop["value"]
               for prop in test.get("properties", [])):
            raise ValueError("disabled CTest entry: " + test["name"])
    return [test["name"] for test in tests]


def verify_report(path, selected):
    cases = ET.parse(path).getroot().findall(".//testcase")
    actual = [case.attrib["name"] for case in cases]
    if Counter(actual) != Counter(selected):
        raise ValueError("JUnit results do not match the selected CTest inventory")
    if any(case.attrib.get("status") == "notrun" or
           any(case.find(tag) is not None for tag in ("skipped", "failure", "error"))
           for case in cases):
        raise ValueError("a selected CTest entry did not pass")


def run(build_dir, shard, shards, output_dir, dry_run=False):
    names = inventory(build_dir)
    selected = partition(names, shard, shards)
    selection = f"{shard},{len(names)},{shards}"
    if inventory(build_dir, selection) != selected:
        raise ValueError("CTest's index selection differs from the planned shard")

    output_dir.mkdir(parents=True, exist_ok=True)
    receipt = {"shard": shard, "shards": shards, "inventory": names,
               "selected": selected, "dry_run": dry_run}
    (output_dir / "inventory.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(f"Shard {shard}/{shards}: {len(selected)} of {len(names)} tests", flush=True)
    if dry_run:
        return 0

    # A fresh report path prevents a previous successful run from masking a
    # crash or an invocation that exits without actually executing its tests.
    with tempfile.TemporaryDirectory(prefix=".ctest-", dir=output_dir) as tmp:
        report = Path(tmp) / "results.xml"
        result = subprocess.run([
            "ctest", "--test-dir", str(build_dir), "--output-on-failure",
            "--parallel", "1", "--no-tests=error",
            "--tests-information", selection, "--output-junit", str(report),
        ], check=False)
        if report.exists():
            (output_dir / "results.xml").write_bytes(report.read_bytes())
        if result.returncode:
            return result.returncode
        verify_report(report, selected)
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-dir", type=Path, required=True)
    parser.add_argument("--shard", type=int, required=True, help="one-based index")
    parser.add_argument("--shards", type=int, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        return run(args.build_dir.resolve(), args.shard, args.shards,
                   args.output_dir.resolve(), args.dry_run)
    except (ValueError, OSError, KeyError, ET.ParseError, subprocess.CalledProcessError) as exc:
        print(f"CTest shard failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
