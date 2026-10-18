#!/usr/bin/env python3
"""Audit saved energy forecasts at maintenance increases; never run a simulator."""

from __future__ import annotations

import argparse
from collections import Counter
from functools import cache
import gzip
import hashlib
import json
from pathlib import Path
import sys
import tarfile

import garden_landing_root_energy as previous
from garden_experiments import digest, snapshot_sources, source_files, write_json
from garden_resources import require

ROOT, DAY, STEP = previous.ROOT, previous.DAY, previous.STEP
RULE = "garden-landing-energy-audit-v1"
INPUT = "benchmarks/garden-seasons/landing-root-energy-results.json.gz"
INPUT_SHA = "dca98970b1efbd6552df4796c280fcb0883bc959f226d569531353a760abe778"
PROTOCOL = "benchmarks/garden-seasons/landing-energy-audit-protocol.md"
TRANSFER_FIELDS = ("income", "upkeep", "growth", "reproduction", "overflow", "discarded")
BUNDLE_FILES = {"results.json.gz", "source.tar.gz", "source.patch"}


@cache
def load_input():
    value = previous.prior.load(ROOT / INPUT, INPUT_SHA)
    previous.check_value(value)
    return value


def identity(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def phase_band(phase):
    return "before-noon" if phase < 64 else "noon-or-afternoon" if phase < 128 else "night"


def select_bid(step):
    bids = step["bids"]
    eligible = [b for b in bids if b["budget"]["allowed"] and b["water_gate"]["allowed"] and b["energy_gate"]["allowed"]]
    return (max(eligible or bids, key=lambda b: b["priority"]), bool(eligible)) if bids else (None, False)


def check_history(case, arm, analysis):
    focal = analysis["focal"]
    steps = focal["steps"] + analysis["followup_steps"]
    life = focal["life"]
    last = min(case["tick"] + 2 * DAY, life["death_tick"] or previous.STOP)
    require([s["tick"] for s in steps] == list(range(case["tick"], last + STEP, STEP)), "incomplete focal history")
    before, receipts = None, []
    for step in steps:
        require(step["plant"]["id"] == life["id"] and step["plant"]["birth"] == life["birth_tick"] and
                step["sun"][0] == (64 + step["tick"] // STEP) % 256, "wrong focal identity/clock")
        receipt = previous.adults.transfers({"tick": step["tick"], **step["plant"]}, life, before)
        receipts.append(receipt["energy"])
        before = step["plant"]["stages"][-1]
        previous.check_bids({"tick": step["tick"], "bids": step["bids"],
                            "bodies": [step["body"]] if step["body"] else []},
                           {"plants": [step["plant"]]}, {life["id"]: life}, case, arm)
        for bid in step["bids"]:
            previous.root.check_water(bid, life, step["tick"])
    return steps, receipts


def window(steps, receipts, life, index, target, *, after_growth):
    """Actual transfers only; death or missing samples never become invented future income."""
    tick = steps[index]["tick"]
    require(target > tick and target % STEP == 0, "invalid forecast endpoint")
    stage = 3 if after_growth else 4
    initial = steps[index]["plant"]["stages"][stage][0]
    total = dict.fromkeys(TRANSFER_FIELDS, 0)
    total["reproduction"] = receipts[index]["reproduction"] if after_growth else 0
    observed = index
    shortages = []
    for j in range(index + 1, len(steps)):
        if steps[j]["tick"] > target:
            break
        require(steps[j]["tick"] == steps[observed]["tick"] + STEP, "window has a missing sample")
        observed = j
        for name in TRANSFER_FIELDS:
            total[name] += receipts[j][name]
        s = steps[j]
        if s["tick"] % (4 * STEP) == 0 and s["plant"]["stages"][1][3] & 2:
            shortages.append(s["tick"])
    observed_tick = steps[observed]["tick"]
    death = life["death_tick"]
    status = "dead" if death is not None and death <= observed_tick else "alive" if observed_tick == target else "censored"
    final = steps[observed]["plant"]["stages"][-1][0]
    require(initial + total["income"] == final + sum(total[k] for k in TRANSFER_FIELDS if k != "income"), "forecast window budget differs")
    return {"start_tick": tick, "target_tick": target, "observed_tick": observed_tick,
            "status": status, "initial": initial, "final": final, "transfers": total,
            "energy_shortages": shortages, "samples_after_start": observed - index}


def paid_event(steps, receipts, life, index, bid):
    step, e = steps[index], bid["energy_gate"]
    tick, phase = step["tick"], step["sun"][0]
    require(bid["action"] != 0 and phase < 128 and e["cost"] > 0 and
            receipts[index]["growth"] == e["cost"] and
            step["plant"]["stages"][2][0] == bid["energy"] and
            step["plant"]["stages"][3][0] == bid["energy"] - e["cost"] and
            step["plant"]["stages"][2][1] - step["plant"]["stages"][3][1] == bid["water_gate"]["cost"] and
            step["body"]["nodes"] == e["post_nodes"], "paid action/price/body differs")
    sunset = window(steps, receipts, life, index, tick + (128 - phase) * STEP, after_growth=True)
    after_cost = bid["energy"] - e["cost"]
    uncapped = after_cost + e["daylight_credit"] - e["daylight_upkeep"]
    cap_loss = max(0, uncapped - 256)
    require(e["projected_sunset"] == uncapped - cap_loss, "forecast cap differs")
    error, night = None, None
    covers_night = None
    if sunset["status"] == "alive":
        actual = sunset["transfers"]
        terms = {"income": e["daylight_credit"] - actual["income"],
                 "maintenance": actual["upkeep"] - e["daylight_upkeep"],
                 "later_growth": actual["growth"], "reproduction": actual["reproduction"],
                 "overflow": actual["overflow"], "discard": actual["discarded"], "forecast_cap": -cap_loss}
        error = {"predicted_minus_actual": e["projected_sunset"] - sunset["final"], "terms": terms}
        require(sum(terms.values()) == error["predicted_minus_actual"], "prediction error decomposition differs")
        covers_night = sunset["final"] >= e["night_upkeep"]
        sunset_index = index + sunset["samples_after_start"]
        night = window(steps, receipts, life, sunset_index, sunset["target_tick"] + 128 * STEP, after_growth=False)
    maintenance_before = max(1, (bid["nodes"] + 7) // 8)
    threshold = e["maintenance"] > maintenance_before
    require(not threshold or (bid["nodes"] in (8, 16, 24) and e["post_nodes"] == bid["nodes"] + 1), "unexpected maintenance increase")
    cash_margin = after_cost - e["daylight_upkeep"] - e["night_upkeep"]
    return {"tick": tick, "phase": phase, "phase_band": phase_band(phase),
            "bid": bid, "maintenance_before": maintenance_before, "step_up": threshold,
            "cash_only_margin": cash_margin, "cash_only_allows": cash_margin >= 0 and after_cost >= e["maintenance"],
            "required_future_income": max(0, -cash_margin), "sunset": sunset, "error": error, "night": night,
            "sunset_covers_nominal_night": covers_night,
            "no_later_paid_growth": sunset["transfers"]["growth"] == 0,
            "clean_interval": sunset["status"] == "alive" and not sunset["energy_shortages"] and
                all(sunset["transfers"][k] == 0 for k in ("growth", "reproduction", "overflow", "discarded"))}


def opportunities(step, executed):
    # All allocating bids for this one plant have the same energy forecast, but
    # keep every otherwise eligible tip rather than counting one forecast per tip.
    bids = [b for b in step["bids"] if b["action"] == 1 and b["budget"]["allocates"] and
            b["nodes"] in (8, 16, 24) and b["budget"]["allowed"] and b["water_gate"]["allowed"]]
    if not bids:
        return None
    e = bids[0]["energy_gate"]
    require(all(b["energy_gate"] == e for b in bids), "same-state allocation energy forecasts differ")
    winner, eligible = select_bid(step)
    raw_eligible = [b for b in step["bids"] if b["budget"]["allowed"] and b["water_gate"]["allowed"]]
    ungated = max(raw_eligible, key=lambda b: b["priority"])
    return {"tick": step["tick"], "phase_band": phase_band(step["sun"][0]),
            "nodes": bids[0]["nodes"], "tips": [b["tip"] for b in bids],
            "forecast": e, "executed_step_up": bool(executed and executed["step_up"]),
            "selected_tip": winner["tip"], "selected_eligible": eligible,
            "energy_rejects_opportunity": e["active"] and not e["allowed"],
            "energy_changes_winner": winner["tip"] != ungated["tip"] or not eligible}


def summarize(histories):
    result = {"histories": len(histories), "paid_events": 0, "opportunities": 0, "energy_rejected_opportunities": 0,
              "step_ups": 0, "by_threshold": Counter(), "by_phase": {}, "by_case": {}, "opportunities_by_phase": {}}
    for history in histories:
        result["paid_events"] += len(history["events"])
        result["opportunities"] += len(history["opportunities"])
        result["energy_rejected_opportunities"] += sum(o["energy_rejects_opportunity"] for o in history["opportunities"])
        for chance in history["opportunities"]:
            counts = result["opportunities_by_phase"].setdefault(chance["phase_band"], Counter())
            counts["decisions"] += 1
            counts["executed"] += chance["executed_step_up"]
            counts["energy_rejected"] += chance["energy_rejects_opportunity"]
            counts["energy_changes_winner"] += chance["energy_changes_winner"]
        result["by_case"][history["id"]] = len([e for e in history["events"] if e["step_up"]])
        for event in history["events"]:
            if not event["step_up"]:
                continue
            result["step_ups"] += 1
            result["by_threshold"][str(event["bid"]["energy_gate"]["post_nodes"])] += 1
            counts = result["by_phase"].setdefault(event["phase_band"], Counter())
            counts["events"] += 1
            counts["forecast_allowed"] += event["bid"]["energy_gate"]["forecast_allowed"]
            counts["cash_only_allowed"] += event["cash_only_allows"]
            counts["confirmed_first_day"] += history["first_day_status"] == "confirmed"
            counts["cash_only_rejects_confirmed"] += not event["cash_only_allows"] and history["first_day_status"] == "confirmed"
            counts["sunset_" + event["sunset"]["status"]] += 1
            if event["error"] is not None:
                counts["income_overestimated"] += event["error"]["terms"]["income"] > 0
                counts["sunset_below_nominal_night"] += not event["sunset_covers_nominal_night"]
                counts["permitted_below_nominal_night"] += event["bid"]["energy_gate"]["forecast_allowed"] and not event["sunset_covers_nominal_night"]
                counts["night_" + event["night"]["status"]] += 1
            counts["clean_interval"] += event["clean_interval"]
    return json.loads(json.dumps(result, sort_keys=True))


def analyze(data):
    require([entry["case"] for entry in data["cases"]] == list(previous.CASES), "wrong audit panel")
    histories, seen = [], {}
    for entry in data["cases"]:
        case = entry["case"]
        require(set(entry["arms"]) == set(previous.ARMS), "missing audit arm")
        for arm in previous.ARMS:
            a = entry["arms"][arm]["analysis"]
            steps, receipts = check_history(case, arm, a)
            name, life = case["id"] + "/" + arm, a["focal"]["life"]
            captured_identity = identity({"life": life, "steps": previous.strip_energy(steps)})
            canonical = seen.setdefault(captured_identity, name)
            events, chances = [], []
            for index, step in enumerate(steps):
                if step["tick"] >= case["tick"] + DAY:
                    break
                bid, eligible = select_bid(step)
                event = None
                if receipts[index]["growth"]:
                    require(bid is not None and eligible, "paid an ineligible/missing winner")
                    event = paid_event(steps, receipts, life, index, bid)
                    events.append(event)
                chance = opportunities(step, event)
                if chance is not None:
                    chances.append(chance)
            histories.append({"id": name, "case": case, "arm": arm, "life": life,
                "captured_history_sha256": captured_identity, "canonical_history": canonical,
                "first_day_status": a["focal"]["first_day"]["status"], "saved_samples": len(steps),
                "events": events, "opportunities": chances})
    return {"histories": histories, "all_histories": summarize(histories),
            "unique_histories": summarize([h for h in histories if h["canonical_history"] == h["id"]])}


def check_value(value):
    require(value["rule"] == RULE and value["input_sha256"] == INPUT_SHA and
            digest(ROOT / INPUT) == INPUT_SHA and
            value["protocol_sha256"] == digest(ROOT / PROTOCOL) and value["native_calls"] == value["training_runs"] == 0 and
            value["source_sha256"].get(PROTOCOL) == value["protocol_sha256"] and
            value["source_sha256"].get(INPUT) == INPUT_SHA and
            value["analysis"] == analyze(load_input()), "saved energy audit differs")


def archived_sources(path):
    sources = {}
    with tarfile.open(path, "r:gz") as archive:
        for member in archive.getmembers():
            name = Path(member.name)
            require(member.isfile() and not name.is_absolute() and ".." not in name.parts and
                    member.name not in sources, "invalid audit source archive")
            with archive.extractfile(member) as stream:
                sources[member.name] = hashlib.sha256(stream.read()).hexdigest()
    return sources


def export(out, *, experiment=None):
    spec = experiment or sys.modules[__name__]
    require(not out.exists() and (out.is_relative_to(ROOT / "artifacts") or not out.is_relative_to(ROOT)), "fresh output required")
    source = source_files()
    value = {"rule": spec.RULE, "input_sha256": spec.INPUT_SHA, "protocol_sha256": digest(ROOT / spec.PROTOCOL),
             "native_calls": 0, "training_runs": 0, "source_sha256": source, "analysis": spec.analyze(spec.load_input())}
    spec.check_value(value)
    require(digest(ROOT / spec.INPUT) == spec.INPUT_SHA and source_files() == source, "audit source/input changed")
    out.mkdir(parents=True)
    snapshot_sources(out, source)
    require(archived_sources(out / "source.tar.gz") == source and source_files() == source,
            "source changed during snapshot")
    previous.order.recovery.founders.write_gzip(out / "results.json.gz", value)
    write_json(out / "manifest.json", {"rule": spec.RULE, "status": "complete", "artifacts": {
        str(p.relative_to(out)): digest(p) for p in sorted(out.rglob("*")) if p.is_file()}})
    print("Audited ten saved histories, including duplicates, with zero native calls.")


def verify(path, *, experiment=None):
    spec = experiment or sys.modules[__name__]
    bundle = path if path.is_dir() else None
    if path.is_dir():
        manifest = json.loads((path / "manifest.json").read_text())
        require(manifest["rule"] == spec.RULE and manifest["status"] == "complete" and
                set(manifest["artifacts"]) == BUNDLE_FILES, "incomplete/wrong audit bundle")
        for name in manifest["artifacts"]:
            previous.root.artifact(path, manifest, name)
        path = path / "results.json.gz"
    with gzip.open(path, "rt") as stream:
        value = json.load(stream)
    spec.check_value(value)
    if bundle is not None:
        require(archived_sources(bundle / "source.tar.gz") == value["source_sha256"], "audit source snapshot differs")
    print("Verified saved decisions, sunset budgets, forecast errors and duplicate accounting; no simulation.")
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--out", type=Path)
    mode.add_argument("--verify", type=Path)
    args = parser.parse_args()
    try:
        if args.out:
            export(args.out.resolve())
        else:
            verify(args.verify.resolve())
        return 0
    except (OSError, RuntimeError, ValueError, KeyError, TypeError, StopIteration, tarfile.TarError) as error:
        print("energy audit failed: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
