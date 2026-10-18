#!/usr/bin/env python3
"""Frozen-model water-eligible arbitration screen; no training or promotion."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import gzip
import json
from pathlib import Path
import shutil
import sys
import tempfile

import garden_landing_water as previous
from garden_experiments import compress, digest, source_files, snapshot_sources, write_json
from garden_gallery import artifact, contact_sheet, rgb565be_to_rgb888, write_png
from garden_resources import require

ROOT, DAY, STEP, STOP = previous.ROOT, previous.DAY, previous.STEP, previous.STOP
training, prior, establishment = previous.training, previous.prior, previous.establishment
RULE = "garden-landing-arbitration-v1"
PROTOCOL = "benchmarks/garden-seasons/landing-arbitration-protocol.md"
INPUTS = {**previous.INPUTS, "landing-water-results.json.gz":
          "9f93b8047cfa6468bb7053d06f11b10dbe459e02fb36d37f1616c1ba56200e9c"}
ARMS = {"veto": False, "eligible": True}


def load_inputs(root):
    for name, sha in INPUTS.items():
        require(digest(root / name) == sha, "wrong frozen input: " + name)
    panel, models, old = previous.load_inputs(root)
    water = json.loads(gzip.decompress((root / "landing-water-results.json.gz").read_bytes()))
    require(water["rule"] == previous.RULE and water["plan"] == old["plan"] and
            water["models"] == old["models"], "wrong historical water panel")
    return models, water


def probe_hash(base, eligible):
    require(type(base) is str and len(base) == 8 and all(c in "0123456789abcdef" for c in base) and
            type(eligible) is bool, "invalid arbitration identity")
    value = 2166136261
    for byte in b"GWA1" + int(base, 16).to_bytes(4, "little") + bytes((2, 1, eligible)):
        value = ((value ^ byte) * 16777619) & 0xffffffff
    return f"{value:08x}"


def common_view(result, mode):
    require(mode in ARMS, "invalid arbitration mode")
    config = result["water_probe"]
    require(result["kind"] == "landing-arbitration-replay" and result["rules"] == 0 and
            config == {"version": 2, "enabled": True, "arbitration": mode} and
            type(config["version"]) is int and type(config["enabled"]) is bool and
            result["run_hash"] == probe_hash(result["base_run_hash"], ARMS[mode]), "wrong arbitration identity")
    return {k: v for k, v in result.items() if k not in ("water_probe", "base_run_hash")} | {
        "kind": "landing-replay", "run_hash": result["base_run_hash"]}


def check_entry(entry, mode):
    require(mode in ARMS and set(entry) == {"id", "original", "selected", "fallback", "result_action", "bids", "committed_memory"},
            "wrong arbitration entry")
    bids = entry["bids"]
    require(type(bids) is list and 1 <= len(bids) <= 256 and type(entry["id"]) is int and entry["id"] > 0 and
            type(entry["original"]) is int and type(entry["selected"]) is int and
            type(entry["fallback"]) is bool and type(entry["result_action"]) is int, "wrong arbitration fields")
    for b in bids:
        require(set(b) == {"tip", "x", "y", "memory", "next_memory", "proposal"} and
                type(b["tip"]) is int and 0 <= b["tip"] < 256 and
                all(type(b[c]) is int and 0 <= b[c] < 240 for c in ("x", "y")), "invalid tip identity")
        for memory in (b["memory"], b["next_memory"], entry["committed_memory"]):
            require(type(memory) is list and len(memory) == 8 and
                    all(type(v) is int and -128 <= v <= 127 for v in memory), "invalid recurrent memory")
        previous.check_winner(b["proposal"], False)
    proposals = [b["proposal"] for b in bids]
    common = ("id", "age", "water", "nodes", "roots", "species", "bids", "denied_bids", "funded_wet_root_bids")
    require(len({b["tip"] for b in bids}) == len(bids) and
            all(b["memory"] == bids[0]["memory"] for b in bids) and
            all({k: p[k] for k in common} == {k: proposals[0][k] for k in common} for p in proposals) and
            proposals[0]["id"] == entry["id"] and proposals[0]["bids"] == len(bids) and
            proposals[0]["denied_bids"] == sum(not p["allowed"] for p in proposals) and
            proposals[0]["funded_wet_root_bids"] == sum(p["allowed"] and p["wet_root"] for p in proposals),
            "bid snapshot/counts differ")
    original = max(range(len(bids)), key=lambda i: proposals[i]["priority"])
    candidates = [i for i, p in enumerate(proposals) if p["allowed"]] if ARMS[mode] else []
    selected = max(candidates, key=lambda i: proposals[i]["priority"]) if candidates else original
    winner = proposals[selected]
    fallback = not winner["allowed"]
    action = 0 if fallback else winner["action"]
    require(entry["original"] == original and entry["selected"] == selected and entry["fallback"] == fallback and
            entry["result_action"] == action and entry["committed_memory"] == bids[selected]["next_memory"],
            "selected proposal/fallback/memory differs")
    return {**winner, "applied": fallback, "result_action": action}


def arbitration_summary(entries):
    changed = [e for e in entries if e["selected"] != e["original"]]
    winners = [e["bids"][e["selected"]]["proposal"] for e in entries]
    return {"decisions": len(entries), "children": len({e["id"] for e in entries}),
        "switches": len(changed), "children_with_switch": len({e["id"] for e in changed}),
        "switch_to_root": sum(e["result_action"] == 1 and e["bids"][e["selected"]]["proposal"]["tissue"] == 1 for e in changed),
        "switch_to_shoot": sum(e["result_action"] == 1 and e["bids"][e["selected"]]["proposal"]["tissue"] == 0 for e in changed),
        "switch_to_finish": sum(e["result_action"] == 2 for e in changed),
        "switch_to_wait": sum(e["result_action"] == 0 for e in changed),
        "fallbacks": sum(e["fallback"] for e in entries),
        "fallback_with_eligible_bid": sum(e["fallback"] and any(b["proposal"]["allowed"] for b in e["bids"]) for e in entries),
        "fallback_with_funded_wet_root": sum(e["fallback"] and p["funded_wet_root_bids"] > 0 for e, p in zip(entries, winners)),
        "genuine_waits": sum(p["action"] == 0 for p in winners)}


def analyze_trace(path, result, audit, mode):
    common_view(result, mode)
    plants = {p["id"]: p for p in audit["plants"]}
    samples = {}
    for p in plants.values():
        roots = 2
        for row in p["rows"]:
            samples[row["tick"], p["id"]] = row, roots
            roots = row["roots"]
    entries, winners, seen, memories = [], [], set(), {}
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt") as stream:
        require(json.loads(next(stream)) == {"schema": "landing-arbitration-trace-v1", "arbitration": mode}, "wrong arbitration header")
        for tick in range(STEP, result["tick"] + 1, STEP):
            sample = json.loads(next(stream))
            require(set(sample) == {"tick", "plants"} and sample["tick"] == tick and
                    type(sample["plants"]) is list and len(sample["plants"]) <= 8 and
                    sum(len(e["bids"]) for e in sample["plants"]) <= 256, "missing/reordered arbitration sample")
            for entry in sample["plants"]:
                w = check_entry(entry, mode)
                key = tick, w["id"]
                require(key in samples and key not in seen, "unknown/duplicate winner")
                seen.add(key)
                p, (row, roots) = plants[w["id"]], samples[key]
                pre, post = row["stages"][2:4]
                require(p["parent"] != 0 and p["generation"] > 0 and
                        (p["death_tick"] is None or p["death_tick"] > tick) and
                        w["age"] == (tick - p["birth_tick"]) // STEP + 1 and w["species"] == p["species"] and
                        (w["water"], w["nodes"], w["roots"]) == (pre[1], pre[4], roots), "winner body differs")
                add = int(w["result_action"] == 1 and w["destination"] is not None)
                require(pre[1] - post[1] == (w["cost"] if w["result_action"] else 0) and post[4] - pre[4] == add and
                        row["roots"] - roots == (add if w["tissue"] == 1 else 0), "winner/resource debit differs")
                require(w["id"] not in memories or entry["bids"][0]["memory"] == memories[w["id"]], "recurrent memory discontinuity")
                memories[w["id"]] = entry["committed_memory"]
                entries.append({"tick": tick, **entry})
                winners.append({"tick": tick, **w})
        require(json.loads(next(stream)) == {"complete": True, "tick": result["tick"]} and
                not stream.read().strip(), "missing completion/trailing data")
    for (tick, ident), (row, _) in samples.items():
        if (tick - plants[ident]["birth_tick"]) // STEP < 256 and row["stages"][2][1] > row["stages"][3][1]:
            require((tick, ident) in seen, "paid first-day growth lacks winner receipt")
    late_ids = {i for i, p in plants.items() if 62 * DAY < p["birth_tick"] <= 190 * DAY}
    return ({"winners": winners, "all": previous.winner_summary(winners),
             "late": previous.winner_summary([w for w in winners if w["id"] in late_ids])},
            {"entries": entries, "all": arbitration_summary(entries),
             "late": arbitration_summary([e for e in entries if e["id"] in late_ids])})


def compare(worlds, archive):
    require([w["id"] for w in worlds] == [w["id"] for w in archive["worlds"]], "unmatched arbitration panel")
    comparisons = {}
    for baseline in ("veto", "ordinary"):
        mapped = [{**w, "arms": {"control": w["arms"]["veto"] if baseline == "veto" else old["arms"]["control"],
                                 "water": w["arms"]["eligible"]}}
                  for w, old in zip(worlds, archive["worlds"], strict=True)]
        comparisons[baseline] = {"control": baseline, "candidate": "eligible", **previous.compare(mapped)}
    return {"comparisons": comparisons, "passes_screen": all(x["passes_screen"] for x in comparisons.values())}


def run_panel(binary, inputs, root, jobs, *, repeats=True):
    model_bytes, archive = load_inputs(inputs)
    require(not root.exists(), "fresh panel required")
    (root / "models").mkdir(parents=True)
    (root / "frames").mkdir()
    models = archive["models"]
    for key, meta in models.items():
        path = root / "models" / (key + ".tgl")
        with path.open("xb") as stream:
            stream.write(model_bytes[meta["model"]])
        require(digest(path) == meta["sha256"], "wrong frozen controller")

    def one(saved):
        case, model, name = saved["case"], saved["model"], saved["id"]
        meta = models[model]["metadata"]
        base = ("arbitration-replay", "models/" + model + ".tgl", case["scenario"], "0x" + case["seed"],
                "--climate", case["climate"], "--ledger")
        initials, arms = {}, {}
        for arm in ARMS:
            stem = arm + "--" + name
            args = (*base, "--water-arbitration", arm)
            initial = training.native(binary, root, *args, "--ticks", 0)
            require(common_view(initial, arm) == previous.common_view(saved["initial"]["water"], True), "initial biology differs")
            initials[arm] = initial
            args = (*args, "--ticks", STOP)
            trace, bids = (root / (stem + suffix + ".jsonl") for suffix in ("", "-bids"))
            result = training.native(binary, root, *args, "--recruitment-trace", trace, "--water-trace", bids)
            raw_name, png_name = "frames/" + stem + ".rgb565be", "frames/" + stem + ".png"
            framed = training.native(binary, root, *args, "--framebuffer", raw_name)
            raw = (root / raw_name).read_bytes()
            require({**framed, "framebuffer_crc32": None} == result, "untraced capture changes trajectory")
            history = previous.previous.history(common_view(framed, arm), case, meta, "narrow", raw)
            if repeats:
                repeat_trace, repeat_bids = (root / (stem + suffix + "-repeat.jsonl") for suffix in ("", "-bids"))
                repeat_raw = root / "frames" / (stem + "-repeat.rgb565be")
                repeat = training.native(binary, root, *args, "--recruitment-trace", repeat_trace,
                    "--water-trace", repeat_bids, "--framebuffer", repeat_raw)
                require(repeat == framed and repeat_raw.read_bytes() == raw and digest(trace) == digest(repeat_trace) and
                        digest(bids) == digest(repeat_bids), "repeat trace/state/pixels differ")
                for p in (repeat_trace, repeat_bids):
                    compress(p, Path(str(p) + ".gz"))
                    p.unlink()
            audit = prior.analyze_trace(trace, result)
            water_audit, arbitration_audit = analyze_trace(bids, result, audit, arm)
            for p in (trace, bids):
                compress(p, Path(str(p) + ".gz"))
                p.unlink()
            trace_sha, bids_sha = (digest(Path(str(p) + ".gz")) for p in (trace, bids))
            if arm == "veto":
                old = saved["arms"]["water"]
                require(common_view(result, arm) == previous.common_view(old["result"], True) and audit == old["audit"] and
                        history == old["history"] and water_audit == old["water_audit"] and trace_sha == old["trace_sha256"] and
                        digest(root / raw_name) == old["frame"]["raw_sha256"], "veto differs from historical water control")
            children = [establishment.summarize_child(p, STOP) for p in audit["plants"]
                        if 62 * DAY < p["birth_tick"] <= 190 * DAY]
            write_png(root / png_name, 240, 240, rgb565be_to_rgb888(raw))
            write_json(root / (stem + ".json"), result)
            arms[arm] = {"result": result, "history": history, "audit": audit, "water_audit": water_audit,
                "arbitration_audit": arbitration_audit, "late_children": children,
                "metrics": previous.previous.metrics(result, audit, history), "trace_sha256": trace_sha,
                "arbitration_trace_sha256": bids_sha,
                "frame": {"id": stem, "framebuffer": raw_name, "png": png_name,
                    "framebuffer_crc32": framed["framebuffer_crc32"], "raw_sha256": digest(root / raw_name),
                    "png_sha256": digest(root / png_name)}}
        require(initials["veto"]["run_hash"] != initials["eligible"]["run_hash"], "mode identity collision")
        require(digest(root / "models" / (model + ".tgl")) == models[model]["sha256"], "model modified")
        print(name + ": exact veto control, verified arbitration and budgets", flush=True)
        return {k: saved[k] for k in ("id", "model", "case")} | {"initial": initials, "arms": arms}

    with ThreadPoolExecutor(max_workers=jobs) as pool:
        worlds = list(pool.map(one, archive["worlds"]))
    sheets = {}
    for climate in ("steady", "seasonal"):
        directory = root / "frames" / climate
        directory.mkdir()
        groups = [[{**w["arms"][a]["frame"], "framebuffer": str(root / w["arms"][a]["frame"]["framebuffer"])}
                   for a in ARMS] for w in worlds if w["case"]["climate"] == climate]
        sheets[climate] = {**contact_sheet(directory, groups), "png": "frames/" + climate + "/contact-sheet.png",
                           "sha256": digest(directory / "contact-sheet.png")}
    return {"schema_version": 1, "rule": RULE, "objective": training.individual.RULE, "inputs": INPUTS,
            "plan": archive["plan"], "models": models, "arms": ARMS, "worlds": worlds,
            "comparison": compare(worlds, archive), "sheets": sheets}


def collect(build, inputs, output, jobs):
    require(1 <= jobs <= 4 and not output.exists() and
            (output.is_relative_to(ROOT / "artifacts") or not output.is_relative_to(ROOT)), "fresh output/jobs 1..4 required")
    load_inputs(inputs)
    cache, binary = build / "CMakeCache.txt", build / "toy-factory-garden-landing"
    settings = previous.check_build(cache)
    require(settings["CMAKE_HOME_DIRECTORY"] == str(ROOT / "sim"), "build from another source tree")
    identities = {"binary": digest(binary), "cache": digest(cache)}
    sources = source_files()
    output.mkdir(parents=True)
    try:
        (output / "bin").mkdir()
        (output / "inputs").mkdir()
        frozen = output / "bin/garden-landing"
        shutil.copy2(binary, frozen)
        shutil.copy2(cache, output / "CMakeCache.txt")
        shutil.copy2(ROOT / PROTOCOL, output / "protocol.md")
        for name in INPUTS:
            shutil.copy2(inputs / name, output / "inputs" / name)
        (output / "sim").mkdir()
        for path in (ROOT / "sim").glob("*.py"):
            shutil.copy2(path, output / "sim" / path.name)
        for name in ("framebuffer_capture.py", "serial_shell.py"):
            target = output / "scripts/container" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / "scripts/container" / name, target)
        snapshot_sources(output, sources)
        result = run_panel(frozen, output / "inputs", output / "panel", jobs)
        require(sources == source_files(), "source changed during collection")
        require(digest(binary) == digest(frozen) == identities["binary"] and
                digest(cache) == digest(output / "CMakeCache.txt") == identities["cache"], "build changed during collection")
        load_inputs(inputs)
        require(digest(output / "protocol.md") == sources[PROTOCOL], "protocol changed")
        write_json(output / "results.json", result)
        write_json(output / "manifest.json", {"rule": RULE, "status": "complete", "repeat_verified": True,
            "build": identities, "settings": settings, "source_sha256_at_collection": sources,
            "artifacts": {str(p.relative_to(output)): digest(p) for p in sorted(output.rglob("*")) if p.is_file()}})
    except BaseException as error:
        (output / "FAILED.txt").write_text(str(error) + "\n")
        raise


def verify(output):
    require(not (output / "FAILED.txt").exists(), "incomplete arbitration collection")
    manifest = json.loads((output / "manifest.json").read_text())
    require(manifest["rule"] == RULE and manifest["status"] == "complete" and manifest["repeat_verified"], "wrong bundle")
    for name in manifest["artifacts"]:
        artifact(output, manifest, name)
    require(previous.check_build(output / "CMakeCache.txt") == manifest["settings"], "build mismatch")
    require(digest(output / "protocol.md") == manifest["source_sha256_at_collection"][PROTOCOL], "protocol mismatch")
    expected = json.loads((output / "results.json").read_text())
    with tempfile.TemporaryDirectory(prefix="landing-arbitration-verify-") as temporary:
        result = run_panel(output / "bin/garden-landing", output / "inputs", Path(temporary) / "panel", 1, repeats=False)
        require(result == expected, "independent frozen arbitration replay differs")
    for name in manifest["artifacts"]:
        artifact(output, manifest, name)
    print("Verified all twelve pairs, exact traces/pixels, arbitration, recurrent memory, budgets and unchanged scoring.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path)
    parser.add_argument("--inputs", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--jobs", type=int)
    parser.add_argument("--verify", type=Path)
    args = parser.parse_args()
    try:
        if args.verify:
            require(all(v is None for v in (args.build, args.inputs, args.out, args.jobs)), "verify takes no overrides")
            verify(args.verify.resolve())
        else:
            require(args.out is not None, "--out required")
            collect((args.build or ROOT / "build-host").resolve(),
                    (args.inputs or ROOT / "benchmarks/garden-seasons").resolve(), args.out.resolve(),
                    2 if args.jobs is None else args.jobs)
        return 0
    except (OSError, ValueError, RuntimeError, StopIteration, KeyError, TypeError) as error:
        print("arbitration screen failed: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
