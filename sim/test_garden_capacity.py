#!/usr/bin/env python3
"""Guard the host-only capacity experiment and compare two explicit builds."""

import argparse
import copy
import itertools
import json
from pathlib import Path
import subprocess
import sys
import tempfile

import garden_ecology as ecology
import garden_experiments as experiment
import garden_node_audit as audit
from test_garden_node_audit import plant
from test_garden_dispersal import run


def rejects(call):
    try:
        call()
    except RuntimeError:
        return
    raise AssertionError("invalid capacity experiment accepted")


def boundaries(cc):
    source = Path(__file__).resolve().parent.parent / "src"
    for wide, water, combined, large in itertools.product((False, True), repeat=4):
        valid = combined == (wide and water) and (not large or combined)
        definitions = [f"-DTOY_FACTORY_GARDEN_{name}=1" for name, enabled in (
            ("WIDE_DISPERSAL", wide), ("WATER_HEADROOM", water),
            ("COMBINED_EXPERIMENT", combined), ("LARGE_POOL", large)) if enabled]
        for device in (False, True):
            expected = valid and not (device and (wide or water or large))
            text = '#include "garden_world.h"\n_Static_assert(PICOSYSTEM_GARDEN_MAX_NODES == '
            text += str(512 if large else 256) + ', "capacity");\n'
            result = subprocess.run([cc, "-std=c11", "-Werror", "-fsyntax-only", "-x", "c",
                                     "-I", str(source), *definitions,
                                     *(["-D__ZEPHYR__"] if device else []), "-"],
                                    input=text, capture_output=True, text=True, timeout=30)
            assert (result.returncode == 0) == expected, result.stderr
        args = ("wide-v1" if wide else "narrow-v1", "headroom-v1" if water else "legacy-v1",
                combined, 512 if large else 256)
        if valid:
            environment = experiment.requested_environment(*args)
            experiment.validate_environment(environment)
            assert environment.get("node_capacity", 256) == args[-1]
        else:
            rejects(lambda: experiment.requested_environment(*args))
    rejects(lambda: experiment.validate_environment({**experiment.COMBINED_ENVIRONMENT, "node_capacity": 300}))
    # A 256-node world is full only under the reference capacity. No hidden
    # default is allowed when inspecting an explicitly identified large build.
    row = {"nodes": 256, "living": 1, "plants": [plant(1, 256, 128)], "seeds": []}
    assert audit.ownership(row)["node_full"] == 1
    rejects(lambda: audit.ownership(row, 512))
    row["node_capacity"] = 512
    result = audit.ownership(row, 512)
    assert result["free_nodes"] == 256 and result["node_full"] == result["seed_node_gate"] == 0
    rejects(lambda: audit.ownership(row))
    for count in (508, 509, 511, 512):
        row.update(nodes=count, plants=[plant(1, count, 128)])
        result = audit.ownership(row, 512)
        assert result["node_full"] == (count == 512)
        assert result["seed_node_gate"] == (count > 508)
    row.update(nodes=513, plants=[plant(1, 513, 128)])
    rejects(lambda: audit.ownership(row, 512))


def integration(reference_build, large_build, root):
    scripts = Path(__file__).resolve().parent
    model = root / "model.tgm"
    run([reference_build / "toy-factory-garden-train", "--generations", "0", "--trials", "1",
         "--ticks", "3840", "--output", model, "--c-output", root / "model.c"])
    for capacity, build, other in ((256, reference_build, large_build), (512, large_build, reference_build)):
        bundle = root / str(capacity)
        common = [sys.executable, scripts / "garden_experiments.py", "--output", bundle,
                  "--evaluator", build / "toy-factory-garden-eval",
                  "--inspector", build / "toy-factory-garden-inspect",
                  "--candidate-model", model, "--control-model", model,
                  "--candidate-probe", experiment.NIGHT_PROBE, "--trials", "1", "--cycles", "2",
                  "--trace-pairs", "1", "--dispersal", "wide-v1", "--water-uptake", "headroom-v1",
                  "--combined-experiment", "--node-capacity", str(capacity)]
        run(common)
        run([*common, "--output", root / f"{capacity}-wrong", "--node-capacity", str(768-capacity)], 1)
        assert not (root / f"{capacity}-wrong/manifest.json").exists()
        run([sys.executable, bundle / "tools/garden_experiments.py", "--replay", bundle])
        for name, script in (("nodes", "garden_node_audit.py"), ("seeds", "garden_establishment.py")):
            output = root / f"{capacity}-{name}"
            command = [sys.executable, scripts / script, "--bundle", bundle, "--output", output,
                       "--late-cycles", "1"]
            if name == "seeds":
                command.extend(("--inspector", build / "toy-factory-garden-inspect"))
            run(command)
            run([sys.executable, output / ("tools/"+script), "--verify", output])
            if name == "seeds":
                run([*command, "--output", root / f"{capacity}-{name}-wrong", "--inspector",
                     other / "toy-factory-garden-inspect"], 1)
        command = [sys.executable, scripts / "garden_gallery.py", "--bundle", bundle,
                   "--output", root / f"{capacity}-gallery", "--checkpoint", "0",
                   "--replayer", build / "toy-factory-garden-replay"]
        run(command)
        run([sys.executable, scripts / "garden_gallery.py", "--verify", root / f"{capacity}-gallery"])
        run([*command, "--output", root / f"{capacity}-wrong-gallery", "--replayer",
             other / "toy-factory-garden-replay"], 1)
    a, b = (experiment.read_json(root / str(capacity) / "manifest.json") for capacity in (256, 512))
    ecology.validate_pair(a, b, experiment.LARGE_POOL_ENVIRONMENT, experiment.COMBINED_ENVIRONMENT)
    rejects(lambda: ecology.validate_pair(a, b, experiment.LARGE_POOL_ENVIRONMENT))
    for field in ("seeds", "cycles", "candidate_probe", "models"):
        bad = copy.deepcopy(b)
        bad[field] = {"candidate": {"sha256": "bad"}} if field == "models" else None
        rejects(lambda: ecology.validate_pair(a, bad, experiment.LARGE_POOL_ENVIRONMENT,
                                             experiment.COMBINED_ENVIRONMENT))
    output = root / "comparison.json"
    run([sys.executable, scripts / "garden_ecology.py", "--control", root / "256",
         "--candidate", root / "512", "--change", "node-capacity", "--late-cycles", "1",
         "--output", output])
    assert len(json.loads(output.read_text())["pairs"]) == 6
    for job in ("candidate", "control"):
        timelines = []
        for capacity in (256, 512):
            bundle = root / str(capacity)
            report = experiment.read_json(bundle / f"reports/{job}.json")
            timelines.append(experiment.load_timelines(bundle / f"timelines/{job}.jsonl.gz", report))
        for key, rows in timelines[0].items():
            other = {row["tick"]: row for row in timelines[1][key]}
            for row in rows:
                if row["nodes"] > 252:
                    break
                assert row == other[row["tick"]], "divergence before node capacity could act"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cc", default="cc")
    parser.add_argument("--reference-build", type=Path)
    parser.add_argument("--large-build", type=Path)
    args = parser.parse_args()
    boundaries(args.cc)
    if bool(args.reference_build) != bool(args.large_build):
        parser.error("supply both builds for integration")
    if args.reference_build:
        with tempfile.TemporaryDirectory(prefix="garden-capacity-test-") as temporary:
            integration(args.reference_build, args.large_build, Path(temporary))
    print("PASS: host capacity guards, ownership boundaries" + (", cross-build replay/identity" if args.large_build else ""))


if __name__ == "__main__":
    main()
