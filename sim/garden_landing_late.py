#!/usr/bin/env python3
"""Unchanged S35 replays with late seedling resource receipts; four native calls."""

from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import gzip
import json
from pathlib import Path
import shutil
import sys
import zlib

import garden_landing_order_regressions as prior
from garden_experiments import compress, digest, snapshot_sources, source_files, write_json
from garden_gallery import artifact, rgb565be_to_rgb888, write_png
from garden_resources import require

order, adults = prior.previous, prior.previous.recovery.adults
ROOT, DAY, STEP, STOP = prior.ROOT, prior.DAY, prior.STEP, prior.STOP
START, MODEL = 218 * DAY, "single-s6d697835-live"
RULE = "garden-landing-late-resources-v1"
PROTOCOL = "benchmarks/garden-seasons/landing-late-resources-protocol.md"
REGRESSION = "benchmarks/garden-seasons/landing-order-regressions-results.json.gz"
REGRESSION_SHA = "9163a9ba3839ecd07dcc35773d8945aa90830add3ea44e33f201a369bb6a20d6"
INPUTS = {prior.INPUT: prior.INPUT_SHA, REGRESSION: REGRESSION_SHA,
          order.previous.MODELS: order.previous.MODEL_SHA}
ARMS, LABELS, KINDS = order.ARMS, ("trace", "repeat"), ("stand", "adult")


def load_inputs():
    data = prior.load(ROOT / prior.INPUT, prior.INPUT_SHA)
    order.check_value(data)
    regression = prior.load(ROOT / REGRESSION, REGRESSION_SHA)
    world = next(w for w in data["worlds"] if w["model"] == MODEL)
    case = next(c for c in regression["cases"] if c["model"] == MODEL and c["context"] == "control")
    models = prior.load(ROOT / order.previous.MODELS, order.previous.MODEL_SHA)
    return data, world, case, bytes.fromhex(models[data["models"][MODEL]["model"]])


def arguments(world, arm, label):
    require(arm in ARMS and label in LABELS, "wrong replay arm/label")
    stem = arm + "-" + label
    args = ["placement-replay", "model.tgl", world["case"]["scenario"], "0x" + world["case"]["seed"],
            "--climate", "seasonal", "--ledger", "--shoot-reserve", "on", "--seed-placement", "spacing"]
    if arm == "rotating":
        args += ["--seed-order", "rotating", "--seed-order-after", str(prior.AT)]
    args += ["--ticks", str(STOP), "--framebuffer", "frames/" + stem + ".raw", "--stand-order"]
    for kind in KINDS:
        args += ["--" + kind + "-trace", stem + "-" + kind + ".jsonl",
                 "--" + kind + "-start", str(START), "--" + kind + "-stop", str(STOP)]
    return args


def historical_boundary(bundle, old):
    require(not (bundle / "FAILED.txt").exists() and digest(bundle / "manifest.json") == prior.MANIFEST_SHA,
            "wrong original bundle")
    boundary = {}
    for kind in KINDS:
        meta = old["traces"][kind]
        path = bundle / meta["path"]
        require(digest(path) == meta["sha256"], "original trace differs")
        with gzip.open(path, "rt") as stream:
            require(json.loads(next(stream)) == prior.header(kind), "wrong original header")
            last = None
            for tick in range(prior.AT, START + STEP, STEP):
                row = json.loads(next(stream))
                require(row["tick"] == tick, "original trace clock differs")
                last = row
            require(json.loads(next(stream)) == prior.footer(kind, old["result"]) and not stream.read(),
                    "original trace incomplete")
        require(digest(path) == meta["sha256"], "original trace changed")
        boundary[kind] = last
    return boundary


def history_summary(life, steps):
    """Reconcile the observed first day without extending censored follow-up."""
    first = life["birth_tick"]
    last = min(first + DAY, life["death_tick"] or STOP, STOP)
    require(START < first <= STOP and [s["tick"] for s in steps] == list(range(first, last + STEP, STEP)),
            "missing/reordered first-day sample")
    total, before, shortages = adults.budget(), None, []
    light, growth, max_stress = Counter(), [], 0
    for s in steps:
        tick, p = s["tick"], s["plant"]
        require(p["id"] == life["id"] and p["birth"] == first, "wrong first-day identity")
        receipt = adults.transfers({"tick": tick, **p}, life, before)
        adults.accumulate(total, receipt, before is None)
        before = p["stages"][-1]
        require(adults.vector(s["sun"], 2, 255) and s["sun"][0] == (64 + tick // STEP) % 256,
                "wrong first-day sun clock")
        light["samples"] += 1
        light["sun_sum"] += s["sun"][1]
        light["active_leaf_sum"] += p["active_leaves"]
        light["no_active_leaf_samples"] += p["active_leaves"] == 0
        dead = tick == life["death_tick"]
        body = s["body"]
        require((body is None) == dead and (dead or body["id"] == life["id"] and
                (body["nodes"], body["roots"]) == (p["stages"][-1][4], p["roots"])), "body/receipt mismatch")
        v = s["visit"]
        require(v["id"] == life["id"] and v["produced"] == (v["blockers"] == 0) and
                p["stages"][3][:2] == [v["energy"], v["water"]] and
                (receipt["energy"]["reproduction"], receipt["water"]["reproduction"]) ==
                (48 * v["produced"], 24 * v["produced"]), "wrong first-day seed fee")
        if p["uptake"]:
            max_stress = max(max_stress, p["stages"][1][2])
            if tick % (4 * STEP) == 0:
                cause = {2: "energy", 4: "water", 6: "energy+water"}.get(p["stages"][1][3] & 6)
                if cause:
                    shortages.append({"tick": tick, "cause": cause, "stress": p["stages"][1][2]})
        if receipt["energy"]["growth"] or receipt["water"]["growth"]:
            growth.append({"tick": tick, "energy": receipt["energy"]["growth"], "water": receipt["water"]["growth"],
                           "nodes": p["stages"][-1][4], "roots": p["roots"], "active_leaves": p["active_leaves"]})
    return {"window": [first, last], "samples": len(steps), "status": order.bank.child_status(life, STOP),
            "right_censored": last < first + DAY and life["death_tick"] is None,
            "resources": total, "first_shortage": shortages[0] if shortages else None,
            "death_shortage": shortages[-1]["cause"] if life["death_tick"] == last else None,
            "shortages": shortages, "max_stress": max_stress, "light": dict(light), "growth": growth}


def analyze(stand, resource, result, arm):
    require(stand[0] == prior.header("stand", START, STOP) and resource[0] == prior.header("adult", START, STOP),
            "wrong late trace window")
    checked = order.analyze(stand, resource, result, arm)
    children = []
    for life in result["lineages"]:
        birth = life["birth_tick"]
        if birth <= START:
            continue
        end = min(birth + DAY, life["death_tick"] or STOP, STOP)
        steps = []
        for tick in range(birth, end + STEP, STEP):
            index = (tick - START) // STEP + 1
            row, r = stand[index], resource[index]
            steps.append({"tick": tick, "sun": r["sun"], "climate": row["climate"], "soil_water": r["soil_water"],
                "plant": next(p for p in r["plants"] if p["id"] == life["id"]),
                "body": next((p for p in row["bodies"] if p["id"] == life["id"]), None),
                "visit": next(p for p in row["reproduction"] if p["id"] == life["id"]),
                "bids": [b for b in row["bids"] if b["id"] == life["id"]]})
        b = resource[(birth - START) // STEP + 1]
        seed = next(s for s in result["seeds"] if s["child_id"] == life["id"])
        children.append({"life": life, "seed": seed, "birth_check": next(s for s in b["seeds"] if s[9] == life["id"]),
            "ancestry": prior.ancestry({"result": result}, life["id"]), "steps": steps,
            "first_day": history_summary(life, steps),
            "observed_resources": next(p for p in checked["gates"]["resources"]["plants"] if p["id"] == life["id"])})
    return {"all_plants": checked, "children": children}


def check_value(value):
    data, world, regression, _ = load_inputs()
    require(value["rule"] == RULE and value["inputs"] == INPUTS and value["protocol_sha256"] == digest(ROOT / PROTOCOL) and
            value["model"] == data["models"][MODEL] and value["case"] == world["case"] and
            value["full_replays"] == 4 and value["checkpoint_replays"] == value["training_runs"] == 0 and
            set(value["arms"]) == set(ARMS), "wrong late trace identity/budget")
    for arm, a in value["arms"].items():
        old = world["contexts"]["control"][arm]
        require(a["result"] == old["result"] and a["frame"] == old["frames"]["256"] and
                a["historical_traces"] == old["traces"] and a["repeat_historical_verified"] is True and
                a["calls"] == [{"arm": arm, "label": label, "args": arguments(world, arm, label)} for label in LABELS],
                "historical trajectory/pixels/calls differ")
        checked = a["analysis"]["all_plants"]
        require(checked["outcomes"] == old["audit"]["outcomes"] and
                (checked["gates"]["start"], checked["gates"]["stop"]) == (START, STOP), "outcomes/window differ")
        expected = [p for p in a["result"]["lineages"] if p["birth_tick"] > START]
        children = a["analysis"]["children"]
        require([p["life"] for p in children] == expected, "late cohort changed")
        for p in children:
            life, seed = p["life"], p["seed"]
            require(seed in a["result"]["seeds"] and seed["child_id"] == life["id"] and
                    seed["parent"] == life["parent"] and seed["end_tick"] == life["birth_tick"] and
                    p["ancestry"] == prior.ancestry(a, life["id"]), "birth/ancestry differs")
            check = p["birth_check"]
            require(len(check) == 11 and (check[0], check[2], check[3], check[8], check[9]) ==
                    (seed["parent"], seed["column"], 0, 2, life["id"]) and check[4] >= 12 and check[5] >= 80,
                    "wrong germination receipt")
            require(p["first_day"] == history_summary(life, p["steps"]) and
                    p["observed_resources"] == next(r for r in checked["gates"]["resources"]["plants"] if r["id"] == life["id"]),
                    "resource reanalysis differs")
            if life["death_tick"] and life["death_tick"] <= life["birth_tick"] + DAY:
                require(p["observed_resources"]["resources"] == p["first_day"]["resources"] and
                        p["observed_resources"]["death_shortage"] == p["first_day"]["death_shortage"], "death budget differs")
        for name in ("closing", "tail"):
            start, stop = regression["arms"][arm][name]["window"]
            actual = [p["life"] for p in children if start < p["life"]["birth_tick"] <= stop]
            require(actual == [p["life"] for p in regression["arms"][arm][name]["children"]], "cohort history differs")


def collect(build, out, reference):
    require(not out.exists() and (out.is_relative_to(ROOT / "artifacts") or not out.is_relative_to(ROOT)), "fresh output required")
    data, world, _, model = load_inputs()
    boundaries = {arm: historical_boundary(reference, world["contexts"]["control"][arm]) for arm in ARMS}
    source, cache = build / "toy-factory-garden-landing", build / "CMakeCache.txt"
    settings = order.previous.growth.water.check_build(cache)
    require(settings["CMAKE_HOME_DIRECTORY"] == str(ROOT / "sim"), "wrong source tree")
    identities, sources = {"binary": digest(source), "cache": digest(cache)}, source_files()
    out.mkdir(parents=True)
    try:
        (out / "bin").mkdir()
        (out / "frames").mkdir()
        (out / "inputs").mkdir()
        binary = out / "bin/garden-landing"
        shutil.copy2(source, binary)
        shutil.copy2(cache, out / "CMakeCache.txt")
        shutil.copy2(ROOT / PROTOCOL, out / "protocol.md")
        snapshot_sources(out, sources)
        for path, sha in INPUTS.items():
            shutil.copy2(ROOT / path, out / "inputs" / Path(path).name)
            require(digest(out / "inputs" / Path(path).name) == sha, "input differs")
        with (out / "model.tgl").open("xb") as stream:
            stream.write(model)
        require(digest(out / "model.tgl") == data["models"][MODEL]["sha256"], "wrong model")

        def one(arm):
            old = world["contexts"]["control"][arm]
            traces, calls = {}, []
            for label in LABELS:
                args = arguments(world, arm, label)
                call = {"arm": arm, "label": label, "args": args}
                write_json(out / (arm + "-" + label + "-call.json"), call)
                raw = order.training.native(binary, out, *args)
                write_json(out / (arm + "-" + label + "-result.json"), raw)
                frame = out / "frames" / (arm + "-" + label + ".raw")
                pixels = frame.read_bytes()
                require({**raw, "framebuffer_crc32": None} == old["result"] and
                        len(pixels) == 240 * 240 * 2 and digest(frame) == old["frames"]["256"]["raw_sha256"] and
                        raw["framebuffer_crc32"] == old["frames"]["256"]["framebuffer_crc32"] == f"{zlib.crc32(pixels):08x}",
                        "historical trajectory/pixels changed")
                paths = []
                for kind in KINDS:
                    path = out / (arm + "-" + label + "-" + kind + ".jsonl")
                    compressed = Path(str(path) + ".gz")
                    compress(path, compressed)
                    paths.append(compressed)
                traces[label] = paths
                calls.append(call)
            require(all(digest(a) == digest(b) for a, b in zip(traces["trace"], traces["repeat"], strict=True)), "trace repeat differs")
            rows = [adults.read_trace(p) for p in traces["trace"]]
            require(dict(zip(KINDS, (r[1] for r in rows), strict=True)) == boundaries[arm], "day-218 overlap differs")
            analysis = analyze(*rows, old["result"], arm)
            write_png(out / "frames" / (arm + ".png"), 240, 240, rgb565be_to_rgb888(
                (out / "frames" / (arm + "-trace.raw")).read_bytes()))
            print(arm + ": historical ledger/pixels, overlap, repeated traces and late budgets verified", flush=True)
            return arm, {"result": old["result"], "frame": old["frames"]["256"], "calls": calls,
                "historical_traces": old["traces"], "boundary": boundaries[arm], "repeat_historical_verified": True,
                "analysis": analysis, "traces": {kind: {"path": p.name, "sha256": digest(p)}
                    for kind, p in zip(KINDS, traces["trace"], strict=True)}}

        with ThreadPoolExecutor(max_workers=2) as pool:
            arms = dict(pool.map(one, ARMS))
        require(source_files() == sources and digest(source) == digest(binary) == identities["binary"] and
                digest(cache) == identities["cache"] and all(digest(ROOT / p) == h for p, h in INPUTS.items()), "source/build/input changed")
        value = {"rule": RULE, "inputs": INPUTS, "protocol_sha256": digest(out / "protocol.md"), "source_sha256": sources,
            "build": identities, "settings": settings, "model": data["models"][MODEL], "case": world["case"],
            "full_replays": 4, "checkpoint_replays": 0, "training_runs": 0, "arms": arms}
        check_value(value)
        order.recovery.founders.write_gzip(out / "results.json.gz", value)
        write_json(out / "manifest.json", {"rule": RULE, "status": "complete", "artifacts": {
            str(p.relative_to(out)): digest(p) for p in sorted(out.rglob("*")) if p.is_file()}})
    except BaseException as error:
        (out / "FAILED.txt").write_text(str(error) + "\n")
        raise


def verify(path):
    bundle = path if path.is_dir() else None
    if bundle:
        require(not (bundle / "FAILED.txt").exists(), "incomplete capture")
        manifest = json.loads((bundle / "manifest.json").read_text())
        require(manifest["rule"] == RULE and manifest["status"] == "complete", "wrong manifest")
        for name in manifest["artifacts"]:
            artifact(bundle, manifest, name)
        path = bundle / "results.json.gz"
    with gzip.open(path, "rt") as stream:
        value = json.load(stream)
    check_value(value)
    if bundle:
        require(digest(bundle / "bin/garden-landing") == value["build"]["binary"] and
                digest(bundle / "CMakeCache.txt") == value["build"]["cache"] and
                digest(bundle / "protocol.md") == value["protocol_sha256"] and
                digest(bundle / "model.tgl") == value["model"]["sha256"], "capture identity differs")
        for arm, a in value["arms"].items():
            rows = []
            for kind in KINDS:
                path = bundle / a["traces"][kind]["path"]
                require(digest(path) == a["traces"][kind]["sha256"] ==
                        digest(bundle / path.name.replace("-trace-", "-repeat-")), "trace identity/repeat differs")
                rows.append(adults.read_trace(path))
            require(analyze(*rows, a["result"], arm) == a["analysis"] and
                    dict(zip(KINDS, (r[1] for r in rows), strict=True)) == a["boundary"], "raw reanalysis differs")
            for label in LABELS:
                stem = arm + "-" + label
                expected = {**a["result"], "framebuffer_crc32": a["frame"]["framebuffer_crc32"]}
                require(json.loads((bundle / (stem + "-result.json")).read_text()) == expected and
                        digest(bundle / "frames" / (stem + ".raw")) == a["frame"]["raw_sha256"] and
                        json.loads((bundle / (stem + "-call.json")).read_text()) == next(c for c in a["calls"] if c["label"] == label),
                        "native receipt differs")
    print("Verified unchanged late outcomes, first-day budgets and censored tail; no new simulation.")
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--out", type=Path)
    mode.add_argument("--verify", type=Path)
    parser.add_argument("--build", type=Path, default=ROOT / "build-host")
    parser.add_argument("--reference", type=Path, default=ROOT / "artifacts/garden-landing-order-v1")
    args = parser.parse_args()
    try:
        if args.verify:
            verify(args.verify.resolve())
        else:
            collect(args.build.resolve(), args.out.resolve(), args.reference.resolve())
        return 0
    except (OSError, RuntimeError, ValueError, KeyError, TypeError, StopIteration) as error:
        print("late resource trace failed: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
