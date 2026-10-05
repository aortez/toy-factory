#!/usr/bin/env python3
"""Five first-day energy counterfactuals after an identical root purchase; no training."""

from __future__ import annotations

import argparse
from collections import Counter
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

import garden_landing_root_choice as root
from garden_resources import require

ROOT, DAY, STEP, STOP = root.ROOT, root.DAY, root.STEP, root.STOP
CASES, ARMS, LABELS, KINDS = root.CASES, root.ARMS, root.LABELS, root.KINDS
order, adults, prior, late = root.order, root.adults, root.prior, root.late
RULE = "garden-landing-root-energy-v1"
PROTOCOL = "benchmarks/garden-seasons/landing-root-energy-protocol.md"
INPUT = "benchmarks/garden-seasons/landing-root-choice-results.json.gz"
INPUT_SHA = "d29470fc81efc4c111ead315a159bb8e7caac7fb0e2b75f7b7ec0a40c1861b9f"
MANIFEST_SHA = "e2925f56da731485dd5df50ee9fe297256ece271e5bc58026b6199a5b4f5ae7b"
INPUTS = {**root.INPUTS, INPUT: INPUT_SHA}
SCHEMA = "landing-root-energy-stand-trace-v1"


@cache
def load_inputs():
    data, world, _, model = root.load_inputs()
    saved = prior.load(ROOT / INPUT, INPUT_SHA)
    root.check_value(saved)
    return data, world, saved, model


def energy_hash(base):
    require(type(base) is str and len(base) == 8, "invalid energy hash input")
    h = 2166136261
    for byte in b"GLE1" + int(base, 16).to_bytes(4, "little"):
        h = ((h ^ byte) * 16777619) & 0xffffffff
    return f"{h:08x}"


def root_result(result, case, arm):
    require(arm in ARMS, "unknown energy arm")
    value = copy.deepcopy(result)
    if arm == "candidate":
        placing = order.previous.placement
        expected = placing.probe_hash(placing.budget.probe_hash(value["base_run_hash"], 2), True)
        if case["order"] == "rotating":
            expected = order.order_hash(expected, prior.AT)
        expected = root.probe_hash(expected, case["tick"], case["lineage"])
        require(value.get("root_energy_probe") == {"version": 1} and
                type(value["root_energy_probe"]["version"]) is int and
                value["run_hash"] == energy_hash(expected), "wrong energy identity")
        del value["root_energy_probe"]
        value["run_hash"] = expected
    else:
        require("root_energy_probe" not in value, "energy guard in control")
    root.common_result(value, case, "candidate")
    return value


def arguments(world, case, arm, label):
    require(case in CASES and arm in ARMS and label in LABELS, "wrong frozen call")
    args = root.arguments(world, case, "candidate", label)
    # Both arms retain the exact same one-time root choice, but have distinct files.
    old, new = root.stem(case, "candidate", label), root.stem(case, arm, label)
    args = [a.replace(old, new) for a in args]
    if label == "prefix":
        args[args.index("--ticks") + 1] = str(case["tick"])
    if label in ("trace", "repeat"):
        args[args.index("--stand-choice")] = "--stand-energy"
    if arm == "candidate":
        args.append("--root-energy-reserve")
    return args


def check_energy(bid, life, tick, case, arm, *, continuous=False):
    """Independent integer forecast; inputs are local observations, never future state."""
    e = bid["energy_gate"]
    zeros = dict.fromkeys(("post_nodes", "cost", "maintenance", "daylight_steps", "daylight_credit",
                          "daylight_upkeep", "night_upkeep", "projected_sunset"), 0)
    inputs = ("age", "sun_phase", "maintenance_phase", "income", "vigor")
    require(set(e) == set(zeros) | set(inputs) | {"active", "allowed", "forecast_allowed"} and
            all(type(e[k]) is int for k in (*zeros, *inputs)) and
            all(type(e[k]) is bool for k in ("active", "allowed", "forecast_allowed")) and
            0 <= e["income"] <= 255 and -128 <= e["vigor"] <= 127, "invalid energy receipt")
    born = life["birth_tick"]
    age = min(65535, (tick - born) // STEP + int(born != 0))
    require(e["age"] == age and e["sun_phase"] == (64 + tick // STEP) % 256 and
            e["maintenance_phase"] == tick // STEP % 4, "wrong energy observation phase/age")
    active = (arm == "candidate" and life["id"] == case["lineage"] and born == case["tick"] and
              life["generation"] > 0 and age >= 2 and (continuous or age <= 256) and tick > case["tick"] and
              (not continuous or life["death_tick"] is None or tick < life["death_tick"]))
    forecast = zeros.copy()
    forecast_allowed = bid["action"] == 0
    if bid["action"] != 0 and e["sun_phase"] < 128:
        nodes = bid["nodes"] + int(bid["action"] == 1 and bid["available"] > 0)
        cost = (9, 8, 7)[life["species"]] - int(e["vigor"] > 0)
        maintenance, remaining = max(1, (nodes + 7) // 8), 128 - e["sun_phase"]
        credit = e["income"] * (remaining - 1) // 2
        upkeep, night = (remaining + e["maintenance_phase"]) // 4 * maintenance, 32 * maintenance
        sunset = min(256, bid["energy"] - cost + credit - upkeep)
        forecast = dict(zip(zeros, (nodes, cost, maintenance, remaining, credit, upkeep, night, sunset), strict=True))
        forecast_allowed = bid["energy"] - cost >= maintenance and sunset >= night
    require(all(e[k] == v for k, v in forecast.items()) and
            (e["active"], e["forecast_allowed"], e["allowed"]) ==
            (active, forecast_allowed, not active or forecast_allowed), "energy forecast/scope differs")


def strip_energy(rows):
    return [{**r, "bids": [{k: v for k, v in b.items() if k != "energy_gate"} for b in r["bids"]]}
            for r in rows]


def choice_stand(rows, result, case, arm):
    normal = root_result(result, case, arm)
    require(rows[0] == {**prior.header("stand", case["tick"] - STEP, STOP), "schema": SCHEMA} and
            rows[-1] == {"complete": True, "tick": STOP, "run_hash": result["run_hash"]}, "wrong energy trace identity")
    return [{**rows[0], "schema": "landing-root-choice-stand-trace-v1"},
            *strip_energy(rows[1:-1]), {**rows[-1], "run_hash": normal["run_hash"]}]


def check_bids(row, resource, lives, case, arm, *, extra_allowed=None, continuous=False):
    counts = Counter()
    resources = {r["id"]: r for r in resource["plants"]}
    for b in row["bids"]:
        life, e, tick = lives[b["id"]], b["energy_gate"], row["tick"]
        check_energy(b, life, tick, case, arm, continuous=continuous)
        r = resources[b["id"]]
        require(e["income"] == (r["uptake"][0][1] if r["uptake"] is not None else 0), "income receipt differs")
        counts["bids"] += 1
        if e["active"]:
            counts["active"] += 1
            if not e["allowed"]:
                counts["energy_denied"] += 1
                if b["budget"]["allowed"] and b["water_gate"]["allowed"]:
                    counts["energy_only_denied"] += 1
    for lineage in {b["id"] for b in row["bids"]}:
        bids = [b for b in row["bids"] if b["id"] == lineage]
        eligible = [b for b in bids if b["budget"]["allowed"] and b["water_gate"]["allowed"] and
                    b["energy_gate"]["allowed"] and (extra_allowed is None or extra_allowed(b))]
        winner = max(eligible or bids, key=lambda b: b["priority"])
        allocating = bool(eligible) and winner["budget"]["allocates"]
        body = next(b for b in row["bodies"] if b["id"] == lineage)
        require(body["nodes"] == winner["nodes"] + allocating and
                body["roots"] == winner["roots"] + int(allocating and winner["tissue"] == 1), "combined eligibility winner differs")
        if not eligible:
            stages = resources[lineage]["stages"]
            require(stages[2] == stages[3], "all-ineligible fallback spent resources")
        counts["allocations"] += allocating
        counts["all_ineligible"] += not eligible
    return counts


def analyze(stand, resources, result, case, arm):
    normal = root_result(result, case, arm)
    choice = choice_stand(stand, result, case, arm)
    base = root.analyze(choice, resources, normal, case, "candidate")
    lives, counts = {p["id"]: p for p in result["lineages"]}, Counter()
    for row, resource in zip(stand[1:-1], resources[1:-1], strict=True):
        require(row["tick"] == resource["tick"], "resource/stand alignment differs")
        counts.update(check_bids(row, resource, lives, case, arm))
    focal = root.focal_history(stand, resources, result, case)
    # Retain the second day too: a first-day rescue can fail when protection ends.
    life, start = focal["life"], case["tick"] - STEP
    followup = []
    for tick in range(case["tick"] + DAY + STEP, min(case["tick"] + 2 * DAY, life["death_tick"] or STOP) + STEP, STEP):
        index = (tick - start) // STEP + 1
        row, r = stand[index], resources[index]
        followup.append({"tick": tick, "sun": r["sun"], "climate": row["climate"], "soil_water": r["soil_water"],
            "plant": next(p for p in r["plants"] if p["id"] == life["id"]),
            "body": next((p for p in row["bodies"] if p["id"] == life["id"]), None),
            "visit": next(p for p in row["reproduction"] if p["id"] == life["id"]),
            "bids": [b for b in row["bids"] if b["id"] == life["id"]]})
    return {**base, "focal": focal, "followup_steps": followup, "eligibility": dict(sorted(counts.items()))}


def historical_check(reference, saved, case, rows, result):
    old = next(c for c in saved["cases"] if c["case"] == case)["arms"]["candidate"]
    metadata = old["traces"]
    projected = choice_stand(rows[0], result, case, "control")
    for kind, records in zip(KINDS, (projected, rows[1]), strict=True):
        path = reference / metadata[kind]["path"]
        require(root.digest(path) == metadata[kind]["sha256"] and adults.read_trace(path) == records,
                "historical root-only trace changed")
        require(root.digest(path) == metadata[kind]["sha256"], "historical trace changed during read")
    return metadata


def check_pair(case, arms, saved):
    old = next(c for c in saved["cases"] if c["case"] == case)["arms"]["candidate"]
    a, b = (arms[arm] for arm in ARMS)
    require(a["runs"]["prefix"]["result"] == root_result(b["runs"]["prefix"]["result"], case, "candidate") and
            a["runs"]["prefix"]["frame"] == b["runs"]["prefix"]["frame"] and
            a["runs"]["prefix"]["result"]["tick"] == case["tick"], "post-root common prefix changed")
    for label in ("day1", "trace", "repeat"):
        require(a["runs"][label] == old["runs"][label], "historical root-only checkpoint changed")
    ca, cb = (arm["analysis"]["focal"] for arm in (a, b))
    require({**ca, "steps": strip_energy(ca["steps"])} == old["analysis"]["focal"], "historical focal history changed")
    require(strip_energy(ca["steps"][:1]) == strip_energy(cb["steps"][:1]) and
            ca["seed"] == cb["seed"] and ca["birth_check"] == cb["birth_check"] and
            ca["steps"][0]["body"]["roots"] == cb["steps"][0]["body"]["roots"] == 3 and
            ca["steps"][0]["body"]["nodes"] == cb["steps"][0]["body"]["nodes"] == 5,
            "root purchase or pre-growth birth differs")
    for arm, a in arms.items():
        require(a["runs"]["trace"] == a["runs"]["repeat"], "full replay repeat differs")
        f = a["analysis"]["focal"]
        require(f["first_day"] == late.history_summary(f["life"], f["steps"]), "first-day budget differs")
        for label, run in a["runs"].items():
            root_result(run["result"], case, arm)
            require(run["result"]["tick"] == {"prefix": case["tick"], "day1": case["tick"] + DAY}.get(label, STOP),
                    "wrong checkpoint tick")
        day1 = a["runs"]["day1"]["result"]
        require(next(p for p in day1["lineages"] if p["id"] == case["lineage"])["death_tick"] ==
                (f["life"]["death_tick"] if f["life"]["death_tick"] and f["life"]["death_tick"] <= day1["tick"] else None),
                "day-one checkpoint outcome differs")


def check_value(value):
    data, world, saved, _ = load_inputs()
    require(value["rule"] == RULE and value["inputs"] == INPUTS and value["world"] == world["case"] and
            value["protocol_sha256"] == root.digest(ROOT / PROTOCOL) and value["model"] == data["models"][late.MODEL] and
            value["full_replays"] == value["checkpoint_replays"] == 20 and value["training_runs"] == 0 and
            len(value["cases"]) == len(CASES) and set(value["build"]) == {"binary", "cache"} and
            value["source_sha256"].get(PROTOCOL) == value["protocol_sha256"], "wrong energy provenance/budget")
    if "validation_recovery" in value:
        r = value["validation_recovery"]
        require(r["schema"] == "landing-root-energy-validation-recovery-v1" and
                type(r["additional_native_calls"]) is int and r["additional_native_calls"] == 0 and
                type(r["capture_failure"]) is str and bool(r["capture_failure"]) and
                r["captured_artifacts"]["FAILED.txt"] == hashlib.sha256(r["capture_failure"].encode()).hexdigest() and
                r["captured_artifacts"]["bin/garden-landing"] == value["build"]["binary"] and
                r["captured_artifacts"]["CMakeCache.txt"] == value["build"]["cache"] and
                r["captured_artifacts"]["protocol.md"] == value["protocol_sha256"] and
                r["validator_source_sha256"][PROTOCOL] == value["protocol_sha256"], "invalid offline recovery provenance")
    for case, entry in zip(CASES, value["cases"], strict=True):
        require(entry["case"] == case and set(entry["arms"]) == set(ARMS), "wrong frozen energy panel")
        check_pair(case, entry["arms"], saved)
        historical = next(c for c in saved["cases"] if c["case"] == case)["arms"]["candidate"]
        for arm, a in entry["arms"].items():
            require(set(a["runs"]) == set(LABELS) and a["calls"] == [
                {"case": case["id"], "arm": arm, "label": label, "args": arguments(world, case, arm, label)}
                for label in LABELS] and a["historical_traces"] == (historical["traces"] if arm == "control" else None),
                "wrong native calls/historical source")
            analysis, result = a["analysis"], a["runs"]["trace"]["result"]
            focal, lives = analysis["focal"], {p["id"]: p for p in result["lineages"]}
            require(focal["life"] == lives[case["lineage"]] and focal["seed"] in result["seeds"] and
                    analysis["all_plants"]["outcomes"] == order.outcomes(result) and
                    (analysis["all_plants"]["gates"]["start"], analysis["all_plants"]["gates"]["stop"]) ==
                    (case["tick"] - STEP, STOP), "wrong outcomes/window")
            end = min(case["tick"] + 2 * DAY, focal["life"]["death_tick"] or STOP)
            require([s["tick"] for s in analysis["followup_steps"]] == list(range(case["tick"] + DAY + STEP, end + STEP, STEP)),
                    "second-day coverage differs")
            before, changes, focal_counts = None, [], Counter()
            for step in focal["steps"] + analysis["followup_steps"]:
                adults.transfers({"tick": step["tick"], **step["plant"]}, focal["life"], before)
                before = step["plant"]["stages"][-1]
                focal_counts.update(check_bids(
                    {"tick": step["tick"], "bids": step["bids"], "bodies": [step["body"]] if step["body"] else []},
                    {"plants": [step["plant"]]}, lives, case, arm))
                for bid in step["bids"]:
                    root.check_water(bid, focal["life"], step["tick"])
                    boost = (step["tick"] == case["tick"] and bid["tissue"] == 1 and bid["action"] == 1 and
                             bid["budget"]["allocates"] and bid["budget"]["allowed"] and bid["water_gate"]["allowed"])
                    require(bid["priority"] == (32767 if boost else bid["raw_priority"]), "extra/missing priority change")
                    if boost:
                        changes.append({"tick": step["tick"], "bid": {k: v for k, v in bid.items() if k != "energy_gate"}})
            require(bool(changes) and analysis["priority_changes"] == changes, "root priority audit differs")
            require(set(analysis["eligibility"]) <= {"bids", "active", "energy_denied", "energy_only_denied", "allocations", "all_ineligible"} and
                    all(type(n) is int and n >= 0 for n in analysis["eligibility"].values()) and
                    all(analysis["eligibility"].get(k, 0) == focal_counts[k] for k in
                        ("active", "energy_denied", "energy_only_denied")), "energy denial summary differs")
            require(analysis["eligibility"].get("active", 0) > 0 if arm == "candidate" else
                    analysis["eligibility"].get("active", 0) == 0, "guard did not exercise correct arm")


def reanalyse(capture, out, reference):
    """Recover a complete raw capture after an offline checker failure, without execution.

    Keep the failed directory intact. The new bundle preserves native source/build
    identity and records the repaired validator separately; never fill missing trials.
    """
    require(capture.is_dir() and (capture / "FAILED.txt").is_file() and not out.exists() and
            (out.is_relative_to(ROOT / "artifacts") or not out.is_relative_to(ROOT)), "failed capture/fresh output required")
    data, world, saved, model = load_inputs()
    require(root.digest(reference / "manifest.json") == MANIFEST_SHA and
            root.digest(reference / "results.json.gz") == INPUT_SHA and
            (capture / "model.tgl").read_bytes() == model and
            root.digest(capture / "protocol.md") == root.digest(ROOT / PROTOCOL) and
            all(root.digest(capture / "inputs" / Path(p).name) == h for p, h in INPUTS.items()), "capture inputs differ")
    files = {str(p.relative_to(capture)): root.digest(p) for p in sorted(capture.rglob("*")) if p.is_file()}
    require(not any(p.is_symlink() for p in capture.rglob("*")), "capture contains symlinks")
    names = [root.stem(c, a, label) for c in CASES for a in ARMS for label in LABELS]
    require({p.name for p in capture.glob("*-call.json")} == {n + "-call.json" for n in names} and
            {p.name for p in capture.glob("*-result.json")} == {n + "-result.json" for n in names},
            "missing or extra native calls; offline recovery cannot simulate")
    sources = {}
    with tarfile.open(capture / "source.tar.gz", "r:gz") as archive:
        for member in archive.getmembers():
            require(member.isfile() and member.name not in sources, "invalid captured source archive")
            with archive.extractfile(member) as stream:
                sources[member.name] = hashlib.sha256(stream.read()).hexdigest()
    require(sources.get(PROTOCOL) == root.digest(capture / "protocol.md"), "captured protocol differs")
    settings = order.previous.growth.water.check_build(capture / "CMakeCache.txt")
    require(settings["CMAKE_HOME_DIRECTORY"] == str(ROOT / "sim"), "wrong captured source tree")
    cases = []
    for case in CASES:
        arms = {}
        for arm in ARMS:
            runs, calls, traces = {}, [], {}
            for label in LABELS:
                name = root.stem(case, arm, label)
                call = json.loads((capture / (name + "-call.json")).read_text())
                require(call == {"case": case["id"], "arm": arm, "label": label,
                                 "args": arguments(world, case, arm, label)}, "captured call differs")
                calls.append(call)
                result = json.loads((capture / (name + "-result.json")).read_text())
                path = capture / "frames" / (name + ".raw")
                pixels = path.read_bytes()
                require(len(pixels) == 240 * 240 * 2 and f"{zlib.crc32(pixels):08x}" == result["framebuffer_crc32"], "captured pixels differ")
                runs[label] = {"result": result, "frame": {"raw_sha256": root.digest(path),
                                                           "framebuffer_crc32": result["framebuffer_crc32"]}}
                if label in ("trace", "repeat"):
                    traces[label] = {}
                    for kind in KINDS:
                        path = capture / (name + "-" + kind + ".jsonl.gz")
                        with gzip.open(path, "rb") as stream:
                            require(hashlib.sha256(stream.read()).hexdigest() == root.digest(path.with_suffix("")),
                                    "compressed/raw trace differs")
                        traces[label][kind] = {"path": path.name, "sha256": root.digest(path)}
            require(runs["trace"] == runs["repeat"] and all(traces["trace"][k]["sha256"] ==
                    traces["repeat"][k]["sha256"] for k in KINDS), "captured repeat differs")
            rows = [adults.read_trace(capture / traces["trace"][k]["path"]) for k in KINDS]
            result = runs["trace"]["result"]
            arms[arm] = {"runs": runs, "calls": calls, "traces": traces["trace"],
                         "analysis": analyze(*rows, result, case, arm),
                         "historical_traces": historical_check(reference, saved, case, rows, result) if arm == "control" else None}
        check_pair(case, arms, saved)
        cases.append({"case": case, "arms": arms})
        print(case["id"] + ": offline raw reanalysis verified", flush=True)
    require(all(root.digest(capture / p) == h for p, h in files.items()), "capture changed during reanalysis")
    shutil.copytree(capture, out, ignore=shutil.ignore_patterns("FAILED.txt"))
    validation_sources = root.source_files()
    (out / "validation").mkdir()
    root.snapshot_sources(out / "validation", validation_sources)
    recovery = {"schema": "landing-root-energy-validation-recovery-v1", "additional_native_calls": 0,
        "capture_failure": (capture / "FAILED.txt").read_text(), "captured_artifacts": files,
        "validator_source_sha256": validation_sources}
    root.write_json(out / "validation-recovery.json", recovery)
    gallery = root.contact_sheet(out, [[{"id": root.stem(c, a, label),
        "framebuffer": "frames/" + root.stem(c, a, label) + ".raw"} for label in ("prefix", "day1", "trace")]
        for c in CASES for a in ARMS])
    value = {"rule": RULE, "inputs": INPUTS, "protocol_sha256": root.digest(out / "protocol.md"),
        "source_sha256": sources, "build": {"binary": root.digest(out / "bin/garden-landing"),
        "cache": root.digest(out / "CMakeCache.txt")}, "settings": settings, "model": data["models"][late.MODEL],
        "world": world["case"], "full_replays": 20, "checkpoint_replays": 20, "training_runs": 0,
        "cases": cases, "gallery": gallery, "validation_recovery": recovery}
    check_value(value)
    order.recovery.founders.write_gzip(out / "results.json.gz", value)
    root.write_json(out / "manifest.json", {"rule": RULE, "status": "complete", "artifacts": {
        str(p.relative_to(out)): root.digest(p) for p in sorted(out.rglob("*")) if p.is_file()}})


def verify(path):
    value = root.verify(path, experiment=sys.modules[__name__])
    if path.is_dir() and "validation_recovery" in value:
        recovery = value["validation_recovery"]
        require(json.loads((path / "validation-recovery.json").read_text()) == recovery, "recovery receipt differs")
        for name in recovery["captured_artifacts"]:
            if name != "FAILED.txt":
                root.artifact(path, {"artifacts": recovery["captured_artifacts"]}, name)
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--out", type=Path)
    mode.add_argument("--verify", type=Path)
    parser.add_argument("--build", type=Path, default=ROOT / "build-host")
    parser.add_argument("--reference", type=Path, default=ROOT / "artifacts/garden-landing-root-choice-v1")
    parser.add_argument("--reanalyse", type=Path, help="reuse a complete failed raw capture; requires fresh --out; never simulates")
    args = parser.parse_args()
    try:
        require(not args.reanalyse or args.out, "--reanalyse requires --out")
        if args.reanalyse:
            reanalyse(args.reanalyse.resolve(), args.out.resolve(), args.reference.resolve())
        elif args.verify:
            verify(args.verify.resolve())
        else:
            root.collect(args.build.resolve(), args.out.resolve(), args.reference.resolve(), experiment=sys.modules[__name__])
        return 0
    except (OSError, RuntimeError, ValueError, KeyError, TypeError, StopIteration) as error:
        print("root-energy experiment failed: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
