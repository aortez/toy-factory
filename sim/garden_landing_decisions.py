#!/usr/bin/env python3
"""Frozen same-state proposal diagnostics; alternatives never advance a world."""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
import json
from pathlib import Path
import shutil
import sys
import tempfile
import time

import garden_landing_signals as signals
from garden_landing_reference import decode, explain
from garden_experiments import digest, source_files, snapshot_sources, write_json
from garden_gallery import artifact
from garden_resources import require

ROOT = Path(__file__).resolve().parents[1]
RULE = "garden-landing-decisions-v1"
PROTOCOL = "benchmarks/garden-seasons/landing-decisions-protocol.md"
INPUTS = signals.INPUTS
training = signals.training
PROBES = [
    {"id": name, "fields": fields, "values": list(values)}
    for name, fields, values in (
        ("live", 0, (0, 0, 0, 0)),
        ("water-light-only", 3, (128, 128, 0, 0)),
        ("occupancy-only", 12, (0, 0, 128, 128)),
        ("neutral", 15, (128, 128, 128, 128)),
        ("occupied", 3, (0, 0, 0, 0)),
        ("open", 3, (255, 0, 0, 0)),
        ("low-resources", 12, (0, 0, 0, 0)),
        ("high-resources", 12, (0, 0, 255, 255)),
        ("fixed-occupied", 15, (0, 0, 128, 128)),
        ("fixed-open", 15, (255, 0, 128, 128)),
        ("water-mid", 4, (0, 0, 128, 0)),
        ("water-low", 4, (0, 0, 0, 0)),
        ("water-high", 4, (0, 0, 255, 0)),
        ("light-mid", 8, (0, 0, 0, 128)),
        ("light-low", 8, (0, 0, 0, 0)),
        ("light-high", 8, (0, 0, 0, 255)),
    )]
METRICS = ("samples", "decision_changed", "proposal_changed", "action_changed", "priority_changed",
           "memory_changed", "both_extend", "order_changed", "first_available_changed",
           "hidden_sum_changed", "hidden_changed", "logits_changed", "hidden_l1",
           "low_clipped_units", "high_clipped_units")
PHASES = ("all", "early", "middle", "late")
ROLES = ("root", "stem")
FIELDS = ("space_free", "dead_only", "water_now", "light_now")


def counters():
    return {phase: {role: {p["id"]: dict.fromkeys(METRICS, 0) for p in PROBES} for role in ROLES}
            for phase in PHASES}


def add_counts(target, other):
    for phase in PHASES:
        for role in ROLES:
            for probe in PROBES:
                for metric in METRICS:
                    target[phase][role][probe["id"]][metric] += other[phase][role][probe["id"]][metric]


def vector(values, length, low, high):
    require(isinstance(values, list) and len(values) == length and
            all(type(v) is int and low <= v <= high for v in values), "invalid trace vector")


def inputs(row, probe):
    """Independent current-mode encoding; preserve legacy inputs and validity."""
    sources = []
    for source, values in enumerate(row["packet"]):
        active = bool(row["valid"] & (1 << source))
        sources.append([(probe["values"][f] if probe["fields"] & (1 << f) else values[f]) - 128
                        if active and f < 4 else 0 for f in range(8)])
    return {**row, "landing_common": sources[0] + [0],
            "landing_candidates": sources[1:]}


def metrics(row, original, altered):
    a, b = original["decision"], altered["decision"]
    both = a["action"] == b["action"] == 1

    def first(decision):
        return next((i for i in decision["order"][:decision["count"]] if row["flags"][i] & 2), None)

    return {
        "samples": 1, "decision_changed": int(a != b),
        "proposal_changed": int(any(a[k] != b[k] for k in ("action", "priority", "count", "order"))),
        "action_changed": int(a["action"] != b["action"]),
        "priority_changed": int(a["priority"] != b["priority"]),
        "memory_changed": int(a["memory"] != b["memory"]),
        "both_extend": int(both), "order_changed": int(both and a["order"] != b["order"]),
        "first_available_changed": int(both and first(a) != first(b)),
        "hidden_sum_changed": int(original["hidden_sum"] != altered["hidden_sum"]),
        "hidden_changed": int(original["hidden"] != altered["hidden"]),
        "logits_changed": int(original["logits"] != altered["logits"]),
        "hidden_l1": sum(abs(x - y) for x, y in zip(original["hidden"], altered["hidden"], strict=True)),
        # Output-at-bound counts include exact values and quantization to zero;
        # they do not count only values changed by the clipping operation.
        "low_clipped_units": altered["hidden"].count(0),
        "high_clipped_units": altered["hidden"].count(127),
    }


def histogram_stats(histogram):
    vector(histogram, 256, 0, 2**32 - 1)
    total = sum(histogram)
    if not total:
        return {"count": 0, "minimum": None, "maximum": None, "median": None, "sum": 0}
    present = [i for i, n in enumerate(histogram) if n]
    cumulative = 0
    median = None
    for i, n in enumerate(histogram):
        cumulative += n
        if cumulative >= (total + 1) // 2:
            median = i
            break
    return {"count": total, "minimum": present[0], "maximum": present[-1], "median": median,
            "sum": sum(i * n for i, n in enumerate(histogram))}


def analyze_trace(rows, model_bytes, result):
    require(len(rows) >= 2, "incomplete trace")
    header, footer = rows[0], rows[-1]
    require(header == {"kind": "landing-decisions-header", "version": 1,
            "sampling": "first-query-per-role-per-day", "day_ticks": training.DAY,
            "model": model_bytes.hex(), "probes": PROBES}, "wrong trace identity/protocol")
    require(footer["kind"] == "complete" and footer["tick"] == result["tick"] and
            footer["run_hash"] == result["run_hash"], "incomplete/mismatched trace")
    model = decode(model_bytes)
    require(model["mode"] == 1 and model["flags"] == 0, "unsupported trace controller")
    daily = footer["daily_queries"]
    require(len(daily) == 256 and len(footer["histograms"]) == 4, "invalid trace census")
    for counts in daily:
        vector(counts, 2, 0, 2**32 - 1)
    require(all(not any(q) for q in daily[(result["tick"] + training.DAY - 1) // training.DAY:]),
            "queries beyond replay horizon")
    histograms = {name: histogram_stats(h) for name, h in zip(FIELDS, footer["histograms"], strict=True)}
    require(all(h["count"] == footer["common_valid"] for h in histograms.values()) and
            footer["common_valid"] == sum(q[1] for q in daily), "sensor/query census mismatch")
    counts, seen = counters(), set()
    previous = (0, -1)
    for row in rows[1:-1]:
        require(row["kind"] == "sample" and type(row["tick"]) is int and
                1 <= row["tick"] <= result["tick"] and row["tick"] % 15 == 0 and
                row["role"] in (0, 1), "invalid sampled query")
        day, role = (row["tick"] - 1) // training.DAY, row["role"]
        require((day, role) not in seen and (row["tick"], role) > previous, "duplicate/unordered sample")
        seen.add((day, role))
        previous = row["tick"], role
        require(row["count"] == (3 if role == 0 else 5) and len(row["packet"]) == 6 and
                len(row["candidates"]) == row["count"] and 0 <= row["warmup"] <= 256, "invalid tensor shape")
        vector(row["flags"], row["count"], 0, 15)
        vector(row["common"], 32, -128, 127)
        vector(row["memory"], 8, -128, 127)
        for c in row["candidates"]:
            vector(c, 9, -128, 127)
        expected_valid = 0 if role == 0 else 1 | sum(1 << (i + 1) for i, f in enumerate(row["flags"]) if f & 1)
        require(row["valid"] == expected_valid, "wrong body/source gating")
        for s, packet in enumerate(row["packet"]):
            vector(packet, 8, 0, 255)
            require(bool(row["valid"] & (1 << s)) or packet == [0] * 8, "unmasked absent source")
        require(len(row["probes"]) == len(PROBES), "missing counterfactual")
        original = explain(inputs(row, PROBES[0]), model)
        require(original["decision"] == row["live"] == row["probes"][0], "live reference mismatch")
        phase = "early" if day < 32 else "middle" if day < 158 else "late"
        for probe, actual in zip(PROBES, row["probes"], strict=True):
            altered = explain(inputs(row, probe), model) if probe["id"] != "live" else original
            require(altered["decision"] == actual, "native/reference decision mismatch: " + probe["id"])
            if role == 0:
                require(altered == original, "root intervention escaped masking")
            values = metrics(row, original, altered)
            for period in ("all", phase):
                target = counts[period][ROLES[role]][probe["id"]]
                for metric in METRICS:
                    target[metric] += values[metric]
    expected = {(d, r) for d, q in enumerate(daily) for r, n in enumerate(q) if n}
    require(seen == expected and len(seen) == footer["samples"], "sampling coverage mismatch")
    return {"queries": {role: sum(q[r] for q in daily) for r, role in enumerate(ROLES)},
            "samples": {role: sum(r == i for _, r in seen) for i, role in enumerate(ROLES)},
            "histograms": histograms, "counts": counts}


def capture_world(task):
    binary, root, model, case = task
    identity = model["id"] + "--" + case["id"]
    path = "traces/" + identity + ".jsonl"
    result = training.native(binary, root, "trace-replay", model["model"], case["scenario"], "0x" + case["seed"],
                             "--ticks", training.STOP, "--climate", case["climate"], "--ledger", "--trace", path)
    rows = [json.loads(line) for line in (root / path).read_text().splitlines()]
    analysis = analyze_trace(rows, (root / model["model"]).read_bytes(), result)
    return identity, {"controller": model["id"], "condition": case["id"], "trace": path,
                      "trace_sha256": digest(root / path), "result": result, "analysis": analysis}


def summarize(worlds, models):
    result = {}
    for model in models:
        groups = {}
        for name, conditions in signals.previous.slices().items():
            selected = [worlds[model["id"] + "--" + case] for case in conditions]
            counts = counters()
            for world in selected:
                add_counts(counts, world["analysis"]["counts"])
            groups[name] = {"worlds": len(selected), "counts": counts,
                           "queries": {role: sum(w["analysis"]["queries"][role] for w in selected) for role in ROLES},
                           "samples": {role: sum(w["analysis"]["samples"][role] for w in selected) for role in ROLES}}
        result[model["id"]] = groups
    return result


def run_panel(binary, inputs_root, root, jobs):
    require(1 <= jobs <= 8 and not root.exists(), "fresh output/jobs 1..8 required")
    models, control = signals.prepare_models(binary, inputs_root, root)
    (root / "traces").mkdir()
    tasks = [(binary, root, m, c) for m in models for c in signals.previous.conditions()]
    worlds = {}
    with ProcessPoolExecutor(max_workers=jobs) as pool:
        for identity, world in pool.map(capture_world, tasks):
            expected = control["evaluations"][world["controller"] + "-as-current"]["worlds"][world["condition"]]["result"]
            require(world["result"] == expected, "observer changed frozen live trajectory")
            worlds[identity] = world
            print(identity + ": " + str(world["analysis"]["samples"]), flush=True)
    for model in models:
        require(digest(root / model["model"]) == model["sha256"], "trace changed model")
    result = {"schema_version": 1, "rule": RULE, "models": models, "probes": PROBES,
              "conditions": signals.previous.conditions(), "worlds": worlds,
              "summary": summarize(worlds, models)}
    write_json(root / "results.json", result)
    return result


def collect(build, inputs_root, output, jobs):
    require(1 <= jobs <= 8 and not output.exists() and
            (output.is_relative_to(ROOT / "artifacts") or not output.is_relative_to(ROOT)),
            "fresh artifacts/external output and jobs 1..8 required")
    signals.load_inputs(inputs_root)
    cache, binary = build / "CMakeCache.txt", build / "toy-factory-garden-landing"
    flags = training.check_flags(cache)
    identities = {"binary": digest(binary), "cache": digest(cache), **INPUTS}
    sources = source_files()
    output.mkdir(parents=True)
    started = time.monotonic()
    try:
        (output / "bin").mkdir()
        (output / "inputs").mkdir()
        shutil.copy2(binary, output / "bin/garden-landing")
        shutil.copy2(cache, output / "CMakeCache.txt")
        shutil.copy2(ROOT / PROTOCOL, output / "protocol.md")
        for name in INPUTS:
            shutil.copy2(inputs_root / name, output / "inputs" / name)
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
                digest(output / "protocol.md") == sources[PROTOCOL], "source/build changed during copy")
        result = run_panel(frozen, output / "inputs", output / "panel", jobs)
        repeated = run_panel(frozen, output / "inputs", output / "repeat", 1)
        require(result == repeated, "worker count changed trace/results")
        for world in result["worlds"].values():
            require((output / "panel" / world["trace"]).read_bytes() ==
                    (output / "repeat" / world["trace"]).read_bytes(), "raw trace changed")
        require(sources == source_files() and digest(binary) == identities["binary"] and
                digest(cache) == identities["cache"], "sources/build changed during collection")
        signals.load_inputs(inputs_root)
        write_json(output / "timings.json", {"collection_and_repeat_seconds": time.monotonic() - started})
        write_json(output / "manifest.json", {"rule": RULE, "status": "complete", "repeat_verified": True,
                   "inputs": identities, "build_flags": flags, "source_sha256_at_collection": sources,
                   "artifacts": {str(p.relative_to(output)): digest(p) for p in sorted(output.rglob("*")) if p.is_file()}})
    except BaseException as error:
        with (output / "FAILED.txt").open("x") as stream:
            stream.write(str(error) + "\n")
        raise
    return result


def verify(output):
    require(not (output / "FAILED.txt").exists(), "incomplete trace bundle")
    manifest = json.loads((output / "manifest.json").read_text())
    require(manifest["rule"] == RULE and manifest["status"] == "complete" and manifest["repeat_verified"] is True,
            "wrong/incomplete trace bundle")
    for name in manifest["artifacts"]:
        artifact(output, manifest, name)
    binary = artifact(output, manifest, "bin/garden-landing")
    require(training.check_flags(output / "CMakeCache.txt") == manifest["build_flags"] and
            manifest["inputs"] == {"binary": digest(binary), "cache": digest(output / "CMakeCache.txt"), **INPUTS} and
            digest(output / "protocol.md") == manifest["source_sha256_at_collection"][PROTOCOL], "provenance mismatch")
    expected = json.loads(artifact(output, manifest, "panel/results.json").read_text())
    require(expected == json.loads(artifact(output, manifest, "repeat/results.json").read_text()), "repeat differs")
    with tempfile.TemporaryDirectory(prefix="landing-decisions-verify-") as temporary:
        fresh = Path(temporary) / "panel"
        actual = run_panel(binary, output / "inputs", fresh, 4)
        require(actual == expected, "trace is not reproducible")
        for path in fresh.rglob("*"):
            if path.is_file():
                require(path.read_bytes() == artifact(output, manifest, "panel/" + str(path.relative_to(fresh))).read_bytes(),
                        "raw replay artifact changed")
    for name in manifest["artifacts"]:
        artifact(output, manifest, name)
    print("Verified all 48 unchanged worlds, exact traces, and every native counterfactual.", flush=True)


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
        print("decision trace failed: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
