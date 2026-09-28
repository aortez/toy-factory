#!/usr/bin/env python3
"""Fixed three-world, first-day reserve counterfactual; no parameter search."""

from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import gzip
import hashlib
from itertools import zip_longest
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

import garden_season_seedlings as seedlings
from garden_deaths import reconcile_death
from garden_resources import budget
from garden_season_confirmation import build_flags
from garden_season_recruitment import digest, identity
from garden_seasons import DAY_TICKS as DAY, analyze_worlds, require, source_hashes

ROOT = seedlings.ROOT
END = seedlings.END
RULE = "seedling-maintenance-reserve-v1"
PROTOCOL = "benchmarks/garden-seasons/seedling-reserve-protocol.md"
PRIOR_SHA = "32c2c1490cbdc7ef2a427d7519dfc40499a56420adc32578b60735b31aebb2a5"


def inputs() -> tuple[dict, list[dict]]:
    parent = seedlings.load_input()
    raw = gzip.decompress((ROOT / "benchmarks/garden-seasons/seedling-resources-histories.json.gz").read_bytes())
    require(hashlib.sha256(raw).hexdigest() == PRIOR_SHA, "Changed frozen focal histories")
    prior = json.loads(raw)
    require(prior["selection"] == seedlings.selection(parent), "Changed focal selection")
    return prior, [{"key": row["role"], "record": row["wide"],
                    "case": next(c for c in parent["cases"]["wide"] if identity(c) == row["case"]),
                    "prior": next(c for c in prior["cases"] if c["key"] == "wide-" + row["case"])}
                   for row in prior["selection"]]


def forecast(bid: dict) -> dict:
    """Independent arithmetic check, not a replacement simulation."""
    o = bid["seedling_reserve"]
    action, order = bid["original_action"], o["original_order"]
    require(action in (0, 1, 2) and 0 <= o["species"] < 3 and
            0 <= o["roots"] <= o["nodes"] and 0 <= o["maintenance_phase"] < 4 and
            0 <= o["sun_phase"] < 256, "Invalid forecast input")
    require(sorted(order) == (list(range(len(bid["candidates"]))) if action == 1 else []),
            "Invalid base candidate permutation")
    destination = next((i for i in order if bid["candidates"][i]["flags"] & 2), 255)
    result = {key: 0 for key in ("post_nodes", "growth_cost", "maintenance_cost", "daylight_steps",
                                "daylight_credit", "daylight_upkeep", "night_upkeep", "projected_sunset",
                                "water_cost", "water_upkeep", "water_reserve")}
    result.update(energy_allowed=action == 0, water_allowed=True, wet_root=False, destination=destination)
    if action and o["sun_phase"] < 128:
        post = o["nodes"] + int(action == 1 and destination != 255)
        cost = (9, 8, 7)[o["species"]] - int(o["vigor"] > 0)
        upkeep, daylight = max(1, (post + 7) // 8), 128 - o["sun_phase"]
        credit, day_upkeep = o["income"] * (daylight - 1) // 2, (daylight + o["maintenance_phase"]) // 4 * upkeep
        sunset = min(256, bid["energy"] - cost + credit - day_upkeep)
        result.update(post_nodes=post, growth_cost=cost, maintenance_cost=upkeep, daylight_steps=daylight,
                      daylight_credit=credit, daylight_upkeep=day_upkeep, night_upkeep=32 * upkeep,
                      projected_sunset=sunset, energy_allowed=bid["energy"] - cost >= upkeep and sunset >= 32 * upkeep)
    if action:
        cost = (5, 5, 4)[o["species"]]
        upkeep = (o["nodes"] - o["roots"] + int(action == 1 and destination != 255 and bid["tissue"] != 1) + 7) // 8
        wet = False
        if action == 1 and bid["tissue"] == 1 and destination != 255:
            candidate = bid["candidates"][destination]
            wet = candidate["y"] >= 144 and candidate["moisture"] >= cost and candidate["moisture"] > o["tip_moisture"]
        reserve = upkeep * (1 if wet else 4)
        result.update(water_cost=cost, water_upkeep=upkeep, water_reserve=reserve,
                      wet_root=wet, water_allowed=bid["water"] >= cost + reserve)
    result["allowed"] = result["energy_allowed"] and result["water_allowed"]
    return result


def treatment_identity(spec: dict, component: str = "both") -> dict:
    require(component in ("both", "energy", "water"), "Invalid reserve component")
    result = {"rule": RULE, "lineage": spec["record"]["id"]}
    if component != "both":
        result["component"] = component
    return result


def check_bid(bid: dict, spec: dict, enabled: bool, component: str = "both") -> Counter:
    require(component in ("both", "energy", "water"), "Invalid reserve component")
    birth, ident = spec["record"]["birth_tick"], spec["record"]["id"]
    active = enabled and bid["id"] == ident and birth <= bid["tick"] < birth + DAY
    require(("seedling_reserve" in bid) == active, "Wrong guard cohort/window")
    require(bid["priority"] == bid["original_priority"], "Guard changed priority")
    counts = Counter(bids=1)
    if not active:
        require(bid["action"] == bid["original_action"], "Changed non-focal/expired action")
        return counts
    o, expected = bid["seedling_reserve"], forecast(bid)
    require(o.get("component") == (None if component == "both" else component), "Wrong bid component")
    if component != "both":
        expected["allowed"] = expected[component + "_allowed"]
    require(o["age"] == 1 + (bid["tick"] - birth) // 15 and
            o["sun_phase"] == (64 + bid["tick"] // 15) % 256 and
            o["maintenance_phase"] == (bid["tick"] // 15) % 4, "Wrong forecast timing")
    require(all(o[key] == value for key, value in expected.items()), "Wrong native reserve forecast")
    require(bid["action"] == (bid["original_action"] if expected["allowed"] else 0) and
            o["order"] == (o["original_order"] if expected["allowed"] else []), "Wrong guard transformation")
    counts["guard_bids"] = 1
    if not expected["allowed"]:
        counts["veto_bids"] = 1
        reason = component if component != "both" else (
            "both" if not o["energy_allowed"] and not o["water_allowed"] else (
                "energy" if not o["energy_allowed"] else "water"))
        counts["veto_" + reason] = 1
    counts["wet_root_exception_bids"] = int(component != "energy" and o["allowed"] and o["wet_root"] and
        bid["water"] < o["water_cost"] + 4 * o["water_upkeep"])
    return counts


def groups(path: Path):
    bids, deaths, last = [], [], -15
    with gzip.open(path, "rt") as stream:
        for line in stream:
            row = json.loads(line)
            require(row["tick"] == last + 15, "Out-of-order ecology record")
            if row["type"] == "bid":
                bids.append(row)
            elif row["type"] == "death":
                deaths.append(row)
            else:
                require(row["type"] == "world" and row.get("death_audit_version") == 1,
                        "Unknown trace record")
                yield row, bids, deaths
                last, bids, deaths = row["tick"], [], []
    require(last == END and not bids and not deaths, "Truncated full trace")


def ledger(steps: list[dict]) -> dict:
    require(steps and [s["tick"] for s in steps] == list(range(steps[0]["tick"], steps[-1]["tick"] + 1, 15)),
            "Incomplete focal ledger")
    totals, due, actions = Counter(), Counter(), Counter()
    previous = None
    for step in steps:
        plant, terminal = step["plant"], step["terminal"]
        if terminal is not None:
            require(step is steps[-1] and previous is not None, "Unexpected focal death position")
            reconcile_death(previous, plant, terminal, step["tick"])
            for resource in ("energy", "water"):
                receipt = terminal[resource]
                for key in ("income", "overflow", "discarded"):
                    totals[resource + "_" + key] += receipt[key]
                totals[resource + "_upkeep"] += receipt["upkeep_paid"]
                due[resource] += receipt["upkeep_due"]
        else:
            live = seedlings.live_point(step, previous, plant, step["bids"])
            require(all(step[key] == value for key, value in live.items()), "Changed focal budget")
            totals.update(live["budget"])
            due.update(live["upkeep_due"])
            actions.update(live["actions"])
        previous = plant
    for resource, initial in (("energy", 64), ("water", 24)):
        require(initial + totals[resource + "_income"] - sum(totals[resource + "_" + key] for key in
            ("overflow", "upkeep", "growth", "seeds", "discarded")) == steps[-1]["plant"][resource],
            "Focal resource conservation failed")
    return {"end_tick": steps[-1]["tick"], "samples": len(steps), "totals": dict(totals),
            "upkeep_due": dict(due), "actions": dict(actions), "last": steps[-1]["plant"],
            "last_live": next(s["plant"] for s in reversed(steps) if not s["plant"]["dead"])}


class Audit:
    def __init__(self, spec: dict, enabled: bool, component: str = "both"):
        self.spec, self.enabled = spec, enabled
        self.component = component
        self.previous, self.sparse, self.steps, self.checkpoints = {}, [], [], {}
        self.counts, self.old_counts = Counter(), (-1, -1)
        self.neighbors = []

    def accept(self, row: dict, proposals: list, receipts: list) -> None:
        tick, focal, birth = row["tick"], self.spec["record"]["id"], self.spec["record"]["birth_tick"]
        require(row["sun_phase"] == (64 + tick // 15) % 256 and "leaf_environment" not in row,
                "Changed sun/environment contract")
        if self.enabled:
            require(row.get("seedling_reserve") == treatment_identity(self.spec, self.component),
                    "Wrong treatment identity")
        else:
            require("seedling_reserve" not in row, "Control contains guard")
        bids, deaths = {}, {}
        for bid in proposals:
            self.counts.update(check_bid(bid, self.spec, self.enabled, self.component))
            bids.setdefault(bid["id"], []).append(bid)
        for receipt in receipts:
            require(receipt["id"] not in deaths, "Duplicate death receipt")
            deaths[receipt["id"]] = receipt
        current = {p["id"]: p for p in row["plants"]}
        require(len(current) == len(row["plants"]), "Duplicate plant")
        for ident, plant in current.items():
            old, choices = self.previous.get(ident), bids.pop(ident, [])
            require(plant["agent"]["decisions"] - (old["agent"]["decisions"] if old else 0) == int(bool(choices)),
                    "Wrong decision delta")
            if choices:
                winner = max(choices, key=lambda b: b["priority"])
                require(all(winner[k] == plant["agent"]["last_" + k] for k in ("priority", "action", "tissue", "x", "y")),
                        "Wrong committed winner")
                if "seedling_reserve" in winner:
                    self.counts["veto_commits"] += winner["action"] != winner["original_action"]
                    self.counts["wet_root_exception_commits"] += check_bid(
                        winner, self.spec, True, self.component)["wet_root_exception_bids"]
            terminal = deaths.pop(ident, None)
            if plant["dead"] and old is not None and not old["dead"]:
                require(terminal is not None, "Missing death receipt")
                reconcile_death(old, plant, terminal, tick)
                self.counts["terminal_receipts"] += 1
            else:
                require(terminal is None and (not plant["dead"] or old is not None), "Unexpected death")
            if old is not None and old["dead"]:
                require(plant["dead"], "Dead plant revived")
            if tick and not plant["dead"]:
                budget(old, plant, tick)
                self.counts["live_budgets"] += 1
            if ident == focal and birth <= tick <= birth + 2 * DAY and (not plant["dead"] or terminal is not None):
                point = {"tick": tick, "phase": row["sun_phase"], "sun_strength": row["sun_strength"],
                         "hash": row["hash"], "climate": row["climate"], "plant": plant,
                         "bids": choices, "terminal": terminal}
                if not plant["dead"]:
                    point.update(seedlings.live_point(row, old, plant, choices))
                for bid in choices:
                    if "seedling_reserve" in bid:
                        o = bid["seedling_reserve"]
                        require((o["nodes"], o["roots"]) == ((old["nodes"], old["roots"]) if old else (4, 2)) and
                                o["income"] == plant["energy_income"] and o["vigor"] == plant["vigor"] and
                                o["species"] == ("flower", "shrub", "ground-cover").index(plant["species"]),
                                "Forecast inputs disagree with plant history")
                self.steps.append(point)
        require(not bids and not deaths and row["deaths"] == self.counts["terminal_receipts"], "Unmatched events")
        require(all(p["dead"] for ident, p in self.previous.items() if ident not in current), "Living plant vanished")
        counts = (row["births"], row["deaths"])
        if tick % DAY == 0 or counts != self.old_counts:
            self.sparse.append(row)
        if tick == birth - 15:
            self.neighbors = sorted(ident for ident, p in current.items() if not p["dead"])
        if tick in (birth + DAY, birth + 2 * DAY):
            self.checkpoints[str(tick)] = row
        self.previous, self.old_counts = current, counts
        self.counts["worlds"] += 1

    def result(self) -> dict:
        history = analyze_worlds(self.sparse, 128, "seasonal")
        if not self.enabled:
            require(all(self.spec["case"][key] == value for key, value in history.items()), "Changed control history")
        record = next(p for p in history["plants"] if p["id"] == self.spec["record"]["id"])
        require(all(record[k] == self.spec["record"][k] for k in record if k != "death_tick"), "Changed focal identity")
        birth, death = record["birth_tick"], record["death_tick"]
        require(self.steps[0]["tick"] == birth and
                self.steps[-1]["tick"] == min(birth + 2 * DAY, death or END), "Wrong follow-up boundary")
        return {"counts": dict(self.counts), "history": history, "focal": record, "neighbors": self.neighbors,
                "survived_one_day": death is None or death > birth + DAY,
                "survived_two_days": death is None or death > birth + 2 * DAY,
                "first_day": ledger([s for s in self.steps if s["tick"] <= birth + DAY]),
                "two_days": ledger(self.steps), "steps": self.steps, "checkpoints": self.checkpoints}


def analyze_pair(control: Path, guard: Path, spec: dict, component: str = "both") -> dict:
    audits = [Audit(spec, False), Audit(spec, True, component)]
    first_change, first_state_change, prefix_worlds = None, None, 0
    for pair in zip_longest(groups(control), groups(guard)):
        require(all(group is not None for group in pair), "Unequal trace lengths")
        (before, old_bids, old_deaths), (after, new_bids, new_deaths) = pair
        require(before["tick"] == after["tick"] and before["climate"] == after["climate"] and
                before["rain_rate"] == after["rain_rate"] and before["sun_strength"] == after["sun_strength"],
                "Unmatched environmental conditions")
        stripped = {k: v for k, v in after.items() if k != "seedling_reserve"}
        changed = [b for b in new_bids if b["action"] != b["original_action"]]
        if first_change is None:
            if changed:
                first_change = before["tick"]
            else:
                require(before == stripped and old_deaths == new_deaths and old_bids ==
                        [{k: v for k, v in b.items() if k != "seedling_reserve"} for b in new_bids],
                        "Changed pre-intervention prefix")
                prefix_worlds += 1
        if first_state_change is None and before["hash"] != after["hash"]:
            require(first_change is not None, "State changed before any override")
            first_state_change = before["tick"]
        for audit, group in zip(audits, pair):
            audit.accept(*group)
    off, on = [audit.result() for audit in audits]
    require(off["neighbors"] == on["neighbors"], "Changed pre-birth neighbors")
    neighbors = []
    for ident in off["neighbors"]:
        lives = [next(p for p in arm["history"]["plants"] if p["id"] == ident) for arm in (off, on)]
        require(all(lives[0][k] == lives[1][k] for k in lives[0] if k != "death_tick"), "Changed neighbor identity")
        a, b = [p["death_tick"] for p in lives]
        neighbors.append({"id": ident, "species": lives[0]["species"], "control_death": a, "guard_death": b,
                          "earlier_death": b is not None and (a is None or b < a)})
    return {"key": spec["key"], "case": identity(spec["case"]), "first_changed_bid": first_change,
            "first_changed_state": first_state_change, "exact_prefix_worlds": prefix_worlds,
            "neighbors": neighbors, "control": off, "guard": on}


def capture(build: Path, spec: dict, enabled: bool, out: Path, component: str = "both") -> None:
    require(component in ("both", "energy", "water") and (enabled or component == "both"),
            "Invalid capture component")
    case = spec["case"]
    command = [build / "toy-factory-garden-inspect", "-", case["scenario"], case["policy"],
               str(int(case["seed"], 16)), "--ticks", str(END), "--climate", "seasonal", "--death-audit"]
    if enabled:
        command += ["--seedling-reserve", str(spec["record"]["id"])]
        if component != "both":
            command += ["--seedling-reserve-component", component]
    with tempfile.TemporaryFile() as stream:
        subprocess.run(list(map(str, command)), stdout=stream, stderr=subprocess.PIPE, check=True, timeout=300)
        stream.seek(0)
        with out.open("xb") as target, gzip.GzipFile(filename="", fileobj=target, mode="wb", mtime=0) as archive:
            shutil.copyfileobj(stream, archive)


def frozen(build: Path) -> dict:
    sources = source_hashes(ROOT)
    for name in (PROTOCOL, "sim/garden_season_seedling_reserve.py", "sim/garden_season_seedlings.py",
                 "sim/garden_resources.py", "sim/garden_deaths.py", "sim/garden_season_confirmation.py",
                 "sim/garden_season_recruitment.py", "sim/garden_season_offspring.py",
                 "sim/CMakeLists.txt", "scripts/container/framebuffer_capture.py"):
        sources[name] = digest(ROOT / name)
    return {"sources": sources, "flags": build_flags(build / "CMakeCache.txt"),
            "inspector_sha256": digest(build / "toy-factory-garden-inspect"),
            "replayer_sha256": digest(build / "toy-factory-garden-replay")}


def compact(report: dict) -> dict:
    result = json.loads(json.dumps(report))
    for case in result["cases"]:
        for arm in ("control", "guard"):
            steps = case[arm].pop("steps")
            case[arm]["steps_sha256"] = hashlib.sha256(json.dumps(steps, sort_keys=True).encode()).hexdigest()
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("collect", "verify"))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--build", type=Path, default=Path("artifacts/build-host-seasonal-seedling-reserve"))
    args = parser.parse_args()
    prior, specs = inputs()
    if args.command == "verify":
        report = json.loads((args.out / "results.json").read_text())
        require(report["protocol"] == RULE and report["input_sha256"] == PRIOR_SHA and len(report["cases"]) == 3,
                "Changed panel identity")
        for spec, saved in zip(specs, report["cases"]):
            actual = analyze_pair(args.out / (spec["key"] + "-control.jsonl.gz"),
                                  args.out / (spec["key"] + "-guard.jsonl.gz"), spec)
            require(all(saved[k] == v for k, v in actual.items()), "Changed paired analysis")
            for arm in ("control", "guard"):
                path = args.out / f"{spec['key']}-{arm}.jsonl.gz"
                require(digest(path) == digest(path.with_name(path.name.replace(".jsonl", ".repeat.jsonl"))) ==
                        saved["traces"][arm], "Changed repeated trace")
            require(saved["traces"]["control"] == spec["prior"]["trace_sha256"], "Changed frozen control")
            for frame in saved["frames"]:
                require(digest(args.out / frame["png"]) == frame["png_sha256"], "Changed frame")
        require(compact(report) == json.loads((args.out / "summary.json").read_text()), "Changed summary")
        print("Verified fixed panel, all budgets, forecast arithmetic, prefixes, repeats and images")
        return
    build = args.build.resolve()
    provenance = frozen(build)
    require(provenance["flags"] == prior["frozen"]["builds"]["wide"]["flags"], "Changed ecology build flags")
    changes = {"sim/garden_inspect.c", "sim/garden_replay.c"}
    for name, sha in prior["frozen"]["sources"].items():
        if name not in changes:
            require(digest(ROOT / name) == sha, "Changed frozen dependency: " + name)
    args.out.mkdir(parents=True, exist_ok=False)
    (args.out / "frames").mkdir()

    def run(spec):
        paths = {}
        for arm in ("control", "guard"):
            path = args.out / f"{spec['key']}-{arm}.jsonl.gz"
            capture(build, spec, arm == "guard", path)
            if arm == "control":
                require(digest(path) == spec["prior"]["trace_sha256"], "Disabled native trace changed")
            repeat = args.out / f"{spec['key']}-{arm}.repeat.jsonl.gz"
            capture(build, spec, arm == "guard", repeat)
            require(digest(path) == digest(repeat), "Nonrepeatable native trace")
            paths[arm] = path
        result = analyze_pair(paths["control"], paths["guard"], spec)
        result["traces"] = {arm: digest(path) for arm, path in paths.items()}
        result["frames"] = render(build, spec, result, args.out / "frames")
        print("Verified " + spec["key"], flush=True)
        return result

    with ThreadPoolExecutor(max_workers=2) as pool:
        cases = list(pool.map(run, specs))
    require(provenance == frozen(build), "Inputs changed during experiment")
    report = {"protocol": RULE, "input_sha256": PRIOR_SHA, "frozen": provenance, "cases": cases}
    (args.out / "results.json").write_text(json.dumps(report, indent=2) + "\n")
    (args.out / "summary.json").write_text(json.dumps(compact(report), indent=2) + "\n")
    print("Completed all three fixed counterfactual pairs")


def render(build: Path, spec: dict, result: dict, output: Path) -> list[dict]:
    import sys
    import zlib
    sys.path.insert(0, str(ROOT / "scripts/container"))
    from framebuffer_capture import rgb565be_to_rgb888, write_png
    frames = []
    case = spec["case"]
    for arm in ("control", "guard"):
        for tick, world in result[arm]["checkpoints"].items():
            path = output / f"reserve-{spec['key']}-{arm}-{tick}.rgb565be"
            command = [build / "toy-factory-garden-replay", "-", case["scenario"], case["policy"],
                       str(int(case["seed"], 16)), "--climate", "seasonal", "--ticks", tick, "--framebuffer", path]
            if arm == "guard":
                command += ["--seedling-reserve", str(spec["record"]["id"])]
            row = json.loads(subprocess.check_output(list(map(str, command)), text=True, timeout=300))
            raw = path.read_bytes()
            require(row["hash"] == world["hash"] and len(raw) == 115200 and
                    row["framebuffer_crc32"] == f"{zlib.crc32(raw):08x}", "Rendered state/CRC mismatch")
            require(row.get("seedling_reserve") == world.get("seedling_reserve"), "Rendered guard identity mismatch")
            png = path.with_suffix(".png")
            write_png(png, 240, 240, rgb565be_to_rgb888(raw))
            frames.append({"png": "frames/" + png.name, "png_sha256": digest(png), "tick": int(tick),
                           "arm": arm, "hash": row["hash"], "framebuffer_crc32": row["framebuffer_crc32"]})
    require(len(frames) == 4, "Incomplete fixed image pair")
    return frames


if __name__ == "__main__":
    main()
