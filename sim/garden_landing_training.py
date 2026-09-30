#!/usr/bin/env python3
"""Fixed-budget landing-mask renewal pilot. No ecology or firmware promotion."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import itertools
import json
from pathlib import Path
import shutil
import sys
import tempfile
import time

import garden_individual_renewal as individual
import garden_landing_evaluate as replay
from garden_experiments import digest, source_files, snapshot_sources, write_json
from garden_gallery import artifact, contact_sheet, rgb565be_to_rgb888, write_png
from garden_resources import require

ROOT = Path(__file__).resolve().parents[1]
RULE = "garden-landing-renewal-pilot-v1"
PROTOCOL = "benchmarks/garden-seasons/landing-training-protocol.md"
BASE_SHA = "fab9b6d97de88a970d63bb8af8fc336d076bb3d0ae6867b307290209abf85cf2"
MODES = ("off", "current", "history")
SEARCH_SEEDS = (0x6d697833, 0x6d697834, 0x6d697835)
TRAIN_SEED, REVIEW_SEED = "a9c30c1f", "ed52188c"
GENERATIONS, CHILDREN = 2, 3
DAY, STOP = 3840, 192 * 3840
TIMEOUT = 120
rolling = individual.previous


def conditions(seed):
    return [{"id": f"{layout}-{climate}-{seed}", "scenario": layout, "climate": climate, "seed": seed}
            for layout, climate in itertools.product(replay.SCENARIOS, ("steady", "seasonal"))]


def native(binary, root, *args):
    return replay.native(root, [str(binary), *map(str, args)], TIMEOUT)


def run_world(binary, root, model, case, ticks=STOP, frame=None):
    return native(binary, root, "replay", model, case["scenario"], "0x" + case["seed"],
                  "--ticks", ticks, "--climate", case["climate"], "--ledger",
                  *(["--framebuffer", frame] if frame else []))


def score_world(result, case, model):
    require(result["schema_version"] == 1 and result["kind"] == "landing-replay"
            and result["run_version"] == 1 and result["rules"] == 0 and result["tick"] == STOP
            and result["ledger_start_tick"] == 0 and result["model"] == model
            and result["scenario"] == case["scenario"] and result["seed"] == case["seed"]
            and result["climate"]["mode"] == case["climate"] and result["gardener"] is False
            and result["irrigation"] is False and result["framebuffer_crc32"] is None,
            "mismatched training world or unsupported ecology")
    plants, seeds = result["lineages"], result["seeds"]
    rolling.descendants.index_records(plants, seeds, 0, STOP)
    require(sum(p["parent"] != 0 for p in plants) == result["births"]
            and sum(p["death_tick"] is not None for p in plants) == result["deaths"]
            and sum(p["death_tick"] is None for p in plants) == result["living"]
            and sum(s["outcome"] == "pending" for s in seeds) == result["seed_bank"],
            "unreconciled complete ledger")
    return rolling.history(plants, seeds, 0, STOP)


def evaluate(binary, root, model, seed, jobs, metadata):
    cases = conditions(seed)
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        results = list(pool.map(lambda c: run_world(binary, root, model, c), cases))
    worlds = {c["id"]: {"result": r, "history": score_world(r, c, metadata)}
              for c, r in zip(cases, results, strict=True)}
    return {"worlds": worlds, "aggregate": individual.aggregate(
        {k: w["history"] for k, w in worlds.items()}, list(worlds))}


def biological(result):
    """Mask identity/run fingerprint can differ even when behavior is identical."""
    return {k: v for k, v in result.items() if k not in ("model", "run_hash", "framebuffer_crc32")}


def winner(incumbent, children):
    best = incumbent
    for child in children:
        if child["train"]["aggregate"]["key"] > best["train"]["aggregate"]["key"]:
            best = child
    return best


def capture(binary, root, model, review, generation):
    frames = []
    for case in conditions(REVIEW_SEED):
        if case["climate"] != "seasonal":
            continue
        for day in (16, 192):
            name = f"g{generation}-{case['id']}-day-{day}"
            raw, png = f"frames/{name}.rgb565be", f"frames/{name}.png"
            result = run_world(binary, root, model, case, day * DAY, raw)
            pixels = (root / raw).read_bytes()
            replay.check_result(result, {**case, "label": "champion"}, day * DAY,
                                review["worlds"][case["id"]]["result"]["model"], 0, pixels)
            if day == 192:
                require({**result, "framebuffer_crc32": None} == review["worlds"][case["id"]]["result"],
                        "capture changed evaluation")
            write_png(root / png, 240, 240, rgb565be_to_rgb888(pixels))
            frames.append({**case, "id": name, "day": day, "framebuffer": raw, "png": png,
                           "model": model, "result": result})
    return frames


def check_gallery(gallery, run):
    candidates = {c["id"]: c for c in run["candidates"]}
    plan = []
    for generation in run["generations"]:
        number = generation["generation"]
        model = candidates[generation["champion"]]["model"]
        for case in conditions(REVIEW_SEED):
            if case["climate"] != "seasonal":
                continue
            for day in (16, 192):
                plan.append({**case, "id": f"g{number}-{case['id']}-day-{day}", "model": model, "day": day})
    require([{k: frame[k] for k in ("id", "model", "day", "scenario", "climate", "seed")}
             for frame in gallery["frames"]] == plan, "missing/extra/reordered/wrong-champion frames")


def search(binary, legacy, root, jobs, images, progress=False):
    """One deterministic search graph; worker count/capture do not affect it."""
    root.mkdir(parents=True)
    searches, galleries = {}, {}
    for search_seed, mode in itertools.product(SEARCH_SEEDS, MODES):
        key = f"s{search_seed:08x}-{mode}"
        work = root / key
        (work / "models").mkdir(parents=True)
        (work / "frames").mkdir()
        initial_path = "models/g0.tgl"
        metadata = native(binary, work, "import", legacy, initial_path, "--mode", mode)["model"]
        require(metadata["legacy_payload_crc32"] == "01b9d94a"
                and metadata["common_nonzero_weights"] == metadata["candidate_nonzero_weights"] == 0
                and metadata["mode"] == mode and metadata["omit_dead_only"] is False,
                "wrong initial controller")
        initial = {"id": "g0", "model": initial_path, "sha256": digest(work / initial_path),
                   "parent": None, "mutation": None, "metadata": metadata,
                   "train": evaluate(binary, work, initial_path, TRAIN_SEED, jobs, metadata)}
        write_json(work / "g0.json", initial)
        incumbent, rng = initial, search_seed
        candidates, generations, frames = [initial], [], []
        for generation in range(GENERATIONS + 1):
            if generation:
                children = []
                for child in range(CHILDREN):
                    identity = f"g{generation}-c{child}"
                    path = f"models/{identity}.tgl"
                    mutation = native(binary, work, "mutate", incumbent["model"], path, rng, 32, 16)
                    require(mutation["rng_before"] == rng and mutation["legacy_mutations"] == 32
                            and mutation["landing_mutations"] == 16
                            and mutation["model"]["mode"] == mode, "invalid mutation receipt")
                    rng = mutation["rng_after"]
                    candidate = {"id": identity, "model": path, "sha256": digest(work / path),
                                 "parent": incumbent["id"], "mutation": mutation, "metadata": mutation["model"],
                                 "train": evaluate(binary, work, path, TRAIN_SEED, jobs, mutation["model"])}
                    write_json(work / f"{identity}.json", candidate)
                    children.append(candidate)
                incumbent = winner(incumbent, children)
                candidates.extend(children)
            review = evaluate(binary, work, incumbent["model"], REVIEW_SEED, jobs, incumbent["metadata"])
            record = {"generation": generation, "champion": incumbent["id"], "sha256": incumbent["sha256"],
                      "rng_after": rng, "training_key": incumbent["train"]["aggregate"]["key"], "review": review}
            write_json(work / f"generation-{generation}.json", record)
            generations.append(record)
            if images:
                frames.extend(capture(binary, work, incumbent["model"], review, generation))
            if progress:
                print(f"{key} generation {generation}: train={record['training_key']} "
                      f"review={review['aggregate']['key']} champion={incumbent['id']}", flush=True)
        searches[key] = {"search_seed": search_seed, "mode": mode, "candidates": candidates,
                         "generations": generations}
        if images:
            rows = [frames[i:i + 2] for i in range(0, len(frames), 2)]
            sheet = contact_sheet(work, rows)
            galleries[key] = {"frames": frames, "sheet": sheet}
    baseline = next(iter(searches.values()))["candidates"][0]["train"]
    for run in searches.values():
        other = run["candidates"][0]["train"]
        require(other["aggregate"] == baseline["aggregate"] and
                all(biological(w["result"]) == biological(baseline["worlds"][k]["result"])
                    for k, w in other["worlds"].items()), "zero-extension controls differ")
    result = {"rule": RULE, "objective": individual.RULE, "searches": searches,
              "candidate_evaluations": len(searches) * (1 + GENERATIONS * CHILDREN)}
    write_json(root / "results.json", result)
    if images:
        write_json(root / "gallery.json", galleries)
    return result


def markdown(result):
    lines = ["# Landing-aware renewal pilot", "", "Development only; no promotion. Fixed budget exhausted.",
             "Training and separate manual-review worlds both use the unchanged bounded-renewal objective.",
             "All keys are lexicographic; their four components are not interchangeable scores.", "",
             "| Search seed / mask | Initial training | Final training | Initial review | Final review | Champion |",
             "|---|---|---|---|---|---|"]
    for key, run in result["searches"].items():
        a, b = run["generations"][0], run["generations"][-1]
        lines.append(f"| {key} | {a['training_key']} | {b['training_key']} | "
                     f"{a['review']['aggregate']['key']} | {b['review']['aggregate']['key']} | {b['champion']} |")
    lines += ["", "The complete search was repeated with one worker and captures disabled; all saved models, "
              "mutation RNG states, ledgers, scores and champion choices matched.",
              "Review does not select winners. These previously seen development seeds are not a final test set.",
              "Equal candidate budgets and mutation draw schedules do not imply equal effective search difficulty.",
              "", "## Generation galleries", "",
              "Columns: days 16 and 192. Rows: generation 0 rainfed/crowded, then generation 1, then generation 2.",
              "Fixed seasonal review seed ed52188c; failures retained."]
    for key in result["searches"]:
        lines += ["", f"### {key}", "", f"![Generation review]({key}/contact-sheet.png)"]
    return "\n".join(lines) + "\n"


def check_flags(cache):
    flags = dict(line.split("=", 1) for line in cache.read_text().splitlines()
                 if line.startswith("TOY_FACTORY_GARDEN_") and ":BOOL=" in line)
    require(flags and all(value == "OFF" for value in flags.values()), "pilot requires ordinary ecology")
    return flags


def collect(build, legacy, output, jobs):
    require(1 <= jobs <= 8, "jobs must be 1..8")
    require(not output.exists() and (output.is_relative_to(ROOT / "artifacts") or
            not output.is_relative_to(ROOT)), "choose a fresh artifacts/ or external output directory")
    require(digest(legacy) == BASE_SHA, "wrong frozen initial controller")
    cache, binary = build / "CMakeCache.txt", build / "toy-factory-garden-landing"
    flags = check_flags(cache)
    inputs = {"binary": digest(binary), "cache": digest(cache), "legacy": digest(legacy)}
    sources = source_files()
    output.mkdir(parents=True)
    start = time.monotonic()
    try:
        (output / "bin").mkdir()
        shutil.copy2(binary, output / "bin/garden-landing")
        shutil.copy2(legacy, output / "initial.tgm")
        shutil.copy2(cache, output / "CMakeCache.txt")
        shutil.copy2(ROOT / PROTOCOL, output / "protocol.md")
        # Preserve the established scorer's transitive imports for frozen verification.
        for path in (ROOT / "sim").glob("*.py"):
            target = output / "sim" / path.name
            target.parent.mkdir(exist_ok=True)
            shutil.copy2(path, target)
        for name in ("framebuffer_capture.py", "serial_shell.py"):
            target = output / "scripts/container" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / "scripts/container" / name, target)
        snapshot_sources(output, sources)
        write_json(output / "started.json", {"rule": RULE, "inputs": inputs, "flags": flags,
                   "protocol_sha256": digest(output / "protocol.md"), "sources": sources})
        frozen_binary, frozen_legacy = output / "bin/garden-landing", output / "initial.tgm"
        require(digest(frozen_binary) == inputs["binary"] and digest(frozen_legacy) == inputs["legacy"]
                and digest(output / "CMakeCache.txt") == inputs["cache"], "inputs changed during copy")
        result = search(frozen_binary, frozen_legacy, output / "search", jobs, True, True)
        print("Repeating complete search/review with one worker and capture disabled...", flush=True)
        repeated = search(frozen_binary, frozen_legacy, output / "repeat", 1, False, True)
        require(result == repeated, "capture/worker count changed search")
        for model in (output / "search").rglob("*.tgl"):
            require(model.read_bytes() == (output / "repeat" / model.relative_to(output / "search")).read_bytes(),
                    "repeat model bytes differ")
        require(sources == source_files(), "sources changed during collection")
        require(inputs == {"binary": digest(binary), "cache": digest(cache), "legacy": digest(legacy)},
                "build/input changed during collection")
        require(inputs == {"binary": digest(frozen_binary), "cache": digest(output / "CMakeCache.txt"),
                           "legacy": digest(frozen_legacy)}, "frozen input changed during collection")
        with (output / "search/report.md").open("x") as stream:
            stream.write(markdown(result))
        write_json(output / "timings.json", {"collection_and_repeat_seconds": time.monotonic() - start})
        artifacts = {str(p.relative_to(output)): digest(p) for p in sorted(output.rglob("*")) if p.is_file()}
        write_json(output / "manifest.json", {"rule": RULE, "status": "complete", "repeat_verified": True,
                   "inputs": inputs, "source_sha256_at_collection": sources, "build_flags": flags,
                   "artifacts": artifacts})
    except BaseException as error:
        with (output / "FAILED.txt").open("x") as stream:
            stream.write(str(error) + "\n")
        raise
    return result


def verify(output):
    require(not (output / "FAILED.txt").exists(), "incomplete bundle")
    manifest = json.loads((output / "manifest.json").read_text())
    require(manifest["rule"] == RULE and manifest["status"] == "complete"
            and manifest["repeat_verified"] is True, "wrong/incomplete pilot")
    for name in manifest["artifacts"]:
        artifact(output, manifest, name)
    binary = artifact(output, manifest, "bin/garden-landing")
    legacy = artifact(output, manifest, "initial.tgm")
    require(digest(legacy) == BASE_SHA and check_flags(output / "CMakeCache.txt") == manifest["build_flags"],
            "wrong input/ecology")
    require(manifest["inputs"] == {"binary": digest(binary), "cache": digest(output / "CMakeCache.txt"),
                                   "legacy": digest(legacy)} and
            digest(output / "protocol.md") == manifest["source_sha256_at_collection"][PROTOCOL],
            "input/protocol provenance mismatch")
    expected = json.loads(artifact(output, manifest, "search/results.json").read_text())
    require(expected == json.loads(artifact(output, manifest, "repeat/results.json").read_text()),
            "saved repetition differs")
    galleries = json.loads(artifact(output, manifest, "search/gallery.json").read_text())
    require(set(galleries) == set(expected["searches"]), "missing generation gallery")
    for key, gallery in galleries.items():
        check_gallery(gallery, expected["searches"][key])
    with tempfile.TemporaryDirectory(prefix="landing-training-verify-") as temporary:
        fresh = Path(temporary) / "search"
        repeated = search(binary, legacy, fresh, 2, False, True)
        require(repeated == expected, "frozen search is not reproducible")
        for model in fresh.rglob("*.tgl"):
            original = artifact(output, manifest, "search/" + str(model.relative_to(fresh)))
            require(original.read_bytes() == model.read_bytes(), "model bytes changed")
        for key, gallery in galleries.items():
            work = output / "search" / key
            for frame in gallery["frames"]:
                raw = Path(temporary) / "frame.raw"
                result = run_world(binary, work, frame["model"], frame, frame["day"] * DAY, str(raw))
                require(result == frame["result"] and raw.read_bytes() == (work / frame["framebuffer"]).read_bytes(),
                        "frame replay differs")
                png = Path(temporary) / "frame.png"
                write_png(png, 240, 240, rgb565be_to_rgb888(raw.read_bytes()))
                require(png.read_bytes() == (work / frame["png"]).read_bytes(), "PNG pixels differ")
                png.unlink()
                raw.unlink()
            rows = [[{**f, "framebuffer": str(work / f["framebuffer"])} for f in gallery["frames"][i:i + 2]]
                    for i in range(0, len(gallery["frames"]), 2)]
            require(contact_sheet(Path(temporary), rows) == gallery["sheet"] and
                    (Path(temporary) / "contact-sheet.png").read_bytes() == (work / "contact-sheet.png").read_bytes(),
                    "contact sheet differs")
            (Path(temporary) / "contact-sheet.png").unlink()
    for name in manifest["artifacts"]:
        artifact(output, manifest, name)
    print("Verified fixed search, model bytes, ledgers, decisions, and all generation frames.", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--jobs", type=int)
    parser.add_argument("--verify", type=Path, help="execute a trusted local frozen bundle")
    args = parser.parse_args()
    try:
        if args.verify:
            require(args.build is None and args.input is None and args.out is None and args.jobs is None,
                    "verify takes no collection overrides")
            verify(args.verify.resolve())
        else:
            require(args.out is not None, "collection requires --out")
            collect((args.build or ROOT / "build-host").resolve(),
                    (args.input or ROOT / "artifacts/garden-seasonal-model-eval/models/candidate.tgm").resolve(),
                    args.out.resolve(), 2 if args.jobs is None else args.jobs)
        return 0
    except (OSError, ValueError, RuntimeError) as error:
        print(f"landing pilot failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
