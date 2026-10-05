#!/usr/bin/env python3
"""Parent-reachable alternatives in the frozen shoot-budget final periods."""

from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import gzip
import json
from pathlib import Path
import shutil
import sys

import garden_landing_germination as germination
import garden_landing_reach as reach
from garden_experiments import compress, digest, snapshot_sources, source_files, write_json
from garden_gallery import artifact
from garden_resources import require

ROOT, DAY, STEP, STOP = reach.ROOT, reach.DAY, reach.STEP, reach.STOP
START, END, ARMS = germination.START, germination.END, germination.ARMS
budget = germination.previous
RULE = "garden-landing-budget-reach-v1"
PROTOCOL = "benchmarks/garden-seasons/landing-budget-reach-protocol.md"
INPUTS = {germination.INPUT: germination.INPUT_SHA, germination.WINDOWS: germination.WINDOWS_SHA}


def load_inputs():
    return tuple(germination.load(ROOT / name, sha) for name, sha in INPUTS.items())


def extract_window(path, full, start=START, end=END):
    """Keep original purchases, including carry-in, but only the requested checks."""
    selected = [s for s in full["seeds"] if s["birth_tick"] <= end and
                (s["end_tick"] is None or s["end_tick"] > start)]
    opener = gzip.open if path.suffix == ".gz" else open
    rows = []
    with opener(path, "rt") as stream:
        require(json.loads(next(stream)) == {"schema": "landing-reach-trace-v1"}, "wrong reach schema")
        for line in stream:
            row = json.loads(line)
            if "checks" in row and start < row["tick"] <= end:
                rows.append({"tick": row["tick"], "checks": row["checks"]})
    return {"purchases": [{"birth_tick": s["birth_tick"], **s["purchase"]} for s in selected], "rows": rows}


def analyze_window(result, recruitment_rows, window, start=START, end=END):
    previous = germination.seed_window(result, recruitment_rows, start, end)
    require(set(window) == {"purchases", "rows"}, "wrong reach window")
    seeds = {(s["parent"], s["birth_tick"]): {**s, "mature_sites": Counter(),
             "open_windows": [[0, None, None, 0, 0] for _ in range(28)]} for s in previous["seeds"]}
    plants = {p["id"]: p for p in result["lineages"]}
    seen, traits = set(), {}
    for p in window["purchases"]:
        require(set(p) == {"birth_tick", "parent", "column", "origin", "dispersal", "choices", "sites"},
                "invalid purchase receipt")
        key = p["parent"], p["birth_tick"]
        require(key in seeds and key not in seen, "unknown/duplicate purchase")
        seen.add(key)
        parent, s = plants[p["parent"]], seeds[key]
        require(p["origin"] == parent["column"] and parent["birth_tick"] <= p["birth_tick"] and
                (parent["death_tick"] is None or p["birth_tick"] < parent["death_tick"]), "wrong producing parent")
        require(p["choices"] == reach.support(p["origin"], p["dispersal"]) and
                p["column"] == s["column"] and p["column"] in p["choices"], "wrong parent support")
        require(traits.setdefault(p["parent"], p["dispersal"]) == p["dispersal"], "parent trait changed")
        reach.sites_decode(p["sites"])
        s["purchase"] = {k: v for k, v in p.items() if k != "birth_tick"}
    require(seen == set(seeds) and len(window["rows"]) == len(recruitment_rows), "incomplete reach window")
    open_ticks, reachable_ticks, alternative_ticks = set(), set(), set()
    for row, old in zip(window["rows"], recruitment_rows, strict=True):
        require(set(row) == {"tick", "checks"} and type(row["tick"]) is int and row["tick"] == old["tick"] and
                len(row["checks"]) == len(old["seeds"]), "missing/reordered reach samples")
        tick = row["tick"]
        for values, receipt in zip(row["checks"], old["seeds"], strict=True):
            require(len(values) == 7 and all(type(v) is int for v in values[:6]) and
                    values[:4] == receipt[:4] and values[4:6] == receipt[8:10], "sequential seed receipt differs")
            parent, age, column, mask, outcome, _, encoded = values
            s = seeds[parent, tick - age * STEP]
            if outcome == 1:
                require(encoded is None, "expiry must not invent site checks")
                continue
            sites = reach.sites_decode(encoded)
            require(sites[column] == mask & ~1 and sum(v == 0 for v in sites) == receipt[10],
                    "site masks disagree with actual/global recruitment gates")
            if mask & 1:
                continue
            s["mature_sites"][encoded] += 1
            opened = {c for c, value in enumerate(sites) if not value}
            reachable = opened & set(s["purchase"]["choices"])
            if mask and opened:
                open_ticks.add(tick)
            if mask and reachable:
                reachable_ticks.add(tick)
            if mask and reachable - {column}:
                alternative_ticks.add(tick)
            for c in opened:
                w = s["open_windows"][c]
                w[4] = w[4] + 1 if w[2] == tick - STEP else 1
                w[0] += 1
                if w[1] is None:
                    w[1] = tick
                w[2], w[3] = tick, max(w[3], w[4])
    for s in seeds.values():
        hist = Counter()
        for encoded, n in s["mature_sites"].items():
            hist[str(reach.sites_decode(encoded)[s["column"]])] += n
        require(hist == s["mature_masks"], "clipped mature masks differ")
        s["mature_sites"] = dict(sorted(s["mature_sites"].items()))
        s["open_windows"] = [w[:4] for w in s["open_windows"]]
        s["opportunities"] = reach.opportunities(s)
    rows = list(seeds.values())

    def summarize(selected):
        # Do not label a seed by a fate after the audited interval.
        return reach.summarize([{**s, "outcome": s["outcome_at_window_end"]} for s in selected])

    return {"window_ticks": [start, end], "ecology_samples": len(recruitment_rows), "seeds": rows,
            "summary": {"all": summarize(rows),
                "by_cohort": {c: summarize([s for s in rows if s["cohort"] == c]) for c in ("carry_in", "purchased")},
                "by_outcome": {o: summarize([s for s in rows if s["outcome_at_window_end"] == o])
                               for o in ("expired", "germinated", "pending")}},
            "blocked_seed_ecology_samples_with": {"global_open": len(open_ticks),
                "reachable_open": len(reachable_ticks), "alternative_open": len(alternative_ticks)}}


def check_value(value, data, windows):
    require(value["rule"] == RULE and value["inputs"] == INPUTS and value["training_runs"] == 0 and
            value["native_runs"] == 36 and value["models"] == data["models"] and
            value["protocol_sha256"] == digest(ROOT / PROTOCOL) and value["window_ticks"] == [START, END],
            "wrong reach comparison")
    for w, old, excerpt in zip(value["worlds"], germination.panel(data), windows["worlds"], strict=True):
        require({k: w[k] for k in ("id", "model", "case")} == {k: old[k] for k in ("id", "model", "case")} and
                w["id"] == excerpt["id"] and set(w["arms"]) == set(ARMS), "wrong reach panel")
        for arm in ARMS:
            a, saved = w["arms"][arm], old["arms"][arm]
            require(a["recruitment_sha256"] == saved["trace_sha256"] == excerpt["arms"][arm]["trace_sha256"] and
                    a["frame_raw_sha256"] == saved["frame"]["raw_sha256"] and a["repeat_and_plain_verified"] is True,
                    "historical receipts/pixels differ")
            budget.common_view(saved["result"], arm)
            require(a["audit"] == analyze_window(saved["result"], excerpt["arms"][arm]["rows"], a["window"]),
                    "saved reach audit differs")


def collect(build, out, jobs):
    require(1 <= jobs <= 4 and not out.exists() and
            (out.is_relative_to(ROOT / "artifacts") or not out.is_relative_to(ROOT)), "fresh output/jobs 1..4 required")
    data, windows = load_inputs()
    model_bytes, _, _, _ = budget.growth.load_inputs(ROOT / "benchmarks/garden-seasons")
    source, cache = build / "toy-factory-garden-landing", build / "CMakeCache.txt"
    settings = budget.growth.water.check_build(cache)
    require(settings["CMAKE_HOME_DIRECTORY"] == str(ROOT / "sim"), "wrong source tree")
    sources, identities = source_files(), {"binary": digest(source), "cache": digest(cache)}
    out.mkdir(parents=True)
    try:
        for name in ("bin", "models", "inputs", "frames"):
            (out / name).mkdir()
        binary = out / "bin/garden-landing"
        shutil.copy2(source, binary)
        shutil.copy2(cache, out / "CMakeCache.txt")
        shutil.copy2(ROOT / PROTOCOL, out / "protocol.md")
        snapshot_sources(out, sources)
        for name, sha in INPUTS.items():
            shutil.copy2(ROOT / name, out / "inputs" / Path(name).name)
            require(digest(out / "inputs" / Path(name).name) == sha, "input changed")
        for key, meta in data["models"].items():
            with (out / "models" / (key + ".tgl")).open("xb") as stream:
                stream.write(model_bytes[meta["model"]])
            require(digest(out / "models" / (key + ".tgl")) == meta["sha256"], "model changed")
        excerpts = {w["id"]: w for w in windows["worlds"]}

        def one(w):
            arms = {}
            for arm in ARMS:
                old, stem = w["arms"][arm], arm + "--" + w["id"]
                args = ("budget-replay", "models/" + w["model"] + ".tgl", w["case"]["scenario"],
                        "0x" + w["case"]["seed"], "--climate", "seasonal", "--ledger", "--ticks", STOP,
                        "--shoot-reserve", "on" if arm == "reserve" else "off")
                path, children, repeat = (out / (stem + suffix) for suffix in
                                         (".jsonl", "-children.jsonl", "-repeat.jsonl"))
                result = budget.training.native(binary, out, *args, "--reach-trace", path,
                                                "--recruitment-trace", children)
                require(result == old["result"], "historical state/ledger differs")
                write_json(out / (stem + "-result.json"), result)
                compress(children, Path(str(children) + ".gz"))
                children.unlink()
                require(digest(Path(str(children) + ".gz")) == old["trace_sha256"], "historical recruitment differs")
                for suffix, options in (("plain", ()), ("repeat", ("--reach-trace", repeat))):
                    raw = out / "frames" / (stem + "-" + suffix + ".raw")
                    image = budget.training.native(binary, out, *args, *options, "--framebuffer", raw)
                    require({**image, "framebuffer_crc32": None} == result and
                            image["framebuffer_crc32"] == old["frame"]["framebuffer_crc32"] and
                            digest(raw) == old["frame"]["raw_sha256"], "observer changes result/pixels")
                require(digest(path) == digest(repeat), "repeat reach bytes differ")
                full = reach.analyze_trace(path, result, old["audit"])
                budget.founders.write_gzip(out / (stem + "-full-audit.json.gz"), full)
                window = extract_window(path, full)
                audit = analyze_window(result, excerpts[w["id"]]["arms"][arm]["rows"], window)
                for p in (path, repeat):
                    compress(p, Path(str(p) + ".gz"))
                    p.unlink()
                arms[arm] = {"window": window, "audit": audit, "trace_sha256": digest(Path(str(path) + ".gz")),
                    "recruitment_sha256": old["trace_sha256"], "frame_raw_sha256": old["frame"]["raw_sha256"],
                    "full_audit_sha256": digest(out / (stem + "-full-audit.json.gz")), "repeat_and_plain_verified": True}
                print(w["id"] + " / " + arm + ": exact historical state, recruitment, repeat and pixels", flush=True)
            return {k: w[k] for k in ("id", "model", "case")} | {"arms": arms}

        with ThreadPoolExecutor(max_workers=jobs) as pool:
            worlds = list(pool.map(one, germination.panel(data)))
        require(source_files() == sources and digest(source) == digest(binary) == identities["binary"] and
                digest(cache) == identities["cache"] and all(digest(ROOT / p) == sha for p, sha in INPUTS.items()) and
                all(digest(out / "models" / (k + ".tgl")) == m["sha256"] for k, m in data["models"].items()),
                "sources/build/inputs/models changed")
        value = {"rule": RULE, "inputs": INPUTS, "models": data["models"], "window_ticks": [START, END],
            "protocol_sha256": digest(out / "protocol.md"), "build": identities, "settings": settings,
            "source_sha256": sources, "training_runs": 0, "native_runs": 36, "worlds": worlds}
        check_value(value, data, windows)
        budget.founders.write_gzip(out / "results.json.gz", value)
        write_json(out / "manifest.json", {"rule": RULE, "status": "complete", "artifacts": {
            str(p.relative_to(out)): digest(p) for p in sorted(out.rglob("*")) if p.is_file()}})
    except BaseException as error:
        (out / "FAILED.txt").write_text(str(error) + "\n")
        raise


def verify(path):
    bundle = path if path.is_dir() else None
    if bundle:
        require(not (bundle / "FAILED.txt").exists(), "incomplete collection")
        manifest = json.loads((bundle / "manifest.json").read_text())
        require(manifest["rule"] == RULE and manifest["status"] == "complete", "wrong bundle")
        for name in manifest["artifacts"]:
            artifact(bundle, manifest, name)
        path = bundle / "results.json.gz"
    with gzip.open(path, "rt") as stream:
        value = json.load(stream)
    data, windows = load_inputs()
    check_value(value, data, windows)
    if bundle:
        for w, old in zip(value["worlds"], germination.panel(data), strict=True):
            for arm in ARMS:
                a, stem = w["arms"][arm], arm + "--" + w["id"]
                trace = bundle / (stem + ".jsonl.gz")
                require(digest(trace) == digest(bundle / (stem + "-repeat.jsonl.gz")) == a["trace_sha256"] and
                        digest(bundle / (stem + "-children.jsonl.gz")) == a["recruitment_sha256"] and
                        digest(bundle / "frames" / (stem + "-plain.raw")) ==
                        digest(bundle / "frames" / (stem + "-repeat.raw")) == a["frame_raw_sha256"] and
                        json.loads((bundle / (stem + "-result.json")).read_text()) == old["arms"][arm]["result"],
                        "bundle parity evidence differs")
                full = reach.analyze_trace(trace, old["arms"][arm]["result"], old["arms"][arm]["audit"])
                require(germination.load(bundle / (stem + "-full-audit.json.gz"), a["full_audit_sha256"]) == full and
                        extract_window(trace, full) == a["window"], "full trace/excerpt differs")
        for name in manifest["artifacts"]:
            artifact(bundle, manifest, name)
    print("Verified twelve parent-reach windows against frozen recruitment and endpoint identities" +
          (", plus full trace lifetimes and all bundle hashes." if bundle else " (offline)."))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--jobs", type=int)
    parser.add_argument("--verify", type=Path)
    args = parser.parse_args()
    try:
        if args.verify:
            require(args.out is None and args.build is None and args.jobs is None, "verify takes no overrides")
            verify(args.verify.resolve())
        else:
            require(args.out is not None, "collection requires --out")
            collect((args.build or ROOT / "build-host").resolve(), args.out.resolve(),
                    2 if args.jobs is None else args.jobs)
        return 0
    except (OSError, ValueError, RuntimeError, KeyError, TypeError, StopIteration) as error:
        print("budget reach audit failed: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
