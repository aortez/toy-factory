#!/usr/bin/env python3
"""Fixed seasonal vacancy assay: refill, reproduction and later stalls, no training."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import gzip
import json
from pathlib import Path
import shutil
import sys
import zlib

import garden_landing_placement_turnover as prior
from garden_experiments import compress, digest, snapshot_sources, source_files, write_json
from garden_gallery import artifact, contact_sheet
from garden_resources import require

ROOT, DAY, STEP = prior.ROOT, prior.DAY, prior.STEP
AT, STOP = 158 * DAY, 256 * DAY
PERIODS = ((158, 190), (190, 222), (222, 254))
FRAMES, ARMS = (158, 160, 192, 256), ("control", "vacancy")
RULE = "garden-landing-vacancy-v1"
PROTOCOL = "benchmarks/garden-seasons/landing-vacancy-protocol.md"
MODELS = "benchmarks/garden-seasons/landing-multiseed-models.json.gz"
MODEL_SHA = "631364e9c1c23c676fb7cf699f630c807b6197cc21b6bc5b317afaf5095e757c"
INPUTS = {prior.INPUT: prior.INPUT_SHA, MODELS: MODEL_SHA}
TARGETS = {"single-s6d697833-live": (20, 14), "multi-s6d697833-live": (26, 18),
           "single-s6d697834-live": (17, 12), "multi-s6d697834-live": (24, 15),
           "single-s6d697835-live": (28, 12), "multi-s6d697835-live": (23, 14)}
placement, growth = prior.previous, prior.previous.growth
recruitment, reach = growth.recruitment, placement.reach


def load_inputs():
    data = prior.germination.load(ROOT / prior.INPUT, prior.INPUT_SHA)
    models = prior.germination.load(ROOT / MODELS, MODEL_SHA)
    for w in prior.panel(data):
        living = [p for p in w["arms"]["spacing"]["result"]["lineages"]
                  if prior.lifetimes.alive(p, AT) and p["birth_tick"] + DAY < AT]
        target = min(living, key=lambda p: (abs(p["column"] - 14), p["id"]))
        require((target["id"], target["column"]) == TARGETS[w["model"]], "frozen target differs")
    return data, {k: bytes.fromhex(v) for k, v in models.items()}


def probe_hash(base, tick, lineage):
    h = 2166136261
    for b in b"GLV1" + b"".join(v.to_bytes(4, "little") for v in (int(base, 16), tick, lineage)):
        h = ((h ^ b) * 16777619) & 0xffffffff
    return f"{h:08x}"


def check_result(result, w, arm, tick, metadata):
    require(result["tick"] == tick and result["model"] == metadata and result["rules"] == 0 and
            result["scenario"] == w["case"]["scenario"] and result["seed"] == w["case"]["seed"] and
            result["climate"]["mode"] == "seasonal" and result["gardener"] is False and
            result["irrigation"] is False and result["ledger_start_tick"] == 0, "wrong replay")
    normalized = result
    removed = [p for p in result["lineages"] if "removal_tick" in p]
    if arm == "vacancy":
        target, column = TARGETS[w["model"]]
        probe = result["vacancy_probe"]
        require(result["kind"] == "landing-vacancy-replay" and set(probe) == {"version", "tick", "lineage", "event"} and
                probe["version"] == 1 and probe["tick"] == AT and probe["lineage"] == target and
                result["run_hash"] == probe_hash(result["placement_run_hash"], AT, target), "wrong vacancy identity")
        event = probe["event"]
        if tick < AT:
            require(event is None and not removed, "early export")
        else:
            require(isinstance(event, dict) and len(removed) == 1 and removed[0]["id"] == target and removed[0]["removal_tick"] == AT and
                    removed[0]["death_tick"] is None and removed[0]["birth_tick"] + DAY < AT and
                    event["tick"] == AT and event["id"] == target and event["column"] == column and
                    event["nodes"] > 0, "missing/wrong adult export")
            require(all(s["birth_tick"] <= AT for s in result["seeds"] if s["parent"] == target), "removed parent bought seed")
        normalized = {k: v for k, v in result.items() if k not in ("vacancy_probe", "placement_run_hash")} | {
            "kind": "landing-placement-replay", "run_hash": result["placement_run_hash"]}
    else:
        require(arm == "control" and not removed and "vacancy_probe" not in result, "export in control")
    placement.common_view(normalized, "spacing")
    records = recruitment.previous.descendants.index_records(result["lineages"], result["seeds"], 0, max(STEP, tick))[0]
    require(sum(p["parent"] != 0 for p in records.values()) == result["births"] and
            sum(p["death_tick"] is not None for p in records.values()) == result["deaths"] and
            sum(p["death_tick"] is None and not p.get("removal_tick") for p in records.values()) == result["living"] and
            sum(s["outcome"] == "pending" for s in result["seeds"]) == result["seed_bank"], "unreconciled ledger")


def credit(plants, start, end):
    # Occupancy ends at export, while the raw death ledger stays untouched.
    # Only the credit arithmetic sees this effective endpoint; its loss field
    # is split below so an artificial removal cannot be reported as mortality.
    projected = [{**p, "death_tick": p.get("removal_tick", p["death_tick"])} for p in plants]
    value = prior.rolling.credit(projected, start, end)
    require(value["ticks"] == prior.rolling.sampled_credit(projected, start, end), "credit oracle differs")
    ids = {p["id"] for p in plants if p.get("removal_tick")}
    removal_lost = sum(p["death_lost_ticks"] for p in value["children"] if p["id"] in ids)
    value["removal_lost_ticks"] = removal_lost
    value["death_lost_ticks"] -= removal_lost
    for p in value["children"]:
        p["removal_lost_ticks"] = p["death_lost_ticks"] if p["id"] in ids else 0
        p["death_lost_ticks"] -= p["removal_lost_ticks"]
    return value


def alive(p, tick):
    return prior.lifetimes.alive(p, tick) and (not p.get("removal_tick") or tick < p["removal_tick"])


def analysis(result, audit, windows, target):
    plants = result["lineages"]
    after = [p for p in audit["plants"] if p["birth_tick"] > AT]
    rows = []
    for p in after:
        children = [c for c in after if c["parent"] == p["id"]]
        # Paired ancestry labels refer to the designated export target even
        # in controls, where that same individual is not actually removed.
        rows.append({**prior.turnover.child_receipt(p, STOP), "column": p["column"],
            "near_vacancy": abs(p["column"] - target[1]) <= 2,
            "removed_parent": p["parent"] == target[0],
            "seeds_created": p["seeds_created"], "children": [c["id"] for c in children],
            "confirmed_children": [c["id"] for c in children if c["outcome"] == "confirmed"]})
    periods = []
    for (a, z), w in zip(PERIODS, windows, strict=True):
        start, end = a * DAY, z * DAY
        require(w["window_ticks"] == [start, end], "wrong seed window")
        cohort = [p for p in rows if start < p["birth_tick"] <= end]
        confirmations = [p["id"] for p in rows if start < p["birth_tick"] + DAY <= end and p["outcome"] == "confirmed"]
        periods.append({"days": [a, z], "credit": credit(plants, start, end),
            "birth_cohort": prior.turnover.cohort(cohort), "birth_ids": [p["id"] for p in cohort],
            "confirmations": confirmations,
            "natural_deaths": [p["id"] for p in plants if p["death_tick"] is not None and start < p["death_tick"] <= end],
            "living_at_end": [p["id"] for p in plants if alive(p, end)],
            "seed_checks": w["summary"], "reachable_open_steps": w["blocked_seed_ecology_samples_with"]})
    return {"post_export_birth_cohort": prior.turnover.cohort(rows), "children": rows, "periods": periods,
            "reproducing_replacements": [p["id"] for p in rows if p["confirmed_children"]],
            "replacement_seed_purchases": sum(p["seeds_created"] for p in rows),
            "near_vacancy_births": sum(p["near_vacancy"] for p in rows),
            "removed_parent_births": sum(p["removed_parent"] for p in rows),
            "last_birth_tick": max((p["birth_tick"] for p in plants if p["parent"]), default=None),
            "last_confirmation_tick": max((p["birth_tick"] + DAY for p in plants
                if p["parent"] and prior.lifetimes.confirmed(p, STOP)), default=None),
            "post_export_natural_deaths": sum(p["death_tick"] is not None and p["death_tick"] > AT for p in plants),
            "living_at_stop": [p["id"] for p in plants if alive(p, STOP)]}


def window_audits(result, child_path, reach_path, full):
    selected = [[] for _ in PERIODS]
    with gzip.open(child_path, "rt") as stream:
        for line in stream:
            row = json.loads(line)
            if "seeds" not in row:
                continue
            for i, (a, z) in enumerate(PERIODS):
                if a * DAY < row["tick"] <= z * DAY:
                    selected[i].append({"tick": row["tick"], "seeds": row["seeds"]})
    # Seed-check receipts occur before the post-step export. For their living
    # witnesses only, occupancy ceases on the next ecology check (not at AT).
    view = {**result, "lineages": [{**p, "death_tick": p["removal_tick"] + STEP}
                                  if p.get("removal_tick") else p for p in result["lineages"]]}
    return [prior.reach_window.analyze_window(view, rows,
        prior.reach_window.extract_window(reach_path, full, a * DAY, z * DAY), a * DAY, z * DAY)
        for (a, z), rows in zip(PERIODS, selected, strict=True)]


def prefix_equal(a, b):
    count = 0
    with gzip.open(a, "rt") as left, gzip.open(b, "rt") as right:
        require(next(left) == next(right), "trace header differs")
        for tick in range(STEP, AT + STEP, STEP):
            x, y = next(left), next(right)
            require(x == y and json.loads(x)["tick"] == tick, "pre-export trace differs")
            count += 1
    return count


def check_boundary(before, after):
    event = after["vacancy_probe"]["event"]
    require(event["before_world_hash"] == before["world_hash"] and event["before_run_hash"] == before["run_hash"] and
            event["after_world_hash"] == after["world_hash"] and event["after_run_hash"] == after["placement_run_hash"],
            "boundary hashes differ")
    require(before["seeds"] == after["seeds"] and before["deaths"] == after["deaths"] and
            before["living"] == after["living"] + 1 and before["nodes"] == after["nodes"] + event["nodes"],
            "boundary census differs")
    expected = [{**p, "removal_tick": event["tick"]} if p["id"] == event["id"] else p
                for p in before["lineages"]]
    require(after["lineages"] == expected, "export changed other lineage facts")


def collect(build, out, jobs):
    require(1 <= jobs <= 4 and not out.exists() and
            (out.is_relative_to(ROOT / "artifacts") or not out.is_relative_to(ROOT)), "fresh output/jobs 1..4 required")
    saved, models = load_inputs()
    source, cache = build / "toy-factory-garden-landing", build / "CMakeCache.txt"
    settings = growth.water.check_build(cache)
    require(settings["CMAKE_HOME_DIRECTORY"] == str(ROOT / "sim"), "wrong source tree")
    sources = source_files()
    identities = {"binary": digest(source), "cache": digest(cache)}
    out.mkdir(parents=True)
    try:
        for directory in ("bin", "models", "inputs", "frames"):
            (out / directory).mkdir()
        binary = out / "bin/garden-landing"
        shutil.copy2(source, binary)
        shutil.copy2(cache, out / "CMakeCache.txt")
        shutil.copy2(ROOT / PROTOCOL, out / "protocol.md")
        snapshot_sources(out, sources)
        for name in INPUTS:
            shutil.copy2(ROOT / name, out / "inputs" / Path(name).name)
        for key, meta in saved["models"].items():
            path = out / "models" / (key + ".tgl")
            with path.open("xb") as stream:
                stream.write(models[meta["model"]])
            require(digest(path) == meta["sha256"], "model identity differs")

        def one(w):
            arms = {}
            for arm in ARMS:
                stem = arm + "--" + w["id"]
                args = ("vacancy-replay" if arm == "vacancy" else "placement-replay",
                    "models/" + w["model"] + ".tgl", w["case"]["scenario"], "0x" + w["case"]["seed"],
                    "--climate", "seasonal", "--ledger", "--shoot-reserve", "on", "--seed-placement", "spacing")
                if arm == "vacancy":
                    args += ("--vacancy-at", AT, "--vacancy-lineage", TARGETS[w["model"]][0])
                frames, checkpoints = {}, {}
                for day in FRAMES[:-1]:
                    frame_result, frame = growth.capture(binary, out, args, day * DAY, stem + "-day" + str(day))
                    repeat_path = out / "frames" / (stem + "-day" + str(day) + "-repeat.raw")
                    repeated = placement.training.native(binary, out, *args, "--ticks", day * DAY, "--framebuffer", repeat_path)
                    check_result(frame_result, w, arm, day * DAY, saved["models"][w["model"]]["metadata"])
                    require(repeated == frame_result and digest(repeat_path) == frame["raw_sha256"], "checkpoint repeat differs")
                    frames[str(day)], checkpoints[str(day)] = frame, frame_result
                    if day == 192 and arm == "control":
                        old = w["arms"]["spacing"]
                        require({**frame_result, "framebuffer_crc32": None} == old["result"] and
                                frame["raw_sha256"] == old["frame"]["raw_sha256"], "archived control differs")
                traces = [out / (stem + suffix + ".jsonl") for suffix in ("-children", "-reach")]
                repeat_traces = [p.with_name(p.stem + "-repeat.jsonl") for p in traces]
                raw, repeat_raw = (out / "frames" / (stem + suffix) for suffix in ("-traced.raw", "-repeat.raw"))
                flags = ("--recruitment-trace", "--reach-trace")
                result = placement.training.native(binary, out, *args, "--ticks", STOP, "--framebuffer", raw,
                    *(v for pair in zip(flags, traces, strict=True) for v in pair))
                repeated = placement.training.native(binary, out, *args, "--ticks", STOP, "--framebuffer", repeat_raw,
                    *(v for pair in zip(flags, repeat_traces, strict=True) for v in pair))
                plain, frame = growth.capture(binary, out, args, STOP, stem + "-day256")
                require(result == repeated == plain and digest(raw) == digest(repeat_raw) == frame["raw_sha256"] and
                        all(digest(a) == digest(b) for a, b in zip(traces, repeat_traces, strict=True)), "observer/repeat differs")
                check_result(result, w, arm, STOP, saved["models"][w["model"]]["metadata"])
                frames["256"] = frame
                result = {**result, "framebuffer_crc32": None}
                write_json(out / (stem + "-result.json"), result)
                for p in (*traces, *repeat_traces):
                    compress(p, Path(str(p) + ".gz"))
                    p.unlink()
                child_path, reach_path = (Path(str(p) + ".gz") for p in traces)
                audit = recruitment.analyze_trace(child_path, result)
                full = reach.analyze_trace(reach_path, result, audit)
                windows = window_audits(result, child_path, reach_path, full)
                arms[arm] = {"result": result, "audit": audit, "windows": windows,
                    "analysis": analysis(result, audit, windows, TARGETS[w["model"]]),
                    "frames": frames, "checkpoints": checkpoints, "trace_sha256": digest(child_path),
                    "reach_sha256": digest(reach_path), "repeat_and_plain_verified": True}
                print(w["model"] + " / " + arm + ": full history, resources, windows and repeated pixels verified", flush=True)
            check_boundary(arms["control"]["checkpoints"]["158"], arms["vacancy"]["checkpoints"]["158"])
            prefixes = {kind: prefix_equal(out / ("control--" + w["id"] + "-" + kind + ".jsonl.gz"),
                                          out / ("vacancy--" + w["id"] + "-" + kind + ".jsonl.gz"))
                        for kind in ("children", "reach")}
            return {k: w[k] for k in ("id", "model", "case")} | {"target": list(TARGETS[w["model"]]), "arms": arms, "prefix_samples": prefixes}

        with ThreadPoolExecutor(max_workers=jobs) as pool:
            worlds = list(pool.map(one, prior.panel(saved)))
        sheets = {}
        for w in worlds:
            directory = out / "frames" / w["model"]
            directory.mkdir()
            rows = [[{**w["arms"][arm]["frames"][str(day)],
                      "framebuffer": str(out / w["arms"][arm]["frames"][str(day)]["framebuffer"])}
                     for day in FRAMES] for arm in ARMS]
            sheets[w["model"]] = {**contact_sheet(directory, rows), "png": str(directory.relative_to(out) / "contact-sheet.png"),
                                  "sha256": digest(directory / "contact-sheet.png")}
        require(source_files() == sources and digest(source) == digest(binary) == identities["binary"] and
                digest(cache) == identities["cache"] and all(digest(ROOT / p) == h for p, h in INPUTS.items()), "source/build/input changed")
        value = {"rule": RULE, "inputs": INPUTS, "protocol_sha256": digest(out / "protocol.md"), "models": saved["models"],
                 "settings": settings, "build": identities, "source_sha256": sources, "training_runs": 0,
                 "full_replays": 36, "checkpoint_replays": 72, "worlds": worlds, "sheets": sheets}
        check_value(value)
        placement.budget.founders.write_gzip(out / "results.json.gz", value)
        write_json(out / "manifest.json", {"rule": RULE, "status": "complete", "artifacts": {
            str(p.relative_to(out)): digest(p) for p in sorted(out.rglob("*")) if p.is_file()}})
    except BaseException as error:
        (out / "FAILED.txt").write_text(str(error) + "\n")
        raise


def check_value(value):
    require(value["rule"] == RULE and value["inputs"] == INPUTS and value["training_runs"] == 0 and
            value["full_replays"] == 36 and value["checkpoint_replays"] == 72 and
            value["protocol_sha256"] == digest(ROOT / PROTOCOL), "wrong vacancy contract")
    saved, _ = load_inputs()
    require(value["models"] == saved["models"] and len(value["worlds"]) == 6 and
            set(value["sheets"]) == set(TARGETS), "wrong models/panel")
    for w, old in zip(value["worlds"], prior.panel(saved), strict=True):
        require(all(w[k] == old[k] for k in ("id", "model", "case")) and set(w["arms"]) == set(ARMS) and
                w["target"] == list(TARGETS[w["model"]]) and w["prefix_samples"] == {"children": AT // STEP, "reach": AT // STEP}, "wrong world")
        for arm, a in w["arms"].items():
            check_result(a["result"], w, arm, STOP, saved["models"][w["model"]]["metadata"])
            require(a["repeat_and_plain_verified"] is True and set(a["checkpoints"]) == {"158", "160", "192"} and
                    set(a["frames"]) == set(map(str, FRAMES)) and
                    a["analysis"] == analysis(a["result"], a["audit"], a["windows"], TARGETS[w["model"]]), "saved analysis differs")
            records = {p["id"]: p for p in a["result"]["lineages"] if p["parent"]}
            require(len(a["audit"]["plants"]) == len(records) and
                    {p["id"] for p in a["audit"]["plants"]} == set(records), "missing/duplicate child audit")
            for p in a["audit"]["plants"]:
                require({k: p[k] for k in records[p["id"]]} == records[p["id"]], "child audit lineage differs")
                checked = dict(p)
                recruitment.analyze_child(checked, STOP)
                require(checked == p, "first-day accounting differs")
            require(a["audit"]["ecology_samples"] == STOP // STEP and
                    all(t["ecology_samples"] == (z - b) * DAY // STEP for (b, z), t in zip(PERIODS, a["windows"], strict=True)),
                    "audit clock differs")
            for day, checkpoint in a["checkpoints"].items():
                check_result(checkpoint, w, arm, int(day) * DAY, saved["models"][w["model"]]["metadata"])
                require(checkpoint["framebuffer_crc32"] == a["frames"][day]["framebuffer_crc32"], "checkpoint pixel receipt differs")
            for day, frame in a["frames"].items():
                require(frame["tick"] == int(day) * DAY and frame["id"] == arm + "--" + w["id"] + "-day" + day,
                        "wrong frame identity")
            if arm == "control":
                require({**a["checkpoints"]["192"], "framebuffer_crc32": None} == old["arms"]["spacing"]["result"] and
                        a["frames"]["192"]["raw_sha256"] == old["arms"]["spacing"]["frame"]["raw_sha256"], "historical control differs")
        check_boundary(w["arms"]["control"]["checkpoints"]["158"], w["arms"]["vacancy"]["checkpoints"]["158"])
        require(value["sheets"][w["model"]]["rows"] == [[w["arms"][arm]["frames"][str(d)]["id"] for d in FRAMES] for arm in ARMS],
                "sheet inventory differs")


def verify(path):
    bundle = path if path.is_dir() else None
    if bundle:
        require(not (bundle / "FAILED.txt").exists(), "incomplete bundle")
        manifest = json.loads((bundle / "manifest.json").read_text())
        require(manifest["rule"] == RULE and manifest["status"] == "complete", "wrong manifest")
        for name in manifest["artifacts"]:
            artifact(bundle, manifest, name)
        path = bundle / "results.json.gz"
    with gzip.open(path, "rt") as stream:
        value = json.load(stream)
    check_value(value)
    if bundle:
        for w in value["worlds"]:
            for arm, a in w["arms"].items():
                stem = arm + "--" + w["id"]
                child, sites = (bundle / (stem + "-" + k + ".jsonl.gz") for k in ("children", "reach"))
                require(recruitment.analyze_trace(child, a["result"]) == a["audit"], "raw resources differ")
                full = reach.analyze_trace(sites, a["result"], a["audit"])
                require(window_audits(a["result"], child, sites, full) == a["windows"], "raw site windows differ")
                for kind, field in (("children", "trace_sha256"), ("reach", "reach_sha256")):
                    require(digest(bundle / (stem + "-" + kind + ".jsonl.gz")) == a[field] ==
                            digest(bundle / (stem + "-" + kind + "-repeat.jsonl.gz")), "repeat trace differs")
                require(json.loads((bundle / (stem + "-result.json")).read_text()) == a["result"], "saved native result differs")
                for day, f in a["frames"].items():
                    raw = bundle / f["framebuffer"]
                    require(digest(raw) == f["raw_sha256"] and digest(bundle / f["png"]) == f["png_sha256"] and
                            f"{zlib.crc32(raw.read_bytes()):08x}" == f["framebuffer_crc32"], "saved pixels differ")
                    repeats = [stem + "-day" + day + "-repeat.raw"] if day != "256" else [stem + "-traced.raw", stem + "-repeat.raw"]
                    require(all(digest(bundle / "frames" / name) == f["raw_sha256"] for name in repeats), "repeated pixels differ")
            sheet = value["sheets"][w["model"]]
            require(digest(bundle / sheet["png"]) == sheet["sha256"], "sheet differs")
            for kind in ("children", "reach"):
                require(prefix_equal(bundle / ("control--" + w["id"] + "-" + kind + ".jsonl.gz"),
                                     bundle / ("vacancy--" + w["id"] + "-" + kind + ".jsonl.gz")) == AT // STEP, "prefix differs")
    print("Verified fixed vacancy assay, unchanged historical controls, removal accounting and recovery cohorts.")
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--out", type=Path)
    mode.add_argument("--verify", type=Path)
    parser.add_argument("--build", type=Path, default=ROOT / "build-host")
    parser.add_argument("--jobs", type=int, default=2)
    args = parser.parse_args()
    try:
        if args.verify:
            verify(args.verify.resolve())
        else:
            collect(args.build.resolve(), args.out.resolve(), args.jobs)
        return 0
    except (OSError, RuntimeError, ValueError, KeyError, TypeError) as error:
        print("vacancy assay failed: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
