#!/usr/bin/env python3
"""Verify/export the mixed-condition pilot; optionally replay rejected extinction cases."""
import argparse
from collections import Counter
from pathlib import Path
import shutil
import statistics
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "sim"))
import garden_mixed_training as mixed

pilot, experiment = mixed.pilot, mixed.experiment


def compact_world(w):
    return {k: v for k, v in w.items() if k != "evaluation"} | {
        "key": w["evaluation"]["key"], "terminal": w["evaluation"]["terminal"]}


def compact_case(c):
    return {k: v for k, v in c.items() if k != "worlds"} | {
        "worlds": {key: compact_world(w) for key, w in c["worlds"].items()}}


def cohort_summary(root, generation, seeds):
    values = []
    for key, _, seed, patch in mixed.conditions(seeds):
        trial = experiment.read_json(root / "review" / f"{mixed.review_name(generation)}.{key}.json")
        score = pilot.validate_trial(trial, seed, trial["model_crc32"], patch=patch)["evaluation"]
        values.append(mixed.validation.cohorts(trial["lineages"], trial["seeds"], score))
    totals = {k: sum(c[k] for c in values) for k in ("credited_children", "available_ticks", "live_ticks",
              "lost_ticks", "other_descendant_ticks", "late_births_not_main_confirmable")}
    for k in ("confirmation_cohort", "credited_main_end_states", "purchase_cohort_followed_to_stop"):
        counter = Counter()
        for c in values:
            counter.update(c[k])
        totals[k] = dict(counter)
    return {"totals": totals, "conditions": {key: c for (key, *_), c in zip(mixed.conditions(seeds), values, strict=True)}}


def export(root, prefix):
    result = mixed.verify(root)
    study = mixed.study_for_rule(result["rule"])
    manifest, timing = (experiment.read_json(root / n) for n in ("manifest.json", "timings.json"))
    calls = [c["seconds"] for c in timing["calls"] if c["artifact"].startswith("search/")]
    summary = {"rule": study.rule, "role": "exploratory-training-not-promoted", "study": study.record(),
               "manifest_sha256": experiment.digest(root / "manifest.json"),
               "artifact_count": len(manifest["artifacts"]), "artifact_bytes": manifest["artifact_bytes"],
               "protocol_sha256": manifest["artifacts"]["input/protocol.md"],
               "development_seeds": list(study.development), "review_seeds": list(study.review),
               "patches": mixed.PATCHES, "main_window": [pilot.START, pilot.END], "stop": pilot.STOP,
               "search_rng": mixed.RNG, "mutations_per_offspring": mixed.MUTATIONS,
               "search": {**result["search"], "candidates": [compact_case(c) for c in result["search"]["candidates"]]},
               "review": [compact_case(r) | {"cohorts": cohort_summary(root, r["generation"], study.review)} for r in result["review"]],
               "diagnostics": result["diagnostics"], "gallery": result["gallery"], "repeat_equal": True,
               "timing": {"wall_seconds": timing["wall_seconds"], "development_trial_seconds": {
                   "total": sum(calls), "median": statistics.median(calls), "min": min(calls), "max": max(calls)}}}
    views = list(summary["review"])
    if study == mixed.COVERAGE:
        summary["narrow_review"] = compact_case(result["narrow_review"]) | {
            "cohorts": cohort_summary(root, "narrow", study.review)}
        summary["coverage_diagnostics"] = result["coverage_diagnostics"]
        summary["narrow_manifest_sha256"] = mixed.NARROW_SHA
        views.append(summary["narrow_review"])
    frame_count = sum(len(v["frames"]) for v in views)
    outputs = [prefix.with_name(prefix.name + s) for s in ("-summary.json", ".png", "-gallery.md", "-frames")]
    mixed.require(all(not p.exists() for p in outputs), "export target already exists")
    target_json, sheet, markdown, frames = outputs
    frames.mkdir(parents=True)
    shutil.copyfile(root / "contact-sheet.png", sheet)
    columns = "0 / 1 / 2 / 3 / narrow reference" if study == mixed.COVERAGE else "0 / 1 / 2 / 3"
    lines = [f"# {study.name.title()} training: generation gallery", "",
             "Fixed review worlds, never used for automated selection. Rows follow the declared",
             f"schedule/seed order; columns show **{columns}** at day **192**.",
             f"These are all {frame_count} required native captures, not a selected set of favorable worlds.",
             "All scored checkpoint hashes and independent byte-for-byte frame repeats match.", "",
             f"![All review conditions and saved controllers]({sheet.name})", "",
             "| Row | Schedule | World seed |", "|---:|---|---|"]
    for row, (_, schedule, seed, _) in enumerate(mixed.conditions(study.review), 1):
        lines.append(f"| {row} | {schedule} | `{seed}` |")
    lines += ["", "## Native frames and endpoint diagnostics", "",
              "Counts describe living species and founder families, not seed-bank extinctions.",
              "Fitness key: terminal tier, renewing-child live ticks, descendant live ticks,",
              "renewing parents, new establishments. Tick totals sum over plants, not CPU time.", "",
              "| Generation / condition | Model CRC | Living | Species / families | World key | World hash / framebuffer CRC |",
              "|---|---|---:|---:|---|---|"]
    for g in views:
        for f in g["frames"]:
            target = frames / f"{f['id']}.png"
            shutil.copyfile(root / f["png"], target)
            mixed.require(experiment.digest(target) == manifest["artifacts"][f["png"]], "exported frame differs")
            f["portable_png"] = f"{frames.name}/{target.name}"
            w = g["worlds"][f["condition"]]
            lines.append(f"| [{f['id']}]({f['portable_png']}) | `{f['model_crc32']}` | {w['final']['living']} | "
                         f"{len(w['terminal_species'])} / {len(w['terminal_families'])} | `{w['key']}` | "
                         f"`{f['hash']}` / `{f['framebuffer_crc32']}` |")
    lines += ["", f"[All candidate scores, paired diagnostics and lifetime attribution]({target_json.name}).", "",
              f"Frozen bundle manifest SHA-256: `{summary['manifest_sha256']}`.", ""]
    with markdown.open("x") as stream:
        stream.write("\n".join(lines))
    experiment.write_json(target_json, summary)
    print(f"Exported {target_json}, {markdown}, overview and {frame_count} native PNGs")


def check_extinctions(root, output):
    """Post-collection verification only; no new scored trials or candidate selection."""
    result = mixed.verify(root)
    study = mixed.study_for_rule(result["rule"])
    mixed.require(output.is_relative_to(experiment.ROOT / "artifacts") and not output.exists() and
                  not output.is_relative_to(root), "choose a fresh separate artifacts directory")
    output.mkdir(parents=True)
    cases = []
    for c in result["search"]["candidates"]:
        for key, _, seed, patch in mixed.conditions(study.development):
            if c["worlds"][key]["evaluation"]["key"][0] != -1:
                continue
            identity = f"{c['id']}.{key}"
            trial = experiment.read_json(root / "search" / f"{identity}.json")
            model = root / "search" / f"{c['id']}.tgm"
            raw, png = output / f"{identity}.rgb565", output / f"{identity}.png"
            replay, _ = pilot.run_json(pilot.replay_command(root, model, seed, pilot.STOP, raw, patch=patch),
                                       output / f"{identity}.json")
            pilot.check_replay(replay, trial, seed, c["model_crc32"], pilot.STOP, raw.read_bytes(), patch=patch)
            pilot.gallery.write_png(png, 240, 240, pilot.gallery.rgb565be_to_rgb888(raw.read_bytes()))
            cases.append({"case": identity, "model_crc32": c["model_crc32"], "model_sha256": c["model_sha256"],
                          "key": trial["key"], "final": trial["checkpoints"][-1],
                          "last_death_tick": max(p["death_tick"] for p in trial["lineages"]),
                          "framebuffer_crc32": replay["framebuffer_crc32"], "png": png.name})
    mixed.require(bool(cases), "no native extinction cases in this bundle")
    experiment.write_json(output / "results.json", {"role": "post-collection-rejected-case-verification",
        "source_manifest_sha256": experiment.digest(root / "manifest.json"), "cases": cases})
    artifacts = {p.name: experiment.digest(p) for p in output.iterdir() if p.is_file()}
    experiment.write_json(output / "manifest.json", {"status": "complete", "artifacts": artifacts,
                          "replayer_sha256": experiment.digest(root / "bin/garden-replay")})
    mixed.verify(root)
    print(f"Independently replayed {len(cases)} rejected extinction conditions: {output}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, default=experiment.ROOT / "artifacts/garden-mixed-training-v1")
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--export", type=Path)
    action.add_argument("--extinction-check", type=Path)
    args = parser.parse_args()
    if args.export:
        export(args.bundle.resolve(), args.export.resolve())
    elif args.extinction_check:
        check_extinctions(args.bundle.resolve(), args.extinction_check.resolve())
    else:
        mixed.verify(args.bundle.resolve())


if __name__ == "__main__":
    main()
