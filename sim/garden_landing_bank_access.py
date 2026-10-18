#!/usr/bin/env python3
"""Audit frozen seed ownership, residence and ordered production access; no simulation."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import gzip
import json
from pathlib import Path
import sys

import garden_descendants as descendants
import garden_landing_recovery as previous
from garden_experiments import digest
from garden_resources import require

ROOT, DAY, STEP = previous.ROOT, previous.DAY, previous.STEP
START, END, STOP = previous.START, previous.END, previous.STOP
RULE = "garden-landing-bank-access-v1"
PROTOCOL = "benchmarks/garden-seasons/landing-bank-access-protocol.md"
INPUT = "benchmarks/garden-seasons/landing-recovery-gates-results.json.gz"
INPUT_SHA = "3fabe95f2d3fa20c6a4d1b97074e15d98d3095f13ba038c02fdc3884044df223"
MANIFEST_SHA = "08c27340adc56e1acff156d2a7fbcec76f3a4c2b4ef799a8f075834c1b88abb1"
VISITS = "benchmarks/garden-seasons/landing-bank-access-visits.json.gz"
VISITS_SHA = "b59d9dd4dd2cd01cb0de93df28605f6eb6b7f49c7972bf6ab2834a5ee870ee1b"
FIELDS = ("id", "blockers", "energy", "water", "energy_required", "water_required", "immature",
          "spent", "ready", "flower", "cooldown", "bank", "stress", "sun", "produced")
OUTCOMES = ("ineligible", "full_at_entry", "earlier_buyers_fill", "purchased")
BANK = 4


def load(path, sha):
    require(digest(path) == sha, "frozen input identity differs: " + str(path))
    with gzip.open(path, "rt") as stream:
        return json.load(stream)


def extract(bundle, data):
    """Copy exact ordered visits, retaining the complete clock and source hashes."""
    require(not (bundle / "FAILED.txt").exists() and digest(bundle / "manifest.json") == MANIFEST_SHA and
            digest(bundle / "results.json.gz") == INPUT_SHA, "wrong/incomplete source bundle")
    manifest = json.loads((bundle / "manifest.json").read_text())
    require(manifest["rule"] == previous.RULE and manifest["status"] == "complete", "wrong source manifest")
    worlds = []
    for w in data["worlds"]:
        arms = {}
        for arm, source in w["arms"].items():
            meta = source["traces"]["stand"]
            name = arm + "--" + w["id"] + "-trace-stand.jsonl.gz"
            require(meta["path"] == name and manifest["artifacts"][name] == meta["sha256"] == digest(bundle / name),
                    "source trace identity differs")
            rows = []
            with gzip.open(bundle / name, "rt") as stream:
                require(json.loads(next(stream)) == {"schema": "landing-stand-trace-v1", "node_limit": 32,
                    "start": START, "stop": END, "budget_mode": 2}, "wrong source trace header")
                for tick in range(START, END + STEP, STEP):
                    row = json.loads(next(stream))
                    require(set(row) == {"tick", "seed_lifetime_ecology_ticks", "climate", "bids", "reproduction", "bodies"} and
                            type(row["tick"]) is int and row["tick"] == tick, "source clock/fields differ")
                    require(all(set(v) == set(FIELDS) for v in row["reproduction"]), "source visit fields differ")
                    rows.append([tick, [[v[k] for k in FIELDS] for v in row["reproduction"]]])
                require(json.loads(next(stream)) == {"complete": True, "tick": STOP, "run_hash": source["result"]["run_hash"]} and
                        not stream.read(), "incomplete/trailing source trace")
            require(digest(bundle / name) == meta["sha256"], "source changed during extraction")
            arms[arm] = {"trace_sha256": meta["sha256"], "rows": rows}
            print(w["model"] + " / " + arm + ": saved ordered visits extracted", flush=True)
        worlds.append({"id": w["id"], "arms": arms})
    require(digest(bundle / "manifest.json") == MANIFEST_SHA, "manifest changed")
    return {"rule": RULE + "-visits", "input_sha256": INPUT_SHA, "manifest_sha256": MANIFEST_SHA,
            "fields": list(FIELDS), "window_ticks": [START, END], "sample_step": STEP, "worlds": worlds}


def owner_status(parent, tick):
    require(parent["birth_tick"] <= tick, "unborn owner")
    if parent.get("removal_tick") is not None and parent["removal_tick"] <= tick:
        return "exported"
    return "dead" if parent["death_tick"] is not None and parent["death_tick"] <= tick else "living"


def child_status(child, horizon):
    due = child["birth_tick"] + DAY
    state = owner_status(child, min(due, horizon))
    if state != "living":
        return "died" if state == "dead" else "exported"
    return "confirmed" if due <= horizon else "pending"


def samples(first, last):
    """Inclusive, aligned post-step census samples, not an invented lifetime."""
    return max(0, (last - first) // STEP + 1)


def residence(result, start, stop, incumbents, focal):
    require(type(start) is int and type(stop) is int and STEP <= start <= stop <= result["tick"] and
            start % STEP == stop % STEP == 0, "invalid residence window")
    lives = {p["id"]: p for p in result["lineages"]}
    records, owners = [], {}
    for seed in result["seeds"]:
        birth, end = seed["birth_tick"], seed["end_tick"]
        first, last = max(start, birth), min(stop, end - STEP if end is not None else stop)
        count = samples(first, last)
        if not count:
            continue
        parent = lives[seed["parent"]]
        cutoff = parent.get("removal_tick", parent["death_tick"])
        living = samples(first, min(last, cutoff - STEP if cutoff is not None else last))
        statuses = dict.fromkeys(("living", "dead", "exported"), 0)
        statuses["living"] = living
        if living < count:
            statuses[owner_status(parent, last)] = count - living
        ages = {name: samples(max(first, birth + a * DAY), min(last, birth + b * DAY - STEP))
                for name, a, b in (("under1", 0, 1), ("1to16", 1, 16), ("16to32", 16, 32))}
        require(sum(statuses.values()) == sum(ages.values()) == count, "residence partition differs")
        child = lives.get(seed["child_id"])
        tag = "focal" if seed["parent"] in focal else "incumbent" if seed["parent"] in incumbents else "other"
        row = {**seed, "owner_cohort": tag, "first_sample": first, "last_sample": last,
            "slot_samples": count, "parent_status_samples": statuses, "age_samples": ages,
            "first_age_ticks": first - birth, "last_age_ticks": last - birth,
            "right_censored": seed["outcome"] == "pending", "parent_at_exit": owner_status(parent, end) if end is not None else None,
            "child_first_day": child_status(child, result["tick"]) if child else None}
        records.append(row)
        owner = owners.setdefault(seed["parent"], {"id": seed["parent"], "cohort": tag, "seeds": 0, "slot_samples": 0,
            "outcomes": Counter(), "outcome_samples": Counter(), "parent_status_samples": Counter(), "age_samples": Counter()})
        owner["seeds"] += 1
        owner["slot_samples"] += count
        owner["outcomes"][seed["outcome"]] += 1
        owner["outcome_samples"][seed["outcome"]] += count
        owner["parent_status_samples"].update(statuses)
        owner["age_samples"].update(ages)
    occupied = sum(s["slot_samples"] for s in records)
    require(occupied <= 8 * samples(start, stop), "residence exceeds bank capacity")
    summary = {"seeds": len(records), "samples": samples(start, stop), "capacity_slot_samples": 8 * samples(start, stop),
        "occupied_slot_samples": occupied, "empty_slot_samples": 8 * samples(start, stop) - occupied,
        "outcomes": dict(Counter(s["outcome"] for s in records)),
        "outcome_samples": {k: sum(s["slot_samples"] for s in records if s["outcome"] == k) for k in ("germinated", "expired", "pending")},
        "cohort_samples": {k: sum(s["slot_samples"] for s in records if s["owner_cohort"] == k) for k in ("incumbent", "focal", "other")},
        "parent_status_samples": {k: sum(s["parent_status_samples"][k] for s in records) for k in ("living", "dead", "exported")},
        "age_samples": {k: sum(s["age_samples"][k] for s in records) for k in ("under1", "1to16", "16to32")},
        "germination": {k: dict(Counter(s["child_first_day"] for s in records if s["outcome"] == "germinated" and
                                          s["parent_at_exit"] == k)) for k in ("living", "dead", "exported")}}
    return {"window_ticks": [start, stop], "summary": summary, "owners": list(owners.values()), "seeds": records}


def analyze_visits(rows, result, start=START, stop=END):
    """Independently reconcile ordered bank counts and production prerequisites."""
    require(type(rows) is list and len(rows) == samples(start, stop) and start % STEP == stop % STEP == 0 and
            STEP <= start <= stop <= result["tick"], "missing visit clock")
    lives, seeds = descendants.index_records(result["lineages"], result["seeds"], 0, result["tick"])
    for p in lives.values():
        if "removal_tick" in p:
            require(type(p["removal_tick"]) is int and p["birth_tick"] + DAY < p["removal_tick"] <= result["tick"] and
                    p["removal_tick"] % STEP == 0 and p["death_tick"] is None, "invalid export")
    require(all(s["lifetime_ecology_ticks"] == 8192 and s["birth_tick"] <= lives[s["parent"]].get("removal_tick", result["tick"])
                for s in seeds.values()), "wrong viability or post-export purchase")
    births, exits = defaultdict(list), defaultdict(list)
    for key, s in seeds.items():
        births[s["birth_tick"]].append(key)
        if s["end_tick"] is not None:
            exits[s["end_tick"]].append(key)
    bank = {k for k, s in seeds.items() if s["birth_tick"] < start <= (s["end_tick"] or result["tick"])}
    initial = len(bank)
    parents, releases, bought, occupancy, entries = {}, [], set(), Counter(), Counter()
    observed_seed_samples = Counter()
    for tick, row in zip(range(start, stop + STEP, STEP), rows, strict=True):
        require(type(row) is list and len(row) == 2 and type(row[0]) is int and row[0] == tick and
                type(row[1]) is list and len(row[1]) <= 8, "invalid/misordered visit row")
        ending, beginning = set(exits[tick]), len(bank)
        require(ending <= bank, "release was not resident")
        bank -= ending
        entry = len(bank)
        require(0 <= entry <= beginning <= 8, "invalid entry capacity")
        entries[str(entry)] += 1
        prior_buyers, seen = [], set()
        living = {i for i, p in lives.items() if previous.present(p, tick, living=True)}
        for rank, raw in enumerate(row[1]):
            require(type(raw) is list and len(raw) == len(FIELDS) and type(raw[-1]) is bool and
                    all(type(x) is int and x >= 0 for x in raw[:-1]), "invalid visit encoding")
            v = dict(zip(FIELDS, raw, strict=True))
            i = v["id"]
            require(i in lives and i not in seen and lives[i]["birth_tick"] <= tick <= lives[i].get("removal_tick", tick),
                    "unknown/duplicate/exported visitor")
            seen.add(i)
            require(v["energy"] <= 256 and v["water"] <= 512 and v["stress"] <= 8 and v["sun"] <= 255 and
                    v["bank"] == len(bank) <= 8 and (v["flower"] < 256 or v["flower"] == 65535) and
                    (v["ready"] == 0) == (v["flower"] == 65535), "visit inventory/bank differs")
            blocked = (bool(v["cooldown"]), tick % (4 * STEP) != 0, len(bank) == 8, i not in living,
                       bool(v["stress"]), v["sun"] <= 24, lives[i]["generation"] == 65535,
                       v["energy"] < v["energy_required"], v["water"] < v["water_required"], v["flower"] == 65535)
            mask = sum(1 << j for j, b in enumerate(blocked) if b)
            require(v["blockers"] == mask and v["produced"] == (mask == 0), "production gates differ")
            if i in living:
                p = parents.setdefault(i, {"id": i, "living_visits": 0, "masks": Counter(), "ready_window_masks": Counter(),
                    "access": dict.fromkeys(OUTCOMES, 0), "ready_access": dict.fromkeys(OUTCOMES, 0),
                    "purchases": [], "missed_openings": []})
                p["living_visits"] += 1
                p["masks"][str(mask)] += 1
                outcome = "ineligible" if mask & ~BANK else "purchased" if mask == 0 else (
                    "full_at_entry" if entry == 8 else "earlier_buyers_fill")
                p["access"][outcome] += 1
                ready = v["ready"] > 0 and not v["cooldown"] and tick % (4 * STEP) == 0 and v["sun"] > 24
                if ready:
                    p["ready_window_masks"][str(mask)] += 1
                    p["ready_access"][outcome] += 1
                if outcome == "earlier_buyers_fill":
                    require(len(prior_buyers) == 8 - entry and prior_buyers, "unexplained lost opening")
                    p["missed_openings"].append({"tick": tick, "rank": rank, "bank_at_entry": entry,
                        "earlier_buyers": list(prior_buyers), "released_seeds": [list(k) for k in sorted(ending)],
                        "visit": raw})
            if v["produced"]:
                key = i, tick
                require(key in seeds and key not in bank and key not in bought, "purchase differs from ledger")
                bank.add(key)
                bought.add(key)
                prior_buyers.append(i)
                parents[i]["purchases"].append(tick)
        require(living <= seen and set(births[tick]) == {(i, tick) for i in prior_buyers}, "missing living visit/purchase")
        require(len(bank) == beginning - len(ending) + len(prior_buyers) <= 8, "bank conservation failed")
        occupancy[str(len(bank))] += 1
        observed_seed_samples.update(bank)
        if ending:
            releases.append({"tick": tick, "bank_before_ageing": beginning, "bank_at_entry": entry,
                "released_seeds": [list(k) for k in sorted(ending)], "buyers": prior_buyers,
                "bank_after": len(bank), "outcomes": dict(Counter(seeds[k]["outcome"] for k in ending))})
    require(bought == {k for k, s in seeds.items() if start <= s["birth_tick"] <= stop}, "missing observed purchases")
    for i, p in parents.items():
        require(p["living_visits"] == samples(max(start, lives[i]["birth_tick"]),
            min(stop, lives[i]["death_tick"] - STEP if lives[i]["death_tick"] is not None else stop,
                lives[i].get("removal_tick", stop))), "living coverage differs")
        require(sum(p["access"].values()) == p["living_visits"] and
                sum(p["ready_access"].values()) == sum(p["ready_window_masks"].values()), "access partition differs")
    released = sum(len(r["released_seeds"]) for r in releases)
    require(initial + len(bought) - released == len(bank), "window bank conservation failed")
    return {"plants": list(parents.values()), "release_events": releases,
        "bank": {"initial": initial, "final": len(bank), "purchases": len(bought), "releases": released,
            "entry_counts": dict(entries), "post_step_counts": dict(occupancy),
            "released_outcomes": dict(sum((Counter(r["outcomes"]) for r in releases), Counter())),
            "release_steps": len(releases), "release_steps_ending_full": sum(r["bank_after"] == 8 for r in releases),
            "access": {k: sum(p["access"][k] for p in parents.values()) for k in OUTCOMES}},
        "resident_samples": [[*key, n] for key, n in sorted(observed_seed_samples.items())]}


def analyze(data, excerpt):
    previous.check_value(data)
    require(excerpt["rule"] == RULE + "-visits" and excerpt["input_sha256"] == INPUT_SHA and
            excerpt["manifest_sha256"] == MANIFEST_SHA and excerpt["fields"] == list(FIELDS) and
            excerpt["window_ticks"] == [START, END] and excerpt["sample_step"] == STEP and
            len(excerpt["worlds"]) == len(data["worlds"]), "wrong visit excerpt")
    worlds = []
    for w, raw in zip(data["worlds"], excerpt["worlds"], strict=True):
        require(raw["id"] == w["id"] and set(raw["arms"]) == set(w["arms"]), "wrong panel")
        arms = {}
        for arm, source in w["arms"].items():
            require(raw["arms"][arm]["trace_sha256"] == source["traces"]["stand"]["sha256"], "trace provenance differs")
            result = source["result"]
            access = analyze_visits(raw["arms"][arm]["rows"], result)
            old = {p["id"]: p for p in source["audit"]["plants"]}
            require({p["id"] for p in access["plants"]} == set(old), "missing source plant")
            for p in access["plants"]:
                require(all(p[k] == old[p["id"]][k] for k in ("living_visits", "masks", "ready_window_masks", "purchases")),
                        "frozen production summary differs")
            focal = w["cohorts"]["early_vacancy"] if arm == "vacancy" else []
            occupants = w["cohorts"]["old_control"]
            stock = residence(result, START, END, occupants, focal)
            require(access.pop("resident_samples") == sorted([s["parent"], s["birth_tick"], s["slot_samples"]] for s in stock["seeds"]) and
                    stock["summary"]["occupied_slot_samples"] == sum(int(k) * n for k, n in access["bank"]["post_step_counts"].items()),
                    "sampled residence oracle differs")
            lives = {p["id"]: p for p in result["lineages"]}
            arms[arm] = {"result_run_hash": result["run_hash"], "trace_sha256": raw["arms"][arm]["trace_sha256"],
                "access": access, "residence": stock, "focal_residence": [
                    {"id": i, **residence(result, max(START, lives[i]["birth_tick"]),
                        min(END, lives[i]["death_tick"] - STEP if lives[i]["death_tick"] else END), occupants, focal)} for i in focal]}
        worlds.append({k: w[k] for k in ("id", "model", "case", "cohorts")} | {"arms": arms})
    return {"rule": RULE, "input_sha256": INPUT_SHA, "visits_sha256": VISITS_SHA,
            "protocol_sha256": digest(ROOT / PROTOCOL), "native_runs": 0, "training_runs": 0,
            "window_ticks": [START, END], "followup_tick": STOP, "worlds": worlds}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / INPUT)
    parser.add_argument("--visits", type=Path, default=ROOT / VISITS)
    parser.add_argument("--extract-from", type=Path, help="read pinned local traces; no simulation")
    output = parser.add_mutually_exclusive_group(required=True)
    output.add_argument("--out", type=Path)
    output.add_argument("--verify", type=Path)
    args = parser.parse_args()
    try:
        require(args.out is None or not args.out.exists(), "fresh output required")
        data = load(args.input, INPUT_SHA)
        value = extract(args.extract_from, data) if args.extract_from else analyze(data, load(args.visits, VISITS_SHA))
        require(digest(args.input) == INPUT_SHA and (args.extract_from or digest(args.visits) == VISITS_SHA), "input changed during audit")
        if args.verify:
            with gzip.open(args.verify, "rt") as stream:
                require(json.load(stream) == value, "saved bank audit differs")
            print("Verified exact saved production visits; no simulation." if args.extract_from else
                  "Verified ownership, residence, ordered access and descendant outcomes in all twelve arms; no simulation.")
        else:
            previous.founders.write_gzip(args.out, value)
        return 0
    except (OSError, RuntimeError, ValueError, KeyError, TypeError, StopIteration) as error:
        print("bank access audit failed: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
