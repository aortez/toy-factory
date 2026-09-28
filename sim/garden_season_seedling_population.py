#!/usr/bin/env python3
"""Fixed 32-world all-offspring reserve screen; no tuning or default promotion."""

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
import sys
import tempfile
import zlib

import garden_season_seedling_components as components
import garden_season_seedling_reserve as reserve
from garden_deaths import reconcile_death
from garden_resources import budget
from garden_season_confirmation import SEEDS, LAYOUTS, POLICIES
from garden_season_dispersal import group
from garden_season_offspring import cohort, validate_history, INPUT_SHA256
from garden_season_recruitment import digest, identity
from garden_seasons import DAY_TICKS as DAY, analyze_worlds, require

ROOT, END = reserve.ROOT, reserve.END
RULE = "seedling-population-reserve-v1"
PROTOCOL = "benchmarks/garden-seasons/seedling-population-protocol.md"
METADATA = {"rule": reserve.RULE, "scope": "offspring"}
ARMS = ("control", "guard")
COMPONENT_SUMMARY_SHA = "6cdc7bec04a53aa01d0fe54c1d20975290801678ec874f06826c64e2f93d46d1"


def inputs() -> list[dict]:
    prior = reserve.seedlings.load_input()
    cases = [c for c in prior["cases"]["wide"] if c["mode"] == "seasonal"]
    expected = {(layout, policy, seed) for layout in LAYOUTS for policy in POLICIES for seed in SEEDS}
    require(len(cases) == 32 and {(c["scenario"], c["policy"], c["seed"]) for c in cases} == expected,
            "Changed fixed seasonal panel")
    return cases


def outcomes(history: dict) -> dict:
    plants, deaths = validate_history(history)
    result = {"cohorts": {}, "two_day": {}}
    for name, start in (("whole", 0), ("closing", 112 * DAY + 1)):
        result["cohorts"][name] = cohort(plants, deaths, start)
        born = [p for p in plants.values() if p["parent"] and p["birth_tick"] >= start]
        eligible = [p for p in born if p["birth_tick"] + 2 * DAY <= END]
        result["two_day"][name] = {"eligible": len(eligible), "censored": len(born) - len(eligible),
            "survivors": sum(p["death_tick"] is None or p["death_tick"] > p["birth_tick"] + 2 * DAY
                             for p in eligible)}
    result["founders"] = [p for p in plants.values() if not p["parent"]]
    return result


class Audit:
    def __init__(self, enabled: bool, seed_capacity: int = 8):
        require(type(seed_capacity) is int and seed_capacity in (8, 16), "Unsupported seed capacity")
        self.seed_capacity = seed_capacity
        self.enabled = enabled
        self.previous, self.births, self.lineages = {}, {}, {}
        self.sparse, self.terminals = [], []
        self.counts, self.old_counts = Counter(), (-1, -1)
        self.first_empty_tick = None

    def accept(self, world: dict, proposals: list, receipts: list) -> None:
        tick = world["tick"]
        require(world.get("seedling_reserve") == (METADATA if self.enabled else None) and
                world["sun_phase"] == (64 + tick // 15) % 256 and "leaf_environment" not in world and
                world["nodes"] <= 256 and len(world["plants"]) <= 8 and
                world.get("seed_capacity", 8) == self.seed_capacity and
                len(world["seeds"]) <= self.seed_capacity,
                "Changed population rule/environment")
        current = {p["id"]: p for p in world["plants"]}
        require(len(current) == len(world["plants"]), "Duplicate plant")
        for ident, plant in current.items():
            if ident not in self.births:
                require(not plant["dead"] and (bool(plant["parent"]) == (tick != 0)) and
                        bool(plant["parent"]) == bool(plant["generation"]), "Invalid new plant")
                self.births[ident] = tick
                self.lineages[ident] = Counter()
            elif ident not in self.previous:
                raise RuntimeError("Reclaimed lineage ID reused")
        bids, deaths = {}, {}
        for bid in proposals:
            ident = bid["id"]
            require(ident in current and not current[ident]["dead"] and bid["tick"] == tick,
                    "Bid for missing/dead plant")
            plant = current[ident]
            birth = self.births[ident]
            spec = {"record": {"id": ident, "birth_tick": birth}}
            counts = reserve.check_bid(bid, spec, self.enabled and bool(plant["parent"]))
            o = bid.get("seedling_reserve")
            if o is not None:
                old = self.previous.get(ident)
                require(o.get("scope") == "offspring" and
                        (o["nodes"], o["roots"]) == ((old["nodes"], old["roots"]) if old else (4, 2)) and
                        o["age"] == plant["age_ecology_ticks"] and o["income"] == plant["energy_income"] and
                        o["vigor"] == plant["vigor"] and
                        o["species"] == ("flower", "shrub", "ground-cover").index(plant["species"]),
                        "Forecast disagrees with plant history")
            self.counts.update(counts)
            self.lineages[ident].update(counts)
            bids.setdefault(ident, []).append(bid)
        for receipt in receipts:
            require(receipt["id"] not in deaths, "Duplicate terminal receipt")
            deaths[receipt["id"]] = receipt
        for ident, plant in current.items():
            old, choices = self.previous.get(ident), bids.pop(ident, [])
            require(plant["agent"]["decisions"] - (old["agent"]["decisions"] if old else 0) == int(bool(choices)),
                    "Wrong decision delta")
            if choices:
                winner = max(choices, key=lambda b: b["priority"])
                require(all(winner[k] == plant["agent"]["last_" + k] for k in ("priority", "action", "tissue", "x", "y")),
                        "Wrong committed winner")
                if "seedling_reserve" in winner:
                    counts = Counter(veto_commits=int(winner["action"] != winner["original_action"]))
                    counts["wet_root_exception_commits"] = reserve.check_bid(winner,
                        {"record": {"id": ident, "birth_tick": self.births[ident]}}, True)["wet_root_exception_bids"]
                    self.counts.update(counts)
                    self.lineages[ident].update(counts)
            terminal = deaths.pop(ident, None)
            if plant["dead"] and old is not None and not old["dead"]:
                require(terminal is not None, "Missing terminal receipt")
                reconcile_death(old, plant, terminal, tick)
                self.terminals.append({"receipt": terminal, "climate": world["climate"]})
                self.counts["terminal_receipts"] += 1
            else:
                require(terminal is None and (not plant["dead"] or old is not None), "Unexpected death")
            if old is not None and old["dead"]:
                require(plant["dead"], "Dead plant revived")
            if tick and not plant["dead"]:
                budget(old, plant, tick)
                self.counts["live_budgets"] += 1
        require(not bids and not deaths and world["deaths"] == self.counts["terminal_receipts"], "Unmatched events")
        require(all(p["dead"] for ident, p in self.previous.items() if ident not in current), "Living plant vanished")
        if self.first_empty_tick is None and not world["living"] and not world["seeds"]:
            self.first_empty_tick = tick
        counts = (world["births"], world["deaths"])
        if tick % DAY == 0 or counts != self.old_counts:
            self.sparse.append(world)
        self.previous, self.old_counts = current, counts
        self.counts["worlds"] += 1

    def result(self, case: dict) -> dict:
        history = analyze_worlds(self.sparse, 128, "seasonal")
        if not self.enabled:
            require(all(case[k] == v for k, v in history.items()), "Changed frozen control history")
        require({p["id"]: p["birth_tick"] for p in history["plants"]} == self.births, "Incomplete birth census")
        return {"history": history, "outcomes": outcomes(history), "counts": dict(self.counts),
                "first_empty_tick": self.first_empty_tick, "terminals": self.terminals,
                "lineages": {str(ident): dict(counts) for ident, counts in self.lineages.items()}}


def analyze_pair(control: Path, guard: Path, case: dict) -> dict:
    audits = [Audit(False), Audit(True)]
    prefix, first_bid, first_state = 0, None, None
    for pair in zip_longest(reserve.groups(control), reserve.groups(guard)):
        require(all(g is not None for g in pair), "Unequal traces")
        (before, old_bids, old_deaths), (after, new_bids, new_deaths) = pair
        require(all(before[k] == after[k] for k in ("tick", "climate", "rain_rate", "sun_strength")) and
                before["rain_deposited"] + before["rain_runoff"] ==
                after["rain_deposited"] + after["rain_runoff"], "Unmatched external environment")
        if first_bid is None:
            if any(b["action"] != b["original_action"] for b in new_bids):
                first_bid = before["tick"]
            else:
                require(before == {k: v for k, v in after.items() if k != "seedling_reserve"} and
                        old_deaths == new_deaths and old_bids ==
                        [{k: v for k, v in b.items() if k != "seedling_reserve"} for b in new_bids],
                        "Changed pre-intervention prefix")
                prefix += 1
        if first_state is None and before["hash"] != after["hash"]:
            require(first_bid is not None, "State changed before override")
            first_state = before["tick"]
        for audit, item in zip(audits, pair):
            audit.accept(*item)
    result = {"case": {k: case[k] for k in ("mode", "scenario", "policy", "seed")},
              "exact_prefix_worlds": prefix, "first_changed_bid": first_bid, "first_changed_state": first_state,
              "arms": {name: audit.result(case) for name, audit in zip(ARMS, audits)}}
    founders = [result["arms"][name]["outcomes"]["founders"] for name in ARMS]
    require([{k: v for k, v in p.items() if k != "death_tick"} for p in founders[0]] ==
            [{k: v for k, v in p.items() if k != "death_tick"} for p in founders[1]], "Changed founder identity")
    result["founder_pairs"] = [{"id": a["id"], "species": a["species"], "control_death": a["death_tick"],
        "guard_death": b["death_tick"], "earlier_death": b["death_tick"] is not None and
        (a["death_tick"] is None or b["death_tick"] < a["death_tick"])} for a, b in zip(*founders)]
    return result


def metrics(arms: list[dict]) -> dict:
    result = group([arm["history"] for arm in arms])
    result["closing_eligible"] = sum(a["history"]["closing_lifetimes"]["eligible"] for a in arms)
    result["closing_censored"] = sum(a["history"]["closing_lifetimes"]["too_young"] for a in arms)
    result["transient_empty_worlds"] = sum(a["first_empty_tick"] is not None for a in arms)
    result["zero_living_endpoints"] = sum(a["history"]["daily"][-1]["living"] == 0 for a in arms)
    result["founders_alive"] = sum(p["death_tick"] is None for a in arms for p in a["outcomes"]["founders"])
    for key in ("living", "seeds_created", "seeds_expired"):
        result[key] = sum(a["history"]["daily"][-1][key] for a in arms)
    result["two_day"] = {window: {key: sum(a["outcomes"]["two_day"][window][key] for a in arms)
        for key in ("eligible", "censored", "survivors")} for window in ("whole", "closing")}
    result["cohorts"] = {window: {key: sum(a["outcomes"]["cohorts"][window]["totals"][key] for a in arms)
        for key in arms[0]["outcomes"]["cohorts"][window]["totals"]} for window in ("whole", "closing")}
    return result


def fraction_retained(before: dict, after: dict) -> bool:
    if before["closing_eligible"] == 0:
        return True
    return after["closing_eligible"] > 0 and (
        after["closing_survivors"] * before["closing_eligible"] >=
        before["closing_survivors"] * after["closing_eligible"])


def analysis(cases: list[dict], panel: list[dict] | None = None) -> dict:
    panel = inputs() if panel is None else panel
    seeds = tuple(dict.fromkeys(c["seed"] for c in panel))
    expected = {identity(c) for c in panel}
    require(len(panel) == 32 and len(seeds) == 8 and expected == {
        identity({"mode": "seasonal", "scenario": layout, "policy": policy, "seed": seed})
        for layout in LAYOUTS for policy in POLICIES for seed in seeds}, "Invalid fixed panel")
    require(len(cases) == 32 and {identity(c["case"]) for c in cases} == expected, "Incomplete/duplicate panel")
    groups = {name: metrics([c["arms"][name] for c in cases]) for name in ARMS}
    before, after = [groups[name] for name in ARMS]
    retained = ("closing_birth_worlds", "closing_survivors", "closing_durable_parents",
                "historical_durable_parents", "multi_viable_species_worlds")
    gates = {"retain_" + name: after[name] >= before[name] for name in retained}
    gates["improve_closing_renewal"] = any(after[name] > before[name] for name in retained[:3])
    gates["retain_closing_survival_fraction"] = fraction_retained(before, after)
    gates["no_new_empty_world"] = all(c["arms"]["guard"]["first_empty_tick"] is None or
        c["arms"]["control"]["first_empty_tick"] is not None for c in cases)
    gates["no_new_zero_living_endpoint"] = all(c["arms"]["guard"]["history"]["daily"][-1]["living"] > 0 or
        c["arms"]["control"]["history"]["daily"][-1]["living"] == 0 for c in cases)
    paired = {}
    for key in (*retained, "births", "survivors", "founders_alive", "living"):
        deltas = [metrics([c["arms"]["guard"]])[key] - metrics([c["arms"]["control"]])[key] for c in cases]
        paired[key] = {"increased": sum(x > 0 for x in deltas), "unchanged": sum(x == 0 for x in deltas),
                       "decreased": sum(x < 0 for x in deltas)}
    partitions = {field: {value: {arm: metrics([c["arms"][arm] for c in cases if c["case"][field] == value])
        for arm in ARMS} for value in values} for field, values in
        (("seed", seeds), ("scenario", LAYOUTS), ("policy", POLICIES))}
    return {"groups": groups, "gates": gates, "passes_screen": all(gates.values()),
            "paired": paired, "partitions": partitions}


def path(output: Path, case: dict, arm: str, repeat: bool = False) -> Path:
    return output / f"{identity(case)}-{arm}{'.repeat' if repeat else ''}.jsonl.gz"


def capture(build: Path, case: dict, arm: str, target: Path) -> None:
    command = [build / "toy-factory-garden-inspect", "-", case["scenario"], case["policy"],
               str(int(case["seed"], 16)), "--climate", "seasonal", "--ticks", str(END), "--death-audit"]
    if arm == "guard":
        command += ["--seedling-reserve", "all"]
    with tempfile.TemporaryFile() as stream:
        subprocess.run(list(map(str, command)), stdout=stream, stderr=subprocess.PIPE, check=True, timeout=300)
        stream.seek(0)
        with target.open("xb") as raw, gzip.GzipFile(filename="", fileobj=raw, mode="wb", mtime=0) as compressed:
            shutil.copyfileobj(stream, compressed)


def render(build: Path, output: Path, result: dict, first_seed: str = SEEDS[0],
           prefix: str = "population") -> list[dict]:
    case = result["case"]
    if case["seed"] != first_seed or case["policy"] != "baseline":
        return []
    sys.path.insert(0, str(ROOT / "scripts/container"))
    from framebuffer_capture import rgb565be_to_rgb888, write_png
    frames = []
    for arm in ARMS:
        for day in (16, 128):
            target = output / "frames" / f"{prefix}-{case['scenario']}-{arm}-day-{day}.rgb565be"
            command = [build / "toy-factory-garden-replay", "-", case["scenario"], case["policy"],
                       str(int(case["seed"], 16)), "--climate", "seasonal", "--ticks", str(day * DAY),
                       "--framebuffer", target]
            if arm == "guard":
                command += ["--seedling-reserve", "all"]
            row = json.loads(subprocess.check_output(list(map(str, command)), text=True, timeout=300))
            raw = target.read_bytes()
            require(row["hash"] == result["arms"][arm]["history"]["daily"][day]["hash"] and
                    len(raw) == 115200 and row["framebuffer_crc32"] == f"{zlib.crc32(raw):08x}" and
                    row.get("seedling_reserve") == (METADATA if arm == "guard" else None), "Render mismatch")
            png = target.with_suffix(".png")
            write_png(png, 240, 240, rgb565be_to_rgb888(raw))
            frames.append({"png": "frames/" + png.name, "png_sha256": digest(png), "arm": arm,
                           "day": day, "hash": row["hash"], "framebuffer_crc32": row["framebuffer_crc32"]})
    return frames


def run_job(item) -> dict:
    build, output, case = item
    for arm in ARMS:
        for repeat in (False, True):
            capture(build, case, arm, path(output, case, arm, repeat))
        require(digest(path(output, case, arm)) == digest(path(output, case, arm, True)), "Nonrepeatable trace")
    result = analyze_pair(path(output, case, "control"), path(output, case, "guard"), case)
    result["traces"] = {arm: digest(path(output, case, arm)) for arm in ARMS}
    result["frames"] = render(build, output, result)
    (output / (identity(case) + ".json")).write_text(json.dumps(result, indent=2) + "\n")
    print("Verified " + identity(case), flush=True)
    return result


def frozen(build: Path) -> dict:
    result = components.frozen(build)
    for name in (PROTOCOL, "sim/garden_season_seedling_population.py", "sim/test_garden_season_seedling_population.py",
                 "sim/garden_season_dispersal.py", "scripts/container/host-garden-defaults.sh"):
        result["sources"][name] = digest(ROOT / name)
    return result


def legacy_controls(build: Path, output: Path) -> list[dict]:
    prior, specs = components.inputs()
    results = []
    for old, spec in zip(prior["cases"], specs):
        for arm in ARMS:
            target = output / f"legacy-{spec['key']}-{arm}.jsonl.gz"
            reserve.capture(build, spec, arm == "guard", target)
            require(digest(target) == old["traces"][arm], "Changed legacy full trace")
            results.append({"path": target.name, "sha256": digest(target)})
    print("Verified all six legacy control/combined traces", flush=True)
    return results


def compact(report: dict) -> dict:
    result = {k: v for k, v in report.items() if k != "cases"}
    result["cases"] = []
    for case in report["cases"]:
        row = {k: v for k, v in case.items() if k != "arms"}
        row["arms"] = {}
        for arm, full in case["arms"].items():
            row["arms"][arm] = {"metrics": metrics([full]), "counts": full["counts"],
                "first_empty_tick": full["first_empty_tick"], "final": full["history"]["daily"][-1],
                "details_sha256": hashlib.sha256(json.dumps(full, sort_keys=True).encode()).hexdigest()}
        result["cases"].append(row)
    return result


def verify_case(item) -> None:
    output, case, saved = item
    actual = analyze_pair(path(output, case, "control"), path(output, case, "guard"), case)
    require(all(saved[k] == v for k, v in actual.items()), "Changed saved paired analysis")
    for arm in ARMS:
        require(digest(path(output, case, arm)) == digest(path(output, case, arm, True)) == saved["traces"][arm],
                "Changed repeated trace")
    for frame in saved["frames"]:
        target = output / frame["png"]
        raw = target.with_suffix(".rgb565be").read_bytes()
        require(digest(target) == frame["png_sha256"] and len(raw) == 115200 and
                f"{zlib.crc32(raw):08x}" == frame["framebuffer_crc32"] and
                frame["hash"] == saved["arms"][frame["arm"]]["history"]["daily"][frame["day"]]["hash"],
                "Changed frame")
    print("Rechecked " + identity(case), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("collect", "verify"))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--build", type=Path, default=Path("artifacts/build-host-seasonal-seedling-population"))
    parser.add_argument("--jobs", type=int, default=4)
    args = parser.parse_args()
    if not 1 <= args.jobs <= 4:
        parser.error("Require 1..4 independent workers")
    cases = inputs()
    if args.command == "verify":
        report = json.loads((args.out / "results.json").read_text())
        require(report["protocol"] == RULE and report["input_sha256"] == INPUT_SHA256 and
                len(report["cases"]) == len(cases), "Changed screen identity")
        with ProcessPoolExecutor(max_workers=args.jobs) as pool:
            list(pool.map(verify_case, ((args.out, c, s) for c, s in zip(cases, report["cases"]))))
        require(analysis(report["cases"]) == report["analysis"] and
                compact(report) == json.loads((args.out / "summary.json").read_text()), "Changed summary/analysis")
        require(len(report["legacy"]) == 6 and all(digest(args.out / r["path"]) == r["sha256"]
                for r in report["legacy"]), "Changed legacy controls")
        print("Verified complete all-offspring panel, budgets, cohorts, gates, repeats and captures")
        return
    build = args.build.resolve()
    provenance = frozen(build)
    previous_path = ROOT / "benchmarks/garden-seasons/seedling-components-summary.json"
    require(digest(previous_path) == COMPONENT_SUMMARY_SHA, "Changed component evidence")
    previous = json.loads(previous_path.read_text())
    require(provenance["flags"] == previous["frozen"]["flags"], "Changed ecology flags")
    allowed = {"sim/garden_inspect.c", "sim/garden_replay.c", "sim/garden_seedling_reserve.c",
               "sim/garden_seedling_reserve.h", "sim/garden_seedling_reserve_test.c", "sim/CMakeLists.txt"}
    for name, sha in previous["frozen"]["sources"].items():
        if name not in allowed:
            require(digest(ROOT / name) == sha, "Changed frozen dependency: " + name)
    args.out.mkdir(parents=True, exist_ok=False)
    (args.out / "frames").mkdir()
    legacy = legacy_controls(build, args.out)
    with ProcessPoolExecutor(max_workers=args.jobs) as pool:
        results = list(pool.map(run_job, ((build, args.out, case) for case in cases)))
    require(provenance == frozen(build), "Inputs changed during collection")
    report = {"protocol": RULE, "input_sha256": INPUT_SHA256, "component_summary_sha256": COMPONENT_SUMMARY_SHA,
              "legacy_input_sha256": components.PRIOR_SHA,
              "frozen": provenance, "legacy": legacy, "cases": results, "analysis": analysis(results)}
    (args.out / "results.json").write_text(json.dumps(report, indent=2) + "\n")
    (args.out / "summary.json").write_text(json.dumps(compact(report), indent=2) + "\n")
    print("Completed all 32 fixed pairs; passes_screen=" + str(report["analysis"]["passes_screen"]))


if __name__ == "__main__":
    main()
