#!/usr/bin/env python3
"""Read-only ownership, residence and matched resource accounting for bank capacity."""

from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
import gzip
import hashlib
import json
from pathlib import Path

import garden_season_seed_bank_capacity as capacity
from garden_deaths import reconcile_death
from garden_resources import budget, TOTAL_KEYS
from garden_seasons import BLOCKERS, require

ROOT, DAY, END = capacity.ROOT, capacity.DAY, capacity.END
RULE = "seasonal-seed-bank-diagnosis-v1"
INPUT_SHA = "3ed1126d0db80996134bac59b6f3e0ffe3f78e61532612ddb8c668f2ba41a94e"
PROTOCOL = "benchmarks/garden-seasons/seed-bank-diagnosis-protocol.md"
WINDOWS = {"whole": 0, "closing": 112 * DAY}
AGES = {"under_1": (0, 1), "1_to_4": (1, 4), "4_to_16": (4, 16), "16_to_32": (16, 32)}
OUTCOMES = ("expired", "pending", "young_alive", "young_dead", "early_death", "day_only", "durable")
FLOW_KEYS = (*TOTAL_KEYS, "energy_discarded", "water_discarded")
STATE_KEYS = ("id", "energy", "water", "energy_income", "water_income", "nodes", "roots",
              "stress", "flags", "dead", "agent")


def load_input() -> dict:
    folder = ROOT / "benchmarks/garden-seasons"
    raw = gzip.decompress((folder / "seed-bank-capacity-histories.json.gz").read_bytes())
    require(hashlib.sha256(raw).hexdigest() == INPUT_SHA, "Changed capacity archive")
    report = json.loads(raw)
    capacity.validate_report(report, capacity.inputs()[0])
    require(capacity.compact(report) == json.loads((folder / "seed-bank-capacity-summary.json").read_text()),
            "Changed capacity summary")
    return report


def samples(seed: dict, start: int, low_age: int = 0, high_age: int = 32 * DAY,
            not_before: int = 0) -> int:
    """Exact post-step interval: creation included, resolution excluded, start excluded."""
    created, resolved = seed["created_tick"], seed["resolved_tick"]
    require(all(type(v) is int and v % 15 == 0 for v in (created, start, low_age, high_age, not_before)) and
            0 <= start <= END and 0 <= low_age < high_age <= 32 * DAY and 0 < created <= END and
            0 <= not_before <= END and
            (resolved is None or type(resolved) is int and resolved % 15 == 0 and created < resolved <= END),
            "Invalid residence interval")
    first = max(created + low_age, start + 15, not_before)
    last = min(END if resolved is None else resolved - 15, created + high_age - 15)
    return max(0, (last - first) // 15 + 1)


def child_outcome(seed: dict, parents: dict) -> str:
    if seed["outcome"] != "germinated":
        require(seed["outcome"] in ("pending", "expired"), "Unknown seed outcome")
        return seed["outcome"]
    record = parents[seed["child"]]
    p = record["plant"]
    if p["birth_tick"] + DAY > END:
        return "young_alive" if p["death_tick"] is None else "young_dead"
    if not capacity.funnel.survived_day(p, END):
        return "early_death"
    return "durable" if any(capacity.funnel.survived_day(parents[i]["plant"], END)
                            for i in record["children"]) else "day_only"


def seed_details(ledger: dict, closing_masks: list[dict]) -> list[dict]:
    require(len(closing_masks) == len(ledger["seeds"]), "Missing closing seed masks")
    parents = {p["plant"]["id"]: p for p in ledger["parents"]}
    result = []
    for index, (seed, closing) in enumerate(zip(ledger["seeds"], closing_masks)):
        parent = parents[seed["parent"]]["plant"]
        founder = parents[parent["family"]]["plant"]
        require(founder["parent"] == 0 and founder["species"] == seed["species"], "Changed family attribution")
        windows = {}
        for window, start in WINDOWS.items():
            masks = seed["post_blockers"] if window == "whole" else closing
            mature = samples(seed, start, 15 * capacity.funnel.DORMANCY)
            require(sum(masks.values()) == mature and all(
                k == str(int(k)) and 0 <= int(k) < 128 and not int(k) & 1 and
                type(v) is int and 0 < v <= seed["post_blockers"].get(k, 0)
                for k, v in masks.items()), "Changed mature/closing blocker samples")
            windows[window] = {"samples": samples(seed, start), "mature_samples": mature,
                "post_blockers": masks,
                "age_samples": {name: samples(seed, start, a * DAY, b * DAY) for name, (a, b) in AGES.items()},
                "posthumous_samples": 0 if parent["death_tick"] is None else
                    samples(seed, start, not_before=parent["death_tick"])}
            require(sum(windows[window]["age_samples"].values()) == windows[window]["samples"],
                    "Incomplete residence age bins")
        result.append({"index": index, "parent": seed["parent"], "family": parent["family"],
            "species": seed["species"], "column": seed["column"], "outcome": child_outcome(seed, parents),
            "seed_outcome": seed["outcome"], "created_tick": seed["created_tick"],
            "resolved_tick": seed["resolved_tick"], "child": seed["child"],
            "wait_ticks": (END if seed["resolved_tick"] is None else seed["resolved_tick"]) - seed["created_tick"],
            "posthumous_germination": seed["outcome"] == "germinated" and parent["death_tick"] is not None and
                seed["resolved_tick"] >= parent["death_tick"], "windows": windows})
    return result


def sum_maps(values) -> dict:
    result = Counter()
    for value in values:
        result.update(value)
    return dict(sorted(result.items()))


def inventory(seeds: list[dict]) -> dict:
    counts = Counter(dict.fromkeys(OUTCOMES, 0))
    counts.update(s["outcome"] for s in seeds)
    windows = {}
    for window in WINDOWS:
        masks = sum_maps(s["windows"][window]["post_blockers"] for s in seeds)
        windows[window] = {"samples": sum(s["windows"][window]["samples"] for s in seeds),
            "mature_samples": sum(masks.values()), "post_blockers": masks,
            "blocker_overlap": {name: sum(v for k, v in masks.items() if int(k) & (1 << i))
                                for i, name in enumerate(BLOCKERS)},
            "post_unblocked": masks.get("0", 0),
            "outcome_samples": {name: sum(s["windows"][window]["samples"] for s in seeds if s["outcome"] == name)
                                for name in OUTCOMES},
            "age_samples": {age: sum(s["windows"][window]["age_samples"][age] for s in seeds) for age in AGES},
            "posthumous_samples": sum(s["windows"][window]["posthumous_samples"] for s in seeds)}
    waits = {name: dict(sorted(Counter(str(s["wait_ticks"]) for s in seeds if s["seed_outcome"] == name).items(),
                              key=lambda item: int(item[0]))) for name in ("germinated", "pending", "expired")}
    return {"seeds": len(seeds), "outcomes": dict(counts), "windows": windows, "wait_histograms": waits,
        "target_columns": dict(sorted(Counter(str(s["column"]) for s in seeds).items(), key=lambda item: int(item[0]))),
        "posthumous_germinations": sum(s["posthumous_germination"] for s in seeds)}


def families(seeds: list[dict], ledger: dict) -> list[dict]:
    return [{"founder": p["plant"], "inventory": inventory([s for s in seeds if s["family"] == p["plant"]["id"]])}
            for p in ledger["parents"] if p["plant"]["parent"] == 0]


def window_limits(incumbent: dict, split: int) -> dict:
    end = min(incumbent[a + "_death"] or END for a in capacity.CAPACITIES)
    require(0 < split <= end <= END and split % 15 == end % 15 == 0, "Invalid shared follow-up")
    return {"since_split": (split, end), "last_day": (max(split, end - DAY + 15), end)}


def empty_budget(start: int, end: int) -> dict:
    return {"start": start, "end": end, "steps": 0, "initial": None, "final": None,
            "last_alive": None, "totals": dict.fromkeys(FLOW_KEYS, 0), "terminal": None,
            "first_shortage": {"energy": None, "water": None}, "seed_ticks": []}


def state(plant: dict, tick: int) -> dict:
    return {"tick": tick, **{k: plant[k] for k in STATE_KEYS}}


def add_budget(record: dict, previous: dict | None, plant: dict, world: dict, receipt: dict | None) -> None:
    tick = world["tick"]
    require(tick == record["start"] + 15 * record["steps"] and tick <= record["end"] and
            (previous is None or not previous["dead"]), "Missing/reordered live accounting step")
    if record["steps"] == 0:
        record["initial"] = state(previous, tick - 15) if previous else {
            "tick": tick - 15, "virtual_newborn_stores": True, "id": plant["id"], "energy": 64, "water": 24}
    values = dict.fromkeys(FLOW_KEYS, 0)
    if plant["dead"]:
        require(previous is not None and receipt is not None and tick == record["end"], "Missing terminal accounting")
        reconcile_death(previous, plant, receipt, tick)
        for name in ("energy", "water"):
            for source, dest in (("income", "income"), ("overflow", "overflow"),
                                 ("upkeep_paid", "upkeep"), ("discarded", "discarded")):
                values[name + "_" + dest] = receipt[name][source]
        record["terminal"] = {"receipt": receipt, "climate": world["climate"]}
        record["last_alive"] = state(previous, tick - 15)
    else:
        require(receipt is None, "Receipt on live accounting step")
        values.update(budget(previous, plant, tick))
        record["last_alive"] = state(plant, tick)
    for name, bit in (("energy", 2), ("water", 4)):
        if plant["flags"] & bit and record["first_shortage"][name] is None:
            record["first_shortage"][name] = tick
    if values["energy_seeds"]:
        record["seed_ticks"].append(tick)
    for key in FLOW_KEYS:
        record["totals"][key] += values[key]
    record["steps"] += 1
    record["final"] = {**state(plant, tick), "climate": world["climate"], "sun_strength": world["sun_strength"]}


def validate_budget(record: dict, parent: dict, seeds: list[dict], terminal: dict | None) -> None:
    start, end = record["start"], record["end"]
    require(0 < start <= end <= END and start % 15 == end % 15 == 0 and
            record["steps"] == (end - start) // 15 + 1 and record["initial"]["tick"] == start - 15 and
            record["final"]["tick"] == end and record["initial"]["id"] == parent["id"] == record["final"]["id"] and
            record["final"]["dead"] == (parent["death_tick"] == end) and
            record["terminal"] == terminal and set(record["totals"]) == set(FLOW_KEYS) and
            all(type(v) is int and v >= 0 for v in record["totals"].values()), "Changed matched accounting window")
    require(record["seed_ticks"] == [s["created_tick"] for s in seeds if s["parent"] == parent["id"] and
            start <= s["created_tick"] <= end], "Seed debit/creation disagreement")
    for name, cost in (("energy", 48), ("water", 24)):
        v = record["totals"]
        expected = record["initial"][name] + v[name + "_income"] - sum(
            v[name + "_" + suffix] for suffix in ("overflow", "upkeep", "growth", "seeds", "discarded"))
        require(expected == record["final"][name] and v[name + "_seeds"] == cost * len(record["seed_ticks"]) and
                v[name + "_discarded"] == (0 if terminal is None else terminal["receipt"][name]["discarded"]),
                "Matched resource conservation/debit failure")
        first = record["first_shortage"][name]
        require(first is None or type(first) is int and start <= first <= end and first % 15 == 0,
                "Invalid shortage onset")
    require(record["last_alive"]["id"] == parent["id"] and not record["last_alive"]["dead"] and
            record["last_alive"]["tick"] == end - (15 if terminal else 0), "Changed last living state")
    if terminal:
        reconcile_death(record["last_alive"], record["final"], terminal["receipt"], end)


def analyze_arm(bundle: Path, old: dict, arm: str) -> dict:
    source = old["arms"][arm]
    path = capacity.population.path(bundle, old["case"], arm)
    require(capacity.digest(path) == old["traces"][arm], "Changed primary capacity trace")
    seeds = source["ledger"]["seeds"]
    lookup = {(s["parent"], s["created_tick"]): i for i, s in enumerate(seeds)}
    closing = [Counter() for s in seeds]
    audit = capacity.population.Audit(True, source["capacity"])
    ledger = capacity.funnel.SeedLedger(source["capacity"])
    budgets = {p["id"]: {w: empty_budget(*limits) for w, limits in window_limits(p, old["first_difference"]["tick"]).items()}
               for p in old["incumbents"]}
    previous = {}
    for world, bids, deaths in capacity.population.reserve.groups(path):
        audit.accept(world, bids, deaths)
        ledger.accept(world)
        tick = world["tick"]
        current, receipts = {p["id"]: p for p in world["plants"]}, {d["id"]: d for d in deaths}
        if tick > WINDOWS["closing"]:
            for s in world["seeds"]:
                if s["age"] >= capacity.funnel.DORMANCY:
                    key = capacity.funnel.seed_key(s, tick)
                    require(key in lookup, "Unknown seed in closing records")
                    closing[lookup[key]][str(s["blockers"])] += 1
        for ident, windows in budgets.items():
            for record in windows.values():
                if record["start"] <= tick <= record["end"]:
                    require(ident in current, "Missing matched incumbent")
                    add_budget(record, previous.get(ident), current[ident], world, receipts.get(ident))
        previous = current
    require(audit.result({}) == source["outcome"] and ledger.result() == source["ledger"] and
            capacity.digest(path) == old["traces"][arm], "Changed trajectory/budget/seed reconstruction")
    details = seed_details(source["ledger"], [dict(c) for c in closing])
    return {"seeds": details, "families": families(details, source["ledger"]),
            "budgets": [{"id": ident, "windows": windows} for ident, windows in budgets.items()]}


def validate_case(result: dict, old: dict) -> None:
    require(result["case"] == old["case"] and result["traces"] == old["traces"], "Changed case/trace identity")
    for arm in capacity.CAPACITIES:
        source, r = old["arms"][arm], result["arms"][arm]
        masks = [s["windows"]["closing"]["post_blockers"] for s in r["seeds"]]
        require(r["seeds"] == seed_details(source["ledger"], masks) and
                r["families"] == families(r["seeds"], source["ledger"]), "Changed seed/family evidence")
        for window in WINDOWS:
            require(sum(s["windows"][window]["samples"] for s in r["seeds"]) ==
                    source["occupancy"][window]["seed_samples"], "Residence/occupancy disagreement")
        require([b["id"] for b in r["budgets"]] == [p["id"] for p in old["incumbents"]], "Missing/duplicate incumbent")
        parents = {p["id"]: p for p in source["outcome"]["history"]["plants"]}
        terminals = {t["receipt"]["id"]: t for t in source["outcome"]["terminals"]}
        for row, incumbent in zip(r["budgets"], old["incumbents"]):
            expected = window_limits(incumbent, old["first_difference"]["tick"])
            require(set(row["windows"]) == set(expected), "Changed resource window selection")
            for w, limits in expected.items():
                record = row["windows"][w]
                require((record["start"], record["end"]) == limits, "Changed matched cutoff")
                parent = parents[row["id"]]
                terminal = terminals[row["id"]] if parent["death_tick"] == limits[1] else None
                validate_budget(record, parent, source["ledger"]["seeds"], terminal)
    for a, b in zip(result["arms"]["eight"]["budgets"], result["arms"]["sixteen"]["budgets"]):
        require(a["windows"]["since_split"]["initial"] == b["windows"]["since_split"]["initial"],
                "Changed shared initial stores")


def resource_summary(pairs: list[tuple]) -> dict:
    result = {"plants": len(pairs), "windows": {}}
    for window in ("since_split", "last_day"):
        a = [p[0]["windows"][window]["totals"] for p in pairs]
        b = [p[1]["windows"][window]["totals"] for p in pairs]
        changes = {}
        for resource in ("energy", "water"):
            for stage in ("seeds", "growth", "upkeep", "usable_income"):
                def value(v):
                    return (v[resource + "_income"] - v[resource + "_overflow"] if stage == "usable_income"
                            else v[resource + "_" + stage])
                deltas = [value(y) - value(x) for x, y in zip(a, b)]
                changes[resource + "_" + stage] = {"more": sum(d > 0 for d in deltas),
                    "same": sum(d == 0 for d in deltas), "less": sum(d < 0 for d in deltas)}
        result["windows"][window] = {"eight": {k: sum(v[k] for v in a) for k in FLOW_KEYS},
            "sixteen": {k: sum(v[k] for v in b) for k in FLOW_KEYS}, "changes": changes,
            "sixteen_no_seed_spending": sum(v["energy_seeds"] == 0 for v in b)}
    return result


def aggregate(cases: list[dict], originals: list[dict]) -> dict:
    groups = {}
    for arm in capacity.CAPACITIES:
        seeds = [s for c in cases for s in c["arms"][arm]["seeds"]]
        groups[arm] = {"inventory": inventory(seeds), "species": {
            s: inventory([r for r in seeds if r["species"] == s]) for s in capacity.funnel.SPECIES}, "concentration": {}}
        for window in WINDOWS:
            totals = [sum(f["inventory"]["windows"][window]["samples"] for f in c["arms"][arm]["families"]) for c in cases]
            tops = [max((f["inventory"]["windows"][window]["samples"] for f in c["arms"][arm]["families"]), default=0)
                    for c in cases]
            groups[arm]["concentration"][window] = {"worlds": len(cases), "occupied_samples": sum(totals),
                "top_family_samples": sum(tops), "at_least_75_percent": sum(t > 0 and 4 * a >= 3 * t for a, t in zip(tops, totals)),
                "single_family": sum(t > 0 and a == t for a, t in zip(tops, totals))}
    pairs = [(a, b, p) for c, old in zip(cases, originals)
             for a, b, p in zip(c["arms"]["eight"]["budgets"], c["arms"]["sixteen"]["budgets"], old["incumbents"])]
    return {"groups": groups, "incumbents": {name: resource_summary([(a, b) for a, b, p in pairs if
        name == "all" or (p["earlier"] if name == "earlier" else p["later"] if name == "later"
                          else not p["earlier"] and not p["later"])]) for name in ("all", "earlier", "later", "unchanged")}}


def analysis(cases: list[dict], original: dict) -> dict:
    require([r["case"] for r in cases] == [r["case"] for r in original["cases"]] == capacity.confirmation.specification(),
            "Incomplete/duplicate/reordered diagnosis panel")
    result = aggregate(cases, original["cases"])
    result["partitions"] = {field: {value: aggregate([c for c in cases if c["case"][field] == value],
        [c for c in original["cases"] if c["case"][field] == value]) for value in values}
        for field, values in (("seed", capacity.confirmation.SEEDS), ("scenario", capacity.population.LAYOUTS),
                              ("policy", capacity.population.POLICIES))}
    return result


def validate_report(report: dict, original: dict) -> None:
    require(report["protocol"] == RULE and report["input_sha256"] == INPUT_SHA and report["native_runs"] == 0 and
            report["analysis"] == analysis(report["cases"], original), "Changed diagnostic identity/summary")
    for result, old in zip(report["cases"], original["cases"]):
        validate_case(result, old)


def compact(report: dict) -> dict:
    return {k: v for k, v in report.items() if k != "cases"} | {"cases": [{"case": c["case"], "traces": c["traces"],
        "details_sha256": hashlib.sha256(json.dumps(c, sort_keys=True).encode()).hexdigest(),
        "arms": {a: {"inventory": inventory(v["seeds"]), "families": v["families"]} for a, v in c["arms"].items()}}
        for c in report["cases"]]}


def frozen(original: dict) -> dict:
    # CMake registration may change; no simulation or existing analyzer dependency may.
    for name, sha in original["frozen"]["sources"].items():
        if name != "sim/CMakeLists.txt":
            require(capacity.digest(ROOT / name) == sha, "Changed native/analysis dependency: " + name)
    names = {*original["frozen"]["sources"], PROTOCOL, "sim/garden_season_seed_bank_diagnosis.py",
             "sim/test_garden_season_seed_bank_diagnosis.py", "sim/garden_resources.py", "sim/garden_deaths.py"}
    return {name: capacity.digest(ROOT / name) for name in sorted(names)}


def run_case(item) -> dict:
    bundle, old = item
    result = {"case": old["case"], "traces": old["traces"],
              "arms": {a: analyze_arm(bundle, old, a) for a in capacity.CAPACITIES}}
    validate_case(result, old)
    print("Audited bank ownership/resources " + capacity.identity(old["case"]), flush=True)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("analyze", "verify"))
    parser.add_argument("--bundle", type=Path, default=Path("artifacts/garden-seasonal-seed-bank-capacity"))
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--jobs", type=int, default=4)
    args = parser.parse_args()
    if not 1 <= args.jobs <= 4:
        parser.error("Require 1..4 independent offline workers")
    original = load_input()
    provenance = frozen(original)
    if args.command == "analyze":
        args.out.mkdir(parents=True, exist_ok=False)
    with ProcessPoolExecutor(max_workers=args.jobs) as pool:
        cases = list(pool.map(run_case, ((args.bundle, c) for c in original["cases"])))
    require(frozen(original) == provenance, "Sources changed during diagnosis")
    report = {"protocol": RULE, "input_sha256": INPUT_SHA, "native_runs": 0,
              "sources": provenance, "cases": cases, "analysis": analysis(cases, original)}
    validate_report(report, original)
    if args.command == "analyze":
        (args.out / "results.json").write_text(json.dumps(report, indent=2) + "\n")
        (args.out / "summary.json").write_text(json.dumps(compact(report), indent=2) + "\n")
    else:
        require(report == json.loads((args.out / "results.json").read_text()) and
                compact(report) == json.loads((args.out / "summary.json").read_text()), "Nonrepeatable offline diagnosis")
    print("All 32 pairs verified; zero new native runs.", flush=True)


if __name__ == "__main__":
    main()
