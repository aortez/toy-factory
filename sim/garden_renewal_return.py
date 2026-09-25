#!/usr/bin/env python3
"""Return frozen 16-world finalists to the old transfer cross; never train."""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
import shutil
import time

import garden_renewal_coverage as coverage
import garden_renewal_transfer as transfer

mixed, pilot, experiment, require = transfer.mixed, transfer.pilot, transfer.experiment, transfer.require
scoring = transfer.scoring
RULE = "garden-renewal-return-v1"
PROTOCOL = "benchmarks/garden-longevity/renewal-return-protocol.md"
INPUTS = {
    "transfer": "0422c3be1c55801ce921014f5314f6cecd655ea34345f140522a15de15b42279",
    "coverage": "c18b16c04a80f5d94973e8f06d7e1ffdafcd8df011f83ca133c3ed917023d780",
}
CELLS = transfer.CELLS
seeds, patches, conditions = transfer.seeds, transfer.patches, transfer.conditions
identity, ledger, checked_trial, check_repeat = transfer.identity, transfer.ledger, transfer.checked_trial, transfer.check_repeat


@dataclass(frozen=True)
class Model:
    name: str
    replica: str
    arm: str
    candidate: str
    crc: str
    control_name: str | None = None

    @property
    def new(self):
        return self.control_name is None

    @property
    def generation(self):
        return 0 if self.name == "original" else 3

    @property
    def source(self):
        return f"replicas/{self.replica}/arms/{self.arm}"


MODELS = (Model("original", "r1", "narrow", "initial", "dc5e849d", "original"),
          Model("r1-n", "r1", "narrow", "g2-c1", "7ce0ed84", "r1-b"),
          Model("r1-w", "r1", "wide", "g3-c3", "502e34a2"),
          Model("r2-n", "r2", "narrow", "g3-c3", "01b9d94a", "r2-b"),
          Model("r2-w", "r2", "wide", "g3-c1", "c9ea07fd"))
PAIRS = (("r1-w-vs-n", "r1-n", "r1-w"), ("r2-w-vs-n", "r2-n", "r2-w"),
         *((f"{m.name}-vs-original", "original", m.name) for m in MODELS[1:]))
BUDGET = {"new_trials": 96, "repeat_trials": 96, "new_frame_replays": 16,
          "repeat_frame_replays": 16, "native_processes": 224, "reused_trials": 144,
          "reused_frames": 24, "total_frames": 40, "training_calls": 0, "mutation_calls": 0}


def frame_plan():
    return [(m, c, k, label, seed, patch) for c in CELLS
            for k, label, seed, patch in mixed.conditions(seeds(c)[:1], patches(c)) for m in MODELS]


def settings():
    return {"rule": RULE, "inputs": dict(INPUTS), "models": [dict(m.__dict__) for m in MODELS],
            "budget": dict(BUDGET), "primary": "G3 wide versus G3 narrow in old RR, separately R1/R2",
            "cells": {c: {"seeds": list(seeds(c)), "patches": patches(c)} for c in CELLS},
            "native_window": [pilot.START, pilot.END], "stop": pilot.STOP,
            "periods": [list(p) for p in scoring.rolling.PERIODS], "credit_age_ticks": scoring.rolling.CREDIT_AGE,
            "concurrent_model_jobs": 2, "fresh_review_context": "saved coverage review; not new or pooled with old RR"}


def candidate(result, model):
    arm = result["replicas"][model.replica]["arms"][model.arm]
    require(arm["search"]["champions"][model.generation] == model.candidate and
            arm["review"][model.generation]["champion"] == model.candidate, "not the frozen original/final")
    value = next(c for c in arm["search"]["candidates"] if c["id"] == model.candidate)
    require(value["model_crc32"] == model.crc, "changed frozen model CRC")
    return value


def validate_models(old, wide):
    require(old["rule"] == transfer.RULE and old["settings"] == transfer.settings(), "wrong transfer contract")
    require(wide["rule"] == coverage.RULE and wide["settings"] == coverage.settings(), "wrong coverage contract")
    for model in MODELS:
        value = candidate(wide, model)
        if not model.new:
            prior = old["models"][model.control_name]
            require(prior["model_crc32"] == model.crc and prior["model_sha256"] == value["model_sha256"],
                    "narrow/original model differs between inputs")


def copies():
    result = {f"input/{name}-results.json": [name, "results.json"] for name in INPUTS}
    for name in ("native-source.tar.gz", "CMakeCache.txt"):
        result[f"input/{name}"] = ["transfer", f"input/{name}"]
    for name in ("garden-persistence-trial", "garden-replay"):
        result[f"bin/{name}"] = ["transfer", f"bin/{name}"]
    for model in MODELS:
        result[f"models/{model.name}.tgm"] = (["coverage", f"{model.source}/search/{model.candidate}.tgm"]
            if model.new else ["transfer", f"models/{model.control_name}.tgm"])
        if model.new:
            continue
        original = next(m for m in transfer.MODELS if m.name == model.control_name)
        for cell in CELLS:
            for key, *_ in conditions(cell):
                for repeat in ((False,) if transfer.reused(cell) else (False, True)):
                    result[ledger(model, cell, key, repeat)] = ["transfer", ledger(original, cell, key, repeat)]
        for m, cell, key, *_ in frame_plan():
            if m == model:
                for suffix in ("rgb565", "png", "replay.json", "repeat.rgb565", "repeat.json"):
                    result[f"frames/{identity(model, cell, key)}.{suffix}"] = [
                        "transfer", f"frames/{identity(original, cell, key)}.{suffix}"]
    return result


def events():
    return ([{"kind": "trial", "model": m.name, "cell": c, "condition": k, "repeat": repeat}
             for m in MODELS if m.new for c in CELLS for k, *_ in conditions(c) for repeat in (False, True)] +
            [{"kind": "frame", "model": m.name, "cell": c, "condition": k, "repeat": repeat}
             for m, c, k, *_ in frame_plan() if m.new for repeat in (False, True)])


def native_command(root, event):
    model = next(m for m in MODELS if m.name == event["model"])
    require(model.new, "cannot rerun a reused control")
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
    fields = ("kind", "model", "cell", "condition", "repeat")
    rows = timing["calls"]
    require(len(rows) == BUDGET["native_processes"] and
            Counter(tuple(r[k] for k in fields) for r in rows) == Counter(tuple(e[k] for k in fields) for e in events()),
            "wrong native event coverage/budget")
    for row in rows:
        command, target = native_command(Path(timing["command_root"]), row)
        require(row["command"] == command and row["artifact"] == target, "native command differs from protocol")


def checked_frame(root, model, cell, key, schedule, seed, patch):
    return {**transfer.checked_frame(root, model, cell, key, schedule, seed, patch), "reused": not model.new}


def collect_model(root, model):
    require(model.new, "cannot collect a reused model")
    calls = []
    for event in (e for e in events() if e["model"] == model.name):
        command, target = native_command(root, event)
        value, elapsed = pilot.run_json(command, root/target)
        calls.append({**event, "command": command, "artifact": target, "seconds": elapsed})
        cell, key = event["cell"], event["condition"]
        _, schedule, seed, patch = next(c for c in conditions(cell) if c[0] == key)
        if event["kind"] == "trial":
            checked_trial(value, model, seed, patch)
            if event["repeat"]:
                check_repeat(root, model, cell, key)
                print(f"{model.name}/{cell}/{key}: trial and repeat verified", flush=True)
        elif event["repeat"]:
            raw = (root/f"frames/{identity(model, cell, key)}.rgb565").read_bytes()
            pilot.gallery.write_png(root/f"frames/{identity(model, cell, key)}.png", 240, 240,
                                    pilot.gallery.rgb565be_to_rgb888(raw))
            checked_frame(root, model, cell, key, schedule, seed, patch)
    print(f"Finished frozen model {model.name}", flush=True)
    return calls


def fresh_context(wide):
    worlds, models = {}, {}
    for model in MODELS:
        arm = wide["replicas"][model.replica]["arms"][model.arm]
        worlds[model.name] = arm["review"][model.generation]["worlds"]
        models[model.name] = {"model_crc32": model.crc,
            "views": coverage.views(worlds[model.name], coverage.REVIEW, coverage.previous.REVIEW_PATCHES),
            "diversity": mixed.diversity(worlds[model.name])}
    return {"source": "coverage review, already inspected; 16 conditions/model, no new calls",
            "models": models, "comparisons": {name: coverage.comparisons(worlds[a], worlds[b]) for name, a, b in PAIRS}}


def analyze(root):
    old, wide = (experiment.read_json(root/f"input/{name}-results.json") for name in INPUTS)
    validate_models(old, wide)
    coverage_manifest = experiment.read_json(root/"input/coverage-manifest.json")
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
                if model.new or not transfer.reused(cell):
                    check_repeat(root, model, cell, key)
                if cell == "tt":
                    source = f"{model.source}/search/{model.candidate}.{key}.json"
                    require(experiment.digest(root/ledger(model, cell, key)) == coverage_manifest["artifacts"][source],
                            "training history differs from coverage")
            if not model.new:
                require(worlds == old["models"][model.control_name]["cells"][cell]["worlds"], "reused control differs")
            if cell == "tt":
                require(worlds == coverage.subset(candidate(wide, model)["worlds"], seeds(cell)), "training subset differs")
            cells[cell] = {"reused": not model.new, "worlds": worlds,
                "views": coverage.views(worlds, seeds(cell), tuple(patches(cell).items())),
                "diversity": mixed.diversity(worlds), "cohorts": {"window": [pilot.START, pilot.END], "followup": pilot.STOP, "worlds": cohorts}}
        models[model.name] = {"model_crc32": model.crc, "model_sha256": experiment.digest(root/"models"/f"{model.name}.tgm"), "cells": cells}
    comparisons = {name: {c: scoring.comparison(models[a]["cells"][c]["worlds"],
        models[b]["cells"][c]["worlds"], seeds(c), patches=patches(c)) for c in CELLS} for name, a, b in PAIRS}
    return {"rule": RULE, "settings": settings(), "models": models, "comparisons": comparisons,
            "axes": {name: transfer.axis_diagnostics(values) for name, values in comparisons.items()},
            "fresh_review_context": fresh_context(wide), "frames": [checked_frame(root, *row) for row in frame_plan()]}


def frame_rows(result):
    frames = result["frames"]
    require([f["id"] for f in frames] == [identity(m, c, k) for m, c, k, *_ in frame_plan()], "changed frame order/panel")
    return [frames[i:i+len(MODELS)] for i in range(0, len(frames), len(MODELS))]


def check_inputs(root):
    priors = {}
    for name, sha in INPUTS.items():
        require(experiment.digest(root/f"input/{name}-manifest.json") == sha, "changed pinned input manifest")
        priors[name] = experiment.read_json(root/f"input/{name}-manifest.json")
    for dest, (name, src) in copies().items():
        require(experiment.digest(root/dest) == priors[name]["artifacts"][src], "changed frozen/reused input")
    for replica in coverage.REPLICAS:
        for arm in coverage.ARMS:
            for name in ("garden-persistence-trial", "garden-replay"):
                require(experiment.digest(root/f"bin/{name}") ==
                        priors["coverage"]["artifacts"][f"replicas/{replica}/arms/{arm}/bin/{name}"], "native binary mismatch")
    for name in ("native-source.tar.gz", "CMakeCache.txt"):
        require(experiment.digest(root/f"input/{name}") == priors["coverage"]["artifacts"][f"input/{name}"],
                "native source/config mismatch")
    require(experiment.read_json(root/"input/settings.json") == settings(), "changed frozen settings")


def verify(root):
    manifest = experiment.read_json(root/"manifest.json")
    require(manifest["rule"] == RULE and manifest["status"] == "complete" and manifest["copied"] == copies(),
            "wrong/incomplete return bundle")
    require(set(manifest["artifacts"]) == {str(p.relative_to(root)) for p in root.rglob("*")
            if p.is_file() and p != root/"manifest.json"}, "extra/missing bundle artifacts")
    for name in manifest["artifacts"]:
        pilot.gallery.artifact(root, manifest, name)
    check_inputs(root)
    started = experiment.read_json(root/"started.json")
    require(started["rule"] == RULE and started["sources"] == manifest["sources"] and
            all(experiment.digest(root/n) == sha for n, sha in started["frozen"].items()) and
            experiment.digest(root/"input/protocol.md") == manifest["sources"][PROTOCOL], "changed source/input freeze")
    check_budget(experiment.read_json(root/"timings.json"))
    saved, result = experiment.read_json(root/"results.json"), analyze(root)
    require(result == {k: v for k, v in saved.items() if k != "gallery"}, "return reanalysis differs")
    coverage.check_sheet(root, frame_rows(saved), saved["gallery"])
    print("Verified 224 calls, 144 reused controls, 96 full trial repeats and all 40 repeated images", flush=True)
    return saved


def collect(inputs, output):
    require(set(inputs) == set(INPUTS) and not output.exists() and output.is_relative_to(experiment.ROOT/"artifacts") and
            not any(output.is_relative_to(p) for p in inputs.values()), "choose fresh separate artifacts output")
    for name, sha in INPUTS.items():
        require(experiment.digest(inputs[name]/"manifest.json") == sha, "wrong input bundle")
    transfer.verify(inputs["transfer"])
    coverage.verify(inputs["coverage"])
    sources = experiment.source_files()
    for root in inputs.values():
        prior = experiment.read_json(root/"manifest.json")
        require(all(sources.get(n) == sha for n, sha in prior["sources"].items()
                    if n.startswith("src/") and n.endswith((".c", ".h"))), "simulation core changed")
    output.mkdir(parents=True)
    experiment.snapshot_sources(output, sources)
    for dest, (name, src) in copies().items():
        (output/dest).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(inputs[name]/src, output/dest)
    for name, root in inputs.items():
        shutil.copy2(root/"manifest.json", output/f"input/{name}-manifest.json")
    shutil.copy2(experiment.ROOT/PROTOCOL, output/"input/protocol.md")
    experiment.write_json(output/"input/settings.json", settings())
    check_inputs(output)
    validate_models(*(experiment.read_json(output/f"input/{name}-results.json") for name in INPUTS))
    for model in MODELS:
        for cell in CELLS:
            (output/"ledgers"/model.name/cell).mkdir(parents=True, exist_ok=True)
    frozen = {str(p.relative_to(output)): experiment.digest(p) for p in output.rglob("*") if p.is_file()}
    experiment.write_json(output/"started.json", {"rule": RULE, "sources": sources, "frozen": frozen})
    start = time.monotonic()
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(collect_model, output, m) for m in MODELS if m.new]
            calls = [row for future in futures for row in future.result()]
        timing = {"command_root": str(output), "calls": calls, "wall_seconds": time.monotonic()-start}
        check_budget(timing)
        result = analyze(output)
        result["gallery"] = pilot.gallery.contact_sheet(output, frame_rows(result))
        coverage.check_sheet(output, frame_rows(result), result["gallery"])
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


def export(root, prefix, check=False):
    result = verify(root)
    require(not prefix.is_relative_to(root), "cannot export into frozen bundle")
    summary, gallery, frames, sheet = (prefix.with_name(prefix.name+s) for s in ("-summary.json", "-gallery.md", "-frames", ".png"))
    expected = transfer.portable(root, result)
    lines = ["# Frozen wide finalists: return to the old cross", "",
             "Columns: **original, R1 N3, R1 W3, R2 N3, R2 W3**. All images at day 192.",
             "N/W trained on eight/sixteen worlds; no training occurs in this check.",
             "Original/N columns reuse 24 captures and repeats; W columns add 16 repeated captures.",
             "Rows use first-in-panel worlds fixed before outcomes, not selected successes.",
             "TT/TR/RT/RR label world-set then schedule-set (training/review).", "",
             f"![All 40 fixed frames]({sheet.name})", "",
             "| Row | Cell | World seed | Schedule |", "|---:|---|---|---|"]
    for i, row in enumerate(frame_rows(result), 1):
        f = row[0]
        lines.append(f"| {i} | {f['cell'].upper()} | `{f['seed']}` | {f['schedule']} / `{f['patch_seed']}` |")
    lines += ["", "| Frame | Capture | Model CRC | Living | World hash | Framebuffer CRC |", "|---|---|---|---:|---|---|"]
    for f in result["frames"]:
        lines.append(f"| [{f['id']}]({frames.name}/{f['id']}.png) | {'Reused' if f['reused'] else 'New'} | `{f['model_crc32']}` | {f['living']} | `{f['hash']}` | `{f['framebuffer_crc32']}` |")
    lines += ["", "All images agree with native ledger endpoints, independent repeats and PNG conversion.",
              "Images alone do not prove reproductive health, coexistence or generalization.",
              "See the [report](renewal-return.md) and [paired data](renewal-return-summary.json).", "",
              f"Manifest SHA-256: `{expected['manifest_sha256']}`.", ""]
    content = "\n".join(lines)
    images = {sheet: root/"contact-sheet.png", **{frames/f"{f['id']}.png": root/f["png"] for f in result["frames"]}}
    if not check:
        require(not any(p.exists() for p in (summary, gallery, frames, sheet)), "export exists")
        frames.mkdir(parents=True)
        experiment.write_json(summary, expected)
        with gallery.open("x") as stream:
            stream.write(content)
        for dest, src in images.items():
            shutil.copyfile(src, dest)
    require(experiment.read_json(summary) == expected and gallery.read_text() == content, "portable analysis differs")
    require(all(experiment.digest(a) == experiment.digest(b) for a, b in images.items()), "portable image differs")
    print("Portable return results, contact sheet and all 40 PNGs match verified evidence", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in INPUTS:
        parser.add_argument(f"--{name}", type=Path, default=experiment.ROOT/f"artifacts/garden-renewal-{name}-v1")
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
        collect({n: getattr(args, n).resolve() for n in INPUTS}, args.output.resolve())


if __name__ == "__main__":
    main()
