#!/usr/bin/env python3
"""Bounded read-only topology capture and conservative shedding feasibility census."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import gzip
import json
from pathlib import Path
import shutil
import tempfile
import time

import garden_renewal_shedding_audit as prior

parent, experiment, require = prior.parent, prior.experiment, prior.require
RULE = "garden-renewal-topology-v1"
PROTOCOL = "benchmarks/garden-longevity/renewal-topology-protocol.md"
AUDIT = "benchmarks/garden-longevity/renewal-shedding-audit-summary.json"
AUDIT_SHA = "59f1d44ff4b9870b8911337b3fc552ad2f254cde404e9475a418e3e6eb58cdc0"
POINTS = (0, 46095, 69120, 72960, 80940, 111000, 184320, 245760)
NONE, TIP, LEAF, FLOWER, PENDING = 65535, 1, 2, 4, 16
REASONS = ("base", "root", "internal", "tip", "branch_pending", "flower", "previous_tip")


def bounded(value, low, high):
    require(type(value) is int and low <= value <= high, "invalid bounded integer")
    return value


def validate(topology, world):
    require(topology["type"] == "topology" and topology["schema_version"] == 1 and
            topology["tick"] == world["tick"] and topology["hash"] == world["hash"],
            "topology does not match adjacent census")
    capacity = bounded(topology["node_capacity"], 256, 512)
    nodes, plants = topology["nodes"], topology["plants"]
    require(len(nodes) == world["nodes"] <= capacity and len(plants) == len(world["plants"]) <= 16,
            "topology inventory differs")
    children, owned, ordinals = Counter(), defaultdict(list), {}
    for i, node in enumerate(nodes):
        require(node["index"] == i, "noncanonical node order")
        owner = bounded(node["owner"], 0, len(plants)-1)
        bounded(node["kind"], 0, 1)
        flags = bounded(node["flags"], 0, 63)
        for key in ("x", "y", "depth", "progress", "children"):
            bounded(node[key], 0, 255)
        if node["condition"] is not None:
            bounded(node["condition"], 0, 255)
            require((flags & LEAF) or node["condition"] == 0, "nonleaf has condition")
        require(not (flags & 32) or flags & FLOWER, "spent nonflower")
        link = bounded(node["parent"], 0, NONE)
        if link != NONE:
            require(link < i and nodes[link]["owner"] == owner, "invalid parent order/ownership")
            children[link] += 1
        owned[owner].append(node)
    identities = set()
    for i, (p, census) in enumerate(zip(plants, world["plants"], strict=True)):
        require(p["index"] == i and p["id"] == census["id"] and p["id"] not in identities and
                p["flags"] == census["flags"], "invalid owner identity/flags")
        identities.add(p["id"])
        base = bounded(p["base"], 0, len(nodes)-1)
        require(nodes[base]["owner"] == i and nodes[base]["parent"] == NONE and
                [n["index"] for n in owned[i] if n["parent"] == NONE] == [base], "invalid base")
        for key in ("last_shoot_tip", "last_root_tip"):
            ref = bounded(p[key], 0, NONE)
            require(ref == NONE or (ref < len(nodes) and nodes[ref]["owner"] == i), "invalid previous tip")
        leaf_nodes = [n for n in owned[i] if n["flags"] & LEAF]
        actual = {"nodes": len(owned[i]), "roots": sum(n["kind"] == 1 for n in owned[i]),
                  "leaves": len(leaf_nodes), "active_leaves": sum(n["progress"] >= 96 for n in leaf_nodes)}
        for key, flag in (("tips", TIP), ("flowers", FLOWER), ("spent_flowers", 32)):
            actual[key] = sum(bool(n["flags"] & flag) for n in owned[i])
        require(all(census[k] == v for k, v in actual.items()), "aggregate node roles differ")
        if "leaf" in census:
            require([n["condition"] for n in leaf_nodes] == census["leaf"]["conditions"], "leaf order differs")
        else:
            require(all(n["condition"] is None for n in owned[i]), "unexpected leaf-maintenance state")
        ordinals.update({n["index"]: (p["id"], ordinal) for ordinal, n in enumerate(leaf_nodes)})
    require(all(n["children"] == children[i] for i, n in enumerate(nodes)), "child count differs from links")
    return children, ordinals


def reasons(node, plant, children):
    flags, index = node["flags"], node["index"]
    return [key for key, value in zip(REASONS, (
        index == plant["base"], node["kind"] == 1, children[index] > 0,
        flags & TIP, flags & PENDING, flags & FLOWER,
        index in (plant["last_shoot_tip"], plant["last_root_tip"])), strict=True) if value]


def census(topology, world, starts):
    children, ordinals = validate(topology, world)
    counts = Counter(dict.fromkeys((*REASONS, "zero", "day_zero", "terminal_zero", "eligible",
                                   "day_eligible", "unprotected_terminal_positive"), 0))
    overlap, eligible, by_owner = Counter(), [], defaultdict(Counter)
    for n in topology["nodes"]:
        p = topology["plants"][n["owner"]]
        if (p["flags"] & 1) or not (n["flags"] & LEAF):
            continue
        why = reasons(n, p, children)
        if n["condition"] != 0:
            counts["unprotected_terminal_positive"] += n["condition"] is not None and not why
            continue
        key = ordinals[n["index"]]
        require(key in starts and starts[key] <= world["tick"], "missing zero history")
        day = int(world["tick"]-starts[key] >= prior.DAY)
        counts.update(why)
        counts.update(zero=1, day_zero=day, terminal_zero=children[n["index"]] == 0)
        overlap["+".join(why) or "eligible"] += 1
        if not why:
            counts.update(eligible=1, day_eligible=day)
            by_owner[p["id"]].update(eligible=1, day_eligible=day)
            eligible.append({"id": key[0], "leaf_ordinal": key[1], "node": n["index"],
                             "parent": n["parent"], "x": n["x"], "y": n["y"],
                             "zero_since": starts[key], "day_zero": day})
    prices = {group: {"energy": 0, "water": 0} for group in ("eligible", "day_eligible")}
    for p in world["plants"]:
        if not p["dead"]:
            for group in prices:
                for resource, difference in prior.upper_savings(p, by_owner[p["id"]][group]).items():
                    prices[group][resource] += difference
    free = topology["node_capacity"]-len(topology["nodes"])
    return {"tick": world["tick"], "hash": world["hash"], "nodes": len(topology["nodes"]),
            "free_nodes": free, "counts": counts, "overlapping_reason_sets": overlap,
            "candidates": eligible, "per_owner": {str(k): v for k, v in by_owner.items()},
            "upkeep_price_reduction_upper": prices,
            "candidate_node_headroom": {g: free+counts[g] for g in prices}}


def history(rows, points):
    """Use consecutive complete censuses, not sparse topology snapshots."""
    starts, selected, previous, last = {}, {}, {}, -15
    for row in rows:
        tick = row["tick"]
        require(row["type"] == "world" and tick == last+15, "missing canonical census")
        current = {p["id"]: p for p in row["plants"]}
        require(len(current) == len(row["plants"]), "duplicate owner")
        for identity, p in current.items():
            prior.leaf_transition(previous.get(identity), p, tick)
        zeros = {(p["id"], i) for p in current.values() if not p["dead"]
                 for i, condition in enumerate(p["leaf"]["conditions"]) if condition == 0}
        starts = {key: starts.get(key, tick) for key in zeros}
        if tick in points:
            selected[tick] = (row, dict(starts))
        previous, last = current, tick
    require(set(selected) == set(points), "missing selected checkpoint")
    return selected


def neutral_trace(captured, baseline, points):
    """Compare every original byte, allowing only adjacent explicit topology records."""
    records, previous, count = [], None, 0
    with gzip.open(captured, "rb") as incoming, gzip.open(baseline, "rb") as original:
        for line in incoming:
            row = json.loads(line)
            if row["type"] == "topology":
                require(previous is not None and previous["type"] == "world", "unattached topology")
                validate(row, previous)
                records.append(row)
                previous = None
            else:
                require(line == original.readline(), "original trace changed with topology capture")
                previous = row
                count += 1
        require(original.read(1) == b"", "truncated original trace")
    require([r["tick"] for r in records] == list(points), "missing/duplicate/unrequested topology")
    return records, count


def analyze(root):
    original = root/"input/control.world.jsonl.gz"
    require(experiment.digest(original) == experiment.digest(root/"traces/off.jsonl.gz"),
            "rebuilt control differs from historical control")
    require(experiment.digest(root/"traces/on.jsonl.gz") == experiment.digest(root/"traces/repeat.jsonl.gz"),
            "topology repeat differs")
    records, count = neutral_trace(root/"traces/on.jsonl.gz", original, POINTS)
    selected = history(prior.gap.read_trace(root/"input/control.worlds.jsonl.gz"), POINTS)
    checkpoints = []
    for topology in records:
        world, starts = selected[topology["tick"]]
        checkpoints.append(census(topology, world, starts))
    return {"rule": RULE, "native_calls": 3, "checkpoints": checkpoints,
            "unchanged_original_records": count, "parent_manifest_sha256": prior.BASELINE_SHA,
            "shedding_audit_sha256": AUDIT_SHA,
            "limits": ["One historical selected world, not generalized ecology qualification.",
                       "Structural eligibility does not establish biological benefit or safe policy choice.",
                       "No pruning, recursive stem contraction, role removal or extra capacity.",
                       "Price/headroom bounds are not actual resource savings or rescued seedlings.",
                       "Zero duration is an observed census interval, not a shedding threshold."]}


def commands():
    command = next(cmd for name, cmd in parent.commands() if name == "traces/control.world.jsonl.gz")
    enabled = [*command, *(s for tick in POINTS for s in ("--topology-at", str(tick)))]
    return [("traces/off.jsonl.gz", command), ("traces/on.jsonl.gz", enabled),
            ("traces/repeat.jsonl.gz", enabled)]


def check_scope(root):
    before = parent.native.native_hashes(root/"input/parent-source.tar.gz")
    after = parent.native.native_hashes(root/"source.tar.gz")
    require(after.keys()-before.keys() == {"sim/garden_topology.c", "sim/garden_topology.h",
                                         "sim/garden_topology_test.c"} and not before.keys()-after.keys() and
            {n for n in before if before[n] != after[n]} == {"sim/garden_inspect.c"}, "native scope changed")
    require(parent.native.cache_settings(root/"input/parent-cache.txt") ==
            parent.native.cache_settings(root/"input/CMakeCache.txt"), "build configuration changed")
    return after


def finish(root):
    require(not (root/"manifest.json").exists(), "bundle already sealed")
    capture = experiment.read_json(root/"capture.json")
    require([(c["artifact"], c["command"]) for c in capture["calls"]] == commands(), "wrong capture inventory")
    for name, sha in capture["artifacts"].items():
        require(experiment.digest(root/name) == sha, "captured artifact changed: "+name)
    check_scope(root)
    result = analyze(root)
    require(result == analyze(root), "repeated analysis differs")
    experiment.write_json(root/"results.json", result)
    paths = sorted(root.rglob("*"))
    experiment.write_json(root/"manifest.json", {"rule": RULE, "artifacts": {
        str(p.relative_to(root)): experiment.digest(p) for p in paths if p.is_file()}})


def collect(baseline, build, output):
    require(not output.exists() and output.is_relative_to(experiment.ROOT/"artifacts") and
            not any(output.is_relative_to(p) for p in (baseline, build)), "choose fresh independent output")
    prior.gap.parent.shadow.check_frozen(baseline, prior.BASELINE_SHA)
    require(experiment.digest(experiment.ROOT/AUDIT) == AUDIT_SHA, "prior audit changed")
    sources = experiment.source_files()
    output.mkdir(parents=True)
    for name in ("input", "bin", "traces", "models"):
        (output/name).mkdir()
    experiment.snapshot_sources(output, sources)
    copies = {"input/parent-manifest.json": "manifest.json", "input/parent-source.tar.gz": "source.tar.gz",
              "input/parent-cache.txt": "input/CMakeCache.txt", "input/control.world.jsonl.gz": "traces/control.world.jsonl.gz",
              "input/control.worlds.jsonl.gz": "traces/control.worlds.jsonl.gz",
              **{f"models/{name}.tgm": f"models/{name}.tgm" for name in ("r2-n", "r2-w")}}
    for destination, name in copies.items():
        shutil.copy2(baseline/name, output/destination)
    for destination, source in (("input/protocol.md", experiment.ROOT/PROTOCOL),
                                ("input/shedding-audit.json", experiment.ROOT/AUDIT),
                                ("input/CMakeCache.txt", build/"CMakeCache.txt"),
                                ("input/build.ninja", build/"build.ninja"),
                                ("bin/inspect", build/"toy-factory-garden-inspect")):
        shutil.copy2(source, output/destination)
    experiment.write_json(output/"started.json", {"sources": sources, "commands": commands(), "copies": copies})
    check_scope(output)
    calls = []
    for target, command in commands():
        start = time.monotonic()
        with tempfile.TemporaryDirectory(prefix="garden-topology-") as temporary:
            raw = Path(temporary)/"trace.jsonl"
            try:
                experiment.command_run(command, raw, output, 180)
            finally:
                if raw.exists():
                    experiment.compress(raw, output/target)
        calls.append({"artifact": target, "command": command, "seconds": time.monotonic()-start})
        if target == "traces/off.jsonl.gz":
            require(experiment.digest(output/target) == experiment.digest(output/"input/control.world.jsonl.gz"),
                    "historical control drift; stop before topology capture")
        print(f"Captured {len(calls)}/3: {target}", flush=True)
    require(experiment.source_files() == sources, "sources changed during capture")
    experiment.write_json(output/"capture.json", {"calls": calls, "artifacts": {
        str(p.relative_to(output)): experiment.digest(p) for p in output.rglob("*") if p.is_file()}})
    finish(output)


def verify(root):
    manifest = experiment.read_json(root/"manifest.json")
    require(manifest["rule"] == RULE, "wrong bundle")
    for name, sha in manifest["artifacts"].items():
        require(experiment.digest(root/name) == sha, "frozen artifact changed: "+name)
    require(experiment.digest(root/"input/parent-manifest.json") == prior.BASELINE_SHA and
            experiment.digest(root/"input/shedding-audit.json") == AUDIT_SHA, "changed parent evidence")
    old = experiment.read_json(root/"input/parent-manifest.json")["artifacts"]
    started = experiment.read_json(root/"started.json")
    for destination, name in started["copies"].items():
        if name != "manifest.json":
            require(experiment.digest(root/destination) == old[name], "changed parent copy")
    native = check_scope(root)
    for name in (PROTOCOL, "sim/garden_renewal_topology.py", "sim/test_garden_renewal_topology.py", "sim/CMakeLists.txt", *native):
        require(experiment.digest(experiment.ROOT/name) == started["sources"][name], "source changed: "+name)
    result = analyze(root)
    require(result == experiment.read_json(root/"results.json"), "saved analysis differs")
    return {**result, "manifest_sha256": experiment.digest(root/"manifest.json")}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, default=experiment.ROOT/"artifacts/garden-renewal-full-pool-v1")
    parser.add_argument("--build", type=Path, default=experiment.ROOT/"artifacts/build-host-full-pool-docker")
    parser.add_argument("--output", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--finish", action="store_true")
    mode.add_argument("--export", type=Path)
    mode.add_argument("--check", type=Path)
    args = parser.parse_args()
    root = args.output.resolve()
    if args.finish:
        finish(root)
    elif args.export or args.check:
        result = verify(root)
        if args.export:
            experiment.write_json(args.export, result)
        else:
            require(result == experiment.read_json(args.check), "portable result differs")
        print("Verified read-only topology census and full-trace neutrality", flush=True)
    else:
        collect(args.baseline.resolve(), args.build.resolve(), root)


if __name__ == "__main__":
    main()
