#!/usr/bin/env python3
"""Two fixed, independent search-stream replicas with schedule-held-out review."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import shutil
import time

import garden_renewal_training as previous

mixed, pilot, experiment, require = previous.mixed, previous.pilot, previous.experiment, previous.require
RULE = "garden-renewal-replication-v1"
PROTOCOL = "benchmarks/garden-longevity/renewal-replication-protocol.md"
BASELINE_SHA = "61d464b839b2dc988c99c1adb95008b4db8b88a71808991264b5acaf08d43a3f"
TRAIN = ("b3376513", "4023af38", "1558f0e0", "a61abb6e", "39ee1dd4", "0cfc84ff", "1b85ea27", "6a6893e3")
REVIEW = ("abf7af73", "58e36558", "0d983a80", "beda710e")
TRAIN_PATCHES = (("train-1", "a3b7e953"), ("train-2", "50a32378"))
REVIEW_PATCHES = (("review-1", "05d87ca0"), ("review-2", "b69a372e"))
STUDIES = tuple(mixed.Study(name, RULE, PROTOCOL, TRAIN, REVIEW, TRAIN_PATCHES, REVIEW_PATCHES, rng)
                for name, rng in (("r1", 0xD4146F83), ("r2", 0x2700A5A8)))
ARMS = previous.ARMS


def settings():
    for base, expected in ((0x72707431, TRAIN), (0x72707231, REVIEW),
                           (0x72707031, tuple(v for _, v in (*TRAIN_PATCHES, *REVIEW_PATCHES))),
                           (0x72706D31, tuple(f"{s.rng:08x}" for s in STUDIES))):
        require(tuple(experiment.trial_seeds(base, len(expected))) == expected, "changed seed derivation")
    require(set(dict(TRAIN_PATCHES).values()).isdisjoint(dict(REVIEW_PATCHES).values()), "schedule leakage")
    seeds = (*TRAIN, *REVIEW, *(v for _, v in (*TRAIN_PATCHES, *REVIEW_PATCHES)), *(f"{s.rng:08x}" for s in STUDIES))
    require(len(set(seeds)) == len(seeds), "seed collision")
    return {"rule": RULE, "replicas": [s.record() for s in STUDIES], "arms": list(ARMS),
            "budget": {k: 2*v for k, v in previous.COUNTS.items()}, "concurrent_replicas": 2,
            "native_window": [pilot.START, pilot.END], "stop": pilot.STOP,
            "periods": [list(p) for p in previous.rolling.PERIODS], "credit_age_ticks": previous.rolling.CREDIT_AGE,
            "selectors": {"v2": pilot.fitness.RULE, "renewal": previous.individual.RULE},
            "freshness_audit": "Before protocol: no seed literal matches in local sim/docs/benchmarks/artifacts JSON/JSONL/Markdown/Python, including ignored files; compressed/private history not claimed"}


def comparisons(a, b, study, *, review=False):
    return previous.comparison(a, b, study.review if review else study.development,
                              patches=dict(study.review_patches if review else study.development_patches))


def cohorts(root, generation, study):
    worlds = {}
    for key, _, seed, patch in mixed.conditions(study.review, dict(study.review_patches)):
        trial = experiment.read_json(root/"review"/f"g{generation}.{key}.json")
        score = pilot.validate_trial(trial, seed, trial["model_crc32"], patch=patch)["evaluation"]
        worlds[key] = mixed.validation.cohorts(trial["lineages"], trial["seeds"], score)
    return {"window": [pilot.START, pilot.END], "followup": pilot.STOP, "worlds": worlds}


def diagnostics(root, arms, study):
    result, finals = {}, {}
    for arm in ARMS:
        r = arms[arm]
        indexed = {c["id"]: c for c in r["search"]["candidates"]}
        finals[arm] = indexed[r["search"]["champions"][-1]]["worlds"]
        result[arm] = []
        for g, name in enumerate(r["search"]["champions"]):
            c, review = indexed[name], r["review"][g]["worlds"]
            result[arm].append({"generation": g, "champion": name, "model_crc32": c["model_crc32"],
                "training": comparisons(indexed["initial"]["worlds"], c["worlds"], study),
                "review": comparisons(r["review"][0]["worlds"], review, study, review=True),
                "training_worlds": previous.compact_worlds(c["worlds"]), "review_worlds": previous.compact_worlds(review),
                "training_diversity": mixed.diversity(c["worlds"]), "review_diversity": mixed.diversity(review),
                "review_cohorts": cohorts(root/"arms"/arm, g, study)})
    result["final_b_vs_a"] = {"training": comparisons(finals["v2"], finals["renewal"], study),
        "review": comparisons(arms["v2"]["review"][-1]["worlds"], arms["renewal"]["review"][-1]["worlds"], study, review=True)}
    return result


def frame_rows(arms, study):
    rows = []
    for i in range(len(mixed.conditions(study.review, dict(study.review_patches)))):
        row = []
        for arm in ARMS:
            for review in arms[arm]["review"]:
                f = review["frames"][i]
                row.append({**f, "id": f"{arm}.{f['id']}", "arm": arm,
                            "framebuffer": f"arms/{arm}/{f['framebuffer']}", "png": f"arms/{arm}/{f['png']}"})
        rows.append(row)
    return rows


def check_prefix(arms):
    a, b = (arms[k]["search"] for k in ARMS)
    for ca, cb in zip(a["candidates"][:4], b["candidates"][:4], strict=True):
        require(ca["id"] == cb["id"] and all(ca[k] == cb[k] for k in
                ("model_sha256", "model_crc32", "mutation", "parent", "worlds")), "common A/B mutation prefix differs")
    require(arms["v2"]["review"][0]["worlds"] == arms["renewal"]["review"][0]["worlds"], "original review differs")


def check_replica(root, result, study):
    require(result["rule"] == RULE and result["study"] == study.record() and set(result["arms"]) == set(ARMS),
            "wrong replica profile or missing arm")
    for arm in ARMS:
        r, sub = result["arms"][arm], root/"arms"/arm
        require(r["objective"] == arm, "changed selector")
        mixed.check_results(sub, r, study=study, objective=previous.Objective(arm))
        for c in r["search"]["candidates"]:
            names = [f"{c['id']}.tgm", *[f"{c['id']}.{k}.json" for k, *_ in
                     mixed.conditions(study.development, dict(study.development_patches))]]
            for name in names:
                require((sub/"search"/name).read_bytes() == (sub/"repeat"/name).read_bytes(), "native repeat differs")
    check_prefix(result["arms"])
    require(result["diagnostics"] == diagnostics(root, result["arms"], study), "replica analysis differs")
    require(result["gallery"]["rows"] == [[f["id"] for f in row] for row in frame_rows(result["arms"], study)],
            "wrong replica gallery")


def cross_replica(replicas):
    require(set(replicas) == {s.name for s in STUDIES}, "missing/extra replica")
    first = replicas[STUDIES[0].name]["arms"]["v2"]
    for r in replicas.values():
        for arm in ARMS:
            current = r["arms"][arm]
            require(first["search"]["candidates"][0]["worlds"] == current["search"]["candidates"][0]["worlds"] and
                    first["review"][0]["worlds"] == current["review"][0]["worlds"], "shared original control differs")
    # Report stream-level signs; shared review worlds do not become independent observations.
    return {view: {"final_b_vs_a_signs": {name: r["diagnostics"]["final_b_vs_a"]["review"][view]["overall"]["comparison"]
                                        for name, r in replicas.items()},
                   "final_vs_original_signs": {name: {arm: r["diagnostics"][arm][-1]["review"][view]["overall"]["comparison"]
                                                      for arm in ARMS} for name, r in replicas.items()}}
            for view in ARMS}


def collect_replica(root, study):
    start, arms, timings = time.monotonic(), {}, {arm: [] for arm in ARMS}
    for arm in ARMS:
        obj, reviews, sub = previous.Objective(arm), [], root/"arms"/arm
        print(f"Starting {study.name}/{arm}: captured search", flush=True)
        search = mixed.search(sub, sub/"search", timings[arm],
            lambda g, c: reviews.append(mixed.review_generation(sub, g, c, timings[arm], study=study, objective=obj)),
            study=study, objective=obj)
        print(f"Starting {study.name}/{arm}: capture-disabled repeat", flush=True)
        repeat = mixed.search(sub, sub/"repeat", timings[arm], study=study, objective=obj)
        require(search == repeat, "capture changed search")
        experiment.write_json(sub/"repeat.json", repeat)
        rows = [[r["frames"][i] for r in reviews] for i in range(len(mixed.conditions(study.review, dict(study.review_patches))))]
        arms[arm] = {"rule": RULE, "objective": arm, "search": search, "review": reviews,
                     "diagnostics": mixed.diagnostics(search, reviews, study=study),
                     "gallery": pilot.gallery.contact_sheet(sub, rows)}
        print(f"Finished {study.name}/{arm}: {search['champions']}", flush=True)
    result = {"rule": RULE, "study": study.record(), "arms": arms, "diagnostics": diagnostics(root, arms, study),
              "gallery": pilot.gallery.contact_sheet(root, frame_rows(arms, study))}
    check_replica(root, result, study)
    timing = {"wall_seconds": time.monotonic()-start, "arms": timings}
    previous.check_budget(timing)
    experiment.write_json(root/"results.json", result)
    experiment.write_json(root/"timings.json", timing)
    return result, timing


def check_results(root, result, timings):
    require(result["rule"] == RULE and result["settings"] == settings() and
            set(timings["replicas"]) == {s.name for s in STUDIES}, "wrong replication contract")
    for study in STUDIES:
        sub, r = root/"replicas"/study.name, result["replicas"][study.name]
        require(r == experiment.read_json(sub/"results.json") and
                timings["replicas"][study.name] == experiment.read_json(sub/"timings.json"), "replica files differ")
        check_replica(sub, r, study)
        previous.check_budget(timings["replicas"][study.name])
    require(result["cross_replica"] == cross_replica(result["replicas"]), "cross-replica analysis differs")


def verify(root):
    manifest = experiment.read_json(root/"manifest.json")
    require(manifest["rule"] == RULE and manifest["status"] == "complete", "wrong/incomplete replication bundle")
    for name in manifest["artifacts"]:
        pilot.gallery.artifact(root, manifest, name)
    require(experiment.digest(root/"input/previous-manifest.json") == BASELINE_SHA, "changed previous bundle")
    prior = experiment.read_json(root/"input/previous-manifest.json")
    for dest, src in manifest["copied"].items():
        require(experiment.digest(root/dest) == prior["artifacts"][src], "changed native input")
    require(experiment.read_json(root/"input/settings.json") == settings(), "changed frozen settings")
    result = experiment.read_json(root/"results.json")
    check_results(root, result, experiment.read_json(root/"timings.json"))
    print("Verified both independent replicas: 1408 ledgers, 128 repeated frames, four repeated searches", flush=True)
    return result


def collect(baseline, output):
    require(not output.exists() and output.is_relative_to(experiment.ROOT/"artifacts") and
            not output.is_relative_to(baseline), "choose fresh separate artifacts output")
    require(experiment.digest(baseline/"manifest.json") == BASELINE_SHA, "wrong preceding A/B")
    previous.verify(baseline)
    prior, sources = experiment.read_json(baseline/"manifest.json"), experiment.source_files()
    require(all(sources.get(n) == sha for n, sha in prior["sources"].items()
                if n.startswith("src/") and n.endswith((".c", ".h"))), "simulation core changed")
    output.mkdir(parents=True)
    experiment.snapshot_sources(output, sources)
    (output/"input").mkdir()
    copied = {"input/native-source.tar.gz": "input/native-source.tar.gz", "input/CMakeCache.txt": "input/CMakeCache.txt"}
    for study in STUDIES:
        for arm in ARMS:
            sub = output/"replicas"/study.name/"arms"/arm
            for name in ("bin", "input", "review"):
                (sub/name).mkdir(parents=True)
            copied[str((sub/"input/initial.tgm").relative_to(output))] = "arms/v2/input/initial.tgm"
            for name in pilot.BINARIES:
                copied[str((sub/"bin"/name).relative_to(output))] = f"arms/v2/bin/{name}"
    for dest, src in copied.items():
        shutil.copy2(baseline/src, output/dest)
        require(experiment.digest(output/dest) == prior["artifacts"][src], "input copy differs")
    shutil.copy2(baseline/"manifest.json", output/"input/previous-manifest.json")
    shutil.copy2(experiment.ROOT/PROTOCOL, output/"input/protocol.md")
    experiment.write_json(output/"input/settings.json", settings())
    frozen = {n: experiment.digest(output/n) for n in (*copied, "input/previous-manifest.json", "input/protocol.md", "input/settings.json")}
    experiment.write_json(output/"started.json", {"rule": RULE, "sources": sources, "frozen": frozen, "copied": copied})
    start = time.monotonic()
    try:
        # Independent serial searches, private directories and no mutable global settings.
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = {s.name: executor.submit(collect_replica, output/"replicas"/s.name, s) for s in STUDIES}
            completed = {s.name: futures[s.name].result() for s in STUDIES}
        replicas = {name: r for name, (r, _) in completed.items()}
        result = {"rule": RULE, "settings": settings(), "replicas": replicas, "cross_replica": cross_replica(replicas)}
        timing = {"wall_seconds": time.monotonic()-start, "replicas": {name: t for name, (_, t) in completed.items()}}
        require(experiment.source_files() == sources and all(experiment.digest(output/n) == sha for n, sha in frozen.items()),
                "source/input changed during collection")
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
    replicas = {}
    for study in STUDIES:
        r = result["replicas"][study.name]
        searches = {}
        for arm in ARMS:
            search = r["arms"][arm]["search"]
            searches[arm] = {**search, "candidates": [{k: v for k, v in c.items() if k != "worlds"} |
                {"worlds": previous.compact_worlds(c["worlds"]), "score_views": {
                    name: previous.Objective(name).aggregate(c["worlds"], study.development, patches=dict(study.development_patches))
                    for name in ARMS}} for c in search["candidates"]]}
        replicas[study.name] = {"study": study.record(), "searches": searches,
            "diagnostics": r["diagnostics"], "frames": frame_rows(r["arms"], study), "repeat_equal": True}
    return {"rule": RULE, "settings": settings(), "replicas": replicas, "cross_replica": result["cross_replica"],
            "manifest_sha256": experiment.digest(root/"manifest.json"), "timing": experiment.read_json(root/"timings.json")}


def export(root, prefix, check=False):
    result = verify(root)
    require(not prefix.is_relative_to(root), "cannot export into frozen evidence")
    summary, gallery, frames = (prefix.with_name(prefix.name+s) for s in ("-summary.json", "-gallery.md", "-frames"))
    images = {s.name: prefix.with_name(f"{prefix.name}-{s.name}.png") for s in STUDIES}
    expected = portable(root, result)
    lines = ["# Independent renewal-training replicas: all generations", "",
             "Each sheet: columns **A0, A1, A2, A3, B0, B1, B2, B3**; all images at day 192.",
             "A selects persistence-v2, B bounded renewal. Both replicas share the fixed review worlds,",
             "but use different mutation streams. Review never selects parents; all outcomes remain.", "",
             "| Row | Review schedule | World seed |", "|---:|---|---|"]
    for i, (_, label, seed, _) in enumerate(mixed.conditions(REVIEW, dict(REVIEW_PATCHES)), 1):
        lines.append(f"| {i} | {label} | `{seed}` |")
    copies = {}
    for study in STUDIES:
        lines += ["", f"## {study.name.upper()} — mutation seed `{study.rng:08x}`", "",
                  f"![All 64 {study.name} frames]({images[study.name].name})", "",
                  "| Frame | Model CRC | Living | World hash | Framebuffer CRC |", "|---|---|---:|---|---|"]
        for row in expected["replicas"][study.name]["frames"]:
            for f in row:
                name = f"{study.name}.{f['id']}.png"
                w = result["replicas"][study.name]["arms"][f["arm"]]["review"][f["generation"]]["worlds"][f["condition"]]
                lines.append(f"| [{study.name}.{f['id']}]({frames.name}/{name}) | `{f['model_crc32']}` | {w['final']['living']} | `{f['hash']}` | `{f['framebuffer_crc32']}` |")
                copies[frames/name] = root/"replicas"/study.name/f["png"]
        copies[images[study.name]] = root/"replicas"/study.name/"contact-sheet.png"
    lines += ["", "All 128 framebuffers independently repeat byte-for-byte and match native ledger endpoints.",
              "Images alone do not establish reproductive health or generalization.",
              "See the [report](renewal-replication.md) and [paired data](renewal-replication-summary.json).", "",
              f"Manifest SHA-256: `{expected['manifest_sha256']}`.", ""]
    content = "\n".join(lines)
    if not check:
        require(not any(p.exists() for p in (summary, gallery, frames, *images.values())), "export exists")
        frames.mkdir(parents=True)
        experiment.write_json(summary, expected)
        with gallery.open("x") as stream:
            stream.write(content)
        for dest, src in copies.items():
            shutil.copyfile(src, dest)
    require(experiment.read_json(summary) == expected and gallery.read_text() == content, "portable analysis differs")
    require(all(experiment.digest(dest) == experiment.digest(src) for dest, src in copies.items()), "portable frame differs")
    print("Portable replica summaries, two sheets and all 128 PNGs match verified evidence", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, default=experiment.ROOT/"artifacts/garden-renewal-training-v1")
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
