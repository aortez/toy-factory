#!/usr/bin/env python3
"""Explain all post-gap recruits using frozen budgets, without new simulations."""
from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

import garden_renewal_wet_germination as parent
import garden_renewal_dark_failures as failures

experiment, require, reference = parent.experiment, parent.require, failures.reference
RULE = "garden-renewal-seedling-budget-v1"
PROTOCOL = "benchmarks/garden-longevity/renewal-seedling-budget-protocol.md"
BASELINE_SHA = "645ea3d984e064d56263238955188b3efd5eee9b9bc9de5a4c96d4e8f4349cef"
PORTABLE = "benchmarks/garden-longevity/renewal-wet-germination-summary.json"
PORTABLE_SHA = "50f90c2d2cdf349f0595c22c201992a056336f426de04075d3573f131a502eb1"
COHORT = {"required": (10,), "optional": (10, 11, 12, 13, 14)}
STEP, DAY, DAYS = 15, 3840, 3
PHASES = (117, 128, 0, 10, 11, 64)
ORIGIN = {"energy": 64, "water": 24}


def scope(records, arm):
    chosen = {p["id"]: p for p in records if p["parent"] and p["birth_tick"] > parent.AT}
    require(tuple(chosen) == COHORT[arm], "post-gap cohort changed")
    require(all(p["birth_tick"]+DAYS*DAY <= parent.STOP for p in chosen.values()), "insufficient follow-up")
    return chosen


def maintenance(old, state, values):
    """Unpaid demand is not a store debit; never infer cleared death-step income."""
    if old is None or state["tick"] % 60 or values is None:
        return None
    result = {}
    for resource, nodes in (("energy", old["nodes"]), ("water", old["nodes"]-old["roots"])):
        due, paid = (nodes+7)//8, values[resource+"_upkeep"]
        require(0 <= paid <= due, "upkeep debit exceeds old-body demand")
        result[resource] = {"due": due, "paid": paid, "unpaid": due-paid}
    return result


def segments(history, birth):
    result, previous = [], ORIGIN
    for day in range(1, DAYS+1):
        start, end = birth+(day-1)*DAY, birth+day*DAY
        entries = [e for e in history if (e["state"]["tick"] >= start if day == 1 else
                   e["state"]["tick"] > start) and e["state"]["tick"] <= end]
        if not entries:
            break
        live = [e for e in entries if not e["state"]["dead"]]
        last = live[-1]["state"] if live else previous
        totals = failures.budget_sum(entries)
        failures.balance(previous, last, totals)
        result.append({"age_day": day, "start": previous, "last_live": last, "budget": totals,
                       "observed_steps": len(entries), "live_steps": len(live),
                       "complete": entries[-1]["state"]["tick"] == end and not entries[-1]["terminal"],
                       "terminal_tick": entries[-1]["state"]["tick"] if entries[-1]["terminal"] else None})
        previous = last
    require(sum(s["observed_steps"] for s in result) == len(history), "day intervals lost/duplicated steps")
    return result


def stress_episodes(history):
    result, active = [], None
    for entry in history:
        p = entry["state"]
        if p["flags"] & 6 or p["stress"]:
            if active is None:
                active = {"first": p, "last": p, "peak_stress": 0,
                          "maintenance_shortages": Counter(), "recovery_tick": None, "terminal_tick": None}
                result.append(active)
            active["last"] = p
            active["peak_stress"] = max(active["peak_stress"], p["stress"])
            if p["tick"] % 60 == 0:
                for resource, bit in (("energy", 2), ("water", 4)):
                    active["maintenance_shortages"][resource] += bool(p["flags"] & bit)
            if entry["terminal"]:
                active["terminal_tick"] = p["tick"]
        elif active is not None:
            active["recovery_tick"] = p["tick"]
            active = None
    return result


def zero_income_runs(history):
    result, current = [], None
    for entry in history:
        p, values = entry["state"], entry["budget"]
        if values is None or values["energy_income"]:
            current = None
            continue
        if current is None:
            current = {"first_tick": p["tick"], "last_tick": p["tick"], "steps": 0,
                       "possible_global_light_steps": 0, "active_leaf_steps": 0}
            result.append(current)
        current["last_tick"] = p["tick"]
        current["steps"] += 1
        current["possible_global_light_steps"] += reference.prior.sun_strength(p["phase"]) >= 64
        current["active_leaf_steps"] += p["active_leaves"] > 0
    return result


def describe(record, full_history, capacity):
    birth, identity = record["birth_tick"], record["id"]
    end = min(birth+DAYS*DAY, record["death_tick"] or parent.STOP)
    history = [e for e in full_history if e["state"]["tick"] <= end]
    require([e["state"]["tick"] for e in history] == list(range(birth, end+1, STEP)), "incomplete focal interval")
    require(all(e["state"]["id"] == identity for e in history), "mixed focal identities")
    require(all(e["terminal"] is None for e in history[:-1]) and
            (history[-1]["terminal"] == "natural") == (record["death_tick"] == end), "wrong focal endpoint")
    old, steps, purchases, changes = None, [], [], []
    for e in history:
        p, values = e["state"], e["budget"]
        require((values is None) == p["dead"], "missing live budget or invented terminal budget")
        if values is not None and any(values["energy_"+k] for k in reference.KINDS):
            stages = reference.spending_stages(old, p, p["tick"], values)
            for stage in stages:
                for key in ("before_budget", "after_budget"):
                    stage[key] = failures.compact(stage[key])
            purchases.append({"tick": p["tick"], "phase": p["phase"], "stages": stages})
        if old is not None and not p["dead"] and (p["nodes"], p["roots"]) != (old["nodes"], old["roots"]):
            changes.append({"tick": p["tick"], "before_nodes": old["nodes"], "after_nodes": p["nodes"],
                            "before_roots": old["roots"], "after_roots": p["roots"],
                            "before_upkeep": (old["nodes"]+7)//8, "after_upkeep": (p["nodes"]+7)//8})
        steps.append({**e, "maintenance": maintenance(old, p, values),
                      "capacity": capacity.get((p["tick"], identity), [])})
        old = p
    live = [e for e in history if not e["state"]["dead"]]
    totals = failures.budget_sum(history)
    failures.balance(ORIGIN, live[-1]["state"], totals)
    windows = failures.all_windows(history)
    for window in windows:
        window["minimum_reserves"] = failures.minimum_energy(window["anchor"]["tick"], window["anchor"])
        first = window["prediction"]["boundaries"]["first_possible_income_tick"]
        next_dusk = first + (117-11)*STEP
        morning = [e for e in history if first <= e["state"]["tick"] <= next_dusk]
        positive = next((e["state"]["tick"] for e in morning if e["budget"] and e["budget"]["energy_income"]), None)
        window["following_daylight"] = {"first_possible_income_tick": first,
            "first_observed_income_tick": positive, "observed_steps": len(morning),
            "last_tick": morning[-1]["state"]["tick"] if morning else None,
            "terminal_step_unaccounted": next((e["state"]["tick"] for e in morning if e["terminal"]), None)}
    death = failures.death_record(history, windows, record, True) if history[-1]["terminal"] else None
    denied = [{"tick": e["state"]["tick"], "receipt": event} for e in steps for event in e["events"] if event["denied"]]
    capacity_denied = [{"tick": e["state"]["tick"], "receipt": event} for e in steps for event in e["capacity"] if event["denied"]]
    income_tick = next((e["state"]["tick"] for e in live if e["budget"]["energy_income"]), None)
    possible_tick = next(t for t in range(birth+STEP, birth+DAY+STEP, STEP)
                         if reference.prior.sun_strength((64+t//STEP)%256) >= 64)
    classification = "early-death" if record["death_tick"] is not None and record["death_tick"] <= birth+DAY else \
                     "later-death" if record["death_tick"] is not None else "alive-at-day-64"
    return {"lineage": record, "group": classification, "analysis_end_tick": end,
        "birth_state": history[0]["state"], "last_live": live[-1]["state"],
        "terminal_budget": "cleared-not-reconstructed" if death else None,
        "budget": totals, "checked_live_steps": len(live), "peak_stress": max(e["state"]["stress"] for e in history),
        "first_possible_global_income_tick": possible_tick, "first_observed_income_tick": income_tick,
        "zero_income_runs": zero_income_runs(history), "stress_episodes": stress_episodes(history),
        "days": segments(history, birth), "dark_windows": windows, "death": death, "paid_stages": purchases,
        "body_changes": changes, "guard_denials": denied, "capacity_denials": capacity_denied,
        "checkpoints": [e["state"] for i, e in enumerate(history) if i in (0, len(history)-1) or
                        e["state"]["phase"] in PHASES or (e["state"]["tick"]-birth)%DAY == 0],
        "steps": steps}


def focal_rows(rows, chosen, capacity):
    """Filtering is only for the focal ledger; parent validation checks the full census."""
    for row in rows:
        for receipt in row["night_capacity"]["events"]:
            expense = row["dark_guard"]["events"][receipt["expense"]]
            if expense["id"] in chosen:
                capacity.setdefault((row["tick"], expense["id"]), []).append({**receipt, "proposal": expense})
        yield {**row, "plants": [p for p in row["plants"] if p["id"] in chosen]}


def analyze(root, saved):
    cases = {}
    for arm in parent.ARMS:
        chosen = scope(saved["cases"][arm]["lineages"], arm)
        capacity = {}
        rows = focal_rows(parent.gap.read_trace(root/f"traces/{arm}.worlds.jsonl.gz"), chosen, capacity)
        histories, checked = failures.histories(rows, {}, chosen, parent.STOP)
        children = []
        for identity, record in chosen.items():
            result = describe(record, histories[identity], capacity)
            previous = next(p for p in saved["cases"][arm]["outcomes"]["post_export_children"] if p["lineage"]["id"] == identity)
            result["germination_receipt"] = previous["receipt"]
            result["own_seeds_through_day_64"] = previous["own_seeds"]
            result["offspring_through_day_64"] = previous["offspring"]
            first = result["stress_episodes"][0]["first"] if result["stress_episodes"] else None
            first_day = first if first is not None and first["tick"] <= record["birth_tick"]+DAY else None
            require((first_day["tick"] if first_day else None) ==
                    (previous["first_shortage"]["tick"] if previous["first_shortage"] else None), "prior first shortage differs")
            children.append(result)
        cases[arm] = {"children": children, "checked_focal_live_steps_through_day_64": checked}
        print("Audited seedling budgets:", arm, flush=True)
    children = [p for c in cases.values() for p in c["children"]]
    return {"rule": RULE, "baseline_manifest_sha256": BASELINE_SHA, "baseline_portable_sha256": PORTABLE_SHA,
        "native_calls": 0, "age_days": DAYS, "cases": cases,
        "summary": {"children": len(children), "groups": Counter(p["group"] for p in children),
            "checked_live_steps": sum(p["checked_live_steps"] for p in children),
            "terminal_steps_unaccounted": sum(p["death"] is not None for p in children),
            "dark_windows": Counter(w["status"] for p in children for w in p["dark_windows"]),
            "exact_dark_prefix_steps": sum(w["exact_prefix_steps"] for p in children for w in p["dark_windows"]),
            "paid_stages": Counter(s["kind"] for p in children for e in p["paid_stages"] for s in e["stages"]),
            "guard_denials": sum(len(p["guard_denials"]) for p in children),
            "capacity_denials": sum(len(p["capacity_denials"]) for p in children)}}


def analysis_sources():
    paths = sorted((experiment.ROOT/"sim").glob("*.py")) + [experiment.ROOT/PROTOCOL, experiment.ROOT/"sim/CMakeLists.txt"]
    return {str(p.relative_to(experiment.ROOT)): experiment.digest(p) for p in paths}


def verify(root):
    require(experiment.digest(root/"manifest.json") == BASELINE_SHA and
            experiment.digest(experiment.ROOT/PORTABLE) == PORTABLE_SHA, "changed frozen inputs")
    sources = analysis_sources()
    native = parent.native.native_hashes(root/"source.tar.gz")
    require(all(experiment.digest(experiment.ROOT/n) == sha for n, sha in native.items()), "native sources changed")
    saved = parent.verify(root)
    portable = experiment.read_json(experiment.ROOT/PORTABLE)
    extras = {"manifest_sha256", "full_results_sha256", "exporter_sha256", "timing"}
    require(saved == {k: v for k, v in portable.items() if k not in extras} and
            portable["full_results_sha256"] == experiment.digest(root/"results.json") and
            portable["exporter_sha256"] == experiment.digest(Path(parent.__file__)), "portable parent differs")
    result = analyze(root, saved)
    require(result == analyze(root, saved), "repeated seedling audit differs")
    require(analysis_sources() == sources, "analysis changed while running")
    require(experiment.digest(root/"manifest.json") == BASELINE_SHA, "parent manifest changed")
    manifest = experiment.read_json(root/"manifest.json")
    for name in manifest["artifacts"]:
        parent.gap.gallery.artifact(root, manifest, name)
    result.update(analysis_sources=sources, native_sources=native)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, default=experiment.ROOT/"artifacts/garden-renewal-wet-germination-v1")
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
        require(experiment.read_json(args.check) == result, "portable seedling audit differs")
    print(result["summary"], flush=True)
    print("Verified seedling budgets; zero new native calls", flush=True)


if __name__ == "__main__":
    main()
