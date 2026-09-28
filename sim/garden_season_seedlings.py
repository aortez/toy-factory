#!/usr/bin/env python3
"""Frozen, read-only first-day seedling resource replays; no interventions."""

from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zlib

from garden_deaths import reconcile_death
from garden_resources import budget, ENERGY_COST, WATER_COST
from garden_season_confirmation import SEEDS, build_flags, summarize
from garden_season_offspring import INPUT_SHA256
from garden_season_recruitment import digest, identity
from garden_seasons import DAY_TICKS as DAY, analyze_worlds, require, source_hashes

ROOT = Path(__file__).resolve().parents[1]
END = 128 * DAY
PROTOCOL = "benchmarks/garden-seasons/seedling-resources-protocol.md"


def load_input() -> dict:
    raw = gzip.decompress((ROOT / "benchmarks/garden-seasons/dispersal-confirmation-histories.json.gz").read_bytes())
    require(hashlib.sha256(raw).hexdigest() == INPUT_SHA256, "Changed frozen histories")
    report = json.loads(raw)
    compact = summarize(report)
    compact["full_report_sha256"] = INPUT_SHA256
    require(compact == json.loads((ROOT / "benchmarks/garden-seasons/dispersal-confirmation-summary.json").read_text()),
            "Changed confirmation evidence")
    return report


def eligible(case: dict) -> list[dict]:
    return sorted([p for p in case["plants"] if p["parent"] and
                   112 * DAY < p["birth_tick"] <= END - DAY], key=lambda p: (p["birth_tick"], p["id"]))


def selection(report: dict) -> list[dict]:
    cases = sorted([c for c in report["cases"]["wide"] if c["mode"] == "seasonal"],
                   key=lambda c: (SEEDS.index(c["seed"]), ("rainfed", "rainfed-crowded").index(c["scenario"]),
                                  ("baseline", "adaptive").index(c["policy"])))
    found = {}
    for case in cases:
        deaths = {d["id"]: d for d in case["deaths"]}
        for plant in eligible(case):
            death = plant["death_tick"]
            if death is None or death > plant["birth_tick"] + DAY:
                role = "survivor"
            else:
                event = deaths[plant["id"]]
                if event["climate"]["drought"] or event["climate"]["light_percent"] != 100:
                    continue
                role = {3: "energy", 5: "water"}.get(event["flags"])
            if role is None or role in found:
                continue
            narrow = next(c for c in report["cases"]["control"] if identity(c) == identity(case))
            analogs = [p for p in eligible(narrow) if p["species"] == plant["species"]]
            analog = min(analogs, key=lambda p: (abs(p["birth_tick"] - plant["birth_tick"]),
                                                p["birth_tick"], p["id"])) if analogs else None
            found[role] = {"role": role, "case": identity(case), "wide": plant, "control": analog}
    require(set(found) == {"energy", "water", "survivor"}, "Missing predeclared focal category")
    return [found[role] for role in ("energy", "water", "survivor")]


def stop(plant: dict) -> int:
    return min(plant["birth_tick"] + DAY, plant["death_tick"] or END)


def jobs_for(report: dict, chosen: list[dict]) -> list[dict]:
    jobs = {}
    for role in chosen:
        for arm in ("control", "wide"):
            key = arm + "-" + role["case"]
            job = jobs.setdefault(key, {"key": key, "arm": arm,
                "case": next(c for c in report["cases"][arm] if identity(c) == role["case"]),
                "plants": {}, "frame_ticks": set()})
            if role[arm] is not None:
                job["plants"][role[arm]["id"]] = role[arm]
            job["frame_ticks"].update((role["wide"]["birth_tick"], stop(role["wide"])))
    return list(jobs.values())


def live_point(row: dict, old: dict | None, plant: dict, bids: list[dict]) -> dict:
    values = budget(old, plant, row["tick"])
    before_agent = old["agent"] if old else {}
    actions = {key: plant["agent"][key] - before_agent.get(key, 0)
               for key in ("decisions", "root_extend", "shoot_extend", "finish", "wait")}
    require(all(n >= 0 for n in actions.values()) and
            actions["decisions"] == sum(actions[k] for k in ("root_extend", "shoot_extend", "finish", "wait")) <= 1,
            "Changed action accounting")
    require(actions["root_extend"] + actions["shoot_extend"] == values["extensions"], "Wrong extension tissue")
    available = {r: (64 if r == "energy" else 24) if old is None else old[r] for r in ("energy", "water")}
    for resource in available:
        available[resource] += values[resource + "_income"] - values[resource + "_overflow"] - values[resource + "_upkeep"]
    costs = {"energy": ENERGY_COST[plant["species"]] - (plant["vigor"] > 0), "water": WATER_COST[plant["species"]]}
    if bids:
        require(all((b["energy"], b["water"]) == (available["energy"], available["water"]) for b in bids),
                "Bid/budget pre-growth stores disagree")
    roots = {(x, y): water for x, y, _, water in plant["root_cells"]}
    require(len(plant["root_cells"]) == plant["roots"], "Root cell/count disagreement")
    old_body = old or plant
    upkeep = {r: (old_body["nodes"] - (old_body["roots"] if r == "water" else 0) + 7) // 8
              if old is not None and row["tick"] % 60 == 0 else 0 for r in ("energy", "water")}
    return {"budget": values, "actions": actions, "pre_growth": available,
            "below_growth_cost": {r: available[r] < costs[r] for r in costs},
            "upkeep_due": upkeep,
            "root_post_water": sum(roots.values()), "unique_root_cells": len(roots),
            "deepest_root_row": max((y for _, y in roots), default=-1)}


def describe(record: dict, steps: list[dict]) -> dict:
    require([s["tick"] for s in steps] == list(range(record["birth_tick"], stop(record) + 1, 15)),
            "Incomplete focal follow-up")
    require(steps[-1]["plant"]["dead"] == (record["death_tick"] == stop(record)), "Wrong focal endpoint")
    totals, due, actions = Counter(), Counter(), Counter()
    for point in steps:
        if point["terminal"] is not None:
            for resource in ("energy", "water"):
                receipt = point["terminal"][resource]
                for metric in ("income", "overflow"):
                    totals[resource + "_" + metric] += receipt[metric]
                totals[resource + "_upkeep"] += receipt["upkeep_paid"]
                totals[resource + "_discarded"] += receipt["discarded"]
                due[resource] += receipt["upkeep_due"]
        else:
            totals.update(point["budget"])
            due.update(point["upkeep_due"])
            actions.update(point["actions"])
    for resource, initial in (("energy", 64), ("water", 24)):
        require(initial + totals[resource + "_income"] - sum(totals[resource + "_" + key]
                for key in ("overflow", "upkeep", "growth", "seeds", "discarded")) == steps[-1]["plant"][resource],
                "Whole focal resource balance does not close")
    live = [s for s in steps if not s["plant"]["dead"]]
    marks = {"birth": steps[0], "last_live": live[-1], "end": steps[-1]}
    for name, condition in (("first_energy_shortage", lambda s: s["plant"]["flags"] & 2),
                            ("first_water_shortage", lambda s: s["plant"]["flags"] & 4),
                            ("first_root_growth", lambda s: not s["plant"]["dead"] and s["actions"]["root_extend"]),
                            ("first_energy_income", lambda s: not s["plant"]["dead"] and s["budget"]["energy_income"]),
                            ("first_sunset", lambda s: s["phase"] == 128),
                            ("first_dawn", lambda s: s["phase"] == 0)):
        marks[name] = next((s for s in steps if condition(s)), None)
    return {"record": record, "observed_steps": len(steps), "live_steps": len(live),
            "totals": dict(totals), "upkeep_due": dict(due), "actions": dict(actions),
            "below_growth_cost_steps": {r: sum(s["below_growth_cost"][r] for s in live) for r in ("energy", "water")},
            "productive_global_light_zero_energy_steps": sum(s["sun_strength"] >= 64 and
                s["plant"]["active_leaves"] > 0 and s["budget"]["energy_income"] == 0 for s in live[1:]),
            "zero_water_income_steps": sum(s["budget"]["water_income"] == 0 for s in live[1:]),
            "checkpoints": marks, "steps": steps}


def analyze_trace(path: Path, job: dict) -> dict:
    previous, bids, deaths, sparse, anchors = {}, {}, {}, [], {}
    histories = {ident: [] for ident in job["plants"]}
    last_tick, old_counts, terminal_count, world_count, bid_count = -15, (-1, -1), 0, 0, 0
    with gzip.open(path, "rt") as stream:
        for line in stream:
            row = json.loads(line)
            tick, kind = row["tick"], row["type"]
            if kind == "bid":
                require(tick == last_tick + 15 and row["action"] == row["original_action"] and
                        row["priority"] == row["original_priority"], "Changed/misordered decision")
                bids.setdefault(row["id"], []).append(row)
                bid_count += 1
                continue
            if kind == "death":
                require(tick == last_tick + 15 and row["id"] not in deaths, "Duplicate/misordered receipt")
                deaths[row["id"]] = row
                continue
            require(kind == "world" and tick == last_tick + 15 and row.get("death_audit_version") == 1,
                    "Missing/unknown ecology sample")
            require("leaf_environment" not in row and row["sun_phase"] == (64 + tick // 15) % 256,
                    "Changed environment/phase")
            current = {p["id"]: p for p in row["plants"]}
            require(len(current) == len(row["plants"]), "Duplicate lineage")
            for ident, plant in current.items():
                old = previous.get(ident)
                proposals = bids.pop(ident, [])
                decisions = plant["agent"]["decisions"] - (old["agent"]["decisions"] if old else 0)
                require(decisions == int(bool(proposals)), "Bid/decision delta mismatch")
                if proposals:
                    winner = max(proposals, key=lambda b: b["priority"])
                    require(all(winner[k] == plant["agent"]["last_" + k] for k in ("priority", "action", "tissue", "x", "y")),
                            "Wrong recorded decision winner")
                terminal = deaths.pop(ident, None)
                if plant["dead"] and (old is None or not old["dead"]):
                    require(old is not None and terminal is not None, "Missing terminal receipt")
                    reconcile_death(old, plant, terminal, tick)
                    terminal_count += 1
                else:
                    require(terminal is None, "Unexpected terminal receipt")
                if ident in histories and job["plants"][ident]["birth_tick"] <= tick <= stop(job["plants"][ident]):
                    point = {"tick": tick, "hash": row["hash"], "phase": row["sun_phase"],
                             "sun_strength": row["sun_strength"], "climate": row["climate"],
                             "world_nodes": row["nodes"], "rain_rate": row["rain_rate"],
                             "plant": plant, "bids": proposals, "terminal": terminal}
                    if not plant["dead"]:
                        point.update(live_point(row, old, plant, proposals))
                    histories[ident].append(point)
            require(not bids and not deaths and row["deaths"] == terminal_count, "Unmatched events/deaths")
            require(all(old["dead"] for ident, old in previous.items() if ident not in current), "Living plant vanished")
            counts = (row["births"], row["deaths"])
            if tick % DAY == 0 or counts != old_counts:
                sparse.append(row)
            if tick in job["frame_ticks"]:
                anchors[str(tick)] = row["hash"]
            previous, last_tick, old_counts = current, tick, counts
            world_count += 1
    require(last_tick == END and not bids and not deaths, "Truncated trace")
    historical = analyze_worlds(sparse, 128, "seasonal")
    require(all(historical[k] == job["case"][k] for k in historical), "Changed historical states/lifetimes")
    return {"key": job["key"], "worlds_checked": world_count, "daily_states_checked": len(historical["daily"]),
            "terminal_receipts_checked": terminal_count, "bids_checked": bid_count, "frame_hashes": anchors,
            "plants": [describe(job["plants"][ident], steps) for ident, steps in histories.items()]}


def capture(build: Path, job: dict, output: Path) -> None:
    case = job["case"]
    command = [build / "toy-factory-garden-inspect", "-", case["scenario"], case["policy"],
               str(int(case["seed"], 16)), "--ticks", str(END), "--climate", "seasonal", "--death-audit"]
    with tempfile.TemporaryFile() as stream:
        subprocess.run(list(map(str, command)), stdout=stream, stderr=subprocess.PIPE, check=True, timeout=300)
        stream.seek(0)
        with output.open("xb") as target, gzip.GzipFile(filename="", fileobj=target, mode="wb", mtime=0) as zipped:
            shutil.copyfileobj(stream, zipped)


def render(build: Path, job: dict, analyzed: dict, output: Path) -> list[dict]:
    sys.path.insert(0, str(ROOT / "scripts/container"))
    from framebuffer_capture import rgb565be_to_rgb888, write_png
    result = []
    for tick in sorted(job["frame_ticks"]):
        raw = output / f"{job['key']}-{tick}.rgb565be"
        case = job["case"]
        command = [build / "toy-factory-garden-replay", "-", case["scenario"], case["policy"],
                   str(int(case["seed"], 16)), "--ticks", str(tick), "--climate", "seasonal", "--framebuffer", raw]
        state = json.loads(subprocess.check_output(list(map(str, command)), text=True, timeout=300))
        pixels = raw.read_bytes()
        require(state["hash"] == analyzed["frame_hashes"][str(tick)] and len(pixels) == 240 * 240 * 2 and
                state["framebuffer_crc32"] == f"{zlib.crc32(pixels):08x}", "Rendered frame mismatch")
        png = raw.with_suffix(".png")
        write_png(png, 240, 240, rgb565be_to_rgb888(pixels))
        result.append({"png": "frames/" + png.name, "png_sha256": digest(png), "tick": tick,
                       "hash": state["hash"], "framebuffer_crc32": state["framebuffer_crc32"]})
    return result


def frozen_inputs(builds: dict) -> dict:
    sources = source_hashes(ROOT)
    for name in (PROTOCOL, "sim/garden_season_seedlings.py", "sim/garden_resources.py", "sim/garden_deaths.py",
                 "sim/garden_season_confirmation.py", "sim/garden_season_offspring.py",
                 "sim/garden_season_recruitment.py", "scripts/container/framebuffer_capture.py"):
        sources[name] = digest(ROOT / name)
    return {"sources": sources, "builds": {arm: {
        "inspector_sha256": digest(build / "toy-factory-garden-inspect"),
        "replayer_sha256": digest(build / "toy-factory-garden-replay"),
        "flags": build_flags(build / "CMakeCache.txt")} for arm, build in builds.items()}}


def compact(report: dict) -> dict:
    result = json.loads(json.dumps(report))
    for case in result["cases"]:
        for plant in case["plants"]:
            steps = plant.pop("steps")
            plant["steps_sha256"] = hashlib.sha256(json.dumps(steps, sort_keys=True).encode()).hexdigest()
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("plan", "collect", "verify"))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--control-build", type=Path, default=Path("build-host"))
    parser.add_argument("--wide-build", type=Path, default=Path("artifacts/build-host-seasonal-wide"))
    args = parser.parse_args()
    parent = load_input()
    chosen = selection(parent)
    if args.command == "plan":
        with args.out.open("x") as stream:
            stream.write(json.dumps(chosen, indent=2) + "\n")
        print(json.dumps(chosen, indent=2))
        return
    jobs = jobs_for(parent, chosen)
    if args.command == "verify":
        report = json.loads((args.out / "results.json").read_text())
        require(report["selection"] == chosen and len(report["cases"]) == len(jobs), "Changed selection")
        for job, saved in zip(jobs, report["cases"]):
            trace = args.out / (job["key"] + ".jsonl.gz")
            require(digest(trace) == digest(args.out / (job["key"] + ".repeat.jsonl.gz")) == saved["trace_sha256"],
                    "Changed/repeated trace")
            actual = analyze_trace(trace, job)
            require(all(saved[k] == v for k, v in actual.items()), "Changed resource analysis")
            for frame in saved["frames"]:
                require(digest(args.out / frame["png"]) == frame["png_sha256"], "Changed PNG")
        require(compact(report) == json.loads((args.out / "summary.json").read_text()), "Changed compact report")
        print("Verified all resource histories, repeated traces, historical states and images")
        return
    builds = {"control": args.control_build.resolve(), "wide": args.wide_build.resolve()}
    frozen = frozen_inputs(builds)
    require(source_hashes(ROOT) == parent["frozen"]["source_sha256"], "Changed native sources")
    for arm, build in frozen["builds"].items():
        require(all(value == parent["frozen"]["builds"][arm][key] for key, value in build.items()),
                "Changed frozen binary/configuration")
    args.out.mkdir(parents=True, exist_ok=False)
    (args.out / "frames").mkdir()

    def run(job):
        trace = args.out / (job["key"] + ".jsonl.gz")
        capture(builds[job["arm"]], job, trace)
        value = analyze_trace(trace, job)
        repeat = args.out / (job["key"] + ".repeat.jsonl.gz")
        capture(builds[job["arm"]], job, repeat)
        require(digest(trace) == digest(repeat), "Nonrepeatable audited native trace")
        value["trace_sha256"] = digest(trace)
        value["frames"] = render(builds[job["arm"]], job, value, args.out / "frames")
        print("Verified " + job["key"], flush=True)
        return value

    with ThreadPoolExecutor(max_workers=2) as pool:
        cases = list(pool.map(run, jobs))
    require(frozen_inputs(builds) == frozen, "Changed inputs during replay")
    report = {"protocol": "seasonal-seedling-resources-v1", "input_sha256": INPUT_SHA256,
              "selection": chosen, "frozen": frozen, "cases": cases}
    (args.out / "results.json").write_text(json.dumps(report, indent=2) + "\n")
    (args.out / "summary.json").write_text(json.dumps(compact(report), indent=2) + "\n")
    print(f"Verified {len(cases)} paired-world jobs and {sum(len(c['plants']) for c in cases)} focal plants")


if __name__ == "__main__":
    main()
