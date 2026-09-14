#!/usr/bin/env python3
"""Fixed mixed-condition persistence search with a separate generation review panel."""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
import shutil
import tempfile
import time

import garden_pilot_validation as validation
import garden_training_pilot as pilot

experiment, fitness, require = pilot.experiment, pilot.fitness, pilot.require
RULE = "garden-mixed-training-v1"
PROTOCOL = "benchmarks/garden-longevity/mixed-training-protocol.md"
DEVELOPMENT = ("5fd2b58f", "acc67fa4", "f9bd207c", "4aff6bf2")
REVIEW = ("2109e05f", "d21d2a74", "876675ac", "34243e22")
PATCHES = validation.PATCHES
GENERATIONS, OFFSPRING, MUTATIONS, RNG = 3, 3, 32, 0x6D697833
NARROW_SHA = "511b26198ed46fbe7e1a5a7893613450613f2cb24b2abea9b2f0ec5ba6fe6fb2"


@dataclass(frozen=True)
class Study:
    name: str
    rule: str
    protocol: str
    development: tuple[str, ...]
    review: tuple[str, ...]

    def record(self):
        return {"name": self.name, "rule": self.rule, "protocol": self.protocol,
                "development": list(self.development), "review": list(self.review),
                "patches": dict(PATCHES), "generations": GENERATIONS, "offspring": OFFSPRING,
                "mutations": MUTATIONS, "rng": RNG}


MIXED = Study("mixed", RULE, PROTOCOL, DEVELOPMENT, REVIEW)
COVERAGE = Study("coverage", "garden-training-coverage-v1",
                 "benchmarks/garden-longevity/training-coverage-protocol.md",
                 DEVELOPMENT + ("68d9e00c", "9bcd2a27", "ceb675ff", "7df43e71"),
                 ("eb300b12", "1824c139", "4d5f9ee1", "fe1dd56f"))
STUDIES = {s.name: s for s in (MIXED, COVERAGE)}


def study_for_rule(rule):
    matching = [s for s in STUDIES.values() if s.rule == rule]
    require(len(matching) == 1, "unknown study rule")
    return matching[0]


def review_name(generation):
    return "narrow" if generation == "narrow" else f"g{generation}"


def conditions(seeds):
    return [(f"{a}.{s}", a, s, patch) for a, patch in PATCHES.items() for s in seeds]


def aggregate(worlds, seeds):
    require(set(worlds) == {c[0] for c in conditions(seeds)}, "missing/extra panel condition")
    return fitness.aggregate({key: worlds[key]["evaluation"] for key, *_ in conditions(seeds)})


def comparison(control, candidate, seeds):
    """Diagnostic paired comparisons; only the development aggregate selects models."""
    aggregate(control, seeds)
    aggregate(candidate, seeds)

    def group(keys):
        a, b = (fitness.aggregate({k: w[k]["evaluation"] for k in keys}) for w in (control, candidate))
        pairs = [{"condition": k, "comparison": fitness.compare(candidate[k]["evaluation"], control[k]["evaluation"]),
                  "renewal_delta": candidate[k]["evaluation"]["key"][1] - control[k]["evaluation"]["key"][1]}
                 for k in keys]
        return {"control": a, "candidate": b, "comparison": fitness.compare(b, a), "pairs": pairs,
                "paired_counts": {label: sum(p["comparison"] == v for p in pairs)
                                  for label, v in (("wins", 1), ("ties", 0), ("losses", -1))}}

    items = conditions(seeds)
    return {"overall": group([c[0] for c in items]),
            "schedules": {a: group([k for k, schedule, *_ in items if schedule == a]) for a in PATCHES},
            "leave_one_world_seed_out": {s: group([k for k, _, seed, _ in items if seed != s]) for s in seeds}}


def diversity(worlds):
    return {field: dict(Counter(str(len(w[field])) for w in worlds.values()))
            for field in ("terminal_species", "terminal_families")}


def evaluate(root, folder, name, model, seeds, timings):
    worlds = {}
    for key, _, seed, patch in conditions(seeds):
        target = folder / f"{name}.{key}.json"
        value, elapsed = pilot.run_json([root / "bin/garden-persistence-trial", model, "neural",
                                         "0x" + seed, "0x" + patch, pilot.START, pilot.END], target)
        worlds[key] = pilot.validate_trial(value, seed, pilot.model_crc(model), patch=patch)
        timings.append({"artifact": str(target.relative_to(root)), "seconds": elapsed})
        print(target.relative_to(root), value["key"], f"{elapsed:.2f}s", flush=True)
    return worlds


def search(root, folder, timings, on_generation=None, *, study=MIXED):
    folder.mkdir()
    candidates, champions, rng = [], [], RNG

    def assess(name, model, parent, mutation):
        worlds = evaluate(root, folder, name, model, study.development, timings)
        candidate = {"id": name, "parent": parent, "mutation": mutation,
                     "model_crc32": pilot.model_crc(model), "model_sha256": experiment.digest(model),
                     "worlds": worlds, "aggregate": aggregate(worlds, study.development)}
        candidates.append(candidate)
        return candidate

    shutil.copyfile(root / "input/initial.tgm", folder / "initial.tgm")
    best = assess("initial", folder / "initial.tgm", None, None)
    champions.append(best["id"])
    if on_generation:
        on_generation(0, best["id"])
    for generation in range(1, GENERATIONS + 1):
        parent, offspring = best, []
        for child in range(1, OFFSPRING + 1):
            name = f"g{generation}-c{child}"
            model = folder / f"{name}.tgm"
            mutation, _ = pilot.run_json([root / "bin/garden-model-mutate", folder / f"{parent['id']}.tgm",
                                          model, rng, MUTATIONS], folder / f"{name}.mutation.json")
            require(mutation["before"] == parent["model_crc32"] and mutation["after"] == pilot.model_crc(model)
                    and mutation["rng_before"] == rng, "mutation identity mismatch")
            rng = mutation["rng_after"]
            offspring.append(assess(name, model, parent["id"], mutation))
        best = pilot.select(parent, offspring)
        champions.append(best["id"])
        if on_generation:
            on_generation(generation, best["id"])
    return {"candidates": candidates, "champions": champions, "rng_after": rng}


def check_search(result, *, study=MIXED):
    names = ["initial"] + [f"g{g}-c{c}" for g in range(1, GENERATIONS + 1) for c in range(1, OFFSPRING + 1)]
    require([c["id"] for c in result["candidates"]] == names, "wrong search order/budget")
    require(len(result["champions"]) == GENERATIONS + 1 and result["champions"][0] == "initial",
            "missing generation/control")
    indexed = {c["id"]: c for c in result["candidates"]}
    best, rng = indexed["initial"], RNG
    require(best["parent"] is None and best["mutation"] is None, "mutated generation zero")
    for c in indexed.values():
        require(aggregate(c["worlds"], study.development) == c["aggregate"], "candidate aggregate mismatch")
    for g in range(1, GENERATIONS + 1):
        children = [indexed[f"g{g}-c{i}"] for i in range(1, OFFSPRING + 1)]
        for c in children:
            m = c["mutation"]
            require(c["parent"] == best["id"] and m["before"] == best["model_crc32"] and
                    m["after"] == c["model_crc32"] and m["rng_before"] == rng and
                    type(m["rng_after"]) is int and 0 <= m["rng_after"] <= 0xFFFFFFFF,
                    "mutation ancestry/RNG mismatch")
            rng = m["rng_after"]
        best = pilot.select(best, children)
        require(result["champions"][g] == best["id"], "wrong development champion")
    require(rng == result["rng_after"], "wrong final RNG")


def review_generation(root, generation, champion, timings, *, study=MIXED):
    folder = root / "review"
    name = review_name(generation)
    model = folder / f"{name}.tgm"
    source = root / "input/narrow.tgm" if generation == "narrow" else root / "search" / f"{champion}.tgm"
    shutil.copyfile(source, model)
    worlds = evaluate(root, folder, name, model, study.review, timings)
    frames = []
    for key, schedule, seed, patch in conditions(study.review):
        identity = f"{name}.{key}"
        raw, png = folder / f"{identity}.rgb565", folder / f"{identity}.png"
        replay, elapsed = pilot.run_json(pilot.replay_command(root, model, seed, pilot.STOP, raw, patch=patch),
                                         folder / f"{identity}.replay.json")
        pixels = raw.read_bytes()
        trial = experiment.read_json(folder / f"{identity}.json")
        pilot.check_replay(replay, trial, seed, pilot.model_crc(model), pilot.STOP, pixels, patch=patch)
        pilot.gallery.write_png(png, 240, 240, pilot.gallery.rgb565be_to_rgb888(pixels))
        with tempfile.TemporaryDirectory(prefix="mixed-garden-frame-") as temp:
            other_raw, other_json = Path(temp) / "frame.rgb565", Path(temp) / "frame.json"
            other, repeat_time = pilot.run_json(pilot.replay_command(root, model, seed, pilot.STOP, other_raw,
                                                                    patch=patch), other_json)
            require(other == replay and other_raw.read_bytes() == pixels, "independent frame repeat differs")
        timings.append({"artifact": str(png.relative_to(root)), "seconds": elapsed, "repeat_seconds": repeat_time})
        frames.append({"id": identity, "generation": generation, "condition": key, "schedule": schedule,
                       "seed": seed, "tick": pilot.STOP, "champion": champion, "model_crc32": pilot.model_crc(model),
                       "hash": replay["hash"], "framebuffer_crc32": replay["framebuffer_crc32"],
                       "framebuffer": str(raw.relative_to(root)), "png": str(png.relative_to(root))})
    return {"generation": generation, "champion": champion, "worlds": worlds,
            "aggregate": aggregate(worlds, study.review), "frames": frames}


def diagnostics(search_result, reviews, *, study=MIXED):
    candidates = {c["id"]: c for c in search_result["candidates"]}
    return [{"generation": g, "champion": champion,
             "development": comparison(candidates["initial"]["worlds"], candidates[champion]["worlds"], study.development),
             "review": comparison(reviews[0]["worlds"], reviews[g]["worlds"], study.review),
             "development_diversity": diversity(candidates[champion]["worlds"]),
             "review_diversity": diversity(reviews[g]["worlds"])}
            for g, champion in enumerate(search_result["champions"])]


def coverage_diagnostics(search_result, reviews, narrow):
    indexed = {c["id"]: c for c in search_result["candidates"]}
    def subset(worlds, seeds):
        return {key: worlds[key] for key, *_ in conditions(seeds)}
    return [{"generation": g,
             "versus_narrow_review": comparison(narrow["worlds"], reviews[g]["worlds"], COVERAGE.review),
             "original_training_seeds": comparison(subset(indexed["initial"]["worlds"], DEVELOPMENT),
                  subset(indexed[champion]["worlds"], DEVELOPMENT), DEVELOPMENT),
             "added_training_seeds": comparison(subset(indexed["initial"]["worlds"], COVERAGE.development[4:]),
                  subset(indexed[champion]["worlds"], COVERAGE.development[4:]), COVERAGE.development[4:])}
            for g, champion in enumerate(search_result["champions"])]


def check_review(root, r, champion, crc, sha, seeds):
    g = r["generation"]
    name = review_name(g)
    require(r["champion"] == champion and experiment.digest(root / "review" / f"{name}.tgm") == sha,
            "wrong review champion")
    require(aggregate(r["worlds"], seeds) == r["aggregate"], "wrong review aggregate")
    require([f["condition"] for f in r["frames"]] == [c[0] for c in conditions(seeds)], "missing/extra frame")
    for f, (key, schedule, seed, patch) in zip(r["frames"], conditions(seeds), strict=True):
        identity = f"{name}.{key}"
        require(all(f[k] == v for k, v in {"id": identity, "generation": g, "schedule": schedule,
                "seed": seed, "tick": pilot.STOP, "champion": champion, "model_crc32": crc,
                "framebuffer": f"review/{identity}.rgb565", "png": f"review/{identity}.png"}.items()),
                "wrong frame identity")
        trial = experiment.read_json(root / "review" / f"{identity}.json")
        require(pilot.validate_trial(trial, seed, crc, patch=patch) == r["worlds"][key], "changed review ledger/score")
        replay = experiment.read_json(root / "review" / f"{identity}.replay.json")
        raw = (root / f["framebuffer"]).read_bytes()
        pilot.check_replay(replay, trial, seed, crc, pilot.STOP, raw, patch=patch)
        require(f["hash"] == replay["hash"] and f["framebuffer_crc32"] == replay["framebuffer_crc32"],
                "changed frame attribution")
        with tempfile.TemporaryDirectory(prefix="mixed-png-check-") as temp:
            png = Path(temp) / "frame.png"
            pilot.gallery.write_png(png, 240, 240, pilot.gallery.rgb565be_to_rgb888(raw))
            require(png.read_bytes() == (root / f["png"]).read_bytes(), "PNG/raw mismatch")


def check_results(root, result, *, study=MIXED):
    require(result["rule"] == study.rule, "wrong result rule")
    search_result = result["search"]
    check_search(search_result, study=study)
    require(search_result == experiment.read_json(root / "repeat.json"), "capture/no-capture search differs")
    for folder in ("search", "repeat"):
        require((root / folder / "initial.tgm").read_bytes() == (root / "input/initial.tgm").read_bytes(),
                "changed original control")
        for c in search_result["candidates"]:
            model = root / folder / f"{c['id']}.tgm"
            require(pilot.model_crc(model) == c["model_crc32"] and experiment.digest(model) == c["model_sha256"],
                    "changed candidate model")
            if c["mutation"]:
                require(experiment.read_json(root / folder / f"{c['id']}.mutation.json") == c["mutation"],
                        "changed mutation record")
            for key, _, seed, patch in conditions(study.development):
                trial = experiment.read_json(root / folder / f"{c['id']}.{key}.json")
                require(pilot.validate_trial(trial, seed, c["model_crc32"], patch=patch) == c["worlds"][key],
                        "changed development ledger/score")
    reviews = result["review"]
    require([r["generation"] for r in reviews] == list(range(GENERATIONS + 1)), "missing/duplicate review generation")
    candidates = {c["id"]: c for c in search_result["candidates"]}
    for r, champion in zip(reviews, search_result["champions"], strict=True):
        check_review(root, r, champion, candidates[champion]["model_crc32"], candidates[champion]["model_sha256"], study.review)
    require(result["diagnostics"] == diagnostics(search_result, reviews, study=study), "changed diagnostic comparison")
    views = list(reviews)
    if study == COVERAGE:
        require(experiment.read_json(root / "input/study.json") == study.record(), "changed study settings")
        require(experiment.digest(root / "input/narrow-manifest.json") == NARROW_SHA, "changed narrow reference manifest")
        reference = experiment.read_json(root / "input/narrow-manifest.json")
        sha = reference["artifacts"]["search/g3-c2.tgm"]
        require(experiment.digest(root / "input/narrow.tgm") == sha, "changed narrow reference model")
        narrow = result["narrow_review"]
        require(narrow["generation"] == "narrow", "reference is not a search generation")
        check_review(root, narrow, "narrow", "449c35fe", sha, study.review)
        # Same mutation stream and original worlds must exactly reproduce generation one.
        for name in ("initial", "g1-c1", "g1-c2", "g1-c3"):
            for suffix in ["tgm"] + [f"{k}.json" for k, *_ in conditions(DEVELOPMENT)]:
                path = f"search/{name}.{suffix}"
                require(experiment.digest(root / path) == reference["artifacts"][path], "common-prefix replay differs")
        require(result["coverage_diagnostics"] == coverage_diagnostics(search_result, reviews, narrow),
                "changed coverage/reference comparison")
        views.append(narrow)
    rows = [[r["frames"][i] for r in views] for i in range(len(conditions(study.review)))]
    require(result["gallery"]["rows"] == [[f["id"] for f in row] for row in rows], "wrong gallery layout")


def verify(root):
    m = experiment.read_json(root / "manifest.json")
    study = study_for_rule(m["rule"])
    require(m["status"] == "complete" and
            m["pilot_manifest_sha256"] == validation.BASELINE_SHA, "wrong/incomplete mixed pilot")
    for name in m["artifacts"]:
        pilot.gallery.artifact(root, m, name)
    require(experiment.digest(root / "input/pilot-manifest.json") == validation.BASELINE_SHA, "changed baseline manifest")
    baseline = experiment.read_json(root / "input/pilot-manifest.json")
    for name in pilot.BINARIES:
        require(experiment.digest(root / "bin" / name) == baseline["artifacts"][f"bin/{name}"], "changed frozen native tool")
    require(experiment.digest(root / "input/initial.tgm") == baseline["artifacts"]["search/initial.tgm"] and
            pilot.model_crc(root / "input/initial.tgm") == "dc5e849d", "changed frozen original model")
    result = experiment.read_json(root / "results.json")
    check_results(root, result, study=study)
    frames = (GENERATIONS + 1 + (study == COVERAGE)) * len(conditions(study.review))
    trials = 2 * (1 + GENERATIONS * OFFSPRING) * len(conditions(study.development)) + frames
    print(f"Verified {trials} trial scores, ten candidate models, capture/no-capture equality and {frames} review frames", flush=True)
    return result


def collect(baseline, output, *, study=MIXED, narrow=None):
    require(output.is_relative_to(experiment.ROOT / "artifacts") and not output.exists() and
            not output.is_relative_to(baseline), "choose a fresh artifacts output directory")
    require(experiment.digest(baseline / "manifest.json") == validation.BASELINE_SHA, "wrong frozen pilot")
    pilot.verify(baseline)
    if study == COVERAGE:
        require(narrow is not None and not output.is_relative_to(narrow) and
                experiment.digest(narrow / "manifest.json") == NARROW_SHA, "wrong narrow reference")
        verify(narrow)
    m = experiment.read_json(baseline / "manifest.json")
    sources = experiment.source_files()
    output.mkdir(parents=True)
    experiment.snapshot_sources(output, sources)
    for folder in ("bin", "input", "review"):
        (output / folder).mkdir()
    copies = {"manifest.json": "input/pilot-manifest.json", "input/CMakeCache.txt": "input/CMakeCache.txt",
              "search/initial.tgm": "input/initial.tgm", **{f"bin/{n}": f"bin/{n}" for n in pilot.BINARIES}}
    for src, dest in copies.items():
        shutil.copy2(baseline / src, output / dest)
        require(experiment.digest(output / dest) ==
                (validation.BASELINE_SHA if src == "manifest.json" else m["artifacts"][src]), "input copy differs")
    shutil.copyfile(experiment.ROOT / study.protocol, output / "input/protocol.md")
    if study == COVERAGE:
        shutil.copyfile(narrow / "manifest.json", output / "input/narrow-manifest.json")
        shutil.copyfile(narrow / "search/g3-c2.tgm", output / "input/narrow.tgm")
        experiment.write_json(output / "input/study.json", study.record())
    frozen = {str(p.relative_to(output)): experiment.digest(p) for folder in ("bin", "input")
              for p in (output / folder).iterdir()}
    experiment.write_json(output / "started.json", {"rule": study.rule, "sources": sources, "frozen": frozen})
    timings, reviews, begin = [], [], time.monotonic()
    try:
        first = search(output, output / "search", timings,
                       lambda g, champion: reviews.append(review_generation(output, g, champion, timings, study=study)),
                       study=study)
        repeated = search(output, output / "repeat", timings, study=study)
        require(first == repeated, "capture/no-capture search differs")
        experiment.write_json(output / "repeat.json", repeated)
        extra, views = {}, list(reviews)
        if study == COVERAGE:
            reference = review_generation(output, "narrow", "narrow", timings, study=study)
            extra = {"narrow_review": reference, "coverage_diagnostics": coverage_diagnostics(first, reviews, reference)}
            views.append(reference)
        rows = [[r["frames"][i] for r in views] for i in range(len(conditions(study.review)))]
        result = {"rule": study.rule, "search": first, "review": reviews, "diagnostics": diagnostics(first, reviews, study=study),
                  **extra,
                  "gallery": pilot.gallery.contact_sheet(output, rows)}
        check_results(output, result, study=study)
        require(experiment.source_files() == sources, "sources changed during collection")
        require(all(experiment.digest(output / n) == d for n, d in frozen.items()), "frozen inputs changed")
        require(experiment.digest(baseline / "manifest.json") == validation.BASELINE_SHA, "baseline changed")
        experiment.write_json(output / "results.json", result)
        experiment.write_json(output / "timings.json", {"wall_seconds": time.monotonic() - begin, "calls": timings})
        artifacts = {str(p.relative_to(output)): experiment.digest(p) for p in sorted(output.rglob("*")) if p.is_file()}
        experiment.write_json(output / "manifest.json", {"rule": study.rule, "status": "complete", "sources": sources,
            "pilot_manifest_sha256": validation.BASELINE_SHA, "artifacts": artifacts,
            "artifact_bytes": sum((output / n).stat().st_size for n in artifacts)})
    except BaseException as error:
        experiment.write_json(output / "failure.json", {"error": str(error)})
        raise
    verify(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pilot", type=Path, default=experiment.ROOT / "artifacts/garden-training-pilot-v1")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--study", choices=tuple(STUDIES), help="Fixed protocol for collection; verification reads the bundle rule")
    parser.add_argument("--narrow-pilot", type=Path, default=experiment.ROOT / "artifacts/garden-mixed-training-v1")
    args = parser.parse_args()
    if args.verify:
        require(args.study is None, "verification reads its study from the saved bundle")
        verify(args.output.resolve())
    else:
        collect(args.pilot.resolve(), args.output.resolve(), study=STUDIES[args.study or "mixed"], narrow=args.narrow_pilot.resolve())


if __name__ == "__main__":
    main()
