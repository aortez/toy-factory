#!/usr/bin/env python3
"""Fresh, fixed weather confirmation of the unchanged all-offspring reserve rule."""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
import gzip
import hashlib
import json
from pathlib import Path

import garden_season_seedling_population as population
from garden_season_recruitment import digest, identity
from garden_seasons import analyze_worlds, require

ROOT, END, ARMS = population.ROOT, population.END, population.ARMS
RULE = "seedling-reserve-confirmation-v1"
PROTOCOL = "benchmarks/garden-seasons/seedling-confirmation-protocol.md"
PRIOR_SHA = "8f70391a857c864ad245fe47cba92eeeed53a38abfc23345de3ff1fc99d14008"
SEED_BASE = 0x73656135
SEEDS = tuple(f"{(SEED_BASE ^ ((i + 1) * 0x9e3779b9)) & 0xffffffff:08x}" for i in range(8))
PREFIX = "reserve-confirmation"
EARLIER_PANELS = ("recruitment-summary.json", "dispersal-confirmation-summary.json",
                  "seedling-population-summary.json")
ORCHESTRATION_CHANGES = {"sim/garden_season_seedling_population.py", "sim/CMakeLists.txt"}


def specification() -> list[dict]:
    return [{"mode": "seasonal", "scenario": layout, "policy": policy, "seed": seed}
            for layout in population.LAYOUTS for policy in population.POLICIES for seed in SEEDS]


def recorded_seeds(value) -> set[str]:
    if isinstance(value, dict):
        result = {value["seed"]} if isinstance(value.get("seed"), str) else set()
        result.update(s for s in value.get("seeds", []) if isinstance(s, str))
        for child in value.values():
            result.update(recorded_seeds(child))
        return result
    if isinstance(value, list):
        return set().union(*(recorded_seeds(child) for child in value))
    return set()


def inputs() -> dict:
    folder = ROOT / "benchmarks/garden-seasons"
    raw = gzip.decompress((folder / "seedling-population-histories.json.gz").read_bytes())
    require(hashlib.sha256(raw).hexdigest() == PRIOR_SHA, "Changed known-seed evidence")
    prior = json.loads(raw)
    require(population.analysis(prior["cases"]) == prior["analysis"] and
            population.compact(prior) == json.loads((folder / "seedling-population-summary.json").read_text()),
            "Changed earlier metrics/gates/summary")
    old_seeds = set().union(*(recorded_seeds(json.loads((folder / p).read_text())) for p in EARLIER_PANELS))
    require(len(set(SEEDS)) == 8 and not set(SEEDS) & old_seeds, "Reused weather seed")
    return prior


def frozen(build: Path) -> dict:
    result = population.frozen(build)
    for name in (PROTOCOL, "sim/garden_season_seedling_confirmation.py",
                 "sim/test_garden_season_seedling_confirmation.py",
                 *("benchmarks/garden-seasons/" + p for p in EARLIER_PANELS)):
        result["sources"][name] = digest(ROOT / name)
    return result


def check_candidate(current: dict, previous: dict) -> None:
    for key in ("flags", "inspector_sha256", "replayer_sha256"):
        require(current[key] == previous[key], "Changed frozen native candidate: " + key)
    for name, sha in previous["sources"].items():
        if name not in ORCHESTRATION_CHANGES:
            require(current["sources"].get(name) == sha, "Changed frozen dependency: " + name)


def analysis(cases: list[dict]) -> dict:
    require([c["case"] for c in cases] == specification(), "Changed fresh panel/order")
    # Use the original gate implementation, not a second set of passing criteria.
    result = population.analysis(cases, specification())
    weather = {}
    for case in cases:
        for arm in ARMS:
            history = case["arms"][arm]["history"]
            require([r["day"] for r in history["daily"]] == list(range(129)), "Incomplete daily census")
            for row in history["daily"]:
                key = case["case"]["seed"], row["day"]
                value = row["climate"], row["rain_deposited"] + row["rain_runoff"]
                require(weather.setdefault(key, value) == value, "Unmatched weather across fresh worlds")
    return result


def legacy_manifest(prior: dict) -> list[dict]:
    return [{"path": f"legacy-{identity(c['case'])}-{arm}.jsonl.gz", "sha256": c["traces"][arm]}
            for c in prior["cases"]
            if c["case"]["seed"] == population.SEEDS[0] and c["case"]["policy"] == "baseline"
            for arm in ARMS]


def legacy_controls(build: Path, output: Path, prior: dict) -> list[dict]:
    manifest = legacy_manifest(prior)
    selected = [c for c in prior["cases"] if c["case"]["seed"] == population.SEEDS[0]
                and c["case"]["policy"] == "baseline"]
    for entry, (case, arm) in zip(manifest, ((c, a) for c in selected for a in ARMS)):
        target = output / entry["path"]
        population.capture(build, case["case"], arm, target)
        require(digest(target) == entry["sha256"], "Changed legacy all-offspring trace")
    require(len(manifest) == 4, "Incomplete legacy panel")
    print("Verified four legacy population traces byte-for-byte", flush=True)
    return manifest


def run_job(item) -> dict:
    build, output, spec = item
    for repeat in (False, True):
        population.capture(build, spec, "control", population.path(output, spec, "control", repeat))
    require(digest(population.path(output, spec, "control")) ==
            digest(population.path(output, spec, "control", True)), "Nonrepeatable fresh control")
    audit = population.Audit(False)
    for group in population.reserve.groups(population.path(output, spec, "control")):
        audit.accept(*group)
    case = {**spec, **analyze_worlds(audit.sparse, 128, "seasonal")}
    audit.result(case)
    # Establish the complete fresh control before running its treatment.
    for repeat in (False, True):
        population.capture(build, spec, "guard", population.path(output, spec, "guard", repeat))
    require(digest(population.path(output, spec, "guard")) ==
            digest(population.path(output, spec, "guard", True)), "Nonrepeatable fresh treatment")
    result = population.analyze_pair(population.path(output, spec, "control"),
                                     population.path(output, spec, "guard"), case)
    result["traces"] = {arm: digest(population.path(output, spec, arm)) for arm in ARMS}
    result["frames"] = population.render(build, output, result, SEEDS[0], PREFIX)
    (output / (identity(spec) + ".json")).write_text(json.dumps(result, indent=2) + "\n")
    print("Verified fresh " + identity(spec), flush=True)
    return result


def validate_report(report: dict, prior: dict) -> None:
    require(report["protocol"] == RULE and report["input_sha256"] == PRIOR_SHA and
            report["seeds"] == list(SEEDS) and report["seed_base"] == f"{SEED_BASE:08x}" and
            report["days"] == 128 and report["gardener"] is False and report["irrigation"] is False,
            "Changed confirmation identity")
    check_candidate(report["frozen"], prior["frozen"])
    require(report["legacy"] == legacy_manifest(prior) and analysis(report["cases"]) == report["analysis"],
            "Changed legacy evidence or confirmation analysis")
    for case in report["cases"]:
        frames = case["frames"]
        selected = case["case"]["seed"] == SEEDS[0] and case["case"]["policy"] == "baseline"
        require(len(frames) == (4 if selected else 0) and
                {(f["arm"], f["day"]) for f in frames} ==
                ({(arm, day) for arm in ARMS for day in (16, 128)} if selected else set()),
                "Changed fixed screenshot selection")
        for frame in frames:
            expected = f"frames/{PREFIX}-{case['case']['scenario']}-{frame['arm']}-day-{frame['day']}.png"
            require(frame["png"] == expected and frame["hash"] ==
                    case["arms"][frame["arm"]]["history"]["daily"][frame["day"]]["hash"],
                    "Changed screenshot identity/state")


def verify_job(item) -> None:
    output, saved = item
    case = {**saved["case"], **saved["arms"]["control"]["history"]}
    population.verify_case((output, case, saved))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("collect", "verify"))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--build", type=Path, default=Path("artifacts/build-host-seasonal-seedling-population"))
    parser.add_argument("--jobs", type=int, default=4)
    args = parser.parse_args()
    if not 1 <= args.jobs <= 4:
        parser.error("Require 1..4 independent workers")
    prior = inputs()
    if args.command == "verify":
        report = json.loads((args.out / "results.json").read_text())
        validate_report(report, prior)
        with ProcessPoolExecutor(max_workers=args.jobs) as pool:
            list(pool.map(verify_job, ((args.out, c) for c in report["cases"])))
        require(population.compact(report) == json.loads((args.out / "summary.json").read_text()),
                "Changed compact evidence")
        require(all(digest(args.out / entry["path"]) == entry["sha256"] for entry in report["legacy"]),
                "Changed legacy traces")
        print("Verified fresh panel, unchanged gates, budgets, repeats and fixed captures")
        return
    build = args.build.resolve()
    provenance = frozen(build)
    check_candidate(provenance, prior["frozen"])
    args.out.mkdir(parents=True, exist_ok=False)
    (args.out / "frames").mkdir()
    legacy = legacy_controls(build, args.out, prior)
    with ProcessPoolExecutor(max_workers=args.jobs) as pool:
        results = list(pool.map(run_job, ((build, args.out, c) for c in specification())))
    require(provenance == frozen(build), "Inputs changed during fresh confirmation")
    report = {"protocol": RULE, "input_sha256": PRIOR_SHA, "seeds": list(SEEDS),
              "seed_base": f"{SEED_BASE:08x}", "days": 128, "gardener": False, "irrigation": False,
              "frozen": provenance, "legacy": legacy, "cases": results, "analysis": analysis(results)}
    validate_report(report, prior)
    (args.out / "results.json").write_text(json.dumps(report, indent=2) + "\n")
    (args.out / "summary.json").write_text(json.dumps(population.compact(report), indent=2) + "\n")
    print("Completed all 32 fresh pairs; passes_screen=" + str(report["analysis"]["passes_screen"]))


if __name__ == "__main__":
    main()
