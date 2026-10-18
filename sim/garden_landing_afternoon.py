#!/usr/bin/env python3
"""Five afternoon maintenance counterfactuals, forty fixed native calls, no training."""

from __future__ import annotations

import argparse
from collections import Counter
import copy
from functools import cache
from pathlib import Path
import sys

import garden_landing_root_energy as previous
from garden_resources import require

root, order, adults, prior, late = previous.root, previous.order, previous.adults, previous.prior, previous.late
ROOT, DAY, STEP, STOP = previous.ROOT, previous.DAY, previous.STEP, previous.STOP
CASES, ARMS, LABELS, KINDS = previous.CASES, previous.ARMS, previous.LABELS, previous.KINDS
RULE = "garden-landing-afternoon-v1"
PROTOCOL = "benchmarks/garden-seasons/landing-afternoon-protocol.md"
INPUT = "benchmarks/garden-seasons/landing-root-energy-results.json.gz"
INPUT_SHA = "dca98970b1efbd6552df4796c280fcb0883bc959f226d569531353a760abe778"
MANIFEST_SHA = "793e82ab64e589b6fbfcde0c451e28560385a75dc583a0260cfbe8d20f1a26c0"
AUDIT = "benchmarks/garden-seasons/landing-energy-audit-results.json.gz"
AUDIT_SHA = "7943e9edb3b2e4c1f8f30925d46bbce1a7d5a5ca8ed7f70ee228f2694fd4e14b"
INPUTS = {**previous.INPUTS, INPUT: INPUT_SHA, AUDIT: AUDIT_SHA}
SCHEMA = "landing-afternoon-stand-trace-v1"


@cache
def load_inputs():
    data, world, _, model = previous.load_inputs()
    saved = prior.load(ROOT / INPUT, INPUT_SHA)
    previous.check_value(saved)
    require(root.digest(ROOT / AUDIT) == AUDIT_SHA, "motivating audit changed")
    return data, world, saved, model


def afternoon_hash(base):
    h = 2166136261
    for byte in b"GLN1" + int(base, 16).to_bytes(4, "little"):
        h = ((h ^ byte) * 16777619) & 0xffffffff
    return f"{h:08x}"


def energy_result(result, case, arm):
    require(arm in ARMS, "unknown afternoon arm")
    value = copy.deepcopy(result)
    if arm == "candidate":
        placing = order.previous.placement
        expected = placing.probe_hash(placing.budget.probe_hash(value["base_run_hash"], 2), True)
        if case["order"] == "rotating":
            expected = order.order_hash(expected, prior.AT)
        expected = previous.energy_hash(root.probe_hash(expected, case["tick"], case["lineage"]))
        require(value.get("root_afternoon_probe") == {"version": 1} and
                type(value["root_afternoon_probe"]["version"]) is int and
                value["run_hash"] == afternoon_hash(expected), "wrong afternoon identity")
        del value["root_afternoon_probe"]
        value["run_hash"] = expected
    else:
        require("root_afternoon_probe" not in value, "afternoon guard in control")
    previous.root_result(value, case, "candidate")
    return value


def arguments(world, case, arm, label):
    require(case in CASES and arm in ARMS and label in LABELS, "wrong frozen afternoon call")
    args = previous.arguments(world, case, "candidate", label)
    old, new = root.stem(case, "candidate", label), root.stem(case, arm, label)
    args = [a.replace(old, new) for a in args]
    if label in ("trace", "repeat"):
        args[args.index("--stand-energy")] = "--stand-afternoon"
    if arm == "candidate":
        args.append("--root-afternoon-reserve")
    return args


def strip_afternoon(rows):
    return [{**r, "bids": [{k: v for k, v in b.items() if k != "afternoon_gate"} for b in r["bids"]]}
            for r in rows]


def energy_stand(rows, result, case, arm):
    normal = energy_result(result, case, arm)
    require(rows[0] == {**prior.header("stand", case["tick"] - STEP, STOP), "schema": SCHEMA} and
            rows[-1] == {"complete": True, "tick": STOP, "run_hash": result["run_hash"]}, "wrong afternoon trace identity")
    return [{**rows[0], "schema": previous.SCHEMA}, *strip_afternoon(rows[1:-1]),
            {**rows[-1], "run_hash": normal["run_hash"]}]


def check_afternoon(bid, life, tick, case, arm, *, continuous=False):
    previous.check_energy(bid, life, tick, case, "candidate", continuous=continuous)
    e, a = bid["energy_gate"], bid["afternoon_gate"]
    require(set(a) == {"active", "allowed", "applies", "forecast_allowed", "maintenance_before", "margin"} and
            all(type(a[k]) is bool for k in ("active", "allowed", "applies", "forecast_allowed")) and
            all(type(a[k]) is int for k in ("maintenance_before", "margin")), "invalid afternoon receipt")
    before = max(1, (bid["nodes"] + 7) // 8)
    applies = (bid["action"] == 1 and bid["available"] > 0 and 64 <= e["sun_phase"] < 128 and
               e["maintenance"] > before)
    margin = bid["energy"] - e["cost"] - e["daylight_upkeep"] - e["night_upkeep"] if applies else 0
    active = arm == "candidate" and e["active"]
    allowed = not applies or margin >= 0
    require(a == {"active": active, "allowed": not active or allowed, "applies": applies,
                  "forecast_allowed": allowed, "maintenance_before": before if applies else 0, "margin": margin},
            "afternoon arithmetic/scope differs")


def winner(bids, *, afternoon):
    eligible = [b for b in bids if b["budget"]["allowed"] and b["water_gate"]["allowed"] and
                b["energy_gate"]["allowed"] and (not afternoon or b["afternoon_gate"]["allowed"])]
    b = max(eligible or bids, key=lambda b: b["priority"])
    return {"tip": b["tip"], "eligible": bool(eligible)}


def check_row(row, resource, lives, case, arm, *, continuous=False, extra_allowed=None):
    counts = Counter()
    for b in row["bids"]:
        check_afternoon(b, lives[b["id"]], row["tick"], case, arm, continuous=continuous)
        a = b["afternoon_gate"]
        if a["active"]:
            counts["active"] += 1
            counts["applicable"] += a["applies"]
            counts["denied"] += not a["allowed"]
            counts["additional_denied"] += (not a["allowed"] and b["energy_gate"]["allowed"] and
                                             b["budget"]["allowed"] and b["water_gate"]["allowed"])
    changes = []
    for lineage in sorted({b["id"] for b in row["bids"]}):
        bids = [b for b in row["bids"] if b["id"] == lineage]
        before, after = winner(bids, afternoon=False), winner(bids, afternoon=True)
        if before != after:
            require(arm == "candidate" and lineage == case["lineage"], "out-of-scope changed choice")
            changes.append({"tick": row["tick"], "id": lineage, "before": before, "after": after})
    energy = previous.check_bids(row, resource, lives, case, "candidate",
                                extra_allowed=lambda b: b["afternoon_gate"]["allowed"] and
                                    (extra_allowed is None or extra_allowed(b)), continuous=continuous)
    return energy, counts, changes


def analyze(stand, resources, result, case, arm, *, continuous=False, followup_stop=None,
            extra_allowed=None, legacy_stand=None):
    normal = energy_result(result, case, arm)
    # Extensions keep their receipts for combined arbitration and focal history,
    # but explicitly project those fields out before the strict legacy reader.
    legacy = stand if legacy_stand is None else legacy_stand
    choice = previous.choice_stand(energy_stand(legacy, result, case, arm), normal, case, "candidate")
    base = root.analyze(choice, resources, previous.root_result(normal, case, "candidate"), case, "candidate")
    lives, energy, afternoon, changes = {p["id"]: p for p in result["lineages"]}, Counter(), Counter(), []
    for row, resource in zip(stand[1:-1], resources[1:-1], strict=True):
        require(row["tick"] == resource["tick"], "stand/resource alignment differs")
        e, a, c = check_row(row, resource, lives, case, arm, continuous=continuous, extra_allowed=extra_allowed)
        energy.update(e)
        afternoon.update(a)
        changes.extend(c)
    focal = root.focal_history(stand, resources, result, case)
    life, start = focal["life"], case["tick"] - STEP
    followup = []
    end = min(followup_stop if followup_stop is not None else case["tick"] + 2 * DAY,
              life["death_tick"] or STOP, STOP)
    for tick in range(case["tick"] + DAY + STEP, end + STEP, STEP):
        index = (tick - start) // STEP + 1
        row, r = stand[index], resources[index]
        followup.append({"tick": tick, "sun": r["sun"], "climate": row["climate"], "soil_water": r["soil_water"],
            "plant": next(p for p in r["plants"] if p["id"] == life["id"]),
            "body": next((p for p in row["bodies"] if p["id"] == life["id"]), None),
            "visit": next(p for p in row["reproduction"] if p["id"] == life["id"]),
            "bids": [b for b in row["bids"] if b["id"] == life["id"]]})
    return {**base, "focal": focal, "followup_steps": followup, "eligibility": dict(sorted(energy.items())),
            "afternoon": {"counts": dict(sorted(afternoon.items())), "changed_choices": changes}}


def historical_check(reference, saved, case, rows, result):
    metadata = next(c for c in saved["cases"] if c["case"] == case)["arms"]["candidate"]["traces"]
    projected = energy_stand(rows[0], result, case, "control")
    for kind, records in zip(KINDS, (projected, rows[1]), strict=True):
        path = reference / metadata[kind]["path"]
        require(root.digest(path) == metadata[kind]["sha256"] and adults.read_trace(path) == records,
                "historical energy trace changed")
        require(root.digest(path) == metadata[kind]["sha256"], "historical trace changed during read")
    return metadata


def first_effect(case, arms):
    changes = arms["candidate"]["analysis"]["afternoon"]["changed_choices"]
    left, right = [a["analysis"]["focal"]["steps"] for a in (arms["control"], arms["candidate"])]
    if not changes:
        return None
    change = changes[0]
    tick = change["tick"]
    before = [[s for s in steps if s["tick"] < tick] for steps in (left, right)]
    require(strip_afternoon(before[0]) == strip_afternoon(before[1]), "histories diverge before first changed choice")
    a, b = [next(s for s in steps if s["tick"] == tick) for steps in (left, right)]
    require(strip_afternoon([a])[0]["bids"] == strip_afternoon([b])[0]["bids"] and
            a["plant"]["stages"][:3] == b["plant"]["stages"][:3], "first changed choice lacks matching pre-action state")
    return {**change, "matching_prior_focal_samples": len(before[0]), "phase": b["sun"][0],
            "bids": b["bids"], "control_stages": a["plant"]["stages"], "candidate_stages": b["plant"]["stages"]}


def check_pair(case, arms, saved):
    a, b = (arms[arm] for arm in ARMS)
    old = next(c for c in saved["cases"] if c["case"] == case)["arms"]["candidate"]
    for label in LABELS:
        require(a["runs"][label] == old["runs"][label], "historical energy checkpoint changed")
    normal = {k: v for k, v in a["analysis"].items() if k != "afternoon"}
    normal["focal"] = {**normal["focal"], "steps": strip_afternoon(normal["focal"]["steps"])}
    normal["followup_steps"] = strip_afternoon(normal["followup_steps"])
    require(normal == old["analysis"], "historical energy analysis differs")
    require(a["runs"]["prefix"]["result"] == energy_result(b["runs"]["prefix"]["result"], case, "candidate") and
            a["runs"]["prefix"]["frame"] == b["runs"]["prefix"]["frame"], "post-root prefix differs")
    fa, fb = [p["analysis"]["focal"] for p in (a, b)]
    require(strip_afternoon(fa["steps"][:1]) == strip_afternoon(fb["steps"][:1]) and
            fa["seed"] == fb["seed"] and fa["birth_check"] == fb["birth_check"] and
            fa["steps"][0]["body"]["roots"] == fb["steps"][0]["body"]["roots"] == 3, "initial root differs")
    effect = first_effect(case, arms)
    if effect is None:
        require(strip_afternoon(fa["steps"]) == strip_afternoon(fb["steps"]) and
                strip_afternoon(a["analysis"]["followup_steps"]) == strip_afternoon(b["analysis"]["followup_steps"]),
                "unchanged choices produced different focal history")
        for label in LABELS:
            require(a["runs"][label]["result"] == energy_result(b["runs"][label]["result"], case, "candidate") and
                    a["runs"][label]["frame"] == b["runs"][label]["frame"], "inactive treatment changed world")
    for arm, entry in arms.items():
        require(entry["runs"]["trace"] == entry["runs"]["repeat"], "afternoon repeat differs")
        f = entry["analysis"]["focal"]
        require(f["first_day"] == late.history_summary(f["life"], f["steps"]), "first-day budget differs")
        for label, run in entry["runs"].items():
            energy_result(run["result"], case, arm)
            require(run["result"]["tick"] == {"prefix": case["tick"], "day1": case["tick"] + DAY}.get(label, STOP), "wrong checkpoint")
        day1 = entry["runs"]["day1"]["result"]
        require(next(p for p in day1["lineages"] if p["id"] == case["lineage"])["death_tick"] ==
                (f["life"]["death_tick"] if f["life"]["death_tick"] and f["life"]["death_tick"] <= day1["tick"] else None),
                "day-one checkpoint outcome differs")


def check_value(value):
    data, world, saved, _ = load_inputs()
    require(value["rule"] == RULE and value["inputs"] == INPUTS and value["world"] == world["case"] and
            value["protocol_sha256"] == root.digest(ROOT / PROTOCOL) and value["model"] == data["models"][late.MODEL] and
            value["full_replays"] == value["checkpoint_replays"] == 20 and value["training_runs"] == 0 and
            len(value["cases"]) == len(CASES) and set(value["build"]) == {"binary", "cache"} and
            value["source_sha256"].get(PROTOCOL) == value["protocol_sha256"], "wrong afternoon provenance/budget")
    for case, entry in zip(CASES, value["cases"], strict=True):
        require(entry["case"] == case and set(entry["arms"]) == set(ARMS), "wrong afternoon panel")
        check_pair(case, entry["arms"], saved)
        historical = next(c for c in saved["cases"] if c["case"] == case)["arms"]["candidate"]
        for arm, a in entry["arms"].items():
            require(set(a["runs"]) == set(LABELS) and a["calls"] == [
                {"case": case["id"], "arm": arm, "label": label, "args": arguments(world, case, arm, label)}
                for label in LABELS] and a["historical_traces"] == (historical["traces"] if arm == "control" else None),
                "wrong afternoon calls/historical source")
            analysis, result = a["analysis"], a["runs"]["trace"]["result"]
            focal, lives = analysis["focal"], {p["id"]: p for p in result["lineages"]}
            require(focal["life"] == lives[case["lineage"]] and focal["seed"] in result["seeds"] and
                    analysis["all_plants"]["outcomes"] == order.outcomes(result) and
                    (analysis["all_plants"]["gates"]["start"], analysis["all_plants"]["gates"]["stop"]) ==
                    (case["tick"] - STEP, STOP), "wrong outcomes/window")
            end = min(case["tick"] + 2 * DAY, focal["life"]["death_tick"] or STOP)
            require([s["tick"] for s in analysis["followup_steps"]] == list(range(case["tick"] + DAY + STEP, end + STEP, STEP)),
                    "second-day coverage differs")
            before, counts, energy, choices, boosts = None, Counter(), Counter(), [], []
            for step in focal["steps"] + analysis["followup_steps"]:
                adults.transfers({"tick": step["tick"], **step["plant"]}, focal["life"], before)
                before = step["plant"]["stages"][-1]
                e, c, changed = check_row({"tick": step["tick"], "bids": step["bids"],
                    "bodies": [step["body"]] if step["body"] else []}, {"plants": [step["plant"]]}, lives, case, arm)
                counts.update(c)
                energy.update(e)
                choices.extend(changed)
                for bid in step["bids"]:
                    root.check_water(bid, focal["life"], step["tick"])
                    boost = (step["tick"] == case["tick"] and bid["tissue"] == 1 and bid["action"] == 1 and
                             bid["budget"]["allocates"] and bid["budget"]["allowed"] and bid["water_gate"]["allowed"])
                    require(bid["priority"] == (32767 if boost else bid["raw_priority"]), "extra/missing priority change")
                    if boost:
                        boosts.append({"tick": step["tick"], "bid": {k: v for k, v in bid.items()
                            if k not in ("energy_gate", "afternoon_gate")}})
            require(analysis["afternoon"] == {"counts": dict(sorted(counts.items())), "changed_choices": choices},
                    "afternoon evidence differs")
            require(bool(boosts) and boosts == analysis["priority_changes"] and
                    all(analysis["eligibility"].get(k, 0) == energy[k] for k in
                        ("active", "energy_denied", "energy_only_denied")), "energy/priority summary differs")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--out", type=Path)
    mode.add_argument("--verify", type=Path)
    parser.add_argument("--build", type=Path, default=ROOT / "build-host")
    parser.add_argument("--reference", type=Path, default=ROOT / "artifacts/garden-landing-root-energy-v1-verified")
    args = parser.parse_args()
    try:
        if args.verify:
            root.verify(args.verify.resolve(), experiment=sys.modules[__name__])
        else:
            root.collect(args.build.resolve(), args.out.resolve(), args.reference.resolve(), experiment=sys.modules[__name__])
        return 0
    except (OSError, RuntimeError, ValueError, KeyError, TypeError, StopIteration) as error:
        print("afternoon experiment failed: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
