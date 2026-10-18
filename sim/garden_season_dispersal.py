#!/usr/bin/env python3
"""One predeclared seasonal scattering-width screen; never selects new parameters."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path

from garden_seasons import require, run_case, source_hashes
from garden_season_recruitment import digest, frames, identity


def group(cases: list[dict]) -> dict:
    return {"worlds": len(cases),
            "closing_birth_worlds": sum(c["closing_births"] > 0 for c in cases),
            "closing_births": sum(c["closing_births"] for c in cases),
            "closing_survivors": sum(c["closing_lifetimes"]["cycle_survivors"] for c in cases),
            "closing_durable_parents": sum(c["closing_lifetimes"]["durable_parents"] for c in cases),
            "historical_durable_parents": sum(c["lifetimes"]["durable_parents"] for c in cases),
            "multi_viable_species_worlds": sum(len(c["daily"][-1]["viable_species"]) > 1 for c in cases),
            "empty_worlds": sum(c["empty_day"] is not None for c in cases),
            "births": sum(c["lifetimes"]["births"] for c in cases),
            "eligible": sum(c["lifetimes"]["eligible"] for c in cases),
            "survivors": sum(c["lifetimes"]["cycle_survivors"] for c in cases),
            "deaths": sum(len(c["deaths"]) for c in cases)}


def screen(controls: list[dict], treatments: list[dict]) -> dict:
    before = {identity(c): c for c in controls}
    require(len(before) == len(controls) == len(treatments) == len({identity(c) for c in treatments}) and
            set(before) == {identity(c) for c in treatments}, "Unmatched/duplicate cases")
    for case in treatments:
        control = before[identity(case)]
        require(case["daily"][0] == control["daily"][0] and
                case["environment"] == control["environment"], "Changed initial state or non-dispersal settings")
    groups = {mode: {"control": group([c for c in controls if c["mode"] == mode]),
                     "wide": group([c for c in treatments if c["mode"] == mode])}
              for mode in ("steady", "seasonal")}
    a, b = groups["seasonal"]["control"], groups["seasonal"]["wide"]
    metrics = ("closing_birth_worlds", "closing_survivors", "closing_durable_parents",
               "historical_durable_parents", "multi_viable_species_worlds")
    gates = {"retain_" + key: b[key] >= a[key] for key in metrics}
    gates["improve_closing_renewal"] = any(b[key] > a[key] for key in metrics[:3])
    gates["no_new_empty_world"] = all(c["empty_day"] is None or before[identity(c)]["empty_day"] is not None
                                       for c in treatments)
    return {"groups": groups, "gates": gates, "passes_screen": all(gates.values()),
            "by_policy": {policy: {"control": group([c for c in controls if c["mode"] == "seasonal"
                                                       and c["policy"] == policy]),
                                    "wide": group([c for c in treatments if c["mode"] == "seasonal"
                                                    and c["policy"] == policy])}
                          for policy in ("baseline", "adaptive")},
            "by_layout": {layout: {"control": group([c for c in controls if c["mode"] == "seasonal"
                                                       and c["scenario"] == layout]),
                                    "wide": group([c for c in treatments if c["mode"] == "seasonal"
                                                    and c["scenario"] == layout])}
                          for layout in ("rainfed", "rainfed-crowded")}}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--panel", type=Path, required=True)
    parser.add_argument("--build", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--jobs", type=int, default=4)
    args = parser.parse_args()
    if not 1 <= args.jobs <= 8:
        parser.error("Require 1–8 jobs")
    root = Path(__file__).resolve().parents[1]
    published = json.loads((root / "benchmarks/garden-seasons/fresh-128.json").read_text())
    require(digest(args.panel) == published["control_input_sha256"], "Changed fixed parent evidence")
    parent = json.loads(args.panel.read_text())
    cases = [c for c in parent["cases"] if c["mode"] in ("steady", "seasonal")]
    require(len(cases) == 32 and parent["days"] == 128, "Wrong panel")
    build = args.build.resolve()
    cache = build / "CMakeCache.txt"
    flags = dict(line.strip().split("=", 1) for line in cache.read_text().splitlines()
                 if line.startswith("TOY_FACTORY_GARDEN_") and ":BOOL=" in line)
    require(flags.get("TOY_FACTORY_GARDEN_WIDE_DISPERSAL:BOOL") == "ON" and
            all(value == "OFF" for key, value in flags.items()
                if key != "TOY_FACTORY_GARDEN_WIDE_DISPERSAL:BOOL"), "Not an isolated wider-scattering build")
    inspector, replayer = build / "toy-factory-garden-inspect", build / "toy-factory-garden-replay"
    frozen = {"source_sha256": source_hashes(root), "inspector_sha256": digest(inspector),
              "replayer_sha256": digest(replayer), "cache_sha256": digest(cache),
              "collector_sha256": digest(Path(__file__)),
              "protocol_sha256": digest(root / "benchmarks/garden-seasons/dispersal-protocol.md")}
    args.out.mkdir(parents=True, exist_ok=False)

    def run(case):
        result = run_case(inspector, 128, case["scenario"], case["policy"], int(case["seed"], 16),
                          case["mode"], True)
        print("Verified wide " + identity(case), flush=True)
        return result

    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        results = list(pool.map(run, cases))
    repeated = []
    for case in results:
        if case["seed"] == "ed52188b" and case["mode"] == "seasonal":
            require(run(case) == case, "Wide trajectory/site audit does not repeat")
            repeated.append(identity(case))
    images = frames(build, args.out / "frames", results, "ed52188b")
    require(source_hashes(root) == frozen["source_sha256"] and digest(inspector) == frozen["inspector_sha256"]
            and digest(replayer) == frozen["replayer_sha256"] and digest(cache) == frozen["cache_sha256"]
            and digest(Path(__file__)) == frozen["collector_sha256"] and
            digest(root / "benchmarks/garden-seasons/dispersal-protocol.md") == frozen["protocol_sha256"],
            "Inputs changed during screen")
    report = {"protocol": "seasonal-dispersal-screen-v1", "control_rule": "narrow-v1", "candidate_rule": "wide-v1",
              "parent_sha256": digest(args.panel), "build_flags": flags, **frozen, "repeated": repeated,
              "frames": images, "screen": screen(cases, results), "cases": results}
    (args.out / "results.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report["screen"], indent=2))


if __name__ == "__main__":
    main()
