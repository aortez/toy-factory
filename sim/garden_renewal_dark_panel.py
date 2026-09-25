#!/usr/bin/env python3
"""Fixed 64-day, four-world comparison of unchanged frozen dark-guard binaries."""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict, dataclass
import json
from pathlib import Path
from garden_plant_slots import plant_capacity
import shutil
import tempfile
import time
import zlib

import garden_renewal_dark_guard as guard
import garden_leaf_competition as competition
import garden_disturbance as disturbance

experiment, startup, gallery, require = guard.experiment, guard.startup, guard.gallery, guard.require
RULE = "garden-renewal-dark-panel-v1"
PROTOCOL = "benchmarks/garden-longevity/renewal-dark-panel-protocol.md"
BASELINE_SHA = "0078077eeabf0fe95393870a626ebb8f9c407d62d7f6225d5dce8f89fcbaaa52"
SEEDS = ("abf7af73", "58e36558", "0d983a80", "beda710e")
CONDITIONS = {"no-patch": None, "patch": "05d87ca0"}
DAY, STOP, LATE = 3840, 64*3840, 48*3840
FRAME_TICKS = (8*DAY, 32*DAY, STOP)


@dataclass(frozen=True)
class Case:
    seed: str
    condition: str
    arm: str

    @property
    def name(self):
        return f"{self.seed}.{self.condition}.{self.arm}"

    @property
    def patch(self):
        return CONDITIONS[self.condition]


CASES = tuple(Case(s, c, a) for s in SEEDS for c in CONDITIONS for a in guard.CASES)


def settings():
    require(tuple(experiment.trial_seeds(0x72707231, 4)) == SEEDS, "changed declared review seeds")
    return {"rule": RULE, "guard_rule": guard.GUARD, "baseline_manifest_sha256": BASELINE_SHA,
            "cases": [asdict(c) for c in CASES], "conditions": CONDITIONS, "stop": STOP, "late_start": LATE,
            "models": guard.settings()["models"], "routing": guard.settings()["routing"],
            "frame_ticks": list(FRAME_TICKS),
            "budget": {"traces": 32, "frame_replays": 96, "native_calls": 128, "training_calls": 0},
            "role": "reused review worlds, frozen focal routing, one patch schedule; not held-out qualification"}


def commands():
    calls = []
    for case in CASES:
        base = ["models/r2-n.tgm", "rainfed-crowded", experiment.NIGHT_POLICY, "0x"+case.seed,
                "--leaf-policy", "selective", "--focal-model", "models/r2-w.tgm", "--focal-founder", "5"]
        if case.patch:
            base += ["--disturbance-seed", "0x"+case.patch]
        for suffix in ("", ".repeat"):
            calls.append((f"traces/{case.name}{suffix}.jsonl.gz",
                          [f"bin/{case.arm}-inspect", *base, "--ecology", "--ticks", str(STOP)]))
        for tick in FRAME_TICKS:
            for suffix in ("", ".repeat"):
                stem = f"frames/{case.name}.{tick}{suffix}"
                calls.append((stem+".json", [f"bin/{case.arm}-replay", *base, "--ticks", str(tick),
                                             "--framebuffer", stem+".rgb565"]))
    return calls


def copies():
    names = [f"bin/{a}-{tool}" for a in guard.CASES for tool in ("inspect", "replay")]
    names += [f"models/{name}.tgm" for name in guard.settings()["models"]]
    names += [f"input/{a}-{name}" for a in guard.CASES for name in ("CMakeCache.txt", "build.ninja")]
    result = {n: n for n in names}
    result["input/native-source.tar.gz"] = "source.tar.gz"
    for arm in guard.CASES:
        result[f"input/{arm}.jsonl.gz"] = f"traces/{arm}.jsonl.gz"
        for extension in ("json", "rgb565"):
            result[f"input/{arm}.{8*DAY}.{extension}"] = f"frames/{arm}.{8*DAY}.{extension}"
    return result


def split_rows(rows, patch, stop=STOP):
    """Keep ordinary pre-event rows; preserve and validate every boundary triple."""
    expected = disturbance.schedule(int(patch, 16) if patch else None, stop)
    ordinary, boundaries, previous = [], {}, None
    iterator = iter(rows)
    for row in iterator:
        if row["type"] != "disturbance":
            require(row["type"] in ("world", "bid", "leaf-bid"), "unknown raw record")
            ordinary.append(row)
            previous = row
            continue
        index = len(boundaries)
        require(index < len(expected) and all(row[k] == v for k, v in expected[index].items()),
                "wrong/repeated patch schedule")
        after = next(iterator, None)
        require(previous is not None and previous["type"] == "world" and after is not None
                and after["type"] == "world", "missing patch boundary census")
        disturbance.validate_boundary(previous, after, row)
        require(row["tick"] not in boundaries, "duplicate patch boundary")
        boundaries[row["tick"]] = {"before": previous, "event": row, "after": after}
        previous = after
    require(len(boundaries) == len(expected), "truncated patch schedule")
    return ordinary, boundaries


def population(row, records):
    live = [p for p in row["plants"] if not p["dead"]]
    require(len(live) == row["living"], "wrong living count")
    species, families = Counter(p["species"] for p in live), Counter(records[p["id"]]["founder"] for p in live)
    bank = [records[s["parent"]] for s in row["seeds"]]
    return {"tick": row["tick"], "hash": row["hash"], "living": len(live),
            "living_founders": sum(p["parent"] == 0 for p in live),
            "living_descendants": sum(p["parent"] != 0 for p in live),
            "species": dict(species), "families": {str(k): v for k, v in sorted(families.items())},
            "living_species": len(species), "living_families": len(families),
            "extant_species": sorted(set(species) | {p["species"] for p in bank}),
            "extant_families": sorted(set(families) | {p["founder"] for p in bank}),
            "seeds_remaining": len(row["seeds"]), "extinct": not live and not bank,
            **{k: row[k] for k in ("births", "deaths", "seeds_created", "seeds_expired", "max_generation", "nodes")}}


def supplementary(rows, boundaries, records, case, stop=STOP, late=LATE):
    """Independent leaf/stress checks and exact [start,stop) time exposure."""
    previous, daily, exposures, seen, peaks = None, [], {k: Counter() for k in ("whole", "late")}, set(), Counter()
    routing = settings()["routing"]
    for row in rows:
        tick = row["tick"]
        require(row.get("weather_seed") == case.seed and row.get("focal_policy") == routing,
                "wrong world/routing metadata")
        plants = {p["id"]: p for p in row["plants"]}
        old = {p["id"]: p for p in previous["plants"]} if previous else {}
        for identity, p in plants.items():
            record = records[identity]
            if identity not in seen:
                require(record["birth_tick"] == tick, "missing birth census")
                parent = record["parent"]
                if parent:
                    require(parent in seen and parent < identity and record["species"] == records[parent]["species"]
                            and record["generation"] == records[parent]["generation"]+1, "invalid ancestry")
                record["founder"] = records[parent]["founder"] if parent else identity
                record["genome"] = p["genome"]
                seen.add(identity)
            require(p["genome"] == record["genome"], "traits changed within lifetime")
            if tick and not p["dead"]:
                prior = old.get(identity)
                values = startup.resources.budget(prior, p, tick)
                startup.check_leaf(prior, p)
                if prior is not None:
                    guard.reference.prior.check_stress(prior, p, tick, values)
                else:
                    require(p["stress"] == 0 and not p["flags"] & 6, "invalid newborn stress")
        if previous is not None:
            values = Counter(living_steps=previous["living"],
                descendant_steps=sum(p["parent"] != 0 and not p["dead"] for p in old.values()),
                tipless_steps=sum(p["tips"] == 0 and not p["dead"] for p in old.values()),
                world_steps=1, node_full_steps=previous["nodes"] == 512,
                plant_full_steps=len(previous["plants"]) == plant_capacity(previous), seed_full_steps=len(previous["seeds"]) == 8)
            exposures["whole"].update(values)
            if previous["tick"] >= late:
                exposures["late"].update(values)
        after = boundaries.get(tick, {}).get("after", row)
        peaks["nodes"] = max(peaks["nodes"], after["nodes"])
        peaks["plant_slots"] = max(peaks["plant_slots"], len(after["plants"]))
        if tick % DAY == 0:
            daily.append(population(after, records))
        previous = after
    require(previous is not None and previous["tick"] == stop and len(seen) == len(records), "incomplete population")
    return {"daily": daily, "exposure": exposures, "peak": peaks}


def summary(world, extra, guard_audit):
    records = world["lineages"]
    windows = {}
    for name, start in (("whole", 0), ("late", LATE)):
        w = world["windows"][name]
        deaths = [p for p in records if p["death_tick"] is not None and start < p["death_tick"] <= STOP]
        natural = [p for p in deaths if not p.get("environmental_death")]
        seed_key = "seeds_created" if name == "whole" else "late_seeds_created"
        children = [p for p in records if p["parent"]]
        windows[name] = {"births": w["births"], "natural_deaths": len(natural),
            "environmental_deaths": len(deaths)-len(natural),
            "natural_death_causes": dict(Counter(startup.SHORTAGES[p["death_flags"] & 6] for p in natural)),
            "seeds_created": w["seeds_created"], "seeds_expired": w["seeds_expired"],
            "descendant_seeds": sum(p[seed_key] for p in children),
            "seed_producing_descendant_parents": sum(p[seed_key] > 0 for p in children),
            "checked_live_steps": w["budget_checked_live_steps"], "terminal_steps_unaccounted": w["terminal_steps"],
            "cohort": world["lifetimes"]["whole" if name == "whole" else "late_born"],
            "exposure": extra["exposure"][name]}
        require(len(natural) == w["natural_deaths"] and len(deaths) == w["deaths"], "death classification mismatch")
    return {"final": extra["daily"][-1], "windows": windows, "peak": extra["peak"],
            "guard": {k: v for k, v in guard_audit.items() if k != "events"}}


def check_frame(value, sample, case, tick, raw, events):
    expected = {"schema_version": 1, "scenario": "rainfed-crowded", "seed": case.seed,
        "policy": experiment.NIGHT_POLICY, "model_crc32": settings()["models"]["r2-n"],
        "node_capacity": 512, "seed_dispersal": "wide-v1", "water_uptake": "headroom-v1",
        "leaf_policy": "selective", "leaf_environment": "leaf-maintenance-v1", "tick": tick,
        "focal_policy": settings()["routing"], "plant_slots": len(sample["plants"]),
        "seed_bank": len(sample["seeds"]),
        "descendants": sum(p["parent"] != 0 and not p["dead"] for p in sample["plants"]),
        **{k: sample[k] for k in ("hash", "living", "nodes", "births", "deaths", "sun_phase",
                                 "sun_strength", "rain_rate", "rain_deposited", "rain_runoff", "moisture")}}
    if case.patch:
        expected.update(disturbance_protocol=disturbance.PROTOCOL, disturbance_seed=case.patch,
                        disturbance_events=sum(e["tick"] <= tick for e in events),
                        environmental_deaths=sum(len(e["killed"]) for e in events if e["tick"] <= tick))
    else:
        require(not any(k in value for k in ("disturbance_protocol", "disturbance_seed", "disturbance_events", "environmental_deaths")),
                "patch metadata in control condition")
    require(value.get("dark_guard_rule") == (guard.GUARD if case.arm == "guard" else None), "wrong frame guard")
    require(all(value.get(k) == v for k, v in expected.items()), "frame/census metadata mismatch")
    require(len(raw) == gallery.FRAME_BYTES and f"{zlib.crc32(raw):08x}" == value["framebuffer_crc32"], "framebuffer differs")


def analyze_case(root, case, create=False):
    path = root / f"traces/{case.name}.jsonl.gz"
    require(experiment.digest(path) == experiment.digest(root / f"traces/{case.name}.repeat.jsonl.gz"), "native repeat differs")
    raw, boundaries = split_rows(startup.read_trace(path), case.patch)
    routed, _ = guard.prior.neighbors.check_routing(iter(raw), guard.prior.ROUTE)
    accounted, audit = guard.accounting_rows(iter(raw), case.arm, stop=STOP, boundaries=boundaries, retain_events=False)
    worlds = [r for r in accounted if r["type"] == "world"]
    for name, rows in (("accounting", accounted), ("worlds", worlds)):
        target = root / f"traces/{case.name}.{name}.jsonl.gz"
        if create:
            guard.write_accounting(target, rows)
        require(rows == list(startup.read_trace(target)), "derived trace differs")
    world, _ = competition.world_analysis(root / f"traces/{case.name}.worlds.jsonl.gz", "selective", 512, STOP, LATE,
                                        disturbances=boundaries)
    tips = startup.tips.analyze_stream((json.dumps(r) for r in accounted if r["type"] != "leaf-bid"),
                                     STOP, LATE, 512, disturbances=boundaries)
    records = {p["id"]: p for p in world["lineages"]}
    for tip in tips["lineages"]:
        require(all(tip[k] == records[tip["id"]][k] for k in ("parent", "species", "birth_tick", "death_tick")),
                "tip/resource lifetimes differ")
    extra = supplementary(worlds, boundaries, records, case)
    for window in ("whole", "late"):
        require(all(tips["windows"][window][k] == extra["exposure"][window][k]
                    for k in ("living_steps", "tipless_steps", "world_steps")), "independent exposure differs")
    events = [b["event"] for b in boundaries.values()]
    frames = []
    samples = {w["tick"]: boundaries.get(w["tick"], {}).get("after", w) for w in worlds if w["tick"] in FRAME_TICKS}
    for tick in FRAME_TICKS:
        stem = f"frames/{case.name}.{tick}"
        value = experiment.read_json(root / (stem+".json"))
        pixels = (root / (stem+".rgb565")).read_bytes()
        check_frame(value, samples[tick], case, tick, pixels, events)
        require(value == experiment.read_json(root / (stem+".repeat.json")) and
                pixels == (root / (stem+".repeat.rgb565")).read_bytes(), "frame repeat differs")
        if case.seed == startup.SEED and tick == 8*DAY:
            old = experiment.read_json(root / f"input/{case.arm}.{tick}.json")
            ignored = {"disturbance_protocol", "disturbance_seed", "disturbance_events", "environmental_deaths"}
            require({k:v for k,v in value.items() if k not in ignored} == {k:v for k,v in old.items() if k not in ignored}
                    and pixels == (root / f"input/{case.arm}.{tick}.rgb565").read_bytes(), "saved eight-day frame differs")
        frames.append({"id": f"{case.name}.{tick}", "case": case.name, "tick": tick,
                       "result": value, "framebuffer": stem+".rgb565", "png": stem+".png"})
    return {"case": asdict(case), "summary": summary(world, extra, audit), "lineages": world["lineages"],
            "daily": extra["daily"], "events": events, "routing": routed,
            "tip_audit": {k: tips[k] for k in ("totals", "windows")}}, frames


def prefix(path, end):
    for row in startup.read_trace(path):
        require(row["tick"] <= end and row["type"] != "disturbance", "invalid prefix boundary")
        yield row
        if row["type"] == "world" and row["tick"] == end:
            return
    raise RuntimeError("truncated shared prefix")


def prefix_checks(root):
    result = {}
    for seed in SEEDS:
        for arm in guard.CASES:
            first = root / f"traces/{seed}.no-patch.{arm}.jsonl.gz"
            second = root / f"traces/{seed}.patch.{arm}.jsonl.gz"
            result[f"{seed}.{arm}"] = guard.prior.check_control(prefix(first, disturbance.FIRST), prefix(second, disturbance.FIRST))
    for condition in CONDITIONS:
        for arm in guard.CASES:
            path = root / f"traces/{startup.SEED}.{condition}.{arm}.jsonl.gz"
            result[f"old.{condition}.{arm}"] = guard.prior.check_control(prefix(path, 8*DAY), startup.read_trace(root/f"input/{arm}.jsonl.gz"))
    return result


def aggregate(cases):
    result = {}
    fields = ("births", "natural_deaths", "environmental_deaths", "seeds_created", "seeds_expired",
              "descendant_seeds", "seed_producing_descendant_parents")
    for condition in CONDITIONS:
        by_arm = {}
        for arm in guard.CASES:
            group = [cases[Case(s, condition, arm).name]["summary"] for s in SEEDS]
            final = Counter()
            windows = {}
            for g in group:
                final.update({k:g["final"][k] for k in ("living", "living_founders", "living_descendants", "extinct")})
                final["three_species_worlds"] += g["final"]["living_species"] == 3
                final["one_species_worlds"] += g["final"]["living_species"] == 1
            for name in ("whole", "late"):
                totals, cohort, exposure = Counter(), Counter(), Counter()
                for g in group:
                    w = g["windows"][name]
                    totals.update({k:w[k] for k in fields})
                    totals["worlds_with_births"] += w["births"] > 0
                    totals["worlds_with_descendant_seeds"] += w["descendant_seeds"] > 0
                    cohort.update(w["cohort"])
                    exposure.update(w["exposure"])
                windows[name] = {"totals": totals, "cohort": cohort, "exposure": exposure}
            by_arm[arm] = {"worlds": len(group), "final": final, "windows": windows}
        paired = []
        for seed in SEEDS:
            a,b = [cases[Case(seed, condition, arm).name]["summary"] for arm in guard.CASES]
            paired.append({"seed": seed, "final_delta": {k:b["final"][k]-a["final"][k] for k in
                ("living", "living_founders", "living_descendants", "living_species", "living_families")},
                "window_delta": {name:{k:b["windows"][name][k]-a["windows"][name][k] for k in fields}
                                 for name in ("whole", "late")},
                "closing_cohort_delta": {k:b["windows"]["late"]["cohort"][k]-a["windows"]["late"]["cohort"][k]
                    for k in a["windows"]["late"]["cohort"]}})
        result[condition] = {"arms": by_arm, "pairs": paired}
    return result


def analyze(root, create=False):
    prefixes, results, frames = prefix_checks(root), {}, []
    for case in CASES:
        result, captures = analyze_case(root, case, create)
        results[case.name] = result
        frames.extend(captures)
        print("Audited", case.name, flush=True)
    return {"rule": RULE, "settings": settings(), "prefix_checks": prefixes,
            "cases": results, "aggregate": aggregate(results), "frames": frames}


def check_inputs(root):
    require(experiment.digest(root/"input/baseline-manifest.json") == BASELINE_SHA, "wrong frozen baseline")
    baseline = experiment.read_json(root/"input/baseline-manifest.json")
    for dest, source in copies().items():
        require(experiment.digest(root/dest) == baseline["artifacts"][source], "frozen input changed")
    require(experiment.read_json(root/"input/settings.json") == settings(), "panel settings changed")
    old = guard.prior.prior.native_hashes(root/"input/native-source.tar.gz")
    new = guard.prior.prior.native_hashes(root/"source.tar.gz")
    require(old == new, "native sources changed; rule must remain frozen")
    started = experiment.read_json(root/"started.json")
    require(all(started["sources"].get(k) == v for k,v in new.items()) and
            experiment.digest(root/"input/protocol.md") == started["sources"][PROTOCOL], "source/protocol provenance differs")


def check_capture(root):
    check_inputs(root)
    capture = experiment.read_json(root/"capture.json")
    require(capture["rule"] == RULE and capture["settings"] == settings() and
            [(c["artifact"],c["command"]) for c in capture["calls"]] == commands(), "wrong native panel")
    for n in capture["artifacts"]:
        gallery.artifact(root, capture, n)
    for target, command in commands():
        require(target in capture["artifacts"] and ("--framebuffer" not in command or command[-1] in capture["artifacts"]),
                "missing native capture")
    require(all(experiment.digest(root/n) == sha for n,sha in experiment.read_json(root/"started.json")["frozen"].items()),
            "frozen inputs changed")
    return capture


def verify(root):
    manifest = experiment.read_json(root/"manifest.json")
    require(manifest["rule"] == RULE and manifest["status"] == "complete", "incomplete panel")
    require(set(manifest["artifacts"]) == {str(p.relative_to(root)) for p in root.rglob("*") if p.is_file() and
            p != root/"manifest.json"}, "extra/missing artifact")
    for name in manifest["artifacts"]:
        gallery.artifact(root, manifest, name)
    capture = check_capture(root)
    require(manifest["sources"] == experiment.read_json(root/"started.json")["sources"] and
            experiment.read_json(root/"timings.json")["calls"] == capture["calls"], "provenance differs")
    result = analyze(root)
    require(result == experiment.read_json(root/"results.json"), "panel reanalysis differs")
    print("Verified 16 trajectories, all guard/resource/tip ledgers, patch boundaries and 48 repeated frames", flush=True)
    return result


def finish(root):
    require(not (root/"manifest.json").exists() and not (root/"results.json").exists(), "already finalized")
    capture = check_capture(root)
    sources = experiment.read_json(root/"started.json")["sources"]
    require(experiment.source_files() == sources, "sources changed during capture")
    begin = time.monotonic()
    result = analyze(root, create=True)
    require(result == analyze(root), "analysis repeat differs")
    for frame in result["frames"]:
        gallery.write_png(root/frame["png"], 240,240,gallery.rgb565be_to_rgb888((root/frame["framebuffer"]).read_bytes()))
    for condition in CONDITIONS:
        groups = [[next(f for f in result["frames"] if f["case"] == Case(seed,condition,arm).name and f["tick"] == tick)
                   for tick in FRAME_TICKS for arm in guard.CASES] for seed in SEEDS]
        folder = root/"galleries"/condition
        folder.mkdir(parents=True)
        # contact_sheet resolves each original framebuffer against its output root.
        groups = [[{**f,"framebuffer":"../../"+f["framebuffer"]} for f in group] for group in groups]
        gallery.contact_sheet(folder, groups)
    require(experiment.source_files() == sources, "sources changed during analysis")
    check_capture(root)
    experiment.write_json(root/"results.json", result)
    experiment.write_json(root/"timings.json", {"capture_seconds":capture["capture_seconds"],
        "analysis_and_repeat_seconds":time.monotonic()-begin,"calls":capture["calls"]})
    artifacts = {str(p.relative_to(root)):experiment.digest(p) for p in root.rglob("*") if p.is_file()}
    experiment.write_json(root/"manifest.json", {"rule":RULE,"status":"complete","sources":sources,"artifacts":artifacts,
        "artifact_bytes":sum((root/n).stat().st_size for n in artifacts)})
    print("Panel complete: exact repeated analysis and captures verified", flush=True)


def collect(baseline, output):
    require(not output.exists() and output.is_relative_to(experiment.ROOT/"artifacts") and not output.is_relative_to(baseline),
            "choose fresh separate artifacts output")
    require(experiment.digest(baseline/"manifest.json") == BASELINE_SHA, "wrong baseline")
    guard.verify(baseline)
    sources = experiment.source_files()
    output.mkdir(parents=True)
    experiment.snapshot_sources(output, sources)
    for name in ("input","bin","models","traces","frames"):
        (output/name).mkdir()
    for dest,source in copies().items():
        shutil.copy2(baseline/source,output/dest)
    shutil.copy2(baseline/"manifest.json",output/"input/baseline-manifest.json")
    shutil.copy2(experiment.ROOT/PROTOCOL,output/"input/protocol.md")
    experiment.write_json(output/"input/settings.json",settings())
    frozen = {str(p.relative_to(output)):experiment.digest(p) for p in output.rglob("*") if p.is_file()}
    experiment.write_json(output/"started.json",{"rule":RULE,"sources":sources,"frozen":frozen})
    begin,timings = time.monotonic(),[]
    try:
        check_inputs(output)
        for target,command in commands():
            start = time.monotonic()
            if target.endswith(".gz"):
                with tempfile.TemporaryDirectory(prefix="garden-dark-panel-") as temp:
                    raw = Path(temp)/"trace.jsonl"
                    try:
                        experiment.command_run(command,raw,output,180)
                    except BaseException:
                        if raw.exists():
                            shutil.copy2(raw,output/(target+".failed-stdout"))
                        raise
                    experiment.compress(raw,output/target)
            else:
                experiment.command_run(command,output/target,output,180)
            timings.append({"artifact":target,"command":command,"seconds":time.monotonic()-start})
            print(f"Captured {len(timings)}/128: {target}",flush=True)
        require(experiment.source_files() == sources, "sources changed during capture")
        artifacts = {str(p.relative_to(output)):experiment.digest(p) for p in output.rglob("*") if p.is_file()}
        experiment.write_json(output/"capture.json",{"rule":RULE,"settings":settings(),"artifacts":artifacts,
            "calls":timings,"capture_seconds":time.monotonic()-begin})
        finish(output)
    except BaseException as error:
        experiment.write_json(output/"failure.json",{"error":str(error),"completed_calls":timings})
        raise


def gallery_markdown(result):
    lines = ["# Dark guard: fixed 64-day native review", "", "Four reused review worlds; not independent held-out tests.",
             "Columns pair control/guard at **days 8, 32 and 64**. Rows follow the four declared seeds.",
             "Every image uses the production renderer and matches its census and exact repeat.", ""]
    for condition in CONDITIONS:
        lines += [f"## {condition}","",f"![Fixed {condition} panel](renewal-dark-panel-{condition}.png)","",
                  "| Row | World seed | End living control / guard | Closing births control / guard | Closing descendant seeds control / guard |",
                  "|---:|---|---:|---:|---:|"]
        for i,seed in enumerate(SEEDS,1):
            a,b = [result["cases"][Case(seed,condition,arm).name]["summary"] for arm in guard.CASES]
            lines.append(f"| {i} | `{seed}` | {a['final']['living']} / {b['final']['living']} | "
                f"{a['windows']['late']['births']} / {b['windows']['late']['births']} | "
                f"{a['windows']['late']['descendant_seeds']} / {b['windows']['late']['descendant_seeds']} |")
        for seed in SEEDS:
            lines += ["",f"### {seed}","","| Day | Control | Guard |","|---:|---|---|"]
            for tick in FRAME_TICKS:
                values = [next(f for f in result["frames"] if f["case"] == Case(seed,condition,arm).name and f["tick"] == tick)
                          for arm in guard.CASES]
                lines.append(f"| {tick//DAY} | " + " | ".join(f"![{f['id']}](renewal-dark-panel-frames/{f['id']}.png)" for f in values)+" |")
    return "\n".join(lines)+"\n"


def export(root, prefix, check=False):
    require(not prefix.is_relative_to(root), "cannot export into frozen evidence")
    result = verify(root)
    value = {**result,"manifest_sha256":experiment.digest(root/"manifest.json"),"timing":experiment.read_json(root/"timings.json")}
    target = prefix.with_name(prefix.name+"-summary.json")
    folder = prefix.with_name(prefix.name+"-frames")
    markdown = prefix.with_name(prefix.name+"-gallery.md")
    images = {prefix.with_name(prefix.name+f"-{c}.png"):root/f"galleries/{c}/contact-sheet.png" for c in CONDITIONS}
    images.update({folder/(f["id"]+".png"):root/f["png"] for f in result["frames"]})
    text = gallery_markdown(result).replace("renewal-dark-panel",prefix.name)
    if not check:
        require(not any(p.exists() for p in (target,folder,markdown,*images)),"export already exists")
        folder.mkdir()
        experiment.write_json(target,value)
        markdown.write_text(text)
        for dest,source in images.items():
            shutil.copy2(source,dest)
    require(experiment.read_json(target) == value and markdown.read_text() == text and
            all(experiment.digest(p) == experiment.digest(q) for p,q in images.items()), "portable panel differs")
    print("Portable summary, 48 native images and fixed galleries match verified evidence",flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline",type=Path,default=experiment.ROOT/"artifacts/garden-renewal-dark-guard-v1")
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--verify",action="store_true")
    parser.add_argument("--export",type=Path)
    parser.add_argument("--check-export",type=Path)
    args = parser.parse_args()
    require(not (args.export and args.check_export) and (args.verify or not (args.export or args.check_export)),"export requires verify")
    if args.export or args.check_export:
        export(args.output.resolve(),(args.export or args.check_export).resolve(),bool(args.check_export))
    elif args.verify:
        verify(args.output.resolve())
    else:
        collect(args.baseline.resolve(),args.output.resolve())


if __name__ == "__main__":
    main()
