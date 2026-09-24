#!/usr/bin/env python3
"""Fixed old-fitness / bounded-renewal training A/B, with independent review."""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
import shutil
import time

import garden_individual_renewal as individual
import garden_mixed_training as mixed

pilot, experiment, require = mixed.pilot, mixed.experiment, mixed.require
rolling = individual.previous
RULE = "garden-renewal-training-v1"
PROTOCOL = "benchmarks/garden-longevity/renewal-training-protocol.md"
BASELINE_SHA = "a9142bff1570b3912b7f7d5dc71dbf4575c3db6df10249cf9b3539643abaf460"
REVIEW = ("78a542dc", "8bb188f7", "decad72f", "6d889ca1")
STUDY = mixed.Study("renewal-training", RULE, PROTOCOL, mixed.COVERAGE.development, REVIEW)
ARMS = ("v2", "renewal")
COUNTS = {"training_trials": 320, "repeat_trials": 320, "review_trials": 64,
          "frame_replays": 128, "mutation_calls": 36, "native_processes": 868}


@dataclass(frozen=True)
class Objective:
    """Immutable opt-in adapter; no simulation, RNG or review state is owned here."""
    name: str

    def __post_init__(self):
        require(self.name in ARMS, "unknown experimental selector")

    def annotate(self, trial, ordinary):
        require(not any(k in trial for k in ("founder_exit", "gap_protocol", "root_bootstrap_rule")),
                "intervention-tainted training trial")
        require((trial["start"], trial["end"], trial["stop"]) == (pilot.START, pilot.END, pilot.STOP),
                "changed training horizon/follow-up")
        history = rolling.history(trial["lineages"], trial["seeds"], trial["start"], trial["stop"])
        require(history["blocks"][-1]["v2_key"] == ordinary["evaluation"]["key"], "changed legacy primary")
        return {**ordinary, "renewal_history": history}

    def aggregate(self, worlds, seeds, *, patches=mixed.PATCHES):
        ordinary = mixed.aggregate(worlds, seeds, patches=patches)
        require(ordinary["status"] == "complete", "incomplete training panel")
        values = {k: w["renewal_history"] for k, w in worlds.items()}
        bounded = individual.aggregate(values, [k for k, *_ in mixed.conditions(seeds, patches)])
        if self.name == "v2":
            return ordinary
        # Use the existing strict comparison/selection contract, with a distinct rule.
        return {**bounded, "status": "complete", "followup_deadline": pilot.STOP,
                "window": {"periods": [list(p) for p in rolling.PERIODS], "credit_age_ticks": rolling.CREDIT_AGE}}


def settings():
    require(tuple(experiment.trial_seeds(0x726E7631, 4)) == REVIEW and
            set(STUDY.development).isdisjoint(REVIEW) and len(set(REVIEW)) == 4, "invalid fixed split")
    return {"study": STUDY.record(), "arms": list(ARMS), "budget": COUNTS,
            "native_window": [pilot.START, pilot.END], "stop": pilot.STOP,
            "periods": [list(p) for p in rolling.PERIODS], "credit_age_ticks": rolling.CREDIT_AGE,
            "bounded_rule": individual.RULE, "legacy_rule": pilot.fitness.RULE,
            "review_seed_generator": "trial_seeds(0x726e7631, 4)",
            "review_seed_audit": "No literal matches before implementation in prior local sim/docs/benchmarks and artifacts JSON/JSONL/Markdown/Python; compressed/private history not claimed"}


def history_worlds(worlds):
    return {k: w["renewal_history"] for k, w in worlds.items()}


def comparison(control, candidate, seeds, *, patches=mixed.PATCHES):
    """Both yardsticks on the same worlds; this never selects or mutates a model."""
    legacy = mixed.comparison(control, candidate, seeds, patches=patches)
    items = mixed.conditions(seeds, patches)
    keys = [k for k, *_ in items]
    a, b = history_worlds(control), history_worlds(candidate)
    bounded = {"overall": individual.pair_group(a, b, keys),
        "schedules": {s: individual.pair_group(a, b, [k for k, schedule, *_ in items if schedule == s])
                      for s in patches},
        "leave_one_world_seed_out": {s: individual.pair_group(a, b, [k for k, _, seed, _ in items if seed != s])
                                     for s in seeds}}
    return {"v2": legacy, "renewal": bounded}


def compact_worlds(worlds):
    result = {}
    for k, w in worlds.items():
        h = individual.aggregate({k: w["renewal_history"]}, [k])
        result[k] = {field: w[field] for field in ("final", "terminal_species", "terminal_families", "lineages", "seed_records")}
        result[k].update(v2_key=w["evaluation"]["key"], terminal=w["evaluation"]["terminal"],
                         renewal_key=h["key"], **h["worlds"][k])
    return result


def cohort_summary(root, generation):
    values = {}
    for key, _, seed, patch in mixed.conditions(REVIEW):
        trial = experiment.read_json(root/"review"/f"g{generation}.{key}.json")
        score = pilot.validate_trial(trial, seed, trial["model_crc32"], patch=patch)["evaluation"]
        values[key] = mixed.validation.cohorts(trial["lineages"], trial["seeds"], score)
    return {"window": [pilot.START, pilot.END], "followup": pilot.STOP, "worlds": values}


def diagnostics(root, arms):
    reports, final_worlds = {}, {}
    for arm, result in arms.items():
        indexed = {c["id"]: c for c in result["search"]["candidates"]}
        final_worlds[arm] = indexed[result["search"]["champions"][-1]]["worlds"]
        reports[arm] = []
        for g, champion in enumerate(result["search"]["champions"]):
            c, review = indexed[champion], result["review"][g]
            reports[arm].append({"generation": g, "champion": champion, "model_crc32": c["model_crc32"],
                "training": comparison(indexed["initial"]["worlds"], c["worlds"], STUDY.development),
                "review": comparison(result["review"][0]["worlds"], review["worlds"], REVIEW),
                "training_worlds": compact_worlds(c["worlds"]), "review_worlds": compact_worlds(review["worlds"]),
                "review_cohorts": cohort_summary(root/"arms"/arm, g),
                "training_diversity": mixed.diversity(c["worlds"]), "review_diversity": mixed.diversity(review["worlds"])})
    reports["final_b_vs_a"] = {
        "training": comparison(final_worlds["v2"], final_worlds["renewal"], STUDY.development),
        "review": comparison(arms["v2"]["review"][-1]["worlds"], arms["renewal"]["review"][-1]["worlds"], REVIEW)}
    return reports


def combined_frames(arms):
    groups = []
    for i in range(len(mixed.conditions(REVIEW))):
        row = []
        for arm in ARMS:
            for r in arms[arm]["review"]:
                f = r["frames"][i]
                row.append({**f, "id": f"{arm}.{f['id']}", "arm": arm,
                            "framebuffer": f"arms/{arm}/{f['framebuffer']}", "png": f"arms/{arm}/{f['png']}"})
        groups.append(row)
    return groups


def check_history_matches(root, arms):
    baseline = experiment.read_json(root/"input/coverage-manifest.json")
    prior = experiment.read_json(root/"input/coverage-results.json")["search"]
    a, b = (arms[k]["search"] for k in ARMS)
    stripped = {**a, "candidates": [{**c, "worlds": {k: {f: v for f, v in w.items() if f != "renewal_history"}
                                                         for k, w in c["worlds"].items()}} for c in a["candidates"]]}
    require(stripped == prior, "A search does not reproduce frozen coverage selection")
    for c in a["candidates"]:
        suffixes = ["tgm", *[f"{k}.json" for k, *_ in mixed.conditions(STUDY.development)]]
        if c["mutation"]:
            suffixes.append("mutation.json")
        for suffix in suffixes:
            name = f"search/{c['id']}.{suffix}"
            require(experiment.digest(root/"arms/v2"/name) == baseline["artifacts"][name], "A native history differs")
    for ca, cb in zip(a["candidates"][:4], b["candidates"][:4], strict=True):
        require(ca["id"] == cb["id"] and all(ca[k] == cb[k] for k in
                ("model_sha256", "model_crc32", "mutation", "parent", "worlds")), "A/B common mutation prefix differs")
    require(arms["v2"]["review"][0]["worlds"] == arms["renewal"]["review"][0]["worlds"], "review original differs")


def check_results(root, result):
    require(result["rule"] == RULE and result["settings"] == settings() and set(result["arms"]) == set(ARMS),
            "wrong A/B contract or missing arm")
    for arm in ARMS:
        r, sub = result["arms"][arm], root/"arms"/arm
        require(r["objective"] == arm, "wrong arm selector")
        mixed.check_results(sub, r, study=STUDY, objective=Objective(arm))
        for c in r["search"]["candidates"]:
            for key, *_ in mixed.conditions(STUDY.development):
                name = f"{c['id']}.{key}.json"
                require((sub/"search"/name).read_bytes() == (sub/"repeat"/name).read_bytes(), "native search repeat differs")
            require((sub/"search"/f"{c['id']}.tgm").read_bytes() ==
                    (sub/"repeat"/f"{c['id']}.tgm").read_bytes(), "mutant byte repeat differs")
    check_history_matches(root, result["arms"])
    require(result["diagnostics"] == diagnostics(root, result["arms"]), "A/B analysis differs")
    groups = combined_frames(result["arms"])
    require(result["gallery"]["rows"] == [[f["id"] for f in row] for row in groups], "wrong combined gallery")


def check_budget(timing):
    require(set(timing["arms"]) == set(ARMS), "missing timing arm")
    commands = [row[k] for arm in ARMS for row in timing["arms"][arm]
                for k in ("command", "repeat_command") if k in row]
    require(Counter(Path(c[0]).name for c in commands) ==
            {"garden-persistence-trial": 704, "garden-replay": 128, "garden-model-mutate": 36}, "wrong native budget")
    require(not any("--founder-exit" in c or "--gap-at" in c for c in commands), "intervention entered training")


def verify(root):
    manifest = experiment.read_json(root/"manifest.json")
    require(manifest["rule"] == RULE and manifest["status"] == "complete", "wrong/incomplete A/B bundle")
    for name in manifest["artifacts"]:
        pilot.gallery.artifact(root, manifest, name)
    require(experiment.digest(root/"input/coverage-manifest.json") == BASELINE_SHA, "changed baseline")
    prior = experiment.read_json(root/"input/coverage-manifest.json")
    for dest, src in manifest["copied"].items():
        require(experiment.digest(root/dest) == prior["artifacts"][src], "changed frozen input")
    require(experiment.read_json(root/"input/settings.json") == settings(), "changed frozen settings")
    timing = experiment.read_json(root/"timings.json")
    check_budget(timing)
    result = experiment.read_json(root/"results.json")
    check_results(root, result)
    print("Verified two 3-generation searches, 704 ledgers, 64 repeated frames and frozen A history", flush=True)
    return result


def collect(baseline, output):
    require(not output.exists() and output.is_relative_to(experiment.ROOT/"artifacts") and
            not output.is_relative_to(baseline), "choose fresh separate artifacts output")
    require(experiment.digest(baseline/"manifest.json") == BASELINE_SHA, "wrong coverage input")
    mixed.verify(baseline)
    prior = experiment.read_json(baseline/"manifest.json")
    sources = experiment.source_files()
    require(all(sources.get(n) == sha for n, sha in prior["sources"].items() if n.startswith("src/") and
                n.endswith((".c", ".h"))), "simulation core changed")
    output.mkdir(parents=True)
    (output/"input").mkdir()
    experiment.snapshot_sources(output, sources)
    copied = {"input/coverage-results.json": "results.json", "input/CMakeCache.txt": "input/CMakeCache.txt",
              "input/native-source.tar.gz": "source.tar.gz"}
    for arm in ARMS:
        sub = output/"arms"/arm
        for name in ("input", "bin", "review"):
            (sub/name).mkdir(parents=True)
        copied[f"arms/{arm}/input/initial.tgm"] = "search/initial.tgm"
        for name in pilot.BINARIES:
            copied[f"arms/{arm}/bin/{name}"] = f"bin/{name}"
    for dest, src in copied.items():
        shutil.copy2(baseline/src, output/dest)
        require(experiment.digest(output/dest) == prior["artifacts"][src], "input copy differs")
    shutil.copy2(baseline/"manifest.json", output/"input/coverage-manifest.json")
    shutil.copy2(experiment.ROOT/PROTOCOL, output/"input/protocol.md")
    experiment.write_json(output/"input/settings.json", settings())
    frozen = {name: experiment.digest(output/name) for name in (*copied, "input/coverage-manifest.json",
                                                               "input/protocol.md", "input/settings.json")}
    experiment.write_json(output/"started.json", {"sources": sources, "frozen": frozen, "copied": copied, "rule": RULE})
    start, arms, timings = time.monotonic(), {}, {arm: [] for arm in ARMS}
    try:
        for arm in ARMS:
            objective, reviews, sub = Objective(arm), [], output/"arms"/arm
            print(f"Starting {arm}: capture-enabled search", flush=True)
            search = mixed.search(sub, sub/"search", timings[arm],
                lambda g, c: reviews.append(mixed.review_generation(sub, g, c, timings[arm], study=STUDY, objective=objective)),
                study=STUDY, objective=objective)
            print(f"Starting {arm}: capture-disabled repeat", flush=True)
            repeat = mixed.search(sub, sub/"repeat", timings[arm], study=STUDY, objective=objective)
            require(search == repeat, "capture/no-capture selection differs")
            experiment.write_json(sub/"repeat.json", repeat)
            rows = [[r["frames"][i] for r in reviews] for i in range(len(mixed.conditions(REVIEW)))]
            arms[arm] = {"rule": RULE, "objective": arm, "search": search, "review": reviews,
                         "diagnostics": mixed.diagnostics(search, reviews, study=STUDY),
                         "gallery": pilot.gallery.contact_sheet(sub, rows)}
            print(f"Finished {arm}: {search['champions']}", flush=True)
        result = {"rule": RULE, "settings": settings(), "arms": arms,
                  "diagnostics": diagnostics(output, arms),
                  "gallery": pilot.gallery.contact_sheet(output, combined_frames(arms))}
        check_results(output, result)
        require(experiment.source_files() == sources and all(experiment.digest(output/n) == sha for n, sha in frozen.items()),
                "source/input changed during collection")
        timing = {"wall_seconds": time.monotonic()-start, "arms": timings}
        check_budget(timing)
        experiment.write_json(output/"results.json", result)
        experiment.write_json(output/"timings.json", timing)
        artifacts = {str(p.relative_to(output)): experiment.digest(p) for p in output.rglob("*") if p.is_file()}
        experiment.write_json(output/"manifest.json", {"rule": RULE, "status": "complete", "sources": sources,
            "copied": copied, "artifacts": artifacts, "artifact_bytes": sum((output/n).stat().st_size for n in artifacts)})
    except BaseException as error:
        experiment.write_json(output/"failure.json", {"error": str(error)})
        raise
    verify(output)


def portable(root, result):
    candidates = {}
    for arm in ARMS:
        r = result["arms"][arm]
        candidates[arm] = {"champions": r["search"]["champions"], "rng_after": r["search"]["rng_after"],
            "candidates": [{k: v for k, v in c.items() if k != "worlds"} |
                           {"worlds": compact_worlds(c["worlds"]), "score_views": {
                               name: Objective(name).aggregate(c["worlds"], STUDY.development) for name in ARMS}}
                           for c in r["search"]["candidates"]]}
    return {"rule": RULE, "settings": settings(), "manifest_sha256": experiment.digest(root/"manifest.json"),
            "searches": candidates, "diagnostics": result["diagnostics"], "frames": combined_frames(result["arms"]),
            "timing": experiment.read_json(root/"timings.json"), "repeat_equal": True}


def export(root, prefix, check=False):
    result = verify(root)
    require(not prefix.is_relative_to(root), "cannot export inside frozen evidence")
    data, image, markdown, frames = [prefix.with_name(prefix.name+s) for s in ("-summary.json", ".png", "-gallery.md", "-frames")]
    expected = portable(root, result)
    lines = ["# Old fitness versus bounded renewal: generation gallery", "",
        "Fixed fresh review panel; all images at day 192. Columns: **A0, A1, A2, A3, B0, B1, B2, B3**.",
        "A selects persistence-v2; B selects individual bounded renewal. Rows follow the table below.",
        "Review never selects search parents; unchanged champions and failed worlds are retained.",
        "", f"![All 64 review frames]({image.name})", "",
        "| Row | Schedule | Seed |", "|---:|---|---|"]
    for i, (_, schedule, seed, _) in enumerate(mixed.conditions(REVIEW), 1):
        lines.append(f"| {i} | {schedule} | `{seed}` |")
    lines += ["", "| Frame | Model CRC | Living | World hash | Framebuffer CRC |", "|---|---|---:|---|---|"]
    for row in expected["frames"]:
        for f in row:
            w = result["arms"][f["arm"]]["review"][f["generation"]]["worlds"][f["condition"]]
            lines.append(f"| [{f['id']}]({frames.name}/{f['id']}.png) | `{f['model_crc32']}` | {w['final']['living']} | `{f['hash']}` | `{f['framebuffer_crc32']}` |")
    lines += ["", "All 64 framebuffers independently repeat byte-for-byte and match native ledger hashes.",
        "Images alone do not prove reproductive health or generalization. These are exploratory review worlds, not a final test.",
        "See the [report](renewal-training.md) and [paired data](renewal-training-summary.json).", "",
        f"Manifest SHA-256: `{expected['manifest_sha256']}`.", ""]
    content = "\n".join(lines)
    if not check:
        require(all(not p.exists() for p in (data, image, markdown, frames)), "export already exists")
        frames.mkdir(parents=True)
        experiment.write_json(data, expected)
        shutil.copyfile(root/"contact-sheet.png", image)
        with markdown.open("x") as stream:
            stream.write(content)
        for row in expected["frames"]:
            for f in row:
                shutil.copyfile(root/f["png"], frames/f"{f['id']}.png")
    require(experiment.read_json(data) == expected and markdown.read_text() == content, "portable metadata differs")
    require(experiment.digest(image) == experiment.digest(root/"contact-sheet.png"), "portable overview differs")
    for row in expected["frames"]:
        for f in row:
            require(experiment.digest(frames/f"{f['id']}.png") == experiment.digest(root/f["png"]), "portable frame differs")
    print("Portable A/B scores, diagnostics and all 64 PNGs match verified evidence", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, default=experiment.ROOT/"artifacts/garden-training-coverage-v1")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--export", type=Path)
    parser.add_argument("--check-export", type=Path)
    args = parser.parse_args()
    require(not (args.export and args.check_export) and (args.verify or not (args.export or args.check_export)), "export requires verify")
    if args.export or args.check_export:
        export(args.output.resolve(), (args.export or args.check_export).resolve(), bool(args.check_export))
    elif args.verify:
        verify(args.output.resolve())
    else:
        collect(args.baseline.resolve(), args.output.resolve())


if __name__ == "__main__":
    main()
