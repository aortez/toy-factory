#!/usr/bin/env python3
"""Bounded, paired live/fixed-input training with a frozen evaluation split."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import gzip
import json
from pathlib import Path
import shutil
import sys
import tempfile
import time

import garden_landing_signals as signals
from garden_experiments import digest, source_files, snapshot_sources, write_json
from garden_gallery import artifact, contact_sheet, rgb565be_to_rgb888, write_png
from garden_resources import require

ROOT = Path(__file__).resolve().parents[1]
RULE = "garden-landing-live-fixed-training-v1"
PROTOCOL = "benchmarks/garden-seasons/landing-controls-protocol.md"
INPUTS = {**signals.previous.INPUTS, "landing-training-histories.json.gz":
          "b4ba4860623a391a065494aff4cc5f3dfe841f046a8d4339ec41ae829691669e"}
PROFILES = ({"id": "live", "occupancy": "live", "resources": "live"},
            {"id": "fixed", "occupancy": "occupied", "resources": "low"})
EVALUATION_SEEDS = ("b6b2db49", "56aa3924", "20588d83", "0cf65b97")
training = signals.training


def load_inputs(root):
    for name, sha in INPUTS.items():
        require(digest(root / name) == sha, "wrong frozen input: " + name)
    models = signals.previous.load_inputs(root)
    old = json.loads(gzip.decompress((root / "landing-training-histories.json.gz").read_bytes()))
    require(old["rule"] == training.RULE and old["objective"] == training.individual.RULE,
            "wrong original training control")
    return models, old


def evaluation_conditions():
    return [c for seed in EVALUATION_SEEDS for c in training.conditions(seed)]


def slices():
    cases = evaluation_conditions()
    return {"all": [c["id"] for c in cases], **{
        f"{field}/{value}": [c["id"] for c in cases if c[field] == value]
        for field in ("seed", "scenario", "climate")
        for value in dict.fromkeys(c[field] for c in cases)}}


def evaluate(binary, root, model, cases, profile, jobs, metadata):
    require(1 <= jobs <= 8 and profile in PROFILES, "invalid worker count/profile")
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        values = list(pool.map(lambda c: signals.run_world(binary, root, model, c, profile), cases))
    worlds = {c["id"]: {"result": r, "history": training.score_world(
        signals.scoring_view(r, profile), c, metadata)} for c, r in zip(cases, values, strict=True)}
    return {"worlds": worlds, "aggregate": training.individual.aggregate(
        {k: w["history"] for k, w in worlds.items()}, [c["id"] for c in cases])}


def equivalent_evaluation(new, old, profile, old_profile=None):
    require(new["aggregate"] == old["aggregate"] and set(new["worlds"]) == set(old["worlds"]),
            "control conditions/score changed")
    for key, world in new["worlds"].items():
        previous = old["worlds"][key]
        a = signals.scoring_view(world["result"], profile)
        b = signals.scoring_view(previous["result"], old_profile) if old_profile else previous["result"]
        # Explicit GSP1 probe identity differs from GLR1, or from another profile.
        require({k: v for k, v in a.items() if k != "run_hash"} ==
                {k: v for k, v in b.items() if k != "run_hash"} and
                world["history"] == previous["history"], "control biological trajectory changed")


def capture(binary, root, model, review, generation, profile):
    frames = []
    for case in training.conditions(training.REVIEW_SEED):
        if case["climate"] != "seasonal":
            continue
        for day in (16, 192):
            name = f"g{generation}-{case['id']}-day-{day}"
            raw, png = f"frames/{name}.rgb565be", f"frames/{name}.png"
            value = signals.run_world(binary, root, model, case, profile, raw, day * training.DAY)
            pixels = (root / raw).read_bytes()
            metadata = review["worlds"][case["id"]]["result"]["model"]
            training.replay.check_result(signals.scoring_view(value, profile), case,
                                         day * training.DAY, metadata, 0, pixels)
            headless = (review["worlds"][case["id"]]["result"] if day == 192 else
                        signals.run_world(binary, root, model, case, profile, ticks=day * training.DAY))
            require({**value, "framebuffer_crc32": None} == headless, "capture changed world")
            write_png(root / png, 240, 240, rgb565be_to_rgb888(pixels))
            frames.append({**case, "id": name, "model": model, "profile": profile, "day": day,
                           "framebuffer": raw, "png": png, "result": value})
    return frames


def search_one(binary, legacy, work, search_seed, profile, jobs, images, *, train_cases=None):
    cases = [dict(c) for c in (training.conditions(training.TRAIN_SEED) if train_cases is None else train_cases)]
    require(cases and len({c["id"] for c in cases}) == len(cases), "empty/duplicate training conditions")
    require(not any(c["seed"] == training.REVIEW_SEED for c in cases), "review seed in training")
    (work / "models").mkdir(parents=True)
    (work / "frames").mkdir()
    path = "models/g0.tgl"
    metadata = training.native(binary, work, "import", legacy, path, "--mode", "current")["model"]
    require(metadata["legacy_payload_crc32"] == "01b9d94a" and metadata["mode"] == "current" and
            metadata["omit_dead_only"] is False and
            metadata["common_nonzero_weights"] == metadata["candidate_nonzero_weights"] == 0,
            "wrong initial controller")
    initial = {"id": "g0", "model": path, "sha256": digest(work / path), "parent": None,
               "mutation": None, "metadata": metadata,
               "train": evaluate(binary, work, path, cases, profile, jobs, metadata)}
    write_json(work / "g0.json", initial)
    incumbent, rng = initial, search_seed
    candidates, generations, frames = [initial], [], []
    for generation in range(training.GENERATIONS + 1):
        if generation:
            children = []
            for child in range(training.CHILDREN):
                identity = f"g{generation}-c{child}"
                path = f"models/{identity}.tgl"
                mutation = training.native(binary, work, "mutate", incumbent["model"], path, rng, 32, 16)
                require(mutation["rng_before"] == rng and mutation["legacy_mutations"] == 32 and
                        mutation["landing_mutations"] == 16 and mutation["model"]["mode"] == "current" and
                        mutation["model"]["omit_dead_only"] is False, "mutation changed schedule/config")
                rng = mutation["rng_after"]
                candidate = {"id": identity, "model": path, "sha256": digest(work / path),
                             "parent": incumbent["id"], "mutation": mutation, "metadata": mutation["model"],
                             "train": evaluate(binary, work, path, cases, profile, jobs, mutation["model"])}
                write_json(work / f"{identity}.json", candidate)
                children.append(candidate)
            incumbent = training.winner(incumbent, children)
            candidates.extend(children)
        review = evaluate(binary, work, incumbent["model"], training.conditions(training.REVIEW_SEED),
                          profile, jobs, incumbent["metadata"])
        record = {"generation": generation, "champion": incumbent["id"], "sha256": incumbent["sha256"],
                  "rng_after": rng, "training_key": incumbent["train"]["aggregate"]["key"], "review": review}
        write_json(work / f"generation-{generation}.json", record)
        generations.append(record)
        if images:
            frames.extend(capture(binary, work, incumbent["model"], review, generation, profile))
        print(f"s{search_seed:08x}-{profile['id']} g{generation}: {incumbent['id']} "
              f"train={record['training_key']} review={review['aggregate']['key']}", flush=True)
    run = {"search_seed": search_seed, "profile": profile, "candidates": candidates, "generations": generations}
    gallery = None
    if images:
        training.check_gallery({"frames": frames}, run)
        gallery = {"frames": frames, "sheet": contact_sheet(work, [frames[i:i + 2] for i in range(0, len(frames), 2)])}
    return run, gallery


def check_controls(searches, root, archived, old):
    first = next(iter(searches.values()))
    for seed in training.SEARCH_SEEDS:
        live, fixed = (searches[f"s{seed:08x}-{p['id']}"] for p in PROFILES)
        prior = old["searches"][f"s{seed:08x}-current"]
        require(len(live["candidates"]) == len(fixed["candidates"]) == len(prior["candidates"]),
                "wrong candidate budget")
        for run in (live, fixed):
            equivalent_evaluation(run["candidates"][0]["train"], first["candidates"][0]["train"],
                                   run["profile"], first["profile"])
        for a, b, previous in zip(live["candidates"], fixed["candidates"], prior["candidates"], strict=True):
            require(a["id"] == b["id"], "unpaired candidate order")
            if a["mutation"] is not None:
                fields = ("rng_before", "rng_after", "legacy_mutations", "landing_mutations")
                require(all(a["mutation"][f] == b["mutation"][f] for f in fields), "unpaired RNG schedule")
            if a["id"] == "g0" or a["id"].startswith("g1-"):
                require(a["sha256"] == b["sha256"], "paired initial/first-generation models differ")
            require({k: v for k, v in a.items() if k != "train"} ==
                    {k: v for k, v in previous.items() if k != "train"}, "live search lineage changed")
            equivalent_evaluation(a["train"], previous["train"], PROFILES[0])
            data = (root / f"s{seed:08x}-live" / a["model"]).read_bytes()
            require(data == archived[f"s{seed:08x}-current/{a['model']}"], "live model bytes changed")
        for a, previous in zip(live["generations"], prior["generations"], strict=True):
            require({k: v for k, v in a.items() if k != "review"} ==
                    {k: v for k, v in previous.items() if k != "review"}, "live champion changed")
            equivalent_evaluation(a["review"], previous["review"], PROFILES[0])


def comparisons(evaluations):
    pairs = []
    for seed in training.SEARCH_SEEDS:
        pairs.append(("paired-training", f"s{seed:08x}-fixed", f"s{seed:08x}-live"))
        pairs.extend(("initial-control", "initial-" + p["id"], f"s{seed:08x}-{p['id']}") for p in PROFILES)
    return [{"kind": kind, "control": a, "candidate": b,
             "slices": {name: training.individual.pair_group(
                 {k: w["history"] for k, w in evaluations[a]["worlds"].items()},
                 {k: w["history"] for k, w in evaluations[b]["worlds"].items()}, ids)
                        for name, ids in slices().items()}} for kind, a, b in pairs]


def support_gate(pairs):
    primary = [p for p in pairs if p["kind"] == "paired-training"]
    require(len(primary) == len(training.SEARCH_SEEDS), "incomplete primary comparisons")
    checks = []
    for pair in primary:
        for name in ("all", "climate/steady", "climate/seasonal"):
            item = pair["slices"][name]
            checks.append({"candidate": pair["candidate"], "slice": name,
                           "pass": item["comparison"] == 1 and all(
                               item["candidate"]["key"][i] >= item["control"]["key"][i] for i in (0, 1))})
    return {"consistent_live_advantage": all(c["pass"] for c in checks), "checks": checks}


def run_panel(binary, inputs, root, jobs, images):
    require(1 <= jobs <= 8 and not root.exists(), "fresh output and jobs 1..8 required")
    archived, old = load_inputs(inputs)
    root.mkdir(parents=True)
    with (root / "initial.tgm").open("xb") as stream:
        stream.write(archived["initial.tgm"])
    searches, galleries = {}, {}
    for seed in training.SEARCH_SEEDS:
        for profile in PROFILES:
            key = f"s{seed:08x}-{profile['id']}"
            searches[key], gallery = search_one(binary, root / "initial.tgm", root / key,
                                                seed, profile, jobs, images)
            if images:
                galleries[key] = gallery
    check_controls(searches, root, archived, old)
    # Every winner is fixed before any new evaluation seed is run.
    models = []
    for profile in PROFILES:
        key = f"s{training.SEARCH_SEEDS[0]:08x}-{profile['id']}"
        initial = searches[key]["candidates"][0]
        models.append({"id": "initial-" + profile["id"], "profile": profile, "champion": "g0",
                       "model": key + "/" + initial["model"], "sha256": initial["sha256"],
                       "metadata": initial["metadata"]})
    for key, run in searches.items():
        final = run["generations"][-1]
        chosen = next(c for c in run["candidates"] if c["id"] == final["champion"])
        models.append({"id": key, "profile": run["profile"], "champion": chosen["id"],
                       "model": key + "/" + chosen["model"], "sha256": chosen["sha256"],
                       "metadata": chosen["metadata"]})
    evaluations = {}
    for model in models:
        value = evaluate(binary, root, model["model"], evaluation_conditions(), model["profile"], jobs, model["metadata"])
        evaluations[model["id"]] = value
        write_json(root / (model["id"] + "-evaluation.json"), value)
        print(model["id"] + " evaluation: " + str(value["aggregate"]["key"]), flush=True)
    equivalent_evaluation(evaluations["initial-live"], evaluations["initial-fixed"], PROFILES[0], PROFILES[1])
    for key, run in searches.items():
        for candidate in run["candidates"]:
            require(digest(root / key / candidate["model"]) == candidate["sha256"], "model changed during replay")
    paired = comparisons(evaluations)
    result = {"schema_version": 1, "rule": RULE, "objective": training.individual.RULE,
              "profiles": list(PROFILES), "evaluation_conditions": evaluation_conditions(),
              "searches": searches, "models": models, "evaluations": evaluations,
              "comparisons": paired, "support_gate": support_gate(paired),
              "candidate_evaluations": len(searches) * (1 + training.GENERATIONS * training.CHILDREN)}
    write_json(root / "results.json", result)
    if images:
        write_json(root / "gallery.json", galleries)
    return result


def collect(build, inputs, output, jobs, *, experiment=None):
    experiment = experiment or sys.modules[__name__]
    require(1 <= jobs <= 8 and not output.exists() and
            (output.is_relative_to(ROOT / "artifacts") or not output.is_relative_to(ROOT)),
            "fresh artifacts/external output and jobs 1..8 required")
    experiment.load_inputs(inputs)
    cache, binary = build / "CMakeCache.txt", build / "toy-factory-garden-landing"
    flags = training.check_flags(cache)
    identities = {"binary": digest(binary), "cache": digest(cache), **experiment.INPUTS}
    sources = source_files()
    output.mkdir(parents=True)
    start = time.monotonic()
    try:
        (output / "bin").mkdir()
        (output / "inputs").mkdir()
        shutil.copy2(binary, output / "bin/garden-landing")
        shutil.copy2(cache, output / "CMakeCache.txt")
        shutil.copy2(ROOT / experiment.PROTOCOL, output / "protocol.md")
        for name in experiment.INPUTS:
            shutil.copy2(inputs / name, output / "inputs" / name)
        for path in (ROOT / "sim").glob("*.py"):
            target = output / "sim" / path.name
            target.parent.mkdir(exist_ok=True)
            shutil.copy2(path, target)
        for name in ("framebuffer_capture.py", "serial_shell.py"):
            target = output / "scripts/container" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / "scripts/container" / name, target)
        snapshot_sources(output, sources)
        frozen = output / "bin/garden-landing"
        require(digest(frozen) == identities["binary"] and digest(output / "CMakeCache.txt") == identities["cache"] and
                digest(output / "protocol.md") == sources[experiment.PROTOCOL], "source/build changed during copy")
        result = experiment.run_panel(frozen, output / "inputs", output / "panel", jobs, True)
        print("Repeating searches and evaluation with one worker and no captures...", flush=True)
        repeated = experiment.run_panel(frozen, output / "inputs", output / "repeat", 1, False)
        require(result == repeated, "worker count/capture changed search or evaluation")
        for path in (output / "panel").rglob("*.tgl"):
            require(path.read_bytes() == (output / "repeat" / path.relative_to(output / "panel")).read_bytes(),
                    "repeat model bytes differ")
        require(sources == source_files() and digest(binary) == identities["binary"] and
                digest(cache) == identities["cache"], "sources/build changed during collection")
        experiment.load_inputs(inputs)
        experiment.load_inputs(output / "inputs")
        write_json(output / "timings.json", {"collection_and_repeat_seconds": time.monotonic() - start})
        write_json(output / "manifest.json", {"rule": experiment.RULE, "status": "complete", "repeat_verified": True,
                   "inputs": identities, "build_flags": flags, "source_sha256_at_collection": sources,
                   "artifacts": {str(p.relative_to(output)): digest(p) for p in sorted(output.rglob("*")) if p.is_file()}})
    except BaseException as error:
        with (output / "FAILED.txt").open("x") as stream:
            stream.write(str(error) + "\n")
        raise
    return result


def verify(output, *, experiment=None):
    experiment = experiment or sys.modules[__name__]
    require(not (output / "FAILED.txt").exists(), "incomplete training bundle")
    manifest = json.loads((output / "manifest.json").read_text())
    require(manifest["rule"] == experiment.RULE and manifest["status"] == "complete" and manifest["repeat_verified"] is True,
            "wrong/incomplete training bundle")
    for name in manifest["artifacts"]:
        artifact(output, manifest, name)
    binary = artifact(output, manifest, "bin/garden-landing")
    require(training.check_flags(output / "CMakeCache.txt") == manifest["build_flags"] and
            manifest["inputs"] == {"binary": digest(binary), "cache": digest(output / "CMakeCache.txt"), **experiment.INPUTS} and
            digest(output / "protocol.md") == manifest["source_sha256_at_collection"][experiment.PROTOCOL], "provenance mismatch")
    expected = json.loads(artifact(output, manifest, "panel/results.json").read_text())
    require(expected == json.loads(artifact(output, manifest, "repeat/results.json").read_text()), "repeat differs")
    with tempfile.TemporaryDirectory(prefix="landing-controls-verify-") as temporary:
        fresh = Path(temporary) / "panel"
        require(experiment.run_panel(binary, output / "inputs", fresh, 4, True) == expected, "training/evaluation not reproducible")
        for path in fresh.rglob("*"):
            if path.is_file():
                require(path.read_bytes() == artifact(output, manifest, "panel/" + str(path.relative_to(fresh))).read_bytes(),
                        "model, record or frame changed")
    for name in manifest["artifacts"]:
        artifact(output, manifest, name)
    scored = sum(len(c["train"]["worlds"]) for s in expected["searches"].values() for c in s["candidates"])
    scored += sum(len(g["review"]["worlds"]) for s in expected["searches"].values() for g in s["generations"])
    scored += sum(len(e["worlds"]) for e in expected["evaluations"].values())
    galleries = json.loads(artifact(output, manifest, "panel/gallery.json").read_text())
    frames = sum(len(g["frames"]) for g in galleries.values())
    print(f"Verified {expected['candidate_evaluations']} candidates, {scored} scored worlds, "
          f"every model and all {frames} frames.", flush=True)


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
            require(args.out is not None, "collection requires --out")
            collect((args.build or ROOT / "build-host").resolve(),
                    (args.inputs or ROOT / "benchmarks/garden-seasons").resolve(),
                    args.out.resolve(), 4 if args.jobs is None else args.jobs)
        return 0
    except (OSError, ValueError, RuntimeError) as error:
        print("live/fixed training failed: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
