#!/usr/bin/env python3
"""Audit seed lifetimes and germination sites in unchanged, hash-matched Garden worlds."""

from __future__ import annotations

import argparse
from collections import Counter
import gzip
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

import garden_experiments as experiment
from garden_resources import require

ROOT = Path(__file__).resolve().parents[1]
COLUMNS = 28
ECOLOGY_TICKS = 15
DORMANCY = 8
LIFETIME = 256
BLOCKERS = {"moisture": 2, "light": 4, "plant_capacity": 8, "node_capacity": 16, "spacing": 32}
NOTES = [
    "Sites are post-step snapshots, after seed checks and subsequent growth/light updates. They are not exact pre-germination decision conditions.",
    "Germinated/expired outcomes are reconciled from seed age, new plant ancestry and aggregate counters at every ecology step.",
    "Bright-day snapshots require sun strength >=128; night is phase >=128. Twilight is reported separately.",
    "Anywhere-open is an unconstrained spatial upper bound; reachable-open uses the parent's dispersal support at seed creation, not a new RNG draw or probability.",
    "Single-blocker counts describe an instantaneous relaxation, not a changed simulation or demonstrated offspring survival.",
    "Full-follow-up cohorts include seeds born at least one seed lifetime before the horizon, whether they germinated early or expired.",
]


def verified(root: Path, manifest: dict, name: str) -> Path:
    path = (root / name).resolve()
    require(path.is_relative_to(root) and name in manifest["artifacts"], "unsafe/unrecorded artifact")
    require(experiment.digest(path) == manifest["artifacts"][name], f"artifact changed: {name}")
    return path


def empty_window() -> dict:
    return {"samples": 0, "bank_samples": 0, "mature_bank_samples": 0, "any_open_samples": 0,
            "mature_bank_any_open_samples": 0, "mature_seed_samples": 0,
            "actual_open_seed_samples": 0, "any_open_seed_samples": 0,
            "reachable_open_seed_samples": 0, "actual_blocker_hist": [0]*64,
            "site_blocker_hist": [0]*64, "open_column_samples": [0]*COLUMNS,
            "seed_column_samples": [0]*COLUMNS}


def seed_key(seed: dict, tick: int) -> tuple[int, int]:
    return seed["parent"], tick - seed["age"] * ECOLOGY_TICKS


def cohort(records: list[dict], end: int, start: int | None = None) -> dict:
    seeds = [s for s in records if start is None or s["birth_tick"] > start]
    eligible = [s for s in seeds if s["birth_tick"] + LIFETIME*ECOLOGY_TICKS <= end]
    result = {"created": len(seeds), "full_followup": len(eligible), "recent": len(seeds)-len(eligible)}
    for scope, group in (("all", seeds), ("full_followup", eligible)):
        for outcome in ("germinated", "expired", "pending"):
            selected = [s for s in group if s["outcome"] == outcome]
            result[f"{scope}_{outcome}"] = len(selected)
            if outcome == "expired":
                for name in ("actual", "any", "reachable"):
                    result[f"{scope}_expired_ever_{name}_open"] = sum(
                        s[f"first_{name}_open_tick"] is not None for s in selected)
    require(result["full_followup_pending"] == 0, "eligible seed still pending beyond lifetime")
    return result


def analyze(path: Path, reference: list[dict], late_cycles: int, node_capacity: int = 256) -> dict:
    with gzip.open(path, "rt") as stream:
        return analyze_stream(stream, reference, late_cycles, node_capacity)


def analyze_stream(stream, reference: list[dict], late_cycles: int, node_capacity: int = 256,
                   *, seed_capacity: int = 8) -> dict:
    end = reference[-1]["tick"]
    start = end - late_cycles * experiment.CYCLE_TICKS
    require(0 <= start < end, "invalid late window")
    expected = {row["tick"]: row for row in reference}
    windows = {window: {phase: empty_window() for phase in ("bright", "twilight", "night")}
               for window in ("whole", "late")}
    records, active, seen_plants = {}, {}, set()
    previous = {"tick": -ECOLOGY_TICKS, "births": 0, "seeds_created": 0, "seeds_expired": 0}
    checked = 0
    for line in stream:
        row = json.loads(line)
        tick = row["tick"]
        require(row["schema_version"] == 1 and row["type"] == "seed-sites", "invalid census schema")
        require(row.get("node_capacity", 256) == node_capacity and 0 <= row["nodes"] <= node_capacity,
                "wrong census node capacity")
        require(tick == previous["tick"] + ECOLOGY_TICKS and tick <= end, "missing/reordered census tick")
        require(row["sun_phase"] == (64 + tick//15) % 256, "invalid census sun phase")
        require(seed_capacity in (8, 16) and row.get("seed_capacity", 8) == seed_capacity,
                "wrong census seed capacity")
        require(len(row["sites"]) == COLUMNS and len(row["seeds"]) <= seed_capacity and len(row["plants"]) <= 8,
                "invalid census capacities")
        for mask, water, light in row["sites"]:
            require(0 <= mask < 64 and not mask & 1 and 0 <= water <= 255 and 0 <= light <= 255,
                    "invalid site observation")
        if tick in expected:
            ref = expected[tick]
            for name in ("hash", "sun_phase", "sun_strength", "rain_rate", "nodes", "living",
                         "births", "deaths", "seeds_created", "seeds_expired"):
                require(row[name] == ref[name], f"census/reference mismatch: tick {tick} {name}")
            require(len(row["seeds"]) == ref["seed_bank"] and len(row["plants"]) == ref["plant_slots"],
                    "census/reference bank mismatch")
            checked += 1
        plants = {p["id"]: p for p in row["plants"]}
        require(len(plants) == len(row["plants"]), "duplicate plant identity")
        newborns = [p for p in row["plants"] if p["id"] not in seen_plants and p["parent"]]
        require(len(newborns) == row["births"] - previous["births"], "missing newborn lineage")
        seen_plants.update(plants)
        current = {}
        for seed in row["seeds"]:
            require(0 <= seed["age"] < LIFETIME and 0 <= seed["column"] < COLUMNS,
                    "invalid seed age/column")
            key = seed_key(seed, tick)
            require(key not in current, "ambiguous seed identity")
            current[key] = seed
            if key in active:
                old = active[key]
                require(seed["age"] == old["age"]+1 and all(seed[k] == old[k]
                        for k in ("parent", "column", "generation", "species")), "seed identity changed")
            else:
                require(key not in records and seed["age"] == 0 and tick > 0, "unobserved seed creation")
                parent = plants.get(seed["parent"])
                require(parent is not None and not parent["dead"], "seed created without living parent")
                reachable = parent["dispersal_columns"]
                require(0 < reachable < 1 << COLUMNS and reachable & (1 << seed["column"]),
                        "actual landing outside parent dispersal support")
                records[key] = {"parent": key[0], "birth_tick": key[1], "column": seed["column"],
                                "generation": seed["generation"], "species": seed["species"],
                                "reachable_columns": reachable, "outcome": "pending", "end_tick": None,
                                "child_id": None, "first_actual_open_tick": None,
                                "first_any_open_tick": None, "first_reachable_open_tick": None}
            expected_mask = row["sites"][seed["column"]][0] | (1 if seed["age"] < DORMANCY else 0)
            require(seed["blockers"] == expected_mask, "site and real-seed checks disagree")
        require(len(current.keys()-active.keys()) == row["seeds_created"]-previous["seeds_created"],
                "seed creation counter mismatch")
        expired = 0
        for key in active.keys()-current.keys():
            old, record = active[key], records[key]
            record["end_tick"] = tick
            if old["age"]+1 == LIFETIME:
                record["outcome"] = "expired"
                expired += 1
            else:
                matches = [p for p in newborns if all(p[k] == old[k]
                           for k in ("parent", "column", "generation", "species"))]
                require(len(matches) == 1 and old["age"]+1 >= DORMANCY,
                        "seed disappearance without unambiguous germination")
                record["outcome"] = "germinated"
                record["child_id"] = matches[0]["id"]
                newborns.remove(matches[0])
        require(not newborns and expired == row["seeds_expired"]-previous["seeds_expired"],
                "unreconciled seed outcome")
        open_mask = sum(1 << column for column, site in enumerate(row["sites"]) if site[0] == 0)
        mature = [s for s in row["seeds"] if s["age"] >= DORMANCY]
        for seed in mature:
            record = records[seed_key(seed, tick)]
            for name, yes in (("actual", seed["blockers"] == 0), ("any", open_mask != 0),
                              ("reachable", open_mask & record["reachable_columns"] != 0)):
                if yes and record[f"first_{name}_open_tick"] is None:
                    record[f"first_{name}_open_tick"] = tick
        # Exclude reset; whole/late windows contain completed ecology steps.
        if tick:
            phase = "night" if row["sun_phase"] >= 128 else ("bright" if row["sun_strength"] >= 128 else "twilight")
            for window in (["whole", "late"] if tick > start else ["whole"]):
                m = windows[window][phase]
                m["samples"] += 1
                m["bank_samples"] += bool(row["seeds"])
                m["mature_bank_samples"] += bool(mature)
                m["any_open_samples"] += bool(open_mask)
                m["mature_bank_any_open_samples"] += bool(mature) and bool(open_mask)
                for column, (mask, _, _) in enumerate(row["sites"]):
                    m["site_blocker_hist"][mask] += 1
                    m["open_column_samples"][column] += mask == 0
                for seed in mature:
                    record = records[seed_key(seed, tick)]
                    m["mature_seed_samples"] += 1
                    m["actual_open_seed_samples"] += seed["blockers"] == 0
                    m["any_open_seed_samples"] += bool(open_mask)
                    m["reachable_open_seed_samples"] += bool(open_mask & record["reachable_columns"])
                    m["actual_blocker_hist"][seed["blockers"]] += 1
                    m["seed_column_samples"][seed["column"]] += 1
        previous, active = row, current
    require(previous["tick"] == end and checked == len(reference), "truncated census/reference coverage")
    seeds = list(records.values())
    require(len(seeds) == previous["seeds_created"], "missing lifetime records")
    require(sum(s["outcome"] == "germinated" for s in seeds) == previous["births"], "birth outcome mismatch")
    return {"end_tick": end, "late_start_tick": start, "checkpoints_verified": checked,
            "windows": windows, "seeds": seeds, "cohorts": {"whole": cohort(seeds, end),
                                                            "late_born": cohort(seeds, end, start)}}


def aggregate(cases: list[dict]) -> dict:
    result = {}
    for policy in sorted({case["policy"] for case in cases}):
        group = [c for c in cases if c["policy"] == policy]
        windows = {w: {p: empty_window() for p in ("bright", "twilight", "night")} for w in ("whole", "late")}
        cohorts = {w: Counter() for w in ("whole", "late_born")}
        for case in group:
            for w in windows:
                for p in windows[w]:
                    for name, value in case["analysis"]["windows"][w][p].items():
                        if isinstance(value, list):
                            windows[w][p][name] = [a+b for a, b in zip(windows[w][p][name], value, strict=True)]
                        else:
                            windows[w][p][name] += value
            for w in cohorts:
                cohorts[w].update(case["analysis"]["cohorts"][w])
        result[policy] = {"trials": len(group), "windows": windows, "cohorts": cohorts}
    return result


def markdown(result: dict) -> str:
    lines = ["# Garden seed establishment audit", "", *[f"- {note}" for note in NOTES], "",
             "## Late-born seeds with full potential follow-up", "",
             "| Policy | Seeds | Germinated | Expired | Expired: any site ever open | Expired: reachable site ever open |",
             "|---|---:|---:|---:|---:|---:|"]
    for policy, data in result["aggregate"].items():
        c = data["cohorts"]["late_born"]
        names = ("full_followup", "full_followup_germinated", "full_followup_expired",
                 "full_followup_expired_ever_any_open", "full_followup_expired_ever_reachable_open")
        lines.append(f"| {policy} | " + " | ".join(str(c[n]) for n in names) + " |")
    lines += ["", "## Late bright-day mature-seed snapshots", "",
              "Counts below are repeated seed observations, not independent seeds or germination probabilities.", "",
              "| Policy | Observations | Actual site open | Anywhere open | Reachable site open |",
              "|---|---:|---:|---:|---:|"]
    for policy, data in result["aggregate"].items():
        m = data["windows"]["late"]["bright"]
        lines.append(f"| {policy} | " + " | ".join(str(m[n]) for n in ("mature_seed_samples",
                     "actual_open_seed_samples", "any_open_seed_samples", "reachable_open_seed_samples")) + " |")
    lines += ["", "## Late bright-day site maps", "",
              "Each row is a world; each character a soil column (0–27, left to right).",
              "Open-snapshot fraction: `.` = never, `1`–`9` = successive 10% bands, `A` = 90–100%.",
              "These are independent hypothetical mature-seed sites under unchanged post-step conditions.", "",
              "```text", "Policy                  Layout           Seed      Columns 0-------------------------27"]
    for case in result["cases"]:
        m = case["analysis"]["windows"]["late"]["bright"]
        strip = "".join("." if n == 0 else "123456789A"[min(9, (n*10-1)//m["samples"])]
                        for n in m["open_column_samples"])
        lines.append(f"{case['policy']:23} {case['scenario']:16} {case['seed']}  {strip}")
    lines += ["```", "", "[Full summary and per-trial references](summary.json) · [Provenance](manifest.json)", ""]
    return "\n".join(lines)


def collect(args: argparse.Namespace) -> None:
    bundle, output = args.bundle.resolve(), args.output.resolve()
    require(not output.exists() and output != ROOT
            and (not output.is_relative_to(ROOT) or output.is_relative_to(ROOT / "artifacts")), "choose a new artifact directory")
    input_digest = experiment.digest(bundle / "manifest.json")
    manifest = experiment.read_json(bundle / "manifest.json")
    require(manifest["status"] == "complete" and manifest["schema_version"] == 1, "incomplete input bundle")
    require(manifest["split"] != "test", "do not use untouched test seeds for exploratory development")
    require(1 <= args.late_cycles <= manifest["cycles"], "invalid late-cycle window")
    for name in manifest["artifacts"]:
        verified(bundle, manifest, name)
    sources = experiment.source_files()
    record = {"schema_version": 1, "kind": "garden-establishment", "status": "running",
              "input_manifest_sha256": input_digest, "source_sha256": sources,
              "late_cycles": args.late_cycles, "notes": NOTES,
              "node_capacity": manifest["environment"].get("node_capacity", 256)}
    output.mkdir(parents=True, exist_ok=False)
    experiment.write_json(output / "started.json", record)
    try:
        for name in ("input", "models", "bin", "tools", "traces", "analyses"):
            (output / name).mkdir()
        experiment.snapshot_sources(output, sources)
        shutil.copy2(bundle / "manifest.json", output / "input/manifest.json")
        require(experiment.digest(output / "input/manifest.json") == input_digest, "input manifest changed")
        inspector_sha = experiment.digest(args.inspector)
        shutil.copy2(args.inspector, output / "bin/garden-inspect")
        require(experiment.digest(output / "bin/garden-inspect") == inspector_sha, "inspector changed")
        for name in ("garden_establishment.py", "garden_experiments.py", "garden_resources.py"):
            shutil.copy2(Path(__file__).with_name(name), output / "tools" / name)
        roles = list(manifest["roles"].values())
        if not any(role["policy"] == "adaptive" for role in roles):
            roles.append({"job": "candidate", "policy": "adaptive"})
        data = {}
        for job in sorted({role["job"] for role in roles}):
            for name in (f"reports/{job}.json", f"timelines/{job}.jsonl.gz"):
                destination = output / "input" / Path(name).name
                shutil.copy2(verified(bundle, manifest, name), destination)
                require(experiment.digest(destination) == manifest["artifacts"][name], "input changed while freezing")
            model = manifest["models"].get(job)
            if model:
                shutil.copy2(verified(bundle, manifest, model["path"]), output / model["path"])
                require(experiment.digest(output / model["path"]) == model["sha256"], "model identity changed")
            report = experiment.read_json(output / f"input/{job}.json")
            experiment.validate_report(report, manifest["seeds"], manifest["cycles"]*experiment.CYCLE_TICKS,
                                       model, manifest.get("candidate_probe") if job == "candidate" else None,
                                       manifest["environment"])
            data[job] = experiment.load_timelines(output / f"input/{job}.jsonl.gz", report)
        cases = []
        for role in roles:
            job, policy = role["job"], role["policy"]
            require(policy in experiment.MODEL_POLICIES | {"adaptive", "baseline", "neural-reference"}, "unknown policy")
            model = manifest["models"][job]["path"] if policy in experiment.MODEL_POLICIES else "-"
            for scenario in sorted(experiment.SCENARIOS):
                for seed in manifest["seeds"]:
                    reference = data[job][(scenario, policy, seed)]
                    case_id = f"{len(cases)+1:02d}"
                    command = ["bin/garden-inspect", model, scenario, policy, "0x"+seed,
                               "--seed-sites", "--ticks", str(reference[-1]["tick"])]
                    packed = output / f"traces/{case_id}.jsonl.gz"
                    with tempfile.TemporaryDirectory(prefix="garden-sites-") as temporary:
                        raw = Path(temporary) / "trace.jsonl"
                        experiment.command_run(command, raw, output, args.timeout)
                        experiment.compress(raw, packed)
                    analysis = analyze(packed, reference, args.late_cycles, record["node_capacity"])
                    analysis_path = f"analyses/{case_id}.json"
                    experiment.write_json(output / analysis_path, analysis)
                    case = {"id": case_id, "scenario": scenario, "policy": policy, "seed": seed,
                            "job": job, "command": command, "analysis": analysis,
                            "analysis_path": analysis_path, "trace_sha256": experiment.digest(packed)}
                    cases.append(case)
                    print(f"{case_id}: {scenario}/{policy}/{seed}: {len(analysis['seeds'])} seeds reconciled; "
                          f"{analysis['checkpoints_verified']} hashes matched", flush=True)
        result = {"schema_version": 1, "aggregate": aggregate(cases), "notes": NOTES, "cases": cases}
        with (output / "index.md").open("x") as stream:
            stream.write(markdown(result))
        for case in cases:
            case.pop("analysis")
        experiment.write_json(output / "summary.json", result)
        require(experiment.source_files() == sources, "source changed during census")
        record["status"] = "complete"
        record["artifacts"] = {str(p.relative_to(output)): experiment.digest(p)
                               for p in sorted(output.rglob("*")) if p.is_file()}
        experiment.write_json(output / "manifest.json", record)
        print(f"Complete: {output / 'index.md'}")
    except Exception as error:
        experiment.write_json(output / "failure.json", {"status": "failed", "error": str(error)})
        raise


def verify(output: Path, case_id: str, timeout: int) -> None:
    manifest = experiment.read_json(output / "manifest.json")
    require(manifest["status"] == "complete" and manifest["kind"] == "garden-establishment", "incomplete census")
    for name in manifest["artifacts"]:
        verified(output, manifest, name)
    cases = experiment.read_json(output / "summary.json")["cases"]
    selected = [c for c in cases if case_id == "all" or c["id"] == case_id]
    require(bool(selected), "unknown case")
    for case in selected:
        report = experiment.read_json(output / f"input/{case['job']}.json")
        timeline = experiment.load_timelines(output / f"input/{case['job']}.jsonl.gz", report)
        with tempfile.TemporaryDirectory(prefix="garden-sites-verify-") as temporary:
            raw, packed = Path(temporary) / "trace", Path(temporary) / "trace.gz"
            experiment.command_run(case["command"], raw, output, timeout)
            experiment.compress(raw, packed)
            require(experiment.digest(packed) == case["trace_sha256"], "frozen trace changed")
            actual = analyze(packed, timeline[(case["scenario"], case["policy"], case["seed"])],
                             manifest["late_cycles"], manifest.get("node_capacity", 256))
            require(actual == experiment.read_json(output / case["analysis_path"]), "reanalysis changed")
    print(f"PASS: {len(selected)} frozen seed censuses and analyses reproduced exactly")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--verify", type=Path)
    parser.add_argument("--case", default="all")
    parser.add_argument("--late-cycles", type=int, default=8)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--inspector", type=Path, default=ROOT / "build-host/toy-factory-garden-inspect")
    args = parser.parse_args()
    if args.timeout <= 0 or (args.verify and (args.bundle or args.output)) or (
            not args.verify and (not args.bundle or not args.output)):
        parser.error("choose --verify, or --bundle plus --output; timeout must be positive")
    try:
        verify(args.verify.resolve(), args.case, args.timeout) if args.verify else collect(args)
    except (OSError, RuntimeError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
        print(f"Garden establishment audit failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
