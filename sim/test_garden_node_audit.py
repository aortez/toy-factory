#!/usr/bin/env python3
"""Check node ledgers, time exposure, reclamation, and immutable frozen replay."""

import argparse
import copy
import gzip
import json
from pathlib import Path
import subprocess
import sys
import tempfile

import garden_node_audit as audit
import garden_experiments as experiment


def plant(identity, nodes, roots, dead=False):
    return {"id": identity, "parent": 0 if identity < 3 else 2, "species": "flower",
            "generation": int(identity >= 3), "column": identity*4,
            "nodes": nodes, "roots": roots, "dead": dead,
            "root_cells": [[0, 0, 0, 0]]*roots, "leaves": 1, "active_leaves": int(not dead),
            "tips": 0 if dead else 1}


def rows_and_reference():
    rows = []
    for tick in range(0, 7681, 15):
        plants = [plant(2, 128, 64)]
        if tick < 735:
            plants.insert(0, plant(1, 128, 64, tick >= 15))
        if tick >= 750:
            plants.append(plant(3, 4, 2))
        rows.append({"type": "world", "tick": tick, "hash": f"{tick:08x}",
                     "nodes": sum(p["nodes"] for p in plants), "plants": plants,
                     "living": sum(not p["dead"] for p in plants),
                     "seeds": [{"blockers": 16}] if tick < 735 else [],
                     "births": int(tick >= 750), "deaths": int(tick >= 15),
                     "sun_phase": (64+tick//15)%256})
    reference = [{**r, "seed_bank": len(r["seeds"]), "plant_slots": len(r["plants"])} for r in rows]
    return rows, reference


def pack(path, rows):
    with gzip.open(path, "wt") as stream:
        for row in rows:
            stream.write(json.dumps(row)+"\n")


def rejects(call):
    try:
        call()
    except RuntimeError:
        return
    raise AssertionError("invalid node census accepted")


def synthetic(root):
    rows, reference = rows_and_reference()
    path = root / "test.gz"
    pack(path, rows)
    result = audit.analyze(path, reference, 1)
    assert result["allocated_nodes"] == 4 and result["reclaimed_nodes"] == 128
    assert result["initial_nodes"] == 256 and result["final"]["live_nodes"] == 132
    assert result["final"]["live_roots"] == result["final"]["live_shoots"] == 66
    assert result["reclamations"] == [{"id": 1, "death_tick": 15, "nodes": 128,
                                        "roots": 64, "reclaim_tick": 735, "delay_steps": 48}]
    whole, late = (result["windows"][w] for w in ("whole", "late"))
    assert whole["steps"] == 512 and late["steps"] == 256
    assert whole["dead_nodes"] == 48*128 and late["dead_nodes"] == 0
    assert whole["node_full"] == 49 and whole["seed_node_gate_after_dead_reclaim"] == 1
    assert whole["node_only_seed_observations"] == 49
    assert whole["node_only_dead_reclaimable_observations"] == 48
    assert late["live_nodes"] == 256*132
    grouped = audit.aggregate([{"policy": "test", "analysis": result}])["test"]
    assert grouped["windows"]["late"]["dead_nodes"] == 0
    assert grouped["delay_steps"] == {"min": 48, "median": 48, "max": 48}
    for mode in ("missing", "hash", "unowned", "roots", "identity", "reuse", "revive", "shrink", "death", "birth"):
        bad = copy.deepcopy(rows)
        if mode == "missing":
            bad.pop()
        elif mode == "hash":
            bad[1]["hash"] = "wrong"
        elif mode == "unowned":
            bad[1]["plants"][0]["nodes"] -= 1
        elif mode == "roots":
            bad[1]["plants"][0]["root_cells"].pop()
        elif mode == "identity":
            bad[1]["plants"][0]["column"] += 1
        elif mode == "reuse":
            bad[50]["plants"][1]["id"] = 1
        elif mode == "revive":
            bad[2]["plants"][0]["dead"] = False
            bad[2]["living"] += 1
        elif mode == "shrink":
            bad[2]["plants"][0]["nodes"] -= 1
            bad[2]["nodes"] -= 1
        elif mode == "death":
            bad[1]["deaths"] = 0
        else:
            bad[50]["births"] = 0
        pack(path, bad)
        rejects(lambda: audit.analyze(path, reference, 1))
    # Death at the endpoint is pending, with zero observed exposure afterwards.
    bad = copy.deepcopy(rows)
    bad[-1]["plants"][0]["dead"] = True
    bad[-1]["living"] -= 1
    bad[-1]["deaths"] += 1
    ref = [{**r, "seed_bank": len(r["seeds"]), "plant_slots": len(r["plants"])} for r in bad]
    pack(path, bad)
    pending = audit.analyze(path, ref, 1)
    assert len(pending["pending_reclamations"]) == 1
    assert pending["windows"]["late"]["dead_nodes"] == 0
    assert pending["final"]["dead_nodes"] == 128
    # Empty worlds retain their full free capacity, without fake reclamations.
    empty = [{**r, "plants": [], "nodes": 0, "living": 0, "seeds": [], "births": 0, "deaths": 0} for r in rows]
    ref = [{**r, "seed_bank": 0, "plant_slots": 0} for r in empty]
    pack(path, empty)
    result = audit.analyze(path, ref, 1)
    assert result["windows"]["late"]["free_nodes"] == 256*256
    assert result["windows"]["late"]["live_nodes"] == 0
    grouped = audit.aggregate([{"policy": "empty", "analysis": result}])["empty"]
    assert grouped["delay_steps"]["median"] is None


def run(command, expected=0):
    result = subprocess.run(list(map(str, command)), capture_output=True, text=True, timeout=120)
    if result.returncode != expected:
        raise RuntimeError(f"{command}: expected {expected}, got {result.returncode}\n{result.stdout}\n{result.stderr}")
    return result.stdout


def integration(args, root):
    bundle = root / "experiment"
    run([sys.executable, experiment.__file__, "--output", bundle, "--cycles", "2", "--trials", "1",
         "--trace-pairs", "1", "--evaluator", args.evaluator, "--inspector", args.inspector])
    before = (bundle / "manifest.json").read_bytes()
    output = root / "nodes"
    command = [sys.executable, audit.__file__, "--bundle", bundle, "--output", output, "--late-cycles", "1"]
    run(command)
    assert before == (bundle / "manifest.json").read_bytes()
    summary = experiment.read_json(output / "summary.json")
    assert len(summary["cases"]) == 4
    assert set(summary["aggregate"]) == {"adaptive", "neural-reference"}
    assert sum(a["reclaimed_plants"] for a in summary["aggregate"].values()) > 0
    run([sys.executable, output / "tools/garden_node_audit.py", "--verify", output])
    tip_output = root / "tips"
    run([*command, "--output", tip_output, "--tips", "--inspector", args.inspector])
    run([sys.executable, tip_output / "tools/garden_node_audit.py", "--verify", tip_output])
    tip_summary = experiment.read_json(tip_output / "summary.json")
    for case in tip_summary["cases"]:
        actual = experiment.read_json(tip_output / case["analysis_path"])
        expected = experiment.read_json(output / case["analysis_path"])
        metrics = actual.pop("tips")
        assert actual == expected, "tip capture changed the original node census"
        assert metrics["totals"]["committed"] > 0 and metrics["totals"]["terminated_tips"] > 0
    assert before == (bundle / "manifest.json").read_bytes()
    for options in (["--tips"], ["--inspector", args.inspector]):
        run([*command, "--output", root / "invalid-options", *options], 2)
        assert not (root / "invalid-options").exists()
    run(command, 1)
    assert not (output / "failure.json").exists()
    run([*command, "--output", root / "bad-window", "--late-cycles", "3"], 1)
    assert not (root / "bad-window").exists()
    (output / "analyses/01.json").write_text("{}")
    run([sys.executable, audit.__file__, "--verify", output], 1)
    manifest = experiment.read_json(bundle / "manifest.json")
    manifest["split"] = "test"
    (bundle / "manifest.json").write_text(json.dumps(manifest))
    run([*command, "--output", root / "test-seeds"], 1)
    assert not (root / "test-seeds").exists()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evaluator", type=Path, required=True)
    parser.add_argument("--inspector", type=Path, required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="garden-node-tests-") as temporary:
        root = Path(temporary)
        synthetic(root)
        integration(args, root)
    print("PASS: node ownership, exposure, reclamation, corrupt/truncated input, frozen replay and input preservation")


if __name__ == "__main__":
    main()
