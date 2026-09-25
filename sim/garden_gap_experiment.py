#!/usr/bin/env python3
"""Freeze a paired largest-adult export/recovery assay against unchanged censuses."""

from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import gzip
import json
from pathlib import Path
import shutil
import tempfile
import zlib

import garden_establishment as establishment
import garden_experiments as experiment
import garden_leaf_competition as competition
import garden_leaf_experiment as maintenance
from garden_gallery import contact_sheet, rgb565be_to_rgb888, write_png
from garden_resources import require

PROTOCOL = "largest-adult-export-v1"
GAP_TICK = 61440
HORIZON = 92160


def validate_boundary(before: dict, after: dict, event: dict) -> None:
    require(event["protocol"] == PROTOCOL and before["tick"] == after["tick"] == event["tick"],
            "invalid intervention boundary")
    require(before["hash"] == event["before_hash"] and after["hash"] == event["after_hash"],
            "intervention hash mismatch")
    removed = [p for p in before["plants"] if p["id"] == event["id"]]
    require(len(removed) == 1 and not removed[0]["dead"], "missing living removal target")
    require([p for p in before["plants"] if p["id"] != event["id"]] == after["plants"],
            "survivor state changed during export")
    require(after["nodes"] == before["nodes"] - event["nodes"]
            and after["living"] == before["living"] - 1, "wrong exported counts")
    require([{k: v for k, v in s.items() if k != "blockers"} for s in before["seeds"]]
            == [{k: v for k, v in s.items() if k != "blockers"} for s in after["seeds"]],
            "seed bank changed during export")
    for key in before.keys() - {"hash", "nodes", "living", "plants", "seeds", "sites"}:
        require(before[key] == after[key], "unexpected intervention change: " + key)
    if before["type"] == "world":
        adult = min((p for p in before["plants"] if not p["dead"] and p["age_ecology_ticks"] >= 256),
                    key=lambda p: (-p["nodes"], p["id"]))
        require(adult["id"] == event["id"], "wrong largest-adult selection")
        require(all(adult[k] == event[k] for k in ("nodes", "column", "energy", "water")),
                "incorrect export accounting")
    else:
        require(all(a[1] == b[1] and a[2] >= b[2] for b, a in zip(before["sites"], after["sites"], strict=True)),
                "export changed soil or decreased light")
        competition.spatial_snapshot(after)


def capture(command: list[str], path: Path, root: Path, kind: str, gap_tick: int | None) -> dict | None:
    boundary = None
    previous = None
    with tempfile.TemporaryDirectory(prefix="garden-gap-") as temp:
        raw = Path(temp) / "raw.jsonl"
        experiment.command_run(command, raw, root, 180)
        with raw.open() as incoming, path.open("xb") as output:
            with gzip.GzipFile(fileobj=output, filename="", mode="wb", mtime=0) as packed:
                iterator = iter(incoming)
                for line in iterator:
                    row = json.loads(line)
                    if row["type"] in ("bid", "leaf-bid"):
                        require(kind == "world", "bid in seed census")
                        continue
                    if row["type"] == "gap":
                        require(boundary is None and gap_tick is not None and row["tick"] == gap_tick
                                and previous is not None, "unexpected gap event")
                        after = json.loads(next(iterator))
                        require(after["type"] == kind, "missing post-gap snapshot")
                        validate_boundary(previous, after, row)
                        boundary = {"event": row, "before": previous, "after": after}
                        # Preserve the ordinary pre-gap step for exact resource/seed accounting.
                        # Immediate post-gap state is separately frozen in the boundary artifact.
                        continue
                    require(row["type"] == kind, "unexpected census record")
                    packed.write(line.encode())
                    previous = row
    require((boundary is not None) == (gap_tick is not None), "missing requested gap")
    return boundary


def compare_prefix(current: Path, frozen: Path, end: int) -> int:
    count = 0
    with gzip.open(current, "rt") as a, gzip.open(frozen, "rt") as b:
        for tick in range(0, end + 1, 15):
            row, old = json.loads(next(a)), json.loads(next(b))
            require(row == old and row["tick"] == tick, "untouched census drift")
            count += 1
    return count


def checkpoints(path: Path, ticks: set[int]) -> dict[int, dict]:
    result = {}
    with gzip.open(path, "rt") as stream:
        for line in stream:
            row = json.loads(line)
            if row["tick"] in ticks:
                result[row["tick"]] = row
    require(result.keys() == ticks, "missing requested checkpoint")
    return result


def metrics(analysis: dict, event: dict, later: dict, gap_tick: int, horizon: int) -> dict:
    world = analysis["world"]
    late = world["windows"]["late"]
    born = [p for p in world["lineages"] if p["birth_tick"] > gap_tick]
    footprint = [p for p in born if abs(p["column"] - event["column"]) < 3]
    germinated = [s for s in analysis["seeds"]["seeds"]
                  if s["outcome"] == "germinated" and s["end_tick"] > gap_tick]
    recent_records = {p["id"]: p for p in world["lineages"]}
    return {"births": late["births"], "natural_deaths": late["deaths"],
            "seeds_created": late["seeds_created"], "seeds_expired": late["seeds_expired"],
            "final_living": world["final"]["living"], "final_nodes": world["final"]["nodes"],
            "first_birth_ticks": min((p["birth_tick"]-gap_tick for p in born), default=None),
            "first_footprint_birth_ticks": min((p["birth_tick"]-gap_tick for p in footprint), default=None),
            "footprint_births": len(footprint),
            "bank_seed_births": sum(s["birth_tick"] <= gap_tick for s in germinated),
            "new_seed_births": sum(s["birth_tick"] > gap_tick for s in germinated),
            "lifetimes": world["lifetimes"]["late_born"],
            "footprint_lifetimes": competition.lifetime_cohort(
                recent_records, horizon, gap_tick, {p["id"] for p in footprint}),
            "closing_births": world["final"]["births"]-later["births"],
            "closing_natural_deaths": world["final"]["deaths"]-later["deaths"],
            "closing_lifetimes": competition.lifetime_cohort(recent_records, horizon, later["tick"])}


def summarize(cases: list[dict]) -> dict:
    result = {}
    for arm in ("control", "gap"):
        totals = Counter()
        lifetimes = Counter()
        seeds = Counter()
        exposure = Counter()
        closing = Counter()
        latencies = []
        for case in cases:
            a = case[arm]
            m = a["metrics"]
            totals.update({k: m[k] for k in ("births", "natural_deaths", "seeds_created", "seeds_expired",
                          "final_living", "final_nodes", "footprint_births", "bank_seed_births", "new_seed_births",
                          "closing_births", "closing_natural_deaths")})
            totals["worlds_with_births"] += m["births"] > 0
            totals["worlds_with_footprint_births"] += m["footprint_births"] > 0
            totals["worlds_with_closing_births"] += m["closing_births"] > 0
            lifetimes.update(m["lifetimes"])
            closing.update(m["closing_lifetimes"])
            seeds.update(a["analysis"]["seeds"]["cohorts"]["late_born"])
            exposure.update(a["analysis"]["world"]["windows"]["late"])
            if m["first_birth_ticks"] is not None:
                latencies.append(m["first_birth_ticks"])
        result[arm] = {"worlds": len(cases), "totals": totals, "lifetimes": lifetimes,
                       "closing_lifetimes": closing, "late_seed_cohort": seeds,
                       "late_exposure": exposure, "first_birth_ticks": sorted(latencies)}
    return result


def collect(bundle: Path, build: Path, output: Path, jobs: int) -> None:
    bundle, build, output = bundle.resolve(), build.resolve(), output.resolve()
    source_manifest = experiment.read_json(bundle / "manifest.json")
    require(source_manifest.get("status") == "complete"
            and source_manifest.get("kind") == "garden-maintenance-competition", "wrong input bundle")
    capacity = source_manifest["node_capacity"]
    require(capacity in (256, 512), "wrong capacity")
    require(not output.is_relative_to(experiment.ROOT) or output.is_relative_to(experiment.ROOT / "artifacts"),
            "output must be outside source or under artifacts/")
    output.mkdir(parents=True, exist_ok=False)
    for folder in ("input", "bin", "traces", "analyses", "frames"):
        (output / folder).mkdir()
    sources = experiment.source_files()
    experiment.snapshot_sources(output, sources)
    shutil.copy2(bundle / "manifest.json", output / "input/manifest.json")
    original_cases = experiment.read_json(establishment.verified(bundle, source_manifest, "cases.json"))
    selected = [c for c in original_cases if c["leaf_policy"] == "selective"]
    expected = {(scenario, seed) for scenario in experiment.SCENARIOS for seed in experiment.trial_seeds(0x6d617463, 8)}
    require(len(selected) == 16 and {(c["scenario"], c["seed"]) for c in selected} == expected,
            "incomplete selective panel")
    for case in selected:
        require(case["growth_policy"] == experiment.NIGHT_POLICY, "wrong growth policy")
        for suffix in ("world", "sites"):
            name = f"traces/{case['id']}.{suffix}.jsonl.gz"
            shutil.copy2(establishment.verified(bundle, source_manifest, name), output / f"input/{case['id']}.{suffix}.gz")
    shutil.copy2(establishment.verified(bundle, source_manifest, "model.tgm"), output / "model.tgm")
    require(experiment.digest(output / "model.tgm") == maintenance.MODEL_SHA, "wrong model")
    experiment.write_json(output / "input/cases.json", selected)
    for tool in ("inspect", "replay"):
        shutil.copy2(build / f"toy-factory-garden-{tool}", output / f"bin/{tool}")
    shutil.copy2(build / "CMakeCache.txt", output / "build-cache.txt")
    frozen = {str(p.relative_to(output)): experiment.digest(p) for p in output.rglob("*") if p.is_file()}
    record = {"schema_version": 1, "kind": "garden-gap-recovery", "protocol": PROTOCOL,
              "node_capacity": capacity, "gap_tick": GAP_TICK, "horizon": HORIZON,
              "source_sha256": sources, "input_manifest_sha256": experiment.digest(output / "input/manifest.json")}
    experiment.write_json(output / "started.json", record)

    def run_case(case):
        result = {k: case[k] for k in ("id", "scenario", "seed")}
        commands = []
        for arm in ("control", "gap"):
            prefix = f"{case['id']}.{arm}"
            base = ["bin/inspect", "model.tgm", case["scenario"], experiment.NIGHT_POLICY, "0x" + case["seed"],
                    "--leaf-policy", "selective", "--ticks", str(HORIZON)]
            if arm == "gap":
                base += ["--gap-at", str(GAP_TICK)]
            boundaries = {}
            verified = 0
            for suffix, flag, kind in (("world", "--ecology", "world"), ("sites", "--seed-sites", "seed-sites")):
                path = output / f"traces/{prefix}.{suffix}.gz"
                boundaries[suffix] = capture(base + [flag], path, output, kind, GAP_TICK if arm == "gap" else None)
                commands.append(base + [flag])
                verified += compare_prefix(path, output / f"input/{case['id']}.{suffix}.gz",
                                           GAP_TICK if arm == "gap" else HORIZON)
            if arm == "gap":
                require(boundaries["world"]["event"] == boundaries["sites"]["event"], "different intervention replays")
                require(boundaries["world"]["after"]["hash"] == boundaries["sites"]["after"]["hash"], "post-gap mismatch")
                experiment.write_json(output / f"analyses/{prefix}.boundary.json", boundaries)
            removal = boundaries["world"]["event"] if arm == "gap" else None
            analysis = competition.analyze(output / f"traces/{prefix}.world.gz", output / f"traces/{prefix}.sites.gz",
                                           case, capacity, HORIZON, 8, removal)
            replay = ["bin/replay", *base[1:]]
            replay_path = output / f"analyses/{prefix}.replay.json"
            experiment.command_run(replay, replay_path, output, 180)
            commands.append(replay)
            last = experiment.read_json(replay_path)
            maintenance.check_identity(last, "selective", capacity)
            require(last["hash"] == analysis["world"]["final"]["hash"]
                    and last["model_crc32"] == "dc5e849d", "independent final replay mismatch")
            if removal:
                require(last["removed_id"] == removal["id"] and last["gap_tick"] == GAP_TICK
                        and last["gap_protocol"] == PROTOCOL, "replay used a different gap")
            experiment.write_json(output / f"analyses/{prefix}.json", analysis)
            result[arm] = {"analysis": analysis, "boundaries": boundaries, "verified_prefix_samples": verified}
        event = result["gap"]["boundaries"]["world"]["event"]
        for arm in ("control", "gap"):
            later = checkpoints(output / f"traces/{case['id']}.{arm}.world.gz", {76800})[76800]
            result[arm]["metrics"] = metrics(result[arm]["analysis"], event, later, GAP_TICK, HORIZON)
        result["commands"] = commands
        print(f"{capacity}/{case['id']} {case['scenario']}/{case['seed']}: "
              f"births {result['control']['metrics']['births']} -> {result['gap']['metrics']['births']}", flush=True)
        return result

    with ThreadPoolExecutor(max_workers=jobs) as pool:
        cases = list(pool.map(run_case, selected))
    experiment.write_json(output / "summary.json", summarize(cases))
    experiment.write_json(output / "cases.json", [{**{k: c[k] for k in ("id", "scenario", "seed", "commands")},
                           **{arm: {k: v for k, v in c[arm].items() if k != "analysis"} for arm in ("control", "gap")}}
                          for c in cases])
    representative = next(c for c in cases if c["scenario"] == "rainfed" and c["seed"] == maintenance.FRAME_SEED)
    frames = []
    for arm in ("control", "gap"):
        group = []
        points = checkpoints(output / f"traces/{representative['id']}.{arm}.world.gz", {GAP_TICK, 65280, HORIZON})
        for index, (tick, apply_gap) in enumerate(((GAP_TICK, False), (GAP_TICK, arm == "gap"),
                                                  (65280, arm == "gap"), (HORIZON, arm == "gap"))):
            name = f"{arm}-{index}"
            frame = f"frames/{name}.rgb565"
            command = ["bin/replay", "model.tgm", "rainfed", experiment.NIGHT_POLICY, "0x"+maintenance.FRAME_SEED,
                       "--leaf-policy", "selective", "--ticks", str(tick), "--framebuffer", frame]
            if apply_gap:
                command += ["--gap-at", str(GAP_TICK)]
            experiment.command_run(command, output / f"frames/{name}.json", output, 180)
            value = experiment.read_json(output / f"frames/{name}.json")
            expected_hash = (representative["gap"]["boundaries"]["world"]["after"]["hash"]
                             if apply_gap and tick == GAP_TICK else points[tick]["hash"])
            raw = (output / frame).read_bytes()
            require(value["hash"] == expected_hash and len(raw) == 115200
                    and value["framebuffer_crc32"] == f"{zlib.crc32(raw):08x}", "native frame mismatch")
            write_png(output / f"frames/{name}.png", 240, 240, rgb565be_to_rgb888(raw))
            group.append({"id": name, "tick": tick, "framebuffer": frame, "command": command, "result": value})
        frames.append(group)
    experiment.write_json(output / "frames.json", {"groups": frames, "sheet": contact_sheet(output, frames)})
    require(experiment.source_files() == sources, "source changed during gap collection")
    require(all(experiment.digest(output / name) == sha for name, sha in frozen.items()), "frozen input changed")
    record.update(status="complete", artifacts={str(p.relative_to(output)): experiment.digest(p)
                                               for p in output.rglob("*") if p.is_file()})
    experiment.write_json(output / "manifest.json", record)
    print(f"Complete: {output}; manifest sha256={experiment.digest(output / 'manifest.json')}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--build", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--jobs", type=int, choices=(1, 2, 4), default=2)
    args = parser.parse_args()
    collect(args.bundle, args.build, args.output, args.jobs)


if __name__ == "__main__":
    main()
