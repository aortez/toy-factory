#!/usr/bin/env python3
"""Offline diagnosis of saved reproduction-order regressions; never simulate."""

from __future__ import annotations

import argparse
from collections import Counter
import copy
import gzip
import json
from pathlib import Path
import sys

import garden_landing_order as previous
from garden_experiments import digest
from garden_resources import require

ROOT, DAY, STEP, AT, END, STOP = (previous.ROOT, previous.DAY, previous.STEP,
                                 previous.AT, previous.END, previous.STOP)
RULE = "garden-landing-order-regressions-v1"
PROTOCOL = "benchmarks/garden-seasons/landing-order-regressions-protocol.md"
INPUT = "benchmarks/garden-seasons/landing-order-results.json.gz"
INPUT_SHA = "65d240d896f7f6aeb014212fed502479b69e135b921f26d4a288e84b41cc4f32"
MANIFEST_SHA = "9075e770e5005c14ff1e2824626eedf013c3952acd0d7b04eab953809e5296f4"
EVENTS = "benchmarks/garden-seasons/landing-order-regressions-events.json.gz"
EVENTS_SHA = "4da3133d07920636f3bec1492943101dcba0b5219d8f64607e077efa4f68b800"
FOCUS = (("single-s6d697834-live", "vacancy"), ("single-s6d697835-live", "control"),
         ("multi-s6d697833-live", "control"))
ARMS = previous.ARMS
load = previous.bank.load


def selected(data):
    worlds = {w["model"]: w for w in data["worlds"]}
    require(len(worlds) == len(data["worlds"]) == 6, "wrong controller panel")
    return [(worlds[model], context) for model, context in FOCUS]


def event_ticks(pair):
    """Union of observed ecological events, not a handpicked outcome window."""
    ticks = {AT}
    for a in pair.values():
        for record in a["result"]["seeds"]:
            ticks.update(t for t in (record["birth_tick"], record["end_tick"]) if t and AT <= t <= END)
        for record in a["result"]["lineages"]:
            ticks.update(t for t in (record["birth_tick"], record["death_tick"]) if t and AT <= t <= END)
        ticks.update(e["tick"] for e in a["audit"]["order"]["openings"] if AT <= e["tick"] <= END)
    return sorted(ticks | {t - STEP for t in ticks if t > AT})


def header(kind, start=AT, stop=END):
    if kind == "adult":
        return {"schema": "landing-adult-resources-v1", "start": start, "stop": stop}
    return {"schema": "landing-ordered-stand-trace-v1", "node_limit": 32,
            "start": start, "stop": stop, "budget_mode": 2}


def footer(kind, result):
    return {"complete": True, "tick": STOP} | ({"run_hash": result["run_hash"]} if kind == "stand" else {})


def extract(bundle, data):
    require(not (bundle / "FAILED.txt").exists() and digest(bundle / "manifest.json") == MANIFEST_SHA and
            digest(bundle / "results.json.gz") == INPUT_SHA, "wrong/incomplete source bundle")
    manifest = json.loads((bundle / "manifest.json").read_text())
    require(manifest["rule"] == previous.RULE and manifest["status"] == "complete", "wrong manifest")
    cases = []
    for w, context in selected(data):
        pair, arms = w["contexts"][context], {}
        ticks = event_ticks(pair)
        for arm in ARMS:
            a = pair[arm]
            rows = {t: {"tick": t} for t in ticks}
            for kind in ("stand", "adult"):
                meta = a["traces"][kind]
                path = bundle / meta["path"]
                require(digest(path) == meta["sha256"] == manifest["artifacts"][meta["path"]], "trace identity differs")
                with gzip.open(path, "rt") as stream:
                    require(json.loads(next(stream)) == header(kind), "wrong trace header")
                    for tick in range(AT, END + STEP, STEP):
                        row = json.loads(next(stream))
                        require(type(row["tick"]) is int and row["tick"] == tick, "missing source clock")
                        if tick in rows:
                            rows[tick][kind] = row
                    require(json.loads(next(stream)) == footer(kind, a["result"]) and not stream.read(), "incomplete/trailing trace")
                require(digest(path) == meta["sha256"], "trace changed during extraction")
            arms[arm] = {"traces": a["traces"], "rows": list(rows.values())}
        cases.append({"id": w["id"], "model": w["model"], "context": context, "arms": arms})
    require(digest(bundle / "manifest.json") == MANIFEST_SHA, "source manifest changed")
    return {"rule": RULE + "-events", "input_sha256": INPUT_SHA, "manifest_sha256": MANIFEST_SHA,
            "protocol_sha256": digest(ROOT / PROTOCOL), "cases": cases}


def validate_events(data, events):
    require(events["rule"] == RULE + "-events" and events["input_sha256"] == INPUT_SHA and
            events["manifest_sha256"] == MANIFEST_SHA and events["protocol_sha256"] == digest(ROOT / PROTOCOL) and
            len(events["cases"]) == len(FOCUS), "wrong event provenance/panel")
    for (w, context), case in zip(selected(data), events["cases"], strict=True):
        require((case["id"], case["model"], case["context"]) == (w["id"], w["model"], context) and
                set(case["arms"]) == set(ARMS), "wrong focus identity")
        pair = w["contexts"][context]
        for arm in ARMS:
            a, raw = pair[arm], case["arms"][arm]
            require(raw["traces"] == a["traces"] and
                    [r["tick"] for r in raw["rows"]] == event_ticks(pair), "missing/reordered events")
            lives = {p["id"]: p for p in a["result"]["lineages"]}
            prior = None
            for row in raw["rows"]:
                tick = row["tick"]
                require(set(row) == {"tick", "stand", "adult"} and row["stand"]["tick"] == row["adult"]["tick"] == tick,
                        "event clocks differ")
                previous.analyze([header("stand", tick, tick), row["stand"], footer("stand", a["result"])],
                                 [header("adult", tick, tick), row["adult"], footer("adult", a["result"])], a["result"], arm)
                if prior and prior["tick"] + STEP == tick:
                    before = {p["id"]: p for p in prior["adult"]["plants"]}
                    for p in row["adult"]["plants"]:
                        old = before.get(p["id"])
                        previous.recovery.adults.transfers({"tick": tick, **p}, lives[p["id"]],
                                                          old["stages"][-1] if old else None)
                prior = row


def plant_view(a, plant):
    """All identities below are within one run; no post-divergence matching."""
    result = a["result"]
    birth = next((s for s in result["seeds"] if s["child_id"] == plant["id"]), None)
    children = [p for p in result["lineages"] if p["parent"] == plant["id"]]
    resources = next((p for p in a["audit"]["gates"]["resources"]["plants"] if p["id"] == plant["id"]), None)
    return {"life": plant, "birth_seed": birth, "first_day": previous.bank.child_status(plant, STOP),
            "confirmed_children": [p["id"] for p in children if previous.bank.child_status(p, STOP) == "confirmed"],
            "resource_window": {k: resources[k] for k in ("first_tick", "last_tick", "left_censored", "right_censored",
                "first_shortage_tick", "death_shortage", "resources")} if resources else None}


def seed_view(a, seed):
    child = next((p for p in a["result"]["lineages"] if p["id"] == seed["child_id"]), None)
    trace = next((s for s in a["audit"]["gates"]["resources"]["seeds"] if
                  (s["parent"], s["birth_tick"]) == (seed["parent"], seed["birth_tick"])), None)
    return {"seed": seed, "child": plant_view(a, child) if child else None,
            "observed_checks": {"start": AT, "stop": END, "samples": trace["samples"],
                "mature_masks": trace["mature_masks"], "open_elsewhere_checks": trace["open_elsewhere_checks"]} if trace else None}


def cohort(a, start, stop):
    require(AT <= start < stop <= STOP and start % STEP == stop % STEP == 0, "invalid cohort")
    r = a["result"]
    children = [plant_view(a, p) for p in r["lineages"] if start < p["birth_tick"] <= stop]
    purchases = [seed_view(a, s) for s in r["seeds"] if start < s["birth_tick"] <= stop]
    carry_in = [seed_view(a, s) for s in r["seeds"] if s["birth_tick"] <= start and
                (s["end_tick"] is None or s["end_tick"] > start)]
    return {"window": [start, stop], "children": children, "purchases": purchases, "carry_in": carry_in,
            "birth_outcomes": dict(Counter(p["first_day"] for p in children)),
            "purchase_outcomes": dict(Counter(s["seed"]["outcome"] for s in purchases)),
            "confirmations": [p["id"] for p in r["lineages"] if start < p["birth_tick"] + DAY <= stop and
                              previous.bank.child_status(p, STOP) == "confirmed"],
            "natural_deaths": [p["id"] for p in r["lineages"] if p["death_tick"] and start < p["death_tick"] <= stop]}


def first_change(pair):
    openings = [{e["tick"]: e for e in pair[a]["audit"]["order"]["openings"]} for a in ARMS]
    for tick in sorted(set(openings[0]) | set(openings[1])):
        if openings[0].get(tick, {}).get("buyers", []) != openings[1].get(tick, {}).get("buyers", []):
            return {"tick": tick, "arms": {arm: {"opening": openings[i].get(tick),
                "purchases": [seed_view(pair[arm], s) for s in pair[arm]["result"]["seeds"] if s["birth_tick"] == tick]}
                for i, arm in enumerate(ARMS)}}
    return None


def pre_purchase(row):
    """Only observed state before the reproduction debit, not a world hash."""
    value = copy.deepcopy(row)
    visits = value["stand"]["reproduction"]
    value["adult"]["bank"] = visits[0]["bank"] if visits else 0
    for v in visits:
        v.pop("bank")
        v.pop("produced")
        v["blockers"] &= ~previous.bank.BANK
    value["stand"]["reproduction"] = sorted(visits, key=lambda v: v["id"])
    for p in value["adult"]["plants"]:
        p["stages"] = p["stages"][:4]
    return value


def bank_timeline(pair, case, cutoff):
    rows = {arm: {r["tick"]: r for r in case["arms"][arm]["rows"]} for arm in ARMS}
    timeline = []
    for tick in event_ticks(pair):
        if tick > cutoff:
            continue
        entry = {"tick": tick, "arms": {}}
        active = False
        for arm in ARMS:
            a, raw = pair[arm], rows[arm][tick]
            bought = [s for s in a["result"]["seeds"] if s["birth_tick"] == tick]
            exited = [s for s in a["result"]["seeds"] if s["end_tick"] == tick]
            lives = a["result"]["lineages"]
            born = [p["id"] for p in lives if p["birth_tick"] == tick]
            dead = [p["id"] for p in lives if p["death_tick"] == tick]
            active |= bool(bought or exited or born or dead)
            visits = raw["stand"]["reproduction"]
            entry["arms"][arm] = {"bank_at_entry": visits[0]["bank"] if visits else 0,
                "bank_after": raw["adult"]["bank"], "purchases": bought, "exits": exited,
                "births": born, "deaths": dead, "visits": visits}
        if active:
            timeline.append(entry)
    return timeline


def ancestry(a, identity):
    lives = {p["id"]: p for p in a["result"]["lineages"]}
    chain, seen = [], set()
    while identity:
        require(identity in lives and identity not in seen, "missing/cyclic ancestry")
        seen.add(identity)
        p = lives[identity]
        chain.append({k: p[k] for k in ("id", "parent", "birth_tick", "column", "generation")} | {
            "birth_seed": next((s for s in a["result"]["seeds"] if s["child_id"] == identity), None)})
        identity = p["parent"]
    return list(reversed(chain))


def opening_misses(a, raw):
    rows = {r["tick"]: r for r in raw["rows"]}
    early = previous.outcomes(a["result"])["early_survivors"]
    ranks = {p["id"]: p for p in a["audit"]["order"]["ranks"]}
    plants = {p["id"]: p for p in a["audit"]["order"]["access"]["plants"]}
    seeds = {(s["parent"], s["birth_tick"]): s for s in a["result"]["seeds"]}
    result = []
    for identity in early:
        p, misses = plants[identity], []
        for miss in p["missed_openings"]:
            row = rows[miss["tick"]]
            visit = row["stand"]["reproduction"][miss["rank"]]
            require(visit == dict(zip(previous.bank.FIELDS, miss["visit"], strict=True)) and
                    visit["id"] == identity and visit["blockers"] == previous.bank.BANK, "missed visit differs")
            misses.append({"tick": miss["tick"], "rank": miss["rank"], "bank_at_entry": miss["bank_at_entry"],
                "visit": visit, "earlier_buyers": miss["earlier_buyers"],
                "released_seeds": [seed_view(a, seeds[tuple(k)]) for k in miss["released_seeds"]],
                "purchased_seeds": [seed_view(a, seeds[(i, miss["tick"])]) for i in miss["earlier_buyers"]]})
        result.append({"id": identity, "ranks": ranks[identity], "access": p["access"], "misses": misses})
    return result


def summary(a):
    o = previous.outcomes(a["result"])
    return {k: len(o[k]) for k in ("early_survivors", "early_successful_parents", "reproducing_replacements", "living_at_stop")} | {
        "birth_outcomes": o["birth_outcomes"], "post_boundary_deaths": o["post_boundary_deaths"],
        "periods": [{"days": p["days"], "births": len(p["births"]), "birth_outcomes": p["birth_outcomes"],
                     "confirmations": len(p["confirmations"]), "natural_deaths": len(p["natural_deaths"])} for p in o["periods"]]}


def incumbents(a):
    resources = {p["id"]: p for p in a["audit"]["gates"]["resources"]["plants"]}
    return [{"plant": plant_view(a, p), "days": resources[p["id"]]["days"]}
            for p in a["result"]["lineages"] if p["birth_tick"] <= AT and
            (p["death_tick"] is None or p["death_tick"] > AT) and p.get("removal_tick", AT) >= AT]


def analyze(data, events):
    previous.check_value(data)
    validate_events(data, events)
    cases = []
    for (w, context), case in zip(selected(data), events["cases"], strict=True):
        pair = w["contexts"][context]
        first = first_change(pair)
        require(first is not None and first["tick"] > AT, "no post-switch allocation divergence")
        samples = {arm: {r["tick"]: r for r in case["arms"][arm]["rows"]} for arm in ARMS}
        first["previous_observations_equal"] = samples["fixed"][first["tick"] - STEP] == samples["rotating"][first["tick"] - STEP]
        first["pre_purchase_observations_equal"] = pre_purchase(samples["fixed"][first["tick"]]) == pre_purchase(samples["rotating"][first["tick"]])
        require(first["previous_observations_equal"] and first["pre_purchase_observations_equal"],
                "observed state diverges before first changed allocation")
        arms = {}
        for arm in ARMS:
            a = pair[arm]
            early, closing, tail = cohort(a, AT, 190 * DAY), cohort(a, 222 * DAY, 254 * DAY), cohort(a, 254 * DAY, STOP)
            born = [p for p in a["result"]["lineages"] if p["birth_tick"] > AT]
            arms[arm] = {"result_run_hash": a["result"]["run_hash"], "summary": summary(a), "early": early,
                "closing": closing, "tail": tail, "new_plants": [plant_view(a, p) for p in born],
                "incumbents": incumbents(a),
                "ancestry": [{"id": p["id"], "path": ancestry(a, p["id"])} for p in born],
                "early_opening_misses": opening_misses(a, case["arms"][arm])}
        cases.append({"id": w["id"], "model": w["model"], "context": context,
                      "first_allocation_change": first, "early_bank_timeline": bank_timeline(pair, case, 190 * DAY), "arms": arms})
    return {"rule": RULE, "input_sha256": INPUT_SHA, "events_sha256": EVENTS_SHA,
        "protocol_sha256": digest(ROOT / PROTOCOL), "native_runs": 0, "training_runs": 0,
        "trace_window": [AT, END], "followup_tick": STOP,
        "screen_unchanged": previous.summarize(data["worlds"]),
        "panel": [{"model": w["model"], "context": context,
                   "arms": {arm: summary(pair[arm]) for arm in ARMS}}
                  for w in data["worlds"] for context, pair in w["contexts"].items()],
        "cases": cases}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / INPUT)
    parser.add_argument("--events", type=Path, default=ROOT / EVENTS)
    parser.add_argument("--extract-from", type=Path, help="read the frozen raw bundle; never simulate")
    output = parser.add_mutually_exclusive_group(required=True)
    output.add_argument("--out", type=Path)
    output.add_argument("--verify", type=Path)
    args = parser.parse_args()
    try:
        require(args.out is None or not args.out.exists(), "fresh output required")
        data = load(args.input, INPUT_SHA)
        if args.extract_from:
            previous.check_value(data)
            value = extract(args.extract_from, data)
            validate_events(data, value)
        else:
            value = analyze(data, load(args.events, EVENTS_SHA))
        require(digest(args.input) == INPUT_SHA and (args.extract_from or digest(args.events) == EVENTS_SHA), "input changed")
        if args.verify:
            with gzip.open(args.verify, "rt") as stream:
                require(json.load(stream) == value, "saved regression audit differs")
            print("Verified saved event extraction; no simulation." if args.extract_from else
                  "Verified full-panel outcomes, allocation events, resource costs and censored regressions; no simulation.")
        else:
            previous.recovery.founders.write_gzip(args.out, value)
        return 0
    except (OSError, RuntimeError, ValueError, KeyError, TypeError, StopIteration) as error:
        print("order regression audit failed: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
