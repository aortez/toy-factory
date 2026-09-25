#!/usr/bin/env python3
"""Audit an existing seed forecast against frozen purchases; never run worlds."""
from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

import garden_renewal_seed_veto as prior
from garden_seed_reserve import forecast

experiment, startup, require = prior.experiment, prior.startup, prior.require
RULE = "garden-renewal-seed-forecast-v1"
BASELINE_SHA = "dd44e765e15d4be5ed0c5c99273699718358ac8e5790af838162121620bcb5ae"
PURCHASE, SUNSET, LAST_NIGHT, DAWN, STOP = 4620, 4800, 6705, 6720, 7140
CASES = (("control", 2), ("veto", 3))
PROTOCOL = "benchmarks/garden-longevity/renewal-seed-forecast-protocol.md"
FROZEN_SOURCES = (
    "src/garden_world.c", "src/garden_world.h", "src/garden_light.c", "src/garden_light.h",
    "src/garden_seed_reserve.h", "sim/garden_seed_reserve.py", "sim/garden_seed_reserve_test.c",
    "sim/garden_resources.py", "sim/garden_renewal_startup.py", "sim/garden_renewal_seed_veto.py",
)
ENERGY_COSTS = ("energy_overflow", "energy_upkeep", "energy_growth", "energy_renewal", "energy_seeds")


def sample(samples, tick, identity):
    require(tick in samples, f"missing census at {tick}")
    row = samples[tick]
    require(row["tick"] == tick and row["sun_phase"] == (64 + tick // 15) % 256,
            "wrong census tick/phase")
    plants = [p for p in row["plants"] if p["id"] == identity]
    require(len(plants) <= 1, "duplicate lineage")
    return plants[0] if plants else None


def checkpoint(samples, tick, identity):
    p = sample(samples, tick, identity)
    return {"tick": tick, "sun_phase": samples[tick]["sun_phase"],
            "sun_strength": samples[tick]["sun_strength"], "present": p is not None,
            **({k: p[k] for k in ("energy", "water", "energy_income", "nodes", "active_leaves",
                                  "stress", "flags", "dead")} if p else {})}


def window(samples, identity, start, end, *, detailed=False):
    """Reconcile (start, end], stopping at death rather than inventing debits."""
    require(0 <= start < end and start % 15 == end % 15 == 0, "invalid window")
    first = sample(samples, start, identity)
    require(first is not None, "lineage absent at window start")
    previous, active = first, not first["dead"]
    last_live, death = (start if active else None), None
    totals, steps, payments = Counter(), [], []
    demand = checked = 0
    for tick in range(start + 15, end + 1, 15):
        p = sample(samples, tick, identity)
        if not active:
            require(p is None or p["dead"], "dead lineage revived")
            continue
        require(p is not None, "living lineage disappeared")
        if p["dead"]:
            death, active = tick, False
            continue  # Death clears income/stores; do not charge a fictional final payment.
        values = startup.resources.budget(previous, p, tick)
        due = (previous["nodes"] + 7) // 8 if tick % 60 == 0 else 0
        require(values["energy_upkeep"] <= due, "paid upkeep exceeds demand")
        totals.update(values)
        demand += due
        checked += 1
        point = checkpoint(samples, tick, identity)
        if tick % 60 == 0:
            payments.append({"tick": tick, "required": due, "paid": values["energy_upkeep"],
                             "energy": p["energy"], "stress": p["stress"]})
        if detailed:
            steps.append({**point, "budget": values, "upkeep_required": due})
        previous, last_live = p, tick
    if last_live is not None:
        require(first["energy"] + totals["energy_income"] - sum(totals[k] for k in ENERGY_COSTS)
                == sample(samples, last_live, identity)["energy"], "window energy does not telescope")
    return {"start_exclusive": start, "end_inclusive": end, "checked_live_steps": checked,
            "already_dead_at_start": first["dead"], "last_live_tick": last_live,
            "terminal_step_not_reconstructed": death, "complete_live_window": active,
            "budget": dict(totals), "upkeep_required_checked_live": demand,
            "upkeep_unpaid_checked_live": demand - totals["energy_upkeep"],
            "start": checkpoint(samples, start, identity), "end": checkpoint(samples, end, identity),
            "payments": payments, **({"steps": steps} if detailed else {})}


def forecast_ledger(energy, income, nodes, phase):
    """Expose the existing heuristic's terms, checked against its saved reference."""
    result = forecast(energy, income, nodes, phase)
    require(0 < phase < 128, "audit requires a daylight purchase")
    projected, totals, steps = result["after_seed"], Counter(), []
    for p in range(phase + 1, 129):
        credit = income // 2 if p < 128 else 0
        overflow = max(0, projected + credit - 256)
        upkeep = result["maintenance_cost"] if p % 4 == 0 else 0
        projected += credit - overflow - upkeep
        totals.update(energy_income=credit, energy_overflow=overflow, energy_upkeep=upkeep)
        steps.append({"phase": p, "income": credit, "overflow": overflow,
                      "upkeep": upkeep, "projected_energy": projected})
    require(projected == result["projected_sunset"], "forecast ledger differs from reference")
    return {**result, "budget": dict(totals), "steps": steps}


def decision(samples, identity, tick):
    require(tick > 0 and tick % 60 == 0, "purchase not on a maintenance step")
    old, p = (sample(samples, t, identity) for t in (tick - 15, tick))
    require(old is not None and p is not None and not old["dead"] and not p["dead"],
            "purchase requires an existing living parent")
    require(0 < samples[tick]["sun_phase"] < 128 and p["reproduction_cooldown"] == 16 and
            old["reproduction_cooldown"] <= 1 and p["spent_flowers"] == old["spent_flowers"] + 1,
            "not a newly observed seed purchase")
    values = startup.resources.budget(old, p, tick)
    require(values["energy_seeds"] == 48 and values["water_seeds"] == 24, "wrong purchase debit")
    row, previous = samples[tick], samples[tick - 15]
    count = row["seeds_created"] - previous["seeds_created"]
    buyers = [q["id"] for q in row["plants"] if not q["dead"] and q["reproduction_cooldown"] == 16]
    require(0 < count <= len(row["seeds"]) and count == len(buyers) and
            [s["parent"] for s in row["seeds"][-count:]] == buyers and identity in buyers,
            "purchase does not reconcile with the appended seed bank")
    require(p["energy_income"] < 255, "saturated decision income")
    # Reproduction is the last resource-changing stage. Do not undo current
    # income/upkeep/growth/renewal: the C gate sees those already applied.
    before = p["energy"] + values["energy_seeds"]
    return {"tick": tick, "id": identity, "species": p["species"], "nodes": p["nodes"],
            "sun_phase": row["sun_phase"], "sun_strength": row["sun_strength"],
            "energy_before_seed": before, "energy_after_seed": p["energy"],
            "current_income": p["energy_income"], "current_step_budget": values,
            "forecast": forecast_ledger(before, p["energy_income"], p["nodes"], row["sun_phase"])}


def compare_daylight(purchase, actual):
    f = purchase["forecast"]
    require(actual["complete_live_window"] and actual["start_exclusive"] == purchase["tick"] and
            actual["end"]["sun_phase"] == 128 and actual["start"]["energy"] == f["after_seed"],
            "daylight ledger does not cover the actual post-purchase horizon")
    predicted, observed = f["budget"], actual["budget"]
    terms = {"income_overestimate": predicted["energy_income"] - observed["energy_income"],
             "overflow_difference": observed["energy_overflow"] - predicted["energy_overflow"],
             "upkeep_difference": observed["energy_upkeep"] - predicted["energy_upkeep"],
             "optional_spending": sum(observed[k] for k in ("energy_growth", "energy_renewal", "energy_seeds"))}
    error = f["projected_sunset"] - actual["end"]["energy"]
    require(sum(terms.values()) == error, "unexplained sunset forecast error")
    return {"projected_sunset": f["projected_sunset"], "actual_sunset": actual["end"]["energy"],
            "sunset_overestimate": error, "error_terms": terms,
            "projected_night_margin": f["projected_sunset"] - f["night_upkeep"],
            "actual_night_margin_fixed_body": actual["end"]["energy"] - f["night_upkeep"],
            "nodes_unchanged": all(s["nodes"] == purchase["nodes"] for s in actual["steps"])}


def trajectory(samples, identity):
    periods = {"daylight": window(samples, identity, PURCHASE, SUNSET, detailed=True),
               "night": window(samples, identity, SUNSET, LAST_NIGHT),
               "dawn_recovery": window(samples, identity, LAST_NIGHT, STOP)}
    observations = [checkpoint(samples, t, identity) for t in range(PURCHASE, STOP + 1, 15)]
    require(all(o["present"] for o in observations), "observed founder disappeared in audit horizon")
    living = [o for o in observations if not o["dead"]]
    first_income = next((o for o in living if o["tick"] >= DAWN and o["energy_income"] > 0), None)
    shortage = next((o for o in living if o["tick"] > PURCHASE and o["flags"] & 2), None)
    recovery = next((o for o in living if shortage and o["tick"] > shortage["tick"] and o["stress"] == 0), None)
    death = next((o for o in observations if o["dead"]), None)
    return {"windows": periods, "first_energy_shortage_after_purchase": shortage,
            "first_income_after_dawn": first_income, "first_stress_clear_after_shortage": recovery,
            "death_in_audit_horizon": death,
            "checkpoints": [checkpoint(samples, t, identity) for t in
                            (PURCHASE, SUNSET, LAST_NIGHT, DAWN, 6780, 6840, 6885, 6900, STOP)]}


def zero_income_interval(samples, body_sizes):
    """Storage lower bound, not a survival prediction or a new gating rule.

    The frozen light solver only subtracts shade from sun strength. Uptake uses
    floor(cell_light / 64) before leaf-condition weighting, so strength below
    64 cannot produce energy, even with perfect leaves and no shade.
    """
    ticks = list(range(PURCHASE + 15, STOP + 1, 15))
    require(all(t in samples for t in ticks), "missing light census")
    start = next((t for t in ticks if samples[t]["sun_strength"] < 64), None)
    require(start is not None, "missing zero-income interval")
    first_light = next((t for t in ticks if t > start and samples[t]["sun_strength"] >= 64), None)
    require(first_light is not None, "missing productive-light boundary")
    payments = [t for t in range(start, first_light, 15) if t % 60 == 0]
    return {"start_inclusive": start, "end_inclusive": first_light - 15,
            "previous_possible_income_tick": start - 15, "earliest_possible_income_tick": first_light,
            "upkeep_ticks": payments, "storage_capacity": 256,
            "fixed_body_lower_bounds": [{"nodes": n, "upkeep": (n + 7) // 8,
                "required_energy": len(payments) * ((n + 7) // 8),
                "minimum_unpaid_from_full_storage": max(0, len(payments) * ((n + 7) // 8) - 256)}
                for n in body_sizes]}


def check_frozen_sources(root):
    saved = experiment.read_json(root / "manifest.json")["sources"]
    hashes = {name: experiment.digest(experiment.ROOT / name) for name in FROZEN_SOURCES}
    require(all(saved.get(name) == sha for name, sha in hashes.items()), "forecast/accounting source changed")
    return hashes


def analyze(root):
    samples = {}
    for case in prior.CASES:
        rows = [r for r in startup.read_trace(root / f"traces/{case}.jsonl.gz") if r["type"] == "world"]
        require([r["tick"] for r in rows] == list(range(0, startup.STOP + 1, 15)), "missing/reordered census")
        samples[case] = {r["tick"]: r for r in rows}
    cases = {}
    for case, identity in CASES:
        purchase = decision(samples[case], identity, PURCHASE)
        actual = trajectory(samples[case], identity)
        comparison = compare_daylight(purchase, actual["windows"]["daylight"])
        other = "veto" if case == "control" else "control"
        context = trajectory(samples[other], identity)
        p = sample(samples[other], PURCHASE, identity)
        require(p["reproduction_cooldown"] == 0 and p["energy"] == purchase["energy_before_seed"] and
                p["energy_income"] == purchase["current_income"] and p["nodes"] == purchase["nodes"],
                "opposite trace does not retain the same no-purchase decision state")
        cases[f"{case}.{identity}"] = {"case": case, "decision": purchase, "actual": actual,
            "comparison": comparison, "no_purchase_context": {"case": other, **context}}
    sizes = [c["decision"]["nodes"] for c in cases.values()]
    gap = zero_income_interval(samples["control"], sizes)
    require(gap == zero_income_interval(samples["veto"], sizes), "light timing differs between traces")
    gap["checked_live_zero_income_steps"] = {}
    for case in prior.CASES:
        for identity, size in zip((2, 3), sizes, strict=True):
            living = [p for t in range(gap["start_inclusive"], gap["end_inclusive"] + 1, 15)
                      if (p := sample(samples[case], t, identity)) is not None and not p["dead"]]
            require(living and all(p["energy_income"] == 0 and p["nodes"] == size for p in living),
                    "zero-income/fixed-body assumption differs from live trace")
            gap["checked_live_zero_income_steps"][f"{case}.{identity}"] = len(living)
    return {"rule": RULE, "baseline_manifest_sha256": BASELINE_SHA,
            "frozen_sources": check_frozen_sources(root),
            "analysis_sources": {name: experiment.digest(experiment.ROOT / name) for name in
                                 ("sim/garden_renewal_seed_forecast.py", PROTOCOL)},
            "new_native_calls": 0, "role": "observed-state shadow audit, not a gate-enabled rollout",
            "horizon": {"purchase": PURCHASE, "sunset": SUNSET, "last_night": LAST_NIGHT,
                        "dawn": DAWN, "recovery_stop": STOP}, "zero_income_interval": gap, "cases": cases}


def verify(root):
    require(experiment.digest(root / "manifest.json") == BASELINE_SHA, "wrong seed-veto baseline")
    prior.verify(root)
    result = analyze(root)
    require(result == analyze(root), "offline analysis repeat differs")
    # No writes to the source bundle, and no time-of-check/source drift.
    manifest = experiment.read_json(root / "manifest.json")
    require(experiment.digest(root / "manifest.json") == BASELINE_SHA, "baseline changed during analysis")
    for name in manifest["artifacts"]:
        prior.gallery.artifact(root, manifest, name)
    require(result["frozen_sources"] == check_frozen_sources(root), "sources changed during analysis")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, default=experiment.ROOT / "artifacts/garden-renewal-seed-veto-v1")
    output = parser.add_mutually_exclusive_group()
    output.add_argument("--output", type=Path, help="write a new portable JSON (never overwrite)")
    output.add_argument("--check", type=Path, help="compare existing portable JSON")
    args = parser.parse_args()
    root = args.baseline.resolve()
    if args.output:
        require(not args.output.exists() and not args.output.resolve().is_relative_to(root),
                "choose a new output outside the frozen bundle")
    result = verify(root)
    if args.output:
        experiment.write_json(args.output, result)
    if args.check:
        require(experiment.read_json(args.check) == result, "portable forecast audit differs")
    for name, case in result["cases"].items():
        c = case["comparison"]
        print(f"{name}: gate={case['decision']['forecast']['allowed']}, "
              f"sunset={c['projected_sunset']} predicted/{c['actual_sunset']} actual, "
              f"error={c['sunset_overestimate']}")
    print("Verified saved-purchase forecast audit; zero new native calls")


if __name__ == "__main__":
    main()
