#!/usr/bin/env python3
"""Read-only reproduction eligibility and ordered bank access in three saved runs."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from pathlib import Path

import garden_resources as resources
import garden_renewal_dawn_reserve as parent
from garden_renewal_phase_forecast import sun_strength

experiment, gap, require = parent.experiment, parent.gap, parent.require
RULE = "garden-renewal-reproduction-access-v1"
PROTOCOL = "benchmarks/garden-longevity/renewal-reproduction-access-protocol.md"
BASELINE_SHA = "ee74ce6b80ff164c5f2358fbcc9829832fac6debebc032086e78b2c52a39f06b"
PORTABLE = "benchmarks/garden-longevity/renewal-dawn-reserve-summary.json"
PORTABLE_SHA = "2cbf7bb6b4568bce1f022d8ff28d330e473b3ca46ebd031e2a44688ceadb3163"
ARMS, STOP, LATE, NOON, ID = parent.ARMS, parent.STOP, parent.LATE, parent.NOON, parent.ID
WINDOWS = ("whole", "after_noon", "late")


def windows(tick):
    return [w for w, include in (("whole", tick > 0), ("after_noon", tick >= NOON),
                                 ("late", tick > LATE)) if include]


def thresholds(plant):
    """The frozen, capped cost-plus-retained-resource gate; not a forecast."""
    nodes, roots, trait = plant["nodes"], plant["roots"], plant["genome"][6]
    require(0 < nodes <= 512 and 0 <= roots <= nodes and -2 <= trait <= 2, "invalid body/trait")
    energy_upkeep, water_upkeep = (nodes+7)//8, (nodes-roots+7)//8
    periods = 40+trait*4
    energy = 48+min(max(96+trait*16, energy_upkeep*periods), 256-energy_upkeep-48)
    water = 24+min(max(32+trait*4, water_upkeep*periods), 512-water_upkeep-24)
    return {"energy": energy, "water": water, "energy_upkeep": energy_upkeep, "water_upkeep": water_upkeep}


def bank_step(previous, row):
    """Undo only verified append operations, not an inferred germination order."""
    require(row["tick"] == previous["tick"]+15, "missing/reordered ecology step")
    phase = (64+row["tick"]//15)%256
    require(row["sun_phase"] == phase and row["sun_strength"] == sun_strength(phase), "wrong sun state")
    bought = row["seeds_created"]-previous["seeds_created"]
    expired = row["seeds_expired"]-previous["seeds_expired"]
    germinated = row["births"]-previous["births"]
    require(all(type(v) is int and v >= 0 for v in (bought, expired, germinated)), "bad seed counter delta")
    start = len(previous["seeds"])-expired-germinated
    require(0 <= start <= len(row["seeds"]) <= 8 and start+bought == len(row["seeds"]),
            "seed removals/appends do not balance")
    ids = [p["id"] for p in row["plants"]]
    require(len(ids) == len(set(ids)) <= 8, "duplicate/overflow plant inventory")
    buyers = [p["id"] for p in row["plants"] if not p["dead"] and p["reproduction_cooldown"] == 16]
    additions = row["seeds"][-bought:] if bought else []
    require(len(buyers) == bought and [s["parent"] for s in additions] == buyers,
            "seed append order differs from paid parent order")
    events = [e for e in row["dark_guard"]["events"] if e["kind"] == "seeds"]
    require(all(e["id"] in ids for e in events) and
            [ids.index(e["id"]) for e in events] == sorted({ids.index(e["id"]) for e in events}),
            "duplicate/out-of-order seed expense")
    return {"tick": row["tick"], "phase": phase, "before_checks": len(previous["seeds"]),
            "expired": expired, "germinated": germinated, "entry": start,
            "buyers": buyers, "purchases": bought, "final": len(row["seeds"]),
            "events": {e["id"]: e for e in events}}


def plant_turn(old, plant, row, bank, index, earlier):
    """Reproduction is the last store-changing stage. Do not undo other spending."""
    tick, identity = row["tick"], plant["id"]
    require(not plant["dead"] and (old is None or not old["dead"]), "not a live plant step")
    values = resources.budget(old, plant, tick)
    paid = values["energy_seeds"] == 48
    require(paid == (identity in bank["buyers"]) and values["water_seeds"] == 24*paid, "unmatched seed debit")
    cooldown = max(0, (old["reproduction_cooldown"] if old else 0)-1)
    require(plant["reproduction_cooldown"] == (16 if paid else cooldown), "wrong cooldown decrement/reset")
    energy, water = plant["energy"]+48*paid, plant["water"]+24*paid
    spent = plant["spent_flowers"]-paid
    expected_spent = old["spent_flowers"] if old and row["sun_phase"] != 0 else 0
    require(spent == expected_spent and 0 <= spent <= plant["flowers"] and
            plant["flowers"] >= (old["flowers"] if old else 0), "wrong living flower reset/consumption")
    unspent = plant["flowers"]-spent
    # Existing nodes advance >=15 * ceil(255/12) progress between censuses,
    # above the 96 active threshold. New flower flags alone prove no maturity.
    mature_lower_bound = max(0, (old["flowers"] if old else 0)-spent)
    event = bank["events"].get(identity)
    maturity = ("prior-step-witness" if mature_lower_bound else "native-receipt" if event else
                "unknown" if unspent else "none")
    require(not event or unspent > 0, "seed expense without an unspent flower")
    limits = thresholds(plant)
    failures = [name for name, failed in (
        ("cooldown", cooldown != 0), ("dark", row["sun_strength"] <= 24),
        ("stress", plant["stress"] != 0), ("generation-limit", plant["generation"] == 65535),
        ("energy", energy < limits["energy"]), ("water", water < limits["water"]),
        ("no-unspent-flower", unspent == 0)) if failed]
    occupancy = bank["entry"]+len(earlier)
    require(0 <= occupancy <= 8, "invalid plant-turn bank size")
    if event:
        require(tick % 60 == 0 and not failures and occupancy < 8 and not event["invalid"] and
                all(event[k] == v for k, v in {"energy": energy, "water": water, "energy_cost": 48,
                    "water_cost": 24, "nodes_before": plant["nodes"], "nodes_after": plant["nodes"],
                    "stress": plant["stress"]}.items()), "native seed receipt contradicts preconditions")
        require(paid == (not event["denied"]), "ordinary guard/seed payment disagrees")
    else:
        require(not paid, "purchase without native receipt")
    eligible = not failures and maturity in ("prior-step-witness", "native-receipt")
    if tick % 60:
        category = "off-cadence"
        require(not event and not paid, "off-cadence reproduction")
    elif failures:
        category = "other-ineligible"
    elif not eligible:
        category = "maturity-unknown"
    elif occupancy == 8:
        category = "bank-full-at-entry" if bank["entry"] == 8 else "earlier-parent-filled"
    elif event and event["denied"]:
        category = "dark-guard"
    else:
        require(paid, "known-eligible plant with free bank did not buy")
        category = "purchase"
    require(not paid or category == "purchase", "ineligible plant paid for a seed")
    return {"tick": tick, "phase": row["sun_phase"], "id": identity, "order_index": index,
            "energy_before": energy, "water_before": water, "required": limits,
            "stress": plant["stress"], "cooldown": cooldown, "flowers": plant["flowers"],
            "unspent_flowers": unspent, "mature_lower_bound": mature_lower_bound, "maturity": maturity,
            "bank_entry": bank["entry"], "bank_at_turn": occupancy, "bank_final": bank["final"],
            "earlier_buyers": list(earlier), "failures": failures, "eligible_except_bank_guard": eligible,
            "category": category, "native_seed_event": event, "budget": values}


def empty_access():
    return {"live_steps": 0, "maintenance_steps": 0, "categories": Counter(), "failures": Counter(),
            "eligible_except_bank_guard": 0, "bank_open_ineligible": 0,
            "last_filler": Counter(), "budget": Counter(), "first_eligible_tick": None,
            "last_eligible_tick": None, "order_indices": Counter(), "purchase_phases": Counter()}


def observe(stats, turn):
    stats["live_steps"] += 1
    stats["budget"].update(turn["budget"])
    if turn["tick"] % 60:
        return
    stats["maintenance_steps"] += 1
    stats["categories"][turn["category"]] += 1
    stats["failures"].update(turn["failures"])
    stats["order_indices"][str(turn["order_index"])] += 1
    if turn["eligible_except_bank_guard"]:
        stats["eligible_except_bank_guard"] += 1
        if stats["first_eligible_tick"] is None:
            stats["first_eligible_tick"] = turn["tick"]
        stats["last_eligible_tick"] = turn["tick"]
    elif turn["bank_at_turn"] < 8:
        stats["bank_open_ineligible"] += 1
    if turn["category"] == "earlier-parent-filled":
        require(bool(turn["earlier_buyers"]), "no earlier filler")
        stats["last_filler"][str(turn["earlier_buyers"][-1])] += 1
    if turn["category"] == "purchase":
        stats["purchase_phases"][str(turn["phase"])] += 1


def analyze_case(root, arm, saved):
    worlds = list(gap.read_trace(root/f"traces/{arm}.worlds.jsonl.gz"))
    require(len(worlds) == STOP//15+1 and worlds[0]["tick"] == 0 and worlds[-1]["tick"] == STOP,
            "wrong audit horizon")
    records = {p["id"]: p for p in saved["lineages"]}
    parents = {str(i): {"lineage": p, "windows": {w: empty_access() for w in WINDOWS}} for i, p in records.items()}
    purchases, endings = defaultdict(list), defaultdict(list)
    for seed in saved["seeds"]:
        purchases[seed["birth_tick"]].append(seed)
        if seed["end_tick"] is not None:
            endings[seed["end_tick"]].append(seed)
    bank_stats = {w: Counter() for w in WINDOWS}
    bank_phases = {w: Counter() for w in WINDOWS}
    focal, releases, checked, terminals = [], [], 0, 0
    for previous, row in zip(worlds, worlds[1:]):
        bank = bank_step(previous, row)
        tick = row["tick"]
        require(bank["buyers"] == [s["parent"] for s in purchases[tick]] and
                bank["expired"] == sum(s["outcome"] == "expired" for s in endings[tick]) and
                bank["germinated"] == sum(s["outcome"] == "germinated" for s in endings[tick]),
                "ordered bank differs from full lifetime ledger")
        old = {p["id"]: p for p in previous["plants"]}
        earlier, all_turns = [], {}
        for index, plant in enumerate(row["plants"]):
            identity = plant["id"]
            require(identity in records, "unrecorded lineage")
            if plant["dead"]:
                terminals += bool(identity in old and not old[identity]["dead"])
                require(identity not in bank["events"], "dead plant seed expense")
                continue
            turn = plant_turn(old.get(identity), plant, row, bank, index, earlier)
            checked += 1
            all_turns[str(identity)] = {k: turn[k] for k in
                ("category", "failures", "bank_at_turn", "energy_before", "water_before", "required", "maturity")}
            for window in windows(tick):
                observe(parents[str(identity)]["windows"][window], turn)
            if identity == ID and tick % 60 == 0:
                focal.append({k: v for k, v in turn.items() if k != "budget"})
            if turn["category"] == "purchase":
                earlier.append(identity)
        require(earlier == bank["buyers"] and bank["entry"]+len(earlier) == bank["final"], "wrong bank at loop exit")
        for window in windows(tick):
            bank_stats[window].update(steps=1, maintenance_steps=int(tick % 60 == 0),
                full_at_entry=int(bank["entry"] == 8), full_at_exit=int(bank["final"] == 8),
                purchases=bank["purchases"], expired=bank["expired"], germinated=bank["germinated"],
                steps_with_release=int(bank["expired"]+bank["germinated"] > 0),
                release_refilled_same_step=int(bank["expired"]+bank["germinated"] > 0 and bank["final"] == 8))
            if bank["purchases"]:
                bank_phases[window][str(bank["phase"])] += bank["purchases"]
        if bank["purchases"] or bank["expired"] or bank["germinated"]:
            releases.append({k: v for k, v in bank.items() if k != "events"} |
                {"removed": [{"parent": s["parent"], "birth_tick": s["birth_tick"], "outcome": s["outcome"]}
                             for s in endings[tick]], "parent_turns": all_turns})
    require(checked == saved["checked_live_budgets"], "live budget coverage differs from parent")
    for i, entry in parents.items():
        stats = entry["windows"]["whole"]
        record = entry["lineage"]
        require(stats["categories"]["purchase"] == record["seeds_created"] and
                stats["budget"]["energy_seeds"] == 48*record["seeds_created"] and
                stats["budget"]["water_seeds"] == 24*record["seeds_created"], "parent purchases/costs disagree")
        for stats in entry["windows"].values():
            require(sum(stats["categories"].values()) == stats["maintenance_steps"], "non-partitioned opportunity categories")
    require(parents[str(ID)]["windows"]["whole"]["budget"] == saved["target"]["budget"],
            "target ledger differs from parent")
    selected, support = gap.seed_audit.focused_observations(worlds, saved["seeds"], records, ID, NOON)
    for seed in selected:
        seed["observations"]["after_noon"] = seed["observations"].pop("since_refusal")
    print("Audited reproduction access:", arm, flush=True)
    return {"parents": parents, "bank": bank_stats, "purchase_phases": bank_phases,
            "releases_and_purchases": releases, "target_maintenance_steps": focal,
            "target_seeds": selected, "target_dispersal_support": support,
            "checked_live_budgets": checked, "terminal_steps_not_reconstructed": terminals,
            "population_outcomes": {k: v for k, v in saved["outcomes"].items() if k != "post_export_children"}}


def analyze(root, saved):
    cases = {arm: analyze_case(root, arm, saved["cases"][arm]) for arm in ARMS}
    return {"rule": RULE, "parent_manifest_sha256": BASELINE_SHA, "portable_parent_sha256": PORTABLE_SHA,
            "native_calls": 0, "training_calls": 0, "stop": STOP, "after_noon_inclusive": NOON,
            "late_start_exclusive": LATE, "cases": cases,
            "notes": ["Plant-turn bank occupancy is an inference from verified append-only stage order.",
                      "Eligibility counters overlap; opportunity outcome categories are disjoint.",
                      "New flower flags alone do not establish maturity; unknown cases remain labeled.",
                      "Terminal income is cleared and not reconstructed.",
                      "No alternate allocation schedule, germination order or counterfactual offspring is simulated."]}


def analysis_sources():
    paths = sorted((experiment.ROOT/"sim").glob("*.py")) + [experiment.ROOT/PROTOCOL, experiment.ROOT/"sim/CMakeLists.txt"]
    return {str(p.relative_to(experiment.ROOT)): experiment.digest(p) for p in paths}


def check_parent(root):
    gap.parent.shadow.check_frozen(root, BASELINE_SHA)
    require(experiment.digest(experiment.ROOT/PORTABLE) == PORTABLE_SHA, "portable parent changed")
    # Added audit modules are not historical dependencies. Every recorded
    # dependency must still match; do not weaken fingerprints for changed files.
    for name, sha in experiment.read_json(root/"analysis-sources.json").items():
        require(experiment.digest(experiment.ROOT/name) == sha, "historical analysis dependency changed")
    native_sources = parent.native.native_hashes(root/"source.tar.gz")
    require(all(experiment.digest(experiment.ROOT/n) == sha for n, sha in native_sources.items()), "native source changed")
    parent.check_capture(root)
    saved = experiment.read_json(root/"results.json")
    require(saved == parent.analyze(root), "historical analysis differs")
    portable = experiment.read_json(experiment.ROOT/PORTABLE)
    require(portable == {**saved, "manifest_sha256": BASELINE_SHA,
                         "full_results_sha256": experiment.digest(root/"results.json"),
                         "timing": experiment.read_json(root/"timings.json")}, "portable parent differs")
    prefix = experiment.ROOT/PORTABLE.removesuffix("-summary.json")
    require(experiment.digest(prefix.with_suffix(".png")) == experiment.digest(root/"contact-sheet.png"),
            "parent overview changed")
    for frame in saved["frames"]:
        require(experiment.digest(prefix.with_name(prefix.name+"-frames")/(frame["id"]+".png")) ==
                experiment.digest(root/frame["png"]), "parent frame changed")
    return saved, native_sources


def verify(root):
    sources = analysis_sources()
    saved, native_sources = check_parent(root)
    result = analyze(root, saved)
    require(result == analyze(root, saved), "repeated access analysis differs")
    require(sources == analysis_sources() and
            all(experiment.digest(experiment.ROOT/n) == sha for n, sha in native_sources.items()), "analysis/native source changed")
    gap.parent.shadow.check_frozen(root, BASELINE_SHA)
    require(experiment.digest(experiment.ROOT/PORTABLE) == PORTABLE_SHA, "portable parent changed during audit")
    return {**result, "analysis_sources": sources, "native_sources": native_sources}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, default=experiment.ROOT/"artifacts/garden-renewal-dawn-reserve-v1")
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--output", type=Path)
    target.add_argument("--check", type=Path)
    args = parser.parse_args()
    root = args.baseline.resolve()
    if args.output:
        require(not args.output.exists() and not args.output.resolve().is_relative_to(root), "choose fresh output outside parent")
    result = verify(root)
    if args.output:
        experiment.write_json(args.output, result)
    else:
        require(experiment.read_json(args.check) == result, "portable access audit differs")
    print("Verified reproduction access; zero new experimental native calls", flush=True)


if __name__ == "__main__":
    main()
