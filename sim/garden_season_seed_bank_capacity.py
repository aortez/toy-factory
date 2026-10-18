#!/usr/bin/env python3
"""One frozen seasonal eight-versus-sixteen seed-bank screen, with unchanged guards."""

from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
import gzip
import hashlib
from itertools import zip_longest
import json
from pathlib import Path
import re
import subprocess
import sys
import zlib

import garden_season_reproduction_funnel as funnel
import garden_season_seedling_confirmation as confirmation
import garden_season_seedling_population as population
from garden_season_confirmation import build_flags
from garden_season_recruitment import digest, identity
from garden_seasons import life_summary, require, source_hashes

ROOT, DAY, END = funnel.ROOT, funnel.DAY, funnel.END
RULE = "seasonal-seed-bank-capacity-v1"
PROTOCOL = "benchmarks/garden-seasons/seed-bank-capacity-protocol.md"
INPUT_SHA = funnel.INPUT_SHA
DIAGNOSIS_SHA = "646131b9f7e2c599ca7bcc436d51e8cf5b9143c4899913119d3eae40bb79ec15"
OPTION = "TOY_FACTORY_GARDEN_SEASONAL_SEED_BANK:BOOL"
CAPACITIES = {"eight": 8, "sixteen": 16}
ALLOWED_CHANGES = {"src/garden_world.h", "sim/CMakeLists.txt", "sim/garden_inspect.c",
    "sim/garden_replay.c", "sim/garden_experiment.c", "sim/garden_production_audit.c",
    "sim/garden_reproduction_audit_test.c", "sim/garden_season_seedling_population.py",
    "sim/garden_season_reproduction_funnel.py", "sim/garden_season_production_gates.py",
    "sim/test_garden_season_production_gates.py", "scripts/container/host-garden-defaults.sh"}


def inputs() -> tuple[dict, dict]:
    prior = funnel.load_input()
    raw = gzip.decompress((ROOT / "benchmarks/garden-seasons/production-gates-parents.json.gz").read_bytes())
    require(hashlib.sha256(raw).hexdigest() == DIAGNOSIS_SHA, "Changed production diagnosis")
    return prior, json.loads(raw)


def first_difference(before: dict, after: dict, old_bids: list, new_bids: list,
                     old_deaths: list, new_deaths: list) -> dict:
    extra = after["seeds"][8:]
    require(before.get("seed_capacity", 8) == 8 and after.get("seed_capacity") == 16 and
            before["tick"] == after["tick"] and before["tick"] > 0 and before["tick"] % 60 == 0 and
            len(before["seeds"]) == 8 < len(after["seeds"]) <= 16 and
            before["seeds"] == after["seeds"][:8] and all(s["age"] == 0 for s in extra) and
            after["seeds_created"] - before["seeds_created"] == len(extra) and
            all(before[k] == after[k] for k in ("births", "deaths", "nodes", "seeds_expired")) and
            old_bids == new_bids and old_deaths == new_deaths,
            "First change is not an isolated extra seed purchase")
    fields = ("id", "parent", "species", "generation", "dead")
    require([{k: p[k] for k in fields} for p in before["plants"]] ==
            [{k: p[k] for k in fields} for p in after["plants"]], "Changed prefix incumbents")
    return {"tick": before["tick"], "eight": before, "sixteen": after}


def incumbent_pairs(arms: dict, difference: dict | None) -> list[dict]:
    if difference is None:
        return []
    tick = difference["tick"]
    old = arms["eight"]["outcome"]["history"]["plants"]
    new = {p["id"]: p for p in arms["sixteen"]["outcome"]["history"]["plants"]}
    result = []
    for p in old:
        if p["birth_tick"] > tick or (p["death_tick"] is not None and p["death_tick"] <= tick):
            continue
        require(p["id"] in new, "Missing incumbent in treatment history")
        q = new[p["id"]]
        require({k: v for k, v in p.items() if k != "death_tick"} ==
                {k: v for k, v in q.items() if k != "death_tick"}, "Changed incumbent ancestry")
        a, b = p["death_tick"], q["death_tick"]
        result.append({"id": p["id"], "species": p["species"], "founder": p["parent"] == 0,
            "eight_death": a, "sixteen_death": b,
            "earlier": b is not None and (a is None or b < a),
            "later": a is not None and (b is None or b > a)})
    require([p["id"] for p in result] == [p["id"] for p in difference["eight"]["plants"] if not p["dead"]],
            "Incomplete incumbent census")
    return result


def occupancy() -> dict:
    return {w: {"samples": 0, "seed_samples": 0, "histogram": {}, "first_full_tick": None}
            for w in ("whole", "closing")}


def add_occupancy(result: dict, world: dict, capacity: int) -> None:
    tick, count = world["tick"], len(world["seeds"])
    for window, start in (("whole", 0), ("closing", 112 * DAY)):
        if tick <= start:
            continue
        r = result[window]
        r["samples"] += 1
        r["seed_samples"] += count
        r["histogram"][str(count)] = r["histogram"].get(str(count), 0) + 1
        if count == capacity and r["first_full_tick"] is None:
            r["first_full_tick"] = tick


def analyze_pair(output: Path, old: dict) -> dict:
    spec = old["case"]
    paths = {a: population.path(output, spec, a) for a in CAPACITIES}
    hashes = {a: digest(p) for a, p in paths.items()}
    require(hashes["eight"] == old["traces"]["guard"], "Rebuilt eight-slot guarded trace changed")
    audits = {a: population.Audit(True, cap) for a, cap in CAPACITIES.items()}
    ledgers = {a: funnel.SeedLedger(cap) for a, cap in CAPACITIES.items()}
    occupancies = {a: occupancy() for a in CAPACITIES}
    prefix, difference = 0, None
    for pair in zip_longest(*(population.reserve.groups(paths[a]) for a in CAPACITIES)):
        require(all(p is not None for p in pair), "Truncated paired traces")
        (before, old_bids, old_deaths), (after, new_bids, new_deaths) = pair
        require(all(before[k] == after[k] for k in ("tick", "climate", "rain_rate", "sun_phase", "sun_strength")) and
                before["rain_deposited"] + before["rain_runoff"] == after["rain_deposited"] + after["rain_runoff"],
                "Unmatched external weather")
        if difference is None:
            stripped = {k: v for k, v in after.items() if k != "seed_capacity"}
            if before == stripped:
                require(old_bids == new_bids and old_deaths == new_deaths, "Changed identical-state decisions")
                prefix += 1
            else:
                difference = first_difference(before, after, old_bids, new_bids, old_deaths, new_deaths)
        for (arm, cap), item in zip(CAPACITIES.items(), pair):
            audits[arm].accept(*item)
            ledgers[arm].accept(item[0])
            add_occupancy(occupancies[arm], item[0], cap)
    arms = {a: {"capacity": cap, "outcome": audits[a].result({}), "ledger": ledgers[a].result(),
                "occupancy": occupancies[a]} for a, cap in CAPACITIES.items()}
    require(arms["eight"]["outcome"] == old["arms"]["guard"], "Changed old guarded outcomes/budgets")
    require(hashes == {a: digest(p) for a, p in paths.items()}, "Traces changed during analysis")
    return {"case": spec, "traces": hashes, "exact_prefix_worlds": prefix, "first_difference": difference,
            "arms": arms, "incumbents": incumbent_pairs(arms, difference)}


def metrics(arms: list[dict]) -> dict:
    result = population.metrics([a["outcome"] for a in arms])
    result["multi_living_species_worlds"] = sum(len(a["outcome"]["history"]["daily"][-1]["species"]) > 1 for a in arms)
    result["seed_pending"] = sum(a["outcome"]["history"]["daily"][-1]["seed_bank"] for a in arms)
    result["occupancy"] = {}
    for window in ("whole", "closing"):
        values = [a["occupancy"][window] for a in arms]
        result["occupancy"][window] = {"samples": sum(v["samples"] for v in values),
            "seed_samples": sum(v["seed_samples"] for v in values),
            "full_samples": sum(v["histogram"].get(str(a["capacity"]), 0) for a, v in zip(arms, values))}
    result["species"] = {}
    for species in funnel.SPECIES:
        plants = [{p["id"]: p for p in a["outcome"]["history"]["plants"] if p["species"] == species} for a in arms]
        result["species"][species] = {}
        for window, start in (("whole", 0), ("closing", 112 * DAY + 1)):
            totals = Counter(life_summary({}, END, start))
            for p in plants:
                totals.update(life_summary(p, END, start))
            result["species"][species][window] = dict(totals)
        result["species"][species]["deaths"] = sum(p["death_tick"] is not None for ps in plants for p in ps.values())
        result["species"][species]["living_endpoints"] = sum(species in a["outcome"]["history"]["daily"][-1]["species"] for a in arms)
        result["species"][species]["viable_endpoints"] = sum(species in a["outcome"]["history"]["daily"][-1]["viable_species"] for a in arms)
    return result


def gates(before: dict, after: dict, cases: list[dict]) -> dict:
    pairs = [(c["arms"]["eight"]["outcome"], c["arms"]["sixteen"]["outcome"]) for c in cases]
    return {"improve_closing_durable_parents": after["closing_durable_parents"] > before["closing_durable_parents"],
        "retain_closing_survivors": after["closing_survivors"] >= before["closing_survivors"],
        "retain_closing_survival_fraction": population.fraction_retained(before, after),
        "retain_historical_durable_parents": after["historical_durable_parents"] >= before["historical_durable_parents"],
        "no_new_empty_world": all(b["first_empty_tick"] is None or a["first_empty_tick"] is not None for a, b in pairs),
        "no_new_zero_living_endpoint": all(b["history"]["daily"][-1]["living"] > 0 or
            a["history"]["daily"][-1]["living"] == 0 for a, b in pairs),
        "retain_viable_species_each_world": all(len(b["history"]["daily"][-1]["viable_species"]) >=
            len(a["history"]["daily"][-1]["viable_species"]) for a, b in pairs),
        "retain_multi_living_species_worlds": after["multi_living_species_worlds"] >= before["multi_living_species_worlds"]}


def analysis(cases: list[dict]) -> dict:
    require([c["case"] for c in cases] == confirmation.specification(), "Incomplete/duplicate/reordered capacity panel")
    groups = {a: metrics([c["arms"][a] for c in cases]) for a in CAPACITIES}
    verdict = gates(groups["eight"], groups["sixteen"], cases)
    comparisons = ("closing_births", "closing_survivors", "closing_durable_parents",
                   "historical_durable_parents", "multi_viable_species_worlds", "deaths", "living")
    paired = {}
    for key in comparisons:
        deltas = [metrics([c["arms"]["sixteen"]])[key] - metrics([c["arms"]["eight"]])[key] for c in cases]
        paired[key] = {"increased": sum(d > 0 for d in deltas), "unchanged": sum(d == 0 for d in deltas),
                       "decreased": sum(d < 0 for d in deltas)}
    incumbents = [p for c in cases for p in c["incumbents"]]
    return {"groups": groups, "gates": verdict, "passes_screen": all(verdict.values()), "paired": paired,
        "incumbents": {"plants": len(incumbents), "earlier_deaths": sum(p["earlier"] for p in incumbents),
            "later_deaths": sum(p["later"] for p in incumbents),
            "unchanged": sum(not p["earlier"] and not p["later"] for p in incumbents),
            "earlier_death_worlds": sum(any(p["earlier"] for p in c["incumbents"]) for c in cases)},
        "partitions": {field: {value: {a: metrics([c["arms"][a] for c in cases if c["case"][field] == value])
            for a in CAPACITIES} for value in values} for field, values in
            (("seed", confirmation.SEEDS), ("scenario", population.LAYOUTS), ("policy", population.POLICIES))}}


def validate_case(case: dict, old: dict) -> None:
    require(case["case"] == old["case"] and case["traces"]["eight"] == old["traces"]["guard"] and
            case["arms"]["eight"]["outcome"] == old["arms"]["guard"], "Changed frozen control")
    for arm, cap in CAPACITIES.items():
        a = case["arms"][arm]
        require(a["capacity"] == cap and a["outcome"]["outcomes"] == population.outcomes(a["outcome"]["history"]),
                "Changed capacity or lifetime metrics")
        funnel.validate_ledger(a["ledger"], a["outcome"])
        for window, samples in (("whole", END // 15), ("closing", 16 * 256)):
            occ = a["occupancy"][window]
            require(occ["samples"] == samples == sum(occ["histogram"].values()) and
                    all(k == str(int(k)) and 0 <= int(k) <= cap and type(n) is int and n > 0
                        for k, n in occ["histogram"].items()) and
                    occ["seed_samples"] == sum(int(k) * n for k, n in occ["histogram"].items()) and
                    (occ["first_full_tick"] is None) == (occ["histogram"].get(str(cap), 0) == 0),
                    "Corrupt occupancy denominator/capacity")
            if occ["first_full_tick"] is not None:
                require((0 if window == "whole" else 112 * DAY) < occ["first_full_tick"] <= END and
                        occ["first_full_tick"] % 15 == 0, "Invalid first saturation tick")
    difference = case["first_difference"]
    require(case["exact_prefix_worlds"] == (END // 15 + 1 if difference is None else difference["tick"] // 15),
            "Changed exact-prefix length")
    if difference is not None:
        require(first_difference(difference["eight"], difference["sixteen"], [], [], [], []) == difference,
                "Changed first capacity event")
    require(case["incumbents"] == incumbent_pairs(case["arms"], difference), "Changed incumbent comparison")
    selected = case["case"]["seed"] == confirmation.SEEDS[0] and case["case"]["policy"] == "baseline"
    frames = case["frames"]
    require(len(frames) == (4 if selected else 0) and {(f["arm"], f["day"]) for f in frames} ==
            ({(a, d) for a in CAPACITIES for d in (16, 128)} if selected else set()), "Changed frame selection")
    for frame in frames:
        require(frame["hash"] == case["arms"][frame["arm"]]["outcome"]["history"]["daily"][frame["day"]]["hash"],
                "Frame state does not match trajectory")
        if frame["arm"] == "eight":
            earlier = next(f for f in old["frames"] if f["arm"] == "guard" and f["day"] == frame["day"])
            require(all(frame[k] == earlier[k] for k in ("hash", "framebuffer_crc32", "png_sha256")), "Changed control image")


def validate_report(report: dict, prior: dict) -> None:
    require(report["protocol"] == RULE and report["input_sha256"] == INPUT_SHA and
            report["diagnosis_sha256"] == DIAGNOSIS_SHA and analysis(report["cases"]) == report["analysis"],
            "Changed capacity trial identity/analysis")
    for case, old in zip(report["cases"], prior["cases"]):
        validate_case(case, old)


def compact(report: dict) -> dict:
    return {**{k: v for k, v in report.items() if k != "cases"}, "cases": [
        {"case": c["case"], "traces": c["traces"], "frames": c["frames"], "incumbents": c["incumbents"],
         "exact_prefix_worlds": c["exact_prefix_worlds"],
         "first_changed_tick": None if c["first_difference"] is None else c["first_difference"]["tick"],
         "arms": {a: {"metrics": metrics([v]), "counts": v["outcome"]["counts"], "occupancy": v["occupancy"],
            "details_sha256": hashlib.sha256(json.dumps(v, sort_keys=True).encode()).hexdigest()}
            for a, v in c["arms"].items()}} for c in report["cases"]]}


def sizes(build: Path) -> dict:
    output = subprocess.check_output([build / "toy-factory-garden-capacity-test"], text=True, timeout=30)
    lines = output.splitlines()
    seed = next(line for line in lines if line.startswith("PASS seed_capacity="))
    node = next(line for line in lines if line.startswith("PASS capacity="))
    result = {k: int(v) for k, v in re.findall(r"(\w+)=(\d+)", seed)}
    result["scene_snapshot"] = int(dict(re.findall(r"(\w+)=(\d+)", node))["snapshot"])
    return result


def frozen(builds: dict, diagnosis: dict) -> dict:
    sources = source_hashes(ROOT)
    files = {PROTOCOL, "sim/garden_season_seed_bank_capacity.py", "sim/test_garden_season_seed_bank_capacity.py",
             "sim/CMakeLists.txt", "scripts/container/host-garden-defaults.sh", *diagnosis["frozen"]["sources"]}
    sources.update({name: digest(ROOT / name) for name in files})
    for name, sha in diagnosis["frozen"]["sources"].items():
        if name not in ALLOWED_CHANGES:
            require(digest(ROOT / name) == sha, "Changed non-capacity dependency: " + name)
    configs = {}
    for arm, build in builds.items():
        flags = build_flags(build / "CMakeCache.txt")
        expected = {**diagnosis["frozen"]["flags"], OPTION: "ON" if arm == "sixteen" else "OFF"}
        require(flags == expected, "Not an isolated capacity build")
        configs[arm] = {"flags": flags, "cache_sha256": digest(build / "CMakeCache.txt"),
            "binaries": {name: digest(build / ("toy-factory-garden-" + name)) for name in ("inspect", "replay", "capacity-test")},
            "sizes": sizes(build)}
        require(configs[arm]["sizes"]["seed_capacity"] == CAPACITIES[arm], "Build/storage capacity mismatch")
    return {"sources": sources, "builds": configs}


def render(builds: dict, output: Path, result: dict) -> list[dict]:
    spec = result["case"]
    if spec["seed"] != confirmation.SEEDS[0] or spec["policy"] != "baseline":
        return []
    sys.path.insert(0, str(ROOT / "scripts/container"))
    from framebuffer_capture import rgb565be_to_rgb888, write_png
    frames = []
    for arm, cap in CAPACITIES.items():
        for day in (16, 128):
            target = output / "frames" / f"bank-{cap}-{spec['scenario']}-day-{day}.rgb565be"
            command = [builds[arm] / "toy-factory-garden-replay", "-", spec["scenario"], spec["policy"],
                str(int(spec["seed"], 16)), "--climate", "seasonal", "--ticks", str(day * DAY),
                "--seedling-reserve", "all", "--framebuffer", target]
            row = json.loads(subprocess.check_output(list(map(str, command)), text=True, timeout=300))
            raw = target.read_bytes()
            require(row["hash"] == result["arms"][arm]["outcome"]["history"]["daily"][day]["hash"] and
                    len(raw) == 115200 and row["framebuffer_crc32"] == f"{zlib.crc32(raw):08x}" and
                    row["seedling_reserve"] == population.METADATA and row.get("seed_capacity", 8) == cap,
                    "Rendered state/capacity mismatch")
            png = target.with_suffix(".png")
            write_png(png, 240, 240, rgb565be_to_rgb888(raw))
            frames.append({"arm": arm, "day": day, "png": "frames/" + png.name, "png_sha256": digest(png),
                           "hash": row["hash"], "framebuffer_crc32": row["framebuffer_crc32"]})
    return frames


def run_job(item) -> dict:
    builds, output, old, collect = item
    for arm in CAPACITIES:
        for repeat in (False, True):
            if collect:
                population.capture(builds[arm], old["case"], "guard", population.path(output, old["case"], arm, repeat))
        require(digest(population.path(output, old["case"], arm)) ==
                digest(population.path(output, old["case"], arm, True)), "Nonrepeatable capacity trace")
    result = analyze_pair(output, old)
    saved_path = output / (identity(old["case"]) + ".json")
    if collect:
        result["frames"] = render(builds, output, result)
        saved_path.write_text(json.dumps(result, indent=2) + "\n")
    else:
        saved = json.loads(saved_path.read_text())
        result["frames"] = saved["frames"]
        require(result == saved, "Changed capacity history/analysis")
    validate_case(result, old)
    for frame in result["frames"]:
        png = output / frame["png"]
        raw = png.with_suffix(".rgb565be").read_bytes()
        require(digest(png) == frame["png_sha256"] and len(raw) == 115200 and
                f"{zlib.crc32(raw):08x}" == frame["framebuffer_crc32"], "Changed screenshot bytes")
    print("Verified seed-bank capacity " + identity(old["case"]), flush=True)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("collect", "verify"))
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--eight", type=Path, default=Path("artifacts/build-host-seasonal-bank-8"))
    parser.add_argument("--sixteen", type=Path, default=Path("artifacts/build-host-seasonal-bank-16"))
    parser.add_argument("--jobs", type=int, default=4)
    args = parser.parse_args()
    if not 1 <= args.jobs <= 4:
        parser.error("Require 1..4 independent workers")
    prior, diagnosis = inputs()
    builds = {a: getattr(args, a).resolve() for a in CAPACITIES}
    provenance = frozen(builds, diagnosis)
    if args.command == "collect":
        args.out.mkdir(parents=True, exist_ok=False)
        (args.out / "frames").mkdir()
    with ProcessPoolExecutor(max_workers=args.jobs) as pool:
        cases = list(pool.map(run_job, ((builds, args.out, old, args.command == "collect") for old in prior["cases"])))
    require(frozen(builds, diagnosis) == provenance, "Inputs changed during capacity screen")
    report = {"protocol": RULE, "input_sha256": INPUT_SHA, "diagnosis_sha256": DIAGNOSIS_SHA,
              "frozen": provenance, "cases": cases, "analysis": analysis(cases)}
    validate_report(report, prior)
    if args.command == "collect":
        (args.out / "results.json").write_text(json.dumps(report, indent=2) + "\n")
        (args.out / "summary.json").write_text(json.dumps(compact(report), indent=2) + "\n")
    else:
        require(report == json.loads((args.out / "results.json").read_text()) and
                compact(report) == json.loads((args.out / "summary.json").read_text()), "Nonrepeatable capacity analysis")
    print("All 32 capacity pairs verified; passes_screen=" + str(report["analysis"]["passes_screen"]), flush=True)


if __name__ == "__main__":
    main()
