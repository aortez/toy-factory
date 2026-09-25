#!/usr/bin/env python3
"""Check the host-only intervention across evaluation, trace accounting, and visual replay."""

import argparse
import copy
import gzip
import io
import json
from pathlib import Path
import sys
import tempfile

import garden_experiments as experiment
import garden_renewal as renewal
import garden_resources as resources
from test_garden_gallery import json_run, run


def rejected(call, message):
    try:
        call()
    except RuntimeError:
        return
    raise AssertionError(message)


def test_window():
    # An empty ending is not counted as zero resources per living plant. Events
    # straddling the analysis boundary contribute only their in-window duration.
    rows = []
    for tick, living, seeds, births, qualified in ((0, 1, 0, 0, 0), (2880, 1, 0, 1, 0),
                                                 (3840, 1, 0, 2, 1), (4000, 0, 1, 3, 2),
                                                 (7680, 0, 1, 3, 2)):
        rows.append(dict(tick=tick, living=living, seed_bank=seeds, births=births,
                         deaths=1-living, seeds_created=seeds, seeds_expired=0,
                         energy=100*living, water=200*living, stress=2*living,
                         nodes=20, plant_slots=1,
                         lifetimes=dict(eligible_offspring=qualified, cycle_survivors=qualified,
                                        cycle_survivors_with_surviving_child=0)))
    trial = dict(living=0, seed_bank=1, germinations=3, deaths=1, death_causes={},
                 seed_germination_blockers={}, lifetimes=rows[-1]["lifetimes"])
    result = renewal.trial_metrics(rows, trial, 1)
    assert result["late_births"] == 1 and result["late_qualified_cycle_survivors"] == 1
    assert result["late_living_fraction"] == 160 / 3840
    assert result["late_seed_only_fraction"] == 3680 / 3840
    assert result["late_mean_energy_per_living_plant"] == 100
    assert result["nonviable"] == 0
    for invalid in (-1, 0, 3):
        rejected(lambda: renewal.trial_metrics(rows, trial, invalid), "invalid window accepted")


def integration(args):
    script = Path(__file__).with_name("garden_experiments.py")
    with tempfile.TemporaryDirectory(prefix="garden-probe-test-") as temporary:
        root = Path(temporary)
        model = root / "model.tgm"
        run([args.trainer, "--generations", "0", "--trials", "1", "--ticks", "60", "--seed", "0x1234",
             "--output", model, "--c-output", root / "model.c"])
        model_bytes = model.read_bytes()
        eval_command = [args.evaluator, "--rainfed", "--model", model, "--trials", "1"]
        ordinary = json_run([*eval_command, "--ticks", "945"])
        probed = json_run([*eval_command, "--ticks", "945", "--no-night-growth"])
        assert probed.pop("candidate_probe") == experiment.NIGHT_PROBE
        for scenario in probed["scenarios"]:
            scenario["policies"][2]["name"] = "neural-candidate"
        assert probed == ordinary, "intervention affected the world before first sunset"
        run([args.evaluator, "--no-night-growth"], 2)
        run([args.evaluator, "--model", model, "--no-night-growth"], 2)
        run([*eval_command, "--no-night-growth", "--no-night-growth"], 2)
        probe_replay = [args.replayer, model, "rainfed", experiment.NIGHT_POLICY,
                        "0x1234", "--ticks", "2880"]
        plain = json_run(probe_replay)
        captured = json_run([*probe_replay, "--framebuffer", root / "probe.raw"])
        assert {**captured, "framebuffer_crc32": None} == plain
        run([args.inspector, model, "rainfed", experiment.NIGHT_POLICY, "1", "--night-wait", "1"], 2)

        bundle = root / "bundle"
        command = [sys.executable, script, "--output", bundle, "--candidate-model", model,
                   "--control-model", model, "--candidate-probe", experiment.NIGHT_PROBE,
                   "--cycles", "2", "--trials", "1", "--trace-pairs", "1",
                   "--evaluator", args.evaluator, "--inspector", args.inspector]
        run(command)
        manifest = experiment.read_json(bundle / "manifest.json")
        assert manifest["candidate_probe"] == experiment.NIGHT_PROBE
        control = experiment.read_json(bundle / "reports/control.json")
        probe = experiment.read_json(bundle / "reports/candidate.json")
        assert control == json_run([*eval_command, "--ticks", "7680", "--seed", "0x6d617463"])
        assert probe == json_run([*eval_command, "--ticks", "7680", "--seed", "0x6d617463",
                                  "--no-night-growth"]), "timeline changed probe outcome"
        rejected(lambda: experiment.validate_report(probe, manifest["seeds"], 7680,
                                                     manifest["models"]["candidate"]),
                 "unidentified intervention accepted")
        traces = experiment.read_json(bundle / "cases.json")["cases"]
        case = next(v for v in traces if v["side"] == "candidate")
        diagnostic = experiment.read_json(bundle / f"traces/{case['id']}.resources.json")
        assert diagnostic["changed_bids"] == 0
        assert diagnostic["probe"]["suppressed_bids"] > 0
        assert all(v["first_cycle_night"]["energy_growth"] == 0 for v in diagnostic["lineages"])
        for case in traces:
            run([sys.executable, bundle / "tools/garden_experiments.py", "--replay", bundle,
                 "--case", case["id"]])
        case = next(v for v in traces if v["side"] == "candidate")
        with gzip.open(bundle / f"traces/{case['id']}.jsonl.gz", "rt") as stream:
            records = [json.loads(line) for line in stream]
        bid = next(v for v in records if v["type"] == "bid" and v["sun_phase"] >= 128)
        bid["action"] = 1
        rejected(lambda: resources.analyze_stream(io.StringIO("\n".join(map(json.dumps, records))), "bad"),
                 "incorrect nighttime action accepted")
        report = renewal.summarize(bundle, 1)
        assert len(report["trials"]) == 6
        assert set(report["aggregate"]) == {"adaptive", "neural-candidate", experiment.NIGHT_POLICY}
        for trial in report["trials"]:
            m = trial["metrics"]
            assert 0 <= m["late_qualified_cycle_survivors"] <= m["cycle_survivors"]
        run([sys.executable, script.with_name("garden_renewal.py"), "--bundle", bundle,
             "--late-cycles", "1", "--output", root / "renewal.json"])
        run([sys.executable, script.with_name("garden_renewal.py"), "--bundle", bundle,
             "--late-cycles", "1", "--output", root / "renewal.json"], 1)

        gallery = root / "gallery"
        run([sys.executable, script.with_name("garden_gallery.py"), "--bundle", bundle,
             "--output", gallery, "--include-adaptive", "--checkpoint", "2880",
             "--replayer", args.replayer])
        frames = experiment.read_json(gallery / "frames.json")["frames"]
        assert len(frames) == 6
        assert {f["policy"] for f in frames} == set(report["aggregate"])
        run([sys.executable, gallery / "tools/garden_gallery.py", "--verify", gallery])
        assert model.read_bytes() == model_bytes

        timelines = experiment.load_timelines(bundle / "timelines/candidate.jsonl.gz", probe)
        broken = copy.deepcopy(timelines)
        next(iter(broken.values()))[-1]["lifetimes"]["cycle_survivors"] += 1
        path = root / "bad.jsonl.gz"
        with gzip.open(path, "wt") as stream:
            for rows in broken.values():
                for row in rows:
                    stream.write(json.dumps(row) + "\n")
        rejected(lambda: experiment.load_timelines(path, probe), "inconsistent lifetime counts accepted")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for tool in ("replayer", "evaluator", "inspector", "trainer"):
        parser.add_argument(f"--{tool}", required=True, type=Path)
    args = parser.parse_args()
    test_window()
    integration(args)
    print("PASS: matched night-growth probe, resource accounting, renewal windows, and exact visual replay")


if __name__ == "__main__":
    main()
