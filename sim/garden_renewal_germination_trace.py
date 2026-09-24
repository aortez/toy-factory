#!/usr/bin/env python3
"""Frozen, hash-neutral seed-loop receipts for the controlled-gap experiment."""
from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
import shutil
import tempfile
import time

import garden_seed_attempts as audit
import garden_renewal_controlled_gap as gap

experiment, require = gap.experiment, gap.require
RULE = "garden-renewal-germination-trace-v1"
PROTOCOL = "benchmarks/garden-longevity/renewal-germination-trace-protocol.md"
PARENT_SHA = "6ed1985364c40524565131bcc2684dfb4dc1ad6e80d8c4c47693e871fee2effb"
PORTABLE = "benchmarks/garden-longevity/renewal-controlled-gap-summary.json"
PORTABLE_SHA = "0b425bfa990c127cca2ca30b25327ddb62a15813f1210841460dbf6154cac352"
START, END = 49545, 57360
FOCAL = ((7, 49560, 3, 2), (7, 53400, 4, 2), (2, 57240, 5, 1))
native = gap.guard.prior.prior


def settings():
    return {"rule": RULE, "from": START, "end": END, "seed": gap.SEED,
            "focal_seeds": [list(k) for k in FOCAL], "native_calls": 4,
            "frame_replays": 0, "training_calls": 0, "parent_manifest_sha256": PARENT_SHA}


def commands():
    result = []
    for arm in gap.ARMS:
        cmd = ["bin/seed-attempts", "models/r2-n.tgm", "rainfed-crowded",
               experiment.NIGHT_POLICY, "0x"+gap.SEED, "0", str(START), str(END),
               "--focal-model", "models/r2-w.tgm", "--focal-founder", "5"]
        if arm == "gap":
            cmd += ["--gap-at", str(gap.AT), "--gap-lineage", str(gap.REMOVED)]
        for suffix in ("", ".repeat"):
            result.append((f"traces/{arm}{suffix}.jsonl.gz", cmd.copy()))
    return result


def expected_header(arm):
    header = {"type": "seed-audit-header", "schema_version": 1, "rule": "seed-attempt-v1",
        "scenario": "rainfed-crowded", "policy": experiment.NIGHT_POLICY, "seed": gap.SEED,
        "model_crc32": "01b9d94a", "schedule": 0, "from": START, "end": END,
        "node_capacity": 512, "leaf_environment": gap.panel.competition.maintenance.ENVIRONMENT,
        "leaf_policy": "selective", "drainage_rule": None,
        "focal_policy": {"rule": "founder-policy-swap-v1", "founder": 5, "model_crc32": "c9ea07fd"}}
    if arm == "gap":
        header["gap"] = {"protocol": gap.NATIVE, "tick": gap.AT, "id": gap.REMOVED}
    return header


def validate_trace(rows, worlds, sites, header, event=None):
    """Use saved states and the existing sequential validator; never run policy logic."""
    rows = list(rows)
    require(rows and rows[0] == header, "wrong seed trace header")
    rows = rows[1:]
    if event is not None:
        require(event["tick"] < header["from"] and rows and rows[0] == event,
                "wrong/missing pre-window export")
        rows = rows[1:]
    ticks = list(range(header["from"], header["end"]+1, 15))
    require(sorted(worlds) == sorted(sites) == ticks and
            [r.get("tick") for r in rows] == ticks, "incomplete/reordered trace or reference")
    values, hist, born = Counter(), Counter(), []
    for index, row in enumerate(rows):
        t = row["tick"]
        w, s = worlds[t], sites[t]
        require(row["type"] == "seed-step" and row["hash"] == w["hash"] == s["hash"] and
                all(row[k] == s[k] for k in ("sun_phase", "sun_strength")), "observer changed state/sun")
        require(all(row[k] == w[k] == s[k] for k in ("nodes", "births")) and
                row["plants"] == len(w["plants"]) == len(s["plants"]) and
                row["seeds"] == len(w["seeds"]) == len(s["seeds"]) and
                row["expired"] == w["seeds_expired"] == s["seeds_expired"] and
                row["created"] == w["seeds_created"] == s["seeds_created"], "state counters differ")
        require([{k: a[k] for k in ("parent", "generation", "column", "blockers")} for a in w["seeds"]] ==
                [{k: a[k] for k in ("parent", "generation", "column", "blockers")} for a in s["seeds"]],
                "reference banks disagree")
        if index == 0:
            require(row["stages"] == row["sites_before"] == row["attempts"] == [], "origin contains a step")
            continue
        old = {**worlds[t-15], "seeds": sites[t-15]["seeds"]}
        v, h, new = audit.check_step(row, old, w, s, header["node_capacity"])
        values.update(v)
        hist.update({str(i): n for i, n in enumerate(h) if n})
        born.extend({"tick": t, **a} for a in new)
    return {"checkpoints": len(rows), "totals": dict(values), "mature_masks": dict(hist),
            "germinations": born, "first_hash": rows[0]["hash"], "last_hash": rows[-1]["hash"]}, rows


def key(seed, tick=None):
    return (seed["parent"], seed["birth_tick"] if tick is None else tick-seed["age"]*15,
            seed["column"], seed["generation"])


def runs(rows, predicate):
    """Inclusive sampled endpoints, not an unobserved continuous duration."""
    result = []
    for r in rows:
        if not predicate(r):
            continue
        if result and result[-1]["last_tick"]+15 == r["tick"]:
            result[-1]["last_tick"] = r["tick"]
            result[-1]["checks"] += 1
        else:
            result.append({"first_tick": r["tick"], "last_tick": r["tick"], "checks": 1})
    return result


def summarize_seed(visits, seed):
    require(seed["outcome"] in ("expired", "germinated") and
            [r["tick"] for r in visits] == list(range(seed["birth_tick"]+15, seed["end_tick"]+1, 15)),
            "incomplete focal seed lifetime")
    require(all(key(r, r["tick"]) == key(seed) for r in visits) and
            [r["age"] for r in visits] == list(range(1, len(visits)+1)), "wrong focal seed identity/age")
    outcome = 1 if seed["outcome"] == "expired" else 2
    require(visits[-1]["outcome"] == outcome and visits[-1]["child"] == (seed["child_id"] or 0)
            and all(r["outcome"] == 0 and r["child"] == 0 for r in visits[:-1]), "focal outcome differs")
    require((visits[-1]["age"] == 256) == (outcome == 1), "expiry counted as germination check")
    checked = [r for r in visits if r["outcome"] != 1]
    mature = [r for r in checked if r["age"] >= 8]
    ranges = {}
    for field, threshold in (("moisture", 12), ("light", 80)):
        ranges[field] = {"minimum": min(r[field] for r in mature), "maximum": max(r[field] for r in mature),
                         "threshold": threshold, "pass_checks": sum(r[field] >= threshold for r in mature),
                         "pass_runs": runs(mature, lambda r: r[field] >= threshold)}
    last = visits[-1]
    return {"seed": seed, "visits": visits, "mature_checks": len(mature),
        "mature_masks": dict(Counter(str(r["blockers"]) for r in mature)), "resources": ranges,
        "dormant_masks": dict(Counter(str(r["blockers"]) for r in checked if r["age"] < 8)),
        "actual_to_post_site_masks": dict(Counter(f"{r['blockers']}->{r['post_site'][0]}" for r in mature)),
        "waiting_seed_post_mask_differences": sum(r["blockers"] != r["post_seed_mask"] for r in checked if r["outcome"] == 0),
        "joint_resource_pass_checks": sum(r["moisture"] >= 12 and r["light"] >= 80 for r in mature),
        "light_blocked_low_sun": sum(r["light"] < 80 and r["sun_strength"] < 80 for r in mature),
        "light_blocked_adequate_sun": sum(r["light"] < 80 and r["sun_strength"] >= 80 for r in mature),
        "final_visit": last}


def references(root, arm):
    result = []
    for kind in ("world", "sites"):
        selected = [r for r in gap.read_trace(root/f"input/{arm}.{kind}.jsonl.gz")
                    if START <= r["tick"] <= END]
        require([r["tick"] for r in selected] == list(range(START, END+1, 15)), "bad reference window")
        result.append({r["tick"]: r for r in selected})
    return result


def analyze_case(root, arm):
    path = root/f"traces/{arm}.jsonl.gz"
    require(experiment.digest(path) == experiment.digest(root/f"traces/{arm}.repeat.jsonl.gz"), "native repeat changed")
    prior = experiment.read_json(root/"input/results.json")["cases"][arm]
    worlds, sites = references(root, arm)
    event = prior["boundary"]["event"] if arm == "gap" else None
    result, rows = validate_trace(gap.read_trace(path), worlds, sites, expected_header(arm), event)
    focal = {k: [] for k in FOCAL}
    if arm == "gap":
        for row in rows:
            t = row["tick"]
            for index, a in enumerate(row["attempts"]):
                identity = key(a, t)
                if identity not in focal:
                    continue
                post = [s for s in sites[t]["seeds"] if key(s, t) == identity]
                require(len(post) == int(a["outcome"] == 0), "focal post-bank outcome differs")
                focal[identity].append({**a, "tick": t, "hash": row["hash"], "index": index,
                    "sun_phase": row["sun_phase"], "sun_strength": row["sun_strength"],
                    "post_site": sites[t]["sites"][a["column"]],
                    "post_seed_mask": post[0]["blockers"] if post else None})
        result["focal"] = []
        for identity, visits in focal.items():
            seeds = [s for s in prior["seeds"] if key(s) == identity]
            require(len(seeds) == 1, "focal seed missing/ambiguous in saved ledger")
            result["focal"].append(summarize_seed(visits, seeds[0]))
    result["export"] = event
    return result


def copies():
    result = {"input/native-source.tar.gz": "source.tar.gz", "input/results.json": "results.json",
              "input/parent-CMakeCache.txt": "input/CMakeCache.txt"}
    result.update({f"models/{n}.tgm": f"models/{n}.tgm" for n in ("r2-n", "r2-w")})
    for arm in gap.ARMS:
        result[f"input/{arm}.world.jsonl.gz"] = f"traces/{arm}.worlds.jsonl.gz"
        result[f"input/{arm}.sites.jsonl.gz"] = f"traces/{arm}.sites.jsonl.gz"
    return result


def check_inputs(root):
    require(experiment.digest(root/"input/parent-manifest.json") == PARENT_SHA and
            experiment.digest(root/"input/parent-summary.json") == PORTABLE_SHA, "changed parent identity")
    manifest = experiment.read_json(root/"input/parent-manifest.json")
    for dest, source in copies().items():
        require(experiment.digest(root/dest) == manifest["artifacts"][source], "changed parent copy")
    started = experiment.read_json(root/"started.json")
    require(started["settings"] == settings(), "changed protocol settings")
    for name, sha in started["frozen"].items():
        require(experiment.digest(root/name) == sha, "frozen file changed")
    require(experiment.digest(root/"input/protocol.md") == started["sources"][PROTOCOL], "protocol differs")
    old, new = [native.native_hashes(root/p) for p in ("input/native-source.tar.gz", "source.tar.gz")]
    require(old.keys() == new.keys() and {n for n in old if old[n] != new[n]} == {"sim/garden_seed_attempts.c"},
            "unexpected native changes")
    require(all(started["sources"].get(n) == sha for n, sha in new.items()), "native snapshot mismatch")
    require(native.cache_settings(root/"input/CMakeCache.txt") == native.cache_settings(root/"input/parent-CMakeCache.txt"),
            "build ecology/compiler settings differ")


def analyze(root):
    check_inputs(root)
    return {"settings": settings(), "cases": {arm: analyze_case(root, arm) for arm in gap.ARMS}}


def verify(root):
    manifest = experiment.read_json(root/"manifest.json")
    require(manifest["rule"] == RULE and manifest["status"] == "complete", "incomplete/wrong bundle")
    require(set(manifest["artifacts"]) == {str(p.relative_to(root)) for p in root.rglob("*")
            if p.is_file() and p != root/"manifest.json"}, "extra/missing artifact")
    for path in manifest["artifacts"]:
        gap.gallery.artifact(root, manifest, path)
    calls = experiment.read_json(root/"timings.json")["calls"]
    require([(c["artifact"], c["command"]) for c in calls] == commands(), "wrong native call inventory")
    result = analyze(root)
    require(result == experiment.read_json(root/"results.json"), "saved analysis differs")
    return result


def collect(baseline, build, output):
    require(not output.exists() and output.is_relative_to(experiment.ROOT/"artifacts") and
            not output.is_relative_to(baseline) and not output.is_relative_to(build), "choose fresh independent output")
    gap.parent.shadow.check_frozen(baseline, PARENT_SHA)
    require(experiment.digest(experiment.ROOT/PORTABLE) == PORTABLE_SHA, "parent portable changed")
    gap.verify(baseline)
    sources = experiment.source_files()
    output.mkdir(parents=True)
    experiment.snapshot_sources(output, sources)
    for name in ("input", "models", "bin", "traces"):
        (output/name).mkdir()
    for dest, source in copies().items():
        shutil.copy2(baseline/source, output/dest)
    for source, dest in ((baseline/"manifest.json", "input/parent-manifest.json"),
                         (experiment.ROOT/PORTABLE, "input/parent-summary.json"),
                         (experiment.ROOT/PROTOCOL, "input/protocol.md"),
                         (build/"CMakeCache.txt", "input/CMakeCache.txt"),
                         (build/"build.ninja", "input/build.ninja"),
                         (build/"toy-factory-garden-seed-attempts", "bin/seed-attempts")):
        shutil.copy2(source, output/dest)
    frozen = {str(p.relative_to(output)): experiment.digest(p) for p in output.rglob("*") if p.is_file()}
    experiment.write_json(output/"started.json", {"settings": settings(), "sources": sources, "frozen": frozen})
    timings = []
    try:
        check_inputs(output)
        for target, cmd in commands():
            start = time.monotonic()
            with tempfile.TemporaryDirectory(prefix="garden-germination-trace-") as temporary:
                raw = Path(temporary)/"trace.jsonl"
                try:
                    experiment.command_run(cmd, raw, output, 180)
                finally:
                    if raw.exists():
                        experiment.compress(raw, output/target)
            timings.append({"artifact": target, "command": cmd, "seconds": time.monotonic()-start})
            print("Captured", target, flush=True)
            if ".repeat." in target:
                analyze_case(output, Path(target).name.split(".")[0])
        require(experiment.source_files() == sources, "sources changed during capture")
        start = time.monotonic()
        result = analyze(output)
        require(result == analyze(output), "repeated analysis differs")
        require(experiment.source_files() == sources, "sources changed during analysis")
        experiment.write_json(output/"results.json", result)
        experiment.write_json(output/"timings.json", {"calls": timings, "analysis_and_repeat_seconds": time.monotonic()-start})
        artifacts = {str(p.relative_to(output)): experiment.digest(p) for p in output.rglob("*") if p.is_file()}
        experiment.write_json(output/"manifest.json", {"rule": RULE, "status": "complete", "artifacts": artifacts,
            "native_calls": len(timings), "artifact_bytes": sum((output/n).stat().st_size for n in artifacts)})
    except BaseException as error:
        experiment.write_json(output/"failure.json", {"error": str(error), "completed_calls": timings})
        raise
    print("Complete: four repeated captures, saved-state parity and repeated analysis verified", flush=True)


def export(root, target, check=False):
    require(not target.is_relative_to(root), "export outside frozen bundle")
    result = {**verify(root), "manifest_sha256": experiment.digest(root/"manifest.json"),
              "full_results_sha256": experiment.digest(root/"results.json"),
              "exporter_sha256": experiment.digest(Path(__file__)), "timing": experiment.read_json(root/"timings.json")}
    if not check:
        experiment.write_json(target, result)
    require(experiment.read_json(target) == result, "portable export differs")
    print("Portable germination evidence verified", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, default=experiment.ROOT/"artifacts/garden-renewal-controlled-gap-v1")
    parser.add_argument("--build", type=Path, default=experiment.ROOT/"artifacts/build-host-germination-trace-docker")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--export", type=Path)
    parser.add_argument("--check-export", type=Path)
    args = parser.parse_args()
    require(not (args.export and args.check_export) and (args.verify or not (args.export or args.check_export)), "export requires verify")
    if args.export or args.check_export:
        export(args.output.resolve(), (args.export or args.check_export).resolve(), bool(args.check_export))
    elif args.verify:
        verify(args.output.resolve())
    else:
        collect(args.baseline.resolve(), args.build.resolve(), args.output.resolve())


if __name__ == "__main__":
    main()
