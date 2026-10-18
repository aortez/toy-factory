#!/usr/bin/env python3
"""Read-only first-day allocation diagnosis on the frozen ordinary-range panel."""

from __future__ import annotations

import argparse
from collections import Counter
import copy
import gzip
import json
from pathlib import Path
import sys

import garden_landing_recruitment as prior
from garden_experiments import digest
from garden_resources import require

ROOT, DAY, STEP = prior.ROOT, prior.DAY, prior.STEP
RULE = "garden-landing-establishment-v1"
INPUT = "benchmarks/garden-seasons/landing-recruitment-trace-results.json.gz"
INPUT_SHA = "2e4a8b9bada29ae847e0f77d22e020cab9b117765455ff6e11fbd52088b44561"
RESOURCES = ("energy", "water")
LANDMARKS = (DAY // 8, DAY // 4)


def load(path):
    require(digest(path) == INPUT_SHA, "wrong frozen ordinary input")
    return json.loads(gzip.decompress(path.read_bytes()))


def due(nodes, roots):
    require(type(nodes) is int and type(roots) is int and 0 <= roots <= nodes <= 256,
            "invalid ordinary body")
    return ((nodes + 7) // 8, (nodes - roots + 7) // 8)


def phase(tick):
    return (64 + tick // STEP) % 256


def maximum_sun(tick):
    """Unattenuated sun only; actual light can be lower in winter or shade."""
    p = phase(tick)
    height = min(p, 128 - p) if p <= 128 else 0
    return 24 + (height * 231 + 32) // 64


def payment_exposure(before, after, nodes, roots):
    costs = due(nodes, roots)
    require(len(before) == len(after) == 2 and all(type(v) is int and v >= 0 for v in [*before, *after]),
            "invalid growth stores")
    require(all(a <= b for a, b in zip(after, before)), "negative growth expense")
    return {"one_payment_due": list(costs),
            "below_payment": [r for j, r in enumerate(RESOURCES) if after[j] < costs[j]],
            "crossed_payment": [r for j, r in enumerate(RESOURCES) if before[j] >= costs[j] > after[j]]}


def summarize_child(plant, stop):
    require(plant["death_tick"] is None or plant["death_tick"] <= stop,
            "future death leaked into censored ledger")
    checked = copy.deepcopy(plant)
    prior.analyze_child(checked, stop)
    require(checked == plant, "saved child accounting differs")
    rows = plant["rows"]
    birth = plant["birth_tick"]
    require(rows[0]["stages"][2][4] == 4 and rows[0]["roots"] in (2, 3), "wrong initial body")
    require(all(not r["stages"][4][3] & 1 for r in rows[:-1]), "sample after death")
    first_root = None
    shortages = []
    purchases = []
    root_changes = []
    income = {r: Counter() for r in RESOURCES}
    zero_tail = dict.fromkeys(RESOURCES, 0)
    previous = None
    for row in rows:
        tick, stages = row["tick"], row["stages"]
        dead = bool(stages[4][3] & 1)
        old_roots = previous["roots"] if previous is not None else 2
        # Decomposition changes leaf maturity on the death tick; root counts and
        # pre-growth nodes, not post-death leaf counts, determine maintenance.
        require(stages[2][4] == (previous["stages"][4][4] if previous else 4), "pre-growth body changed")
        if previous is not None:
            costs = due(stages[0][4], old_roots) if tick % 60 == 0 else (0, 0)
            missing = []
            for j, resource in enumerate(RESOURCES):
                raw = row["uptake"][j]
                paid = raw[4] if dead else stages[0][j] - stages[1][j]
                require(paid == min(costs[j], stages[0][j]), "maintenance payment differs")
                if dead:
                    require(raw[3] == costs[j], "death demand differs")
                if paid < costs[j]:
                    missing.append(resource)
                credit = raw[1]
                income[resource]["samples"] += 1
                income[resource]["positive_samples"] += credit > 0
                zero_tail[resource] = 0 if credit else zero_tail[resource] + 1
                if resource == "energy" and not credit:
                    key = ("zero_global_ceiling_below_income" if maximum_sun(tick) < 64 else
                           "zero_with_active_leaf_and_possible_global_light" if previous["active_leaves"] else
                           "zero_without_active_leaf_and_possible_global_light")
                    income[resource][key] += 1
                if resource == "water" and old_roots == 2:
                    income[resource]["initial_roots_samples"] += 1
                    income[resource]["initial_roots_income"] += credit
            if tick % 60 == 0:
                expected = previous["stages"][4][2] + 1 if missing else max(0, previous["stages"][4][2] - 1)
                bits = (2 if "energy" in missing else 0) | (4 if "water" in missing else 0)
                require(stages[1][2] == expected and stages[1][3] & 6 == bits and dead == (expected == 8),
                        "stress/shortage transition differs")
                if missing:
                    shortages.append({"tick": tick, "age_ticks": tick - birth, "resources": missing,
                                      "roots": old_roots, "nodes": stages[0][4], "stress": expected,
                                      "income": [r[1] for r in row["uptake"]],
                                      "before_upkeep": stages[0][:2], "due": list(costs)})
            else:
                require(stages[1][2:4] == previous["stages"][4][2:4], "stress changed off cadence")
        if not dead:
            root_delta = row["roots"] - old_roots
            nodes_delta = stages[3][4] - stages[2][4]
            require(0 <= root_delta <= nodes_delta <= 1, "unexpected ordinary growth delta")
            if root_delta:
                first_root = tick if first_root is None else first_root
                root_changes.append(tick)
            spend = [stages[2][j] - stages[3][j] for j in range(2)]
            if any(spend):
                require(all(spend), "partial growth debit")
                kind = "root" if root_delta else "shoot" if nodes_delta else "no_new_node"
                # This is a one-payment exposure, not a prediction: no future
                # uptake, policy decision, or causal rescue is inferred.
                purchases.append({"tick": tick, "kind": kind, "cost": spend,
                                  "before": stages[2][:2], "after": stages[3][:2],
                                  "roots": row["roots"], "nodes": stages[3][4], "stress": stages[3][2],
                                  **payment_exposure(stages[2][:2], stages[3][:2], stages[3][4], row["roots"])})
        previous = row
    living_rows = [r for r in rows if not r["stages"][4][3] & 1]
    last_live = living_rows[-1]
    first_shortage = {r: next((s for s in shortages if r in s["resources"]), None) for r in RESOURCES}
    return {k: plant[k] for k in ("id", "parent", "species", "generation", "birth_tick", "death_tick", "outcome", "death_shortage")} | {
        "age_observed_ticks": rows[-1]["tick"] - birth, "resources": plant["resources"],
        "death_sun_phase": phase(plant["death_tick"]) if plant["outcome"] == "died" else None,
        "first_root_tick": first_root, "root_growth_ticks": root_changes,
        "last_living_body": {"tick": last_live["tick"], "nodes": last_live["stages"][4][4],
                             "roots": last_live["roots"], "active_leaves": last_live["active_leaves"]},
        "first_shortage": first_shortage, "shortages": shortages, "growth": purchases,
        "income_samples": {r: dict(sorted(v.items())) for r, v in income.items()},
        "terminal_zero_income_run_steps": zero_tail,
        "landmarks": {str(age): next(({"roots": r["roots"], "nodes": r["stages"][4][4],
                                      "energy": r["stages"][4][0], "water": r["stages"][4][1]}
                                     for r in living_rows if r["tick"] == birth + age), None) for age in LANDMARKS}}


def aggregate(children):
    dead = [p for p in children if p["outcome"] == "died"]
    return {
        "children": len(children),
        "outcomes": dict(sorted(Counter(p["outcome"] for p in children).items())),
        "death_shortages": dict(sorted(Counter(p["death_shortage"] for p in dead).items())),
        "no_root_expansion": sum(p["first_root_tick"] is None for p in children),
        "root_expanded_without_prior_shortage": {r: sum(p["first_root_tick"] is not None and
            (p["first_shortage"][r] is None or p["first_root_tick"] < p["first_shortage"][r]["tick"]) for p in children)
                                      for r in RESOURCES},
        "ever_short": {r: sum(p["first_shortage"][r] is not None for p in children) for r in RESOURCES},
        "pre_shortage_growth_crossed_one_payment": {r: sum(p["first_shortage"][r] is not None and
            any(r in g["crossed_payment"] and g["tick"] < p["first_shortage"][r]["tick"] for g in p["growth"])
                                                          for p in children) for r in RESOURCES},
        "growth_after_first_shortage": {r: sum(p["first_shortage"][r] is not None and
            any(g["tick"] >= p["first_shortage"][r]["tick"] for g in p["growth"]) for p in children) for r in RESOURCES},
        "deaths_with_globally_unavailable_energy": sum(maximum_sun(p["death_tick"]) < 64 for p in dead),
        "growth": {kind: {"purchases": sum(g["kind"] == kind for p in children for g in p["growth"]),
                          **{r: sum(g["cost"][j] for p in children for g in p["growth"] if g["kind"] == kind)
                             for j, r in enumerate(RESOURCES)}} for kind in ("root", "shoot", "no_new_node")},
        "resources": {r: {f: sum(p["resources"][r][f] for p in children) for f in prior.RESOURCE_FIELDS} for r in RESOURCES},
        "income_samples": {r: dict(sorted(sum((Counter(p["income_samples"][r]) for p in children), Counter()).items()))
                           for r in RESOURCES},
        "landmarks": {str(age): {"not_living": sum(p["landmarks"][str(age)] is None for p in children),
                                 "initial_roots": sum(p["landmarks"][str(age)] is not None and
                                     p["landmarks"][str(age)]["roots"] == 2 for p in children),
                                 "expanded_roots": sum(p["landmarks"][str(age)] is not None and
                                     p["landmarks"][str(age)]["roots"] > 2 for p in children)} for age in LANDMARKS}}


def analyze(data):
    require(data["rule"] == prior.RULE and data["stages"] == list(prior.STAGES) and
            data["resource_fields"] == list(prior.RESOURCE_FIELDS), "wrong trace contract")
    require(len(data["worlds"]) == 12 and len({w["id"] for w in data["worlds"]}) == 12, "wrong panel")
    worlds = []
    for world in data["worlds"]:
        require(world["result"]["rules"] == 0 and world["result"]["tick"] == prior.STOP, "not ordinary full horizon")
        plants = world["audit"]["plants"]
        for p in plants:
            require(p["death_tick"] is None or p["death_tick"] <= prior.STOP, "future death in input")
            checked = copy.deepcopy(p)
            prior.analyze_child(checked, prior.STOP)
            require(checked == p, "full-panel child budget differs")
        children = [summarize_child(p, prior.STOP) for p in plants if 62 * DAY < p["birth_tick"] <= 190 * DAY]
        require(all(p["outcome"] != "pending" for p in children), "incomplete late follow-up")
        require(len(children) == world["audit"]["summary"]["late_children"]["children"], "cohort mismatch")
        scores = prior.training.score_world(world["result"], world["case"], data["models"][world["model"]]["metadata"])
        worlds.append({k: world[k] for k in ("id", "case", "model", "trace_sha256")} |
                      {"children": children, "summary": aggregate(children), "unchanged_history": scores})
    groups = {}
    for climate in ("all", "steady", "seasonal"):
        ps = [p for w in worlds if climate == "all" or w["case"]["climate"] == climate for p in w["children"]]
        groups[climate] = {outcome: aggregate([p for p in ps if outcome == "all" or p["outcome"] == outcome])
                           for outcome in ("all", "died", "confirmed")}
        groups[climate]["by_death_shortage"] = {r: aggregate([p for p in ps if p["death_shortage"] == r])
                                               for r in ("energy", "water", "energy+water")}
    return {"rule": RULE, "input": INPUT, "input_sha256": INPUT_SHA,
            "cohort": {"birth_after": 62 * DAY, "birth_through": 190 * DAY, "followup_ticks": DAY},
            "groups": groups, "worlds": worlds}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / INPUT)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--out", type=Path)
    target.add_argument("--verify", type=Path)
    args = parser.parse_args()
    try:
        result = analyze(load(args.input))
        require(digest(args.input) == INPUT_SHA, "input changed during diagnosis")
        if args.verify:
            raw = args.verify.read_bytes()
            require(json.loads(gzip.decompress(raw) if args.verify.suffix == ".gz" else raw) == result,
                    "saved diagnosis differs")
            print("Verified all 127 late children, first-day budgets, maintenance, allocation and unchanged histories.")
        else:
            raw = (json.dumps(result, sort_keys=True, indent=2) + "\n").encode()
            with args.out.open("xb") as stream:
                if args.out.suffix == ".gz":
                    with gzip.GzipFile(filename="", fileobj=stream, mode="wb", mtime=0) as zipped:
                        zipped.write(raw)
                else:
                    stream.write(raw)
            print(json.dumps({c: {k: v for k, v in groups["all"].items() if k in
                                 ("children", "outcomes", "death_shortages", "no_root_expansion")}
                              for c, groups in result["groups"].items()}, sort_keys=True))
        return 0
    except (OSError, ValueError, RuntimeError, KeyError, TypeError) as error:
        print("establishment diagnosis failed: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
