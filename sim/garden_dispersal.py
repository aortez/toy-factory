#!/usr/bin/env python3
"""Compare matched narrow/wide scattering bundles, without training or changing firmware."""

import argparse
from pathlib import Path
import sys

import garden_experiments as experiment
import garden_ecology as ecology
import garden_renewal as renewal
from garden_resources import require


def validate_pair(narrow: dict, wide: dict) -> None:
    ecology.validate_pair(narrow, wide, experiment.WIDE_ENVIRONMENT)


def compare(narrow: Path, wide: Path, late_cycles: int) -> dict:
    manifests = [experiment.read_json(path / "manifest.json") for path in (narrow, wide)]
    validate_pair(*manifests)
    data = {name: renewal.summarize(path, late_cycles)
            for name, path in (("narrow", narrow), ("wide", wide))}
    pairs = ecology.paired_metrics(data["narrow"], data["wide"], "narrow", "wide")
    return {"schema_version": 1, "kind": "garden-dispersal-comparison",
            "analysis_sha256": experiment.digest(Path(__file__)),
            "notes": ["Only compiled scattering support differs; model weights and policy probes are fixed.",
                      "Counts are exploratory, paired by seed/layout/policy, not independent replicates.",
                      "Late lifetime qualifications are not a late-born offspring cohort.",
                      "A full-cycle survivor or durable parent can subsequently die."],
            **data, "pairs": pairs}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--narrow", type=Path, required=True)
    parser.add_argument("--wide", type=Path, required=True)
    parser.add_argument("--late-cycles", type=int, default=8)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        require(not args.output.exists(), "output already exists")
        result = compare(args.narrow.resolve(), args.wide.resolve(), args.late_cycles)
        experiment.write_json(args.output, result)
        print(f"Compared {len(result['pairs'])} matched worlds: {args.output}")
    except (OSError, RuntimeError, KeyError, ValueError, TypeError) as error:
        print(f"Dispersal comparison failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
