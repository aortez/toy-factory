#!/usr/bin/env python3
"""Complete the four-condition uptake × scattering comparison without training."""

import argparse
from pathlib import Path
import sys

import garden_ecology as ecology
import garden_experiments as experiment
import garden_renewal as renewal
from garden_resources import require

ENVIRONMENTS = {"baseline": experiment.ENVIRONMENT, "wide": experiment.WIDE_ENVIRONMENT,
                "capped": experiment.WATER_ENVIRONMENT, "combined": experiment.COMBINED_ENVIRONMENT}


def contrasts(data: dict) -> dict:
    require(data.keys() == ENVIRONMENTS.keys(), "require all four conditions")
    pairs = {name: ecology.paired_metrics(data["baseline"], data[name], "baseline", name)
             for name in ("wide", "capped", "combined")}
    identities = lambda rows: [(r["scenario"], r["policy"], r["seed"]) for r in rows]
    require(identities(pairs["wide"]) == identities(pairs["capped"]) == identities(pairs["combined"]),
            "factorial trial identities differ")
    interactions = []
    for wide, capped, combined in zip(pairs["wide"], pairs["capped"], pairs["combined"], strict=True):
        common = wide["delta"].keys() & capped["delta"].keys() & combined["delta"].keys()
        interactions.append({"scenario": wide["scenario"], "policy": wide["policy"], "seed": wide["seed"],
                             "delta": {k: combined["delta"][k] - wide["delta"][k] - capped["delta"][k]
                                       for k in sorted(common)}})
    return {"versus_baseline": pairs,
            "combined_versus_wide": ecology.paired_metrics(data["wide"], data["combined"], "wide", "combined"),
            "combined_versus_capped": ecology.paired_metrics(data["capped"], data["combined"], "capped", "combined"),
            "interaction": interactions}


def compare(paths: dict[str, Path], late_cycles: int) -> dict:
    require(paths.keys() == ENVIRONMENTS.keys(), "require all four conditions")
    manifests = {name: experiment.read_json(path / "manifest.json") for name, path in paths.items()}
    for name in ("wide", "capped", "combined"):
        ecology.validate_pair(manifests["baseline"], manifests[name], ENVIRONMENTS[name])
    data = {name: renewal.summarize(path, late_cycles) for name, path in paths.items()}
    return {"schema_version": 1, "kind": "garden-ecology-factorial", "conditions": data,
            "analysis_sha256": {Path(module.__file__).name: experiment.digest(Path(module.__file__))
                                for module in (sys.modules[__name__], ecology, experiment, renewal)},
            "notes": ["Same seeds/layouts/policies across four conditions; exploratory, not independent replications.",
                      "Interaction = combined - wide - capped + baseline on each metric's raw scale.",
                      "This descriptive interaction is not statistical significance or a guarantee of biological synergy.",
                      "Survival counts need eligible-cohort denominators; late qualifications are not late-born cohorts."],
            **contrasts(data)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ENVIRONMENTS:
        parser.add_argument("--"+name, type=Path, required=True)
    parser.add_argument("--late-cycles", type=int, default=8)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        require(not args.output.exists(), "output already exists")
        result = compare({name: getattr(args, name).resolve() for name in ENVIRONMENTS}, args.late_cycles)
        experiment.write_json(args.output, result)
        print(f"Compared four conditions across {len(result['interaction'])} matched worlds: {args.output}")
    except (OSError, RuntimeError, KeyError, ValueError, TypeError) as error:
        print(f"Factorial comparison failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
