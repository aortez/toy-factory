#!/usr/bin/env python3
"""Frozen shoot-budget screen with a separate budget-arbitration control."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import gzip
import json
from pathlib import Path
import shutil
import sys

import garden_landing_founders as founders
from garden_experiments import compress, digest, source_files, snapshot_sources, write_json
from garden_gallery import artifact, contact_sheet
from garden_resources import require

growth, species = founders.previous, founders.species
adults, training = growth.adults, growth.training
ROOT, DAY, STEP, STOP = growth.ROOT, growth.DAY, growth.STEP, growth.STOP
RULE = "garden-landing-budget-v1"
PROTOCOL = "benchmarks/garden-seasons/landing-budget-protocol.md"
FOUNDER_INPUT = "benchmarks/garden-seasons/landing-founders-results.json.gz"
FOUNDER_SHA = "1641f0cb96d3df0753cb3187f522f408ca9887dba23f88e1e4c4bb01671f0d70"
ARMS = ("off", "32", "eligible", "reserve")
MODES = {"eligible": 1, "reserve": 2}


def probe_hash(base, mode):
    require(type(base) is str and len(base) == 8 and all(c in "0123456789abcdef" for c in base) and
            type(mode) is int and mode in (1, 2), "invalid budget identity")
    h = 2166136261
    for byte in b"GLB1" + int(base, 16).to_bytes(4, "little") + bytes((1, 32, mode)):
        h = ((h ^ byte) * 16777619) & 0xffffffff
    return f"{h:08x}"


def common_view(result, arm):
    if arm in growth.ARMS:
        return growth.common_view(result, arm)
    require(arm in MODES, "unknown budget arm")
    c = result["budget_probe"]
    require(result["kind"] == "landing-budget-replay" and result["rules"] == 0 and
            c == {"version": 1, "node_limit": 32, "shoot_reserve": arm == "reserve", "water_arbitration": "eligible"} and
            type(c["version"]) is int and type(c["node_limit"]) is int and type(c["shoot_reserve"]) is bool and
            result["run_hash"] == probe_hash(result["base_run_hash"], MODES[arm]), "wrong budget identity")
    return {k: v for k, v in result.items() if k not in ("budget_probe", "base_run_hash")} | {
        "kind": "landing-replay", "run_hash": result["base_run_hash"]}


def load_founders():
    require(digest(ROOT / FOUNDER_INPUT) == FOUNDER_SHA, "wrong founder input")
    with gzip.open(ROOT / FOUNDER_INPUT, "rt") as stream:
        return json.load(stream)


def compare(worlds, ordinary, arbitration):
    require(len(worlds) == 12 and all(set(w["arms"]) == set(ARMS) for w in worlds) and
            [w["id"] for w in worlds] == [w["id"] for w in ordinary["worlds"]] ==
            [w["id"] for w in arbitration["worlds"]], "unmatched budget panel")
    comparisons = {}
    for baseline in ("eligible", "32", "off", "veto", "ordinary"):
        mapped = []
        for w, o, a in zip(worlds, ordinary["worlds"], arbitration["worlds"], strict=True):
            control = (a["arms"]["veto"] if baseline == "veto" else o["arms"]["control"] if baseline == "ordinary"
                       else w["arms"][baseline])
            mapped.append({**w, "arms": {"control": control, "water": w["arms"]["reserve"]}})
        groups = {}
        for name in ("all", "steady", "seasonal", "single", "multi"):
            rows = [w for w in mapped if name == "all" or w["case"]["climate"] == name or w["model"].split("-")[0] == name]
            histories = [{w["id"]: w["arms"][arm]["history"] for w in rows} for arm in ("control", "water")]
            groups[name] = {"scores": training.individual.pair_group(*histories, [w["id"] for w in rows]),
                "totals": {arm: growth.scoring.totals([w["arms"][arm]["metrics"] for w in rows])
                           for arm in ("control", "water")}}
        gates = growth.water.gates(groups, mapped)
        comparisons[baseline] = {"groups": groups, "gates": gates, "passes_screen": all(gates.values())}
    return {"comparisons": comparisons, "passes_screen": all(c["passes_screen"] for c in comparisons.values())}


def collect(build, out, jobs):
    require(1 <= jobs <= 4 and not out.exists() and
            (out.is_relative_to(ROOT / "artifacts") or not out.is_relative_to(ROOT)), "fresh output/jobs 1..4 required")
    saved, old_founders = species.load(ROOT / species.INPUT), load_founders()
    models, ordinary, arbitration, _ = growth.load_inputs(ROOT / "benchmarks/garden-seasons")
    source, cache = build / "toy-factory-garden-landing", build / "CMakeCache.txt"
    settings = growth.water.check_build(cache)
    require(settings["CMAKE_HOME_DIRECTORY"] == str(ROOT / "sim"), "wrong source tree")
    sources, identities = source_files(), {"binary": digest(source), "cache": digest(cache)}
    out.mkdir(parents=True)
    try:
        for folder in ("bin", "models", "frames", "inputs"):
            (out / folder).mkdir()
        binary = out / "bin/garden-landing"
        shutil.copy2(source, binary)
        shutil.copy2(cache, out / "CMakeCache.txt")
        shutil.copy2(ROOT / PROTOCOL, out / "protocol.md")
        inputs = {**growth.INPUTS, Path(species.INPUT).name: species.INPUT_SHA, Path(FOUNDER_INPUT).name: FOUNDER_SHA}
        for name, sha in inputs.items():
            shutil.copy2(ROOT / "benchmarks/garden-seasons" / name, out / "inputs" / name)
            require(digest(out / "inputs" / name) == sha, "input changed")
        snapshot_sources(out, sources)
        for key, meta in saved["models"].items():
            with (out / "models" / (key + ".tgl")).open("xb") as stream:
                stream.write(models[meta["model"]])
            require(digest(out / "models" / (key + ".tgl")) == meta["sha256"], "model changed")
        old_founders = {w["id"]: w for w in old_founders["worlds"]}

        def one(w):
            arms, initial = {}, {}
            for arm in ARMS:
                stem = arm + "--" + w["id"]
                args = (("growth-replay" if arm in growth.ARMS else "budget-replay"),
                        "models/" + w["model"] + ".tgl", w["case"]["scenario"], "0x" + w["case"]["seed"],
                        "--climate", w["case"]["climate"], "--ledger",
                        *(("--node-limit", arm) if arm in growth.ARMS else
                          ("--shoot-reserve", "on" if arm == "reserve" else "off")))
                initial[arm] = training.native(binary, out, *args, "--ticks", 0)
                require(common_view(initial[arm], arm) == growth.common_view(w["initial"]["off"], "off"), "initial differs")
                path, early, recruitment = (out / (stem + suffix) for suffix in (".jsonl", "-early.jsonl", "-children.jsonl"))
                options = ("--founder-start", STEP, "--founder-stop", founders.END,
                           "--adult-start", STEP, "--adult-stop", founders.RESOURCE_END)
                result = training.native(binary, out, *args, "--ticks", STOP, "--founder-trace", path,
                    "--adult-trace", early, *options, *(("--recruitment-trace", recruitment) if arm in MODES else ()))
                framed, frame = growth.capture(binary, out, args, STOP, stem)
                require({**framed, "framebuffer_crc32": None} == result, "observer changes result")
                rows, resources = adults.read_trace(path), adults.read_trace(early)
                audit = founders.analyze(rows, result, "32" if arm in MODES else arm, resources,
                                         budget_mode=MODES.get(arm, 0))
                if arm in growth.ARMS:
                    old, f = w["arms"][arm], old_founders[w["id"]]["arms"][arm]
                    require(result == old["result"] and frame["raw_sha256"] == old["frame"]["raw_sha256"] and
                            rows == f["trace"] and resources == f["early_trace"] and audit == f["audit"] and
                            digest(path) == f["trace_sha256"] and digest(early) == f["early_sha256"],
                            "historical control or receipts differ")
                    a = {k: old[k] for k in ("result", "history", "audit", "metrics", "trace_sha256")}
                    a.update(founder_audit=audit, frame=frame, historical_verified=True)
                else:
                    repeat, repeat_early, repeat_children = (out / (stem + suffix) for suffix in
                        ("-repeat.jsonl", "-early-repeat.jsonl", "-children-repeat.jsonl"))
                    repeat_raw = out / "frames" / (stem + "-repeat.raw")
                    repeated = training.native(binary, out, *args, "--ticks", STOP, "--founder-trace", repeat,
                        "--adult-trace", repeat_early, "--recruitment-trace", repeat_children, *options,
                        "--framebuffer", repeat_raw)
                    require(repeated == framed and digest(repeat_raw) == frame["raw_sha256"] and
                            all(digest(x) == digest(y) for x, y in
                                ((path, repeat), (early, repeat_early), (recruitment, repeat_children))),
                            "repeat trace/state/pixels differ")
                    child_audit = growth.recruitment.analyze_trace(recruitment, result)
                    history = training.score_world(common_view(result, arm), w["case"], saved["models"][w["model"]]["metadata"])
                    a = {"result": result, "history": history, "audit": child_audit,
                         "metrics": growth.scoring.metrics(result, child_audit, history), "frame": frame,
                         "founder_trace": rows, "early_trace": resources, "founder_audit": audit,
                         "repeat_and_capture_verified": True}
                    image, early_frame = growth.capture(binary, out, args, 2 * DAY, stem + "-day2")
                    a["early_frame"] = {**early_frame, "result": image}
                    for p in (recruitment, repeat_children, repeat, repeat_early):
                        compress(p, Path(str(p) + ".gz"))
                        p.unlink()
                    a["trace_sha256"] = digest(Path(str(recruitment) + ".gz"))
                    a["species_audit"] = species.analyze_arm(a, arm, w["case"], saved["models"][w["model"]]["metadata"],
                                                            normalize=common_view)
                    require(all(s is None or s[4] <= 32 for p in child_audit["plants"] for r in p["rows"]
                                for s in r["stages"]), "descendant cap exceeded")
                a.update(founder_sha256=digest(path), early_sha256=digest(early))
                for p in (path, early):
                    compress(p, Path(str(p) + ".gz"))
                    p.unlink()
                arms[arm] = a
                print(w["id"] + " / " + arm + ": verified state, receipts and pixels", flush=True)
            require(len({r["run_hash"] for r in initial.values()}) == 4, "identity collision")
            return {k: w[k] for k in ("id", "model", "case")} | {"initial": initial, "arms": arms}

        with ThreadPoolExecutor(max_workers=jobs) as pool:
            worlds = list(pool.map(one, saved["worlds"]))
        sheets = {}
        for climate in ("steady", "seasonal"):
            for early in (False, True):
                name = climate + ("-day2" if early else "")
                directory = out / "frames" / name
                directory.mkdir()
                groups = [[w["arms"][arm]["early_frame" if early else "frame"] for arm in (MODES if early else ARMS)]
                          for w in worlds if w["case"]["climate"] == climate]
                groups = [[{**f, "framebuffer": str(out / f["framebuffer"])} for f in row] for row in groups]
                sheets[name] = {**contact_sheet(directory, groups), "png": "frames/" + name + "/contact-sheet.png",
                                "sha256": digest(directory / "contact-sheet.png")}
        require(source_files() == sources and digest(source) == digest(binary) == identities["binary"] and
                digest(cache) == identities["cache"] and all(digest(ROOT / "benchmarks/garden-seasons" / p) == sha
                    for p, sha in inputs.items()) and all(digest(out / "models" / (k + ".tgl")) == m["sha256"]
                    for k, m in saved["models"].items()), "sources/build/inputs/models changed")
        value = {"rule": RULE, "input_sha256": species.INPUT_SHA, "founder_input_sha256": FOUNDER_SHA,
                 "models": saved["models"], "protocol_sha256": digest(out / "protocol.md"), "build": identities,
                 "settings": settings, "source_sha256": sources, "training_runs": 0, "worlds": worlds,
                 "comparison": compare(worlds, ordinary, arbitration), "sheets": sheets}
        founders.write_gzip(out / "results.json.gz", value)
        write_json(out / "manifest.json", {"rule": RULE, "status": "complete", "artifacts": {
            str(p.relative_to(out)): digest(p) for p in sorted(out.rglob("*")) if p.is_file()}})
    except BaseException as error:
        (out / "FAILED.txt").write_text(str(error) + "\n")
        raise


def verify(path):
    if path.is_dir():
        require(not (path / "FAILED.txt").exists(), "incomplete collection")
        manifest = json.loads((path / "manifest.json").read_text())
        require(manifest["rule"] == RULE and manifest["status"] == "complete", "wrong bundle")
        for name in manifest["artifacts"]:
            artifact(path, manifest, name)
        path = path / "results.json.gz"
    with gzip.open(path, "rt") as stream:
        value = json.load(stream)
    saved, old_founders = species.load(ROOT / species.INPUT), load_founders()
    _, ordinary, arbitration, _ = growth.load_inputs(ROOT / "benchmarks/garden-seasons")
    require(value["rule"] == RULE and value["input_sha256"] == species.INPUT_SHA and
            value["founder_input_sha256"] == FOUNDER_SHA and value["models"] == saved["models"] and
            value["protocol_sha256"] == digest(ROOT / PROTOCOL) and value["training_runs"] == 0, "wrong screen")
    for w, old, f in zip(value["worlds"], saved["worlds"], old_founders["worlds"], strict=True):
        require({k: w[k] for k in ("id", "model", "case")} == {k: old[k] for k in ("id", "model", "case")} and
                w["id"] == f["id"] and set(w["arms"]) == set(ARMS) and set(w["initial"]) == set(ARMS), "wrong panel")
        for arm, a in w["arms"].items():
            require(common_view(w["initial"][arm], arm) == growth.common_view(old["initial"]["off"], "off"), "initial differs")
            require(a["history"] == training.score_world(common_view(a["result"], arm), w["case"],
                    value["models"][w["model"]]["metadata"]) and
                    a["metrics"] == growth.scoring.metrics(a["result"], a["audit"], a["history"]), "score/metrics differ")
            if arm in growth.ARMS:
                require(all(a[k] == old["arms"][arm][k] for k in ("result", "history", "audit", "metrics", "trace_sha256")) and
                        a["frame"]["raw_sha256"] == old["arms"][arm]["frame"]["raw_sha256"] and
                        a["founder_audit"] == f["arms"][arm]["audit"] and
                        a["founder_sha256"] == f["arms"][arm]["trace_sha256"] and
                        a["early_sha256"] == f["arms"][arm]["early_sha256"] and a["historical_verified"] is True,
                        "historical control differs")
            else:
                require(a["repeat_and_capture_verified"] is True and
                        a["founder_audit"] == founders.analyze(a["founder_trace"], a["result"], "32", a["early_trace"],
                                                             budget_mode=MODES[arm]) and
                        (a["founder_audit"]["start"], a["founder_audit"]["stop"]) == (STEP, founders.END) and
                        (a["early_trace"][0]["start"], a["early_trace"][0]["stop"]) == (STEP, founders.RESOURCE_END),
                        "founder budget/window differs")
                require(a["species_audit"] == species.analyze_arm(a, arm, w["case"], value["models"][w["model"]]["metadata"],
                                                                normalize=common_view), "species audit differs")
                require(all(s is None or s[4] <= 32 for p in a["audit"]["plants"] for r in p["rows"] for s in r["stages"]),
                        "descendant cap exceeded")
                early = a["early_frame"]
                require(common_view(early["result"], arm)["tick"] == early["tick"] == 2 * DAY and
                        early["result"]["model"] == value["models"][w["model"]]["metadata"] and
                        early["result"]["framebuffer_crc32"] == early["framebuffer_crc32"], "early frame differs")
        require(len({r["run_hash"] for r in w["initial"].values()}) == 4, "identity collision")
    for climate in ("steady", "seasonal"):
        for early in (False, True):
            name = climate + ("-day2" if early else "")
            require(value["sheets"][name]["rows"] == [[w["arms"][arm]["early_frame" if early else "frame"]["id"]
                    for arm in (MODES if early else ARMS)] for w in value["worlds"] if w["case"]["climate"] == climate],
                    "gallery order differs")
    require(value["comparison"] == compare(value["worlds"], ordinary, arbitration), "comparison/gates differ")
    print("Verified all 48 histories, frozen controls, budget receipts, species accounts and unchanged gates (offline).")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path, default=ROOT / "build-host")
    parser.add_argument("--jobs", type=int, default=2)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--out", type=Path)
    group.add_argument("--verify", type=Path)
    args = parser.parse_args()
    try:
        if args.verify:
            verify(args.verify.resolve())
        else:
            collect(args.build.resolve(), args.out.resolve(), args.jobs)
        return 0
    except (OSError, ValueError, RuntimeError, KeyError, TypeError, StopIteration) as error:
        print("budget screen failed: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
