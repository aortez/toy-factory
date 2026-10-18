#!/usr/bin/env python3
"""One frozen spacing-aware seed-placement screen; no training or promotion."""

from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import gzip
import json
from pathlib import Path
import shutil
import sys

import garden_landing_budget as budget
import garden_landing_germination as germination
import garden_landing_reach as reach
from garden_experiments import compress, digest, snapshot_sources, source_files, write_json
from garden_gallery import artifact, contact_sheet
from garden_resources import require

growth, training = budget.growth, budget.training
ROOT, DAY, STEP, STOP = reach.ROOT, reach.DAY, reach.STEP, reach.STOP
RULE = "garden-landing-placement-v1"
PROTOCOL = "benchmarks/garden-seasons/landing-placement-protocol.md"
INPUTS = {germination.INPUT: germination.INPUT_SHA,
          "benchmarks/garden-seasons/landing-budget-reach-results.json.gz":
          "93cba7dfac249a4cca2326e6e163b89856f7d0e1268f3ac0a6eb0e3d7ca637aa"}
ARMS = ("eligible", "reserve", "spacing")


def probe_hash(base, enabled):
    require(type(base) is str and len(base) == 8 and all(c in "0123456789abcdef" for c in base) and
            type(enabled) is bool, "invalid placement identity")
    h = 2166136261
    for byte in b"GLP1" + int(base, 16).to_bytes(4, "little") + bytes((1, enabled)):
        h = ((h ^ byte) * 16777619) & 0xffffffff
    return f"{h:08x}"


def common_view(result, arm):
    require(arm in ARMS, "unknown placement arm")
    c = result["placement_probe"]
    base_arm = "eligible" if arm == "eligible" else "reserve"
    base_hash = budget.probe_hash(result["base_run_hash"], budget.MODES[base_arm])
    require(result["kind"] == "landing-placement-replay" and
            c == {"version": 1, "enabled": arm == "spacing"} and
            type(c["version"]) is int and type(c["enabled"]) is bool and
            result["run_hash"] == probe_hash(base_hash, arm == "spacing"), "wrong placement identity")
    normalized = {k: v for k, v in result.items() if k != "placement_probe"} | {
        "kind": "landing-budget-replay", "run_hash": base_hash}
    return budget.common_view(normalized, base_arm)


def choose(p, enabled):
    """Independent integer reference, including reflected duplicate choices."""
    require(type(enabled) is bool and type(p["random"]) is int and 0 <= p["random"] <= 0xffffffff and
            type(p["blocked"]) is int and 0 <= p["blocked"] < 64 and
            p["choices"] == reach.support(p["origin"], p["dispersal"]), "invalid placement observation")
    for i, column in enumerate(p["choices"]):
        require(all(((p["blocked"] >> i) & 1) == ((p["blocked"] >> j) & 1)
                    for j, other in enumerate(p["choices"]) if other == column), "inconsistent reflection aliases")
    original = p["random"] % 6
    clear = [i for i in range(6) if not p["blocked"] & (1 << i)]
    return clear[(p["random"] // 6) % len(clear)] if enabled and clear and original not in clear else original


def read_trace(path, stop, enabled):
    require(type(stop) is int and stop >= 0 and type(enabled) is bool, "invalid trace clock/config")
    purchases = []
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt") as stream:
        require(json.loads(next(stream)) == {"schema": "landing-placement-trace-v1", "enabled": enabled},
                "wrong placement header")
        for tick in range(STEP, stop + 1, STEP):
            row = json.loads(next(stream))
            require(set(row) == {"tick", "purchases"} and type(row["tick"]) is int and row["tick"] == tick and
                    type(row["purchases"]) is list, "missing/reordered placement step")
            for p in row["purchases"]:
                require(set(p) == {"parent", "random", "origin", "dispersal", "blocked", "selected", "choices"},
                        "wrong placement receipt")
                purchases.append({"tick": tick, **p})
        require(json.loads(next(stream)) == {"complete": True, "tick": stop} and not stream.read(),
                "incomplete/trailing placement trace")
    return {"ecology_samples": stop // STEP, "purchases": purchases}


def purchase_sites(full_reach):
    return [{"tick": s["birth_tick"], **s["purchase"]} for s in full_reach["seeds"]]


def analyze(result, receipts, sites, enabled):
    """Cross-check each paid purchase against independent reach and seed ledgers."""
    require(set(receipts) == {"ecology_samples", "purchases"} and
            receipts["ecology_samples"] == result["tick"] // STEP, "incomplete placement coverage")
    ledger = {(s["parent"], s["birth_tick"]): s for s in result["seeds"]}
    require(len(ledger) == len(result["seeds"]), "duplicate ledger purchase")
    parents = {p["id"]: p for p in result["lineages"]}
    native_sites = {(s["parent"], s["tick"]): s for s in sites}
    require(len(native_sites) == len(sites) and set(native_sites) == set(ledger), "reach purchase inventory differs")
    seen, traits, rows = set(), {}, []
    last_tick = 0
    for p in receipts["purchases"]:
        require(set(p) == {"tick", "parent", "random", "origin", "dispersal", "blocked", "selected", "choices"} and
                type(p["tick"]) is int and last_tick <= p["tick"] <= result["tick"] and
                p["tick"] > 0 and p["tick"] % STEP == 0 and type(p["parent"]) is int,
                "invalid placement receipt/clock")
        last_tick = p["tick"]
        key = p["parent"], p["tick"]
        require(key in ledger and key not in seen, "unknown/duplicate paid placement")
        seen.add(key)
        seed, parent, site = ledger[key], parents[p["parent"]], native_sites[key]
        require(set(site) == {"tick", "parent", "column", "origin", "dispersal", "choices", "sites"} and
                p["origin"] == parent["column"] and parent["birth_tick"] <= p["tick"] and
                (parent["death_tick"] is None or p["tick"] < parent["death_tick"]) and
                traits.setdefault(p["parent"], p["dispersal"]) == p["dispersal"], "wrong producing parent")
        require(type(p["selected"]) is int and p["selected"] == choose(p, enabled), "placement mapping differs")
        mask = reach.sites_decode(site["sites"])
        require(all(p[k] == site[k] for k in ("parent", "origin", "dispersal", "choices")) and
                site["column"] == seed["column"] == p["choices"][p["selected"]] and
                p["blocked"] == sum(1 << i for i, column in enumerate(p["choices"]) if mask[column] & 32),
                "placement and native spacing/ledger disagree")
        original = p["random"] % 6
        rows.append({**seed, "original": p["choices"][original], "selected": seed["column"],
                     "redirected": original != p["selected"], "original_blocked": bool(p["blocked"] & (1 << original)),
                     "all_blocked": p["blocked"] == 63, "selected_site_mask": mask[seed["column"]]})
    require(seen == set(ledger), "missing paid placement")

    def summary(selected):
        return {"seeds": len(selected), "redirected": sum(s["redirected"] for s in selected),
                "original_blocked": sum(s["original_blocked"] for s in selected),
                "all_blocked": sum(s["all_blocked"] for s in selected),
                "selected_spacing_clear": sum(not s["selected_site_mask"] & 32 for s in selected),
                "selected_all_gates_open": sum(s["selected_site_mask"] == 0 for s in selected),
                "outcomes": dict(sorted(Counter(s["outcome"] for s in selected).items())),
                "redirected_outcomes": dict(sorted(Counter(s["outcome"] for s in selected if s["redirected"]).items()))}

    return {"seeds": rows, "summary": {"all": summary(rows),
            "late_purchases": summary([s for s in rows if 62 * DAY < s["birth_tick"] <= 190 * DAY])}}


def compare(worlds):
    require(len(worlds) == 12 and len({w["id"] for w in worlds}) == 12 and
            all(set(w["arms"]) == set(ARMS) for w in worlds), "unmatched placement panel")
    comparisons = {}
    for baseline in ARMS[:2]:
        mapped = [{**w, "arms": {"control": w["arms"][baseline], "water": w["arms"]["spacing"]}} for w in worlds]
        groups = {}
        for name in ("all", "steady", "seasonal", "single", "multi"):
            rows = [w for w in mapped if name == "all" or w["case"]["climate"] == name or w["model"].split("-")[0] == name]
            histories = [{w["id"]: w["arms"][a]["history"] for w in rows} for a in ("control", "water")]
            groups[name] = {"scores": training.individual.pair_group(*histories, [w["id"] for w in rows]),
                "totals": {a: growth.scoring.totals([w["arms"][a]["metrics"] for w in rows]) for a in ("control", "water")}}
        gates = growth.water.gates(groups, mapped)
        comparisons[baseline] = {"groups": groups, "gates": gates, "passes_screen": all(gates.values())}
    return {"comparisons": comparisons, "passes_screen": all(c["passes_screen"] for c in comparisons.values())}


def check_value(value, saved):
    require(value["rule"] == RULE and value["inputs"] == INPUTS and value["training_runs"] == 0 and
            value["full_replays"] == 108 and value["initial_snapshots"] == 36 and value["models"] == saved["models"] and
            value["protocol_sha256"] == digest(ROOT / PROTOCOL), "wrong placement screen")
    for w, old in zip(value["worlds"], saved["worlds"], strict=True):
        require({k: w[k] for k in ("id", "model", "case")} == {k: old[k] for k in ("id", "model", "case")} and
                set(w["arms"]) == set(w["initial"]) == set(ARMS), "wrong panel")
        for arm in ARMS:
            a = w["arms"][arm]
            require(common_view(w["initial"][arm], arm) == budget.common_view(old["initial"]["eligible"], "eligible"),
                    "initial biology differs")
            require(a["result"]["tick"] == a["frame"]["tick"] == STOP and a["repeat_and_plain_verified"] is True and
                    a["history"] == training.score_world(common_view(a["result"], arm), w["case"],
                                                         saved["models"][w["model"]]["metadata"]) and
                    a["metrics"] == growth.scoring.metrics(a["result"], a["audit"], a["history"]), "history/metrics differ")
            require(a["placement_audit"] == analyze(a["result"], a["placements"], a["purchase_sites"], arm == "spacing") and
                    a["species_audit"] == budget.species.analyze_arm(a, arm, w["case"],
                        saved["models"][w["model"]]["metadata"], normalize=common_view), "placement/species audit differs")
            require(all(s is None or s[4] <= 32 for p in a["audit"]["plants"] for r in p["rows"] for s in r["stages"]),
                    "descendant cap exceeded")
            if arm != "spacing":
                previous = old["arms"][arm]
                require(common_view(a["result"], arm) == budget.common_view(previous["result"], arm) and
                        all(a[k] == previous[k] for k in ("history", "audit", "metrics", "trace_sha256")) and
                        a["frame"]["raw_sha256"] == previous["frame"]["raw_sha256"] and
                        a["frame"]["framebuffer_crc32"] == previous["frame"]["framebuffer_crc32"], "historical control differs")
        require(len({r["run_hash"] for r in w["initial"].values()}) == 3, "identity collision")
    require(value["comparison"] == compare(value["worlds"]), "comparison/gates differ")
    for climate in ("steady", "seasonal"):
        require(value["sheets"][climate]["rows"] == [[w["arms"][a]["frame"]["id"] for a in ARMS]
                for w in value["worlds"] if w["case"]["climate"] == climate], "gallery order differs")


def load_input():
    for name, sha in INPUTS.items():
        require(digest(ROOT / name) == sha, "wrong frozen input")
    return germination.load(ROOT / germination.INPUT, germination.INPUT_SHA)


def collect(build, out, jobs):
    require(1 <= jobs <= 4 and not out.exists() and
            (out.is_relative_to(ROOT / "artifacts") or not out.is_relative_to(ROOT)), "fresh output/jobs 1..4 required")
    saved = load_input()
    models = growth.load_inputs(ROOT / "benchmarks/garden-seasons")[0]
    source, cache = build / "toy-factory-garden-landing", build / "CMakeCache.txt"
    settings = growth.water.check_build(cache)
    require(settings["CMAKE_HOME_DIRECTORY"] == str(ROOT / "sim"), "wrong source tree")
    sources, identities = source_files(), {"binary": digest(source), "cache": digest(cache)}
    out.mkdir(parents=True)
    try:
        for name in ("bin", "models", "inputs", "frames"):
            (out / name).mkdir()
        binary = out / "bin/garden-landing"
        shutil.copy2(source, binary)
        shutil.copy2(cache, out / "CMakeCache.txt")
        shutil.copy2(ROOT / PROTOCOL, out / "protocol.md")
        snapshot_sources(out, sources)
        for name, sha in INPUTS.items():
            shutil.copy2(ROOT / name, out / "inputs" / Path(name).name)
            require(digest(out / "inputs" / Path(name).name) == sha, "input changed")
        for key, meta in saved["models"].items():
            with (out / "models" / (key + ".tgl")).open("xb") as stream:
                stream.write(models[meta["model"]])
            require(digest(out / "models" / (key + ".tgl")) == meta["sha256"], "model changed")

        def one(w):
            arms, initial = {}, {}
            for arm in ARMS:
                stem = arm + "--" + w["id"]
                args = ("placement-replay", "models/" + w["model"] + ".tgl", w["case"]["scenario"],
                        "0x" + w["case"]["seed"], "--climate", w["case"]["climate"], "--ledger",
                        "--shoot-reserve", "off" if arm == "eligible" else "on",
                        "--seed-placement", "spacing" if arm == "spacing" else "off")
                initial[arm] = training.native(binary, out, *args, "--ticks", 0)
                paths = [out / (stem + suffix + ".jsonl") for suffix in ("-placement", "-children", "-reach")]
                repeats = [p.with_name(p.stem + "-repeat.jsonl") for p in paths]
                flags = ("--placement-trace", "--recruitment-trace", "--reach-trace")
                options = tuple(v for pair in zip(flags, paths, strict=True) for v in pair)
                result = training.native(binary, out, *args, "--ticks", STOP, *options)
                framed, frame = growth.capture(binary, out, args, STOP, stem)
                raw = out / "frames" / (stem + "-repeat.raw")
                repeated = training.native(binary, out, *args, "--ticks", STOP, "--framebuffer", raw,
                    *(v for pair in zip(flags, repeats, strict=True) for v in pair))
                require({**framed, "framebuffer_crc32": None} == result and repeated == framed and
                        digest(raw) == frame["raw_sha256"] and
                        all(digest(p) == digest(q) for p, q in zip(paths, repeats, strict=True)),
                        "observer/repeat changes state, traces or pixels")
                write_json(out / (stem + "-result.json"), result)
                audit = growth.recruitment.analyze_trace(paths[1], result)
                full = reach.analyze_trace(paths[2], result, audit)
                placements, sites = read_trace(paths[0], STOP, arm == "spacing"), purchase_sites(full)
                history = training.score_world(common_view(result, arm), w["case"], saved["models"][w["model"]]["metadata"])
                budget.founders.write_gzip(out / (stem + "-reach-audit.json.gz"), full)
                for p in (*paths, *repeats):
                    compress(p, Path(str(p) + ".gz"))
                    p.unlink()
                a = {"result": result, "history": history, "audit": audit,
                     "metrics": growth.scoring.metrics(result, audit, history), "frame": frame,
                     "placements": placements, "purchase_sites": sites,
                     "placement_audit": analyze(result, placements, sites, arm == "spacing"),
                     "trace_sha256": digest(Path(str(paths[1]) + ".gz")),
                     "placement_sha256": digest(Path(str(paths[0]) + ".gz")),
                     "reach_sha256": digest(Path(str(paths[2]) + ".gz")),
                     "reach_audit_sha256": digest(out / (stem + "-reach-audit.json.gz")),
                     "repeat_and_plain_verified": True}
                a["species_audit"] = budget.species.analyze_arm(a, arm, w["case"],
                    saved["models"][w["model"]]["metadata"], normalize=common_view)
                if arm != "spacing":
                    old = w["arms"][arm]
                    require(common_view(result, arm) == budget.common_view(old["result"], arm) and
                            a["trace_sha256"] == old["trace_sha256"] and frame["raw_sha256"] == old["frame"]["raw_sha256"],
                            "archived control differs")
                arms[arm] = a
                print(w["id"] + " / " + arm + ": verified purchase mapping, lifetimes, repeat and pixels", flush=True)
            return {k: w[k] for k in ("id", "model", "case")} | {"initial": initial, "arms": arms}

        with ThreadPoolExecutor(max_workers=jobs) as pool:
            worlds = list(pool.map(one, saved["worlds"]))
        sheets = {}
        for climate in ("steady", "seasonal"):
            directory = out / "frames" / climate
            directory.mkdir()
            groups = [[{**w["arms"][a]["frame"], "framebuffer": str(out / w["arms"][a]["frame"]["framebuffer"])}
                       for a in ARMS] for w in worlds if w["case"]["climate"] == climate]
            sheets[climate] = {**contact_sheet(directory, groups), "png": "frames/" + climate + "/contact-sheet.png",
                               "sha256": digest(directory / "contact-sheet.png")}
        require(source_files() == sources and digest(source) == digest(binary) == identities["binary"] and
                digest(cache) == identities["cache"] and all(digest(ROOT / p) == sha for p, sha in INPUTS.items()) and
                all(digest(out / "models" / (k + ".tgl")) == m["sha256"] for k, m in saved["models"].items()),
                "sources/build/inputs/models changed")
        value = {"rule": RULE, "inputs": INPUTS, "models": saved["models"], "protocol_sha256": digest(out / "protocol.md"),
                 "build": identities, "settings": settings, "source_sha256": sources, "training_runs": 0,
                 "full_replays": 108, "initial_snapshots": 36, "worlds": worlds,
                 "comparison": compare(worlds), "sheets": sheets}
        check_value(value, saved)
        budget.founders.write_gzip(out / "results.json.gz", value)
        write_json(out / "manifest.json", {"rule": RULE, "status": "complete", "artifacts": {
            str(p.relative_to(out)): digest(p) for p in sorted(out.rglob("*")) if p.is_file()}})
    except BaseException as error:
        (out / "FAILED.txt").write_text(str(error) + "\n")
        raise


def verify(path):
    bundle = path if path.is_dir() else None
    if bundle:
        require(not (bundle / "FAILED.txt").exists(), "incomplete collection")
        manifest = json.loads((bundle / "manifest.json").read_text())
        require(manifest["rule"] == RULE and manifest["status"] == "complete", "wrong bundle")
        for name in manifest["artifacts"]:
            artifact(bundle, manifest, name)
        path = bundle / "results.json.gz"
    with gzip.open(path, "rt") as stream:
        value = json.load(stream)
    check_value(value, load_input())
    if bundle:
        for w in value["worlds"]:
            for arm in ARMS:
                a, stem = w["arms"][arm], arm + "--" + w["id"]
                for suffix, field in (("children", "trace_sha256"), ("reach", "reach_sha256"),
                                      ("placement", "placement_sha256")):
                    require(digest(bundle / (stem + "-" + suffix + ".jsonl.gz")) == a[field] ==
                            digest(bundle / (stem + "-" + suffix + "-repeat.jsonl.gz")), "repeat trace bytes differ")
                require(json.loads((bundle / (stem + "-result.json")).read_text()) == a["result"] and
                        digest(bundle / a["frame"]["framebuffer"]) == a["frame"]["raw_sha256"] ==
                        digest(bundle / "frames" / (stem + "-repeat.raw")) and
                        digest(bundle / a["frame"]["png"]) == a["frame"]["png_sha256"], "result/frame identity differs")
                require(growth.recruitment.analyze_trace(bundle / (stem + "-children.jsonl.gz"), a["result"]) == a["audit"],
                        "recruitment audit differs")
                full = reach.analyze_trace(bundle / (stem + "-reach.jsonl.gz"), a["result"], a["audit"])
                require(full == germination.load(bundle / (stem + "-reach-audit.json.gz"), a["reach_audit_sha256"]) and
                        purchase_sites(full) == a["purchase_sites"] and
                        read_trace(bundle / (stem + "-placement.jsonl.gz"), STOP, arm == "spacing") == a["placements"],
                        "full reach/placement receipts differ")
        for name in manifest["artifacts"]:
            artifact(bundle, manifest, name)
    print("Verified 36 placement histories, old controls, purchase masks and renewal gates" +
          (", plus full trace lifetimes and bundle hashes." if bundle else " (offline)."))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path, default=ROOT / "build-host")
    parser.add_argument("--jobs", type=int, default=2)
    output = parser.add_mutually_exclusive_group(required=True)
    output.add_argument("--out", type=Path)
    output.add_argument("--verify", type=Path)
    args = parser.parse_args()
    try:
        if args.verify:
            verify(args.verify.resolve())
        else:
            collect(args.build.resolve(), args.out.resolve(), args.jobs)
        return 0
    except (OSError, ValueError, RuntimeError, KeyError, TypeError, StopIteration) as error:
        print("placement screen failed: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
