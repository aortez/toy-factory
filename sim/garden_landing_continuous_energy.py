#!/usr/bin/env python3
"""Remove only the energy cutoff in five fixed pairs; forty calls, no training."""

from __future__ import annotations

import argparse
from collections import Counter
import copy
from functools import cache
from pathlib import Path
import sys

import garden_landing_afternoon as previous
from garden_resources import require

root, order, adults, prior, late = previous.root, previous.order, previous.adults, previous.prior, previous.late
ROOT, DAY, STEP, STOP = previous.ROOT, previous.DAY, previous.STEP, previous.STOP
CASES, ARMS, LABELS, KINDS = previous.CASES, previous.ARMS, previous.LABELS, previous.KINDS
RULE = "garden-landing-continuous-energy-v1"
PROTOCOL = "benchmarks/garden-seasons/landing-continuous-energy-protocol.md"
INPUT = "benchmarks/garden-seasons/landing-afternoon-results.json.gz"
INPUT_SHA = "dea464eae46233bcc2f253ae657a7b4a05e8b2d3c51a8b484f23e04c40602afc"
MANIFEST_SHA = "9ec0e6c08a0bf19971e89a6ffbaaef8fe97a5675c20d4d0ade390e3f3e219e82"
INPUTS = {**previous.INPUTS, INPUT: INPUT_SHA}


@cache
def load_inputs():
    data, world, _, model = previous.load_inputs()
    saved = prior.load(ROOT / INPUT, INPUT_SHA)
    previous.check_value(saved)
    return data, world, saved, model


def continuous_hash(base):
    h = 2166136261
    for byte in b"GLU1" + int(base, 16).to_bytes(4, "little"):
        h = ((h ^ byte) * 16777619) & 0xffffffff
    return f"{h:08x}"


def afternoon_result(result, case, arm):
    require(arm in ARMS, "unknown continuous arm")
    value = copy.deepcopy(result)
    if arm == "candidate":
        placing = order.previous.placement
        expected = placing.probe_hash(placing.budget.probe_hash(value["base_run_hash"], 2), True)
        if case["order"] == "rotating":
            expected = order.order_hash(expected, prior.AT)
        expected = previous.afternoon_hash(previous.previous.energy_hash(root.probe_hash(expected, case["tick"], case["lineage"])))
        require(value.get("root_continuous_energy_probe") == {"version": 1} and
                type(value["root_continuous_energy_probe"]["version"]) is int and
                value["run_hash"] == continuous_hash(expected), "wrong continuous identity")
        del value["root_continuous_energy_probe"]
        value["run_hash"] = expected
    else:
        require("root_continuous_energy_probe" not in value, "continuous guard in control")
    previous.energy_result(value, case, "candidate")
    return value


def arguments(world, case, arm, label):
    require(case in CASES and arm in ARMS and label in LABELS, "wrong frozen continuous call")
    args = previous.arguments(world, case, "candidate", label)
    old, new = root.stem(case, "candidate", label), root.stem(case, arm, label)
    args = [a.replace(old, new) for a in args]
    return args + (["--root-continuous-energy"] if arm == "candidate" else [])


def afternoon_stand(rows, result, case, arm):
    normal = afternoon_result(result, case, arm)
    require(rows[0] == {**prior.header("stand", case["tick"] - STEP, STOP), "schema": previous.SCHEMA} and
            rows[-1] == {"complete": True, "tick": STOP, "run_hash": result["run_hash"]}, "wrong continuous trace identity")
    return [*rows[:-1], {**rows[-1], "run_hash": normal["run_hash"]}]


def steps(analysis):
    return analysis["focal"]["steps"] + analysis["followup_steps"]


def physical(rows):
    """Keep forecast inputs and outputs; omit only configured scope/eligibility."""
    return [{**s, "bids": [{**b, **{gate: {k: v for k, v in b[gate].items() if k not in ("active", "allowed")}
                for gate in ("energy_gate", "afternoon_gate")}} for b in s["bids"]]} for s in rows]


def cutoff_choices(row, case, arm):
    if arm != "candidate" or row["tick"] < case["tick"] + DAY:
        return []
    bids = [b for b in row["bids"] if b["id"] == case["lineage"]]
    if not bids:
        return []
    # Evaluate the former cutoff on the SAME proposals, not a diverged control.
    unguarded = [{**b, **{gate: {**b[gate], "active": False, "allowed": True}
                          for gate in ("energy_gate", "afternoon_gate")}} for b in bids]
    before, after = previous.winner(unguarded, afternoon=True), previous.winner(bids, afternoon=True)
    return ([{"tick": row["tick"], "id": case["lineage"], "before": before, "after": after}]
            if before != after else [])


def analyze(stand, resources, result, case, arm):
    normal = afternoon_result(result, case, arm)
    base = previous.analyze(afternoon_stand(stand, result, case, arm), resources, normal, case, "candidate",
                            continuous=arm == "candidate", followup_stop=STOP)
    return {**base, "cutoff_choices": [c for row in stand[1:-1] for c in cutoff_choices(row, case, arm)]}


def historical_check(reference, saved, case, rows, result):
    afternoon_result(result, case, "control")
    metadata = next(c for c in saved["cases"] if c["case"] == case)["arms"]["candidate"]["traces"]
    for kind, records in zip(KINDS, rows, strict=True):
        path = reference / metadata[kind]["path"]
        require(root.digest(path) == metadata[kind]["sha256"] and adults.read_trace(path) == records,
                "historical afternoon trace changed")
        require(root.digest(path) == metadata[kind]["sha256"], "historical trace changed during read")
    return metadata


def first_effect(case, arms):
    changes = arms["candidate"]["analysis"]["cutoff_choices"]
    if not changes:
        return None
    change = changes[0]
    tick = change["tick"]
    left, right = [steps(arms[a]["analysis"]) for a in ARMS]
    before = [[s for s in rows if s["tick"] < tick] for rows in (left, right)]
    require(physical(before[0]) == physical(before[1]), "histories differ before first continuous choice")
    a, b = [next(s for s in rows if s["tick"] == tick) for rows in (left, right)]
    require(physical([a])[0]["bids"] == physical([b])[0]["bids"] and
            a["plant"]["stages"][:3] == b["plant"]["stages"][:3], "first effect lacks matching pre-action state")
    return {**change, "matching_prior_focal_samples": len(before[0]), "phase": b["sun"][0],
            "bids": b["bids"], "control_stages": a["plant"]["stages"], "candidate_stages": b["plant"]["stages"]}


def check_pair(case, arms, saved):
    a, b = (arms[arm] for arm in ARMS)
    old = next(c for c in saved["cases"] if c["case"] == case)["arms"]["candidate"]
    require(a["runs"] == old["runs"], "historical afternoon checkpoints changed")
    projected = {k: v for k, v in a["analysis"].items() if k != "cutoff_choices"}
    projected["followup_steps"] = [s for s in projected["followup_steps"] if s["tick"] <= case["tick"] + 2 * DAY]
    require(projected == old["analysis"], "historical afternoon analysis changed")
    require(a["runs"]["prefix"]["result"] == afternoon_result(b["runs"]["prefix"]["result"], case, "candidate") and
            a["runs"]["prefix"]["frame"] == b["runs"]["prefix"]["frame"], "post-root prefix changed")
    fa, fb = [p["analysis"]["focal"] for p in (a, b)]
    require(fa["seed"] == fb["seed"] and fa["birth_check"] == fb["birth_check"] and
            fa["steps"][0] == fb["steps"][0] and fa["steps"][0]["body"]["roots"] == 3, "initial root differs")
    if first_effect(case, arms) is None:
        require(physical(steps(a["analysis"])) == physical(steps(b["analysis"])), "inactive choices changed history")
        for label in LABELS:
            require(a["runs"][label]["result"] == afternoon_result(b["runs"][label]["result"], case, "candidate") and
                    a["runs"][label]["frame"] == b["runs"][label]["frame"], "inactive treatment changed world")
    for arm, entry in arms.items():
        require(entry["runs"]["trace"] == entry["runs"]["repeat"], "continuous repeat differs")
        focal = entry["analysis"]["focal"]
        require(focal["first_day"] == late.history_summary(focal["life"], focal["steps"]), "first-day budget differs")
        for label, run in entry["runs"].items():
            afternoon_result(run["result"], case, arm)
            require(run["result"]["tick"] == {"prefix": case["tick"], "day1": case["tick"] + DAY}.get(label, STOP), "wrong checkpoint")
        day1 = entry["runs"]["day1"]["result"]
        require(next(p for p in day1["lineages"] if p["id"] == case["lineage"])["death_tick"] ==
                (focal["life"]["death_tick"] if focal["life"]["death_tick"] and focal["life"]["death_tick"] <= day1["tick"] else None),
                "day-one checkpoint outcome differs")


def check_value(value):
    data, world, saved, _ = load_inputs()
    require(value["rule"] == RULE and value["inputs"] == INPUTS and value["world"] == world["case"] and
            value["protocol_sha256"] == root.digest(ROOT / PROTOCOL) and value["model"] == data["models"][late.MODEL] and
            value["full_replays"] == value["checkpoint_replays"] == 20 and value["training_runs"] == 0 and
            len(value["cases"]) == len(CASES) and set(value["build"]) == {"binary", "cache"} and
            value["source_sha256"].get(PROTOCOL) == value["protocol_sha256"], "wrong continuous provenance/budget")
    for case, entry in zip(CASES, value["cases"], strict=True):
        require(entry["case"] == case and set(entry["arms"]) == set(ARMS), "wrong continuous panel")
        check_pair(case, entry["arms"], saved)
        historical = next(c for c in saved["cases"] if c["case"] == case)["arms"]["candidate"]
        for arm, a in entry["arms"].items():
            require(set(a["runs"]) == set(LABELS) and a["calls"] == [
                {"case": case["id"], "arm": arm, "label": label, "args": arguments(world, case, arm, label)}
                for label in LABELS] and a["historical_traces"] == (historical["traces"] if arm == "control" else None),
                "wrong continuous calls/historical source")
            analysis, result = a["analysis"], a["runs"]["trace"]["result"]
            focal, lives = analysis["focal"], {p["id"]: p for p in result["lineages"]}
            require(focal["life"] == lives[case["lineage"]] and focal["seed"] in result["seeds"] and
                    analysis["all_plants"]["outcomes"] == order.outcomes(result) and
                    (analysis["all_plants"]["gates"]["start"], analysis["all_plants"]["gates"]["stop"]) ==
                    (case["tick"] - STEP, STOP), "wrong outcomes/window")
            end = focal["life"]["death_tick"] or STOP
            require([s["tick"] for s in focal["steps"]] == list(range(case["tick"], min(case["tick"] + DAY, end) + STEP, STEP)) and
                    [s["tick"] for s in analysis["followup_steps"]] == list(range(case["tick"] + DAY + STEP, end + STEP, STEP)),
                    "full lifetime coverage differs")
            before, counts, energy, choices, boosts, cutoff = None, Counter(), Counter(), [], [], []
            for step in steps(analysis):
                require(step["plant"]["id"] == case["lineage"] and
                        all(b["id"] == case["lineage"] for b in step["bids"]), "wrong focal history identity")
                adults.transfers({"tick": step["tick"], **step["plant"]}, focal["life"], before)
                before = step["plant"]["stages"][-1]
                row = {"tick": step["tick"], "bids": step["bids"], "bodies": [step["body"]] if step["body"] else []}
                e, c, changed = previous.check_row(row, {"plants": [step["plant"]]}, lives, case, "candidate", continuous=arm == "candidate")
                counts.update(c)
                energy.update(e)
                choices.extend(changed)
                cutoff.extend(cutoff_choices(row, case, arm))
                for bid in step["bids"]:
                    root.check_water(bid, focal["life"], step["tick"])
                    boost = (step["tick"] == case["tick"] and bid["tissue"] == 1 and bid["action"] == 1 and
                             bid["budget"]["allocates"] and bid["budget"]["allowed"] and bid["water_gate"]["allowed"])
                    require(bid["priority"] == (32767 if boost else bid["raw_priority"]), "extra/missing priority change")
                    if boost:
                        boosts.append({"tick": step["tick"], "bid": {k: v for k, v in bid.items()
                            if k not in ("energy_gate", "afternoon_gate")}})
            require(analysis["afternoon"] == {"counts": dict(sorted(counts.items())), "changed_choices": choices} and
                    analysis["cutoff_choices"] == cutoff, "continuous choice evidence differs")
            require(bool(boosts) and boosts == analysis["priority_changes"] and
                    all(analysis["eligibility"].get(k, 0) == energy[k] for k in
                        ("active", "energy_denied", "energy_only_denied")), "energy/priority summary differs")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--out", type=Path)
    mode.add_argument("--verify", type=Path)
    parser.add_argument("--build", type=Path, default=ROOT / "build-host")
    parser.add_argument("--reference", type=Path, default=ROOT / "artifacts/garden-landing-afternoon-v1")
    args = parser.parse_args()
    try:
        if args.verify:
            root.verify(args.verify.resolve(), experiment=sys.modules[__name__])
        else:
            root.collect(args.build.resolve(), args.out.resolve(), args.reference.resolve(), experiment=sys.modules[__name__])
        return 0
    except (OSError, RuntimeError, ValueError, KeyError, TypeError, StopIteration) as error:
        print("continuous energy experiment failed: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
