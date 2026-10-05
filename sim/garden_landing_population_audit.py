#!/usr/bin/env python3
"""Explain one saved population regression; extract receipts without running a simulator."""

from __future__ import annotations

import argparse
from functools import cache
import gzip
import json
from pathlib import Path
import sys

import garden_landing_population as population
import garden_landing_light_audit as light
from garden_landing_energy_audit import archived_sources
from garden_experiments import digest, snapshot_sources, source_files, write_json
from garden_resources import require

ROOT, DAY, STEP, STOP = population.ROOT, population.DAY, population.STEP, population.STOP
RULE = "garden-landing-population-audit-v1"
INPUT = "benchmarks/garden-seasons/landing-population-results.json.gz"
INPUT_SHA = "c823c7b9d1c19d476403a5741a6ff25996ad60847f4340e2207ba2260091fa2a"
MANIFEST_SHA = "9e6322e3ae8709c94f7c4d6d762783214a735b9104848b3ccc5e3a4f7a15a58a"
PROTOCOL = "benchmarks/garden-seasons/landing-population-audit-protocol.md"
CASE_IDS = ("f7ee4528-fixed", "f7ee4528-rotating")
RESOURCES = {"energy": 256, "water": 512}
CAPTURE_SOURCES = {
    "src/garden_world.c": "6fb1395fa0a5f66efab00cbdcc54654f0215c2e64537044b98ce712f60917ce9",
    "src/garden_light.c": "5f5cf18c5f9079976ffce06e8b39627dd2a4f5ccf78dad31338f7e3fbff7e3bb",
    "sim/garden_reserve_policy.c": "13a0c817f7f3b068f14e10b31d5f1a037b7c884394cd95aff4473de5a4a8db77",
    "sim/garden_landing_root_choice.c": "5018c4e8bc434a68e102c31a586b1cce8686d2352e87e5088a765cc486d36aef",
    "sim/garden_landing_plant_trace.c": "da587bf44e125d9adb506ae07f9de61facd9962808c20a84e5472d656720d2cc",
}


@cache
def load_input():
    require(digest(ROOT / INPUT) == INPUT_SHA, "population input changed")
    with gzip.open(ROOT / INPUT, "rt") as stream:
        data = json.load(stream)
    population.check_value(data)
    require(all(data["source_sha256"].get(k) == v for k, v in CAPTURE_SOURCES.items()),
            "unsupported captured accounting sources")
    require(all(data["settings"].get(k) == "OFF" for k in (
        "TOY_FACTORY_GARDEN_WATER_HEADROOM", "TOY_FACTORY_GARDEN_LEAF_MAINTENANCE",
        "TOY_FACTORY_GARDEN_CANOPY_TRANSMISSION", "TOY_FACTORY_GARDEN_SEED_RESERVE")),
        "unsupported captured resource experiment")
    return data


def cases():
    return [c for c in load_input()["cases"] if c["case"]["id"] in CASE_IDS]


def age_band(tick, birth):
    age = tick - birth
    require(age >= 0, "negative age")
    return "through_1_day" if age <= DAY else "through_16_days" if age <= 16 * DAY else "older"


def intervals(summary):
    """Union the preceding and current solar day for EVERY shortage, plus focal life."""
    life = summary["life"]
    born, end = max(STEP, life["birth_tick"]), life["death_tick"] or STOP
    windows = []
    for event in summary["shortages"]:
        tick = event["tick"]
        dawn = tick - ((64 + tick // STEP) % 256) * STEP
        windows.append((max(born, dawn - DAY), min(end, dawn + DAY - STEP)))
    if life["id"] == 9:
        windows.append((born, end))
    merged = []
    for start, stop in sorted(windows):
        require(born <= start <= stop <= end, "invalid selected interval")
        if merged and start <= merged[-1][1] + STEP:
            merged[-1][1] = max(stop, merged[-1][1])
        else:
            merged.append([start, stop])
    return merged


def required_opening(samples, capacity, spending):
    """Minimum capped balance for frozen income/body/demands, NOT a world replay."""
    names = ("income", "due", "growth", "reproduction")
    require(type(capacity) is int and capacity > 0 and
            spending in ("all", "no_reproduction", "maintenance_only"), "invalid funding mode")
    require(all(type(s[k]) is int and s[k] >= 0 for s in samples for k in names), "invalid funding sample")
    required = 0
    for s in reversed(samples):
        cost = s["due"] + (s["growth"] if spending != "maintenance_only" else 0)
        cost += s["reproduction"] if spending == "all" else 0
        after_uptake = required + cost
        if after_uptake > capacity:
            return None
        required = max(0, after_uptake - s["income"])
    return required


def birth_keys(result):
    keys = {}
    for p in result["lineages"]:
        keys[p["id"]] = (keys[p["parent"]] if p["parent"] else (),
                         p["birth_tick"], p["column"], p["species"])
    require(len(set(keys.values())) == len(keys), "ambiguous ancestry/site identity")
    return keys


def ledger_events(result, kind):
    keys, events = birth_keys(result), {}
    for p in result["seeds"] if kind == "seed_purchase" else result["lineages"]:
        tick = p["death_tick"] if kind == "death" else p["birth_tick"]
        if tick is None:
            continue
        identity = ((keys[p["parent"]], p["column"], p["species"], p["generation"])
                    if kind == "seed_purchase" else keys[p["id"]])
        # Future germination/expiry is deliberately NOT part of a seed purchase.
        events.setdefault(tick, []).append(json.dumps(identity, separators=(",", ":")))
    return {t: sorted(v) for t, v in events.items()}


def first_ledger_difference(control, candidate, kind):
    a, b = ledger_events(control, kind), ledger_events(candidate, kind)
    for tick in sorted(a.keys() | b.keys()):
        if a.get(tick, []) != b.get(tick, []):
            return {"tick": tick, "control": [json.loads(v) for v in a.get(tick, [])],
                    "candidate": [json.loads(v) for v in b.get(tick, [])]}
    return None


def cohort_totals(entry, arm):
    matched = {pair[population.ARMS.index(arm)] for pair in entry["birth_matching"]["matched"]}
    grouped = {}
    for name in ("founders", "matched_offspring", "unmatched_offspring"):
        plants = [p for p in entry["arms"][arm]["analysis"]["plants"] if
                  ("founders" if p["life"]["generation"] == 0 else
                   "matched_offspring" if p["life"]["id"] in matched else "unmatched_offspring") == name]
        payments = sum(p["payments"] for p in plants)
        grouped[name] = {"ids": [p["life"]["id"] for p in plants], "payments": payments}
        for r in RESOURCES:
            events = [(p["life"], e) for p in plants for e in p["shortages"] if e[r]["unpaid"]]
            units = sum(e[r]["unpaid"] for _, e in events)
            grouped[name][r] = {"bills": len(events), "unpaid": units,
                "units_per_1000_payments": 1000 * units / payments if payments else None,
                "unpaid_by_age": {band: sum(e[r]["unpaid"] for p, e in events
                    if age_band(e["tick"], p["birth_tick"]) == band)
                    for band in ("through_1_day", "through_16_days", "older")}}
    return grouped


def decode(row, life, previous):
    tick, plant = row["tick"], row["plant"]
    require(plant["id"] == life["id"] and plant["birth"] == life["birth_tick"], "wrong excerpt identity")
    receipt = population.adults.transfers({"tick": tick, **plant}, life,
                                         previous["stages"][-1] if previous else None)
    paid = population.payment(plant, receipt, previous["roots"] if previous else None, tick, row["sun"][0])
    lit = light.illumination(row, life, receipt["energy"])
    for r, capacity in RESOURCES.items():
        flow = receipt[r]
        require(flow["overflow"] == max(0, flow["initial"] + flow["income"] - capacity), "wrong storage cap")
        flow["due"] = paid[r]["due"] if paid else 0
        flow["unpaid"] = flow["due"] - flow["upkeep"]
    return {"tick": tick, "resources": receipt, "light": lit, "payment": paid,
            "soil_water": row["soil_water"], "nodes": plant["stages"][-1][4],
            "roots": plant["roots"], "stress": plant["stages"][-1][2]}


def collect_world(bundle, saved):
    result, summaries = saved["result"], saved["analysis"]["plants"]
    selected = {p["life"]["id"]: intervals(p) for p in summaries if intervals(p)}
    retained = {i: [{"start": a, "end": b, "previous": None, "rows": []} for a, b in spans]
                for i, spans in selected.items()}
    by_id = {p["life"]["id"]: p for p in summaries}
    checked = {i: {"resources": population.adults.budget(), "payments": 0, "shortages": [], "samples": 0}
               for i in by_id}
    paths = {k: bundle / v["path"] for k, v in saved["runs"]["trace"]["traces"].items()}
    for k, path in paths.items():
        require(digest(path) == saved["runs"]["trace"]["traces"][k]["sha256"], "trace changed before reading")
    previous = {}
    streams = [population.trace_rows(paths[k], k, result) for k in ("stand", "adult")]
    for stand, adult in zip(*streams, strict=True):
        tick = adult["tick"]
        expected = {i for i, p in by_id.items() if p["life"]["birth_tick"] <= tick <= (p["life"]["death_tick"] or STOP)}
        require(len(adult["plants"]) == len(expected) and {p["id"] for p in adult["plants"]} == expected,
                "incomplete resource census")
        for p in adult["plants"]:
            i = p["id"]
            row = {"tick": tick, "sun": adult["sun"], "climate": stand["climate"],
                   "soil_water": adult["soil_water"], "plant": p}
            flow = decode(row, by_id[i]["life"], previous.get(i))
            c = checked[i]
            population.adults.accumulate(c["resources"], flow["resources"], c["samples"] == 0)
            c["samples"] += 1
            if flow["payment"]:
                c["payments"] += 1
                if any(flow["payment"][r]["unpaid"] for r in RESOURCES):
                    c["shortages"].append(flow["payment"])
            for segment in retained.get(i, []):
                if segment["start"] <= tick <= segment["end"]:
                    if tick == segment["start"]:
                        segment["previous"] = previous.get(i)
                    if i == 9 and tick <= p["birth"] + DAY:
                        row["focal"] = {"bids": [b for b in stand["bids"] if b["id"] == i],
                            "body": next((b for b in stand["bodies"] if b["id"] == i), None),
                            "reproduction": next(v for v in stand["reproduction"] if v["id"] == i)}
                    segment["rows"].append(row)
            previous[i] = p
    for i, c in checked.items():
        require(all(c[k] == by_id[i][k] for k in c), "full resource audit differs from saved population")
    for k, path in paths.items():
        require(digest(path) == saved["runs"]["trace"]["traces"][k]["sha256"], "trace changed during reading")
    return [{"id": i, "segments": s} for i, s in sorted(retained.items())]


def totals(samples):
    out = population.adults.budget()
    for j, s in enumerate(samples):
        population.adults.accumulate(out, s["resources"], j == 0)
    return out


def window_summary(samples, life):
    budget = totals(samples)
    end = samples[-1]["tick"]
    return {"start": samples[0]["tick"], "end": end, "samples": len(samples), "resources": budget,
        "starts_at_birth": samples[0]["tick"] == life["birth_tick"],
        "ends_at_death": end == life["death_tick"], "ends_at_capture": end == STOP,
        "funding": {r: {mode: required_opening([s["resources"][r] for s in samples], cap, mode)
            for mode in ("all", "no_reproduction", "maintenance_only")} for r, cap in RESOURCES.items()}}


def analyze_world(saved, excerpts):
    summaries = {p["life"]["id"]: p for p in saved["analysis"]["plants"]}
    require([x["id"] for x in excerpts] == sorted(i for i, p in summaries.items() if intervals(p)), "wrong excerpt panel")
    plants = []
    for excerpt in excerpts:
        p = summaries[excerpt["id"]]
        life = p["life"]
        require([[s["start"], s["end"]] for s in excerpt["segments"]] == intervals(p), "wrong interval coverage")
        shortages, windows, early = [], [], []
        for segment in excerpt["segments"]:
            rows, previous = segment["rows"], segment["previous"]
            previous_body = None
            require([r["tick"] for r in rows] == list(range(segment["start"], segment["end"] + STEP, STEP)),
                    "incomplete/reordered excerpt")
            require((previous is None) == (segment["start"] == max(STEP, life["birth_tick"])), "missing opening state")
            require(previous is None or (previous["id"], previous["birth"]) == (life["id"], life["birth_tick"]),
                    "wrong preceding identity")
            samples = []
            for row in rows:
                s = decode(row, life, previous)
                samples.append(s)
                if life["id"] == 9 and row["tick"] <= life["birth_tick"] + DAY:
                    focal = row["focal"]
                    bids = focal["bids"]
                    chosen = population.dawn.winner(bids, dawn=True) if bids else None
                    if bids:
                        selected = next(b for b in bids if b["tip"] == chosen["tip"])
                        population.check_growth(row, {"sun": row["sun"], "plants": [row["plant"]]},
                            life, bids, focal["body"], previous_body,
                            "candidate" if "root_dawn_reserve_probe" in saved["result"] else "control")
                        early.append({"tick": row["tick"], "choice": chosen,
                            "tissue": selected["tissue"], "action": selected["action"],
                            "body": focal["body"], "resources": s["resources"]})
                    require(focal["reproduction"]["produced"] == bool(s["resources"]["energy"]["reproduction"]),
                            "focal reproduction debit differs")
                    previous_body = focal["body"]
                previous = row["plant"]
            windows.append(window_summary(samples, life))
            for j, s in enumerate(samples):
                event = s["payment"]
                if not event or not any(event[r]["unpaid"] for r in RESOURCES):
                    continue
                recent = samples[max(0, j - DAY // STEP + 1):j + 1]
                require(recent[0]["tick"] == max(max(STEP, life["birth_tick"]), s["tick"] - DAY + STEP),
                        "missing preceding-day shortage context")
                shortages.append({"event": event, "age": age_band(s["tick"], life["birth_tick"]),
                    "light": s["light"], "soil_water": s["soil_water"], "stress": s["stress"],
                    "preceding_day": window_summary(recent, life),
                    "last_growth_in_window": next((q["tick"] for q in reversed(samples[:j + 1])
                        if q["resources"]["energy"]["growth"]), None),
                    "last_reproduction_in_window": next((q["tick"] for q in reversed(samples[:j + 1])
                        if q["resources"]["energy"]["reproduction"]), None)})
        require([s["event"] for s in shortages] == p["shortages"], "missing/extra shortage receipt")
        out = {"life": life, "windows": windows, "shortages": shortages}
        if life["id"] == 9:
            require(len(windows) == 1 and windows[0]["resources"] == p["resources"], "incomplete focal lifetime")
            out["focal"] = {"early_choices": early, "first_flower": p["first_flower"], "body_changes": p["body_changes"],
                "seeds": [s for s in saved["result"]["seeds"] if s["parent"] == 9],
                "children": [c for c in saved["result"]["lineages"] if c["parent"] == 9]}
        plants.append(out)
    return plants


def analyze(excerpts):
    require([c["id"] for c in excerpts] == list(CASE_IDS), "wrong audit cases")
    out = []
    for entry, captured in zip(cases(), excerpts, strict=True):
        require(set(captured["arms"]) == set(population.ARMS), "wrong audit arms")
        arms = {a: {"cohorts": cohort_totals(entry, a),
            "plants": analyze_world(entry["arms"][a], captured["arms"][a])} for a in population.ARMS}
        result = [entry["arms"][a]["result"] for a in population.ARMS]
        out.append({"id": captured["id"], "arms": arms,
            "first_ledger_differences": {k: first_ledger_difference(*result, k)
                for k in ("seed_purchase", "birth", "death")}})
    return out


def check_value(value):
    require(digest(ROOT / INPUT) == INPUT_SHA and value["rule"] == RULE and value["input_sha256"] == INPUT_SHA and
            value["raw_manifest_sha256"] == MANIFEST_SHA and value["native_calls"] == value["training_runs"] == 0 and
            value["protocol_sha256"] == digest(ROOT / PROTOCOL) and
            value["source_sha256"].get(PROTOCOL) == value["protocol_sha256"] and
            value["source_sha256"].get(INPUT) == INPUT_SHA, "wrong audit provenance")
    require(value["analysis"] == analyze(value["excerpts"]), "saved audit analysis differs")


def export(bundle, out):
    require(not out.exists() and (out.is_relative_to(ROOT / "artifacts") or not out.is_relative_to(ROOT)),
            "fresh output required")
    require(digest(bundle / "manifest.json") == MANIFEST_SHA, "wrong raw population manifest")
    source = source_files()
    out.mkdir(parents=True)
    snapshot_sources(out, source)
    excerpts = []
    for entry in cases():
        arms = {}
        for a in population.ARMS:
            arms[a] = collect_world(bundle, entry["arms"][a])
            print(entry["case"]["id"] + "/" + a + ": complete resource receipts verified and selected", flush=True)
        excerpts.append({"id": entry["case"]["id"], "arms": arms})
    value = {"rule": RULE, "input_sha256": INPUT_SHA, "raw_manifest_sha256": MANIFEST_SHA,
        "protocol_sha256": digest(ROOT / PROTOCOL), "source_sha256": source, "native_calls": 0,
        "training_runs": 0, "excerpts": excerpts, "analysis": analyze(excerpts)}
    check_value(value)
    require(source_files() == source and digest(bundle / "manifest.json") == MANIFEST_SHA, "audit inputs/source changed")
    population.order.recovery.founders.write_gzip(out / "results.json.gz", value)
    write_json(out / "manifest.json", {"rule": RULE, "status": "complete", "artifacts": {
        name: digest(out / name) for name in ("results.json.gz", "source.tar.gz")}})
    print("Saved four-world offline audit; zero native calls or training runs.")


def verify(path, raw=None):
    directory = path if path.is_dir() else None
    if directory:
        manifest = json.loads((directory / "manifest.json").read_text())
        require(manifest["rule"] == RULE and manifest["status"] == "complete" and
                set(manifest["artifacts"]) == {"results.json.gz", "source.tar.gz"}, "wrong audit manifest")
        for name, sha in manifest["artifacts"].items():
            require(digest(directory / name) == sha, "audit artifact changed")
        path = directory / "results.json.gz"
    with gzip.open(path, "rt") as stream:
        value = json.load(stream)
    check_value(value)
    if directory:
        require(archived_sources(directory / "source.tar.gz") == value["source_sha256"],
                "audit source archive differs")
    if raw is not None:
        require(digest(raw / "manifest.json") == MANIFEST_SHA, "wrong raw population manifest")
        for entry, excerpts in zip(cases(), value["excerpts"], strict=True):
            for arm in population.ARMS:
                require(collect_world(raw, entry["arms"][arm]) == excerpts["arms"][arm], "raw excerpts differ")
                print(entry["case"]["id"] + "/" + arm + ": raw excerpts verified", flush=True)
    print("Verified complete selection, resource balances, shortage context and recomputed summaries; no simulation.")
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--out", type=Path)
    mode.add_argument("--verify", type=Path)
    parser.add_argument("--bundle", type=Path, default=ROOT / "artifacts/garden-landing-population-v1")
    parser.add_argument("--verify-raw", action="store_true")
    args = parser.parse_args()
    require(not args.verify_raw or args.verify is not None, "--verify-raw needs --verify")
    if args.out:
        export(args.bundle.resolve(), args.out.resolve())
    else:
        verify(args.verify.resolve(), args.bundle.resolve() if args.verify_raw else None)


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError, KeyError, TypeError, OSError, StopIteration) as error:
        print("population audit failed: " + str(error), file=sys.stderr)
        sys.exit(1)
