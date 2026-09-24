#!/usr/bin/env python3
"""Read-only, population-wide dark-window and residual-mortality audit."""
from __future__ import annotations

import argparse
from collections import Counter
from itertools import islice
from pathlib import Path

import garden_renewal_dark_panel as panel

guard, experiment, require = panel.guard, panel.experiment, panel.require
reference, startup = guard.reference, panel.startup
RULE = "garden-renewal-dark-failures-v1"
PROTOCOL = "benchmarks/garden-longevity/renewal-dark-failures-protocol.md"
BASELINE_SHA = "d62a870fea9ecfede3a32cebe1465097c0391f53a0cf781358574fc2db2e4ae8"
PORTABLE = "benchmarks/garden-longevity/renewal-dark-panel-summary.json"
PORTABLE_SHA = "acab8e8c821a11f9b8748bc30856c4af1a1c788efa7d5cb4f223650be80b9ca9"
LOOKBACK = 2 * panel.DAY
STORES = ("energy", "water")
COSTS = ("overflow", "upkeep", "growth", "renewal", "seeds")


def point(tick, plant):
    return {"tick": tick, "phase": (64+tick//15) % 256,
            **{k: plant[k] for k in ("id", "species", "dead", "energy", "water", "nodes", "roots",
                                    "leaves", "active_leaves", "tips", "stress", "flags")},
            "leaf_condition_sum": sum(plant["leaf"]["conditions"])}


def forecast(tick, state):
    return reference.project(tick, state["energy"], state["nodes"], state["stress"])


def compact(prediction):
    result = reference.compact(prediction)
    bounds = prediction["boundaries"]
    result["boundaries"] = {k: v for k, v in bounds.items() if k != "maintenance_ticks"}
    result["boundaries"]["maintenance_payments"] = len(bounds["maintenance_ticks"])
    return result


def budget_sum(entries):
    values = Counter()
    for entry in entries:
        if entry["budget"] is not None:
            values.update(entry["budget"])
    return values


def balance(first, last, values):
    for resource in STORES:
        expected = first[resource] + values[resource+"_income"] - sum(values[resource+"_"+k] for k in COSTS)
        require(expected == last[resource], "lookback/lifetime budget does not telescope")


def histories(rows, boundaries, records, end):
    """Charge the ordinary step, then carry observed post-patch state forward."""
    result, previous, seen_boundaries, checked = {}, {}, set(), 0
    last = -15
    for row in rows:
        if row["type"] != "world":
            continue
        tick = row["tick"]
        require(tick == last+15 and tick <= end and row["sun_phase"] == (64+tick//15) % 256,
                "missing or wrong ecology step")
        require(row["sun_strength"] == reference.prior.sun_strength(row["sun_phase"]), "wrong light phase")
        current = {p["id"]: p for p in row["plants"]}
        require(len(current) == len(row["plants"]), "duplicate identity")
        after = current
        boundary = boundaries.get(tick)
        if boundary:
            require(boundary["before"] == row, "wrong patch census")
            panel.disturbance.validate_boundary(row, boundary["after"], boundary["event"])
            after = {p["id"]: p for p in boundary["after"]["plants"]}
            seen_boundaries.add(tick)
        for identity, p in current.items():
            record, old = records[identity], previous.get(identity)
            if old is not None and old["dead"]:
                require(p["dead"], "dead plant revived")
                continue
            if old is None:
                require(identity not in result and record["birth_tick"] == tick and not p["dead"], "wrong birth")
                result[identity] = []
            values = None
            terminal = None
            if p["dead"]:
                require(old is not None and tick % 60 == 0 and old["stress"] == 7 and p["stress"] == 8
                        and p["flags"] & 6, "unexplained natural death")
                require(all(p[k] == 0 for k in ("energy", "water", "energy_income", "water_income")),
                        "terminal telemetry unexpectedly retained")
                terminal = "natural"
            elif tick:
                values = startup.resources.budget(old, p, tick)
                startup.check_leaf(old, p)
                if old is not None:
                    reference.prior.check_stress(old, p, tick, values)
                else:
                    require(p["stress"] == 0 and p["flags"] & 6 == 0, "stressed newborn")
                checked += 1
            if boundary and identity in boundary["event"]["killed"]:
                require(terminal is None, "natural death charged again as a patch")
                terminal = "patch"
            if terminal:
                require(record["death_tick"] == tick and bool(record.get("environmental_death")) == (terminal == "patch"),
                        "saved lifetime disagrees with terminal event")
            events = [e for e in row.get("dark_guard", {}).get("events", []) if e["id"] == identity]
            require(not p["dead"] or not events, "natural death acted after maintenance")
            result[identity].append({"state": point(tick, after[identity]), "budget": values,
                                    "terminal": terminal, "events": events})
        require(all(previous[i]["dead"] for i in previous.keys()-current.keys()), "live plant disappeared")
        previous, last = after, tick
    require(last == end and set(result) == set(records) and seen_boundaries == boundaries.keys(), "incomplete histories")
    for identity, history in result.items():
        p = records[identity]
        require(history[-1]["state"]["tick"] == (p["death_tick"] if p["death_tick"] is not None else end),
                "truncated lifetime")
    return result, checked


def audit_window(history, index):
    start = history[index]["state"]
    require(not start["dead"], "dead anchor")
    predicted = forecast(start["tick"], start)
    require(predicted["supported"], "unsupported dark anchor")
    end = predicted["boundaries"]["last_dark_tick"]
    breaks, totals = {}, Counter()
    prefix_checked = checked = 0
    errors = Counter(energy=0, stress=0)
    last_live, terminal, first_shortage = start, None, None
    peak = start["stress"]
    expected_tick = start["tick"]+15
    for entry in islice(history,index+1,None):
        p, values = entry["state"], entry["budget"]
        tick = p["tick"]
        if tick > end:
            break
        require(tick == expected_tick,"missing dark follow-up step")
        expected_tick += 15
        require(reference.prior.sun_strength(p["phase"]) < 64, "window crossed possible income")
        if entry["terminal"] == "patch":
            breaks.setdefault("patch", tick)
            terminal = {"kind": "patch", "tick": tick}
            break
        if tick % 60 == 0 and p["flags"] & 4:
            breaks.setdefault("water_shortage", tick)
        if tick % 60 == 0 and p["flags"] & 2 and first_shortage is None:
            first_shortage = tick
        if entry["terminal"]:
            terminal = {"kind": "natural", "tick": tick, "cause": startup.SHORTAGES[p["flags"] & 6]}
            peak = 8
            break
        require(values is not None and values["energy_income"] == 0, "income inside guaranteed-dark interval")
        if (p["nodes"]+7)//8 != (start["nodes"]+7)//8:
            breaks.setdefault("energy_upkeep_change", tick)
        if any(values["energy_"+k] for k in reference.KINDS):
            breaks.setdefault("optional_spending", tick)
        expect = predicted["steps"][tick]
        for field in ("energy", "stress"):
            errors[field] = max(errors[field], abs(expect[field]-p[field]))
        if not breaks:
            require(not expect["dead"] and all(expect[k] == p[k] for k in ("energy", "stress")),
                    "exact dark prefix differs")
            prefix_checked += 1
        checked += 1
        totals.update(values)
        last_live, peak = p, max(peak, p["stress"])
    balance(start, last_live, totals)
    if terminal and terminal["kind"] == "patch":
        status = "patch-censored"
    elif terminal is None and last_live["tick"] < end:
        status = "trace-censored"
    elif breaks:
        status = "assumption-broken"
    elif terminal:
        require(terminal["cause"] == "energy" and predicted["death_tick"] == terminal["tick"],
                "exact dark death differs")
        status = "exact-energy-death"
    else:
        require(predicted["death_tick"] is None, "predicted death but clean window survived")
        status = "exact-survival"
    if status.startswith("exact-"):
        require(predicted["first_shortage_tick"] == first_shortage and predicted["peak_stress"] == peak,
                "exact dark stress summary differs")
    return {"anchor": start, "prediction": compact(predicted), "status": status,
            "actual": {"last_live": last_live, "terminal": terminal, "first_shortage_tick": first_shortage,
                       "peak_stress": peak, "live_budget": totals, "assumption_breaks": breaks},
            "checked_live_steps": checked, "exact_prefix_steps": prefix_checked, "maximum_errors": errors}


def all_windows(history):
    return [audit_window(history, i) for i, entry in enumerate(history) if not entry["state"]["dead"] and
            (entry["state"]["phase"] == 117 or
             i == 0 and reference.horizon(entry["state"]["tick"])["dark_steps"] > 0)]


def minimum_energy(tick, state):
    cap = reference.project(tick, 256, state["nodes"], state["stress"])
    require(cap["supported"], "unsupported minimum-energy query")
    minimum = None
    if cap["death_tick"] is None:
        lo, hi = 0, 256
        while lo < hi:
            mid = (lo+hi)//2
            if reference.project(tick, mid, state["nodes"], state["stress"])["death_tick"] is None:
                hi = mid
            else:
                lo = mid+1
        minimum = lo
    return {"minimum_energy_within_cap": minimum, "at_storage_cap": compact(cap)}


def death_record(history, windows, record, detailed):
    terminal, last_live = history[-1]["state"], history[-2]["state"]
    require(history[-1]["terminal"] == "natural", "not a natural-death record")
    tick = terminal["tick"]
    latest = windows[-1] if windows else None
    relation = ("no-prior-dark-anchor" if latest is None else "inside-dark-window" if
                tick <= latest["prediction"]["boundaries"]["last_dark_tick"] else "after-dark-window")
    result = {"id": record["id"], "parent": record["parent"], "species": record["species"],
              "generation": record["generation"], "birth_tick": record["birth_tick"], "death_tick": tick,
              "cause": startup.SHORTAGES[terminal["flags"] & 6], "relation": relation,
              "last_live": last_live, "terminal": terminal, "terminal_budget": "cleared-not-reconstructed",
              "latest_anchor_tick": latest["anchor"]["tick"] if latest else None,
              "latest_window_status": latest["status"] if latest else None,
              "latest_prediction": latest["prediction"].get("classification") if latest else None}
    if not detailed:
        return result
    lifetime = budget_sum(history)
    origin = {"energy": 64, "water": 24} if record["parent"] else history[0]["state"]
    balance(origin, last_live, lifetime)
    first_index = next(i for i,e in enumerate(history) if e["state"]["tick"] >= tick-LOOKBACK)
    lookback = history[first_index:]
    budget = budget_sum(lookback[1:])
    balance(lookback[0]["state"], last_live, budget)
    purchases, timeline, body_changes = [], [], []
    for i in range(first_index, len(history)):
        entry, old = history[i], history[i-1]["state"] if i else None
        p, values = entry["state"], entry["budget"]
        if values and any(values["energy_"+k] for k in reference.KINDS):
            stages = reference.spending_stages(old, p, p["tick"], values)
            for stage in stages:
                for k in ("before_budget", "after_budget"):
                    stage[k] = compact(stage[k])
            purchases.append({"tick": p["tick"], "phase": p["phase"], "stages": stages})
        changed = old is not None and (old["nodes"],old["roots"]) != (p["nodes"],p["roots"])
        if changed:
            body_changes.append({"tick":p["tick"], "nodes_before":old["nodes"], "nodes_after":p["nodes"],
                                 "roots_before":old["roots"], "roots_after":p["roots"]})
        if (i in (0,first_index,len(history)-2,len(history)-1) or p["phase"] in (0,10,11,64,117,128) or
            old is not None and ((old["stress"],old["flags"]) != (p["stress"],p["flags"]) or
                                 (old["nodes"]+7)//8 != (p["nodes"]+7)//8)):
            timeline.append({"state":p,"budget":values})
    post_dark = None
    if latest and relation == "after-dark-window":
        first_possible = latest["prediction"]["boundaries"]["first_possible_income_tick"]
        after = [e for e in history if first_possible <= e["state"]["tick"] < tick]
        incomes = [e["state"]["tick"] for e in after if e["budget"]["energy_income"]]
        post_dark = {"first_possible_income_tick":first_possible, "first_observed_income_tick":min(incomes) if incomes else None,
                     "checked_live_steps":len(after),"live_budget":budget_sum(after),
                     "boundary_state":latest["actual"]["last_live"], "terminal_income_unknown":True}
    result.update(lifetime_live_budget=lifetime, lookback={"start":lookback[0]["state"], "last_live":last_live,
        "live_budget":budget, "purchases":purchases, "body_changes":body_changes, "timeline":timeline},
        dark_entry_feasibility=minimum_energy(latest["anchor"]["tick"],latest["anchor"]) if latest else None,
        post_dark=post_dark)
    return result


def denied_records(history, record, end):
    result = []
    for entry in history:
        tick = entry["state"]["tick"]
        for event in entry["events"]:
            if not event["denied"]:
                continue
            bounds = reference.horizon(tick)
            death = record["death_tick"]
            require(bounds["dark_steps"] > 0, "denied outside supported interval")
            outcome = ("patch-before-boundary" if record.get("environmental_death") else "natural-death-before-boundary") \
                if death is not None and death <= bounds["last_dark_tick"] else \
                "trace-censored" if end < bounds["last_dark_tick"] else "alive-at-boundary"
            result.append({"tick":tick,"id":record["id"],"event":event,"post_step":entry["state"],
                "already_fatal":event["before"]["death_step"] != 0,
                "death_tick":death,"environmental_death":bool(record.get("environmental_death")),
                "observed_outcome":outcome,"last_dark_tick":bounds["last_dark_tick"]})
    return result


def summarize(windows, deaths, denials):
    already = [d for d in denials if d["already_fatal"]]
    return {"anchors":len(windows), "natural_deaths":len(deaths), "denials":len(denials),
        "already_fatal_denials":len(already), "already_fatal_plants":len({d["id"] for d in already}),
        "denied_plants":len({d["id"] for d in denials}),
        "checked_dark_live_steps":sum(w["checked_live_steps"] for w in windows),
        "exact_dark_prefix_steps":sum(w["exact_prefix_steps"] for w in windows),
        "window_status":dict(Counter(w["status"] for w in windows)),
        "window_predictions":dict(Counter(w["prediction"]["classification"] for w in windows)),
        "window_breaks":dict(Counter(k for w in windows for k in w["actual"]["assumption_breaks"])),
        "death_causes":dict(Counter(d["cause"] for d in deaths)),
        "death_relation":dict(Counter(d["relation"] for d in deaths)),
        "death_prior_window_status":dict(Counter(d["latest_window_status"] or "none" for d in deaths)),
        "death_prior_prediction":dict(Counter(d["latest_prediction"] or "none" for d in deaths)),
        "already_fatal_outcomes":dict(Counter(d["observed_outcome"] for d in already)),
        "newly_fatal_outcomes":dict(Counter(d["observed_outcome"] for d in denials if not d["already_fatal"]))}


def analyze_case(root, case, saved):
    raw, boundaries = panel.split_rows(startup.read_trace(root/f"traces/{case.name}.jsonl.gz"),case.patch)
    records = {p["id"]:p for p in saved["lineages"]}
    per_plant, checked = histories(raw,boundaries,records,panel.STOP)
    require(checked == saved["summary"]["windows"]["whole"]["checked_live_steps"], "live accounting coverage changed")
    windows, deaths, denials = [], [], []
    for identity, history in per_plant.items():
        record = records[identity]
        plant_windows = all_windows(history)
        windows.extend(plant_windows)
        if history[-1]["terminal"] == "natural":
            deaths.append(death_record(history,plant_windows,record,case.arm == "guard"))
        denials.extend(denied_records(history,record,panel.STOP))
    result = summarize(windows,deaths,denials)
    require(result["natural_deaths"] == saved["summary"]["windows"]["whole"]["natural_deaths"] and
            result["death_causes"] == saved["summary"]["windows"]["whole"]["natural_death_causes"],"natural deaths differ")
    require(len(denials) == sum(saved["summary"]["guard"]["denied"].values()),"missing guard denials")
    require(result["already_fatal_denials"] == saved["summary"]["guard"]["counts"].get("already-fatal",0),
            "already-fatal inventory differs")
    print("Audited dark windows and deaths:",case.name,flush=True)
    return {"case":saved["case"],"summary":result,"windows":windows,"deaths":deaths,"denials":denials}


def aggregate(cases):
    groups = {}
    for condition in panel.CONDITIONS:
        groups[condition] = {}
        for arm in guard.CASES:
            merged = {}
            for seed in panel.SEEDS:
                summary = cases[panel.Case(seed,condition,arm).name]["summary"]
                for k,v in summary.items():
                    if isinstance(v,dict):
                        merged.setdefault(k,Counter()).update(v)
                    else:
                        merged[k] = merged.get(k,0)+v
            groups[condition][arm] = merged
    return groups


def analyze(root, saved):
    cases = {c.name:analyze_case(root,c,saved["cases"][c.name]) for c in panel.CASES}
    return {"rule":RULE,"baseline_manifest_sha256":BASELINE_SHA,"baseline_summary_sha256":PORTABLE_SHA,
            "native_calls":0,"lookback_ticks":LOOKBACK,"cases":cases,"aggregate":aggregate(cases)}


def analysis_sources():
    paths = sorted((experiment.ROOT/"sim").glob("*.py")) + [experiment.ROOT/PROTOCOL,experiment.ROOT/"sim/CMakeLists.txt"]
    return {str(p.relative_to(experiment.ROOT)):experiment.digest(p) for p in paths}


def verify(root):
    require(experiment.digest(root/"manifest.json") == BASELINE_SHA and
            experiment.digest(experiment.ROOT/PORTABLE) == PORTABLE_SHA,"changed frozen inputs")
    sources = analysis_sources()
    native = guard.prior.prior.native_hashes(root/"source.tar.gz")
    require(all(experiment.digest(experiment.ROOT/n) == sha for n,sha in native.items()),"native sources changed")
    saved = panel.verify(root)
    portable = experiment.read_json(experiment.ROOT/PORTABLE)
    require(saved == {k:v for k,v in portable.items() if k not in ("manifest_sha256","timing")},"portable parent differs")
    result = analyze(root,saved)
    require(result == analyze(root,saved),"mortality analysis repeat differs")
    require(analysis_sources() == sources,"analysis sources changed")
    manifest = experiment.read_json(root/"manifest.json")
    require(experiment.digest(root/"manifest.json") == BASELINE_SHA,"baseline changed")
    for name in manifest["artifacts"]:
        panel.gallery.artifact(root,manifest,name)
    result["analysis_sources"] = sources
    result["native_sources"] = native
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline",type=Path,default=experiment.ROOT/"artifacts/garden-renewal-dark-panel-v1")
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--output",type=Path)
    target.add_argument("--check",type=Path)
    args = parser.parse_args()
    root = args.baseline.resolve()
    if args.output:
        require(not args.output.exists() and not args.output.resolve().is_relative_to(root),"choose fresh output outside bundle")
    result = verify(root)
    if args.output:
        experiment.write_json(args.output,result)
    else:
        require(experiment.read_json(args.check) == result,"portable mortality audit differs")
    for condition,arms in result["aggregate"].items():
        for arm,s in arms.items():
            print(condition,arm,s["natural_deaths"],"natural deaths;",s["death_relation"],s["window_status"])
    print("Verified frozen mortality audit; zero new native calls",flush=True)


if __name__ == "__main__":
    main()
