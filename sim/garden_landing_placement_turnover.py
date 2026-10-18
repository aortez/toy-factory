#!/usr/bin/env python3
"""Offline turnover and seed-blocker diagnosis of the frozen placement screen."""

from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path
import sys

import garden_landing_placement as previous
import garden_landing_budget_reach as reach_window
import garden_landing_germination as germination
from garden_experiments import digest
from garden_resources import require

ROOT, DAY, STEP, STOP = previous.ROOT, previous.DAY, previous.STEP, previous.STOP
START, END = germination.START, germination.END
turnover, renewal = germination.turnover, germination.renewal
lifetimes, rolling = turnover.lifetimes, turnover.rolling
RULE = "garden-landing-placement-turnover-v1"
ARMS = ("reserve", "spacing")
INPUT = "benchmarks/garden-seasons/landing-placement-results.json.gz"
INPUT_SHA = "c94d1d8e466dd0e81b399cf7416f353cb5533cb1e8288d33f17719097ef7fa82"
MANIFEST_SHA = "f04e1d84db9b14e415ee13d17393aab4c91c682a85ec01c74779e44ff924a7e7"
WINDOWS = "benchmarks/garden-seasons/landing-placement-turnover-windows.json.gz"
WINDOWS_SHA = "4ed8be4e907713886297eba32c8967277b2557e3bd623115b58c0e77e01d0339"


def panel(data):
    require(data["rule"] == previous.RULE and data["training_runs"] == 0 and
            len(data["worlds"]) == 12 and len({w["id"] for w in data["worlds"]}) == 12,
            "wrong placement panel")
    worlds = [w for w in data["worlds"] if w["case"]["climate"] == "seasonal"]
    require(len(worlds) == 6, "missing seasonal worlds")
    return worlds


def extract(bundle, data):
    """Export exact final-period rows from pinned saved traces, never simulate."""
    require(not (bundle / "FAILED.txt").exists() and digest(bundle / "manifest.json") == MANIFEST_SHA and
            digest(bundle / "results.json.gz") == INPUT_SHA, "wrong/incomplete source bundle")
    manifest = json.loads((bundle / "manifest.json").read_text())
    require(manifest["rule"] == previous.RULE and manifest["status"] == "complete", "wrong manifest")
    worlds = []
    for w in panel(data):
        arms = {}
        for arm in ARMS:
            source, stem = w["arms"][arm], arm + "--" + w["id"]
            excerpts = {}
            for kind, field in (("children", "trace_sha256"), ("reach", "reach_sha256")):
                name = stem + "-" + kind + ".jsonl.gz"
                sha, path = source[field], bundle / name
                require(manifest["artifacts"][name] == digest(path) == sha, "source trace differs")
                rows, purchases = [], []
                schema = "recruitment" if kind == "children" else "reach"
                fields = {"tick", "seeds", "plants"} if kind == "children" else {"tick", "purchases", "checks"}
                with gzip.open(path, "rt") as stream:
                    require(json.loads(next(stream)) == {"schema": "landing-" + schema + "-trace-v1"}, "wrong trace schema")
                    for tick in range(STEP, STOP + STEP, STEP):
                        row = json.loads(next(stream))
                        require(set(row) == fields and type(row["tick"]) is int and row["tick"] == tick,
                                "missing/reordered source trace step")
                        if kind == "reach":
                            purchases.extend({"tick": tick, **p} for p in row["purchases"])
                        if START < tick <= END:
                            key = "seeds" if kind == "children" else "checks"
                            rows.append({"tick": tick, key: row[key]})
                    require(json.loads(next(stream)) == {"complete": True, "tick": STOP} and not stream.read(),
                            "incomplete/trailing source trace")
                require(digest(path) == sha, "source trace changed during extraction")
                if kind == "reach":
                    require(purchases == source["purchase_sites"], "source parent purchases differ")
                excerpts[kind] = rows
            selected = {(s["parent"], s["birth_tick"]) for s in source["result"]["seeds"]
                        if s["birth_tick"] <= END and (s["end_tick"] is None or s["end_tick"] > START)}
            purchases = [{"birth_tick": p["tick"], **{k: v for k, v in p.items() if k != "tick"}}
                         for p in source["purchase_sites"] if (p["parent"], p["tick"]) in selected]
            arms[arm] = {"trace_sha256": source["trace_sha256"], "reach_sha256": source["reach_sha256"],
                         "rows": excerpts["children"], "reach": {"purchases": purchases, "rows": excerpts["reach"]}}
            print(w["model"] + " / " + arm + ": extracted saved final-period receipts", flush=True)
        worlds.append({"id": w["id"], "arms": arms})
    require(digest(bundle / "manifest.json") == MANIFEST_SHA, "source manifest changed")
    return {"rule": RULE + "-windows", "input_sha256": INPUT_SHA, "manifest_sha256": MANIFEST_SHA,
            "window_ticks": [START, END], "sample_step": STEP, "worlds": worlds}


def redirected_paths(result, seeds):
    """Within-run ancestry labels, not matched rescues or causal attribution."""
    records = {p["id"]: p for p in result["lineages"]}
    require(len(records) == len(result["lineages"]), "duplicate plant")
    births = {s["child_id"]: s for s in seeds if s["child_id"] is not None}
    require(len(births) == sum(s["child_id"] is not None for s in seeds) and
            set(births) == {p["id"] for p in records.values() if p["parent"]}, "seed/child ancestry differs")
    direct = set()
    for ident, s in births.items():
        p = records[ident]
        require(s["parent"] == p["parent"] and s["end_tick"] == p["birth_tick"] and
                s["outcome"] == "germinated" and type(s["redirected"]) is bool, "wrong child purchase")
        if s["redirected"]:
            direct.add(ident)
    paths = {}
    for ident in records:
        chain, seen, current = [], set(), ident
        while current:
            require(current in records and current not in seen, "missing/cyclic ancestry")
            seen.add(current)
            if current in direct:
                chain.append(current)
            current = records[current]["parent"]
        paths[ident] = {"direct_redirect": ident in direct, "redirected_lineage_ids": list(reversed(chain))}
    return paths


def first_redirect(control, candidate):
    """Only the identical prefix is matched across diverging trajectories."""
    a, b = control["placements"]["purchases"], candidate["placements"]["purchases"]
    index = next((i for i, p in enumerate(b) if p["selected"] != p["random"] % 6), None)
    if index is None:
        require(a == b, "unredirected purchase traces differ")
        return None
    require(len(a) > index and a[:index] == b[:index] and
            {k: v for k, v in a[index].items() if k != "selected"} ==
            {k: v for k, v in b[index].items() if k != "selected"} and
            a[index]["selected"] == a[index]["random"] % 6, "prefix diverges before first redirected purchase")
    p = b[index]
    return {"matching_prior_purchases": index, "tick": p["tick"], "parent": p["parent"],
            "original_column": p["choices"][a[index]["selected"]], "selected_column": p["choices"][p["selected"]]}


def credit_exits(result, paths):
    """Observed end of each credit interval, separated from biological death."""
    records, rows = {p["id"]: p for p in result["lineages"]}, []
    for p in result["lineages"]:
        if not lifetimes.qualifies(p, records, result["tick"]):
            continue
        due = p["birth_tick"] + DAY
        age_end = due + rolling.CREDIT_AGE
        end = min(age_end, p["death_tick"] if p["death_tick"] is not None else age_end)
        reason = "age_limit" if p["death_tick"] is None or p["death_tick"] > age_end else (
            "death_and_age_limit" if p["death_tick"] == age_end else "death")
        if end > result["tick"]:
            end, reason = None, "right_censored"
        rows.append({**p, **paths[p["id"]], "confirmation_tick": due, "age_limit_tick": age_end,
                     "credit_end_exclusive": end, "credit_end_reason": reason})
    return rows


def no_credit_intervals(result, start, end):
    spans = turnover.segments(result, start + STEP, end)
    gaps = []
    for s in spans:
        if s["state"]["plants"]["credit_eligible"]:
            continue
        if gaps and gaps[-1]["end_exclusive"] == s["first_tick"]:
            gaps[-1]["end_exclusive"] = s["end_exclusive"]
        else:
            gaps.append({"first_tick": s["first_tick"], "end_exclusive": s["end_exclusive"]})
    for g in gaps:
        g.update(stats=turnover.interval_stats(spans, g["first_tick"], g["end_exclusive"]),
                 first=turnover.population(result, g["first_tick"]),
                 last=turnover.population(result, g["end_exclusive"] - STEP),
                 clipped_at_start=g["first_tick"] == start + STEP,
                 clipped_at_end=g["end_exclusive"] == end + STEP)
    return gaps


def analyze_arm(source, arm, case, model, excerpt):
    result = source["result"]
    require(result["tick"] == STOP and result["ledger_start_tick"] == 0 and
            excerpt["trace_sha256"] == source["trace_sha256"] and excerpt["reach_sha256"] == source["reach_sha256"],
            "wrong horizon/trace provenance")
    history = previous.training.score_world(previous.common_view(result, arm), case, model)
    require(history == source["history"] and source["metrics"] == previous.growth.scoring.metrics(result, source["audit"], history),
            "history/metrics changed")
    require(source["placement_audit"] == previous.analyze(result, source["placements"], source["purchase_sites"], arm == "spacing"),
            "placement receipts differ")
    paths = redirected_paths(result, source["placement_audit"]["seeds"])
    records = {p["id"]: p for p in result["lineages"]}
    audits = source["audit"]["plants"]
    require({p["id"] for p in audits} == {p["id"] for p in records.values() if p["parent"]} and
            len(audits) == sum(bool(p["parent"]) for p in records.values()), "missing/duplicate child audit")
    children = []
    for p in audits:
        require({k: p[k] for k in records[p["id"]]} == records[p["id"]], "child audit lineage differs")
        checked = dict(p)
        germination.recruitment.analyze_child(checked, STOP)
        require(checked == p, "first-day accounting differs")
        children.append({**turnover.child_receipt(p, STOP), **paths[p["id"]]})
    checks = germination.seed_window(result, excerpt["rows"])
    reach = reach_window.analyze_window(result, excerpt["rows"], excerpt["reach"])
    born = [p for p in children if START < p["birth_tick"] <= END]
    require({p["id"] for p in born} == {p["child"] for p in checks["germinations"]}, "final birth inventory differs")
    final = renewal.audit_period(result, history["blocks"][-1])
    require(history["blocks"][-1]["window_ticks"] == [START, END], "wrong final period")
    exits = credit_exits(result, paths)
    living_start = [{**p, **paths[p["id"]]} for p in result["lineages"] if lifetimes.alive(p, START)]
    spans = turnover.segments(result, START + STEP, END)
    return {"unchanged_history": history, "unchanged_metrics": source["metrics"], "period": final,
            "seed_window": checks, "reach_window": reach, "living_at_start": living_start,
            "population_stats": turnover.interval_stats(spans, START + STEP, END + STEP),
            "birth_cohort": turnover.cohort(born), "children": born,
            "established_deaths": [p for p in result["lineages"] if p["death_tick"] is not None and
                START < p["death_tick"] <= END and p["death_tick"] > p["birth_tick"] + DAY],
            "credit_exits": exits, "no_credit_intervals": no_credit_intervals(result, 62 * DAY, END),
            "last_birth_tick": max((p["birth_tick"] for p in result["lineages"] if p["parent"] and p["birth_tick"] <= END), default=None),
            "last_credit_end": max((p["credit_end_exclusive"] for p in exits
                                    if p["credit_end_exclusive"] is not None and p["credit_end_exclusive"] <= END), default=None),
            "redirected_children": [p for p in children if p["direct_redirect"]],
            "descendants_of_redirected_children": [p for p in children if p["redirected_lineage_ids"] and not p["direct_redirect"]],
            "final_credit_contributors": [{**p, **paths[p["id"]]} for p in history["blocks"][-1]["rolling"]["children"]]}


def analyze(data, windows):
    worlds = panel(data)
    require(windows["rule"] == RULE + "-windows" and windows["input_sha256"] == INPUT_SHA and
            windows["manifest_sha256"] == MANIFEST_SHA and windows["window_ticks"] == [START, END] and
            windows["sample_step"] == STEP and [w["id"] for w in windows["worlds"]] == [w["id"] for w in worlds],
            "wrong window panel")
    require(data["comparison"] == previous.compare(data["worlds"]), "saved comparison differs")
    audited = []
    for w, excerpt in zip(worlds, windows["worlds"], strict=True):
        require(set(excerpt["arms"]) == set(ARMS), "missing/extra arm")
        arms = {arm: analyze_arm(w["arms"][arm], arm, w["case"], data["models"][w["model"]]["metadata"], excerpt["arms"][arm])
                for arm in ARMS}
        audited.append({k: w[k] for k in ("id", "model", "case")} | {"arms": arms,
            "first_redirect": first_redirect(w["arms"]["reserve"], w["arms"]["spacing"])})
    return {"rule": RULE, "input_sha256": INPUT_SHA, "windows_sha256": WINDOWS_SHA,
            "native_runs": 0, "training_runs": 0, "window_ticks": [START, END], "worlds": audited,
            "period_summaries": {arm: renewal.summarize([w["arms"][arm]["period"] for w in audited]) for arm in ARMS},
            "unchanged_comparison": data["comparison"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / INPUT)
    parser.add_argument("--windows", type=Path, default=ROOT / WINDOWS)
    parser.add_argument("--extract-from", type=Path, help="read frozen local traces, without simulation")
    output = parser.add_mutually_exclusive_group(required=True)
    output.add_argument("--out", type=Path)
    output.add_argument("--verify", type=Path)
    args = parser.parse_args()
    try:
        require(args.out is None or not args.out.exists(), "fresh output required")
        data = germination.load(args.input, INPUT_SHA)
        value = extract(args.extract_from, data) if args.extract_from else analyze(data, germination.load(args.windows, WINDOWS_SHA))
        require(digest(args.input) == INPUT_SHA and (args.extract_from or digest(args.windows) == WINDOWS_SHA),
                "input changed during analysis")
        if args.verify:
            with gzip.open(args.verify, "rt") as stream:
                require(json.load(stream) == value, "saved turnover diagnosis differs")
            print("Verified exact frozen trace windows; no simulation." if args.extract_from else
                  "Verified twelve final periods, credit expiry, seed blockers, redirection ancestry and unchanged scores; no simulation.")
        else:
            previous.budget.founders.write_gzip(args.out, value)
        return 0
    except (OSError, ValueError, RuntimeError, KeyError, TypeError, StopIteration) as error:
        print("placement turnover audit failed: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
