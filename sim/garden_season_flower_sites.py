#!/usr/bin/env python3
"""Read-only flower reach at every purchase on the frozen origin-screen trajectories."""

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

import garden_season_flower_origin as origin
import garden_season_production_gates as gates
from garden_season_confirmation import build_flags
from garden_season_recruitment import digest, identity
from garden_seasons import require, source_hashes

ROOT, DAY, END, ARMS = origin.ROOT, origin.DAY, origin.END, origin.ARMS
RULE = "seasonal-flower-sites-v1"
PROTOCOL = "benchmarks/garden-seasons/flower-sites-protocol.md"
INPUT_SHA = "7ef2def2a33d1c3ebc3840f19d648501d412c40d28dbaa14897f0532c93e9230"
VIEWS = {"all": 126, "local": 38}
CLASSES = ("actual_reach_open", "flower_reach_available", "open_outside_flower_reach", "world_closed")
WINDOWS = {"whole": 0, "closing": 112 * DAY}
CHILD_OUTCOMES = origin.diagnosis.OUTCOMES
SPECIES = origin.funnel.SPECIES
ALLOWED_CHANGES = {"src/garden_world.c", "sim/CMakeLists.txt", "sim/garden_production_audit.c"}


def load_input() -> dict:
    folder = ROOT / "benchmarks/garden-seasons"
    raw = gzip.decompress((folder / "flower-origin-histories.json.gz").read_bytes())
    require(hashlib.sha256(raw).hexdigest() == INPUT_SHA, "Changed origin evidence")
    result = json.loads(raw)
    origin.validate_report(result, origin.diagnosis.load_input())
    require(origin.compact(result) == json.loads((folder / "flower-origin-summary.json").read_text()),
            "Changed origin summary")
    return result


def pixel_column(x: int) -> int:
    require(type(x) is int and 0 <= x <= 255, "Invalid flower x")
    return min(27, max(0, (x - 8) // 8))


def placements(column: int, trait: int) -> list[int]:
    require(type(column) is int and 0 <= column < 28 and type(trait) is int and -2 <= trait <= 2,
            "Invalid origin/dispersal")
    result = []
    for choice in range(14):
        offset = (-1 if choice % 2 == 0 else 1) * (3 + trait + choice // 2)
        landing = column + offset
        if not 0 <= landing < 28:
            landing = column - offset
        result.append(min(27, max(0, landing)))
    return result


def branch_weights() -> list[int]:
    # Nonzero xorshift32 output space; distance consumes the upper 31 bits.
    quotient, remainder = divmod(1 << 31, 7)
    return [quotient + int(i // 2 < remainder) - int(i == 0) for i in range(14)]


WEIGHTS = branch_weights()
TOTAL_WEIGHT = (1 << 32) - 1


def bitset(columns) -> int:
    return sum(1 << c for c in set(columns))


def validate_sites(sites: list, context: dict) -> None:
    require(set(context) == {"nodes", "bases", "cold"} and type(context["nodes"]) is int and
            4 <= context["nodes"] <= 256 and type(context["cold"]) is bool and
            1 <= len(context["bases"]) <= 8 and
            all(type(c) is int and 0 <= c < 28 for c in context["bases"]) and len(sites) == 28,
            "Invalid site context")
    for column, site in enumerate(sites):
        require(len(site) == 3 and all(type(v) is int and 0 <= v <= 255 for v in site),
                "Invalid site row")
        moisture, light, mask = site
        expected = (2 * (moisture < 12) + 4 * (light < 80) + 8 * (len(context["bases"]) == 8) +
                    16 * (context["nodes"] > 252) + 32 * any(abs(column - c) < 3 for c in context["bases"]) +
                    64 * context["cold"])
        require(mask == expected, "Site mask disagrees with moisture/light/spacing/capacity/cold")


def evaluate(purchase: dict, sites: list, arm: str) -> dict:
    require(arm in ARMS and type(purchase["choice"]) is int and 0 <= purchase["choice"] < 14 and
            type(purchase["id"]) is int and purchase["id"] > 0 and type(purchase["species"]) is int and
            0 <= purchase["species"] < 3 and type(purchase["base"]) is int and 0 <= purchase["base"] < 28,
            "Invalid purchase identity/draw")
    actual = placements(purchase["origin"], purchase["dispersal"])
    require(type(purchase["columns"]) is int and purchase["columns"] == bitset(actual) and
            type(purchase["column"]) is int and purchase["column"] == actual[purchase["choice"]],
            "Actual draw/support mismatch")
    flowers = purchase["flowers"]
    require(1 <= len(flowers) <= 256 and all(len(f) == 4 and all(type(v) is int for v in f) and
            0 <= f[0] < 256 and 0 <= f[2] <= 255 for f in flowers), "Invalid eligible flowers")
    indices = [f[0] for f in flowers]
    require(indices == sorted(set(indices)) and purchase["selected"] == indices[0],
            "Changed first-ready flower selection")
    columns = [placements(pixel_column(f[1]), purchase["dispersal"]) for f in flowers]
    require(all(f[3] == bitset(c) for f, c in zip(flowers, columns)) and purchase["origin"] ==
            (purchase["base"] if arm == "base" else pixel_column(flowers[0][1])), "Changed origin/support rule")
    result = {"flowers": len(flowers), "origins": len({pixel_column(f[1]) for f in flowers}), "views": {}}
    for name, constraint_mask in VIEWS.items():
        open_columns = {i for i, s in enumerate(sites) if not s[2] & constraint_mask}
        weight = lambda c: sum(w for landing, w in zip(c, WEIGHTS) if landing in open_columns)
        actual_weight = weight(actual)
        flower_weights = [weight(c) for c in columns]
        best = max(flower_weights)
        category = CLASSES[0 if actual_weight else 1 if best else 2 if open_columns else 3]
        result["views"][name] = {"category": category, "world_open_columns": bitset(open_columns),
            "actual_open_columns": bitset(set(actual) & open_columns), "actual_open_weight": actual_weight,
            "first_flower_open_weight": flower_weights[0], "best_flower_open_weight": best,
            "best_flowers": [f[0] for f, w in zip(flowers, flower_weights) if w == best],
            "better_flower": best > flower_weights[0],
            "first_flower_rescuable": flower_weights[0] == 0 < best,
            "actual_landing_open": purchase["column"] in open_columns}
    return result


def summarize(events: list[dict]) -> dict:
    result = {"purchases": len(events), "flowers": dict(sorted(Counter(str(e["diagnostics"]["flowers"]) for e in events).items())),
        "origins": dict(sorted(Counter(str(e["diagnostics"]["origins"]) for e in events).items())),
        "outcomes": {s: sum(e["child_outcome"] == s for e in events) for s in CHILD_OUTCOMES}, "views": {}}
    for name in VIEWS:
        values = [e["diagnostics"]["views"][name] for e in events]
        result["views"][name] = {"classes": {c: sum(v["category"] == c for v in values) for c in CLASSES},
            **{k: sum(v[k] for v in values) for k in ("better_flower", "first_flower_rescuable", "actual_landing_open",
                "actual_open_weight", "first_flower_open_weight", "best_flower_open_weight")},
            "class_outcomes": {c: {s: sum(e["child_outcome"] == s and e["diagnostics"]["views"][name]["category"] == c
                for e in events) for s in CHILD_OUTCOMES} for c in CLASSES}}
    result["global_limits"] = {"cold": sum(e["context"]["cold"] for e in events),
        "plant_capacity": sum(len(e["context"]["bases"]) == 8 for e in events),
        "node_capacity": sum(e["context"]["nodes"] > 252 for e in events)}
    result["landing_blockers"] = dict(sorted(Counter(str(e["sites"][e["purchase"]["column"]][2]) for e in events).items()))
    return result


def windows(events: list[dict]) -> dict:
    return {w: summarize([e for e in events if e["tick"] > start]) for w, start in WINDOWS.items()}


def validate_case(case: dict, old: dict, arm: str) -> None:
    saved = old["arms"][arm]
    require(case["case"] == old["case"] and case["arm"] == arm and case["worlds"] == END // 15 + 1 and
            case["source_trace_sha256"] == old["traces"][arm], "Changed case/source/coverage")
    seeds = saved["ledger"]["seeds"]
    parents = {p["plant"]["id"]: p for p in saved["ledger"]["parents"]}
    require(len(case["events"]) == len(seeds), "Incomplete or duplicate purchases")
    for index, (event, seed) in enumerate(zip(case["events"], seeds)):
        p = event["purchase"]
        parent = parents[seed["parent"]]
        require(event["seed_index"] == index and event["tick"] == seed["created_tick"] and
                p["id"] == seed["parent"] and p["column"] == seed["column"] and
                p["species"] == SPECIES.index(seed["species"]) and p["base"] == parent["column"] and
                event["fate"] == seed["outcome"] and event["child_outcome"] ==
                origin.diagnosis.child_outcome(seed, parents), "Purchase/outcome attribution mismatch")
        validate_sites(event["sites"], event["context"])
        require(event["diagnostics"] == evaluate(p, event["sites"], arm), "Changed reachable-site analysis")
    require(case["summary"] == windows(case["events"]), "Changed per-world summary")


def audit_trace(trace: Path, original: Path, old: dict, arm: str) -> dict:
    require(digest(original) == old["traces"][arm], "Changed original trajectory")
    trace_sha = digest(trace)
    saved = old["arms"][arm]
    parents = {p["plant"]["id"]: p for p in saved["ledger"]["parents"]}
    seeds = saved["ledger"]["seeds"]
    events, worlds = [], 0
    with gzip.open(trace, "rt") as stream:
        header = json.loads(next(stream))
        expected = {"version": 2, "flower_audit": "flower-sites-v1", "site_phase": "post-light-refresh",
            "flower_fields": ["node", "x", "y", "columns"], "site_fields": ["moisture", "light", "blockers"],
            "scenario": old["case"]["scenario"], "policy": old["case"]["policy"], "seed": old["case"]["seed"],
            "arm": "guard", "end": END, "climate": "seasonal", "dispersal": "wide-v1", "fields": list(gates.FIELDS)}
        if arm == "flower":
            expected["seed_origin"] = origin.ORIGIN
        require(header == expected, "Wrong observation phase/environment/metadata")
        original_worlds = (w for w, _, _ in origin.population.reserve.groups(original))
        for line, world in zip_longest(stream, original_worlds):
            require(line is not None and world is not None, "Truncated/extended observer trajectory")
            native = json.loads(line)
            tick = worlds * 15
            require(native["tick"] == world["tick"] == tick and native["hash"] == world["hash"] and
                    native["created"] == world["seeds_created"], "Observer changed authoritative state")
            plants = world["plants"] if tick else []
            require(len(native["visits"]) == len(plants), "Missing sequential production visit")
            visits = [gates.decode(v, tick, p, world["sun_strength"]) for v, p in zip(native["visits"], plants)]
            produced = [v for v in visits if v["produced"]]
            require([v["id"] for v in produced] == [p["id"] for p in native["purchases"]] ==
                    [s["parent"] for s in world["seeds"] if s["age"] == 0], "Missing/extra purchase or wrong order")
            bank = len(world["seeds"]) - len(produced)
            for v in visits:
                require(v["bank"] == bank, "Changed sequential final-slot admission")
                bank += v["produced"]
            if produced:
                context = {"nodes": world["nodes"], "bases": [p["column"] for p in plants],
                           "cold": world["climate"]["cold"]}
                validate_sites(native["sites"], context)
            else:
                require(native["sites"] == [], "Sites emitted outside a purchase opportunity")
            seen = set()
            for purchase, visit in zip(native["purchases"], produced):
                ident = purchase["id"]
                plant = next(p for p in plants if p["id"] == ident)
                require(len(events) < len(seeds), "Extra seed purchase")
                seed = seeds[len(events)]
                require((ident, tick, purchase["column"]) == (seed["parent"], seed["created_tick"], seed["column"]) and
                        purchase["dispersal"] == plant["genome"][7] and purchase["base"] == plant["column"] and
                        purchase["species"] == SPECIES.index(plant["species"]) and
                        len(purchase["flowers"]) == visit["ready"] and purchase["selected"] == visit["flower_index"],
                        "Wrong parent/flower/trait census")
                indices = {f[0] for f in purchase["flowers"]}
                require(not seen & indices and all(0 <= i < world["nodes"] for i in indices), "Shared/invalid flower ownership")
                seen.update(indices)
                for s in world["seeds"]:
                    require((s["blockers"] & ~1) == native["sites"][s["column"]][2], "Stale site/light masks")
                event = {"tick": tick, "hash": world["hash"], "seed_index": len(events), "context": context,
                    "sites": native["sites"], "purchase": purchase, "fate": seed["outcome"],
                    "child_outcome": origin.diagnosis.child_outcome(seed, parents),
                    "diagnostics": evaluate(purchase, native["sites"], arm)}
                events.append(event)
            require(len(events) == native["created"], "Unaccounted seed purchase")
            worlds += 1
    require(worlds == END // 15 + 1 and trace_sha == digest(trace) and digest(original) == old["traces"][arm],
            "Incomplete/changed observations")
    result = {"case": old["case"], "arm": arm, "worlds": worlds, "source_trace_sha256": old["traces"][arm],
              "observation_sha256": trace_sha, "events": events, "summary": windows(events)}
    validate_case(result, old, arm)
    return result


def analysis(cases: list[dict]) -> dict:
    require([(c["case"], c["arm"]) for c in cases] == [(s, a) for s in origin.confirmation.specification() for a in ARMS],
            "Incomplete/duplicate/reordered observation panel")
    groups = {a: windows([e for c in cases if c["arm"] == a for e in c["events"]]) for a in ARMS}
    partitions = {field: {value: {a: windows([e for c in cases if c["case"][field] == value and c["arm"] == a
                    for e in c["events"]]) for a in ARMS} for value in values}
                  for field, values in (("seed", origin.confirmation.SEEDS), ("scenario", origin.population.LAYOUTS),
                                        ("policy", origin.population.POLICIES))}
    partitions["species"] = {s: {a: windows([e for c in cases if c["arm"] == a for e in c["events"]
        if e["purchase"]["species"] == i]) for a in ARMS} for i, s in enumerate(SPECIES)}
    return {"groups": groups, "partitions": partitions, "worlds_with": {a: {w: {
        "purchases": sum(c["summary"][w]["purchases"] > 0 for c in cases if c["arm"] == a),
        "better_flower_local": sum(c["summary"][w]["views"]["local"]["better_flower"] > 0 for c in cases if c["arm"] == a),
        "first_flower_rescuable_local": sum(c["summary"][w]["views"]["local"]["first_flower_rescuable"] > 0
                                            for c in cases if c["arm"] == a)} for w in WINDOWS} for a in ARMS}}


def validate_report(report: dict, prior: dict) -> None:
    require(report["protocol"] == RULE and report["input_sha256"] == INPUT_SHA and
            report["analysis"] == analysis(report["cases"]), "Changed observation identity/analysis")
    for case, (old, arm) in zip(report["cases"], ((c, a) for c in prior["cases"] for a in ARMS)):
        validate_case(case, old, arm)


def compact(report: dict) -> dict:
    return {**{k: v for k, v in report.items() if k != "cases"}, "cases": [
        {**{k: v for k, v in c.items() if k != "events"}, "events_sha256":
         hashlib.sha256(json.dumps(c["events"], sort_keys=True).encode()).hexdigest()} for c in report["cases"]]}


def frozen(builds: dict, prior: dict) -> dict:
    sources = source_hashes(ROOT)
    names = {PROTOCOL, "sim/garden_season_flower_sites.py", "sim/test_garden_season_flower_sites.py",
             *prior["frozen"]["sources"]}
    sources.update({n: digest(ROOT / n) for n in names})
    for name, sha in prior["frozen"]["sources"].items():
        if name not in ALLOWED_CHANGES:
            require(digest(ROOT / name) == sha, "Changed non-observation source: " + name)
    configs = {}
    for arm, build in builds.items():
        flags = build_flags(build / "CMakeCache.txt")
        require(flags == prior["frozen"]["builds"][arm]["flags"], "Changed ecology flags")
        configs[arm] = {"flags": flags, "cache_sha256": digest(build / "CMakeCache.txt"),
            "observer_sha256": digest(build / "toy-factory-garden-production-audit"), "sizes": origin.capacity.sizes(build)}
        require(configs[arm]["sizes"] == prior["frozen"]["builds"][arm]["sizes"], "Changed world storage")
    return {"sources": sources, "builds": configs}


def capture(build: Path, old: dict, target: Path) -> None:
    spec = old["case"]
    command = [build / "toy-factory-garden-production-audit", spec["scenario"], spec["policy"],
               str(int(spec["seed"], 16)), "guard", str(END), "--flower-sites"]
    with tempfile.TemporaryFile() as stream:
        subprocess.run(list(map(str, command)), stdout=stream, stderr=subprocess.PIPE, check=True, timeout=300)
        stream.seek(0)
        with target.open("xb") as raw, gzip.GzipFile(filename="", fileobj=raw, mode="wb", mtime=0) as compressed:
            shutil.copyfileobj(stream, compressed)


def run_job(item) -> dict:
    builds, output, bundle, old, arm, collect = item
    target = origin.population.path(output, old["case"], arm)
    repeat = origin.population.path(output, old["case"], arm, True)
    if collect:
        capture(builds[arm], old, target)
        capture(builds[arm], old, repeat)
    require(digest(target) == digest(repeat), "Nonrepeatable observation trace")
    result = audit_trace(target, origin.population.path(bundle, old["case"], arm), old, arm)
    saved = output / (identity(old["case"]) + "-" + arm + ".json")
    if collect:
        saved.write_text(json.dumps(result, indent=2) + "\n")
    else:
        require(result == json.loads(saved.read_text()), "Nonrepeatable site analysis")
    print("Verified flower sites " + identity(old["case"]) + " " + arm, flush=True)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("collect", "verify"))
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--bundle", type=Path, default=Path("artifacts/garden-seasonal-flower-origin"))
    parser.add_argument("--base", type=Path, default=Path("artifacts/build-host-flower-sites-base"))
    parser.add_argument("--flower", type=Path, default=Path("artifacts/build-host-flower-sites-flower"))
    parser.add_argument("--jobs", type=int, default=4)
    args = parser.parse_args()
    if not 1 <= args.jobs <= 4:
        parser.error("Require 1..4 independent workers")
    prior = load_input()
    builds = {a: getattr(args, a).resolve() for a in ARMS}
    provenance = frozen(builds, prior)
    if args.command == "collect":
        args.out.mkdir(parents=True, exist_ok=False)
    with ProcessPoolExecutor(max_workers=args.jobs) as pool:
        cases = list(pool.map(run_job, ((builds, args.out, args.bundle, old, a, args.command == "collect")
                                       for old in prior["cases"] for a in ARMS)))
    require(frozen(builds, prior) == provenance, "Inputs changed during site observation")
    report = {"protocol": RULE, "input_sha256": INPUT_SHA, "frozen": provenance, "cases": cases, "analysis": analysis(cases)}
    validate_report(report, prior)
    if args.command == "collect":
        (args.out / "results.json").write_text(json.dumps(report, indent=2) + "\n")
        (args.out / "summary.json").write_text(json.dumps(compact(report), indent=2) + "\n")
    else:
        require(report == json.loads((args.out / "results.json").read_text()) and
                compact(report) == json.loads((args.out / "summary.json").read_text()), "Changed portable evidence")
    print("All 64 observed worlds verified; purchases=" + str(sum(len(c["events"]) for c in cases)), flush=True)


if __name__ == "__main__":
    main()
