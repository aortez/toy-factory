#!/usr/bin/env python3
"""Audit node ownership and whole-plant reclamation using frozen, unchanged inspectors."""

import argparse
from collections import Counter
import gzip
import json
from pathlib import Path
import shutil
import statistics
import subprocess
import sys
import tempfile

import garden_establishment as establishment
import garden_experiments as experiment
import garden_tip_audit as tips
from garden_resources import require

CAPACITY = 256
SEED_NODES = 4
ECOLOGY_TICKS = 15
NOTES = [
    "Node ownership is disjoint: live roots + live shoots + dead roots + dead shoots + free = declared capacity.",
    "Leaves, flowers and tips are flags on nodes, not additional allocated objects.",
    "Window exposure uses post-step state held until the next ecology step; endpoint is excluded.",
    "Remaining mature-seed blockers are overlapping post-step observations, not independent failure probabilities.",
    "Dead-reclaimable node-only sites hypothetically free storage only; no plant is removed or seed relocated.",
    "Death-to-removal delays are exact ecology-step observations; unreclaimed deaths are right-censored.",
    "No ecology, model, policy, allocation capacity or authoritative state is changed.",
]


def ownership(row: dict, capacity: int = CAPACITY) -> dict:
    plants = row["plants"]
    require(capacity in (256, 512) and row.get("node_capacity", 256) == capacity,
            "wrong node census capacity")
    require(0 <= row["nodes"] <= capacity and len(plants) <= 8, "invalid capacities")
    require(len({p["id"] for p in plants}) == len(plants), "duplicate plant identity")
    require(sum(p["nodes"] for p in plants) == row["nodes"], "unowned node storage")
    require(sum(not p["dead"] for p in plants) == row["living"], "wrong living count")
    values = Counter()
    values["free_nodes"] = capacity - row["nodes"]
    for plant in plants:
        require(plant["id"] > 0 and type(plant["dead"]) is bool, "invalid plant identity/state")
        require(0 < plant["nodes"] <= capacity and 0 <= plant["roots"] <= plant["nodes"],
                "invalid root/node counts")
        require(len(plant["root_cells"]) == plant["roots"], "root list/count mismatch")
        require(0 <= plant["active_leaves"] <= plant["leaves"] <= plant["nodes"] - plant["roots"]
                and 0 <= plant["tips"] <= plant["nodes"], "invalid foliage/tip counts")
        prefix = "dead" if plant["dead"] else "live"
        values[prefix+"_plants"] += 1
        values[prefix+"_roots"] += plant["roots"]
        values[prefix+"_shoots"] += plant["nodes"] - plant["roots"]
        if not plant["dead"]:
            values["live_tips"] += plant["tips"]
            values["live_active_leaves"] += plant["active_leaves"]
            values["live_tipless_plants"] += plant["tips"] == 0
    # Stable zero fields matter for aggregation and wholly extinct worlds.
    for prefix in ("live", "dead"):
        for suffix in ("plants", "roots", "shoots"):
            values[prefix+"_"+suffix] += 0
        values[prefix+"_nodes"] = values[prefix+"_roots"] + values[prefix+"_shoots"]
    for name in ("live_tips", "live_active_leaves", "live_tipless_plants"):
        values[name] += 0
    values["living_world"] = int(row["living"] > 0)
    values["node_full"] = int(row["nodes"] == capacity)
    values["seed_node_gate"] = int(values["free_nodes"] < SEED_NODES)
    values["seed_node_gate_after_dead_reclaim"] = int(values["live_nodes"] > capacity-SEED_NODES)
    values["full_with_live_tips"] = int(values["node_full"] and values["live_tips"] > 0)
    values["plant_full"] = int(len(plants) == 8)
    values["live_plant_full"] = int(values["live_plants"] == 8)
    values["dead_present"] = int(values["dead_plants"] > 0)
    values["mature_seed_observations"] = 0
    values["node_only_seed_observations"] = 0
    values["node_only_dead_reclaimable_observations"] = 0
    for seed in row["seeds"]:
        blockers = seed["blockers"]
        require(0 <= blockers < 64, "invalid seed blockers")
        values["mature_seed_observations"] += not (blockers & 1)
        if blockers == 16:
            values["node_only_seed_observations"] += 1
            values["node_only_dead_reclaimable_observations"] += (
                values["free_nodes"] + values["dead_nodes"] >= SEED_NODES)
    return dict(values)


def analyze(path: Path, reference: list[dict], late_cycles: int, capacity: int = CAPACITY,
            include_tips: bool = False) -> dict:
    end = reference[-1]["tick"]
    start = end - late_cycles * experiment.CYCLE_TICKS
    require(end % ECOLOGY_TICKS == 0 and 0 <= start < end, "invalid late window")
    expected = {r["tick"]: r for r in reference}
    require(len(expected) == len(reference), "duplicate reference checkpoint")
    windows = {name: Counter() for name in ("whole", "late")}
    previous = None
    previous_values = None
    seen, deaths, events = set(), {}, []
    checked = allocated = reclaimed = 0
    with gzip.open(path, "rt") as stream:
        for line in stream:
            row = json.loads(line)
            if include_tips and row["type"] == "bid":
                continue
            tick = row["tick"]
            require(row["type"] == "world" and tick == (0 if previous is None else previous["tick"]+15)
                    and tick <= end, "missing/reordered node census tick")
            values = ownership(row, capacity)
            if tick in expected:
                ref = expected[tick]
                for name in ("hash", "nodes", "living", "births", "deaths", "sun_phase"):
                    require(row[name] == ref[name], f"reference mismatch: {tick} {name}")
                require(len(row["seeds"]) == ref["seed_bank"]
                        and len(row["plants"]) == ref["plant_slots"], "reference slot mismatch")
                checked += 1
            plants = {p["id"]: p for p in row["plants"]}
            if previous is None:
                require(not any(p["dead"] for p in plants.values()) and row["deaths"] == 0
                        and row["births"] == 0, "census must begin with living founders")
                initial_nodes = row["nodes"]
                seen.update(plants)
            else:
                # All world changes occur on this ecology grid in these unassisted runs.
                for name in ("whole", "late"):
                    if name == "whole" or previous["tick"] >= start:
                        windows[name]["steps"] += 1
                        windows[name].update(previous_values)
                prior = {p["id"]: p for p in previous["plants"]}
                new = plants.keys() - prior.keys()
                require(not new & seen, "reused lineage identity")
                require(row["births"] - previous["births"] == len(new), "unreconciled births")
                seen.update(new)
                newly_dead = 0
                added = removed = 0
                for identity, plant in plants.items():
                    old = prior.get(identity)
                    require(old is not None or not plant["dead"], "newborn already dead")
                    if old is not None:
                        require(not old["dead"] or plant["dead"], "dead plant revived")
                        require(plant["nodes"] >= old["nodes"] and plant["roots"] >= old["roots"],
                                "tissue disappeared before whole-plant reclamation")
                        require(plant["nodes"]-plant["roots"] >= old["nodes"]-old["roots"],
                                "shoot tissue disappeared before reclamation")
                        require(all(plant[k] == old[k] for k in ("parent", "species", "generation", "column")),
                                "lineage identity changed")
                        if old["dead"]:
                            require(plant["nodes"] == old["nodes"] and plant["roots"] == old["roots"],
                                    "dead tissue allocation changed before reclamation")
                        if plant["dead"] and not old["dead"]:
                            deaths[identity] = {"id": identity, "death_tick": tick,
                                                "nodes": plant["nodes"], "roots": plant["roots"]}
                            newly_dead += 1
                    added += plant["nodes"] - (old["nodes"] if old else 0)
                require(row["deaths"] - previous["deaths"] == newly_dead, "unreconciled deaths")
                for identity in prior.keys() - plants.keys():
                    require(prior[identity]["dead"] and identity in deaths, "living plant disappeared")
                    event = deaths.pop(identity)
                    event.update(reclaim_tick=tick, delay_steps=(tick-event["death_tick"])//15)
                    events.append(event)
                    removed += event["nodes"]
                require(row["nodes"] == previous["nodes"] + added - removed, "node ledger mismatch")
                allocated += added
                reclaimed += removed
            previous, previous_values = row, values
    require(previous is not None and previous["tick"] == end and checked == len(expected),
            "truncated or mismatched node census")
    require(initial_nodes + allocated - reclaimed == previous["nodes"], "final ledger mismatch")
    require(previous["deaths"] == len(events)+len(deaths), "unaccounted terminal deaths")
    result = {"checkpoints_verified": checked, "end_tick": end, "late_start_tick": start,
            "initial_nodes": initial_nodes, "allocated_nodes": allocated, "reclaimed_nodes": reclaimed,
            "windows": windows, "final": previous_values, "final_plants": previous["plants"],
            "reclamations": events, "pending_reclamations": list(deaths.values())}
    if include_tips:
        result["tips"] = tips.analyze(path, end, start, capacity)
    return result


def capture(command: list[str], destination: Path, cwd: Path, timeout: int, keep_bids: bool = False) -> None:
    # Reuse the frozen inspector; discard bid logs, not world states. Bound raw
    # scratch storage to one trial, and preserve original world-row bytes.
    with tempfile.TemporaryDirectory(prefix="garden-node-census-") as temporary:
        raw = Path(temporary) / "trace.jsonl"
        experiment.command_run(command, raw, cwd, timeout)
        with raw.open("rb") as source, destination.open("xb") as target:
            with gzip.GzipFile(fileobj=target, filename="", mode="wb", mtime=0) as packed:
                for line in source:
                    kind = json.loads(line)["type"]
                    require(kind in ("world", "bid"), "unexpected inspector record")
                    if kind == "world" or keep_bids:
                        packed.write(line)


def aggregate(cases: list[dict]) -> dict:
    def total(values):
        result = Counter()
        for value in values:
            result.update(value)
        return result

    result = {}
    for policy in sorted({c["policy"] for c in cases}):
        selected = [c["analysis"] for c in cases if c["policy"] == policy]
        windows = {w: total(a["windows"][w] for a in selected)
                   for w in ("whole", "late")}
        delays = [e["delay_steps"] for a in selected for e in a["reclamations"]]
        result[policy] = {"worlds": len(selected), "windows": windows,
                          "final": total(a["final"] for a in selected),
                          "allocated_nodes": sum(a["allocated_nodes"] for a in selected),
                          "reclaimed_nodes": sum(a["reclaimed_nodes"] for a in selected),
                          "reclaimed_plants": len(delays),
                          "pending_reclamations": sum(len(a["pending_reclamations"]) for a in selected),
                          "delay_steps": {"min": min(delays) if delays else None,
                                          "median": statistics.median(delays) if delays else None,
                                          "max": max(delays) if delays else None}}
        if "tips" in selected[0]:
            result[policy]["tips"] = {
                "totals": total(a["tips"]["totals"] for a in selected),
                "windows": {w: total(a["tips"]["windows"][w] for a in selected) for w in ("whole", "late")}}
    return result


def collect(args: argparse.Namespace) -> None:
    bundle, output = args.bundle.resolve(), args.output.resolve()
    require(not output.exists() and output != experiment.ROOT and
            (not output.is_relative_to(experiment.ROOT) or output.is_relative_to(experiment.ROOT / "artifacts")),
            "choose a new artifact directory")
    manifest = experiment.read_json(bundle / "manifest.json")
    require(manifest["status"] == "complete" and manifest["schema_version"] == 1
            and manifest["split"] == "exploratory", "require a completed exploratory bundle")
    require(1 <= args.late_cycles <= manifest["cycles"], "invalid late window")
    experiment.validate_environment(manifest["environment"])
    for name in manifest["artifacts"]:
        establishment.verified(bundle, manifest, name)
    sources = experiment.source_files()
    record = {"schema_version": 1, "kind": "garden-node-audit", "status": "running",
              "input_manifest_sha256": experiment.digest(bundle / "manifest.json"),
              "environment": manifest["environment"], "late_cycles": args.late_cycles,
              "source_sha256": sources, "notes": NOTES}
    if args.tips:
        require(args.inspector is not None and args.inspector.is_file(), "tip audit requires --inspector")
        record["tip_audit_version"] = 1
        record["tip_notes"] = tips.NOTES
        record["inspector_sha256"] = experiment.digest(args.inspector)
    output.mkdir(parents=True)
    experiment.write_json(output / "started.json", record)
    try:
        for name in ("input", "models", "bin", "tools", "traces", "analyses"):
            (output / name).mkdir()
        experiment.snapshot_sources(output, sources)
        shutil.copy2(bundle / "manifest.json", output / "input/manifest.json")
        require(experiment.digest(output / "input/manifest.json") == record["input_manifest_sha256"],
                "input manifest changed")

        def freeze(name, destination):
            shutil.copy2(establishment.verified(bundle, manifest, name), output / destination)
            require(experiment.digest(output / destination) == manifest["artifacts"][name], "input changed")

        if args.tips:
            shutil.copy2(args.inspector, output / "bin/garden-inspect")
            require(experiment.digest(output / "bin/garden-inspect") == record["inspector_sha256"],
                    "inspector changed while freezing")
        else:
            freeze("bin/garden-inspect", "bin/garden-inspect")
        for name in ("garden_node_audit.py", "garden_tip_audit.py", "garden_establishment.py", "garden_experiments.py", "garden_resources.py"):
            shutil.copy2(Path(__file__).with_name(name), output / "tools" / name)
        roles = list(manifest["roles"].values())
        if not any(r["policy"] == "adaptive" for r in roles):
            roles.append({"job": "candidate", "policy": "adaptive"})
        require(len({r["policy"] for r in roles}) == len(roles), "duplicate audit policy")
        data = {}
        for job in sorted({r["job"] for r in roles}):
            for name in (f"reports/{job}.json", f"timelines/{job}.jsonl.gz"):
                freeze(name, "input/"+Path(name).name)
            model = manifest["models"].get(job)
            if model:
                freeze(model["path"], model["path"])
            report = experiment.read_json(output / f"input/{job}.json")
            experiment.validate_report(report, manifest["seeds"], manifest["cycles"]*experiment.CYCLE_TICKS,
                                       model, manifest.get("candidate_probe") if job == "candidate" else None,
                                       manifest["environment"])
            data[job] = experiment.load_timelines(output / f"input/{job}.jsonl.gz", report)
        cases = []
        for role in roles:
            job, policy = role["job"], role["policy"]
            model = manifest["models"][job]["path"] if policy in experiment.MODEL_POLICIES else "-"
            for scenario in sorted(experiment.SCENARIOS):
                for seed in manifest["seeds"]:
                    reference = data[job][scenario, policy, seed]
                    case_id = f"{len(cases)+1:02d}"
                    command = ["bin/garden-inspect", model, scenario, policy, "0x"+seed,
                               "--ecology", "--ticks", str(reference[-1]["tick"])]
                    path = output / f"traces/{case_id}.jsonl.gz"
                    capture(command, path, output, args.timeout, args.tips)
                    analysis = analyze(path, reference, args.late_cycles,
                                       manifest["environment"].get("node_capacity", 256), args.tips)
                    analysis_path = f"analyses/{case_id}.json"
                    experiment.write_json(output / analysis_path, analysis)
                    cases.append({"id": case_id, "scenario": scenario, "policy": policy, "seed": seed,
                                  "job": job, "command": command, "analysis_path": analysis_path,
                                  "trace_sha256": experiment.digest(path), "analysis": analysis})
                    print(f"{case_id}: {scenario}/{policy}/{seed}: {analysis['checkpoints_verified']} hashes; "
                          f"final live/dead/free nodes {analysis['final']['live_nodes']}/"
                          f"{analysis['final']['dead_nodes']}/{analysis['final']['free_nodes']}", flush=True)
        result = {"schema_version": 1, "aggregate": aggregate(cases), "notes": NOTES, "cases": cases}
        for case in cases:
            case.pop("analysis")
        experiment.write_json(output / "summary.json", result)
        require(experiment.source_files() == sources, "source changed during node audit")
        record["status"] = "complete"
        record["artifacts"] = {str(p.relative_to(output)): experiment.digest(p)
                               for p in sorted(output.rglob("*")) if p.is_file()}
        experiment.write_json(output / "manifest.json", record)
        print(f"Complete: {output / 'summary.json'}")
    except Exception as error:
        experiment.write_json(output / "failure.json", {"status": "failed", "error": str(error)})
        raise


def verify(root: Path, case_id: str, timeout: int) -> None:
    manifest = experiment.read_json(root / "manifest.json")
    require(manifest["status"] == "complete" and manifest["kind"] == "garden-node-audit", "incomplete audit")
    for name in manifest["artifacts"]:
        establishment.verified(root, manifest, name)
    cases = experiment.read_json(root / "summary.json")["cases"]
    selected = [c for c in cases if case_id == "all" or c["id"] == case_id]
    require(bool(selected), "unknown case")
    for case in selected:
        report = experiment.read_json(root / f"input/{case['job']}.json")
        timeline = experiment.load_timelines(root / f"input/{case['job']}.jsonl.gz", report)
        with tempfile.TemporaryDirectory(prefix="garden-node-verify-") as temporary:
            path = Path(temporary) / "trace.gz"
            include_tips = manifest.get("tip_audit_version") == 1
            capture(case["command"], path, root, timeout, include_tips)
            require(experiment.digest(path) == case["trace_sha256"], "frozen node census changed")
            actual = analyze(path, timeline[case["scenario"], case["policy"], case["seed"]],
                             manifest["late_cycles"], manifest["environment"].get("node_capacity", 256), include_tips)
            require(actual == experiment.read_json(root / case["analysis_path"]), "node reanalysis changed")
    print(f"PASS: {len(selected)} frozen node censuses and ledgers reproduced exactly")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--verify", type=Path)
    parser.add_argument("--case", default="all")
    parser.add_argument("--late-cycles", type=int, default=8)
    parser.add_argument("--tips", action="store_true", help="Also retain bids and reconcile tip termination")
    parser.add_argument("--inspector", type=Path, help="Explicit current inspector, required only with --tips")
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args()
    if bool(args.inspector) != args.tips or (args.verify and args.tips):
        parser.error("use --tips and --inspector together only for collection")
    if args.timeout <= 0 or (args.verify and (args.bundle or args.output)) or (
            not args.verify and (not args.bundle or not args.output)):
        parser.error("choose --verify, or --bundle plus --output; timeout must be positive")
    try:
        verify(args.verify.resolve(), args.case, args.timeout) if args.verify else collect(args)
    except (OSError, RuntimeError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
        print(f"Garden node audit failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
