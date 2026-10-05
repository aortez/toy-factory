#!/usr/bin/env python3
"""Fixed 32-node construction screen; frozen models, no training or promotion."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import gzip
import json
from pathlib import Path
import shutil
import sys

import garden_landing_adults as adults
from garden_experiments import compress, digest, source_files, snapshot_sources, write_json
from garden_gallery import artifact, contact_sheet, rgb565be_to_rgb888, write_png
from garden_resources import require

ROOT, DAY, STEP, STOP = adults.ROOT, adults.DAY, adults.STEP, adults.STOP
arbitration, water, turnover = adults.arbitration, adults.water, adults.previous
training, recruitment, scoring = arbitration.training, arbitration.prior, water.previous
RULE = "garden-landing-growth-v1"
PROTOCOL = "benchmarks/garden-seasons/landing-growth-protocol.md"
ARMS = {"off": 0, "32": 32}
INPUTS = {**arbitration.INPUTS, Path(turnover.INPUT).name: turnover.INPUT_SHA,
          "landing-adult-resources-results.json.gz":
          "88f8468afd443d45a1aa4260052cc92b82fbbda031409837f713012955c6ad3d"}


def load_inputs(root):
    for name, sha in INPUTS.items():
        require(digest(root / name) == sha, "wrong frozen input: " + name)
    models, old = arbitration.load_inputs(root)
    archive = turnover.load(root / Path(turnover.INPUT).name)
    diagnosis = json.loads(gzip.decompress((root / "landing-adult-resources-results.json.gz").read_bytes()))
    return models, old, archive, diagnosis


def probe_hash(base, limit):
    require(type(base) is str and len(base) == 8 and all(c in "0123456789abcdef" for c in base)
            and type(limit) is int and limit in ARMS.values(), "invalid growth identity")
    h = 2166136261
    for b in b"GLC1" + int(base, 16).to_bytes(4, "little") + bytes((1, limit)):
        h = ((h ^ b) * 16777619) & 0xffffffff
    return f"{h:08x}"


def common_view(result, arm):
    require(arm in ARMS, "unknown cap")
    config = result["growth_probe"]
    require(result["kind"] == "landing-growth-replay" and result["rules"] == 0 and
            config == {"version": 1, "node_limit": ARMS[arm], "water_arbitration": "eligible"} and
            type(config["version"]) is int and type(config["node_limit"]) is int and
            result["run_hash"] == probe_hash(result["base_run_hash"], ARMS[arm]), "wrong growth identity")
    return {k: v for k, v in result.items() if k not in ("growth_probe", "base_run_hash")} | {
        "kind": "landing-replay", "run_hash": result["base_run_hash"]}


def compare(worlds, old, archive):
    require(len(worlds) == 12 and [w["id"] for w in worlds] == [w["id"] for w in old["worlds"]] ==
            [w["id"] for w in archive["worlds"]] and all(set(w["arms"]) == set(ARMS) for w in worlds),
            "unmatched growth panel")
    comparisons = {}
    for baseline in ("eligible", "veto", "ordinary"):
        mapped = []
        for w, a, o in zip(worlds, archive["worlds"], old["worlds"], strict=True):
            control = w["arms"]["off"] if baseline == "eligible" else (
                a["arms"]["veto"] if baseline == "veto" else o["arms"]["control"])
            mapped.append({**w, "arms": {"control": control, "water": w["arms"]["32"]}})
        groups = {}
        for name in ("all", "steady", "seasonal", "single", "multi"):
            rows = [w for w in mapped if name == "all" or w["case"]["climate"] == name or
                    w["model"].split("-")[0] == name]
            histories = [{w["id"]: w["arms"][a]["history"] for w in rows} for a in ("control", "water")]
            groups[name] = {"scores": training.individual.pair_group(*histories, [w["id"] for w in rows]),
                "totals": {a: scoring.totals([w["arms"][a]["metrics"] for w in rows]) for a in ("control", "water")}}
        checks = water.gates(groups, mapped)
        comparisons[baseline] = {"control": baseline, "candidate": "32", "groups": groups,
                                 "gates": checks, "passes_screen": all(checks.values())}
    return {"comparisons": comparisons, "passes_screen": all(c["passes_screen"] for c in comparisons.values())}


def capture(binary, root, args, tick, stem):
    raw, png = "frames/" + stem + ".rgb565be", "frames/" + stem + ".png"
    result = training.native(binary, root, *args, "--ticks", tick, "--framebuffer", raw)
    write_png(root / png, 240, 240, rgb565be_to_rgb888((root / raw).read_bytes()))
    return result, {"id": stem, "tick": tick, "framebuffer": raw, "png": png,
                    "framebuffer_crc32": result["framebuffer_crc32"], "raw_sha256": digest(root / raw),
                    "png_sha256": digest(root / png)}


def run_panel(binary, inputs, root, jobs):
    model_bytes, old, archive, diagnosis = load_inputs(inputs)
    (root / "models").mkdir(parents=True)
    (root / "frames").mkdir()
    for key, meta in archive["models"].items():
        path = root / "models" / (key + ".tgl")
        with path.open("xb") as stream:
            stream.write(model_bytes[meta["model"]])
        require(digest(path) == meta["sha256"], "model bytes differ")

    def one(saved):
        name, model, case = saved["id"], saved["model"], saved["case"]
        initial, arms = {}, {}
        for arm in ARMS:
            stem = arm + "--" + name
            args = ("growth-replay", "models/" + model + ".tgl", case["scenario"], "0x" + case["seed"],
                    "--climate", case["climate"], "--node-limit", arm, "--ledger")
            initial[arm] = training.native(binary, root, *args, "--ticks", 0)
            require(common_view(initial[arm], arm) == arbitration.common_view(saved["initial"]["eligible"], "eligible"),
                    "initial biology differs")
            path = root / (stem + ".jsonl")
            adult_path = root / (stem + "-adult.jsonl")
            extra = ("--adult-trace", adult_path, "--adult-start", adults.START, "--adult-stop", adults.END) if name == adults.CASE else ()
            result = training.native(binary, root, *args, "--ticks", STOP, "--recruitment-trace", path, *extra)
            framed, frame = capture(binary, root, args, STOP, stem)
            require({**framed, "framebuffer_crc32": None} == result, "observer changed result")
            repeated_path = root / (stem + "-repeat.jsonl")
            repeated_adult = root / (stem + "-adult-repeat.jsonl")
            repeated_raw = root / "frames" / (stem + "-repeat.rgb565be")
            repeated = training.native(binary, root, *args, "--ticks", STOP, "--recruitment-trace", repeated_path,
                "--framebuffer", repeated_raw, *(("--adult-trace", repeated_adult, "--adult-start", adults.START,
                                                 "--adult-stop", adults.END) if extra else ()))
            require(repeated == framed and digest(repeated_raw) == frame["raw_sha256"] and
                    digest(path) == digest(repeated_path), "repeat state/trace/pixels differ")
            audit = recruitment.analyze_trace(path, result)
            history = scoring.history(common_view(framed, arm), case, archive["models"][model]["metadata"],
                                      "narrow", (root / frame["framebuffer"]).read_bytes())
            for p in (path, repeated_path):
                compress(p, Path(str(p) + ".gz"))
                p.unlink()
            arms[arm] = {"result": result, "history": history, "audit": audit,
                         "metrics": scoring.metrics(result, audit, history), "frame": frame,
                         "trace_sha256": digest(Path(str(path) + ".gz"))}
            if arm == "off":
                control = saved["arms"]["eligible"]
                require(common_view(result, arm) == arbitration.common_view(control["result"], "eligible") and
                        all(arms[arm][k] == control[k] for k in ("history", "audit", "metrics", "trace_sha256")) and
                        frame["raw_sha256"] == control["frame"]["raw_sha256"], "historical eligible control differs")
            if extra:
                records = adults.read_trace(adult_path)
                adult_audit = adults.analyze(records, result)
                require(digest(adult_path) == digest(repeated_adult), "adult repeat differs")
                if arm == "off":
                    require(records == diagnosis["arms"]["eligible"]["trace"] and
                            adult_audit == diagnosis["arms"]["eligible"]["audit"], "historical adult receipts differ")
                if arm == "32":
                    require(all(s is None or s[4] <= 32 for r in records[1:-1] for p in r["plants"]
                                for s in p["stages"]), "cap exceeded in adult trace")
                frames = []
                for tick in adults.FRAMES:
                    image, f = capture(binary, root, args, tick, f"{arm}-focus-{tick}")
                    other_raw = root / "frames" / f"{arm}-focus-{tick}-repeat.rgb565be"
                    traced_path = root / f"{arm}-focus-{tick}.jsonl"
                    other = training.native(binary, root, *args, "--ticks", tick, "--framebuffer", other_raw,
                        "--adult-trace", traced_path, "--adult-start", adults.START, "--adult-stop", tick)
                    require(other == image and digest(other_raw) == f["raw_sha256"], "intermediate observer pixels differ")
                    compress(traced_path, Path(str(traced_path) + ".gz"))
                    traced_path.unlink()
                    frames.append({**f, "result": image})
                arms[arm]["focus"] = {"trace": records, "audit": adult_audit, "frames": frames,
                    "gaps": turnover.gaps(result, turnover.segments(result, adults.START, adults.END))}
                for p in (adult_path, repeated_adult):
                    compress(p, Path(str(p) + ".gz"))
                    p.unlink()
            write_json(root / (stem + ".json"), result)
        require(initial["off"]["run_hash"] != initial["32"]["run_hash"], "cap identity collision")
        require(digest(root / "models" / (model + ".tgl")) == archive["models"][model]["sha256"], "model changed")
        print(name + ": exact old control, repeated cap result/pixels, balanced resource traces", flush=True)
        return {k: saved[k] for k in ("id", "model", "case")} | {"initial": initial, "arms": arms}

    with ThreadPoolExecutor(max_workers=jobs) as pool:
        worlds = list(pool.map(one, archive["worlds"]))
    sheets = {}
    focus = next(w for w in worlds if w["id"] == adults.CASE)
    for name in ("steady", "seasonal", "focus"):
        directory = root / "frames" / name
        directory.mkdir()
        groups = ([focus["arms"][a]["focus"]["frames"] for a in ARMS] if name == "focus" else
                  [[w["arms"][a]["frame"] for a in ARMS] for w in worlds if w["case"]["climate"] == name])
        groups = [[{**f, "framebuffer": str(root / f["framebuffer"])} for f in row] for row in groups]
        sheets[name] = {**contact_sheet(directory, groups), "png": "frames/" + name + "/contact-sheet.png",
                        "sha256": digest(directory / "contact-sheet.png")}
    return {"schema_version": 1, "rule": RULE, "objective": training.individual.RULE, "inputs": INPUTS,
            "plan": archive["plan"], "models": archive["models"], "arms": ARMS, "worlds": worlds,
            "comparison": compare(worlds, old, archive), "sheets": sheets, "training_runs": 0}


def collect(build, inputs, output, jobs):
    require(1 <= jobs <= 4 and not output.exists() and
            (output.is_relative_to(ROOT / "artifacts") or not output.is_relative_to(ROOT)), "fresh output/jobs 1..4 required")
    load_inputs(inputs)
    cache, binary = build / "CMakeCache.txt", build / "toy-factory-garden-landing"
    settings = water.check_build(cache)
    require(settings["CMAKE_HOME_DIRECTORY"] == str(ROOT / "sim"), "wrong source tree")
    sources, identities = source_files(), {"binary": digest(binary), "cache": digest(cache)}
    output.mkdir(parents=True)
    try:
        for folder in ("bin", "inputs", "sim"):
            (output / folder).mkdir()
        frozen = output / "bin/garden-landing"
        shutil.copy2(binary, frozen)
        shutil.copy2(cache, output / "CMakeCache.txt")
        shutil.copy2(ROOT / PROTOCOL, output / "protocol.md")
        for name in INPUTS:
            shutil.copy2(inputs / name, output / "inputs" / name)
        for path in (ROOT / "sim").glob("*.py"):
            shutil.copy2(path, output / "sim" / path.name)
        for name in ("framebuffer_capture.py", "serial_shell.py"):
            dest = output / "scripts/container" / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / "scripts/container" / name, dest)
        snapshot_sources(output, sources)
        result = run_panel(frozen, output / "inputs", output / "panel", jobs)
        require(source_files() == sources and digest(binary) == digest(frozen) == identities["binary"] and
                digest(cache) == digest(output / "CMakeCache.txt") == identities["cache"], "source/build changed during collection")
        load_inputs(inputs)
        result.update(build=identities, settings=settings, source_sha256_at_collection=sources,
                      protocol_sha256=digest(output / "protocol.md"), repeat_verified=True)
        write_json(output / "results.json", result)
        compress(output / "results.json", output / "results.json.gz")
        write_json(output / "manifest.json", {"rule": RULE, "status": "complete", "repeat_verified": True,
            "artifacts": {str(p.relative_to(output)): digest(p) for p in sorted(output.rglob("*")) if p.is_file()}})
    except BaseException as error:
        (output / "FAILED.txt").write_text(str(error) + "\n")
        raise


def verify(path):
    if path.is_dir():
        require(not (path / "FAILED.txt").exists(), "incomplete collection")
        manifest = json.loads((path / "manifest.json").read_text())
        require(manifest["rule"] == RULE and manifest["status"] == "complete" and manifest["repeat_verified"] is True,
                "invalid bundle")
        for name in manifest["artifacts"]:
            artifact(path, manifest, name)
        path = path / "results.json.gz"
    value = json.loads(gzip.decompress(path.read_bytes()))
    _, old, archive, diagnosis = load_inputs(ROOT / "benchmarks/garden-seasons")
    require(value["rule"] == RULE and value["inputs"] == INPUTS and value["arms"] == ARMS and
            value["objective"] == training.individual.RULE and value["training_runs"] == 0 and
            value["models"] == archive["models"] and value["plan"] == archive["plan"] and
            value["repeat_verified"] is True and value["protocol_sha256"] == digest(ROOT / PROTOCOL), "wrong screen identity")
    for w, saved in zip(value["worlds"], archive["worlds"], strict=True):
        require({k: w[k] for k in ("id", "model", "case")} == {k: saved[k] for k in ("id", "model", "case")}, "wrong panel case")
        for arm, a in w["arms"].items():
            normalized = common_view(a["result"], arm)
            history = training.score_world(normalized, w["case"], value["models"][w["model"]]["metadata"])
            require(a["history"] == history and a["metrics"] == scoring.metrics(a["result"], a["audit"], history), "score/metrics differ")
            children = {p["id"]: p for p in a["result"]["lineages"] if p["parent"]}
            require(len(a["audit"]["plants"]) == len(children) and
                    {p["id"] for p in a["audit"]["plants"]} == set(children), "missing/duplicate child budgets")
            for p in a["audit"]["plants"]:
                require({k: p[k] for k in children[p["id"]]} == children[p["id"]], "child ledger differs")
                checked = dict(p)
                recruitment.analyze_child(checked, STOP)
                require(checked == p, "first-day budget differs")
                if arm == "32":
                    require(all(s is None or s[4] <= 32 for row in p["rows"] for s in row["stages"]),
                            "cap exceeded in first-day trace")
            require(common_view(w["initial"][arm], arm) == arbitration.common_view(saved["initial"]["eligible"], "eligible"), "initial differs")
            if arm == "off":
                require(normalized == arbitration.common_view(saved["arms"]["eligible"]["result"], "eligible") and
                        all(a[k] == saved["arms"]["eligible"][k] for k in ("audit", "history", "metrics", "trace_sha256")) and
                        a["frame"]["raw_sha256"] == saved["arms"]["eligible"]["frame"]["raw_sha256"], "historical control differs")
            require(("focus" in a) == (w["id"] == adults.CASE), "wrong focus")
            if "focus" in a:
                f = a["focus"]
                require(f["audit"] == adults.analyze(f["trace"], a["result"]) and
                        f["gaps"] == turnover.gaps(a["result"], turnover.segments(a["result"], adults.START, adults.END)) and
                        [image["tick"] for image in f["frames"]] == list(adults.FRAMES), "focus budgets/timeline differ")
                if arm == "off":
                    require(f["trace"] == diagnosis["arms"]["eligible"]["trace"], "historical adult trace differs")
                else:
                    require(all(s is None or s[4] <= 32 for r in f["trace"][1:-1] for p in r["plants"]
                                for s in p["stages"]), "cap exceeded in adult trace")
                for image in f["frames"]:
                    require(common_view(image["result"], arm)["tick"] == image["tick"] and
                            image["result"]["model"] == value["models"][w["model"]]["metadata"], "wrong frame identity")
    for climate in ("steady", "seasonal"):
        require(value["sheets"][climate]["rows"] == [[w["arms"][a]["frame"]["id"] for a in ARMS]
                for w in value["worlds"] if w["case"]["climate"] == climate], "wrong panel gallery order")
    focus = next(w for w in value["worlds"] if w["id"] == adults.CASE)
    require(value["sheets"]["focus"]["rows"] == [[f["id"] for f in focus["arms"][a]["focus"]["frames"]] for a in ARMS],
            "wrong focus gallery order")
    require(value["comparison"] == compare(value["worlds"], old, archive), "gates differ")
    print("Verified frozen controls, cap identities, unchanged scores/gates, and focused adult/seed budgets (offline).")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path, default=ROOT / "build-host")
    parser.add_argument("--inputs", type=Path, default=ROOT / "benchmarks/garden-seasons")
    parser.add_argument("--jobs", type=int, default=2)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--out", type=Path)
    group.add_argument("--verify", type=Path)
    args = parser.parse_args()
    try:
        if args.verify:
            verify(args.verify.resolve())
        else:
            collect(args.build.resolve(), args.inputs.resolve(), args.out.resolve(), args.jobs)
        return 0
    except (OSError, ValueError, RuntimeError, StopIteration, KeyError, TypeError) as error:
        print("growth screen failed: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
