#!/usr/bin/env python3
"""Retain compact seasonal evidence and check a predeclared shorter-drought screen."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from garden_seasons import MODES, require


def summarize(panel: dict) -> dict:
    require(panel["protocol"] == "garden-seasons-v2", "Expected ancestry-aware seasonal panel")
    cases = panel["cases"]
    identities = {(c["mode"], c["scenario"], c["policy"], c["seed"]) for c in cases}
    expected = {(m, s, p, seed) for m in MODES for s in ("rainfed", "rainfed-crowded")
                for p in ("baseline", "adaptive") for seed in panel["seeds"]}
    require(identities == expected and len(cases) == len(expected), "Incomplete/duplicate panel")
    require(not panel["gardener"] and not panel["irrigation"], "Assisted panel")
    for case in cases:
        require([r["day"] for r in case["daily"]] == list(range(panel["days"] + 1)),
                "Incomplete daily census")
    groups = {}
    for mode in MODES:
        group = [c for c in cases if c["mode"] == mode]
        end = [c["daily"][-1] for c in group]
        groups[mode] = {
            "worlds": len(group), "living_at_end": sum(r["living"] > 0 for r in end),
            "observed_empty_worlds": sum(c["empty_day"] is not None for c in group),
            "births": sum(r["births"] for r in end), "deaths": sum(r["deaths"] for r in end),
            "closing_births": sum(c["closing_births"] for c in group),
            "closing_birth_worlds": sum(c["closing_births"] > 0 for c in group),
            "multi_viable_species_worlds": sum(len(r["viable_species"]) > 1 for r in end),
            "living_species_histogram": dict(Counter(len(r["species"]) for r in end)),
            "viable_species_histogram": dict(Counter(len(r["viable_species"]) for r in end)),
            "historical_durable_parents": sum(c["lifetimes"]["durable_parents"] for c in group),
            "closing_cycle_survivors": sum(c["closing_lifetimes"]["cycle_survivors"] for c in group),
            "closing_durable_parents": sum(c["closing_lifetimes"]["durable_parents"] for c in group),
            "all_spacing_blocked_worlds": sum(
                c.get("seed_audit", {}).get("mature_seed_samples", 0) > 0 and
                c["seed_audit"]["blockers"].get("spacing", 0) == c["seed_audit"]["mature_seed_samples"]
                for c in group),
        }
    return {"protocol": panel["protocol"], "days": panel["days"], "seed_base": panel["seed_base"],
            "seeds": panel["seeds"], "groups": groups,
            "source_sha256": panel["source_sha256"], "inspector_sha256": panel["inspector_sha256"],
            "replayer_sha256": panel["replayer_sha256"], "frames": panel["frames"],
            "cases": [{**{k: c[k] for k in ("mode", "scenario", "policy", "seed", "environment",
                         "trace_sha256", "lifetimes", "closing_lifetimes", "empty_day")},
                       "final": c["daily"][-1], "seed_audit": c.get("seed_audit")}
                      for c in cases]}


def screen(control: dict, candidate: dict) -> dict:
    for key in ("protocol", "days", "seeds", "seed_base", "gardener", "irrigation"):
        require(control[key] == candidate[key], f"Unmatched {key}")
    a, b = summarize(control), summarize(candidate)
    key = lambda c: (c["mode"], c["scenario"], c["policy"], c["seed"])
    references = {key(c): c for c in control["cases"]}
    negative_controls = 0
    for case in candidate["cases"]:
        previous = references[key(case)]
        require(case["environment"] == previous["environment"], "Unmatched capacity/environment")
        require(case["daily"][:5] == previous["daily"][:5], "Changed pre-drought prefix")
        if case["mode"] in ("steady", "winter"):
            for field in ("daily", "plants", "deaths", "lifetimes", "closing_lifetimes", "trace_sha256"):
                require(case[field] == previous[field], f"Changed negative control: {field}")
            require(case.get("seed_audit") == previous.get("seed_audit"), "Changed negative-control audit")
            negative_controls += 1
    before, after = a["groups"]["seasonal"], b["groups"]["seasonal"]
    gates = {
        "no_new_empty_world": all(c["empty_day"] is None or references[key(c)]["empty_day"] is not None
                                  for c in candidate["cases"]),
        "more_multi_species_endpoints": after["multi_viable_species_worlds"] > before["multi_viable_species_worlds"],
        "closing_birth_worlds_retained": after["closing_birth_worlds"] >= before["closing_birth_worlds"],
        "closing_survivors_retained": after["closing_cycle_survivors"] >= before["closing_cycle_survivors"],
        "historical_durable_parents_retained": after["historical_durable_parents"] >= before["historical_durable_parents"],
    }
    if control["days"] > 64:
        gates["closing_durable_parents_retained"] = after["closing_durable_parents"] >= before["closing_durable_parents"]
    return {"primary_arm": "seasonal", "negative_controls_verified": negative_controls,
            "prefixes_verified": len(references), "gates": gates, "passes_screen": all(gates.values())}


def load(path: Path) -> tuple[dict, str]:
    data = path.read_bytes()
    return json.loads(data), hashlib.sha256(data).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--control", type=Path, required=True)
    parser.add_argument("--candidate", type=Path)
    parser.add_argument("--out", type=Path, required=True, help="New compact JSON file")
    args = parser.parse_args()
    control, digest = load(args.control)
    report = {"schema_version": 1, "control_input_sha256": digest, "control": summarize(control),
              "notes": ["Full-day parent/child survival is historical credit, not proof of present renewal.",
                        "Final-year cohorts censor births with less than one day of potential follow-up.",
                        "Viable species count living plants plus unexpired seeds, not successful recruitment.",
                        "Site blockers are overlapping post-step observations, not decision-stage receipts.",
                        "Layouts and policies share weather seeds; worlds are not independent replicates."]}
    if args.candidate:
        candidate, digest = load(args.candidate)
        report.update(candidate_input_sha256=digest, candidate=summarize(candidate),
                      screen=screen(control, candidate))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x") as stream:
        json.dump(report, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(args.out)


if __name__ == "__main__":
    main()
