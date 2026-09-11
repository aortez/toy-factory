#!/usr/bin/env python3
"""Compare explicitly identified host ecology conditions on matched frozen worlds."""

import argparse
from pathlib import Path
import sys

import garden_experiments as experiment
import garden_renewal as renewal
from garden_resources import require


def validate_pair(control: dict, candidate: dict, environment: dict) -> None:
    require(environment in (experiment.WIDE_ENVIRONMENT, experiment.WATER_ENVIRONMENT,
                            experiment.COMBINED_ENVIRONMENT), "unsupported ecology experiment")
    require(control["environment"] == experiment.ENVIRONMENT
            and candidate["environment"] == environment, "wrong control/candidate ecology")
    require(control["split"] == candidate["split"] == "exploratory", "use exploratory bundles")
    for field in ("cycles", "seeds", "seed", "trial_count", "roles", "candidate_probe",
                  "declared_training_seeds"):
        require(control[field] == candidate[field], f"unmatched experiment setting: {field}")
    for role in ("candidate", "control"):
        require(control["models"][role]["sha256"] == candidate["models"][role]["sha256"],
                f"unmatched {role} model bytes")


def paired_metrics(control: dict, candidate: dict, left: str = "control", right: str = "candidate") -> list[dict]:
    def index(report):
        result = {(t["scenario"], t["policy"], t["seed"]): t["metrics"] for t in report["trials"]}
        require(len(result) == len(report["trials"]), "duplicate trial identity")
        return result

    a, b = index(control), index(candidate)
    require(a.keys() == b.keys(), "unmatched trial identities")
    return [{"scenario": k[0], "policy": k[1], "seed": k[2], left: a[k], right: b[k],
             "delta": {name: b[k][name] - value for name, value in a[k].items()
                       if isinstance(value, (int, float)) and isinstance(b[k][name], (int, float))}}
            for k in sorted(a)]


def compare(control: Path, candidate: Path, environment: dict, late_cycles: int) -> dict:
    manifests = [experiment.read_json(path / "manifest.json") for path in (control, candidate)]
    validate_pair(*manifests, environment)
    data = {name: renewal.summarize(path, late_cycles)
            for name, path in (("control", control), ("candidate", candidate))}
    return {"schema_version": 1, "kind": "garden-ecology-comparison",
            "analysis_sha256": experiment.digest(Path(__file__)),
            "notes": ["Exploratory paired worlds; shared weather seeds are not independent replicates.",
                      "Full-cycle survivors may later die; late qualifications are not a late-born cohort."],
            **data, "pairs": paired_metrics(data["control"], data["candidate"])}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--control", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--change", choices=("water-headroom", "wide-dispersal", "combined"), required=True)
    parser.add_argument("--late-cycles", type=int, default=8)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        require(not args.output.exists(), "output already exists")
        environment = (experiment.COMBINED_ENVIRONMENT if args.change == "combined"
                       else experiment.WATER_ENVIRONMENT if args.change == "water-headroom"
                       else experiment.WIDE_ENVIRONMENT)
        result = compare(args.control.resolve(), args.candidate.resolve(), environment, args.late_cycles)
        experiment.write_json(args.output, result)
        print(f"Compared {len(result['pairs'])} matched worlds: {args.output}")
    except (OSError, RuntimeError, KeyError, ValueError, TypeError) as error:
        print(f"Ecology comparison failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
