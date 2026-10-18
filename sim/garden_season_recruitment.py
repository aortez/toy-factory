#!/usr/bin/env python3
"""Exact, read-only recruitment diagnosis against a retained seasonal panel."""

from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import zlib

from garden_seasons import BLOCKERS, DAY_TICKS, SPECIES, life_summary, require, source_hashes

STRUCTURAL = 8 | 16 | 32
COUNTS = ("births", "expired", "created", "deaths")


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def identity(case: dict) -> str:
    return "-".join(case[k] for k in ("mode", "scenario", "policy", "seed"))


def sites_valid(sites: list) -> None:
    require(len(sites) == 28 and all(type(m) is int and 0 <= m < 128 and not m & 1
                                    for m in sites), "Invalid mature site map")


def step_metrics(row: dict, previous: dict, plants: dict) -> tuple[Counter, Counter, list]:
    """Validate decision-stage receipts before attributing any diagnostic counts."""
    require(row["tick"] == previous["tick"] + 15, "Missing/unordered seed step")
    stages = row["stages"]
    require(len(stages) == 5 and all(len(s) == 3 and all(type(v) is int and 0 <= v <= cap
            for v, cap in zip(s, (256, 8, 8))) for s in stages), "Invalid stage inventory")
    start, before, checked, grown, final = stages
    require(start[2] == before[2] == len(row["attempts"]), "Missing seed visits")
    require(grown[1:] == checked[1:] and final[:2] == grown[:2], "Invalid growth/reproduction inventory")
    require(grown[0] >= checked[0], "Growth removed nodes")
    sites_valid(row["sites_before"])
    sites_valid(row["sites_after"])
    require(len(row["support"]) == 3 and all(type(m) is int and 0 <= m < 1 << 28
                                            for m in row["support"]), "Invalid support")
    stats, masks, births = Counter(steps=1), Counter(), []
    nodes, count = before[:2]
    for attempt in row["attempts"]:
        stats["visits"] += 1
        require(attempt["parent"] in plants, "Unknown seed parent")
        parent = plants[attempt["parent"]]
        require(0 <= attempt["species"] < len(SPECIES) and
                SPECIES[attempt["species"]] == parent["species"] and
                attempt["generation"] == parent["generation"] + 1 and
                0 <= attempt["column"] < 28 and 0 < attempt["age"] <= 8192,
                "Invalid seed identity/age")
        require([attempt["nodes"], attempt["plants"]] == [nodes, count], "Bad sequential inventory")
        if attempt["outcome"] == 1:
            require(attempt["age"] == 8192 and attempt["child"] == 0 and
                    attempt["sites"] == [0] * 28 and attempt["blockers"] == 0 and
                    attempt["moisture"] == attempt["light"] == 0, "Expiry is not a seed check")
            stats["expired"] += 1
            continue
        require(attempt["age"] < 8192, "Expired seed was checked")
        sites_valid(attempt["sites"])
        mask = attempt["blockers"]
        require(mask == (attempt["sites"][attempt["column"]] | (attempt["age"] < 8)),
                "Site/actual blocker mismatch")
        require(bool(mask & 2) == (attempt["moisture"] < 12) and
                bool(mask & 4) == (attempt["light"] < 80) and
                bool(mask & 8) == (count >= 8) and bool(mask & 16) == (nodes > 252) and
                bool(mask & 64) == row["climate"]["cold"], "Resource/capacity/cold mismatch")
        require(attempt["outcome"] == (0 if mask else 2), "Eligible seed failed or blocked seed germinated")
        if mask & 1:
            stats["dormant_checks"] += 1
        else:
            stats["mature_checks"] += 1
            masks[mask] += 1
            for bit, name in enumerate(BLOCKERS):
                stats[f"blocked_{name}"] += bool(mask & (1 << bit))
        if attempt["outcome"] == 2:
            child = plants.get(attempt["child"])
            require(child is not None and child["birth_tick"] == row["tick"] and
                    child["parent"] == attempt["parent"] and child["species"] == parent["species"] and
                    child["generation"] == attempt["generation"], "Unmatched saved birth")
            births.append(child["id"])
            nodes += 4
            count += 1
        else:
            require(attempt["child"] == 0, "Failed check claims a child")
    stats["births"] = len(births)
    require(checked == [nodes, count, before[2] - len(births) - stats["expired"]],
            "Germination inventory mismatch")
    require(row["births"] - previous["births"] == len(births) and
            row["expired"] - previous["expired"] == stats["expired"] and
            row["created"] - previous["created"] == final[2] - grown[2] >= 0,
            "Counter/receipt mismatch")
    ready = sum(1 << c for c, mask in enumerate(row["sites_before"]) if mask == 0)
    structural = any(not mask & STRUCTURAL for mask in row["sites_before"])
    stats["no_structural_space_steps"] = not structural
    stats["environment_blocked_steps"] = structural and not ready
    stats["ready_steps"] = bool(ready)
    stats["ready_column_samples"] = ready.bit_count()
    stats["birth_steps"] = bool(births)
    require(not births or ready, "Birth without an initial usable site")
    if ready:
        stats["ready_no_mature_seed_steps"] = not stats["mature_checks"]
        if stats["mature_checks"] and not births:
            stats["missed_landing_steps"] = 1
            support = row["support"][0] | row["support"][1] | row["support"][2]
            stats["missed_outside_living_support_steps"] = not ready & support
            stats["missed_within_living_support_steps"] = bool(ready & support)
    stats["births_without_post_step_opening"] = len(births) if 0 not in row["sites_after"] else 0
    return stats, masks, births


def analyze(lines, case: dict, early_end: int, late_from: int, end: int) -> dict:
    header_line = next(lines, None)
    require(header_line is not None, "Empty trace")
    header = json.loads(header_line)
    require(header["type"] == "recruitment-header" and header["version"] == 1, "Wrong trace format")
    for key in ("scenario", "policy", "seed"):
        require(header[key] == case[key], f"Trace identity mismatch: {key}")
    require(header["climate"]["mode"] == case["mode"] and header["climate"]["version"] == 1 and
            header["seed_lifetime_ecology_ticks"] == 8192 and
            [header[k] for k in ("early_end", "from", "end")] == [early_end, late_from, end],
            "Trace climate/window mismatch")
    require([header[k] for k in ("node_capacity", "plant_capacity", "seed_capacity")] == [256, 8, 8]
            and header["dispersal"] == "narrow-v1" and not header["gardener"] and
            not header["irrigation"], "Not the normal unassisted ecology")
    plants = {p["id"]: p for p in case["plants"]}
    windows = {"early": (0, early_end), "closing": (late_from, end)}
    totals = {name: Counter() for name in windows}
    histograms = {name: Counter() for name in windows}
    born = {name: [] for name in windows}
    checkpoints, last_step, previous, survivors = [], {name: start for name, (start, _) in windows.items()}, None, None
    for line in lines:
        row = json.loads(line)
        tick = row["tick"]
        if row["type"] == "checkpoint":
            require(tick == len(checkpoints) * DAY_TICKS, "Missing/unordered daily checkpoint")
            daily = case["daily"][len(checkpoints)]
            require(row["hash"] == daily["hash"] and row["births"] == daily["births"] and
                    row["expired"] == daily["seeds_expired"] and row["created"] == daily["seeds_created"]
                    and row["deaths"] == daily["deaths"], "Changed historical daily state")
            if previous is not None and previous["tick"] == tick:
                require(all(row[k] == previous[k] for k in (*COUNTS, "hash")), "Checkpoint/step mismatch")
            checkpoints.append(row["hash"])
        else:
            require(row["type"] == "seed-step", "Unexpected record")
            require(previous is not None, "Missing initial checkpoint")
            name = next((name for name, (start, stop) in windows.items() if start < tick <= stop), None)
            require(name is not None and tick == last_step[name] + 15, "Missing/out-of-window step")
            require(row["climate"]["mode"] == case["mode"] and row["climate"]["version"] == 1 and
                    row["seed_lifetime_ecology_ticks"] == 8192, "Changed environment during trace")
            stats, masks, births = step_metrics(row, previous, plants)
            if survivors is not None and previous["tick"] == tick - 15 and last_step[name] != windows[name][0]:
                inherited = Counter(seed_identity(a, tick) for a in row["attempts"] if a["age"] > 1)
                require(inherited == survivors, "Seed continuity mismatch")
            survivors = Counter(seed_identity(a, tick) for a in row["attempts"] if a["outcome"] == 0)
            totals[name].update(stats)
            histograms[name].update(masks)
            born[name].extend(births)
            last_step[name] = tick
        previous = row
    require(len(checkpoints) == end // DAY_TICKS + 1 and previous["tick"] == end,
            "Incomplete trace/checkpoints")
    result = {}
    for name, (start, stop) in windows.items():
        expected = sorted(p["id"] for p in plants.values() if p["parent"] and start < p["birth_tick"] <= stop)
        require(last_step[name] == stop and totals[name]["steps"] == (stop - start) // 15 and
                sorted(born[name]) == expected, "Incomplete window/birth history")
        stats = totals[name]
        require(stats["no_structural_space_steps"] + stats["environment_blocked_steps"] + stats["ready_steps"]
                == stats["steps"], "Opportunity partition mismatch")
        require(stats["birth_steps"] + stats["missed_landing_steps"] + stats["ready_no_mature_seed_steps"]
                == stats["ready_steps"], "Landing partition mismatch")
        require(stats["expired"] == case["daily"][stop // DAY_TICKS]["seeds_expired"] -
                case["daily"][start // DAY_TICKS]["seeds_expired"], "Expiry total mismatch")
        result[name] = {"from": start, "end": stop, "counts": dict(sorted(stats.items())),
                        "mature_masks": dict(sorted(histograms[name].items())), "birth_ids": born[name],
                        "cohorts": life_summary(plants, stop, start + 1)}
    require(result["closing"]["cohorts"] == case["closing_lifetimes"], "Changed closing cohorts")
    return {**{k: case[k] for k in ("mode", "scenario", "policy", "seed")},
            "daily_hashes": checkpoints, "windows": result}


def seed_identity(attempt: dict, tick: int) -> tuple:
    # Multiset, not a unique seed ID: same-parent simultaneous placements can collide.
    return tuple(attempt[k] for k in ("parent", "generation", "species", "column")) + (tick - 15 * attempt["age"],)


def capture(binary: Path, directory: Path, case: dict, end: int) -> dict:
    command = [str(binary), case["scenario"], case["policy"], str(int(case["seed"], 16)),
               case["mode"], str(16 * DAY_TICKS), str(end - 16 * DAY_TICKS), str(end)]
    name = identity(case)
    with tempfile.TemporaryFile(mode="w+t") as stream:
        subprocess.run(command, stdout=stream, stderr=subprocess.PIPE, text=True, check=True, timeout=300)
        stream.seek(0)
        result = analyze(iter(stream), case, 16 * DAY_TICKS, end - 16 * DAY_TICKS, end)
        stream.seek(0)
        checksum = hashlib.sha256()
        with (directory / (name + ".jsonl.gz")).open("xb") as raw:
            with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed:
                for line in stream:
                    data = line.encode()
                    checksum.update(data)
                    compressed.write(data)
    print(f"Verified {name}: {len(result['daily_hashes'])} daily states", flush=True)
    return {**result, "trace_sha256": checksum.hexdigest(), "command": command,
            "trace": name + ".jsonl.gz"}


def frames(build: Path, output: Path, cases: list[dict], first_seed: str) -> list[dict]:
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts/container"))
    from framebuffer_capture import rgb565be_to_rgb888, write_png
    output.mkdir()
    results = []
    for case in cases:
        if (case["seed"], case["scenario"], case["policy"]) != (first_seed, "rainfed", "adaptive"):
            continue
        for day in (16, 128):
            name = f"{case['mode']}-day-{day}"
            raw = output / (name + ".rgb565be")
            command = [build / "toy-factory-garden-replay", "-", case["scenario"], case["policy"],
                       str(int(first_seed, 16)), "--climate", case["mode"], "--ticks", str(day * DAY_TICKS),
                       "--framebuffer", raw]
            frame = json.loads(subprocess.check_output(list(map(str, command)), text=True, timeout=300))
            data = raw.read_bytes()
            require(frame["hash"] == case["daily"][day]["hash"] and len(data) == 240 * 240 * 2 and
                    frame["framebuffer_crc32"] == f"{zlib.crc32(data):08x}", "Frame replay mismatch")
            png = output / (name + ".png")
            write_png(png, 240, 240, rgb565be_to_rgb888(data))
            results.append({"png": "frames/" + png.name, "day": day, "mode": case["mode"],
                            "hash": frame["hash"], "framebuffer_crc32": frame["framebuffer_crc32"],
                            "png_sha256": digest(png)})
    return results


def frozen_sources(root: Path) -> dict:
    return {**source_hashes(root), **{str(p.relative_to(root)): digest(p) for p in
            (Path(__file__).resolve(), root / "sim/garden_seasons.py", root / "sim/CMakeLists.txt",
             root / "benchmarks/garden-seasons/recruitment-protocol.md")}}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--panel", type=Path, required=True)
    parser.add_argument("--build", type=Path, default=Path("build-host"))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--jobs", type=int, default=4)
    args = parser.parse_args()
    if not 1 <= args.jobs <= 8:
        parser.error("Require 1–8 jobs")
    root = Path(__file__).resolve().parents[1]
    published = json.loads((root / "benchmarks/garden-seasons/fresh-128.json").read_text())
    require(digest(args.panel) == published["control_input_sha256"], "Changed parent seasonal evidence")
    panel = json.loads(args.panel.read_text())
    require(panel["protocol"] == "garden-seasons-v2" and panel["days"] == 128 and
            panel["seed_base"] == "73656132" and not panel["gardener"] and not panel["irrigation"],
            "Expected the fixed unassisted fresh-128 panel")
    cases = [c for c in panel["cases"] if c["mode"] in ("steady", "seasonal")]
    expected = {(mode, layout, policy, seed) for mode in ("steady", "seasonal")
                for layout in ("rainfed", "rainfed-crowded") for policy in ("baseline", "adaptive")
                for seed in ("ed52188b", "4f0b9240", "a9c30c19", "0bb887d6")}
    require(len(cases) == 32 and {tuple(c[k] for k in ("mode", "scenario", "policy", "seed"))
                                for c in cases} == expected, "Incomplete/duplicate fixed panel")
    args.out.mkdir(parents=True, exist_ok=False)
    build = args.build.resolve()
    binary = build / "toy-factory-garden-recruitment-audit"
    replayer = build / "toy-factory-garden-replay"
    sources, binary_hash, replay_hash, parent_hash = frozen_sources(root), digest(binary), digest(replayer), digest(args.panel)
    end = 128 * DAY_TICKS
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        results = list(pool.map(lambda case: capture(binary, args.out, case, end), cases))
    repeated = []
    (args.out / "repeats").mkdir()
    for case, result in zip(cases, results):
        if case["mode"] == "seasonal" and case["seed"] == "ed52188b":
            repeat = capture(binary, args.out / "repeats", case, end)
            require(repeat == result, "Nonrepeatable trace/analysis")
            repeated.append(identity(case))
    images = frames(build, args.out / "frames", cases, "ed52188b")
    require(frozen_sources(root) == sources and digest(binary) == binary_hash and
            digest(replayer) == replay_hash and digest(args.panel) == parent_hash, "Experiment inputs changed")
    groups = {}
    for mode in ("steady", "seasonal"):
        groups[mode] = {}
        for window in ("early", "closing"):
            group = [r["windows"][window] for r in results if r["mode"] == mode]
            groups[mode][window] = {"counts": dict(sum((Counter(g["counts"]) for g in group), Counter())),
                                    "cohorts": dict(sum((Counter(g["cohorts"]) for g in group), Counter())),
                                    "worlds_with_ready_sites": sum(g["counts"].get("ready_steps", 0) > 0 for g in group),
                                    "worlds_with_missed_landings": sum(g["counts"].get("missed_landing_steps", 0) > 0 for g in group)}
    report = {"protocol": "seasonal-recruitment-v1", "parent_sha256": parent_hash,
              "source_sha256": sources, "auditor_sha256": binary_hash, "replayer_sha256": replay_hash,
              "repeated": repeated, "frames": images, "groups": groups, "cases": results}
    (args.out / "summary.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(groups, indent=2))


if __name__ == "__main__":
    main()
