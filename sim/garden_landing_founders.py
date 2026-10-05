#!/usr/bin/env python3
"""Trace frozen founders' construction and reproduction, without a policy change."""

from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import gzip
import io
import json
from pathlib import Path
import shutil
import sys

import garden_landing_species as species
from garden_experiments import compress, digest, snapshot_sources, source_files, write_json
from garden_gallery import artifact
from garden_resources import require

previous = species.previous
adults, training = previous.adults, previous.training
ROOT, DAY, STEP, STOP = species.ROOT, species.DAY, species.STEP, species.STOP
START, END, RESOURCE_END = STEP, 64 * DAY, 2 * DAY
RULE = "garden-landing-founders-v1"
PROTOCOL = "benchmarks/garden-seasons/landing-founders-protocol.md"
BLOCKERS = ("cooldown", "cadence", "bank", "dead", "stress", "light", "generation", "energy", "water", "flower")
ARMS = previous.ARMS


def analyze(rows, result, arm, resource_rows=None, *, budget_mode=0):
    require(type(rows) is list and len(rows) >= 3, "incomplete founder trace")
    require(type(budget_mode) is int and 0 <= budget_mode <= 2, "wrong budget mode")
    if budget_mode:
        from garden_landing_budget import common_view
        common_view(result, "reserve" if budget_mode == 2 else "eligible")
        require(arm == "32", "budget requires 32 nodes")
    else:
        previous.common_view(result, arm)
    founders = {p["id"]: p for p in result["lineages"] if not p["parent"]}
    h = rows[0]
    expected_header = {"schema": "landing-founder-trace-v1", "node_limit": ARMS[arm],
                       "start": h["start"], "stop": h["stop"], "founders": sorted(founders)}
    if budget_mode:
        expected_header.update(schema="landing-budget-founder-trace-v1", budget_mode=budget_mode)
    require(type(h["node_limit"]) is int and h == expected_header, "wrong founder header")
    start, stop = h["start"], h["stop"]
    require(type(start) is int and type(stop) is int and STEP <= start <= stop <= result["tick"] and
            start % STEP == stop % STEP == 0, "invalid founder window")
    require(rows[-1] == {"complete": True, "tick": result["tick"], "run_hash": result["run_hash"]} and
            len(rows) == (stop - start) // STEP + 3, "incomplete/trailing founder trace")
    purchases = {(s["parent"], s["birth_tick"]) for s in result["seeds"] if s["parent"] in founders and
                 start <= s["birth_tick"] <= stop}
    seen_purchases = set()
    resources = {}
    resource_audit = None
    if resource_rows is not None:
        resource_audit = adults.analyze(resource_rows, result)
        resources = {r["tick"]: {p["id"]: p for p in r["plants"]} for r in resource_rows[1:-1]}
    summary = {i: {**p, "living_visits": 0, "masks": Counter(), "queries": 0,
        "projected": Counter(), "projected_depths": Counter(), "raw_actions": Counter(),
        "first_projection": None, "last_projection": None, "first_flower": None,
        "first_ready": None, "purchases": [], "max_flowers": 0, "max_ready": 0,
        "body_changes": [], "last_living_body": None} for i, p in founders.items()}
    if budget_mode:
        for s in summary.values():
            s["budget_denied"] = Counter()
    for tick, row in zip(range(start, stop + 1, STEP), rows[1:-1], strict=True):
        require(set(row) == {"tick", "bids", "reproduction", "bodies"} and type(row["tick"]) is int and
                row["tick"] == tick, "missing/misordered founder sample")
        living = {i for i, p in founders.items() if species.lifetimes.alive(p, tick)}
        bodies = {b["id"]: b for b in row["bodies"]}
        prior_flowers = {i: (s["last_living_body"]["body"]["flowers"] if s["last_living_body"] else
                            0 if start == STEP else None) for i, s in summary.items()}
        visits = {v["id"]: v for v in row["reproduction"]}
        require(set(bodies) == living and len(bodies) == len(row["bodies"]) and
                len(visits) == len(row["reproduction"]) and set(visits) <= set(founders) and
                living <= set(visits), "founder inventory mismatch")
        for i, b in bodies.items():
            require(set(b) == {"id", "species", "nodes", "roots", "flowers", "maximum_stem_depth", "tips"} and
                    b["species"] == founders[i]["species"] and
                    all(type(b[k]) is int and b[k] >= 0 for k in ("nodes", "roots", "flowers", "maximum_stem_depth")) and
                    0 <= b["roots"] <= b["nodes"] <= (32 if arm == "32" else 256) and
                    b["flowers"] <= b["nodes"] - b["roots"], "invalid living body")
            tips = b["tips"]
            require(len(tips) <= b["nodes"] and len({t[0] for t in tips}) == len(tips) and
                    all(adults.vector(t, 3) and t[0] < 256 and t[1] in (0, 1) and t[2] <= 255 and
                        (t[1] == 1 or t[2] <= b["maximum_stem_depth"]) for t in tips), "invalid active tips")
            shape = {k: b[k] for k in ("nodes", "roots", "flowers", "maximum_stem_depth")} | {
                "tips": sorted(t[1:] for t in tips)}
            s = summary[i]
            if not s["body_changes"] or s["body_changes"][-1]["body"] != shape:
                s["body_changes"].append({"tick": tick, "body": shape})
            s["last_living_body"] = {"tick": tick, "body": shape}
            if tick in resources:
                r = resources[tick][i]
                require((b["nodes"], b["roots"]) == (r["stages"][-1][4], r["roots"]), "body/resource mismatch")
        for i, v in visits.items():
            require(set(v) == {"id", "blockers", "energy", "water", "energy_required", "water_required",
                "immature", "spent", "ready", "flower", "cooldown", "bank", "stress", "sun", "produced"} and
                type(v["produced"]) is bool and all(type(n) is int and n >= 0 for k, n in v.items() if k != "produced"),
                "invalid reproduction receipt")
            require(v["energy"] <= 256 and v["water"] <= 512 and v["bank"] <= 8 and v["stress"] <= 8 and
                    v["sun"] <= 255 and (v["flower"] < 256 or v["flower"] == 65535), "invalid reproduction ranges")
            blocked = (v["cooldown"] > 0, tick % (4 * STEP) != 0, v["bank"] >= 8, i not in living,
                       v["stress"] > 0, v["sun"] <= 24, False, v["energy"] < v["energy_required"],
                       v["water"] < v["water_required"], v["flower"] == 65535)
            require(v["blockers"] == sum((1 << j) for j, b in enumerate(blocked) if b) and
                    v["produced"] == (v["blockers"] == 0), "reproduction gates differ")
            if v["produced"]:
                require((i, tick) in purchases, "purchase missing from ledger")
                seen_purchases.add((i, tick))
            if i not in living:
                continue
            total = v["immature"] + v["spent"] + v["ready"]
            require(total == bodies[i]["flowers"] and (v["ready"] == 0) == (v["flower"] == 65535),
                    "flower inventory mismatch")
            if tick in resources:
                r = resources[tick][i]
                require(r["stages"][3][:2] == [v["energy"], v["water"]] and
                        r["stages"][4][:2] == [v["energy"] - 48 * v["produced"], v["water"] - 24 * v["produced"]],
                        "purchase debit differs")
            s = summary[i]
            s["living_visits"] += 1
            s["masks"][str(v["blockers"])] += 1
            s["max_flowers"] = max(s["max_flowers"], total)
            s["max_ready"] = max(s["max_ready"], v["ready"])
            if total and s["first_flower"] is None:
                s["first_flower"] = tick
            if v["ready"] and s["first_ready"] is None:
                s["first_ready"] = tick
            if v["produced"]:
                s["purchases"].append(tick)
        bid_keys = set()
        for raw_bid in row["bids"]:
            b = {k: v for k, v in raw_bid.items() if not (budget_mode and k == "budget")}
            require(set(b) == {"id", "tip", "tissue", "depth", "maximum_depth", "flower_depth", "nodes", "roots",
                "shoots", "energy", "water", "available", "raw_action", "action", "priority"} and
                all(type(n) is int for n in b.values()) and b["id"] in living and b["tissue"] in (0, 1) and
                b["raw_action"] in (0, 1, 2) and b["action"] in (0, 1, 2) and
                b["nodes"] == b["roots"] + b["shoots"] and 0 <= b["nodes"] <= 256 and
                0 <= b["roots"] <= b["nodes"] and 0 <= b["energy"] <= 256 and 0 <= b["water"] <= 512 and
                all(0 <= b[k] <= 255 for k in ("depth", "maximum_depth", "flower_depth")) and
                -32768 <= b["priority"] <= 32767 and
                0 <= b["available"] <= 5 and 0 <= b["tip"] < 256, "invalid founder bid")
            key = (b["id"], b["tip"])
            require(key not in bid_keys, "duplicate founder tip query")
            bid_keys.add(key)
            capped = not budget_mode and arm == "32" and b["nodes"] >= 32 and b["raw_action"] == 1 and b["available"] > 0
            require(b["action"] == (0 if capped else b["raw_action"]), "projection differs")
            s = summary[b["id"]]
            s["queries"] += 1
            s["raw_actions"][str(b["raw_action"])] += 1
            if capped:
                kind = "root" if b["tissue"] else "stem"
                s["projected"][kind] += 1
                s["projected_depths"][f"{kind}:{b['depth']}:{b['flower_depth']}"] += 1
                if s["first_projection"] is None:
                    s["first_projection"] = {"tick": tick, "bid": b}
                s["last_projection"] = {"tick": tick, "bid": b}
            if budget_mode:
                budget = raw_bid["budget"]
                require(set(budget) == {"leader", "remaining", "required", "flower", "allocates", "allowed"} and
                        all(type(budget[k]) is bool for k in ("flower", "allocates", "allowed")) and
                        all(type(budget[k]) is int and budget[k] >= 0 for k in ("leader", "remaining", "required")),
                        "invalid budget receipt")
                shoots = [v for v in row["bids"] if v["id"] == b["id"] and v["tissue"] == 0]
                leader = min(shoots, key=lambda v: (-v["depth"], v["tip"])) if shoots and budget_mode == 2 else None
                require(budget["leader"] == (leader["tip"] if leader else 65535), "wrong shoot leader")
                if budget_mode == 1:
                    require(not budget["flower"], "cap-only reservation")
                elif prior_flowers[b["id"]] is not None:
                    require(budget["flower"] == (prior_flowers[b["id"]] > 0), "wrong reservation release")
                remaining = max(0, leader["maximum_depth"] - leader["depth"]) if leader and not budget["flower"] else 0
                allocates = b["raw_action"] == 1 and b["available"] > 0
                needed = b["nodes"] + (1 + remaining - int(budget["leader"] == b["tip"] and remaining > 0)
                                       if allocates else 0)
                allowed = not allocates or needed <= 32
                require((budget["remaining"], budget["required"], budget["allocates"], budget["allowed"]) ==
                        (remaining, needed, allocates, allowed), "budget arithmetic differs")
                if not allowed:
                    s["budget_denied"]["root" if b["tissue"] else "stem"] += 1
        if budget_mode:
            for i in {b["id"] for b in row["bids"]}:
                bids = [b for b in row["bids"] if b["id"] == i]
                eligible = [b for b in bids if b["budget"]["allowed"]]
                # Founder water eligibility is unrestricted; only descendants
                # use the first-day water floor. max keeps the first tied bid.
                winner = max(eligible or bids, key=lambda b: b["priority"])
                allocating = bool(eligible) and winner["budget"]["allocates"]
                require(bodies[i]["nodes"] == winner["nodes"] + allocating, "selected allocation differs")
        require(len(row["bids"]) <= 256, "query capacity exceeded")
    require(seen_purchases == purchases, "missing founder purchase")
    for s in summary.values():
        s["blocker_checks"] = {b: sum(n for mask, n in s["masks"].items() if int(mask) & (1 << j))
                               for j, b in enumerate(BLOCKERS)}
        s["flower_only_checks"] = s["masks"].get("512", 0)
        s["living_history_complete"] = start == STEP and s["death_tick"] is not None and s["death_tick"] <= stop
        s["trace_right_censored"] = s["death_tick"] is None or s["death_tick"] > stop
        expected = len(range(start, min(stop + STEP, s["death_tick"] or stop + STEP), STEP))
        require(s["living_visits"] == expected, "living visit coverage mismatch")
        for k in ("masks", "projected", "projected_depths", "raw_actions"):
            s[k] = dict(sorted(s[k].items()))
        if budget_mode:
            s["budget_denied"] = dict(sorted(s["budget_denied"].items()))
    return {"start": start, "stop": stop, "samples": len(rows) - 2,
            "founders": list(summary.values()), "early_resource_audit": resource_audit}


def write_gzip(path, value):
    with path.open("xb") as raw:
        with gzip.GzipFile(filename="", fileobj=raw, mode="wb", mtime=0) as zipped:
            with io.TextIOWrapper(zipped, encoding="utf-8") as stream:
                json.dump(value, stream, sort_keys=True, separators=(",", ":"))
                stream.write("\n")


def collect(build, out, jobs):
    require(1 <= jobs <= 4 and not out.exists() and
            (out.is_relative_to(ROOT / "artifacts") or not out.is_relative_to(ROOT)), "fresh output/jobs 1..4 required")
    saved = species.load(ROOT / species.INPUT)
    models = previous.load_inputs(ROOT / "benchmarks/garden-seasons")[0]
    binary, cache = build / "toy-factory-garden-landing", build / "CMakeCache.txt"
    settings = previous.water.check_build(cache)
    require(settings["CMAKE_HOME_DIRECTORY"] == str(ROOT / "sim"), "wrong build source")
    sources, identities = source_files(), {"binary": digest(binary), "cache": digest(cache)}
    out.mkdir(parents=True)
    try:
        for folder in ("bin", "models", "frames"):
            (out / folder).mkdir()
        frozen = out / "bin/garden-landing"
        shutil.copy2(binary, frozen)
        shutil.copy2(cache, out / "CMakeCache.txt")
        shutil.copy2(ROOT / PROTOCOL, out / "protocol.md")
        shutil.copy2(ROOT / species.INPUT, out / "input.json.gz")
        snapshot_sources(out, sources)
        for key, meta in saved["models"].items():
            with (out / "models" / (key + ".tgl")).open("xb") as stream:
                stream.write(models[meta["model"]])
            require(digest(out / "models" / (key + ".tgl")) == meta["sha256"], "wrong model")

        def one(w):
            arms = {}
            for arm in ARMS:
                stem = arm + "--" + w["id"]
                args = ("growth-replay", "models/" + w["model"] + ".tgl", w["case"]["scenario"],
                        "0x" + w["case"]["seed"], "--climate", w["case"]["climate"], "--node-limit", arm, "--ledger")
                require(training.native(frozen, out, *args, "--ticks", 0) == w["initial"][arm], "initial changed")
                path, early, raw = out / (stem + ".jsonl"), out / (stem + "-early.jsonl"), out / "frames" / (stem + ".raw")
                options = ("--founder-start", START, "--founder-stop", END,
                           "--adult-start", START, "--adult-stop", RESOURCE_END)
                result = training.native(frozen, out, *args, "--ticks", STOP, "--founder-trace", path,
                                         "--adult-trace", early, *options, "--framebuffer", raw)
                require({**result, "framebuffer_crc32": None} == w["arms"][arm]["result"] and
                        digest(raw) == w["arms"][arm]["frame"]["raw_sha256"], "historical trajectory/pixels changed")
                for label in ("plain", "repeat"):
                    dest, repeat, early_repeat = (out / "frames" / (stem + "-" + label + ".raw"),
                        out / (stem + "-repeat.jsonl"), out / (stem + "-early-repeat.jsonl"))
                    value = training.native(frozen, out, *args, "--ticks", STOP, "--framebuffer", dest,
                        *(("--founder-trace", repeat, "--adult-trace", early_repeat, *options) if label == "repeat" else ()))
                    require(value == result and digest(dest) == digest(raw), "observer state/pixel mismatch")
                    if label == "repeat":
                        require(digest(repeat) == digest(path) and digest(early_repeat) == digest(early), "trace repeat differs")
                rows, resource_rows = adults.read_trace(path), adults.read_trace(early)
                audit = analyze(rows, result, arm, resource_rows)
                arms[arm] = {"result": result, "trace": rows, "early_trace": resource_rows, "audit": audit,
                    "trace_sha256": digest(path), "early_sha256": digest(early), "frame_sha256": digest(raw),
                    "history": w["arms"][arm]["history"], "repeat_and_capture_verified": True}
                for p in (path, early, repeat, early_repeat):
                    compress(p, Path(str(p) + ".gz"))
                    p.unlink()
            print(w["id"] + ": exact historical state/pixels, repeated founder gates and early budgets", flush=True)
            return {k: w[k] for k in ("id", "model", "case")} | {"arms": arms}

        with ThreadPoolExecutor(max_workers=jobs) as pool:
            worlds = list(pool.map(one, saved["worlds"]))
        require(source_files() == sources and digest(binary) == digest(frozen) == identities["binary"] and
                digest(cache) == identities["cache"] and digest(ROOT / species.INPUT) == species.INPUT_SHA,
                "sources/build/input changed during collection")
        require(all(digest(out / "models" / (k + ".tgl")) == m["sha256"] for k, m in saved["models"].items()), "model changed")
        value = {"rule": RULE, "input_sha256": species.INPUT_SHA, "protocol_sha256": digest(out / "protocol.md"),
            "build": identities, "settings": settings, "source_sha256": sources, "models": saved["models"],
            "training_runs": 0, "worlds": worlds, "unchanged_comparison": saved["comparison"]}
        write_gzip(out / "results.json.gz", value)
        write_json(out / "manifest.json", {"rule": RULE, "status": "complete", "artifacts": {
            str(p.relative_to(out)): digest(p) for p in sorted(out.rglob("*")) if p.is_file()}})
    except BaseException as error:
        (out / "FAILED.txt").write_text(str(error) + "\n")
        raise


def verify(path):
    if path.is_dir():
        require(not (path / "FAILED.txt").exists(), "incomplete collection")
        manifest = json.loads((path / "manifest.json").read_text())
        require(manifest["rule"] == RULE and manifest["status"] == "complete", "wrong bundle")
        for name in manifest["artifacts"]:
            artifact(path, manifest, name)
        path = path / "results.json.gz"
    with gzip.open(path, "rt") as stream:
        value = json.load(stream)
    saved = species.load(ROOT / species.INPUT)
    require(value["rule"] == RULE and value["input_sha256"] == species.INPUT_SHA and value["training_runs"] == 0 and
            value["protocol_sha256"] == digest(ROOT / PROTOCOL) and value["models"] == saved["models"] and
            value["unchanged_comparison"] == saved["comparison"], "wrong diagnosis")
    for w, old in zip(value["worlds"], saved["worlds"], strict=True):
        require({k: w[k] for k in ("id", "model", "case")} == {k: old[k] for k in ("id", "model", "case")} and
                set(w["arms"]) == set(ARMS), "wrong panel identity")
        for arm, a in w["arms"].items():
            require(a["repeat_and_capture_verified"] is True and
                    {**a["result"], "framebuffer_crc32": None} == old["arms"][arm]["result"] and
                    a["result"]["framebuffer_crc32"] == old["arms"][arm]["frame"]["framebuffer_crc32"] and
                    a["frame_sha256"] == old["arms"][arm]["frame"]["raw_sha256"] and
                    a["history"] == training.score_world(previous.common_view(old["arms"][arm]["result"], arm),
                        w["case"], value["models"][w["model"]]["metadata"]), "historical result/score differs")
            require(a["audit"] == analyze(a["trace"], a["result"], arm, a["early_trace"]) and
                    (a["audit"]["start"], a["audit"]["stop"]) == (START, END) and
                    (a["early_trace"][0]["start"], a["early_trace"][0]["stop"]) == (START, RESOURCE_END), "audit/window differs")
    print("Verified all 24 historical histories, founder construction/gates and early resource accounts (offline).")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path, default=ROOT / "build-host")
    parser.add_argument("--jobs", type=int, default=2)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--out", type=Path)
    group.add_argument("--verify", type=Path)
    args = parser.parse_args()
    try:
        if args.verify:
            verify(args.verify.resolve())
        else:
            collect(args.build.resolve(), args.out.resolve(), args.jobs)
        return 0
    except (OSError, ValueError, RuntimeError, KeyError, TypeError, StopIteration) as error:
        print("founder trace failed: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
