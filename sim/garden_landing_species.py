#!/usr/bin/env python3
"""Offline species, survival and allocation audit of the frozen construction screen."""

from __future__ import annotations

import argparse
from collections import Counter
import gzip
import json
from pathlib import Path
import sys

import garden_landing_growth as previous
from garden_experiments import digest
from garden_resources import require

ROOT, DAY, STEP, STOP = previous.ROOT, previous.DAY, previous.STEP, previous.STOP
RULE = "garden-landing-species-v1"
INPUT = "benchmarks/garden-seasons/landing-growth-results.json.gz"
INPUT_SHA = "9027651cd3da4d8a9a8703ef7a78d4ecc351faef35ece5fe4f2ee43f5605d2da"
SPECIES = ("flower", "shrub", "ground-cover")
ARMS = tuple(previous.ARMS)
AGES = (DAY, 8 * DAY, 32 * DAY)
BODY_AGES = (DAY // 8, DAY)
recruitment, rolling = previous.recruitment, previous.training.rolling
lifetimes = previous.turnover.lifetimes


def load(path):
    require(digest(path) == INPUT_SHA, "wrong frozen construction panel")
    return json.loads(gzip.decompress(path.read_bytes()))


def survival(plants, age, stop):
    """Fixed-age cohort; late births are excluded even if their early death is known."""
    require(type(age) is int and type(stop) is int and age > 0 and stop >= 0 and
            age % STEP == stop % STEP == 0, "invalid survival clock")
    observed = [p for p in plants if p["birth_tick"] + age <= stop]
    alive = sum(lifetimes.alive(p, p["birth_tick"] + age) for p in observed)
    return {"cohort": len(plants), "full_possible_followup": len(observed), "alive_at_age": alive,
            "died_by_age": len(observed) - alive, "insufficient_possible_followup": len(plants) - len(observed)}


def body_at_age(plant, age, stop):
    """Living, post-ecology morphology at an exact age, not a last-seen average."""
    require(age in BODY_AGES, "unsupported body age")
    tick = plant["birth_tick"] + age
    if tick > stop:
        return {"status": "insufficient-followup"}
    if not lifetimes.alive(plant, tick):
        return {"status": "dead"}
    rows = [r for r in plant["rows"] if r["tick"] == tick]
    require(len(rows) == 1, "missing/duplicate fixed-age body")
    row = rows[0]
    energy, water, stress, flags, nodes = row["stages"][-1]
    roots, leaves = row["roots"], row["active_leaves"]
    require(not flags & 1 and 0 <= roots <= nodes and 0 <= leaves <= nodes - roots,
            "invalid living morphology")
    return {"status": "observed", "tick": tick, "nodes": nodes, "roots": roots,
            "above_ground": nodes - roots, "active_leaves": leaves,
            "energy": energy, "water": water, "stress": stress,
            "energy_due_per_payment": (nodes + 7) // 8,
            "water_due_per_payment": (nodes - roots + 7) // 8}


def distribution(values):
    return {"count": len(values), "sum": sum(values),
            "minimum": min(values, default=None), "maximum": max(values, default=None)}


def body_summary(children, age):
    bodies = [p["first_day"]["bodies"][str(age)] for p in children]
    living = [b for b in bodies if b["status"] == "observed"]
    fields = ("nodes", "roots", "above_ground", "active_leaves", "energy", "water", "stress",
              "energy_due_per_payment", "water_due_per_payment")
    return {"cohort": len(bodies), "coverage": dict(sorted(Counter(b["status"] for b in bodies).items())),
            "living_only": {k: distribution([b[k] for b in living]) for k in fields}}


def species_summary(plants, seeds, periods):
    groups = {}
    for species, name in enumerate(SPECIES):
        selected = [p for p in plants if p["species"] == species]
        founders = [p for p in selected if not p["parent"]]
        children = [p for p in selected if p["parent"]]
        late = [p for p in children if 62 * DAY < p["birth_tick"] <= 190 * DAY]
        seed_rows = [s for s in seeds if s["species"] == species]
        def cohort(rows):
            return {"births": len(rows),
                    "outcomes": dict(sorted(Counter(p["first_day"]["outcome"] for p in rows).items())),
                    "death_shortages": dict(sorted(Counter(p["first_day"]["death_shortage"] for p in rows
                        if p["first_day"]["outcome"] == "died").items()))}
        groups[name] = {
            "plants": len(selected), "founders": len(founders), "births": len(children),
            "founders_alive_at_end": sum(lifetimes.alive(p, STOP) for p in founders),
            "descendants_alive_at_end": sum(lifetimes.alive(p, STOP) for p in children),
            "seed_producing_founders": sum(p["seeds_created"] > 0 for p in founders),
            "seed_producing_descendants": sum(p["seeds_created"] > 0 for p in children),
            "founder_survival": {str(t): survival(founders, t, STOP) for t in (*AGES, STOP)},
            "descendant_survival": {str(t): survival(children, t, STOP) for t in AGES},
            "seeds": recruitment.seed_summary(seed_rows),
            "first_day": cohort(children), "late_first_day": cohort(late),
            "bodies": {str(t): body_summary(children, t) for t in BODY_AGES},
            "credit_ticks": sum(p["species"][name]["credit_ticks"] for p in periods),
            "fresh_renewal_confirmations": sum(p["species"][name]["fresh_confirmations"] for p in periods)}
    return groups


def analyze_arm(source, arm, case, model, *, normalize=previous.common_view):
    result = source["result"]
    normalized = normalize(result, arm)
    history = previous.training.score_world(normalized, case, model)
    require(history == source["history"] and result["tick"] == STOP and result["ledger_start_tick"] == 0,
            "saved history/horizon differs")
    rolling.descendants.index_records(result["lineages"], result["seeds"], 0, STOP)
    # index_records validates ancestry and seed/child identity; species inheritance
    # is an additional invariant of this audit, not a new ecological restriction.
    plants = {p["id"]: p for p in result["lineages"]}
    require(all(type(p["species"]) is int and 0 <= p["species"] < len(SPECIES) and
                (not p["parent"] or p["species"] == plants[p["parent"]]["species"])
                for p in plants.values()), "invalid plant species inheritance")
    require(all(type(s["species"]) is int and s["species"] == plants[s["parent"]]["species"] and
                (s["child_id"] is None or s["species"] == plants[s["child_id"]]["species"])
                for s in result["seeds"]), "invalid seed species inheritance")
    audits, seeds = source["audit"]["plants"], source["audit"]["seeds"]
    require(len(audits) == sum(bool(p["parent"]) for p in plants.values()) and
            {p["id"] for p in audits} == {p["id"] for p in plants.values() if p["parent"]},
            "missing/duplicate child audit")
    require(len(seeds) == len(result["seeds"]) and
            [{k: s[k] for k in original} for s, original in zip(seeds, result["seeds"], strict=True)] == result["seeds"],
            "seed audit ledger differs")
    require(recruitment.seed_summary(seeds) == source["audit"]["summary"]["all_seeds"], "seed masks differ")
    require(source["metrics"] == previous.scoring.metrics(result, source["audit"], history), "saved metrics differ")
    facts = {p["id"]: {**p, "first_day": None} for p in plants.values()}
    for p in audits:
        require({k: p[k] for k in plants[p["id"]]} == plants[p["id"]], "child audit lineage differs")
        checked = dict(p)
        recruitment.analyze_child(checked, STOP)
        require(checked == p, "first-day accounting differs")
        facts[p["id"]]["first_day"] = {k: p[k] for k in ("outcome", "death_shortage", "resources")} | {
            "bodies": {str(t): body_at_age(p, t, STOP) for t in BODY_AGES}}
    periods = []
    for block in history["blocks"]:
        groups = {name: {"credit_ticks": sum(c["live_ticks"] for c in block["rolling"]["children"]
                                            if plants[c["id"]]["species"] == species),
                         "fresh_confirmations": sum(not c["carry_in"] for c in block["rolling"]["children"]
                                                    if plants[c["id"]]["species"] == species)}
                  for species, name in enumerate(SPECIES)}
        require(sum(s["credit_ticks"] for s in groups.values()) == block["rolling"]["ticks"], "credit partition differs")
        periods.append({"days": block["days"], "species": groups})
    require(sum(p["species"][s]["fresh_confirmations"] for p in periods for s in SPECIES) ==
            source["metrics"]["late_renewal_confirmations"], "confirmation partition differs")
    ordered = sorted(facts.values(), key=lambda p: p["id"])
    value = {"world_hash": result["world_hash"], "trace_sha256": source["trace_sha256"],
             "unchanged_history": history, "unchanged_metrics": source["metrics"],
             "plants": ordered, "periods": periods, "species": species_summary(ordered, seeds, periods),
             "whole_run_seed_checks": recruitment.seed_summary(seeds)}
    if "focus" in source:
        focus = source["focus"]
        require(focus["audit"] == previous.adults.analyze(focus["trace"], result), "adult accounting differs")
        value["focus_day_125"] = [{k: p[k] for k in ("id", "parent", "species", "birth_tick", "death_tick")} | {
            "receipts": p["days"]["125"]} for p in focus["audit"]["plants"] if "125" in p["days"]]
    return value


def analyze(data):
    require(data["rule"] == previous.RULE and data["arms"] == previous.ARMS and
            data["objective"] == previous.training.individual.RULE and data["training_runs"] == 0 and
            data["repeat_verified"] is True and len(data["worlds"]) == 12 and
            len({w["id"] for w in data["worlds"]}) == 12 and
            [{k: w[k] for k in ("id", "model", "case")} for w in data["worlds"]] == data["plan"],
            "wrong frozen panel")
    worlds = []
    for w in data["worlds"]:
        require(set(w["arms"]) == set(ARMS) and
                previous.common_view(w["initial"]["off"], "off") == previous.common_view(w["initial"]["32"], "32"),
                "unmatched initial biology")
        initial = w["initial"]["off"]["lineages"]
        arms = {a: analyze_arm(w["arms"][a], a, w["case"], data["models"][w["model"]]["metadata"]) for a in ARMS}
        matched = []
        for p in initial:
            require(p["parent"] == 0 and p["birth_tick"] == 0, "nonfounder initial plant")
            pair = {a: next(q for q in arms[a]["plants"] if q["id"] == p["id"]) for a in ARMS}
            require(all(all(q[k] == p[k] for k in ("id", "parent", "species", "generation", "column", "birth_tick"))
                        for q in pair.values()), "unmatched founder identity")
            matched.append({"id": p["id"], "species": p["species"], "arms": {
                a: {k: q[k] for k in ("death_tick", "seeds_created")} for a, q in pair.items()}})
        worlds.append({k: w[k] for k in ("id", "model", "case")} | {"arms": arms, "matched_founders": matched})
    groups = {}
    for climate in ("steady", "seasonal"):
        selected = [(old, new) for old, new in zip(data["worlds"], worlds, strict=True) if new["case"]["climate"] == climate]
        require(len(selected) == 6, "incomplete climate panel")
        groups[climate] = {a: species_summary([p for _, w in selected for p in w["arms"][a]["plants"]],
            [s for old, _ in selected for s in old["arms"][a]["audit"]["seeds"]],
            [p for _, w in selected for p in w["arms"][a]["periods"]]) for a in ARMS}
    return {"rule": RULE, "input": INPUT, "input_sha256": INPUT_SHA, "native_runs": 0, "training_runs": 0,
            "stop_tick": STOP, "species_names": list(SPECIES), "worlds": worlds, "groups": groups,
            "unchanged_comparison": data["comparison"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / INPUT)
    output = parser.add_mutually_exclusive_group(required=True)
    output.add_argument("--out", type=Path)
    output.add_argument("--verify", type=Path)
    args = parser.parse_args()
    try:
        require(args.out is None or not args.out.exists(), "fresh output required")
        value = analyze(load(args.input))
        require(digest(args.input) == INPUT_SHA, "input changed during diagnosis")
        if args.verify:
            raw = args.verify.read_bytes()
            require(json.loads(gzip.decompress(raw) if args.verify.suffix == ".gz" else raw) == value,
                    "saved species diagnosis differs")
            print("Verified 24 species censuses, matched founders, age cohorts, allocation and unchanged scores; no simulation.")
        else:
            raw = (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()
            with args.out.open("xb") as stream:
                if args.out.suffix == ".gz":
                    with gzip.GzipFile(filename="", fileobj=stream, mode="wb", mtime=0) as zipped:
                        zipped.write(raw)
                else:
                    stream.write(raw)
        return 0
    except (OSError, ValueError, RuntimeError, StopIteration, KeyError, TypeError) as error:
        print("species diagnosis failed: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
