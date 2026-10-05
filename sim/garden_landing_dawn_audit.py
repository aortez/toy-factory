#!/usr/bin/env python3
"""Audit saved night and dawn funding, including successful growth; no simulator."""

from __future__ import annotations

import argparse
from collections import Counter
from functools import cache
from pathlib import Path
import sys
import tarfile

import garden_landing_daylight as previous
import garden_landing_light_audit as light
import garden_landing_energy_audit as energy
from garden_experiments import digest
from garden_resources import require

ROOT, DAY, STEP, STOP = previous.ROOT, previous.DAY, previous.STEP, previous.STOP
RULE = "garden-landing-dawn-audit-v1"
INPUT = "benchmarks/garden-seasons/landing-daylight-results.json.gz"
INPUT_SHA = "9e2acb8cf141e75307020c0b854c3a76611942cec615c21b95db750c97d7748b"
PROTOCOL = "benchmarks/garden-seasons/landing-dawn-audit-protocol.md"
CAPTURE_SOURCES = {**light.CAPTURE_SOURCES,
    "sim/garden_reserve_policy.c": "b1154698dfdceee84654b917b2f97a77bc4fb92306fc909aba92745a1e3a8c24"}
LIMITATIONS = [
    "Ten selected, overlapping histories are not independent environmental trials.",
    "Funding requirements hold recorded income, bodies and spending fixed; they are not world replays.",
    "Death/censoring supplies only an observed-prefix requirement, never invented future income.",
    "Maintenance-only accounting retains the recorded body path despite omitting its growth cost.",
    "The diagnostic holds current attenuation and post-action upkeep fixed; it cannot know future shade or weather.",
    "An unavailable morning-light estimate is not permission or a default buffer.",
    "A same-state rejected purchase is neither a demonstrated benefit nor a demonstrated regression.",
    "All focal seed counts are zero; survival through day 256 is censored, not autonomous renewal.",
]


def check_capture(data):
    require(all(data["source_sha256"].get(k) == v for k, v in CAPTURE_SOURCES.items()),
            "unsupported captured dawn sources")
    require(all(data["settings"].get(k) == "OFF" for k in
                ("TOY_FACTORY_GARDEN_LEAF_MAINTENANCE", "TOY_FACTORY_GARDEN_CANOPY_TRANSMISSION",
                 "TOY_FACTORY_GARDEN_DAWN_FINISH", "TOY_FACTORY_GARDEN_DARK_GUARD", "TOY_FACTORY_GARDEN_NIGHT_CAPACITY")),
            "unsupported captured dawn experiment")


@cache
def load_input():
    value = previous.prior.load(ROOT / INPUT, INPUT_SHA)
    previous.check_value(value)
    check_capture(value)
    return value


def sample(row, receipt, illumination):
    plant, tick = row["plant"], row["tick"]
    due = (max(1, (plant["stages"][0][4] + 7) // 8)
           if plant["uptake"] is not None and tick % (4 * STEP) == 0 else 0)
    paid = receipt["upkeep"]
    require(paid == min(due, plant["stages"][0][0]) if plant["uptake"] is not None else paid == 0,
            "maintenance due/paid differs")
    if plant["uptake"] is not None:
        require(receipt["overflow"] == max(0, receipt["initial"] + receipt["income"] - 256), "storage cap differs")
        if tick % (4 * STEP) == 0:
            require(bool(plant["stages"][1][3] & 2) == (paid < due), "shortage flag differs at payment")
    return {**illumination, **receipt, "due": due, "paid": paid, "unpaid": due - paid,
            "nodes": plant["stages"][-1][4], "stress": plant["stages"][-1][2],
            "flags": plant["stages"][-1][3]}


def required_opening(samples, *, spending):
    """Backward min balance for frozen demands, with uptake capped BEFORE costs."""
    names = ("income", "due", "growth", "reproduction")
    for s in samples:
        require(all(type(s[k]) is int and s[k] >= 0 for k in names), "invalid funding sample")
    required = 0
    for s in reversed(samples):
        after_uptake = required + s["due"] + (s["growth"] + s["reproduction"] if spending else 0)
        if after_uptake > 256:
            return None
        required = max(0, after_uptake - s["income"])
    return required


def funding(samples, opening):
    require(type(opening) is int and 0 <= opening <= 256, "invalid opening energy")
    result = {"opening": opening}
    for name, spending in (("maintenance_only", False), ("recorded_spending", True)):
        required = required_opening(samples, spending=spending)
        result[name] = {"required": required, "shortfall": max(0, required - opening) if required is not None else None}
    return result


def window(rows, receipts, samples, life, index, target):
    actual = energy.window(rows, receipts, life, index, target, after_growth=False)
    future = samples[index + 1:index + 1 + actual["samples_after_start"]]
    require(actual["energy_shortages"] == [s["tick"] for s in future if s["unpaid"]], "shortage event accounting differs")
    return {"actual": actual, "samples": future, "funding": funding(future, actual["initial"]),
            "due": sum(s["due"] for s in future), "paid": sum(s["paid"] for s in future),
            "unpaid": sum(s["unpaid"] for s in future)}


def morning(rows, receipts, samples, life, index):
    dawn = samples[index]
    require(dawn["phase"] == 0, "not a dawn")
    result = window(rows, receipts, samples, life, index, dawn["tick"] + 64 * STEP)
    future, boundaries = result["samples"], {}
    for name, predicate in (("global_light", lambda s: s["strength"] >= 64), ("income", lambda s: s["income"] > 0)):
        j = next((i for i, s in enumerate(future) if predicate(s)), None)
        boundaries[name] = None if j is None else {"tick": future[j]["tick"], "phase": future[j]["phase"],
            "income": future[j]["income"], "due_before": sum(s["due"] for s in future[:j]),
            "due_through": sum(s["due"] for s in future[:j + 1]),
            "funding": funding(future[:j + 1], dawn["final"])}
    payments = [s for s in [dawn, *future] if s["due"]]
    first_short = next((s["tick"] for s in payments if s["unpaid"]), None)
    first_paid = next((s["tick"] for s in payments if first_short is not None and
                       s["tick"] > first_short and not s["unpaid"]), None)
    return {**result, "at_dawn": dawn, "boundaries": boundaries, "first_shortage": first_short,
            "first_fully_paid_after_shortage": first_paid,
            "shortages_after_first_paid": [s["tick"] for s in payments if first_paid is not None and
                                           s["tick"] > first_paid and s["unpaid"]]}


def diagnostic(phase, strength, maintenance):
    """Current observations only; an unproductive estimated noon has no fallback."""
    require(type(phase) is int and 64 <= phase < 128 and type(strength) is int and 24 <= strength <= 255 and
            type(maintenance) is int and 1 <= maintenance <= 8192, "invalid dawn diagnostic input")
    beam = light.base_beam(phase)
    first = next((q for q in range(1, 65) if 24 + light.base_beam(q) * (strength - 24) // beam >= 64), None)
    payment = ((first + 3) // 4) * 4 if first is not None else None
    return {"status": "estimated" if first is not None else "unavailable", "first_phase": first,
            "payment_phase": payment, "reserve": payment // 4 * maintenance if payment is not None else None}


def assess(bid):
    e, d, a = bid["energy_gate"], bid["daylight_gate"], bid["afternoon_gate"]
    if bid["action"] == 0 or not 64 <= e["sun_phase"] < 128:
        return {"active": False, "estimate": None, "projected_margin": None, "stores_margin": None, "newly_rejects": False}
    estimate = diagnostic(e["sun_phase"], d["sun_strength"], e["maintenance"])
    active = d["active"]
    reserve = estimate["reserve"]
    projected = d["projected_sunset"] - e["night_upkeep"] - reserve if reserve is not None else None
    stores = a["margin"] - reserve if reserve is not None and a["applies"] else None
    rejects = None if reserve is None else projected < 0 or (stores is not None and stores < 0)
    return {"active": active, "estimate": estimate, "projected_margin": projected,
            "stores_margin": stores, "newly_rejects": rejects if active else False}


def summarize(histories):
    dawns = [d for h in histories for d in h["mornings"]]
    sunsets = [n for h in histories for n in h["sunsets"]]
    complete = [d for d in dawns if d["actual"]["status"] == "alive"]
    def distribution(values):
        return dict(sorted(Counter(str(v) for v in values).items()))
    return {"histories": len(histories), "samples": sum(h["saved_samples"] for h in histories),
            "sunsets": len(sunsets), "sunset_status": distribution(n["actual"]["status"] for n in sunsets),
            "mornings": len(dawns), "morning_status": distribution(d["actual"]["status"] for d in dawns),
            "mornings_with_shortages": sum(d["first_shortage"] is not None for d in dawns),
            "unpaid_at_dawn": sum(d["at_dawn"]["unpaid"] for d in dawns),
            "unpaid_after_dawn": sum(d["unpaid"] for d in dawns),
            "first_global_phase": distribution(d["boundaries"]["global_light"]["phase"] if d["boundaries"]["global_light"] else None for d in dawns),
            "first_income_phase": distribution(d["boundaries"]["income"]["phase"] if d["boundaries"]["income"] else None for d in dawns),
            "complete_morning_requirements": {name: distribution(d["funding"][name]["required"] for d in complete)
                                               for name in ("maintenance_only", "recorded_spending")}}


def analyze(data):
    check_capture(data)
    require([e["case"] for e in data["cases"]] == list(previous.CASES), "wrong dawn panel")
    histories, seen, seen_mornings = [], {}, {}
    for entry in data["cases"]:
        case = entry["case"]
        require(set(entry["arms"]) == set(previous.ARMS), "missing dawn arm")
        for arm in previous.ARMS:
            a, name = entry["arms"][arm]["analysis"], case["id"] + "/" + arm
            rows, receipts, lights, totals = light.check_history(case, a)
            life = a["focal"]["life"]
            samples = [sample(s, r, l) for s, r, l in zip(rows, receipts, lights, strict=True)]
            physical = previous.previous.physical(previous.strip_daylight(rows))
            identity = energy.identity({"life": life, "steps": physical})
            canonical = seen.setdefault(identity, name)
            mornings = [morning(rows, receipts, samples, life, i) for i, s in enumerate(samples) if s["phase"] == 0]
            for d in mornings:
                tick = d["at_dawn"]["tick"]
                index = (tick - case["tick"]) // STEP
                last = index + len(d["samples"]) + 1
                captured = energy.identity(physical[index:last])
                d["physical_sha256"] = captured
                d["canonical_morning"] = seen_mornings.setdefault(captured, name + "/" + str(tick))
            by_dawn = {d["at_dawn"]["tick"]: d for d in mornings}
            sunsets, events = [], []
            for i, s in enumerate(samples):
                if s["phase"] == 128:
                    dawn = s["tick"] + 128 * STEP
                    n = window(rows, receipts, samples, life, i, dawn + 64 * STEP)
                    n["night"] = window(rows, receipts, samples, life, i, dawn)
                    # The encompassing samples already contain the night's samples.
                    del n["night"]["samples"]
                    n["dawn_tick"] = dawn
                    n["morning_observed"] = dawn in by_dawn
                    n["nominal_night"] = 32 * max(1, (s["nodes"] + 7) // 8)
                    sunsets.append(n)
                if receipts[i]["growth"]:
                    selected = previous.winner(rows[i]["bids"], daylight=True)
                    bid = next(b for b in rows[i]["bids"] if b["tip"] == selected["tip"])
                    require(selected["eligible"] and bid["action"] != 0, "paid an ineligible bid")
                    forecast = None
                    if s["phase"] < 128:
                        event = energy.paid_event(rows, receipts, life, i, bid)
                        predicted = bid["daylight_gate"]["projected_sunset"] if bid["daylight_gate"]["active"] and bid["daylight_gate"]["applies"] else bid["energy_gate"]["projected_sunset"]
                        forecast = {"predicted": predicted, "sunset": event["sunset"],
                                    "error": predicted - event["sunset"]["final"] if event["sunset"]["status"] == "alive" else None}
                    check = assess(bid)
                    evaluation = None
                    if check["estimate"] is not None:
                        next_dawn = s["tick"] + (256 - s["phase"]) * STEP
                        m = by_dawn.get(next_dawn)
                        complete = m is not None and m["actual"]["status"] == "alive"
                        reserve = check["estimate"]["reserve"]
                        needed = m["funding"]["maintenance_only"]["required"] if complete else None
                        evaluation = {"dawn_tick": next_dawn, "complete": complete,
                            "actual_first_global_phase": m["boundaries"]["global_light"]["phase"] if complete and m["boundaries"]["global_light"] else None,
                            "actual_first_income_phase": m["boundaries"]["income"]["phase"] if complete and m["boundaries"]["income"] else None,
                            "actual_dawn_nodes": m["at_dawn"]["nodes"] if m else None,
                            "frozen_morning_requirement": needed,
                            "reserve_minus_requirement": reserve - needed if reserve is not None and needed is not None else None}
                    events.append({"tick": s["tick"], "phase": s["phase"], "bid": bid, "forecast": forecast,
                                   "diagnostic": check, "evaluation": evaluation})
            histories.append({"id": name, "case": case, "arm": arm, "life": life,
                "saved_samples": len(rows), "captured_history_sha256": identity, "canonical_history": canonical,
                "totals": totals, "mornings": mornings, "sunsets": sunsets, "purchases": events})
    candidates = [h for h in histories if h["arm"] == "candidate"]
    diagnostics = {h["id"]: {"active_purchases": sum(e["diagnostic"]["active"] for e in h["purchases"]),
        "newly_rejected": [e["tick"] for e in h["purchases"] if e["diagnostic"]["newly_rejects"]],
        "unavailable": [e["tick"] for e in h["purchases"] if e["diagnostic"]["active"] and e["diagnostic"]["newly_rejects"] is None]}
        for h in candidates}
    unique_mornings = [d for h in histories for d in h["mornings"]
                      if d["canonical_morning"] == h["id"] + "/" + str(d["at_dawn"]["tick"])]
    return {"histories": histories, "all_histories": summarize(histories),
            "unique_histories": summarize([h for h in histories if h["canonical_history"] == h["id"]]),
            "unique_morning_windows": {"count": len(unique_mornings),
                "with_shortages": sum(d["first_shortage"] is not None for d in unique_mornings)},
            "candidate_diagnostic": diagnostics, "capture_sources": CAPTURE_SOURCES, "limitations": LIMITATIONS}


def check_value(value):
    require(value["rule"] == RULE and value["input_sha256"] == INPUT_SHA and digest(ROOT / INPUT) == INPUT_SHA and
            value["protocol_sha256"] == digest(ROOT / PROTOCOL) and value["native_calls"] == value["training_runs"] == 0 and
            value["source_sha256"].get(PROTOCOL) == value["protocol_sha256"] and
            value["source_sha256"].get(INPUT) == INPUT_SHA and value["analysis"] == analyze(load_input()), "saved dawn audit differs")


def export(out):
    energy.export(out, experiment=sys.modules[__name__])


def verify(path):
    return energy.verify(path, experiment=sys.modules[__name__])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--out", type=Path)
    mode.add_argument("--verify", type=Path)
    args = parser.parse_args()
    try:
        export(args.out.resolve()) if args.out else verify(args.verify.resolve())
        return 0
    except (OSError, RuntimeError, ValueError, KeyError, TypeError, StopIteration, tarfile.TarError) as error:
        print("dawn audit failed: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
