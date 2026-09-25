#!/usr/bin/env python3
"""Recheck the frozen paired panel and export scores, cohort attribution and selected pictures."""
import argparse
from collections import Counter
from pathlib import Path
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "sim"))
import garden_pilot_validation as validation


def compact(case):
    score = case["evaluation"]
    return {k: v for k, v in case.items() if k != "evaluation"} | {
        "key": score["key"], "terminal": score["terminal"]}


def totals(cases):
    result = {}
    for side in validation.MODELS:
        worlds = [c for c in cases if c["side"] == side]
        cohorts = [c["cohorts"] for c in worlds]
        counts = {}
        for name in ("confirmation_cohort", "credited_main_end_states", "purchase_cohort_followed_to_stop"):
            counter = Counter()
            for c in cohorts:
                counter.update(c[name])
            counts[name] = dict(counter)
        result[side] = {**counts, **{k: sum(c[k] for c in cohorts) for k in (
            "credited_children", "available_ticks", "live_ticks", "lost_ticks", "other_descendant_ticks")},
            "confirmation_bin_ticks": [sum(c["confirmation_bins"][i]["live_ticks"] for c in cohorts) for i in range(4)],
            "terminal_species_count_histogram": dict(Counter(str(len(c["terminal_species"])) for c in worlds)),
            "terminal_family_count_histogram": dict(Counter(str(len(c["terminal_families"])) for c in worlds))}
    return result


def export(root, prefix):
    result = validation.verify(root)
    m = validation.experiment.read_json(root / "manifest.json")
    summary = {"rule": validation.RULE, "role": "paired-follow-up-not-new-training-or-promotion",
               "manifest_sha256": validation.experiment.digest(root / "manifest.json"),
               "pilot_manifest_sha256": validation.BASELINE_SHA,
               "artifact_count": len(m["artifacts"]), "artifact_bytes": m["artifact_bytes"],
               "timings": validation.experiment.read_json(root / "timings.json"),
               "panel": result["panel"], "totals": totals(result["cases"]),
               "cases": [compact(c) for c in result["cases"]],
               "historical_review": [compact(c) for c in result["historical_review"]], "gallery": result["gallery"]}
    outputs = [prefix.with_name(prefix.name + s) for s in ("-summary.json", ".png", "-gallery.md", "-frames")]
    validation.require(all(not p.exists() for p in outputs), "export target already exists")
    data, overview, markdown, frames = outputs
    frames.mkdir(parents=True)
    shutil.copyfile(root / "contact-sheet.png", overview)
    lines = ["# Frozen-controller panel: selected comparisons", "",
             "**Left: original controller `dc5e849d`. Right: pilot winner `fa0c2cd8`.**",
             "All images are native 240×240 captures at day 192 (tick 737280).",
             "Rows are the largest renewal-tick gain/loss within each schedule, chosen by",
             "the frozen protocol. These are outcome-selected examples, not representative samples.", "",
             f"![Original versus winner]({overview.name})", "",
             "| Row | Selection | Patch schedule | World seed | Renewal ticks, original → winner |",
             "|---:|---|---|---|---:|"]
    for index, (pair, row) in enumerate(zip(summary["panel"]["selected"], summary["gallery"]["frames"], strict=True), 1):
        lines.append(f"| {index} | {pair['label']} | {pair['schedule']} | `{pair['seed']}` | "
                     f"{row[0]['key'][1]:,} → {row[1]['key'][1]:,} |")
    lines += ["", "## Native frames and identities", "",
              "| Frame | World hash | Framebuffer CRC32 |", "|---|---|---|"]
    for row in summary["gallery"]["frames"]:
        for f in row:
            target = frames / f"{f['id']}.png"
            shutil.copyfile(root / f["png"], target)
            f["portable_png"] = f"{frames.name}/{target.name}"
            lines.append(f"| [{f['id']}]({f['portable_png']}) | `{f['hash']}` | `{f['framebuffer_crc32']}` |")
    lines += ["", "All scored endpoints were checked against independent replays; these eight frames",
              "also reproduced pixel-for-pixel on separate resets. Pictures did not affect scores.", "",
              f"[All paired scores, cohorts and diversity counts]({data.name}).", "",
              f"Bundle manifest SHA-256: `{summary['manifest_sha256']}`.", ""]
    with markdown.open("x") as stream:
        stream.write("\n".join(lines))
    validation.experiment.write_json(data, summary)
    print(f"Exported {data}, gallery and eight native images", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, default=validation.experiment.ROOT / "artifacts/garden-pilot-validation-v1")
    parser.add_argument("--export", type=Path, help="Fresh path prefix for portable outputs")
    args = parser.parse_args()
    if args.export:
        export(args.bundle.resolve(), args.export.resolve())
    else:
        validation.verify(args.bundle.resolve())


if __name__ == "__main__":
    main()
