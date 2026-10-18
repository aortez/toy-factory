#!/usr/bin/env python3
"""Passive uptake attribution on four pinned worlds, with observer-on/off neutrality."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from functools import cache, lru_cache
import gzip
import json
from pathlib import Path
import shutil
import sys

import garden_landing_population_audit as previous
import garden_landing_population as population
from garden_experiments import compress, digest, snapshot_sources, source_files, write_json
from garden_landing_energy_audit import archived_sources
from garden_resources import require

ROOT, STEP, STOP = population.ROOT, population.STEP, population.STOP
RULE = "garden-landing-uptake-v1"
PROTOCOL = "benchmarks/garden-seasons/landing-uptake-protocol.md"
AUDIT = "benchmarks/garden-seasons/landing-population-audit-results.json.gz"
AUDIT_SHA = "c40da0fc11e0a9e7cb1480faa0cbaaa328c758ddea8681d7f8981084244cf461"
INPUTS = {previous.INPUT: previous.INPUT_SHA, AUDIT: AUDIT_SHA}
ENERGY = ("actual", "open", "without_self", "without_other_live", "without_dead", "self_only")
WATER = ("wanted", "taken", "absent_before", "earlier_depletion", "without_earlier_self_gain",
         "without_earlier_other_gain", "overflow")


@cache
def audit_input():
    require(digest(ROOT / AUDIT) == AUDIT_SHA, "saved window audit changed")
    with gzip.open(ROOT / AUDIT, "rt") as stream:
        data = json.load(stream)
    previous.check_value(data)
    return data


def saved_excerpts(case_id, arm):
    return next(c for c in audit_input()["excerpts"] if c["id"] == case_id)["arms"][arm]


def windows(case_id, arm):
    spans = sorted([s["start"], s["end"]] for p in saved_excerpts(case_id, arm) for s in p["segments"])
    merged = []
    for start, stop in spans:
        if merged and start <= merged[-1][1] + STEP:
            merged[-1][1] = max(stop, merged[-1][1])
        else:
            merged.append([start, stop])
    require(0 < len(merged) <= 64, "too many selected windows")
    return merged


@cache
def rays(ray):
    require(type(ray) is int and -12 <= ray <= 12, "invalid ray direction")
    paths = []
    for row in range(14):
        for column in range(28):
            path = []
            for distance in range(1, row + 1):
                product = ray * distance
                offset = ((abs(product) + 8) // 16) * (-1 if product < 0 else 1)
                source = column - offset
                if not 0 <= source < 28:
                    break
                path.append((row - distance) * 28 + source)
            paths.append(tuple(path))
    return tuple(paths)


@lru_cache(maxsize=512)
def opacity(sources, owner, mode):
    grid = [0] * (28 * 14)
    for node, lineage, dead, column, row, center, side in sources:
        own = lineage == owner
        if (mode == "without_self" and own or mode == "without_other_live" and not own and not dead or
                mode == "without_dead" and dead or mode == "self_only" and not own):
            continue
        for c, amount in ((column, center), (column - 1, side), (column + 1, side)):
            if 0 <= c < 28:
                cell = row * 28 + c
                grid[cell] = min(255, grid[cell] + amount)
    return tuple(grid)


@lru_cache(maxsize=512)
def attenuation(grid, ray):
    return tuple(sum(grid[cell] for cell in path) for path in rays(ray))


def field(grid, strength, ray):
    return [max(24, strength - reduction) for reduction in attenuation(grid, ray)]


def vector(value, size, upper):
    return isinstance(value, list) and len(value) == size and all(type(n) is int and 0 <= n <= upper for n in value)


def attribute(row, resources, lives, *, partial=False):
    """Reconcile one actual uptake, then diagnose removals on frozen geometry/order."""
    require(set(row) == {"tick", "sun", "sources", "roots", "leaves", "soil_before", "soil_after", "light"}, "wrong uptake fields")
    tick = row["tick"]
    phase, strength, ray = row["sun"]
    require(type(tick) is int and tick % STEP == 0 and phase == (64 + tick // STEP) % 256 and
            24 <= strength <= 255 and ray == previous.light.ray_step(phase), "wrong uptake clock/sun")
    before, after, recorded = [list(bytes.fromhex(row[k])) for k in ("soil_before", "soil_after", "light")]
    require(len(before) == len(after) == 28 * 11 and len(recorded) == 28 * 14, "wrong grid dimensions")
    sources = tuple(tuple(s) for s in row["sources"])
    require(len(sources) <= 256 and all(vector(list(s), 7, 0xffffffff) and s[0] < 256 and s[2] in (0, 1) and
            s[3] < 28 and s[4] < 14 and s[5] <= 255 and s[6] <= 255 for s in sources), "invalid shade source")
    require([s[0] for s in sources] == sorted({s[0] for s in sources}), "duplicate/unordered shade source")
    def alive(i):
        require(i in lives, "unknown uptake lineage")
        p = lives[i]
        require(p["birth_tick"] < tick, "uptake before birth")
        return p["death_tick"] is None or p["death_tick"] >= tick
    for source in sources:
        require(bool(source[2]) != alive(source[1]), "wrong live/dead shade identity")
    require(field(opacity(sources, 0, "actual"), strength, ray) == recorded, "light field reconstruction differs")
    owners = {r[1] for k in ("roots", "leaves") for r in row[k]}
    expected = {i for i, p in resources.items() if p["uptake"] is not None}
    require(partial or owners <= expected, "missing uptake resource receipt")
    totals = {i: {"energy": [0] * len(ENERGY), "water": [0] * len(WATER)} for i in owners | resources.keys()}
    require(len(row["roots"]) + len(row["leaves"]) <= 256, "too many uptake events")
    nodes, last, slots, stores = set(), (-1, -1), {}, {}
    soil, consumers = before.copy(), defaultdict(lambda: defaultdict(int))
    for r in row["roots"]:
        require(vector(r, 11, 0xffffffff), "invalid root record")
        node, i, slot, col, y, limit, opening, taken, closing, stored, final = r
        require(node < 256 and node not in nodes and alive(i) and slot < 8 and col < 28 and y < 11 and
                1 <= limit <= 3 and 0 <= opening <= 255 and stored <= 512 and final <= 512 and
                (slot, node) > last and slots.setdefault(slot, i) == i, "invalid root identity/order")
        nodes.add(node)
        last = slot, node
        cell = y * 28 + col
        require(opening == soil[cell] and taken == min(limit, opening) and closing == opening - taken and
                final == min(512, stored + taken), "root transfer differs")
        if i not in stores and i in expected:
            stores[i] = resources[i]["uptake"][1][0]
        require(stores.get(i, stored) == stored, "root storage discontinuity")
        stores[i] = final
        own = consumers[cell][i]
        other = sum(consumers[cell].values()) - own
        values = (limit, taken, limit - min(limit, before[cell]), min(limit, before[cell]) - taken,
                  min(limit, opening + own) - taken, min(limit, opening + other) - taken, stored + taken - final)
        totals[i]["water"] = [a + b for a, b in zip(totals[i]["water"], values, strict=True)]
        consumers[cell][i] += taken
        soil[cell] = closing
    require(soil == after, "post-uptake soil differs")
    leaf_fields = {}
    for leaf in row["leaves"]:
        require(vector(leaf, 6, 0xffffffff), "invalid leaf record")
        node, i, col, y, local, income = leaf
        require(node < 256 and node not in nodes and alive(i) and col < 28 and y < 14,
                "invalid leaf identity")
        nodes.add(node)
        cell = y * 28 + col
        require(local == recorded[cell] and income == local // 64, "leaf income differs")
        if i not in leaf_fields:
            leaf_fields[i] = {mode: field(opacity(sources, i, mode), strength, ray) for mode in ENERGY[2:]}
        values = [income, strength // 64, *(leaf_fields[i][m][cell] // 64 for m in ENERGY[2:])]
        require(all(income <= n <= values[1] for n in values[2:]), "invalid shade removal bound")
        totals[i]["energy"] = [a + b for a, b in zip(totals[i]["energy"], values, strict=True)]
    for i in expected:
        p, t = resources[i], totals[i]
        require(t["energy"][0] == p["uptake"][0][1] and t["water"][1] == p["uptake"][1][1] and
                t["water"][6] == p["uptake"][1][2], "plant uptake/overflow differs")
    return totals


def observation_rows(path, spans, result):
    with gzip.open(path, "rt") as stream:
        require(json.loads(next(stream)) == {"schema": "landing-uptake-v1", "stop": STOP, "windows": spans}, "wrong uptake header")
        for start, stop in spans:
            for tick in range(start, stop + STEP, STEP):
                row = json.loads(next(stream))
                require(row["tick"] == tick, "missing/reordered uptake row")
                yield row
        require(json.loads(next(stream)) == {"complete": True, "tick": STOP, "run_hash": result["run_hash"]}
                and not stream.read(), "incomplete/trailing uptake trace")


def analyze_raw(directory, case, arm, run):
    saved = next(c for c in previous.cases() if c["case"] == case)["arms"][arm]
    selected = saved_excerpts(case["id"], arm)
    histories = [{"id": p["id"], "segments": [{"start": s["start"], "stop": s["end"], "samples": []}
                  for s in p["segments"]]} for p in selected]
    targets = {p["id"]: p["segments"] for p in histories}
    lives = {p["id"]: p for p in saved["result"]["lineages"]}
    shortage_ticks = {e["tick"] for p in saved["analysis"]["plants"] for e in p["shortages"]}
    stream = observation_rows(directory / run["traces"]["uptake"]["path"], windows(case["id"], arm), saved["result"])
    current = next(stream, None)
    witnesses, counts = [], {"frames": 0, "roots": 0, "leaves": 0, "sources": 0}
    previous_roots = {}
    for adult in population.trace_rows(directory / run["traces"]["adult"]["path"], "adult", saved["result"]):
        old_roots = previous_roots.copy()
        previous_roots.update({p["id"]: p["roots"] for p in adult["plants"]})
        if current is None or adult["tick"] != current["tick"]:
            continue
        require(adult["sun"] == current["sun"][:2], "uptake sun differs from resource trace")
        resources = {p["id"]: p for p in adult["plants"]}
        require(Counter(r[1] for r in current["roots"]) == Counter({
            i: old_roots.get(i, p["roots"]) for i, p in resources.items() if p["uptake"] is not None}),
            "missing/extra pre-growth root visit")
        totals = attribute(current, resources, lives)
        for i, segments in targets.items():
            for s in segments:
                if s["start"] <= current["tick"] <= s["stop"]:
                    t = totals.get(i, {"energy": [0] * len(ENERGY), "water": [0] * len(WATER)})
                    require(i in resources, "selected plant missing")
                    s["samples"].append([current["tick"], t["energy"], t["water"]])
        counts["frames"] += 1
        for k in ("roots", "leaves", "sources"):
            counts[k] += len(current[k])
        if current["tick"] in shortage_ticks:
            witnesses.append(current)
        current = next(stream, None)
    require(current is None, "unconsumed uptake samples")
    return {"counts": counts, "histories": histories, "shortage_witnesses": witnesses}


def summaries(analysis, case_id, arm):
    expected = saved_excerpts(case_id, arm)
    require([h["id"] for h in analysis["histories"]] == [p["id"] for p in expected], "wrong uptake history panel")
    out = []
    for history, p in zip(analysis["histories"], expected, strict=True):
        require([[s["start"], s["stop"]] for s in history["segments"]] == [[s["start"], s["end"]] for s in p["segments"]], "wrong uptake selection")
        summary = {"id": p["id"], "windows": []}
        for segment, old in zip(history["segments"], p["segments"], strict=True):
            totals = {"energy": [0] * len(ENERGY), "water": [0] * len(WATER)}
            require([s[0] for s in segment["samples"]] == list(range(old["start"], old["end"] + STEP, STEP)), "incomplete uptake history")
            for sample, raw in zip(segment["samples"], old["rows"], strict=True):
                tick, energy, water = sample
                require(vector(energy, len(ENERGY), 768) and vector(water, len(WATER), 768), "invalid attributed income")
                r = raw["plant"]["uptake"]
                require(energy[0] == (r[0][1] if r else 0) and water[1] == (r[1][1] if r else 0) and
                        water[6] == (r[1][2] if r else 0) and water[0] == sum(water[1:4]) and
                        all(energy[0] <= n <= energy[1] for n in energy[2:]) and
                        water[4] <= water[3] and water[5] <= water[3], "attribution/resource bounds differ")
                for k, v in (("energy", energy), ("water", water)):
                    totals[k] = [a + b for a, b in zip(totals[k], v, strict=True)]
            summary["windows"].append({"start": old["start"], "stop": old["end"], **{
                k: dict(zip(names, totals[k], strict=True)) for k, names in (("energy", ENERGY), ("water", WATER))}})
        out.append(summary)
    return out


def check_value(value):
    require(value["rule"] == RULE and value["inputs"] == INPUTS and
            all(digest(ROOT / k) == v for k, v in INPUTS.items()) and value["full_replays"] == 8 and
            value["training_runs"] == 0 and value["protocol_sha256"] == digest(ROOT / PROTOCOL) and
            value["source_sha256"].get(PROTOCOL) == value["protocol_sha256"], "wrong uptake provenance")
    require(all(value["source_sha256"].get(k) == v for k, v in INPUTS.items()) and
            value["settings"] == previous.load_input()["settings"], "wrong uptake input/configuration pins")
    require([e["case"] for e in value["cases"]] == [c["case"] for c in previous.cases()], "wrong uptake panel")
    for entry, saved in zip(value["cases"], previous.cases(), strict=True):
        require(set(entry["arms"]) == set(population.ARMS), "wrong uptake arms")
        for arm, a in entry["arms"].items():
            require(set(a["runs"]) == {"on", "off"}, "missing observer ablation")
            historical = saved["arms"][arm]["runs"]["trace"]
            for label, run in a["runs"].items():
                expected_args = population.arguments(entry["case"], arm, "trace")
                if label == "on":
                    expected_args += ["--uptake-trace", "uptake.jsonl"]
                    for start, stop in windows(entry["case"]["id"], arm):
                        expected_args += ["--uptake-window", f"{start}:{stop}"]
                require(run["args"] == expected_args and run["result"] == historical["result"] and
                        run["frame"]["sha256"] == historical["frame"]["sha256"] and
                        all(run["traces"][k]["sha256"] == historical["traces"][k]["sha256"] for k in ("stand", "adult")),
                        "observer/historical behavior changed")
            require(a["summary"] == summaries(a["analysis"], entry["case"]["id"], arm), "uptake summary differs")
            saved_analysis = saved["arms"][arm]["analysis"]
            expected_ticks = sorted({e["tick"] for p in saved_analysis["plants"] for e in p["shortages"]})
            require([r["tick"] for r in a["analysis"]["shortage_witnesses"]] == expected_ticks, "missing shortage witness")
            expected_frames = sum((b - s) // STEP + 1 for s, b in windows(entry["case"]["id"], arm))
            require(a["analysis"]["counts"]["frames"] == expected_frames, "wrong observed frame count")
            lives = {p["life"]["id"]: p["life"] for p in saved_analysis["plants"]}
            by_tick = defaultdict(dict)
            sun_by_tick = {}
            for p in saved_excerpts(entry["case"]["id"], arm):
                for segment in p["segments"]:
                    for row in segment["rows"]:
                        by_tick[row["tick"]][p["id"]] = row["plant"]
                        sun_by_tick[row["tick"]] = row["sun"]
            samples = {p["id"]: {s[0]: s for segment in p["segments"] for s in segment["samples"]}
                       for p in a["analysis"]["histories"]}
            for witness in a["analysis"]["shortage_witnesses"]:
                t = witness["tick"]
                require(witness["sun"][:2] == sun_by_tick[t], "shortage illumination differs")
                observed = attribute(witness, by_tick[t], lives, partial=True)
                for i, table in samples.items():
                    if t in table:
                        require(table[t][1:] == [observed[i]["energy"], observed[i]["water"]], "shortage attribution differs")


def collect(build, out, jobs):
    require(not out.exists() and (out.is_relative_to(ROOT / "artifacts") or not out.is_relative_to(ROOT)), "fresh output required")
    inputs = previous.cases()
    audit_input()
    metadata, model = population.load_model()
    binary, cache_path = build / "toy-factory-garden-landing", build / "CMakeCache.txt"
    settings = population.order.previous.placement.budget.growth.water.check_build(cache_path)
    sources = source_files()
    out.mkdir(parents=True)
    (out / "bin").mkdir()
    frozen = out / "bin/garden-landing"
    shutil.copy2(binary, frozen)
    shutil.copy2(cache_path, out / "CMakeCache.txt")
    shutil.copy2(ROOT / PROTOCOL, out / "protocol.md")
    snapshot_sources(out, sources)
    value = {"rule": RULE, "inputs": INPUTS, "full_replays": 8, "training_runs": 0,
             "protocol_sha256": digest(ROOT / PROTOCOL), "source_sha256": sources, "settings": settings,
             "build": {"binary": digest(frozen), "cache": digest(cache_path)}, "cases": []}
    calls = [(e, a, label) for e in inputs for a in population.ARMS for label in ("on", "off")]
    def capture(call):
        entry, arm, label = call
        case = entry["case"]
        name = case["id"] + "-" + arm + "-" + label
        directory = out / name
        directory.mkdir()
        (directory / "frames").mkdir()
        with (directory / "model.tgl").open("xb") as stream:
            stream.write(model)
        args = population.arguments(case, arm, "trace")
        if label == "on":
            args += ["--uptake-trace", "uptake.jsonl"]
            for start, stop in windows(case["id"], arm):
                args += ["--uptake-window", f"{start}:{stop}"]
        result = population.order.training.native(frozen, directory, *args)
        write_json(directory / "result.json", result)
        traces = {}
        for kind in ("stand", "adult", *(["uptake"] if label == "on" else [])):
            file = args[args.index("--" + kind + "-trace") + 1]
            target = directory / (file + ".gz")
            compress(directory / file, target)
            traces[kind] = {"path": name + "/" + target.name, "sha256": digest(target)}
        frame = args[args.index("--framebuffer") + 1]
        run = {"args": args, "result": result, "traces": traces,
               "frame": {"path": name + "/" + frame, "sha256": digest(directory / frame)}}
        historical = entry["arms"][arm]["runs"]["trace"]
        require(result == historical["result"] and run["frame"]["sha256"] == historical["frame"]["sha256"] and
                all(traces[k]["sha256"] == historical["traces"][k]["sha256"] for k in ("stand", "adult")),
                "historical neutrality failed: " + name)
        print(name + ": historical result, all decisions/resources and pixels match", flush=True)
        return run
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        captured = list(pool.map(capture, calls))
    it = iter(captured)
    for entry in inputs:
        arms = {}
        for arm in population.ARMS:
            runs = {label: next(it) for label in ("on", "off")}
            analysis = analyze_raw(out, entry["case"], arm, runs["on"])
            arms[arm] = {"runs": runs, "analysis": analysis,
                         "summary": summaries(analysis, entry["case"]["id"], arm)}
            print(entry["case"]["id"] + "/" + arm + ": all uptake reconstructed", flush=True)
        value["cases"].append({"case": entry["case"], "arms": arms})
    check_value(value)
    require(source_files() == sources and digest(binary) == value["build"]["binary"] and
            digest(cache_path) == value["build"]["cache"], "source/build changed during capture")
    population.order.recovery.founders.write_gzip(out / "results.json.gz", value)
    write_json(out / "manifest.json", {"rule": RULE, "artifacts": {
        str(p.relative_to(out)): digest(p) for p in sorted(out.rglob("*")) if p.is_file()}})
    return value


def verify(path):
    directory = path if path.is_dir() else None
    if directory:
        manifest = json.loads((directory / "manifest.json").read_text())
        require(manifest["rule"] == RULE, "wrong uptake bundle")
        for name, sha in manifest["artifacts"].items():
            p = (directory / name).resolve()
            require(p.is_relative_to(directory) and digest(p) == sha, "uptake artifact changed")
        path = directory / "results.json.gz"
    with gzip.open(path, "rt") as stream:
        value = json.load(stream)
    check_value(value)
    if directory:
        require(archived_sources(directory / "source.tar.gz") == value["source_sha256"], "uptake source archive differs")
        require(digest(directory / "bin/garden-landing") == value["build"]["binary"] and
                digest(directory / "CMakeCache.txt") == value["build"]["cache"] and
                digest(directory / "protocol.md") == value["protocol_sha256"], "frozen build/protocol differs")
        for entry in value["cases"]:
            for arm, a in entry["arms"].items():
                for run in a["runs"].values():
                    for item in (run["frame"], *run["traces"].values()):
                        require(manifest["artifacts"].get(item["path"]) == item["sha256"], "run/manifest artifact differs")
                    result_path = (directory / run["traces"]["adult"]["path"]).parent / "result.json"
                    require(json.loads(result_path.read_text()) == run["result"], "raw result differs")
                require(analyze_raw(directory, entry["case"], arm, a["runs"]["on"]) == a["analysis"], "raw uptake analysis differs")
                print(entry["case"]["id"] + "/" + arm + ": raw attribution verified", flush=True)
    print("Verified frozen worlds, observer neutrality, uptake accounting and attributed windows.")
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path, default=ROOT / "build-host")
    parser.add_argument("--out", type=Path, default=ROOT / "artifacts/garden-landing-uptake-v1")
    parser.add_argument("--jobs", type=int, choices=range(1, 5), default=2)
    parser.add_argument("--verify", type=Path)
    args = parser.parse_args()
    if args.verify:
        verify(args.verify.resolve())
    else:
        collect(args.build.resolve(), args.out.resolve(), args.jobs)


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError, KeyError, TypeError, OSError, StopIteration) as error:
        print("uptake attribution failed: " + str(error), file=sys.stderr)
        sys.exit(1)
