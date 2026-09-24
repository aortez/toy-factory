#!/usr/bin/env python3
"""Score one fixed phase-aware energy forecast on every saved seed purchase."""
from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

import garden_renewal_seed_forecast as prior

experiment, startup, require = prior.experiment, prior.startup, prior.require
RULE = "garden-renewal-phase-forecast-v1"
PROTOCOL = "benchmarks/garden-longevity/renewal-phase-forecast-protocol.md"
OLD_SUMMARY = "benchmarks/garden-longevity/renewal-seed-forecast-summary.json"
OLD_SHA = "0a239e0921521c06bbb71c4b60fb73f8baab55402630bf1b36d462e20fa623fa"
BODY = ("nodes", "roots", "leaves", "active_leaves")
OPTIONAL = ("energy_growth", "energy_renewal", "energy_seeds")


def sun_strength(phase):
    require(isinstance(phase, int) and 0 <= phase <= 255, "invalid sun phase")
    height = min(phase, 128 - phase) if phase <= 128 else 0
    return 24 + (height * 231 + 32) // 64


def boundaries(tick):
    require(isinstance(tick, int) and tick > 0 and tick % 60 == 0, "invalid purchase tick")
    phase = (64 + tick // 15) % 256
    require(0 < phase < 128, "purchase outside daylight")
    dawn = tick + (256 - phase) * 15
    return {"sunset": tick + (128 - phase) * 15, "dawn": dawn,
            "first_possible_income": dawn + 11 * 15, "noon": dawn + 64 * 15}


def project(tick, energy, income, nodes, stress):
    """Only decision-time inputs; energy stress assumes sufficient future water.

    Potential income is diagnostic even after a predicted death. Credited
    income and all state changes stop at death, as they do in the native world.
    """
    bounds = boundaries(tick)
    require(all(isinstance(v, int) for v in (energy, income, nodes, stress)) and
            0 <= energy <= 256 and 0 <= income < 255 and 1 <= nodes <= 512 and 0 <= stress < 8,
            "invalid forecast anchor")
    tier = sun_strength((64 + tick // 15) % 256) // 64
    result = {"supported": tier > 0, "reason": None if tier else "zero-current-light-tier",
              "anchor_tier": tier, "boundaries": bounds, "steps": {}}
    if not tier:
        return result
    upkeep, death, first_shortage = (nodes + 7) // 8, None, None
    peak, unpaid_total = stress, 0
    for when in range(tick + 15, bounds["noon"] + 1, 15):
        phase = (64 + when // 15) % 256
        potential = income * (sun_strength(phase) // 64) // tier
        credit = overflow = due = paid = unpaid = 0
        if death is None:
            credit = potential
            overflow = max(0, energy + credit - 256)
            energy = min(256, energy + credit)
            if when % 60 == 0:
                due, paid = upkeep, min(energy, upkeep)
                unpaid = due - paid
                energy -= paid
                stress = stress + 1 if unpaid else max(0, stress - 1)
                if unpaid and first_shortage is None:
                    first_shortage = when
                if stress == 8:
                    death, energy = when, 0
            peak = max(peak, stress)
            unpaid_total += unpaid
        result["steps"][when] = {"energy": energy, "stress": stress, "dead": death is not None,
            "potential_income": potential, "credited_income": credit, "overflow": overflow,
            "upkeep_required": due, "upkeep_paid": paid, "upkeep_unpaid": unpaid}
    result.update(death_tick=death, first_shortage_tick=first_shortage, peak_stress=peak,
                  unpaid_energy=unpaid_total)
    return result


def check_stress(old, plant, tick, values):
    """Validate observed live transitions independently of the shadow forecast."""
    if tick % 60:
        require(plant["stress"] == old["stress"] and plant["flags"] & 6 == old["flags"] & 6,
                "stress/shortage changed outside maintenance")
        return
    energy_short = values["energy_upkeep"] < (old["nodes"] + 7) // 8
    water_short = values["water_upkeep"] < (old["nodes"] - old["roots"] + 7) // 8
    expected = old["stress"] + 1 if energy_short or water_short else max(0, old["stress"] - 1)
    require(plant["stress"] == expected and bool(plant["flags"] & 2) == energy_short and
            bool(plant["flags"] & 4) == water_short, "observed stress does not reconcile")


def observe(samples, identity, start, end):
    """Keep actual live ledgers, future assumption breaks and censoring explicit."""
    require(start < end and start % 15 == end % 15 == 0, "invalid observation horizon")
    first = prior.sample(samples, start, identity)
    require(first is not None and not first["dead"], "invalid starting parent")
    stop = min(end, max(samples))
    require(stop >= start, "trace ends before purchase")
    previous, death, last_live = first, None, start
    totals, steps, breaks = Counter(), {}, {}
    first_shortage, peak = None, first["stress"]
    for tick in range(start + 15, stop + 1, 15):
        p = prior.sample(samples, tick, identity)
        require(p is not None, "living parent disappeared")
        if p["flags"] & 4:
            breaks.setdefault("water_shortage", {"tick": tick})
        if p["dead"]:
            require(tick % 60 == 0 and previous["stress"] == 7 and p["stress"] == 8 and p["flags"] & 6,
                    "unexplained terminal stress transition")
            require(all(p[k] == 0 for k in ("energy", "water", "energy_income", "water_income")),
                    "unexpected uncleared terminal telemetry")
            death = {"tick": tick, "cause": startup.SHORTAGES[p["flags"] & 6]}
            peak = 8
            break  # Neither current income nor paid upkeep survives mark_plant_dead.
        values = startup.resources.budget(previous, p, tick)
        check_stress(previous, p, tick, values)
        fields = [k for k in BODY if p[k] != first[k]]
        if fields:
            breaks.setdefault("body_change", {"tick": tick, "fields": fields})
        if any(values[k] for k in OPTIONAL):
            breaks.setdefault("optional_spending", {"tick": tick, "costs": {k: values[k] for k in OPTIONAL}})
        if p["flags"] & 2 and first_shortage is None:
            first_shortage = tick
        totals.update(values)
        steps[tick] = {"energy": p["energy"], "stress": p["stress"], "income": p["energy_income"]}
        previous, last_live = p, tick
        peak = max(peak, p["stress"])
    require(first["energy"] + totals["energy_income"] - sum(totals[k] for k in prior.ENERGY_COSTS)
            == previous["energy"], "actual live budget does not telescope")
    censored = death is None and end > stop
    first_break = min((b["tick"] for b in breaks.values()), default=None)
    return {"outcome": "dead" if death else "right-censored" if censored else "alive",
            "death": death, "horizon_tick": end, "trace_end": max(samples),
            "last_live_tick": last_live, "terminal_step_not_reconstructed": None if death is None else death["tick"],
            "checked_live_steps": len(steps), "budget": dict(totals), "peak_stress": peak,
            "first_energy_shortage_tick": first_shortage, "assumption_breaks": breaks,
            "first_assumption_break_tick": first_break, "steps": steps}


def error_stats(values):
    values = list(values)
    return {"count": len(values), "signed_sum": sum(values), "absolute_sum": sum(abs(v) for v in values),
            "maximum_absolute": max((abs(v) for v in values), default=None)}


def merge_errors(values):
    values = list(values)
    return {"count": sum(v["count"] for v in values), "signed_sum": sum(v["signed_sum"] for v in values),
            "absolute_sum": sum(v["absolute_sum"] for v in values),
            "maximum_absolute": max((v["maximum_absolute"] for v in values if v["count"]), default=None)}


def compare(prediction, actual, legacy):
    result = {"endpoints": {}, "errors": {}}
    supported = prediction["supported"]
    cut = actual["first_assumption_break_tick"]
    for name, tick in prediction["boundaries"].items():
        if actual["death"] and actual["death"]["tick"] <= tick:
            status = "observed-dead"
        elif tick > actual["trace_end"]:
            status = "trace-censored"
        else:
            status = "living"
        point = {"tick": tick, "status": status, "assumptions_held": cut is None or tick < cut}
        if supported:
            point["prediction"] = prediction["steps"][tick]
        if status == "living":
            point["actual"] = actual["steps"][tick]
            if supported:
                point["energy_error"] = point["prediction"]["energy"] - point["actual"]["energy"]
            if name == "sunset":
                point["legacy_energy"] = legacy["projected_sunset"]
                point["legacy_energy_error"] = legacy["projected_sunset"] - point["actual"]["energy"]
        result["endpoints"][name] = point
    if not supported:
        return result
    for label, ticks in (("all_live", list(actual["steps"])),
                         ("assumption_valid_prefix", [t for t in actual["steps"] if cut is None or t < cut])):
        result["errors"][label] = {}
        for key, field, observed in (("energy", "energy", "energy"), ("stress", "stress", "stress"),
                                      ("potential_income", "potential_income", "income")):
            errors = {t: prediction["steps"][t][field] - actual["steps"][t][observed] for t in ticks}
            worst = max(errors, key=lambda t: abs(errors[t])) if errors else None
            result["errors"][label][key] = {**error_stats(errors.values()),
                "worst_sample": None if worst is None else {"tick": worst, "error": errors[worst],
                    "predicted": prediction["steps"][worst][field], "actual": actual["steps"][worst][observed]}}
    result["death_prediction"] = {
        "predicted_tick": prediction["death_tick"], "actual": actual["outcome"],
        "actual_tick": None if actual["death"] is None else actual["death"]["tick"],
        "assumptions_held_through_observed_outcome": cut is None,
        "early_while_observed_alive": prediction["death_tick"] is not None and
            prediction["death_tick"] <= actual["last_live_tick"]}
    return result


def audit_purchase(samples, case, identity, tick):
    decision = prior.decision(samples, identity, tick)
    p = prior.sample(samples, tick, identity)
    require(p["stress"] == 0, "seed purchased while stressed")
    prediction = project(tick, p["energy"], p["energy_income"], p["nodes"], p["stress"])
    actual = observe(samples, identity, tick, prediction["boundaries"]["noon"])
    comparison = compare(prediction, actual, decision["forecast"])
    return {"key": f"{case}.{identity}.{tick}", "case": case,
            "decision": {k: v for k, v in decision.items() if k != "forecast"},
            "legacy_forecast": {k: v for k, v in decision["forecast"].items() if k != "steps"},
            "prediction": {k: v for k, v in prediction.items() if k != "steps"},
            "actual": {k: v for k, v in actual.items() if k != "steps"}, "comparison": comparison}


def confusion(records, *, clean):
    counts = Counter()
    for r in records:
        if not r["prediction"]["supported"]:
            counts["unsupported"] += 1
            continue
        observed = r["actual"]
        if clean and observed["first_assumption_break_tick"] is not None:
            counts["assumption_broken"] += 1
            continue
        if observed["outcome"] == "right-censored":
            counts["right_censored"] += 1
            continue
        predicted = r["prediction"]["death_tick"] is not None
        actual = observed["outcome"] == "dead"
        counts["true_death" if predicted and actual else "missed_death" if actual else
               "false_death" if predicted else "true_survival"] += 1
    require(sum(counts.values()) == len(records), "death comparison lost records")
    return dict(counts)


def summarize(records):
    supported = [r for r in records if r["prediction"]["supported"]]
    endpoints = [r["comparison"]["endpoints"]["sunset"] for r in supported]
    sunset = {}
    for label, points in (("all_living", [p for p in endpoints if p["status"] == "living"]),
                          ("assumptions_held", [p for p in endpoints if p["status"] == "living" and p["assumptions_held"]])):
        sunset[label] = {"phase": error_stats(p["energy_error"] for p in points),
                         "legacy": error_stats(p["legacy_energy_error"] for p in points)}
    deaths = {(r["case"], r["decision"]["id"], r["actual"]["death"]["tick"])
              for r in records if r["actual"]["death"]}
    return {"purchases": len(records), "supported": len(supported),
            "distinct_parent_deaths_in_windows": len(deaths),
            "species": dict(Counter(r["decision"]["species"] for r in records)),
            "outcomes": dict(Counter(r["actual"]["outcome"] for r in records)),
            "legacy_allowed": sum(r["legacy_forecast"]["allowed"] for r in records),
            "assumption_breaks": {k: sum(k in r["actual"]["assumption_breaks"] for r in records)
                                  for k in ("body_change", "optional_spending", "water_shortage")},
            "checked_live_steps_overlapping_windows": sum(r["actual"]["checked_live_steps"] for r in records),
            "sunset_error": sunset,
            "errors": {label: {key: merge_errors(r["comparison"]["errors"][label][key] for r in supported)
                               for key in ("energy", "stress", "potential_income")}
                       for label in ("all_live", "assumption_valid_prefix")},
            "death_comparison_all": confusion(records, clean=False),
            "death_comparison_assumptions_held": confusion(records, clean=True)}


def analyze(root):
    records, by_case = [], {}
    for case in prior.prior.CASES:
        rows = [r for r in startup.read_trace(root / f"traces/{case}.jsonl.gz") if r["type"] == "world"]
        require([r["tick"] for r in rows] == list(range(0, startup.STOP + 1, 15)), "missing/reordered census")
        require(all(r["sun_phase"] == (64 + r["tick"] // 15) % 256 and
                    r["sun_strength"] == sun_strength(r["sun_phase"]) for r in rows), "sun formula differs from trace")
        samples = {r["tick"]: r for r in rows}
        purchases = [(r["tick"], p["id"]) for r in rows for p in r["plants"]
                     if not p["dead"] and p["reproduction_cooldown"] == 16]
        require(len(purchases) == rows[-1]["seeds_created"], "not all purchases captured")
        by_case[case] = [audit_purchase(samples, case, identity, tick) for tick, identity in purchases]
        records.extend(by_case[case])
    common = {}
    for case, cases in by_case.items():
        common[case] = {(r["decision"]["tick"], r["decision"]["id"]): r["decision"] for r in cases
                        if r["decision"]["tick"] < prior.PURCHASE}
    require(common["control"] == common["veto"], "shared-prefix purchases differ")
    require(len(by_case["control"]) == 52 and len(by_case["veto"]) == 60, "fixed purchase inventory changed")
    return {"rule": RULE, "baseline_manifest_sha256": prior.BASELINE_SHA,
            "previous_audit_sha256": OLD_SHA, "new_native_calls": 0,
            "analysis_sources": {name: experiment.digest(experiment.ROOT / name) for name in
                                 ("sim/garden_renewal_phase_forecast.py", PROTOCOL)},
            "frozen_sources": prior.check_frozen_sources(root),
            "role": "reused-world shadow energy/stress diagnostic; no gating policy",
            "shared_prefix_purchases_per_trace": len(common["control"]),
            "summary": {"all": summarize(records), **{c: summarize(v) for c, v in by_case.items()}},
            "purchases": records}


def verify(root):
    require(experiment.digest(experiment.ROOT / OLD_SUMMARY) == OLD_SHA, "previous audit changed")
    require(prior.verify(root) == experiment.read_json(experiment.ROOT / OLD_SUMMARY), "previous audit no longer reproduces")
    result = analyze(root)
    require(result == analyze(root), "phase forecast analysis repeat differs")
    require(experiment.digest(root / "manifest.json") == prior.BASELINE_SHA, "baseline manifest changed")
    manifest = experiment.read_json(root / "manifest.json")
    for name in manifest["artifacts"]:
        prior.prior.gallery.artifact(root, manifest, name)
    require(result["frozen_sources"] == prior.check_frozen_sources(root), "frozen sources changed")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, default=experiment.ROOT / "artifacts/garden-renewal-seed-veto-v1")
    output = parser.add_mutually_exclusive_group()
    output.add_argument("--output", type=Path, help="write fresh portable JSON; no overwrite")
    output.add_argument("--check", type=Path, help="verify existing portable JSON")
    args = parser.parse_args()
    root = args.baseline.resolve()
    if args.output:
        require(not args.output.exists() and not args.output.resolve().is_relative_to(root),
                "choose fresh output outside the frozen bundle")
    result = verify(root)
    if args.output:
        experiment.write_json(args.output, result)
    if args.check:
        require(experiment.read_json(args.check) == result, "portable phase forecast differs")
    for name, summary in result["summary"].items():
        s = summary["sunset_error"]["all_living"]
        print(f"{name}: {summary['purchases']} purchases, {summary['supported']} supported; "
              f"paired sunset absolute error phase/legacy={s['phase']['absolute_sum']}/{s['legacy']['absolute_sum']} "
              f"over {s['phase']['count']} live sunsets; deaths={summary['death_comparison_all']}")
    print("Verified fixed phase-aware shadow audit; zero new native calls")


if __name__ == "__main__":
    main()
