#!/usr/bin/env python3
"""Replay frozen shadow packets through versioned input masks; never run a new policy."""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
import gzip
import hashlib
import json
from pathlib import Path
import subprocess

import garden_landing_features as features
import garden_landing_shadow as shadow
from garden_season_confirmation import build_flags
from garden_season_recruitment import digest, identity
from garden_seasons import require, source_hashes

ROOT, DAY, END = shadow.ROOT, shadow.DAY, shadow.END
RULE = "landing-input-encoding-v1"
CONTRACT = "docs/garden-landing-encoding.md"
INPUT = "benchmarks/garden-seasons/landing-shadow-histories.json.gz"
INPUT_SHA = "24c4623c78ebb752f7236324f5f3d9863387357bc86184c2f0c1d3d1719113da"
SUMMARY = "benchmarks/garden-seasons/landing-shadow-summary.json"
SUMMARY_SHA = "bddedac9f56cc99d7ea61935730d1b4c51ac9cbbc2a326446b8cb15aa1c40239"
COUNTS = ("queries", "stems", "roots", "choices", "sources", "cold_stems", "history_added",
          "current_dead_only", "history_dead_only")


def load_input():
    require(digest(ROOT / INPUT) == INPUT_SHA and digest(ROOT / SUMMARY) == SUMMARY_SHA, "Changed shadow evidence")
    report = json.loads(gzip.decompress((ROOT / INPUT).read_bytes()))
    shadow.validate_report(report)
    require(shadow.compact(report) == json.loads((ROOT / SUMMARY).read_text()), "Changed shadow summary")
    return report


def new_stats():
    return {**dict.fromkeys(COUNTS, 0), "separation": {name: [0] * 256 for name in features.NAMES}}


def separation(encoded, available):
    if len(available) < 2:
        return 0
    return max(max(encoded["candidates"][i][f] for i in available) -
               min(encoded["candidates"][i][f] for i in available) for f in range(8))


def add_bid(stats, bid, encoded):
    stats["queries"] += 1
    if bid["kind"] == 1:
        stats["roots"] += 1
        return
    stats["stems"] += 1
    stats["sources"] += bid["packet"]["valid"].bit_count()
    stats["cold_stems"] += bid["packet"]["samples"] == 0
    available = [i for i, (_, flags) in enumerate(bid["candidates"]) if flags & 2]
    if len(available) < 2:
        return
    stats["choices"] += 1
    spans = {name: separation(encoded[name], available) for name in features.NAMES}
    require(spans["off"] == 0 and spans["current"] <= spans["history"] and
            spans["current-no-dead"] <= spans["current"] and spans["history-no-dead"] <= spans["history"] and
            spans["current-no-dead"] <= spans["history-no-dead"], "A mask added information")
    for name, span in spans.items():
        stats["separation"][name][span] += 1
    stats["history_added"] += spans["history"] > 0 and spans["current"] == 0
    stats["current_dead_only"] += spans["current"] > 0 and spans["current-no-dead"] == 0
    stats["history_dead_only"] += spans["history"] > 0 and spans["history-no-dead"] == 0


def merge(rows):
    result = new_stats()
    for row in rows:
        for key in COUNTS:
            result[key] += row[key]
        for name in features.NAMES:
            result["separation"][name] = [a + b for a, b in zip(result["separation"][name], row["separation"][name])]
    return result


def summary(stats):
    return {**{k: v for k, v in stats.items() if k != "separation"}, "masks": {name: {
        "ge_1": sum(hist[1:]), "ge_4": sum(hist[4:]), "ge_16": sum(hist[16:]),
        "max": next((i for i in range(255, -1, -1) if hist[i]), None)}
        for name, hist in stats["separation"].items()}}


def aggregate(cases):
    return {window: {arm: summary(merge(d["stats"] for c in cases if c["arm"] == arm for d in c["days"][start:]))
            for arm in shadow.ARMS} for window, start in (("whole", 0), ("warmed", 1), ("closing", 112))}


def analysis(cases):
    return {"groups": aggregate(cases), "partitions": {field: {value: aggregate(
        [c for c in cases if c["case"][field] == value]) for value in values} for field, values in (
        ("seed", shadow.SEEDS), ("scenario", ("rainfed", "rainfed-crowded")), ("policy", ("baseline", "adaptive")))}}


def native(probe, data):
    result = subprocess.run([str(probe)], input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            check=True, timeout=120)
    require(len(result.stdout) == len(data) // features.REQUEST_SIZE * features.RESPONSE_SIZE,
            "Truncated or extra native response")
    return result.stdout


def replay_case(item):
    probe, bundle, old = item
    trace = shadow.sites.origin.population.path(bundle, old["case"], old["arm"])
    require(digest(trace) == old["trace_sha256"], "Changed dense shadow trace")
    packets, requests, history, worlds = [], bytearray(), None, 0
    with gzip.open(trace, "rt") as stream:
        require(json.loads(next(stream)) == shadow.header(old["case"], old["arm"]), "Changed shadow header")
        for line in stream:
            row = json.loads(line)
            require(row["tick"] == worlds * 15, "Missing, extra or reordered ecology row")
            history = shadow.decode_cache(row["cache"], history)
            require(history.tick == worlds, "Wrong ecology clock")
            for bid in row["bids"]:
                shadow.check_packet(history, bid, old["arm"])
                flags = [c[1] for c in bid["candidates"]]
                packets.append((row["tick"], bid))
                for mode, omit in features.VARIANTS:
                    requests += features.request(bid["kind"], flags, bid["packet"], mode, omit)
            worlds += 1
    require(worlds == old["worlds"] and len(packets) == old["bids"] and
            row["hash"] == old["final_hash"] and row["created"] == old["created"], "Changed horizon/counts")
    data = bytes(requests)
    output = native(probe, data)
    require(output == native(probe, data), "Nonrepeatable native encoding")
    days = [{"stats": new_stats(), "first_stem": None} for _ in range(128)]
    offset = 0
    for tick, bid in packets:
        encoded = {}
        for name, (mode, omit) in zip(features.NAMES, features.VARIANTS):
            error, actual = features.response(output[offset:offset + features.RESPONSE_SIZE])
            offset += features.RESPONSE_SIZE
            expected = features.encode(bid["kind"], [c[1] for c in bid["candidates"]], bid["packet"], mode, omit)
            require(error == 0 and actual == expected, "Native/reference input encoding mismatch")
            encoded[name] = actual
        day = days[(tick - 1) // DAY]
        add_bid(day["stats"], bid, encoded)
        if bid["kind"] == 0 and day["first_stem"] is None:
            day["first_stem"] = {"tick": tick, "bid": bid, "encoded": encoded}
    require(offset == len(output) and digest(trace) == old["trace_sha256"], "Changed stream/input")
    case = {"case": old["case"], "arm": old["arm"], "trace_sha256": old["trace_sha256"],
        "bids": old["bids"], "worlds": worlds, "records": len(packets) * len(features.VARIANTS),
        "requests_sha256": hashlib.sha256(data).hexdigest(), "responses_sha256": hashlib.sha256(output).hexdigest(),
        "days": days}
    validate_case(case, old)
    print("Verified feature encoding " + identity(old["case"]) + " " + old["arm"], flush=True)
    return case


def validate_case(case, old):
    require(all(case[k] == old[k] for k in ("case", "arm", "trace_sha256", "bids", "worlds")) and
            case["records"] == case["bids"] * len(features.VARIANTS) and len(case["days"]) == 128, "Changed panel case")
    for day, prior in zip(case["days"], old["days"]):
        stats = day["stats"]
        require(set(stats) == set(new_stats()) and all(type(stats[k]) is int and stats[k] >= 0 for k in COUNTS) and
                all(stats[k] == prior["stats"][k] for k in ("queries", "stems", "roots", "choices", "sources")) and
                stats["cold_stems"] <= stats["stems"] and set(stats["separation"]) == set(features.NAMES), "Changed daily coverage")
        for name, hist in stats["separation"].items():
            require(len(hist) == 256 and all(type(v) is int and v >= 0 for v in hist) and
                    sum(hist) == stats["choices"], "Invalid separation histogram")
            require(name != "off" or not any(hist[1:]), "Off mask leaked a reading")
            require(case["arm"] != "base" or not any(hist[1:]), "Base origin acquired positional information")
        m = summary(stats)["masks"]
        require(m["history"]["ge_1"] == prior["stats"]["variable"] and
                stats["history_added"] == m["history"]["ge_1"] - m["current"]["ge_1"] and
                stats["current_dead_only"] == m["current"]["ge_1"] - m["current-no-dead"]["ge_1"] and
                stats["history_dead_only"] == m["history"]["ge_1"] - m["history-no-dead"]["ge_1"], "Wrong mask partition")
        for threshold in ("ge_1", "ge_4", "ge_16"):
            require(m["current-no-dead"][threshold] <= m["current"][threshold] <= m["history"][threshold] and
                    m["current-no-dead"][threshold] <= m["history-no-dead"][threshold] <= m["history"][threshold], "Mask gained separation")
        first = day["first_stem"]
        require((first is None) == (prior["first_stem"] is None), "Missing first-stem fixture")
        if first:
            require(first["tick"] == prior["first_stem"]["tick"] and first["bid"] == prior["first_stem"]["bid"], "Changed first-stem selection")
            bid = first["bid"]
            require(first["encoded"] == {name: features.encode(bid["kind"], [c[1] for c in bid["candidates"]],
                bid["packet"], mode, omit) for name, (mode, omit) in zip(features.NAMES, features.VARIANTS)}, "Changed fixture encoding")


def validate_report(report, prior):
    require(report["protocol"] == RULE and report["input_sha256"] == INPUT_SHA and
            len(report["cases"]) == len(prior["cases"]) == 16, "Wrong report identity/coverage")
    for case, old in zip(report["cases"], prior["cases"]):
        validate_case(case, old)
    require(report["analysis"] == analysis(report["cases"]), "Changed analysis")


def compact(report):
    return {**{k: v for k, v in report.items() if k != "cases"}, "cases": [
        {**{k: v for k, v in c.items() if k != "days"}, "days_sha256": hashlib.sha256(
            json.dumps(c["days"], sort_keys=True).encode()).hexdigest()} for c in report["cases"]]}


def frozen(build, prior):
    sources = source_hashes(ROOT)
    sources.update({n: digest(ROOT / n) for n in {CONTRACT, INPUT, SUMMARY,
        "sim/garden_landing_features.py", "sim/garden_landing_encoding.py", "sim/test_garden_landing_features.py",
        *prior["frozen"]["sources"]}})
    for name, sha in prior["frozen"]["sources"].items():
        if name != "sim/CMakeLists.txt":
            require(digest(ROOT / name) == sha, "Changed pre-existing source: " + name)
    flags = build_flags(build / "CMakeCache.txt")
    require(all(v == "OFF" for v in flags.values()), "Use ordinary probe build; no new ecology")
    return {"sources": sources, "build": {"flags": flags, "cache_sha256": digest(build / "CMakeCache.txt"),
        "probe_sha256": digest(build / "toy-factory-garden-landing-features-probe")}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("collect", "verify"))
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--build", type=Path, default=Path("artifacts/build-host-landing-encoding"))
    parser.add_argument("--bundle", type=Path, default=Path("artifacts/garden-landing-shadow"))
    parser.add_argument("--jobs", type=int, default=4)
    args = parser.parse_args()
    require(1 <= args.jobs <= 4, "Require 1..4 independent workers")
    prior = load_input()
    provenance = frozen(args.build, prior)
    if args.command == "collect":
        args.out.mkdir(parents=True, exist_ok=False)
    probe = args.build.resolve() / "toy-factory-garden-landing-features-probe"
    with ProcessPoolExecutor(max_workers=args.jobs) as pool:
        cases = list(pool.map(replay_case, ((probe, args.bundle, c) for c in prior["cases"])))
    require(frozen(args.build, prior) == provenance, "Inputs changed during replay")
    report = {"protocol": RULE, "input_sha256": INPUT_SHA, "frozen": provenance, "cases": cases, "analysis": analysis(cases)}
    validate_report(report, prior)
    output, summarized = args.out / "histories.json.gz", args.out / "summary.json"
    if args.command == "collect":
        output.write_bytes(gzip.compress(json.dumps(report, sort_keys=True, separators=(",", ":")).encode(), mtime=0))
        summarized.write_text(json.dumps(compact(report), indent=2) + "\n")
    else:
        require(report == json.loads(gzip.decompress(output.read_bytes())) and
                compact(report) == json.loads(summarized.read_text()), "Nonrepeatable replay/summary")
    print(f"All {len(cases)} cases verified; bids={sum(c['bids'] for c in cases)}; encodings={sum(c['records'] for c in cases)}", flush=True)


if __name__ == "__main__":
    main()
