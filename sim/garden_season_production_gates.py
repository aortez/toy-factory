#!/usr/bin/env python3
"""Read-only exact production receipts on the frozen fresh confirmation worlds."""

from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
import gzip
import hashlib
from itertools import zip_longest
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

import garden_season_reproduction_funnel as funnel
from garden_season_confirmation import build_flags
from garden_season_recruitment import digest, identity
from garden_seasons import require, source_hashes

ROOT, DAY, END = funnel.ROOT, funnel.DAY, funnel.END
RULE = "seasonal-production-gates-v1"
PROTOCOL = "benchmarks/garden-seasons/production-gates-protocol.md"
INPUT_SHA = "b420df72e0a4dc64ca6d47817ed1df4a2847e670c5149c45260bbdb2c570ebd0"
FIELDS = ("id", "blockers", "energy", "water", "energy_required", "water_required", "immature",
          "spent", "ready", "flower_index", "cooldown", "bank", "stress", "light", "produced")
GATES = ("cooldown", "cadence", "bank", "dead", "stress", "light", "generation", "energy", "water", "flower")
BITS = {name: 1 << i for i, name in enumerate(GATES)}
WINDOW_EXCLUDED = sum(BITS[k] for k in ("cooldown", "cadence", "dead", "light", "flower"))


def load_input() -> dict:
    raw = gzip.decompress((ROOT / "benchmarks/garden-seasons/reproduction-funnel-ledgers.json.gz").read_bytes())
    require(hashlib.sha256(raw).hexdigest() == INPUT_SHA, "Changed frozen seed ledger")
    result = json.loads(raw)
    funnel.validate_report(result, funnel.load_input())
    return result


def required_resources(plant: dict) -> tuple[int, int]:
    trait = plant["genome"][6]
    energy_upkeep = (plant["nodes"] + 7) // 8
    water_upkeep = (plant["nodes"] - plant["roots"] + 7) // 8
    periods = 40 + trait * 4
    return (48 + min(max(96 + trait * 16, energy_upkeep * periods), 256 - energy_upkeep - 48),
            24 + min(max(32 + trait * 4, water_upkeep * periods), 512 - water_upkeep - 24))


def decode(values: list, tick: int, plant: dict, light: int, seed_capacity: int = 8) -> dict:
    require(type(seed_capacity) is int and seed_capacity in (8, 16), "Unsupported seed capacity")
    require(len(values) == len(FIELDS) and all(type(v) is int for v in values[:-1]) and
            type(values[-1]) is bool, "Malformed visit fields")
    v = dict(zip(FIELDS, values))
    require(v["id"] == plant["id"] and 0 <= v["blockers"] < 1024 and
            0 <= v["energy"] <= 256 and 0 <= v["water"] <= 512 and
            0 <= v["cooldown"] < 16 and 0 <= v["bank"] <= seed_capacity and
            0 <= v["stress"] <= 8 and 0 <= v["light"] <= 255 and
            all(0 <= v[k] <= 256 for k in ("immature", "spent", "ready")) and
            (v["flower_index"] == 65535 if not v["ready"] else 0 <= v["flower_index"] < 256),
            "Invalid visit ranges/flower selection")
    require((v["energy_required"], v["water_required"]) == required_resources(plant),
            "Changed reserve arithmetic")
    flags = (v["cooldown"] > 0, tick % 60 != 0, v["bank"] == seed_capacity, plant["dead"],
             v["stress"] != 0, v["light"] <= 24, plant["generation"] == 65535,
             v["energy"] < v["energy_required"], v["water"] < v["water_required"], not v["ready"])
    require(v["blockers"] == sum(1 << i for i, blocked in enumerate(flags) if blocked) and
            v["produced"] == (v["blockers"] == 0), "Gate flags disagree with exact decision")
    require(v["energy"] == plant["energy"] + 48 * v["produced"] and
            v["water"] == plant["water"] + 24 * v["produced"] and
            plant["reproduction_cooldown"] == (16 if v["produced"] else v["cooldown"]) and
            v["stress"] == plant["stress"] and v["light"] == light and
            sum(v[k] for k in ("immature", "spent", "ready")) == plant["flowers"] and
            (plant["dead"] or plant["spent_flowers"] == v["spent"] + v["produced"]),
            "Decision snapshot disagrees with frozen post-step state")
    return v


def empty_counts() -> dict:
    return {"visits": 0, "live_visits": 0, "productions": 0,
            "first_ready_tick": None, "first_window_tick": None,
            "cadence_masks": {}, "window_masks": {}, "shortfalls": {}}


def add_visit(counts: dict, v: dict, tick: int) -> None:
    mask = v["blockers"]
    counts["visits"] += 1
    counts["productions"] += v["produced"]
    if mask & BITS["dead"]:
        return
    counts["live_visits"] += 1
    if v["ready"] and counts["first_ready_tick"] is None:
        counts["first_ready_tick"] = tick
    if not mask & BITS["cadence"]:
        key = str(mask)
        counts["cadence_masks"][key] = counts["cadence_masks"].get(key, 0) + 1
    if not mask & WINDOW_EXCLUDED:
        if counts["first_window_tick"] is None:
            counts["first_window_tick"] = tick
        key = str(mask)
        counts["window_masks"][key] = counts["window_masks"].get(key, 0) + 1
        # Exact overlapping shortfalls, not independent marginal rescue counts.
        key = f"{max(0, v['energy_required'] - v['energy'])},{max(0, v['water_required'] - v['water'])},{v['bank']}"
        counts["shortfalls"][key] = counts["shortfalls"].get(key, 0) + 1


def audit_trace(trace: Path, original: Path, row: dict, end: int = END) -> dict:
    require(digest(original) == row["trace_sha256"], "Changed frozen primary trace")
    before = digest(trace)
    counts = {p["plant"]["id"]: empty_counts() for p in row["ledger"]["parents"]}
    expected = {}
    for seed in row["ledger"]["seeds"]:
        expected.setdefault(seed["created_tick"], []).append(seed["parent"])
    creations, worlds = 0, 0
    with gzip.open(trace, "rt") as stream:
        header = json.loads(next(stream))
        require(header == {"version": 1, "scenario": row["case"]["scenario"],
            "policy": row["case"]["policy"], "seed": row["case"]["seed"], "arm": row["arm"],
            "end": end, "climate": "seasonal", "dispersal": "wide-v1", "fields": list(FIELDS)},
            "Changed production collector identity")
        old_worlds = (w for w, _, _ in funnel.population.reserve.groups(original))
        for line, world in zip_longest(stream, old_worlds):
            require(line is not None and world is not None, "Truncated/extended receipt trace")
            native = json.loads(line)
            tick = worlds * 15
            require(native["tick"] == world["tick"] == tick and native["hash"] == world["hash"] and
                    native["created"] == world["seeds_created"], "Observed replay changed frozen state")
            plants = world["plants"] if tick else []
            require(len(native["visits"]) == len(plants), "Missing or extra sequential visit")
            visits = [decode(v, tick, p, world["sun_strength"]) for v, p in zip(native["visits"], plants)]
            produced = [v["id"] for v in visits if v["produced"]]
            require(produced == expected.get(tick, []) and
                    produced == [s["parent"] for s in world["seeds"] if s["age"] == 0],
                    "Changed production ledger/order")
            bank = len(world["seeds"]) - len(produced)
            for v in visits:
                require(v["bank"] == bank and v["id"] in counts, "Changed sequential bank/lineage")
                bank += v["produced"]
                add_visit(counts[v["id"]], v, tick)
            creations += len(produced)
            require(creations == native["created"], "Unaccounted seed creation")
            worlds += 1
    require(worlds == end // 15 + 1 and digest(trace) == before and
            digest(original) == row["trace_sha256"], "Incomplete/changed traces")
    result = {"case": row["case"], "arm": row["arm"], "worlds": worlds,
              "source_trace_sha256": row["trace_sha256"], "receipt_sha256": before,
              "parents": [{"plant": p["plant"], "counts": counts[p["plant"]["id"]]} for p in row["ledger"]["parents"]]}
    validate_case(result, row)
    return result


def validate_case(case: dict, old: dict) -> None:
    require(case["case"] == old["case"] and case["arm"] == old["arm"] and
            case["source_trace_sha256"] == old["trace_sha256"] and case["worlds"] == END // 15 + 1 and
            [p["plant"] for p in case["parents"]] == [p["plant"] for p in old["ledger"]["parents"]],
            "Changed parent panel/identity")
    for row, saved in zip(case["parents"], old["ledger"]["parents"]):
        p, c = row["plant"], row["counts"]
        first = max(15, p["birth_tick"])
        last = END if p["death_tick"] is None else p["death_tick"] - 15
        live = max(0, (last - first) // 15 + 1)
        cadence = max(0, last // 60 - (first - 1) // 60)
        require(c["live_visits"] == live and c["visits"] >= live and
                c["productions"] == len(saved["seed_indices"]) and
                sum(c["cadence_masks"].values()) == cadence, "Changed parent follow-up/production counts")
        for name, excluded in (("cadence_masks", BITS["cadence"] | BITS["dead"]), ("window_masks", WINDOW_EXCLUDED)):
            require(all(k == str(int(k)) and 0 <= int(k) < 1024 and not int(k) & excluded and
                        type(n) is int and n > 0 for k, n in c[name].items()), "Invalid gate histogram")
            require(c[name].get("0", 0) == c["productions"], "Allowed visits do not match productions")
        require(c["window_masks"] == {k: v for k, v in c["cadence_masks"].items() if not int(k) & WINDOW_EXCLUDED},
                "Window is not a subset of cadence visits")
        total = sum(c["window_masks"].values())
        require(sum(c["shortfalls"].values()) == total and
                (c["first_window_tick"] is None) == (total == 0), "Changed window follow-up")
        shortfall_masks = Counter()
        for key, n in c["shortfalls"].items():
            e, w, bank = map(int, key.split(","))
            require(key == f"{e},{w},{bank}" and 0 <= e <= 256 and 0 <= w <= 512 and 0 <= bank <= 8 and
                    type(n) is int and n > 0, "Invalid resource shortfall")
            mask = BITS["energy"] * bool(e) | BITS["water"] * bool(w) | BITS["bank"] * (bank == 8)
            shortfall_masks[str(mask)] += n
        projected = Counter()
        for key, n in c["window_masks"].items():
            projected[str(int(key) & (BITS["energy"] | BITS["water"] | BITS["bank"]))] += n
        require(shortfall_masks == projected, "Shortfalls disagree with gate histograms")
        for key in ("first_ready_tick", "first_window_tick"):
            require(c[key] is None or first <= c[key] <= last and c[key] % 15 == 0, "Future/dead observation")
        require(c["first_window_tick"] is None or c["first_ready_tick"] is not None and
                c["first_ready_tick"] <= c["first_window_tick"] and c["first_window_tick"] % 60 == 0,
                "Window before ready flower")


def summarize(parents: list[dict]) -> dict:
    result = {"parents": len(parents), "alive": sum(p["plant"]["death_tick"] is None for p in parents),
              "no_ready_flower": sum(p["counts"]["first_ready_tick"] is None for p in parents),
              "no_window": sum(p["counts"]["first_window_tick"] is None for p in parents)}
    result["lifetime_ecology_samples"] = sum(p["counts"]["live_visits"] for p in parents)
    for kind in ("cadence", "window"):
        masks = Counter()
        for p in parents:
            masks.update(p["counts"][kind + "_masks"])
        result[kind] = {"visits": sum(masks.values()), "masks": dict(masks),
            "first_failed": {k: sum(n for mask, n in masks.items() if int(mask) and
                (int(mask) & -int(mask)) == bit) for k, bit in BITS.items()},
            "overlap": {k: sum(n for mask, n in masks.items() if int(mask) & bit) for k, bit in BITS.items()},
            "produced": masks.get("0", 0)}
    result["window_parent_limits"] = {k: sum(any(int(mask) & bit for mask in p["counts"]["window_masks"])
                                             for p in parents) for k, bit in BITS.items()}
    result["window_parent_sufficient"] = {name: sum(any(not int(mask) & excluded
        for mask in p["counts"]["window_masks"]) for p in parents) for name, excluded in
        (("energy", BITS["energy"]), ("water", BITS["water"]), ("bank", BITS["bank"]),
         ("resources", BITS["energy"] | BITS["water"]),
         ("resources_and_bank", BITS["energy"] | BITS["water"] | BITS["bank"]))}
    shortfalls = Counter()
    for p in parents:
        shortfalls.update(p["counts"]["shortfalls"])
    result["shortfalls"] = dict(shortfalls)
    return result


def aggregate(cases: list[dict], species: str | None = None) -> dict:
    parents = [p for c in cases for p in c["parents"] if p["plant"]["parent"] and
               funnel.survived_day(p["plant"], END) and (species is None or p["plant"]["species"] == species)]
    return {window: {kind: summarize([p for p in parents if p["plant"]["birth_tick"] >= start and
        (p["counts"]["productions"] == 0) == (kind == "no_seed")]) for kind in ("no_seed", "seed_producer")}
        for window, start in (("whole", 0), ("closing", 112 * DAY + 1))}


def analysis(cases: list[dict]) -> dict:
    require([(r["case"], r["arm"]) for r in cases] == [(c, a) for c in funnel.confirmation.specification()
            for a in funnel.population.ARMS], "Incomplete/duplicate/reordered gate panel")
    return {"groups": {a: aggregate([r for r in cases if r["arm"] == a]) for a in funnel.population.ARMS},
        "partitions": {field: {value: {a: aggregate([r for r in cases if r["arm"] == a and
            (field == "species" or r["case"][field] == value)], value if field == "species" else None)
            for a in funnel.population.ARMS} for value in values} for field, values in
            (("seed", funnel.confirmation.SEEDS), ("scenario", funnel.population.LAYOUTS),
             ("policy", funnel.population.POLICIES), ("species", funnel.SPECIES))}}


def validate_report(report: dict, prior: dict) -> None:
    require(report["protocol"] == RULE and report["input_sha256"] == INPUT_SHA and
            analysis(report["cases"]) == report["analysis"], "Changed gate analysis")
    for row, old in zip(report["cases"], prior["cases"]):
        validate_case(row, old)


def compact(report: dict) -> dict:
    return {**{k: v for k, v in report.items() if k != "cases"}, "cases": [
        {**{k: v for k, v in c.items() if k != "parents"}, "cohorts": aggregate([c]),
         "parents_sha256": hashlib.sha256(json.dumps(c["parents"], sort_keys=True).encode()).hexdigest()}
        for c in report["cases"]]}


def frozen(build: Path, prior: dict) -> dict:
    sources = source_hashes(ROOT)
    files = {PROTOCOL, "sim/garden_season_production_gates.py", "sim/test_garden_season_production_gates.py",
             "sim/garden_season_reproduction_funnel.py", "sim/CMakeLists.txt", *prior["sources"]}
    sources.update({name: digest(ROOT / name) for name in files})
    confirmation = funnel.load_input()["frozen"]
    for name, sha in confirmation["sources"].items():
        if name not in {"src/garden_world.c", "sim/CMakeLists.txt"}:
            require(digest(ROOT / name) == sha, "Changed non-observer dependency: " + name)
    flags = build_flags(build / "CMakeCache.txt")
    require(flags == confirmation["flags"], "Changed ecology build flags")
    return {"sources": sources, "flags": flags, "cache_sha256": digest(build / "CMakeCache.txt"),
            "collector_sha256": digest(build / "toy-factory-garden-production-audit")}


def capture(build: Path, row: dict, target: Path) -> None:
    spec = row["case"]
    command = [build / "toy-factory-garden-production-audit", spec["scenario"], spec["policy"],
               str(int(spec["seed"], 16)), row["arm"], str(END)]
    with tempfile.TemporaryFile() as stream:
        subprocess.run(list(map(str, command)), stdout=stream, stderr=subprocess.PIPE, check=True, timeout=300)
        stream.seek(0)
        with target.open("xb") as raw, gzip.GzipFile(filename="", fileobj=raw, mode="wb", mtime=0) as out:
            shutil.copyfileobj(stream, out)


def run_job(item) -> dict:
    build, out, bundle, row, collect = item
    target = funnel.population.path(out, row["case"], row["arm"])
    repeat = funnel.population.path(out, row["case"], row["arm"], True)
    if collect:
        capture(build, row, target)
        capture(build, row, repeat)
    require(digest(target) == digest(repeat), "Nonrepeatable observer output")
    result = audit_trace(target, funnel.population.path(bundle, row["case"], row["arm"]), row)
    print("Verified production gates " + identity(row["case"]) + " / " + row["arm"], flush=True)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("collect", "verify"))
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--bundle", type=Path, default=Path("artifacts/garden-seasonal-seedling-confirmation"))
    parser.add_argument("--build", type=Path, default=Path("artifacts/build-host-production-gates"))
    parser.add_argument("--jobs", type=int, default=4)
    args = parser.parse_args()
    if not 1 <= args.jobs <= 4:
        parser.error("Require 1..4 independent workers")
    prior, build = load_input(), args.build.resolve()
    provenance = frozen(build, prior)
    if args.command == "collect":
        args.out.mkdir(parents=True, exist_ok=False)
    with ProcessPoolExecutor(max_workers=args.jobs) as pool:
        cases = list(pool.map(run_job, ((build, args.out, args.bundle, row, args.command == "collect")
                                       for row in prior["cases"])))
    require(frozen(build, prior) == provenance, "Sources/binary changed during observation")
    report = {"protocol": RULE, "input_sha256": INPUT_SHA, "frozen": provenance,
              "cases": cases, "analysis": analysis(cases)}
    validate_report(report, prior)
    if args.command == "verify":
        require(report == json.loads((args.out / "results.json").read_text()) and
                compact(report) == json.loads((args.out / "summary.json").read_text()), "Changed retained results")
    else:
        (args.out / "results.json").write_text(json.dumps(report, indent=2) + "\n")
        (args.out / "summary.json").write_text(json.dumps(compact(report), indent=2) + "\n")
    print("All 64 production traces reconcile with frozen ecology states and seed histories", flush=True)


if __name__ == "__main__":
    main()
