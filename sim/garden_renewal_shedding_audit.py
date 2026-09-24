#!/usr/bin/env python3
"""Read-only living-leaf storage bounds; never infer topology or delete nodes."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
from pathlib import Path
import tarfile

import garden_renewal_full_pool as parent
from garden_node_audit import ownership

experiment, gap, require = parent.experiment, parent.gap, parent.require
RULE = "garden-renewal-shedding-audit-v1"
PROTOCOL = "benchmarks/garden-longevity/renewal-shedding-audit-protocol.md"
BASELINE_SHA = "c35c3ab8ec8479312e6bf2b14a9a78867a536b72693a5ce492cc6d64bd03a97a"
PORTABLE = "benchmarks/garden-longevity/renewal-full-pool-summary.json"
PORTABLE_SHA = "4a99f3776ba5ac5fae4bdd45ac60f5ca8e5109224c9035c07dcc0ad28621c873"
AFTER, LATE, STOP, DAY, STEP = parent.AFTER, parent.LATE, parent.STOP, parent.DAY, 15
REGISTRATION = ('\nadd_test(NAME garden-renewal-shedding-audit-unit\n'
                '\tCOMMAND ${Python3_EXECUTABLE} -W error\n'
                '\t\t${CMAKE_CURRENT_LIST_DIR}/test_garden_renewal_shedding_audit.py)\n')
REGISTRATION_ANCHOR = '\nadd_test(NAME garden-root-bootstrap-audit COMMAND ${Python3_EXECUTABLE}'


def inventory(p):
    for name in ("id", "nodes", "roots", "leaves", "active_leaves", "tips", "flowers", "spent_flowers"):
        require(type(p[name]) is int and p[name] >= 0, "noninteger/negative plant inventory")
    require(p["id"] > 0 and type(p["dead"]) is bool and 0 < p["nodes"] <= 512 and
            0 <= p["roots"] < p["nodes"] and
            0 <= p["active_leaves"] <= p["leaves"] <= p["nodes"]-p["roots"] and
            p["tips"] <= p["nodes"] and p["spent_flowers"] <= p["flowers"] <= p["nodes"]-p["roots"],
            "invalid plant inventory")
    conditions = p["leaf"]["conditions"]
    require(isinstance(conditions, list) and len(conditions) == p["leaves"] and
            all(type(c) is int and 0 <= c <= 255 for c in conditions), "invalid condition inventory")
    for name in ("renewals", "restored", "worn"):
        require(type(p["leaf"][name]) is int and p["leaf"][name] >= 0, "invalid leaf accounting")
    return conditions


def leaf_transition(old, p, tick):
    """Leaf ordinals are stable only in these append-only, unpruned histories."""
    conditions = inventory(p)
    if old is None:
        require(not p["dead"] and all(c == 255 for c in conditions) and
                all(p["leaf"][k] == 0 for k in ("renewals", "restored", "worn")),
                "invalid initial/newborn leaves")
        return {"checked_ordinals": 0, "renewed_ordinals": []}
    before = inventory(old)
    require(p["id"] == old["id"] and p["nodes"]-old["nodes"] in (0, 1) and
            0 <= len(conditions)-len(before) <= p["nodes"]-old["nodes"] and
            all(c == 255 for c in conditions[len(before):]), "leaf order/allocation changed")
    if old["dead"]:
        require(p["dead"] and p["nodes"] == old["nodes"] and p["leaf"] == old["leaf"],
                "dead leaf history changed")
        return {"checked_ordinals": len(before), "renewed_ordinals": []}
    worn = int(tick % 60 == 0)
    expected = [max(0, c-worn) for c in before]
    renewed = [i for i, (a, b) in enumerate(zip(expected, conditions)) if a != b]
    require(len(renewed) <= 1 and all(conditions[i] == 255 for i in renewed) and
            (not renewed or (not p["dead"] and renewed[0] == (tick//STEP+p["id"]) % len(before))),
            "unexplained/reordered leaf renewal")
    for name, delta in (("renewals", len(renewed)), ("restored", sum(255-expected[i] for i in renewed)),
                        ("worn", worn*sum(c > 0 for c in before))):
        require(p["leaf"][name]-old["leaf"][name] == delta, "leaf ordinal accounting differs: "+name)
    return {"checked_ordinals": len(before), "renewed_ordinals": renewed}


def upper_savings(p, removed):
    """Hypothetical same-census upkeep, not a valid deletion or paid saving."""
    require(type(removed) is int and 0 <= removed <= p["leaf"]["conditions"].count(0),
            "removal bound exceeds zero-condition leaves")
    shoots = p["nodes"]-p["roots"]
    require(removed < p["nodes"] and removed <= shoots, "bound removes whole owner")
    return {"energy": (p["nodes"]+7)//8-(p["nodes"]-removed+7)//8,
            "water": (shoots+7)//8-(shoots-removed+7)//8}


def checkpoint(row, starts):
    owned = ownership(row, 512)
    plants = []
    for p in row["plants"]:
        conditions = inventory(p)
        if p["dead"]:
            continue
        zero = conditions.count(0)
        require({i for i, c in enumerate(conditions) if c == 0} ==
                {i for identity, i in starts if identity == p["id"]}, "zero-spell inventory differs")
        persistent = sum(c == 0 and row["tick"]-starts[p["id"], i] >= DAY
                         for i, c in enumerate(conditions))
        plants.append({"id": p["id"], "nodes": p["nodes"], "roots": p["roots"], "tips": p["tips"],
            "leaves": p["leaves"], "mature_leaves": p["active_leaves"], "flowers": p["flowers"],
            "zero": zero, "day_zero": persistent,
            "zero_savings_upper": upper_savings(p, zero), "day_zero_savings_upper": upper_savings(p, persistent)})
    value = {**{k: owned[k] for k in ("free_nodes", "live_nodes", "dead_nodes", "live_roots", "live_shoots")},
             "tick": row["tick"], "hash": row["hash"], "plants": plants,
             "safe_removals_lower": 0, "safe_removals_exact": None}
    for group in ("zero", "day_zero"):
        count = sum(p[group] for p in plants)
        value[group] = count
        value[group+"_headroom_upper"] = owned["free_nodes"]+count
        value[group+"_savings_upper"] = {k: sum(p[group+"_savings_upper"][k] for p in plants)
                                        for k in ("energy", "water")}
    return value


def window_add(window, value):
    counts, histogram = window["counts"], window["zero_histogram"]
    free = value["free_nodes"]
    counts.update(checkpoints=1, full=free == 0, seed_node_gate=free < 4,
                  live_node_samples=value["live_nodes"], dead_node_samples=value["dead_nodes"],
                  live_root_samples=value["live_roots"], live_shoot_samples=value["live_shoots"])
    histogram[str(value["zero"])] += 1
    for group in ("zero", "day_zero"):
        counts[group+"_node_samples"] += value[group]
        counts[group+"_present"] += value[group] > 0
        counts[group+"_seed_gate_relief_upper"] += free < 4 <= value[group+"_headroom_upper"]
        for resource, amount in value[group+"_savings_upper"].items():
            counts[group+"_"+resource+"_upkeep_saving_upper_samples"] += amount


def removal_boundary(p, record, previous, tick, exported):
    require(tick == previous["tick"]+STEP, "nonconsecutive removal")
    if p["dead"]:
        return tick, tick-STEP, "owner_death"
    # Canonical census keeps the pre-export row; absence is seen one step later.
    event = exported.get("event", {})
    require(event.get("id") == p["id"] and event.get("tick") == previous["tick"] and
            record.get("removal_tick") == previous["tick"] and
            event.get("before_hash") == previous["hash"], "unexplained living owner removal")
    return event["tick"], previous["tick"], "manual_export"


def analyze_rows(rows, saved, arm):
    previous, starts, episodes, last = None, {}, [], -STEP
    checked, renewals = 0, 0
    windows = {name: {"counts": Counter(), "zero_histogram": Counter()} for name in ("after", "late", "full_after")}
    snapshots, per_plant = {}, defaultdict(Counter)
    records = {p["id"]: p for p in saved["lineages"]}

    def close(key, tick, reason, last_zero_tick=None):
        start = starts.pop(key)
        last_zero_tick = tick-STEP if last_zero_tick is None else last_zero_tick
        episodes.append({"id": key[0], "leaf_ordinal": key[1], "first_tick": start,
                         "last_zero_tick": last_zero_tick, "span_ticks": last_zero_tick-start,
                         "exit_tick": None if reason == "endpoint" else tick, "exit": reason})

    for row in rows:
        tick = row["tick"]
        require(row["type"] == "world" and type(tick) is int and tick == last+STEP and tick <= STOP,
                "missing/reordered shedding census")
        parent.check_rule(row, arm)
        ownership(row, 512)
        current = {p["id"]: p for p in row["plants"]}
        before = {} if previous is None else {p["id"]: p for p in previous["plants"]}
        if tick > AFTER:
            parent.ownership.ledger(previous, row)
        for identity, p in before.items():
            if identity in current:
                continue
            exit_tick, last_zero, reason = removal_boundary(p, records[identity], previous, tick,
                                                          saved.get("export", {}))
            for key in [key for key in starts if key[0] == identity]:
                close(key, exit_tick, reason, last_zero)
        for identity, p in current.items():
            old = before.get(identity)
            require(identity in records and (old is not None or records[identity]["birth_tick"] == tick),
                    "unrecorded/reused leaf owner")
            transition = leaf_transition(old, p, tick)
            checked += transition["checked_ordinals"]
            renewals += len(transition["renewed_ordinals"])
            if p["dead"]:
                for key in [key for key in starts if key[0] == identity]:
                    close(key, tick, "owner_death")
                continue
            for ordinal, condition in enumerate(p["leaf"]["conditions"]):
                key = identity, ordinal
                if condition == 0:
                    starts.setdefault(key, tick)
                elif key in starts:
                    require(ordinal in transition["renewed_ordinals"], "zero leaf recovered without renewal")
                    close(key, tick, "renewal")
        value = checkpoint(row, starts)
        if tick in (AFTER, STOP):
            snapshots["boundary" if tick == AFTER else "endpoint"] = value
        if tick > AFTER:
            window_add(windows["after"], value)
            if tick > LATE:
                window_add(windows["late"], value)
            if value["free_nodes"] == 0:
                window_add(windows["full_after"], value)
                snapshots.setdefault("first_full", value)
                if "peak_zero_full" not in snapshots or value["zero"] > snapshots["peak_zero_full"]["zero"]:
                    snapshots["peak_zero_full"] = value
            for p in value["plants"]:
                counts = per_plant[str(p["id"])]
                counts.update(live_checkpoints=1, full_checkpoints=value["free_nodes"] == 0,
                              zero_node_samples=p["zero"], day_zero_node_samples=p["day_zero"])
                counts["peak_zero"] = max(counts["peak_zero"], p["zero"])
                counts["peak_day_zero"] = max(counts["peak_day_zero"], p["day_zero"])
        previous, last = row, tick
    require(last == STOP and "boundary" in snapshots, "truncated shedding trace")
    for key in list(starts):
        close(key, STOP+STEP, "endpoint")
    selected = [e for e in episodes if e["last_zero_tick"] > AFTER]
    totals = Counter(episodes=len(selected), distinct_leaves=len({(e["id"], e["leaf_ordinal"]) for e in selected}),
                     full_day_episodes=sum(e["span_ticks"] >= DAY for e in selected))
    totals.update(e["exit"] for e in selected)
    totals.update({k: 0 for k in ("renewal", "owner_death", "manual_export", "endpoint")})
    return {"windows": windows, "snapshots": snapshots, "per_plant": dict(per_plant),
            "zero_spells": {"counts": totals, "episodes": selected},
            "checked_leaf_ordinal_transitions": checked, "checked_renewals": renewals}


def analyze(root, saved):
    return {"rule": RULE, "parent_manifest_sha256": BASELINE_SHA, "parent_portable_sha256": PORTABLE_SHA,
            "window": {"after": AFTER, "late": LATE, "stop": STOP, "step": STEP, "day": DAY},
            "new_native_calls": 0,
            "cases": {arm: analyze_rows(gap.read_trace(root/f"traces/{arm}.worlds.jsonl.gz"),
                                        saved["cases"][arm], arm) for arm in parent.ARMS},
            "limits": ["Zero condition is not a terminal/topologically removable node or permanent loss.",
                       "active_leaves denotes maturity, not positive condition or productive light.",
                       "Bounds concern only zero-condition leaf nodes, not all forms of unproductive structure.",
                       "Safe removable count is unknown with lower bound zero; topology and retained roles are absent.",
                       "Upkeep bounds are same-census price differences, not paid savings or survival forecasts.",
                       "Headroom is post-step and node-only, not an earlier germination rejection or guaranteed birth.",
                       "Continuous zero spans are observed post-step states; death endpoints are excluded.",
                       "No pruning, policy change, new native execution or ecological qualification."]}


def analysis_sources():
    paths = sorted((experiment.ROOT/"sim").glob("*.py"))+[experiment.ROOT/PROTOCOL, experiment.ROOT/"sim/CMakeLists.txt"]
    return {str(p.relative_to(experiment.ROOT)): experiment.digest(p) for p in paths}


def check_build_registration(original, current, sha):
    anchor = REGISTRATION_ANCHOR.encode()
    require(hashlib.sha256(original).hexdigest() == sha and original.count(anchor) == 1 and
            current == original.replace(anchor, REGISTRATION.encode()+anchor), "unexpected historical CMake change")


def check_parent(root):
    gap.parent.shadow.check_frozen(root, BASELINE_SHA)
    require(experiment.digest(experiment.ROOT/PORTABLE) == PORTABLE_SHA, "portable parent changed")
    with tarfile.open(root/"source.tar.gz") as archive:
        original = archive.extractfile("sim/CMakeLists.txt").read()
    for name, sha in experiment.read_json(root/"analysis-sources.json").items():
        if name == "sim/CMakeLists.txt":
            check_build_registration(original, (experiment.ROOT/name).read_bytes(), sha)
        else:
            require(experiment.digest(experiment.ROOT/name) == sha, "historical dependency changed: "+name)
    native = parent.native.native_hashes(root/"source.tar.gz")
    current_native = {n: sha for n, sha in experiment.source_files().items() if n.endswith((".c", ".h"))}
    require(current_native == native, "native source changed")
    capture = parent.check_capture(root)
    require(experiment.read_json(root/"timings.json")["calls"] == capture["calls"], "capture timings changed")
    saved = experiment.read_json(root/"results.json")
    require(saved == parent.analyze(root), "historical analysis differs")
    require(experiment.read_json(experiment.ROOT/PORTABLE) == {**saved, "manifest_sha256": BASELINE_SHA,
            "full_results_sha256": experiment.digest(root/"results.json"),
            "timing": experiment.read_json(root/"timings.json")}, "portable parent differs")
    prefix = experiment.ROOT/PORTABLE.removesuffix("-summary.json")
    require(experiment.digest(prefix.with_suffix(".png")) == experiment.digest(root/"contact-sheet.png"), "overview changed")
    for frame in saved["frames"]:
        require(experiment.digest(prefix.with_name(prefix.name+"-frames")/(frame["id"]+".png")) ==
                experiment.digest(root/frame["png"]), "parent frame changed")
    return saved, native


def verify(root):
    sources = analysis_sources()
    saved, native = check_parent(root)
    result = analyze(root, saved)
    require(result == analyze(root, saved), "repeated shedding audit differs")
    require(sources == analysis_sources() and all(experiment.digest(experiment.ROOT/n) == sha for n, sha in native.items()),
            "analysis/native source changed during audit")
    gap.parent.shadow.check_frozen(root, BASELINE_SHA)
    require(experiment.digest(experiment.ROOT/PORTABLE) == PORTABLE_SHA, "parent summary changed during audit")
    return {**result, "analysis_sources": sources, "native_sources": native}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, default=experiment.ROOT/"artifacts/garden-renewal-full-pool-v1")
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--output", type=Path)
    target.add_argument("--check", type=Path)
    args = parser.parse_args()
    root = args.baseline.resolve()
    if args.output:
        require(not args.output.exists() and not args.output.resolve().is_relative_to(root), "choose fresh output outside parent")
    result = verify(root)
    if args.output:
        experiment.write_json(args.output, result)
    else:
        require(experiment.read_json(args.check) == result, "portable shedding audit differs")
    print("Verified shedding feasibility audit; zero new native research calls", flush=True)


if __name__ == "__main__":
    main()
