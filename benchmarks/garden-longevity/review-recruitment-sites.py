"""Verify the frozen recruitment bundle and export counts plus a labeled post-hoc example."""
import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "sim"))
import garden_recruitment as audit

BUNDLE = ROOT / "artifacts/garden-crowded-recruitment"
DAY = 3840


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def vacancy_example():
    """Selected after inspecting outcomes; it does not replace the declared paired panel."""
    key = "256.44.fresh-4.off.reserve"
    a = json.loads((BUNDLE / f"analyses/{key}.json").read_text())
    patch = a["patches"][-1]["event"]
    assert patch["killed"] == [24]
    reclaim = next(p["reclaimed_tick"] for p in a["world"]["lineages"] if p["id"] == 24)
    landmarks, before = {}, None
    with gzip.open(BUNDLE / f"traces/{key}.world.gz", "rt") as stream:
        for line in stream:
            row = json.loads(line)
            tick = row["tick"]
            if tick == reclaim - 15:
                before = row
            if tick == reclaim:
                landmarks["after_reclaim"] = row
            if tick > reclaim and row["nodes"] > 252:
                landmarks.setdefault("insufficient_seedling_nodes", row)
            if tick > reclaim and row["nodes"] == 256:
                landmarks["full_again"] = row
                break
    assert before is not None and len(landmarks) == 3
    survivors = {p["id"]: p for p in before["plants"] if not p["dead"]}
    final = landmarks["full_again"]
    assert set(survivors) == {p["id"] for p in final["plants"]}
    assert before["births"] == final["births"]
    growth = {str(p["id"]): p["nodes"] - survivors[p["id"]]["nodes"] for p in final["plants"]}
    assert sum(growth.values()) == 46
    site = None
    with gzip.open(BUNDLE / f"traces/{key}.sites.gz", "rt") as stream:
        for line in stream:
            row = json.loads(line)
            if row["tick"] == reclaim:
                site = row
                break
    assert site is not None and site["hash"] == landmarks["after_reclaim"]["hash"]
    assert all(s["blockers"] for s in site["seeds"])
    return {"selection": "post-hoc final patch in adverse 256 reserve case", "key": key,
        "event": patch, "reclaimed_tick": reclaim, "before_reclaim_hash": before["hash"],
        "incumbent_node_growth": growth,
        "landmarks": {k: {n: r[n] for n in ("tick", "hash", "nodes", "births", "sun_phase")}
                      for k, r in landmarks.items()},
        "open_columns_after_reclaim": [i for i, s in enumerate(site["sites"]) if s[0] == 0],
        "seed_bank_after_reclaim": site["seeds"]}


def collect(reanalyze=False):
    m = json.loads((BUNDLE / "manifest.json").read_text())
    assert m["kind"] == "garden-crowded-recruitment" and m["status"] == "complete"
    assert m["expected_runs"] == 8 and m["horizon"] == 192 * DAY
    for name, sha in m["artifacts"].items():
        path = (BUNDLE / name).resolve()
        assert path.is_relative_to(BUNDLE.resolve()) and digest(path) == sha, name
    cases = json.loads((BUNDLE / "cases.json").read_text())
    assert len(cases) == 8
    output, checks = [], Counter()
    for c in cases:
        key = c["key"]
        a = json.loads((BUNDLE / f"analyses/{key}.json").read_text())
        if reanalyze:
            current = audit.analyze(BUNDLE / f"traces/{key}.world.gz", BUNDLE / f"traces/{key}.sites.gz",
                json.loads((BUNDLE / f"analyses/{key}.boundaries.json").read_text()),
                json.loads((BUNDLE / f"input/{key}.population.json").read_text()),
                BUNDLE / f"input/{key}.population.gz", c["capacity"], c["policy"])
            assert current == a, key
        checks.update(site_world_checkpoints=a["seeds"]["checkpoints_verified"],
            sparse_checkpoints=a["checked_sparse"], seed_lifetimes=len(a["seeds"]["seeds"]),
            live_resource_steps=a["world"]["windows"]["whole"]["budget_checked_live_steps"],
            patch_boundaries=len(a["patches"]), independent_replays=3, final_frames=1)
        patches = [p for p in a["patches"] if p["event"]["tick"] > 160 * DAY]
        output.append({"key": key, "capacity": c["capacity"], "seed": c["seed"], "arm": c["arm"],
            "policy": c["policy"], "cohorts": a["cohorts"],
            "closing_seed_cohort": a["seeds"]["cohorts"]["late_born"],
            "closing_bright_seed_snapshots": a["seeds"]["windows"]["late"]["bright"],
            "closing_spatial": a["spatial"]["late"], "closing_world": a["world"]["windows"]["late"],
            "closing_patches": [{k: p[k] for k in ("event", "births", "first", "reclamation_delays")}
                                for p in patches]})
    return {"manifest_sha256": digest(BUNDLE / "manifest.json"), "artifacts_verified": len(m["artifacts"]),
        "source_count": len(m["source_sha256"]), "checks": checks, "cases": output,
        "post_hoc_vacancy_example": vacancy_example()}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--reanalyze", action="store_true", help="Recheck all unchanged full traces too")
    args = parser.parse_args()
    if args.output is not None and args.output.exists():
        parser.error("output already exists")
    result = json.dumps(collect(args.reanalyze), sort_keys=True, indent=2) + "\n"
    if args.output is None:
        print(result, end="")
    else:
        with args.output.open("x") as stream:
            stream.write(result)
        print(f"Verified bundle; wrote {args.output}")
