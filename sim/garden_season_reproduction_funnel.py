#!/usr/bin/env python3
"""Read-only seed/parent ledgers and age-matched funnels for the fresh reserve panel."""

from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
import gzip
import hashlib
import json
from pathlib import Path

import garden_season_seedling_confirmation as confirmation
import garden_season_seedling_population as population
from garden_season_recruitment import digest, identity
from garden_seasons import DAY_TICKS as DAY, require

ROOT, END = confirmation.ROOT, confirmation.END
RULE = "seasonal-reproduction-funnel-v1"
INPUT_SHA = "49baf29c3e2976bfdfb0bbbef19240ceadbfc3747d9354dfe6afe3a89fc4f1e5"
PROTOCOL = "benchmarks/garden-seasons/reproduction-funnel-protocol.md"
LIFETIME, DORMANCY = 8192, 8
AGES = (1, 2, 4, 8, 16)
STAGES = ("no_seed", "seeds_pending", "seeds_expired", "children_pending", "children_failed", "durable")
SPECIES = ("flower", "shrub", "ground-cover")
PLANT_IDENTITY = ("id", "parent", "species", "generation")
SEED_IDENTITY = ("parent", "generation", "column", "species")


def load_input() -> dict:
    folder = ROOT / "benchmarks/garden-seasons"
    raw = gzip.decompress((folder / "seedling-confirmation-histories.json.gz").read_bytes())
    require(hashlib.sha256(raw).hexdigest() == INPUT_SHA, "Changed fresh confirmation archive")
    result = json.loads(raw)
    confirmation.validate_report(result, confirmation.inputs())
    require(population.compact(result) == json.loads((folder / "seedling-confirmation-summary.json").read_text()),
            "Changed fresh confirmation summary")
    return result


def seed_key(seed: dict, tick: int) -> tuple[int, int]:
    require(type(seed["age"]) is int and 0 <= seed["age"] < LIFETIME and
            type(seed["column"]) is int and 0 <= seed["column"] < 28 and
            type(seed["blockers"]) is int and 0 <= seed["blockers"] < 128 and
            bool(seed["blockers"] & 1) == (seed["age"] < DORMANCY), "Invalid seed age/column/blockers")
    return seed["parent"], tick - 15 * seed["age"]


class SeedLedger:
    def __init__(self, seed_capacity: int = 8):
        require(type(seed_capacity) is int and seed_capacity in (8, 16), "Unsupported seed capacity")
        self.seed_capacity = seed_capacity
        self.tick, self.worlds = -15, 0
        self.previous, self.plants = {}, {}
        self.bank, self.seeds, self.lookup = [], [], {}
        self.expired, self.germinated = 0, 0

    def accept(self, world: dict) -> None:
        tick = world["tick"]
        require(tick == self.tick + 15 and world["seed_lifetime_ecology_ticks"] == LIFETIME and
                world.get("seed_capacity", 8) == self.seed_capacity and
                len(world["seeds"]) <= self.seed_capacity and len(world["plants"]) <= 8 and world["nodes"] <= 256,
                "Missing step or changed ecology")
        current = {p["id"]: p for p in world["plants"]}
        require(len(current) == len(world["plants"]), "Duplicate plant")
        children = []
        for plant in world["plants"]:
            ident, parent = plant["id"], plant["parent"]
            if ident not in self.plants:
                require(not plant["dead"] and bool(parent) == (tick != 0) and
                        (not parent or parent in self.plants), "Invalid birth/parent")
                ancestor = self.plants[parent]["plant"] if parent else None
                require(plant["species"] in SPECIES and
                        (plant["generation"] == 0 if ancestor is None else
                         plant["generation"] == ancestor["generation"] + 1 and
                         plant["species"] == ancestor["species"]), "Changed plant ancestry")
                self.plants[ident] = {"plant": {**{k: plant[k] for k in PLANT_IDENTITY},
                    "family": ancestor["family"] if ancestor else ident, "birth_tick": tick, "death_tick": None},
                    "column": plant["column"], "seed_indices": [], "children": [],
                    "first_flower_tick": None, "max_flowers": 0}
                if parent:
                    children.append(plant)
                    self.plants[parent]["children"].append(ident)
            else:
                require(ident in self.previous and all(plant[k] == self.plants[ident]["plant"][k]
                        for k in PLANT_IDENTITY) and plant["column"] == self.plants[ident]["column"],
                        "Reused lineage or changed plant identity")
                old = self.previous[ident]
                require(not old["dead"] or plant["dead"], "Dead plant revived")
                if plant["dead"] and not old["dead"]:
                    self.plants[ident]["plant"]["death_tick"] = tick
            record = self.plants[ident]
            if not plant["dead"]:
                record["max_flowers"] = max(record["max_flowers"], plant["flowers"])
                if plant["flowers"] and record["first_flower_tick"] is None:
                    record["first_flower_tick"] = tick
        require(all(p["dead"] for ident, p in self.previous.items() if ident not in current),
                "Living parent vanished")

        keys = [seed_key(s, tick) for s in world["seeds"]]
        require(len(set(keys)) == len(keys), "Duplicate seed creation identity")
        require([k for k in keys if k in self.lookup] == [k for k in self.bank if k in keys],
                "Changed surviving seed order or reappearing seed")
        child_index = 0
        for key in self.bank:
            record = self.seeds[self.lookup[key]]
            age = (tick - record["created_tick"]) // 15
            if key in keys:
                require(age < LIFETIME, "Expired seed retained")
                continue
            record["resolved_tick"] = tick
            if age == LIFETIME:
                record["outcome"] = "expired"
                self.expired += 1
            else:
                require(DORMANCY <= age < LIFETIME and child_index < len(children),
                        "Missing child or impossible seed disappearance")
                child = children[child_index]
                require(all(record[k] == child[k] for k in SEED_IDENTITY), "Changed germination order/ancestry")
                record["outcome"], record["child"] = "germinated", child["id"]
                self.germinated += 1
                child_index += 1
        require(child_index == len(children), "Unmatched newborn child")
        created_parents = []
        for key, seed in zip(keys, world["seeds"]):
            parent = seed["parent"]
            require(parent in self.plants, "Seed with unknown parent")
            ancestor = self.plants[parent]["plant"]
            require(seed["generation"] == ancestor["generation"] + 1 and
                    seed["species"] == ancestor["species"], "Changed seed ancestry")
            if key not in self.lookup:
                require(seed["age"] == 0 and tick > 0 and tick % 60 == 0 and
                        parent in current and not current[parent]["dead"] and
                        current[parent]["reproduction_cooldown"] == 16 and current[parent]["flowers"] > 0,
                        "New seed not observable at production")
                self.lookup[key] = len(self.seeds)
                self.plants[parent]["seed_indices"].append(len(self.seeds))
                self.seeds.append({**{k: seed[k] for k in SEED_IDENTITY}, "created_tick": tick,
                    "resolved_tick": None, "outcome": "pending", "child": None,
                    "mature_post_samples": 0, "post_blockers": {}})
                created_parents.append(parent)
            record = self.seeds[self.lookup[key]]
            require(all(record[k] == seed[k] for k in SEED_IDENTITY) and record["outcome"] == "pending",
                    "Changed/revived seed")
            if seed["age"] >= DORMANCY:
                mask = str(seed["blockers"])
                record["post_blockers"][mask] = record["post_blockers"].get(mask, 0) + 1
                record["mature_post_samples"] += 1
        require(len(set(created_parents)) == len(created_parents) and
                created_parents == [p["id"] for p in world["plants"] if p["id"] in created_parents],
                "Multiple productions per parent or changed production order")
        require(keys == [k for k in self.bank if k in keys] +
                [(parent, tick) for parent in created_parents], "Seed bank append/compaction mismatch")
        require(world["seeds_created"] == len(self.seeds) and world["seeds_expired"] == self.expired and
                world["births"] == self.germinated and len(keys) == len(self.seeds) - self.expired - self.germinated,
                "Seed creation/expiry/germination counters disagree")
        require(world["deaths"] == sum(p["plant"]["death_tick"] is not None for p in self.plants.values()),
                "Death history mismatch")
        self.bank, self.previous, self.tick = keys, current, tick
        self.worlds += 1

    def result(self, end: int = END) -> dict:
        require(self.tick == end and self.worlds == end // 15 + 1, "Incomplete seed ledger")
        return {"worlds": self.worlds, "parents": list(self.plants.values()), "seeds": self.seeds}


def survived_day(plant: dict, cutoff: int) -> bool:
    boundary = plant["birth_tick"] + DAY
    return boundary <= cutoff and (plant["death_tick"] is None or plant["death_tick"] > boundary)


def events(record: dict, ledger: dict, cutoff: int) -> tuple[dict, list, list]:
    plants = {p["plant"]["id"]: p["plant"] for p in ledger["parents"]}
    seeds = [ledger["seeds"][i] for i in record["seed_indices"] if ledger["seeds"][i]["created_tick"] <= cutoff]
    children = [plants[i] for i in record["children"] if plants[i]["birth_tick"] <= cutoff]
    counts = Counter(seed_created=len(seeds), children=len(children))
    for seed in seeds:
        outcome = seed["outcome"] if seed["resolved_tick"] is not None and seed["resolved_tick"] <= cutoff else "pending"
        counts["seed_" + outcome] += 1
    for child in children:
        if child["birth_tick"] + DAY > cutoff:
            counts["child_young_dead" if child["death_tick"] is not None and child["death_tick"] <= cutoff
                   else "child_young_alive"] += 1
        else:
            counts["child_eligible"] += 1
            counts["child_day_survivor" if survived_day(child, cutoff) else "child_early_death"] += 1
    return counts, seeds, children


def stage(record: dict, ledger: dict, cutoff: int) -> tuple[str, dict]:
    counts, seeds, children = events(record, ledger, cutoff)
    if counts["child_day_survivor"]:
        return "durable", counts
    if children:
        return ("children_pending" if counts["child_young_alive"] else "children_failed"), counts
    if seeds:
        return ("seeds_pending" if counts["seed_pending"] else "seeds_expired"), counts
    return "no_seed", counts


COUNT_KEYS = ("parents", "followup_censored_alive", "followup_censored_dead", "alive", "dead",
              "no_seed_no_observed_flower", "no_seed_observed_flower", "seed_created", "seed_pending",
              "seed_expired", "seed_germinated", "children", "child_eligible", "child_day_survivor",
              "child_early_death", "child_young_alive", "child_young_dead") + tuple(
                  prefix + name for prefix in ("stage_", "alive_", "dead_") for name in STAGES)


def census(records: list[dict], ledger: dict, age: int | None = None) -> dict:
    counts = Counter(dict.fromkeys(COUNT_KEYS, 0))
    for record in records:
        plant = record["plant"]
        cutoff = END if age is None else plant["birth_tick"] + age * DAY
        if cutoff > END:
            counts["followup_censored_alive" if plant["death_tick"] is None else "followup_censored_dead"] += 1
            continue
        counts["parents"] += 1
        alive = plant["death_tick"] is None or plant["death_tick"] > cutoff
        counts["alive" if alive else "dead"] += 1
        name, outcomes = stage(record, ledger, cutoff)
        counts["stage_" + name] += 1
        counts[("alive_" if alive else "dead_") + name] += 1
        counts.update(outcomes)
        if name == "no_seed":
            flower = record["first_flower_tick"] is not None and record["first_flower_tick"] <= cutoff
            counts["no_seed_observed_flower" if flower else "no_seed_no_observed_flower"] += 1
    require(set(counts) == set(COUNT_KEYS), "Unknown funnel metric")
    return dict(counts)


def cohorts(ledger: dict, species: str | None = None) -> dict:
    result = {}
    for name, start in (("whole", 0), ("closing", 112 * DAY + 1)):
        selected = [r for r in ledger["parents"] if r["plant"]["parent"] and
                    r["plant"]["birth_tick"] >= start and survived_day(r["plant"], END) and
                    (species is None or r["plant"]["species"] == species)]
        result[name] = {"endpoint": census(selected, ledger),
                        "ages": {str(age): census(selected, ledger, age) for age in AGES}}
    return result


def validate_ledger(ledger: dict, original: dict) -> None:
    plants = {r["plant"]["id"]: r for r in ledger["parents"]}
    require([r["plant"] for r in ledger["parents"]] == original["history"]["plants"] and
            ledger["worlds"] == END // 15 + 1, "Changed parent history")
    require(len(ledger["seeds"]) == original["history"]["daily"][-1]["seeds_created"], "Changed seed total")
    seen, children, owners = set(), set(), {ident: [] for ident in plants}
    for index, seed in enumerate(ledger["seeds"]):
        parent = plants[seed["parent"]]["plant"]
        key = seed["parent"], seed["created_tick"]
        require(key not in seen and parent["birth_tick"] <= seed["created_tick"] <= END and
                seed["created_tick"] > 0 and seed["created_tick"] % 60 == 0 and
                (parent["death_tick"] is None or seed["created_tick"] < parent["death_tick"]) and
                seed["generation"] == parent["generation"] + 1 and seed["species"] == parent["species"],
                "Invalid portable seed creation")
        seen.add(key)
        owners[parent["id"]].append(index)
        require(sum(seed["post_blockers"].values()) == seed["mature_post_samples"] and
                all(0 <= int(mask) < 128 and int(mask) % 2 == 0 and n > 0
                    for mask, n in seed["post_blockers"].items()), "Changed post-step blocker samples")
        resolved = seed["resolved_tick"]
        last_age = (END - seed["created_tick"]) // 15 if resolved is None else (resolved - seed["created_tick"]) // 15 - 1
        require(seed["mature_post_samples"] == max(0, last_age - DORMANCY + 1),
                "Incomplete mature post-step samples")
        if seed["outcome"] == "pending":
            require(resolved is None and seed["child"] is None and
                    seed["created_tick"] + 15 * LIFETIME > END, "Invalid pending seed")
        elif seed["outcome"] == "expired":
            require(resolved == seed["created_tick"] + 15 * LIFETIME <= END and seed["child"] is None,
                    "Changed expiry boundary")
        else:
            require(seed["outcome"] == "germinated" and seed["child"] in plants and
                    seed["child"] not in children and resolved is not None and
                    seed["created_tick"] + 15 * DORMANCY <= resolved < seed["created_tick"] + 15 * LIFETIME,
                    "Invalid child/seed germination boundary")
            child = plants[seed["child"]]
            require(child["plant"]["birth_tick"] == resolved and
                    all(seed[k] == child["plant"][k] for k in ("parent", "generation", "species")) and
                    seed["column"] == child["column"], "Child/seed attribution mismatch")
            children.add(seed["child"])
    require(children == {p["plant"]["id"] for p in ledger["parents"] if p["plant"]["parent"]},
            "Missing/duplicate child attribution")
    for ident, record in plants.items():
        require(record["seed_indices"] == owners[ident] and record["children"] ==
                [r["plant"]["id"] for r in ledger["parents"] if r["plant"]["parent"] == ident],
                "Changed parent event index")
        plant = record["plant"]
        first = record["first_flower_tick"]
        require((first is None) == (record["max_flowers"] == 0) and
                (first is None or plant["birth_tick"] <= first <= END and first % 15 == 0 and
                 (plant["death_tick"] is None or first < plant["death_tick"])) and
                (not record["seed_indices"] or first is not None and
                 first <= min(ledger["seeds"][i]["created_tick"] for i in record["seed_indices"])),
                "Changed observed flower history")
    counts = cohorts(ledger)
    for window in counts:
        a, b = counts[window]["endpoint"], original["outcomes"]["cohorts"][window]["totals"]
        require(a["parents"] == b["day_survivors"] and a["stage_durable"] == b["durable_parents"] and
                sum(a["stage_" + s] for s in STAGES[:3]) == b["no_child"] and
                a["stage_children_pending"] + a["stage_children_failed"] == b["child_without_day_survivor"],
                "Changed established parent cohorts")


def analyze_trace(item) -> dict:
    bundle, case, arm = item
    path = population.path(bundle, case["case"], arm)
    require(digest(path) == case["traces"][arm], "Changed primary trace")
    ledger = SeedLedger()
    daily = case["arms"][arm]["history"]["daily"]
    for world, _, _ in population.reserve.groups(path):
        require(world.get("seedling_reserve") == (population.METADATA if arm == "guard" else None),
                "Changed reserve selector")
        if world["tick"] % DAY == 0:
            require(world["hash"] == daily[world["tick"] // DAY]["hash"], "Changed daily state")
        ledger.accept(world)
    result = ledger.result()
    validate_ledger(result, case["arms"][arm])
    require(digest(path) == case["traces"][arm], "Trace changed during audit")
    print("Audited " + identity(case["case"]) + " / " + arm, flush=True)
    return {"case": case["case"], "arm": arm, "trace_sha256": case["traces"][arm], "ledger": result}


def aggregate(rows: list[dict], species: str | None = None) -> dict:
    groups = [cohorts(row["ledger"], species) for row in rows]
    def total(window, age):
        values = [g[window]["endpoint"] if age is None else g[window]["ages"][age] for g in groups]
        return {key: sum(c[key] for c in values) for key in COUNT_KEYS}
    return {window: {"endpoint": total(window, None), "ages": {str(a): total(window, str(a)) for a in AGES}}
            for window in ("whole", "closing")}


def seed_inventory(rows: list[dict]) -> dict:
    owners = {category: Counter(dict.fromkeys(("created", "pending", "expired", "germinated"), 0))
              for category in ("founder", "established_descendant", "other_descendant")}
    masks, posthumous = Counter(), 0
    for row in rows:
        ledger = row["ledger"]
        parents = {p["plant"]["id"]: p["plant"] for p in ledger["parents"]}
        for seed in ledger["seeds"]:
            parent = parents[seed["parent"]]
            kind = "founder" if not parent["parent"] else (
                "established_descendant" if survived_day(parent, END) else "other_descendant")
            owners[kind]["created"] += 1
            owners[kind][seed["outcome"]] += 1
            masks.update(seed["post_blockers"])
            if seed["outcome"] == "germinated" and parent["death_tick"] is not None:
                posthumous += seed["resolved_tick"] >= parent["death_tick"]
    return {"by_parent_cohort": {name: dict(counts) for name, counts in owners.items()},
            "posthumous_germinations": posthumous, "mature_post_samples": sum(masks.values()),
            "post_blockers": dict(sorted(masks.items(), key=lambda item: int(item[0])))}


def analysis(rows: list[dict]) -> dict:
    require([(row["case"], row["arm"]) for row in rows] ==
            [(case, arm) for case in confirmation.specification() for arm in population.ARMS],
            "Incomplete/duplicate/reordered funnel panel")
    return {"groups": {arm: aggregate([r for r in rows if r["arm"] == arm]) for arm in population.ARMS},
            "seed_inventory": {arm: seed_inventory([r for r in rows if r["arm"] == arm])
                               for arm in population.ARMS},
            "partitions": {field: {value: {arm: aggregate([r for r in rows if r["arm"] == arm and
                (field == "species" or r["case"][field] == value)], value if field == "species" else None)
                for arm in population.ARMS} for value in values} for field, values in
                (("seed", confirmation.SEEDS), ("scenario", population.LAYOUTS),
                 ("policy", population.POLICIES), ("species", SPECIES))}}


def compact(report: dict) -> dict:
    return {**{k: v for k, v in report.items() if k != "cases"}, "cases": [
        {**{k: v for k, v in row.items() if k != "ledger"}, "cohorts": cohorts(row["ledger"]),
         "ledger_sha256": hashlib.sha256(json.dumps(row["ledger"], sort_keys=True).encode()).hexdigest()}
        for row in report["cases"]]}


def snapshot() -> dict:
    files = (PROTOCOL, "sim/garden_season_reproduction_funnel.py", "sim/test_garden_season_reproduction_funnel.py",
             "sim/garden_season_seedling_confirmation.py", "sim/garden_season_seedling_population.py",
             "sim/garden_season_seedling_reserve.py", "sim/garden_seasons.py", "sim/garden_season_offspring.py",
             "src/garden_world.c", "src/garden_world.h", "sim/garden_inspect.c", "sim/CMakeLists.txt")
    return {name: digest(ROOT / name) for name in files}


def validate_report(report: dict, original: dict) -> None:
    require(report["protocol"] == RULE and report["input_sha256"] == INPUT_SHA, "Wrong audit identity")
    require(analysis(report["cases"]) == report["analysis"], "Changed funnel analysis")
    for row, (case, arm) in zip(report["cases"], ((c, a) for c in original["cases"] for a in population.ARMS)):
        require(row["case"] == case["case"] and row["arm"] == arm and
                row["trace_sha256"] == case["traces"][arm], "Changed source trace identity")
        validate_ledger(row["ledger"], case["arms"][arm])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("collect", "verify"))
    parser.add_argument("--bundle", type=Path, default=Path("artifacts/garden-seasonal-seedling-confirmation"))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--jobs", type=int, default=4)
    args = parser.parse_args()
    if not 1 <= args.jobs <= 4:
        parser.error("Require 1..4 independent readers")
    original, frozen = load_input(), snapshot()
    for name in ("src/garden_world.c", "src/garden_world.h", "sim/garden_inspect.c"):
        require(frozen[name] == original["frozen"]["sources"][name], "Changed seed lifecycle contract")
    if args.command == "collect":
        args.out.mkdir(parents=True, exist_ok=False)
    with ProcessPoolExecutor(max_workers=args.jobs) as pool:
        rows = list(pool.map(analyze_trace, ((args.bundle, c, a) for c in original["cases"] for a in population.ARMS)))
    require(snapshot() == frozen, "Audit sources changed during analysis")
    report = {"protocol": RULE, "input_sha256": INPUT_SHA, "sources": frozen,
              "cases": rows, "analysis": analysis(rows)}
    validate_report(report, original)
    if args.command == "verify":
        require(report == json.loads((args.out / "results.json").read_text()) and
                compact(report) == json.loads((args.out / "summary.json").read_text()), "Nonrepeatable audit")
        print("Verified identical raw-trace seed ledgers, parent funnels and age landmarks")
    else:
        (args.out / "results.json").write_text(json.dumps(report, indent=2) + "\n")
        (args.out / "summary.json").write_text(json.dumps(compact(report), indent=2) + "\n")
        print("Completed read-only audit of all 64 fresh primary traces")


if __name__ == "__main__":
    main()
