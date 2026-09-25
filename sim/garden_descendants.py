#!/usr/bin/env python3
"""Join frozen seed purchases, exact opportunities and descendant survival; no fitness."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import gzip
import json
from pathlib import Path
import shutil

import garden_recruitment as recruitment
import garden_seed_attempts as attempts

experiment, require = recruitment.experiment, recruitment.require
DAY, STEP, START, END = 3840, 15, 160 * 3840, 192 * 3840
RULE = "garden-descendant-outcomes-v1"
INPUTS = {
    "recruitment": "7c3e50235343b2a223e607bbacbfe6d06f55b735c0ea452fc777ed04e1b5ef77",
    "attempts": "0615e91b550b20ce60050f76b6bce5d7beef8902123ebbeaa9053e0e5c37eacb",
}


def state_at(plant, tick):
    if tick < plant["birth_tick"]:
        return "unborn"
    if plant["death_tick"] is None or plant["death_tick"] > tick:
        return "alive"
    return "patch-dead" if plant.get("environmental_death", False) else "natural-dead"


def confirmation(plant, origin, end):
    require(plant["birth_tick"] <= origin <= end, "invalid confirmation origin")
    due = origin + DAY
    state = state_at(plant, min(due, end))
    if state != "alive":
        return "patch-censored" if state == "patch-dead" else "natural-failure"
    return "confirmed" if due <= end else "horizon-censored"


def index_records(lineages, seeds, start, end):
    require(0 <= start < end and start % STEP == end % STEP == 0, "invalid cohort window")
    records = {p["id"]: p for p in lineages}
    require(len(records) == len(lineages) and all(type(k) is int and k > 0 for k in records),
            "duplicate/invalid plant identity")
    for p in lineages:
        birth, death = p["birth_tick"], p["death_tick"]
        require(type(birth) is int and 0 <= birth <= end and birth % STEP == 0 and
                (death is None or type(death) is int and birth <= death <= end and death % STEP == 0),
                "invalid lifetime")
        require(not p.get("environmental_death", False) or death is not None, "patch without death")
        require(p["parent"] == 0 or p["parent"] in records and
                records[p["parent"]]["birth_tick"] < birth, "invalid ancestry")
    indexed, children = {}, set()
    counts, closing = Counter(), Counter()
    for s in seeds:
        key = s["parent"], s["birth_tick"]
        require(key not in indexed and s["parent"] in records, "ambiguous seed or missing parent")
        parent, tick = records[s["parent"]], s["birth_tick"]
        require(type(tick) is int and 0 < tick <= end and tick % STEP == 0 and
                parent["birth_tick"] <= tick and (state_at(parent, tick) == "alive" or
                parent.get("environmental_death", False) and parent["death_tick"] == tick),
                "seed not purchased by a living parent")
        status, finish = s["outcome"], s["end_tick"]
        require(status in ("germinated", "expired", "pending"), "invalid seed outcome")
        if status == "pending":
            require(finish is None and s["child_id"] is None and tick + DAY > end, "invalid pending seed")
        else:
            require(type(finish) is int and tick < finish <= min(tick + DAY, end) and
                    finish % STEP == 0, "invalid seed end")
            if status == "expired":
                require(finish == tick + DAY and s["child_id"] is None, "invalid expiry")
            else:
                require(s["child_id"] in records and s["child_id"] not in children and
                        tick + recruitment.establishment.DORMANCY * STEP <= finish < tick + DAY,
                        "invalid/duplicate germination")
                child = records[s["child_id"]]
                require(child["parent"] == s["parent"] and child["birth_tick"] == finish and
                        all(child[k] == s[k] for k in ("column", "generation")), "seed/child mismatch")
                children.add(child["id"])
        indexed[key] = s
        counts[s["parent"]] += 1
        closing[s["parent"]] += tick > start
    require(children == {p["id"] for p in lineages if p["parent"]}, "unmatched child birth")
    require(all(p["seeds_created"] == counts[p["id"]] and
                p["late_seeds_created"] == closing[p["id"]] for p in lineages),
            "per-parent seed ledger mismatch")
    return records, indexed


def funnel(events):
    result = Counter(created=len(events), germinated=0, expired=0, pending=0,
                     established=0, child_natural_failure=0, child_patch_censored=0,
                     child_horizon_censored=0, established_with_established_child=0)
    parents, matrix = Counter(), defaultdict(Counter)
    for e in events:
        result[e["seed_outcome"]] += 1
        field = {"confirmed": "established", "natural-failure": "child_natural_failure",
                 "patch-censored": "child_patch_censored", "horizon-censored": "child_horizon_censored"}
        if e["child_confirmation"] is not None:
            result[field[e["child_confirmation"]]] += 1
        result["established_with_established_child"] += bool(e["established_grandchildren"])
        parents[e["parent_confirmation"]] += 1
        matrix[e["parent_confirmation"]][e["child_confirmation"] or e["seed_outcome"]] += 1
    require(result["created"] == sum(result[k] for k in ("germinated", "expired", "pending")) and
            result["germinated"] == sum(result[k] for k in ("established", "child_natural_failure",
                "child_patch_censored", "child_horizon_censored")), "funnel does not reconcile")
    return {"counts": dict(result), "parent_confirmation": dict(parents),
            "parent_child_cross_tab": dict(matrix)}


def outcomes(lineages, seeds, start=START, end=END):
    records, indexed = index_records(lineages, seeds, start, end)
    children = defaultdict(list)
    for p in lineages:
        if p["parent"]:
            children[p["parent"]].append(p)
    events = []
    for (parent_id, tick), s in sorted(indexed.items()):
        if tick <= start:
            continue
        parent = records[parent_id]
        child = records.get(s["child_id"])
        status = confirmation(child, child["birth_tick"], end) if child else None
        grandchildren = sorted(c["id"] for c in children[s["child_id"]]
            if status == "confirmed" and confirmation(c, c["birth_tick"], end) == "confirmed")
        events.append({"parent": parent_id, "purchase_tick": tick, "column": s["column"],
            "full_potential_followup": tick + 2 * DAY <= end,
            "parent_confirmation": confirmation(parent, tick, end),
            "parent_final": state_at(parent, end), "seed_outcome": s["outcome"],
            "seed_end_tick": s["end_tick"], "child": s["child_id"], "child_confirmation": status,
            "child_confirmation_tick": child["birth_tick"] + DAY if child else None,
            "child_final": state_at(child, end) if child else None,
            "parent_at_child_confirmation": state_at(parent, child["birth_tick"] + DAY)
                if child and child["birth_tick"] + DAY <= end else None,
            "child_seed_purchases": child["seeds_created"] if child else 0,
            "established_grandchildren": grandchildren})
    parents = []
    for identity, p in sorted(records.items()):
        if p["death_tick"] is not None and p["death_tick"] <= start:
            continue
        own = [e for e in events if e["parent"] == identity]
        bins = sorted({(e["purchase_tick"] - p["birth_tick"]) // DAY for e in own
                       if e["parent_confirmation"] == "confirmed"})
        established = [e["child"] for e in own if e["child_confirmation"] == "confirmed"]
        origin = max(start, p["birth_tick"])
        last_live = end if p["death_tick"] is None else p["death_tick"] - STEP
        parents.append({"id": identity, "lineage": p, "closing_origin": origin,
            "closing_live_ticks": max(0, last_live - origin),
            "closing_day_confirmation": confirmation(p, origin, end), "final_state": state_at(p, end),
            "purchases": len(own), "confirmed_parent_age_bins": bins, "capped_parent_bins": min(4, len(bins)),
            "established_children": established,
            "established_children_with_established_child": [e["child"] for e in own if e["established_grandchildren"]],
            "category": "established-child" if established else
                ("purchases-no-observed-established-child" if own else "no-closing-purchases"),
            "outcomes": funnel(own)})
    return {"window": {"start_exclusive": start, "end_inclusive": end}, "seeds": events, "parents": parents,
            "all": funnel(events), "full_potential": funnel([e for e in events if e["full_potential_followup"]]),
            "recent": funnel([e for e in events if not e["full_potential_followup"]]),
            "birth_cohort_reconciliation": {
                "all_closing_births": sum(p["parent"] != 0 and p["birth_tick"] > start for p in lineages),
                "from_closing_purchases": sum(e["child"] is not None for e in events),
                "from_earlier_purchases": sum(s["birth_tick"] <= start and s["outcome"] == "germinated" and
                                              s["end_tick"] > start for s in seeds)}}


def opportunities(rows, seeds, start=START, end=END):
    """Join already validated exact visits; check every cohort seed's entire visit sequence."""
    selected = {(s["parent"], s["birth_tick"]): s for s in seeds if start < s["birth_tick"] <= end}
    counts = {key: Counter() for key in selected}
    last = {key: key[1] for key in selected}
    for row in rows:
        if row["type"] != "seed-step":
            continue
        tick = row["tick"]
        for a in row["attempts"]:
            key = a["parent"], tick - a["age"] * STEP
            if key not in selected:
                require(key[1] <= start, "unmatched closing seed visit")
                continue
            s, c = selected[key], counts[key]
            require(tick == last[key] + STEP and tick <= (s["end_tick"] or end) and
                    all(a[k] == s[k] for k in ("column", "generation", "species")), "seed visit join mismatch")
            last[key] = tick
            c["visits"] += 1
            if a["outcome"] in (1, 2):
                require(tick == s["end_tick"] and s["outcome"] ==
                        ("expired" if a["outcome"] == 1 else "germinated") and
                        a["child"] == (s["child_id"] or 0), "terminal seed visit mismatch")
            if a["outcome"] == 1:
                c["expired"] += 1
                continue
            c["checks"] += 1
            if a["age"] < recruitment.establishment.DORMANCY:
                c["dormant_checks"] += 1
                continue
            c["mature_checks"] += 1
            actual, anywhere = a["blockers"] == 0, 0 in a["sites"]
            reachable = any(mask == 0 and s["reachable_columns"] & (1 << col)
                            for col, mask in enumerate(a["sites"]))
            require(actual == (a["outcome"] == 2), "eligible seed did not germinate")
            c["actual_open"] += actual
            c["anywhere_open"] += anywhere
            c["reachable_open"] += reachable
            c["anywhere_open_actual_blocked"] += anywhere and not actual
            for name, bit in recruitment.establishment.BLOCKERS.items():
                c["blocked_" + name] += bool(a["blockers"] & bit)
    for key, s in selected.items():
        require(last[key] == (s["end_tick"] or end), "truncated cohort seed visits")
        require(counts[key]["actual_open"] == int(s["outcome"] == "germinated") and
                counts[key]["expired"] == int(s["outcome"] == "expired"), "seed opportunity outcome mismatch")
    return counts


def examples(cases):
    options = [(c["key"], p) for c in sorted(cases, key=lambda c: c["key"]) for p in c["parents"]]
    predicates = {
        "nonproducing_survivor": lambda p: p["purchases"] == 0 and p["final_state"] == "alive" and
            p["closing_day_confirmation"] == "confirmed",
        "producer_without_established_child": lambda p: p["purchases"] > 0 and not p["established_children"],
        "producer_with_established_child": lambda p: bool(p["established_children"]),
        "naturally_dead_parent_with_established_child": lambda p: p["final_state"] == "natural-dead" and
            bool(p["established_children"]),
        "two_generation_establishment": lambda p: bool(p["established_children_with_established_child"]),
    }
    return {name: next(({"case": key, "parent": p["id"]} for key, p in options if predicate(p)), None)
            for name, predicate in predicates.items()}


def evaluate(roots):
    manifests = {}
    for name, root in roots.items():
        require(experiment.digest(root / "manifest.json") == INPUTS[name], "wrong frozen input " + name)
        m = experiment.read_json(root / "manifest.json")
        require(m["status"] == "complete" and m["expected_runs"] == 8, "incomplete input")
        for path in m["artifacts"]:
            recruitment.establishment.verified(root, m, path)
        manifests[name] = m
    root, audit_root = roots["recruitment"], roots["attempts"]
    specs = experiment.read_json(root / "cases.json")
    require(len(specs) == 8 and len({c["key"] for c in specs}) == 8, "wrong case panel")
    output, checked = [], Counter()
    for c in specs:
        key = c["key"]
        a = experiment.read_json(root / f"analyses/{key}.json")
        boundaries = experiment.read_json(root / f"analyses/{key}.boundaries.json")
        for old, new in ((f"traces/{key}.world.gz", f"input/{key}.world.gz"),
                         (f"traces/{key}.sites.gz", f"input/{key}.sites.gz"),
                         (f"analyses/{key}.boundaries.json", f"input/{key}.boundaries.json")):
            require(manifests["recruitment"]["artifacts"][old] == manifests["attempts"]["artifacts"][new],
                    "opportunity bundle is not the same frozen history")
        current = recruitment.analyze(root / f"traces/{key}.world.gz", root / f"traces/{key}.sites.gz",
            boundaries, experiment.read_json(root / f"input/{key}.population.json"),
            root / f"input/{key}.population.gz", c["capacity"], c["policy"])
        require(current == a, "original recruitment reanalysis differs: " + key)
        audit = experiment.read_json(audit_root / f"analyses/{key}.json")
        require(audit["header"] == attempts.expected_header(c), "wrong exact-attempt case identity")
        require(attempts.analyze(audit_root / f"traces/{key}.gz", root / f"traces/{key}.world.gz",
            root / f"traces/{key}.sites.gz", boundaries, audit["header"]) == audit,
            "original opportunity reanalysis differs: " + key)
        result = outcomes(a["world"]["lineages"], a["seeds"]["seeds"])
        require(result["all"]["counts"]["created"] == audit["windows"]["all"]["created"] and
                result["birth_cohort_reconciliation"]["all_closing_births"] == audit["windows"]["all"]["germinations"],
                "closing purchases/births differ from exact visits")
        with gzip.open(audit_root / f"traces/{key}.gz", "rt") as stream:
            visits = opportunities((json.loads(line) for line in stream), a["seeds"]["seeds"])
        for seed in result["seeds"]:
            seed["opportunities"] = dict(visits[seed["parent"], seed["purchase_tick"]])
        for parent in result["parents"]:
            total = Counter()
            for seed in result["seeds"]:
                if seed["parent"] == parent["id"]:
                    total.update(seed["opportunities"])
            parent["opportunities"] = dict(total)
        result["case_opportunities"] = audit["windows"]
        result["final_hash"] = a["world"]["final"]["hash"]
        output.append({"key": key, "capacity": c["capacity"], "seed": c["seed"],
                       "schedule": c["arm"], "policy": c["policy"], **result})
        checked.update(site_world_checkpoints=a["seeds"]["checkpoints_verified"],
            live_resource_steps=a["world"]["windows"]["whole"]["budget_checked_live_steps"],
            seed_lifetimes=len(a["seeds"]["seeds"]), exact_attempt_checkpoints=audit["checked"])
        print("Reverified and joined", key, result["all"]["counts"], flush=True)
    totals = {scope: {field: sum(c[scope]["counts"][field] for c in output)
                      for field in output[0][scope]["counts"]}
              for scope in ("all", "full_potential", "recent")}
    for name, root in roots.items():
        require(experiment.digest(root / "manifest.json") == INPUTS[name] and all(
            experiment.digest(root / path) == sha for path, sha in manifests[name]["artifacts"].items()),
            "input changed during analysis")
    return {"rule": RULE, "role": "exploratory-descendant-diagnostic-not-fitness", "input_manifests": INPUTS,
            "native_runs": 0, "training_runs": 0, "checks": dict(checked), "cases": output,
            "totals": totals, "examples": examples(output)}


def collect(roots, output):
    require(output.is_relative_to(experiment.ROOT / "artifacts") and not output.exists() and
            all(not output.is_relative_to(root) for root in roots.values()), "choose new artifacts output")
    sources = experiment.source_files()
    output.mkdir(parents=True)
    experiment.snapshot_sources(output, sources)
    shutil.copy2(experiment.ROOT / "benchmarks/garden-longevity/descendant-outcomes-protocol.md",
                 output / "protocol.md")
    started = {"rule": RULE, "input_manifests": INPUTS, "source_sha256": sources}
    experiment.write_json(output / "started.json", started)
    try:
        result = evaluate(roots)
        experiment.write_json(output / "results.json", result)
        require(experiment.source_files() == sources, "source changed during analysis")
        experiment.write_json(output / "manifest.json", started | {"status": "complete", "artifacts": {
            str(p.relative_to(output)): experiment.digest(p) for p in output.rglob("*") if p.is_file()}})
    except BaseException as error:
        experiment.write_json(output / "failure.json", {"error": str(error)})
        raise


def verify(roots, output, export=None):
    m = experiment.read_json(output / "manifest.json")
    require(m["rule"] == RULE and m["status"] == "complete" and m["input_manifests"] == INPUTS,
            "wrong/incomplete descendant bundle")
    for name in m["artifacts"]:
        recruitment.establishment.verified(output, m, name)
    result = evaluate(roots)
    require(result == experiment.read_json(output / "results.json"), "descendant reanalysis differs")
    if export is not None:
        experiment.write_json(export, result | {"manifest_sha256": experiment.digest(output / "manifest.json")})
    print("Verified every lineage, purchase, opportunity and descendant classification; no simulation")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--output", type=Path)
    group.add_argument("--verify", type=Path)
    parser.add_argument("--recruitment", type=Path, default=experiment.ROOT / "artifacts/garden-crowded-recruitment")
    parser.add_argument("--attempts", type=Path, default=experiment.ROOT / "artifacts/garden-seed-attempts")
    parser.add_argument("--export", type=Path)
    args = parser.parse_args()
    require(args.export is None or args.verify is not None, "export requires verification")
    roots = {name: getattr(args, name).resolve() for name in INPUTS}
    if args.verify:
        verify(roots, args.verify.resolve(), args.export)
    else:
        collect(roots, args.output.resolve())


if __name__ == "__main__":
    main()
