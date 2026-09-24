#!/usr/bin/env python3
"""Fixed frozen-model world/schedule cross; no training or model selection."""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
import shutil
import tempfile
import time

import garden_renewal_replication as previous

mixed, pilot, experiment, require = previous.mixed, previous.pilot, previous.experiment, previous.require
scoring = previous.previous
RULE = "garden-renewal-transfer-v1"
PROTOCOL = "benchmarks/garden-longevity/renewal-transfer-protocol.md"
BASELINE_SHA = "8cc60dbe89f9040457f4abd60e81b2c3f5379dac6987b5b3deb872dcc870a45f"


@dataclass(frozen=True)
class Model:
    name: str
    replica: str
    arm: str
    candidate: str
    crc: str

    @property
    def source(self):
        return f"replicas/{self.replica}/arms/{self.arm}"

    @property
    def generation(self):
        return 0 if self.name == "original" else 3


MODELS = (Model("original", "r1", "v2", "initial", "dc5e849d"),
          Model("r1-a", "r1", "v2", "g3-c2", "46fad3c2"),
          Model("r1-b", "r1", "renewal", "g2-c1", "7ce0ed84"),
          Model("r2-a", "r2", "v2", "g1-c2", "f51cb1d4"),
          Model("r2-b", "r2", "renewal", "g3-c3", "01b9d94a"))
CELLS = ("tt", "tr", "rt", "rr")
PAIRS = (("r1-b-vs-a", "r1-a", "r1-b"), ("r2-b-vs-a", "r2-a", "r2-b"),
         *((f"{m.name}-vs-original", "original", m.name) for m in MODELS[1:]))
BUDGET = {"new_trials": 120, "repeat_trials": 120, "new_frame_replays": 30,
          "repeat_frame_replays": 30, "native_processes": 300, "reused_trials": 120,
          "reused_frames": 10, "total_frames": 40, "training_calls": 0, "mutation_calls": 0}


def seeds(cell):
    require(cell in CELLS, "unknown cross cell")
    return previous.TRAIN if cell[0] == "t" else previous.REVIEW


def patches(cell):
    require(cell in CELLS, "unknown cross cell")
    return dict(previous.TRAIN_PATCHES if cell[1] == "t" else previous.REVIEW_PATCHES)


def conditions(cell):
    return mixed.conditions(seeds(cell), patches(cell))


def reused(cell):
    require(cell in CELLS, "unknown cross cell")
    return cell[0] == cell[1]


def identity(model, cell, key):
    return f"{model.name}.{cell}.{key}"


def ledger(model, cell, key, repeat=False):
    return f"ledgers/{model.name}/{cell}/{key}{'.repeat' if repeat else ''}.json"


def frame_plan():
    return [(model, cell, key, schedule, seed, patch) for cell in CELLS
            for key, schedule, seed, patch in mixed.conditions(seeds(cell)[:1], patches(cell)) for model in MODELS]


def settings():
    return {"rule": RULE, "models": [dict(m.__dict__) for m in MODELS], "budget": dict(BUDGET),
            "cells": {c: {"seeds": list(seeds(c)), "patches": patches(c), "reused": reused(c)} for c in CELLS},
            "native_window": [pilot.START, pilot.END], "stop": pilot.STOP,
            "periods": [list(p) for p in scoring.rolling.PERIODS], "credit_age_ticks": scoring.rolling.CREDIT_AGE,
            "frame_world_seeds": [previous.TRAIN[0], previous.REVIEW[0]], "concurrent_model_jobs": 2}


def validate_models(baseline):
    require(baseline["rule"] == previous.RULE and baseline["settings"] == previous.settings(), "changed input study")
    for model in MODELS:
        arm = baseline["replicas"][model.replica]["arms"][model.arm]
        require(arm["search"]["champions"][model.generation] == model.candidate, "model is not frozen final/original")
        candidate = next(c for c in arm["search"]["candidates"] if c["id"] == model.candidate)
        require(candidate["model_crc32"] == model.crc and
                arm["review"][model.generation]["champion"] == model.candidate, "frozen model identity differs")


def copies():
    result = {"input/replication-results.json": "results.json", "input/native-source.tar.gz": "input/native-source.tar.gz",
              "input/CMakeCache.txt": "input/CMakeCache.txt"}
    for name in ("garden-persistence-trial", "garden-replay"):
        result[f"bin/{name}"] = f"replicas/r1/arms/v2/bin/{name}"
    for model in MODELS:
        result[f"models/{model.name}.tgm"] = f"{model.source}/search/{model.candidate}.tgm"
        for cell in ("tt", "rr"):
            for key, *_ in conditions(cell):
                folder, name = ("search", model.candidate) if cell == "tt" else ("review", f"g{model.generation}")
                result[ledger(model, cell, key)] = f"{model.source}/{folder}/{name}.{key}.json"
    for model, cell, key, *_ in frame_plan():
        if cell == "rr":
            for suffix in ("rgb565", "png", "replay.json", "repeat.rgb565", "repeat.json"):
                result[f"frames/{identity(model, cell, key)}.{suffix}"] = (
                    f"{model.source}/review/g{model.generation}.{key}.{suffix}")
    return result


def events():
    trials = [{"kind": "trial", "model": m.name, "cell": c, "condition": k, "repeat": repeat}
              for m in MODELS for c in CELLS if not reused(c) for k, *_ in conditions(c) for repeat in (False, True)]
    frames = [{"kind": "frame", "model": m.name, "cell": c, "condition": k, "repeat": repeat}
              for m, c, k, *_ in frame_plan() if c != "rr" for repeat in (False, True)]
    return trials + frames


def native_command(root, event):
    model = next(m for m in MODELS if m.name == event["model"])
    cell, key, repeat = event["cell"], event["condition"], event["repeat"]
    _, _, seed, patch = next(item for item in conditions(cell) if item[0] == key)
    model_path = root/"models"/f"{model.name}.tgm"
    if event["kind"] == "trial":
        command = [root/"bin/garden-persistence-trial", model_path, "neural", "0x"+seed, "0x"+patch, pilot.START, pilot.END]
        target = ledger(model, cell, key, repeat)
    else:
        require(event["kind"] == "frame", "unknown native event")
        stem = f"frames/{identity(model, cell, key)}"
        command = pilot.replay_command(root, model_path, seed, pilot.STOP,
            root/(stem+(".repeat.rgb565" if repeat else ".rgb565")), patch=patch)
        target = stem+(".repeat.json" if repeat else ".replay.json")
    return [str(x) for x in command], target


def check_budget(timing):
    rows = timing["calls"]
    fields = ("kind", "model", "cell", "condition", "repeat")
    require(len(rows) == BUDGET["native_processes"] and
            Counter(tuple(r[k] for k in fields) for r in rows) == Counter(tuple(e[k] for k in fields) for e in events()),
            "wrong native event coverage/budget")
    for row in rows:
        command, target = native_command(Path(timing["command_root"]), row)
        require(row["command"] == command and row["artifact"] == target, "native command differs from protocol")


def checked_trial(trial, model, seed, patch):
    ordinary = pilot.validate_trial(trial, seed, model.crc, patch=patch)
    return scoring.Objective("renewal").annotate(trial, ordinary)


def check_repeat(root, model, cell, key):
    require((root/ledger(model, cell, key)).read_bytes() ==
            (root/ledger(model, cell, key, True)).read_bytes(), "native ledger repeat differs")


def checked_frame(root, model, cell, key, schedule, seed, patch):
    name = identity(model, cell, key)
    stem = root/"frames"/name
    trial = experiment.read_json(root/ledger(model, cell, key))
    replay = experiment.read_json(Path(str(stem)+".replay.json"))
    raw = Path(str(stem)+".rgb565").read_bytes()
    pilot.check_replay(replay, trial, seed, model.crc, pilot.STOP, raw, patch=patch)
    require(raw == Path(str(stem)+".repeat.rgb565").read_bytes() and
            replay == experiment.read_json(Path(str(stem)+".repeat.json")), "image repeat differs")
    with tempfile.TemporaryDirectory(prefix="garden-transfer-frame-") as temp:
        png = Path(temp)/"frame.png"
        pilot.gallery.write_png(png, 240, 240, pilot.gallery.rgb565be_to_rgb888(raw))
        require(png.read_bytes() == Path(str(stem)+".png").read_bytes(), "PNG/raw mismatch")
    return {"id": name, "model": model.name, "cell": cell, "condition": key, "schedule": schedule,
            "seed": seed, "patch_seed": patch, "tick": pilot.STOP, "model_crc32": model.crc,
            "hash": replay["hash"], "living": replay["living"], "framebuffer_crc32": replay["framebuffer_crc32"],
            "reused": cell == "rr", "framebuffer": f"frames/{name}.rgb565", "png": f"frames/{name}.png"}


def collect_model(root, model):
    calls = []
    for event in (e for e in events() if e["model"] == model.name):
        command, target = native_command(root, event)
        value, elapsed = pilot.run_json(command, root/target)
        calls.append({**event, "command": command, "artifact": target, "seconds": elapsed})
        cell, key = event["cell"], event["condition"]
        _, _, seed, patch = next(c for c in conditions(cell) if c[0] == key)
        if event["kind"] == "trial":
            checked_trial(value, model, seed, patch)
            if event["repeat"]:
                check_repeat(root, model, cell, key)
                print(f"{model.name}/{cell}/{key}: trial and repeat verified", flush=True)
        elif event["repeat"]:
            raw = (root/f"frames/{identity(model, cell, key)}.rgb565").read_bytes()
            pilot.gallery.write_png(root/f"frames/{identity(model, cell, key)}.png", 240, 240,
                                    pilot.gallery.rgb565be_to_rgb888(raw))
            checked_frame(root, model, cell, key, key.split(".")[0], seed, patch)
    print(f"Finished frozen model {model.name}", flush=True)
    return calls


def rational(value):
    return {"numerator": value.numerator, "denominator": value.denominator}


def contrasts(groups):
    require(set(groups) == set(CELLS), "incomplete cross")
    means = {}
    for cell, group in groups.items():
        require(group["pairs"], "empty cell")
        means[cell] = Fraction(group["candidate"]["key"][2] - group["control"]["key"][2], len(group["pairs"]))
    schedule_t, schedule_r = means["tr"]-means["tt"], means["rr"]-means["rt"]
    return {"units": "candidate-minus-control credit ticks per world/schedule condition",
            "terminal_prefixes_equal": all(g["candidate"]["key"][:2] == g["control"]["key"][:2] for g in groups.values()),
            "means": {c: rational(v) for c, v in means.items()},
            "schedule_shifts": {"training_worlds": rational(schedule_t), "review_worlds": rational(schedule_r)},
            "world_set_shifts": {"training_schedules": rational(means["rt"]-means["tt"]),
                                 "review_schedules": rational(means["rr"]-means["tr"])},
            "interaction": rational(schedule_r-schedule_t)}


def axis_diagnostics(comparisons):
    result = {}
    for view in scoring.ARMS:
        groups = {c: comparisons[c][view]["overall"] for c in CELLS}
        omitted = {}
        for seed in (*previous.TRAIN, *previous.REVIEW):
            omitted[seed] = contrasts({c: comparisons[c][view]["leave_one_world_seed_out"][seed]
                if seed in seeds(c) else groups[c] for c in CELLS})
        shifts = {}
        field = "minimum_delta" if view == "renewal" else "renewal_delta"
        for role, left, right in (("training", "tt", "tr"), ("review", "rt", "rr")):
            shifts[role] = {}
            for seed in seeds(left):
                values = {}
                for cell in (left, right):
                    pairs = [p for p in groups[cell]["pairs"] if p["condition"].endswith("."+seed)]
                    require(len(pairs) == 2, "incomplete per-world schedule pairing")
                    values[cell] = Fraction(sum(p[field] for p in pairs), 2)
                shifts[role][seed] = {"training_schedule_mean": rational(values[left]),
                    "review_schedule_mean": rational(values[right]), "shift": rational(values[right]-values[left])}
        result[view] = {"full": contrasts(groups), "leave_one_world_seed_out": omitted, "per_world_schedule_shifts": shifts}
    return result


def analyze(root):
    baseline = experiment.read_json(root/"input/replication-results.json")
    validate_models(baseline)
    models = {}
    for model in MODELS:
        require(pilot.model_crc(root/"models"/f"{model.name}.tgm") == model.crc, "changed model bytes")
        cells = {}
        for cell in CELLS:
            worlds, cohorts = {}, {}
            for key, _, seed, patch in conditions(cell):
                trial = experiment.read_json(root/ledger(model, cell, key))
                worlds[key] = checked_trial(trial, model, seed, patch)
                cohorts[key] = mixed.validation.cohorts(trial["lineages"], trial["seeds"], worlds[key]["evaluation"])
                if not reused(cell):
                    check_repeat(root, model, cell, key)
            if reused(cell):
                arm = baseline["replicas"][model.replica]["arms"][model.arm]
                expected = (next(c for c in arm["search"]["candidates"] if c["id"] == model.candidate)["worlds"]
                            if cell == "tt" else arm["review"][model.generation]["worlds"])
                require(worlds == expected, "reused diagonal differs from replication")
            cells[cell] = {"reused": reused(cell), "worlds": worlds,
                "views": {view: scoring.Objective(view).aggregate(worlds, seeds(cell), patches=patches(cell)) for view in scoring.ARMS},
                "diversity": mixed.diversity(worlds), "cohorts": {"window": [pilot.START, pilot.END], "followup": pilot.STOP, "worlds": cohorts}}
        models[model.name] = {"model_crc32": model.crc, "model_sha256": experiment.digest(root/"models"/f"{model.name}.tgm"), "cells": cells}
    comparisons, axes = {}, {}
    for name, control, candidate in PAIRS:
        comparisons[name] = {c: scoring.comparison(models[control]["cells"][c]["worlds"],
            models[candidate]["cells"][c]["worlds"], seeds(c), patches=patches(c)) for c in CELLS}
        axes[name] = axis_diagnostics(comparisons[name])
    frames = [checked_frame(root, *row) for row in frame_plan()]
    return {"rule": RULE, "settings": settings(), "models": models, "comparisons": comparisons, "axes": axes, "frames": frames}


def frame_rows(result):
    frames = result["frames"]
    require([f["id"] for f in frames] == [identity(m, c, k) for m, c, k, *_ in frame_plan()], "changed image panel/order")
    return [frames[i:i+len(MODELS)] for i in range(0, len(frames), len(MODELS))]


def check_sheet(root, result):
    rows = [[{**f, "framebuffer": str(root/f["framebuffer"])} for f in row] for row in frame_rows(result)]
    with tempfile.TemporaryDirectory(prefix="garden-transfer-sheet-") as temp:
        expected = pilot.gallery.contact_sheet(Path(temp), rows)
        require(expected == result["gallery"] and (Path(temp)/"contact-sheet.png").read_bytes() ==
                (root/"contact-sheet.png").read_bytes(), "contact sheet differs from frames")


def verify(root):
    manifest = experiment.read_json(root/"manifest.json")
    require(manifest["rule"] == RULE and manifest["status"] == "complete" and manifest["copied"] == copies(),
            "wrong/incomplete transfer bundle")
    for name in manifest["artifacts"]:
        pilot.gallery.artifact(root, manifest, name)
    require(experiment.digest(root/"input/replication-manifest.json") == BASELINE_SHA, "changed replication manifest")
    prior = experiment.read_json(root/"input/replication-manifest.json")
    for dest, src in copies().items():
        require(experiment.digest(root/dest) == prior["artifacts"][src], "changed frozen input/reuse")
    require(experiment.read_json(root/"input/settings.json") == settings(), "changed settings")
    check_budget(experiment.read_json(root/"timings.json"))
    saved = experiment.read_json(root/"results.json")
    result = analyze(root)
    require(result == {k: v for k, v in saved.items() if k != "gallery"}, "transfer reanalysis differs")
    check_sheet(root, saved)
    print("Verified 240 unique outcomes (120 reused), 120 full repeats and 40 repeated images; no training", flush=True)
    return saved


def collect(baseline, output):
    require(not output.exists() and output.is_relative_to(experiment.ROOT/"artifacts") and
            not output.is_relative_to(baseline), "choose fresh separate artifacts output")
    require(experiment.digest(baseline/"manifest.json") == BASELINE_SHA, "wrong replication input")
    previous.verify(baseline)
    prior, sources = experiment.read_json(baseline/"manifest.json"), experiment.source_files()
    require(all(sources.get(n) == sha for n, sha in prior["sources"].items()
                if n.startswith("src/") and n.endswith((".c", ".h"))), "simulation core changed")
    validate_models(experiment.read_json(baseline/"results.json"))
    output.mkdir(parents=True)
    experiment.snapshot_sources(output, sources)
    for directory in ("input", "bin", "models", "frames"):
        (output/directory).mkdir()
    for model in MODELS:
        for cell in CELLS:
            (output/"ledgers"/model.name/cell).mkdir(parents=True)
    for dest, src in copies().items():
        shutil.copy2(baseline/src, output/dest)
        require(experiment.digest(output/dest) == prior["artifacts"][src], "input copy differs")
    shutil.copy2(baseline/"manifest.json", output/"input/replication-manifest.json")
    shutil.copy2(experiment.ROOT/PROTOCOL, output/"input/protocol.md")
    experiment.write_json(output/"input/settings.json", settings())
    frozen = {n: experiment.digest(output/n) for n in (*copies(), "input/replication-manifest.json", "input/protocol.md", "input/settings.json")}
    experiment.write_json(output/"started.json", {"rule": RULE, "sources": sources, "frozen": frozen})
    start = time.monotonic()
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(collect_model, output, model) for model in MODELS]
            calls = [row for future in futures for row in future.result()]
        timing = {"command_root": str(output), "calls": calls, "wall_seconds": time.monotonic()-start}
        check_budget(timing)
        result = analyze(output)
        result["gallery"] = pilot.gallery.contact_sheet(output, frame_rows(result))
        check_sheet(output, result)
        require(experiment.source_files() == sources and all(experiment.digest(output/n) == sha for n, sha in frozen.items()),
                "source/input changed during collection")
        experiment.write_json(output/"results.json", result)
        timing["collection_and_analysis_seconds"] = time.monotonic()-start
        experiment.write_json(output/"timings.json", timing)
        artifacts = {str(p.relative_to(output)): experiment.digest(p) for p in output.rglob("*") if p.is_file()}
        experiment.write_json(output/"manifest.json", {"rule": RULE, "status": "complete", "sources": sources,
            "copied": copies(), "artifacts": artifacts, "artifact_bytes": sum((output/n).stat().st_size for n in artifacts)})
    except BaseException as error:
        experiment.write_json(output/"failure.json", {"error": str(error)})
        raise
    verify(output)


def portable(root, result):
    models = {}
    for name, model in result["models"].items():
        models[name] = {**model, "cells": {cell: {**values, "worlds": scoring.compact_worlds(values["worlds"])}
                                           for cell, values in model["cells"].items()}}
    return {**result, "models": models, "manifest_sha256": experiment.digest(root/"manifest.json"),
            "timing": experiment.read_json(root/"timings.json")}


def export(root, prefix, check=False):
    result = verify(root)
    require(not prefix.is_relative_to(root), "cannot export into frozen bundle")
    summary, gallery, frames, sheet = (prefix.with_name(prefix.name+s) for s in ("-summary.json", "-gallery.md", "-frames", ".png"))
    expected = portable(root, result)
    lines = ["# Frozen-model world/schedule transfer gallery", "",
             "Columns: **original, R1 A, R1 B, R2 A, R2 B**. All images at day 192.",
             "World seeds are fixed first-in-panel anchors, not outcome-selected examples.",
             "TT/TR/RT/RR label world-set then schedule-set (training/review).", "",
             f"![All 40 fixed frames]({sheet.name})", "",
             "| Row | Cell | World seed | Schedule | Capture |", "|---:|---|---|---|---|"]
    for i, row in enumerate(frame_rows(result), 1):
        f = row[0]
        lines.append(f"| {i} | {f['cell'].upper()} | `{f['seed']}` | {f['schedule']} / `{f['patch_seed']}` | {'Reused' if f['reused'] else 'New'} |")
    lines += ["", "| Frame | Model CRC | Living | World hash | Framebuffer CRC |", "|---|---|---:|---|---|"]
    for f in result["frames"]:
        lines.append(f"| [{f['id']}]({frames.name}/{f['id']}.png) | `{f['model_crc32']}` | {f['living']} | `{f['hash']}` | `{f['framebuffer_crc32']}` |")
    lines += ["", "All frames match native ledger endpoints and independent repeats. Ten RR captures",
              "and their original repeats are reused; the remaining 30 pairs were newly captured.",
              "Images do not prove reproductive health or isolate why a controller transfers poorly.",
              "See the [report](renewal-transfer.md) and [paired data](renewal-transfer-summary.json).", "",
              f"Manifest SHA-256: `{expected['manifest_sha256']}`.", ""]
    content = "\n".join(lines)
    image_copies = {sheet: root/"contact-sheet.png", **{frames/f"{f['id']}.png": root/f["png"] for f in result["frames"]}}
    if not check:
        require(not any(p.exists() for p in (summary, gallery, frames, sheet)), "export exists")
        frames.mkdir(parents=True)
        experiment.write_json(summary, expected)
        with gallery.open("x") as stream:
            stream.write(content)
        for dest, src in image_copies.items():
            shutil.copyfile(src, dest)
    require(experiment.read_json(summary) == expected and gallery.read_text() == content, "portable analysis differs")
    require(all(experiment.digest(a) == experiment.digest(b) for a, b in image_copies.items()), "portable image differs")
    print("Portable transfer results, contact sheet and all 40 PNGs match verified evidence", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, default=experiment.ROOT/"artifacts/garden-renewal-replication-v1")
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
