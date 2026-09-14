#!/usr/bin/env python3
"""Frozen seven-candidate persistence-v2 pilot; not the general-purpose trainer."""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import time
import zlib

import garden_experiments as experiment
import garden_gallery as gallery
import garden_lineage_persistence as fitness
from garden_resources import require

DAY, START, END, STOP = 3840, 606720, 729600, 737280
PATCH = "e4d65e6f"
DEVELOPMENT = ("13579bdf", "2468ace1")
REVIEW = ("6c696665", "72657632")
TICKS = (480, 2880, STOP)
RULE = "garden-training-pilot-v1"
RECRUITMENT_SHA = "7c3e50235343b2a223e607bbacbfe6d06f55b735c0ea452fc777ed04e1b5ef77"
PROTOCOL = "benchmarks/garden-longevity/training-pilot-protocol.md"
BINARIES = ("garden-model-mutate", "garden-persistence-trial", "garden-replay")
SPECIES = ("flower", "shrub", "ground-cover")


def model_crc(path):
    raw = path.read_bytes()
    require(len(raw) >= 16, "truncated model")
    magic, version, header, size, crc = struct.unpack("<IHHII", raw[:16])
    require(magic == 0x314D4754 and version == 1 and header == 16 and
            len(raw) == header + size and zlib.crc32(raw[header:]) == crc, "invalid model file")
    return f"{crc:08x}"


def run_json(command, output):
    begin = time.monotonic()
    experiment.command_run([str(v) for v in command], output, output.parent, 120)
    return experiment.read_json(output), time.monotonic() - begin


def validate_trial(value, seed, crc, start=START, end=END, policy="neural", *, patch=PATCH):
    expected = {"rule": "garden-persistence-trial-v1", "seed": seed, "patch_seed": patch,
                "model_crc32": crc, "policy": policy, "start": start, "end": end,
                "stop": end + 2 * DAY, "node_capacity": 512, "seed_capacity": 8,
                "scenario": "rainfed-crowded", "gardener": False, "drainage": False,
                "seed_reserve": False, "leaf_policy": "selective"}
    require(all(value.get(k) == v for k, v in expected.items()), "trial identity mismatch")
    plants, seeds = value["lineages"], value["seeds"]
    score = fitness.world(plants, seeds, start, end, expected["stop"])
    require(score["status"] == "complete" and score["key"] == value["key"], "C/Python fitness mismatch")
    checkpoints = value["checkpoints"]
    require([c["tick"] for c in checkpoints] == sorted({0, 480, 2880, start, end, end + 2 * DAY}),
            "missing or duplicate checkpoints")
    require([p["id"] for p in plants] == list(range(1, len(plants) + 1)), "non-dense lineage ledger")
    require(len(plants) <= 4096 and len(seeds) <= 65536, "ledger capacity exceeded")
    for c in checkpoints:
        present = [p for p in plants if p["birth_tick"] <= c["tick"]]
        dead = sum(p["death_tick"] is not None and p["death_tick"] <= c["tick"] for p in present)
        pending = sum(s["birth_tick"] <= c["tick"] and
                      (s["end_tick"] is None or s["end_tick"] > c["tick"]) for s in seeds)
        require(c["births"] == sum(bool(p["parent"]) for p in present) and
                c["deaths"] == dead and c["living"] == len(present) - dead and c["seeds"] == pending,
                "checkpoint/ledger mismatch")
        require(0 <= c["nodes"] <= 512 and 0 <= pending <= 8, "world capacity exceeded")
    by_id = {p["id"]: p for p in plants}
    families = {}
    for p in plants:
        require(p["species"] in range(3), "invalid species")
        if p["parent"]:
            require(by_id[p["parent"]]["species"] == p["species"], "changed inherited species")
        families[p["id"]] = families[p["parent"]] if p["parent"] else p["id"]
    living = [p for p in plants if p["death_tick"] is None]
    return {"evaluation": score, "terminal_species": dict(Counter(SPECIES[p["species"]] for p in living)),
            "terminal_families": dict(Counter(str(families[p["id"]]) for p in living)),
            "final": checkpoints[-1], "lineages": len(plants), "seed_records": len(seeds)}


def evaluate(root, model, seed, target, timings, policy="neural"):
    value, elapsed = run_json([root / "bin/garden-persistence-trial", model, policy,
                              "0x" + seed, "0x" + PATCH, START, END], target)
    result = validate_trial(value, seed, model_crc(model), policy=policy)
    timings.append({"artifact": str(target.relative_to(root)), "seconds": elapsed})
    print(target.relative_to(root), result["evaluation"]["key"],
          result["final"]["hash"], f"{elapsed:.3f}s", flush=True)
    return result


def select(incumbent, candidates):
    best = incumbent
    for candidate in candidates:
        if fitness.compare(candidate["aggregate"], best["aggregate"]) > 0:
            best = candidate
    return best


def search(root, folder, timings):
    folder.mkdir()
    candidates, champions = [], []
    rng = 0x70696C32

    def assess(name, model, parent, mutation):
        worlds = {seed: evaluate(root, model, seed, folder / f"{name}.{seed}.json", timings)
                  for seed in DEVELOPMENT}
        c = {"id": name, "parent": parent, "mutation": mutation, "model_crc32": model_crc(model),
             "model_sha256": experiment.digest(model), "worlds": worlds,
             "aggregate": fitness.aggregate({s: r["evaluation"] for s, r in worlds.items()})}
        candidates.append(c)
        return c

    shutil.copyfile(root / "input/initial.tgm", folder / "initial.tgm")
    best = assess("initial", folder / "initial.tgm", None, None)
    champions.append(best["id"])
    for generation in (1, 2):
        parent, offspring = best, []
        for child in (1, 2, 3):
            name = f"g{generation}-c{child}"
            model = folder / f"{name}.tgm"
            mutation, _ = run_json([root / "bin/garden-model-mutate", folder / f"{parent['id']}.tgm",
                                    model, rng, 32], folder / f"{name}.mutation.json")
            require(mutation["before"] == parent["model_crc32"] and
                    mutation["after"] == model_crc(model) and mutation["rng_before"] == rng,
                    "mutation identity mismatch")
            rng = mutation["rng_after"]
            offspring.append(assess(name, model, parent["id"], mutation))
        best = select(parent, offspring)
        champions.append(best["id"])
    return {"candidates": candidates, "champions": champions, "rng_after": rng}


def replay_command(root, model, seed, tick, raw=None, policy="neural", *, patch=PATCH):
    mode = "neural-no-night-growth" if policy == "neural" else "neural-reserve-growth"
    args = [root / "bin/garden-replay", model, "rainfed-crowded", mode, "0x" + seed,
            "--leaf-policy", "selective", "--disturbance-seed", int(patch, 16), "--ticks", tick]
    return args + (["--framebuffer", raw] if raw else [])


def check_replay(value, trial, seed, crc, tick, raw=None, policy="neural", *, patch=PATCH):
    checkpoint = next(c for c in trial["checkpoints"] if c["tick"] == tick)
    expected = {"schema_version": 1, "scenario": "rainfed-crowded", "seed": seed,
                "policy": "neural-no-night-growth" if policy == "neural" else "neural-reserve-growth",
                "model_crc32": crc, "node_capacity": 512, "leaf_policy": "selective",
                "seed_dispersal": "wide-v1", "water_uptake": "headroom-v1",
                "leaf_environment": "leaf-maintenance-v1", "disturbance_protocol": "patch-death-v1",
                "disturbance_seed": patch, "tick": tick,
                **{k: checkpoint[k] for k in ("hash", "living", "births", "deaths", "nodes")},
                "seed_bank": checkpoint["seeds"]}
    require(all(value.get(k) == v for k, v in expected.items()), "independent replay mismatch")
    if raw is not None:
        require(len(raw) == gallery.FRAME_BYTES and f"{zlib.crc32(raw):08x}" == value["framebuffer_crc32"],
                "invalid framebuffer length/CRC")


def preflight(root, recruitment, timings):
    require(experiment.digest(recruitment / "manifest.json") == RECRUITMENT_SHA,
            "wrong frozen recruitment bundle")
    manifest = experiment.read_json(recruitment / "manifest.json")
    folder = root / "preflight"
    folder.mkdir()
    results = []
    for number, seed in ((44, "b61837dc"), (45, "c7f54e18")):
        for policy in ("neural", "reserve"):
            case = f"512.{number}.fresh-1.off.{policy}"
            source = f"analyses/{case}.json"
            require(experiment.digest(recruitment / source) == manifest["artifacts"][source],
                    "changed recruitment history")
            old = experiment.read_json(recruitment / source)
            shutil.copyfile(recruitment / source, folder / f"{case}.baseline.json")
            target = folder / f"{case}.json"
            score = evaluate(root, root / "input/initial.tgm", seed, target, timings, policy)
            new = experiment.read_json(target)
            original = fitness.world(old["world"]["lineages"], old["seeds"]["seeds"], START, END, STOP,
                                     source_start=160 * DAY)
            require(score["evaluation"] == original, "saved/native full fitness differs")
            require(len(new["lineages"]) == len(old["world"]["lineages"]), "saved/native birth count differs")
            for a, b in zip(new["lineages"], old["world"]["lineages"]):
                require(all(a[k] == b[k] for k in ("id", "parent", "birth_tick", "death_tick", "column",
                                                 "generation", "seeds_created")) and
                        a["environmental_death"] == b.get("environmental_death", False) and
                        SPECIES[a["species"]] == b["species"], "saved/native lifetime differs")
            require(len(new["seeds"]) == len(old["seeds"]["seeds"]), "saved/native seed count differs")
            key = lambda s: (s["parent"], s["birth_tick"])
            for a, b in zip(sorted(new["seeds"], key=key), sorted(old["seeds"]["seeds"], key=key)):
                require(all(a[k] == b[k] for k in a), "saved/native seed outcome differs")
            replay, _ = run_json(replay_command(root, root / "input/initial.tgm", seed, STOP, policy=policy),
                                 folder / f"{case}.replay.json")
            check_replay(replay, new, seed, "dc5e849d", STOP, policy=policy)
            require(replay["hash"] == old["world"]["final"]["hash"], "optimized/saved world hash differs")
            results.append({"case": case, "key": new["key"], "hash": replay["hash"],
                            "lineages": len(new["lineages"]), "seed_records": len(new["seeds"])})
    return results


def review(root, search_result, timings):
    folder = root / "review"
    folder.mkdir()
    generations, rows = [], []
    for generation, champion in enumerate(search_result["champions"]):
        model = folder / f"generation-{generation}.tgm"
        shutil.copyfile(root / "search" / f"{champion}.tgm", model)
        worlds = {}
        for seed in REVIEW:
            name = f"g{generation}.{seed}"
            trial_file = folder / f"{name}.json"
            worlds[seed] = evaluate(root, model, seed, trial_file, timings)
            trial = experiment.read_json(trial_file)
            frames = []
            for tick in TICKS:
                frame_id = f"{name}.{tick}"
                raw_file, png = folder / f"{frame_id}.rgb565", folder / f"{frame_id}.png"
                replay, elapsed = run_json(replay_command(root, model, seed, tick, raw_file),
                                           folder / f"{frame_id}.replay.json")
                raw = raw_file.read_bytes()
                check_replay(replay, trial, seed, model_crc(model), tick, raw)
                gallery.write_png(png, 240, 240, gallery.rgb565be_to_rgb888(raw))
                # A separate reset/process must reproduce both the state and the pixels.
                with tempfile.TemporaryDirectory(prefix="garden-frame-repeat-") as temp:
                    other_raw, other_json = Path(temp) / "frame.rgb565", Path(temp) / "replay.json"
                    other, _ = run_json(replay_command(root, model, seed, tick, other_raw), other_json)
                    require(other == replay and other_raw.read_bytes() == raw, "independent frame repeat differs")
                frames.append({"id": frame_id, "generation": generation, "seed": seed, "tick": tick,
                               "champion": champion, "model_crc32": model_crc(model),
                               "hash": replay["hash"], "framebuffer_crc32": replay["framebuffer_crc32"],
                               "framebuffer": str(raw_file.relative_to(root)),
                               "png": str(png.relative_to(root))})
                timings.append({"artifact": str(png.relative_to(root)), "seconds": elapsed})
            rows.append(frames)
        generations.append({"generation": generation, "champion": champion, "worlds": worlds,
                            "aggregate": fitness.aggregate({s: v["evaluation"] for s, v in worlds.items()})})
    sheet = gallery.contact_sheet(root, rows)
    return {"generations": generations, "frames": rows, "contact_sheet": sheet}


def verify(root):
    manifest = experiment.read_json(root / "manifest.json")
    require(manifest["rule"] == RULE and manifest["status"] == "complete", "incomplete/wrong pilot")
    for name in manifest["artifacts"]:
        gallery.artifact(root, manifest, name)
    result = experiment.read_json(root / "results.json")
    require(result["search"] == experiment.read_json(root / "repeat.json"), "search repeat mismatch")
    search_result = result["search"]
    require(len(search_result["candidates"]) == 7 and len(search_result["champions"]) == 3,
            "wrong search budget")
    candidates = {c["id"]: c for c in search_result["candidates"]}
    best = candidates["initial"]
    require(search_result["champions"][0] == "initial", "missing unchanged control")
    for generation in (1, 2):
        offspring = [candidates[f"g{generation}-c{i}"] for i in (1, 2, 3)]
        require(all(c["parent"] == best["id"] for c in offspring), "wrong mutation parent")
        best = select(best, offspring)
        require(best["id"] == search_result["champions"][generation], "wrong champion selection")
    for folder in ("search", "repeat"):
        for c in result["search"]["candidates"]:
            model = root / folder / f"{c['id']}.tgm"
            require(experiment.digest(model) == c["model_sha256"] and model_crc(model) == c["model_crc32"],
                    "candidate model mismatch")
            for seed in DEVELOPMENT:
                trial = experiment.read_json(root / folder / f"{c['id']}.{seed}.json")
                require(validate_trial(trial, seed, c["model_crc32"]) == c["worlds"][seed],
                        "saved candidate score mismatch")
            require(fitness.aggregate({s: w["evaluation"] for s, w in c["worlds"].items()}) == c["aggregate"],
                    "candidate aggregate mismatch")
    for g in result["review"]["generations"]:
        model = root / "review" / f"generation-{g['generation']}.tgm"
        require(experiment.digest(model) == candidates[g["champion"]]["model_sha256"], "wrong review model")
        for seed in REVIEW:
            trial = experiment.read_json(root / "review" / f"g{g['generation']}.{seed}.json")
            require(validate_trial(trial, seed, model_crc(model)) == g["worlds"][seed], "review score mismatch")
    frames = result["review"]["frames"]
    require(len(frames) == 6 and all(len(row) == 3 for row in frames), "missing generation pictures")
    for row in frames:
        for frame in row:
            trial = experiment.read_json(root / "review" / f"g{frame['generation']}.{frame['seed']}.json")
            replay = experiment.read_json(root / "review" / f"{frame['id']}.replay.json")
            check_replay(replay, trial, frame["seed"], frame["model_crc32"], frame["tick"],
                         (root / frame["framebuffer"]).read_bytes())
    print("Verified complete pilot artifacts, models, all 34 trial scores and search repeat", flush=True)


def run(build, recruitment, output):
    begin, timings = time.monotonic(), []
    require(not output.exists(), "pilot output already exists")
    require(experiment.digest(recruitment / "manifest.json") == RECRUITMENT_SHA,
            "wrong frozen recruitment bundle")
    baseline = experiment.read_json(recruitment / "manifest.json")
    require(experiment.digest(recruitment / "input/512.tgm") == baseline["artifacts"]["input/512.tgm"],
            "initial model differs from the frozen file")
    cache = (build / "CMakeCache.txt").read_text().splitlines()
    required = {"TOY_FACTORY_SIMULATOR_SANITIZERS": "ON", "TOY_FACTORY_GARDEN_WIDE_DISPERSAL": "ON",
                "TOY_FACTORY_GARDEN_WATER_HEADROOM": "ON", "TOY_FACTORY_GARDEN_COMBINED_EXPERIMENT": "ON",
                "TOY_FACTORY_GARDEN_LARGE_POOL": "ON", "TOY_FACTORY_GARDEN_LEAF_MAINTENANCE": "ON",
                "TOY_FACTORY_GARDEN_BOTTOM_DRAINAGE": "OFF", "TOY_FACTORY_GARDEN_LARGE_SEED_BANK": "OFF",
                "TOY_FACTORY_GARDEN_SEED_RESERVE": "OFF"}
    require(all(f"{k}:BOOL={v}" in cache for k, v in required.items()) and
            "CMAKE_BUILD_TYPE:STRING=RelWithDebInfo" in cache and
            "CMAKE_C_FLAGS_RELWITHDEBINFO:STRING=-O2 -g" in cache, "wrong pilot build settings")
    output.mkdir(parents=True)
    sources = experiment.source_files()
    experiment.snapshot_sources(output, sources)
    (output / "bin").mkdir()
    (output / "input").mkdir()
    for name in BINARIES:
        shutil.copy2(build / f"toy-factory-{name}", output / "bin" / name)
    for name in ("CMakeCache.txt", "build.ninja"):
        shutil.copyfile(build / name, output / "input" / name)
    shutil.copyfile(experiment.ROOT / PROTOCOL, output / "input/protocol.md")
    shutil.copyfile(recruitment / "input/512.tgm", output / "input/initial.tgm")
    shutil.copyfile(recruitment / "manifest.json", output / "input/recruitment-manifest.json")
    require(model_crc(output / "input/initial.tgm") == "dc5e849d", "wrong initial model")
    frozen = {str(p.relative_to(output)): experiment.digest(p)
              for directory in ("bin", "input") for p in (output / directory).iterdir()}
    pre = preflight(output, recruitment, timings)
    first = search(output, output / "search", timings)
    repeated = search(output, output / "repeat", timings)
    require(first == repeated, "full search repeat differs")
    for c in first["candidates"]:
        require((output / "search" / f"{c['id']}.tgm").read_bytes() ==
                (output / "repeat" / f"{c['id']}.tgm").read_bytes(), "repeated model bytes differ")
    views = review(output, first, timings)
    require(experiment.source_files() == sources, "sources changed during collection")
    require(all(experiment.digest(output / n) == d for n, d in frozen.items()), "frozen inputs changed")
    experiment.write_json(output / "repeat.json", repeated)
    experiment.write_json(output / "results.json", {"rule": RULE, "preflight": pre, "search": first,
                                                   "review": views, "repeat_equal": True})
    experiment.write_json(output / "timings.json", {"wall_seconds": time.monotonic() - begin, "calls": timings})
    artifacts = {str(p.relative_to(output)): experiment.digest(p) for p in sorted(output.rglob("*")) if p.is_file()}
    experiment.write_json(output / "manifest.json", {"rule": RULE, "status": "complete", "sources": sources,
        "artifacts": artifacts, "artifact_bytes": sum((output / n).stat().st_size for n in artifacts),
        "recruitment_manifest_sha256": RECRUITMENT_SHA, "protocol_sha256": frozen["input/protocol.md"],
        "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=experiment.ROOT, text=True).strip()})
    verify(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path, default=Path("artifacts/persistence-pilot-build"))
    parser.add_argument("--recruitment", type=Path, default=Path("artifacts/garden-crowded-recruitment"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.verify:
        verify(args.output.resolve())
    else:
        run(args.build.resolve(), args.recruitment.resolve(), args.output.resolve())


if __name__ == "__main__":
    main()
