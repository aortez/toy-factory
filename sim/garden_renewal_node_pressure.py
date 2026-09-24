#!/usr/bin/env python3
"""Offline node ownership, growth-stage pressure and incumbent-death audit."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
from pathlib import Path
import tarfile

import garden_node_audit as nodes
import garden_renewal_plant_slots as parent

experiment, gap, require = parent.experiment, parent.gap, parent.require
light = parent.parent.light_audit
RULE = "garden-renewal-node-pressure-v1"
PROTOCOL = "benchmarks/garden-longevity/renewal-node-pressure-protocol.md"
BASELINE_SHA = "1cec5406f4f595972fde3cfea355d9f8c6c712fb279112d81f8e0ec3a77e0d3b"
PORTABLE = "benchmarks/garden-longevity/renewal-plant-slots-summary.json"
PORTABLE_SHA = "5aca6ec16c07185aeb857f9267537e7346b0510b2dd7abd7f8f4977395059c82"
AFTER, STOP, LATE, DAY, STEP = parent.AFTER, parent.STOP, parent.LATE, parent.DAY, 15
REGISTRATION = ('\nadd_test(NAME garden-renewal-node-pressure-unit\n'
                '\tCOMMAND ${Python3_EXECUTABLE} -W error\n'
                '\t\t${CMAKE_CURRENT_LIST_DIR}/test_garden_renewal_node_pressure.py)\n')
REGISTRATION_ANCHOR = '\nadd_test(NAME garden-root-bootstrap-audit COMMAND ${Python3_EXECUTABLE}'


def ledger(previous, row):
    """Exact node stages: reclaim, germinate four each, then ordered growth."""
    require(row["tick"] == previous["tick"]+STEP and row["tick"] > AFTER,
            "non-consecutive post-split transition")
    before = {p["id"]: p for p in previous["plants"]}
    current = {p["id"]: p for p in row["plants"]}
    require(len(before) == len(previous["plants"]) and len(current) == len(row["plants"]),
            "duplicate node owner")
    for world in (previous, row):
        require(sum(p["nodes"] for p in world["plants"]) == world["nodes"] <= 512,
                "unowned or excessive node storage")
    removed = [p for p in previous["plants"] if p["id"] not in current]
    newborns = [p for p in row["plants"] if p["id"] not in before]
    require(all(p["dead"] for p in removed), "unexplained living removal")
    require(all(not p["dead"] and p["parent"] > 0 for p in newborns) and
            row["births"]-previous["births"] == len(newborns), "wrong birth allocation")
    survivors = [p["id"] for p in previous["plants"] if p["id"] in current]
    require(list(current) == survivors+[p["id"] for p in newborns], "dense growth order changed")
    reclaimed = sum(p["nodes"] for p in removed)
    seed_entry = previous["nodes"]-reclaimed
    count = seed_entry+4*len(newborns)
    require(count <= 512, "germination over capacity")
    entries, allocated = {}, 0
    for p in row["plants"]:
        old = before.get(p["id"])
        added = p["nodes"]-(old["nodes"] if old else 4)
        require(added in (0, 1) and (not p["dead"] or added == 0), "invalid growth allocation")
        if old:
            require(not old["dead"] or p["dead"], "dead owner revived")
            require(p["roots"]-old["roots"] in (0, added), "invalid root allocation")
        require(added == 0 or count < 512, "growth past node capacity")
        entries[p["id"]] = count
        count += added
        allocated += added
    require(count == row["nodes"], "node ledger does not reconcile")
    return {"seed_entry_nodes": seed_entry, "growth_entry_nodes": seed_entry+4*len(newborns),
            "plant_entry_nodes": entries, "reclaimed_nodes": reclaimed,
            "reclaimed_plants": len(removed), "seedling_nodes": 4*len(newborns),
            "growth_nodes": allocated}


def pressure(old, p, tick, at_entry, bids, values):
    """Exposure, not an unobserved request; cooldown is deliberately unknown."""
    require(not p["dead"] and 0 <= at_entry <= 512, "invalid live growth stage")
    full = at_entry == 512
    renewal = values["energy_renewal"] > 0
    tips = old is not None and old["tips"] > 0
    if full:
        require(not bids and not any(values[k] for k in ("extensions", "finishes", "waits")),
                "growth policy evaluated despite pre-policy node gate")
    available = {r: p[r]+values[r+"_growth"]+values[r+"_seeds"] for r in ("energy", "water")}
    affordable = (available["energy"] >= light.resources.ENERGY_COST[p["species"]]-(p["vigor"] > 0) and
                  available["water"] >= light.resources.WATER_COST[p["species"]])
    return {"live_steps": 1, "full_entry": int(full), "full_entry_with_tips": int(full and tips),
            "full_entry_tip_no_renewal": int(full and tips and not renewal),
            "full_entry_tip_no_renewal_affordable": int(full and tips and not renewal and affordable),
            "full_entry_renewals": int(full and renewal), "tipless_steps": int(p["tips"] == 0),
            "offered_bid_steps": int(bool(bids)), "offered_bids": len(bids),
            "allocated_nodes": p["nodes"]-(old["nodes"] if old else 4)}


def append_run(runs, tick):
    if runs and runs[-1]["last_tick"] == tick-STEP:
        runs[-1]["last_tick"] = tick
        runs[-1]["samples"] += 1
    else:
        runs.append({"first_tick": tick, "last_tick": tick, "samples": 1})


def snapshot(row, incumbents):
    return {"tick": row["tick"], "ownership": nodes.ownership(row, 512),
            "plants": [{"incumbent": p["id"] in incumbents,
                        **light.failures.point(row["tick"], p)} for p in row["plants"]]}


def terminal(old, p, tick, bids, leaf):
    require(old and not old["dead"] and old["stress"] == 7 and p["stress"] == 8 and
            p["dead"] and p["flags"] & 6 and tick % 60 == 0 and not bids and leaf is None and
            all(p[k] == 0 for k in ("energy", "water", "energy_income", "water_income")),
            "invalid cleared terminal state")
    return {"state": light.failures.point(tick, p), "budget": None, "terminal": "natural",
            "light": None, "growth": None, "maintenance": None, "roots": {}}


def summarize_history(entries, origin):
    result = light.summarize(entries, origin)
    roots = Counter()
    for e in entries:
        roots.update(e["roots"])
    result["roots"] = roots
    result["body"] = {"first": {k: origin[k] for k in ("nodes", "roots", "leaves", "tips")},
                      "last": {k: entries[-1]["state"][k] for k in ("nodes", "roots", "leaves", "tips")},
                      "live_tip_steps": sum(bool(e["state"]["tips"]) for e in entries if not e["terminal"])}
    return result


def matched_window(history, death):
    start = death-DAY
    entries = [e for e in history if start < e["state"]["tick"] < death]
    origin = next((e["state"] for e in history if e["state"]["tick"] == start), None)
    require(origin is not None and not origin["dead"] and
            [e["state"]["tick"] for e in entries] == list(range(start+STEP, death, STEP)) and
            not any(e["terminal"] for e in entries), "unavailable matched live pre-death window")
    result = summarize_history(entries, origin)
    result["sunsets"] = [e["state"] for e in entries if e["state"]["phase"] == 128]
    result["expenses"] = [{"tick": e["state"]["tick"], "phase": e["state"]["phase"],
                           "post_energy": e["state"]["energy"], "post_water": e["state"]["water"],
                           **{r+"_"+k: e["budget"][r+"_"+k]
                              for r in ("energy", "water") for k in ("growth", "seeds", "renewal")}}
                          for e in entries if any(e["budget"]["energy_"+k] for k in ("growth", "seeds", "renewal"))]
    return result


def analyze_case(root, arm, saved):
    previous, boundary, last = None, None, None
    pending, offered = {}, defaultdict(list)
    histories, per_plant = defaultdict(list), defaultdict(Counter)
    windows = {name: Counter() for name in ("after", "late")}
    runs, snapshots, last_full_start = [], {}, None
    records = {p["id"]: p for p in saved["lineages"]}
    checked, deaths = 0, 0
    for row in gap.read_trace(root/f"traces/{arm}.world.jsonl.gz"):
        tick = row.get("tick", -1)
        if tick < AFTER:
            continue
        if row["type"] in ("leaf-bid", "bid"):
            if tick == AFTER:
                continue
            if row["type"] == "leaf-bid":
                require(row["id"] not in pending, "duplicate leaf sample")
                pending[row["id"]] = row
            else:
                offered[row["id"]].append(row)
            continue
        require(row["type"] == "world" and tick <= STOP, "unexpected post-split record")
        parent.check_rule(row, arm)
        if tick == AFTER:
            require(previous is None, "duplicate boundary")
            previous, boundary = row, row
            incumbents = {p["id"] for p in row["plants"] if not p["dead"]}
            require(incumbents == {2, 4, 5, 6, 7, 9, 12}, "wrong incumbent scope")
            snapshots["boundary"] = snapshot(row, incumbents)
            continue
        require(previous is not None, "missing boundary")
        stages = ledger(previous, row)
        ownership = nodes.ownership(row, 512)
        counts = {**ownership, "checkpoints": 1,
                  **{k: stages[k] for k in ("reclaimed_nodes", "reclaimed_plants", "seedling_nodes", "growth_nodes")},
                  "full_seed_entry": int(stages["seed_entry_nodes"] == 512),
                  "seed_entry_node_gate": int(stages["seed_entry_nodes"] > 508),
                  "full_growth_entry": int(stages["growth_entry_nodes"] == 512),
                  "incumbent_nodes": sum(p["nodes"] for p in row["plants"] if p["id"] in incumbents),
                  "new_nodes": sum(p["nodes"] for p in row["plants"] if p["id"] not in incumbents)}
        for name, start in (("after", AFTER), ("late", LATE)):
            if tick > start:
                windows[name].update(counts)
        if ownership["node_full"]:
            append_run(runs, tick)
            if "first_full" not in snapshots:
                snapshots["first_full"] = snapshot(row, incumbents)
            if previous["nodes"] < 512:
                last_full_start = snapshot(row, incumbents)
        before = {p["id"]: p for p in previous["plants"]}
        for p in row["plants"]:
            identity, old = p["id"], before.get(p["id"])
            leaf, bids = pending.pop(identity, None), offered.pop(identity, [])
            if old and old["dead"]:
                require(p["dead"] and not bids and leaf is None, "dead owner observed")
                continue
            if p["dead"]:
                entry = terminal(old, p, tick, bids, leaf)
                require(records[identity]["death_tick"] == tick, "wrong death identity/time")
                deaths += 1
            else:
                values = light.resources.budget(old, p, tick)
                light.check_leaf(old, p)
                if old:
                    light.check_stress(old, p, tick, values)
                else:
                    require(records[identity]["birth_tick"] == tick, "wrong newborn identity/time")
                exposure = pressure(old, p, tick, stages["plant_entry_nodes"][identity], bids, values)
                per_plant[str(identity)].update(exposure)
                checked += 1
                entry = None
                if identity in incumbents:
                    entry = {"state": light.failures.point(tick, p), "budget": values, "terminal": None,
                             "light": light.photometry(old, p, tick, leaf, values),
                             "growth": light.growth(old, p, tick, bids, values),
                             "maintenance": light.seedlings.maintenance(old, {**p, "tick": tick}, values),
                             "roots": parent.prior.root_exposure(previous, row, identity)}
            if identity in incumbents:
                histories[identity].append(entry)
        require(not pending and not offered, "unmatched policy observation")
        previous, last = row, tick
    require(last == STOP and boundary is not None, "truncated node audit")
    snapshots["endpoint"] = snapshot(previous, incumbents)
    snapshots["final_full_start"] = last_full_start if previous["nodes"] == 512 else None
    summaries = {}
    for identity in sorted(incumbents):
        history = histories[identity]
        end = records[identity]["death_tick"] or STOP
        require([e["state"]["tick"] for e in history] == list(range(AFTER+STEP, end+STEP, STEP)),
                "incomplete incumbent lifetime")
        origin = light.failures.point(AFTER, next(p for p in boundary["plants"] if p["id"] == identity))
        summaries[str(identity)] = {"lineage": records[identity], "whole": summarize_history(history, origin),
                                   "stress_episodes": light.seedlings.stress_episodes(history)}
    pressure_total = Counter()
    for value in per_plant.values():
        pressure_total.update(value)
    return {"windows": windows, "full_runs": runs, "snapshots": snapshots,
            "growth_pressure": {"total": pressure_total, "by_plant": dict(per_plant)},
            "incumbents": summaries, "checked_live_budgets": checked,
            "terminal_budgets_not_reconstructed": deaths}, histories


def death_comparisons(cases, histories):
    comparisons = []
    for identity, record in cases["sixteen"]["incumbents"].items():
        death = record["lineage"]["death_tick"]
        if death is None:
            continue
        identity = int(identity)
        pair = {}
        for arm in parent.ARMS:
            pair[arm] = matched_window(histories[arm][identity], death)
        episodes = record["stress_episodes"]
        require(episodes and episodes[-1]["terminal_tick"] == death, "missing terminal stress episode")
        start_stress = episodes[-1]["first"]["tick"]
        terminal_maintenance = [{k: e["state"][k] for k in
                                ("tick", "phase", "stress", "flags", "energy", "water", "nodes", "tips")}
                               for e in histories["sixteen"][identity]
                               if start_stress <= e["state"]["tick"] <= death and e["state"]["tick"] % 60 == 0]
        comparisons.append({"id": identity, "candidate_death_tick": death, "matched": pair,
                            "terminal_stress_maintenance": terminal_maintenance})
    return comparisons


def analyze(root, saved):
    cases, histories = {}, {}
    for arm in parent.ARMS:
        cases[arm], histories[arm] = analyze_case(root, arm, saved["cases"][arm])
    return {"rule": RULE, "parent_manifest_sha256": BASELINE_SHA, "parent_portable_sha256": PORTABLE_SHA,
            "window": {"after": AFTER, "late": LATE, "stop": STOP, "step": STEP, "day": DAY},
            "new_native_calls": 0, "cases": cases, "death_comparisons": death_comparisons(cases, histories),
            "limits": ["Full-entry counts are exposure, not rejected requested EXTEND actions; cooldown is not exported.",
                       "Leaf renewal precedes the full-node growth gate and can succeed at capacity.",
                       "Terminal income/stores are cleared; terminal budgets remain unknown.",
                       "Shared roots and sampled light do not causally attribute extraction, shading or death.",
                       "No new counterfactual or qualification beyond this selected world."]}


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
    require(all(experiment.digest(experiment.ROOT/n) == sha for n, sha in native.items()), "native source changed")
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
    require(result == analyze(root, saved), "repeated node audit differs")
    require(sources == analysis_sources() and all(experiment.digest(experiment.ROOT/n) == sha for n, sha in native.items()),
            "analysis/native source changed during audit")
    gap.parent.shadow.check_frozen(root, BASELINE_SHA)
    require(experiment.digest(experiment.ROOT/PORTABLE) == PORTABLE_SHA, "parent summary changed during audit")
    return {**result, "analysis_sources": sources, "native_sources": native}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, default=experiment.ROOT/"artifacts/garden-renewal-plant-slots-v1")
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
        require(experiment.read_json(args.check) == result, "portable node audit differs")
    print("Verified node/death audit; zero new native research calls", flush=True)


if __name__ == "__main__":
    main()
