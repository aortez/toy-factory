#!/usr/bin/env python3
"""Read-only matched seed blockers and first-day resource accounting."""

from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import gzip
import json
from pathlib import Path
import shutil
import sys
import tempfile

import garden_landing_renewal_audit as previous
from garden_experiments import compress, digest, source_files, snapshot_sources, write_json
from garden_gallery import artifact
from garden_resources import require

ROOT = Path(__file__).resolve().parents[1]
RULE = "garden-landing-recruitment-trace-v1"
PROTOCOL = "benchmarks/garden-seasons/landing-recruitment-trace-protocol.md"
INPUTS = {
    previous.INPUT: previous.INPUT_SHA,
    "landing-multiseed-models.json.gz": "631364e9c1c23c676fb7cf699f630c807b6197cc21b6bc5b317afaf5095e757c",
    "landing-renewal-audit-results.json.gz": "974866fec534ee6c3a147e9b2c251d5b016184a6e8546606b222ca0b03f82539",
}
training = previous.training
DAY, STEP, STOP = previous.DAY, previous.STEP, training.STOP
BLOCKERS = ("dormant", "moisture", "light", "plant_capacity", "node_capacity", "spacing", "cold")
STAGES = ("uptake", "maintenance", "germination", "growth", "reproduction")
RESOURCE_FIELDS = ("initial", "income", "overflow", "upkeep", "growth", "reproduction", "discarded", "final")


def load_inputs(root):
    for name, sha in INPUTS.items():
        require(digest(root / name) == sha, "wrong frozen input: " + name)
    panel, models, audit = (json.loads(gzip.decompress((root / name).read_bytes())) for name in INPUTS)
    require(audit == previous.analyze(panel), "saved renewal audit differs")
    return panel, {k: bytes.fromhex(v) for k, v in models.items()}, audit


def select(audit):
    rows = []
    for suffix in ("33", "34", "35"):
        ids = [f"{c}-s6d6978{suffix}-live" for c in ("single", "multi")]
        old, new = (audit["worlds"][m] for m in ids)
        confirmations = lambda ps: sum(c["renewal_eligible"] for p in ps for c in p["confirmations"])
        steady = [c for c, w in sorted(new.items()) if w["climate"] == "steady" and any(
            p["terminal_tier"] == 1 and p["credit"]["earned_ticks"] == 0 and
            p["seed_cohorts"]["purchased"]["counts"]["child_died"] for p in w["periods"])]
        seasonal = [c for c, w in sorted(new.items()) if w["climate"] == "seasonal" and
                    0 < confirmations(w["periods"]) < confirmations(old[c]["periods"])]
        require(steady and seasonal, "missing prespecified diagnostic stratum")
        for case in (steady[0], seasonal[0]):
            for model in ids:
                rows.append({"id": model + "--" + case, "model": model,
                             "case": {k: new[case][k] for k in ("id", "scenario", "climate", "seed")}})
    return rows


def signal_hash(base):
    value = 2166136261
    for byte in b"GSP1" + int(base, 16).to_bytes(4, "little") + bytes((1, 0, 0, 0)):
        value = ((value ^ byte) * 16777619) & 0xffffffff
    return f"{value:08x}"


def check_history(result, saved, case, metadata):
    old = previous.controls.signals.scoring_view(saved["result"], previous.controls.PROFILES[0])
    require({**result, "run_hash": signal_hash(result["run_hash"])} == old, "historical trajectory differs")
    require(training.score_world(result, case, metadata) == saved["history"], "historical score differs")


def seed_summary(rows):
    hist = Counter()
    for s in rows:
        hist.update(s["mature_masks"])
    checks = sum(hist.values())
    return {"seeds": len(rows), "mature_checks": checks,
            "outcomes": dict(sorted(Counter(s["outcome"] for s in rows).items())),
            "blocker_checks": {b: sum(n for mask, n in hist.items() if int(mask) & (1 << i))
                               for i, b in enumerate(BLOCKERS)},
            "always_blocked_seeds": {b: sum(bool(s["mature_masks"]) and all(int(m) & (1 << i)
                                             for m in s["mature_masks"]) for s in rows)
                                     for i, b in enumerate(BLOCKERS)},
            "open_elsewhere_checks": sum(s["open_elsewhere_checks"] for s in rows)}


def child_summary(rows):
    return {"children": len(rows), "outcomes": dict(sorted(Counter(p["outcome"] for p in rows).items())),
            "death_shortages": dict(sorted(Counter(p["death_shortage"] for p in rows if p["death_shortage"]).items())),
            "zero_energy_income": sum(p["resources"]["energy"]["income"] == 0 for p in rows),
            "resources": {r: {f: sum(p["resources"][r][f] for p in rows) for f in RESOURCE_FIELDS}
                          for r in ("energy", "water")}}


def analyze_trace(path, result):
    """Reconcile every check/sample, not just matching final fingerprints."""
    stop = result["tick"]
    require(type(stop) is int and stop >= 0, "invalid trace horizon")
    if stop < STEP:
        require(not result["seeds"] and all(p["parent"] == p["birth_tick"] == p["seeds_created"] == 0
                and p["death_tick"] is None for p in result["lineages"]), "events before first ecology step")
    previous.descendants.index_records(result["lineages"], result["seeds"], 0, max(STEP, stop - stop % STEP))
    seeds = {(s["parent"], s["birth_tick"]): {**s, "samples": 0, "masks": Counter(),
              "mature_masks": Counter(), "open_elsewhere_checks": 0,
              "moisture_range": None, "light_range": None} for s in result["seeds"]}
    plants = {p["id"]: {**p, "rows": []} for p in result["lineages"] if p["parent"]}
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt") as stream:
        require(json.loads(next(stream)) == {"schema": "landing-recruitment-trace-v1"}, "wrong trace schema")
        for tick in range(STEP, stop + 1, STEP):
            row = json.loads(next(stream))
            require(set(row) == {"tick", "seeds", "plants"} and row["tick"] == tick, "missing/reordered ecology sample")
            seen = set()
            for values in row["seeds"]:
                require(len(values) == 11 and all(type(v) is int for v in values), "invalid seed check")
                parent, age, column, mask, moisture, light, slots, nodes, outcome, child, opened = values
                key = parent, tick - age * STEP
                require(key in seeds and key not in seen, "unknown/duplicate seed check")
                seen.add(key)
                s = seeds[key]
                require(age == s["samples"] + 1 and column == s["column"] and 0 <= mask < 128 and
                        0 <= moisture <= 255 and 0 <= light <= 255 and 0 <= slots <= 8 and
                        0 <= nodes <= 256, "invalid seed age/resources")
                expected = (0 if s["end_tick"] != tick else {"expired": 1, "germinated": 2}[s["outcome"]])
                require(outcome == expected and child == (s["child_id"] if outcome == 2 else 0), "seed fate differs")
                s["samples"] += 1
                if outcome == 1:
                    require(age == s["lifetime_ecology_ticks"] and mask == moisture == light == 0 and opened == -1,
                            "expiry incorrectly counted as a check")
                    continue
                require(0 <= opened <= 28 and bool(mask & 1) == (age < 8) and
                        ((mask == 0) == (outcome == 2)), "invalid dormancy/germination gate")
                require(bool(mask & 2) == (moisture < 12) and bool(mask & 4) == (light < 80) and
                        bool(mask & 8) == (slots >= 8) and bool(mask & 16) == (nodes + 4 > 256),
                        "blocker mask disagrees with resources/capacity")
                s["masks"][str(mask)] += 1
                if not mask & 1:
                    s["mature_masks"][str(mask)] += 1
                    s["open_elsewhere_checks"] += bool(opened and mask)
                for name, value in (("moisture_range", moisture), ("light_range", light)):
                    s[name] = [value, value] if s[name] is None else [min(s[name][0], value), max(s[name][1], value)]
            require(seen == {k for k, s in seeds.items() if s["birth_tick"] < tick <= (s["end_tick"] or stop)},
                    "incomplete seed check inventory")
            seen_plants = set()
            for p in row["plants"]:
                pid = p["id"]
                require(pid in plants and pid not in seen_plants and p["birth"] == plants[pid]["birth_tick"],
                        "unknown/duplicate plant sample")
                seen_plants.add(pid)
                plants[pid]["rows"].append({"tick": tick, **p})
            require(seen_plants == {i for i, p in plants.items() if p["birth_tick"] <= tick <=
                    min(p["birth_tick"] + DAY, p["death_tick"] or stop, stop)}, "incomplete first-day inventory")
        require(json.loads(next(stream)) == {"complete": True, "tick": stop} and stream.read() == "",
                "incomplete/trailing trace")
    for s in seeds.values():
        require(s["samples"] == ((s["end_tick"] or stop) - s["birth_tick"]) // STEP, "seed lifetime gap")
        for field in ("masks", "mature_masks"):
            s[field] = dict(sorted(s[field].items(), key=lambda x: int(x[0])))
    for p in plants.values():
        analyze_child(p, stop)
    seed_rows, plant_rows = list(seeds.values()), list(plants.values())
    late_seeds = [s for s in seed_rows if s["outcome"] == "expired" and 62 * DAY < s["end_tick"] <= 190 * DAY]
    late_plants = [p for p in plant_rows if 62 * DAY < p["birth_tick"] <= 190 * DAY]
    return {"ecology_samples": stop // STEP, "seed_samples": sum(s["samples"] for s in seed_rows),
            "seed_checks": sum(sum(s["masks"].values()) for s in seed_rows),
            "first_day_samples": sum(len(p["rows"]) for p in plant_rows), "seeds": seed_rows, "plants": plant_rows,
            "summary": {"all_seeds": seed_summary(seed_rows), "late_expired": seed_summary(late_seeds),
                        "all_children": child_summary(plant_rows), "late_children": child_summary(late_plants)}}


def analyze_child(p, stop):
    rows = p["rows"]
    end = min(p["birth_tick"] + DAY, p["death_tick"] or stop, stop)
    require([r["tick"] for r in rows] == list(range(p["birth_tick"], end + 1, STEP)), "first-day sample gap")
    totals = {k: dict.fromkeys(RESOURCE_FIELDS, 0) for k in ("energy", "water")}
    previous_row = None
    for row in rows:
        stages, raw = row["stages"], row["uptake"]
        require(len(stages) == 5 and all(s is None or len(s) == 5 and all(type(v) is int and v >= 0 for v in s)
                                        for s in stages), "invalid resource stages")
        born = row["tick"] == p["birth_tick"]
        dead = p["death_tick"] == row["tick"]
        require(all(s is not None for s in stages[2:]) and bool(stages[4][3] & 1) == dead, "missing stage/death")
        require(row["roots"] >= 0 and row["active_leaves"] >= 0, "invalid morphology")
        if born:
            require(stages[:2] == [None, None] and raw is None and stages[2][:2] == [64, 24], "wrong birth endowment")
        else:
            require(stages[0] is not None and stages[1] == stages[2] and len(raw) == 2, "preexisting stage mismatch")
        for j, name in enumerate(("energy", "water")):
            t = totals[name]
            if born:
                t["initial"] = stages[2][j]
            else:
                before, income, overflow, due, paid, discarded = raw[j]
                require(all(type(v) is int and v >= 0 for v in raw[j]) and
                        before == previous_row["stages"][4][j] and
                        stages[0][j] == before + income - overflow, "uptake balance differs")
                upkeep = stages[0][j] - stages[1][j]
                if dead:
                    require(stages[1][j] == 0 and paid <= due and paid + discarded == stages[0][j],
                            "death receipt does not balance")
                    upkeep = paid
                    t["discarded"] += discarded
                else:
                    require(due == paid == discarded == 0, "live receipt has death-only fields")
                require(upkeep >= 0, "negative upkeep")
                t["income"] += income
                t["overflow"] += overflow
                t["upkeep"] += upkeep
            growth, reproduction = stages[2][j] - stages[3][j], stages[3][j] - stages[4][j]
            require(growth >= 0 and reproduction >= 0, "negative spending")
            t["growth"] += growth
            t["reproduction"] += reproduction
            t["final"] = stages[4][j]
            require(t["final"] == t["initial"] + t["income"] - sum(t[k] for k in
                    ("overflow", "upkeep", "growth", "reproduction", "discarded")), "cumulative budget differs")
        previous_row = row
    p["resources"] = totals
    p["outcome"] = ("died" if p["death_tick"] is not None and p["death_tick"] <= p["birth_tick"] + DAY
                    else "confirmed" if p["birth_tick"] + DAY <= stop else "pending")
    flags = rows[-1]["stages"][4][3]
    p["death_shortage"] = ({2: "energy", 4: "water", 6: "energy+water"}.get(flags & 6, "other")
                           if p["outcome"] == "died" else None)


def run_panel(binary, inputs, root, jobs, *, controls=True):
    panel, archive, audit = load_inputs(inputs)
    plan = select(audit)
    require(not root.exists(), "fresh panel required")
    (root / "models").mkdir(parents=True)
    models = {m["id"]: m for m in panel["models"] if m["id"] in {r["model"] for r in plan}}
    for key, m in models.items():
        path = root / "models" / (key + ".tgl")
        with path.open("xb") as stream:
            stream.write(archive[m["model"]])
        require(digest(path) == m["sha256"], "model identity mismatch")
    def one(item):
        case, model = item["case"], item["model"]
        name = item["id"]
        args = ("replay", "models/" + model + ".tgl", case["scenario"], "0x" + case["seed"],
                "--ticks", STOP, "--climate", case["climate"], "--ledger")
        result = training.native(binary, root, *args, "--recruitment-trace", name + ".jsonl")
        check_history(result, panel["evaluations"][model]["worlds"][case["id"]], case, models[model]["metadata"])
        if controls:
            require(training.native(binary, root, *args) == result, "tracing changes world")
            repeated = training.native(binary, root, *args, "--recruitment-trace", name + "-repeat.jsonl")
            require(repeated == result and digest(root / (name + ".jsonl")) == digest(root / (name + "-repeat.jsonl")),
                    "trace replay differs")
            compress(root / (name + "-repeat.jsonl"), root / (name + "-repeat.jsonl.gz"))
            (root / (name + "-repeat.jsonl")).unlink()
        value = analyze_trace(root / (name + ".jsonl"), result)
        compress(root / (name + ".jsonl"), root / (name + ".jsonl.gz"))
        (root / (name + ".jsonl")).unlink()
        require(digest(root / "models" / (model + ".tgl")) == models[model]["sha256"], "model changed during replay")
        write_json(root / (name + ".json"), result)
        print(name + ": exact historical replay and resource balance", flush=True)
        return {**item, "result": result, "audit": value, "trace_sha256": digest(root / (name + ".jsonl.gz"))}
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        worlds = list(pool.map(one, plan))
    return {"schema_version": 1, "rule": RULE, "inputs": INPUTS, "plan": plan,
            "models": models, "worlds": worlds, "stages": STAGES, "resource_fields": RESOURCE_FIELDS}


def collect(build, inputs, output, jobs):
    require(1 <= jobs <= 4 and not output.exists() and
            (output.is_relative_to(ROOT / "artifacts") or not output.is_relative_to(ROOT)), "fresh output/jobs 1..4 required")
    load_inputs(inputs)
    binary, cache = build / "toy-factory-garden-landing", build / "CMakeCache.txt"
    flags = training.check_flags(cache)
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
    with tempfile.TemporaryDirectory(prefix="landing-recruitment-verify-") as temporary:
        result = run_panel(output / "bin/garden-landing", output / "inputs", Path(temporary) / "panel", 1, controls=False)
        require(json.loads(json.dumps(result)) == expected, "independent frozen trace differs")
    for name in manifest["artifacts"]:
        artifact(output, manifest, name)
    print("Verified all twelve historical worlds, raw traces, seed checks and first-day budgets.")


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
        print("recruitment trace failed: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
