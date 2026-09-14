#!/usr/bin/env python3
"""Verify the frozen seed-bank bundle and export its compact comparison."""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]/"sim"))
import garden_seed_bank as bank


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, default=bank.experiment.ROOT/"artifacts/garden-seed-bank")
    parser.add_argument("--reanalyze", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = args.bundle.resolve()
    m = bank.experiment.read_json(root/"manifest.json")
    bank.require(m["status"] == "complete" and m["kind"] == "garden-seed-bank"
                 and m["expected_runs"] == 8, "wrong/incomplete bundle")
    for name in m["artifacts"]:
        bank.establishment.verified(root, m, name)
    summary = bank.experiment.read_json(root/"summary.json")
    bank.require(len(summary["runs"]) == 8 and len(summary["prefixes"]) == 4, "incomplete panel")
    for small in summary["runs"]:
        key = small["key"]
        r = bank.experiment.read_json(root/f"analyses/{key}.json")
        bank.require(bank.compact(r) == small, "summary mismatch")
        if args.reanalyze:
            bounds = bank.experiment.read_json(root/f"analyses/{key}.boundaries.json")
            a = bank.analyze(root/f"traces/{key}.world.gz", root/f"traces/{key}.sites.gz",
                             bounds, r["bank"], r["side"])
            audit = bank.attempts.analyze(root/f"traces/{key}.attempts.gz", root/f"traces/{key}.world.gz",
                root/f"traces/{key}.sites.gz", bounds, r["attempts"]["header"])
            bank.require(a == r["analysis"] and audit == r["attempts"], "reanalyzed result changed")
        print(key, small["lifetimes"]["late_born"])
    if args.output:
        bank.require(not args.output.exists(), "output exists")
        bank.experiment.write_json(args.output, summary | {
            "manifest_sha256": bank.experiment.digest(root/"manifest.json")})
    print(f"Verified {len(m['artifacts'])} artifacts; manifest {bank.experiment.digest(root/'manifest.json')}")


if __name__ == "__main__":
    main()
