#!/usr/bin/env python3
"""Read-only parent-specific dispersal support and sequential site opportunity."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
import gzip
import json
from pathlib import Path
import shutil
import sys
import tempfile

import garden_landing_recruitment as prior
from garden_experiments import compress, digest, source_files, snapshot_sources, write_json
from garden_gallery import artifact
from garden_resources import require

ROOT = prior.ROOT
DAY, STEP, STOP = prior.DAY, prior.STEP, prior.STOP
RULE = "garden-landing-reach-v1"
PROTOCOL = "benchmarks/garden-seasons/landing-reach-protocol.md"
PREVIOUS = "landing-recruitment-trace-results.json.gz"
INPUTS = {**prior.INPUTS, PREVIOUS: "2e4a8b9bada29ae847e0f77d22e020cab9b117765455ff6e11fbd52088b44561"}


def load_inputs(root):
    panel, models, audit = prior.load_inputs(root)
    require(digest(root / PREVIOUS) == INPUTS[PREVIOUS], "wrong recruitment input")
    previous = json.loads(gzip.decompress((root / PREVIOUS).read_bytes()))
    require(previous["plan"] == prior.select(audit) and previous["inputs"] == prior.INPUTS and
            previous["rule"] == prior.RULE, "wrong recruitment panel")
    return panel, models, previous


def support(origin, trait):
    """Independent reference for ordinary production, preserving reflection aliases."""
    require(type(origin) is int and 0 <= origin < 28 and type(trait) is int and -2 <= trait <= 2,
            "invalid origin/parent trait")
    result = []
    for choice in range(6):
        distance, direction = 5 + trait + choice // 2, 1 if choice & 1 else -1
        column = origin + direction * distance
        if not 0 <= column < 28:
            column = origin - direction * distance
        result.append(min(27, max(0, column)))
    return result


def sites_decode(value):
    require(type(value) is str and len(value) == 56, "wrong site mask width")
    sites = bytes.fromhex(value)
    require(len(sites) == 28 and sites.hex() == value and all(v < 128 and not v & 1 for v in sites),
            "invalid mature site mask")
    return sites


def opportunities(seed):
    choices = seed["purchase"]["choices"]
    columns = set(choices)
    hist = {k: Counter() for k in ("global_open", "reachable_open", "alternative_open",
                                  "reachable_spacing_clear", "open_choices")}
    all_blocked = Counter()
    for encoded, count in seed["mature_sites"].items():
        sites = sites_decode(encoded)
        opened = {c for c, mask in enumerate(sites) if not mask}
        counts = (len(opened), len(opened & columns), len((opened & columns) - {seed["column"]}),
                  sum(not sites[c] & 32 for c in columns), sum(c in opened for c in choices))
        for key, n in zip(hist, counts, strict=True):
            hist[key][str(n)] += count
        for i, name in enumerate(prior.BLOCKERS):
            if all(sites[c] & (1 << i) for c in columns):
                all_blocked[name] += count
    purchase_sites = sites_decode(seed["purchase"]["sites"])
    return {"unique_columns": sorted(columns), "histograms": {k: dict(sorted(v.items())) for k, v in hist.items()},
            "all_reachable_blocked_by": {b: all_blocked[b] for b in prior.BLOCKERS},
            "purchase": {"actual_mask": purchase_sites[seed["column"]],
                         "open_columns": sorted(c for c in columns if not purchase_sites[c]),
                         "open_choices": sum(not purchase_sites[c] for c in choices)}}


def summarize(seeds):
    result = {"seeds": len(seeds), "mature_checks": 0, "any_global_open": 0, "any_reachable_open": 0,
              "any_alternative_open": 0, "never_reachable_open": 0, "no_mature_checks": 0,
              "any_reachable_spacing_clear": 0, "always_reachable_spacing_blocked": 0,
              "purchase_reachable_open": 0, "purchase_alternative_open_actual_blocked": 0,
              "outcomes": dict(sorted(Counter(s["outcome"] for s in seeds).items())),
              "checks_with": dict.fromkeys(("global_open", "reachable_open", "alternative_open",
                                           "reachable_spacing_clear"), 0),
              "unique_support_counts": dict(sorted(Counter(str(len(set(s["purchase"]["choices"])))
                                                          for s in seeds).items()))}
    for s in seeds:
        op = s["opportunities"]
        n = sum(s["mature_sites"].values())
        result["mature_checks"] += n
        counts = {k: sum(v for mask, v in h.items() if int(mask)) for k, h in op["histograms"].items()}
        for k in result["checks_with"]:
            result["checks_with"][k] += counts[k]
        for name in ("global_open", "reachable_open", "alternative_open", "reachable_spacing_clear"):
            result["any_" + name] += bool(counts[name])
        result["never_reachable_open"] += bool(n and not counts["reachable_open"])
        result["no_mature_checks"] += not n
        result["always_reachable_spacing_blocked"] += bool(n and not counts["reachable_spacing_clear"])
        result["purchase_reachable_open"] += bool(op["purchase"]["open_columns"])
        result["purchase_alternative_open_actual_blocked"] += bool(op["purchase"]["open_columns"] and
                                                                  op["purchase"]["actual_mask"])
    return result


def analyze_trace(path, result, previous):
    stop = result["tick"]
    require(type(stop) is int and stop >= 0, "invalid horizon")
    ledger = {(s["parent"], s["birth_tick"]): s for s in result["seeds"]}
    require(len(ledger) == len(result["seeds"]), "duplicate ledger seed")
    old = {(s["parent"], s["birth_tick"]): s for s in previous["seeds"]}
    require(set(old) == set(ledger), "old seed inventory differs")
    plants = {p["id"]: p for p in result["lineages"]}
    born = defaultdict(set)
    for key in ledger:
        born[key[1]].add(key)
    seeds, active, traits = {}, set(), {}
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt") as stream:
        require(json.loads(next(stream)) == {"schema": "landing-reach-trace-v1"}, "wrong reach schema")
        for tick in range(STEP, stop + 1, STEP):
            row = json.loads(next(stream))
            require(set(row) == {"tick", "purchases", "checks"} and row["tick"] == tick, "missing/reordered reach step")
            seen, ended = set(), set()
            for values in row["checks"]:
                require(len(values) == 7 and all(type(v) is int for v in values[:6]), "invalid reach check")
                parent, age, column, mask, outcome, child, encoded = values
                key = parent, tick - age * STEP
                require(key in active and key not in seen, "unknown/duplicate reach check")
                seen.add(key)
                s = seeds[key]
                require(age == s["samples"] + 1 and column == s["column"] and 0 <= mask < 128,
                        "invalid reach age/column/mask")
                expected = 0 if s["end_tick"] != tick else {"expired": 1, "germinated": 2}[s["outcome"]]
                require(outcome == expected and child == (s["child_id"] if outcome == 2 else 0), "reach fate differs")
                s["samples"] += 1
                if outcome:
                    ended.add(key)
                if outcome == 1:
                    require(encoded is None and mask == 0 and age == s["lifetime_ecology_ticks"],
                            "expiry is not a site check")
                    continue
                sites = sites_decode(encoded)
                require(bool(mask & 1) == (age < 8) and (mask & ~1) == sites[column] and
                        ((mask == 0) == (outcome == 2)), "actual versus hypothetical gate differs")
                s["masks"][str(mask)] += 1
                if mask & 1:
                    continue
                s["mature_sites"][encoded] += 1
                opened = [c for c, value in enumerate(sites) if not value]
                s["open_elsewhere_checks"] += bool(opened and mask)
                for c in opened:
                    window = s["open_windows"][c]
                    window[4] = window[4] + 1 if window[2] == tick - STEP else 1
                    window[0] += 1
                    if window[1] is None:
                        window[1] = tick
                    window[2] = tick
                    window[3] = max(window[3], window[4])
            require(seen == active, "incomplete reach check inventory")
            active -= ended
            purchased = set()
            for p in row["purchases"]:
                require(set(p) == {"parent", "column", "origin", "dispersal", "choices", "sites"}, "invalid purchase")
                key = p["parent"], tick
                require(key in ledger and key not in seeds, "unknown/duplicate purchase")
                parent = plants[p["parent"]]
                require(p["origin"] == parent["column"] and parent["birth_tick"] <= tick and
                        (parent["death_tick"] is None or tick < parent["death_tick"]), "wrong producing parent")
                require(p["choices"] == support(p["origin"], p["dispersal"]) and
                        p["column"] in p["choices"] and p["column"] == ledger[key]["column"], "wrong production support")
                sites_decode(p["sites"])
                require(traits.setdefault(p["parent"], p["dispersal"]) == p["dispersal"], "parent trait changed")
                seeds[key] = {**ledger[key], "purchase": p, "samples": 0, "masks": Counter(),
                              "mature_sites": Counter(), "open_elsewhere_checks": 0,
                              "open_windows": [[0, None, None, 0, 0] for _ in range(28)]}
                purchased.add(key)
            require(purchased == born[tick], "incomplete purchase inventory")
            active |= purchased
        require(json.loads(next(stream)) == {"complete": True, "tick": stop} and not stream.read(),
                "incomplete/trailing reach trace")
    require(set(seeds) == set(ledger), "missing seed purchases")
    for key, s in seeds.items():
        require(s["samples"] == ((s["end_tick"] or stop) - s["birth_tick"]) // STEP, "reach lifetime gap")
        for field in ("samples", "masks", "open_elsewhere_checks"):
            require(s[field] == old[key][field], "reach checks disagree with recruitment trace: " + field)
        mature = Counter()
        for encoded, n in s["mature_sites"].items():
            mature[str(sites_decode(encoded)[s["column"]])] += n
        require(mature == old[key]["mature_masks"], "mature masks disagree with recruitment trace")
        for field in ("masks", "mature_sites"):
            s[field] = dict(sorted(s[field].items()))
        s["open_windows"] = [w[:4] for w in s["open_windows"]]
        s["opportunities"] = opportunities(s)
    rows = [seeds[key] for key in ledger]
    late = [s for s in rows if s["outcome"] == "expired" and 62 * DAY < s["end_tick"] <= 190 * DAY]
    return {"ecology_samples": stop // STEP, "seed_samples": sum(s["samples"] for s in rows),
            "seeds": rows, "summary": {"all_seeds": summarize(rows), "late_expired": summarize(late)}}


def run_panel(binary, inputs, root, jobs, *, controls=True):
    panel, archive, previous = load_inputs(inputs)
    require(not root.exists(), "fresh panel required")
    (root / "models").mkdir(parents=True)
    models = previous["models"]
    for key, m in models.items():
        path = root / "models" / (key + ".tgl")
        with path.open("xb") as stream:
            stream.write(archive[m["model"]])
        require(digest(path) == m["sha256"], "model identity mismatch")
    def one(saved):
        case, model, name = saved["case"], saved["model"], saved["id"]
        args = ("replay", "models/" + model + ".tgl", case["scenario"], "0x" + case["seed"],
                "--ticks", STOP, "--climate", case["climate"], "--ledger")
        result = prior.training.native(binary, root, *args, "--reach-trace", name + ".jsonl",
                                       "--recruitment-trace", name + "-recruitment.jsonl")
        require(result == saved["result"], "frozen recruitment trajectory differs")
        prior.check_history(result, panel["evaluations"][model]["worlds"][case["id"]], case, models[model]["metadata"])
        compress(root / (name + "-recruitment.jsonl"), root / (name + "-recruitment.jsonl.gz"))
        (root / (name + "-recruitment.jsonl")).unlink()
        require(digest(root / (name + "-recruitment.jsonl.gz")) == saved["trace_sha256"], "old raw trace differs")
        if controls:
            require(prior.training.native(binary, root, *args) == result, "reach tracing changes world")
            repeated = prior.training.native(binary, root, *args, "--reach-trace", name + "-repeat.jsonl")
            require(repeated == result and digest(root / (name + ".jsonl")) == digest(root / (name + "-repeat.jsonl")),
                    "repeated reach trace differs")
            compress(root / (name + "-repeat.jsonl"), root / (name + "-repeat.jsonl.gz"))
            (root / (name + "-repeat.jsonl")).unlink()
        value = analyze_trace(root / (name + ".jsonl"), result, saved["audit"])
        compress(root / (name + ".jsonl"), root / (name + ".jsonl.gz"))
        (root / (name + ".jsonl")).unlink()
        require(digest(root / "models" / (model + ".tgl")) == models[model]["sha256"], "model changed during replay")
        write_json(root / (name + ".json"), result)
        print(name + ": exact historical replay, old trace and parent reach", flush=True)
        return {k: saved[k] for k in ("id", "model", "case")} | {"result": result, "audit": value,
            "trace_sha256": digest(root / (name + ".jsonl.gz")), "recruitment_trace_sha256": saved["trace_sha256"]}
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        worlds = list(pool.map(one, previous["worlds"]))
    return {"schema_version": 1, "rule": RULE, "inputs": INPUTS, "plan": previous["plan"],
            "models": models, "worlds": worlds, "open_window_fields": ["checks", "first_tick", "last_tick", "longest_checks"]}


def collect(build, inputs, output, jobs):
    require(1 <= jobs <= 4 and not output.exists() and
            (output.is_relative_to(ROOT / "artifacts") or not output.is_relative_to(ROOT)), "fresh output/jobs 1..4 required")
    load_inputs(inputs)
    binary, cache = build / "toy-factory-garden-landing", build / "CMakeCache.txt"
    flags = prior.training.check_flags(cache)
    sources = source_files()
    identities = {"binary": digest(binary), "cache": digest(cache)}
    output.mkdir(parents=True)
    try:
        (output / "bin").mkdir()
        (output / "inputs").mkdir()
        shutil.copy2(binary, output / "bin/garden-landing")
        shutil.copy2(cache, output / "CMakeCache.txt")
        shutil.copy2(ROOT / PROTOCOL, output / "protocol.md")
        for name in INPUTS:
            shutil.copy2(inputs / name, output / "inputs" / name)
        for path in (ROOT / "sim").glob("*.py"):
            (output / "sim").mkdir(exist_ok=True)
            shutil.copy2(path, output / "sim" / path.name)
        for name in ("framebuffer_capture.py", "serial_shell.py"):
            target = output / "scripts/container" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / "scripts/container" / name, target)
        snapshot_sources(output, sources)
        result = run_panel(output / "bin/garden-landing", output / "inputs", output / "panel", jobs)
        require(sources == source_files() and digest(binary) == identities["binary"] and digest(cache) == identities["cache"],
                "source/build changed during collection")
        load_inputs(inputs)
        require(digest(output / "bin/garden-landing") == identities["binary"] and
                digest(output / "CMakeCache.txt") == identities["cache"] and
                digest(output / "protocol.md") == sources[PROTOCOL], "frozen source/build mismatch")
        write_json(output / "results.json", result)
        write_json(output / "manifest.json", {"rule": RULE, "status": "complete", "repeat_verified": True,
            "identities": identities, "build_flags": flags, "source_sha256_at_collection": sources,
            "artifacts": {str(p.relative_to(output)): digest(p) for p in sorted(output.rglob("*")) if p.is_file()}})
    except BaseException as error:
        (output / "FAILED.txt").write_text(str(error) + "\n")
        raise


def verify(output):
    require(not (output / "FAILED.txt").exists(), "incomplete collection")
    manifest = json.loads((output / "manifest.json").read_text())
    require(manifest["rule"] == RULE and manifest["status"] == "complete" and manifest["repeat_verified"], "wrong bundle")
    for name in manifest["artifacts"]:
        artifact(output, manifest, name)
    expected = json.loads((output / "results.json").read_text())
    require(digest(output / "protocol.md") == manifest["source_sha256_at_collection"][PROTOCOL], "protocol mismatch")
    with tempfile.TemporaryDirectory(prefix="landing-reach-verify-") as temporary:
        result = run_panel(output / "bin/garden-landing", output / "inputs", Path(temporary) / "panel", 1, controls=False)
        require(result == expected, "independent frozen reach trace differs")
    for name in manifest["artifacts"]:
        artifact(output, manifest, name)
    print("Verified all twelve historical worlds, parent supports, exact site checks and prior raw traces.")


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
                    (args.inputs or ROOT / "benchmarks/garden-seasons").resolve(), args.out.resolve(),
                    2 if args.jobs is None else args.jobs)
        return 0
    except (OSError, ValueError, RuntimeError, StopIteration, KeyError, TypeError) as error:
        print("reach trace failed: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
