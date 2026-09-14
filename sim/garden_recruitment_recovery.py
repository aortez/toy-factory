#!/usr/bin/env python3
"""Trace unchanged disturbance openings, exact seed checks and surviving recruits."""
from __future__ import annotations

import argparse
from collections import Counter
import gzip
import json
from pathlib import Path
import shutil
import tempfile
import time

import garden_renewal_stalls as stalls
import garden_seed_attempts as audit

experiment, require = stalls.experiment, stalls.require
disturbance = audit.recruitment.diversity.disturbance
DAY, STEP = stalls.DAY, stalls.STEP
START, SPLIT, END = 62 * DAY, 94 * DAY, 126 * DAY
RULE = "garden-recruitment-recovery-v1"
BASELINE_SHA = "7e2b0136cfc43babd2d8ffd9442fefe6239eaa3a5ce1a73e588df58ddcb7c1ca"
PROTOCOL = "benchmarks/garden-longevity/recruitment-recovery-protocol.md"


def packed_rows(path):
    with gzip.open(path, "rt") as stream:
        for line in stream:
            yield json.loads(line)


def columns(masks, relaxed=0):
    return [c for c, mask in enumerate(masks) if not mask & ~relaxed]


def local_columns(event, records):
    return [c for c in range(28) if any(abs(c - records[i]["column"]) < 3 for i in event["killed"])]


def owner(events, tick):
    """An ordinary step precedes a disturbance at the same tick."""
    return next((e for e in reversed(events) if e["tick"] < tick <= e["end_tick"]), None)


def birth_record(p, records, event=None):
    due = p["birth_tick"] + DAY
    death = p["death_tick"]
    status = "pending" if due > END + DAY else "confirmed" if stalls.confirmed(p, due) else \
             "patch_failure" if p["environmental_death"] else "natural_failure"
    return {"id": p["id"], "parent": p["parent"], "generation": p["generation"], "column": p["column"],
            "birth_tick": p["birth_tick"], "confirmation_tick": due, "status": status,
            "early_death_tick": death if death is not None and death <= due else None,
            "parent_class": stalls.parent_class(records[p["parent"]], p["birth_tick"]),
            "qualifying": status == "confirmed" and stalls.qualifies(p, records, due),
            "local": p["column"] in event["local_columns"] if event else None,
            "delay_ticks": p["birth_tick"] - event["tick"] if event else None}


def attempt_exposure(row, records, supports):
    """Exact sequential checks; hypothetical support never means actual eligibility."""
    groups = {name: Counter() for name in stalls.PARENT_CLASSES}
    visits = []
    for a in row["attempts"]:
        key = (a["parent"], row["tick"] - a["age"] * STEP)
        group = groups[stalls.parent_class(records[a["parent"]], row["tick"])]
        group["visits"] += 1
        if a["outcome"] == 1:
            group["expired"] += 1
            continue
        if a["age"] < 8:
            group["dormant"] += 1
            continue
        open_cols = columns(a["sites"])
        reachable = [c for c in open_cols if supports[key] & (1 << c)]
        displaced = row["sites_before"][a["column"]] == 0 and a["blockers"] != 0
        values = {"mature_checks": 1, "any_open": int(bool(open_cols)),
                  "reachable_open": int(bool(reachable)), "actual_open": int(a["blockers"] == 0),
                  "sequentially_displaced": int(displaced), "germinated": int(a["outcome"] == 2),
                  **{"blocked_" + k: int(bool(a["blockers"] & bit)) for k, bit in audit.establishment.BLOCKERS.items()}}
        require(values["actual_open"] == values["germinated"], "actual opportunity did not germinate")
        group.update(values)
        visits.append({"key": key, "values": values, "blockers": a["blockers"]})
    return groups, visits


def expected_header(seed, crc):
    return {"type": "seed-audit-header", "schema_version": 1, "rule": "seed-attempt-v1",
            "scenario": "rainfed-crowded", "policy": "neural-no-night-growth", "seed": seed,
            "model_crc32": crc, "schedule": int(stalls.PATCH, 16), "from": START, "end": END,
            "node_capacity": 512, "leaf_environment": "leaf-maintenance-v1", "leaf_policy": "selective", "drainage_rule": None}


def attempt_rows(path, header, events):
    stream = iter(packed_rows(path))
    require(next(stream, None) == header, "wrong audit header/model/configuration")
    tick, index = START - STEP, 0
    for row in stream:
        if row["type"] == "disturbance":
            require(index < len(events) and row == events[index] and
                    (row["tick"] < START or row["tick"] == tick), "wrong audit event/order")
            index += 1
            continue
        require(row["type"] == "seed-step" and row["tick"] == tick + STEP and row["tick"] <= END,
                "incomplete/reordered audit")
        tick = row["tick"]
        yield row
    require(tick == END and index == len(events), "truncated audit/events")


def new_event(event, end, records):
    return {**event, "end_tick": end, "right_censored": end == END,
            "local_columns": local_columns(event, records), "reclaimed": {}, "first": {},
            "exposure": Counter(), "attempts": {k: Counter() for k in stalls.PARENT_CLASSES}, "births": []}


def note_step(event, row, groups, reclaimed, born):
    if event is None:
        return
    tick = row["tick"]
    masks, local = row["sites_before"], event["local_columns"]
    opened = columns(masks)
    values = {"steps": 1, "plant_slot": int(not masks[0] & 8), "any_open": int(bool(opened)),
              "local_geometric": int(any(not masks[c] & 56 for c in local)),
              "local_open": int(any(c in opened for c in local)),
              "any_open_no_birth": int(bool(opened) and not born)}
    event["exposure"].update(values)
    for name in ("plant_slot", "any_open", "local_geometric", "local_open"):
        if values[name]:
            event["first"].setdefault(name, tick)
    for identity in reclaimed:
        if identity in event["killed"]:
            event["reclaimed"][str(identity)] = tick
    for name, counts in groups.items():
        event["attempts"][name].update(counts)
    for b in born:
        event["births"].append(b)
        for name, yes in (("birth", True), ("local_birth", b["local"]),
                          ("confirmed_birth", b["status"] == "confirmed"),
                          ("local_confirmed_birth", b["local"] and b["status"] == "confirmed"),
                          ("qualifying_birth", b["qualifying"])):
            if yes:
                event["first"].setdefault(name, tick)


def analyze_case(root, identity, seed, crc):
    trial = experiment.read_json(root / "input" / f"{identity}.json")
    stalls.pilot.validate_trial(trial, seed, crc, patch=stalls.PATCH)
    records = {p["id"]: p for p in trial["lineages"]}
    seed_records = {(s["parent"], s["birth_tick"]): s for s in trial["seeds"]}
    require(len(seed_records) == len(trial["seeds"]), "duplicate original seed key")
    sparse = {r["tick"]: r for r in stalls.read_census(root / "input" / f"{identity}.census.jsonl") if r["type"] == "world" and r["tick"] <= END}
    bounds = experiment.read_json(root / "traces" / f"{identity}.boundaries.json")
    planned = disturbance.schedule(int(stalls.PATCH, 16), END)
    events = [b["event"] for b in bounds["world"]]
    require(events == [b["event"] for b in bounds["sites"]] and len(events) == len(planned) and
            all(all(e[k] == v for k, v in p.items()) for e, p in zip(events, planned, strict=True)), "wrong patch panel")
    after, site_after = {}, {}
    for w, s in zip(bounds["world"], bounds["sites"], strict=True):
        for b in (w, s):
            disturbance.validate_boundary(b["before"], b["after"], b["event"])
        require(w["after"]["hash"] == s["after"]["hash"], "post-patch hash differs")
        after[w["event"]["tick"]] = w["after"]
        site_after[s["event"]["tick"]] = s["after"]
    selected = [e for e in events if START < e["tick"] <= END]
    episodes = [new_event(e, selected[i+1]["tick"] if i+1 < len(selected) else END, records)
                for i, e in enumerate(selected)]
    groups = {band: {name: Counter() for name in stalls.PARENT_CLASSES} for band in ("gap", "recovery")}
    exposure = {band: Counter() for band in groups}
    seed_exposure, supports, reclaimed_all, births = {}, {}, {}, []
    trace = iter(attempt_rows(root / "traces" / f"{identity}.attempts.gz", expected_header(seed, crc), events))
    old_w, old_s, checked, sparse_checked, last = None, None, 0, 0, -STEP
    for w, s in zip(packed_rows(root / "traces" / f"{identity}.world.gz"),
                    packed_rows(root / "traces" / f"{identity}.sites.gz"), strict=True):
        tick = w["tick"]
        require(tick == last + STEP and tick <= END and s["tick"] == tick and s["hash"] == w["hash"], "world/site stream mismatch")
        audit.recruitment.competition.maintenance.check_identity(w, "selective", 512)
        audit.recruitment.site_identity(s, 512, "neural")
        audit.check_sites([v[0] for v in s["sites"]], s["nodes"], s["plants"], 512)
        current_w, current_s = after.get(tick, w), site_after.get(tick, s)
        if tick in sparse:
            require(current_w == sparse[tick], "original census changed")
            sparse_checked += 1
        for p in current_w["plants"]:
            saved = records[p["id"]]
            require(all(p[k] == saved[k] for k in ("parent", "generation", "column")) and
                    p["dead"] == (saved["death_tick"] is not None and saved["death_tick"] <= tick), "original plant identity/fate differs")
        for v in s["seeds"]:
            key = audit.establishment.seed_key(v, tick)
            saved = seed_records[key]
            require(all(v[k] == saved[k] for k in ("parent", "column", "generation")) and
                    v["species"] == records[v["parent"]]["species"] and
                    (saved["end_tick"] is None or saved["end_tick"] > tick), "original seed identity/lifetime differs")
            if v["age"] == 0:
                parent = next(p for p in s["plants"] if p["id"] == v["parent"])
                supports[key] = parent["dispersal_columns"]
        if old_w is not None:
            removed = [p["id"] for p in old_w["plants"] if p["id"] not in {q["id"] for q in w["plants"]}]
            require(all(records[i]["death_tick"] is not None and records[i]["death_tick"] < tick for i in removed), "live plant reclaimed")
            reclaimed_all.update({str(i): tick for i in removed})
        else:
            removed = []
        if tick >= START:
            row = next(trace, None)
            require(row is not None and row["tick"] == tick and row["hash"] == w["hash"] and
                    all(row[k] == w[k] for k in ("nodes", "births", "sun_phase", "sun_strength")) and
                    row["plants"] == len(w["plants"]) and row["seeds"] == len(w["seeds"]) and
                    row["created"] == w["seeds_created"] and row["expired"] == w["seeds_expired"], "audit changed reference world")
            if tick == START:
                require(row["stages"] == row["sites_before"] == row["attempts"] == [], "start contains a step")
            else:
                values, _, germinated = audit.check_step(row, {**old_w, "seeds": old_s["seeds"]}, w, s, 512)
                band = "gap" if tick <= SPLIT else "recovery"
                exposure[band].update(values)
                ag, visits = attempt_exposure(row, records, supports)
                for name, counts in ag.items():
                    groups[band][name].update(counts)
                for visit in visits:
                    key = visit["key"]
                    item = seed_exposure.setdefault(key, {"parent": key[0], "birth_tick": key[1],
                        "column": seed_records[key]["column"], "reachable_columns": supports[key],
                        "first": {}, "counts": Counter(), "blockers": Counter()})
                    item["counts"].update(visit["values"])
                    item["blockers"][str(visit["blockers"])] += 1
                    for k in ("any_open", "reachable_open", "actual_open", "sequentially_displaced"):
                        if visit["values"][k]:
                            item["first"].setdefault(k, tick)
                for a in row["attempts"]:
                    saved = seed_records[(a["parent"], tick - a["age"] * STEP)]
                    outcome = {0: "pending", 1: "expired", 2: "germinated"}[a["outcome"]]
                    require((outcome == "pending" and (saved["end_tick"] is None or saved["end_tick"] > tick)) or
                            (saved["outcome"] == outcome and saved["end_tick"] == tick and
                             (a["child"] == 0 if outcome == "expired" else a["child"] == saved["child_id"])), "original seed fate differs")
                event = owner(episodes, tick)
                born = [birth_record(records[a["child"]], records, event) for a in germinated]
                require(all(b["birth_tick"] == tick for b in born), "original birth tick differs")
                births.extend(born)
                note_step(event, row, ag, removed, born)
                checked += 1
        old_w, old_s, last = current_w, current_s, tick
    require(last == END and next(trace, None) is None and checked == (END-START)//STEP and sparse_checked == len(sparse), "truncated references")
    expected_births = {p["id"] for p in records.values() if p["parent"] and START < p["birth_tick"] <= END}
    require({b["id"] for b in births} == expected_births, "missing original births")
    for e in episodes:
        # Reclamation can extend past the next patch, so keep that time separately.
        e["victim_reclamation_ticks"] = {str(i): reclaimed_all.get(str(i)) for i in e["killed"]}
    seed_results = []
    for key, item in sorted(seed_exposure.items()):
        saved = seed_records[key]
        item["outcome"] = saved["outcome"] if saved["end_tick"] is not None and saved["end_tick"] <= END else "pending"
        item["end_tick"] = saved["end_tick"] if item["outcome"] != "pending" else None
        seed_results.append(item)
    return {"id": identity, "seed": seed, "model_crc32": crc, "events": episodes, "births": births,
            "natural_deaths": [p for p in records.values() if p["death_tick"] is not None and START < p["death_tick"] <= END and not p["environmental_death"]],
            "groups": groups, "exposure": exposure, "seeds": seed_results,
            "matched_world_site_ticks": END//STEP+1, "matched_prior_censuses": sparse_checked,
            "checked_seed_steps": checked, "final_hash": old_w["hash"]}


def analyze(root):
    return {"rule": RULE, "native_processes": 12, "training_runs": 0, "new_images": 0,
            "cases": [analyze_case(root, f"{name}.{seed}", seed, crc)
                      for seed in stalls.SEEDS for name, crc in stalls.MODELS.values()]}


def verify(root):
    manifest = experiment.read_json(root / "manifest.json")
    require(manifest["rule"] == RULE and manifest["status"] == "complete", "wrong/incomplete bundle")
    for name in manifest["artifacts"]:
        stalls.gallery.artifact(root, manifest, name)
    require(experiment.digest(root / "input/stalls-manifest.json") == BASELINE_SHA, "wrong frozen stall input")
    prior = experiment.read_json(root / "input/stalls-manifest.json")
    for dest, src in manifest["copied"].items():
        require(experiment.digest(root / dest) == prior["artifacts"][src], "copied input changed")
    result = analyze(root)
    require(result == experiment.read_json(root / "results.json"), "recovery reanalysis differs")
    print("Verified four matched recovery trajectories and exact sequential seed checks", flush=True)
    return result


def review_summary(result):
    """Portable diagnostic comparisons; no new score or opportunity denominator."""
    rows = []
    for c in result["cases"]:
        bands = {}
        for band in ("gap", "recovery"):
            e, groups = c["exposure"][band], c["groups"][band]
            descendants = Counter()
            for name in ("established-descendant", "unconfirmed-descendant"):
                descendants.update(groups[name])
            bands[band] = {"ecology_steps": e["steps"], "open_steps": e["pre_open"],
                "open_steps_without_birth": e["pre_open_no_germination"],
                "open_steps_without_mature_seed": e["pre_open_no_mature_seed"],
                "founder_attempts": groups["founder"], "descendant_attempts": dict(descendants),
                "births": [b for b in c["births"] if (START if band == "gap" else SPLIT) <
                           b["birth_tick"] <= (SPLIT if band == "gap" else END)]}
        events = []
        for e in c["events"]:
            opened = e["first"].get("local_open")
            local = [b for b in e["births"] if b["local"]]
            confirmed = [b for b in local if b["status"] == "confirmed"]
            first = local[0] if local else None
            survivor = confirmed[0] if confirmed else None
            require(first is None or opened is not None and first["birth_tick"] >= opened,
                    "local birth preceded any usable local site")
            events.append({"index": e["index"], "tick": e["tick"], "end_tick": e["end_tick"],
                "killed": e["killed"], "local_columns": e["local_columns"], "first_local_open_tick": opened,
                "reclamation_ticks": e["victim_reclamation_ticks"],
                "first_local_birth": first, "first_local_survivor": survivor,
                "first_local_birth_after_open_ticks": first["birth_tick"]-opened if first else None,
                "first_local_survivor_birth_after_open_ticks": survivor["birth_tick"]-opened if survivor else None,
                "births_elsewhere": [b for b in e["births"] if not b["local"]],
                "local_open_steps": e["exposure"].get("local_open", 0)})
        rows.append({"id": c["id"], "bands": bands, "events": events})
    return {"cases": rows, "note": "Selected trajectories; event ownership is temporal, not causal; open steps and seed checks are repeated observations, not independent trials."}


def portable(root, result):
    return {**result, "manifest_sha256": experiment.digest(root / "manifest.json"),
            "timings": experiment.read_json(root / "timings.json"), "review": review_summary(result)}


def collect(baseline, build, output):
    require(output.is_relative_to(experiment.ROOT / "artifacts") and not output.exists() and not output.is_relative_to(baseline), "choose fresh separate artifact directory")
    require(experiment.digest(baseline / "manifest.json") == BASELINE_SHA, "wrong baseline")
    stalls.verify(baseline)
    prior = experiment.read_json(baseline / "manifest.json")
    sources = experiment.source_files()
    require(all(sources.get(n) == sha for n, sha in prior["sources"].items() if n.endswith((".c", ".h"))), "native sources changed")
    require(experiment.digest(build / "CMakeCache.txt") == prior["artifacts"]["input/CMakeCache.txt"], "build configuration changed")
    output.mkdir(parents=True)
    for folder in ("input", "bin", "traces"):
        (output / folder).mkdir()
    experiment.snapshot_sources(output, sources)
    copied = {"bin/garden-inspect": "bin/garden-inspect", "input/CMakeCache.txt": "input/CMakeCache.txt"}
    for name, _ in stalls.MODELS.values():
        copied[f"input/{name}.tgm"] = f"input/{name}.tgm"
        for seed in stalls.SEEDS:
            identity = f"{name}.{seed}"
            copied[f"input/{identity}.json"] = f"input/{identity}.json"
            copied[f"input/{identity}.census.jsonl"] = f"census/{identity}.jsonl"
    for dest, src in copied.items():
        shutil.copy2(baseline / src, output / dest)
    shutil.copy2(baseline / "manifest.json", output / "input/stalls-manifest.json")
    native = build / "toy-factory-garden-seed-attempts"
    native_sha = experiment.digest(native)
    shutil.copy2(native, output / "bin/seed-attempts")
    require(experiment.digest(output / "bin/seed-attempts") == native_sha, "audit binary copy differs")
    shutil.copy2(experiment.ROOT / PROTOCOL, output / "protocol.md")
    frozen = {str(p.relative_to(output)): experiment.digest(p) for d in ("input", "bin") for p in (output / d).iterdir()}
    experiment.write_json(output / "started.json", {"rule": RULE, "copied": copied, "frozen": frozen, "sources": sources})
    started, timings, cases = time.monotonic(), [], []
    try:
        for seed in stalls.SEEDS:
            for name, crc in stalls.MODELS.values():
                identity = f"{name}.{seed}"
                model = f"input/{name}.tgm"
                require(stalls.pilot.model_crc(output / model) == crc, "model CRC differs")
                args = [model, "rainfed-crowded", "neural-no-night-growth", "0x" + seed]
                bounds = {}
                for kind, flag in (("world", "--ecology"), ("sites", "--seed-sites")):
                    command = ["bin/garden-inspect", *args, "--leaf-policy", "selective", "--disturbance-seed", str(int(stalls.PATCH, 16)), flag, "--ticks", str(END)]
                    t = time.monotonic()
                    bounds[kind] = disturbance.capture(command, output / "traces" / f"{identity}.{kind}.gz", output,
                        "world" if kind == "world" else "seed-sites", int(stalls.PATCH, 16), END)
                    timings.append({"command": command, "seconds": time.monotonic() - t})
                    print("Captured", identity, kind, flush=True)
                experiment.write_json(output / "traces" / f"{identity}.boundaries.json", bounds)
                command = ["bin/seed-attempts", *args, str(int(stalls.PATCH, 16)), str(START), str(END)]
                t = time.monotonic()
                with tempfile.TemporaryDirectory(prefix="garden-recovery-") as temp:
                    raw = Path(temp) / "audit.jsonl"
                    experiment.command_run(command, raw, output, 300)
                    experiment.compress(raw, output / "traces" / f"{identity}.attempts.gz")
                timings.append({"command": command, "seconds": time.monotonic() - t})
                case = analyze_case(output, identity, seed, crc)
                cases.append(case)
                print("Checked", identity, case["checked_seed_steps"], "seed steps", flush=True)
        result = {"rule": RULE, "native_processes": 12, "training_runs": 0, "new_images": 0, "cases": cases}
        require(result == analyze(output) and len(timings) == 12, "repeat/process count differs")
        require(experiment.source_files() == sources and all(experiment.digest(output / n) == sha for n, sha in frozen.items()), "source/input changed during collection")
        experiment.write_json(output / "results.json", result)
        experiment.write_json(output / "timings.json", {"seconds": time.monotonic() - started, "calls": timings})
        artifacts = {str(p.relative_to(output)): experiment.digest(p) for p in output.rglob("*") if p.is_file()}
        experiment.write_json(output / "manifest.json", {"rule": RULE, "status": "complete", "copied": copied,
            "sources": sources, "artifacts": artifacts, "artifact_bytes": sum((output / n).stat().st_size for n in artifacts)})
    except BaseException as error:
        experiment.write_json(output / "failure.json", {"error": str(error)})
        raise
    verify(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, default=experiment.ROOT / "artifacts/garden-renewal-stalls-v1")
    parser.add_argument("--build", type=Path, default=experiment.ROOT / "artifacts/persistence-pilot-build")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--export", type=Path)
    parser.add_argument("--check-export", type=Path)
    args = parser.parse_args()
    require(not (args.export and args.check_export) and (args.verify or not (args.export or args.check_export)),
            "export/check-export requires verify")
    if args.verify:
        root = args.output.resolve()
        result = verify(root)
        if args.export:
            target = args.export.resolve()
            require(not target.is_relative_to(root) and not target.exists(), "choose a fresh external export path")
            experiment.write_json(target, portable(root, result))
        elif args.check_export:
            require(experiment.read_json(args.check_export) == portable(root, result), "portable recovery summary differs")
            print("Portable recovery summary matches verified native evidence", flush=True)
    else:
        collect(args.baseline.resolve(), args.build.resolve(), args.output.resolve())


if __name__ == "__main__":
    main()
