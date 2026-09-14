#!/usr/bin/env python3
"""Reconcile committed tip changes; inspect causes without modifying any world."""

from collections import Counter
import gzip
import json

from garden_resources import require

NOTES = [
    "Only committed winning bids are counted; ties retain the first bid in trace order.",
    "Termination reason describes the winning observation, not the raw NN output before safety guards.",
    "Depth limit takes precedence over blocked candidates; blockage details retain overlapping flags.",
    "Tipless exposure uses post-step state over [start,end); decisions use (start,end].",
    "Tipless means no growth-policy calls, not dead, dormant, infertile, or no resource processing.",
    "No tissue aging, maintenance action, reactivation, or controller change is implemented.",
]


def termination(bid):
    flags = [candidate["flags"] for candidate in bid["candidates"]]
    in_bounds = [flag for flag in flags if flag & 1]
    available = sum(bool(flag & 2) for flag in flags)
    reason = ("depth_limit" if bid["depth"] >= bid["maximum_depth"] else
              "no_available_candidate" if not available else "policy_finish_available")
    return {"reason": reason, "depth": bid["depth"], "maximum_depth": bid["maximum_depth"],
            "tissue": bid["tissue"], "x": bid["x"], "y": bid["y"],
            "action": bid["action"], "available": available,
            "in_bounds": len(in_bounds), "out_of_bounds": len(flags)-len(in_bounds),
            "own_blocked": sum(bool(flag & 4) for flag in in_bounds),
            "foreign_blocked": sum(bool(flag & 8) for flag in in_bounds)}


def analyze(path, end, late_start, capacity):
    with gzip.open(path, "rt") as stream:
        return analyze_stream(stream, end, late_start, capacity)


def analyze_stream(stream, end, late_start, capacity):
    require(capacity in (256, 512) and 0 <= late_start < end and end % 15 == 0,
            "invalid tip audit horizon/capacity")
    prior, records, pending = {}, {}, {}
    last_tick = -15
    events = []
    windows = {name: Counter() for name in ("whole", "late")}
    totals = Counter()
    for line in stream:
        row = json.loads(line)
        tick = row["tick"]
        if row["type"] == "bid":
            require(row.get("tip_audit_version") == 1 and tick == last_tick+15
                    and tick <= end and 0 <= row["tip_index"] < capacity,
                    "missing/invalid tip observation metadata")
            require(row["tissue"] in (0, 1) and row["action"] in (0, 1, 2)
                    and 0 <= row["depth"] <= 255 and 1 <= row["maximum_depth"] <= 255,
                    "invalid tip decision")
            require(row["action"] == row["original_action"]
                    and row["priority"] == row["original_priority"], "lineage override not allowed")
            flags = [c["flags"] for c in row["candidates"]]
            require(len(flags) == (5 if row["tissue"] == 0 else 3)
                    and all(f in (0, 3, 5, 9, 13) for f in flags), "invalid candidate flags")
            pending.setdefault(row["id"], []).append(row)
            totals["offered_bids"] += 1
            continue
        require(row["type"] == "world" and tick == last_tick+15 and tick <= end
                and row.get("node_capacity", 256) == capacity, "incomplete/wrong tip census")
        current = {p["id"]: p for p in row["plants"]}
        require(len(current) == len(row["plants"]), "duplicate lineage")
        if tick:
            for name, window in windows.items():
                if name == "late" and last_tick < late_start:
                    continue
                window["world_steps"] += 1
                for p in prior.values():
                    if not p["dead"]:
                        window["living_steps"] += 1
                        window["tipless_steps"] += p["tips"] == 0
        for identity, plant in current.items():
            old = prior.get(identity)
            if old is None:
                require(identity not in records and not plant["dead"], "reused/dead newborn")
                records[identity] = {"id": identity, "parent": plant["parent"], "species": plant["species"],
                                     "birth_tick": tick, "tipless_tick": None, "death_tick": None,
                                     "last_decision_tick": None, "last_termination": None,
                                     "seeds_after_tipless": 0}
                totals["initial_tips" if tick == 0 else "newborn_tips"] += 3
            record = records[identity]
            bids = pending.pop(identity, [])
            delta = {key: plant["agent"][key] - (old["agent"][key] if old else 0)
                     for key in ("decisions", "extend", "finish", "wait")}
            require(delta["decisions"] == sum(delta[k] for k in ("extend", "finish", "wait"))
                    == bool(bids) and all(v >= 0 for v in delta.values()), "unreconciled committed bid")
            tips_before = old["tips"] if old else 3
            nodes_before = old["nodes"] if old else 4
            tip_delta, node_delta = plant["tips"]-tips_before, plant["nodes"]-nodes_before
            if plant["dead"]:
                require(not bids and plant["tips"] == 0 and node_delta == 0, "dead plant acted")
                if old is not None and not old["dead"]:
                    totals["death_tips"] += tips_before
                    record["death_tick"] = tick
                continue
            require(old is None or not old["dead"], "dead plant revived")
            if old is not None and old["tips"] == 0:
                require(not bids and tip_delta == 0, "tipless plant acted/reactivated")
                record["seeds_after_tipless"] += plant["reproduction_cooldown"] == 16
            if not bids:
                require(tip_delta == node_delta == 0, "tip/node changed without a decision")
                continue
            require(tick > 0 and tips_before > 0, "decision without a living tip")
            require(len({b["tip_index"] for b in bids}) == len(bids), "duplicate tip bid")
            bid = max(bids, key=lambda b: b["priority"])
            require(all(bid[k] == plant["agent"]["last_"+k]
                        for k in ("priority", "action", "tissue", "x", "y")), "wrong winning bid")
            action = ("wait", "extend", "finish")[bid["action"]]
            require(delta[action] == 1, "winning action/counter disagreement")
            record["last_decision_tick"] = tick
            totals["committed"] += 1
            for name, window in windows.items():
                if name == "whole" or tick > late_start:
                    window["committed"] += 1
                    window[action] += 1
            if action == "wait":
                require(tip_delta == node_delta == 0, "WAIT changed topology")
                totals["waits"] += 1
                continue
            if action == "extend" and node_delta == 1:
                require(tip_delta in (0, 1), "extension lost or invented tips")
                totals["successful_extensions"] += 1
                totals["branch_tips"] += tip_delta
                continue
            require(node_delta == 0 and tip_delta == -1, "termination did not remove exactly one tip")
            event = {"tick": tick, "id": identity, **termination(bid)}
            require(action == "finish" or event["available"] == 0, "unexplained failed extension")
            totals["terminated_tips"] += 1
            totals["failed_extensions"] += action == "extend"
            events.append(event)
            record["last_termination"] = event
            if plant["tips"] == 0:
                require(record["tipless_tick"] is None, "second tipless transition")
                record["tipless_tick"] = tick
        require(not pending, "bid without a plant in post-step world")
        for identity in prior.keys()-current.keys():
            require(prior[identity]["dead"], "living plant disappeared")
        prior, last_tick = current, tick
    require(last_tick == end and not pending, "truncated tip census")
    totals["final_tips"] = sum(p["tips"] for p in prior.values())
    require(totals["initial_tips"] + totals["newborn_tips"] + totals["branch_tips"]
            - totals["terminated_tips"] - totals["death_tips"] == totals["final_tips"], "tip ledger mismatch")
    for key in ("initial_tips", "newborn_tips", "branch_tips", "terminated_tips", "death_tips",
                "offered_bids", "committed", "failed_extensions", "successful_extensions", "waits"):
        totals[key] += 0
    for name, window in windows.items():
        selected = [e for e in events if name == "whole" or e["tick"] > late_start]
        for reason in ("depth_limit", "no_available_candidate", "policy_finish_available"):
            window[reason] = sum(e["reason"] == reason for e in selected)
        for key in ("world_steps", "living_steps", "tipless_steps", "committed", "wait", "extend", "finish"):
            window[key] += 0
    for identity, record in records.items():
        record["alive_at_end"] = identity in prior and not prior[identity]["dead"]
        record["tips_at_end"] = prior[identity]["tips"] if record["alive_at_end"] else None
        record["tipless_ticks"] = (0 if record["tipless_tick"] is None else
                                    (record["death_tick"] or end)-record["tipless_tick"])
    return {"totals": totals, "windows": windows, "terminations": events, "lineages": list(records.values())}
