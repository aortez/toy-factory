#!/usr/bin/env python3
"""Five independent one-root-choice counterfactuals, forty native calls, no training."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import copy
import gzip
import json
from pathlib import Path
import shutil
import sys
import zlib

import garden_landing_late as late
from garden_experiments import compress, digest, snapshot_sources, source_files, write_json
from garden_gallery import artifact, contact_sheet, rgb565be_to_rgb888, write_png
from garden_resources import require

order, adults, prior = late.order, late.adults, late.prior
ROOT, DAY, STEP, STOP = late.ROOT, late.DAY, late.STEP, late.STOP
RULE = "garden-landing-root-choice-v1"
PROTOCOL = "benchmarks/garden-seasons/landing-root-choice-protocol.md"
INPUT = "benchmarks/garden-seasons/landing-late-resources-results.json.gz"
INPUT_SHA = "6e30507abd1262163afc4e975a7f9e261ca3633c998d799a1aecbf9464ae4f89"
MANIFEST_SHA = "a82a6808b6922683c5b876faadb38ed681e4b49f317a10de75d978564f8ff4a7"
INPUTS = {**late.INPUTS, INPUT: INPUT_SHA}
CASES = tuple({"id": f"{arm}-{lineage}", "order": arm, "lineage": lineage, "tick": tick,
               "column": column, "role": "harm-check" if arm == "fixed" else "failure"}
              for arm, lineage, tick, column in (("fixed", 45, 859860, 25), ("fixed", 46, 905595, 3),
                  ("rotating", 48, 899130, 27), ("rotating", 49, 906570, 12), ("rotating", 50, 906720, 27)))
ARMS, LABELS, KINDS = ("control", "candidate"), ("prefix", "day1", "trace", "repeat"), ("stand", "adult")


def load_inputs():
    data, world, _, model = late.load_inputs()
    saved = prior.load(ROOT / INPUT, INPUT_SHA)
    late.check_value(saved)
    return data, world, saved, model


def probe_hash(base, tick, lineage):
    require(type(tick) is int and type(lineage) is int and 0 < tick <= STOP and tick % STEP == 0 and
            0 < lineage <= 0xffffffff, "invalid root-choice configuration")
    h = 2166136261
    for byte in b"GLQ1" + b"".join(n.to_bytes(4, "little") for n in (int(base, 16), tick, lineage)):
        h = ((h ^ byte) * 16777619) & 0xffffffff
    return f"{h:08x}"


def common_result(result, case, arm):
    require(arm in ARMS, "unknown counterfactual arm")
    placing = order.previous.placement
    expected = placing.probe_hash(placing.budget.probe_hash(result["base_run_hash"], 2), True)
    if case["order"] == "rotating":
        expected = order.order_hash(expected, prior.AT)
    value = copy.deepcopy(result)
    if arm == "candidate":
        probe = {"version": 1, "tick": case["tick"], "lineage": case["lineage"]}
        require(value.get("root_choice_probe") == probe and
                all(type(n) is int for n in value["root_choice_probe"].values()) and
                value["run_hash"] == probe_hash(expected, case["tick"], case["lineage"]), "wrong root-choice identity")
        del value["root_choice_probe"]
        value["run_hash"] = expected
    else:
        require("root_choice_probe" not in value and value["run_hash"] == expected, "control changed identity")
    order.common_view(value, case["order"])
    return value


def stem(case, arm, label):
    return case["id"] + "-" + arm + "-" + label


def arguments(world, case, arm, label):
    require(case in CASES and arm in ARMS and label in LABELS, "wrong frozen call")
    name = stem(case, arm, label)
    tick = {"prefix": case["tick"] - STEP, "day1": case["tick"] + DAY}.get(label, STOP)
    args = ["placement-replay", "model.tgl", world["case"]["scenario"], "0x" + world["case"]["seed"],
            "--climate", "seasonal", "--ledger", "--shoot-reserve", "on", "--seed-placement", "spacing"]
    if case["order"] == "rotating":
        args += ["--seed-order", "rotating", "--seed-order-after", str(prior.AT)]
    if arm == "candidate":
        args += ["--root-choice-at", str(case["tick"]), "--root-choice-lineage", str(case["lineage"])]
    args += ["--ticks", str(tick), "--framebuffer", "frames/" + name + ".raw"]
    if label in ("trace", "repeat"):
        args += ["--stand-choice"]
        for kind in KINDS:
            args += ["--" + kind + "-trace", name + "-" + kind + ".jsonl", "--" + kind + "-start",
                     str(case["tick"] - STEP), "--" + kind + "-stop", str(STOP)]
    return args


def check_water(b, life, tick):
    """Recompute the existing water forecast independently, never grant water."""
    w, destination = b["water_gate"], b["water_gate"]["destination"]
    require(set(w) == {"active", "allowed", "cost", "upkeep", "reserve", "wet_root", "tip_moisture", "destination"} and
            all(type(w[k]) is bool for k in ("active", "allowed", "wet_root")) and
            all(type(w[k]) is int and w[k] >= 0 for k in ("cost", "upkeep", "reserve", "tip_moisture")) and
            w["tip_moisture"] <= 255 and (destination is None or adults.vector(destination, 3, 255)), "invalid water receipt")
    active = life["generation"] > 0 and 0 <= tick - life["birth_tick"] < DAY
    allocating = b["action"] == 1 and b["available"] > 0
    require((destination is not None) == allocating, "wrong destination presence")
    cost = (5, 5, 4)[life["species"]] if b["action"] != 0 else 0
    wet = bool(allocating and b["tissue"] == 1 and destination[1] >= 144 and
               destination[2] >= cost and destination[2] > w["tip_moisture"])
    upkeep = (b["shoots"] + int(allocating and b["tissue"] == 0) + 7) // 8 if cost else 0
    reserve = upkeep * (1 if wet else 4)
    allowed = not active or b["water"] >= cost + reserve
    require((w["active"], w["cost"], w["wet_root"], w["upkeep"], w["reserve"], w["allowed"]) ==
            (active, cost, wet, upkeep, reserve, allowed), "water guard arithmetic differs")


def project_stand(rows, result, case, arm):
    """Validate every priority change before adapting to the legacy analyzer."""
    start = case["tick"] - STEP
    require(rows[0] == {**prior.header("stand", start, STOP), "schema": "landing-root-choice-stand-trace-v1"} and
            rows[-1] == {"complete": True, "tick": STOP, "run_hash": result["run_hash"]} and
            len(rows) == (STOP - start) // STEP + 3, "wrong choice trace window/footer")
    normal = common_result(result, case, arm)
    lives, changes = {p["id"]: p for p in result["lineages"]}, []
    projected = [prior.header("stand", start, STOP)]
    for tick, row in zip(range(start, STOP + STEP, STEP), rows[1:-1], strict=True):
        require(row["tick"] == tick, "missing choice ecology sample")
        bids = []
        for b in row["bids"]:
            check_water(b, lives[b["id"]], tick)
            require(type(b["raw_priority"]) is int and -32768 <= b["raw_priority"] <= 32767 and
                    b["raw_action"] == b["action"], "invalid raw decision")
            boost = (arm == "candidate" and tick == case["tick"] and b["id"] == case["lineage"] and
                     b["water_gate"]["active"] and b["roots"] == 2 and b["tissue"] == 1 and b["action"] == 1 and
                     b["budget"]["allocates"] and b["budget"]["allowed"] and b["water_gate"]["allowed"] and
                     (64 + tick // STEP) % 256 < 128)
            require(b["priority"] == (32767 if boost else b["raw_priority"]), "out-of-scope or missing priority change")
            if boost:
                require(b["energy"] >= 9, "selected root cannot afford ordinary growth")
                changes.append({"tick": tick, "bid": b})
            bids.append({k: v for k, v in b.items() if k not in ("raw_priority", "water_gate")})
        projected.append({**row, "bids": bids})
    projected.append({**rows[-1], "run_hash": normal["run_hash"]})
    require(bool(changes) == (arm == "candidate"), "no targeted eligible root bid")
    return projected, changes


def focal_history(stand, resources, result, case):
    life = next(p for p in result["lineages"] if p["id"] == case["lineage"])
    require((life["birth_tick"], life["column"]) == (case["tick"], case["column"]), "wrong focal birth")
    start = case["tick"] - STEP
    end = min(life["birth_tick"] + DAY, life["death_tick"] or STOP, STOP)
    steps = []
    for tick in range(life["birth_tick"], end + STEP, STEP):
        index = (tick - start) // STEP + 1
        row, r = stand[index], resources[index]
        steps.append({"tick": tick, "sun": r["sun"], "climate": row["climate"], "soil_water": r["soil_water"],
            "plant": next(p for p in r["plants"] if p["id"] == life["id"]),
            "body": next((p for p in row["bodies"] if p["id"] == life["id"]), None),
            "visit": next(p for p in row["reproduction"] if p["id"] == life["id"]),
            "bids": [b for b in row["bids"] if b["id"] == life["id"]]})
    return {"life": life, "seed": next(s for s in result["seeds"] if s["child_id"] == life["id"]),
            "birth_check": next(s for s in resources[2]["seeds"] if s[9] == life["id"]),
            "steps": steps, "first_day": late.history_summary(life, steps)}


def analyze(stand, resources, result, case, arm):
    projected, changes = project_stand(stand, result, case, arm)
    normal = common_result(result, case, arm)
    checked = order.analyze(projected, resources, normal, case["order"])
    return {"priority_changes": changes, "all_plants": checked,
            "focal": focal_history(stand, resources, result, case)}


def strip_extra(steps):
    value = copy.deepcopy(steps)
    for step in value:
        step["bids"] = [{k: v for k, v in b.items() if k not in ("raw_priority", "water_gate")} for b in step["bids"]]
    return value


def check_pair(case, arms, saved):
    control, candidate = (arms[a] for a in ARMS)
    require(common_result(control["runs"]["prefix"]["result"], case, "control") ==
            common_result(candidate["runs"]["prefix"]["result"], case, "candidate") and
            control["runs"]["prefix"]["frame"] == candidate["runs"]["prefix"]["frame"], "common prefix differs")
    historical = saved["arms"][case["order"]]
    require({**control["runs"]["trace"]["result"], "framebuffer_crc32": None} == historical["result"] and
            control["runs"]["trace"]["frame"] == {k: historical["frame"][k] for k in ("raw_sha256", "framebuffer_crc32")},
            "historical endpoint changed")
    a, b = control["analysis"]["focal"], candidate["analysis"]["focal"]
    old = next(p for p in historical["analysis"]["children"] if p["life"]["id"] == case["lineage"])
    require(a["life"] == old["life"] and a["first_day"] == old["first_day"] and
            strip_extra(a["steps"]) == old["steps"], "historical focal history changed")
    require(a["seed"] == b["seed"] == old["seed"] and a["birth_check"] == b["birth_check"] == old["birth_check"] and
            a["steps"][0]["plant"]["stages"][:3] == b["steps"][0]["plant"]["stages"][:3], "different pre-growth birth")
    for p in (a, b):
        require(p["first_day"] == late.history_summary(p["life"], p["steps"]), "focal budget differs")
    raw_a = a["steps"][0]["bids"]
    raw_b = [{**bid, "priority": bid["raw_priority"]} for bid in b["steps"][0]["bids"]]
    require(raw_a == raw_b, "intervention changed raw target proposals or eligibility")
    before, after = a["steps"][0], b["steps"][0]
    require(before["body"]["roots"] == 2 and after["body"]["roots"] == 3 and
            before["body"]["nodes"] == after["body"]["nodes"] == 5 and
            before["plant"]["stages"] == after["plant"]["stages"] and
            after["plant"]["stages"][2][:2] == [64, 24] and
            after["plant"]["stages"][3][:2] in ([55, 19], [56, 19]),
            "did not substitute one paid root for one shoot")
    for arm, value in arms.items():
        require(value["runs"]["trace"] == value["runs"]["repeat"], "full replay repeat differs")
        f = value["analysis"]["focal"]
        day1 = value["runs"]["day1"]["result"]
        require(day1["tick"] == case["tick"] + DAY and
                next(p for p in day1["lineages"] if p["id"] == case["lineage"])["death_tick"] ==
                (f["life"]["death_tick"] if f["life"]["death_tick"] and f["life"]["death_tick"] <= day1["tick"] else None),
                "first-day checkpoint outcome differs")
        for run in value["runs"].values():
            common_result(run["result"], case, arm)


def check_value(value):
    data, world, saved, _ = load_inputs()
    require(value["rule"] == RULE and value["inputs"] == INPUTS and
            value["protocol_sha256"] == digest(ROOT / PROTOCOL) and value["model"] == data["models"][late.MODEL] and
            value["world"] == world["case"] and value["full_replays"] == value["checkpoint_replays"] == 20 and
            value["training_runs"] == 0 and len(value["cases"]) == len(CASES), "wrong counterfactual provenance/budget")
    require(set(value["build"]) == {"binary", "cache"} and value["source_sha256"].get(PROTOCOL) == value["protocol_sha256"],
            "missing source/build provenance")
    for case, entry in zip(CASES, value["cases"], strict=True):
        require(entry["case"] == case and set(entry["arms"]) == set(ARMS), "wrong frozen panel")
        check_pair(case, entry["arms"], saved)
        for arm, a in entry["arms"].items():
            require(set(a["runs"]) == set(LABELS) and a["calls"] == [
                {"case": case["id"], "arm": arm, "label": label, "args": arguments(world, case, arm, label)}
                for label in LABELS], "call budget/arguments changed")
            historical = saved["arms"][case["order"]]
            require(a["historical_traces"] == (historical["traces"] if arm == "control" else None), "wrong historical source")
            focal, checked = a["analysis"]["focal"], a["analysis"]["all_plants"]
            result = a["runs"]["trace"]["result"]
            require(focal["life"] in result["lineages"] and focal["seed"] in result["seeds"] and
                    checked["outcomes"] == order.outcomes(result) and
                    (checked["gates"]["start"], checked["gates"]["stop"]) == (case["tick"] - STEP, STOP),
                    "outcome/window differs")
            changes = []
            for step in focal["steps"]:
                for bid in step["bids"]:
                    check_water(bid, focal["life"], step["tick"])
                    boost = (arm == "candidate" and step["tick"] == case["tick"] and bid["tissue"] == 1 and
                             bid["action"] == 1 and bid["available"] > 0 and bid["budget"]["allowed"] and
                             bid["water_gate"]["allowed"])
                    require(bid["priority"] == (32767 if boost else bid["raw_priority"]), "wrong focal priority")
                    if boost:
                        changes.append({"tick": step["tick"], "bid": bid})
            require(a["analysis"]["priority_changes"] == changes and bool(changes) == (arm == "candidate"),
                    "missing/extra priority changes")


def historical_overlap(reference, metadata, kind, rows, result):
    path = reference / metadata["path"]
    require(digest(path) == metadata["sha256"], "historical trace changed")
    start, index = rows[0]["start"], 1
    with gzip.open(path, "rt") as stream:
        require(json.loads(next(stream)) == prior.header(kind, late.START, STOP), "wrong historical header")
        for tick in range(late.START, STOP + STEP, STEP):
            row = json.loads(next(stream))
            require(row["tick"] == tick, "historical sample missing")
            if tick >= start:
                require(row == rows[index], "historical overlapping trace differs")
                index += 1
        require(json.loads(next(stream)) == prior.footer(kind, result) and not stream.read() and
                index == len(rows) - 1, "historical trace incomplete")
    require(digest(path) == metadata["sha256"], "historical trace changed during read")


def historical_check(reference, saved, case, rows, result):
    historical = saved["arms"][case["order"]]["traces"]
    projected, _ = project_stand(rows[0], result, case, "control")
    for kind, records in zip(KINDS, (projected, rows[1]), strict=True):
        historical_overlap(reference, historical[kind], kind, records, result)
    return historical


def collect(build, out, reference, *, experiment=None):
    """Shared fixed-panel capture; the supplied module owns rule-specific checks."""
    spec = experiment or sys.modules[__name__]
    require(not out.exists() and (out.is_relative_to(ROOT / "artifacts") or not out.is_relative_to(ROOT)), "fresh output required")
    data, world, saved, model = spec.load_inputs()
    require(not (reference / "FAILED.txt").exists() and digest(reference / "manifest.json") == spec.MANIFEST_SHA and
            digest(reference / "results.json.gz") == spec.INPUT_SHA, "wrong historical bundle")
    source, cache = build / "toy-factory-garden-landing", build / "CMakeCache.txt"
    settings = order.previous.growth.water.check_build(cache)
    require(settings["CMAKE_HOME_DIRECTORY"] == str(ROOT / "sim"), "wrong source tree")
    identities, sources = {"binary": digest(source), "cache": digest(cache)}, source_files()
    out.mkdir(parents=True)
    try:
        for directory in ("bin", "frames", "inputs"):
            (out / directory).mkdir()
        binary = out / "bin/garden-landing"
        shutil.copy2(source, binary)
        shutil.copy2(cache, out / "CMakeCache.txt")
        shutil.copy2(ROOT / spec.PROTOCOL, out / "protocol.md")
        snapshot_sources(out, sources)
        for path, sha in spec.INPUTS.items():
            shutil.copy2(ROOT / path, out / "inputs" / Path(path).name)
            require(digest(out / "inputs" / Path(path).name) == sha, "input changed")
        with (out / "model.tgl").open("xb") as stream:
            stream.write(model)
        require(digest(out / "model.tgl") == data["models"][late.MODEL]["sha256"], "wrong model")

        def one(case):
            arms = {}
            for arm in ARMS:
                runs, calls, traces = {}, [], {}
                for label in LABELS:
                    name, args = stem(case, arm, label), spec.arguments(world, case, arm, label)
                    call = {"case": case["id"], "arm": arm, "label": label, "args": args}
                    write_json(out / (name + "-call.json"), call)
                    raw = order.training.native(binary, out, *args)
                    write_json(out / (name + "-result.json"), raw)
                    path = out / "frames" / (name + ".raw")
                    pixels = path.read_bytes()
                    require(len(pixels) == 240 * 240 * 2 and
                            f"{zlib.crc32(pixels):08x}" == raw["framebuffer_crc32"], "framebuffer corrupt")
                    frame = {"raw_sha256": digest(path), "framebuffer_crc32": raw["framebuffer_crc32"]}
                    runs[label] = {"result": raw, "frame": frame}
                    calls.append(call)
                    if label in ("trace", "repeat"):
                        paths = {}
                        for kind in KINDS:
                            path = out / (name + "-" + kind + ".jsonl")
                            target = Path(str(path) + ".gz")
                            compress(path, target)
                            paths[kind] = {"path": target.name, "sha256": digest(target)}
                        traces[label] = paths
                    if label != "repeat":
                        write_png(out / "frames" / (name + ".png"), 240, 240, rgb565be_to_rgb888(pixels))
                    print(name + ": captured", flush=True)
                require(runs["trace"] == runs["repeat"] and all(traces["trace"][k]["sha256"] ==
                        traces["repeat"][k]["sha256"] for k in KINDS), "non-deterministic repeated replay")
                rows = [adults.read_trace(out / traces["trace"][k]["path"]) for k in KINDS]
                analysis = spec.analyze(*rows, runs["trace"]["result"], case, arm)
                historical = None
                if arm == "control":
                    historical = spec.historical_check(reference, saved, case, rows, runs["trace"]["result"])
                arms[arm] = {"runs": runs, "calls": calls, "traces": traces["trace"],
                             "historical_traces": historical, "analysis": analysis}
            spec.check_pair(case, arms, saved)
            print(case["id"] + ": prefix, historical overlap, repeated traces and focal budgets verified", flush=True)
            return {"case": case, "arms": arms}

        with ThreadPoolExecutor(max_workers=2) as pool:
            cases = list(pool.map(one, spec.CASES))
        require(source_files() == sources and digest(source) == digest(binary) == identities["binary"] and
                digest(cache) == identities["cache"] and all(digest(ROOT / p) == h for p, h in spec.INPUTS.items()) and
                digest(reference / "manifest.json") == spec.MANIFEST_SHA, "source/build/input changed")
        # Rows are case/control, case/candidate; columns prefix, first day, day 256.
        gallery = contact_sheet(out, [[{"id": stem(c, a, label),
            "framebuffer": "frames/" + stem(c, a, label) + ".raw"} for label in ("prefix", "day1", "trace")]
            for c in spec.CASES for a in ARMS])
        value = {"rule": spec.RULE, "inputs": spec.INPUTS, "protocol_sha256": digest(out / "protocol.md"), "source_sha256": sources,
            "build": identities, "settings": settings, "model": data["models"][late.MODEL], "world": world["case"],
            "full_replays": 20, "checkpoint_replays": 20, "training_runs": 0, "cases": cases, "gallery": gallery}
        spec.check_value(value)
        order.recovery.founders.write_gzip(out / "results.json.gz", value)
        write_json(out / "manifest.json", {"rule": spec.RULE, "status": "complete", "artifacts": {
            str(p.relative_to(out)): digest(p) for p in sorted(out.rglob("*")) if p.is_file()}})
    except BaseException as error:
        (out / "FAILED.txt").write_text(str(error) + "\n")
        raise


def verify(path, *, experiment=None):
    spec = experiment or sys.modules[__name__]
    bundle = path if path.is_dir() else None
    if bundle:
        require(not (bundle / "FAILED.txt").exists(), "incomplete experiment")
        manifest = json.loads((bundle / "manifest.json").read_text())
        require(manifest["rule"] == spec.RULE and manifest["status"] == "complete", "wrong manifest")
        for name in manifest["artifacts"]:
            artifact(bundle, manifest, name)
        path = bundle / "results.json.gz"
    with gzip.open(path, "rt") as stream:
        value = json.load(stream)
    spec.check_value(value)
    if bundle:
        require(digest(bundle / "bin/garden-landing") == value["build"]["binary"] and
                digest(bundle / "CMakeCache.txt") == value["build"]["cache"] and
                digest(bundle / "protocol.md") == value["protocol_sha256"] and
                digest(bundle / "model.tgl") == value["model"]["sha256"], "capture identity differs")
        for entry in value["cases"]:
            case = entry["case"]
            for arm, a in entry["arms"].items():
                rows = []
                for kind in KINDS:
                    p = bundle / a["traces"][kind]["path"]
                    require(digest(p) == a["traces"][kind]["sha256"] ==
                            digest(bundle / p.name.replace("-trace-", "-repeat-")), "trace identity/repeat differs")
                    rows.append(adults.read_trace(p))
                require(spec.analyze(*rows, a["runs"]["trace"]["result"], case, arm) == a["analysis"], "raw reanalysis differs")
                for label in LABELS:
                    name, run = stem(case, arm, label), a["runs"][label]
                    require(json.loads((bundle / (name + "-result.json")).read_text()) == run["result"] and
                            digest(bundle / "frames" / (name + ".raw")) == run["frame"]["raw_sha256"] and
                            json.loads((bundle / (name + "-call.json")).read_text()) ==
                            next(c for c in a["calls"] if c["label"] == label), "native receipt differs")
    print("Verified " + spec.RULE + ": five pairs, common prefixes, budgets and harm checks; no new simulation.")
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--out", type=Path)
    mode.add_argument("--verify", type=Path)
    parser.add_argument("--build", type=Path, default=ROOT / "build-host")
    parser.add_argument("--reference", type=Path, default=ROOT / "artifacts/garden-landing-late-v1")
    args = parser.parse_args()
    try:
        if args.verify:
            verify(args.verify.resolve())
        else:
            collect(args.build.resolve(), args.out.resolve(), args.reference.resolve())
        return 0
    except (OSError, RuntimeError, ValueError, KeyError, TypeError, StopIteration) as error:
        print("root-choice experiment failed: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
