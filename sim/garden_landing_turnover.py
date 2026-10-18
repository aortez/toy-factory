#!/usr/bin/env python3
"""Offline seed supply, establishment and turnover audit of frozen arbitration runs."""

from __future__ import annotations

import argparse
from collections import Counter
import gzip
import json
from pathlib import Path
import sys

import garden_landing_arbitration as previous
import garden_landing_renewal_audit as renewal
from garden_experiments import digest
from garden_resources import require

ROOT, DAY, STEP, STOP = previous.ROOT, previous.DAY, previous.STEP, previous.STOP
START = 62 * DAY
RULE = "garden-landing-turnover-v1"
INPUT = "benchmarks/garden-seasons/landing-arbitration-results.json.gz"
INPUT_SHA = "7e3a88e1077f0944b84c412675a6bfabc1b531da6bf21844f62be68ac7b4bec7"
ARMS = tuple(previous.ARMS)
lifetimes, rolling = renewal.lifetimes, renewal.rolling
recruitment, establishment = previous.establishment.prior, previous.establishment


def load(path):
    require(digest(path) == INPUT_SHA, "wrong frozen arbitration panel")
    return json.loads(gzip.decompress(path.read_bytes()))


def population(result, tick):
    """Post-ecology state: birth is inclusive, death/seed completion exclusive."""
    require(type(tick) is int and 0 <= tick <= result["tick"] and tick % STEP == 0,
            "invalid population clock")
    value = renewal.snapshot(result["lineages"], result["seeds"], tick)
    groups = value["plants"]
    established = sorted(i for bucket in renewal.BUCKETS[2:] for i in groups[bucket])
    terminal = {"classification": "established-present" if established else
                "living-unestablished" if value["living"] else
                "seed-only-unconfirmed" if value["pending_seeds"] else "observed-extinct",
                "living_founders": len(groups["founder"]),
                "young_descendants": groups["unconfirmed_descendant"],
                "established_descendants": established, "pending_seeds": len(value["pending_seeds"])}
    return {**value, "terminal": terminal}


def segments(result, start=START, stop=STOP):
    """Constant-state spans representing samples start, start+STEP, ..., stop."""
    require(type(start) is int and type(stop) is int and 0 <= start <= stop <= result["tick"] and
            start % STEP == stop % STEP == 0, "invalid segment interval")
    cuts = {start, stop + STEP}
    for p in result["lineages"]:
        due = p["birth_tick"] + DAY
        cuts.update(t for t in (p["birth_tick"], p["death_tick"], due, due + rolling.CREDIT_AGE)
                    if t is not None and start < t <= stop)
    for s in result["seeds"]:
        cuts.update(t for t in (s["birth_tick"], s["end_tick"]) if t is not None and start < t <= stop)
    cuts = sorted(cuts)
    return [{"first_tick": a, "end_exclusive": z, "state": population(result, a)}
            for a, z in zip(cuts, cuts[1:])]


def interval_stats(spans, first, end):
    require(type(first) is int and type(end) is int and first < end and
            first % STEP == end % STEP == 0, "invalid sample interval")
    rows = [(max(first, s["first_tick"]), min(end, s["end_exclusive"]), s["state"])
            for s in spans if s["first_tick"] < end and s["end_exclusive"] > first]
    require(sum(z - a for a, z, _ in rows) == end - first, "incomplete interval coverage")
    return {"sample_ticks": end - first, "samples": (end - first) // STEP,
            "minimum_seed_bank": min(len(s["pending_seeds"]) for _, _, s in rows),
            "maximum_seed_bank": max(len(s["pending_seeds"]) for _, _, s in rows),
            "zero_seed_bank_ticks": sum(z - a for a, z, s in rows if not s["pending_seeds"]),
            "no_living_plant_ticks": sum(z - a for a, z, s in rows if not s["living"]),
            "biologically_empty_ticks": sum(z - a for a, z, s in rows
                                             if not s["living"] and not s["pending_seeds"])}


def gaps(result, spans):
    """All intervals without an established descendant, including seed-only recovery."""
    groups = []
    for row in spans:
        if row["state"]["terminal"]["established_descendants"]:
            continue
        a, z = row["first_tick"], row["end_exclusive"]
        if groups and groups[-1]["end_exclusive"] == a:
            groups[-1]["end_exclusive"] = z
        else:
            groups.append({"first_tick": a, "end_exclusive": z})
    for g in groups:
        a, z = g["first_tick"], g["end_exclusive"]
        before = population(result, a - STEP) if a else None
        after = population(result, z) if z <= result["tick"] else None
        seen = sorted({i for row in spans if a <= row["first_tick"] < z
                       for i in row["state"]["terminal"]["young_descendants"]})
        g.update(stats=interval_stats(spans, a, z), children_seen=seen,
                 before=before, first=population(result, a), last=population(result, z - STEP), after=after,
                 clipped_at_start=a == spans[0]["first_tick"],
                 recovery_censored=after is None or not after["terminal"]["established_descendants"],
                 deaths_at_start=sorted(p["id"] for p in result["lineages"] if p["death_tick"] == a),
                 restoring_ids=after["terminal"]["established_descendants"] if after else [],
                 checkpoints=[t for t in (96 * DAY, 128 * DAY, 160 * DAY, 192 * DAY) if a <= t < z])
    return groups


def no_birth_spells(result, spans, seed_audits):
    """All >=1-day no-birth sample spans; bank exposure is not site feasibility."""
    start, end = spans[0]["first_tick"], spans[-1]["end_exclusive"]
    births = sorted({p["birth_tick"] for p in result["lineages"] if p["parent"]})
    points = [t for t in births if start <= t < end]
    cursor, intervals = start, []
    for tick in [*points, end]:
        if tick - cursor >= DAY:
            intervals.append((cursor, tick))
        cursor = tick + STEP
    rows = []
    for a, z in intervals:
        # Only complete seed lifetimes contained in this exact no-birth span:
        # their cumulative masks cannot accidentally describe another window.
        contained = [s for s in seed_audits if a <= s["birth_tick"] and
                     s["end_tick"] is not None and s["end_tick"] < z]
        complete = []
        for s in contained:
            masks = s["mature_masks"]
            complete.append({k: s[k] for k in ("parent", "birth_tick", "end_tick", "column", "outcome")} | {
                "mature_checks": sum(masks.values()), "open_elsewhere_checks": s["open_elsewhere_checks"],
                "always_mature_blockers": [b for j, b in enumerate(recruitment.BLOCKERS)
                    if masks and all(int(m) & (1 << j) for m in masks)]})
        rows.append({"first_tick": a, "end_exclusive": z, "stats": interval_stats(spans, a, z),
                     "previous_birth_tick": max((t for t in births if t < a), default=None),
                     "next_birth_tick": z if z in births else None,
                     "purchases": sum(a <= s["birth_tick"] < z for s in result["seeds"]),
                     "expiries": sum(s["outcome"] == "expired" and a <= s["end_tick"] < z
                                     for s in result["seeds"]), "complete_seed_lifetimes": complete})
    return rows


def child_receipt(p, stop):
    value = establishment.summarize_child(p, stop)
    return {k: value[k] for k in ("id", "parent", "birth_tick", "death_tick", "outcome", "death_shortage",
                                  "resources", "first_shortage", "last_living_body", "first_root_tick")} | {
        "birth_sun_phase": establishment.phase(p["birth_tick"]),
        "death_sun_phase": value["death_sun_phase"],
        "growth_crossed_payment_before_shortage": {r: sum(r in g["crossed_payment"] and
            value["first_shortage"][r] is not None and g["tick"] < value["first_shortage"][r]["tick"]
            for g in value["growth"]) for r in establishment.RESOURCES},
        "global_light_ceiling_insufficient_at_death":
            establishment.maximum_sun(p["death_tick"]) < 64 if p["outcome"] == "died" else None}


def cohort(children):
    return {"births": len(children), "confirmed": sum(p["outcome"] == "confirmed" for p in children),
            "died": sum(p["outcome"] == "died" for p in children),
            "pending": sum(p["outcome"] == "pending" for p in children),
            "shortages": dict(sorted(Counter(p["death_shortage"] for p in children
                                              if p["outcome"] == "died").items()))}


def analyze_arm(source, arm):
    result = source["result"]
    previous.common_view(result, arm)
    require(result["tick"] == STOP and result["ledger_start_tick"] == 0, "incomplete run")
    history = rolling.history(result["lineages"], result["seeds"], 0, STOP)
    require(history == source["history"], "saved score history differs")
    records = {p["id"]: p for p in result["lineages"]}
    plant_audits, seed_audits = source["audit"]["plants"], source["audit"]["seeds"]
    require({p["id"] for p in plant_audits} == {p["id"] for p in records.values() if p["parent"]} and
            len(plant_audits) == sum(bool(p["parent"]) for p in records.values()), "missing/duplicate child audit")
    for p in plant_audits:
        require({k: p[k] for k in records[p["id"]]} == records[p["id"]], "child audit lineage differs")
    require([{k: s[k] for k in original} for s, original in
             zip(seed_audits, result["seeds"], strict=True)] == result["seeds"], "seed audit ledger differs")
    require(recruitment.seed_summary(seed_audits) == source["audit"]["summary"]["all_seeds"], "seed summary differs")
    children = [child_receipt(p, STOP) for p in plant_audits]
    spans = segments(result)
    periods = []
    for b in history["blocks"]:
        require(population(result, b["followup_deadline"])["terminal"] == b["terminal"], "terminal census differs")
        p = renewal.audit_period(result, b)
        a, z = b["window_ticks"]
        born = [c for c in children if a < c["birth_tick"] <= z]
        older_deaths = [c for c in records.values() if c["parent"] and c["death_tick"] is not None and
                        a < c["death_tick"] <= z and c["death_tick"] > c["birth_tick"] + DAY]
        p.update(birth_cohort=cohort(born), birth_ids=[c["id"] for c in born],
                 established_deaths=[{"id": c["id"], "tick": c["death_tick"], "resource_cause": "not-recorded"}
                                     for c in older_deaths], bank=interval_stats(spans, a + STEP, z + STEP))
        periods.append(p)
    late = [c for c in children if START < c["birth_tick"] <= 190 * DAY]
    require(cohort(late)["pending"] == 0, "late cohort censored")
    gap_rows = gaps(result, spans)
    return {"world_hash": result["world_hash"], "trace_sha256": source["trace_sha256"],
            "arbitration_trace_sha256": source["arbitration_trace_sha256"],
            "unchanged_history": history, "periods": periods, "children": children,
            "late_cohort": cohort(late), "gaps": gap_rows,
            "gap_sample_ticks": sum(g["stats"]["sample_ticks"] for g in gap_rows),
            "no_birth_spells": no_birth_spells(result, spans, seed_audits),
            "population_stats": interval_stats(spans, START, STOP + STEP)}


def analyze(data):
    require(data["rule"] == previous.RULE and data["arms"] == previous.ARMS and
            len(data["worlds"]) == 12 and len({w["id"] for w in data["worlds"]}) == 12 and
            [w["id"] for w in data["worlds"]] == [w["id"] for w in data["plan"]], "wrong arbitration panel")
    mapped = [{**w, "arms": {"control": w["arms"]["veto"], "water": w["arms"]["eligible"]}}
              for w in data["worlds"]]
    require({"control": "veto", "candidate": "eligible", **previous.previous.compare(mapped)} ==
            data["comparison"]["comparisons"]["veto"], "veto comparison changed")
    worlds = [{k: w[k] for k in ("id", "model", "case")} | {
        "arms": {arm: analyze_arm(w["arms"][arm], arm) for arm in ARMS}} for w in data["worlds"]]
    groups = {}
    for climate in ("all", "steady", "seasonal"):
        selected = [w for w in worlds if climate == "all" or w["case"]["climate"] == climate]
        groups[climate] = {a: {"late_cohort": cohort([p for w in selected for p in w["arms"][a]["children"]
                                      if START < p["birth_tick"] <= 190 * DAY]),
            "gaps": sum(len(w["arms"][a]["gaps"]) for w in selected),
            "gap_sample_ticks": sum(w["arms"][a]["gap_sample_ticks"] for w in selected),
            "biologically_empty_ticks": sum(w["arms"][a]["population_stats"]["biologically_empty_ticks"] for w in selected),
            "periods": renewal.summarize([p for w in selected for p in w["arms"][a]["periods"]])} for a in ARMS}
    return {"rule": RULE, "input": INPUT, "input_sha256": INPUT_SHA, "native_runs": 0, "training_runs": 0,
            "sample_range_inclusive": [START, STOP], "sample_step": STEP,
            "worlds": worlds, "groups": groups, "unchanged_comparison": data["comparison"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / INPUT)
    output = parser.add_mutually_exclusive_group(required=True)
    output.add_argument("--out", type=Path)
    output.add_argument("--verify", type=Path)
    args = parser.parse_args()
    try:
        value = analyze(load(args.input))
        require(digest(args.input) == INPUT_SHA, "input changed during diagnosis")
        if args.verify:
            raw = args.verify.read_bytes()
            require(json.loads(gzip.decompress(raw) if args.verify.suffix == ".gz" else raw) == value,
                    "saved turnover diagnosis differs")
            print("Verified 24 histories, 96 periods, turnover gaps, seed supply and first-day resource receipts; no simulation.")
        else:
            raw = (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()
            with args.out.open("xb") as stream:
                if args.out.suffix == ".gz":
                    with gzip.GzipFile(filename="", fileobj=stream, mode="wb", mtime=0) as zipped:
                        zipped.write(raw)
                else:
                    stream.write(raw)
        return 0
    except (OSError, ValueError, RuntimeError, KeyError, TypeError) as error:
        print("turnover diagnosis failed: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
