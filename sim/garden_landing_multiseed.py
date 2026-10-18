#!/usr/bin/env python3
"""Five-seed landing training versus frozen single-seed finalists."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import sys

import garden_landing_controls as controls
from garden_experiments import digest, write_json
from garden_resources import require

ROOT = controls.ROOT
RULE = "garden-landing-multiseed-training-v1"
PROTOCOL = "benchmarks/garden-seasons/landing-multiseed-protocol.md"
INPUTS = {
    "landing-controls-models.json.gz": "e99cd1b864d5920b3ddc8b28cb96565228dfd3408f53aa1f1f31aa5a32a2ab7b",
    "landing-controls-results.json.gz": "82cb873997a12cbd3401f71dde5d65d9cc60f975454d1cec22d749679ccd246d",
}
training = controls.training
PROFILES = controls.PROFILES
TRAIN_SEEDS = (training.TRAIN_SEED, *controls.EVALUATION_SEEDS)
EVALUATION_SEEDS = ("b6bebb2a", "5aa2b327", "940cfdc4", "7d3b7bde")


def training_conditions():
    return [c for seed in TRAIN_SEEDS for c in training.conditions(seed)]


def evaluation_conditions():
    return [c for seed in EVALUATION_SEEDS for c in training.conditions(seed)]


def slices():
    cases = evaluation_conditions()
    return {"all": [c["id"] for c in cases], **{
        f"{field}/{value}": [c["id"] for c in cases if c[field] == value]
        for field in ("seed", "scenario", "climate")
        for value in dict.fromkeys(c[field] for c in cases)}}


def load_inputs(root):
    for name, sha in INPUTS.items():
        require(digest(root / name) == sha, "wrong frozen input: " + name)
    models = {k: bytes.fromhex(v) for k, v in json.loads(gzip.decompress(
        (root / "landing-controls-models.json.gz").read_bytes())).items()}
    old = json.loads(gzip.decompress((root / "landing-controls-results.json.gz").read_bytes()))
    require(old["rule"] == controls.RULE and old["objective"] == training.individual.RULE and
            old["profiles"] == list(PROFILES), "wrong single-seed control")
    require(hashlib.sha256(models["initial.tgm"]).hexdigest() == training.BASE_SHA,
            "wrong legacy initializer")
    for key, search in old["searches"].items():
        for c in search["candidates"]:
            require(hashlib.sha256(models[key + "/" + c["model"]]).hexdigest() == c["sha256"],
                    "archived model identity mismatch")
    return models, old


def check_controls(searches, root, archived, old):
    identities = {f"s{s:08x}-{p['id']}" for s in training.SEARCH_SEEDS for p in PROFILES}
    require(set(searches) == identities, "incomplete paired searches")
    first = searches[f"s{training.SEARCH_SEEDS[0]:08x}-live"]
    for key, run in searches.items():
        prior = old["searches"][key]
        require(run["profile"] == prior["profile"] and run["search_seed"] == prior["search_seed"],
                "unpaired search identity")
        require(len(run["candidates"]) == 7 and len(run["generations"]) == 3, "wrong search budget")
        controls.equivalent_evaluation(run["candidates"][0]["train"], first["candidates"][0]["train"],
                                       run["profile"], first["profile"])
        controls.equivalent_evaluation(run["generations"][0]["review"], prior["generations"][0]["review"],
                                       run["profile"], prior["profile"])
        for a, b in zip(run["candidates"], prior["candidates"], strict=True):
            require(a["id"] == b["id"], "unpaired candidate order")
            require(set(a["train"]["worlds"]) == {c["id"] for c in training_conditions()},
                    "wrong training panel")
            require(digest(root / key / a["model"]) == a["sha256"], "model changed during search")
            if a["mutation"] is not None:
                fields = ("rng_before", "rng_after", "legacy_mutations", "landing_mutations")
                require(all(a["mutation"][f] == b["mutation"][f] for f in fields), "unpaired RNG schedule")
            if a["id"] == "g0" or a["id"].startswith("g1-"):
                require(a["sha256"] == b["sha256"] and (root / key / a["model"]).read_bytes() ==
                        archived[key + "/" + b["model"]], "initial/first-generation bytes changed")


def evaluation_models(searches, old):
    models = []
    for profile in PROFILES:
        key = f"s{training.SEARCH_SEEDS[0]:08x}-{profile['id']}"
        c = searches[key]["candidates"][0]
        models.append({"id": "initial-" + profile["id"], "profile": profile, "champion": "g0",
                       "model": key + "/" + c["model"], "sha256": c["sha256"], "metadata": c["metadata"]})
    for cohort, runs in (("single", old["searches"]), ("multi", searches)):
        for seed in training.SEARCH_SEEDS:
            for profile in PROFILES:
                key = f"s{seed:08x}-{profile['id']}"
                run = runs[key]
                chosen = next(c for c in run["candidates"] if c["id"] == run["generations"][-1]["champion"])
                models.append({"id": cohort + "-" + key, "profile": profile, "champion": chosen["id"],
                               "model": ("single/" if cohort == "single" else "") + key + "/" + chosen["model"],
                               "sha256": chosen["sha256"], "metadata": chosen["metadata"]})
    return models


def comparisons(evaluations):
    pairs = []
    for seed in training.SEARCH_SEEDS:
        base = f"s{seed:08x}"
        for profile in PROFILES:
            key = base + "-" + profile["id"]
            pairs.append(("breadth-" + profile["id"], "single-" + key, "multi-" + key))
            pairs.extend(("initial-" + cohort, "initial-" + profile["id"], cohort + "-" + key)
                         for cohort in ("single", "multi"))
        pairs.append(("multi-live-fixed", "multi-" + base + "-fixed", "multi-" + base + "-live"))
    return [{"kind": kind, "control": a, "candidate": b,
             "slices": {name: training.individual.pair_group(
                 {k: w["history"] for k, w in evaluations[a]["worlds"].items()},
                 {k: w["history"] for k, w in evaluations[b]["worlds"].items()}, ids)
                        for name, ids in slices().items()}} for kind, a, b in pairs]


def support_gates(pairs):
    gates = {}
    for kind in ("breadth-live", "breadth-fixed", "multi-live-fixed"):
        selected = [p for p in pairs if p["kind"] == kind]
        expected = {f"multi-s{s:08x}-{'fixed' if kind == 'breadth-fixed' else 'live'}"
                    for s in training.SEARCH_SEEDS}
        require(len(selected) == 3 and {p["candidate"] for p in selected} == expected,
                "incomplete/duplicate primary comparisons")
        # Same strict replicate/climate/tier gate as the preceding pilot.
        gate = controls.support_gate([{**p, "kind": "paired-training"} for p in selected])
        gates[kind] = {"consistent_advantage": gate["consistent_live_advantage"], "checks": gate["checks"]}
    return gates


def run_panel(binary, inputs, root, jobs, images):
    require(1 <= jobs <= 8 and not root.exists(), "fresh output and jobs 1..8 required")
    archived, old = load_inputs(inputs)
    root.mkdir(parents=True)
    with (root / "initial.tgm").open("xb") as stream:
        stream.write(archived["initial.tgm"])
    searches, galleries = {}, {}
    for seed in training.SEARCH_SEEDS:
        for profile in PROFILES:
            key = f"s{seed:08x}-{profile['id']}"
            searches[key], gallery = controls.search_one(binary, root / "initial.tgm", root / key,
                seed, profile, jobs, images, train_cases=training_conditions())
            if images:
                galleries[key] = gallery
    check_controls(searches, root, archived, old)
    # No evaluation data can influence training or choose among the six finalists.
    models = evaluation_models(searches, old)
    evaluations = {}
    for model in models:
        path = root / model["model"]
        if model["id"].startswith("single-"):
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("xb") as stream:
                stream.write(archived[model["model"].removeprefix("single/")])
        require(digest(path) == model["sha256"], "evaluation model identity changed")
        value = controls.evaluate(binary, root, model["model"], evaluation_conditions(), model["profile"],
                                  jobs, model["metadata"])
        require(digest(path) == model["sha256"], "evaluation changed model")
        evaluations[model["id"]] = value
        write_json(root / (model["id"] + "-evaluation.json"), value)
        print(model["id"] + " evaluation: " + str(value["aggregate"]["key"]), flush=True)
    controls.equivalent_evaluation(evaluations["initial-live"], evaluations["initial-fixed"], *PROFILES)
    paired = comparisons(evaluations)
    result = {"schema_version": 1, "rule": RULE, "objective": training.individual.RULE,
              "profiles": list(PROFILES), "training_conditions": training_conditions(),
              "evaluation_conditions": evaluation_conditions(), "searches": searches, "models": models,
              "evaluations": evaluations, "comparisons": paired, "support_gates": support_gates(paired),
              "candidate_evaluations": 42, "scored_worlds": 1136}
    write_json(root / "results.json", result)
    if images:
        write_json(root / "gallery.json", galleries)
    return result


def collect(build, inputs, output, jobs):
    return controls.collect(build, inputs, output, jobs, experiment=sys.modules[__name__])


def verify(output):
    controls.verify(output, experiment=sys.modules[__name__])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path)
    parser.add_argument("--inputs", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--jobs", type=int)
    parser.add_argument("--verify", type=Path)
    args = parser.parse_args()
    try:
        if args.verify:
            require(all(v is None for v in (args.build, args.inputs, args.out, args.jobs)), "verify takes no overrides")
            verify(args.verify.resolve())
        else:
            require(args.out is not None, "collection requires --out")
            collect((args.build or ROOT / "build-host").resolve(),
                    (args.inputs or ROOT / "benchmarks/garden-seasons").resolve(),
                    args.out.resolve(), 4 if args.jobs is None else args.jobs)
        return 0
    except (OSError, ValueError, RuntimeError) as error:
        print("multi-seed training failed: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
