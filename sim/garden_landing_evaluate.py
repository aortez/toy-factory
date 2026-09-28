#!/usr/bin/env python3
"""Matched, fixed-checkpoint TGL2 replays; diagnostics, never a training score."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import itertools
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import zlib

from garden_experiments import digest, source_files, snapshot_sources, write_json
from garden_gallery import artifact, contact_sheet, rgb565be_to_rgb888, write_png
from garden_resources import require

ROOT = Path(__file__).resolve().parents[1]
DAY = 3840
CLIMATES = ("steady", "winter", "drought", "seasonal")
SCENARIOS = ("rainfed", "rainfed-crowded")
TOOLS = ("sim/garden_landing_evaluate.py", "sim/garden_gallery.py", "sim/garden_experiments.py",
         "sim/garden_resources.py", "scripts/container/framebuffer_capture.py",
         "scripts/container/serial_shell.py")


def native(root: Path, command: list[str], timeout: int) -> dict:
    result = subprocess.run(command, cwd=root, capture_output=True, text=True, timeout=timeout)
    require(result.returncode == 0, f"landing command failed: {result.stderr.strip()}")
    return json.loads(result.stdout)


def command(case: dict, tick: int) -> list[str]:
    require(re.fullmatch(r"[a-z][a-z0-9-]{0,31}", case["label"]) is not None, "invalid label")
    require(case["scenario"] in SCENARIOS and case["climate"] in CLIMATES, "invalid scenario/climate")
    require(re.fullmatch(r"[0-9a-f]{8}", case["seed"]) is not None
            and int(case["seed"], 16) > 0, "invalid seed")
    require(type(tick) is int and 0 <= tick <= 256 * DAY, "invalid tick")
    return ["bin/garden-landing", "replay", f"models/{case['label']}.tgl", case["scenario"],
            "0x" + case["seed"], "--ticks", str(tick), "--climate", case["climate"]]


def check_result(result: dict, case: dict, tick: int, model: dict, rules: int, raw: bytes) -> None:
    require(result["schema_version"] == 1 and result["kind"] == "landing-replay"
            and result["run_version"] == 1 and result["rules"] == rules, "wrong replay/build rules")
    require(result["model"] == model and result["scenario"] == case["scenario"]
            and result["seed"] == case["seed"] and result["tick"] == tick
            and result["climate"]["mode"] == case["climate"], "mismatched replay settings")
    require(result["gardener"] is False and result["irrigation"] is False, "assisted replay")
    require(result["warmup_samples"] == min(tick // 15, 256), "wrong history clock")
    require(len(raw) == 240 * 240 * 2 and result["framebuffer_crc32"] == f"{zlib.crc32(raw):08x}",
            "framebuffer length/CRC mismatch")
    m = result["lifetimes"]
    require(m["offspring_born"] == result["births"]
            and m["offspring_deaths"] + m["founder_deaths"] == result["deaths"]
            and m["offspring_living_at_end"] == result["descendants"]
            and m["offspring_living_at_end"] + m["founders_living_at_end"] == result["living"]
            and m["eligible_offspring"] == m["cycle_survivors"] + m["died_before_cycle"]
            and m["offspring_born"] == m["eligible_offspring"] + m["too_young_alive"] + m["too_young_dead"],
            "unreconciled lifetime census")
    require(len(result["species_lifetimes"]) == 3 and all(
        sum(s[k] for s in result["species_lifetimes"]) == v for k, v in m.items()),
        "unreconciled species totals")


def check_repeat(root: Path, case: dict, tick: int, expected: dict, raw: bytes, timeout: int) -> None:
    with tempfile.TemporaryDirectory(prefix="landing-repeat-") as temporary:
        path = Path(temporary) / "frame.rgb565be"
        repeated = native(root, command(case, tick) + ["--framebuffer", str(path)], timeout)
        require(repeated == expected and path.read_bytes() == raw, "nonrepeatable state/pixels")


def capture_case(root: Path, case: dict, days: list[int], model: dict, rules: int, timeout: int) -> dict:
    frames = []
    for day in days:
        name = "-".join((case["label"], case["scenario"], case["climate"], case["seed"], f"day-{day}"))
        raw_path, png_path = f"frames/{name}.rgb565be", f"frames/{name}.png"
        result = native(root, command(case, day * DAY) + ["--framebuffer", raw_path], timeout)
        raw = (root / raw_path).read_bytes()
        check_result(result, case, day * DAY, model, rules, raw)
        check_repeat(root, case, day * DAY, result, raw, timeout)
        write_png(root / png_path, 240, 240, rgb565be_to_rgb888(raw))
        frames.append({"id": name, "day": day, "framebuffer": raw_path, "png": png_path, "result": result})
    return {**case, "frames": frames}


def report(cases: list[dict], sheets: list[dict], days: list[int]) -> str:
    lines = ["# Landing-model development comparison", "",
             "Fixed requested worlds; no selection of best-looking runs, no new fitness score.",
             "Rain-fed, gardener off. All saved states and raw frames repeat exactly.",
             "Imported zero-extra-weight models are controls, not trained landing-aware policies.", "",
             "| Model | Climate / layout / seed | End living / seeds | Births | Day survivors / eligible | Durable parents |",
             "|---|---|---:|---:|---:|---:|"]
    for case in cases:
        r = case["frames"][-1]["result"]
        m = r["lifetimes"]
        lines.append(f"| {case['label']} ({r['model']['mode']}) | {case['climate']} / {case['scenario']} / "
                     f"`{case['seed']}` | {r['living']} / {r['seed_bank']} | {r['births']} | "
                     f"{m['cycle_survivors']} / {m['eligible_offspring']} | "
                     f"{m['cycle_survivors_with_surviving_child']} |")
    lines += ["", "Day = 3,840 logic ticks = 256 ecology steps. Recent births are censored separately.",
              "Durable parents and their children each survived a day; this is cumulative history, not proof of ongoing renewal.",
              "An empty eligible cohort is not a zero-percent success rate. See results.json for per-species outcomes.",
              "", "## Fixed first-seed gallery", "",
              "Columns: Garden days " + ", ".join(map(str, days)) + ". All other requested frames are also retained."]
    for sheet in sheets:
        lines += ["", f"### {sheet['climate']}", "", f"![Fixed replay panel]({sheet['png']})", "",
                  "Rows: " + "; ".join(sheet["labels"]) + "."]
    lines += ["", "[Results](results.json) · [Provenance and hashes](manifest.json)", "",
              "Verify this trusted local bundle inside a compatible builder container:", "", "```sh",
              "python3 sim/garden_landing_evaluate.py --verify .", "```", ""]
    return "\n".join(lines)


def validate_settings(settings: dict) -> None:
    for key, maximum in (("labels", 4), ("seeds", 8), ("climates", 4), ("scenarios", 2)):
        require(1 <= len(settings[key]) <= maximum and len(set(settings[key])) == len(settings[key]),
                f"choose 1-{maximum} distinct {key}")
    days = settings["checkpoints"]
    require(type(settings["days"]) is int and 1 <= settings["days"] <= 256, "days must be 1..256")
    require(1 <= len(days) <= 6 and days == sorted(set(days)) and days[-1] == settings["days"]
            and all(type(d) is int and 0 <= d <= settings["days"] for d in days), "invalid checkpoints")
    for label, scenario, climate, seed in itertools.product(
            settings["labels"], settings["scenarios"], settings["climates"], settings["seeds"]):
        command(dict(label=label, scenario=scenario, climate=climate, seed=seed), 0)


def case_plan(settings: dict) -> list[dict]:
    return [dict(label=label, scenario=scenario, climate=climate, seed=seed)
            for label, scenario, climate, seed in itertools.product(
                settings["labels"], settings["scenarios"], settings["climates"], settings["seeds"])]


def collect(args: argparse.Namespace) -> Path:
    require(args.out is not None and args.model, "collection requires --out and at least one --model LABEL=PATH")
    require(1 <= args.jobs <= 8 and 1 <= args.timeout <= 3600, "invalid jobs/timeout")
    models = {}
    for entry in args.model:
        label, separator, name = entry.partition("=")
        require(separator and name and label not in models, "use distinct --model LABEL=PATH entries")
        models[label] = Path(name).resolve()
    settings = {"labels": list(models), "seeds": [f"{s:08x}" for s in (args.seed or [0xa9c30c1f])],
                "climates": args.climate or ["seasonal"], "scenarios": args.scenario or list(SCENARIOS),
                "days": args.days, "checkpoints": sorted(set(
                    (args.checkpoint_day or [min(1, args.days), min(16, args.days)]) + [args.days]))}
    validate_settings(settings)
    build, output = args.build.resolve(), args.out.resolve()
    require(not output.exists(), "output exists; choose a fresh directory")
    require(not output.is_relative_to(ROOT) or output.is_relative_to(ROOT / "artifacts"),
            "put output outside the source tree or under artifacts/")
    executable = build / "toy-factory-garden-landing"
    cache = build / "CMakeCache.txt"
    flags = dict(line.split("=", 1) for line in cache.read_text().splitlines()
                 if line.startswith("TOY_FACTORY_GARDEN_") and ":BOOL=" in line)
    allowed = {"TOY_FACTORY_GARDEN_WIDE_DISPERSAL:BOOL": 1, "TOY_FACTORY_GARDEN_FLOWER_DISPERSAL:BOOL": 2}
    require(flags and all(v == "OFF" or (k in allowed and v == "ON") for k, v in flags.items()),
            "unsupported ecology build")
    rules = sum(bit for key, bit in allowed.items() if flags.get(key) == "ON")
    inputs = {"executable": digest(executable), "cache": digest(cache),
              "models": {label: digest(path) for label, path in models.items()}}
    inspected = {label: native(ROOT, [str(executable), "inspect", str(path)], args.timeout)["model"]
                 for label, path in models.items()}
    sources = source_files()
    output.mkdir(parents=True)
    try:
        for directory in ("bin", "models", "frames"):
            (output / directory).mkdir()
        shutil.copy2(executable, output / "bin/garden-landing")
        shutil.copy2(cache, output / "CMakeCache.txt")
        for label, path in models.items():
            shutil.copy2(path, output / f"models/{label}.tgl")
            require(digest(output / f"models/{label}.tgl") == inputs["models"][label], "model changed during copy")
            require(native(output, ["bin/garden-landing", "inspect", f"models/{label}.tgl"], args.timeout)["model"]
                    == inspected[label], "model changed during inspection")
        require(digest(output / "bin/garden-landing") == inputs["executable"]
                and digest(output / "CMakeCache.txt") == inputs["cache"], "build changed during copy")
        for name in TOOLS:
            target = output / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / name, target)
        snapshot_sources(output, sources)
        with ThreadPoolExecutor(max_workers=args.jobs) as pool:
            cases = list(pool.map(lambda case: capture_case(output, case, settings["checkpoints"],
                                  inspected[case["label"]], rules, args.timeout), case_plan(settings)))
        sheets = []
        for climate in settings["climates"]:
            chosen = [c for c in cases if c["climate"] == climate and c["seed"] == settings["seeds"][0]]
            directory = output / "gallery" / climate
            directory.mkdir(parents=True)
            sheet = contact_sheet(directory, [[{**f, "framebuffer": "../../" + f["framebuffer"]}
                                                for f in c["frames"]] for c in chosen])
            sheets.append({**sheet, "climate": climate, "png": f"gallery/{climate}/contact-sheet.png",
                           "labels": [f"{c['label']} / {c['scenario']} / {c['seed']}" for c in chosen]})
        write_json(output / "results.json", {"schema_version": 1, "cases": cases, "sheets": sheets})
        with (output / "report.md").open("x") as stream:
            stream.write(report(cases, sheets, settings["checkpoints"]))
        require(sources == source_files(), "source tree changed during collection; discard this incomplete run")
        require(digest(executable) == inputs["executable"] and digest(cache) == inputs["cache"]
                and all(digest(p) == inputs["models"][k] for k, p in models.items()), "inputs changed during collection")
        artifacts = {str(p.relative_to(output)): digest(p) for p in sorted(output.rglob("*")) if p.is_file()}
        write_json(output / "manifest.json", {"schema_version": 1, "kind": "landing-evaluation", "status": "complete",
                   "split": "development", "settings": settings, "rules": rules, "build_flags": flags,
                   "models": inspected, "inputs_sha256": inputs, "source_sha256_at_collection": sources,
                   "artifacts": artifacts, "repeat_verified": True})
    except BaseException as error:
        with (output / "FAILED.txt").open("x") as stream:
            stream.write(str(error) + "\n")
        raise
    return output


def verify(root: Path, timeout: int) -> None:
    root = root.resolve()
    require(not (root / "FAILED.txt").exists(), "incomplete bundle")
    manifest = json.loads((root / "manifest.json").read_text())
    require(manifest["schema_version"] == 1 and manifest["kind"] == "landing-evaluation"
            and manifest["status"] == "complete" and manifest["split"] == "development", "unsupported bundle")
    validate_settings(manifest["settings"])
    for name in manifest["artifacts"]:
        artifact(root, manifest, name)
    artifact(root, manifest, "bin/garden-landing")
    for label in manifest["settings"]["labels"]:
        artifact(root, manifest, f"models/{label}.tgl")
        require(native(root, ["bin/garden-landing", "inspect", f"models/{label}.tgl"], timeout)["model"]
                == manifest["models"][label], "model metadata mismatch")
    results = json.loads(artifact(root, manifest, "results.json").read_text())
    require(results["schema_version"] == 1, "unsupported results")
    require([{k: c[k] for k in ("label", "scenario", "climate", "seed")} for c in results["cases"]]
            == case_plan(manifest["settings"]), "missing/extra/reordered cases")
    for case in results["cases"]:
        require([f["day"] for f in case["frames"]] == manifest["settings"]["checkpoints"], "wrong checkpoints")
        for frame in case["frames"]:
            raw = artifact(root, manifest, frame["framebuffer"]).read_bytes()
            artifact(root, manifest, frame["png"])
            check_result(frame["result"], case, frame["day"] * DAY,
                         manifest["models"][case["label"]], manifest["rules"], raw)
            check_repeat(root, case, frame["day"] * DAY, frame["result"], raw, timeout)
    for name in manifest["artifacts"]:
        artifact(root, manifest, name)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--model", action="append", help="LABEL=path.tgl, repeat to compare (max 4)")
    parser.add_argument("--seed", action="append", type=lambda s: int(s, 0), help="repeat, max 8 nonzero u32 seeds")
    parser.add_argument("--scenario", action="append", choices=SCENARIOS)
    parser.add_argument("--climate", action="append", choices=CLIMATES)
    parser.add_argument("--days", type=int)
    parser.add_argument("--checkpoint-day", action="append", type=int)
    parser.add_argument("--jobs", type=int)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--verify", type=Path, help="replay an existing trusted local bundle")
    args = parser.parse_args()
    try:
        if args.verify:
            require(not args.out and not args.model and not args.seed and not args.climate
                    and not args.scenario and not args.checkpoint_day and args.build is None
                    and args.days is None and args.jobs is None, "verify cannot override recorded settings")
            require(1 <= args.timeout <= 3600, "invalid timeout")
            verify(args.verify, args.timeout)
            print("Verified saved landing-model states and pixels.")
        else:
            args.build = ROOT / "build-host" if args.build is None else args.build
            args.days = 32 if args.days is None else args.days
            args.jobs = 2 if args.jobs is None else args.jobs
            print(collect(args) / "report.md")
    except (OSError, RuntimeError, ValueError, KeyError, TypeError, IndexError, subprocess.SubprocessError) as error:
        print(f"landing evaluation failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
