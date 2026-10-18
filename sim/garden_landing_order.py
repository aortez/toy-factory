#!/usr/bin/env python3
"""Paired post-day-158 reproduction order screen; frozen models, no training."""

from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import copy
import gzip
import json
from pathlib import Path
import shutil
import sys
import zlib

import garden_landing_bank_access as bank
from garden_experiments import compress, digest, snapshot_sources, source_files, write_json
from garden_gallery import artifact, contact_sheet, rgb565be_to_rgb888, write_png
from garden_resources import require

recovery, previous = bank.previous, bank.previous.previous
ROOT, DAY, STEP, STOP = bank.ROOT, bank.DAY, bank.STEP, bank.STOP
AT, END = previous.AT, recovery.END
RULE = "garden-landing-order-v1"
PROTOCOL = "benchmarks/garden-seasons/landing-order-protocol.md"
ARMS, FRAMES = ("fixed", "rotating"), (158, 192, 256)
INPUTS = {**recovery.INPUTS, bank.INPUT: bank.INPUT_SHA, bank.VISITS: bank.VISITS_SHA}
training = recovery.training


def order_hash(base, after):
    require(type(after) is int and 0 < after <= 0xffffffff and after % 60 == 0,
            "invalid rotation boundary")
    h = 2166136261
    for byte in b"GLR1" + int(base, 16).to_bytes(4, "little") + after.to_bytes(4, "little"):
        h = ((h ^ byte) * 16777619) & 0xffffffff
    return f"{h:08x}"


def common_view(result, arm, after=AT):
    """Check the actual fingerprint before projecting away experiment identity."""
    require(arm in ARMS, "unknown order arm")
    placing = previous.placement
    base = placing.probe_hash(placing.budget.probe_hash(result["base_run_hash"], 2), True)
    value = copy.deepcopy(result)
    if arm == "rotating":
        require(result.get("seed_order_probe") == {"version": 1, "after": after} and
                type(result["seed_order_probe"]["version"]) is int and
                type(result["seed_order_probe"]["after"]) is int, "wrong order config")
        del value["seed_order_probe"]
        expected = order_hash(base, after)
    else:
        require("seed_order_probe" not in result, "fixed arm enabled rotation")
        expected = base
    if "vacancy_probe" in result:
        probe = result["vacancy_probe"]
        require(result["placement_run_hash"] == expected and result["run_hash"] ==
                previous.probe_hash(expected, probe["tick"], probe["lineage"]), "wrong vacancy/order fingerprint")
        value["placement_run_hash"] = base
        value["run_hash"] = previous.probe_hash(base, probe["tick"], probe["lineage"])
    else:
        require(result["run_hash"] == expected, "wrong order fingerprint")
        value["run_hash"] = base
    return value


def check_prefix(fixed, rotating, after=AT):
    a, b = common_view(fixed, "fixed", after), common_view(rotating, "rotating", after)
    require(a["tick"] == b["tick"] == after, "wrong common-prefix endpoint")
    if "vacancy_probe" in a and a["vacancy_probe"]["event"]:
        for key in ("before_run_hash", "after_run_hash"):
            require(b["vacancy_probe"]["event"][key] == order_hash(a["vacancy_probe"]["event"][key], after),
                    "export fingerprint differs")
            b["vacancy_probe"]["event"][key] = a["vacancy_probe"]["event"][key]
    require(a == b, "physical/cache/ledger/pixel prefix differs")


def analyze_order(rows, result, arm, after=AT):
    """Verify recorded traversal against independent physical array inventories."""
    require(type(rows) is list and len(rows) >= 3, "missing ordered trace")
    header = rows[0]
    start, stop = header["start"], header["stop"]
    require(header == {"schema": "landing-ordered-stand-trace-v1", "node_limit": 32,
                       "start": start, "stop": stop, "budget_mode": 2} and arm in ARMS,
            "wrong ordered schema/arm")
    require(rows[-1] == {"complete": True, "tick": result["tick"], "run_hash": result["run_hash"]} and
            len(rows) == (stop - start) // STEP + 3, "incomplete ordered trace")
    visits, ranks, openings = [], {}, []
    plain = [{**header, "schema": "landing-stand-trace-v1"}]
    for row in rows[1:-1]:
        tick, slots, ordered = row["tick"], row["plant_order"], row["reproduction"]
        require(type(slots) is list and len(slots) <= 8 and len(set(slots)) == len(slots) and
                all(type(i) is int and i > 0 for i in slots), "invalid physical array")
        first = ((tick - after) // 60) % len(slots) if (
            arm == "rotating" and tick > after and tick % 60 == 0 and slots) else 0
        require([p["id"] for p in ordered] == slots[first:] + slots[:first], "wrong actual traversal")
        entry = ordered[0]["bank"] if ordered else 0
        eligible, buyers = [], []
        for rank, v in enumerate(ordered):
            if v["blockers"] & 8:
                continue
            p = ranks.setdefault(v["id"], {"id": v["id"], "maintenance": Counter(),
                "eligible": Counter(), "open_eligible": Counter(), "purchased": Counter()})
            if tick % 60 == 0:
                p["maintenance"][str(rank)] += 1
            if not v["blockers"] & ~bank.BANK:
                p["eligible"][str(rank)] += 1
                if entry < 8:
                    p["open_eligible"][str(rank)] += 1
                    eligible.append(v["id"])
            if v["produced"]:
                buyers.append(v["id"])
                p["purchased"][str(rank)] += 1
        if eligible:
            openings.append({"tick": tick, "bank_at_entry": entry, "start": first,
                             "plant_order": slots, "eligible": eligible, "buyers": buyers})
        require(all(set(v) == set(bank.FIELDS) for v in ordered), "wrong visit fields")
        visits.append([tick, [[v[k] for k in bank.FIELDS] for v in ordered]])
        plain.append({k: v for k, v in row.items() if k != "plant_order"})
    plain.append(rows[-1])
    access = bank.analyze_visits(visits, result, start, stop)
    for p in access["plants"]:
        r = ranks[p["id"]]
        require(sum(r["purchased"].values()) == p["access"]["purchased"] and
                sum(r["eligible"].values()) == p["living_visits"] - p["access"]["ineligible"] and
                sum(r["open_eligible"].values()) == p["access"]["purchased"] + p["access"]["earlier_buyers_fill"],
                "rank/access partition differs")
    access.pop("resident_samples")
    return plain, {"access": access, "ranks": list(ranks.values()), "openings": openings}


def outcomes(result):
    lives, seeds = bank.descendants.index_records(result["lineages"], result["seeds"], 0, result["tick"])
    rows = []
    for p in lives.values():
        if p["birth_tick"] <= AT:
            continue
        children = [c for c in lives.values() if c["parent"] == p["id"]]
        purchases = [s for s in seeds.values() if s["parent"] == p["id"]]
        rows.append({**p, "outcome": bank.child_status(p, result["tick"]),
            "children": [c["id"] for c in children],
            "confirmed_children": [c["id"] for c in children if bank.child_status(c, result["tick"]) == "confirmed"],
            "child_outcomes": dict(Counter(bank.child_status(c, result["tick"]) for c in children)),
            "seed_outcomes": dict(Counter(s["outcome"] for s in purchases))})
    early = [p for p in rows if p["birth_tick"] <= 190 * DAY]
    survivors = [p for p in early if p["outcome"] == "confirmed"]
    periods = []
    for a, z in previous.PERIODS:
        cohort = [p for p in rows if a * DAY < p["birth_tick"] <= z * DAY]
        periods.append({"days": [a, z], "births": [p["id"] for p in cohort],
            "birth_outcomes": dict(Counter(p["outcome"] for p in cohort)),
            "confirmations": [p["id"] for p in rows if a * DAY < p["birth_tick"] + DAY <= z * DAY and p["outcome"] == "confirmed"],
            "natural_deaths": [p["id"] for p in lives.values() if p["death_tick"] is not None and a * DAY < p["death_tick"] <= z * DAY],
            "living_at_end": [p["id"] for p in lives.values() if previous.alive(p, z * DAY)],
            "credit": previous.credit(result["lineages"], a * DAY, z * DAY)})
    return {"children": rows, "birth_outcomes": dict(Counter(p["outcome"] for p in rows)),
        "early_ids": [p["id"] for p in early], "early_survivors": [p["id"] for p in survivors],
        "early_seed_parents": [p["id"] for p in survivors if p["seeds_created"]],
        "early_successful_parents": [p["id"] for p in survivors if p["confirmed_children"]],
        "early_seed_outcomes": dict(sum((Counter(p["seed_outcomes"]) for p in survivors), Counter())),
        "early_child_outcomes": dict(sum((Counter(p["child_outcomes"]) for p in survivors), Counter())),
        "reproducing_replacements": [p["id"] for p in rows if p["confirmed_children"]],
        "post_boundary_deaths": sum(p["death_tick"] is not None and p["death_tick"] > AT for p in lives.values()),
        "living_at_stop": [p["id"] for p in lives.values() if previous.alive(p, result["tick"])],
        "incumbents": [p for p in lives.values() if p["birth_tick"] <= AT and
                       (p["death_tick"] is None or p["death_tick"] > AT)],
        "periods": periods}


def analyze(stand, adult, result, arm):
    plain, order = analyze_order(stand, result, arm)
    return {"order": order, "gates": recovery.analyze(plain, adult, result), "outcomes": outcomes(result)}


def check_historical(audit, old):
    expected = old["analysis"]
    actual = audit["outcomes"]
    require(actual["reproducing_replacements"] == expected["reproducing_replacements"] and
            actual["living_at_stop"] == expected["living_at_stop"], "historical offspring summary differs")
    for a, b in zip(actual["periods"], expected["periods"], strict=True):
        require(a["births"] == b["birth_ids"] and all(a[k] == b[k] for k in
                ("days", "confirmations", "natural_deaths", "living_at_end", "credit")), "historical period differs")


def summarize(worlds):
    totals = {}
    for arm in ARMS:
        selected = [group[arm]["audit"]["outcomes"] for w in worlds for group in w["contexts"].values()]
        totals[arm] = {"early_survivors": sum(len(a["early_survivors"]) for a in selected),
            "early_seed_parents": sum(len(a["early_seed_parents"]) for a in selected),
            "early_successful_parents": sum(len(a["early_successful_parents"]) for a in selected),
            "new_reproducing_parents": sum(len(a["reproducing_replacements"]) for a in selected),
            "closing_confirmations": sum(len(a["periods"][-1]["confirmations"]) for a in selected),
            "birth_outcomes": dict(sum((Counter(a["birth_outcomes"]) for a in selected), Counter()))}
    a, b = totals["fixed"], totals["rotating"]
    gates = {"early_established_parents_gain": b["early_successful_parents"] > a["early_successful_parents"],
             "retain_reproducing_parents": b["new_reproducing_parents"] >= a["new_reproducing_parents"],
             "retain_closing_confirmations": b["closing_confirmations"] >= a["closing_confirmations"]}
    return {"totals": totals, "gates": gates, "passes_screen": all(gates.values())}


def load_inputs():
    saved, models = recovery.load_inputs()
    frozen = bank.load(ROOT / bank.INPUT, bank.INPUT_SHA)
    visits = bank.load(ROOT / bank.VISITS, bank.VISITS_SHA)
    return saved, models, frozen, visits


def check_value(value):
    saved, _, _, _ = load_inputs()
    require(value["rule"] == RULE and value["inputs"] == INPUTS and value["training_runs"] == 0 and
            value["full_replays"] == 72 and value["checkpoint_replays"] == 48 and
            value["models"] == saved["models"] and value["protocol_sha256"] == digest(ROOT / PROTOCOL) and
            len(value["worlds"]) == 6 and value["summary"] == summarize(value["worlds"]), "wrong order screen")
    for w, old in zip(value["worlds"], saved["worlds"], strict=True):
        require(all(w[k] == old[k] for k in ("id", "model", "case")) and
                set(w["contexts"]) == set(previous.ARMS), "wrong panel/context")
        expected_calls = [(context + "-" + arm + "--" + w["id"] + "-" + label, tick)
                          for context in previous.ARMS for arm in ARMS
                          for label, tick in (("day158", AT), ("day192", 192 * DAY),
                                              ("trace", STOP), ("repeat", STOP), ("plain", STOP))]
        require([(c["name"], c["tick"]) for c in w["calls"]] == expected_calls, "call budget/order differs")
        for context, pair in w["contexts"].items():
            require(set(pair) == set(ARMS), "wrong order arms")
            for arm, a in pair.items():
                require(set(a["checkpoints"]) == {"158", "192"} and set(a["frames"]) == {"158", "192", "256"} and
                        a["repeat_plain_verified"] is True and a["audit"]["outcomes"] == outcomes(a["result"]), "invalid coverage/outcomes")
                previous.check_result(common_view(a["result"], arm), old, context, STOP, value["models"][w["model"]]["metadata"])
                if arm == "fixed":
                    require(a["result"] == old["arms"][context]["result"], "historical final world changed")
                for day, r in a["checkpoints"].items():
                    previous.check_result(common_view(r, arm), old, context, int(day) * DAY, value["models"][w["model"]]["metadata"])
                    require(a["frames"][day]["framebuffer_crc32"] == r["framebuffer_crc32"], "checkpoint pixels differ")
                    if arm == "fixed":
                        require(r == old["arms"][context]["checkpoints"][day], "historical checkpoint changed")
                if arm == "fixed":
                    require(all(a["frames"][str(day)]["raw_sha256"] == old["arms"][context]["frames"][str(day)]["raw_sha256"]
                                for day in FRAMES), "historical pixels changed")
            check_prefix(pair["fixed"]["checkpoints"]["158"], pair["rotating"]["checkpoints"]["158"])
            require(pair["fixed"]["frames"]["158"]["raw_sha256"] == pair["rotating"]["frames"]["158"]["raw_sha256"], "prefix frame differs")
            require(pair["fixed"]["boundary"] == pair["rotating"]["boundary"] and
                    all(r["tick"] == AT for r in pair["fixed"]["boundary"].values()), "boundary trace differs")


def collect(build, out, jobs):
    require(1 <= jobs <= 4 and not out.exists() and
            (out.is_relative_to(ROOT / "artifacts") or not out.is_relative_to(ROOT)), "fresh output/jobs 1..4 required")
    saved, models, frozen, excerpt = load_inputs()
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
            require(digest(ROOT / name) == sha, "input changed")
            shutil.copy2(ROOT / name, out / "inputs" / Path(name).name)
        for key, meta in saved["models"].items():
            path = out / "models" / (key + ".tgl")
            with path.open("xb") as stream:
                stream.write(models[meta["model"]])
            require(digest(path) == meta["sha256"], "model identity differs")

        def one(w):
            old_trace = next(v for v in frozen["worlds"] if v["id"] == w["id"])
            old_visits = next(v for v in excerpt["worlds"] if v["id"] == w["id"])
            contexts, calls = {}, []
            for context in previous.ARMS:
                pair = {}
                for arm in ARMS:
                    stem = context + "-" + arm + "--" + w["id"]
                    args = ("vacancy-replay" if context == "vacancy" else "placement-replay", "models/" + w["model"] + ".tgl",
                        w["case"]["scenario"], "0x" + w["case"]["seed"], "--climate", "seasonal", "--ledger",
                        "--shoot-reserve", "on", "--seed-placement", "spacing")
                    if context == "vacancy":
                        args += ("--vacancy-at", AT, "--vacancy-lineage", previous.TARGETS[w["model"]][0])
                    if arm == "rotating":
                        args += ("--seed-order", "rotating", "--seed-order-after", AT)

                    def call(label, tick, extra=()):
                        name = stem + "-" + label
                        raw, png = "frames/" + name + ".raw", "frames/" + name + ".png"
                        command = (*args, "--ticks", tick, "--framebuffer", raw, *extra)
                        result = training.native(binary, out, *command)
                        write_json(out / (name + "-result.json"), result)
                        calls.append({"name": name, "tick": tick, "args": list(map(str, command))})
                        pixels = (out / raw).read_bytes()
                        require(len(pixels) == 240 * 240 * 2 and f"{zlib.crc32(pixels):08x}" == result["framebuffer_crc32"], "wrong pixels")
                        write_png(out / png, 240, 240, rgb565be_to_rgb888(pixels))
                        return result, {"id": name, "tick": tick, "framebuffer": raw, "png": png,
                            "framebuffer_crc32": result["framebuffer_crc32"], "raw_sha256": digest(out / raw), "png_sha256": digest(out / png)}

                    checkpoints, frames = {}, {}
                    for day in FRAMES[:-1]:
                        checkpoints[str(day)], frames[str(day)] = call("day" + str(day), day * DAY)
                    paths, results, hashes = [], [], []
                    for label in ("trace", "repeat", "plain"):
                        extra, traces = (), []
                        if label != "plain":
                            for kind in ("stand", "adult"):
                                path = stem + "-" + label + "-" + kind + ".jsonl"
                                traces.append(out / path)
                                extra += ("--" + kind + "-trace", path, "--" + kind + "-start", AT,
                                          "--" + kind + "-stop", END)
                            extra += ("--stand-order",)
                        result, frame = call(label, STOP, extra)
                        results.append(result)
                        hashes.append(frame["raw_sha256"])
                        if label == "plain":
                            frames["256"] = frame
                        for path in traces:
                            compress(path, Path(str(path) + ".gz"))
                            # Remove only this invocation's losslessly archived duplicate.
                            path.unlink()
                        if traces:
                            paths.append([Path(str(p) + ".gz") for p in traces])
                    require(results[0] == results[1] == results[2] and len(set(hashes)) == 1 and
                            all(digest(a) == digest(b) for a, b in zip(*paths, strict=True)), "repeat/observer differs")
                    result = {**results[0], "framebuffer_crc32": None}
                    stand, adult = (recovery.adults.read_trace(p) for p in paths[0])
                    audit = analyze(stand, adult, result, arm)
                    if arm == "fixed":
                        # Clip only the added boundary sample for exact historical comparison.
                        clipped = [{**stand[0], "schema": "landing-stand-trace-v1", "start": recovery.START},
                            *({k: v for k, v in r.items() if k != "plant_order"} for r in stand[2:-1]), stand[-1]]
                        clipped_resources = [{**adult[0], "start": recovery.START}, *adult[2:]]
                        require(recovery.analyze(clipped, clipped_resources, result) == old_trace["arms"][context]["audit"], "historical gates/resources differ")
                        visits = [[r["tick"], [[v[k] for k in bank.FIELDS] for v in r["reproduction"]]] for r in stand[2:-1]]
                        require(visits == old_visits["arms"][context]["rows"], "historical ordered visits differ")
                        check_historical(audit, w["arms"][context])
                    pair[arm] = {"result": result, "audit": audit, "checkpoints": checkpoints, "frames": frames,
                        "boundary": {"stand": stand[1], "adult": adult[1]},
                        "repeat_plain_verified": True, "traces": {k: {"path": p.name, "sha256": digest(p)}
                            for k, p in zip(("stand", "adult"), paths[0], strict=True)}}
                    print(w["model"] + " / " + context + " / " + arm + ": repeats, traversal, gates and budgets verified", flush=True)
                check_prefix(pair["fixed"]["checkpoints"]["158"], pair["rotating"]["checkpoints"]["158"])
                directory = out / "frames" / (context + "--" + w["model"])
                directory.mkdir()
                groups = [[{**pair[a]["frames"][str(d)], "framebuffer": str(out / pair[a]["frames"][str(d)]["framebuffer"])}
                           for d in FRAMES] for a in ARMS]
                contact_sheet(directory, groups)
                contexts[context] = pair
            return {k: w[k] for k in ("id", "model", "case")} | {"contexts": contexts, "calls": calls}

        with ThreadPoolExecutor(max_workers=jobs) as pool:
            worlds = list(pool.map(one, saved["worlds"]))
        require(source_files() == sources and digest(source) == digest(binary) == identities["binary"] and
                digest(cache) == identities["cache"] and all(digest(ROOT / p) == h for p, h in INPUTS.items()), "source/build/input changed")
        require(sum(len(w["calls"]) for w in worlds) == 120, "wrong native call budget")
        value = {"rule": RULE, "inputs": INPUTS, "models": saved["models"], "protocol_sha256": digest(out / "protocol.md"),
            "build": identities, "settings": settings, "source_sha256": sources, "training_runs": 0,
            "full_replays": 72, "checkpoint_replays": 48, "worlds": worlds, "summary": summarize(worlds)}
        check_value(value)
        recovery.founders.write_gzip(out / "results.json.gz", value)
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
        require(manifest["rule"] == RULE and manifest["status"] == "complete", "wrong manifest")
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
            for context, pair in w["contexts"].items():
                for arm, a in pair.items():
                    paths = [bundle / a["traces"][kind]["path"] for kind in ("stand", "adult")]
                    for kind, p in zip(("stand", "adult"), paths, strict=True):
                        require(digest(p) == a["traces"][kind]["sha256"] == digest(p.with_name(p.name.replace("-trace-", "-repeat-"))), "raw repeat/identity differs")
                    raw_traces = [recovery.adults.read_trace(p) for p in paths]
                    require(analyze(*raw_traces, a["result"], arm) == a["audit"] and
                            a["boundary"] == dict(zip(("stand", "adult"), (r[1] for r in raw_traces), strict=True)), "offline reanalysis differs")
                    stem = context + "-" + arm + "--" + w["id"]
                    for label, day in (("day158", "158"), ("day192", "192"), ("trace", "256"), ("repeat", "256"), ("plain", "256")):
                        raw_result = json.loads((bundle / (stem + "-" + label + "-result.json")).read_text())
                        expected = a["checkpoints"][day] if day != "256" else {**a["result"], "framebuffer_crc32": a["frames"][day]["framebuffer_crc32"]}
                        require(raw_result == expected and digest(bundle / "frames" / (stem + "-" + label + ".raw")) ==
                                a["frames"][day]["raw_sha256"], "native result/pixel repeat differs")
                    for f in a["frames"].values():
                        raw = bundle / f["framebuffer"]
                        require(digest(raw) == f["raw_sha256"] and digest(bundle / f["png"]) == f["png_sha256"] and
                                f"{zlib.crc32(raw.read_bytes()):08x}" == f["framebuffer_crc32"], "frame identity differs")
                    print(w["model"] + " / " + context + " / " + arm + ": offline raw analysis verified", flush=True)
    print("Verified fixed panel, rotation access, resource budgets and descendant outcomes; no new simulation.")
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
        print("order screen failed: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
