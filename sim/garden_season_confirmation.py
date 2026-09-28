#!/usr/bin/env python3
"""Fresh-weather confirmation of the frozen seasonal scattering candidate."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path

from garden_season_dispersal import group, screen
from garden_season_recruitment import digest, frames, identity
from garden_seasons import DAY_TICKS, life_summary, require, run_case, source_hashes

SEED_BASE = 0x73656134
SEEDS = tuple(f"{(SEED_BASE ^ ((i + 1) * 0x9e3779b9)) & 0xffffffff:08x}" for i in range(8))
DAYS = 128
MODES = ("steady", "seasonal")
LAYOUTS = ("rainfed", "rainfed-crowded")
POLICIES = ("baseline", "adaptive")
ENVIRONMENT = {"node_capacity": 256, "seed_capacity": 8,
               "seed_lifetime_ecology_ticks": 8192, "leaf_environment": None}


def specification() -> list[dict]:
    return [{"mode": mode, "scenario": layout, "policy": policy, "seed": seed}
            for layout in LAYOUTS for policy in POLICIES for seed in SEEDS for mode in MODES]


def validate_panel(cases: list[dict]) -> None:
    expected = {identity(c) for c in specification()}
    require(len(cases) == len(expected) and {identity(c) for c in cases} == expected,
            "Incomplete/duplicate fresh panel")
    for case in cases:
        require(case["environment"] == ENVIRONMENT, "Changed device-sized ecology")
        require([r["day"] for r in case["daily"]] == list(range(DAYS + 1)), "Incomplete daily states")
        require(all(r["climate"]["mode"] == case["mode"] and r["climate"]["version"] == 1
                    for r in case["daily"]), "Changed climate")
        plants = {p["id"]: p for p in case["plants"]}
        require(len(plants) == len(case["plants"]) and
                life_summary(plants, DAYS * DAY_TICKS) == case["lifetimes"] and
                life_summary(plants, DAYS * DAY_TICKS, (DAYS - 16) * DAY_TICKS + 1) == case["closing_lifetimes"],
                "Changed lifetime cohorts")
        require(case["lifetimes"]["births"] == case["daily"][-1]["births"] and
                case["closing_births"] == case["closing_lifetimes"]["births"] ==
                case["daily"][-1]["births"] - case["daily"][-17]["births"] and
                len(case["deaths"]) == case["daily"][-1]["deaths"], "Unreconciled births/deaths")
        empty = next((r["day"] for r in case["daily"] if not r["living"] and not r["seed_bank"]), None)
        require(case["empty_day"] == empty, "Changed empty-world classification")
        audit = case["seed_audit"]
        require(audit["window_days"] == 16 and audit["ecology_samples"] == 16 * 256 and
                sum(audit["mask_histogram"].values()) == audit["mature_seed_samples"],
                "Incomplete seed-site audit")


def analysis(control: list[dict], wide: list[dict]) -> dict:
    for cases in (control, wide):
        validate_panel(cases)
    rainfall = {}
    for case in (*control, *wide):
        for day in case["daily"]:
            key = (case["mode"], case["seed"], day["day"])
            offered = day["rain_deposited"] + day["rain_runoff"]
            require(rainfall.setdefault(key, offered) == offered, "Unmatched offered rainfall")
    result = screen(control, wide)
    before = {identity(c): c for c in control}
    metrics = {"closing_births": lambda c: c["closing_births"],
               "closing_survivors": lambda c: c["closing_lifetimes"]["cycle_survivors"],
               "closing_durable_parents": lambda c: c["closing_lifetimes"]["durable_parents"],
               "historical_durable_parents": lambda c: c["lifetimes"]["durable_parents"],
               "viable_species": lambda c: len(c["daily"][-1]["viable_species"])}
    result["seasonal_pairs"] = {}
    for name, metric in metrics.items():
        differences = [metric(c) - metric(before[identity(c)]) for c in wide if c["mode"] == "seasonal"]
        result["seasonal_pairs"][name] = {"increased": sum(d > 0 for d in differences),
                                           "unchanged": sum(d == 0 for d in differences),
                                           "decreased": sum(d < 0 for d in differences)}
    result["by_seed"] = {seed: {arm: group([c for c in cases if c["mode"] == "seasonal" and c["seed"] == seed])
                                for arm, cases in (("control", control), ("wide", wide))} for seed in SEEDS}
    result["first_year"] = {}
    for mode in MODES:
        result["first_year"][mode] = {}
        for arm, cases in (("control", control), ("wide", wide)):
            group_cases = [c for c in cases if c["mode"] == mode]
            cohorts = [life_summary({p["id"]: p for p in c["plants"]}, 16 * DAY_TICKS) for c in group_cases]
            result["first_year"][mode][arm] = {
                "cohorts": {key: sum(c[key] for c in cohorts) for key in cohorts[0]},
                "natural_deaths": sum(d["tick"] <= 16 * DAY_TICKS for c in group_cases for d in c["deaths"])}
    return result


def build_flags(cache: Path) -> dict:
    return dict(line.strip().split("=", 1) for line in cache.read_text().splitlines()
                if line.startswith("TOY_FACTORY_GARDEN_") and ":BOOL=" in line)


def snapshot(root: Path, builds: dict[str, Path]) -> dict:
    files = ("sim/garden_season_confirmation.py", "sim/garden_season_dispersal.py",
             "sim/garden_season_recruitment.py", "scripts/container/framebuffer_capture.py",
             "sim/CMakeLists.txt", "scripts/container/host-garden-defaults.sh",
             "benchmarks/garden-seasons/dispersal-confirmation-protocol.md",
             "benchmarks/garden-seasons/recruitment-summary.json")
    return {"source_sha256": source_hashes(root),
            "support_sha256": {p: digest(root / p) for p in files},
            "builds": {arm: {"inspector_sha256": digest(build / "toy-factory-garden-inspect"),
                              "replayer_sha256": digest(build / "toy-factory-garden-replay"),
                              "cache_sha256": digest(build / "CMakeCache.txt"),
                              "flags": build_flags(build / "CMakeCache.txt")}
                       for arm, build in builds.items()}}


def check_frozen_candidate(frozen: dict, previous: dict) -> None:
    require(frozen["source_sha256"] == previous["wide"]["source_sha256"], "Changed candidate C/collector sources")
    for arm in ("control", "wide"):
        expected = dict(previous["wide"]["build_flags"])
        expected["TOY_FACTORY_GARDEN_WIDE_DISPERSAL:BOOL"] = "ON" if arm == "wide" else "OFF"
        require(frozen["builds"][arm]["flags"] == expected, "Not isolated narrow/wide configurations")
    for key in ("inspector_sha256", "replayer_sha256"):
        require(frozen["builds"]["wide"][key] == previous["wide"][key], "Changed frozen wide executable")
    old_seeds = {c["seed"] for c in previous["audit"]["cases"]}
    require(len(set(SEEDS)) == 8 and not set(SEEDS) & old_seeds, "Reused screening seed")


def summarize(report: dict) -> dict:
    require(report["protocol"] == "seasonal-dispersal-confirmation-v1" and report["seeds"] == list(SEEDS),
            "Wrong confirmation identity")
    checked = analysis(report["cases"]["control"], report["cases"]["wide"])
    require(checked == report["analysis"], "Changed saved confirmation analysis")
    compact = {k: v for k, v in report.items() if k != "cases"}
    compact["cases"] = {arm: [
        {**{k: c[k] for k in ("mode", "scenario", "policy", "seed", "environment", "trace_sha256",
                              "lifetimes", "closing_lifetimes", "closing_births", "empty_day", "seed_audit")},
         "daily_hashes": [r["hash"] for r in c["daily"]], "final": c["daily"][-1],
         "deaths": len(c["deaths"])} for c in cases] for arm, cases in report["cases"].items()}
    return compact


def collect(args) -> None:
    root = Path(__file__).resolve().parents[1]
    builds = {"control": args.control_build.resolve(), "wide": args.wide_build.resolve()}
    frozen = snapshot(root, builds)
    previous = json.loads((root / "benchmarks/garden-seasons/recruitment-summary.json").read_text())
    check_frozen_candidate(frozen, previous)
    args.out.mkdir(parents=True, exist_ok=False)

    def run(item):
        arm, case = item
        result = run_case(builds[arm] / "toy-factory-garden-inspect", DAYS, case["scenario"],
                          case["policy"], int(case["seed"], 16), case["mode"], True)
        print(f"Verified {arm} {identity(case)}", flush=True)
        return arm, result

    # Stable paired order; workers never share mutable worlds or RNG state.
    jobs = [(arm, case) for case in specification() for arm in builds]
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        results = list(pool.map(run, jobs))
    cases = {arm: [case for kind, case in results if kind == arm] for arm in builds}
    repeated, images = [], {}
    for arm in builds:
        for case in cases[arm]:
            if case["seed"] == SEEDS[0] and case["mode"] == "seasonal":
                require(run((arm, case))[1] == case, "Nonrepeatable fresh trajectory/site audit")
                repeated.append({"arm": arm, "case": identity(case), "trace_sha256": case["trace_sha256"]})
        images[arm] = frames(builds[arm], args.out / (arm + "-frames"), cases[arm], SEEDS[0])
        repeated_images = frames(builds[arm], args.out / (arm + "-frames-repeat"), cases[arm], SEEDS[0])
        require(repeated_images == images[arm], "Nonrepeatable fresh native frames")
    require(snapshot(root, builds) == frozen, "Inputs changed during confirmation")
    report = {"protocol": "seasonal-dispersal-confirmation-v1", "days": DAYS, "seed_base": f"{SEED_BASE:08x}",
              "seeds": list(SEEDS), "gardener": False, "irrigation": False,
              "control_rule": "narrow-v1", "candidate_rule": "wide-v1", "frozen": frozen,
              "repeated": repeated, "frames": images, "analysis": analysis(cases["control"], cases["wide"]),
              "cases": cases}
    full_path = args.out / "results.json"
    full_path.write_text(json.dumps(report, indent=2) + "\n")
    compact = summarize(report)
    compact["full_report_sha256"] = digest(full_path)
    (args.out / "summary.json").write_text(json.dumps(compact, indent=2) + "\n")
    print(json.dumps(report["analysis"], indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("collect")
    run.add_argument("--control-build", type=Path, default=Path("build-host"))
    run.add_argument("--wide-build", type=Path, default=Path("artifacts/build-host-seasonal-wide"))
    run.add_argument("--out", type=Path, required=True)
    run.add_argument("--jobs", type=int, default=4)
    verify = commands.add_parser("verify")
    verify.add_argument("--bundle", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "collect":
        if not 1 <= args.jobs <= 8:
            parser.error("Require 1–8 jobs")
        collect(args)
    else:
        full = args.bundle / "results.json"
        compact = summarize(json.loads(full.read_text()))
        compact["full_report_sha256"] = digest(full)
        require(compact == json.loads((args.bundle / "summary.json").read_text()), "Changed compact evidence")
        for arm, images in compact["frames"].items():
            for image in images:
                for suffix in ("-frames", "-frames-repeat"):
                    require(digest(args.bundle / (arm + suffix) / Path(image["png"]).name) == image["png_sha256"],
                            "Changed confirmation image")
        print("Verified fresh panel, cohorts, rainfall, gates, paired summaries and all repeated images")


if __name__ == "__main__":
    main()
