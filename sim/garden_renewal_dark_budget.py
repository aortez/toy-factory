#!/usr/bin/env python3
"""Audit exact energy/stress budgets only until sunlight could next pay income."""
from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

import garden_renewal_phase_forecast as prior

experiment, startup, require = prior.experiment, prior.startup, prior.require
seed_audit, capture = prior.prior, prior.prior.prior
RULE = "garden-renewal-dark-budget-v1"
PROTOCOL = "benchmarks/garden-longevity/renewal-dark-budget-protocol.md"
OLD_SUMMARY = "benchmarks/garden-longevity/renewal-phase-forecast-summary.json"
OLD_SHA = "f716bc85c47659f03c4b8b7e6fe10c05936a566444feea543879c56a4fb60f6f"
BASELINE_SHA = seed_audit.BASELINE_SHA
sample = seed_audit.sample
KINDS = ("growth", "renewal", "seeds")


def horizon(tick):
    require(type(tick) is int and tick >= 0 and tick % 15 == 0, "invalid anchor tick")
    for offset in range(1, 257):
        when = tick + offset * 15
        if prior.sun_strength((64 + when // 15) % 256) >= 64:
            break
    else:
        raise RuntimeError("sun cycle has no possible income")
    return {"first_possible_income_tick": when, "last_dark_tick": when - 15,
            "dark_steps": offset - 1,
            "maintenance_ticks": list(range(tick + 60 - tick % 60, when, 60))}


def project(tick, energy, nodes, stress):
    """Decision-time inputs only; fixed energy upkeep, no expenses, adequate water.

    The first potentially productive step is excluded, including its maintenance.
    Nothing here predicts actual morning income or a causal effect of a veto.
    """
    require(all(type(v) is int for v in (energy, nodes, stress)) and
            0 <= energy <= 256 and 1 <= nodes <= 512 and 0 <= stress < 8,
            "invalid dark-budget anchor")
    bounds = horizon(tick)
    result = {"supported": bounds["dark_steps"] > 0, "boundaries": bounds, "steps": {}}
    if not result["supported"]:
        result["reason"] = "next-step-could-earn-income"
        return result
    upkeep, death, first_shortage = (nodes + 7) // 8, None, None
    peak, paid_total, unpaid_total = stress, 0, 0
    for when in range(tick + 15, bounds["first_possible_income_tick"], 15):
        paid = unpaid = due = 0
        if death is None and when % 60 == 0:
            due, paid = upkeep, min(energy, upkeep)
            unpaid = due - paid
            energy -= paid
            stress = stress + 1 if unpaid else max(0, stress - 1)
            if unpaid and first_shortage is None:
                first_shortage = when
            if stress == 8:
                death, energy = when, 0
        paid_total += paid
        unpaid_total += unpaid
        peak = max(peak, stress)
        result["steps"][when] = {"energy": energy, "stress": stress, "dead": death is not None,
                                "upkeep_required": due, "upkeep_paid": paid, "upkeep_unpaid": unpaid}
    result.update(maintenance_cost=upkeep,
        fixed_body_demand_to_boundary=upkeep * len(bounds["maintenance_ticks"]),
        upkeep_paid_until_death_or_boundary=paid_total, upkeep_unpaid_until_death_or_boundary=unpaid_total,
        first_shortage_tick=first_shortage, death_tick=death, peak_stress=peak,
        final={"energy": energy, "stress": stress, "dead": death is not None},
        classification="death" if death else "shortage-alive" if first_shortage is not None else
                       "all-paid" if bounds["maintenance_ticks"] else "no-maintenance")
    return result


def compact(prediction):
    return {k: v for k, v in prediction.items() if k != "steps"}


def spending_stages(old, plant, tick, values):
    """Undo only optional expenses, retaining current uptake and old-body upkeep."""
    nodes = 4 if old is None else old["nodes"]
    energy = plant["energy"] + sum(values[f"energy_{k}"] for k in KINDS)
    water = plant["water"] + sum(values[f"water_{k}"] for k in KINDS)
    require(0 <= energy <= 256 and 0 <= water <= 512, "invalid pre-spending stores")
    require(plant["nodes"] >= nodes and
            (values["energy_growth"] or plant["nodes"] == nodes), "unexplained body change")
    stages = []
    for kind in KINDS:
        cost = values[f"energy_{kind}"]
        if not cost:
            continue
        before = {"energy": energy, "water": water, "nodes": nodes, "stress": plant["stress"]}
        energy -= cost
        water -= values[f"water_{kind}"]
        if kind == "growth":
            nodes = plant["nodes"]
        after = {"energy": energy, "water": water, "nodes": nodes, "stress": plant["stress"]}
        a, b = (project(tick, p["energy"], p["nodes"], p["stress"]) for p in (before, after))
        effect = None
        if a["supported"]:
            effect = ("already-fatal" if a["death_tick"] is not None else
                      "becomes-fatal" if b["death_tick"] is not None else "both-alive-at-boundary")
        stages.append({"kind": kind,
            "action": ("extend" if values["extensions"] else "finish") if kind == "growth" else kind,
            "energy_cost": cost, "water_cost": values[f"water_{kind}"], "before": before, "after": after,
            "before_budget": compact(a), "after_budget": compact(b), "local_effect": effect})
    require((energy, water, nodes) == (plant["energy"], plant["water"], plant["nodes"]),
            "spending stages do not reconcile")
    return stages


def observe(samples, identity, start, end):
    require(start < end and start % 15 == end % 15 == 0, "invalid dark observation window")
    first = sample(samples, start, identity)
    require(first is not None and not first["dead"], "invalid starting plant")
    previous, death, last_live = first, None, start
    totals, steps, breaks = Counter(), {}, {}
    first_shortage, peak = None, first["stress"]
    for tick in range(start + 15, min(end, max(samples)) + 1, 15):
        require(prior.sun_strength((64 + tick // 15) % 256) < 64, "observation crosses dark boundary")
        p = sample(samples, tick, identity)
        require(p is not None, "living plant disappeared")
        # Flags persist between maintenance steps; an old flag is not a new debit.
        if tick % 60 == 0 and p["flags"] & 4:
            breaks.setdefault("water_shortage", {"tick": tick})
        if tick % 60 == 0 and p["flags"] & 2 and first_shortage is None:
            first_shortage = tick
        if p["dead"]:
            require(tick % 60 == 0 and previous["stress"] == 7 and p["stress"] == 8 and p["flags"] & 6,
                    "unexplained terminal stress transition")
            require(all(p[k] == 0 for k in ("energy", "water", "energy_income", "water_income")),
                    "unexpected uncleared terminal telemetry")
            death = {"tick": tick, "cause": startup.SHORTAGES[p["flags"] & 6]}
            peak = 8
            break  # No observed terminal income or payment can be reconstructed.
        values = startup.resources.budget(previous, p, tick)
        prior.check_stress(previous, p, tick, values)
        require(p["energy_income"] == 0, "nonzero income inside guaranteed-dark interval")
        if (p["nodes"] + 7) // 8 != (first["nodes"] + 7) // 8:
            breaks.setdefault("energy_upkeep_change", {"tick": tick, "nodes": p["nodes"]})
        if any(values[f"energy_{k}"] for k in KINDS):
            breaks.setdefault("optional_spending", {"tick": tick,
                "costs": {k: values[f"energy_{k}"] for k in KINDS}})
        totals.update(values)
        steps[tick] = {"energy": p["energy"], "stress": p["stress"]}
        previous, last_live = p, tick
        peak = max(peak, p["stress"])
    require(first["energy"] - sum(totals[k] for k in seed_audit.ENERGY_COSTS) == previous["energy"],
            "actual dark budget does not telescope")
    return {"outcome": "dead" if death else "right-censored" if end > max(samples) else "alive",
            "death": death, "horizon_tick": end, "trace_end": max(samples), "last_live_tick": last_live,
            "last_live_state": {k: previous[k] for k in ("energy", "stress")},
            "terminal_step_not_reconstructed": None if death is None else death["tick"],
            "checked_live_steps": len(steps), "budget": dict(totals), "peak_stress": peak,
            "first_energy_shortage_tick": first_shortage, "assumption_breaks": breaks,
            "first_assumption_break_tick": min((b["tick"] for b in breaks.values()), default=None),
            "steps": steps}


def compare(prediction, actual):
    require(prediction["supported"] and actual["horizon_tick"] == prediction["boundaries"]["last_dark_tick"],
            "comparison requires matching dark horizon")
    cut = actual["first_assumption_break_tick"]
    errors = {}
    for label, ticks in (("all_live", list(actual["steps"])),
                         ("valid_prefix", [t for t in actual["steps"] if cut is None or t < cut])):
        errors[label] = {}
        for key in ("energy", "stress"):
            diffs = {t: prediction["steps"][t][key] - actual["steps"][t][key] for t in ticks}
            worst = max(diffs, key=lambda t: abs(diffs[t])) if diffs else None
            errors[label][key] = {**prior.error_stats(diffs.values()),
                "worst_sample": None if worst is None else {"tick": worst, "error": diffs[worst],
                    "predicted": prediction["steps"][worst][key], "actual": actual["steps"][worst][key]}}
        if label == "valid_prefix":
            require(all(errors[label][k]["absolute_sum"] == 0 for k in ("energy", "stress")),
                    "exact dark-budget prefix mismatch")
            require(all(not prediction["steps"][t]["dead"] for t in ticks), "predicted death before live prefix")
    if cut is not None:
        status = "assumption-broken"
    elif actual["outcome"] == "right-censored":
        status = "right-censored"
    elif actual["death"]:
        require(prediction["death_tick"] == actual["death"]["tick"] and actual["death"]["cause"] == "energy",
                "exact dark-budget death mismatch")
        status = "exact-death"
    else:
        require(prediction["death_tick"] is None, "exact dark-budget survival mismatch")
        status = "exact-alive-at-boundary"
    if status.startswith("exact-"):
        require(prediction["first_shortage_tick"] == actual["first_energy_shortage_tick"] and
                prediction["peak_stress"] == actual["peak_stress"], "exact dark-budget stress summary mismatch")
    return {"status": status, "errors": errors}


def audit_state(samples, case, identity, tick, panel, stages=None, values=None):
    p = sample(samples, tick, identity)
    require(p is not None and not p["dead"], "invalid audited plant")
    prediction = project(tick, p["energy"], p["nodes"], p["stress"])
    actual = comparison = None
    if prediction["supported"]:
        actual = observe(samples, identity, tick, prediction["boundaries"]["last_dark_tick"])
        comparison = compare(prediction, actual)
    return {"key": f"{case}.{identity}.{tick}", "case": case, "panel": panel,
            "anchor": {"tick": tick, "sun_phase": samples[tick]["sun_phase"],
                **{k: p[k] for k in ("id", "species", "energy", "water", "nodes", "stress")}},
            "stages": stages, "current_step_budget": values, "prediction": compact(prediction),
            "actual": None if actual is None else {k: v for k, v in actual.items() if k != "steps"},
            "comparison": comparison}


def summarize(records):
    supported = [r for r in records if r["prediction"]["supported"]]
    stages = [s for r in records for s in r["stages"] or []]
    deaths = {(r["case"], r["anchor"]["id"], r["actual"]["death"]["tick"])
              for r in supported if r["actual"]["death"]}
    clean = [r for r in supported if r["comparison"]["status"].startswith("exact-")]
    return {"anchors": len(records), "supported": len(supported),
            "out_of_scope": len(records) - len(supported),
            "expenses": dict(Counter(s["kind"] for s in stages)),
            "covered_expenses": dict(Counter(s["kind"] for s in stages if s["after_budget"]["supported"])),
            "local_effects": dict(Counter(s["local_effect"] for s in stages if s["local_effect"])),
            "predictions": dict(Counter(r["prediction"]["classification"] for r in supported)),
            "observed_outcomes": dict(Counter(r["actual"]["outcome"] for r in supported)),
            "comparisons": dict(Counter(r["comparison"]["status"] for r in supported)),
            "complete_clean_predictions": dict(Counter(r["prediction"]["classification"] for r in clean)),
            "distinct_case_specific_deaths": len(deaths),
            "assumption_breaks": {k: sum(k in r["actual"]["assumption_breaks"] for r in supported)
                                  for k in ("energy_upkeep_change", "optional_spending", "water_shortage")},
            "checked_live_steps_overlapping_windows": sum(r["actual"]["checked_live_steps"] for r in supported),
            "errors": {label: {k: prior.merge_errors(r["comparison"]["errors"][label][k] for r in supported)
                               for k in ("energy", "stress")} for label in ("all_live", "valid_prefix")}}


def analyze(root):
    panels = {"spending": [], "evening": []}
    inventories, live_checks = {}, {}
    for case in capture.CASES:
        rows = [r for r in startup.read_trace(root / f"traces/{case}.jsonl.gz") if r["type"] == "world"]
        require([r["tick"] for r in rows] == list(range(0, startup.STOP + 1, 15)), "missing/reordered census")
        require(all(r["sun_phase"] == (64 + r["tick"] // 15) % 256 and
                    r["sun_strength"] == prior.sun_strength(r["sun_phase"]) for r in rows), "sun formula mismatch")
        samples = {r["tick"]: r for r in rows}
        previous, counts, checked = {}, Counter(), 0
        for row in rows:
            tick = row["tick"]
            current = {p["id"]: p for p in row["plants"]}
            require(len(current) == len(row["plants"]), "duplicate lineage in census")
            for identity, p in current.items():
                if p["dead"]:
                    continue
                old = previous.get(identity)
                if tick:
                    require(old is None or not old["dead"], "dead lineage revived")
                    values = startup.resources.budget(old, p, tick)
                    if old is not None:
                        prior.check_stress(old, p, tick, values)
                    else:
                        require(p["stress"] == 0 and p["flags"] & 6 == 0 and
                                p["energy_income"] == p["water_income"] == 0, "invalid newborn budget")
                    checked += 1
                    if values["energy_seeds"]:
                        seed_audit.decision(samples, identity, tick)
                    if any(values[f"energy_{k}"] for k in KINDS):
                        stages = spending_stages(old, p, tick, values)
                        counts.update(s["kind"] for s in stages)
                        counts["spending_steps"] += 1
                        counts["newborn_steps"] += old is None
                        counts["coincident_steps"] += len(stages) > 1
                        panels["spending"].append(audit_state(samples, case, identity, tick, "spending", stages, values))
                if row["sun_phase"] == 117:
                    panels["evening"].append(audit_state(samples, case, identity, tick, "evening"))
            previous = current
        inventories[case], live_checks[case] = dict(counts), checked
    require(inventories == {
        "control": {"growth": 703, "renewal": 65, "seeds": 52, "spending_steps": 814, "newborn_steps": 14, "coincident_steps": 6},
        "veto": {"growth": 547, "renewal": 105, "seeds": 60, "spending_steps": 711, "newborn_steps": 9, "coincident_steps": 1}},
        "fixed spending inventory changed")
    shared, summaries = {}, {}
    for panel, records in panels.items():
        groups = {case: [r for r in records if r["case"] == case] for case in inventories}
        common = {c: {r["key"].split(".", 1)[1]: (r["anchor"], r["stages"], r["prediction"])
                      for r in rr if r["anchor"]["tick"] < seed_audit.PURCHASE} for c, rr in groups.items()}
        require(common["control"] == common["veto"], "shared-prefix anchors differ")
        shared[panel] = len(common["control"])
        summaries[panel] = {"all": summarize(records), **{c: summarize(rr) for c, rr in groups.items()}}
    return {"rule": RULE, "baseline_manifest_sha256": BASELINE_SHA, "previous_audit_sha256": OLD_SHA,
            "new_native_calls": 0, "role": "offline exact dark-budget diagnostic, not a gating policy",
            "analysis_sources": {name: experiment.digest(experiment.ROOT / name) for name in
                ("sim/garden_renewal_dark_budget.py", "sim/test_garden_renewal_dark_budget.py", PROTOCOL)},
            "frozen_sources": seed_audit.check_frozen_sources(root), "inventory": inventories,
            "checked_live_census_steps": live_checks, "shared_prefix_anchors_per_trace": shared,
            "summary": summaries, "panels": panels}


def verify(root):
    require(experiment.digest(experiment.ROOT / OLD_SUMMARY) == OLD_SHA, "previous audit changed")
    require(prior.verify(root) == experiment.read_json(experiment.ROOT / OLD_SUMMARY), "previous audit no longer reproduces")
    result = analyze(root)
    require(result == analyze(root), "dark-budget repeat differs")
    require(experiment.digest(root / "manifest.json") == BASELINE_SHA, "baseline manifest changed")
    manifest = experiment.read_json(root / "manifest.json")
    for name in manifest["artifacts"]:
        capture.gallery.artifact(root, manifest, name)
    require(result["frozen_sources"] == seed_audit.check_frozen_sources(root), "frozen sources changed")
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
                "choose fresh output outside frozen bundle")
    result = verify(root)
    if args.output:
        experiment.write_json(args.output, result)
    if args.check:
        require(experiment.read_json(args.check) == result, "portable dark budget differs")
    for panel, cases in result["summary"].items():
        for case, summary in cases.items():
            print(f"{panel}/{case}: {summary['supported']}/{summary['anchors']} covered anchors; "
                  f"{summary['comparisons']}; local expense effects={summary['local_effects']}")
    print("Verified exact dark-budget audit; zero new native calls")


if __name__ == "__main__":
    main()
