#!/usr/bin/env python3
"""Verify a frozen persistence pilot and export its portable results and native gallery."""
import argparse
from pathlib import Path
import shutil
import statistics
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "sim"))
import garden_training_pilot as pilot


def compact_world(world):
    score = world["evaluation"]
    return {k: v for k, v in world.items() if k != "evaluation"} | {
        "key": score["key"], "components": score["components"], "terminal": score["terminal"],
        "pending_seed_followup": score["pending_seed_followup"]}


def compact_case(case):
    return {k: v for k, v in case.items() if k != "worlds"} | {
        "worlds": {seed: compact_world(w) for seed, w in case["worlds"].items()}}


def export(root, prefix):
    pilot.verify(root)
    read, digest = pilot.experiment.read_json, pilot.experiment.digest
    result, manifest = read(root / "results.json"), read(root / "manifest.json")
    timings = read(root / "timings.json")
    values = [c["seconds"] for c in timings["calls"] if c["artifact"].startswith("search/")]
    summary = {"rule": pilot.RULE, "role": "bounded-learning-signal-pilot-not-promoted",
               "manifest_sha256": digest(root / "manifest.json"), "artifact_count": len(manifest["artifacts"]),
               "artifact_bytes": manifest["artifact_bytes"], "protocol_sha256": manifest["protocol_sha256"],
               "source_head": manifest["head"], "source_dirty": True, "preflight": result["preflight"],
               "development": list(pilot.DEVELOPMENT), "review_seeds": list(pilot.REVIEW),
               "main_window": [pilot.START, pilot.END], "followup_deadline": pilot.STOP,
               "search": {**result["search"], "candidates": [compact_case(c) for c in result["search"]["candidates"]]},
               "review": {**result["review"], "generations": [compact_case(g) for g in result["review"]["generations"]]},
               "repeat_equal": result["repeat_equal"], "timing": {"bundle_wall_seconds": timings["wall_seconds"],
                    "development_trial_seconds": {"total": sum(values), "minimum": min(values),
                                                   "median": statistics.median(values), "maximum": max(values)}}}
    outputs = [prefix.with_name(prefix.name + suffix) for suffix in ("-summary.json", ".png", "-gallery.md", "-frames")]
    pilot.require(all(not p.exists() for p in outputs), "export target already exists")
    json_file, picture, markdown, frames = outputs
    frames.mkdir(parents=True)
    shutil.copyfile(root / "contact-sheet.png", picture)
    lines = ["# Persistence pilot: generation review", "",
             "Two review seeds, never used for automated selection. Generation 0 is the unchanged",
             "control; generations 1 and 2 use the same winning model. Their duplicate images are",
             "intentional: every completed generation is retained.", "",
             "Columns: tick **480** (early daylight), **2880** (first dawn), **737280** (day 192).",
             "All images use native 240×240 shared-renderer output. Each state hash matches the",
             "scored simulation; a separate reset/process reproduces every frame byte-for-byte.", "",
             f"![All generations and review worlds]({picture.name})", "",
             "| Row | Generation | World seed | Model CRC | Final living | Species / founder families | World fitness key |",
             "|---:|---:|---|---|---:|---:|---|"]
    for index, row in enumerate(summary["review"]["frames"], 1):
        f = row[0]
        w = summary["review"]["generations"][f["generation"]]["worlds"][f["seed"]]
        lines.append(f"| {index} | {f['generation']} | `{f['seed']}` | `{f['model_crc32']}` | "
                     f"{w['final']['living']} | {len(w['terminal_species'])} / {len(w['terminal_families'])} | `{w['key']}` |")
    lines += ["", "World key: terminal tier, recent renewing-child live ticks, all-descendant live",
              "ticks, renewing parents, new establishments. Tick totals sum over plants; they are",
              "not frame times. Established descendants are present at every recorded endpoint.", "",
              "## Individual native frames", "",
              "| Frame (generation / seed / tick) | World hash | Framebuffer CRC32 |",
              "|---|---|---|"]
    for row in summary["review"]["frames"]:
        for f in row:
            target = frames / f"{f['id']}.png"
            shutil.copyfile(root / f["png"], target)
            f["portable_png"] = f"{frames.name}/{target.name}"
            lines.append(f"| [{f['id']}]({f['portable_png']}) | `{f['hash']}` | `{f['framebuffer_crc32']}` |")
    lines += ["", f"[Complete portable scores and model identities]({json_file.name}).", "",
              f"Bundle manifest SHA-256: `{summary['manifest_sha256']}`.", ""]
    with markdown.open("x") as stream:
        stream.write("\n".join(lines))
    pilot.experiment.write_json(json_file, summary)
    print(f"Exported {json_file}, {markdown}, overview and 18 native PNGs")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, default=pilot.experiment.ROOT / "artifacts/garden-training-pilot-v1")
    parser.add_argument("--export", type=Path, help="New output prefix, for example benchmarks/garden-longevity/training-pilot")
    args = parser.parse_args()
    if args.export:
        export(args.bundle.resolve(), args.export.resolve())
    else:
        pilot.verify(args.bundle.resolve())


if __name__ == "__main__":
    main()
