#!/usr/bin/env python3
"""Explain frozen crowded recruitment pairs without changing policies or ecology."""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import gzip
import json
from pathlib import Path
import shutil
import zlib

import garden_diversity as diversity
import garden_establishment as establishment
import garden_experiments as experiment
import garden_leaf_competition as competition
import garden_policy_diagnostic as policy
from garden_gallery import contact_sheet, rgb565be_to_rgb888, write_png
from garden_resources import require

DAY, HORIZON = diversity.DAY, diversity.HORIZON
PANEL = ((256, "44", "fresh-4"), (256, "44", "fresh-1"),
         (512, "44", "fresh-1"), (512, "45", "fresh-1"))
PHASES = ("bright", "twilight", "night")


def phase(row):
    return "night" if row["sun_phase"] >= 128 else (
        "bright" if row["sun_strength"] >= 128 else "twilight")


def site_identity(row, capacity, side):
    # Compact site rows omit leaf metadata; every hash is bound to a checked world row.
    require(side in ("neural", "reserve"), "unknown growth policy")
    require(row.get("node_capacity", 256) == capacity and
            row.get("drainage_rule") is None and row.get("growth_policy") ==
            (policy.RESERVE if side == "reserve" else None), "wrong site identity")


def site_counts(row):
    values = competition.spatial_snapshot(row)
    seeds = row["seeds"]
    mature = [s for s in seeds if s["age"] >= establishment.DORMANCY]
    masks = [s[0] for s in row["sites"]]
    values.update(bank_empty=int(not seeds), bank_full=int(len(seeds) == 8),
                  mature_bank_empty=int(not mature), mature_seed_samples=len(mature),
                  bank_samples=int(bool(seeds)), mature_bank_samples=int(bool(mature)),
                  any_open_without_mature_seed=int(0 in masks and not mature),
                  mature_bank_any_open=int(0 in masks and bool(mature)),
                  spacing_open_columns=sum(not m & 32 for m in masks))
    for name, bits in establishment.BLOCKERS.items():
        values["blocked_" + name] = sum(bool(s["blockers"] & bits) for s in mature)
        values["only_" + name] = sum(s["blockers"] == bits for s in mature)
    for name, bits in competition.RELAXATIONS.items():
        values["actual_open_relax_" + name] = sum(not (s["blockers"] & ~bits) for s in mature)
    return values


def analyze(world_path, site_path, boundaries, prior, sparse_path, capacity, side,
            horizon=HORIZON, late_days=32):
    start = horizon - late_days * DAY
    require(0 <= start < horizon, "invalid closing window")
    require([b["event"] for b in boundaries["world"]] ==
            [b["event"] for b in boundaries["sites"]] == prior["events"], "event mismatch")
    for kind in ("world", "sites"):
        for b in boundaries[kind]:
            diversity.disturbance.validate_boundary(b["before"], b["after"], b["event"])
    for w, s in zip(boundaries["world"], boundaries["sites"], strict=True):
        for when in ("before", "after"):
            policy.identity(w[when], "off", side, capacity)
            site_identity(s[when], capacity, side)
            require(w[when]["hash"] == s[when]["hash"], "boundary hash mismatch")
    events = {b["event"]["tick"]: b for b in boundaries["world"]}
    require(len(events) == len(boundaries["world"]), "duplicate event")
    world, references = competition.world_analysis(world_path, "selective", capacity,
        horizon, start, disturbances=events,
        growth_policy=policy.RESERVE if side == "reserve" else None)
    require(world["final"] == prior["final"], "frozen final state mismatch")
    refs = {r["tick"]: r for r in references}
    checked_sparse, sparse_tick = 0, -15
    with gzip.open(sparse_path, "rt") as stream:
        for line in stream:
            r = json.loads(line)
            policy.identity(r, "off", side, capacity)
            require(r["tick"] > sparse_tick and r["tick"] in refs and
                    r["hash"] == refs[r["tick"]]["hash"],
                    "frozen sparse checkpoint mismatch")
            checked_sparse += 1
            sparse_tick = r["tick"]
    require(checked_sparse == prior["observed_rows"] and sparse_tick == horizon,
            "incomplete frozen sparse census")
    records = {r["id"]: r for r in world["lineages"]}
    require(records.keys() == {r["id"] for r in prior["lineages"]}, "lineage set mismatch")
    for old in prior["lineages"]:
        require(all(records[old["id"]][k] == old[k] for k in
            ("parent", "species", "generation", "column", "birth_tick", "death_tick", "death_flags")),
            "frozen lineage mismatch")
    cohorts = {name: competition.lifetime_cohort(records, horizon, begin) for name, begin in
               (("closing", start), ("post_establishment", 16*DAY))}
    require(all(cohorts[k] == prior["milestones"][str(horizon)][k] for k in cohorts),
            "frozen cohort mismatch")
    spatial = {w: {p: Counter() for p in PHASES} for w in ("whole", "late")}
    patches = []
    for b in boundaries["world"]:
        e = b["event"]
        patches.append({"event": e, "first": {}, "births": 0,
            "spatial": {p: Counter() for p in PHASES},
            "reclamation_delays": [records[k].get("reclaimed_tick", horizon + 15) - e["tick"]
                if "reclaimed_tick" in records[k] else None for k in e["killed"]]})
    site_events = {b["event"]["tick"]: b for b in boundaries["sites"]}

    def observed_rows(stream):
        patch_index, last_births = -1, 0
        for line in stream:
            r = json.loads(line)
            site_identity(r, capacity, side)
            tick = r["tick"]
            # Ordinary outcomes at a patch tick belong to the preceding interval.
            if patch_index >= 0:
                p = patches[patch_index]
                born = r["births"] - last_births
                if tick not in site_events:
                    p["births"] += born
                    if born:
                        p["first"].setdefault("birth", tick)
                else:
                    p["births_at_next_boundary_before_patch"] = born
            last_births = r["births"]
            # Whole/late counts match the ordinary post-step seed ledger exactly.
            if tick:
                values = site_counts(r)
                for window in (("whole", "late") if tick > start else ("whole",)):
                    spatial[window][phase(r)].update(values)
            if tick in site_events:
                patch_index += 1
                r = site_events[tick]["after"]
            if patch_index >= 0:
                p = patches[patch_index]
                p["last_sample_tick"] = tick
                p["spatial"][phase(r)].update(site_counts(r))
                masks = [s[0] for s in r["sites"]]
                for name, yes in (("node_headroom", not masks[0] & 16),
                        ("plant_slot", not masks[0] & 8),
                        ("spacing_open", any(not m & 32 for m in masks)),
                        ("any_open", 0 in masks),
                        ("mature_seed_at_open", any(s["blockers"] == 0 for s in r["seeds"]))):
                    if yes:
                        p["first"].setdefault(name, tick)
            yield line

    with gzip.open(site_path, "rt") as stream:
        seeds = establishment.analyze_stream(observed_rows(stream), references, late_days, capacity)
    for seed in seeds["seeds"]:
        if seed["outcome"] == "germinated":
            child = records[seed["child_id"]]
            require(child["birth_tick"] == seed["end_tick"] and child["parent"] == seed["parent"],
                    "seed/child lifetime mismatch")
    return {"world": world, "seeds": seeds, "spatial": spatial, "patches": patches,
            "cohorts": cohorts, "checked_sparse": checked_sparse}


def collect(bundles, output, jobs):
    output = output.resolve()
    require(not output.is_relative_to(experiment.ROOT) or
            output.is_relative_to(experiment.ROOT / "artifacts"), "unsafe output location")
    require(not output.exists(), "output already exists")
    inputs, cases = {}, []
    for capacity, root in bundles.items():
        root = root.resolve()
        m = experiment.read_json(root / "manifest.json")
        require(m["status"] == "complete" and m["kind"] == "garden-drainage-policy" and
                m["panel"] == "full" and m["node_capacity"] == capacity and
                m["horizon"] == HORIZON and m["reference_policy"] == policy.RESERVE,
                "wrong frozen panel")
        entries = experiment.read_json(establishment.verified(root, m, "cases.json"))
        for cap, identity, arm in PANEL:
            if cap != capacity:
                continue
            for side in ("neural", "reserve"):
                selected = [c for c in entries if c["id"] == identity and c["arm"] == arm
                            and c["setting"] == "off" and c["policy"] == side]
                require(len(selected) == 1, "missing/duplicate diagnostic case")
                c = selected[0]
                require(c["scenario"] == "rainfed-crowded" and c["seed"] ==
                        ("b61837dc" if identity == "44" else "c7f54e18"), "wrong selected world")
                cases.append({**c, "capacity": capacity, "key": f"{capacity}.{c['name']}"})
        inputs[capacity] = (root, m)
    require(len(cases) == 8, "incomplete diagnostic panel")
    output.mkdir(parents=True)
    for folder in ("input", "bin", "traces", "analyses", "frames"):
        (output / folder).mkdir()
    sources = experiment.source_files()
    experiment.snapshot_sources(output, sources)
    for capacity, (root, m) in inputs.items():
        # Executables were built for the old panel; require every C/header unchanged.
        require(all(sources.get(n) == sha for n, sha in m["source_sha256"].items()
                    if Path(n).suffix in (".c", ".h")), "native sources differ from frozen build")
        shutil.copy2(root / "manifest.json", output / f"input/{capacity}.manifest.json")
        for tool in ("inspect", "replay"):
            shutil.copy2(establishment.verified(root, m, f"bin/off-{tool}"),
                         output / f"bin/{capacity}-{tool}")
        model = establishment.verified(root, m, "model.tgm")
        require(experiment.digest(model) == competition.maintenance.MODEL_SHA, "wrong model")
        shutil.copy2(model, output / f"input/{capacity}.tgm")
    for c in cases:
        root, m = inputs[c["capacity"]]
        for old, new in ((f"analyses/{c['name']}.population.json", "population.json"),
                         (f"traces/{c['name']}.population.gz", "population.gz"),
                         (f"frames/{c['name']}.rgb565", "rgb565")):
            shutil.copy2(establishment.verified(root, m, old), output / f"input/{c['key']}.{new}")
    frozen = {str(p.relative_to(output)): experiment.digest(p) for p in output.rglob("*") if p.is_file()}
    manifest = {"kind": "garden-crowded-recruitment", "status": "started", "horizon": HORIZON,
        "source_sha256": sources, "input_manifests": {str(c): experiment.digest(r / "manifest.json")
            for c, (r, _) in inputs.items()}, "panel": PANEL, "expected_runs": 8}
    experiment.write_json(output / "started.json", manifest)

    def run(c):
        key, cap, side = c["key"], c["capacity"], c["policy"]
        schedule = diversity.SCHEDULES[c["arm"]]
        args = [f"input/{cap}.tgm", c["scenario"], policy.POLICIES[side], "0x" + c["seed"],
                "--leaf-policy", "selective", "--disturbance-seed", str(schedule)]
        bounds, commands = {}, []
        for kind, flag in (("world", "--ecology"), ("sites", "--seed-sites")):
            cmd = [f"bin/{cap}-inspect", *args, flag, "--ticks", str(HORIZON)]
            bounds[kind] = diversity.disturbance.capture(cmd, output / f"traces/{key}.{kind}.gz",
                output, "world" if kind == "world" else "seed-sites", schedule, HORIZON)
            commands.append(cmd)
            print(f"Captured {key} {kind}", flush=True)
        prior = experiment.read_json(output / f"input/{key}.population.json")
        data = analyze(output / f"traces/{key}.world.gz", output / f"traces/{key}.sites.gz", bounds,
            prior, output / f"input/{key}.population.gz", cap, side)
        frames = []
        for day in (64, 128, 192):
            cmd = [f"bin/{cap}-replay", *args, "--ticks", str(day * DAY)]
            frame = f"frames/{key}.rgb565"
            if day == 192:
                cmd += ["--framebuffer", frame]
            path = output / f"frames/{key}.{day}.json"
            experiment.command_run(cmd, path, output, 300)
            r = experiment.read_json(path)
            require(r["hash"] == prior["daily"][day]["hash"] and r["policy"] == policy.POLICIES[side]
                and r["model_crc32"] == "dc5e849d" and r["scenario"] == c["scenario"]
                and r["seed"] == c["seed"] and r["tick"] == day * DAY, "replay mismatch")
            competition.maintenance.check_identity({**r, "growth_policy":
                policy.RESERVE if side == "reserve" else None}, "selective", cap,
                growth_policy=policy.RESERVE if side == "reserve" else None)
            if day == 192:
                raw = (output / frame).read_bytes()
                require(len(raw) == 115200 and f"{zlib.crc32(raw):08x}" == r["framebuffer_crc32"]
                    and raw == (output / f"input/{key}.rgb565").read_bytes(), "frame mismatch")
                write_png(output / f"frames/{key}.png", 240, 240, rgb565be_to_rgb888(raw))
                frames.append({"id": key, "tick": day * DAY, "framebuffer": frame})
            commands.append(cmd)
        experiment.write_json(output / f"analyses/{key}.json", data)
        experiment.write_json(output / f"analyses/{key}.boundaries.json", bounds)
        print(f"Verified {key}: {data['seeds']['checkpoints_verified']} site/world checkpoints", flush=True)
        return {**c, "commands": commands, "frames": frames, "analysis": data}

    try:
        with ThreadPoolExecutor(max_workers=jobs) as pool:
            results = list(pool.map(run, cases))
        groups = [[f for c in results if (c["capacity"], c["id"], c["arm"]) == pair
                   for f in c["frames"]] for pair in PANEL]
        experiment.write_json(output / "frames.json", contact_sheet(output, groups))
        experiment.write_json(output / "cases.json", [{k: v for k, v in c.items() if k != "analysis"}
                                                       for c in results])
        experiment.write_json(output / "summary.json", [{"key": c["key"],
            **{k: c["analysis"][k] for k in ("cohorts", "spatial", "patches", "checked_sparse")},
            "world_windows": c["analysis"]["world"]["windows"],
            "seed_cohorts": c["analysis"]["seeds"]["cohorts"],
            "seed_windows": c["analysis"]["seeds"]["windows"]} for c in results])
        require(experiment.source_files() == sources, "sources changed during collection")
        require(all(experiment.digest(output / n) == sha for n, sha in frozen.items()), "input changed")
        manifest.update(status="complete", artifacts={str(p.relative_to(output)): experiment.digest(p)
            for p in output.rglob("*") if p.is_file()})
        experiment.write_json(output / "manifest.json", manifest)
        print(f"Complete {output}; manifest SHA256={experiment.digest(output / 'manifest.json')}", flush=True)
    except BaseException as error:
        experiment.write_json(output / "failure.json", {"error": str(error)})
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-256", type=Path, required=True)
    parser.add_argument("--baseline-512", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--jobs", type=int, choices=(1, 2, 4), default=2)
    args = parser.parse_args()
    collect({256: args.baseline_256, 512: args.baseline_512}, args.output, args.jobs)


if __name__ == "__main__":
    main()
