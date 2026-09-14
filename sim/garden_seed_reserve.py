#!/usr/bin/env python3
"""Frozen single-rule seed affordability A/B; no training or firmware promotion."""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import gzip
import json
from pathlib import Path
import shutil
import zlib

import garden_turnover as turnover
from garden_gallery import contact_sheet, rgb565be_to_rgb888, write_png

bank = turnover.bank
experiment = bank.experiment
require = bank.require
RULE = "sunset-seed-reserve-v1"
BASELINE_SHA = "0feca7b8584012cfa384e9a5fde197bc8ed8ddec3c1f10a1a254b4828815e7ff"
KEYS = tuple(f"{seed}.{side}.{capacity}" for seed in ("b61837dc", "c7f54e18")
             for side in ("neural", "reserve") for capacity in (8, 16))


def forecast(energy, income, nodes, phase):
    """Independent accounting reference, never used to drive native worlds."""
    require(0 <= energy <= 256 and 0 <= income <= 255 and 1 <= nodes <= 512 and
            0 <= phase <= 255, "invalid forecast input")
    upkeep = (nodes + 7) // 8
    after = energy - 48
    projected, funded = after, after >= upkeep
    for p in range(phase + 1, 129):
        if p < 128:
            projected = min(256, projected + income // 2)
        if p % 4 == 0:
            projected -= upkeep
            funded &= projected >= 0
    return {"after_seed": after, "projected_sunset": projected, "maintenance_cost": upkeep,
            "night_upkeep": 31 * upkeep,
            "allowed": 0 < phase < 128 and funded and projected >= 31 * upkeep}


def compare_prefix(old_path, new_path):
    matched, first, purchases, last_created = 0, None, 0, 0
    with gzip.open(old_path, "rt") as old, gzip.open(new_path, "rt") as new:
        for a, b in zip(old, new, strict=True):
            x, y = json.loads(a), json.loads(b)
            require(x["tick"] == y["tick"] and y.get("seed_reserve_rule") == RULE and
                    x.get("seed_reserve_rule") is None, "wrong prefix identity")
            buyers = [p for p in y["plants"] if not p["dead"] and p["reproduction_cooldown"] == 16]
            require(y["seeds_created"] - last_created == len(buyers), "unreconciled seed purchase")
            for p in buyers:
                require(y["tick"] % 60 == 0 and forecast(p["energy"] + 48, p["energy_income"],
                        p["nodes"], y["sun_phase"])["allowed"], "unaffordable native purchase")
                purchases += 1
            last_created = y["seeds_created"]
            if first is not None:
                continue
            comparable = {k: v for k, v in y.items() if k != "seed_reserve_rule"}
            if x == comparable:
                matched += 1
                continue
            stable = x.keys() - {"hash", "plants", "seeds", "seeds_created"}
            require(all(x[k] == y[k] for k in stable) and x["hash"] != y["hash"],
                    "first difference changed non-reproduction state")
            old_buyers = [p for p in x["plants"] if not p["dead"] and p["reproduction_cooldown"] == 16]
            initial = len(x["seeds"]) - len(old_buyers)
            require(initial == len(y["seeds"]) - len(buyers) and initial >= 0 and
                    x["seeds"][:initial] == y["seeds"][:initial], "existing bank changed")
            for row, produced in ((x, old_buyers), (y, buyers)):
                require([s["parent"] for s in row["seeds"][initial:]] == [p["id"] for p in produced],
                        "seed append order mismatch")
            old_seeds = {s["parent"]: s for s in x["seeds"][initial:]}
            new_seeds = {s["parent"]: s for s in y["seeds"][initial:]}
            require(all(old_seeds[i] == new_seeds[i] for i in old_seeds.keys() & new_seeds.keys()),
                    "unaffected purchase changed")
            refused, reassigned = [], []
            old_count = new_count = initial
            capacity = x.get("seed_capacity", 8)
            for p, q in zip(x["plants"], y["plants"], strict=True):
                old_bought = p in old_buyers
                new_bought = q in buyers
                if p != q:
                    require(old_bought != new_bought, "unexplained plant change")
                    before, after = (q, p) if old_bought else (p, q)
                    expected = {**before, "energy": before["energy"]-48, "water": before["water"]-24,
                                "reproduction_cooldown": 16,
                                "spent_flowers": before["spent_flowers"]+1}
                    require(before["reproduction_cooldown"] == 0 and after == expected,
                            "purchase/refusal changed more than debit, flower and cooldown")
                    f = forecast(before["energy"], before["energy_income"], before["nodes"], y["sun_phase"])
                    record = {"id": before["id"], "forecast": f, "before_gate": before}
                    if old_bought:
                        require(not f["allowed"] and old_count < capacity, "unexplained refusal")
                        refused.append(record)
                    else:
                        require(f["allowed"] and refused and old_count == capacity and new_count < capacity,
                                "new purchase is not a later freed-slot use")
                        reassigned.append(record)
                old_count += old_bought
                new_count += new_bought
            require(refused and x["seeds_created"]-y["seeds_created"] == len(refused)-len(reassigned),
                    "unreconciled first-step purchases")
            first = {"tick": y["tick"], "matched_rows": matched, "refused": refused,
                     "reassigned": reassigned, "hashes": [x["hash"], y["hash"]]}
    return {"first": first, "matched_rows": matched, "checked_purchases": purchases}


def analyze(path, bounds, key, gate):
    seed, side, capacity = key.split(".")
    require(key in KEYS and gate in ("off", "on"), "unknown case")
    rule = RULE if gate == "on" else None
    growth = bank.recruitment.policy.RESERVE if side == "reserve" else None
    for boundary in bounds:
        bank.recruitment.diversity.disturbance.validate_boundary(
            boundary["before"], boundary["after"], boundary["event"])
        for when in ("before", "after"):
            bank.competition.maintenance.check_identity(boundary[when], "selective", 512,
                growth_policy=growth, seed_capacity=int(capacity), seed_reserve=rule)
    world, refs = bank.competition.world_analysis(path, "selective", 512, bank.END, bank.START,
        disturbances={b["event"]["tick"]: b for b in bounds}, growth_policy=growth,
        seed_capacity=int(capacity), seed_reserve=rule)
    result = {"key": key, "gate": gate, "world": world,
              "lifetimes": turnover.summary_lifetimes(world["lineages"]),
              "milestones": {str(r["tick"]): r["hash"] for r in refs if r["tick"] % (64*bank.DAY) == 0}}
    if key in turnover.FOCUS:
        result["resource_trace"] = turnover.resource_trace(path, {"world": bounds}, world,
            int(capacity), seed_reserve=rule)
    return result


def compact(result):
    world = result["world"]
    mortality = {}
    for label, start in (("whole", 0), ("late", bank.START)):
        dead = [p for p in world["lineages"] if p["death_tick"] is not None and
                p["death_tick"] > start and not p.get("environmental_death")]
        mortality[label] = {"flags": dict(Counter(str(p["death_flags"]) for p in dead)),
            "under_one_day": sum(p["death_tick"]-p["birth_tick"] < bank.DAY for p in dead)}
    return {"key": result["key"], "gate": result["gate"], "lifetimes": result["lifetimes"],
            "windows": world["windows"], "mortality": mortality,
            "final": {k: world["final"][k] for k in ("hash", "living", "nodes", "births", "deaths",
                                                       "seeds_created", "seeds_expired")}}


def collect(baseline, build_root, output, reuse=None):
    baseline, build_root, output = baseline.resolve(), build_root.resolve(), output.resolve()
    require(not output.exists() and (not output.is_relative_to(experiment.ROOT) or
            output.is_relative_to(experiment.ROOT/"artifacts")), "unsafe/existing output")
    manifest_path = baseline/"manifest.json"
    require(experiment.digest(manifest_path) == BASELINE_SHA, "wrong frozen baseline")
    old_manifest = experiment.read_json(manifest_path)
    for name in old_manifest["artifacts"]:
        bank.establishment.verified(baseline, old_manifest, name)
    output.mkdir(parents=True)
    for name in ("bin", "input", "analyses", "traces", "frames"):
        (output/name).mkdir()
    sources = experiment.source_files()
    experiment.snapshot_sources(output, sources)
    shutil.copy2(manifest_path, output/"input/manifest.json")
    shutil.copy2(experiment.ROOT/"benchmarks/garden-longevity/seed-reserve-protocol.md", output/"protocol.md")
    shutil.copy2(baseline/"model.tgm", output/"model.tgm")
    require(experiment.digest(output/"model.tgm") == bank.competition.maintenance.MODEL_SHA, "wrong model")
    if reuse is not None:
        reuse = reuse.resolve()
        prior = experiment.read_json(reuse/"started.json")
        require(prior["kind"] == "garden-seed-reserve" and prior["expected_runs"] == 16 and
                prior["baseline_manifest_sha256"] == BASELINE_SHA and
                experiment.read_json(reuse/"failure.json")["error"] == "gate never exercised",
                "reuse is restricted to the completed captures with the no-effect audit failure")
        require(all(sources.get(name) == sha for name, sha in prior["source_sha256"].items()
                    if Path(name).suffix in (".c", ".h")), "native source changed since capture")
        require(experiment.digest(reuse/"model.tgm") == experiment.digest(output/"model.tgm"), "reuse model changed")
        names = ["started.json", "failure.json", "source.tar.gz", "protocol.md"]
        names += [f"traces/{key}.{gate}.world.gz" for key in KEYS for gate in ("off", "on")]
        names += [f"analyses/{key}.{gate}.boundaries.json" for key in KEYS for gate in ("off", "on")]
        names += [str(p.relative_to(reuse)) for p in (reuse/"frames").glob("*")
                  if p.suffix in (".json", ".rgb565")]
        for name in names:
            target = output/"input/reused"/name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(reuse/name, target)
    for key in KEYS:
        for name in (f"traces/{key}.world.gz", f"analyses/{key}.json", f"analyses/{key}.boundaries.json"):
            shutil.copy2(baseline/name, output/"input"/Path(name).name)
        for day in (64, 128, 192):
            shutil.copy2(baseline/f"frames/{key}.{day}.rgb565", output/f"input/{key}.{day}.rgb565")
    for gate in ("off", "on"):
        for capacity in (8, 16):
            build = build_root/f"seed-reserve-build-{gate}-{capacity}"
            cache = (build/"CMakeCache.txt").read_text()
            for name, on in (("WIDE_DISPERSAL", True), ("WATER_HEADROOM", True),
                ("COMBINED_EXPERIMENT", True), ("LARGE_POOL", True), ("LEAF_MAINTENANCE", True),
                ("BOTTOM_DRAINAGE", False), ("LARGE_SEED_BANK", capacity == 16), ("SEED_RESERVE", gate == "on")):
                require(f"TOY_FACTORY_GARDEN_{name}:BOOL={'ON' if on else 'OFF'}" in cache, "wrong build: "+name)
            require("TOY_FACTORY_SIMULATOR_SANITIZERS:BOOL=ON" in cache, "sanitizers required")
            for tool in ("inspect", "replay", "capacity-test", "seed-reserve-test"):
                shutil.copy2(build/f"toy-factory-garden-{tool}", output/f"bin/{gate}-{capacity}-{tool}")
                if reuse is not None:
                    require(experiment.digest(reuse/f"bin/{gate}-{capacity}-{tool}") ==
                            experiment.digest(output/f"bin/{gate}-{capacity}-{tool}"), "reuse binary changed")
            shutil.copy2(build/"CMakeCache.txt", output/f"input/{gate}-{capacity}.cache.txt")
            for tool in ("capacity-test", "seed-reserve-test"):
                experiment.command_run([f"bin/{gate}-{capacity}-{tool}"],
                    output/f"input/{gate}-{capacity}.{tool}.txt", output, 60)
    frozen = {str(p.relative_to(output)): experiment.digest(p) for p in output.rglob("*") if p.is_file()}
    manifest = {"kind": "garden-seed-reserve", "status": "started", "expected_runs": 16,
                "source_sha256": sources, "baseline_manifest_sha256": BASELINE_SHA,
                "reused_capture_bundle": str(reuse) if reuse else None}
    experiment.write_json(output/"started.json", manifest)

    def run(job):
        key, gate = job
        seed, side, capacity = key.split(".")
        name = f"{key}.{gate}"
        args = ["model.tgm", "rainfed-crowded", bank.POLICIES[side], "0x"+seed,
                "--leaf-policy", "selective", "--disturbance-seed", str(bank.SCHEDULE)]
        cmd = [f"bin/{gate}-{capacity}-inspect", *args, "--ecology", "--ticks", str(bank.END)]
        path = output/f"traces/{name}.world.gz"
        if reuse is None:
            bounds = bank.recruitment.diversity.disturbance.capture(cmd, path, output,
                "world", bank.SCHEDULE, bank.END)
        else:
            shutil.copy2(output/f"input/reused/traces/{name}.world.gz", path)
            bounds = experiment.read_json(output/f"input/reused/analyses/{name}.boundaries.json")
        print(f"Captured {name}", flush=True)
        experiment.write_json(output/f"analyses/{name}.boundaries.json", bounds)
        if gate == "off":
            with gzip.open(path, "rb") as x, gzip.open(output/f"input/{key}.world.gz", "rb") as y:
                require(all(a == b for a, b in zip(x, y, strict=True)), "off baseline changed")
            require(bounds == experiment.read_json(output/f"input/{key}.boundaries.json")["world"],
                    "off boundaries changed")
        result = analyze(path, bounds, key, gate)
        if gate == "off":
            require(result["world"] == experiment.read_json(output/f"input/{key}.json")["analysis"]["world"],
                    "off analysis changed")
        else:
            result["prefix"] = compare_prefix(output/f"input/{key}.world.gz", path)
        result["commands"], result["frames"] = [cmd], []
        result["native_reuse"] = {"capture": reuse is not None, "frame_days": []}
        for day in (64, 128, 192):
            frame = f"frames/{name}.{day}.rgb565"
            command = [f"bin/{gate}-{capacity}-replay", *args, "--ticks", str(day*bank.DAY), "--framebuffer", frame]
            result["commands"].append(command)
            if reuse is not None and (output/"input/reused"/frame).exists():
                shutil.copy2(output/"input/reused"/frame, output/frame)
                shutil.copy2(output/f"input/reused/frames/{name}.{day}.json", output/f"frames/{name}.{day}.json")
                result["native_reuse"]["frame_days"].append(day)
            else:
                experiment.command_run(command, output/f"frames/{name}.{day}.json", output, 300)
            replay = experiment.read_json(output/f"frames/{name}.{day}.json")
            raw = (output/frame).read_bytes()
            require(replay["hash"] == result["milestones"][str(day*bank.DAY)] and
                replay["model_crc32"] == "dc5e849d" and replay["policy"] == bank.POLICIES[side] and
                replay.get("seed_capacity", 8) == int(capacity) and
                replay.get("seed_reserve_rule") == (RULE if gate == "on" else None) and
                len(raw) == 115200 and replay["framebuffer_crc32"] == f"{zlib.crc32(raw):08x}",
                "replay/frame mismatch")
            if gate == "off":
                require(raw == (output/f"input/{key}.{day}.rgb565").read_bytes(), "off frame changed")
            write_png(output/f"frames/{name}.{day}.png", 240, 240, rgb565be_to_rgb888(raw))
            result["frames"].append({"id": f"{name}.day{day}", "framebuffer": frame})
        experiment.write_json(output/f"analyses/{name}.json", result)
        print(f"Verified {name}: {result['lifetimes']['closing']['ages']}", flush=True)
        return result

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(run, [(key, gate) for key in KEYS for gate in ("off", "on")]))
        experiment.write_json(output/"summary.json", {"runs": [compact(r) for r in results]})
        for index, day in enumerate((64, 128, 192)):
            experiment.write_json(output/f"frames-{day}.json", contact_sheet(output,
                [[a["frames"][index], b["frames"][index]]
                 for a, b in zip(results[::2], results[1::2], strict=True)]))
            (output/"contact-sheet.png").rename(output/f"contact-{day}.png")
        require(experiment.source_files() == sources, "source changed during collection")
        require(all(experiment.digest(output/n) == sha for n, sha in frozen.items()), "frozen input changed")
        for name in old_manifest["artifacts"]:
            bank.establishment.verified(baseline, old_manifest, name)
        manifest.update(status="complete", artifacts={str(p.relative_to(output)): experiment.digest(p)
            for p in output.rglob("*") if p.is_file()})
        experiment.write_json(output/"manifest.json", manifest)
        print(f"Complete {output}; {experiment.digest(output/'manifest.json')}", flush=True)
    except BaseException as error:
        experiment.write_json(output/"failure.json", {"error": str(error)})
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, default=experiment.ROOT/"artifacts/garden-seed-bank")
    parser.add_argument("--build-root", type=Path, default=experiment.ROOT/"artifacts")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--reuse", type=Path, help="Reaudit frozen v2 captures after the no-effect audit correction")
    args = parser.parse_args()
    collect(args.baseline, args.build_root, args.output, args.reuse)
