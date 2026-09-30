#!/usr/bin/env python3
"""Frozen-model narrow/wide placement screen; no trainer or firmware promotion."""

from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import shutil
import sys
import tempfile

import garden_landing_reach as reach
from garden_experiments import compress, digest, source_files, snapshot_sources, write_json
from garden_gallery import artifact, contact_sheet, rgb565be_to_rgb888, write_png
from garden_resources import require

ROOT, DAY, STEP, STOP = reach.ROOT, reach.DAY, reach.STEP, reach.STOP
prior, training = reach.prior, reach.prior.training
lifetimes = prior.previous.lifetimes
RULE = "garden-landing-range-v1"
PROTOCOL = "benchmarks/garden-seasons/landing-range-protocol.md"
INPUTS = reach.INPUTS
ARMS = {"narrow": 0, "wide": 1}
WIDE = "TOY_FACTORY_GARDEN_WIDE_DISPERSAL"


def cache_values(path):
    return {k.split(":")[0]: v for line in path.read_text().splitlines()
            if line and not line.startswith(("#", "//")) and "=" in line
            for k, v in [line.split("=", 1)]}


def check_builds(caches):
    require(set(caches) == set(ARMS), "both isolated builds required")
    values = {arm: cache_values(path) for arm, path in caches.items()}
    flags = {arm: {k: v for k, v in c.items() if k.startswith("TOY_FACTORY_GARDEN_")}
             for arm, c in values.items()}
    require(WIDE in flags["narrow"] and set(flags["narrow"]) == set(flags["wide"]), "mismatched ecology options")
    for arm in ARMS:
        require(all(v == ("ON" if arm == "wide" and k == WIDE else "OFF") for k, v in flags[arm].items()),
                "not an isolated range build: " + arm)
        require(values[arm].get("TOY_FACTORY_SIMULATOR_SANITIZERS") == "ON", "UBSan build required")
    shared = {k for c in values.values() for k in c if k.startswith(("CMAKE_C_FLAGS", "TOY_FACTORY_SIMULATOR_"))}
    shared |= {"CMAKE_C_COMPILER", "CMAKE_BUILD_TYPE", "CMAKE_HOME_DIRECTORY"}
    require(all(k in values["narrow"] and values["narrow"][k] == values["wide"].get(k) for k in shared),
            "compiler/source/build settings differ")
    return {"ecology": flags, "shared": {k: values["narrow"][k] for k in sorted(shared)}}


def history(result, case, model, arm, raw):
    """Same pure scoring, but validate explicit treatment identity, never erase it."""
    require(arm in ARMS and result["ledger_start_tick"] == 0, "unsupported arm/ledger")
    training.replay.check_result(result, case, STOP, model, ARMS[arm], raw)
    plants, seeds = result["lineages"], result["seeds"]
    training.rolling.descendants.index_records(plants, seeds, 0, STOP)
    require(sum(bool(p["parent"]) for p in plants) == result["births"] and
            sum(p["death_tick"] is not None for p in plants) == result["deaths"] and
            sum(p["death_tick"] is None for p in plants) == result["living"] and
            sum(s["outcome"] == "pending" for s in seeds) == result["seed_bank"], "unreconciled range ledger")
    return training.rolling.history(plants, seeds, 0, STOP)


def first_empty(result):
    """First post-step biological emptiness; simultaneous events apply together."""
    plants, seeds, stop = result["lineages"], result["seeds"], result["tick"]
    cuts = {0, stop}
    for p in [*plants, *seeds]:
        cuts.add(p["birth_tick"])
        end = p.get("death_tick") if "death_tick" in p else p["end_tick"]
        if end is not None:
            cuts.add(end)
    return next((t for t in sorted(cuts) if 0 <= t <= stop and
                 not any(lifetimes.alive(p, t) for p in plants) and
                 not any(s["birth_tick"] <= t and (s["end_tick"] is None or s["end_tick"] > t) for s in seeds)), None)


def metrics(result, audit, score):
    plants, seeds = result["lineages"], result["seeds"]
    records = {p["id"]: p for p in plants}
    late = [p for p in audit["plants"] if 62 * DAY < p["birth_tick"] <= 190 * DAY]
    counts = Counter(p["outcome"] for p in late)
    require(counts["pending"] == 0 and sum(counts.values()) == len(late), "late birth cohort lacks follow-up")
    confirmations = [p for p in plants if p["parent"] and 62 * DAY < p["birth_tick"] + DAY <= 190 * DAY and
                     lifetimes.qualifies(p, records, 190 * DAY)]
    fresh = [p for b in score["blocks"] for p in b["rolling"]["children"] if not p["carry_in"]]
    require({p["id"] for p in confirmations} == {p["id"] for p in fresh} and len(confirmations) == len(fresh),
            "confirmation/score mismatch")
    credits = [b["rolling"]["ticks"] for b in score["blocks"]]
    return {"births": result["births"], "deaths": result["deaths"], "living": result["living"],
            "seed_bank": result["seed_bank"], "first_empty_tick": first_empty(result),
            "seed_outcomes": dict(sorted(Counter(s["outcome"] for s in seeds).items())),
            "late_seed_expiries": sum(s["outcome"] == "expired" and 62 * DAY < s["end_tick"] <= 190 * DAY for s in seeds),
            "late_child_births": len(late), "late_child_survivors": counts["confirmed"], "late_child_deaths": counts["died"],
            "late_child_shortages": dict(sorted(Counter(p["death_shortage"] for p in late if p["outcome"] == "died").items())),
            "late_renewal_confirmations": len(confirmations),
            "historical_durable_parents": result["lifetimes"]["cycle_survivors_with_surviving_child"],
            "period_ticks": credits, "minimum_ticks": min(credits), "total_ticks": sum(credits),
            "zero_periods": credits.count(0), "terminal_tiers": [b["v2_key"][0] for b in score["blocks"]]}


def totals(rows):
    fields = ("births", "deaths", "living", "seed_bank", "late_seed_expiries", "late_child_births",
              "late_child_survivors", "late_child_deaths", "late_renewal_confirmations", "historical_durable_parents",
              "minimum_ticks", "total_ticks", "zero_periods")
    return {"worlds": len(rows), **{k: sum(r[k] for r in rows) for k in fields},
            "empty_worlds": sum(r["first_empty_tick"] is not None for r in rows),
            **{k: dict(sorted(sum((Counter(r[k]) for r in rows), Counter()).items()))
               for k in ("seed_outcomes", "late_child_shortages")}}


def gates(groups, worlds):
    checks = {}
    for climate in ("steady", "seasonal"):
        group = groups[climate]
        checks[climate + "_retain_key"] = group["scores"]["candidate"]["key"] >= group["scores"]["control"]["key"]
        checks[climate + "_retain_late_survivors"] = (group["totals"]["wide"]["late_child_survivors"] >=
                                                     group["totals"]["narrow"]["late_child_survivors"])
    checks["improve_key_or_renewal"] = any(groups[c]["scores"]["comparison"] > 0 or
        groups[c]["totals"]["wide"]["late_renewal_confirmations"] > groups[c]["totals"]["narrow"]["late_renewal_confirmations"]
        for c in ("steady", "seasonal"))
    checks["no_earlier_or_new_empty_world"] = all(w["arms"]["wide"]["metrics"]["first_empty_tick"] is None or
        (w["arms"]["narrow"]["metrics"]["first_empty_tick"] is not None and
         w["arms"]["wide"]["metrics"]["first_empty_tick"] >= w["arms"]["narrow"]["metrics"]["first_empty_tick"])
        for w in worlds)
    return checks


def compare(worlds):
    require(len(worlds) == 12 and len({w["id"] for w in worlds}) == 12 and
            all(set(w["arms"]) == set(ARMS) for w in worlds), "unmatched range panel")
    groups = {}
    for name in ("all", "steady", "seasonal", "single", "multi"):
        rows = [w for w in worlds if name == "all" or w["case"]["climate"] == name or w["model"].split("-")[0] == name]
        keys = [w["id"] for w in rows]
        scores = [{w["id"]: w["arms"][arm]["history"] for w in rows} for arm in ARMS]
        groups[name] = {"scores": training.individual.pair_group(*scores, keys),
                        "totals": {arm: totals([w["arms"][arm]["metrics"] for w in rows]) for arm in ARMS}}
    checks = gates(groups, worlds)
    return {"groups": groups, "gates": checks, "passes_screen": all(checks.values())}


def run_panel(binaries, inputs, root, jobs, *, controls=True):
    panel, archive, previous = reach.load_inputs(inputs)
    require(not root.exists() and set(binaries) == set(ARMS), "fresh matched panel required")
    (root / "models").mkdir(parents=True)
    (root / "frames").mkdir()
    models = previous["models"]
    for key, model in models.items():
        path = root / "models" / (key + ".tgl")
        with path.open("xb") as stream:
            stream.write(archive[model["model"]])
        require(digest(path) == model["sha256"], "wrong frozen controller")

    def one(saved):
        case, model, name = saved["case"], saved["model"], saved["id"]
        meta = models[model]["metadata"]
        base = ("replay", "models/" + model + ".tgl", case["scenario"], "0x" + case["seed"], "--climate", case["climate"], "--ledger")
        initials, arms = {}, {}
        for arm, binary in binaries.items():
            stem = arm + "--" + name
            initial = training.native(binary, root, *base, "--ticks", 0)
            require(initial["rules"] == ARMS[arm] and initial["model"] == meta and initial["tick"] == 0 and
                    initial["seeds"] == [] and all(p["parent"] == 0 for p in initial["lineages"]), "wrong initial state")
            initials[arm] = initial
            args = (*base, "--ticks", STOP)
            trace = root / (stem + ".jsonl")
            result = training.native(binary, root, *args, "--recruitment-trace", trace)
            raw_name, png_name = "frames/" + stem + ".rgb565be", "frames/" + stem + ".png"
            framed = training.native(binary, root, *args, "--framebuffer", raw_name)
            raw = (root / raw_name).read_bytes()
            require({**framed, "framebuffer_crc32": None} == result, "untraced capture changes trajectory")
            score = history(framed, case, meta, arm, raw)
            if controls:
                repeated = root / (stem + "-repeat.jsonl")
                repeat_raw = root / "frames" / (stem + "-repeat.rgb565be")
                repeat = training.native(binary, root, *args, "--recruitment-trace", repeated, "--framebuffer", repeat_raw)
                require(repeat == framed and repeat_raw.read_bytes() == raw and digest(trace) == digest(repeated),
                        "repeat trace/state/pixels differ")
                compress(repeated, Path(str(repeated) + ".gz"))
                repeated.unlink()
            audit = prior.analyze_trace(trace, result)
            compress(trace, Path(str(trace) + ".gz"))
            trace.unlink()
            trace_sha = digest(Path(str(trace) + ".gz"))
            if arm == "narrow":
                require(result == saved["result"] and audit == saved["audit"] and trace_sha == saved["trace_sha256"],
                        "narrow historical result/trace/accounting differs")
                prior.check_history(result, panel["evaluations"][model]["worlds"][case["id"]], case, meta)
                require(score == training.score_world(result, case, meta), "ordinary objective changed")
            write_png(root / png_name, 240, 240, rgb565be_to_rgb888(raw))
            write_json(root / (stem + ".json"), result)
            arms[arm] = {"result": result, "history": score, "audit": audit, "metrics": metrics(result, audit, score),
                         "trace_sha256": trace_sha, "frame": {"id": stem, "framebuffer": raw_name, "png": png_name,
                         "framebuffer_crc32": framed["framebuffer_crc32"], "raw_sha256": digest(root / raw_name),
                         "png_sha256": digest(root / png_name)}}
        # Rule bits and the rule-aware GLR1 fingerprint must differ. Everything
        # biological (including full world hash and founder ledger) must match.
        initial_views = [{k: v for k, v in initials[a].items() if k not in ("rules", "run_hash")} for a in ARMS]
        require(initial_views[0] == initial_views[1] and initials["narrow"]["run_hash"] != initials["wide"]["run_hash"],
                "initial biology changed or missing rule-aware identity")
        require(digest(root / "models" / (model + ".tgl")) == models[model]["sha256"], "controller modified")
        print(name + ": paired range worlds, exact controls/repeats and first-day budgets", flush=True)
        return {k: saved[k] for k in ("id", "model", "case")} | {"initial": initials, "arms": arms}

    with ThreadPoolExecutor(max_workers=jobs) as pool:
        worlds = list(pool.map(one, previous["worlds"]))
    sheets = {}
    for climate in ("steady", "seasonal"):
        directory = root / "frames" / climate
        directory.mkdir()
        groups = [[{**w["arms"][arm]["frame"], "framebuffer": str(root / w["arms"][arm]["frame"]["framebuffer"])}
                   for arm in ARMS] for w in worlds if w["case"]["climate"] == climate]
        sheets[climate] = {**contact_sheet(directory, groups), "png": "frames/" + climate + "/contact-sheet.png",
                           "sha256": digest(directory / "contact-sheet.png")}
    return {"schema_version": 1, "rule": RULE, "objective": training.individual.RULE, "inputs": INPUTS,
            "plan": previous["plan"], "models": models, "arms": ARMS, "worlds": worlds,
            "comparison": compare(worlds), "sheets": sheets}


def collect(builds, inputs, output, jobs):
    require(1 <= jobs <= 4 and not output.exists() and
            (output.is_relative_to(ROOT / "artifacts") or not output.is_relative_to(ROOT)), "fresh output/jobs 1..4 required")
    reach.load_inputs(inputs)
    caches = {arm: path / "CMakeCache.txt" for arm, path in builds.items()}
    settings = check_builds(caches)
    require(settings["shared"]["CMAKE_HOME_DIRECTORY"] == str(ROOT / "sim"), "builds from another source tree")
    binaries = {arm: path / "toy-factory-garden-landing" for arm, path in builds.items()}
    identities = {arm: {"binary": digest(binaries[arm]), "cache": digest(caches[arm])} for arm in ARMS}
    sources = source_files()
    output.mkdir(parents=True)
    try:
        (output / "bin").mkdir()
        (output / "inputs").mkdir()
        frozen = {}
        for arm in ARMS:
            frozen[arm] = output / "bin" / ("garden-landing-" + arm)
            shutil.copy2(binaries[arm], frozen[arm])
            shutil.copy2(caches[arm], output / (arm + "-CMakeCache.txt"))
        shutil.copy2(ROOT / PROTOCOL, output / "protocol.md")
        for name in INPUTS:
            shutil.copy2(inputs / name, output / "inputs" / name)
        (output / "sim").mkdir()
        for path in (ROOT / "sim").glob("*.py"):
            shutil.copy2(path, output / "sim" / path.name)
        for name in ("framebuffer_capture.py", "serial_shell.py"):
            target = output / "scripts/container" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / "scripts/container" / name, target)
        snapshot_sources(output, sources)
        result = run_panel(frozen, output / "inputs", output / "panel", jobs)
        require(sources == source_files(), "source changed during collection")
        for arm in ARMS:
            require(digest(binaries[arm]) == digest(frozen[arm]) == identities[arm]["binary"] and
                    digest(caches[arm]) == digest(output / (arm + "-CMakeCache.txt")) == identities[arm]["cache"],
                    "build changed during collection")
        reach.load_inputs(inputs)
        require(digest(output / "protocol.md") == sources[PROTOCOL], "protocol changed")
        write_json(output / "results.json", result)
        write_json(output / "manifest.json", {"rule": RULE, "status": "complete", "repeat_verified": True,
            "builds": identities, "settings": settings, "source_sha256_at_collection": sources,
            "artifacts": {str(p.relative_to(output)): digest(p) for p in sorted(output.rglob("*")) if p.is_file()}})
    except BaseException as error:
        (output / "FAILED.txt").write_text(str(error) + "\n")
        raise


def verify(output):
    require(not (output / "FAILED.txt").exists(), "incomplete range collection")
    manifest = json.loads((output / "manifest.json").read_text())
    require(manifest["rule"] == RULE and manifest["status"] == "complete" and manifest["repeat_verified"], "wrong bundle")
    for name in manifest["artifacts"]:
        artifact(output, manifest, name)
    require(check_builds({a: output / (a + "-CMakeCache.txt") for a in ARMS}) == manifest["settings"], "build mismatch")
    require(digest(output / "protocol.md") == manifest["source_sha256_at_collection"][PROTOCOL], "protocol mismatch")
    expected = json.loads((output / "results.json").read_text())
    with tempfile.TemporaryDirectory(prefix="landing-range-verify-") as temporary:
        result = run_panel({a: output / "bin" / ("garden-landing-" + a) for a in ARMS}, output / "inputs",
                           Path(temporary) / "panel", 1, controls=False)
        require(result == expected, "independent frozen range replay differs")
    for name in manifest["artifacts"]:
        artifact(output, manifest, name)
    print("Verified both arms of all twelve worlds, exact traces, pixels, budgets and unchanged renewal scoring.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--narrow-build", type=Path)
    parser.add_argument("--wide-build", type=Path)
    parser.add_argument("--inputs", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--jobs", type=int)
    parser.add_argument("--verify", type=Path)
    args = parser.parse_args()
    try:
        if args.verify:
            require(all(v is None for v in (args.narrow_build, args.wide_build, args.inputs, args.out, args.jobs)),
                    "verify takes no overrides")
            verify(args.verify.resolve())
        else:
            require(all(v is not None for v in (args.narrow_build, args.wide_build, args.out)), "both builds and --out required")
            collect({a: getattr(args, a + "_build").resolve() for a in ARMS},
                    (args.inputs or ROOT / "benchmarks/garden-seasons").resolve(), args.out.resolve(),
                    2 if args.jobs is None else args.jobs)
        return 0
    except (OSError, ValueError, RuntimeError, StopIteration, KeyError, TypeError) as error:
        print("range screen failed: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
