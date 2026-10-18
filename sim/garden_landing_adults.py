#!/usr/bin/env python3
"""Read-only adult budgets and simultaneous seed blockers in one frozen pair."""

from __future__ import annotations

import argparse
from collections import Counter
import gzip
import json
from pathlib import Path
import shutil
import sys

import garden_landing_turnover as previous
import garden_landing_arbitration as arbitration
import garden_landing_water as water
from garden_experiments import compress, digest, source_files, snapshot_sources, write_json
from garden_gallery import contact_sheet, rgb565be_to_rgb888, write_png
from garden_resources import require

ROOT, DAY, STEP = previous.ROOT, previous.DAY, previous.STEP
RULE = "garden-landing-adult-resources-v1"
PROTOCOL = "benchmarks/garden-seasons/landing-adult-resources-protocol.md"
CASE = "single-s6d697834-live--rainfed-crowded-seasonal-940cfdc4"
START, END, STOP = 96 * DAY, 130 * DAY, previous.STOP
FRAMES = tuple(int(d * DAY) for d in (120, 124, 126.5, 127, 128, 129, 130))
FIELDS = previous.recruitment.RESOURCE_FIELDS
BLOCKERS = previous.recruitment.BLOCKERS
training = arbitration.training


def read_trace(path):
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt") as stream:
        return [json.loads(line) for line in stream]


def vector(value, size, maximum=65535):
    return (type(value) is list and len(value) == size and
            all(type(v) is int and 0 <= v <= maximum for v in value))


def budget():
    return {r: dict.fromkeys(FIELDS, 0) for r in ("energy", "water")}


def transfers(row, life, before=None):
    """Validate a complete sample and return actual transfers, including terminal discard."""
    require(set(row) == {"tick", "id", "birth", "stages", "uptake", "roots", "active_leaves"},
            "wrong plant fields")
    stages, raw, tick = row["stages"], row["uptake"], row["tick"]
    born, dead = tick == life["birth_tick"], tick == life["death_tick"]
    require(type(stages) is list and len(stages) == 5 and
            all(s is None or vector(s, 5) and s[0] <= 256 and s[1] <= 512 and
                s[2] <= 8 and s[3] <= 7 and s[4] <= 256 for s in stages), "invalid stages")
    require(all(s is not None for s in stages[2:]) and bool(stages[-1][3] & 1) == dead,
            "missing stage or death mismatch")
    require(type(row["roots"]) is int and type(row["active_leaves"]) is int and
            0 <= row["roots"] <= stages[-1][4] and 0 <= row["active_leaves"] <= stages[-1][4],
            "invalid morphology")
    if born:
        require(stages[:2] == [None, None] and raw is None and stages[2][:2] == [64, 24] and
                before is None and life["parent"] != 0, "wrong birth endowment")
    else:
        require(all(s is not None for s in stages) and stages[1] == stages[2] and
                type(raw) is list and len(raw) == 2 and all(vector(r, 6) for r in raw),
                "missing uptake/maintenance stages")
    result = budget()
    for j, name in enumerate(result):
        b = result[name]
        if born:
            b["initial"] = stages[2][j]
        else:
            initial, income, overflow, due, paid, discarded = raw[j]
            require(before is None or initial == before[j], "inter-step resource discontinuity")
            require(stages[0][j] == initial + income - overflow, "uptake does not balance")
            upkeep = stages[0][j] - stages[1][j]
            if dead:
                require(stages[1][j] == 0 and paid <= due and paid + discarded == stages[0][j],
                        "death receipt does not balance")
                upkeep = paid
            else:
                require(due == paid == discarded == 0, "death-only fields on living plant")
            require(upkeep >= 0 and (tick % (4 * STEP) == 0 or upkeep == 0), "invalid upkeep")
            b.update(initial=initial, income=income, overflow=overflow, upkeep=upkeep, discarded=discarded)
        b.update(growth=stages[2][j] - stages[3][j], reproduction=stages[3][j] - stages[4][j],
                 final=stages[4][j])
        require(all(v >= 0 for v in b.values()) and b["initial"] + b["income"] ==
                sum(b[k] for k in FIELDS if k not in ("initial", "income")), "step budget mismatch")
    if not born:
        flags, stress = stages[1][3], stages[1][2]
        expected = min(8, stages[0][2] + 1) if flags & 6 else max(0, stages[0][2] - 1)
        require((stress == expected if tick % (4 * STEP) == 0 else stages[0] == stages[1]),
                "stress does not match maintenance")
        require(not dead or stress == 8 and bool(flags & 6), "invalid terminal stress")
    return result


def accumulate(total, sample, first):
    for r in total:
        if first:
            total[r]["initial"] = sample[r]["initial"]
        else:
            require(total[r]["final"] == sample[r]["initial"], "aggregate budget discontinuity")
        for k in FIELDS:
            if k not in ("initial", "final"):
                total[r][k] += sample[r][k]
        total[r]["final"] = sample[r]["final"]
        require(total[r]["initial"] + total[r]["income"] ==
                sum(total[r][k] for k in FIELDS if k not in ("initial", "income")), "total imbalance")


def analyze(records, result):
    require(type(records) is list and len(records) >= 3, "incomplete trace")
    header = records[0]
    require(set(header) == {"schema", "start", "stop"} and header["schema"] == "landing-adult-resources-v1",
            "wrong trace schema")
    start, end = header["start"], header["stop"]
    require(type(start) is int and type(end) is int and STEP <= start <= end <= result["tick"] and
            start % STEP == end % STEP == 0, "invalid window")
    require(records[-1] == {"complete": True, "tick": result["tick"]} and
            len(records) == (end - start) // STEP + 3, "incomplete/trailing trace")
    lives = {p["id"]: p for p in result["lineages"]}
    seeds = {(s["parent"], s["birth_tick"]): s for s in result["seeds"]}
    require(len(lives) == len(result["lineages"]) and len(seeds) == len(result["seeds"]), "duplicate ledger identity")
    for p in lives.values():
        if "removal_tick" in p:
            require(type(p["removal_tick"]) is int and p["birth_tick"] + DAY < p["removal_tick"] <= result["tick"] and
                    p["removal_tick"] % STEP == 0 and p["death_tick"] is None, "invalid adult export")
    plants, daily, checks, previous_rows = {}, {}, {}, {}
    for tick, row in zip(range(start, end + 1, STEP), records[1:-1], strict=True):
        require(set(row) == {"tick", "sun", "season", "cold", "soil_water", "bank", "seeds", "plants"} and
                type(row["tick"]) is int and row["tick"] == tick and vector(row["sun"], 2, 255) and
                row["sun"][0] == (64 + tick // STEP) % 256 and type(row["season"]) is int and
                0 <= row["season"] < 4 and type(row["cold"]) is bool and type(row["soil_water"]) is int and
                0 <= row["soil_water"] <= 28 * 11 * 255 and type(row["bank"]) is int and
                0 <= row["bank"] <= 8, "invalid ecology sample")
        d = daily.setdefault(str(tick // DAY), {"samples": 0, "mature_seed_checks": 0, "masks": Counter(),
            "germinations": [], "expiries": 0, "minimum_bank": 8, "maximum_bank": 0})
        d["samples"] += 1
        d["minimum_bank"] = min(d["minimum_bank"], row["bank"])
        d["maximum_bank"] = max(d["maximum_bank"], row["bank"])
        require(row["bank"] == sum(s["birth_tick"] <= tick < (s["end_tick"] or result["tick"] + STEP)
                                   for s in seeds.values()), "seed bank differs from ledger")
        seen = set()
        for values in row["seeds"]:
            require(type(values) is list and len(values) == 11 and all(type(v) is int for v in values),
                    "invalid seed record")
            parent, age, column, mask, moisture, light, slots, nodes, outcome, child, opened = values
            key = parent, tick - age * STEP
            require(key in seeds and key not in seen and age > 0, "unknown/duplicate seed")
            seen.add(key)
            s = seeds[key]
            expected = 0 if s["end_tick"] != tick else {"expired": 1, "germinated": 2}[s["outcome"]]
            require(column == s["column"] and outcome == expected and
                    child == (s["child_id"] if outcome == 2 else 0) and 0 <= slots <= 8 and 0 <= nodes <= 256,
                    "seed identity/outcome mismatch")
            summary = checks.setdefault(key, {**s, "samples": 0, "mature_masks": Counter(), "open_elsewhere_checks": 0})
            summary["samples"] += 1
            if outcome == 1:
                require(age == s["lifetime_ecology_ticks"] and mask == moisture == light == 0 and opened == -1,
                        "invalid expiry")
                d["expiries"] += 1
                continue
            require(0 <= mask < 128 and 0 <= moisture <= 255 and 0 <= light <= 255 and 0 <= opened <= 28 and
                    bool(mask & 1) == (age < 8) and bool(mask & 2) == (moisture < 12) and
                    bool(mask & 4) == (light < 80) and bool(mask & 8) == (slots >= 8) and
                    bool(mask & 16) == (nodes + 4 > 256) and bool(mask & 64) == row["cold"] and
                    (mask == 0) == (outcome == 2), "invalid seed mask")
            if not mask & 1:
                summary["mature_masks"][str(mask)] += 1
                summary["open_elsewhere_checks"] += bool(opened and mask)
                d["masks"][str(mask)] += 1
                d["mature_seed_checks"] += 1
            if outcome == 2:
                d["germinations"].append(child)
        require(seen == {k for k, s in seeds.items() if s["birth_tick"] < tick <= (s["end_tick"] or result["tick"])},
                "incomplete seed inventory")
        seen = set()
        for p in row["plants"]:
            pid = p["id"]
            require(type(pid) is int and pid in lives and pid not in seen and p["birth"] == lives[pid]["birth_tick"],
                    "unknown/duplicate plant")
            seen.add(pid)
            life = lives[pid]
            old = previous_rows.get(pid)
            receipt = transfers({"tick": tick, **p}, life, old["stages"][-1] if old else None)
            a = plants.setdefault(pid, {**life, "first_tick": tick, "last_tick": tick, "samples": 0,
                "left_censored": life["birth_tick"] < start, "right_censored": life["death_tick"] is None or life["death_tick"] > end,
                "resources": budget(), "days": {}, "first_shortage_tick": None, "max_stress": 0, "death_shortage": None})
            accumulate(a["resources"], receipt, a["samples"] == 0)
            day = a["days"].setdefault(str(tick // DAY), {"samples": 0, "resources": budget(), "shortages": Counter(),
                "max_stress": 0, "last_nodes": 0, "last_roots": 0, "last_active_leaves": 0})
            accumulate(day["resources"], receipt, day["samples"] == 0)
            day["samples"] += 1
            a["samples"] += 1
            a["last_tick"] = tick
            day.update(last_nodes=p["stages"][-1][4], last_roots=p["roots"], last_active_leaves=p["active_leaves"])
            stress = p["stages"][1][2] if p["uptake"] else 0
            day["max_stress"] = max(day["max_stress"], stress)
            a["max_stress"] = max(a["max_stress"], stress)
            if p["uptake"] and tick % (4 * STEP) == 0:
                shortage = {2: "energy", 4: "water", 6: "energy+water"}.get(p["stages"][1][3] & 6)
                if shortage:
                    day["shortages"][shortage] += 1
                    a["first_shortage_tick"] = a["first_shortage_tick"] or tick
                    if life["death_tick"] == tick:
                        a["death_shortage"] = shortage
            previous_rows[pid] = p
        # Observers publish before the post-step export, so its boundary sample
        # is present. Removed plants are absent on subsequent ecology steps.
        require(seen == {i for i, p in lives.items() if p["birth_tick"] <= tick <=
                        min(p["death_tick"] or result["tick"], p.get("removal_tick", result["tick"]))},
                "incomplete plant inventory")
    for value in daily.values():
        value["blockers"] = {b: sum(n for m, n in value["masks"].items() if int(m) & (1 << i))
                             for i, b in enumerate(BLOCKERS)}
    return {"start": start, "stop": end, "ecology_samples": len(records) - 2,
            "plant_samples": sum(p["samples"] for p in plants.values()),
            "seed_samples": sum(s["samples"] for s in checks.values()),
            "plants": list(plants.values()), "seeds": list(checks.values()), "days": daily}


def collect(build, inputs, out):
    require(not out.exists() and (out.is_relative_to(ROOT / "artifacts") or not out.is_relative_to(ROOT)),
            "fresh external/artifact output required")
    models, archive = arbitration.load_inputs(inputs)
    saved = next(w for w in previous.load(inputs / Path(previous.INPUT).name)["worlds"] if w["id"] == CASE)
    meta = archive["models"][saved["model"]]
    cache, binary = build / "CMakeCache.txt", build / "toy-factory-garden-landing"
    settings = water.check_build(cache)
    sources = source_files()
    out.mkdir(parents=True)
    try:
        (out / "bin").mkdir()
        (out / "frames").mkdir()
        frozen = out / "bin/garden-landing"
        shutil.copy2(binary, frozen)
        shutil.copy2(cache, out / "CMakeCache.txt")
        shutil.copy2(ROOT / PROTOCOL, out / "protocol.md")
        snapshot_sources(out, sources)
        model = out / "model.tgl"
        with model.open("xb") as stream:
            stream.write(models[meta["model"]])
        require(digest(model) == meta["sha256"], "wrong frozen model")
        result = {"rule": RULE, "case": saved["case"], "model": meta, "input_sha256": previous.INPUT_SHA,
                  "protocol_sha256": digest(out / "protocol.md"), "training_runs": 0, "arms": {},
                  "build": {"binary_sha256": digest(frozen), "cache_sha256": digest(cache), "settings": settings},
                  "source_sha256_at_collection": sources}
        groups = []
        for arm in previous.ARMS:
            base = ("arbitration-replay", "model.tgl", saved["case"]["scenario"], "0x" + saved["case"]["seed"],
                    "--climate", saved["case"]["climate"], "--water-arbitration", arm, "--ledger")
            path = out / (arm + ".jsonl")
            raw = out / "frames" / (arm + "-192.rgb565be")
            extra = ("--adult-start", START, "--adult-stop", END)
            traced = training.native(frozen, out, *base, "--ticks", STOP, "--adult-trace", path,
                                     *extra, "--framebuffer", raw)
            require({**traced, "framebuffer_crc32": None} == saved["arms"][arm]["result"] and
                    digest(raw) == saved["arms"][arm]["frame"]["raw_sha256"], "historical trajectory/pixels changed")
            records = read_trace(path)
            audit = analyze(records, traced)
            for label, traced_again in (("plain", False), ("repeat", True)):
                dest = out / "frames" / (arm + "-" + label + ".rgb565be")
                trace = out / (arm + "-repeat.jsonl")
                actual = training.native(frozen, out, *base, "--ticks", STOP, "--framebuffer", dest,
                                         *(("--adult-trace", trace, *extra) if traced_again else ()))
                require(actual == traced and dest.read_bytes() == raw.read_bytes(), "tracing changes state/pixels")
                if traced_again:
                    require(trace.read_bytes() == path.read_bytes(), "repeated trace differs")
            frames = []
            for tick in FRAMES:
                stem = f"{arm}-{tick}"
                raw_name, png_name = "frames/" + stem + ".rgb565be", "frames/" + stem + ".png"
                image = training.native(frozen, out, *base, "--ticks", tick, "--framebuffer", raw_name)
                repeat_raw = out / "frames" / (stem + "-traced.rgb565be")
                repeat_trace = out / (stem + "-trace.jsonl")
                repeated = training.native(frozen, out, *base, "--ticks", tick, "--framebuffer", repeat_raw,
                    "--adult-trace", repeat_trace, "--adult-start", START, "--adult-stop", tick)
                require(image == repeated and (out / raw_name).read_bytes() == repeat_raw.read_bytes(), "window pixels differ")
                write_png(out / png_name, 240, 240, rgb565be_to_rgb888((out / raw_name).read_bytes()))
                frames.append({"id": stem, "tick": tick, "framebuffer": raw_name, "png": png_name,
                               "sha256": digest(out / png_name), "result": image})
            groups.append(frames)
            result["arms"][arm] = {"result": traced, "trace": records, "audit": audit, "frames": frames,
                                   "trace_sha256": digest(path), "repeat_and_capture_verified": True}
            compress(path, out / (arm + ".jsonl.gz"))
            print(arm + ": reconciled adult/seed samples; exact historical state and repeated pixels", flush=True)
        result["sheet"] = contact_sheet(out, groups)
        require(source_files() == sources and digest(model) == meta["sha256"] and digest(binary) == digest(frozen),
                "source/model/binary changed during collection")
        require(digest(cache) == result["build"]["cache_sha256"] and water.check_build(cache) == settings,
                "build settings changed")
        write_json(out / "results.json", result)
        compress(out / "results.json", out / "results.json.gz")
        write_json(out / "manifest.json", {"rule": RULE, "status": "complete", "settings": settings,
            "source_sha256": sources, "artifacts": {str(p.relative_to(out)): digest(p)
                                                    for p in sorted(out.rglob("*")) if p.is_file()}})
    except BaseException as error:
        (out / "FAILED.txt").write_text(str(error) + "\n")
        raise


def verify(path):
    value = json.loads(gzip.decompress(path.read_bytes()) if path.suffix == ".gz" else path.read_bytes())
    require(value["rule"] == RULE and value["input_sha256"] == previous.INPUT_SHA and value["training_runs"] == 0 and
            value["protocol_sha256"] == digest(ROOT / PROTOCOL) and set(value["arms"]) == set(previous.ARMS), "wrong diagnosis")
    saved = next(w for w in previous.load(ROOT / previous.INPUT)["worlds"] if w["id"] == CASE)
    require(value["case"] == saved["case"] and value["model"]["id"] == saved["model"] and
            value["model"]["metadata"] == saved["arms"]["eligible"]["result"]["model"], "wrong case/controller")
    for arm, data in value["arms"].items():
        require(data["repeat_and_capture_verified"] is True and
                {**data["result"], "framebuffer_crc32": None} == saved["arms"][arm]["result"] and
                data["result"]["framebuffer_crc32"] == saved["arms"][arm]["frame"]["framebuffer_crc32"],
                "historical replay mismatch")
        require(data["audit"] == analyze(data["trace"], data["result"]) and
                (data["audit"]["start"], data["audit"]["stop"]) == (START, END), "adult analysis mismatch")
        require([f["tick"] for f in data["frames"]] == list(FRAMES) and
                all(f["result"]["tick"] == f["tick"] and
                    arbitration.common_view(f["result"], arm)["model"] == value["model"]["metadata"]
                    for f in data["frames"]), "wrong frame panel")
    require(value["sheet"]["rows"] == [[f["id"] for f in value["arms"][a]["frames"]] for a in previous.ARMS],
            "wrong contact sheet ordering")
    print("Verified complete window inventories and resource accounts against frozen historical pair (offline).")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path, default=ROOT / "build-host")
    parser.add_argument("--inputs", type=Path, default=ROOT / "benchmarks/garden-seasons")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--out", type=Path)
    group.add_argument("--verify", type=Path)
    args = parser.parse_args()
    try:
        if args.verify:
            verify(args.verify)
        else:
            collect(args.build.resolve(), args.inputs.resolve(), args.out.resolve())
        return 0
    except (OSError, ValueError, RuntimeError, KeyError, TypeError, StopIteration) as error:
        print("adult-resource diagnosis failed: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
