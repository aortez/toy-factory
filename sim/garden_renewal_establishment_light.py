#!/usr/bin/env python3
"""Read-only light, establishment spending and flower decline in frozen spacing runs."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
from pathlib import Path
import tarfile

import garden_resources as resources
import garden_renewal_dark_failures as failures
import garden_renewal_seed_spacing as parent
import garden_renewal_seedling_budget as seedlings
from garden_renewal_phase_forecast import check_stress, sun_strength
from garden_renewal_startup import check_leaf

experiment, gap, require = parent.experiment, parent.gap, parent.require
RULE = "garden-renewal-establishment-light-v1"
PROTOCOL = "benchmarks/garden-longevity/renewal-establishment-light-protocol.md"
BASELINE_SHA = "f230a7eeb305eb9bef28381ea618cb8fec44a3da4d5885bd5978eeb675507007"
PORTABLE = "benchmarks/garden-longevity/renewal-seed-spacing-summary.json"
PORTABLE_SHA = "bdd740f2b1a2b74488c3e2aed8b674b750a516a13dd9b56fd2b656deafc6fb0e"
AFTER, STOP, DAY, STEP = parent.AFTER, parent.STOP, parent.DAY, 15
FLOWER, DEATH = 5, 214200
CHILDREN = tuple(range(13, 32))
REGISTRATION = ('\nadd_test(NAME garden-renewal-establishment-light-unit\n'
                '\tCOMMAND ${Python3_EXECUTABLE} -W error\n'
                '\t\t${CMAKE_CURRENT_LIST_DIR}/test_garden_renewal_establishment_light.py)\n')
REGISTRATION_ANCHOR = '\nadd_test(NAME garden-root-bootstrap-audit COMMAND ${Python3_EXECUTABLE}'


def photometry(old, plant, tick, bid, values):
    """Recover the sum of condition * floor(light/64), never individual light."""
    require(not plant["dead"] and tick > 0 and tick % STEP == 0, "invalid live photometry step")
    if old is None:
        require(bid is None and plant["energy_income"] == plant["leaf"]["remainder"] == 0,
                "newborn absorbed light before germination")
        return None
    before, after = old["leaf"], plant["leaf"]
    require(all(0 <= c <= 255 for c in before["conditions"]) and
            len(before["conditions"]) == old["leaves"], "invalid prior leaf inventory")
    # Growth animation is ceil(255/12) per logic tick; all old leaves are mature
    # after the 15 intervening ticks. Wear precedes uptake and policy observation.
    conditions = [max(0, c-int(tick % 60 == 0)) for c in before["conditions"]]
    require(all(0 <= r < 255 for r in (before["remainder"], after["remainder"])), "invalid carry")
    numerator = plant["energy_income"]*255+after["remainder"]-before["remainder"]
    require(0 <= numerator <= 3*sum(conditions), "impossible photosynthesis numerator")
    count = len(conditions)
    require(after["observations"]-before["observations"] == int(count > 0) == int(bid is not None),
            "missing/extra sampled leaf observation")
    if bid is None:
        require(numerator == 0, "income without an old leaf")
        return {"numerator": numerator, "mature_leaves": 0, "all_positive": False,
                "all_bands_zero_proven": False, "sample": None}
    require(bid["tick"] == tick and bid["id"] == plant["id"] and bid["mature_leaves"] == count,
            "misaligned leaf or immature prior leaves")
    index = (tick//STEP+plant["id"]) % count
    require(bid["condition"] == conditions[index] and 0 <= bid["light"] <= 255,
            "sampled condition does not match pre-uptake wear/order")
    contribution = bid["condition"]*(bid["light"]//64)
    require(contribution <= numerator <= contribution+3*(sum(conditions)-conditions[index]),
            "sampled leaf contradicts whole-plant photosynthesis")
    for resource, cap in (("energy", 256), ("water", 512)):
        expected = min(cap, old[resource]+plant[resource+"_income"])-values[resource+"_upkeep"]
        require(bid[resource] == expected, "leaf policy observed wrong stage stores")
    limits = {"energy": 9+min(128, 40*((old["nodes"]+7)//8)),
              "water": 5+min(256, 40*((old["nodes"]-old["roots"]+7)//8))}
    failed = [k for k, fail in (("condition", bid["condition"] > 128), ("light", bid["light"] < 128),
                                ("energy", bid["energy"] < limits["energy"]),
                                ("water", bid["water"] < limits["water"])) if fail]
    require(bid["action"] == int(not failed) and
            after["proposals"]-before["proposals"] == bid["action"], "selective renewal rule differs")
    accepted = after["renewals"]-before["renewals"]
    require(0 <= accepted <= bid["action"] and values["energy_renewal"] == 9*accepted,
            "renewal proposal/payment mismatch")
    positive = all(c > 0 for c in conditions)
    return {"numerator": numerator, "mature_leaves": count, "all_positive": positive,
            "all_bands_zero_proven": positive and numerator == 0,
            "sample": {**{k: bid[k] for k in ("site_x", "site_y", "condition", "light", "energy", "water")},
                       "band": bid["light"]//64, "renewal_failures": failed,
                       "limits": limits, "proposed": bid["action"], "accepted": accepted}}


def growth(old, plant, tick, bids, values):
    """Only paid, committed actions are spending; offered/refused bids are not."""
    agent, before = plant["agent"], old["agent"] if old else {}
    committed = sum(values[k] for k in ("extensions", "finishes", "waits"))
    require(agent["decisions"]-before.get("decisions", 0) == committed <= 1, "bad committed counter")
    if not committed:
        require(values["energy_growth"] == 0, "uncommitted growth was charged")
        return None
    require(bool(bids) and len({b["tip_index"] for b in bids}) == len(bids), "missing/duplicate winning bids")
    winner = max(bids, key=lambda b: b["priority"])  # C keeps the first equal-priority bid.
    require(all(winner[k] == agent["last_"+k] for k in ("priority", "action", "tissue", "x", "y")),
            "recorded winner differs from committed telemetry")
    require(all((b["tick"], b["id"], b["energy"], b["water"]) ==
                (tick, plant["id"], winner["energy"], winner["water"]) for b in bids), "mixed bid snapshots")
    require(values[("waits", "extensions", "finishes")[winner["action"]]] == 1, "wrong action debit")
    for tissue, name in ((0, "shoot_extend"), (1, "root_extend")):
        require(agent[name]-before.get(name, 0) == int(winner["action"] == 1 and winner["tissue"] == tissue),
                "wrong committed root/shoot counter")
    if not values["energy_growth"]:
        return None
    candidates = winner["candidates"]
    require(len(candidates) == (5 if winner["tissue"] == 0 else 3) and
            all(c["flags"] in (0, 3, 5, 9, 13) and 0 <= c["light"] <= 255 for c in candidates),
            "invalid available-candidate telemetry")
    available = [c["light"] for c in candidates if c["flags"] & 2]
    return {"tick": tick, "phase": (64+tick//STEP)%256, "action": ("wait", "extend", "finish")[winner["action"]],
            "tissue": "root" if winner["tissue"] else "shoot", "energy": values["energy_growth"],
            "water": values["water_growth"], "energy_before": winner["energy"], "water_before": winner["water"],
            "available_candidate_lights": available,
            "maximum_available_light": max(available) if available else None,
            "chosen_candidate": "not recorded"}


def scope(records):
    cohort = [p for p in records if p["birth_tick"] > AFTER]
    chosen = {p["id"]: p for p in cohort}
    require(len(cohort) == len(chosen) and tuple(chosen) == CHILDREN and
            all(p["parent"] and p["birth_tick"] <= STOP for p in chosen.values()),
            "changed post-boundary cohort")
    return chosen


def raw_observations(root, arm, chosen):
    leaves, bids = {}, defaultdict(list)
    for row in gap.read_trace(root/f"traces/{arm}.world.jsonl.gz"):
        if row["type"] not in ("bid", "leaf-bid") or row["id"] not in chosen or row["tick"] <= AFTER:
            continue
        if row["id"] == FLOWER and row["tick"] > DEATH:
            continue
        key = (row["tick"], row["id"])
        if row["type"] == "leaf-bid":
            require(key not in leaves, "duplicate leaf observation")
            leaves[key] = row
        else:
            bids[key].append(row)
    return leaves, bids


def histories(root, arm, chosen):
    leaves, bids = raw_observations(root, arm, chosen)
    result, anchors, previous, last = defaultdict(list), {}, {}, -STEP
    for row in gap.read_trace(root/f"traces/{arm}.worlds.jsonl.gz"):
        tick, phase = row["tick"], row["sun_phase"]
        require(tick == last+STEP and phase == (64+tick//STEP)%256 and row["sun_strength"] == sun_strength(phase),
                "missing/misaligned census")
        current = {p["id"]: p for p in row["plants"]}
        require(len(current) == len(row["plants"]), "duplicate lineage")
        for identity in chosen.keys() & current.keys():
            p, old = current[identity], previous.get(identity)
            if identity == FLOWER and tick == AFTER:
                anchors[identity] = failures.point(tick, p)
            if tick <= AFTER or identity == FLOWER and tick > DEATH or old and old["dead"]:
                continue
            record = chosen[identity]
            require(all(p[k] == record[k] for k in ("id", "parent", "column", "species", "generation", "genome")),
                    "changed focal identity")
            if old is None:
                require(not result[identity] and tick == record["birth_tick"], "wrong newborn boundary")
            leaf, offered = leaves.pop((tick, identity), None), bids.pop((tick, identity), [])
            point = failures.point(tick, p)
            if p["dead"]:
                require(old and old["stress"] == 7 and p["stress"] == 8 and p["flags"] & 6 and
                        tick == record["death_tick"] and tick % 60 == 0 and not leaf and not offered and
                        all(p[k] == 0 for k in ("energy", "water", "energy_income", "water_income")),
                        "invalid terminal telemetry")
                entry = {"state": point, "budget": None, "terminal": "natural", "light": None,
                         "growth": None, "maintenance": None, "offered_bids": 0}
            else:
                require(old is None or not old["dead"], "revived lineage")
                values = resources.budget(old, p, tick)
                check_leaf(old, p)
                if old:
                    check_stress(old, p, tick, values)
                entry = {"state": point, "budget": values, "terminal": None,
                         "light": photometry(old, p, tick, leaf, values),
                         "growth": growth(old, p, tick, offered, values),
                         "maintenance": seedlings.maintenance(old, {**p, "tick": tick}, values),
                         "offered_bids": len(offered)}
            result[identity].append(entry)
        # The parent validates the earlier founder export/handoff boundaries.
        # This audit begins after them and permits no later live disappearance.
        require(tick <= AFTER or all(previous[i]["dead"] for i in previous.keys()-current.keys()),
                "live lineage disappeared")
        previous, last = current, tick
    require(last == STOP and not leaves and not bids and result.keys() == chosen.keys(), "incomplete focal histories")
    for identity, record in chosen.items():
        start = AFTER+STEP if identity == FLOWER else record["birth_tick"]
        end = min(record["death_tick"] or STOP, DEATH if identity == FLOWER else STOP)
        require([e["state"]["tick"] for e in result[identity]] == list(range(start, end+STEP, STEP)),
                "incomplete focal lifetime")
    return result, anchors


def summarize(entries, initial):
    require(bool(entries), "empty summary window")
    live = [e for e in entries if e["budget"] is not None]
    require(bool(live) and all(e["terminal"] is None for e in entries[:-1]) and
            all((e["budget"] is None) == e["state"]["dead"] for e in entries), "fabricated/missing terminal budget")
    totals = failures.budget_sum(entries)
    failures.balance(initial, live[-1]["state"], totals)
    stats, bands, bright_bands, renewal, shortage = Counter(), Counter(), Counter(), Counter(), Counter()
    for e in live:
        stats["live_steps"] += 1
        bright = sun_strength(e["state"]["phase"]) >= 64
        stats["global_possible_income_steps"] += bright
        if e["maintenance"]:
            for k, v in e["maintenance"].items():
                shortage[k+"_required"] += v["due"]
                shortage[k+"_unpaid"] += v["unpaid"]
        light = e["light"]
        if light is None:
            stats["newborn_no_uptake_steps"] += 1
            continue
        stats["photosynthesis_numerator"] += light["numerator"]
        stats["bright_zero_numerator_steps"] += bright and light["numerator"] == 0
        stats["bright_all_bands_zero_proven_steps"] += bright and light["all_bands_zero_proven"]
        stats["bright_positive_numerator_zero_integer_income_steps"] += bright and light["numerator"] > 0 and e["budget"]["energy_income"] == 0
        sample = light["sample"]
        if sample:
            bands[str(sample["band"])] += 1
            if bright:
                bright_bands[str(sample["band"])] += 1
                stats["bright_sample_light_sum"] += sample["light"]
                stats["bright_sample_condition_sum"] += sample["condition"]
                stats["bright_samples"] += 1
                stats["bright_samples_at_ambient_floor"] += sample["light"] == 24
                stats["bright_samples_above_floor_below_income_band"] += 24 < sample["light"] < 64
            renewal.update({"proposed": sample["proposed"], "accepted": sample["accepted"],
                            "refused": sample["proposed"]-sample["accepted"]})
            renewal.update("failed_"+k for k in sample["renewal_failures"])
            if sample["condition"] <= 128 and sample["light"] >= 128:
                renewal["old_and_lit_samples"] += 1
                renewal["old_and_lit_energy_insufficient"] += "energy" in sample["renewal_failures"]
                renewal["old_and_lit_water_insufficient"] += "water" in sample["renewal_failures"]
    return {"first_tick": entries[0]["state"]["tick"], "last_tick": entries[-1]["state"]["tick"],
            "initial": initial, "last_live": live[-1]["state"], "budget": totals, "light": stats,
            "sampled_bands": bands, "bright_sampled_bands": bright_bands,
            "renewal": renewal, "maintenance": shortage,
            "terminal_step_unaccounted": entries[-1]["state"]["tick"] if entries[-1]["terminal"] else None}


def describe_child(record, history):
    birth = record["birth_tick"]
    origin = {"energy": 64, "water": 24}
    first_income = next((e["state"]["tick"] for e in history if e["budget"] and e["budget"]["energy_income"]), None)
    before = [e for e in history if first_income is None or e["state"]["tick"] < first_income]
    first_day = [e for e in history if e["state"]["tick"] <= birth+DAY]
    available = STOP >= birth+DAY
    survived = available and (record["death_tick"] is None or record["death_tick"] > birth+DAY)
    paid = [e["growth"] for e in history if e["growth"]]
    require(sum(p["energy"] for p in paid) == failures.budget_sum(history)["energy_growth"], "growth join misses spending")
    return {"lineage": record, "first_day_eligible": available, "survived_first_day": survived,
            "followup_ticks": history[-1]["state"]["tick"]-birth,
            "first_possible_global_income_tick": next(t for t in range(birth+STEP, birth+DAY+STEP, STEP)
                                                       if sun_strength((64+t//STEP)%256) >= 64),
            "first_observed_income_tick": first_income, "lifetime": summarize(history, origin),
            "first_day": summarize(first_day, origin),
            "before_first_income": summarize(before, origin) if before else None,
            "growth": paid, "zero_income_runs": seedlings.zero_income_runs(history),
            "stress_episodes": seedlings.stress_episodes(history)}


def paired_samples(control, candidate):
    require(len(control) == len(candidate), "different paired-window lengths")
    counts, differences = Counter(), []
    for a, b in zip(control, candidate, strict=True):
        tick = a["state"]["tick"]
        require(tick == b["state"]["tick"], "misaligned paired times")
        if a["terminal"] or b["terminal"]:
            counts["terminal_excluded"] += 1
            continue
        x, y = a["light"]["sample"], b["light"]["sample"]
        require(x is not None and y is not None and
                (x["site_x"], x["site_y"]) == (y["site_x"], y["site_y"]), "different sampled leaf sites")
        counts["matched_samples"] += 1
        if sun_strength(a["state"]["phase"]) < 64:
            continue
        counts["bright_samples"] += 1
        for k in ("light", "band", "condition"):
            counts[k+"_control_sum"] += x[k]
            counts[k+"_candidate_sum"] += y[k]
            direction = "lower" if y[k] < x[k] else "higher" if y[k] > x[k] else "same"
            counts[k+"_candidate_"+direction] += 1
        if x["light"] != y["light"] and len(differences) < 8:
            differences.append({"tick": tick, "phase": a["state"]["phase"], "control": x, "two": y})
    return {"counts": counts, "first_eight_bright_light_differences": differences}


def flower_summary(histories_by_arm, anchors):
    by_tick = {a: {e["state"]["tick"]: e for e in h} for a, h in histories_by_arm.items()}
    for h in histories_by_arm.values():
        require(all((e["state"]["nodes"], e["state"]["roots"], e["state"]["leaves"], e["state"]["tips"]) ==
                    (36, 20, 8, 0) for e in h), "flower body changed")
    def window(start, end):
        entries = {a: [by_tick[a][t] for t in range(start+STEP, end+STEP, STEP)] for a in parent.ARMS}
        result = {a: summarize(entries[a], anchors[a] if start == AFTER else by_tick[a][start]["state"])
                  for a in parent.ARMS}
        return {"start_exclusive": start, "end_inclusive": end, "arms": result,
                "paired": paired_samples(entries["control"], entries["two"])}
    days = [window(t, min(t+DAY, DEATH-STEP)) for t in range(AFTER, DEATH-STEP, DAY)]
    stress = seedlings.stress_episodes(histories_by_arm["two"])
    require(len(stress) == 1 and stress[0]["terminal_tick"] == DEATH, "changed flower shortage history")
    first = stress[0]["first"]["tick"]
    final = [{"tick": t, **{a: by_tick[a][t] for a in parent.ARMS}} for t in range(first, DEATH+STEP, 60)]
    require(len(final) == 8, "not eight consecutive terminal shortages")
    return {"body": {"nodes": 36, "roots": 20, "leaves": 8, "tips": 0},
            "common_live_interval": window(AFTER, DEATH-STEP), "days": days,
            "penultimate_day": window(DEATH-2*DAY, DEATH-DAY),
            "final_day": window(DEATH-DAY, DEATH),
            "shortage_episode": stress[0], "final_maintenance_steps": final,
            "matching_control_terminal_time": by_tick["control"][DEATH]["state"]}


def analyze(root, saved):
    chosen = scope(saved["cases"]["two"]["lineages"])
    require(not [p for p in saved["cases"]["control"]["lineages"] if p["birth_tick"] > AFTER], "control has new cohort")
    all_histories, anchors = {}, {}
    for arm in parent.ARMS:
        flower = next(p for p in saved["cases"][arm]["lineages"] if p["id"] == FLOWER)
        records = {FLOWER: flower, **(chosen if arm == "two" else {})}
        all_histories[arm], start = histories(root, arm, records)
        anchors[arm] = start[FLOWER]
    children = [describe_child(p, all_histories["two"][i]) for i, p in chosen.items()]
    print("Audited 19 seedlings and matched flower light/spending from saved traces", flush=True)
    return {"rule": RULE, "baseline_manifest_sha256": BASELINE_SHA, "baseline_portable_sha256": PORTABLE_SHA,
            "experimental_native_calls": 0, "training_calls": 0, "children": children,
            "flower": flower_summary({a: all_histories[a][FLOWER] for a in parent.ARMS}, anchors),
            "summary": {"children": len(children), "first_day_eligible": sum(p["first_day_eligible"] for p in children),
                        "first_day_survivors": [p["lineage"]["id"] for p in children if p["survived_first_day"]],
                        "zero_recorded_lifetime_income": [p["lineage"]["id"] for p in children
                                                         if p["lifetime"]["budget"]["energy_income"] == 0],
                        "zero_recorded_photosynthesis_numerator": [p["lineage"]["id"] for p in children
                                                                  if p["lifetime"]["light"]["photosynthesis_numerator"] == 0],
                        "seedling_live_budgets": sum(p["lifetime"]["light"]["live_steps"] for p in children),
                        "seedling_terminals_unaccounted": sum(p["lineage"]["death_tick"] is not None for p in children)}}


def analysis_sources():
    paths = sorted((experiment.ROOT/"sim").glob("*.py"))+[experiment.ROOT/PROTOCOL, experiment.ROOT/"sim/CMakeLists.txt"]
    return {str(p.relative_to(experiment.ROOT)): experiment.digest(p) for p in paths}


def check_build_registration(original, current, sha):
    anchor = REGISTRATION_ANCHOR.encode()
    require(hashlib.sha256(original).hexdigest() == sha and original.count(anchor) == 1 and
            current == original.replace(anchor, REGISTRATION.encode()+anchor),
            "historical CMake changed beyond the exact new audit test registration")


def check_parent(root):
    gap.parent.shadow.check_frozen(root, BASELINE_SHA)
    require(experiment.digest(experiment.ROOT/PORTABLE) == PORTABLE_SHA, "portable parent changed")
    with tarfile.open(root/"source.tar.gz") as archive:
        original = archive.extractfile("sim/CMakeLists.txt").read()
    for name, sha in experiment.read_json(root/"analysis-sources.json").items():
        if name == "sim/CMakeLists.txt":
            check_build_registration(original, (experiment.ROOT/name).read_bytes(), sha)
        else:
            require(experiment.digest(experiment.ROOT/name) == sha, "historical analysis dependency changed: "+name)
    native = parent.native.native_hashes(root/"source.tar.gz")
    require(all(experiment.digest(experiment.ROOT/n) == sha for n, sha in native.items()), "native source changed")
    capture = parent.check_capture(root)
    require(experiment.read_json(root/"timings.json")["calls"] == capture["calls"], "capture timings differ")
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
    require(result == analyze(root, saved), "repeated light audit differs")
    require(sources == analysis_sources() and all(experiment.digest(experiment.ROOT/n) == sha for n, sha in native.items()),
            "analysis/native source changed")
    gap.parent.shadow.check_frozen(root, BASELINE_SHA)
    require(experiment.digest(experiment.ROOT/PORTABLE) == PORTABLE_SHA, "portable changed during audit")
    return {**result, "analysis_sources": sources, "native_sources": native}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, default=experiment.ROOT/"artifacts/garden-renewal-seed-spacing-v1")
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
        require(experiment.read_json(args.check) == result, "portable light audit differs")
    print("Verified establishment light audit; zero new experimental native calls", flush=True)


if __name__ == "__main__":
    main()
