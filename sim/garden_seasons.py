#!/usr/bin/env python3
"""Matched, unassisted seasonal trials; daily censuses and natural-death observations."""

from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import zlib

DAY_TICKS = 256 * 15
MODES = ("steady", "winter", "drought", "seasonal")
SPECIES = ("flower", "shrub", "ground-cover")
BLOCKERS = ("dormant", "moisture", "light", "plant_capacity", "node_capacity", "spacing", "cold")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def life_summary(plants: dict, end: int, start: int = 0) -> dict:
    """Birth-window cohorts: death on the full-day boundary fails; late births are censored."""
    def survived(p):
        boundary = p["birth_tick"] + DAY_TICKS
        return boundary <= end and (p["death_tick"] is None or p["death_tick"] > boundary)

    offspring = [p for p in plants.values() if p["parent"] and start <= p["birth_tick"] <= end]
    eligible = [p for p in offspring if p["birth_tick"] + DAY_TICKS <= end]
    successful_parents = {p["parent"] for p in plants.values() if p["parent"] and survived(p)}
    return {"births": len(offspring), "eligible": len(eligible),
            "cycle_survivors": sum(survived(p) for p in eligible),
            "too_young": len(offspring) - len(eligible),
            "durable_parents": sum(survived(p) and p["id"] in successful_parents for p in eligible)}


def analyze_worlds(rows: list[dict], days: int, mode: str) -> dict:
    require(rows and rows[0]["tick"] == 0 and rows[-1]["tick"] == days * DAY_TICKS,
            "Incomplete seasonal trial")
    daily, deaths, plants = [], [], {}
    last_tick = -1
    for row in rows:
        require(row["tick"] > last_tick, "Unordered seasonal samples")
        last_tick = row["tick"]
        require(row["climate"]["mode"] == mode and row["seed_lifetime_ecology_ticks"] == 8192,
                "Unexpected environment contract")
        for plant in row["plants"]:
            ident = plant["id"]
            if ident not in plants:
                parent = plant["parent"]
                require(not parent or parent in plants, "Missing parent history")
                plants[ident] = {"id": ident, "parent": parent, "species": plant["species"],
                                 "family": plants[parent]["family"] if parent else ident,
                                 "generation": plant["generation"], "birth_tick": row["tick"],
                                 "death_tick": None}
            record = plants[ident]
            if plant["dead"] and record["death_tick"] is None:
                record["death_tick"] = row["tick"]
                deaths.append({**record, "tick": row["tick"], "flags": plant["flags"],
                               "climate": row["climate"]})
        for seed in row["seeds"]:
            require(seed["parent"] in plants and seed["species"] == plants[seed["parent"]]["species"]
                    and 0 <= seed["age"] < row["seed_lifetime_ecology_ticks"], "Invalid seed ancestry/age")
        if row["tick"] % DAY_TICKS == 0:
            living = [p for p in row["plants"] if not p["dead"]]
            adults = Counter(p["species"] for p in living)
            bank = Counter(s["species"] for s in row["seeds"])
            families = {plants[p["id"]]["family"] for p in living}
            seed_families = {plants[s["parent"]]["family"] for s in row["seeds"]}
            daily.append({"day": row["tick"] // DAY_TICKS,
                          **{key: row[key] for key in ("hash", "living", "nodes", "births", "deaths",
                             "seeds_created", "seeds_expired", "moisture", "rain_deposited",
                             "rain_runoff", "max_generation", "climate")},
                          "seed_bank": len(row["seeds"]),
                          "oldest_seed": max((s["age"] for s in row["seeds"]), default=0),
                          "species": sorted(adults), "viable_species": sorted(adults.keys() | bank.keys()),
                          "living_by_species": dict(adults), "seeds_by_species": dict(bank),
                          "living_families": sorted(families), "viable_families": sorted(families | seed_families)})
    require(len(daily) == days + 1 and len(deaths) == rows[-1]["deaths"],
            "Missing daily census or natural-death transition")
    lifetimes = life_summary(plants, days * DAY_TICKS)
    require(lifetimes["births"] == rows[-1]["births"], "Missing offspring history")
    final = daily[-1]
    return {"daily": daily, "deaths": deaths, "plants": list(plants.values()),
            "lifetimes": lifetimes,
            "closing_lifetimes": life_summary(plants, days * DAY_TICKS, (days - 16) * DAY_TICKS + 1),
            "closing_births": final["births"] - daily[days - 16]["births"],
            "empty_day": next((r["day"] for r in daily if not r["living"] and not r["seed_bank"]), None)}


def audit_seed_sites(command: list[str], case: dict) -> dict:
    """Uniform post-step samples, not germination-decision receipts or counterfactual rescues."""
    days = case["daily"][-1]["day"]
    closing_tick = (days - 16) * DAY_TICKS
    sample_count, full, mature = 0, 0, 0
    masks, reasons, per_species = Counter(), Counter(), {}
    site_ready = 0
    with tempfile.TemporaryFile(mode="w+t") as stream:
        subprocess.run([*command, "--seed-sites", "--ecology"], stdout=stream,
                       stderr=subprocess.PIPE, text=True, check=True, timeout=300)
        stream.seek(0)
        last = -15
        for line in stream:
            row = json.loads(line)
            require(row["type"] == "seed-sites" and row["tick"] == last + 15, "Missing site sample")
            last = row["tick"]
            if last % DAY_TICKS == 0:
                require(row["hash"] == case["daily"][last // DAY_TICKS]["hash"], "Site replay hash mismatch")
            if last <= closing_tick:
                continue
            sample_count += 1
            full += len(row["seeds"]) == case["environment"]["seed_capacity"]
            site_ready += sum(site[0] == 0 for site in row["sites"])
            for seed in row["seeds"]:
                mask = seed["blockers"]
                if mask & 1:
                    continue
                require(0 <= mask < 128, "Unknown seed blocker")
                mature += 1
                masks[mask] += 1
                group = per_species.setdefault(SPECIES[seed["species"]], Counter())
                group["samples"] += 1
                group["ready"] += mask == 0
                for bit, reason in enumerate(BLOCKERS):
                    if mask & (1 << bit):
                        reasons[reason] += 1
                        group[reason] += 1
        require(last == days * DAY_TICKS and sample_count == 16 * 256, "Incomplete site audit")
    return {"window_days": 16, "ecology_samples": sample_count, "full_bank_samples": full,
            "mature_seed_samples": mature, "ready_site_samples": site_ready,
            "mask_histogram": dict(sorted(masks.items())), "blockers": dict(reasons),
            "by_species": {k: dict(v) for k, v in sorted(per_species.items())}}


def source_hashes(root: Path) -> dict:
    files = [p for folder in ("src", "sim") for p in sorted((root / folder).glob("*"))
             if p.suffix in (".c", ".h")]
    files.append(Path(__file__).resolve())
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}


def screenshots(build: Path, output: Path, results: list[dict], seed: int) -> list[dict]:
    # Fixed first-seed panel, not a search for attractive survivors.
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts/container"))
    from framebuffer_capture import rgb565be_to_rgb888, write_png

    frames = []
    output.mkdir()
    for case in results:
        if case["scenario"] != "rainfed" or case["policy"] != "adaptive" or case["seed"] != f"{seed:08x}":
            continue
        for day in (3, 5, 14, 16):
            name = f"{case['mode']}-day-{day:02}"
            raw = output / (name + ".rgb565be")
            command = [build / "toy-factory-garden-replay", "-", case["scenario"], case["policy"],
                       str(seed), "--ticks", str(day * DAY_TICKS), "--climate", case["mode"],
                       "--framebuffer", raw]
            result = json.loads(subprocess.check_output(list(map(str, command)), text=True))
            data = raw.read_bytes()
            if (result["hash"] != case["daily"][day]["hash"] or len(data) != 240 * 240 * 2 or
                    result["framebuffer_crc32"] != f"{zlib.crc32(data):08x}"):
                raise RuntimeError("Screenshot replay mismatch")
            png = output / (name + ".png")
            write_png(png, 240, 240, rgb565be_to_rgb888(data))
            frames.append({"png": str(png.relative_to(output.parent)), "day": day,
                           "mode": case["mode"], "hash": result["hash"],
                           "framebuffer_crc32": result["framebuffer_crc32"]})
    return frames


def run_case(inspector: Path, days: int, scenario: str, policy: str, seed: int, mode: str,
             seed_audit: bool = False) -> dict:
    command = [str(inspector), "-", scenario, policy, str(seed), "--ticks", str(days * DAY_TICKS),
               "--climate", mode]
    result = subprocess.run(command, capture_output=True, text=True, check=True, timeout=300)
    rows = [row for line in result.stdout.splitlines() if (row := json.loads(line))["type"] == "world"]
    analyzed = analyze_worlds(rows, days, mode)
    case = {"scenario": scenario, "policy": policy, "seed": f"{seed:08x}", "mode": mode,
            "command": command, "trace_sha256": hashlib.sha256(result.stdout.encode()).hexdigest(),
            "environment": {"node_capacity": rows[0].get("node_capacity", 256),
                            "seed_capacity": rows[0].get("seed_capacity", 8),
                            "seed_lifetime_ecology_ticks": rows[0]["seed_lifetime_ecology_ticks"],
                            "leaf_environment": rows[0].get("leaf_environment")},
            **analyzed}
    if seed_audit:
        case["seed_audit"] = audit_seed_sites(command, case)
    return case


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path, default=Path("build-host"))
    parser.add_argument("--out", type=Path, required=True, help="New output directory")
    parser.add_argument("--days", type=int, default=64)
    parser.add_argument("--trials", type=int, default=2)
    parser.add_argument("--jobs", type=int, default=2)
    parser.add_argument("--seed-base", type=lambda x: int(x, 0), default=0x6576616c,
                        help="Predeclare a fresh deterministic weather/initial-world panel")
    parser.add_argument("--seed-audit", action="store_true", help="Audit final-year germination blockers at every ecology step")
    parser.add_argument("--screenshots", action="store_true", help="Capture a fixed, hash-verified first-seed panel")
    args = parser.parse_args()
    if not 32 <= args.days <= 256 or not 1 <= args.trials <= 16 or not 1 <= args.jobs <= 16:
        parser.error("Require 32–256 days, 1–16 trials and 1–16 jobs")
    if not 0 < args.seed_base <= 0xffffffff:
        parser.error("Require nonzero uint32 seed base")
    inspector = (args.build / "toy-factory-garden-inspect").resolve()
    if not inspector.is_file():
        parser.error("Build the host inspector first")
    args.out.mkdir(parents=True, exist_ok=False)
    root = Path(__file__).resolve().parents[1]
    sources = source_hashes(root)
    binary_hash = hashlib.sha256(inspector.read_bytes()).hexdigest()
    replayer = (args.build / "toy-factory-garden-replay").resolve()
    replay_hash = hashlib.sha256(replayer.read_bytes()).hexdigest() if args.screenshots else None
    seeds = [((args.seed_base ^ ((i + 1) * 0x9e3779b9)) & 0xffffffff) or 0x6576616c
             for i in range(args.trials)]
    cases = [(scenario, policy, seed, mode) for scenario in ("rainfed", "rainfed-crowded")
             for policy in ("baseline", "adaptive") for seed in seeds for mode in MODES]
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        results = list(pool.map(lambda case: run_case(inspector, args.days, *case, args.seed_audit), cases))
    offered = {}
    for case in results:
        for row in case["daily"]:
            key = case["mode"], case["seed"], row["day"]
            rain = row["rain_deposited"] + row["rain_runoff"]
            require(offered.setdefault(key, rain) == rain, "Unmatched offered rainfall")
    frames = screenshots(args.build.resolve(), args.out / "frames", results, seeds[0]) if args.screenshots else []
    if source_hashes(root) != sources or hashlib.sha256(inspector.read_bytes()).hexdigest() != binary_hash:
        raise RuntimeError("Sources or inspector changed during the experiment")
    if args.screenshots and hashlib.sha256(replayer.read_bytes()).hexdigest() != replay_hash:
        raise RuntimeError("Replayer changed during the experiment")
    report = {"protocol": "garden-seasons-v2", "days": args.days, "trials": args.trials,
              "seed_base": f"{args.seed_base:08x}", "seeds": [f"{s:08x}" for s in seeds],
              "gardener": False, "irrigation": False, "source_sha256": sources,
              "inspector_sha256": binary_hash, "replayer_sha256": replay_hash,
              "frames": frames, "cases": results}
    (args.out / "results.json").write_text(json.dumps(report, indent=2) + "\n")
    print("mode worlds living-at-end extinct births closing-births deaths")
    for mode in MODES:
        group = [r for r in results if r["mode"] == mode]
        print(mode, len(group), sum(r["daily"][-1]["living"] > 0 for r in group),
              sum(r["empty_day"] is not None for r in group),
              sum(r["daily"][-1]["births"] for r in group), sum(r["closing_births"] for r in group),
              sum(len(r["deaths"]) for r in group))


if __name__ == "__main__":
    main()
