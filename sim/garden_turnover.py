#!/usr/bin/env python3
"""Read-only lifetime/resource follow-up of the frozen seed-bank comparison."""
from __future__ import annotations

import argparse
from collections import Counter, deque
import gzip
import json
from pathlib import Path
import shutil

import garden_seed_bank as bank
from garden_resources import budget, require

DAY, END, START = bank.DAY, bank.END, bank.START
AGES = (1, 2, 4, 8, 16)
FOCUS = ("c7f54e18.reserve.8", "c7f54e18.reserve.16")


def survival(records, start, stop, end=END):
    require(0 <= start < stop <= end and end <= END, "invalid cohort window")
    group = [r for r in records if r["parent"] and start < r["birth_tick"] <= stop]
    result = {}
    for days in AGES:
        eligible = [r for r in group if r["birth_tick"] + days*DAY <= end]
        survived = [r for r in eligible if r["death_tick"] is None or
                    r["death_tick"] > r["birth_tick"] + days*DAY]
        died = [r for r in eligible if r not in survived]
        result[str(days)] = {"eligible": len(eligible), "survived": len(survived),
            "survived_ids": [r["id"] for r in survived], "recent": len(group)-len(eligible),
            "natural_deaths": sum(not r.get("environmental_death") for r in died),
            "patch_deaths": sum(bool(r.get("environmental_death")) for r in died)}
    return {"born": len(group), "ages": result}


def summary_lifetimes(records, end=END):
    ids = {r["id"]: r for r in records}
    require(len(ids) == len(records), "duplicate lineage")
    for r in records:
        require(0 <= r["birth_tick"] <= end and (r["death_tick"] is None or
                r["birth_tick"] <= r["death_tick"] <= end), "invalid lifetime")
        if r["parent"]:
            parent = ids.get(r["parent"])
            require(parent is not None and parent["birth_tick"] < r["birth_tick"]
                    and r["generation"] == parent["generation"]+1, "bad ancestry")
    eligible = lambda r: r["birth_tick"]+DAY <= end and (r["death_tick"] is None or
                                                        r["death_tick"] > r["birth_tick"]+DAY)
    durable = []
    for r in records:
        if not (r["parent"] and r["birth_tick"] > START and eligible(r)):
            continue
        children = [c for c in records if c["parent"] == r["id"] and eligible(c)]
        if children:
            qualification = max(r["birth_tick"]+DAY, min(c["birth_tick"]+DAY for c in children))
            durable.append({"id": r["id"], "children": [c["id"] for c in children],
                "qualification_tick": qualification, "alive_when_qualified": r["death_tick"] is None or
                    r["death_tick"] > qualification, "alive_at_end": r["death_tick"] is None})
    return {"whole": survival(records, 0, end, end), "closing": survival(records, START, end, end),
            # Same birth cohort and denominator at all five ages; no horizon advantage.
            "closing_full_16_day_followup": survival(records, START, end-16*DAY, end),
            "durable_closing": durable}


def snapshot(row, p):
    return {"tick": row["tick"], "hash": row["hash"], "phase": row["sun_phase"],
        **{k: p[k] for k in ("energy", "water", "stress", "flags", "nodes", "roots", "tips",
            "leaves", "active_leaves", "energy_income", "water_income", "reproduction_cooldown")},
        "leaf_condition_sum": sum(p["leaf"]["conditions"]),
        "leaf_renewals": p["leaf"]["renewals"], "genome": p["genome"],
        "root_cells": p["root_cells"]}


def sum_budgets(history, after):
    total = Counter()
    for entry in history:
        if entry["point"]["tick"] > after:
            total.update(entry["budget"])
    return dict(total)


def resource_trace(path, boundaries, reference, capacity, start=START, end=END, *,
                   side="reserve", seed_reserve=None):
    records = {r["id"]: r for r in reference["lineages"]}
    events = {b["event"]["tick"]: b for b in boundaries["world"]}
    seen, seen_deaths, seed_counts = set(), set(), Counter()
    previous, histories, sunsets, last_seeds, age_points = {}, {}, {}, {}, {}
    daily = {str(d): Counter() for d in range(1, (end+DAY-1)//DAY+1)}
    deaths, last_tick, checks = [], -15, 0
    for b in boundaries["world"]:
        bank.recruitment.diversity.disturbance.validate_boundary(b["before"], b["after"], b["event"])
    with gzip.open(path, "rt") as stream:
        for line in stream:
            row = json.loads(line)
            bank.competition.maintenance.check_identity(row, "selective", 512,
                growth_policy=bank.recruitment.policy.RESERVE if side == "reserve" else None,
                seed_capacity=capacity, seed_reserve=seed_reserve)
            tick = row["tick"]
            require(row["type"] == "world" and tick == last_tick+15 and tick <= end
                    and row["sun_phase"] == (64+tick//15)%256, "missing/reordered world")
            current = {p["id"]: p for p in row["plants"]}
            require(len(current) == len(row["plants"]), "duplicate plant")
            day = daily.get(str((tick+DAY-1)//DAY))
            for identity, p in current.items():
                require(identity in records, "unknown lineage")
                record, old = records[identity], previous.get(identity)
                if identity not in seen:
                    require(tick == record["birth_tick"] and not p["dead"], "unobserved birth")
                    seen.add(identity)
                    histories[identity] = deque()
                    age_points[identity] = {"birth": snapshot(row,p)}
                    if tick:
                        day["births"] += 1
                require(all(p[k] == record[k] for k in ("parent","species","generation","column")),
                        "lineage identity changed")
                if p["dead"]:
                    if old is not None and not old["dead"]:
                        require(record["death_tick"] == tick and record["death_flags"] == p["flags"]
                                and not record.get("environmental_death"), "natural death mismatch")
                        require(p["energy"] == p["water"] == p["energy_income"] == p["water_income"] == 0,
                                "unexpected terminal clearing")
                        require(tick%60 == 0 and old["stress"] == 7 and p["stress"] == 8,
                                "invalid terminal maintenance/stress transition")
                        seen_deaths.add(identity)
                        day["natural_deaths"] += 1
                        if tick > start:
                            hist = histories[identity]
                            recent = [e for e in hist if e["point"]["tick"] > tick-DAY]
                            sunset = sunsets.get(identity)
                            night = [e for e in hist if sunset and e["point"]["tick"] > sunset["tick"]]
                            failures = [e["point"] for e in recent if e["point"]["tick"]%60 == 0
                                        and e["point"]["flags"] & 6]
                            deaths.append({"id": identity, "parent":record["parent"], "species":p["species"],
                                "generation":p["generation"], "birth_tick":record["birth_tick"],
                                "death_tick":tick, "death_phase":row["sun_phase"], "death_flags":p["flags"],
                                "age_ticks":tick-record["birth_tick"], "last_alive":hist[-1]["point"],
                                "last_sunset":sunset, "last_seed_tick":last_seeds.get(identity),
                                "first_day_points":age_points[identity], "seeds_produced":seed_counts[identity],
                                "last_day_budget":sum_budgets(hist, tick-DAY),
                                "since_sunset_budget":sum_budgets(hist, sunset["tick"]) if sunset else None,
                                "since_sunset_nodes_unchanged": bool(sunset) and all(
                                    e["point"]["nodes"] == sunset["nodes"] for e in night),
                                "last_day_maintenance": [e["point"] for e in recent if e["point"]["tick"]%60 == 0],
                                "first_last_day_shortage":failures[0] if failures else None})
                    continue
                require(record["death_tick"] is None or tick <= record["death_tick"], "plant revived")
                point = snapshot(row,p)
                values = budget(old,p,tick) if tick else {}
                checks += bool(tick)
                hist = histories[identity]
                hist.append({"point":point, "budget":values})
                while hist and hist[0]["point"]["tick"] < tick-DAY:
                    hist.popleft()
                age = tick-record["birth_tick"]
                if age in [d*DAY for d in AGES]:
                    age_points[identity][str(age//DAY)] = point
                if row["sun_phase"] == 128:
                    sunsets[identity] = point
                if values.get("energy_seeds"):
                    seed_counts[identity] += 1
                    last_seeds[identity] = tick
                if tick:
                    day.update({"living_samples":1, "nodes":p["nodes"], "energy":p["energy"], "water":p["water"]})
                    day.update({"budget_"+k:v for k,v in values.items()})
            require(all(previous[i]["dead"] for i in previous.keys()-current.keys()), "living plant disappeared")
            if tick in events:
                b = events[tick]
                require(row == b["before"], "boundary no longer matches trace")
                for identity in b["event"]["killed"]:
                    require(records[identity].get("environmental_death") and records[identity]["death_tick"]==tick,
                            "patch death mismatch")
                    seen_deaths.add(identity)
                day["patch_deaths"] += len(b["event"]["killed"])
                current = {p["id"]:p for p in b["after"]["plants"]}
            previous, last_tick = current, tick
    require(last_tick == end and seen == records.keys() and seen_deaths ==
            {i for i,r in records.items() if r["death_tick"] is not None}, "incomplete lifetime coverage")
    require(all(seed_counts[i] == r["seeds_created"] for i,r in records.items()), "production count mismatch")
    # Counters include patch-boundary ordinary steps; occupancy samples are pre-patch.
    return {"checked_live_steps":checks, "daily":daily, "closing_natural_deaths":deaths,
            "lineage_age_points":age_points}


def collect(baseline, output):
    baseline, output = baseline.resolve(), output.resolve()
    require(not output.exists() and (not output.is_relative_to(bank.experiment.ROOT) or
        output.is_relative_to(bank.experiment.ROOT/"artifacts")), "unsafe/existing output")
    m = bank.experiment.read_json(baseline/"manifest.json")
    require(m["kind"] == "garden-seed-bank" and m["status"] == "complete" and
        bank.experiment.digest(baseline/"manifest.json") ==
        "0feca7b8584012cfa384e9a5fde197bc8ed8ddec3c1f10a1a254b4828815e7ff", "wrong frozen comparison")
    for name in m["artifacts"]:
        bank.establishment.verified(baseline,m,name)
    output.mkdir(parents=True)
    (output/"input").mkdir()
    sources = bank.experiment.source_files()
    bank.experiment.snapshot_sources(output,sources)
    shutil.copy2(baseline/"manifest.json",output/"input/manifest.json")
    manifest = {"kind":"garden-turnover", "status":"started", "focus":FOCUS,
        "source_sha256":sources, "baseline_manifest_sha256":bank.experiment.digest(baseline/"manifest.json")}
    bank.experiment.write_json(output/"started.json",manifest)
    try:
        result = {"overview":{}, "focus":{}}
        old = bank.experiment.read_json(baseline/"summary.json")
        for c in old["runs"]:
            key = c["key"]
            path = f"analyses/{key}.json"
            shutil.copy2(baseline/path,output/f"input/{key}.json")
            r = bank.experiment.read_json(output/f"input/{key}.json")
            require(bank.compact(r)==c, "prior summary changed")
            life = summary_lifetimes(r["analysis"]["world"]["lineages"])
            require(life["closing"]["ages"]["1"]["survived"] == c["lifetimes"]["late_born"]["cycle_survivors"]
                    and len(life["durable_closing"]) == c["lifetimes"]["late_born"]["cycle_survivors_with_surviving_child"],
                    "one-day/ancestry result disagrees with frozen comparison")
            result["overview"][key] = life
            if key not in FOCUS:
                continue
            for n in (f"traces/{key}.world.gz", f"analyses/{key}.boundaries.json"):
                shutil.copy2(baseline/n,output/"input"/Path(n).name)
            bounds = bank.experiment.read_json(output/f"input/{key}.boundaries.json")
            a, refs = bank.competition.world_analysis(output/f"input/{key}.world.gz","selective",512,END,START,
                disturbances={b["event"]["tick"]:b for b in bounds["world"]},
                growth_policy=bank.recruitment.policy.RESERVE, seed_capacity=c["bank"])
            require(a==r["analysis"]["world"], "old whole-world audit changed")
            detail = resource_trace(output/f"input/{key}.world.gz",bounds,a,c["bank"])
            require(len(detail["closing_natural_deaths"]) == a["windows"]["late"]["natural_deaths"],
                    "closing death count mismatch")
            detail["checked_world_rows"] = len(refs)
            result["focus"][key] = detail
            print(f"Verified {key}: {len(refs)} worlds; {len(detail['closing_natural_deaths'])} closing natural deaths",flush=True)
        bank.experiment.write_json(output/"summary.json",result)
        for name in m["artifacts"]:
            bank.establishment.verified(baseline,m,name)
        require(bank.experiment.source_files()==sources,"source changed during audit")
        manifest.update(status="complete",artifacts={str(p.relative_to(output)):bank.experiment.digest(p)
            for p in output.rglob("*") if p.is_file()})
        bank.experiment.write_json(output/"manifest.json",manifest)
        print(f"Complete {output}; SHA256={bank.experiment.digest(output/'manifest.json')}",flush=True)
    except BaseException as error:
        bank.experiment.write_json(output/"failure.json",{"error":str(error)})
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline",type=Path,default=bank.experiment.ROOT/"artifacts/garden-seed-bank")
    parser.add_argument("--output",type=Path,required=True)
    args = parser.parse_args()
    collect(args.baseline,args.output)
