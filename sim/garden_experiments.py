#!/usr/bin/env python3
"""Collect matched Garden experiments and verify automatically selected deep replays."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import gzip
import hashlib
import json
from pathlib import Path
import platform
import shlex
import shutil
import statistics
import struct
import subprocess
import sys
import tarfile
import tempfile
import zlib

from garden_resources import analyze, require


ROOT = Path(__file__).resolve().parents[1]
CYCLE_TICKS = 3840
SCENARIOS = {"rainfed", "rainfed-crowded"}
ENVIRONMENT = {"rain_version": 1, "gardener": False, "irrigation": False,
               "climate": "steady", "seed_lifetime_ecology_ticks": 8192}
WIDE_ENVIRONMENT = {**ENVIRONMENT, "seed_dispersal": "wide-v1"}
WATER_ENVIRONMENT = {**ENVIRONMENT, "water_uptake": "headroom-v1"}
COMBINED_ENVIRONMENT = {**WIDE_ENVIRONMENT, "water_uptake": "headroom-v1"}
LARGE_POOL_ENVIRONMENT = {**COMBINED_ENVIRONMENT, "node_capacity": 512}
SELECTION_ORDER = ["viable", "durable_parents", "cycle_survivors", "descendant_plant_ticks"]
CLIMATES = ("steady", "winter", "drought", "seasonal")
MAX_TICKS = 256 * CYCLE_TICKS


def validate_environment(environment: dict) -> None:
    current = (ENVIRONMENT, WIDE_ENVIRONMENT, WATER_ENVIRONMENT, COMBINED_ENVIRONMENT,
               LARGE_POOL_ENVIRONMENT)
    legacy = tuple({k: v for k, v in e.items() if k not in ("climate", "seed_lifetime_ecology_ticks")}
                   for e in current)
    seasonal = tuple({**e, "climate": mode, "climate_version": 1}
                     for e in current for mode in CLIMATES[1:])
    require(environment in (*current, *legacy, *seasonal),
            "unexpected experiment environment")


def requested_environment(dispersal: str, water_uptake: str, combined: bool, node_capacity: int = 256,
                          climate: str = "steady") -> dict:
    require(climate in CLIMATES, "unknown climate")
    require(dispersal in ("narrow-v1", "wide-v1") and water_uptake in ("legacy-v1", "headroom-v1"),
            "unknown ecology option")
    require(combined == (dispersal == "wide-v1" and water_uptake == "headroom-v1"),
            "combining both rules requires --combined-experiment; opt-in requires both rules")
    require(node_capacity in (256, 512) and (node_capacity == 256 or combined),
            "512 nodes requires the combined experiment")
    environment = (LARGE_POOL_ENVIRONMENT if node_capacity == 512 else
                   COMBINED_ENVIRONMENT if combined else WATER_ENVIRONMENT if water_uptake == "headroom-v1"
                   else WIDE_ENVIRONMENT if dispersal == "wide-v1" else ENVIRONMENT)
    return (dict(environment) if climate == "steady" else
            {**environment, "climate": climate, "climate_version": 1})


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def write_json(path: Path, value: object) -> None:
    with path.open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")


def read_json(path: Path) -> dict:
    with path.open() as stream:
        return json.load(stream)


def trial_seeds(base: int, count: int) -> list[str]:
    result = []
    for index in range(count):
        value = base ^ (((index + 1) * 0x9E3779B9) & 0xFFFFFFFF)
        value ^= (value << 13) & 0xFFFFFFFF
        value ^= value >> 17
        value ^= (value << 5) & 0xFFFFFFFF
        result.append(f"{value or 0x6576616C:08x}")
    return result


def compress(source: Path, target: Path) -> None:
    # Stable gzip headers let repeated traces have identical artifact hashes.
    with source.open("rb") as incoming, target.open("xb") as raw:
        with gzip.GzipFile(fileobj=raw, filename="", mode="wb", mtime=0) as outgoing:
            shutil.copyfileobj(incoming, outgoing)


def command_run(command: list[str], output: Path, cwd: Path, timeout: int) -> None:
    with output.open("xb") as stream:
        result = subprocess.run(command, cwd=cwd, stdout=stream, stderr=subprocess.PIPE,
                                timeout=timeout, check=False)
    require(result.returncode == 0,
            f"command failed ({result.returncode}): {shlex.join(command)}\n"
            f"{result.stderr.decode(errors='replace')[-4000:]}")


def source_files() -> dict[str, str]:
    names = subprocess.check_output(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"], cwd=ROOT,
    ).decode().split("\0")
    result = {}
    for name in sorted(set(names) - {""}):
        path = ROOT / name
        require(not path.is_symlink(), f"source snapshot does not support symlink: {name}")
        if path.is_file():
            result[name] = digest(path)
    return result


def snapshot_sources(output: Path, sources: dict[str, str]) -> None:
    with tarfile.open(output / "source.tar.gz", "w:gz") as archive:
        for name in sources:
            archive.add(ROOT / name, arcname=name, recursive=False)
    with (output / "source.patch").open("xb") as stream:
        subprocess.run(["git", "diff", "--binary", "HEAD"], cwd=ROOT, stdout=stream, check=True)


def report_trials(report: dict) -> dict[tuple[str, str, str], dict]:
    return {(scenario["name"], policy["name"], trial["seed"]): trial
            for scenario in report["scenarios"] for policy in scenario["policies"]
            for trial in policy["trials"]}


NIGHT_PROBE = "no-night-growth-v1"
NIGHT_POLICY = "neural-no-night-growth"
MODEL_POLICIES = {"neural-candidate", NIGHT_POLICY}


def validate_report(report: dict, seeds: list[str], ticks: int, model: dict | None,
                    probe: str | None = None, environment: dict | None = None) -> None:
    require(report.get("schema_version") == 4, "unsupported evaluator schema")
    environment = ENVIRONMENT if environment is None else environment
    validate_environment(environment)
    require(report.get("environment") == environment, "unexpected environment or gardener enabled")
    require(report.get("tick_count") == ticks and report.get("trial_count") == len(seeds),
            "wrong evaluation dimensions")
    require({s["name"] for s in report["scenarios"]} == SCENARIOS and len(report["scenarios"]) == 2,
            "wrong rain-fed scenarios")
    require(probe in (None, NIGHT_PROBE) and (not probe or model), "invalid policy probe")
    require(report.get("candidate_probe") == probe, "wrong evaluated policy probe")
    neural = NIGHT_POLICY if probe else ("neural-candidate" if model else "neural-reference")
    require(report.get("candidate_model_crc32") == (model["crc32"] if model else None),
            "wrong evaluated model")
    offered = {}
    for scenario in report["scenarios"]:
        require(scenario["irrigation_pattern"] == "none" and scenario["irrigation_period_ticks"] == 0,
                "unexpected fixed irrigation")
        require({p["name"] for p in scenario["policies"]} == {"baseline", "adaptive", neural}
                and len(scenario["policies"]) == 3, "wrong policies")
        for policy in scenario["policies"]:
            require([t["seed"] for t in policy["trials"]] == seeds, "unmatched trial seeds")
            for trial in policy["trials"]:
                weather = trial["weather"]
                require(weather["seed"] == trial["seed"], "wrong weather seed")
                amount = weather["deposited"] + weather["runoff"]
                require(offered.setdefault(trial["seed"], amount) == amount,
                        "policies received different offered rain")


def load_timelines(path: Path, report: dict) -> dict[tuple[str, str, str], list[dict]]:
    capacity = report.get("environment", {}).get("node_capacity", 256)
    require(capacity in (256, 512), "unsupported node capacity")
    expected = report_trials(report)
    result: dict[tuple[str, str, str], list[dict]] = {key: [] for key in expected}
    offered = {}
    with gzip.open(path, "rt") as stream:
        for line in stream:
            row = json.loads(line)
            key = row["scenario"], row["policy"], row["seed"]
            require(key in result and row["schema_version"] == 1, "unknown timeline trial/schema")
            values = result[key]
            tick = row["tick"]
            require((not values and tick == 0) or (values and 0 < tick - values[-1]["tick"] <= 60),
                    "timeline is missing samples or not ordered")
            require(tick <= report["tick_count"] and tick % 15 == 0, "invalid timeline cadence")
            require(row["sun_phase"] == (64 + tick // 15) % 256, "invalid sun phase")
            environment = report["environment"]
            if environment.get("climate", "steady") != "steady":
                require(row.get("climate", {}).get("mode") == environment["climate"]
                        and row["climate"]["version"] == environment["climate_version"]
                        and row.get("seed_lifetime_ecology_ticks") == environment["seed_lifetime_ecology_ticks"],
                        "timeline climate contract differs")
                require(not row["climate"]["drought"] or row["rain_rate"] == 0,
                        "rain during scheduled drought")
            require(0 <= row["descendants"] <= row["living"] <= row["plant_slots"] <= 8,
                    "invalid population counts")
            require(0 <= row["nodes"] <= capacity and 0 <= row["moisture"] <= 28 * 11 * 255,
                    "invalid capacity counts")
            if values:
                for name in ("births", "deaths", "living_plant_ticks", "descendant_plant_ticks",
                             "rain_deposited", "rain_runoff"):
                    require(row[name] >= values[-1][name], f"nonmonotonic {name}")
            if tick % 60 == 0:
                amount = row["rain_deposited"] + row["rain_runoff"]
                require(offered.setdefault((key[2], tick), amount) == amount, "timeline rain differs")
            values.append(row)
    for key, rows in result.items():
        require(bool(rows) and rows[-1]["tick"] == report["tick_count"], "truncated timeline")
        require(set(range(0, report["tick_count"] + 1, 60)).issubset({r["tick"] for r in rows}),
                "missing one-second timeline checkpoint")
        trial = expected[key]
        # Optional schema-1 extensions: older frozen bundles remain readable.
        lifetime_rows = [row for row in rows if "lifetimes" in row]
        if lifetime_rows:
            require([row["tick"] for row in lifetime_rows]
                    == list(range(0, report["tick_count"] + 1, CYCLE_TICKS)),
                    "missing lifetime cycle checkpoint")
            previous = {name: 0 for name in lifetime_rows[0]["lifetimes"]}
            for row in lifetime_rows:
                metrics = row["lifetimes"]
                require(set(metrics) == {"eligible_offspring", "cycle_survivors",
                                         "cycle_survivors_with_surviving_child"},
                        "invalid lifetime checkpoint fields")
                require(0 <= metrics["cycle_survivors_with_surviving_child"]
                        <= metrics["cycle_survivors"] <= metrics["eligible_offspring"]
                        <= row["births"], "invalid lifetime checkpoint counts")
                require(all(metrics[name] >= previous[name] for name in previous),
                        "nonmonotonic lifetime counts")
                previous = metrics
            if rows[-1]["tick"] % CYCLE_TICKS == 0:
                require(all(previous[name] == trial["lifetimes"][name] for name in previous),
                        "lifetime checkpoint/report mismatch")
        if "seeds_created" in rows[0]:
            for name in ("seeds_created", "seeds_expired"):
                require(all(a[name] <= b[name] for a, b in zip(rows, rows[1:])),
                        f"nonmonotonic {name}")
                require(rows[-1][name] == trial[name], f"timeline/report {name} mismatch")
        for timeline_field, report_field in (
            ("hash", "hash"), ("living", "living"), ("nodes", "nodes"), ("seed_bank", "seed_bank"),
            ("births", "germinations"), ("deaths", "deaths"), ("energy", "energy"),
            ("water", "water"), ("moisture", "moisture"), ("living_plant_ticks", "living_plant_ticks"),
            ("descendant_plant_ticks", "descendant_plant_ticks"),
        ):
            require(rows[-1][timeline_field] == trial[report_field], f"timeline/report {report_field} mismatch")
    return result


def measures(trial: dict) -> dict:
    lifetimes = trial["lifetimes"]
    return {
        "viable": int(trial["living"] + trial["seed_bank"] > 0),
        "durable_parents": lifetimes["cycle_survivors_with_surviving_child"],
        "cycle_survivors": lifetimes["cycle_survivors"],
        "eligible_offspring": lifetimes["eligible_offspring"],
        "offspring_survival_rate": (lifetimes["cycle_survivors"] / lifetimes["eligible_offspring"]
                                    if lifetimes["eligible_offspring"] else None),
        "descendant_plant_ticks": trial["descendant_plant_ticks"],
        "living_plant_ticks": trial["living_plant_ticks"],
        "extinction_tick": trial["extinction_tick"],
    }


def compare(candidate: dict, control: dict, candidate_policy: str, control_policy: str) -> list[dict]:
    candidate_trials, control_trials = report_trials(candidate), report_trials(control)
    pairs = []
    for (scenario, policy, seed), trial in sorted(candidate_trials.items()):
        if policy != candidate_policy:
            continue
        other = control_trials[(scenario, control_policy, seed)]
        require(trial["weather"]["seed"] == other["weather"]["seed"], "unpaired weather")
        left, right = measures(trial), measures(other)
        delta = {name: left[name] - right[name] for name in SELECTION_ORDER}
        rank = tuple(delta.values())
        pairs.append({"scenario": scenario, "seed": seed, "candidate": left, "control": right,
                      "delta": delta, "result": "win" if rank > (0, 0, 0, 0) else
                      "loss" if rank < (0, 0, 0, 0) else "tie"})
    return pairs


def select_pairs(pairs: list[dict], limit: int) -> list[dict]:
    selected = {}
    ordered = sorted(pairs, key=lambda p: (tuple(p["delta"][k] for k in SELECTION_ORDER),
                                           p["scenario"], p["seed"]))

    def add(pair: dict, reason: str) -> None:
        key = pair["scenario"], pair["seed"]
        if key not in selected and len(selected) < limit:
            selected[key] = {"scenario": key[0], "seed": key[1], "reasons": []}
        if key in selected:
            selected[key]["reasons"].append(reason)

    add(ordered[len(ordered) // 2], "median paired outcome")
    if ordered[-1]["result"] == "win":
        add(ordered[-1], "largest paired improvement")
    if ordered[0]["result"] == "loss":
        add(ordered[0], "largest paired regression")
    extinct = [p for p in pairs if any(p[side]["extinction_tick"] is not None
                                      for side in ("candidate", "control"))]
    if extinct:
        add(min(extinct, key=lambda p: (min(p[s]["extinction_tick"] for s in ("candidate", "control")
                                             if p[s]["extinction_tick"] is not None),
                                       p["scenario"], p["seed"])), "earliest extinction")
    add(max(pairs, key=lambda p: (tuple(p["candidate"][k] for k in SELECTION_ORDER),
                                  p["scenario"], p["seed"])), "best candidate outcome")
    return list(selected.values())


def verify_trace(path: Path, reference: list[dict]) -> int:
    hashes = {row["tick"]: row["hash"] for row in reference}
    conditions = {row["tick"]: row for row in reference}
    matched = set()
    last_tick = -15
    with gzip.open(path, "rt") as stream:
        for line in stream:
            row = json.loads(line)
            if row["type"] != "world":
                continue
            tick = row["tick"]
            require(tick == last_tick + 15, "trace is incomplete or unordered")
            last_tick = tick
            if tick in hashes:
                require(row["hash"] == hashes[tick], f"replay hash mismatch at tick {tick}")
                for key in ("climate", "seed_lifetime_ecology_ticks"):
                    if key in conditions[tick]:
                        require(row.get(key) == conditions[tick][key], f"replay {key} mismatch")
                matched.add(tick)
    require(last_tick == reference[-1]["tick"] and matched == set(hashes),
            "replay did not cover every timeline hash")
    return len(matched)


def diagnostic_signals(diagnostic: dict) -> dict:
    deaths = sorted((p for p in diagnostic["lineages"] if p["death_tick"] is not None),
                    key=lambda p: (p["death_tick"], p["id"]))
    # Trace observations, deliberately not automatically inferred causes.
    first = None
    if deaths:
        plant = deaths[0]
        flags = plant["checkpoints"]["death"]["flags"]
        first = {"lineage": plant["id"], "tick": plant["death_tick"],
                 "age_ticks": plant["death_tick"] - plant["birth_tick"],
                 "shortage_flags": [name for name, mask in (("energy", 2), ("water", 4)) if flags & mask],
                 "last_living": plant["last_living"]}
    night_spenders = [p["id"] for p in diagnostic["lineages"]
                      if p["first_cycle_night"]["energy_growth"] > 0
                      and p["first_cycle_night"]["energy_income"] == 0]
    return {"first_death": first, "first_cycle_night_growth_without_income": night_spenders}


def trace_case(output: Path, case: dict, reference: list[dict], timeout: int) -> dict:
    destination = output / "traces" / f"{case['id']}.jsonl.gz"
    command = ["bin/garden-inspect", case["model"] or "-", case["scenario"], case["policy"],
               "0x" + case["seed"], "--ecology", "--ticks", str(reference[-1]["tick"])]
    if case.get("climate", "steady") != "steady":
        command += ["--climate", case["climate"]]
    with tempfile.TemporaryDirectory(prefix="garden-trace-") as temporary:
        raw = Path(temporary) / "trace.jsonl"
        command_run(command, raw, output, timeout)
        compress(raw, destination)
    checked = verify_trace(destination, reference)
    diagnostic = analyze(destination)
    require(diagnostic["changed_bids"] == 0, "observational replay changed policy decisions")
    diagnostic["trace"] = str(destination.relative_to(output))
    write_json(output / "traces" / f"{case['id']}.resources.json", diagnostic)
    return {**case, "command": command, "checkpoints_verified": checked,
            "trace_sha256": digest(destination),
            "signals": diagnostic_signals(diagnostic),
            "diagnostics": {"checked_live_steps": diagnostic["checked_live_steps"],
                            "terminal_steps_not_reconstructed": diagnostic["terminal_steps_not_reconstructed"]}}


def summary_markdown(pairs: list[dict], cases: list[dict], cycles: int, trials: int, roles: dict) -> str:
    lines = ["# Garden matched experiment", "",
             f"{trials} seeds × 2 rain-fed layouts × {cycles} day/night cycles per policy.", "",
             f"Candidate: **{roles['candidate']['policy']}** "
             f"(model CRC {roles['candidate']['model_crc32'] or 'built-in'}). "
             f"Control: **{roles['control']['policy']}** "
             f"(model CRC {roles['control']['model_crc32'] or 'built-in'}).", "",
             "Gardener off; fixed startup resources, then identical seeded rain. No fitness or ecology changes.",
             "", "## Paired outcomes", "",
             "Wins/losses use a **diagnostic selection order**, not a new training fitness: "
             "population viability, durable parents, full-cycle offspring survivors, descendant plant-time.",
             "A durable parent and its child each survived a full day/night cycle.", "",
             "| Layout | Wins / ties / losses | Candidate extinctions | Control extinctions |",
             "|---|---:|---:|---:|"]
    for scenario in sorted(SCENARIOS):
        rows = [p for p in pairs if p["scenario"] == scenario]
        counts = [sum(p["result"] == result for p in rows) for result in ("win", "tie", "loss")]
        ext = [sum(p[s]["viable"] == 0 for p in rows) for s in ("candidate", "control")]
        lines.append(f"| {scenario} | {' / '.join(map(str, counts))} | {ext[0]}/{len(rows)} | {ext[1]}/{len(rows)} |")
    lines += ["", "| Paired delta (candidate − control) | Min | Median | Max |",
              "|---|---:|---:|---:|"]
    for name in SELECTION_ORDER:
        values = [p["delta"][name] for p in pairs]
        lines.append(f"| {name} | {min(values)} | {statistics.median(values):g} | {max(values)} |")
    lines += ["", "See [comparisons.json](comparisons.json) for every paired seed and cohort denominator; "
              "an empty offspring cohort has rate `null`, not zero. These are descriptive results, "
              "not significance tests. The two layouts share seeds and are not independent replicates.",
              "", "## Selected diagnostic replays", "",
              "| Case | Policy | Layout / seed | Selection reasons | Verified checkpoints |",
              "|---|---|---|---|---:|"]
    for case in cases:
        lines.append(f"| [{case['id']}](traces/{case['id']}.resources.json) | {case['side']}: {case['policy']} | "
                     f"{case['scenario']} / `{case['seed']}` | {', '.join(case['reasons'])} | "
                     f"{case['checkpoints_verified']} |")
    lines += ["", "Each selected pair includes both policies. Detailed traces record every ecology step "
              "and bid; resource summaries identify first shortages, sunsets/dawns, last living state, "
              "and first-cycle income/spending. Death clears resource telemetry: those terminal steps "
              "are explicitly **not reconstructed**. These observations suggest hypotheses, not causes.",
              "", "### Observations from selected traces", ""]
    for case in cases:
        signals = case["signals"]
        death = signals["first_death"]
        detail = (f"first death: lineage {death['lineage']} at tick {death['tick']} "
                  f"(age {death['age_ticks'] / 60:g}s), shortage flags "
                  f"{', '.join(death['shortage_flags']) or 'none'}" if death else "no deaths")
        count = len(signals["first_cycle_night_growth_without_income"])
        lines.append(f"- Case {case['id']}: {detail}; {count} lineages spent energy on nighttime "
                     "growth with zero nighttime income during their first-cycle observation window.")
    lines += ["", "These selected cases are not an unbiased sample of the batch.",
              "", "Replay a case from this bundle directory (inside the build container):", "",
              "```sh", "python3 tools/garden_experiments.py --replay . --case 01", "```", "",
              "[Cycle checkpoints](cycles.json) summarize every run. Compressed timelines retain "
              "one-second samples plus births, deaths, and rain transitions. Raw final reports, models, "
              "executables, source archive, patch, and hashes are retained in the bundle.", ""]
    return "\n".join(lines)


def replay(output: Path, case_id: str, timeout: int) -> None:
    manifest = read_json(output / "manifest.json")
    require(manifest["status"] == "complete", "bundle is not complete")
    require(digest(output / "cases.json") == manifest["artifacts"]["cases.json"], "case selection changed")
    cases = read_json(output / "cases.json")["cases"]
    case = next((v for v in cases if v["id"] == case_id), None)
    require(case is not None, "unknown case ID")
    for name in ("bin/garden-inspect", f"reports/{case['job']}.json",
                 f"timelines/{case['job']}.jsonl.gz", case["model"],
                 "tools/garden_resources.py", "tools/garden_experiments.py", "cases.json"):
        if name:
            require(digest(output / name) == manifest["artifacts"][name], f"artifact changed: {name}")
    report = read_json(output / "reports" / f"{case['job']}.json")
    timelines = load_timelines(output / "timelines" / f"{case['job']}.jsonl.gz", report)
    reference = timelines[(case["scenario"], case["policy"], case["seed"])]
    with tempfile.TemporaryDirectory(prefix="garden-replay-") as temporary:
        raw, packed = Path(temporary) / "trace.jsonl", Path(temporary) / "trace.jsonl.gz"
        command_run(case["command"], raw, output, timeout)
        compress(raw, packed)
        checked = verify_trace(packed, reference)
        require(digest(packed) == case["trace_sha256"], "replay trace bytes changed")
    print(f"PASS case {case_id}: {checked} checkpoints, final hash {reference[-1]['hash']}, identical trace")


def collect(args: argparse.Namespace) -> None:
    output = args.output.resolve()
    require(output != ROOT and (not output.is_relative_to(ROOT) or output.is_relative_to(ROOT / "artifacts")),
            "put bundles outside the source tree or under artifacts/")
    require(not output.exists(), "output already exists; choose a new experiment directory")
    require(not args.candidate_probe or args.candidate_model is not None,
            "candidate probe requires an external candidate model")
    environment = requested_environment(args.dispersal, args.water_uptake, args.combined_experiment,
                                        args.node_capacity, args.climate)
    seeds = trial_seeds(args.seed, args.trials)
    models = {}
    for side in ("candidate", "control"):
        path = getattr(args, f"{side}_model")
        if path is not None:
            data = path.read_bytes()
            require(len(data) == 1220 and struct.unpack_from("<IHHI", data) == (0x314D4754, 1, 16, 1204),
                    f"invalid {side} model envelope")
            crc = struct.unpack_from("<I", data, 12)[0]
            require(zlib.crc32(data[16:]) == crc, f"corrupt {side} model")
            models[side] = {"path": f"models/{side}.tgm", "sha256": digest(path), "crc32": f"{crc:08x}"}
    training_seeds = set()
    training_crcs = set()
    for path in args.training_report:
        report = read_json(path)
        training_crcs.add(report["final"]["model_crc32"])
        training_seeds.update(trial_seeds(int(report["base_seed"], 16),
                                         report["settings"]["trials_per_scenario"]))
    require(not training_seeds.intersection(seeds), "training/evaluation seed overlap")
    if args.split != "exploratory":
        require(all(model["crc32"] in training_crcs for model in models.values()),
                "validation/test requires training reports for all external models")
    sources = source_files()
    output.mkdir(parents=True, exist_ok=False)
    manifest = {"schema_version": 1, "status": "running", "split": args.split,
                "seed": f"{args.seed:08x}", "seeds": seeds, "cycles": args.cycles,
                "trial_count": args.trials,
                "environment": environment,
                "models": models,
                "declared_training_seeds": sorted(training_seeds), "source_sha256": sources,
                "git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                "git_status": subprocess.check_output(["git", "status", "--short"], cwd=ROOT, text=True),
                "python": sys.version, "platform": platform.platform(), "jobs": args.jobs,
                "selection_order": SELECTION_ORDER, "trace_pair_limit": args.trace_pairs}
    if args.candidate_probe:
        manifest["candidate_probe"] = args.candidate_probe
    write_json(output / "started.json", manifest)
    try:
        for directory in ("bin", "models", "reports", "timelines", "traces", "tools", "training"):
            (output / directory).mkdir()
        snapshot_sources(output, sources)
        for name, path in (("garden-eval", args.evaluator), ("garden-inspect", args.inspector)):
            shutil.copy2(path, output / "bin" / name)
        for name in ("garden_experiments.py", "garden_resources.py"):
            shutil.copy2(Path(__file__).with_name(name), output / "tools" / name)
        for side, model in models.items():
            shutil.copy2(getattr(args, f"{side}_model"), output / model["path"])
            require(digest(output / model["path"]) == model["sha256"], "model changed while freezing")
        for index, path in enumerate(args.training_report):
            shutil.copy2(path, output / "training" / f"{index:02d}.json")
        cache = args.evaluator.parent / "CMakeCache.txt"
        if cache.is_file():
            shutil.copy2(cache, output / "build-cache.txt")
        jobs = ["candidate"] + (["control"] if "control" in models else [])

        def evaluate(job: str) -> tuple[dict, dict]:
            command = ["bin/garden-eval", "--rainfed", "--trials", str(args.trials),
                       "--ticks", str(args.cycles * CYCLE_TICKS), "--seed", hex(args.seed)]
            if args.climate != "steady":
                command += ["--climate", args.climate]
            model = models.get(job)
            if model:
                command.extend(("--model", model["path"]))
            probe = args.candidate_probe if job == "candidate" else None
            if probe:
                command.append("--no-night-growth")
            with tempfile.TemporaryDirectory(prefix="garden-timeline-") as temporary:
                timeline = Path(temporary) / "timeline.jsonl"
                command_run(command + ["--timeline", str(timeline)], output / "reports" / f"{job}.json",
                            output, args.timeout)
                compress(timeline, output / "timelines" / f"{job}.jsonl.gz")
            report = read_json(output / "reports" / f"{job}.json")
            validate_report(report, seeds, args.cycles * CYCLE_TICKS, model, probe, manifest["environment"])
            timelines = load_timelines(output / "timelines" / f"{job}.jsonl.gz", report)
            print(f"{job}: {len(timelines)} trials and timelines validated", flush=True)
            return report, timelines

        with ThreadPoolExecutor(max_workers=args.jobs) as pool:
            data = dict(zip(jobs, pool.map(evaluate, jobs), strict=True))
        control_job = "control" if "control" in models else "candidate"
        candidate_policy = "neural-candidate" if "candidate" in models else "neural-reference"
        if args.candidate_probe:
            candidate_policy = NIGHT_POLICY
        control_policy = "neural-candidate" if "control" in models else "adaptive"
        roles = {"candidate": {"policy": candidate_policy, "job": "candidate",
                               "model_crc32": models.get("candidate", {}).get("crc32")},
                 "control": {"policy": control_policy, "job": control_job,
                             "model_crc32": models.get("control", {}).get("crc32")}}
        manifest["roles"] = roles
        if "control" in data:
            a, b = report_trials(data["candidate"][0]), report_trials(data["control"][0])
            require(all(a[key] == b[key] for key in a if key[1] in ("baseline", "adaptive")),
                    "common baseline policies changed between candidate/control batches")
        pairs = compare(data["candidate"][0], data[control_job][0], candidate_policy, control_policy)
        write_json(output / "comparisons.json", {"selection_order": SELECTION_ORDER, "roles": roles,
                                                 "pairs": pairs})
        cycles = [{"job": job, **row} for job, (_, timelines) in data.items()
                  for rows in timelines.values() for row in rows if row["tick"] % CYCLE_TICKS == 0]
        write_json(output / "cycles.json", {"checkpoints": cycles})
        cases = []
        for pair in select_pairs(pairs, args.trace_pairs):
            for side, job, policy in (("candidate", "candidate", candidate_policy),
                                      ("control", control_job, control_policy)):
                case = {**pair, "id": f"{len(cases) + 1:02d}", "side": side, "job": job,
                        "climate": args.climate,
                        "policy": policy, "model": (models[job]["path"]
                                                     if policy in MODEL_POLICIES else None)}
                reference = data[job][1][(pair["scenario"], policy, pair["seed"])]
                cases.append(trace_case(output, case, reference, args.timeout))
                print(f"case {case['id']}: {side} {pair['scenario']}/{pair['seed']} replay verified", flush=True)
        write_json(output / "cases.json", {"cases": cases})
        with (output / "summary.md").open("x") as stream:
            stream.write(summary_markdown(pairs, cases, args.cycles, args.trials, roles))
        require(source_files() == sources, "source changed during experiment; do not use mixed provenance")
        manifest["status"] = "complete"
        manifest["artifacts"] = {str(p.relative_to(output)): digest(p)
                                 for p in sorted(output.rglob("*")) if p.is_file()}
        write_json(output / "manifest.json", manifest)
        print(f"Complete: {output / 'summary.md'}")
    except Exception as error:
        write_json(output / "failure.json", {"status": "failed", "error": str(error)})
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--output", type=Path)
    mode.add_argument("--replay", type=Path)
    parser.add_argument("--case", default="01")
    parser.add_argument("--candidate-model", type=Path)
    parser.add_argument("--node-capacity", type=int, choices=(256, 512), default=256,
                        help="Expected host build capacity; 512 requires the combined experiment")
    parser.add_argument("--dispersal", choices=("narrow-v1", "wide-v1"), default="narrow-v1",
                        help="Expected compiled ecology rule; does not switch the executable's behavior")
    parser.add_argument("--water-uptake", choices=("legacy-v1", "headroom-v1"), default="legacy-v1",
                        help="Expected compiled uptake rule")
    parser.add_argument("--combined-experiment", action="store_true",
                        help="Explicitly validate the wide-dispersal plus capped-uptake condition")
    parser.add_argument("--control-model", type=Path)
    parser.add_argument("--climate", choices=CLIMATES, default="steady")
    parser.add_argument("--candidate-probe", choices=(NIGHT_PROBE,),
                        help="Host-only intervention on the candidate; weights/environment unchanged")
    parser.add_argument("--training-report", type=Path, action="append", default=[])
    parser.add_argument("--split", choices=("exploratory", "validation", "test"), default="exploratory")
    parser.add_argument("--trials", type=int, choices=range(1, 65), default=8, metavar="1-64")
    parser.add_argument("--cycles", type=int, choices=range(1, 257), default=8, metavar="1-256")
    parser.add_argument("--trace-pairs", type=int, choices=range(1, 7), default=5, metavar="1-6")
    parser.add_argument("--seed", type=lambda x: int(x, 0), default=0x6D617463)
    parser.add_argument("--jobs", type=int, choices=range(1, 5), default=2)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--evaluator", type=Path, default=ROOT / "build-host/toy-factory-garden-eval")
    parser.add_argument("--inspector", type=Path, default=ROOT / "build-host/toy-factory-garden-inspect")
    args = parser.parse_args()
    if not 0 < args.seed <= 0xFFFFFFFF or args.timeout <= 0:
        parser.error("seed must be a nonzero uint32 and timeout must be positive")
    try:
        if args.replay:
            replay(args.replay.resolve(), args.case, args.timeout)
        else:
            collect(args)
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.SubprocessError) as error:
        print(f"Garden experiment failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
