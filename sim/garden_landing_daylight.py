#!/usr/bin/env python3
"""Test productive afternoon credit in five fixed pairs; forty calls, no training."""

from __future__ import annotations

import argparse
from collections import Counter
import copy
from functools import cache
from pathlib import Path
import sys

import garden_landing_continuous_energy as previous
import garden_landing_light_audit as audit
from garden_resources import require

afternoon = previous.previous
root, order, adults, prior, late = previous.root, previous.order, previous.adults, previous.prior, previous.late
ROOT, DAY, STEP, STOP = previous.ROOT, previous.DAY, previous.STEP, previous.STOP
CASES, ARMS, LABELS, KINDS = previous.CASES, previous.ARMS, previous.LABELS, previous.KINDS
RULE = "garden-landing-daylight-v1"
PROTOCOL = "benchmarks/garden-seasons/landing-daylight-protocol.md"
INPUT, INPUT_SHA = audit.INPUT, audit.INPUT_SHA
MANIFEST_SHA = "5b091e2e033fca3a0ceaeb1669646bff698fb23f675354b82ddf561ae16fa4a0"
AUDIT = "benchmarks/garden-seasons/landing-light-audit-results.json.gz"
AUDIT_SHA = "80d7c070d41bf0d7c6d6836e342d830fe98b9436cc82ba09a5231bf0f9c5975b"
INPUTS = {**previous.INPUTS, INPUT: INPUT_SHA, AUDIT: AUDIT_SHA}
SCHEMA = "landing-daylight-stand-trace-v1"


@cache
def load_inputs():
    data, world, _, model = previous.load_inputs()
    saved = audit.load_input()
    require(root.digest(ROOT / AUDIT) == AUDIT_SHA, "motivating light audit changed")
    return data, world, saved, model


def daylight_hash(base):
    h = 2166136261
    for byte in b"GLD1" + int(base, 16).to_bytes(4, "little"):
        h = ((h ^ byte) * 16777619) & 0xffffffff
    return f"{h:08x}"


def continuous_result(result, case, arm):
    require(arm in ARMS, "unknown daylight arm")
    value = copy.deepcopy(result)
    if arm == "candidate":
        placing = order.previous.placement
        expected = placing.probe_hash(placing.budget.probe_hash(value["base_run_hash"], 2), True)
        if case["order"] == "rotating":
            expected = order.order_hash(expected, prior.AT)
        expected = previous.continuous_hash(afternoon.afternoon_hash(afternoon.previous.energy_hash(
            root.probe_hash(expected, case["tick"], case["lineage"]))))
        require(value.get("root_daylight_energy_probe") == {"version": 1} and
                type(value["root_daylight_energy_probe"]["version"]) is int and
                value["run_hash"] == daylight_hash(expected), "wrong daylight identity")
        del value["root_daylight_energy_probe"]
        value["run_hash"] = expected
    else:
        require("root_daylight_energy_probe" not in value, "daylight guard in control")
    previous.afternoon_result(value, case, "candidate")
    return value


def arguments(world, case, arm, label):
    require(case in CASES and arm in ARMS and label in LABELS, "wrong frozen daylight call")
    args = previous.arguments(world, case, "candidate", label)
    old, new = root.stem(case, "candidate", label), root.stem(case, arm, label)
    args = [a.replace(old, new) for a in args]
    if label in ("trace", "repeat"):
        args[args.index("--stand-afternoon")] = "--stand-daylight"
    return args + (["--root-daylight-energy"] if arm == "candidate" else [])


def strip_daylight(rows):
    return [{**s, "bids": [{k: v for k, v in b.items() if k != "daylight_gate"} for b in s["bids"]]} for s in rows]


def continuous_stand(rows, result, case, arm):
    normal = continuous_result(result, case, arm)
    require(rows[0] == {**prior.header("stand", case["tick"] - STEP, STOP), "schema": SCHEMA} and
            rows[-1] == {"complete": True, "tick": STOP, "run_hash": result["run_hash"]}, "wrong daylight trace identity")
    return [{**rows[0], "schema": afternoon.SCHEMA}, *strip_daylight(rows[1:-1]),
            {**rows[-1], "run_hash": normal["run_hash"]}]


def check_daylight(bid, life, tick, case, arm, sun):
    afternoon.check_afternoon(bid, life, tick, case, "candidate", continuous=True)
    e, d = bid["energy_gate"], bid["daylight_gate"]
    require(set(d) == {"active", "allowed", "applies", "forecast_allowed", "sun_strength",
                      "useful_steps", "daylight_credit", "projected_sunset"} and
            all(type(d[k]) is bool for k in ("active", "allowed", "applies", "forecast_allowed")) and
            all(type(d[k]) is int for k in ("sun_strength", "useful_steps", "daylight_credit", "projected_sunset")),
            "invalid daylight receipt")
    require(e["sun_phase"] == sun[0] and d["sun_strength"] == sun[1], "daylight observation differs")
    applies = bid["action"] != 0 and 64 <= e["sun_phase"] < 128
    useful, credit, sunset, allowed = 0, 0, 0, True
    if applies:
        calculated = audit.diagnostic(e["sun_phase"], sun[1], e["income"])
        useful, credit = calculated["useful_steps"], calculated["credit"]
        sunset = min(256, bid["energy"] - e["cost"] + credit - e["daylight_upkeep"])
        allowed = bid["energy"] - e["cost"] >= e["maintenance"] and sunset >= e["night_upkeep"]
        require(credit <= e["daylight_credit"] and (not allowed or e["forecast_allowed"]), "daylight guard relaxed forecast")
    active = arm == "candidate" and e["active"]
    require(d == {"active": active, "allowed": not active or allowed, "applies": applies,
                  "forecast_allowed": allowed, "sun_strength": sun[1], "useful_steps": useful,
                  "daylight_credit": credit, "projected_sunset": sunset}, "daylight arithmetic/scope differs")


def winner(bids, *, daylight, extra_allowed=None):
    if not daylight and extra_allowed is None:
        return afternoon.winner(bids, afternoon=True)
    gates = ("budget", "water_gate", "energy_gate", "afternoon_gate") + (("daylight_gate",) if daylight else ())
    eligible = [b for b in bids if all(b[g]["allowed"] for g in gates) and
                (extra_allowed is None or extra_allowed(b))]
    chosen = max(eligible or bids, key=lambda b: b["priority"])
    return {"tip": chosen["tip"], "eligible": bool(eligible)}


def check_row(row, resource, lives, case, arm, *, extra_allowed=None):
    sun = resource["sun"]
    require(sun[0] == (64 + row["tick"] // STEP) % 256 and
            sun[1] == audit.strength(sun[0], row["climate"]["light_percent"]), "daylight clock/strength differs")
    counts, changes = Counter(), []
    for b in row["bids"]:
        check_daylight(b, lives[b["id"]], row["tick"], case, arm, sun)
        d = b["daylight_gate"]
        if d["active"]:
            counts["active"] += 1
            counts["applicable"] += d["applies"]
            counts["denied"] += not d["allowed"]
            counts["additional_denied"] += not d["allowed"] and all(
                b[g]["allowed"] for g in ("budget", "water_gate", "energy_gate", "afternoon_gate"))
    for lineage in sorted({b["id"] for b in row["bids"]}):
        bids = [b for b in row["bids"] if b["id"] == lineage]
        before, after = winner(bids, daylight=False), winner(bids, daylight=True)
        if before != after:
            require(arm == "candidate" and lineage == case["lineage"], "out-of-scope daylight choice")
            changes.append({"tick": row["tick"], "id": lineage, "before": before, "after": after})
        stages = next(p for p in resource["plants"] if p["id"] == lineage)["stages"]
        if stages[2][0] != stages[3][0]:
            actual = winner(bids, daylight=True, extra_allowed=extra_allowed)
            selected = next(b for b in bids if b["tip"] == actual["tip"])
            require(actual["eligible"] and selected["action"] != 0 and
                    stages[2][0] == selected["energy"] and stages[2][0] - stages[3][0] ==
                    (9, 8, 7)[lives[lineage]["species"]] - int(selected["energy_gate"]["vigor"] > 0),
                    "paid action/price differs from combined winner")
    e, a, c = afternoon.check_row(row, resource, lives, case, "candidate", continuous=True,
                                extra_allowed=lambda b: b["daylight_gate"]["allowed"] and
                                (extra_allowed is None or extra_allowed(b)))
    return e, a, c, counts, changes


def analyze(stand, resources, result, case, arm, *, extra_allowed=None, legacy_stand=None):
    normal = continuous_result(result, case, arm)
    old_stand = previous.afternoon_stand(continuous_stand(legacy_stand or stand, result, case, arm), normal, case, "candidate")
    old_result = previous.afternoon_result(normal, case, "candidate")
    extended = [old_stand[0], *stand[1:-1], old_stand[-1]]
    base = afternoon.analyze(extended, resources, old_result, case, "candidate", continuous=True, followup_stop=STOP,
                             extra_allowed=lambda b: b["daylight_gate"]["allowed"] and
                             (extra_allowed is None or extra_allowed(b)), legacy_stand=old_stand)
    lives, counts, changes = {p["id"]: p for p in result["lineages"]}, Counter(), []
    for row, resource in zip(stand[1:-1], resources[1:-1], strict=True):
        _, _, _, c, changed = check_row(row, resource, lives, case, arm, extra_allowed=extra_allowed)
        counts.update(c)
        changes.extend(changed)
    return {**base, "cutoff_choices": [c for row in stand[1:-1] for c in previous.cutoff_choices(row, case, "candidate")],
            "daylight": {"counts": dict(sorted(counts.items())), "changed_choices": changes}}


def historical_check(reference, saved, case, rows, result):
    metadata = next(c for c in saved["cases"] if c["case"] == case)["arms"]["candidate"]["traces"]
    projected = continuous_stand(rows[0], result, case, "control")
    for kind, records in zip(KINDS, (projected, rows[1]), strict=True):
        path = reference / metadata[kind]["path"]
        require(root.digest(path) == metadata[kind]["sha256"] and adults.read_trace(path) == records,
                "historical continuous trace changed")
        require(root.digest(path) == metadata[kind]["sha256"], "historical trace changed during read")
    return metadata


def first_effect(case, arms):
    changes = arms["candidate"]["analysis"]["daylight"]["changed_choices"]
    if not changes:
        return None
    change = changes[0]
    tick = change["tick"]
    rows = [previous.steps(arms[a]["analysis"]) for a in ARMS]
    before = [[s for s in history if s["tick"] < tick] for history in rows]
    require(strip_daylight(before[0]) == strip_daylight(before[1]), "histories differ before first daylight choice")
    a, b = [next(s for s in history if s["tick"] == tick) for history in rows]
    require(strip_daylight([a])[0]["bids"] == strip_daylight([b])[0]["bids"] and
            a["plant"]["stages"][:3] == b["plant"]["stages"][:3] and a["sun"] == b["sun"],
            "first daylight choice lacks matching pre-action state")
    return {**change, "matching_prior_focal_samples": len(before[0]), "phase": b["sun"][0],
            "bids": b["bids"], "control_stages": a["plant"]["stages"], "candidate_stages": b["plant"]["stages"]}


def check_pair(case, arms, saved):
    a, b = [arms[arm] for arm in ARMS]
    old = next(c for c in saved["cases"] if c["case"] == case)["arms"]["candidate"]
    require(a["runs"] == old["runs"], "historical continuous checkpoints changed")
    projected = {k: v for k, v in a["analysis"].items() if k != "daylight"}
    projected["focal"] = {**projected["focal"], "steps": strip_daylight(projected["focal"]["steps"])}
    projected["followup_steps"] = strip_daylight(projected["followup_steps"])
    require(projected == old["analysis"], "historical continuous analysis changed")
    require(a["runs"]["prefix"]["result"] == continuous_result(b["runs"]["prefix"]["result"], case, "candidate") and
            a["runs"]["prefix"]["frame"] == b["runs"]["prefix"]["frame"], "post-root prefix changed")
    fa, fb = [x["analysis"]["focal"] for x in (a, b)]
    require(fa["seed"] == fb["seed"] and fa["birth_check"] == fb["birth_check"] and
            strip_daylight(fa["steps"][:1]) == strip_daylight(fb["steps"][:1]) and
            fa["steps"][0]["body"]["roots"] == fb["steps"][0]["body"]["roots"] == 3, "initial root differs")
    if first_effect(case, arms) is None:
        require(strip_daylight(previous.steps(a["analysis"])) == strip_daylight(previous.steps(b["analysis"])),
                "inactive daylight choices changed history")
        for label in LABELS:
            require(a["runs"][label]["result"] == continuous_result(b["runs"][label]["result"], case, "candidate") and
                    a["runs"][label]["frame"] == b["runs"][label]["frame"], "inactive treatment changed world")
    for arm, entry in arms.items():
        require(entry["runs"]["trace"] == entry["runs"]["repeat"], "daylight repeat differs")
        focal = entry["analysis"]["focal"]
        require(focal["first_day"] == late.history_summary(focal["life"], focal["steps"]), "first-day budget differs")
        for label, run in entry["runs"].items():
            continuous_result(run["result"], case, arm)
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
            value["source_sha256"].get(PROTOCOL) == value["protocol_sha256"], "wrong daylight provenance/budget")
    for case, entry in zip(CASES, value["cases"], strict=True):
        require(entry["case"] == case and set(entry["arms"]) == set(ARMS), "wrong daylight panel")
        check_pair(case, entry["arms"], saved)
        historical = next(c for c in saved["cases"] if c["case"] == case)["arms"]["candidate"]
        for arm, a in entry["arms"].items():
            require(set(a["runs"]) == set(LABELS) and a["calls"] == [
                {"case": case["id"], "arm": arm, "label": label, "args": arguments(world, case, arm, label)}
                for label in LABELS] and a["historical_traces"] == (historical["traces"] if arm == "control" else None),
                "wrong daylight calls/historical source")
            analysis, result = a["analysis"], a["runs"]["trace"]["result"]
            focal, lives = analysis["focal"], {p["id"]: p for p in result["lineages"]}
            require(focal["life"] == lives[case["lineage"]] and focal["seed"] in result["seeds"] and
                    analysis["all_plants"]["outcomes"] == order.outcomes(result) and
                    (analysis["all_plants"]["gates"]["start"], analysis["all_plants"]["gates"]["stop"]) ==
                    (case["tick"] - STEP, STOP), "wrong daylight outcomes/window")
            end = focal["life"]["death_tick"] or STOP
            require([s["tick"] for s in focal["steps"]] == list(range(case["tick"], min(case["tick"] + DAY, end) + STEP, STEP)) and
                    [s["tick"] for s in analysis["followup_steps"]] == list(range(case["tick"] + DAY + STEP, end + STEP, STEP)),
                    "full daylight lifetime coverage differs")
            before, counts, energy, afternoon_counts, choices, afternoon_choices, boosts, cutoff = None, Counter(), Counter(), Counter(), [], [], [], []
            for step in previous.steps(analysis):
                require(step["plant"]["id"] == case["lineage"] and
                        all(b["id"] == case["lineage"] for b in step["bids"]), "wrong daylight focal identity")
                adults.transfers({"tick": step["tick"], **step["plant"]}, focal["life"], before)
                before = step["plant"]["stages"][-1]
                row = {"tick": step["tick"], "bids": step["bids"], "climate": step["climate"], "bodies": [step["body"]] if step["body"] else []}
                e, ac, ach, c, changed = check_row(row, {"plants": [step["plant"]], "sun": step["sun"]}, lives, case, arm)
                energy.update(e)
                afternoon_counts.update(ac)
                afternoon_choices.extend(ach)
                counts.update(c)
                choices.extend(changed)
                cutoff.extend(previous.cutoff_choices(row, case, "candidate"))
                for bid in step["bids"]:
                    root.check_water(bid, focal["life"], step["tick"])
                    boost = (step["tick"] == case["tick"] and bid["tissue"] == 1 and bid["action"] == 1 and
                             bid["budget"]["allocates"] and bid["budget"]["allowed"] and bid["water_gate"]["allowed"])
                    require(bid["priority"] == (32767 if boost else bid["raw_priority"]), "extra/missing priority change")
                    if boost:
                        boosts.append({"tick": step["tick"], "bid": {k: v for k, v in bid.items()
                            if k not in ("energy_gate", "afternoon_gate", "daylight_gate")}})
            require(analysis["daylight"] == {"counts": dict(sorted(counts.items())), "changed_choices": choices} and
                    analysis["afternoon"] == {"counts": dict(sorted(afternoon_counts.items())), "changed_choices": afternoon_choices} and
                    analysis["cutoff_choices"] == cutoff, "daylight/component choice evidence differs")
            require(bool(boosts) and boosts == analysis["priority_changes"] and
                    all(analysis["eligibility"].get(k, 0) == energy[k] for k in ("active", "energy_denied", "energy_only_denied")),
                    "daylight energy/priority summary differs")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--out", type=Path)
    mode.add_argument("--verify", type=Path)
    parser.add_argument("--build", type=Path, default=ROOT / "build-host")
    parser.add_argument("--reference", type=Path, default=ROOT / "artifacts/garden-landing-continuous-energy-v1")
    args = parser.parse_args()
    try:
        if args.verify:
            root.verify(args.verify.resolve(), experiment=sys.modules[__name__])
        else:
            root.collect(args.build.resolve(), args.out.resolve(), args.reference.resolve(), experiment=sys.modules[__name__])
        return 0
    except (OSError, RuntimeError, ValueError, KeyError, TypeError, StopIteration) as error:
        print("daylight experiment failed: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
