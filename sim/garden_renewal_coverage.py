#!/usr/bin/env python3
"""Fixed 8/16-world bounded-renewal comparison with reused narrow searches."""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from fractions import Fraction
from pathlib import Path
import shutil
import tempfile
import time

import garden_renewal_replication as previous

mixed, pilot, experiment, require = previous.mixed, previous.pilot, previous.experiment, previous.require
scoring = previous.previous
RULE = "garden-renewal-coverage-v1"
PROTOCOL = "benchmarks/garden-longevity/renewal-coverage-protocol.md"
BASELINE_SHA = "8cc60dbe89f9040457f4abd60e81b2c3f5379dac6987b5b3deb872dcc870a45f"
ADDED = ("42f07d93", "b1e4b7b8", "e49fe860", "57dda3ee", "c8290554", "fd3b9c7f", "ea42f2a7", "9baf8b63")
REVIEW = ("5a30b7f3", "a9247dd8", "fc5f2200", "4f1d698e", "d0e9cf34", "e5fb561f", "f28238c7", "836f4103")
ARMS = ("narrow", "wide")
REPLICAS = tuple(s.name for s in previous.STUDIES)
OBJECTIVE = scoring.Objective("renewal")
BUDGET = {"training_trials": 640, "repeat_trials": 640, "review_trials": 256,
          "frame_replays": 512, "mutation_calls": 36, "native_processes": 2084,
          "reused_trial_histories": 640, "reused_mutation_records": 36, "frames": 256}


def study(replica, arm):
    require(replica in REPLICAS and arm in ARMS, "unknown coverage replica/arm")
    old = next(s for s in previous.STUDIES if s.name == replica)
    return mixed.Study(f"{replica}-{arm}", RULE, PROTOCOL,
        previous.TRAIN + (ADDED if arm == "wide" else ()), REVIEW,
        previous.TRAIN_PATCHES, previous.REVIEW_PATCHES, old.rng)


def settings():
    require(tuple(experiment.trial_seeds(0x63767432, 8)) == ADDED and
            tuple(experiment.trial_seeds(0x63767232, 8)) == REVIEW, "changed fresh seed derivation")
    seeds = (*previous.TRAIN, *previous.REVIEW, *ADDED, *REVIEW,
             *(v for _, v in (*previous.TRAIN_PATCHES, *previous.REVIEW_PATCHES)),
             *(f"{s.rng:08x}" for s in previous.STUDIES))
    require(len(set(seeds)) == len(seeds), "seed collision/leakage")
    return {"rule": RULE, "replicas": {r: {a: study(r,a).record() for a in ARMS} for r in REPLICAS},
            "selector": scoring.individual.RULE, "legacy_view": pilot.fitness.RULE,
            "budget": dict(BUDGET), "concurrent_replicas": 2, "native_window": [pilot.START,pilot.END],
            "stop": pilot.STOP, "periods": [list(p) for p in scoring.rolling.PERIODS],
            "credit_age_ticks": scoring.rolling.CREDIT_AGE,
            "freshness_audit": "Before protocol: no literal matches in local sim/docs/benchmarks/artifacts JSON/JSONL/Markdown/Python including ignored files; compressed/private history not claimed"}


def names():
    return ["initial", *[f"g{g}-c{c}" for g in range(1,mixed.GENERATIONS+1) for c in range(1,mixed.OFFSPRING+1)]]


def subpath(replica, arm):
    return Path("replicas")/replica/"arms"/arm


def copies():
    result = {"input/replication-results.json": "results.json", "input/native-source.tar.gz": "input/native-source.tar.gz",
              "input/CMakeCache.txt": "input/CMakeCache.txt"}
    for replica in REPLICAS:
        old = f"replicas/{replica}/arms/renewal"
        for arm in ARMS:
            sub = subpath(replica,arm)
            for name in pilot.BINARIES:
                result[str(sub/"bin"/name)] = f"{old}/bin/{name}"
            result[str(sub/"input/initial.tgm")] = f"{old}/input/initial.tgm"
        sub = subpath(replica,"narrow")
        result[str(sub/"repeat.json")] = f"{old}/repeat.json"
        for folder in ("search","repeat"):
            for name in names():
                suffixes = ["tgm", *[f"{k}.json" for k,*_ in mixed.conditions(previous.TRAIN,dict(previous.TRAIN_PATCHES))]]
                if name != "initial":
                    suffixes.append("mutation.json")
                for suffix in suffixes:
                    result[str(sub/folder/f"{name}.{suffix}")] = f"{old}/{folder}/{name}.{suffix}"
    return result


def subset(worlds, seeds, patches=previous.TRAIN_PATCHES):
    return {k: worlds[k] for k,*_ in mixed.conditions(seeds,dict(patches))}


def views(worlds, seeds, patches):
    result = {}
    for view in scoring.ARMS:
        value = scoring.Objective(view).aggregate(worlds,seeds,patches=dict(patches))
        mean = Fraction(value["key"][2], len(worlds))
        result[view] = {"aggregate": value, "condition_count": len(worlds),
                        "mean_credit_ticks": {"numerator": mean.numerator, "denominator": mean.denominator}}
    return result


def comparisons(a, b, seeds=REVIEW, patches=previous.REVIEW_PATCHES):
    return scoring.comparison(a,b,seeds,patches=dict(patches))


def check_prefix(root, arms):
    a,b = (arms[arm]["search"] for arm in ARMS)
    for ca,cb in zip(a["candidates"][:4],b["candidates"][:4],strict=True):
        require(all(ca[k] == cb[k] for k in ("id","parent","mutation","model_crc32","model_sha256")),
                "common mutation prefix differs")
        require(ca["worlds"] == subset(cb["worlds"],previous.TRAIN), "common prefix worlds differ")
        for suffix in ("tgm",*[f"{k}.json" for k,*_ in mixed.conditions(previous.TRAIN,dict(previous.TRAIN_PATCHES))]):
            path = Path("search")/f"{ca['id']}.{suffix}"
            require((root/"arms/narrow"/path).read_bytes() == (root/"arms/wide"/path).read_bytes(),
                    "common prefix native bytes differ")
    require(arms["narrow"]["review"][0]["worlds"] == arms["wide"]["review"][0]["worlds"], "original review differs")


def diagnostics(root, arms, replica):
    result = {}
    for arm in ARMS:
        r, s = arms[arm], study(replica,arm)
        indexed = {c["id"]: c for c in r["search"]["candidates"]}
        generations = []
        for g,name in enumerate(r["search"]["champions"]):
            c, original = indexed[name], indexed["initial"]["worlds"]
            training = {"original_worlds": comparisons(subset(original,previous.TRAIN),
                subset(c["worlds"],previous.TRAIN),previous.TRAIN,previous.TRAIN_PATCHES)}
            if arm == "wide":
                training["added_worlds"] = comparisons(subset(original,ADDED),subset(c["worlds"],ADDED),ADDED,previous.TRAIN_PATCHES)
            generations.append({"generation": g, "champion": name, "model_crc32": c["model_crc32"],
                "training_views": views(c["worlds"],s.development,s.development_patches),
                "training_vs_original": training,
                "review_vs_original": comparisons(r["review"][0]["worlds"],r["review"][g]["worlds"]),
                "review_worlds": scoring.compact_worlds(r["review"][g]["worlds"]),
                "review_diversity": mixed.diversity(r["review"][g]["worlds"]),
                "training_diversity": mixed.diversity(c["worlds"]),
                "review_cohorts": previous.cohorts(root/"arms"/arm,g,s)})
        result[arm] = generations
    result["review_wide_vs_narrow"] = [comparisons(arms["narrow"]["review"][g]["worlds"],
        arms["wide"]["review"][g]["worlds"]) for g in range(mixed.GENERATIONS+1)]
    return result


def frame_rows(arms):
    return [[{**r["frames"][i], "id": f"{arm}.{r['frames'][i]['id']}", "arm": arm,
              "framebuffer": f"arms/{arm}/{r['frames'][i]['framebuffer']}", "png": f"arms/{arm}/{r['frames'][i]['png']}"}
             for arm in ARMS for r in arms[arm]["review"]]
            for i in range(len(mixed.conditions(REVIEW,dict(previous.REVIEW_PATCHES))))]


def check_sheet(root, rows, saved):
    absolute = [[{**f,"framebuffer": str(root/f["framebuffer"])} for f in row] for row in rows]
    with tempfile.TemporaryDirectory(prefix="garden-coverage-sheet-") as temp:
        result = pilot.gallery.contact_sheet(Path(temp),absolute)
        require(result == saved and (Path(temp)/"contact-sheet.png").read_bytes() == (root/"contact-sheet.png").read_bytes(),
                "contact sheet differs from frames")


def check_replica(root, result, baseline, replica):
    require(result["rule"] == RULE and set(result["arms"]) == set(ARMS), "wrong coverage replica")
    require(result["arms"]["narrow"]["search"] == baseline["replicas"][replica]["arms"]["renewal"]["search"],
            "changed reused narrow search")
    for arm in ARMS:
        sub, r, s = root/"arms"/arm, result["arms"][arm], study(replica,arm)
        require(r["objective"] == "renewal" and r["study"] == s.record(), "changed selector/profile")
        mixed.check_results(sub,r,study=s,objective=OBJECTIVE)
        for c in r["search"]["candidates"]:
            suffixes = ["tgm",*[f"{k}.json" for k,*_ in mixed.conditions(s.development,dict(s.development_patches))]]
            if c["mutation"]:
                suffixes.append("mutation.json")
            for suffix in suffixes:
                name = f"{c['id']}.{suffix}"
                require((sub/"search"/name).read_bytes() == (sub/"repeat"/name).read_bytes(), "native search repeat differs")
    check_prefix(root,result["arms"])
    require(result["diagnostics"] == diagnostics(root,result["arms"],replica), "coverage analysis differs")
    check_sheet(root,frame_rows(result["arms"]),result["gallery"])


def expected_calls(root, search, s, *, train):
    """Artifact-indexed primary commands; replay repeats use private temporary paths."""
    result = {}
    def add(target, command):
        require(target not in result, "duplicate expected native call")
        result[target] = [str(x) for x in command]
    if train:
        for folder in ("search","repeat"):
            for c in search["candidates"]:
                name = c["id"]
                model = root/folder/f"{name}.tgm"
                if c["mutation"]:
                    add(f"{folder}/{name}.mutation.json",[root/"bin/garden-model-mutate",
                        root/folder/f"{c['parent']}.tgm",model,c["mutation"]["rng_before"],mixed.MUTATIONS])
                for key,_,seed,patch in mixed.conditions(s.development,dict(s.development_patches)):
                    add(f"{folder}/{name}.{key}.json",[root/"bin/garden-persistence-trial",model,"neural",
                        "0x"+seed,"0x"+patch,pilot.START,pilot.END])
    for g in range(mixed.GENERATIONS+1):
        model = root/"review"/f"g{g}.tgm"
        for key,_,seed,patch in mixed.conditions(s.review,dict(s.review_patches)):
            name = f"review/g{g}.{key}"
            add(name+".json",[root/"bin/garden-persistence-trial",model,"neural",
                "0x"+seed,"0x"+patch,pilot.START,pilot.END])
            add(name+".png",pilot.replay_command(root,model,seed,pilot.STOP,root/(name+".rgb565"),patch=patch))
    return result


def check_budget(timing, result):
    require(set(timing["replicas"]) == set(REPLICAS), "wrong timing replicas")
    root = Path(timing["command_root"])
    commands = []
    for replica in REPLICAS:
        arms = timing["replicas"][replica]["arms"]
        require(set(arms) == set(ARMS), "wrong timing arms")
        for arm in ARMS:
            sub = root/subpath(replica,arm)
            expected = expected_calls(sub,result["replicas"][replica]["arms"][arm]["search"],
                                      study(replica,arm),train=arm == "wide")
            records = arms[arm]
            require(len(records) == len(expected) and {r["artifact"] for r in records} == set(expected),
                    "missing/extra/duplicate native calls")
            for row in records:
                command = expected[row["artifact"]]
                require(row["command"] == command, "native command differs from protocol")
                commands.append(command)
                if row["artifact"].endswith(".png"):
                    repeat = row.get("repeat_command",[])
                    require(len(repeat) == len(command), "missing/wrong image repeat command")
                    target = Path(repeat[-1])
                    require(repeat[:-1] == command[:-1] and target.is_absolute() and target.name == "frame.rgb565" and
                            target.parent.name.startswith("mixed-garden-frame-"), "changed repeat command/target")
                    commands.append(repeat)
                else:
                    require("repeat_command" not in row, "extra native command")
    require(len(commands) == BUDGET["native_processes"] and Counter(Path(c[0]).name for c in commands) ==
            {"garden-persistence-trial": 1536, "garden-replay": 512, "garden-model-mutate": 36}, "wrong native budget")


def collect_replica(root, replica, baseline):
    begin, arms, timings = time.monotonic(), {}, {a: [] for a in ARMS}
    for arm in ARMS:
        sub, s, reviews = root/"arms"/arm, study(replica,arm), []
        def capture(g, champion):
            reviews.append(mixed.review_generation(sub,g,champion,timings[arm],study=s,objective=OBJECTIVE))
        if arm == "narrow":
            search = baseline["replicas"][replica]["arms"]["renewal"]["search"]
            print(f"Starting {replica}/narrow: fresh review of frozen generations",flush=True)
            for g,champion in enumerate(search["champions"]):
                capture(g,champion)
        else:
            print(f"Starting {replica}/wide: captured 16-world search",flush=True)
            search = mixed.search(sub,sub/"search",timings[arm],capture,study=s,objective=OBJECTIVE)
            print(f"Starting {replica}/wide: capture-disabled complete repeat",flush=True)
            repeat = mixed.search(sub,sub/"repeat",timings[arm],study=s,objective=OBJECTIVE)
            require(search == repeat, "capture changed wide search")
            experiment.write_json(sub/"repeat.json",repeat)
        rows = [[r["frames"][i] for r in reviews] for i in range(len(mixed.conditions(REVIEW,dict(previous.REVIEW_PATCHES))))]
        arms[arm] = {"rule": RULE, "study": s.record(), "objective": "renewal", "search": search, "review": reviews,
                     "diagnostics": mixed.diagnostics(search,reviews,study=s), "gallery": pilot.gallery.contact_sheet(sub,rows)}
        print(f"Finished {replica}/{arm}: {search['champions']}",flush=True)
    result = {"rule": RULE, "arms": arms, "diagnostics": diagnostics(root,arms,replica),
              "gallery": pilot.gallery.contact_sheet(root,frame_rows(arms))}
    check_replica(root,result,baseline,replica)
    timing = {"wall_seconds": time.monotonic()-begin, "arms": timings}
    experiment.write_json(root/"results.json",result)
    experiment.write_json(root/"timings.json",timing)
    return result,timing


def cross_replica(replicas):
    require(set(replicas) == set(REPLICAS), "missing/extra replica")
    original = replicas[REPLICAS[0]]["arms"]
    for r in replicas.values():
        for arm in ARMS:
            current = r["arms"][arm]
            require(current["search"]["candidates"][0]["worlds"] == original[arm]["search"]["candidates"][0]["worlds"] and
                    current["review"][0]["worlds"] == original["narrow"]["review"][0]["worlds"], "shared original differs")
    return {view: {"final_wide_vs_narrow_signs": {name:r["diagnostics"]["review_wide_vs_narrow"][-1][view]["overall"]["comparison"]
                                               for name,r in replicas.items()},
                   "final_vs_original_signs": {name:{arm:r["diagnostics"][arm][-1]["review_vs_original"][view]["overall"]["comparison"]
                                                    for arm in ARMS} for name,r in replicas.items()}}
            for view in scoring.ARMS}


def verify(root):
    manifest = experiment.read_json(root/"manifest.json")
    require(manifest["rule"] == RULE and manifest["status"] == "complete" and manifest["copied"] == copies(),
            "wrong/incomplete coverage bundle")
    for name in manifest["artifacts"]:
        pilot.gallery.artifact(root,manifest,name)
    require(experiment.digest(root/"input/replication-manifest.json") == BASELINE_SHA, "changed replication manifest")
    old = experiment.read_json(root/"input/replication-manifest.json")
    for dest,src in copies().items():
        require(experiment.digest(root/dest) == old["artifacts"][src], "changed frozen/reused input")
    require(experiment.read_json(root/"input/settings.json") == settings(), "changed frozen settings")
    result, timing = experiment.read_json(root/"results.json"), experiment.read_json(root/"timings.json")
    require(result["rule"] == RULE and result["settings"] == settings(), "wrong coverage contract")
    baseline = experiment.read_json(root/"input/replication-results.json")
    for replica in REPLICAS:
        sub = root/"replicas"/replica
        require(result["replicas"][replica] == experiment.read_json(sub/"results.json") and
                timing["replicas"][replica] == experiment.read_json(sub/"timings.json"), "replica records differ")
        check_replica(sub,result["replicas"][replica],baseline,replica)
    require(result["cross_replica"] == cross_replica(result["replicas"]), "changed cross-replica analysis")
    check_budget(timing,result)
    print("Verified 2,084 new calls, two reused narrow searches, two complete wide repeats and 256 repeated frames",flush=True)
    return result


def collect(baseline, output):
    require(not output.exists() and output.is_relative_to(experiment.ROOT/"artifacts") and not output.is_relative_to(baseline),
            "choose fresh separate artifacts output")
    require(experiment.digest(baseline/"manifest.json") == BASELINE_SHA, "wrong replication input")
    original = previous.verify(baseline)
    prior, sources = experiment.read_json(baseline/"manifest.json"), experiment.source_files()
    require(all(sources.get(n) == sha for n,sha in prior["sources"].items() if n.startswith("src/") and n.endswith((".c",".h"))),
            "simulation core changed")
    output.mkdir(parents=True)
    experiment.snapshot_sources(output,sources)
    for replica in REPLICAS:
        for arm in ARMS:
            for folder in ("input","bin","review"):
                (output/subpath(replica,arm)/folder).mkdir(parents=True)
    (output/"input").mkdir()
    for dest,src in copies().items():
        (output/dest).parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(baseline/src,output/dest)
        require(experiment.digest(output/dest) == prior["artifacts"][src], "input copy differs")
    shutil.copy2(baseline/"manifest.json",output/"input/replication-manifest.json")
    shutil.copy2(experiment.ROOT/PROTOCOL,output/"input/protocol.md")
    experiment.write_json(output/"input/settings.json",settings())
    frozen = {n:experiment.digest(output/n) for n in (*copies(),"input/replication-manifest.json","input/protocol.md","input/settings.json")}
    experiment.write_json(output/"started.json",{"rule":RULE,"sources":sources,"frozen":frozen})
    begin = time.monotonic()
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = {r:executor.submit(collect_replica,output/"replicas"/r,r,original) for r in REPLICAS}
            completed = {r:futures[r].result() for r in REPLICAS}
        replicas = {r:completed[r][0] for r in REPLICAS}
        result = {"rule":RULE,"settings":settings(),"replicas":replicas,"cross_replica":cross_replica(replicas)}
        timing = {"wall_seconds":time.monotonic()-begin,"command_root":str(output),"replicas":{r:completed[r][1] for r in REPLICAS}}
        check_budget(timing,result)
        require(experiment.source_files() == sources and all(experiment.digest(output/n) == sha for n,sha in frozen.items()),
                "source/input changed during collection")
        experiment.write_json(output/"results.json",result)
        experiment.write_json(output/"timings.json",timing)
        artifacts = {str(p.relative_to(output)):experiment.digest(p) for p in output.rglob("*") if p.is_file()}
        experiment.write_json(output/"manifest.json",{"rule":RULE,"status":"complete","sources":sources,"copied":copies(),
            "artifacts":artifacts,"artifact_bytes":sum((output/n).stat().st_size for n in artifacts)})
    except BaseException as error:
        experiment.write_json(output/"failure.json",{"error":str(error)})
        raise
    verify(output)


def portable(root, result):
    replicas = {}
    for replica in REPLICAS:
        r = result["replicas"][replica]
        searches = {}
        for arm in ARMS:
            search, s = r["arms"][arm]["search"], study(replica,arm)
            searches[arm] = {**search,"candidates":[{k:v for k,v in c.items() if k != "worlds"} |
                {"worlds":scoring.compact_worlds(c["worlds"]), "score_views":views(c["worlds"],s.development,s.development_patches)}
                for c in search["candidates"]]}
        replicas[replica] = {"searches":searches,"diagnostics":r["diagnostics"],"frames":frame_rows(r["arms"]),
                             "narrow_reused":True,"wide_repeat_equal":True}
    return {"rule":RULE,"settings":settings(),"replicas":replicas,"cross_replica":result["cross_replica"],
            "manifest_sha256":experiment.digest(root/"manifest.json"),"timing":experiment.read_json(root/"timings.json")}


def export(root, prefix, check=False):
    result = verify(root)
    require(not prefix.is_relative_to(root), "cannot export into frozen bundle")
    summary,gallery,frames = (prefix.with_name(prefix.name+s) for s in ("-summary.json","-gallery.md","-frames"))
    sheets = {r:prefix.with_name(f"{prefix.name}-{r}.png") for r in REPLICAS}
    expected = portable(root,result)
    lines = ["# Bounded-renewal world coverage: all review generations","",
             "Each sheet: columns **N0, N1, N2, N3, W0, W1, W2, W3**, all at day 192.",
             "N/W train on 8/16 worlds using the same bounded-renewal selector and mutation budget.",
             "N searches are reused; all fresh review captures are new. Review never selects parents.","",
             "| Row | Schedule | World seed |","|---:|---|---|"]
    for i,(_,label,seed,_) in enumerate(mixed.conditions(REVIEW,dict(previous.REVIEW_PATCHES)),1):
        lines.append(f"| {i} | {label} | `{seed}` |")
    images = {}
    for replica in REPLICAS:
        lines += ["",f"## {replica.upper()} — mutation seed `{study(replica,'wide').rng:08x}`","",
                  f"![All 128 {replica} frames]({sheets[replica].name})","",
                  "| Frame | Model CRC | Living | World hash | Framebuffer CRC |","|---|---|---:|---|---|"]
        for row in expected["replicas"][replica]["frames"]:
            for f in row:
                name = f"{replica}.{f['id']}.png"
                world = result["replicas"][replica]["arms"][f["arm"]]["review"][f["generation"]]["worlds"][f["condition"]]
                lines.append(f"| [{replica}.{f['id']}]({frames.name}/{name}) | `{f['model_crc32']}` | {world['final']['living']} | `{f['hash']}` | `{f['framebuffer_crc32']}` |")
                images[frames/name] = root/"replicas"/replica/f["png"]
        images[sheets[replica]] = root/"replicas"/replica/"contact-sheet.png"
    lines += ["","All 256 images match ledger endpoints, independently repeated pixels and PNG conversions.",
              "Images alone do not establish reproduction, coexistence or generalization.",
              "See the [report](renewal-coverage.md) and [paired data](renewal-coverage-summary.json).","",
              f"Manifest SHA-256: `{expected['manifest_sha256']}`.",""]
    content = "\n".join(lines)
    if not check:
        require(not any(p.exists() for p in (summary,gallery,frames,*sheets.values())), "export exists")
        frames.mkdir(parents=True)
        experiment.write_json(summary,expected)
        with gallery.open("x") as stream:
            stream.write(content)
        for dest,src in images.items():
            shutil.copyfile(src,dest)
    require(experiment.read_json(summary) == expected and gallery.read_text() == content, "portable analysis differs")
    require(all(experiment.digest(dest) == experiment.digest(src) for dest,src in images.items()), "portable image differs")
    print("Portable coverage summaries, both contact sheets and all 256 PNGs match verified evidence",flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline",type=Path,default=experiment.ROOT/"artifacts/garden-renewal-replication-v1")
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--verify",action="store_true")
    parser.add_argument("--export",type=Path)
    parser.add_argument("--check-export",type=Path)
    args = parser.parse_args()
    require(not (args.export and args.check_export) and (args.verify or not (args.export or args.check_export)), "export requires verify")
    if args.export or args.check_export:
        export(args.output.resolve(),(args.export or args.check_export).resolve(),bool(args.check_export))
    elif args.verify:
        verify(args.output.resolve())
    else:
        collect(args.baseline.resolve(),args.output.resolve())


if __name__ == "__main__":
    main()
