#!/usr/bin/env python3
"""Test a current-light dawn reserve in five fixed pairs; forty calls, no training."""

from __future__ import annotations

import argparse
from collections import Counter
import copy
from functools import cache
from pathlib import Path
import sys

import garden_landing_daylight as previous
import garden_landing_dawn_audit as audit
from garden_resources import require

root, order, adults, prior, late = previous.root, previous.order, previous.adults, previous.prior, previous.late
ROOT, DAY, STEP, STOP = previous.ROOT, previous.DAY, previous.STEP, previous.STOP
CASES, ARMS, LABELS, KINDS = previous.CASES, previous.ARMS, previous.LABELS, previous.KINDS
RULE = "garden-landing-dawn-v1"
PROTOCOL = "benchmarks/garden-seasons/landing-dawn-protocol.md"
INPUT, INPUT_SHA = audit.INPUT, audit.INPUT_SHA
MANIFEST_SHA = "bab1fbfa18f0430c15557de67cf26d2f351c21661e03870cb8e735ffe961dba0"
AUDIT = "benchmarks/garden-seasons/landing-dawn-audit-results.json.gz"
AUDIT_SHA = "6cdfc3ae4318042a6d40d983f369463771e9f326f86a3a7c75a2d67003ee3c88"
INPUTS = {**previous.INPUTS, INPUT: INPUT_SHA, AUDIT: AUDIT_SHA}
SCHEMA = "landing-dawn-stand-trace-v1"
steps = previous.previous.steps


@cache
def load_inputs():
    data, world, _, model = previous.load_inputs()
    saved = audit.load_input()
    require(root.digest(ROOT / AUDIT) == AUDIT_SHA, "motivating dawn audit changed")
    return data, world, saved, model


def dawn_hash(base):
    h = 2166136261
    for byte in b"GLM1" + int(base, 16).to_bytes(4, "little"):
        h = ((h ^ byte) * 16777619) & 0xffffffff
    return f"{h:08x}"


def daylight_result(result, case, arm):
    require(arm in ARMS, "unknown dawn arm")
    value = copy.deepcopy(result)
    if arm == "candidate":
        placing = order.previous.placement
        expected = placing.probe_hash(placing.budget.probe_hash(value["base_run_hash"], 2), True)
        if case["order"] == "rotating":
            expected = order.order_hash(expected, prior.AT)
        afternoon = previous.afternoon
        expected = previous.daylight_hash(previous.previous.continuous_hash(afternoon.afternoon_hash(
            afternoon.previous.energy_hash(root.probe_hash(expected, case["tick"], case["lineage"])))))
        require(value.get("root_dawn_reserve_probe") == {"version": 1} and
                type(value["root_dawn_reserve_probe"]["version"]) is int and
                value["run_hash"] == dawn_hash(expected), "wrong dawn identity")
        del value["root_dawn_reserve_probe"]
        value["run_hash"] = expected
    else:
        require("root_dawn_reserve_probe" not in value, "dawn guard in control")
    previous.continuous_result(value, case, "candidate")
    return value


def arguments(world, case, arm, label):
    require(case in CASES and arm in ARMS and label in LABELS, "wrong frozen dawn call")
    args = previous.arguments(world, case, "candidate", label)
    old, new = root.stem(case, "candidate", label), root.stem(case, arm, label)
    args = [a.replace(old, new) for a in args]
    if label in ("trace", "repeat"):
        args[args.index("--stand-daylight")] = "--stand-dawn"
    return args + (["--root-dawn-reserve"] if arm == "candidate" else [])


def strip_dawn(rows):
    return [{**s, "bids": [{k: v for k, v in b.items() if k != "dawn_gate"} for b in s["bids"]]} for s in rows]


def daylight_stand(rows, result, case, arm):
    normal = daylight_result(result, case, arm)
    require(rows[0] == {**prior.header("stand", case["tick"] - STEP, STOP), "schema": SCHEMA} and
            rows[-1] == {"complete": True, "tick": STOP, "run_hash": result["run_hash"]}, "wrong dawn trace identity")
    return [{**rows[0], "schema": previous.SCHEMA}, *strip_dawn(rows[1:-1]),
            {**rows[-1], "run_hash": normal["run_hash"]}]


def expected_dawn(bid, arm):
    """Independent Python arithmetic; old receipts are validated by the caller."""
    require(arm in ARMS, "unknown dawn arm")
    e, light, afternoon = bid["energy_gate"], bid["daylight_gate"], bid["afternoon_gate"]
    active = arm == "candidate" and e["active"]
    result = {"active": active, "allowed": True, "applies": bid["action"] != 0 and 64 <= e["sun_phase"] < 128,
              "forecast_allowed": True, "estimate_available": False, "first_light_phase": 0,
              "payment_phase": 0, "reserve": 0, "projected_margin": 0, "stores_applies": False, "stores_margin": 0}
    if result["applies"]:
        forecast = audit.diagnostic(e["sun_phase"], light["sun_strength"], e["maintenance"])
        result["stores_applies"] = afternoon["applies"]
        result["estimate_available"] = forecast["status"] == "estimated"
        result["forecast_allowed"] = False
        if result["estimate_available"]:
            reserve = forecast["reserve"]
            margin = light["projected_sunset"] - e["night_upkeep"] - reserve
            stores = afternoon["margin"] - reserve if afternoon["applies"] else 0
            result.update(first_light_phase=forecast["first_phase"], payment_phase=forecast["payment_phase"],
                          reserve=reserve, projected_margin=margin, stores_margin=stores,
                          forecast_allowed=margin >= 0 and (not afternoon["applies"] or stores >= 0))
        result["allowed"] = not active or result["forecast_allowed"]
    return result


def check_dawn(bid, life, tick, case, arm, sun):
    previous.check_daylight(bid, life, tick, case, "candidate", sun)
    expected, actual = expected_dawn(bid, arm), bid["dawn_gate"]
    require(set(actual) == set(expected) and all(type(actual[k]) is type(v) for k, v in expected.items()) and
            actual == expected, "dawn arithmetic/scope differs")


def winner(bids, *, dawn):
    return previous.winner(bids, daylight=True, extra_allowed=(lambda b: b["dawn_gate"]["allowed"]) if dawn else None)


def check_row(row, resource, lives, case, arm):
    components = previous.check_row(row, resource, lives, case, "candidate",
                                     extra_allowed=lambda b: b["dawn_gate"]["allowed"])
    counts, changes = Counter(), []
    for b in row["bids"]:
        check_dawn(b, lives[b["id"]], row["tick"], case, arm, resource["sun"])
        d = b["dawn_gate"]
        if d["active"]:
            counts["active"] += 1
            counts["applicable"] += d["applies"]
            counts["unavailable"] += d["applies"] and not d["estimate_available"]
            counts["denied"] += not d["allowed"]
            counts["additional_denied"] += not d["allowed"] and all(b[g]["allowed"] for g in
                ("budget", "water_gate", "energy_gate", "afternoon_gate", "daylight_gate"))
    for lineage in sorted({b["id"] for b in row["bids"]}):
        bids = [b for b in row["bids"] if b["id"] == lineage]
        before, after = winner(bids, dawn=False), winner(bids, dawn=True)
        if before != after:
            require(arm == "candidate" and lineage == case["lineage"], "out-of-scope dawn choice")
            changes.append({"tick": row["tick"], "id": lineage, "before": before, "after": after})
    return *components, counts, changes


def shortages(history, life):
    """Only actual maintenance payments; stale flags at intervening ticks do not count."""
    events, before, roots = [], None, None
    for s in history:
        plant, tick = s["plant"], s["tick"]
        receipt = adults.transfers({"tick": tick, **plant}, life, before)
        if plant["uptake"] is not None and tick % (4 * STEP) == 0:
            n = plant["stages"][0][4]
            require(roots is not None and 0 <= roots <= n, "missing pre-maintenance roots")
            event = {"tick": tick, "phase": s["sun"][0], "nodes": n, "roots": roots}
            for index, (name, body, flag) in enumerate((("energy", n, 2), ("water", n - roots, 4))):
                due = (body + 7) // 8
                paid = receipt[name]["upkeep"]
                require(paid == min(due, plant["stages"][0][index]) and
                        bool(plant["stages"][1][3] & flag) == (paid < due), "shortage payment differs")
                event[name] = {"due": due, "paid": paid, "unpaid": due - paid}
            if any(event[name]["unpaid"] for name in ("energy", "water")):
                events.append(event)
        roots, before = plant["roots"], plant["stages"][-1]
    return events


def analyze(stand, resources, result, case, arm):
    normal = daylight_result(result, case, arm)
    legacy = daylight_stand(stand, result, case, arm)
    extended = [legacy[0], *stand[1:-1], legacy[-1]]
    base = previous.analyze(extended, resources, normal, case, "candidate",
        extra_allowed=lambda b: b["dawn_gate"]["allowed"], legacy_stand=legacy)
    lives, counts, changes = {p["id"]: p for p in result["lineages"]}, Counter(), []
    for row, resource in zip(stand[1:-1], resources[1:-1], strict=True):
        *_, c, changed = check_row(row, resource, lives, case, arm)
        counts.update(c)
        changes.extend(changed)
    return {**base, "dawn": {"counts": dict(sorted(counts.items())), "changed_choices": changes,
            "shortages": shortages(steps(base), base["focal"]["life"])}}


def historical_check(reference, saved, case, rows, result):
    metadata = next(c for c in saved["cases"] if c["case"] == case)["arms"]["candidate"]["traces"]
    projected = daylight_stand(rows[0], result, case, "control")
    for kind, records in zip(KINDS, (projected, rows[1]), strict=True):
        path = reference / metadata[kind]["path"]
        require(root.digest(path) == metadata[kind]["sha256"] and adults.read_trace(path) == records,
                "historical daylight trace changed")
        require(root.digest(path) == metadata[kind]["sha256"], "historical trace changed during read")
    return metadata


def first_effect(case, arms):
    changes = arms["candidate"]["analysis"]["dawn"]["changed_choices"]
    if not changes:
        return None
    change = changes[0]
    tick = change["tick"]
    rows = [steps(arms[a]["analysis"]) for a in ARMS]
    before = [[s for s in history if s["tick"] < tick] for history in rows]
    require(strip_dawn(before[0]) == strip_dawn(before[1]), "histories differ before first dawn choice")
    a, b = [next(s for s in history if s["tick"] == tick) for history in rows]
    require(strip_dawn([a])[0]["bids"] == strip_dawn([b])[0]["bids"] and
            a["plant"]["stages"][:3] == b["plant"]["stages"][:3] and a["sun"] == b["sun"],
            "first dawn choice lacks matching pre-action state")
    return {**change, "matching_prior_focal_samples": len(before[0]), "phase": b["sun"][0],
            "bids": b["bids"], "control_stages": a["plant"]["stages"], "candidate_stages": b["plant"]["stages"]}


def check_pair(case, arms, saved):
    a, b = [arms[arm] for arm in ARMS]
    old = next(c for c in saved["cases"] if c["case"] == case)["arms"]["candidate"]
    require(a["runs"] == old["runs"], "historical daylight checkpoints changed")
    projected = {k: v for k, v in a["analysis"].items() if k != "dawn"}
    projected["focal"] = {**projected["focal"], "steps": strip_dawn(projected["focal"]["steps"])}
    projected["followup_steps"] = strip_dawn(projected["followup_steps"])
    require(projected == old["analysis"], "historical daylight analysis changed")
    require(a["runs"]["prefix"]["result"] == daylight_result(b["runs"]["prefix"]["result"], case, "candidate") and
            a["runs"]["prefix"]["frame"] == b["runs"]["prefix"]["frame"], "post-root prefix changed")
    fa, fb = [x["analysis"]["focal"] for x in (a, b)]
    require(fa["seed"] == fb["seed"] and fa["birth_check"] == fb["birth_check"] and
            strip_dawn(fa["steps"][:1]) == strip_dawn(fb["steps"][:1]) and
            fa["steps"][0]["body"]["roots"] == fb["steps"][0]["body"]["roots"] == 3, "initial root differs")
    if first_effect(case, arms) is None:
        require(strip_dawn(steps(a["analysis"])) == strip_dawn(steps(b["analysis"])), "inactive dawn choices changed history")
        for label in LABELS:
            require(a["runs"][label]["result"] == daylight_result(b["runs"][label]["result"], case, "candidate") and
                    a["runs"][label]["frame"] == b["runs"][label]["frame"], "inactive treatment changed world")
    for arm, entry in arms.items():
        require(entry["runs"]["trace"] == entry["runs"]["repeat"], "dawn repeat differs")
        focal = entry["analysis"]["focal"]
        require(focal["first_day"] == late.history_summary(focal["life"], focal["steps"]), "first-day budget differs")
        for label, run in entry["runs"].items():
            daylight_result(run["result"], case, arm)
            require(run["result"]["tick"] == {"prefix": case["tick"], "day1": case["tick"] + DAY}.get(label, STOP), "wrong checkpoint")
        observed = next(p for p in entry["runs"]["day1"]["result"]["lineages"] if p["id"] == case["lineage"])
        death = focal["life"]["death_tick"]
        require(observed["death_tick"] == (death if death and death <= case["tick"] + DAY else None), "day-one outcome differs")


def check_value(value):
    data, world, saved, _ = load_inputs()
    require(value["rule"] == RULE and value["inputs"] == INPUTS and value["world"] == world["case"] and
            value["protocol_sha256"] == root.digest(ROOT / PROTOCOL) and value["model"] == data["models"][late.MODEL] and
            value["full_replays"] == value["checkpoint_replays"] == 20 and value["training_runs"] == 0 and
            len(value["cases"]) == len(CASES) and set(value["build"]) == {"binary", "cache"} and
            value["source_sha256"].get(PROTOCOL) == value["protocol_sha256"], "wrong dawn provenance/budget")
    for case, entry in zip(CASES, value["cases"], strict=True):
        require(entry["case"] == case and set(entry["arms"]) == set(ARMS), "wrong dawn panel")
        check_pair(case, entry["arms"], saved)
        historical = next(c for c in saved["cases"] if c["case"] == case)["arms"]["candidate"]
        for arm, a in entry["arms"].items():
            require(set(a["runs"]) == set(LABELS) and a["calls"] == [
                {"case": case["id"], "arm": arm, "label": label, "args": arguments(world, case, arm, label)}
                for label in LABELS] and a["historical_traces"] == (historical["traces"] if arm == "control" else None),
                "wrong dawn calls/historical source")
            analysis, result = a["analysis"], a["runs"]["trace"]["result"]
            focal, lives = analysis["focal"], {p["id"]: p for p in result["lineages"]}
            require(focal["life"] == lives[case["lineage"]] and focal["seed"] in result["seeds"] and
                    analysis["all_plants"]["outcomes"] == order.outcomes(result) and
                    (analysis["all_plants"]["gates"]["start"], analysis["all_plants"]["gates"]["stop"]) ==
                    (case["tick"] - STEP, STOP), "wrong dawn outcomes/window")
            end = focal["life"]["death_tick"] or STOP
            require([s["tick"] for s in focal["steps"]] == list(range(case["tick"], min(case["tick"] + DAY, end) + STEP, STEP)) and
                    [s["tick"] for s in analysis["followup_steps"]] == list(range(case["tick"] + DAY + STEP, end + STEP, STEP)),
                    "full dawn lifetime coverage differs")
            counters = [Counter() for _ in range(4)]
            choices, afternoon_choices, daylight_choices, boosts, cutoff = [], [], [], [], []
            for step in steps(analysis):
                require(step["plant"]["id"] == case["lineage"] and
                        all(b["id"] == case["lineage"] for b in step["bids"]), "wrong dawn focal identity")
                row = {"tick": step["tick"], "bids": step["bids"], "climate": step["climate"], "bodies": [step["body"]] if step["body"] else []}
                e, ac, ach, dc, dch, c, changed = check_row(row, {"plants": [step["plant"]], "sun": step["sun"]}, lives, case, arm)
                for total, part in zip(counters, (e, ac, dc, c), strict=True):
                    total.update(part)
                afternoon_choices.extend(ach)
                daylight_choices.extend(dch)
                choices.extend(changed)
                cutoff.extend(previous.previous.cutoff_choices(row, case, "candidate"))
                for bid in step["bids"]:
                    root.check_water(bid, focal["life"], step["tick"])
                    boost = (step["tick"] == case["tick"] and bid["tissue"] == 1 and bid["action"] == 1 and
                             bid["budget"]["allocates"] and bid["budget"]["allowed"] and bid["water_gate"]["allowed"])
                    require(bid["priority"] == (32767 if boost else bid["raw_priority"]), "extra/missing priority change")
                    if boost:
                        boosts.append({"tick": step["tick"], "bid": {k: v for k, v in bid.items()
                            if k not in ("energy_gate", "afternoon_gate", "daylight_gate", "dawn_gate")}})
            energy, afternoon_counts, daylight_counts, counts = counters
            require(analysis["dawn"] == {"counts": dict(sorted(counts.items())), "changed_choices": choices,
                                         "shortages": shortages(steps(analysis), focal["life"])} and
                    analysis["daylight"] == {"counts": dict(sorted(daylight_counts.items())), "changed_choices": daylight_choices} and
                    analysis["afternoon"] == {"counts": dict(sorted(afternoon_counts.items())), "changed_choices": afternoon_choices} and
                    analysis["cutoff_choices"] == cutoff, "dawn/component choice evidence differs")
            require(bool(boosts) and boosts == analysis["priority_changes"] and
                    all(analysis["eligibility"].get(k, 0) == energy[k] for k in ("active", "energy_denied", "energy_only_denied")),
                    "dawn energy/priority summary differs")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--out", type=Path)
    mode.add_argument("--verify", type=Path)
    parser.add_argument("--build", type=Path, default=ROOT / "build-host")
    parser.add_argument("--reference", type=Path, default=ROOT / "artifacts/garden-landing-daylight-v1")
    args = parser.parse_args()
    try:
        if args.verify:
            root.verify(args.verify.resolve(), experiment=sys.modules[__name__])
        else:
            root.collect(args.build.resolve(), args.out.resolve(), args.reference.resolve(), experiment=sys.modules[__name__])
        return 0
    except (OSError, RuntimeError, ValueError, KeyError, TypeError, StopIteration) as error:
        print("dawn experiment failed: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
