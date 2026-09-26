#!/usr/bin/env python3
"""Audit actual sequential germination checks against frozen post-step worlds."""
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

import garden_recruitment as recruitment
import garden_experiments as experiment
import garden_establishment as establishment
from garden_resources import require
from garden_gallery import contact_sheet, rgb565be_to_rgb888, write_png

DAY, END, START = 3840, 192 * 3840, 160 * 3840


def rows(path, start):
    with gzip.open(path, "rt") as stream:
        result = {}
        for line in stream:
            row = json.loads(line)
            if row["tick"] >= start:
                require(row["tick"] not in result, "duplicate reference tick")
                result[row["tick"]] = row
        return result


def check_sites(masks, nodes, plants, capacity):
    require(len(masks) == 28 and 0 <= nodes <= capacity and len(plants) <= 8, "bad site capacity")
    for col, mask in enumerate(masks):
        require(type(mask) is int and 0 <= mask < 64 and not mask & 1, "invalid site mask")
        require(bool(mask & 16) == (nodes + 4 > capacity) and bool(mask & 8) == (len(plants) == 8)
                and bool(mask & 32) == any(abs(col - p["column"]) < 3 for p in plants),
                "site mask disagrees with exact allocation/spacing")


def check_step(row, old, world, sites, capacity, *, seed_capacity=8, light_required=True):
    """Check identities, sequential resource changes and outcomes; never run a policy."""
    lifetime = world.get("seed_lifetime_ecology_ticks", 256)
    require(type(lifetime) is int and 8 < lifetime <= 65535 and
            old.get("seed_lifetime_ecology_ticks", 256) == lifetime,
            "invalid/changing seed lifetime")
    stages = row["stages"]
    require(len(stages) == 5 and all(len(s) == 3 and all(type(v) is int for v in s) for s in stages),
            "missing stage inventory")
    before, pre, post, grown, final = stages
    require(before == [old["nodes"], len(old["plants"]), len(old["seeds"])] and
            final == [world["nodes"], len(world["plants"]), len(world["seeds"])], "stage endpoint mismatch")
    retained = [p for p in old["plants"] if p["id"] in {v["id"] for v in world["plants"]}]
    require(all(p["dead"] for p in old["plants"] if p not in retained), "living plant disappeared")
    require(pre == [sum(p["nodes"] for p in retained), len(retained), len(old["seeds"])],
            "decomposition accounting mismatch")
    check_sites(row["sites_before"], pre[0], retained, capacity)
    require(type(light_required) is bool and (light_required or not any(m & 4 for m in row["sites_before"])),
            "unexpected light gate in optional-light rule")
    attempts = row["attempts"]
    require(seed_capacity in (8, 16) and len(attempts) == len(old["seeds"]) <= seed_capacity
            and 0 <= final[2] <= seed_capacity, "missing/repeated seed visit or bank overflow")
    values = Counter(steps=1, visits=len(attempts), reclaimed_nodes=before[0]-pre[0],
                     pre_open=int(0 in row["sites_before"]), post_open=int(any(s[0] == 0 for s in sites["sites"])))
    nodes, plants, expired, born = pre[0], list(retained), 0, []
    masks = list(row["sites_before"])
    water, light = {}, {}
    mature = 0
    hist = [0] * 64
    for a, seed in zip(attempts, old["seeds"], strict=True):
        require(all(a[k] == seed[k] for k in ("parent", "generation", "species", "column")) and
                a["age"] == seed["age"] + 1 and a["nodes"] == nodes and a["plants"] == len(plants),
                "seed visit identity/order mismatch")
        if a["age"] == lifetime:
            require(a["outcome"] == 1 and a["child"] == 0 and a["blockers"] == 0
                and a["moisture"] == a["light"] == 0 and a["sites"] == [0] * 28,
                "expired seed was checked or has impossible output")
            expired += 1
            continue
        require(0 < a["age"] < lifetime and a["outcome"] in (0, 2), "invalid check age/outcome")
        check_sites(a["sites"], nodes, plants, capacity)
        require(a["sites"] == masks, "unexpected change between sequential checks")
        col = a["column"]
        require(0 <= a["moisture"] <= 255 and 0 <= a["light"] <= 255 and
            bool(a["blockers"] & 2) == (a["moisture"] < 12) and
            bool(a["blockers"] & 4) == (light_required and a["light"] < 80), "raw resource threshold mismatch")
        require(a["blockers"] == masks[col] | int(a["age"] < 8), "dormancy/actual-site mismatch")
        require(col not in water or water[col] == a["moisture"], "sequential germination water mismatch")
        require(col not in light or light[col] == a["light"], "light changed within seed checks")
        water[col], light[col] = a["moisture"], a["light"]
        values["checks"] += 1
        values["dormant"] += a["age"] < 8
        if a["age"] >= 8:
            mature += 1
            hist[a["blockers"]] += 1
            for name, bit in establishment.BLOCKERS.items():
                values["blocked_" + name] += bool(a["blockers"] & bit)
                values["only_" + name] += a["blockers"] == bit
            values["mature_any_open"] += 0 in masks
        if a["outcome"] == 0:
            require(a["child"] == 0 and a["blockers"] != 0, "viable seed did not germinate")
            continue
        require(a["blockers"] == 0 and a["age"] >= 8, "blocked seed germinated")
        child = next((p for p in world["plants"] if p["id"] == a["child"]), None)
        require(child is not None and child["id"] not in {p["id"] for p in plants}
            and child["parent"] == a["parent"] and child["column"] == col
            and child["generation"] == a["generation"], "child attribution mismatch")
        plants.append(child)
        nodes += 4
        water[col] -= 12
        born.append(a)
        # Only four-node allocation, spacing and this surface debit can change
        # site eligibility within the seed loop; light is rebuilt after growth.
        for c in range(28):
            masks[c] = (masks[c] & 6) | (16 if nodes + 4 > capacity else 0) | (
                8 if len(plants) == 8 else 0) | (32 if any(abs(c-p["column"]) < 3 for p in plants) else 0)
        masks[col] = (masks[col] & ~2) | (2 if water[col] < 12 else 0)
    require(post == [nodes, len(plants), pre[2]-expired-len(born)], "germination stage mismatch")
    require(post[0] <= grown[0] <= capacity and grown[1:] == post[1:] and final[:2] == grown[:2]
        and final[2] >= grown[2], "growth/reproduction inventory mismatch")
    require(len(born) == world["births"] - old["births"] and expired == world["seeds_expired"] - old["seeds_expired"]
        and final[2] - grown[2] == world["seeds_created"] - old["seeds_created"], "seed outcome counters mismatch")
    require({a["child"] for a in born} == {p["id"] for p in world["plants"]} - {p["id"] for p in old["plants"]},
            "unaccounted newborn")
    values.update(mature_checks=mature, expired=expired, germinations=len(born), growth_nodes=grown[0]-post[0],
        germination_nodes=4*len(born), created=final[2]-grown[2],
        pre_open_no_germination=int(values["pre_open"] and not born),
        pre_open_no_mature_seed=int(values["pre_open"] and not mature),
        pre_open_mature_no_germination=int(values["pre_open"] and mature and not born),
        pre_open_post_closed=int(values["pre_open"] and not values["post_open"]),
        germinations_post_closed=len(born) if not values["post_open"] else 0,
        growth_closes_node_gate=int(post[0] <= capacity-4 < grown[0]),
        growth_closes_node_gate_no_birth=int(post[0] <= capacity-4 < grown[0] and not born))
    return values, hist, born


def analyze(path, world_path, site_path, bounds, header):
    start, end, cap = header["from"], header["end"], header["node_capacity"]
    require(0 <= start < end <= END and start % 15 == end % 15 == 0, "invalid trace window")
    worlds, sites = rows(world_path, start), rows(site_path, start)
    require(set(worlds) == set(sites) == set(range(start, end+1, 15)), "incomplete reference window")
    events = [b["event"] for b in bounds["world"]]
    after = {b["event"]["tick"]: b["after"] for b in bounds["world"]}
    windows = {p: Counter() for p in ("all", *recruitment.PHASES)}
    hist = {p: [0]*64 for p in windows}
    germinations, missed, focal = [], [], Counter()
    previous, event_index, checked = None, 0, 0
    with gzip.open(path, "rt") as stream:
        actual = json.loads(next(stream))
        require(actual == header, "wrong trace/model/environment header")
        for line in stream:
            r = json.loads(line)
            if r["type"] == "disturbance":
                require(event_index < len(events) and r == events[event_index], "wrong patch boundary")
                if r["tick"] >= start:
                    require(previous == r["tick"], "patch before ordinary step")
                event_index += 1
                continue
            t = r["tick"]
            require(r["type"] == "seed-step" and t == (start if previous is None else previous+15)
                and t in worlds, "missing/reordered attempt step")
            w, s = worlds[t], sites[t]
            require(r["hash"] == w["hash"] == s["hash"] and r["sun_phase"] == s["sun_phase"]
                and r["sun_strength"] == s["sun_strength"], "observer changed world/sun")
            require(all(r[k] == w[k] for k in ("nodes", "births")) and r["plants"] == len(w["plants"])
                and r["seeds"] == len(w["seeds"]) and r["expired"] == w["seeds_expired"]
                and r["created"] == w["seeds_created"], "post-step metadata mismatch")
            if t == start:
                require(r["stages"] == r["sites_before"] == r["attempts"] == [], "origin contains a step")
            else:
                old = {**after.get(t-15, worlds[t-15]), "seeds": sites[t-15]["seeds"]}
                seed_capacity = header.get("seed_capacity", 8)
                require(w.get("seed_capacity", 8) == s.get("seed_capacity", 8) == seed_capacity,
                        "attempt/reference seed capacity mismatch")
                v, h, born = check_step(r, old, w, s, cap, seed_capacity=seed_capacity)
                for p in ("all", recruitment.phase(r)):
                    windows[p].update(v)
                    hist[p] = [a+b for a,b in zip(hist[p], h, strict=True)]
                germinations.extend({"tick": t, "phase": recruitment.phase(r), **a} for a in born)
                if v["pre_open_mature_no_germination"] and len(missed) < 8:
                    missed.append({"tick": t, "open_columns": [i for i,m in enumerate(r["sites_before"]) if m == 0],
                                   "attempts": r["attempts"]})
                if (cap == 256 and header["seed"] == "b61837dc" and header["schedule"] == 0xf1fb8012 and
                        header["policy"] == recruitment.policy.RESERVE and 721650 <= t <= 722670):
                    focal.update(v)
            previous = t
            checked += 1
    require(previous == end and event_index == len(events), "truncated steps/patches")
    return {"header": header, "checked": checked, "windows": windows, "mature_blocker_hist": hist,
            "germinations": germinations, "first_missed_samples": missed, "prior_vacancy_window": focal}


def expected_header(c, start=START, end=END, crc="dc5e849d", drainage=None, *, seed_capacity=8):
    return {"type": "seed-audit-header", "schema_version": 1, "rule": "seed-attempt-v1",
        "scenario": c["scenario"], "policy": recruitment.policy.POLICIES[c["policy"]], "seed": c["seed"],
        "model_crc32": crc, "schedule": recruitment.diversity.SCHEDULES[c["arm"]] or 0,
        "from": start, "end": end, "node_capacity": c["capacity"],
        "leaf_environment": recruitment.competition.maintenance.ENVIRONMENT, "leaf_policy": "selective",
        "drainage_rule": drainage, **({"seed_capacity": seed_capacity} if seed_capacity != 8 else {})}


def collect(baseline, builds, output):
    baseline, output = baseline.resolve(), output.resolve()
    require(not output.exists() and (not output.is_relative_to(experiment.ROOT) or
        output.is_relative_to(experiment.ROOT/"artifacts")), "unsafe/existing output")
    m = experiment.read_json(baseline/"manifest.json")
    require(m["kind"] == "garden-crowded-recruitment" and m["status"] == "complete" and
        m["expected_runs"] == 8, "wrong prior diagnostic")
    cases = experiment.read_json(establishment.verified(baseline, m, "cases.json"))
    require(len(cases) == 8 and {(c["capacity"], c["id"], c["arm"], c["policy"]) for c in cases} ==
        {(*p, side) for p in recruitment.PANEL for side in ("neural", "reserve")}, "incomplete fixed panel")
    output.mkdir(parents=True)
    for folder in ("input", "bin", "traces", "analyses", "frames"):
        (output/folder).mkdir()
    sources = experiment.source_files()
    experiment.snapshot_sources(output, sources)
    shutil.copy2(baseline/"manifest.json", output/"input/manifest.json")
    for cap, build in builds.items():
        for tool in ("seed-attempts", "replay"):
            shutil.copy2(build/f"toy-factory-garden-{tool}", output/f"bin/{cap}-{tool}")
        shutil.copy2(build/"CMakeCache.txt", output/f"input/{cap}.build-cache.txt")
        model = establishment.verified(baseline, m, f"input/{cap}.tgm")
        require(experiment.digest(model) == recruitment.competition.maintenance.MODEL_SHA, "wrong model")
        shutil.copy2(model, output/f"input/{cap}.tgm")
    for c in cases:
        key = c["key"]
        for name in (f"traces/{key}.world.gz", f"traces/{key}.sites.gz",
                     f"analyses/{key}.boundaries.json", f"frames/{key}.rgb565"):
            shutil.copy2(establishment.verified(baseline, m, name), output/"input"/Path(name).name)
    frozen = {str(p.relative_to(output)): experiment.digest(p) for p in output.rglob("*") if p.is_file()}
    record = {"kind": "garden-seed-attempts", "status": "started", "from": START, "end": END,
        "expected_runs": 8, "source_sha256": sources, "baseline_manifest_sha256": experiment.digest(baseline/"manifest.json")}
    experiment.write_json(output/"started.json", record)

    def run(c):
        cap, key = c["capacity"], c["key"]
        h = expected_header(c)
        cmd = [f"bin/{cap}-seed-attempts", f"input/{cap}.tgm", h["scenario"], h["policy"],
               "0x"+h["seed"], str(h["schedule"]), str(START), str(END)]
        path = output/f"traces/{key}.gz"
        with tempfile.TemporaryDirectory(prefix="garden-seed-attempts-") as temp:
            raw = Path(temp)/"trace.jsonl"
            experiment.command_run(cmd, raw, output, 300)
            experiment.compress(raw, path)
        a = analyze(path, output/f"input/{key}.world.gz", output/f"input/{key}.sites.gz",
            experiment.read_json(output/f"input/{key}.boundaries.json"), h)
        frame = f"frames/{key}.rgb565"
        replay = [f"bin/{cap}-replay", f"input/{cap}.tgm", h["scenario"], h["policy"], "0x"+h["seed"],
            "--leaf-policy", "selective", "--disturbance-seed", str(h["schedule"]),
            "--ticks", str(END), "--framebuffer", frame]
        experiment.command_run(replay, output/f"frames/{key}.json", output, 300)
        r = experiment.read_json(output/f"frames/{key}.json")
        raw = (output/frame).read_bytes()
        require(raw == (output/f"input/{key}.rgb565").read_bytes() and len(raw) == 115200
            and r["framebuffer_crc32"] == f"{zlib.crc32(raw):08x}" and
            r["hash"] == rows(output/f"input/{key}.world.gz", END)[END]["hash"] and
            r["policy"] == h["policy"] and r["model_crc32"] == h["model_crc32"], "replay/frame mismatch")
        write_png(output/f"frames/{key}.png", 240, 240, rgb565be_to_rgb888(raw))
        experiment.write_json(output/f"analyses/{key}.json", a)
        print(f"{key}: {a['checked']} hashes; {a['windows']['all']['germinations']} germinations", flush=True)
        return {"key": key, "commands": [cmd, replay], "analysis": a,
                "frame": {"id": key, "framebuffer": frame}}
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(run, cases))
        experiment.write_json(output/"summary.json", results)
        experiment.write_json(output/"frames.json", contact_sheet(output,
            [[r["frame"] for r in results[i:i+2]] for i in range(0, 8, 2)]))
        require(experiment.source_files() == sources, "source changed during collection")
        require(all(experiment.digest(output/n) == sha for n,sha in frozen.items()), "frozen input changed")
        record.update(status="complete", artifacts={str(p.relative_to(output)): experiment.digest(p)
            for p in output.rglob("*") if p.is_file()})
        experiment.write_json(output/"manifest.json", record)
        print(f"Complete {output}; SHA256={experiment.digest(output/'manifest.json')}", flush=True)
    except BaseException as error:
        experiment.write_json(output/"failure.json", {"error": str(error)})
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--build-256", type=Path, required=True)
    parser.add_argument("--build-512", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    collect(args.baseline, {256: args.build_256, 512: args.build_512}, args.output)
