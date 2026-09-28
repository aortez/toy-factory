#!/usr/bin/env python3
"""Exact seed waiting checks on the frozen flower-origin panel; no intervention."""

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

import garden_season_flower_sites as sites
from garden_season_confirmation import build_flags
from garden_season_recruitment import digest, identity
from garden_seasons import require, source_hashes

origin = sites.origin
ROOT, DAY, END, ARMS = sites.ROOT, sites.DAY, sites.END, sites.ARMS
RULE = "seasonal-seed-waits-v1"
PROTOCOL = "benchmarks/garden-seasons/seed-waits-protocol.md"
INPUT_SHA = "0023876df42885ebdaae940ab13af3e442434f93cb3c51c1ddd4075a6f39c18d"
FIELDS = ("parent", "child", "age", "generation", "column", "species", "nodes", "plants",
          "moisture", "light", "blockers", "outcome")
BITS = {"dormancy": 1, "moisture": 2, "light": 4, "plant_capacity": 8,
        "node_capacity": 16, "spacing": 32, "cold": 64}
LIFETIME, DORMANCY = origin.funnel.LIFETIME, origin.funnel.DORMANCY
ALLOWED_CHANGES = {"sim/garden_production_audit.c", "sim/CMakeLists.txt"}


def load_input() -> tuple[dict, dict]:
    folder = ROOT / "benchmarks/garden-seasons"
    raw = gzip.decompress((folder / "flower-sites-purchases.json.gz").read_bytes())
    require(hashlib.sha256(raw).hexdigest() == INPUT_SHA, "Changed purchase evidence")
    purchases, old = json.loads(raw), sites.load_input()
    sites.validate_report(purchases, old)
    require(sites.compact(purchases) == json.loads((folder / "flower-sites-summary.json").read_text()),
            "Changed purchase summary")
    return purchases, old


def header(spec: dict, arm: str, end: int = END) -> dict:
    result = {"version": 3, "seed_audit": "seed-waits-v1", "site_phase": "sequential-check",
        "attempt_fields": list(FIELDS), "sun_fields": ["phase", "strength", "ray_step_x_q4"],
        "scenario": spec["scenario"], "policy": spec["policy"], "seed": spec["seed"],
        "arm": "guard", "end": end, "climate": "seasonal", "dispersal": "wide-v1"}
    if arm == "flower":
        result["seed_origin"] = origin.ORIGIN
    return result


def decode(values: list, seed: dict, tick: int, nodes: int, plants: list, cold: bool) -> dict:
    require(len(values) == len(FIELDS) and all(type(v) is int and v >= 0 for v in values),
            "Malformed seed receipt")
    a = dict(zip(FIELDS, values))
    require(a["parent"] == seed["parent"] and a["age"] == (tick - seed["created_tick"]) // 15 and
            a["generation"] == seed["generation"] and a["column"] == seed["column"] and
            a["species"] == sites.SPECIES.index(seed["species"]) and a["nodes"] == nodes and
            a["plants"] == len(plants) and 1 <= a["age"] <= LIFETIME and 0 <= nodes <= 256 and
            len(plants) <= 8 and a["moisture"] <= 255 and a["light"] <= 255,
            "Wrong sequential seed identity/inventory")
    if a["age"] == LIFETIME:
        require(a["outcome"] == 1 and all(a[k] == 0 for k in ("child", "moisture", "light", "blockers")) and
                seed["outcome"] == "expired" and seed["resolved_tick"] == tick,
                "Expiration must precede resource checks")
        return a
    expected = (int(a["age"] < DORMANCY) + 2 * (a["moisture"] < 12) + 4 * (a["light"] < 80) +
        8 * (len(plants) == 8) + 16 * (nodes > 252) +
        32 * any(abs(seed["column"] - p["column"]) < 3 for p in plants) + 64 * cold)
    require(a["blockers"] == expected and a["outcome"] == (0 if expected else 2),
            "Receipt disagrees with exact germination checks")
    if expected:
        require(a["child"] == 0 and (seed["resolved_tick"] is None or tick < seed["resolved_tick"]),
                "Resolved seed was retained")
    else:
        require(seed["outcome"] == "germinated" and seed["resolved_tick"] == tick and
                a["child"] == seed["child"], "Wrong germination resolution")
    return a


def new_record(index: int, seed: dict, purchase: dict) -> dict:
    return {"seed_index": index, **{k: seed[k] for k in ("parent", "generation", "column", "species",
        "created_tick", "resolved_tick", "outcome", "child")},
        "child_outcome": purchase["child_outcome"], "purchase_class": purchase["diagnostics"]["views"]["all"]["category"],
        "purchase_site": purchase["sites"][seed["column"]], "runs": [], "first": None,
        "first_mature": None, "terminal_pair": [], "spacing_releases": []}


def add_check(record: dict, snapshot: dict) -> None:
    """Only real checks enter this function, never zero-filled expiry receipts."""
    age, mask, dim = snapshot["age"], snapshot["mask"], snapshot["sun"] < 80
    runs = record["runs"]
    require(age == (runs[-1][1] + 1 if runs else 1) and age < LIFETIME,
            "Skipped, repeated or expired check")
    if runs and runs[-1][2:] == [mask, dim]:
        runs[-1][1] = age
    else:
        runs.append([age, age, mask, dim])
    if record["first"] is None:
        record["first"] = snapshot
    if age == DORMANCY:
        record["first_mature"] = snapshot
    previous = record["terminal_pair"][-1] if record["terminal_pair"] else None
    if previous and previous["mask"] & 32 and not mask & 32:
        require(previous["neighbors"] and not snapshot["neighbors"] and
                set(previous["neighbors"]) <= set(snapshot["removed"]),
                "Spacing cleared without reclaiming occupied neighbors")
        record["spacing_releases"].append({"age": age, "ids": previous["neighbors"],
                                            "removed": snapshot["removed"]})
    record["terminal_pair"] = ([previous] if previous else []) + [snapshot]


def audit_trace(trace: Path, original: Path, old: dict, purchase_case: dict) -> dict:
    arm = purchase_case["arm"]
    require(digest(original) == old["traces"][arm], "Changed original trajectory")
    trace_sha = digest(trace)
    saved = old["arms"][arm]["ledger"]["seeds"]
    records = [new_record(i, s, p) for i, (s, p) in enumerate(zip(saved, purchase_case["events"]))]
    require(len(records) == len(saved) == len(purchase_case["events"]), "Incomplete purchase join")
    lookup = {(s["parent"], s["created_tick"]): i for i, s in enumerate(saved)}
    worlds, checks, expired, germinated, previous = 0, 0, 0, 0, None
    with gzip.open(trace, "rt") as stream:
        require(json.loads(next(stream)) == header(old["case"], arm), "Changed audit header/phase/rules")
        originals = (w for w, _, _ in origin.population.reserve.groups(original))
        for line, world in zip_longest(stream, originals):
            require(line is not None and world is not None, "Truncated or extra ecology observation")
            row = json.loads(line)
            tick = worlds * 15
            require(row["tick"] == world["tick"] == tick and row["hash"] == world["hash"] and
                    row["created"] == world["seeds_created"] and
                    row["sun"][:2] == [world["sun_phase"], world["sun_strength"]],
                    "Observer changed authoritative state/weather")
            require(len(row["sun"]) == 3 and -12 <= row["sun"][2] <= 12, "Invalid solar direction")
            if previous is None:
                require(row["attempts"] == [] and row["stages"] == [[0, 0, 0]] * 5 and not world["seeds"],
                        "Unexpected initial attempts")
            else:
                prior_plants = {p["id"]: p for p in previous["plants"]}
                current = {p["id"]: p for p in world["plants"]}
                removed = [i for i in prior_plants if i not in current]
                require(all(prior_plants[i]["dead"] for i in removed), "Living neighbor disappeared")
                plants = [p for p in world["plants"] if p["id"] in prior_plants]
                newborns = [p for p in world["plants"] if p["id"] not in prior_plants]
                nodes = previous["nodes"] - sum(prior_plants[i]["nodes"] for i in removed)
                stages = row["stages"]
                require(len(stages) == 5 and stages[0] == [previous["nodes"], len(prior_plants), len(previous["seeds"])] and
                        stages[1] == [nodes, len(plants), len(previous["seeds"])] and
                        len(row["attempts"]) == len(previous["seeds"]), "Changed pre-check inventories")
                births, resolutions = 0, 0
                for values, pending in zip(row["attempts"], previous["seeds"]):
                    key = origin.funnel.seed_key(pending, tick - 15)
                    index = lookup[key]
                    seed = saved[index]
                    a = decode(values, seed, tick, nodes, plants, world["climate"]["cold"])
                    if a["outcome"] == 1:
                        expired += 1
                        resolutions += 1
                        continue
                    require(a["light"] <= row["sun"][1], "Ground light exceeds unobstructed light")
                    neighbors = sorted(p["id"] for p in plants if abs(p["column"] - seed["column"]) < 3)
                    snapshot = {"age": a["age"], "mask": a["blockers"], "moisture": a["moisture"],
                        "light": a["light"], "sun": row["sun"][1], "phase": row["sun"][0],
                        "rain_rate": world["rain_rate"],
                        "rain_deposited": world["rain_deposited"] - previous["rain_deposited"],
                        "nodes": nodes, "plants": len(plants), "cold": world["climate"]["cold"],
                        "neighbors": neighbors, "removed": removed}
                    add_check(records[index], snapshot)
                    checks += 1
                    if a["outcome"] == 2:
                        require(births < len(newborns) and newborns[births]["id"] == a["child"] and
                                newborns[births]["parent"] == a["parent"] and
                                newborns[births]["column"] == a["column"], "Wrong sequential newborn")
                        plants.append(newborns[births])
                        births += 1
                        resolutions += 1
                        germinated += 1
                        nodes += 4
                after_seeds = len(previous["seeds"]) - resolutions
                purchases = sum(s["age"] == 0 for s in world["seeds"])
                require(births == len(newborns) and stages[2] == [nodes, len(plants), after_seeds] and
                        world["nodes"] >= nodes and stages[3] == [world["nodes"], len(plants), after_seeds] and
                        stages[4] == [world["nodes"], len(plants), len(world["seeds"])] and
                        after_seeds + purchases == len(world["seeds"]) and
                        expired == world["seeds_expired"] and germinated == world["births"],
                        "Changed resolution/growth/reproduction inventory")
            previous = world
            worlds += 1
    require(digest(trace) == trace_sha and digest(original) == old["traces"][arm], "Inputs changed during analysis")
    result = {"case": old["case"], "arm": arm, "source_trace_sha256": old["traces"][arm],
              "trace_sha256": trace_sha, "worlds": worlds, "checks": checks, "records": records}
    result["summary"] = cohorts(records)
    validate_case(result, old, purchase_case)
    return result


def counts(values) -> dict:
    return dict(sorted(Counter(str(v) for v in values).items(), key=lambda p: int(p[0])))


def exposures(record: dict) -> dict:
    histogram = Counter()
    dim, shaded = 0, 0
    for start, end, mask, global_dim in record["runs"]:
        samples = max(0, end - max(start, DORMANCY) + 1)
        histogram[str(mask)] += samples
        if mask & 4:
            dim += samples if global_dim else 0
            shaded += samples if not global_dim else 0
    return {"mature_checks": sum(histogram.values()), "masks": {k: v for k, v in histogram.items() if v},
            "globally_dim": dim, "bright_sun_but_shaded": shaded}


def age_band(age: int) -> str:
    return "under_1_day" if age < 256 else "1_to_4_days" if age < 1024 else "4_to_16_days" if age < 4096 else "16_to_32_days"


def summarize(records: list[dict]) -> dict:
    births = [r for r in records if r["outcome"] == "germinated"]
    pairs = [r["terminal_pair"] for r in births]
    histogram = Counter()
    exposure = [exposures(r) for r in records]
    for e in exposure:
        histogram.update(e["masks"])
    ages = sorted((r["resolved_tick"] - r["created_tick"]) // 15 for r in births)
    quantiles = {name: ages[max(0, (len(ages) * n + 99) // 100 - 1)] if ages else None
                 for name, n in (("min", 0), ("median", 50), ("p90", 90), ("max", 100))}
    lead_times = {name: [] for name in BITS}
    for r in births:
        final = r["terminal_pair"][-1]["age"]
        for name, bit in BITS.items():
            blocked = [end for _, end, mask, _ in r["runs"] if mask & bit]
            if blocked:
                lead_times[name].append(final - max(blocked))
    return {"seeds": len(records), "outcomes": dict(Counter(r["outcome"] for r in records)),
        "child_outcomes": {s: sum(r["child_outcome"] == s for r in records) for s in sites.CHILD_OUTCOMES},
        "wait_age_ecology_ticks": quantiles,
        "age_bands": {fate: dict(Counter(age_band(((r["resolved_tick"] if r["resolved_tick"] is not None else END) -
            r["created_tick"]) // 15) for r in records if r["outcome"] == fate)) for fate in ("germinated", "expired", "pending")},
        "last_masks_before_germination": counts(p[-2]["mask"] for p in pairs),
        "last_bits_before_germination": {n: sum(bool(p[-2]["mask"] & b) for p in pairs) for n, b in BITS.items()},
        "last_light_context": dict(Counter("sun_became_bright_enough" if p[-2]["sun"] < 80 else
            "previously_bright_sun_but_shaded" for p in pairs if p[-2]["mask"] & 4)),
        "last_water_context": dict(Counter(("rain" if p[-1]["rain_deposited"] else "no_rain") + "+" +
            ("reclaim" if p[-1]["removed"] else "no_reclaim") for p in pairs if p[-2]["mask"] & 2)),
        "ever_blocked_before_birth": {n: len(v) for n, v in lead_times.items()},
        "clearance_lead_ecology_ticks": {n: counts(v) for n, v in lead_times.items()},
        "spacing_releases": sum(len(r["spacing_releases"]) for r in records),
        "seeds_with_spacing_release": sum(bool(r["spacing_releases"]) for r in records),
        "exposure": {"mature_checks": sum(e["mature_checks"] for e in exposure), "masks": dict(sorted(histogram.items())),
            "bits": {n: sum(v for k, v in histogram.items() if int(k) & b) for n, b in BITS.items()},
            **{k: sum(e[k] for e in exposure) for k in ("globally_dim", "bright_sun_but_shaded")}},
        "exposure_by_fate": {f: {"mature_checks": sum(e["mature_checks"] for r, e in zip(records, exposure) if r["outcome"] == f),
            "bits": {n: sum(v for r, e in zip(records, exposure) if r["outcome"] == f
                for k, v in e["masks"].items() if int(k) & b) for n, b in BITS.items()}}
            for f in ("germinated", "expired", "pending")}}


def cohorts(records: list[dict]) -> dict:
    return {"all": summarize(records), "world_closed": summarize([r for r in records if r["purchase_class"] == "world_closed"])}


def validate_record(r: dict, seed: dict, purchase: dict, parents: dict) -> None:
    empty = new_record(r["seed_index"], seed, purchase)
    require(all(r[k] == v for k, v in empty.items() if k not in
                ("runs", "first", "first_mature", "terminal_pair", "spacing_releases")), "Changed seed/purchase/outcome join")
    stop = seed["resolved_tick"] if seed["resolved_tick"] is not None else END
    last = (stop - seed["created_tick"]) // 15 - int(seed["outcome"] == "expired")
    age, previous, releases = 1, None, []
    for run in r["runs"]:
        require(len(run) == 4 and all(type(v) is int for v in run[:3]) and type(run[3]) is bool,
                "Malformed waiting interval")
        start, end, mask, dim = run
        require(start == age and start <= end < LIFETIME and 0 <= mask < 128 and
                bool(mask & 1) == (start < DORMANCY) == (end < DORMANCY) and
                (not dim or bool(mask & 4)) and (previous is None or previous[2:] != run[2:]) and
                (mask != 0 or seed["outcome"] == "germinated" and start == end == last),
                "Invalid, missing, overlapping or unmerged check interval")
        if previous and previous[2] & 32 and not mask & 32:
            releases.append(start)
        age, previous = end + 1, run
    require(age == last + 1 and len(r["terminal_pair"]) == min(last, 2) and
            [s["age"] for s in r["terminal_pair"]] == list(range(max(1, last - 1), last + 1)) and
            (r["first"] is not None) == (last > 0) and
            (r["first_mature"] is not None) == (last >= DORMANCY), "Wrong censored/resolved check coverage")
    snapshots = r["terminal_pair"] + ([r["first"]] if last else []) + ([r["first_mature"]] if last >= DORMANCY else [])
    for s in snapshots:
        mask, dim = next((mask, dim) for lo, hi, mask, dim in r["runs"] if lo <= s["age"] <= hi)
        require(s["mask"] == mask and (s["sun"] < 80) == dim and 0 <= s["moisture"] <= 255 and
                0 <= s["light"] <= s["sun"] <= 255 and 0 <= s["phase"] < 256 and
                0 <= s["nodes"] <= 256 and 0 <= s["plants"] <= 8 and type(s["cold"]) is bool and
                s["rain_rate"] >= 0 and s["rain_deposited"] >= 0 and
                s["neighbors"] == sorted(set(s["neighbors"])) and
                all(i in parents and abs(parents[i]["column"] - r["column"]) < 3 for i in s["neighbors"]),
                "Invalid retained check context")
        expected = (int(s["age"] < DORMANCY) + 2 * (s["moisture"] < 12) + 4 * (s["light"] < 80) +
            8 * (s["plants"] == 8) + 16 * (s["nodes"] > 252) + 32 * bool(s["neighbors"]) + 64 * s["cold"])
        require(expected == mask, "Retained mask disagrees with retained resources/context")
        tick = r["created_tick"] + s["age"] * 15
        require(all(i in parents and parents[i]["plant"]["death_tick"] is not None and
                    parents[i]["plant"]["death_tick"] < tick for i in s["removed"]), "Removed neighbor was not dead")
    require(not last or r["first"]["age"] == 1, "Missing first check")
    require(last < DORMANCY or r["first_mature"]["age"] == DORMANCY, "Missing first mature check")
    require([e["age"] for e in r["spacing_releases"]] == releases, "Missing spacing-clearance event")
    for e in r["spacing_releases"]:
        tick = r["created_tick"] + 15 * e["age"]
        require(e["ids"] and set(e["ids"]) <= set(e["removed"]) and all(i in parents and
            abs(parents[i]["column"] - r["column"]) < 3 and parents[i]["plant"]["death_tick"] is not None and
            parents[i]["plant"]["death_tick"] < tick for i in e["ids"]), "Invalid reclaimed spacing neighbors")
    if seed["outcome"] == "germinated":
        require(last >= DORMANCY and r["terminal_pair"][-1]["mask"] == 0 and
                r["terminal_pair"][-2]["mask"] != 0, "Missing first feasible germination check")


def validate_case(case: dict, old: dict, purchase_case: dict) -> None:
    arm = purchase_case["arm"]
    require(case["case"] == old["case"] == purchase_case["case"] and case["arm"] == arm and
            case["source_trace_sha256"] == old["traces"][arm] and case["worlds"] == END // 15 + 1,
            "Changed case/arm/coverage")
    ledger = old["arms"][arm]["ledger"]
    require(len(case["records"]) == len(ledger["seeds"]) == len(purchase_case["events"]), "Incomplete seed coverage")
    parents = {p["plant"]["id"]: p for p in ledger["parents"]}
    for i, (record, seed, purchase) in enumerate(zip(case["records"], ledger["seeds"], purchase_case["events"])):
        require(record["seed_index"] == i, "Changed seed order")
        validate_record(record, seed, purchase, parents)
    require(case["checks"] == sum(hi - lo + 1 for r in case["records"] for lo, hi, _, _ in r["runs"]) and
            case["summary"] == cohorts(case["records"]), "Changed checks/summary")


def analysis(cases: list[dict]) -> dict:
    require(len(cases) == 64 and len({(identity(c["case"]), c["arm"]) for c in cases}) == 64,
            "Incomplete or duplicate panel")
    groups = {a: cohorts([r for c in cases if c["arm"] == a for r in c["records"]]) for a in ARMS}
    partitions = {field: {value: {a: cohorts([r for c in cases if c["arm"] == a and c["case"][field] == value
        for r in c["records"]]) for a in ARMS} for value in values} for field, values in (
            ("seed", origin.confirmation.SEEDS), ("scenario", origin.population.LAYOUTS), ("policy", origin.population.POLICIES))}
    partitions["species"] = {s: {a: cohorts([r for c in cases if c["arm"] == a for r in c["records"] if r["species"] == s])
                                  for a in ARMS} for s in sites.SPECIES}
    return {"groups": groups, "partitions": partitions}


def validate_report(report: dict, purchases: dict, old: dict) -> None:
    require(report["protocol"] == RULE and report["input_sha256"] == INPUT_SHA and
            len(report["cases"]) == len(purchases["cases"]) == 64, "Wrong report identity or coverage")
    for i, case in enumerate(report["cases"]):
        validate_case(case, old["cases"][i // 2], purchases["cases"][i])
    require(report["analysis"] == analysis(report["cases"]), "Changed panel analysis")


def compact(report: dict) -> dict:
    return {**{k: v for k, v in report.items() if k != "cases"}, "cases": [
        {**{k: v for k, v in c.items() if k != "records"}, "records_sha256":
         hashlib.sha256(json.dumps(c["records"], sort_keys=True).encode()).hexdigest()} for c in report["cases"]]}


def frozen(builds: dict, purchases: dict) -> dict:
    sources = source_hashes(ROOT)
    sources.update({n: digest(ROOT / n) for n in {PROTOCOL, "sim/garden_season_seed_waits.py",
        "sim/test_garden_season_seed_waits.py", *purchases["frozen"]["sources"]}})
    for name, sha in purchases["frozen"]["sources"].items():
        if name not in ALLOWED_CHANGES:
            require(digest(ROOT / name) == sha, "Changed non-observation source: " + name)
    configs = {}
    for arm, build in builds.items():
        flags = build_flags(build / "CMakeCache.txt")
        require(flags == purchases["frozen"]["builds"][arm]["flags"], "Changed ecology flags")
        configs[arm] = {"flags": flags, "cache_sha256": digest(build / "CMakeCache.txt"),
            "observer_sha256": digest(build / "toy-factory-garden-production-audit"), "sizes": origin.capacity.sizes(build)}
        require(configs[arm]["sizes"] == purchases["frozen"]["builds"][arm]["sizes"], "Changed world storage")
    return {"sources": sources, "builds": configs}


def capture(build: Path, old: dict, target: Path) -> None:
    spec = old["case"]
    command = [build / "toy-factory-garden-production-audit", spec["scenario"], spec["policy"],
               str(int(spec["seed"], 16)), "guard", str(END), "--seed-waits"]
    with tempfile.TemporaryFile() as stream:
        subprocess.run(list(map(str, command)), stdout=stream, stderr=subprocess.PIPE, check=True, timeout=300)
        stream.seek(0)
        with target.open("xb") as raw, gzip.GzipFile(filename="", fileobj=raw, mode="wb", mtime=0) as compressed:
            shutil.copyfileobj(stream, compressed)


def run_job(item) -> dict:
    builds, output, bundle, old, purchase_case, collect = item
    arm = purchase_case["arm"]
    target = origin.population.path(output, old["case"], arm)
    repeat = origin.population.path(output, old["case"], arm, True)
    if collect:
        capture(builds[arm], old, target)
        capture(builds[arm], old, repeat)
    require(digest(target) == digest(repeat), "Nonrepeatable seed observation")
    result = audit_trace(target, origin.population.path(bundle, old["case"], arm), old, purchase_case)
    saved = output / (identity(old["case"]) + "-" + arm + ".json")
    if collect:
        saved.write_text(json.dumps(result, indent=2) + "\n")
    else:
        require(result == json.loads(saved.read_text()), "Nonrepeatable waiting analysis")
    print("Verified seed waits " + identity(old["case"]) + " " + arm, flush=True)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("collect", "verify"))
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--bundle", type=Path, default=Path("artifacts/garden-seasonal-flower-origin"))
    parser.add_argument("--base", type=Path, default=Path("artifacts/build-host-seed-waits-base"))
    parser.add_argument("--flower", type=Path, default=Path("artifacts/build-host-seed-waits-flower"))
    parser.add_argument("--jobs", type=int, default=4)
    args = parser.parse_args()
    if not 1 <= args.jobs <= 4:
        parser.error("Require 1..4 independent workers")
    purchases, old = load_input()
    builds = {a: getattr(args, a).resolve() for a in ARMS}
    provenance = frozen(builds, purchases)
    if args.command == "collect":
        args.out.mkdir(parents=True, exist_ok=False)
    with ProcessPoolExecutor(max_workers=args.jobs) as pool:
        cases = list(pool.map(run_job, ((builds, args.out, args.bundle, old["cases"][i // 2], p, args.command == "collect")
                                       for i, p in enumerate(purchases["cases"]))))
    require(frozen(builds, purchases) == provenance, "Inputs changed during observation")
    report = {"protocol": RULE, "input_sha256": INPUT_SHA, "frozen": provenance, "cases": cases, "analysis": analysis(cases)}
    validate_report(report, purchases, old)
    if args.command == "collect":
        (args.out / "results.json").write_text(json.dumps(report, indent=2) + "\n")
        (args.out / "summary.json").write_text(json.dumps(compact(report), indent=2) + "\n")
    else:
        require(report == json.loads((args.out / "results.json").read_text()) and
                compact(report) == json.loads((args.out / "summary.json").read_text()), "Changed portable evidence")
    print("All 64 waiting histories verified; checks=" + str(sum(c["checks"] for c in cases)), flush=True)


if __name__ == "__main__":
    main()
