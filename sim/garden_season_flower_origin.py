#!/usr/bin/env python3
"""Frozen base-versus-producing-flower dispersal screen; no default promotion."""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
import gzip
import hashlib
from itertools import zip_longest
import json
from pathlib import Path
import subprocess
import sys
import zlib

import garden_season_seed_bank_capacity as capacity
import garden_season_seed_bank_diagnosis as diagnosis
from garden_season_confirmation import build_flags
from garden_season_recruitment import digest, identity
from garden_seasons import require, source_hashes

ROOT, DAY, END = capacity.ROOT, capacity.DAY, capacity.END
population, funnel, confirmation = capacity.population, capacity.funnel, capacity.confirmation
RULE = "seasonal-flower-origin-v1"
ORIGIN = "flower-v1"
PROTOCOL = "benchmarks/garden-seasons/flower-origin-protocol.md"
OPTION = "TOY_FACTORY_GARDEN_FLOWER_DISPERSAL:BOOL"
ARMS = ("base", "flower")
ALLOWED_CHANGES = {"src/garden_world.c", "src/garden_world.h", "sim/CMakeLists.txt",
    "sim/garden_inspect.c", "sim/garden_replay.c", "sim/garden_experiment.c",
    "sim/garden_production_audit.c", "sim/garden_seed_sites_test.c",
    "scripts/container/host-garden-defaults.sh"}


def first_difference(before: dict, after: dict, old_bids: list, new_bids: list,
                     old_deaths: list, new_deaths: list) -> dict:
    require("seed_origin" not in before and after.get("seed_origin") == ORIGIN and
            before["tick"] == after["tick"] and before["tick"] > 0 and before["tick"] % 60 == 0 and
            before["hash"] != after["hash"] and old_bids == new_bids and old_deaths == new_deaths,
            "Changed prefix decisions/origin/timing")
    stripped = lambda w: {k: v for k, v in w.items() if k not in ("hash", "seed_origin", "seeds")}
    require(stripped(before) == stripped(after) and len(before["seeds"]) == len(after["seeds"]),
            "First change is not isolated seed placement")
    changed = []
    for a, b in zip(before["seeds"], after["seeds"]):
        if a == b:
            continue
        require(a["age"] == b["age"] == 0 and a["column"] != b["column"] and
                all(type(s["column"]) is int and 0 <= s["column"] < 28 for s in (a, b)) and
                {k: v for k, v in a.items() if k not in ("column", "blockers")} ==
                {k: v for k, v in b.items() if k not in ("column", "blockers")},
                "Changed existing seed, ancestry, or non-placement field")
        changed.append({"parent": a["parent"], "base_column": a["column"], "flower_column": b["column"]})
    require(bool(changed), "No changed landing column")
    return {"tick": before["tick"], "base": before, "flower": after, "seeds": changed}


def incumbent_pairs(arms: dict, difference: dict | None) -> list[dict]:
    # Reuse the frozen identity/censoring rules, not post-divergence numeric IDs.
    legacy = {a: arms[b] for a, b in zip(capacity.CAPACITIES, ARMS)}
    split = None if difference is None else {"tick": difference["tick"], "eight": difference["base"]}
    return [{("base_death" if k == "eight_death" else "flower_death" if k == "sixteen_death" else k): v
             for k, v in p.items()} for p in capacity.incumbent_pairs(legacy, split)]


def analyze_pair(output: Path, old: dict) -> dict:
    paths = {a: population.path(output, old["case"], a) for a in ARMS}
    hashes = {a: digest(p) for a, p in paths.items()}
    require(hashes["base"] == old["traces"]["eight"], "Rebuilt base control changed")
    audits = {a: population.Audit(True) for a in ARMS}
    ledgers = {a: funnel.SeedLedger() for a in ARMS}
    occupancies = {a: capacity.occupancy() for a in ARMS}
    prefix, difference = 0, None
    for pair in zip_longest(*(population.reserve.groups(paths[a]) for a in ARMS)):
        require(all(p is not None for p in pair), "Truncated paired traces")
        (before, old_bids, old_deaths), (after, new_bids, new_deaths) = pair
        require("seed_origin" not in before and after.get("seed_origin") == ORIGIN,
                "Wrong seed-origin metadata")
        require(all(before[k] == after[k] for k in ("tick", "climate", "rain_rate", "sun_phase", "sun_strength")) and
                before["rain_deposited"] + before["rain_runoff"] == after["rain_deposited"] + after["rain_runoff"],
                "Unmatched external weather")
        if difference is None:
            if before == {k: v for k, v in after.items() if k != "seed_origin"}:
                require(old_bids == new_bids and old_deaths == new_deaths, "Changed identical-state decisions")
                prefix += 1
            else:
                difference = first_difference(before, after, old_bids, new_bids, old_deaths, new_deaths)
        for arm, item in zip(ARMS, pair):
            audits[arm].accept(*item)
            ledgers[arm].accept(item[0])
            capacity.add_occupancy(occupancies[arm], item[0], 8)
    arms = {a: {"capacity": 8, "outcome": audits[a].result({}), "ledger": ledgers[a].result(),
                "occupancy": occupancies[a]} for a in ARMS}
    require(arms["base"] == old["arms"]["eight"], "Changed saved control budgets/outcomes/ledger")
    require(hashes == {a: digest(p) for a, p in paths.items()}, "Traces changed during analysis")
    return {"case": old["case"], "traces": hashes, "exact_prefix_worlds": prefix,
            "first_difference": difference, "arms": arms, "incumbents": incumbent_pairs(arms, difference)}


def analysis(cases: list[dict]) -> dict:
    # Identical gates and metric implementation to the capacity screen; arm names
    # are adapted only at this boundary. Both capacities here are eight.
    result = capacity.analysis([{**c, "arms": {a: c["arms"][b] for a, b in zip(capacity.CAPACITIES, ARMS)}}
                                for c in cases])
    result["groups"] = {b: result["groups"][a] for a, b in zip(capacity.CAPACITIES, ARMS)}
    for partition in result["partitions"].values():
        for value, groups in partition.items():
            partition[value] = {b: groups[a] for a, b in zip(capacity.CAPACITIES, ARMS)}
    return result


def validate_case(case: dict, old: dict) -> None:
    require(case["case"] == old["case"] and case["traces"]["base"] == old["traces"]["eight"] and
            case["arms"]["base"] == old["arms"]["eight"], "Changed frozen base control")
    for arm in ARMS:
        a = case["arms"][arm]
        require(a["capacity"] == 8 and a["outcome"]["outcomes"] == population.outcomes(a["outcome"]["history"]),
                "Changed capacity or lifetime outcomes")
        funnel.validate_ledger(a["ledger"], a["outcome"])
        for window, samples in (("whole", END // 15), ("closing", 16 * 256)):
            o = a["occupancy"][window]
            require(o["samples"] == samples == sum(o["histogram"].values()) and
                    all(k == str(int(k)) and 0 <= int(k) <= 8 and type(n) is int and n > 0
                        for k, n in o["histogram"].items()) and
                    o["seed_samples"] == sum(int(k) * n for k, n in o["histogram"].items()) and
                    (o["first_full_tick"] is None) == (o["histogram"].get("8", 0) == 0), "Corrupt occupancy")
            if o["first_full_tick"] is not None:
                require((0 if window == "whole" else 112 * DAY) < o["first_full_tick"] <= END and
                        o["first_full_tick"] % 15 == 0, "Invalid saturation tick")
    difference = case["first_difference"]
    require(case["exact_prefix_worlds"] == (END // 15 + 1 if difference is None else difference["tick"] // 15),
            "Changed prefix length")
    if difference is not None:
        require(first_difference(difference["base"], difference["flower"], [], [], [], []) == difference,
                "Changed first seed-placement event")
    require(case["incumbents"] == incumbent_pairs(case["arms"], difference), "Changed incumbent comparisons")
    selected = case["case"]["seed"] == confirmation.SEEDS[0] and case["case"]["policy"] == "baseline"
    frames = case["frames"]
    require(len(frames) == (4 if selected else 0) and {(f["arm"], f["day"]) for f in frames} ==
            ({(a, d) for a in ARMS for d in (16, 128)} if selected else set()), "Changed fixed frame panel")
    for frame in frames:
        require(frame["hash"] == case["arms"][frame["arm"]]["outcome"]["history"]["daily"][frame["day"]]["hash"],
                "Frame does not match trajectory")
        if frame["arm"] == "base":
            earlier = next(f for f in old["frames"] if f["arm"] == "eight" and f["day"] == frame["day"])
            require(all(frame[k] == earlier[k] for k in ("hash", "framebuffer_crc32", "png_sha256")),
                    "Changed baseline image")


def validate_report(report: dict, prior: dict) -> None:
    require(report["protocol"] == RULE and report["input_sha256"] == diagnosis.INPUT_SHA and
            analysis(report["cases"]) == report["analysis"], "Changed trial identity/analysis")
    for case, old in zip(report["cases"], prior["cases"]):
        validate_case(case, old)


def compact(report: dict) -> dict:
    return {**{k: v for k, v in report.items() if k != "cases"}, "cases": [
        {"case": c["case"], "traces": c["traces"], "frames": c["frames"], "incumbents": c["incumbents"],
         "exact_prefix_worlds": c["exact_prefix_worlds"],
         "first_changed_tick": None if c["first_difference"] is None else c["first_difference"]["tick"],
         "arms": {a: {"metrics": capacity.metrics([v]), "counts": v["outcome"]["counts"], "occupancy": v["occupancy"],
            "details_sha256": hashlib.sha256(json.dumps(v, sort_keys=True).encode()).hexdigest()}
            for a, v in c["arms"].items()}} for c in report["cases"]]}


def frozen(builds: dict, prior: dict) -> dict:
    sources = source_hashes(ROOT)
    files = {PROTOCOL, "sim/garden_season_flower_origin.py", "sim/test_garden_season_flower_origin.py",
             "sim/garden_season_seed_bank_diagnosis.py", "sim/test_garden_season_seed_bank_diagnosis.py",
             "sim/CMakeLists.txt", "scripts/container/host-garden-defaults.sh", *prior["frozen"]["sources"]}
    sources.update({name: digest(ROOT / name) for name in files})
    for name, sha in prior["frozen"]["sources"].items():
        if name not in ALLOWED_CHANGES:
            require(digest(ROOT / name) == sha, "Changed non-origin dependency: " + name)
    configs = {}
    for arm, build in builds.items():
        flags = build_flags(build / "CMakeCache.txt")
        expected = {**prior["frozen"]["builds"]["eight"]["flags"], OPTION: "ON" if arm == "flower" else "OFF"}
        require(flags == expected, "Not an isolated origin build")
        configs[arm] = {"flags": flags, "cache_sha256": digest(build / "CMakeCache.txt"),
            "binaries": {n: digest(build / ("toy-factory-garden-" + n)) for n in ("inspect", "replay", "capacity-test")},
            "sizes": capacity.sizes(build)}
    require(configs["base"]["sizes"] == configs["flower"]["sizes"], "Origin changed storage")
    return {"sources": sources, "builds": configs}


def render(builds: dict, output: Path, result: dict) -> list[dict]:
    spec = result["case"]
    if spec["seed"] != confirmation.SEEDS[0] or spec["policy"] != "baseline":
        return []
    sys.path.insert(0, str(ROOT / "scripts/container"))
    from framebuffer_capture import rgb565be_to_rgb888, write_png
    frames = []
    for arm in ARMS:
        for day in (16, 128):
            target = output / "frames" / f"origin-{arm}-{spec['scenario']}-day-{day}.rgb565be"
            command = [builds[arm] / "toy-factory-garden-replay", "-", spec["scenario"], spec["policy"],
                str(int(spec["seed"], 16)), "--climate", "seasonal", "--ticks", str(day * DAY),
                "--seedling-reserve", "all", "--framebuffer", target]
            row = json.loads(subprocess.check_output(list(map(str, command)), text=True, timeout=300))
            raw = target.read_bytes()
            require(row["hash"] == result["arms"][arm]["outcome"]["history"]["daily"][day]["hash"] and
                    len(raw) == 115200 and row["framebuffer_crc32"] == f"{zlib.crc32(raw):08x}" and
                    row["seedling_reserve"] == population.METADATA and row.get("seed_capacity", 8) == 8 and
                    row.get("seed_origin") == (ORIGIN if arm == "flower" else None), "Rendered state/origin mismatch")
            png = target.with_suffix(".png")
            write_png(png, 240, 240, rgb565be_to_rgb888(raw))
            frames.append({"arm": arm, "day": day, "png": "frames/" + png.name, "png_sha256": digest(png),
                           "hash": row["hash"], "framebuffer_crc32": row["framebuffer_crc32"]})
    return frames


def run_job(item) -> dict:
    builds, output, old, collect = item
    for arm in ARMS:
        for repeat in (False, True):
            if collect:
                population.capture(builds[arm], old["case"], "guard", population.path(output, old["case"], arm, repeat))
        require(digest(population.path(output, old["case"], arm)) ==
                digest(population.path(output, old["case"], arm, True)), "Nonrepeatable origin trace")
    result = analyze_pair(output, old)
    saved_path = output / (identity(old["case"]) + ".json")
    if collect:
        result["frames"] = render(builds, output, result)
        saved_path.write_text(json.dumps(result, indent=2) + "\n")
    else:
        saved = json.loads(saved_path.read_text())
        result["frames"] = saved["frames"]
        require(result == saved, "Changed origin history/analysis")
    validate_case(result, old)
    for frame in result["frames"]:
        png = output / frame["png"]
        raw = png.with_suffix(".rgb565be").read_bytes()
        require(digest(png) == frame["png_sha256"] and len(raw) == 115200 and
                f"{zlib.crc32(raw):08x}" == frame["framebuffer_crc32"], "Changed screenshot bytes")
    print("Verified flower origin " + identity(old["case"]), flush=True)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("collect", "verify"))
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--base", type=Path, default=Path("artifacts/build-host-flower-origin-base"))
    parser.add_argument("--flower", type=Path, default=Path("artifacts/build-host-flower-origin-flower"))
    parser.add_argument("--jobs", type=int, default=4)
    args = parser.parse_args()
    if not 1 <= args.jobs <= 4:
        parser.error("Require 1..4 independent workers")
    prior = diagnosis.load_input()
    builds = {a: getattr(args, a).resolve() for a in ARMS}
    provenance = frozen(builds, prior)
    if args.command == "collect":
        args.out.mkdir(parents=True, exist_ok=False)
        (args.out / "frames").mkdir()
    with ProcessPoolExecutor(max_workers=args.jobs) as pool:
        cases = list(pool.map(run_job, ((builds, args.out, old, args.command == "collect") for old in prior["cases"])))
    require(frozen(builds, prior) == provenance, "Inputs changed during origin screen")
    report = {"protocol": RULE, "input_sha256": diagnosis.INPUT_SHA, "frozen": provenance,
              "cases": cases, "analysis": analysis(cases)}
    validate_report(report, prior)
    if args.command == "collect":
        (args.out / "results.json").write_text(json.dumps(report, indent=2) + "\n")
        (args.out / "summary.json").write_text(json.dumps(compact(report), indent=2) + "\n")
    else:
        require(report == json.loads((args.out / "results.json").read_text()) and
                compact(report) == json.loads((args.out / "summary.json").read_text()), "Nonrepeatable analysis")
    print("All 32 origin pairs verified; passes_screen=" + str(report["analysis"]["passes_screen"]), flush=True)


if __name__ == "__main__":
    main()
