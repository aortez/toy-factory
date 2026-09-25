#!/usr/bin/env python3
"""Native step tracing, prefix neutrality and malformed audit rejection."""
import argparse
import copy
import gzip
import json
from pathlib import Path
import subprocess
import tempfile

import garden_seed_attempts as audit
from garden_resources import require


def rejects(call):
    try:
        call()
    except RuntimeError:
        return
    raise AssertionError("invalid seed audit accepted")


def sequential_fixture():
    parent = {"id": 1, "nodes": 4, "column": 0, "dead": False}
    child = {"id": 2, "nodes": 4, "column": 14, "parent": 1, "generation": 1, "dead": False}
    seed = {"parent": 1, "age": 7, "generation": 1, "column": 14, "species": 0}
    old = {"nodes": 4, "plants": [parent], "seeds": [seed, seed],
           "births": 0, "seeds_created": 0, "seeds_expired": 0}
    world = {"nodes": 8, "plants": [parent, child], "seeds": [seed],
             "births": 1, "seeds_created": 0, "seeds_expired": 0}
    before = [32 if c < 3 else 0 for c in range(28)]
    after = [32 if c < 3 or abs(c-14) < 3 else 0 for c in range(28)]
    first = {**seed, "age": 8, "child": 2, "nodes": 4, "plants": 1, "moisture": 32,
             "light": 255, "blockers": 0, "outcome": 2, "sites": before}
    second = {**first, "child": 0, "nodes": 8, "plants": 2, "moisture": 20,
              "blockers": 32, "outcome": 0, "sites": after}
    row = {"stages": [[4,1,2], [4,1,2], [8,2,1], [8,2,1], [8,2,1]],
           "sites_before": before, "attempts": [first, second]}
    run = lambda r: audit.check_step(r, old, world, {"sites": [[m,32,255] for m in after]}, 256)
    values, _, born = run(row)
    assert values["germinations"] == len(born) == 1 and values["only_spacing"] == 1
    bad = copy.deepcopy(row); bad["attempts"][1]["sites"] = before
    rejects(lambda: run(bad))
    bad = copy.deepcopy(row); bad["attempts"][1]["moisture"] += 12
    rejects(lambda: run(bad))
    for change in ("outcome", "age", "child", "nodes", "blockers", "sites"):
        bad = copy.deepcopy(row)
        a = bad["attempts"][0]
        if change == "sites":
            a["sites"][a["column"]] = 64
        else:
            a[change] += 1
        rejects(lambda: run(bad))
    bad = copy.deepcopy(row); bad["attempts"].pop()
    rejects(lambda: run(bad))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path, required=True)
    build = parser.parse_args().build.resolve()
    sequential_fixture()
    with tempfile.TemporaryDirectory(prefix="seed-attempt-test-") as temp:
        root = Path(temp)
        model = root/"model.tgm"
        subprocess.run([str(build/"toy-factory-garden-water-audit-test"), str(model)], check=True, timeout=60)
        end = 18*3840
        for side in ("neural", "reserve"):
            folder = root/side
            folder.mkdir()
            c = {"scenario": "rainfed-crowded", "seed": "b61837dc", "policy": side, "arm": "fresh-4"}
            policy = audit.recruitment.policy.POLICIES[side]
            schedule = audit.recruitment.diversity.SCHEDULES["fresh-4"]
            args = [str(model), c["scenario"], policy, "0x"+c["seed"]]
            bounds = {}
            for kind, flag in (("world", "--ecology"), ("sites", "--seed-sites")):
                bounds[kind] = audit.recruitment.diversity.disturbance.capture(
                    [str(build/"toy-factory-garden-inspect"), *args, "--leaf-policy", "selective",
                     "--disturbance-seed", str(schedule), flag, "--ticks", str(end)],
                    folder/f"{kind}.gz", root, "world" if kind == "world" else "seed-sites", schedule, end)
            for start in (0, 16*3840):
                raw = folder/f"{start}.jsonl"
                cmd = [str(build/"toy-factory-garden-seed-attempts"), *args, str(schedule), str(start), str(end)]
                audit.experiment.command_run(cmd, raw, root, 60)
                packed = folder/f"{start}.gz"
                audit.experiment.compress(raw, packed)
                with raw.open() as f:
                    values = [json.loads(l) for l in f]
                h = values[0]
                c["capacity"] = h["node_capacity"]
                expect = audit.expected_header(c, start, end, h["model_crc32"], h["drainage_rule"],
                                               seed_capacity=h.get("seed_capacity", 8))
                result = audit.analyze(packed, folder/"world.gz", folder/"sites.gz", bounds, expect)
                assert result["checked"] == (end-start)//15+1
                assert result["windows"]["all"]["steps"] == (end-start)//15
                if start == 0:
                    worlds = audit.rows(folder/"world.gz", 0)
                    sites = audit.rows(folder/"sites.gz", 0)
                    r = next(v for v in values if v["type"] == "seed-step" and v["tick"] == 15)
                    old = {**worlds[r["tick"]-15], "seeds": sites[r["tick"]-15]["seeds"]}
                    run = lambda v: audit.check_step(v, old, worlds[v["tick"]], sites[v["tick"]], c["capacity"])
                    run(r)
                    bad = copy.deepcopy(r); bad["stages"][1][0] += 1
                    rejects(lambda: run(bad))
                damaged = folder/f"{start}.bad.gz"

                def check_bad(records, header=expect):
                    with gzip.open(damaged, "wt") as stream:
                        for r in records:
                            stream.write(json.dumps(r)+"\n")
                    return audit.analyze(damaged, folder/"world.gz", folder/"sites.gz", bounds, header)

                rejects(lambda: check_bad(values[:-1]))
                rejects(lambda: check_bad([v for v in values if v["type"] != "disturbance"]))
                rejects(lambda: check_bad(values, {**expect, "model_crc32": "wrong"}))
                print(f"Seed attempts {c['capacity']}/{side}/from={start}: neutral and validated", flush=True)
            for bad in (("bad-policy", "0", "270"), (policy, "270", "270"), (policy, "1", "270"),
                        (policy, "0", "737295"), (policy, "0", "-15")):
                result = subprocess.run([str(build/"toy-factory-garden-seed-attempts"), str(model),
                    c["scenario"], bad[0], "123", "0", bad[1], bad[2]], capture_output=True, timeout=30)
                require(result.returncode == 2, "invalid CLI accepted")


if __name__ == "__main__":
    main()
