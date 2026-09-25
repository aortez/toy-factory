#!/usr/bin/env python3
"""Frozen host-only 8/16-seed comparison; no policy or ecology tuning."""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import gzip
import json
from pathlib import Path
import shutil
import tempfile
import zlib

import garden_seed_attempts as attempts
import garden_recruitment as recruitment
import garden_establishment as establishment
import garden_experiments as experiment
import garden_leaf_competition as competition
from garden_gallery import contact_sheet, rgb565be_to_rgb888, write_png
from garden_resources import require

DAY, END, START = attempts.DAY, attempts.END, attempts.START
SCHEDULE = 0xe4d65e6f
POLICIES = recruitment.policy.POLICIES


def identity(row, bank, side, capacity=512):
    competition.maintenance.check_identity(row, "selective", capacity,
        growth_policy=recruitment.policy.RESERVE if side == "reserve" else None,
        seed_capacity=bank)


def analyze(world_path, site_path, bounds, bank, side, end=END, start=START, capacity=512):
    require(bank in (8, 16), "unsupported bank")
    require([b["event"] for b in bounds["world"]] == [b["event"] for b in bounds["sites"]],
            "world/site patch mismatch")
    for kind in ("world", "sites"):
        for b in bounds[kind]:
            recruitment.diversity.disturbance.validate_boundary(b["before"], b["after"], b["event"])
            for when in ("before", "after"):
                r = b[when]
                require(r.get("seed_capacity", 8) == bank, "wrong boundary bank")
                if kind == "world":
                    identity(r, bank, side, capacity)
    world, refs = competition.world_analysis(world_path, "selective", capacity, end, start,
        disturbances={b["event"]["tick"]: b for b in bounds["world"]},
        growth_policy=recruitment.policy.RESERVE if side == "reserve" else None, seed_capacity=bank)
    spatial = {p: Counter() for p in recruitment.PHASES}

    def checked_sites(stream):
        for line in stream:
            r = json.loads(line)
            require(r.get("seed_capacity", 8) == bank and r.get("node_capacity", 256) == capacity
                    and r.get("drainage_rule") is None and r.get("growth_policy") ==
                    (recruitment.policy.RESERVE if side == "reserve" else None), "wrong site identity")
            if r["tick"] > start:
                spatial[recruitment.phase(r)].update(competition.spatial_snapshot(r))
            yield line

    with gzip.open(site_path, "rt") as f:
        seeds = establishment.analyze_stream(checked_sites(f), refs, (end-start)//DAY, capacity,
                                             seed_capacity=bank)
    lineages = {p["id"]: p for p in world["lineages"]}
    for s in seeds["seeds"]:
        if s["outcome"] == "germinated":
            child = lineages[s["child_id"]]
            require(child["parent"] == s["parent"] and child["birth_tick"] == s["end_tick"],
                    "seed/child mismatch")
    patches = {w: [b["event"] for b in bounds["world"] if b["event"]["tick"] > begin]
               for w, begin in (("whole", -1), ("late", start))}
    return {"world": world, "seeds": seeds, "spatial": spatial,
            "patches": {w: {"events": len(es), "occupied": sum(bool(e["killed"]) for e in es),
                             "killed": sum(len(e["killed"]) for e in es)} for w, es in patches.items()},
            "milestone_hashes": {str(r["tick"]): r["hash"] for r in refs if r["tick"] % (64*DAY) == 0}}


def compare_prefix(old_path, new_path):
    """The first different state must be the first bank capacity use, not a new hash tag."""
    matched, divergence = 0, None
    with gzip.open(old_path, "rt") as old, gzip.open(new_path, "rt") as new:
        for a, b in zip(old, new, strict=True):
            x, y = json.loads(a), json.loads(b)
            require(x["tick"] == y["tick"], "pair tick mismatch")
            if divergence is not None:
                continue
            y.pop("seed_capacity", None)
            if x == y:
                matched += 1
                continue
            require(x["hash"] != y["hash"] and len(x["seeds"]) == 8 and len(y["seeds"]) > 8
                    and x["births"] == y["births"] and x["deaths"] == y["deaths"]
                    and x["nodes"] == y["nodes"] and y["seeds_created"] > x["seeds_created"],
                    "pair diverged before using the extra seed capacity")
            divergence = {"tick": x["tick"], "matched_rows": matched,
                "seeds": [len(x["seeds"]), len(y["seeds"])],
                "hashes": [x["hash"], y["hash"]]}
    require(divergence is not None, "comparison never exercised extra capacity")
    return divergence


def compact(result):
    a = result["analysis"]
    return {k: result[k] for k in ("key", "bank", "seed", "side")} | {
        "world_windows": a["world"]["windows"], "lifetimes": a["world"]["lifetimes"],
        "seed_cohorts": a["seeds"]["cohorts"], "patches": a["patches"],
        "final": {k: a["world"]["final"][k] for k in ("hash", "living", "nodes", "births", "deaths")},
        "spatial": a["spatial"], "attempt_windows": result["attempts"]["windows"],
        "checked_worlds": a["seeds"]["checkpoints_verified"], "checked_attempts": result["attempts"]["checked"]}


def collect(baseline, builds, output):
    baseline, output = baseline.resolve(), output.resolve()
    require(not output.exists() and (not output.is_relative_to(experiment.ROOT) or
        output.is_relative_to(experiment.ROOT/"artifacts")), "unsafe/existing output")
    m = experiment.read_json(baseline/"manifest.json")
    require(m["kind"] == "garden-crowded-recruitment" and m["status"] == "complete", "wrong baseline")
    cases = experiment.read_json(establishment.verified(baseline, m, "cases.json"))
    cases = [c for c in cases if c["capacity"] == 512]
    require(len(cases) == 4 and {(c["seed"], c["arm"], c["policy"]) for c in cases} ==
        {(s, "fresh-1", p) for s in ("b61837dc", "c7f54e18") for p in ("neural", "reserve")},
        "wrong fixed panel")
    for bank, build in builds.items():
        cache = (build/"CMakeCache.txt").read_text()
        for name, on in (("WIDE_DISPERSAL", True), ("WATER_HEADROOM", True),
            ("COMBINED_EXPERIMENT", True), ("LEAF_MAINTENANCE", True), ("LARGE_POOL", True),
            ("BOTTOM_DRAINAGE", False), ("LARGE_SEED_BANK", bank == 16)):
            require(f"TOY_FACTORY_GARDEN_{name}:BOOL={'ON' if on else 'OFF'}" in cache, "wrong build: " + name)
        require("TOY_FACTORY_SIMULATOR_SANITIZERS:BOOL=ON" in cache, "sanitizers required")
    output.mkdir(parents=True)
    for folder in ("input", "bin", "traces", "analyses", "frames"):
        (output/folder).mkdir()
    sources = experiment.source_files()
    experiment.snapshot_sources(output, sources)
    shutil.copy2(baseline/"manifest.json", output/"input/manifest.json")
    shutil.copy2(experiment.ROOT/"benchmarks/garden-longevity/seed-bank-protocol.md", output/"protocol.md")
    model = establishment.verified(baseline, m, "input/512.tgm")
    require(experiment.digest(model) == competition.maintenance.MODEL_SHA, "wrong frozen model")
    shutil.copy2(model, output/"model.tgm")
    for bank, build in builds.items():
        for tool in ("inspect", "replay", "seed-attempts", "capacity-test"):
            shutil.copy2(build/f"toy-factory-garden-{tool}", output/f"bin/{bank}-{tool}")
        shutil.copy2(build/"CMakeCache.txt", output/f"input/{bank}.build-cache.txt")
        experiment.command_run([f"bin/{bank}-capacity-test"], output/f"input/{bank}.sizes.txt", output, 60)
    for c in cases:
        for old in (f"traces/{c['key']}.world.gz", f"traces/{c['key']}.sites.gz",
                    f"analyses/{c['key']}.boundaries.json", f"frames/{c['key']}.rgb565"):
            shutil.copy2(establishment.verified(baseline, m, old), output/"input"/Path(old).name)
    frozen = {str(p.relative_to(output)): experiment.digest(p) for p in output.rglob("*") if p.is_file()}
    manifest = {"kind": "garden-seed-bank", "status": "started", "horizon": END, "closing_start": START,
        "expected_runs": 8, "source_sha256": sources, "baseline_manifest_sha256": experiment.digest(baseline/"manifest.json")}
    experiment.write_json(output/"started.json", manifest)

    def run(job):
        c, bank = job
        side, key = c["policy"], f"{c['seed']}.{c['policy']}.{bank}"
        args = ["model.tgm", c["scenario"], POLICIES[side], "0x"+c["seed"], "--leaf-policy", "selective",
                "--disturbance-seed", str(SCHEDULE)]
        bounds, commands = {}, []
        for kind, flag in (("world", "--ecology"), ("sites", "--seed-sites")):
            cmd = [f"bin/{bank}-inspect", *args, flag, "--ticks", str(END)]
            commands.append(cmd)
            path = output/f"traces/{key}.{kind}.gz"
            bounds[kind] = recruitment.diversity.disturbance.capture(cmd, path, output,
                "world" if kind == "world" else "seed-sites", SCHEDULE, END)
            if bank == 8:
                with gzip.open(path, "rb") as a, gzip.open(output/f"input/{c['key']}.{kind}.gz", "rb") as b:
                    require(all(x == y for x,y in zip(a, b, strict=True)), "baseline rows changed")
            print(f"Captured {key} {kind}", flush=True)
        if bank == 8:
            require(bounds == experiment.read_json(output/f"input/{c['key']}.boundaries.json"),
                    "baseline boundaries changed")
        experiment.write_json(output/f"analyses/{key}.boundaries.json", bounds)
        a = analyze(output/f"traces/{key}.world.gz", output/f"traces/{key}.sites.gz", bounds, bank, side)
        header = attempts.expected_header(c, seed_capacity=bank)
        cmd = [f"bin/{bank}-seed-attempts", "model.tgm", c["scenario"], POLICIES[side],
               "0x"+c["seed"], str(SCHEDULE), str(START), str(END)]
        commands.append(cmd)
        with tempfile.TemporaryDirectory(prefix="seed-bank-attempts-") as temp:
            raw = Path(temp)/"attempts.jsonl"
            experiment.command_run(cmd, raw, output, 300)
            experiment.compress(raw, output/f"traces/{key}.attempts.gz")
        audit = attempts.analyze(output/f"traces/{key}.attempts.gz", output/f"traces/{key}.world.gz",
                                 output/f"traces/{key}.sites.gz", bounds, header)
        frames = []
        for day in (64, 128, 192):
            frame = f"frames/{key}.{day}.rgb565"
            cmd = [f"bin/{bank}-replay", *args, "--ticks", str(day*DAY), "--framebuffer", frame]
            commands.append(cmd)
            experiment.command_run(cmd, output/f"frames/{key}.{day}.json", output, 300)
            r = experiment.read_json(output/f"frames/{key}.{day}.json")
            raw = (output/frame).read_bytes()
            require(r["hash"] == a["milestone_hashes"][str(day*DAY)] and r["model_crc32"] == "dc5e849d"
                and r["policy"] == POLICIES[side] and r.get("seed_capacity", 8) == bank
                and len(raw) == 115200 and r["framebuffer_crc32"] == f"{zlib.crc32(raw):08x}",
                "independent replay/frame mismatch")
            if day == 192 and bank == 8:
                require(raw == (output/f"input/{c['key']}.rgb565").read_bytes(), "baseline frame changed")
            write_png(output/f"frames/{key}.{day}.png", 240, 240, rgb565be_to_rgb888(raw))
            frames.append({"id": f"{key}.day{day}", "framebuffer": frame})
        r = {"key": key, "bank": bank, "side": side, "seed": c["seed"], "analysis": a,
             "attempts": audit, "commands": commands, "frames": frames}
        experiment.write_json(output/f"analyses/{key}.json", r)
        print(f"Verified {key}: {a['world']['lifetimes']['late_born']}", flush=True)
        return r

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(run, [(c, bank) for c in cases for bank in (8,16)]))
        prefixes = []
        for a, b in zip(results[::2], results[1::2], strict=True):
            prefixes.append({"seed": a["seed"], "side": a["side"], **compare_prefix(
                output/f"traces/{a['key']}.world.gz", output/f"traces/{b['key']}.world.gz")})
        summary = {"runs": [compact(r) for r in results], "prefixes": prefixes}
        experiment.write_json(output/"summary.json", summary)
        for index, day in enumerate((64, 128, 192)):
            experiment.write_json(output/f"frames-{day}.json", contact_sheet(output,
                [[a["frames"][index], b["frames"][index]] for a,b in zip(results[::2],results[1::2],strict=True)]))
            (output/"contact-sheet.png").rename(output/f"contact-{day}.png")
        require(experiment.source_files() == sources, "source changed during collection")
        require(all(experiment.digest(output/n) == sha for n,sha in frozen.items()), "input changed")
        manifest.update(status="complete", artifacts={str(p.relative_to(output)): experiment.digest(p)
            for p in output.rglob("*") if p.is_file()})
        experiment.write_json(output/"manifest.json", manifest)
        print(f"Complete {output}; SHA256={experiment.digest(output/'manifest.json')}", flush=True)
    except BaseException as error:
        experiment.write_json(output/"failure.json", {"error": str(error)})
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--build-8", type=Path, required=True)
    parser.add_argument("--build-16", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    collect(args.baseline, {8: args.build_8, 16: args.build_16}, args.output)
