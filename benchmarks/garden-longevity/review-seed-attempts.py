"""Verify/export the frozen seed-attempt diagnostic; never execute a simulation."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/"sim"))
import garden_seed_attempts as audit


def review(reanalyze):
    root = ROOT/"artifacts/garden-seed-attempts"
    manifest = root/"manifest.json"
    m = json.loads(manifest.read_text())
    assert m["status"] == "complete" and m["kind"] == "garden-seed-attempts" and m["expected_runs"] == 8
    for name, sha in m["artifacts"].items():
        path = (root/name).resolve()
        assert path.is_relative_to(root.resolve()) and hashlib.sha256(path.read_bytes()).hexdigest() == sha
    results = json.loads((root/"summary.json").read_text())
    assert len(results) == 8
    total, cases = Counter(), []
    for result in results:
        key, a = result["key"], result["analysis"]
        assert a == json.loads((root/f"analyses/{key}.json").read_text())
        if reanalyze:
            current = audit.analyze(root/f"traces/{key}.gz", root/f"input/{key}.world.gz",
                root/f"input/{key}.sites.gz", json.loads((root/f"input/{key}.boundaries.json").read_text()),
                a["header"])
            assert current == a, key
        total.update(a["windows"]["all"])
        total["hashes"] += a["checked"]
        cases.append({"key": key, **{k: a[k] for k in ("header", "checked", "windows", "mature_blocker_hist", "prior_vacancy_window")},
            "germinations": [{k: g[k] for k in ("tick", "phase", "parent", "child", "age", "column", "nodes", "plants")}
                             for g in a["germinations"]]})
    assert total["visits"] == total["checks"] + total["expired"]
    assert total["checks"] == total["mature_checks"] + total["dormant"]
    assert total["germination_nodes"] == total["germinations"] * 4
    return {"manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
        "artifacts_verified": len(m["artifacts"]), "source_count": len(m["source_sha256"]),
        "totals": total, "cases": cases}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--reanalyze", action="store_true")
    args = parser.parse_args()
    if args.output is not None and args.output.exists():
        parser.error("output already exists")
    report = json.dumps(review(args.reanalyze), sort_keys=True, indent=2)+"\n"
    if args.output is None:
        print(report, end="")
    else:
        with args.output.open("x") as stream:
            stream.write(report)
        print(f"Verified and exported {args.output}")
