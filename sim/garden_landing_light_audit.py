#!/usr/bin/env python3
"""Audit quantized light and income in complete saved lifetimes; no simulator."""

from __future__ import annotations

import argparse
from collections import Counter
from functools import cache
from pathlib import Path
import sys
import tarfile

import garden_landing_continuous_energy as previous
import garden_landing_energy_audit as energy
from garden_experiments import digest
from garden_resources import require

ROOT, DAY, STEP, STOP = previous.ROOT, previous.DAY, previous.STEP, previous.STOP
RULE = "garden-landing-light-audit-v1"
INPUT = "benchmarks/garden-seasons/landing-continuous-energy-results.json.gz"
INPUT_SHA = "143cfbb3a1064cadbe0b46b8c0907684928e7e2dc7e54b0a0502324648c3d1b5"
PROTOCOL = "benchmarks/garden-seasons/landing-light-audit-protocol.md"
# These are the captured sources, not a requirement that future working trees
# keep the same implementation. Bounds below apply only to this frozen build.
CAPTURE_SOURCES = {
    "src/garden_light.c": "5f5cf18c5f9079976ffce06e8b39627dd2a4f5ccf78dad31338f7e3fbff7e3bb",
    "src/garden_light.h": "12addc14869705cfdf4db128a4ff32ee92ff8cde76f06e5a63175e67cd694e73",
    "src/garden_world.c": "6fb1395fa0a5f66efab00cbdcc54654f0215c2e64537044b98ce712f60917ce9",
    "src/garden_world.h": "ab0ce75d4fe2e0e919ccea3124e84df475b99ed6e7cd2e308c3410869e780a23",
    "src/garden_agent.h": "194f497fe913f62f2a8606543749bfac0fe0327406ccdac614243c36d7d0b1db",
    "src/garden_climate.c": "523517697ca44a1da9bb372b2353736433ec139867858047bde2d4fd19834bb6",
    "sim/garden_landing_recruitment.c": "72cce8ce36c12aa30b97775f75e843f961c18dc748861de20d034d361c1752c7",
    "sim/garden_reserve_policy.c": "b18069fc4bb677a047eab70e4af73acc5e535ca07ba0d4314c4a6914ff29f034",
}
LIMITATIONS = [
    "Overlapping histories and purchase-to-sunset windows are not independent trials.",
    "No per-leaf light, positions or occluder identities: self/neighbor shade cannot be separated.",
    "The actual-body unshaded bound is not a no-shade counterfactual or a policy observation.",
    "The diagnostic holds current attenuation fixed; it does not know future climate or growth.",
    "Same-state rejected purchases are not simulated rescues or demonstrated regressions.",
    "Survival through day 256 is censored; all focal plants produced zero seeds.",
]


def check_capture(data):
    require(all(data["source_sha256"].get(k) == v for k, v in CAPTURE_SOURCES.items()),
            "unsupported captured light/uptake sources")
    for name in ("TOY_FACTORY_GARDEN_LEAF_MAINTENANCE", "TOY_FACTORY_GARDEN_CANOPY_TRANSMISSION"):
        require(data["settings"].get(name) == "OFF", "unsupported captured lighting experiment")


@cache
def load_input():
    data = previous.prior.load(ROOT / INPUT, INPUT_SHA)
    previous.check_value(data)
    check_capture(data)
    return data


def base_beam(phase):
    require(type(phase) is int and 0 <= phase < 256, "invalid sun phase")
    return (min(phase, 128 - phase) * 231 + 32) // 64 if phase <= 128 else 0


def strength(phase, light_percent):
    require(type(light_percent) is int and 0 <= light_percent <= 100, "invalid light percentage")
    return 24 + base_beam(phase) * light_percent // 100


def ray_step(phase):
    traversal = phase if phase <= 128 else 256 - phase
    return 12 - (traversal * 24 + 64) // 128


def diagnostic(phase, sun_strength, income):
    """Only current observations; deliberately no future weather/body argument."""
    require(0 <= phase < 128 and 24 <= sun_strength <= 255 and 0 <= income <= 255,
            "invalid daylight diagnostic input")
    remaining = 127 - phase
    if phase < 64:
        return {"applies": False, "useful_steps": None, "credit": income * remaining // 2}
    beam = base_beam(phase)
    useful = (sum(24 + base_beam(q) * (sun_strength - 24) // beam >= 64
                  for q in range(phase + 1, 128)) if sun_strength >= 64 and beam else 0)
    return {"applies": True, "useful_steps": useful, "credit": income * useful // 2}


def illumination(step, life, receipt):
    phase, sun = step["sun"]
    tick, plant = step["tick"], step["plant"]
    require(phase == (64 + tick // STEP) % 256 and
            sun == strength(phase, step["climate"]["light_percent"]), "recorded illumination/clock differs")
    born, dead = tick == life["birth_tick"], tick == life["death_tick"]
    income = receipt["income"]
    require(sun >= 64 or income == 0, "income in globally unproductive light")
    # Birth has no uptake; death resets progress after uptake. Neither post-step
    # leaf count describes that sample's absorbing canopy.
    bound = None if born or dead else plant["active_leaves"] * (sun // 64)
    require(bound is None or income <= bound, "income exceeds unshaded bound")
    return {"tick": tick, "phase": phase, "strength": sun,
            "light_percent": step["climate"]["light_percent"], "ray_step": ray_step(phase),
            "leaves": plant["active_leaves"], "income": income, "open_sky_upper": bound,
            "bound_excluded": "birth" if born else "death" if dead else None}


def check_history(case, analysis):
    rows, life = previous.steps(analysis), analysis["focal"]["life"]
    last = life["death_tick"] or STOP
    require([s["tick"] for s in rows] == list(range(case["tick"], last + STEP, STEP)), "incomplete focal history")
    before, receipts, lights, totals = None, [], [], previous.adults.budget()
    for index, step in enumerate(rows):
        require(step["plant"]["id"] == life["id"] == case["lineage"] and
                step["plant"]["birth"] == life["birth_tick"] == case["tick"], "wrong focal identity")
        receipt = previous.adults.transfers({"tick": step["tick"], **step["plant"]}, life, before)
        previous.adults.accumulate(totals, receipt, index == 0)
        receipts.append(receipt["energy"])
        lights.append(illumination(step, life, receipt["energy"]))
        before = step["plant"]["stages"][-1]
    return rows, receipts, lights, totals


def select_bid(step):
    if not step["bids"]:
        return None, False
    selected = previous.previous.winner(step["bids"], afternoon=True)
    return next(b for b in step["bids"] if b["tip"] == selected["tip"]), selected["eligible"]


def half_error(income, lit, dim, actual):
    terms = {"globally_dim": income * dim, "lit_window_remainder": income * lit - 2 * actual,
             "integer_rounding": -(income * (lit + dim) % 2)}
    require(sum(terms.values()) == 2 * (income * (lit + dim) // 2 - actual), "half-energy partition differs")
    return terms


def daylight_event(rows, receipts, lights, life, index, bid):
    event = energy.paid_event(rows, receipts, life, index, bid)
    e, current = bid["energy_gate"], lights[index]
    require(e["income"] == current["income"], "forecast uses wrong current income")
    future = lights[index + 1:index + 1 + event["sunset"]["samples_after_start"]]
    before_sunset = [r for r in future if r["tick"] < event["sunset"]["target_tick"]]
    complete = event["sunset"]["status"] == "alive"
    lit = sum(r["strength"] >= 64 for r in before_sunset)
    dim = len(before_sunset) - lit
    decomposition = None
    actual = event["sunset"]["transfers"]["income"]
    if complete:
        require(len(before_sunset) == e["daylight_steps"] - 1 and
                e["daylight_credit"] == e["income"] * len(before_sunset) // 2 and
                future[-1]["phase"] == 128 and future[-1]["income"] == 0, "wrong pre-sunset horizon")
        decomposition = half_error(e["income"], lit, dim, actual)
    leaves = [r["leaves"] for r in [current, *future]]
    percentages = [r["light_percent"] for r in [current, *future]]
    bound = (sum(r["open_sky_upper"] for r in future)
             if all(r["open_sky_upper"] is not None for r in future) else None)
    alt = diagnostic(event["phase"], current["strength"], e["income"])
    projected = min(256, bid["energy"] - e["cost"] + alt["credit"] - e["daylight_upkeep"])
    allowed = bid["energy"] - e["cost"] >= e["maintenance"] and projected >= e["night_upkeep"]
    changed = e["forecast_allowed"] and not allowed
    born = rows[index]["tick"] == life["birth_tick"]
    alt.update(projected_sunset=projected, forecast_allowed=allowed,
               newly_rejects_purchase=changed, birth_exempt=born,
               newly_rejects_nonbirth_purchase=changed and not born,
               changes_active_gate=changed and e["active"],
               income_error=alt["credit"] - actual if complete else None,
               sunset_error=projected - event["sunset"]["final"] if complete else None)
    return {**event, "current_light": current, "future_light": future,
            "illumination": {"complete_living_window": complete, "lit_steps": lit, "dim_steps": dim,
                "income_error_half_units": decomposition, "actual_body_open_sky_upper": bound,
                "actual_body_bound_minus_income": bound - actual if bound is not None else None,
                "leaves_min": min(leaves), "leaves_max": max(leaves), "leaves_unchanged": len(set(leaves)) == 1,
                "light_percent_min": min(percentages), "light_percent_max": max(percentages),
                "ray_changes": sum(a["ray_step"] != b["ray_step"] for a, b in zip([current, *future], future))},
            "diagnostic": alt}


def dawn_window(rows, receipts, lights, life, index):
    start = rows[index]["tick"]
    require(lights[index]["phase"] == 0, "not a dawn")
    samples = []
    end, reason = index, "capture-end"
    for j in range(index, len(rows)):
        s, r = rows[j], receipts[j]
        if s["tick"] > start + 64 * STEP:
            break
        end = j
        due = (max(1, (s["plant"]["stages"][0][4] + 7) // 8)
               if s["plant"]["uptake"] is not None and s["tick"] % (4 * STEP) == 0 else 0)
        paid = r["upkeep"]
        require(paid <= due and (due == 0 or paid == min(due, s["plant"]["stages"][0][0])),
                "dawn maintenance receipt differs")
        samples.append({**lights[j], "final_energy": r["final"], "maintenance_due": due,
                        "maintenance_paid": paid, "maintenance_unpaid": due - paid,
                        "energy_shortage": due > paid, "growth": r["growth"],
                        "reproduction": r["reproduction"], "overflow": r["overflow"], "discarded": r["discarded"]})
        if s["tick"] == life["death_tick"]:
            reason = "death"
            break
        if r["income"] > 0:
            reason = "first-income"
            break
        if s["tick"] == start + 64 * STEP:
            reason = "noon-without-income"
            break
    dark = [s for s in samples[1:] if s["income"] == 0]
    return {"tick": start, "initial_after_dawn": receipts[index]["final"],
            "observed_tick": rows[end]["tick"], "stop_reason": reason,
            "samples": samples, "balance": energy.window(rows, receipts, life, index, rows[end]["tick"],
                after_growth=False) if end > index else None,
            "before_first_income": {"samples_after_dawn": len(dark),
                "maintenance_due": sum(s["maintenance_due"] for s in dark),
                "maintenance_paid": sum(s["maintenance_paid"] for s in dark),
                "maintenance_unpaid": sum(s["maintenance_unpaid"] for s in dark),
                "shortages": [s["tick"] for s in dark if s["energy_shortage"]]}}


def error_summary(events):
    complete = [e for e in events if e["error"] is not None]
    result = {"complete_windows": len(complete)}
    for method in ("original", "diagnostic"):
        errors = [e["error"]["terms"]["income"] if method == "original" else e["diagnostic"]["income_error"] for e in complete]
        result[method] = {"signed_total": sum(errors), "absolute_total": sum(abs(v) for v in errors),
                          "largest_overestimate": max([0, *errors]), "largest_underestimate": -min([0, *errors])}
    result["smaller_absolute_error"] = sum(abs(e["diagnostic"]["income_error"]) < abs(e["error"]["terms"]["income"]) for e in complete)
    result["larger_absolute_error"] = sum(abs(e["diagnostic"]["income_error"]) > abs(e["error"]["terms"]["income"]) for e in complete)
    return result


def summarize(histories):
    counts = Counter(histories=len(histories), samples=sum(h["saved_samples"] for h in histories))
    phases, by_case = {}, {}
    for h in histories:
        alive = h["life"]["death_tick"] is None
        by_case[h["id"]] = {"daylight_purchases": len(h["events"]), "night_purchases": len(h["night_events"]),
            "afternoon_errors": error_summary([e for e in h["events"] if e["phase"] >= 64]),
            "new_nonbirth_rejections": [e["tick"] for e in h["events"] if e["diagnostic"]["newly_rejects_nonbirth_purchase"]]}
        counts["night_purchases"] += len(h["night_events"])
        counts["dawns"] += len(h["dawns"])
        counts["dawns_with_dark_shortage"] += sum(bool(d["before_first_income"]["shortages"]) for d in h["dawns"])
        for e in h["events"]:
            c = phases.setdefault(e["phase_band"], Counter())
            c["purchases"] += 1
            c["sunset_" + e["sunset"]["status"]] += 1
            c["clean_interval"] += e["clean_interval"]
            c["unchanged_leaves"] += e["illumination"]["leaves_unchanged"]
            c["diagnostic_new_rejections"] += e["diagnostic"]["newly_rejects_purchase"]
            c["diagnostic_nonbirth_rejections"] += e["diagnostic"]["newly_rejects_nonbirth_purchase"]
            c["diagnostic_active_rejections"] += e["diagnostic"]["changes_active_gate"]
            c["diagnostic_nonbirth_survivor_rejections"] += e["diagnostic"]["newly_rejects_nonbirth_purchase"] and alive
            if e["error"] is not None:
                c["old_income_overestimates"] += e["error"]["terms"]["income"] > 0
                c["new_income_overestimates"] += e["diagnostic"]["income_error"] > 0
                c["new_income_underestimates"] += e["diagnostic"]["income_error"] < 0
                c["sunset_below_nominal_night"] += not e["sunset_covers_nominal_night"]
                c["clean_old_overestimates"] += e["clean_interval"] and e["error"]["terms"]["income"] > 0
                c["clean_new_overestimates"] += e["clean_interval"] and e["diagnostic"]["income_error"] > 0
    events = [e for h in histories for e in h["events"]]
    return {**dict(counts), "by_phase": {k: dict(v) for k, v in phases.items()}, "by_case": by_case,
            "income_errors": {phase: error_summary([e for e in events if e["phase_band"] == phase]) for phase in phases},
            "clean_afternoon_errors": error_summary([e for e in events if e["phase"] >= 64 and e["clean_interval"]])}


def analyze(data):
    check_capture(data)
    require([e["case"] for e in data["cases"]] == list(previous.CASES), "wrong light audit panel")
    histories, seen = [], {}
    for entry in data["cases"]:
        case = entry["case"]
        require(set(entry["arms"]) == set(previous.ARMS), "missing light audit arm")
        for arm in previous.ARMS:
            a = entry["arms"][arm]["analysis"]
            rows, receipts, lights, totals = check_history(case, a)
            name, life = case["id"] + "/" + arm, a["focal"]["life"]
            captured = energy.identity({"life": life, "steps": previous.physical(rows)})
            canonical = seen.setdefault(captured, name)
            events, nights, dawns = [], [], []
            for index, step in enumerate(rows):
                bid, eligible = select_bid(step)
                if receipts[index]["growth"]:
                    require(bid is not None and eligible and bid["action"] != 0, "paid an ineligible/missing winner")
                    if step["sun"][0] < 128:
                        events.append(daylight_event(rows, receipts, lights, life, index, bid))
                    else:
                        require(step["plant"]["stages"][2][0] == bid["energy"] and
                                not bid["energy_gate"]["forecast_allowed"] and not bid["energy_gate"]["active"],
                                "paid night action despite active guard")
                        nights.append({"tick": step["tick"], "bid": bid, "energy": receipts[index],
                                       "stages": step["plant"]["stages"]})
                if step["sun"][0] == 0:
                    dawns.append(dawn_window(rows, receipts, lights, life, index))
            bounds = [r for r in lights if r["open_sky_upper"] is not None]
            histories.append({"id": name, "case": case, "arm": arm, "life": life,
                "captured_history_sha256": captured, "canonical_history": canonical,
                "saved_samples": len(rows), "totals": totals,
                "light_checks": {"bounded_samples": len(bounds),
                    "birth_excluded": sum(r["bound_excluded"] == "birth" for r in lights),
                    "death_excluded": sum(r["bound_excluded"] == "death" for r in lights),
                    "globally_dim_samples": sum(r["strength"] < 64 for r in lights),
                    "bounded_income": sum(r["income"] for r in bounds),
                    "actual_body_open_sky_upper": sum(r["open_sky_upper"] for r in bounds)},
                "events": events, "night_events": nights, "dawns": dawns})
    return {"histories": histories, "all_histories": summarize(histories),
            "unique_histories": summarize([h for h in histories if h["id"] == h["canonical_history"]]),
            "capture_sources": CAPTURE_SOURCES, "limitations": LIMITATIONS}


def check_value(value):
    require(value["rule"] == RULE and value["input_sha256"] == INPUT_SHA and digest(ROOT / INPUT) == INPUT_SHA and
            value["protocol_sha256"] == digest(ROOT / PROTOCOL) and
            value["native_calls"] == value["training_runs"] == 0 and
            value["source_sha256"].get(PROTOCOL) == value["protocol_sha256"] and
            value["source_sha256"].get(INPUT) == INPUT_SHA and
            value["analysis"] == analyze(load_input()), "saved light audit differs")


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
        if args.out:
            export(args.out.resolve())
        else:
            verify(args.verify.resolve())
        return 0
    except (OSError, RuntimeError, ValueError, KeyError, TypeError, StopIteration, tarfile.TarError) as error:
        print("light audit failed: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
