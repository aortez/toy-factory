#!/usr/bin/env python3
"""Shadow landing observations: reference arithmetic, noninterference and fixed-panel variation."""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
import gzip
import hashlib
from itertools import zip_longest
import json
from pathlib import Path
import platform
import shutil
import statistics
import subprocess
import tempfile

import garden_landing_contract as contract
import garden_season_flower_sites as sites
from garden_season_confirmation import build_flags
from garden_season_recruitment import digest, identity
from garden_seasons import require, source_hashes

ROOT, DAY, END, ARMS = sites.ROOT, sites.DAY, sites.END, sites.ARMS
SEEDS = ("ed52188c", "82deacfd")
RULE = "landing-shadow-v1"
PROTOCOL = "benchmarks/garden-seasons/landing-shadow-protocol.md"
PRIOR = "benchmarks/garden-seasons/seed-waits-summary.json"
PRIOR_SHA = "5d089e00e11e180bb1cb18c7143a05e67c0db0c0bed9c440ac58d61f38b640c2"
COUNTERS = ("queries", "stems", "roots", "sources", "choices", "variable",
            "in_bounds_choices", "in_bounds_variable", "joint_below_marginals")


def load_input():
    require(digest(ROOT / PRIOR) == PRIOR_SHA, "Changed seed-waits checkpoint")
    return sites.load_input(), json.loads((ROOT / PRIOR).read_text())


def header(spec, arm, end=END, rule="wide-v1"):
    return {"version": 1, "observer": RULE, "phase": "after-seeds-before-growth",
        "scenario": spec["scenario"], "policy": spec["policy"], "seed": spec["seed"],
        "end": end, "climate": "seasonal", "guard": True, "dispersal": rule,
        "origin": arm, "cache_bytes": 316, "packet_bytes": 52}


def decode_cache(row, previous):
    require(set(row) == {"tick", "samples", "water", "light", "occupied", "traces"}, "Wrong cache fields")
    current = contract.Terrain(*(tuple(row[k]) for k in ("water", "light", "occupied")))
    expected = contract.reset(current) if previous is None else contract.sample(previous, row["tick"], current)
    require(row["tick"] == expected.tick and row["samples"] == expected.samples and
            row["traces"] == [list(r) for r in expected.traces], "Wrong clock/history update")
    return expected


def check_packet(history, bid, arm, rule="wide-v1"):
    require(type(bid["tip"]) is int and 0 <= bid["tip"] < 256 and bid["kind"] in (0, 1) and
            8 <= bid["base_x"] < 232 and bid["action"] in (0, 1, 2) and
            -32768 <= bid["priority"] <= 32767, "Invalid bid identity")
    candidates = bid["candidates"]
    require(len(candidates) == (5 if bid["kind"] == 0 else 3) and all(
        len(c) == 2 and all(type(v) is int for v in c) and 0 <= c[0] <= 255 and 0 <= c[1] <= 15 and
        (not c[1] & 2 or c[1] == 3) and (not c[1] & 12 or c[1] & 1) for c in candidates),
        "Invalid candidate bounds/availability")
    xs = [x if flags & 1 else None for x, flags in candidates]
    xs += [None] * (5 - len(xs))
    expected = contract.packet(history, bid["x"], xs, contract.pixel_column(bid["base_x"]),
        bid["dispersal"], stem=bid["kind"] == 0, origin_rule=arm, rule=rule)
    expected["values"] = [list(row) for row in expected["values"]]
    require(bid["packet"] == expected, "Native packet disagrees with independent reference")


def new_stats():
    return {**dict.fromkeys(COUNTERS, 0), "max_origins": 0,
            "field_variation": [0] * 8, "hist": [[0] * 256 for _ in range(8)]}


def add_bid(stats, bid, arm):
    stats["queries"] += 1
    if bid["kind"] == 1:
        stats["roots"] += 1
        return
    stats["stems"] += 1
    packet = bid["packet"]
    valid = [i for i in range(6) if packet["valid"] & (1 << i)]
    bounds = [i for i in valid if i > 0]
    available = [i for i in bounds if bid["candidates"][i - 1][1] & 2]
    origins = {contract.pixel_column(bid["base_x"] if arm == "base" else
        bid["x"] if i == 0 else bid["candidates"][i - 1][0]) for i in valid}
    require(len(origins) <= 3, "Canonical shoot exceeded memoization bound")
    stats["max_origins"] = max(stats["max_origins"], len(origins))
    for i in valid:
        values = packet["values"][i]
        require(values[7] <= values[6] <= min(values[4:6]), "Invalid joint trace ordering")
        stats["sources"] += 1
        stats["joint_below_marginals"] += values[6] < min(values[4:6])
        for field, value in enumerate(values):
            stats["hist"][field][value] += 1
    varied = [len({packet["values"][i][f] for i in available}) > 1 for f in range(8)]
    stats["choices"] += len(available) >= 2
    stats["variable"] += any(varied)
    stats["in_bounds_choices"] += len(bounds) >= 2
    stats["in_bounds_variable"] += len({tuple(packet["values"][i]) for i in bounds}) > 1
    for f, different in enumerate(varied):
        stats["field_variation"][f] += different


def merge_stats(rows):
    result = new_stats()
    for row in rows:
        for key in COUNTERS:
            result[key] += row[key]
        result["max_origins"] = max(result["max_origins"], row["max_origins"])
        result["field_variation"] = [a + b for a, b in zip(result["field_variation"], row["field_variation"])]
        result["hist"] = [[a + b for a, b in zip(left, right)] for left, right in zip(result["hist"], row["hist"])]
    return result


def summarize(stats):
    return {**{k: v for k, v in stats.items() if k != "hist"}, "fields": {
        name: {"values": sum(n > 0 for n in hist), "min": next((i for i, n in enumerate(hist) if n), None),
               "max": next((i for i in range(255, -1, -1) if hist[i]), None),
               "zero": hist[0], "sum": sum(i * n for i, n in enumerate(hist))}
        for name, hist in zip(contract.FIELDS, stats["hist"])}}


def aggregate(cases):
    windows = {"whole": 0, "warmed": 1, "closing": 112}
    return {window: {a: summarize(merge_stats(day["stats"] for c in cases if c["arm"] == a
        for day in c["days"][start:])) for a in ARMS} for window, start in windows.items()}


def analysis(cases):
    return {"groups": aggregate(cases), "partitions": {field: {value: aggregate(
        [c for c in cases if c["case"][field] == value]) for value in values} for field, values in (
        ("seed", SEEDS), ("scenario", ("rainfed", "rainfed-crowded")), ("policy", ("baseline", "adaptive")))}}


def audit_trace(trace, original, old, arm):
    require(digest(original) == old["traces"][arm], "Changed original trajectory")
    days = [{"stats": new_stats(), "first_stem": None} for _ in range(128)]
    history, count, matched_bids = None, 0, 0
    with gzip.open(trace, "rt") as stream:
        require(json.loads(next(stream)) == header(old["case"], arm), "Changed observer header")
        originals = sites.origin.population.reserve.groups(original)
        for line, saved in zip_longest(stream, originals):
            require(line is not None and saved is not None, "Truncated or extra trace")
            world, original_bids, _ = saved
            row = json.loads(line)
            require(row["tick"] == world["tick"] == count * 15 and row["hash"] == world["hash"] and
                    row["created"] == world["seeds_created"], "Observer changed authoritative world")
            history = decode_cache(row["cache"], history)
            require(history.tick == count and history.current == contract.terrain(
                history.current.water, history.current.light, [(p["column"], p["dead"]) for p in world["plants"]]),
                "Spacing snapshot does not match admitted live/dead slots")
            require(len(row["bids"]) == len(original_bids) and len({b["tip"] for b in row["bids"]}) == len(row["bids"]),
                    "Missing, extra, repeated or reordered bids")
            for bid, previous in zip(row["bids"], original_bids):
                plant = next(p for p in world["plants"] if p["id"] == previous["id"])
                require([bid[k] for k in ("tip", "kind", "x", "action", "priority")] ==
                        [previous[k] for k in ("tip_index", "tissue", "x", "action", "priority")] and
                        bid["candidates"] == [[c["x"], c["flags"]] for c in previous["candidates"]] and
                        contract.pixel_column(bid["base_x"]) == plant["column"] and
                        bid["dispersal"] == plant["genome"][7], "Changed bid input or proposal")
                check_packet(history, bid, arm)
                day = days[(count - 1) // 256]
                add_bid(day["stats"], bid, arm)
                if bid["kind"] == 0 and day["first_stem"] is None:
                    day["first_stem"] = {"tick": row["tick"], "cache": row["cache"], "bid": bid}
                matched_bids += 1
            count += 1
    require(count == END // 15 + 1, "Wrong horizon")
    return {"case": old["case"], "arm": arm, "trace_sha256": digest(trace),
        "original_sha256": old["traces"][arm], "worlds": count, "bids": matched_bids,
        "days": days, "final_hash": row["hash"], "created": row["created"]}


def validate_case(case):
    require(case["arm"] in ARMS and case["worlds"] == END // 15 + 1 and len(case["days"]) == 128,
            "Incomplete case")
    for index, day in enumerate(case["days"]):
        stats = day["stats"]
        require(set(stats) == set(new_stats()) and all(type(stats[k]) is int and stats[k] >= 0 for k in COUNTERS)
                and stats["queries"] == stats["stems"] + stats["roots"] and
                stats["stems"] <= stats["sources"] <= 6 * stats["stems"] and
                0 <= stats["max_origins"] <= (1 if case["arm"] == "base" else 3) and
                0 <= stats["variable"] <= stats["choices"] <= stats["in_bounds_choices"] <= stats["stems"] and
                stats["variable"] <= stats["in_bounds_variable"] <= stats["in_bounds_choices"] and
                stats["joint_below_marginals"] <= stats["sources"], "Invalid daily counters")
        require(len(stats["hist"]) == len(stats["field_variation"]) == 8 and all(
            len(h) == 256 and all(type(v) is int and v >= 0 for v in h) and sum(h) == stats["sources"]
            for h in stats["hist"]) and all(type(v) is int and 0 <= v <= stats["variable"]
            for v in stats["field_variation"]), "Invalid histogram/variation")
        require(case["arm"] != "base" or (stats["variable"] == stats["in_bounds_variable"] == 0),
                "Base-origin advertises positional benefit")
        first = day["first_stem"]
        require((first is None) == (stats["stems"] == 0), "Missing first-stem fixture")
        if first:
            require(index * DAY < first["tick"] <= (index + 1) * DAY and first["bid"]["kind"] == 0,
                    "Wrong first-stem window")
            row = first["cache"]
            h = contract.History(row["tick"], row["samples"], contract.Terrain(
                *(tuple(row[k]) for k in ("water", "light", "occupied"))), tuple(tuple(r) for r in row["traces"]))
            require(h.tick * 15 == first["tick"], "Wrong first-stem cache clock")
            check_packet(h, first["bid"], case["arm"])
    require(sum(d["stats"]["queries"] for d in case["days"]) == case["bids"], "Wrong bid total")


def validate_report(report):
    require(report["protocol"] == RULE and report["prior_sha256"] == PRIOR_SHA, "Wrong provenance")
    expected = {(s, layout, policy, arm) for s in SEEDS for layout in ("rainfed", "rainfed-crowded")
                for policy in ("baseline", "adaptive") for arm in ARMS}
    require(len(report["cases"]) == 16 and {(c["case"]["seed"], c["case"]["scenario"], c["case"]["policy"], c["arm"])
            for c in report["cases"]} == expected, "Changed panel selection")
    for case in report["cases"]:
        validate_case(case)
    require(report["analysis"] == analysis(report["cases"]), "Changed aggregate summaries")


def compact(report):
    return {**{k: v for k, v in report.items() if k != "cases"}, "cases": [
        {**{k: v for k, v in c.items() if k != "days"}, "days_sha256": hashlib.sha256(
            json.dumps(c["days"], sort_keys=True).encode()).hexdigest()} for c in report["cases"]]}


def frozen(builds, prior):
    sources = source_hashes(ROOT)
    sources.update({n: digest(ROOT / n) for n in {PROTOCOL, PRIOR, "sim/garden_landing_shadow.py",
        "sim/test_garden_landing_shadow.py", "sim/garden_landing_contract.py", "sim/test_garden_landing_contract.py",
        "docs/garden-landing-observation.md", *prior["frozen"]["sources"]}})
    for name, sha in prior["frozen"]["sources"].items():
        if name not in {"src/garden_world.c", "sim/CMakeLists.txt"}:
            require(digest(ROOT / name) == sha, "Changed non-observation source: " + name)
    configs = {}
    for arm, build in builds.items():
        flags = build_flags(build / "CMakeCache.txt")
        require(flags == prior["frozen"]["builds"][arm]["flags"], "Changed ecology flags")
        configs[arm] = {"flags": flags, "cache_sha256": digest(build / "CMakeCache.txt"),
            "observer_sha256": digest(build / "toy-factory-garden-landing-audit"), "sizes": sites.origin.capacity.sizes(build)}
        require(configs[arm]["sizes"] == prior["frozen"]["builds"][arm]["sizes"], "Changed world storage")
    return {"sources": sources, "builds": configs}


def capture(build, spec, target):
    command = [build / "toy-factory-garden-landing-audit", spec["scenario"], spec["policy"],
               str(int(spec["seed"], 16)), str(END)]
    with tempfile.TemporaryFile() as stream:
        subprocess.run(list(map(str, command)), stdout=stream, stderr=subprocess.PIPE, check=True, timeout=300)
        stream.seek(0)
        with target.open("xb") as raw, gzip.GzipFile(filename="", fileobj=raw, mode="wb", mtime=0) as compressed:
            shutil.copyfileobj(stream, compressed)


def run_job(item):
    builds, output, bundle, old, arm, collect = item
    target = sites.origin.population.path(output, old["case"], arm)
    repeat = sites.origin.population.path(output, old["case"], arm, True)
    if collect:
        capture(builds[arm], old["case"], target)
        capture(builds[arm], old["case"], repeat)
    require(digest(target) == digest(repeat), "Nonrepeatable capture")
    result = audit_trace(target, sites.origin.population.path(bundle, old["case"], arm), old, arm)
    validate_case(result)
    print("Verified landing shadow " + identity(old["case"]) + " " + arm, flush=True)
    return result


def profile(build, output):
    _, prior = load_input()
    before = frozen({"flower": build}, prior)
    cache = (build / "CMakeCache.txt").read_text()
    require("CMAKE_BUILD_TYPE:STRING=Release\n" in cache and "TOY_FACTORY_SIMULATOR_SANITIZERS:BOOL=OFF\n" in cache,
            "Timing requires unsanitized Release build")
    command = [build / "toy-factory-garden-landing-audit", "rainfed-crowded", "adaptive", "0xed52188c", str(END), "--bench"]
    modes = ("plain", "sample", "observe")
    rows = []
    for repeat in range(5):
        for i in range(3):
            mode = modes[(i + repeat) % 3]
            row = json.loads(subprocess.check_output(list(map(str, [*command, mode])), text=True, timeout=120))
            require(row["mode"] == mode and row["cpu_us"] > 0, "Invalid timing")
            rows.append({"repeat": repeat, **row})
    require(len({(r["hash"], r["created"]) for r in rows}) == 1 and
            len({r["queries"] for r in rows if r["mode"] == "observe"}) == 1 and
            frozen({"flower": build}, prior) == before, "Timing changed state or sources")
    result = {"protocol": RULE, "case": {"scenario": "rainfed-crowded", "policy": "adaptive", "seed": SEEDS[0]},
        "end": END, "frozen": before, "platform": platform.platform(),
        "compiler": subprocess.check_output(["cc", "--version"], text=True).splitlines()[0], "runs": rows,
        "median_cpu_us": {m: statistics.median(r["cpu_us"] for r in rows if r["mode"] == m) for m in modes}}
    with output.open("x") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(result["median_cpu_us"], flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("collect", "verify", "profile"))
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--bundle", type=Path, default=Path("artifacts/garden-seasonal-flower-origin"))
    parser.add_argument("--base", type=Path, default=Path("artifacts/build-host-landing-shadow-base"))
    parser.add_argument("--flower", type=Path, default=Path("artifacts/build-host-landing-shadow-flower"))
    parser.add_argument("--jobs", type=int, default=4)
    args = parser.parse_args()
    require(1 <= args.jobs <= 4, "Require 1..4 workers")
    if args.command == "profile":
        profile(args.flower.resolve(), args.out)
        return
    old, prior = load_input()
    builds = {a: getattr(args, a).resolve() for a in ARMS}
    provenance = frozen(builds, prior)
    collect = args.command == "collect"
    if collect:
        args.out.mkdir(parents=True, exist_ok=False)
    selected = [c for c in old["cases"] if c["case"]["seed"] in SEEDS]
    with ProcessPoolExecutor(max_workers=args.jobs) as pool:
        cases = list(pool.map(run_job, ((builds, args.out, args.bundle, c, a, collect) for c in selected for a in ARMS)))
    require(frozen(builds, prior) == provenance, "Inputs changed during capture")
    report = {"protocol": RULE, "prior_sha256": PRIOR_SHA, "frozen": provenance, "cases": cases, "analysis": analysis(cases)}
    validate_report(report)
    result_file, summary_file = args.out / "histories.json.gz", args.out / "summary.json"
    if collect:
        result_file.write_bytes(gzip.compress(json.dumps(report, sort_keys=True, separators=(",", ":")).encode(), mtime=0))
        summary_file.write_text(json.dumps(compact(report), indent=2) + "\n")
    else:
        require(report == json.loads(gzip.decompress(result_file.read_bytes())) and
                compact(report) == json.loads(summary_file.read_text()), "Nonrepeatable analysis")
    print(f"All {len(cases)} worlds verified; states={sum(c['worlds'] for c in cases)}; bids={sum(c['bids'] for c in cases)}", flush=True)


if __name__ == "__main__":
    main()
