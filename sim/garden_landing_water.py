#!/usr/bin/env python3
"""One frozen-model first-day water-reserve screen, not a training mode."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import gzip
import json
from pathlib import Path
import shutil
import sys
import tempfile

import garden_landing_establishment as establishment
import garden_landing_range as previous
from garden_experiments import compress, digest, source_files, snapshot_sources, write_json
from garden_gallery import artifact, contact_sheet, rgb565be_to_rgb888, write_png
from garden_resources import require

ROOT, DAY, STEP, STOP = previous.ROOT, previous.DAY, previous.STEP, previous.STOP
prior, training = previous.prior, previous.training
RULE = "garden-landing-water-v1"
PROTOCOL = "benchmarks/garden-seasons/landing-water-protocol.md"
INPUTS = {**previous.INPUTS, "landing-establishment-results.json.gz":
          "0c3d3fc87c0cefd3d4d756485cd3b863af50b583d7ddd1d2ddaedeaf43cd720d"}
ARMS = {"control": False, "water": True}


def load_inputs(root):
    for name, sha in INPUTS.items():
        require(digest(root / name) == sha, "wrong frozen input: " + name)
    return previous.reach.load_inputs(root)


def check_build(cache):
    training.check_flags(cache)
    values = previous.cache_values(cache)
    require(values.get("TOY_FACTORY_SIMULATOR_SANITIZERS") == "ON", "UBSan build required")
    return {k: v for k, v in values.items() if k.startswith(("TOY_FACTORY_", "CMAKE_C_FLAGS")) or
            k in ("CMAKE_C_COMPILER", "CMAKE_BUILD_TYPE", "CMAKE_HOME_DIRECTORY")}


def water_hash(base, enabled):
    require(type(base) is str and len(base) == 8 and all(c in "0123456789abcdef" for c in base) and
            type(enabled) is bool, "invalid probe identity")
    value = 2166136261
    for byte in b"GWP1" + int(base, 16).to_bytes(4, "little") + bytes((1, enabled)):
        value = ((value ^ byte) * 16777619) & 0xffffffff
    return f"{value:08x}"


def common_view(result, enabled):
    """Validate the tag before checking shared fields; never rewrite saved identity."""
    config = result["water_probe"]
    require(result["kind"] == "landing-water-replay" and result["rules"] == 0 and
            config == {"version": 1, "enabled": enabled} and type(config["version"]) is int and
            type(config["enabled"]) is bool and
            result["run_hash"] == water_hash(result["base_run_hash"], enabled), "wrong water probe identity")
    return {k: v for k, v in result.items() if k not in ("water_probe", "base_run_hash")} | {
        "kind": "landing-replay", "run_hash": result["base_run_hash"]}


def check_winner(w, enabled):
    fields = {"id", "age", "water", "nodes", "roots", "species", "tissue", "action", "priority",
              "tip_moisture", "destination", "cost", "upkeep", "reserve", "wet_root", "allowed", "applied",
              "result_action", "bids", "denied_bids", "funded_wet_root_bids"}
    require(set(w) == fields and type(enabled) is bool, "wrong winner fields")
    boolean = {"wet_root", "allowed", "applied"}
    require(all(type(w[k]) is bool for k in boolean) and
            all(type(w[k]) is int for k in fields - boolean - {"destination"}), "wrong winner types")
    require(w["id"] > 0 and 1 <= w["age"] <= 256 and 0 <= w["water"] <= 65535 and
            0 <= w["roots"] <= w["nodes"] <= 256 and w["species"] in (0, 1, 2) and
            w["tissue"] in (0, 1) and w["action"] in (0, 1, 2) and -32768 <= w["priority"] <= 32767 and
            0 <= w["tip_moisture"] <= 255 and 1 <= w["bids"] <= w["nodes"] and
            0 <= w["denied_bids"] <= w["bids"] and 0 <= w["funded_wet_root_bids"] <= w["bids"] and
            w["denied_bids"] + w["funded_wet_root_bids"] <= w["bids"], "invalid winner range")
    dest = w["destination"]
    require(dest is None or (type(dest) is list and len(dest) == 2 and
            all(type(v) is int for v in dest) and 0 <= dest[0] < 240 and 0 <= dest[1] <= 255 and
            w["action"] == 1), "invalid ranked destination")
    cost, upkeep, reserve, wet, allowed = 0, 0, 0, False, True
    if w["action"] != 0:
        cost = (5, 5, 4)[w["species"]]
        shoots = w["nodes"] - w["roots"] + int(w["action"] == 1 and dest is not None and w["tissue"] == 0)
        upkeep = (shoots + 7) // 8
        wet = bool(w["tissue"] == 1 and dest is not None and dest[0] >= 144 and
                   dest[1] >= cost and dest[1] > w["tip_moisture"])
        reserve = upkeep * (1 if wet else 4)
        allowed = w["water"] >= cost + reserve
    applied = enabled and not allowed
    require((w["cost"], w["upkeep"], w["reserve"], w["wet_root"], w["allowed"], w["applied"], w["result_action"]) ==
            (cost, upkeep, reserve, wet, allowed, applied, 0 if applied else w["action"]), "water forecast differs")
    require((allowed or w["denied_bids"] > 0) and
            (not (wet and allowed) or w["funded_wet_root_bids"] > 0), "winner absent from bid counts")


def winner_summary(rows):
    return {"winners": len(rows), "children": len({r["id"] for r in rows}),
            "bids": sum(r["bids"] for r in rows), "denied_bids": sum(r["denied_bids"] for r in rows),
            "would_deny_winners": sum(not r["allowed"] for r in rows),
            "applied_waits": sum(r["applied"] for r in rows),
            "children_with_applied_wait": len({r["id"] for r in rows if r["applied"]}),
            "applied_wait_with_funded_wet_root_bid": sum(r["applied"] and r["funded_wet_root_bids"] > 0 for r in rows),
            "children_with_wait_and_funded_wet_root_bid": len({r["id"] for r in rows if
                r["applied"] and r["funded_wet_root_bids"] > 0}),
            "selected_funded_wet_root": sum(r["wet_root"] and r["allowed"] for r in rows)}


def analyze_water_trace(path, result, audit, enabled):
    common_view(result, enabled)
    plants = {p["id"]: p for p in audit["plants"]}
    samples = {}
    for p in plants.values():
        roots = 2
        for row in p["rows"]:
            samples[row["tick"], p["id"]] = row, roots
            roots = row["roots"]
    winners, seen = [], set()
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt") as stream:
        require(json.loads(next(stream)) == {"schema": "landing-water-trace-v1", "enabled": enabled}, "wrong water header")
        for tick in range(STEP, result["tick"] + 1, STEP):
            entry = json.loads(next(stream))
            require(set(entry) == {"tick", "winners"} and entry["tick"] == tick and
                    type(entry["winners"]) is list, "missing/reordered water sample")
            for w in entry["winners"]:
                check_winner(w, enabled)
                key = tick, w["id"]
                require(key in samples and key not in seen, "unknown/duplicate winner")
                seen.add(key)
                p, (row, roots) = plants[w["id"]], samples[key]
                pre, post = row["stages"][2:4]
                require(p["parent"] != 0 and p["generation"] > 0 and
                        (p["death_tick"] is None or p["death_tick"] > tick) and
                        w["age"] == (tick - p["birth_tick"]) // STEP + 1 and w["species"] == p["species"] and
                        (w["water"], w["nodes"], w["roots"]) == (pre[1], pre[4], roots), "winner state differs")
                paid = w["result_action"] != 0
                add = int(w["result_action"] == 1 and w["destination"] is not None)
                require(pre[1] - post[1] == (w["cost"] if paid else 0) and post[4] - pre[4] == add and
                        row["roots"] - roots == (add if w["tissue"] == 1 else 0), "winner/resource debit differs")
                winners.append({"tick": tick, **w})
        require(json.loads(next(stream)) == {"complete": True, "tick": result["tick"]} and
                not stream.read().strip(), "missing water completion/trailing data")
    for (tick, ident), (row, _) in samples.items():
        age = (tick - plants[ident]["birth_tick"]) // STEP + 1
        if age <= 256 and row["stages"][2][1] > row["stages"][3][1]:
            require((tick, ident) in seen, "paid first-day growth lacks winner receipt")
    late = [w for w in winners if 62 * DAY < plants[w["id"]]["birth_tick"] <= 190 * DAY]
    return {"winners": winners, "all": winner_summary(winners), "late": winner_summary(late)}


def gates(groups, worlds):
    checks = {}
    for climate in ("steady", "seasonal"):
        group = groups[climate]
        checks[climate + "_retain_key"] = group["scores"]["candidate"]["key"] >= group["scores"]["control"]["key"]
        checks[climate + "_retain_late_survivors"] = (group["totals"]["water"]["late_child_survivors"] >=
                                                     group["totals"]["control"]["late_child_survivors"])
    checks["improve_key_or_renewal"] = any(groups[c]["scores"]["comparison"] > 0 or
        groups[c]["totals"]["water"]["late_renewal_confirmations"] > groups[c]["totals"]["control"]["late_renewal_confirmations"]
        for c in ("steady", "seasonal"))
    checks["no_earlier_or_new_empty_world"] = all(w["arms"]["water"]["metrics"]["first_empty_tick"] is None or
        (w["arms"]["control"]["metrics"]["first_empty_tick"] is not None and
         w["arms"]["water"]["metrics"]["first_empty_tick"] >= w["arms"]["control"]["metrics"]["first_empty_tick"])
        for w in worlds)
    return checks


def compare(worlds):
    require(len(worlds) == 12 and len({w["id"] for w in worlds}) == 12 and
            all(set(w["arms"]) == set(ARMS) for w in worlds), "unmatched water panel")
    groups = {}
    for name in ("all", "steady", "seasonal", "single", "multi"):
        rows = [w for w in worlds if name == "all" or w["case"]["climate"] == name or w["model"].split("-")[0] == name]
        scores = [{w["id"]: w["arms"][arm]["history"] for w in rows} for arm in ARMS]
        groups[name] = {"scores": training.individual.pair_group(*scores, [w["id"] for w in rows]),
            "totals": {a: previous.totals([w["arms"][a]["metrics"] for w in rows]) for a in ARMS},
            "late_allocation": {a: establishment.aggregate([p for w in rows for p in w["arms"][a]["late_children"]]) for a in ARMS},
            "late_winners": {a: {k: sum(w["arms"][a]["water_audit"]["late"][k] for w in rows)
                for k in winner_summary([])} for a in ARMS}}
    checks = gates(groups, worlds)
    return {"groups": groups, "gates": checks, "passes_screen": all(checks.values())}


def run_panel(binary, inputs, root, jobs, *, controls=True):
    panel, archive, old = load_inputs(inputs)
    require(not root.exists(), "fresh panel required")
    (root / "models").mkdir(parents=True)
    (root / "frames").mkdir()
    models = old["models"]
    for key, model in models.items():
        path = root / "models" / (key + ".tgl")
        with path.open("xb") as stream:
            stream.write(archive[model["model"]])
        require(digest(path) == model["sha256"], "wrong frozen controller")

    def one(saved):
        case, model, name = saved["case"], saved["model"], saved["id"]
        meta = models[model]["metadata"]
        base = ("water-replay", "models/" + model + ".tgl", case["scenario"], "0x" + case["seed"],
                "--climate", case["climate"], "--ledger")
        initials, arms = {}, {}
        for arm, enabled in ARMS.items():
            stem = arm + "--" + name
            args = (*base, "--water-reserve", "on" if enabled else "off")
            initial = training.native(binary, root, *args, "--ticks", 0)
            view = common_view(initial, enabled)
            require(view["model"] == meta and view["tick"] == 0 and view["seeds"] == [] and
                    all(p["parent"] == 0 for p in view["lineages"]), "wrong initial biology")
            initials[arm] = initial
            args = (*args, "--ticks", STOP)
            trace, water = (root / (stem + suffix + ".jsonl") for suffix in ("", "-water"))
            result = training.native(binary, root, *args, "--recruitment-trace", trace, "--water-trace", water)
            raw_name, png_name = "frames/" + stem + ".rgb565be", "frames/" + stem + ".png"
            framed = training.native(binary, root, *args, "--framebuffer", raw_name)
            raw = (root / raw_name).read_bytes()
            require({**framed, "framebuffer_crc32": None} == result, "untraced capture changes trajectory")
            score = previous.history(common_view(framed, enabled), case, meta, "narrow", raw)
            if controls:
                repeated, repeat_water = (root / (stem + suffix + "-repeat.jsonl") for suffix in ("", "-water"))
                repeat_raw = root / "frames" / (stem + "-repeat.rgb565be")
                repeat = training.native(binary, root, *args, "--recruitment-trace", repeated,
                    "--water-trace", repeat_water, "--framebuffer", repeat_raw)
                require(repeat == framed and repeat_raw.read_bytes() == raw and digest(trace) == digest(repeated) and
                        digest(water) == digest(repeat_water), "repeat trace/state/pixels differ")
                for p in (repeated, repeat_water):
                    compress(p, Path(str(p) + ".gz"))
                    p.unlink()
            audit = prior.analyze_trace(trace, result)
            water_audit = analyze_water_trace(water, result, audit, enabled)
            for p in (trace, water):
                compress(p, Path(str(p) + ".gz"))
                p.unlink()
            trace_sha, water_sha = (digest(Path(str(p) + ".gz")) for p in (trace, water))
            if not enabled:
                ordinary = common_view(result, False)
                require(ordinary == saved["result"] and audit == saved["audit"] and trace_sha == saved["trace_sha256"],
                        "off mode differs from historical ordinary result/trace/accounting")
                prior.check_history(ordinary, panel["evaluations"][model]["worlds"][case["id"]], case, meta)
                require(score == training.score_world(ordinary, case, meta), "ordinary objective changed")
            children = [establishment.summarize_child(p, STOP) for p in audit["plants"]
                        if 62 * DAY < p["birth_tick"] <= 190 * DAY]
            write_png(root / png_name, 240, 240, rgb565be_to_rgb888(raw))
            write_json(root / (stem + ".json"), result)
            arms[arm] = {"result": result, "history": score, "audit": audit, "water_audit": water_audit,
                         "late_children": children, "metrics": previous.metrics(result, audit, score),
                         "trace_sha256": trace_sha, "water_trace_sha256": water_sha,
                         "frame": {"id": stem, "framebuffer": raw_name, "png": png_name,
                         "framebuffer_crc32": framed["framebuffer_crc32"], "raw_sha256": digest(root / raw_name),
                         "png_sha256": digest(root / png_name)}}
        require(common_view(initials["control"], False) == common_view(initials["water"], True) and
                initials["control"]["run_hash"] != initials["water"]["run_hash"], "initial biology/identity mismatch")
        require(digest(root / "models" / (model + ".tgl")) == models[model]["sha256"], "model modified")
        print(name + ": paired water worlds, exact controls and reconciled receipts", flush=True)
        return {k: saved[k] for k in ("id", "model", "case")} | {"initial": initials, "arms": arms}

    with ThreadPoolExecutor(max_workers=jobs) as pool:
        worlds = list(pool.map(one, old["worlds"]))
    sheets = {}
    for climate in ("steady", "seasonal"):
        directory = root / "frames" / climate
        directory.mkdir()
        groups = [[{**w["arms"][a]["frame"], "framebuffer": str(root / w["arms"][a]["frame"]["framebuffer"])}
                   for a in ARMS] for w in worlds if w["case"]["climate"] == climate]
        sheets[climate] = {**contact_sheet(directory, groups), "png": "frames/" + climate + "/contact-sheet.png",
                           "sha256": digest(directory / "contact-sheet.png")}
    return {"schema_version": 1, "rule": RULE, "objective": training.individual.RULE, "inputs": INPUTS,
            "plan": old["plan"], "models": models, "arms": ARMS, "worlds": worlds,
            "comparison": compare(worlds), "sheets": sheets}


def collect(build, inputs, output, jobs):
    require(1 <= jobs <= 4 and not output.exists() and
            (output.is_relative_to(ROOT / "artifacts") or not output.is_relative_to(ROOT)), "fresh output/jobs 1..4 required")
    load_inputs(inputs)
    cache, binary = build / "CMakeCache.txt", build / "toy-factory-garden-landing"
    settings = check_build(cache)
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
    require(not (output / "FAILED.txt").exists(), "incomplete water collection")
    manifest = json.loads((output / "manifest.json").read_text())
    require(manifest["rule"] == RULE and manifest["status"] == "complete" and manifest["repeat_verified"], "wrong bundle")
    for name in manifest["artifacts"]:
        artifact(output, manifest, name)
    require(check_build(output / "CMakeCache.txt") == manifest["settings"], "build mismatch")
    require(digest(output / "protocol.md") == manifest["source_sha256_at_collection"][PROTOCOL], "protocol mismatch")
    expected = json.loads((output / "results.json").read_text())
    with tempfile.TemporaryDirectory(prefix="landing-water-verify-") as temporary:
        result = run_panel(output / "bin/garden-landing", output / "inputs", Path(temporary) / "panel", 1, controls=False)
        require(result == expected, "independent frozen water replay differs")
    for name in manifest["artifacts"]:
        artifact(output, manifest, name)
    print("Verified all twelve pairs, exact traces, pixels, water receipts, budgets and unchanged renewal scoring.")


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
        print("water screen failed: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
