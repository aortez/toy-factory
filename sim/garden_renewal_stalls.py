#!/usr/bin/env python3
"""Selected renewal-stall timelines and matched native captures; no intervention."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import shutil
import time
import zlib

import garden_sustained_renewal as sustained

mixed, pilot, fitness = sustained.mixed, sustained.pilot, sustained.fitness
experiment, require, gallery = sustained.experiment, sustained.require, pilot.gallery
DAY, STEP = sustained.DAY, sustained.STEP
RULE = "garden-renewal-stalls-v1"
PROTOCOL = "benchmarks/garden-longevity/renewal-stalls-protocol.md"
BASELINE_SHA = sustained.BASELINE_SHA
MODELS = {"original": ("g0", "dc5e849d"), "broad-final": ("g3", "c7c1b31e")}
SEEDS = ("1824c139", "4d5f9ee1")
PATCH = "17c29444"
FRAME_DAYS = (62, 78, 94, 110)
BANDS = ((30, 62), (62, 94), (94, 126))
PARENT_CLASSES = ("founder", "established-descendant", "unconfirmed-descendant")


def alive(p, tick):
    return p["birth_tick"] <= tick and (p["death_tick"] is None or p["death_tick"] > tick)


def confirmed(p, tick):
    due = p["birth_tick"] + DAY
    return due <= tick and alive(p, due)


def parent_class(p, tick):
    return "founder" if not p["parent"] else "established-descendant" if confirmed(p, tick) else "unconfirmed-descendant"


def qualifies(p, records, tick):
    return bool(p["parent"] and records[p["parent"]]["parent"] and confirmed(p, tick)
                and confirmed(records[p["parent"]], p["birth_tick"] + DAY))


def counts(trial, tick):
    plants = trial["lineages"]
    living = [p for p in plants if alive(p, tick)]
    return {"living": len(living), "living_ids": sorted(p["id"] for p in living),
            "living_generations": dict(Counter(str(p["generation"]) for p in living)),
            "births": sum(bool(p["parent"]) and p["birth_tick"] <= tick for p in plants),
            "deaths": sum(p["death_tick"] is not None and p["death_tick"] <= tick for p in plants),
            "seed_bank": sum(s["birth_tick"] <= tick and (s["end_tick"] is None or s["end_tick"] > tick)
                             for s in trial["seeds"]),
            "seeds_created": sum(s["birth_tick"] <= tick for s in trial["seeds"]),
            "seeds_expired": sum(s["outcome"] == "expired" and s["end_tick"] <= tick for s in trial["seeds"])}


def funnel(trial, start, end):
    plants, seeds = fitness.project(trial["lineages"], trial["seeds"], start, end + 2 * DAY, pilot.START, pilot.STOP)
    records = {p["id"]: p for p in plants}
    fields = ("purchases", "germinated", "expired", "pending", "confirmed", "qualifying", "natural_failure", "patch_failure", "unconfirmed")
    groups = {name: dict.fromkeys(fields, 0) for name in PARENT_CLASSES}
    parents = {}
    for s in seeds:
        if not start < s["birth_tick"] <= end:
            continue
        p = records[s["parent"]]
        rows = (groups[parent_class(p, s["birth_tick"])], parents.setdefault(str(p["id"]), dict.fromkeys(fields, 0)))
        for row in rows:
            row["purchases"] += 1
            row[s["outcome"]] += 1
        if s["child_id"] is None:
            continue
        child = records[s["child_id"]]
        due = child["birth_tick"] + DAY
        status = "confirmed" if confirmed(child, end + 2 * DAY) else \
                 "patch_failure" if child["death_tick"] is not None and child["death_tick"] <= due and child["environmental_death"] else \
                 "natural_failure" if child["death_tick"] is not None and child["death_tick"] <= due else "unconfirmed"
        for row in rows:
            row[status] += 1
            row["qualifying"] += qualifies(child, records, end + 2 * DAY)
    for row in [*groups.values(), *parents.values()]:
        require(row["purchases"] == row["germinated"] + row["expired"] + row["pending"] and
                row["germinated"] == sum(row[k] for k in ("confirmed", "natural_failure", "patch_failure", "unconfirmed")),
                "seed funnel does not reconcile")
    return {"days": [start // DAY, end // DAY], "followup_day": end // DAY + 2, "classes": groups, "parents": parents}


def lifetime_analysis(trial):
    records = {p["id"]: p for p in trial["lineages"]}
    events = []
    for p in trial["lineages"]:
        due = p["birth_tick"] + DAY
        if not p["parent"] or not confirmed(p, pilot.STOP):
            continue
        events.append({"id": p["id"], "parent": p["parent"], "generation": p["generation"],
                       "species": p["species"], "confirmation_tick": due, "birth_tick": p["birth_tick"],
                       "death_tick": p["death_tick"], "environmental_death": p["environmental_death"],
                       "parent_class_at_confirmation": parent_class(records[p["parent"]], due),
                       "qualifying": qualifies(p, records, due)})
    events.sort(key=lambda e: (e["confirmation_tick"], e["id"]))
    qualified = [e for e in events if e["qualifying"]]
    next_credit = []
    for e in qualified:
        first = max(94 * DAY + STEP, e["confirmation_tick"])
        last = min(pilot.STOP, e["confirmation_tick"] + sustained.CREDIT_AGE - STEP,
                   e["death_tick"] - STEP if e["death_tick"] is not None else pilot.STOP)
        if first <= last:
            next_credit.append({"id": e["id"], "tick": first})
    timeline = []
    for day in range(30, 127):
        tick = day * DAY
        row = counts(trial, tick)
        row.update(day=day, qualifying_alive=sum(qualifies(p, records, tick) and alive(p, tick) and
                        tick < p["birth_tick"] + DAY + sustained.CREDIT_AGE for p in trial["lineages"]),
                   confirmations_today=[e["id"] for e in events if tick - DAY < e["confirmation_tick"] <= tick],
                   qualifying_confirmations_today=[e["id"] for e in qualified if tick - DAY < e["confirmation_tick"] <= tick])
        timeline.append(row)
    gap = sustained.score_block(trial["lineages"], trial["seeds"], 62 * DAY, 94 * DAY, pilot.START, pilot.STOP)[0]
    return {"daily": timeline, "confirmations": events,
            "first_qualifying_confirmation": qualified[0] if qualified else None,
            "first_credit_after_gap": min(next_credit, key=lambda x: (x["tick"], x["id"])) if next_credit else None,
            "bands": [funnel(trial, a * DAY, b * DAY) for a, b in BANDS], "gap_score": gap,
            "lineages": trial["lineages"]}


def validate_census(rows, trial):
    samples = {}
    for row in rows:
        if row["type"] == "world":
            samples[row["tick"]] = row  # Last sample at a patch tick is post-disturbance.
    require(set(range(0, pilot.STOP + 1, DAY)) <= samples.keys(), "missing daily census")
    for tick, row in samples.items():
        # This inspector omits growth_policy for the ordinary neural night veto;
        # the fixed command/model and same-tick native hashes establish that mode.
        require(0 <= tick <= pilot.STOP and tick % STEP == 0 and row["node_capacity"] == 512 and
                row["leaf_policy"] == "selective" and row["leaf_environment"] == "leaf-maintenance-v1" and
                not any(k in row for k in ("growth_policy", "drainage_rule", "seed_reserve_rule", "root_bootstrap_rule")),
                "wrong census identity")
        c = counts(trial, tick)
        require(all(row[k] == c[k] for k in ("living", "births", "deaths", "seeds_created", "seeds_expired")) and
                len(row["seeds"]) == c["seed_bank"] and
                sorted(p["id"] for p in row["plants"] if not p["dead"]) == c["living_ids"], "census/lifetime disagreement")
    for checkpoint in trial["checkpoints"]:
        if checkpoint["tick"] in samples:
            row = samples[checkpoint["tick"]]
            require(row["hash"] == checkpoint["hash"] and row["nodes"] == checkpoint["nodes"], "census checkpoint differs")
    return samples


def validate_replay(value, trial, seed, crc, day, samples, raw=None):
    tick = day * DAY
    if day == 192:
        pilot.check_replay(value, trial, seed, crc, tick, raw, patch=PATCH)
    expected = {"schema_version": 1, "scenario": "rainfed-crowded", "policy": "neural-no-night-growth",
                "seed": seed, "tick": tick, "model_crc32": crc, "node_capacity": 512,
                "seed_dispersal": "wide-v1", "water_uptake": "headroom-v1", "leaf_environment": "leaf-maintenance-v1",
                "leaf_policy": "selective", "disturbance_protocol": "patch-death-v1", "disturbance_seed": PATCH}
    c = counts(trial, tick)
    expected.update({k: c[k] for k in ("living", "births", "deaths", "seed_bank")})
    expected.update(hash=samples[tick]["hash"], nodes=samples[tick]["nodes"])
    require(all(value.get(k) == v for k, v in expected.items()), "replay/census identity differs")
    require(not any(k in value for k in ("drainage_rule", "seed_reserve_rule", "root_bootstrap_rule", "gap_protocol")),
            "unexpected replay intervention")
    if raw is not None:
        require(len(raw) == gallery.FRAME_BYTES and value["framebuffer_crc32"] == f"{zlib.crc32(raw):08x}", "invalid frame")


def inspect_summary(samples):
    by_id = defaultdict(list)
    for tick, row in samples.items():
        if 62 * DAY <= tick <= 94 * DAY:
            for p in row["plants"]:
                if not p["dead"] and p["parent"]:
                    by_id[p["id"]].append((tick, p))
    fields = ("energy", "water", "stress", "nodes", "tips", "active_leaves", "flowers", "spent_flowers", "energy_income", "water_income")
    return {"frames": {str(d): samples[d * DAY] for d in FRAME_DAYS},
            "gap_descendant_samples": {str(i): {"parent": values[0][1]["parent"], "generation": values[0][1]["generation"],
                "sample_count": len(values), "first_tick": min(t for t, _ in values), "last_tick": max(t for t, _ in values),
                "ranges": {k: [min(p[k] for _, p in values), max(p[k] for _, p in values)] for k in fields}}
                for i, values in by_id.items()}}


def read_census(path):
    with path.open() as stream:
        return [json.loads(line) for line in stream]


def sampled_blockers(samples, records):
    """Daily observations, not unique seed fates or time-weighted blocker rates."""
    masks, flags, living, nodes = Counter(), Counter(), Counter(), []
    bits = {"moisture": 2, "light": 4, "plant_capacity": 8, "node_capacity": 16, "spacing": 32}
    for day in range(62, 95):
        row = samples[day * DAY]
        living[str(row["living"])] += 1
        nodes.append(row["nodes"])
        for seed in row["seeds"]:
            mask = seed["blockers"]
            if not records[seed["parent"]]["parent"] or mask & 1:
                continue
            masks[str(mask)] += 1
            for name, bit in bits.items():
                flags[name] += bool(mask & bit)
    return {"daily_checks": 33, "daily_living_histogram": dict(living), "daily_node_range": [min(nodes), max(nodes)],
            "non_dormant_descendant_seed_observations": sum(masks.values()),
            "blocker_masks": dict(masks), "blocker_observations": dict(flags)}


def review_diagnostics(root, result):
    diagnostics = {}
    for c in result["cases"]:
        samples = {r["tick"]: r for r in read_census(root / "census" / f"{c['id']}.jsonl") if r["type"] == "world"}
        records = {p["id"]: p for p in c["lifetimes"]["lineages"]}
        prior = [e for e in c["lifetimes"]["confirmations"] if e["qualifying"] and e["confirmation_tick"] <= 62 * DAY]
        last = max(prior, key=lambda e: e["confirmation_tick"], default=None)
        prior_credit_end = max((min(e["confirmation_tick"] + sustained.CREDIT_AGE,
                                   e["death_tick"] if e["death_tick"] is not None else pilot.STOP + STEP)
                                for e in prior), default=None)
        diagnostics[c["id"]] = {"sampled_blockers": sampled_blockers(samples, records),
            "latest_qualifying_confirmation_before_gap": last,
            "latest_credit_expiry_of_pre_gap_cohorts": prior_credit_end,
            "gap_deaths": [p for p in records.values() if p["death_tick"] is not None and 62 * DAY < p["death_tick"] <= 94 * DAY]}
    return diagnostics


def analyze(root):
    cases, groups = [], []
    for seed in SEEDS:
        for side, (name, crc) in MODELS.items():
            identity = f"{name}.{seed}"
            trial = experiment.read_json(root / "input" / f"{identity}.json")
            original = pilot.validate_trial(trial, seed, crc, patch=PATCH)
            samples = validate_census(read_census(root / "census" / f"{identity}.jsonl"), trial)
            validate_replay(experiment.read_json(root / "frames" / f"{identity}.192.json"), trial, seed, crc, 192, samples)
            frames = []
            for day in FRAME_DAYS:
                stem = f"{identity}.{day}"
                value = experiment.read_json(root / "frames" / f"{stem}.json")
                raw = (root / "frames" / f"{stem}.rgb565").read_bytes()
                validate_replay(value, trial, seed, crc, day, samples, raw)
                require(value == experiment.read_json(root / "frames" / f"{stem}.repeat.json") and
                        raw == (root / "frames" / f"{stem}.repeat.rgb565").read_bytes(), "frame repeat differs")
                frames.append({"id": stem, "day": day, "side": side, "seed": seed, "model_crc32": crc,
                               "hash": value["hash"], "framebuffer_crc32": value["framebuffer_crc32"],
                               "framebuffer": f"frames/{stem}.rgb565", "png": f"frames/{stem}.png"})
            ledger = lifetime_analysis(trial)
            require(side != "broad-final" or ledger["gap_score"]["rolling"]["ticks"] == 0, "selected stall no longer matches")
            cases.append({"id": identity, "seed": seed, "side": side, "model_crc32": crc, "original_primary": original,
                          "lifetimes": ledger, "inspector": inspect_summary(samples), "frames": frames,
                          "verified_census_samples": len(samples)})
            groups.append(frames)
    return {"rule": RULE, "role": "outcome-selected-stall-diagnostic-not-new-fitness", "source_manifest_sha256": BASELINE_SHA,
            "native_processes": 40, "native_replays": 36, "native_censuses": 4, "training_runs": 0,
            "cases": cases, "frame_groups": groups}


def verify(root):
    manifest = experiment.read_json(root / "manifest.json")
    require(manifest["status"] == "complete" and manifest["rule"] == RULE, "wrong/incomplete stall bundle")
    for name in manifest["artifacts"]:
        gallery.artifact(root, manifest, name)
    require(experiment.digest(root / "input/coverage-manifest.json") == BASELINE_SHA, "changed source manifest")
    source = experiment.read_json(root / "input/coverage-manifest.json")
    for dest, src in manifest["copied"].items():
        require(experiment.digest(root / dest) == source["artifacts"][src], "changed frozen input")
    result = analyze(root)
    require(result == experiment.read_json(root / "results.json"), "stall reanalysis differs")
    print("Verified four matched lifetime/census trajectories and 16 independently repeated native frames", flush=True)
    return result


def collect(baseline, inspector, output):
    require(output.is_relative_to(experiment.ROOT / "artifacts") and not output.exists() and
            not output.is_relative_to(baseline), "choose a fresh separate artifact output")
    require(experiment.digest(baseline / "manifest.json") == BASELINE_SHA, "wrong coverage bundle")
    mixed.verify(baseline)
    manifest = experiment.read_json(baseline / "manifest.json")
    require(all((experiment.ROOT / n).is_file() and experiment.digest(experiment.ROOT / n) == sha
                for n, sha in manifest["sources"].items() if n.endswith((".c", ".h"))), "native sources changed")
    require(experiment.digest(inspector.parent / "CMakeCache.txt") == manifest["artifacts"]["input/CMakeCache.txt"],
            "inspector build configuration differs")
    sources = experiment.source_files()
    inspector_sha = experiment.digest(inspector)
    output.mkdir(parents=True)
    for folder in ("input", "bin", "census", "frames"):
        (output / folder).mkdir()
    experiment.snapshot_sources(output, sources)
    copied = {"bin/garden-replay": "bin/garden-replay", "input/CMakeCache.txt": "input/CMakeCache.txt"}
    for name, _ in MODELS.values():
        copied[f"input/{name}.tgm"] = f"review/{name}.tgm"
        for seed in SEEDS:
            copied[f"input/{name}.{seed}.json"] = f"review/{name}.fresh-2.{seed}.json"
    for dest, src in copied.items():
        shutil.copy2(baseline / src, output / dest)
        require(experiment.digest(output / dest) == manifest["artifacts"][src], "input copy differs")
    shutil.copyfile(baseline / "manifest.json", output / "input/coverage-manifest.json")
    shutil.copy2(inspector, output / "bin/garden-inspect")
    require(experiment.digest(output / "bin/garden-inspect") == inspector_sha, "inspector copy differs")
    shutil.copyfile(experiment.ROOT / PROTOCOL, output / "protocol.md")
    frozen = {str(p.relative_to(output)): experiment.digest(p) for d in ("input", "bin") for p in (output / d).iterdir()}
    experiment.write_json(output / "started.json", {"rule": RULE, "sources": sources, "frozen": frozen, "copied": copied})
    begin, timings = time.monotonic(), []
    try:
        for seed in SEEDS:
            for side, (name, crc) in MODELS.items():
                identity, model = f"{name}.{seed}", output / "input" / f"{name}.tgm"
                require(pilot.model_crc(model) == crc, "model identity differs")
                target = output / "census" / f"{identity}.jsonl"
                command = [output / "bin/garden-inspect", model, "rainfed-crowded", "neural-no-night-growth", "0x" + seed,
                           "--leaf-policy", "selective", "--disturbance-seed", str(int(PATCH, 16)), "--population", "--ticks", str(pilot.STOP)]
                t = time.monotonic()
                experiment.command_run([str(v) for v in command], target, output, 120)
                timings.append({"artifact": str(target.relative_to(output)), "seconds": time.monotonic() - t})
                trial = experiment.read_json(output / "input" / f"{identity}.json")
                samples = validate_census(read_census(target), trial)
                for day in (*FRAME_DAYS, 192):
                    stem = f"{identity}.{day}"
                    raw = output / "frames" / f"{stem}.rgb565" if day != 192 else None
                    target = output / "frames" / f"{stem}.json"
                    value, elapsed = pilot.run_json(pilot.replay_command(output, model, seed, day * DAY, raw, patch=PATCH), target)
                    validate_replay(value, trial, seed, crc, day, samples, raw.read_bytes() if raw else None)
                    timings.append({"artifact": str(target.relative_to(output)), "seconds": elapsed})
                    if raw:
                        other_raw = output / "frames" / f"{stem}.repeat.rgb565"
                        other, elapsed = pilot.run_json(pilot.replay_command(output, model, seed, day * DAY, other_raw, patch=PATCH),
                                                        output / "frames" / f"{stem}.repeat.json")
                        require(other == value and other_raw.read_bytes() == raw.read_bytes(), "native frame repeat differs")
                        timings.append({"artifact": f"frames/{stem}.repeat.json", "seconds": elapsed})
                        gallery.write_png(output / "frames" / f"{stem}.png", 240, 240, gallery.rgb565be_to_rgb888(raw.read_bytes()))
                print("Captured and checked", side, seed, flush=True)
        result = analyze(output)
        require(result == analyze(output), "deterministic timeline reanalysis differs")
        gallery.contact_sheet(output, result["frame_groups"])
        require(len(timings) == 40, "wrong native process budget")
        require(experiment.source_files() == sources and all(experiment.digest(output / n) == sha for n, sha in frozen.items()),
                "sources or inputs changed during collection")
        experiment.write_json(output / "results.json", result)
        experiment.write_json(output / "timings.json", {"wall_seconds": time.monotonic() - begin, "calls": timings})
        artifacts = {str(p.relative_to(output)): experiment.digest(p) for p in output.rglob("*") if p.is_file()}
        experiment.write_json(output / "manifest.json", {"rule": RULE, "status": "complete", "copied": copied,
            "sources": sources, "artifacts": artifacts, "artifact_bytes": sum((output / n).stat().st_size for n in artifacts)})
    except BaseException as error:
        experiment.write_json(output / "failure.json", {"error": str(error)})
        raise
    verify(output)


def export(root, prefix):
    result = verify(root)
    require(not prefix.is_relative_to(root), "do not export inside frozen evidence")
    data, image, markdown, frames = [prefix.with_name(prefix.name + suffix) for suffix in ("-summary.json", ".png", "-gallery.md", "-frames")]
    require(all(not p.exists() for p in (data, image, markdown, frames)), "export already exists")
    frames.mkdir(parents=True)
    shutil.copyfile(root / "contact-sheet.png", image)
    lines = ["# Selected renewal stalls: matched native frames", "",
             "Outcome-selected cases, not a representative panel. Columns: **days 62, 78, 94, 110**.",
             "Rows: seed 1824c139 original/broad, then seed 4d5f9ee1 original/broad. Fresh-2 only.",
             "The first three views bracket the (62,94] zero-credit interval; the last is a later comparison.",
             "", f"![Matched native views]({image.name})", "", "| Frame | World hash | Framebuffer CRC32 |", "|---|---|---|"]
    for case in result["cases"]:
        for f in case["frames"]:
            target = frames / f"{f['id']}.png"
            shutil.copyfile(root / f["png"], target)
            require(experiment.digest(target) == experiment.digest(root / f["png"]), "PNG copy differs")
            lines.append(f"| [{case['side']} / {case['seed']} / day {f['day']}]({frames.name}/{target.name}) | `{f['hash']}` | `{f['framebuffer_crc32']}` |")
    sha = experiment.digest(root / "manifest.json")
    lines += ["", "All 16 frames reproduced pixel-for-pixel after independent resets and matched the",
              "same-tick population-inspector hashes. Four day-192 anchors match original saved hashes.",
              "Images alone do not establish reproductive health; see the [case study](renewal-stalls.md).", "",
              f"Manifest SHA-256: `{sha}`.", ""]
    with markdown.open("x") as stream:
        stream.write("\n".join(lines))
    experiment.write_json(data, result | {"manifest_sha256": sha, "timing": experiment.read_json(root / "timings.json"),
                                         "review_diagnostics": review_diagnostics(root, result)})


def check_export(root, prefix):
    result = verify(root)
    expected = result | {"manifest_sha256": experiment.digest(root / "manifest.json"),
                         "timing": experiment.read_json(root / "timings.json"), "review_diagnostics": review_diagnostics(root, result)}
    require(experiment.read_json(prefix.with_name(prefix.name + "-summary.json")) == expected, "portable summary differs")
    require(experiment.digest(prefix.with_name(prefix.name + ".png")) == experiment.digest(root / "contact-sheet.png"), "portable overview differs")
    for case in result["cases"]:
        for frame in case["frames"]:
            require(experiment.digest(prefix.with_name(prefix.name + "-frames") / f"{frame['id']}.png") ==
                    experiment.digest(root / frame["png"]), "portable frame differs")
    print("Portable stall summary, overview and all 16 frames match verified evidence")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, default=experiment.ROOT / "artifacts/garden-training-coverage-v1")
    parser.add_argument("--inspector", type=Path, default=experiment.ROOT / "artifacts/persistence-pilot-build/toy-factory-garden-inspect")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--export", type=Path)
    parser.add_argument("--check-export", type=Path)
    args = parser.parse_args()
    require(not (args.export and args.check_export) and
            (args.verify or not (args.export or args.check_export)), "export/check-export requires verify")
    if args.export:
        export(args.output.resolve(), args.export.resolve())
    elif args.check_export:
        check_export(args.output.resolve(), args.check_export.resolve())
    elif args.verify:
        verify(args.output.resolve())
    else:
        collect(args.baseline.resolve(), args.inspector.resolve(), args.output.resolve())


if __name__ == "__main__":
    main()
