#!/usr/bin/env python3
"""Run the frozen development allocation challenge; no training or scalar fitness."""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import gzip
import json
from pathlib import Path
import shutil
import time
import zlib

import garden_experiments as experiment
from garden_gallery import artifact, contact_sheet, rgb565be_to_rgb888, write_png
from garden_resources import budget, require

RULE = "allocation-challenge-v1"
BUNDLE_SHA = "aaf2ebd117045b817822394126c196dae49c0f6f749d684f48003f00f01ab7e8"
MODEL_SHA = "bd9f9c6ba7f5fd17309f917972da5f759c305c077798e1d4ba9a52701e2cd48b"
DAY, ROOT_AFTER = 3840, 614400
ARMS = ("reference", "wet-root", "wait", "candidate")
CASES = (
    ("wet-root-opportunity", "c7f54e18.reserve.16", "off", 65, 617805),
    ("rooted-water-baseline", "b61837dc.neural.16", "on", 92, 621480),
    ("rooted-water-bank8", "b61837dc.reserve.8", "on", 66, 625410),
    ("rooted-water-bank16", "b61837dc.reserve.16", "on", 68, 636945),
    ("energy-tradeoff", "c7f54e18.neural.8", "off", 38, 618300),
    ("established-control", "c7f54e18.neural.8", "off", 39, 626100),
)


def case_spec(case):
    name, key, arm, lineage, birth = case
    seed, growth, bank = key.split(".")
    return dict(name=name, key=key, history_arm=arm, lineage=lineage, birth=birth,
                seed=seed, growth=growth, bank=int(bank), end=birth + 8 * DAY,
                root_after=ROOT_AFTER if arm == "on" else 0)


SPECS = tuple(map(case_spec, CASES))


def dawn_tick(birth):
    # A birth exactly at dawn must still face its first future night.
    phase = (64 + birth // 15) % 256
    return birth + (256 - phase) * 15


def followup(death, boundary, end):
    if death is not None and death["tick"] <= min(boundary, end):
        return "patch-censored" if death["cause"] == "patch" else death["cause"]
    return "alive" if boundary <= end else "horizon-censored"


def projection(row, spec, stage):
    p = next((p for p in row["plants"] if p["id"] == spec["lineage"]), None)
    # Preserve authoritative world hash plus target telemetry used by accounting.
    names = ("id", "parent", "species", "generation", "age_ecology_ticks", "column",
             "dead", "energy", "water", "energy_income", "water_income", "stress",
             "flags", "vigor", "nodes", "roots", "active_leaves", "tips", "reproduction_cooldown")
    plant = None if p is None else {k: p[k] for k in names} | {
        "leaf": {"renewals": p["leaf"]["renewals"]},
        "agent": {k: p["agent"][k] for k in
                  ("decisions", "extend", "root_extend", "shoot_extend", "finish", "wait")}}
    return {k: row[k] for k in ("tick", "hash", "sun_phase", "living", "births", "deaths",
                               "rain_deposited", "rain_runoff")} | {"stage": stage, "plant": plant,
        "new_children": [p["id"] for p in row["plants"] if p["parent"] == spec["lineage"] and
                         p["age_ecology_ticks"] == 1 and not p["dead"]]}


def reference_window(bundle, manifest, spec):
    stem = f"{spec['key']}.{spec['history_arm']}"
    paths = [f"traces/{stem}.world.gz", f"analyses/{stem}.boundaries.json", f"analyses/{stem}.json"]
    checked = [artifact(bundle, manifest, name) for name in paths]
    bounds = experiment.read_json(checked[1])
    analysis = experiment.read_json(checked[2])
    lineage = next(p for p in analysis["world"]["lineages"] if p["id"] == spec["lineage"])
    require(lineage["birth_tick"] == spec["birth"] and lineage["parent"] != 0, "case birth changed")
    events = {b["event"]["tick"]: b for b in bounds}
    start = spec["birth"] - 15
    rows = []
    with gzip.open(checked[0], "rt") as stream:
        for line in stream:
            r = json.loads(line)
            tick = r["tick"]
            if tick < start:
                continue
            if tick > spec["end"]:
                break
            if tick == start:
                rows.append(projection(events[tick]["after"] if tick in events else r, spec, "checkpoint"))
            else:
                rows.append(projection(r, spec, "ecology"))
                if tick in events:
                    rows.append(projection(events[tick]["after"], spec, "patch"))
    require(rows[0]["tick"] == start and rows[-1]["tick"] == spec["end"] and
            rows[0]["plant"] is None, "incomplete reference window")
    return {"spec": spec, "lineage": lineage, "rows": rows,
            "events": [b["event"] for b in bounds if start < b["event"]["tick"] <= spec["end"]]}, {
                name: manifest["artifacts"][name] for name in paths}


def validate_identity(meta, spec, checkpoint, candidate_crc):
    expected = {"type": "identity", "rule": RULE, "seed": spec["seed"], "growth": spec["growth"],
        "root_after": spec["root_after"], "lineage": spec["lineage"], "birth": spec["birth"],
        "end": spec["end"], "checkpoint_tick": spec["birth"] - 15, "checkpoint_hash": checkpoint,
        "reference_crc32": "dc5e849d", "candidate_crc32": candidate_crc, "node_capacity": 512,
        "seed_capacity": spec["bank"], "patch_seed": "e4d65e6f",
        "seed_reserve_rule": "sunset-seed-reserve-v1", "leaf_policy": "selective",
        "water_uptake": "headroom-v1", "seed_dispersal": "wide-v1", "scenario": "rainfed-crowded",
        "gardener": False, "drainage": False}
    require(meta == expected, "wrong challenge identity/configuration")


def analyze_arm(rows, spec):
    require(rows and rows[0]["stage"] == "checkpoint" and rows[0]["plant"] is None and
            rows[0]["tick"] == spec["birth"] - 15, "wrong arm checkpoint")
    previous, last, death = None, rows[0]["tick"], None
    totals, actions = Counter(), Counter()
    marks = {"birth": spec["birth"], "dawn": dawn_tick(spec["birth"]),
             "day1": spec["birth"] + DAY, "day8": spec["end"]}
    snapshots, last_live = {}, None
    live_steps, peak_leaves = 0, 0
    children = set()
    for row in rows[1:]:
        tick, stage, p = row["tick"], row["stage"], row["plant"]
        require(stage in ("ecology", "patch") and
                (tick == last + 15 if stage == "ecology" else tick == last), "missing/reordered sample")
        require(tick <= spec["end"] and row["sun_phase"] == (64 + tick // 15) % 256 and
                row["manual_actions"] == row["auto_actions"] == 0, "bad cadence or gardener input")
        if stage == "ecology":
            born = row["new_children"]
            require(len(born) == len(set(born)) and not children.intersection(born) and
                    all(isinstance(i, int) and i > spec["lineage"] for i in born), "duplicate/invalid child birth")
            children.update(born)
        if p is None:
            require(death is not None, "target disappeared without death")
        else:
            require(p["id"] == spec["lineage"], "wrong target identity")
            if p["dead"]:
                if death is None:
                    require(previous is not None and not previous["dead"], "missing last live target")
                    cause = "patch" if stage == "patch" else {2: "energy", 4: "water", 6: "both"}.get(p["flags"] & 6)
                    require(cause is not None, "unknown natural death cause")
                    death = {"tick": tick, "age_days": (tick - spec["birth"]) / DAY, "cause": cause,
                             "terminal_step_budget": None}
            else:
                require(death is None and p["age_ecology_ticks"] == (tick - spec["birth"]) // 15 + 1,
                        "target revived or wrong birth")
                if stage == "ecology":
                    values = budget(previous, p, tick)
                    old_actions = previous["agent"] if previous is not None else {}
                    delta = {k: p["agent"][k] - old_actions.get(k, 0) for k in
                             ("decisions", "root_extend", "shoot_extend", "finish", "wait")}
                    require(all(v >= 0 for v in delta.values()) and delta["decisions"] ==
                        sum(delta[k] for k in ("root_extend", "shoot_extend", "finish", "wait")) <= 1,
                        "invalid committed action delta")
                    totals.update(values)
                    actions.update(delta)
                    live_steps += 1
                    last_live = {"tick": tick, "plant": p}
                    peak_leaves = max(peak_leaves, p["active_leaves"])
        # Patch after ecology supersedes its same-tick milestone, with no second debit.
        for name, boundary in marks.items():
            if tick == boundary:
                snapshots[name] = {"tick": tick, "hash": row["hash"], "plant": p,
                                   "budget": dict(totals), "actions": dict(actions)}
        previous, last = p, tick
    require(last == spec["end"] and set(snapshots) == set(marks), "incomplete follow-up")
    require(last_live is not None, "no live birth sample")
    for resource, initial in (("water", 24), ("energy", 64)):
        spent = sum(totals[f"{resource}_{k}"] for k in ("overflow", "growth", "upkeep", "renewal", "seeds"))
        require(initial + totals[f"{resource}_income"] - spent == last_live["plant"][resource],
                "lifetime resource balance does not close")
    require(totals["energy_seeds"] % 48 == 0, "fractional seed purchase")
    return {"death": death, "followup": {k: followup(death, v, spec["end"]) for k, v in marks.items()},
        "live_steps_checked": live_steps, "budget": dict(totals), "actions": dict(actions),
        "milestones": snapshots, "last_alive": last_live, "peak_active_leaves": peak_leaves,
        "seeds_created": totals["energy_seeds"] // 48, "children_germinated": len(children),
        "child_ids": sorted(children),
        "final_world": {k: rows[-1][k] for k in ("tick", "hash", "living", "births", "deaths")}}


def check_rows(native, reference, spec, candidate_crc, frame_root=None):
    validate_identity(native[0], spec, reference["rows"][0]["hash"], candidate_crc)
    samples = {arm: [] for arm in ARMS}
    frames = []
    arm_index, pending_patch, events = 0, None, []
    expected_events = reference["events"]
    for row in native[1:]:
        if row["type"] == "disturbance":
            require(pending_patch is None and len(events) < len(expected_events), "extra patch")
            expected = expected_events[len(events)]
            require(all(row[k] == expected[k] for k in
                        ("tick", "index", "protocol", "seed", "first_column", "last_column")), "wrong schedule")
            require(samples[ARMS[arm_index]][-1]["hash"] == row["before_hash"], "wrong pre-patch hash")
            pending_patch = row
            continue
        require(row["arm"] in ARMS, "unknown arm")
        arm = row["arm"]
        if ARMS.index(arm) != arm_index:
            require(ARMS.index(arm) == arm_index + 1 and row["type"] == "sample" and
                    row["stage"] == "checkpoint" and pending_patch is None and
                    len(events) == len(expected_events), "incomplete/reordered arm")
            arm_index += 1
            events = []
        if row["type"] == "frame":
            require(pending_patch is None and row["hash"] == samples[arm][-1]["hash"] and
                    row["tick"] == samples[arm][-1]["tick"], "frame/state mismatch")
            expected_ticks = {"birth": spec["birth"], "dawn": dawn_tick(spec["birth"]),
                              "day1": spec["birth"] + DAY, "day8": spec["end"]}
            require(row["milestone"] in expected_ticks and row["tick"] == expected_ticks[row["milestone"]],
                    "wrong frame milestone")
            if frame_root is not None:
                raw = (frame_root / f"{arm}.{row['milestone']}.rgb565").read_bytes()
                require(len(raw) == 115200 and f"{zlib.crc32(raw):08x}" == row["framebuffer_crc32"], "corrupt frame")
            frames.append(row)
            continue
        require(row["type"] == "sample", "unknown native record")
        if row["stage"] == "patch":
            require(pending_patch is not None and row["tick"] == pending_patch["tick"] and
                    row["hash"] == pending_patch["after_hash"], "wrong post-patch state")
            p = row["plant"]
            if spec["lineage"] in pending_patch["killed"]:
                require(p is not None and p["dead"], "patch failed to kill selected target")
            events.append(pending_patch)
            pending_patch = None
        else:
            require(pending_patch is None, "missing post-patch row")
        samples[arm].append(row)
    require(arm_index == 3 and pending_patch is None and len(events) == len(expected_events), "truncated run")
    require(len(samples["reference"]) == len(reference["rows"]), "reference sample count mismatch")
    for actual, expected in zip(samples["reference"], reference["rows"], strict=True):
        comparable = {k: actual[k] for k in expected}
        if comparable["plant"] is not None:
            comparable["plant"] = {k: v for k, v in comparable["plant"].items() if k != "offspring"}
        require(comparable == expected, "reference continuation differs from frozen trace")
    for arm in ARMS:
        require(samples[arm][0] | {"arm": "reference"} == samples["reference"][0], "fork checkpoint differs")
    results = {arm: analyze_arm(samples[arm], spec) for arm in ARMS}
    old = reference["lineage"]
    expected_death = old["death_tick"] if old["death_tick"] is not None and old["death_tick"] <= spec["end"] else None
    require((results["reference"]["death"] or {}).get("tick") == expected_death, "reference death differs")
    if candidate_crc == "dc5e849d" and spec["root_after"] == 0:
        require([{k: v for k, v in row.items() if k != "arm"} for row in samples["candidate"]] ==
                [{k: v for k, v in row.items() if k != "arm"} for row in samples["reference"]],
                "same-model candidate changed a root-off world")
    if frames:
        require(len(frames) == 16 and len({(r['arm'], r['milestone']) for r in frames}) == 16,
                "missing/duplicate milestone frames")
    require(frame_root is None or len(frames) == 16, "capture was requested but absent")
    return {"spec": spec, "identity": native[0], "arms": results,
            "matched_reference_rows": len(reference["rows"]), "frames": frames}


def run_case(root, spec, reference, candidate_crc):
    directory = root / spec["name"]
    directory.mkdir()
    command = [f"bin/{spec['bank']}-allocation", "reference.tgm", "candidate.tgm", "0x" + spec["seed"],
        spec["growth"], str(spec["root_after"]), str(spec["lineage"]), str(spec["birth"]),
        str(spec["end"]), spec["name"]]
    start = time.monotonic()
    raw = directory / "trace.jsonl"
    experiment.command_run(command, raw, root, 300)
    with raw.open() as stream:
        rows = [json.loads(line) for line in stream]
    result = check_rows(rows, reference, spec, candidate_crc, directory)
    # A second execution with capture disabled must produce identical simulation rows.
    repeat = directory / "headless.jsonl"
    experiment.command_run(command[:-1] + ["-"], repeat, root, 300)
    with repeat.open() as stream:
        repeated = [json.loads(line) for line in stream]
    require(repeated == [r for r in rows if r["type"] != "frame"], "capture perturbed continuation")
    result.update(command=command, headless_command=command[:-1] + ["-"],
                  elapsed_seconds=time.monotonic() - start)
    experiment.write_json(directory / "result.json", result)
    for frame in result["frames"]:
        path = directory / f"{frame['arm']}.{frame['milestone']}"
        write_png(Path(str(path) + ".png"), 240, 240,
                  rgb565be_to_rgb888(Path(str(path) + ".rgb565").read_bytes()))
    print(spec["name"], {arm: r["followup"]["day1"] for arm, r in result["arms"].items()}, flush=True)
    return result


def summarize(results):
    return {"rule": RULE, "role": "development-diagnostic", "scalar_fitness": None,
        "cases": [{"spec": r["spec"], "checkpoint_hash": r["identity"]["checkpoint_hash"],
            "matched_reference_rows": r["matched_reference_rows"], "arms": {arm: {
                k: v for k, v in a.items() if k not in ("milestones", "last_alive")}
                for arm, a in r["arms"].items()}} for r in results]}


def verify(root):
    manifest = experiment.read_json(root / "manifest.json")
    require(manifest["status"] == "complete" and manifest["rule"] == RULE and
            manifest["input_manifest_sha256"] == BUNDLE_SHA and manifest["specs"] == list(SPECS),
            "wrong/incomplete challenge bundle")
    for name in manifest["artifacts"]:
        artifact(root, manifest, name)
    results = []
    for spec in SPECS:
        ref = experiment.read_json(root / f"input/{spec['name']}.json")
        with (root / spec["name"] / "trace.jsonl").open() as stream:
            rows = [json.loads(line) for line in stream]
        result = check_rows(rows, ref, spec, manifest["candidate_crc32"], root / spec["name"])
        saved = experiment.read_json(root / spec["name"] / "result.json")
        require(all(saved[k] == v for k, v in result.items()), "saved analysis differs")
        with (root / spec["name"] / "headless.jsonl").open() as stream:
            require([json.loads(line) for line in stream] == [r for r in rows if r["type"] != "frame"],
                    "headless evidence differs")
        results.append(result)
    require(summarize(results) == experiment.read_json(root / "summary.json"), "summary differs")
    print(f"Verified {len(results)} cases, 24 arms, 96 frames and resource ledgers; no native rerun", flush=True)


def collect(args):
    bundle, root = args.bundle.resolve(), args.output.resolve()
    require(root.is_relative_to(experiment.ROOT / "artifacts") and not root.exists() and
            not root.is_relative_to(bundle), "choose a new output under artifacts/")
    require(experiment.digest(bundle / "manifest.json") == BUNDLE_SHA, "wrong root-bootstrap bundle")
    manifest = experiment.read_json(bundle / "manifest.json")
    require(manifest["status"] == "complete", "incomplete input experiment")
    model = artifact(bundle, manifest, "model.tgm")
    require(experiment.digest(model) == MODEL_SHA, "wrong reference model")
    candidate = (args.candidate_model or model).resolve()
    data = candidate.read_bytes()
    require(len(data) == 1220, "wrong candidate model size")
    candidate_crc = f"{zlib.crc32(data[16:]):08x}"  # Native decoder also validates header/ABI.
    sources = experiment.source_files()
    root.mkdir(parents=True)
    for name in ("bin", "input"):
        (root / name).mkdir()
    experiment.snapshot_sources(root, sources)
    shutil.copy2(model, root / "reference.tgm")
    shutil.copy2(candidate, root / "candidate.tgm")
    protocol = experiment.ROOT / "benchmarks/garden-longevity/allocation-challenge-protocol.md"
    shutil.copy2(protocol, root / "protocol.md")
    started = {"rule": RULE, "role": "development-diagnostic", "specs": SPECS,
        "input_manifest_sha256": BUNDLE_SHA, "source_sha256": sources,
        "candidate_sha256": experiment.digest(candidate), "candidate_crc32": candidate_crc,
        "candidate_is_frozen_reference": experiment.digest(candidate) == MODEL_SHA,
        "inputs": {"model.tgm": MODEL_SHA}}
    experiment.write_json(root / "started.json", started)
    try:
        for bank in (8, 16):
            build = experiment.ROOT / f"artifacts/seed-reserve-build-on-{bank}"
            cache = (build / "CMakeCache.txt").read_text()
            for flag, value in (("WIDE_DISPERSAL", True), ("WATER_HEADROOM", True),
                    ("COMBINED_EXPERIMENT", True), ("LARGE_POOL", True), ("LEAF_MAINTENANCE", True),
                    ("SEED_RESERVE", True), ("LARGE_SEED_BANK", bank == 16), ("BOTTOM_DRAINAGE", False)):
                require(f"TOY_FACTORY_GARDEN_{flag}:BOOL={'ON' if value else 'OFF'}" in cache,
                        "wrong challenge build configuration")
            require("TOY_FACTORY_SIMULATOR_SANITIZERS:BOOL=ON" in cache, "UBSan required")
            shutil.copy2(build / "CMakeCache.txt", root / f"input/{bank}.cache.txt")
            shutil.copy2(build / "toy-factory-garden-allocation", root / f"bin/{bank}-allocation")
        references = []
        for spec in SPECS:
            ref, inputs = reference_window(bundle, manifest, spec)
            references.append(ref)
            started["inputs"].update(inputs)
            experiment.write_json(root / f"input/{spec['name']}.json", ref)
        frozen = {str(p.relative_to(root)): experiment.digest(p) for p in root.rglob("*") if p.is_file()}
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda pair: run_case(root, *pair, candidate_crc), zip(SPECS, references)))
        experiment.write_json(root / "summary.json", summarize(results))
        groups = [[{"id": f"{spec['name']}.{arm}.day1",
                    "framebuffer": f"{spec['name']}/{arm}.day1.rgb565"} for arm in ARMS] for spec in SPECS]
        experiment.write_json(root / "frames.json", contact_sheet(root, groups))
        require(experiment.source_files() == sources, "source changed during capture")
        require(all(experiment.digest(bundle / name) == value for name, value in started["inputs"].items()),
                "frozen experiment input changed")
        require(all(experiment.digest(root / name) == value for name, value in frozen.items()),
                "frozen collector input changed")
        experiment.write_json(root / "manifest.json", started | {"status": "complete", "artifacts": {
            str(p.relative_to(root)): experiment.digest(p) for p in root.rglob("*") if p.is_file()}})
    except BaseException as error:
        experiment.write_json(root / "failure.json", {"error": str(error)})
        raise
    verify(root)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--output", type=Path)
    group.add_argument("--verify", type=Path)
    parser.add_argument("--bundle", type=Path, default=experiment.ROOT / "artifacts/garden-root-bootstrap")
    parser.add_argument("--candidate-model", type=Path)
    args = parser.parse_args()
    require(not args.verify or args.candidate_model is None, "candidate model is only for collection")
    verify(args.verify.resolve()) if args.verify else collect(args)


if __name__ == "__main__":
    main()
