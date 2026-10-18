#!/usr/bin/env python3
"""Fixed whole-population dawn screen; streaming receipts, 32 replays, no training."""

from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import copy
from functools import cache
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tarfile
import zlib

import garden_landing_dawn as dawn
import garden_experiments as experiment
from garden_gallery import artifact, contact_sheet
from garden_resources import require

ROOT, DAY, STEP, STOP = dawn.ROOT, dawn.DAY, dawn.STEP, dawn.STOP
order, adults = dawn.order, dawn.adults
ARMS, LABELS = ("control", "candidate"), ("trace", "repeat")
RULE = "garden-landing-population-v1"
PROTOCOL = "benchmarks/garden-seasons/landing-population-protocol.md"
INPUT = "benchmarks/garden-seasons/landing-dawn-results.json.gz"
INPUT_SHA = "6c35b2c53f258d0521d7b773f551158fa75770ece81b0ec4564a0b825d1c6687"
MODEL_SHA = "f2dc989380339614dc512f64f11f2bf03f7079c465c4c9bd18895044ec3e1567"
INPUTS = {INPUT: INPUT_SHA, order.previous.MODELS: order.previous.MODEL_SHA}
FRESH = tuple(experiment.trial_seeds(0x20261002, 3))
CASES = tuple({"id": seed + "-" + traversal, "seed": seed, "order": traversal,
               "role": "diagnostic" if seed == "940cfdc4" else "fresh"}
              for seed in ("940cfdc4", *FRESH) for traversal in order.ARMS)
FLAGS = ("--root-all-offspring", "--root-energy-reserve", "--root-afternoon-reserve",
         "--root-continuous-energy", "--root-daylight-energy")
GATES = ("budget", "water_gate", "energy_gate", "afternoon_gate", "daylight_gate", "dawn_gate")
KINDS = ("founders", "offspring")


@cache
def load_model():
    for path, sha in INPUTS.items():
        require(experiment.digest(ROOT / path) == sha, "population input changed")
    with gzip.open(ROOT / INPUT, "rt") as stream:
        metadata = json.load(stream)["model"]
    with gzip.open(ROOT / order.previous.MODELS, "rt") as stream:
        model = bytes.fromhex(json.load(stream)[metadata["model"]])
    require(metadata["sha256"] == hashlib.sha256(model).hexdigest() == MODEL_SHA, "wrong model")
    return metadata, model


def wrapped(base, tag):
    value = 2166136261
    for byte in tag + int(base, 16).to_bytes(4, "little"):
        value = ((value ^ byte) * 16777619) & 0xffffffff
    return f"{value:08x}"


def common_result(result, case, arm):
    require(arm in ARMS, "unknown population arm")
    value = copy.deepcopy(result)
    placing = order.previous.placement
    expected = placing.probe_hash(placing.budget.probe_hash(value["base_run_hash"], 2), True)
    if case["order"] == "rotating":
        expected = order.order_hash(expected, order.AT)
    base = expected
    for key, tag in (("all_offspring", b"GLF1"), ("energy", b"GLE1"), ("afternoon", b"GLN1"),
                     ("continuous_energy", b"GLU1"), ("daylight_energy", b"GLD1"),
                     *([("dawn_reserve", b"GLM1")] if arm == "candidate" else [])):
        name = "root_" + key + "_probe"
        require(value.get(name) == {"version": 1} and type(value[name]["version"]) is int, "wrong population scope")
        del value[name]
        expected = wrapped(expected, tag)
    require(not any(k.startswith("root_") for k in value) and value["run_hash"] == expected,
            "wrong population fingerprint/extra probe")
    value["run_hash"] = base
    order.common_view(value, case["order"])
    require(result["scenario"] == "rainfed-crowded" and result["seed"] == case["seed"] and
            result["climate"]["mode"] == "seasonal" and result["model"] == load_model()[0]["metadata"] and
            result["rules"] == 0 and result["gardener"] is False and result["irrigation"] is False and
            result["seed_lifetime_ecology_ticks"] == 8192 and result["ledger_start_tick"] == 0,
            "wrong population environment/model")
    return value


def stem(case, arm, label):
    return case["id"] + "-" + arm + "-" + label


def arguments(case, arm, label, *, stop=STOP):
    require(case in CASES and arm in ARMS and label in LABELS, "wrong population call")
    name = stem(case, arm, label)
    args = ["placement-replay", "model.tgl", "rainfed-crowded", "0x" + case["seed"],
            "--climate", "seasonal", "--ledger", "--shoot-reserve", "on", "--seed-placement", "spacing",
            *FLAGS, "--ticks", str(stop), "--framebuffer", "frames/" + name + ".raw", "--stand-dawn"]
    for kind in ("stand", "adult"):
        args += ["--" + kind + "-trace", name + "-" + kind + ".jsonl",
                 "--" + kind + "-start", str(STEP), "--" + kind + "-stop", str(stop)]
    if case["order"] == "rotating":
        args += ["--seed-order", "rotating", "--seed-order-after", str(order.AT)]
    return args + (["--root-dawn-reserve"] if arm == "candidate" else [])


def trace_rows(path, kind, result):
    """Validate complete framing while keeping only the current row in memory."""
    stop = result["tick"]
    header = ({"schema": dawn.SCHEMA, "node_limit": 32, "budget_mode": 2} if kind == "stand"
              else {"schema": "landing-adult-resources-v1"}) | {"start": STEP, "stop": stop}
    footer = {"complete": True, "tick": stop} | ({"run_hash": result["run_hash"]} if kind == "stand" else {})
    with (gzip.open(path, "rt") if path.suffix == ".gz" else path.open()) as stream:
        require(json.loads(next(stream)) == header, "wrong population trace header")
        for tick in range(STEP, stop + STEP, STEP):
            row = json.loads(next(stream))
            require(type(row.get("tick")) is int and row["tick"] == tick, "missing/reordered ecology step")
            yield row
        require(json.loads(next(stream)) == footer and not stream.read(), "wrong footer/trailing trace")


def payment(plant, receipt, previous_roots, tick, phase):
    if plant["uptake"] is None or tick % (4 * STEP):
        return None
    nodes = plant["stages"][0][4]
    require(previous_roots is not None and 0 <= previous_roots <= nodes, "missing pre-maintenance roots")
    event = {"tick": tick, "phase": phase, "nodes": nodes, "roots": previous_roots}
    for j, (name, body, flag) in enumerate((("energy", nodes, 2), ("water", nodes - previous_roots, 4))):
        due = (body + 7) // 8
        paid = receipt[name]["upkeep"]
        require(paid == min(due, plant["stages"][0][j]) and
                bool(plant["stages"][1][3] & flag) == (paid < due), "maintenance shortage differs")
        event[name] = {"due": due, "paid": paid, "unpaid": due - paid}
    return event


def check_spending(stages, selected, eligible, species):
    # EXTEND without space closes the tip with -ENOSPC, which is still paid.
    # Allocation/body validation is separate from the executor's spending rule.
    paid = eligible and selected["action"] != 0
    costs = ((9, 8, 7)[species] - int(selected["energy_gate"]["vigor"] > 0), (5, 5, 4)[species])
    require([stages[2][j] - stages[3][j] for j in (0, 1)] == [cost * paid for cost in costs],
            "combined winner/paid price mismatch")


def check_growth(row, resource, life, bids, body, prior_body, arm, *, priority_check=None):
    """Reuse independently implemented forecast validators with each actual birth identity."""
    tick, sun = row["tick"], resource["sun"]
    case = {"tick": life["birth_tick"], "lineage": life["id"]}
    shoots = [b for b in bids if b["tissue"] == 0]
    leader = min(shoots, key=lambda b: (-b["depth"], b["tip"])) if shoots else None
    plant = next(p for p in resource["plants"] if p["id"] == life["id"])
    require(len({b["tip"] for b in bids}) == len(bids), "duplicate bid")
    boosts, denied, unavailable = 0, 0, 0
    for b in bids:
        dawn.root.check_water(b, life, tick)
        dawn.check_dawn(b, life, tick, case, arm, sun)
        budget = b["budget"]
        require(budget["leader"] == (leader["tip"] if leader else 65535), "wrong shoot leader")
        if prior_body is not None:
            require(budget["flower"] == bool(prior_body["flowers"]), "wrong flower reservation")
        remaining = max(0, leader["maximum_depth"] - leader["depth"]) if leader and not budget["flower"] else 0
        allocating = b["action"] == 1 and b["available"] > 0
        required = b["nodes"] + (1 + remaining - int(b["tip"] == budget["leader"] and remaining > 0) if allocating else 0)
        require((budget["remaining"], budget["required"], budget["allocates"], budget["allowed"]) ==
                (remaining, required, allocating, not allocating or required <= 32), "wrong shoot budget")
        boost = (life["generation"] > 0 and tick == life["birth_tick"] and b["roots"] == 2 and
                 b["tissue"] == 1 and b["action"] == 1 and budget["allocates"] and budget["allowed"] and
                 b["water_gate"]["allowed"] and b["energy_gate"]["cost"] > 0 and
                 b["energy"] >= b["energy_gate"]["cost"])
        priority = 32767 if boost else b["raw_priority"]
        if priority_check is not None:
            priority = priority_check(b, life, tick, plant, priority)
        else:
            require('allocation' not in b, 'unexpected allocation receipt')
        require(b["raw_action"] == b["action"] and b["priority"] == priority,
                "out-of-scope birth priority")
        require(b["energy_gate"]["income"] == (plant["uptake"][0][1] if plant["uptake"] else 0) and
                [b["energy"], b["water"]] == plant["stages"][2][:2], "growth observation mismatch")
        boosts += boost
        denied += not b["dawn_gate"]["allowed"] and all(b[g]["allowed"] for g in GATES[:-1])
        unavailable += b["dawn_gate"]["active"] and b["dawn_gate"]["applies"] and not b["dawn_gate"]["estimate_available"]
    chosen = dawn.winner(bids, dawn=True)
    selected = next(b for b in bids if b["tip"] == chosen["tip"])
    allocating = chosen["eligible"] and selected["budget"]["allocates"]
    require(body["nodes"] == selected["nodes"] + allocating and
            body["roots"] == selected["roots"] + int(allocating and selected["tissue"] == 1), "combined winner/body mismatch")
    check_spending(plant["stages"], selected, chosen["eligible"], life["species"])
    before = dawn.winner(bids, dawn=False)
    changed = before != chosen
    require(not changed or arm == "candidate" and life["generation"] > 0, "out-of-scope dawn arbitration")
    return {"boosted_bids": boosts, "additional_denied": denied, "unavailable": unavailable,
            "changed_choices": int(changed)}, ({"tick": tick, "id": life["id"], "before": before, "after": chosen,
            "bids": bids, "stages": plant["stages"]} if changed else None)


def check_visits(row, resource, result, lives, living):
    tick, slots = row["tick"], row["plant_order"]
    first = ((tick - order.AT) // 60) % len(slots) if ("seed_order_probe" in result and tick > order.AT and
            tick % 60 == 0 and slots) else 0
    require(len(slots) == len(set(slots)) and len(slots) <= 8 and
            [v["id"] for v in row["reproduction"]] == slots[first:] + slots[:first] and
            living <= set(slots) <= set(lives), "reproduction order/inventory differs")
    bank = sum(s["birth_tick"] < tick < (s["end_tick"] or result["tick"] + STEP) for s in result["seeds"])
    purchases = {s["parent"] for s in result["seeds"] if s["birth_tick"] == tick}
    bought, bank_only = set(), []
    for v in row["reproduction"]:
        i = v["id"]
        blocked = (v["cooldown"] > 0, tick % 60 != 0, bank >= 8, i not in living,
                   v["stress"] > 0, v["sun"] <= 24, lives[i]["generation"] == 65535,
                   v["energy"] < v["energy_required"], v["water"] < v["water_required"], v["flower"] == 65535)
        mask = sum(1 << j for j, bit in enumerate(blocked) if bit)
        require(v["blockers"] == mask and v["produced"] == (mask == 0) and v["bank"] == bank and
                v["sun"] == resource["sun"][1], "production gates differ")
        if i in living:
            stages = next(p for p in resource["plants"] if p["id"] == i)["stages"]
            require(stages[3][:2] == [v["energy"], v["water"]] and stages[4][:2] ==
                    [v["energy"] - 48 * v["produced"], v["water"] - 24 * v["produced"]], "production debit differs")
        if v["produced"]:
            bank += 1
            bought.add(i)
        if mask == 4:
            bank_only.append(i)
    require(bought == purchases and bank == resource["bank"], "seed ledger/bank mismatch")
    return bank_only


def analyze(stand_path, adult_path, result, case, arm):
    common_result(result, case, arm)
    return analyze_receipts(stand_path, adult_path, result, arm)


def analyze_receipts(stand_path, adult_path, result, arm, *, priority_check=None):
    """Shared population accounting after the caller validates its experiment identity."""
    lives, _ = order.bank.descendants.index_records(result["lineages"], result["seeds"], 0, result["tick"])
    plants, days, previous, shapes = {}, [], {}, {}
    counts, first_choice = Counter(), None
    daily = None
    for row, resource in zip(trace_rows(stand_path, "stand", result), trace_rows(adult_path, "adult", result), strict=True):
        tick, sun = row["tick"], resource["sun"]
        require(sun[0] == (64 + tick // STEP) % 256 and
                sun[1] == dawn.previous.audit.strength(sun[0], row["climate"]["light_percent"]), "wrong light clock")
        rr, bodies = {p["id"]: p for p in resource["plants"]}, {b["id"]: b for b in row["bodies"]}
        present = {i for i, p in lives.items() if p["birth_tick"] <= tick <= (p["death_tick"] or result["tick"])}
        living = {i for i in present if lives[i]["death_tick"] != tick}
        require(len(rr) == len(resource["plants"]) and set(rr) == present and
                len(bodies) == len(row["bodies"]) and set(bodies) == living, "incomplete population census")
        if daily is None or daily["day"] != tick // DAY:
            daily = {"day": tick // DAY, "samples": 0, "living_samples": 0, "minimum_living": 8,
                     "minimum_bank": 8, "maximum_bank": 0, "last_living": []}
            days.append(daily)
        daily["samples"] += 1
        daily["living_samples"] += len(living)
        daily["minimum_living"] = min(daily["minimum_living"], len(living))
        daily["minimum_bank"] = min(daily["minimum_bank"], resource["bank"])
        daily["maximum_bank"] = max(daily["maximum_bank"], resource["bank"])
        daily["last_living"] = sorted(living)
        bids = {}
        for b in row["bids"]:
            require(b["id"] in living, "dead/absent bidder")
            bids.setdefault(b["id"], []).append(b)
        for i, p in rr.items():
            life, old = lives[i], previous.get(i)
            receipt = adults.transfers({"tick": tick, **p}, life, old["stages"][-1] if old else None)
            summary = plants.setdefault(i, {"life": life, "samples": 0, "resources": adults.budget(),
                "payments": 0, "shortages": [], "max_stress": 0, "first_flower": None,
                "body_changes": [], "last_body": None, "bank_only_visits": 0, "choices": Counter()})
            adults.accumulate(summary["resources"], receipt, summary["samples"] == 0)
            summary["samples"] += 1
            summary["max_stress"] = max(summary["max_stress"], p["stages"][-1][2])
            event = payment(p, receipt, old["roots"] if old else None, tick, sun[0])
            if event is not None:
                summary["payments"] += 1
                if event["energy"]["unpaid"] or event["water"]["unpaid"]:
                    summary["shortages"].append(event)
            if i in bodies:
                body = bodies[i]
                require((body["nodes"], body["roots"]) == (p["stages"][-1][4], p["roots"]) and
                        body["roots"] <= body["nodes"] <= 32 and body["species"] == life["species"], "body receipt mismatch")
                if i in bids:
                    counted, changed = check_growth(row, resource, life, bids[i], body, shapes.get(i), arm,
                                                    priority_check=priority_check)
                    summary["choices"].update(counted)
                    counts.update(counted)
                    if changed and first_choice is None:
                        first_choice = changed
                if body["flowers"] and summary["first_flower"] is None:
                    summary["first_flower"] = tick
                shape = {k: body[k] for k in ("nodes", "roots", "flowers", "maximum_stem_depth")} | {
                    "tips": sorted(t[1:] for t in body["tips"])}
                if shape != summary["last_body"]:
                    summary["body_changes"].append({"tick": tick, "body": shape})
                summary["last_body"] = shape
                shapes[i] = body
            previous[i] = p
        for i in check_visits(row, resource, result, lives, living):
            plants[i]["bank_only_visits"] += 1
    require(set(plants) == set(lives), "missing life history")
    return {"plants": list(plants.values()), "days": days, "choices": dict(counts), "first_choice": first_choice}


def survival(life, stop, days):
    due = life["birth_tick"] + days * DAY
    if life["death_tick"] is not None and life["death_tick"] <= min(due, stop):
        return "died"
    return "confirmed" if due <= stop else "censored"


def metrics(result, analysis):
    lives, stop = result["lineages"], result["tick"]
    offspring = [p for p in lives if p["generation"] > 0]
    credit = lambda ps, start, end: sum(max(0, min(p["death_tick"] or stop, end) - max(p["birth_tick"], start)) for p in ps)
    value = {"living": sum(p["death_tick"] is None for p in lives),
             "species": sorted({p["species"] for p in lives if p["death_tick"] is None}),
             "births": len(offspring), "seeds": len(result["seeds"]),
             "seed_parents": sum(p["seeds_created"] > 0 for p in offspring),
             "successful_parents": sum(any(c["parent"] == p["id"] and survival(c, stop, 1) == "confirmed"
                                          for c in offspring) for p in offspring),
             "founder_credit": credit([p for p in lives if p["generation"] == 0], 0, stop),
             "closing_credit": credit(lives, 222 * DAY, min(stop, 254 * DAY)),
             "survival": {str(d): dict(Counter(survival(p, stop, d) for p in offspring)) for d in (1, 16, 32)}}
    boundaries = sorted({p["death_tick"] for p in lives if p["death_tick"] is not None})
    value["first_empty_tick"] = next((t for t in boundaries if not any(
        p["birth_tick"] <= t and (p["death_tick"] is None or t < p["death_tick"]) for p in lives)), None)
    value["resources"] = {}
    for kind in KINDS:
        rows = [p for p in analysis["plants"] if (p["life"]["generation"] == 0) == (kind == "founders")]
        value["resources"][kind] = {"payments": sum(p["payments"] for p in rows), **{
            r: {"shortages": sum(e[r]["unpaid"] > 0 for p in rows for e in p["shortages"]),
                "unpaid": sum(e[r]["unpaid"] for p in rows for e in p["shortages"])} for r in ("energy", "water")}}
    return value


def comparison(a, b):
    checks = {"retain_" + k: b[k] >= a[k] for k in ("living", "seed_parents", "successful_parents", "founder_credit", "closing_credit")}
    checks["retain_species"] = set(a["species"]) <= set(b["species"])
    for d in ("1", "32"):
        checks["retain_" + d + "_day_survivors"] = b["survival"][d].get("confirmed", 0) >= a["survival"][d].get("confirmed", 0)
    checks["no_earlier_empty"] = b["first_empty_tick"] is None or a["first_empty_tick"] is not None and b["first_empty_tick"] >= a["first_empty_tick"]
    rates = {}
    for r in ("energy", "water"):
        x, y = a["resources"]["offspring"], b["resources"]["offspring"]
        delta = y[r]["unpaid"] * x["payments"] - x[r]["unpaid"] * y["payments"]
        rates[r] = None if not x["payments"] or not y["payments"] else (delta > 0) - (delta < 0)
        checks["no_worse_" + r + "_rate"] = rates[r] is not None and rates[r] <= 0
    return {"checks": checks, "unpaid_rate_comparison": rates, "passes_harm_screen": all(checks.values()),
            "improves_rate": any(v == -1 for v in rates.values())}


def matched_births(a, b):
    def index(result):
        keys = {}
        for p in result["lineages"]:
            keys[p["id"]] = (keys[p["parent"]] if p["parent"] else (), p["birth_tick"], p["column"], p["species"])
        require(len(set(keys.values())) == len(keys), "ambiguous ancestry/site identity")
        return {key: i for i, key in keys.items()}
    x, y = index(a), index(b)
    return {"matched": [[x[k], y[k]] for k in sorted(x.keys() & y.keys())],
            "control_only": sorted(x[k] for k in x.keys() - y.keys()),
            "candidate_only": sorted(y[k] for k in y.keys() - x.keys())}


def first_effect(directory, case, arms):
    target = arms["candidate"]["analysis"]["first_choice"]
    streams = [[trace_rows(directory / arms[a]["runs"]["trace"]["traces"][k]["path"], k, arms[a]["result"])
                for k in ("stand", "adult")] for a in ARMS]
    histories = [zip(*pair, strict=True) for pair in streams]
    try:
        for (s, r), (t, q) in zip(*histories, strict=True):
            require(dawn.strip_dawn([s])[0]["bids"] == dawn.strip_dawn([t])[0]["bids"], "different bids before first effect")
            if target and s["tick"] == target["tick"]:
                require(s["climate"] == t["climate"] and r["sun"] == q["sun"] and
                        [(p["id"], p["stages"][:3]) for p in r["plants"]] ==
                        [(p["id"], p["stages"][:3]) for p in q["plants"]], "first effect has unequal pre-action state")
                return {"tick": s["tick"], "matching_prior_samples": s["tick"] // STEP - 1,
                        "control": {"stand": s, "adult": r}, "candidate": {"stand": t, "adult": q}}
            require(dawn.strip_dawn([s]) == dawn.strip_dawn([t]) and r == q, "physical prefix mismatch")
        require(target is None, "missing first effect")
        return None
    finally:
        # Closing the row generators releases files even when stopping at first divergence.
        for pair in streams:
            for stream in pair:
                stream.close()


def check_analysis(analysis, result):
    lives = {p["id"]: p for p in result["lineages"]}
    require(len(analysis["plants"]) == len(lives) and {p["life"]["id"] for p in analysis["plants"]} == set(lives), "missing summarized plant")
    for p in analysis["plants"]:
        life = p["life"]
        require(life == lives[life["id"]], "summary life differs")
        end = life["death_tick"] or result["tick"]
        start = max(STEP, life["birth_tick"])
        require(p["samples"] == (end - start) // STEP + 1 and p["payments"] ==
                end // 60 - life["birth_tick"] // 60, "incomplete resource coverage")
        require(len({e["tick"] for e in p["shortages"]}) == len(p["shortages"]) and all(
                start <= e["tick"] <= end and e["tick"] % 60 == 0 and
                e["phase"] == (64 + e["tick"] // STEP) % 256 and 0 <= e["roots"] <= e["nodes"] <= 32 and
                e["energy"]["due"] == (e["nodes"] + 7) // 8 and
                e["water"]["due"] == (e["nodes"] - e["roots"] + 7) // 8 and
                any(e[r]["unpaid"] > 0 for r in ("energy", "water")) and all(
                    e[r]["due"] == e[r]["paid"] + e[r]["unpaid"] and min(e[r].values()) >= 0
                    for r in ("energy", "water")) for e in p["shortages"]), "invalid shortage summary")
        for r, budget in p["resources"].items():
            require(budget["initial"] + budget["income"] == sum(v for k, v in budget.items() if k not in ("initial", "income")) and
                    all(type(v) is int and v >= 0 for v in budget.values()) and
                    budget["reproduction"] == (48 if r == "energy" else 24) * life["seeds_created"], "unbalanced lifetime budget")
    require(sum(d["samples"] for d in analysis["days"]) == result["tick"] // STEP and
            analysis["days"][-1]["last_living"] == sorted(p["id"] for p in lives.values() if p["death_tick"] is None), "wrong daily coverage")
    require(dict(sum((Counter(p["choices"]) for p in analysis["plants"]), Counter())) ==
            {k: v for k, v in analysis["choices"].items() if v}, "choice totals differ")


def check_effect(entry):
    effect = entry["first_effect"]
    target = entry["arms"]["candidate"]["analysis"]["first_choice"]
    require((effect is None) == (target is None), "missing/extra first effect")
    if effect is None:
        a, b = [entry["arms"][arm] for arm in ARMS]
        require(common_result(a["result"], entry["case"], "control") ==
                common_result(b["result"], entry["case"], "candidate"), "unchanged choices changed endpoint")
        return
    require(effect["tick"] == target["tick"] and effect["matching_prior_samples"] == target["tick"] // STEP - 1,
            "wrong first-effect boundary")
    a, b = [effect[arm] for arm in ARMS]
    require(dawn.strip_dawn([a["stand"]])[0]["bids"] == dawn.strip_dawn([b["stand"]])[0]["bids"] and
            a["stand"]["climate"] == b["stand"]["climate"] and a["adult"]["sun"] == b["adult"]["sun"] and
            [(p["id"], p["stages"][:3]) for p in a["adult"]["plants"]] ==
            [(p["id"], p["stages"][:3]) for p in b["adult"]["plants"]], "unequal first-effect observations")
    for arm, step in (("control", a), ("candidate", b)):
        life = next(p for p in entry["arms"][arm]["result"]["lineages"] if p["id"] == target["id"])
        bids = [bid for bid in step["stand"]["bids"] if bid["id"] == target["id"]]
        body = next(p for p in step["stand"]["bodies"] if p["id"] == target["id"])
        _, change = check_growth(step["stand"], step["adult"], life, bids, body, None, arm)
        require(change == (target if arm == "candidate" else None), "wrong first-effect choice")


def check_value(value):
    require(value["rule"] == RULE and value["inputs"] == INPUTS and value["model"] == load_model()[0] and
            value["full_replays"] == 32 and value["training_runs"] == 0 and
            value["protocol_sha256"] == experiment.digest(ROOT / PROTOCOL) and
            value["source_sha256"][PROTOCOL] == value["protocol_sha256"], "wrong population provenance")
    audit = value["prior_seed_audit"]
    require(audit["seeds"] == list(FRESH) and audit["matches"] == [] and bool(audit["files"]) and
            all(value["source_sha256"].get(p) == sha for p, sha in audit["files"].items()), "wrong fresh-seed audit")
    for case, entry in zip(CASES, value["cases"], strict=True):
        require(entry["case"] == case and set(entry["arms"]) == set(ARMS), "wrong population panel")
        for arm, a in entry["arms"].items():
            common_result(a["result"], case, arm)
            require(a["result"]["tick"] == STOP and set(a["runs"]) == set(LABELS), "wrong horizon/repeat")
            check_analysis(a["analysis"], a["result"])
            require(a["metrics"] == metrics(a["result"], a["analysis"]), "population metrics differ")
            for label, run in a["runs"].items():
                require(run["args"] == arguments(case, arm, label) and run["result"] == a["result"], "wrong call/repeat")
            x, y = [a["runs"][label] for label in LABELS]
            require(x["frame"]["sha256"] == y["frame"]["sha256"] and all(x["traces"][k]["sha256"] ==
                    y["traces"][k]["sha256"] for k in ("stand", "adult")), "repeat artifacts differ")
        a, b = [entry["arms"][arm] for arm in ARMS]
        require(entry["comparison"] == comparison(a["metrics"], b["metrics"]) and
                entry["birth_matching"] == matched_births(a["result"], b["result"]), "paired comparison differs")
        check_effect(entry)
    require(value["summary"] == summarize(value["cases"]), "population summary differs")


def summarize(cases):
    return {role: {"cases": len(rows), "harm_passes": sum(r["comparison"]["passes_harm_screen"] for r in rows),
                   "improved_rate_pairs": sum(r["comparison"]["improves_rate"] for r in rows)}
            for role in ("diagnostic", "fresh") if (rows := [r for r in cases if r["case"]["role"] == role])} | {
        "passes_screen": all(r["comparison"]["passes_harm_screen"] for r in cases) and
        any(r["case"]["role"] == "fresh" and r["comparison"]["improves_rate"] for r in cases)}


def prior_seed_audit():
    files = {}
    for path in sorted((ROOT / "benchmarks").rglob("*.json*")):
        if not path.name.endswith((".json", ".json.gz")) or path.name.startswith("landing-population-"):
            continue
        with (gzip.open(path, "rt") if path.suffix == ".gz" else path.open()) as stream:
            text = stream.read()
        require(not any(seed in text or str(int(seed, 16)) in text for seed in FRESH), "fresh seed already recorded")
        files[str(path.relative_to(ROOT))] = experiment.digest(path)
    return {"seeds": list(FRESH), "files": files, "matches": []}


def collect(build, out, jobs):
    require(not out.exists() and (out.is_relative_to(ROOT / "artifacts") or not out.is_relative_to(ROOT)), "fresh external/artifact directory required")
    metadata, model = load_model()
    cache_path, binary = build / "CMakeCache.txt", build / "toy-factory-garden-landing"
    settings = order.previous.placement.budget.growth.water.check_build(cache_path)
    sources, audit = experiment.source_files(), prior_seed_audit()
    out.mkdir(parents=True)
    (out / "bin").mkdir()
    (out / "frames").mkdir()
    frozen = out / "bin/garden-landing"
    shutil.copy2(binary, frozen)
    shutil.copy2(cache_path, out / "CMakeCache.txt")
    shutil.copy2(ROOT / PROTOCOL, out / "protocol.md")
    experiment.snapshot_sources(out, sources)
    with (out / "model.tgl").open("xb") as stream:
        stream.write(model)
    value = {"rule": RULE, "inputs": INPUTS, "model": metadata, "full_replays": 32, "training_runs": 0,
             "protocol_sha256": experiment.digest(out / "protocol.md"), "source_sha256": sources,
             "prior_seed_audit": audit, "settings": settings,
             "build": {"binary": experiment.digest(frozen), "cache": experiment.digest(cache_path)}, "cases": []}
    calls = [(c, a, label) for c in CASES for a in ARMS for label in LABELS]
    def capture(call):
        case, arm, label = call
        args = arguments(case, arm, label)
        name = stem(case, arm, label)
        result = order.training.native(frozen, out, *args)
        experiment.write_json(out / (name + ".json"), result)
        frame_path = args[args.index("--framebuffer") + 1]
        raw = (out / frame_path).read_bytes()
        require(len(raw) == 240 * 240 * 2 and f"{zlib.crc32(raw):08x}" == result["framebuffer_crc32"], "wrong framebuffer")
        traces = {}
        for kind in ("stand", "adult"):
            path = out / (name + "-" + kind + ".jsonl")
            target = path.with_suffix(".jsonl.gz")
            experiment.compress(path, target)
            traces[kind] = {"path": target.name, "sha256": experiment.digest(target)}
        print(name + ": captured", flush=True)
        return {"args": args, "result": result, "frame": {"path": frame_path, "sha256": experiment.digest(out / frame_path)}, "traces": traces}
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        captured = list(pool.map(capture, calls))
    iterator, gallery = iter(captured), []
    for case in CASES:
        arms, images = {}, []
        for arm in ARMS:
            runs = dict(zip(LABELS, (next(iterator), next(iterator)), strict=True))
            run = runs["trace"]
            analysis = analyze(*(out / run["traces"][k]["path"] for k in ("stand", "adult")), run["result"], case, arm)
            arms[arm] = {"runs": runs, "result": run["result"], "analysis": analysis, "metrics": metrics(run["result"], analysis)}
            images.append({"id": stem(case, arm, "trace"), "framebuffer": run["frame"]["path"]})
            print(case["id"] + " / " + arm + ": full receipts verified", flush=True)
        entry = {"case": case, "arms": arms, "comparison": comparison(*(arms[a]["metrics"] for a in ARMS)),
                 "birth_matching": matched_births(*(arms[a]["result"] for a in ARMS)), "first_effect": first_effect(out, case, arms)}
        value["cases"].append(entry)
        gallery.append(images)
    value["summary"] = summarize(value["cases"])
    value["gallery"] = contact_sheet(out, gallery)
    check_value(value)
    require(experiment.source_files() == sources and experiment.digest(binary) == value["build"]["binary"] and
            experiment.digest(cache_path) == value["build"]["cache"], "sources/build changed during capture")
    experiment.write_json(out / "results.json", value)
    experiment.compress(out / "results.json", out / "results.json.gz")
    experiment.write_json(out / "manifest.json", {"rule": RULE, "artifacts": {
        str(p.relative_to(out)): experiment.digest(p) for p in sorted(out.rglob("*")) if p.is_file()}})
    return value


def verify(path):
    if path.is_dir():
        manifest = experiment.read_json(path / "manifest.json")
        require(manifest["rule"] == RULE, "wrong bundle rule")
        for name in manifest["artifacts"]:
            artifact(path, manifest, name)
        with gzip.open(artifact(path, manifest, "results.json.gz"), "rt") as stream:
            value = json.load(stream)
        check_value(value)
        require(manifest["artifacts"]["bin/garden-landing"] == value["build"]["binary"] and
                manifest["artifacts"]["CMakeCache.txt"] == value["build"]["cache"] and
                manifest["artifacts"]["protocol.md"] == value["protocol_sha256"] and
                manifest["artifacts"]["model.tgl"] == MODEL_SHA, "bundle provenance differs")
        with tarfile.open(path / "source.tar.gz", "r:gz") as archive:
            require({m.name for m in archive.getmembers()} == set(value["source_sha256"]), "source archive inventory differs")
            for name, sha in value["source_sha256"].items():
                with archive.extractfile(name) as stream:
                    require(hashlib.file_digest(stream, "sha256").hexdigest() == sha, "archived source changed: " + name)
        for entry in value["cases"]:
            for arm, a in entry["arms"].items():
                for label, r in a["runs"].items():
                    require(experiment.read_json(path / (stem(entry["case"], arm, label) + ".json")) == r["result"], "saved native JSON differs")
                    for item in [r["frame"], *r["traces"].values()]:
                        require(manifest["artifacts"][item["path"]] == item["sha256"], "run/manifest hash mismatch")
                run = a["runs"]["trace"]
                require(analyze(*(artifact(path, manifest, run["traces"][k]["path"]) for k in ("stand", "adult")),
                                a["result"], entry["case"], arm) == a["analysis"], "raw analysis differs")
            require(first_effect(path, entry["case"], entry["arms"]) == entry["first_effect"], "first-effect evidence differs")
            print(entry["case"]["id"] + ": raw verified", flush=True)
    else:
        with gzip.open(path, "rt") as stream:
            value = json.load(stream)
        check_value(value)
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path, default=ROOT / "build-host")
    parser.add_argument("--out", type=Path, default=ROOT / "artifacts/garden-landing-population-v1")
    parser.add_argument("--jobs", type=int, choices=range(1, 5), default=2)
    parser.add_argument("--verify", type=Path)
    args = parser.parse_args()
    value = verify(args.verify.resolve()) if args.verify else collect(args.build.resolve(), args.out.resolve(), args.jobs)
    print(json.dumps(value["summary"], indent=2))


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError, KeyError, OSError, StopIteration) as error:
        print(f"population screen failed: {error}", file=sys.stderr)
        sys.exit(1)
