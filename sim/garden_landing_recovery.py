#!/usr/bin/env python3
"""Read-only production gates and resource losses in the frozen vacancy panel."""

from __future__ import annotations

import argparse
from collections import Counter, deque
from concurrent.futures import ThreadPoolExecutor
import gzip
import json
from pathlib import Path
import shutil
import sys
import zlib

import garden_landing_vacancy as previous
from garden_experiments import compress, digest, snapshot_sources, source_files, write_json
from garden_gallery import artifact
from garden_resources import require

ROOT, DAY, STEP, STOP = previous.ROOT, previous.DAY, previous.STEP, previous.STOP
START, END = previous.AT + STEP, 218 * DAY
RULE = "garden-landing-recovery-gates-v1"
PROTOCOL = "benchmarks/garden-seasons/landing-recovery-gates-protocol.md"
INPUT = "benchmarks/garden-seasons/landing-vacancy-results.json.gz"
INPUT_SHA = "f49fa29abdefbc931bbe57937c90c33c2e51c35c573ce3709c9428cee46c6801"
INPUTS = {INPUT: INPUT_SHA, previous.MODELS: previous.MODEL_SHA}
FOCAL = {"single-s6d697833-live": [], "multi-s6d697833-live": [28],
         "single-s6d697834-live": [26], "multi-s6d697834-live": [25],
         "single-s6d697835-live": [40], "multi-s6d697835-live": [29]}
founders = previous.placement.budget.founders
adults, training = founders.adults, founders.training
BLOCKERS = founders.BLOCKERS


def load_inputs():
    saved = previous.prior.germination.load(ROOT / INPUT, INPUT_SHA)
    models = previous.prior.germination.load(ROOT / previous.MODELS, previous.MODEL_SHA)
    require(len(saved["worlds"]) == 6 and set(saved["models"]) == set(FOCAL), "wrong frozen panel")
    return saved, {k: bytes.fromhex(v) for k, v in models.items()}


def present(life, tick, *, living):
    # Publication precedes post-step export, but follows natural death.
    death = life["death_tick"]
    return (life["birth_tick"] <= tick <= life.get("removal_tick", tick) and
            (death is None or tick < death or not living and tick == death))


def analyze(rows, resource_rows, result):
    require(type(rows) is list and len(rows) >= 3, "incomplete stand trace")
    h = rows[0]
    start, stop = h["start"], h["stop"]
    require(h == {"schema": "landing-stand-trace-v1", "node_limit": 32,
                  "start": start, "stop": stop, "budget_mode": 2} and
            type(start) is int and type(stop) is int and STEP <= start <= stop <= result["tick"] and
            start % STEP == stop % STEP == 0, "wrong stand header/window")
    require(rows[-1] == {"complete": True, "tick": result["tick"], "run_hash": result["run_hash"]} and
            len(rows) == (stop - start) // STEP + 3, "incomplete/trailing stand trace")
    resources = adults.analyze(resource_rows, result)
    require((resources["start"], resources["stop"]) == (start, stop), "resource window differs")
    lives = {p["id"]: p for p in result["lineages"]}
    purchases = {(s["parent"], s["birth_tick"]) for s in result["seeds"] if start <= s["birth_tick"] <= stop}
    bought, summaries, climate, days, recent = set(), {}, [], {}, {}
    for tick, row, resource in zip(range(start, stop + 1, STEP), rows[1:-1], resource_rows[1:-1], strict=True):
        require(set(row) == {"tick", "seed_lifetime_ecology_ticks", "climate", "bids", "reproduction", "bodies"} and
                type(row["tick"]) is int and row["tick"] == resource["tick"] == tick and
                row["seed_lifetime_ecology_ticks"] == 8192, "wrong stand sample")
        c = row["climate"]
        require(set(c) == {"version", "mode", "year", "day", "season", "light_percent", "drought", "cold"} and
                c["version"] == 1 and c["mode"] == result["climate"]["mode"] and
                c["year"] == tick // (16 * DAY) and c["day"] == tick // DAY % 16 and
                c["season"] == ("spring", "summer", "autumn", "winter")[resource["season"]] and
                type(c["drought"]) is bool and type(c["cold"]) is bool and c["cold"] == resource["cold"] and
                type(c["light_percent"]) is int and 0 <= c["light_percent"] <= 100, "invalid climate receipt")
        if not climate or climate[-1]["climate"] != c:
            climate.append({"tick": tick, "climate": c})
        d = days.setdefault(str(tick // DAY), {"samples": 0, "minimum_soil_water": 28 * 11 * 255,
            "maximum_soil_water": 0, "first_soil_water": resource["soil_water"], "last_soil_water": 0})
        d["samples"] += 1
        d["minimum_soil_water"] = min(d["minimum_soil_water"], resource["soil_water"])
        d["maximum_soil_water"] = max(d["maximum_soil_water"], resource["soil_water"])
        d["last_soil_water"] = resource["soil_water"]
        rr = {p["id"]: p for p in resource["plants"]}
        living = {i for i, p in lives.items() if present(p, tick, living=True)}
        bodies = {b["id"]: b for b in row["bodies"]}
        visits = {v["id"]: v for v in row["reproduction"]}
        require(len(bodies) == len(row["bodies"]) and set(bodies) == living and
                len(visits) == len(row["reproduction"]) and living <= set(visits) <= set(lives) and
                len(visits) <= 8, "stand inventory mismatch")
        prior_flowers = {i: summaries[i]["last_body"]["flowers"] if i in summaries else
                        0 if lives[i]["birth_tick"] == tick else None for i in living}
        for i, b in bodies.items():
            require(set(b) == {"id", "species", "nodes", "roots", "flowers", "maximum_stem_depth", "tips"} and
                    b["species"] == lives[i]["species"] and
                    all(type(b[k]) is int and b[k] >= 0 for k in ("nodes", "roots", "flowers", "maximum_stem_depth")) and
                    b["roots"] <= b["nodes"] <= 32 and b["flowers"] <= b["nodes"] - b["roots"], "invalid body")
            tips = b["tips"]
            require(len(tips) <= b["nodes"] and len({t[0] for t in tips}) == len(tips) and
                    all(adults.vector(t, 3) and t[0] < 256 and t[1] in (0, 1) and t[2] <= 255 and
                        (t[1] == 1 or t[2] <= b["maximum_stem_depth"]) for t in tips), "invalid tips")
            require((b["nodes"], b["roots"]) == (rr[i]["stages"][-1][4], rr[i]["roots"]), "body/resource mismatch")
            s = summaries.setdefault(i, {**lives[i], "first_tick": tick, "last_tick": tick, "living_visits": 0,
                "masks": Counter(), "ready_window_masks": Counter(), "first_flower": None, "first_ready": None,
                "max_flowers": 0, "max_ready": 0, "purchases": [], "body_changes": [], "last_body": None,
                "queries": 0, "bid_counts": Counter(), "budget_denied": Counter(), "first_denied": None,
                "last_denied": None, "days": {}})
            shape = {k: b[k] for k in ("nodes", "roots", "flowers", "maximum_stem_depth")} | {
                "tips": sorted(t[1:] for t in tips)}
            if s["last_body"] != shape:
                s["body_changes"].append({"tick": tick, "body": shape})
            s["last_body"], s["last_tick"] = shape, tick
        # Seed ageing/germination happens before reproduction. Include only
        # older seeds that did not exit this step, then apply visits in order.
        bank = sum(s["birth_tick"] < tick < (s["end_tick"] or result["tick"] + STEP) for s in result["seeds"])
        for i, v in visits.items():
            require(set(v) == {"id", "blockers", "energy", "water", "energy_required", "water_required", "immature",
                    "spent", "ready", "flower", "cooldown", "bank", "stress", "sun", "produced"} and
                    type(v["produced"]) is bool and all(type(n) is int and n >= 0 for k, n in v.items() if k != "produced") and
                    lives[i]["birth_tick"] <= tick <= lives[i].get("removal_tick", tick), "invalid production visit")
            require(v["energy"] <= 256 and v["water"] <= 512 and v["stress"] <= 8 and v["bank"] == bank <= 8 and
                    v["sun"] == resource["sun"][1] and (v["flower"] < 256 or v["flower"] == 65535), "invalid visit ranges/bank")
            blocked = (v["cooldown"] > 0, tick % (4 * STEP) != 0, bank >= 8, i not in living,
                       v["stress"] > 0, v["sun"] <= 24, lives[i]["generation"] == 65535,
                       v["energy"] < v["energy_required"], v["water"] < v["water_required"], v["flower"] == 65535)
            mask = sum(1 << j for j, b in enumerate(blocked) if b)
            require(v["blockers"] == mask and v["produced"] == (mask == 0), "production gates differ")
            if v["produced"]:
                require((i, tick) in purchases, "purchase missing from ledger")
                bought.add((i, tick))
                bank += 1
            if i not in living:
                continue
            total = v["immature"] + v["spent"] + v["ready"]
            require(total == bodies[i]["flowers"] and (v["ready"] == 0) == (v["flower"] == 65535), "flower inventory differs")
            require(rr[i]["stages"][3][:2] == [v["energy"], v["water"]] and
                    rr[i]["stages"][4][:2] == [v["energy"] - 48 * v["produced"], v["water"] - 24 * v["produced"]],
                    "production debit differs")
            s = summaries[i]
            s["living_visits"] += 1
            s["masks"][str(mask)] += 1
            sd = s["days"].setdefault(str(tick // DAY), {"samples": 0, "masks": Counter(), "purchases": 0, "max_ready": 0})
            sd["samples"] += 1
            sd["masks"][str(mask)] += 1
            sd["purchases"] += v["produced"]
            sd["max_ready"] = max(sd["max_ready"], v["ready"])
            if v["ready"] and not v["cooldown"] and tick % (4 * STEP) == 0 and v["sun"] > 24:
                s["ready_window_masks"][str(mask)] += 1
            s["max_flowers"], s["max_ready"] = max(s["max_flowers"], total), max(s["max_ready"], v["ready"])
            if total and s["first_flower"] is None:
                s["first_flower"] = tick
            if v["ready"] and s["first_ready"] is None:
                s["first_ready"] = tick
            if v["produced"]:
                s["purchases"].append(tick)
        require(bank == resource["bank"], "final production bank differs")
        bid_keys = set()
        for b in row["bids"]:
            require(set(b) == {"id", "tip", "tissue", "depth", "maximum_depth", "flower_depth", "nodes", "roots",
                    "shoots", "energy", "water", "available", "raw_action", "action", "priority", "budget"} and
                    all(type(n) is int for k, n in b.items() if k != "budget") and b["id"] in living and
                    b["tissue"] in (0, 1) and b["raw_action"] == b["action"] and b["action"] in (0, 1, 2) and
                    b["nodes"] == b["roots"] + b["shoots"] and 0 <= b["roots"] <= b["nodes"] <= 32 and
                    0 <= b["energy"] <= 256 and 0 <= b["water"] <= 512 and 0 <= b["tip"] < 256 and
                    0 <= b["available"] <= 5 and -32768 <= b["priority"] <= 32767 and
                    all(0 <= b[k] <= 255 for k in ("depth", "maximum_depth", "flower_depth")), "invalid growth bid")
            key = b["id"], b["tip"]
            require(key not in bid_keys, "duplicate tip query")
            bid_keys.add(key)
            budget = b["budget"]
            require(set(budget) == {"leader", "remaining", "required", "flower", "allocates", "allowed"} and
                    all(type(budget[k]) is bool for k in ("flower", "allocates", "allowed")) and
                    all(type(budget[k]) is int and budget[k] >= 0 for k in ("leader", "remaining", "required")), "invalid budget")
            shoots = [q for q in row["bids"] if q["id"] == b["id"] and q["tissue"] == 0]
            leader = min(shoots, key=lambda q: (-q["depth"], q["tip"])) if shoots else None
            require(budget["leader"] == (leader["tip"] if leader else 65535), "wrong shoot leader")
            if prior_flowers[b["id"]] is not None:
                require(budget["flower"] == bool(prior_flowers[b["id"]]), "wrong reservation release")
            remaining = max(0, leader["maximum_depth"] - leader["depth"]) if leader and not budget["flower"] else 0
            allocating = b["action"] == 1 and b["available"] > 0
            required = b["nodes"] + (1 + remaining - int(b["tip"] == budget["leader"] and remaining > 0) if allocating else 0)
            require((budget["remaining"], budget["required"], budget["allocates"], budget["allowed"]) ==
                    (remaining, required, allocating, not allocating or required <= 32), "budget arithmetic differs")
            s, kind = summaries[b["id"]], "root" if b["tissue"] else "stem"
            s["queries"] += 1
            s["bid_counts"][f"{kind}:action{b['action']}:space{bool(b['available'])}:allowed{budget['allowed']}"] += 1
            if not budget["allowed"]:
                s["budget_denied"][kind] += 1
                if s["first_denied"] is None:
                    s["first_denied"] = {"tick": tick, "bid": b}
                s["last_denied"] = {"tick": tick, "bid": b}
        require(len(bid_keys) <= 256, "query capacity exceeded")
        if tick % (4 * STEP) == 0:
            for i, r in rr.items():
                recent.setdefault(i, deque(maxlen=8)).append({"tick": tick, "climate": c,
                    "soil_water": resource["soil_water"], "plant": r})
    require(bought == purchases, "missing production purchase")
    for i, s in summaries.items():
        s["blocker_checks"] = {b: sum(n for m, n in s["masks"].items() if int(m) & (1 << j)) for j, b in enumerate(BLOCKERS)}
        s["only_blocker_checks"] = {b: s["masks"].get(str(1 << j), 0) for j, b in enumerate(BLOCKERS)}
        s["last_maintenance"] = list(recent.get(i, []))
        expected = sum(present(lives[i], t, living=True) for t in range(start, stop + 1, STEP))
        require(s["living_visits"] == expected, "incomplete living coverage")
    return {"start": start, "stop": stop, "samples": len(rows) - 2, "plants": list(summaries.values()),
            "resources": resources, "climate": climate, "days": days}


def cohorts(world):
    old = [p["id"] for p in world["arms"]["control"]["checkpoints"]["158"]["lineages"]
           if previous.alive(p, previous.AT)]
    early = [p["id"] for p in world["arms"]["vacancy"]["analysis"]["children"]
             if p["birth_tick"] <= 190 * DAY and
             (p["death_tick"] is None or p["death_tick"] > p["birth_tick"] + DAY)]
    require(early == FOCAL[world["model"]], "focal cohort differs from frozen evidence")
    return {"old_control": old, "early_vacancy": early}


def check_value(value):
    saved, _ = load_inputs()
    require(value["rule"] == RULE and value["inputs"] == INPUTS and value["training_runs"] == 0 and
            value["full_replays"] == 36 and value["checkpoint_replays"] == 0 and
            value["models"] == saved["models"] and value["protocol_sha256"] == digest(ROOT / PROTOCOL) and
            len(value["worlds"]) == 6, "wrong recovery audit")
    for w, old in zip(value["worlds"], saved["worlds"], strict=True):
        require({k: w[k] for k in ("id", "model", "case")} == {k: old[k] for k in ("id", "model", "case")} and
                w["cohorts"] == cohorts(old) and set(w["arms"]) == set(previous.ARMS), "wrong panel/cohort")
        for arm, a in w["arms"].items():
            original = old["arms"][arm]
            require(a["result"] == original["result"] and a["frame_sha256"] == original["frames"]["256"]["raw_sha256"] and
                    a["framebuffer_crc32"] == original["frames"]["256"]["framebuffer_crc32"] and
                    a["repeat_plain_historical_verified"] is True, "historical replay differs")
            audit = a["audit"]
            require((audit["start"], audit["stop"], audit["samples"]) == (START, END, (END - START) // STEP + 1) and
                    (audit["resources"]["start"], audit["resources"]["stop"]) == (START, END), "audit window differs")
            lives = {p["id"]: p for p in a["result"]["lineages"]}
            seen = set()
            for p in audit["plants"]:
                i = p["id"]
                require(i in lives and i not in seen and all(p[k] == v for k, v in lives[i].items()), "plant identity differs")
                seen.add(i)
                expected = sum(present(lives[i], t, living=True) for t in range(START, END + 1, STEP))
                require(p["living_visits"] == expected == sum(p["masks"].values()) == sum(d["samples"] for d in p["days"].values()) and
                        p["purchases"] == [s["birth_tick"] for s in a["result"]["seeds"]
                            if s["parent"] == i and START <= s["birth_tick"] <= END], "plant coverage/purchases differ")
                require(p["blocker_checks"] == {b: sum(n for m, n in p["masks"].items() if int(m) & (1 << j))
                        for j, b in enumerate(BLOCKERS)} and
                        p["only_blocker_checks"] == {b: p["masks"].get(str(1 << j), 0) for j, b in enumerate(BLOCKERS)},
                        "blocker totals differ")
                require((p["first_flower"] is None) == (p["max_flowers"] == 0) and
                        (p["first_ready"] is None) == (p["max_ready"] == 0) and
                        p["last_body"] == p["body_changes"][-1]["body"], "flower/body summary differs")
            require(seen == {i for i, p in lives.items() if any(present(p, t, living=True)
                    for t in (START, max(START, p["birth_tick"]))) and p["birth_tick"] <= END}, "missing plant summary")
            for p in audit["resources"]["plants"]:
                for name, b in p["resources"].items():
                    require(b["initial"] + b["income"] == sum(b[k] for k in adults.FIELDS if k not in ("initial", "income")) and
                            all(b[k] == sum(d["resources"][name][k] for d in p["days"].values())
                                for k in adults.FIELDS if k not in ("initial", "final")), "resource aggregate imbalance")


def collect(build, out, jobs):
    require(1 <= jobs <= 4 and not out.exists() and
            (out.is_relative_to(ROOT / "artifacts") or not out.is_relative_to(ROOT)), "fresh output/jobs 1..4 required")
    saved, models = load_inputs()
    source, cache = build / "toy-factory-garden-landing", build / "CMakeCache.txt"
    settings = previous.growth.water.check_build(cache)
    require(settings["CMAKE_HOME_DIRECTORY"] == str(ROOT / "sim"), "wrong source tree")
    sources, identities = source_files(), {"binary": digest(source), "cache": digest(cache)}
    out.mkdir(parents=True)
    try:
        for directory in ("bin", "models", "inputs", "frames"):
            (out / directory).mkdir()
        binary = out / "bin/garden-landing"
        shutil.copy2(source, binary)
        shutil.copy2(cache, out / "CMakeCache.txt")
        shutil.copy2(ROOT / PROTOCOL, out / "protocol.md")
        snapshot_sources(out, sources)
        for name, sha in INPUTS.items():
            shutil.copy2(ROOT / name, out / "inputs" / Path(name).name)
            require(digest(out / "inputs" / Path(name).name) == sha, "wrong frozen input")
        for key, meta in saved["models"].items():
            path = out / "models" / (key + ".tgl")
            with path.open("xb") as stream:
                stream.write(models[meta["model"]])
            require(digest(path) == meta["sha256"], "model identity differs")

        def one(w):
            arms = {}
            for arm in previous.ARMS:
                stem = arm + "--" + w["id"]
                args = ("vacancy-replay" if arm == "vacancy" else "placement-replay", "models/" + w["model"] + ".tgl",
                    w["case"]["scenario"], "0x" + w["case"]["seed"], "--climate", "seasonal", "--ledger",
                    "--shoot-reserve", "on", "--seed-placement", "spacing", "--ticks", STOP)
                if arm == "vacancy":
                    args += ("--vacancy-at", previous.AT, "--vacancy-lineage", previous.TARGETS[w["model"]][0])
                paths, results, pixels = [], [], []
                for label in ("trace", "repeat", "plain"):
                    raw = out / "frames" / (stem + "-" + label + ".raw")
                    extra = ("--framebuffer", raw)
                    traces = []
                    if label != "plain":
                        for kind in ("stand", "adult"):
                            path = out / (stem + "-" + label + "-" + kind + ".jsonl")
                            traces.append(path)
                            extra += ("--" + kind + "-trace", path, "--" + kind + "-start", START, "--" + kind + "-stop", END)
                    results.append(training.native(binary, out, *args, *extra))
                    pixels.append(digest(raw))
                    for path in traces:
                        compressed = Path(str(path) + ".gz")
                        compress(path, compressed)
                        # Only this invocation's uncompressed duplicate; the
                        # original bytes remain losslessly archived beside it.
                        path.unlink()
                    if traces:
                        paths.append([Path(str(p) + ".gz") for p in traces])
                old = w["arms"][arm]
                require(results[0] == results[1] == results[2] and
                        {**results[0], "framebuffer_crc32": None} == old["result"] and
                        results[0]["framebuffer_crc32"] == old["frames"]["256"]["framebuffer_crc32"] and
                        all(p == old["frames"]["256"]["raw_sha256"] for p in pixels) and
                        all(digest(a) == digest(b) for a, b in zip(*paths, strict=True)), "historical/repeat/observer differs")
                result = {**results[0], "framebuffer_crc32": None}
                write_json(out / (stem + "-result.json"), result)
                audit = analyze(*(adults.read_trace(p) for p in paths[0]), result)
                arms[arm] = {"result": result, "audit": audit, "frame_sha256": pixels[0],
                    "framebuffer_crc32": results[0]["framebuffer_crc32"], "repeat_plain_historical_verified": True,
                    "traces": {kind: {"path": p.name, "sha256": digest(p)} for kind, p in zip(("stand", "adult"), paths[0], strict=True)}}
                print(w["model"] + " / " + arm + ": repeated gates, budgets and historical pixels verified", flush=True)
            return {k: w[k] for k in ("id", "model", "case")} | {"cohorts": cohorts(w), "arms": arms}

        with ThreadPoolExecutor(max_workers=jobs) as pool:
            worlds = list(pool.map(one, saved["worlds"]))
        require(source_files() == sources and digest(source) == digest(binary) == identities["binary"] and
                digest(cache) == identities["cache"] and all(digest(ROOT / p) == h for p, h in INPUTS.items()) and
                all(digest(out / "models" / (k + ".tgl")) == m["sha256"] for k, m in saved["models"].items()), "source/build/input changed")
        value = {"rule": RULE, "inputs": INPUTS, "protocol_sha256": digest(out / "protocol.md"), "models": saved["models"],
                 "settings": settings, "build": identities, "source_sha256": sources, "training_runs": 0,
                 "full_replays": 36, "checkpoint_replays": 0, "worlds": worlds}
        check_value(value)
        founders.write_gzip(out / "results.json.gz", value)
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
    check_value(value)
    if bundle:
        require(digest(bundle / "bin/garden-landing") == value["build"]["binary"] and
                digest(bundle / "CMakeCache.txt") == value["build"]["cache"] and
                digest(bundle / "protocol.md") == value["protocol_sha256"], "bundle identity differs")
        for w in value["worlds"]:
            for arm, a in w["arms"].items():
                stem = arm + "--" + w["id"]
                paths = []
                for kind in ("stand", "adult"):
                    p = bundle / (stem + "-trace-" + kind + ".jsonl.gz")
                    require(a["traces"][kind] == {"path": p.name, "sha256": digest(p)} and
                            digest(p) == digest(bundle / (stem + "-repeat-" + kind + ".jsonl.gz")), "trace identity/repeat differs")
                    paths.append(p)
                require(analyze(*(adults.read_trace(p) for p in paths), a["result"]) == a["audit"], "raw reanalysis differs")
                require(json.loads((bundle / (stem + "-result.json")).read_text()) == a["result"], "native result differs")
                for label in ("trace", "repeat", "plain"):
                    raw = bundle / "frames" / (stem + "-" + label + ".raw")
                    require(digest(raw) == a["frame_sha256"] and f"{zlib.crc32(raw.read_bytes()):08x}" == a["framebuffer_crc32"], "pixels differ")
                print(w["model"] + " / " + arm + ": offline raw reanalysis verified", flush=True)
    print("Verified fixed recovery panel, unchanged histories, production gates and resource accounts.")
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--out", type=Path)
    mode.add_argument("--verify", type=Path)
    parser.add_argument("--build", type=Path, default=ROOT / "build-host")
    parser.add_argument("--jobs", type=int, default=2)
    args = parser.parse_args()
    try:
        if args.verify:
            verify(args.verify.resolve())
        else:
            collect(args.build.resolve(), args.out.resolve(), args.jobs)
        return 0
    except (OSError, RuntimeError, ValueError, KeyError, TypeError) as error:
        print("recovery audit failed: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
