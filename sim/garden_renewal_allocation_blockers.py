#!/usr/bin/env python3
"""Offline allocation-only evidence from the frozen fractional-canopy A/B."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
from pathlib import Path
import tarfile

import garden_renewal_canopy_transmission as parent

experiment, gap, require = parent.experiment, parent.gap, parent.require
RULE = "garden-renewal-allocation-blockers-v1"
PROTOCOL = "benchmarks/garden-longevity/renewal-allocation-blockers-protocol.md"
BASELINE_SHA = "ea243a36dccd49eda1db5cbfc30956ebf281e81013fec5a4adc8e69bc7212b69"
PORTABLE = "benchmarks/garden-longevity/renewal-canopy-transmission-summary.json"
PORTABLE_SHA = "ad7c804d94fb9ac687a7d0c5175982579ba2b118336f425b1316fb3a857ccc60"
AFTER, STOP, LATE, STEP = parent.AFTER, parent.STOP, parent.LATE, 15
WINDOWS = {"after": AFTER, "late": LATE}
SPECIES = ("flower", "shrub", "ground-cover")
COUNTS = ("retained_samples", "dormant_samples", "mature_samples", "plant_only",
          "plant_with_other", "no_plant_gate", "stable_full", "stable_spacing",
          "full_with_dead", "confirmed_plant_only", "birth_step_plant_only",
          "confirmed_all_live", "confirmed_with_dead")
REGISTRATION = ('\nadd_test(NAME garden-renewal-allocation-blockers-unit\n'
                '\tCOMMAND ${Python3_EXECUTABLE} -W error\n'
                '\t\t${CMAKE_CURRENT_LIST_DIR}/test_garden_renewal_allocation_blockers.py)\n')
REGISTRATION_ANCHOR = '\nadd_test(NAME garden-root-bootstrap-audit COMMAND ${Python3_EXECUTABLE}'


def seed_key(seed):
    return seed["parent"], seed["birth_tick"]


def empty_stats():
    return {"counts": dict.fromkeys(COUNTS, 0), "masks": Counter(),
            "confirmed_runs": [], "first_confirmed": None, "last_confirmed": None}


def validate_sites(row, records, previous_births):
    tick = row["tick"]
    require(type(tick) is int and tick >= 0 and tick % STEP == 0 and
            row["type"] == "seed-sites", "invalid site checkpoint")
    plants, sites, nodes = row["plants"], row["sites"], row["nodes"]
    require(len(sites) == 28 and len(plants) <= 8 and type(nodes) is int and 0 <= nodes <= 512 and
            len({p["id"] for p in plants}) == len(plants), "invalid allocation inventory")
    spacing = 2 if tick > AFTER else 3
    wet = row.get("germination_rule") == "wet-germination-v1"
    require(tick <= AFTER or wet, "post-boundary light gate unexpectedly enabled")
    newborns = []
    for p in plants:
        r = records[p["id"]]
        # The canonical export-tick census is before removal. The lifetime's
        # death_tick marks that exit, not a dead occupant consuming a slot.
        removal = r.get("removal_tick")
        dead = removal is None and r["death_tick"] is not None and r["death_tick"] <= tick
        require(type(p["column"]) is int and 0 <= p["column"] < 28 and type(p["dead"]) is bool and
                all(p[k] == r[k] for k in ("id", "parent", "column", "generation")) and
                type(p["species"]) is int and 0 <= p["species"] < len(SPECIES) and
                SPECIES[p["species"]] == r["species"] and r["birth_tick"] <= tick and
                (removal is None or tick <= removal == r["death_tick"]) and p["dead"] == dead,
                "site occupant differs from frozen lineage")
        if p["parent"] and r["birth_tick"] == tick:
            newborns.append(p["id"])
    require(row["births"]-previous_births == len(newborns), "birth counter/newborn inventory mismatch")
    for column, values in enumerate(sites):
        require(len(values) == 3 and all(type(v) is int for v in values), "invalid site tuple")
        mask, moisture, light = values
        require(0 <= mask < 64 and 0 <= moisture <= 255 and 0 <= light <= 255, "site values out of range")
        expected = (2*int(moisture < 12) | 4*int(not wet and light < 80) |
                    8*int(len(plants) == 8) | 16*int(nodes+4 > 512) |
                    32*int(any(abs(p["column"]-column) < spacing for p in plants)))
        require(mask == expected, "site gates disagree with inventory/resources")
    return {"newborns": newborns, "spacing": spacing, "wet": wet,
            "stable": [p for p in plants if records[p["id"]]["birth_tick"] < tick]}


def aligned_bank(row, active, records):
    require(len(row["seeds"]) == len(active) <= 8 and len({seed_key(s) for s in active}) == len(active),
            "missing/duplicate retained seed")
    for observed, seed in zip(row["seeds"], active, strict=True):
        age = observed["age"]
        require(type(age) is int and 0 <= age < 256 and
                row["tick"]-age*STEP == seed["birth_tick"] and
                all(observed[k] == seed[k] for k in ("parent", "column", "generation")) and
                observed["generation"] == records[seed["parent"]]["generation"]+1 and
                type(observed["species"]) is int and 0 <= observed["species"] < len(SPECIES) and
                SPECIES[observed["species"]] == seed["species"] == records[seed["parent"]]["species"],
                "seed age/identity/order differs from ledger")
        require(type(observed["blockers"]) is int and observed["blockers"] ==
                (row["sites"][observed["column"]][0] | int(age < 8)), "seed/site masks differ")


def witness(row, observed, context):
    """Post-step evidence plus a narrowly justified, no-birth code-order inference."""
    require(row["tick"] > AFTER and context["wet"], "witness outside fixed wet-germination scope")
    mask, column = observed["blockers"], observed["column"]
    stable = context["stable"]
    occupants = [p["id"] for p in stable if abs(p["column"]-column) < context["spacing"]]
    dead = [p["id"] for p in row["plants"] if p["dead"]]
    confirmed = observed["age"] >= 8 and mask == 8 and not context["newborns"] and len(stable) == 8
    if confirmed:
        require(row["sites"][column][1] >= 12 and row["nodes"]+4 <= 512 and not occupants,
                "exclusive allocation inference lacks gate witnesses")
    return {"tick": row["tick"], "age": observed["age"], "column": column, "mask": mask,
            "post_moisture": row["sites"][column][1], "post_light": row["sites"][column][2],
            "post_nodes": row["nodes"], "post_plant_slots": len(row["plants"]),
            "stable_occupants": [p["id"] for p in stable], "stable_spacing_occupants": occupants,
            "dead_occupants": dead, "newborns": context["newborns"],
            "confirmed_plant_only": confirmed}


def observe(stats, point):
    counts = stats["counts"]
    counts["retained_samples"] += 1
    if point["age"] < 8:
        counts["dormant_samples"] += 1
        return
    mask = point["mask"]
    counts["mature_samples"] += 1
    stats["masks"][str(mask)] += 1
    counts["plant_only" if mask == 8 else "plant_with_other" if mask & 8 else "no_plant_gate"] += 1
    counts["stable_full"] += len(point["stable_occupants"]) == 8
    counts["stable_spacing"] += bool(point["stable_spacing_occupants"])
    counts["full_with_dead"] += bool(mask & 8 and point["dead_occupants"])
    if mask == 8 and not point["confirmed_plant_only"]:
        require(bool(point["newborns"]), "unexplained unconfirmed plant-only mask")
        counts["birth_step_plant_only"] += 1
    if point["confirmed_plant_only"]:
        counts["confirmed_plant_only"] += 1
        counts["confirmed_with_dead" if point["dead_occupants"] else "confirmed_all_live"] += 1
        stats["first_confirmed"] = stats["first_confirmed"] or point
        stats["last_confirmed"] = point
        runs, tick = stats["confirmed_runs"], point["tick"]
        if runs and runs[-1]["last_tick"]+STEP == tick:
            runs[-1]["last_tick"] = tick
            runs[-1]["samples"] += 1
        else:
            runs.append({"first_tick": tick, "last_tick": tick, "samples": 1})


def check_stats(stats):
    c = stats["counts"]
    require(c["retained_samples"] == c["dormant_samples"]+c["mature_samples"] and
            c["mature_samples"] == sum(stats["masks"].values()) ==
            c["plant_only"]+c["plant_with_other"]+c["no_plant_gate"] and
            c["plant_only"] == c["confirmed_plant_only"]+c["birth_step_plant_only"] and
            c["confirmed_plant_only"] == c["confirmed_all_live"]+c["confirmed_with_dead"] ==
            sum(r["samples"] for r in stats["confirmed_runs"]), "inconsistent observation partition")


def check_lifetime(seed, samples, masks):
    birth, end, outcome = seed["birth_tick"], seed["end_tick"], seed["outcome"]
    require(type(birth) is int and birth >= 0 and birth % STEP == 0 and birth <= STOP, "bad seed birth")
    if outcome == "pending":
        require(end is None and seed["child_id"] is None and STOP-birth < 256*STEP, "bad pending censoring")
        last = STOP
    else:
        require(type(end) is int and birth < end <= STOP and end % STEP == 0, "bad seed terminal time")
        age = (end-birth)//STEP
        require((outcome == "expired" and age == 256 and seed["child_id"] is None) or
                (outcome == "germinated" and 8 <= age < 256 and seed["child_id"] is not None), "bad seed outcome")
        last = end-STEP  # No post-step sample for a seed removed by the loop.
    require(samples == (last-birth)//STEP+1 and sum(masks.values()) == max(0, (last-birth)//STEP-7) and
            sum(masks.values()) == seed["mature_snapshots"] and masks == seed["mature_blockers"],
            "retained seed lifetime coverage differs from parent")


def summary(seeds, window):
    counts, masks = Counter(), Counter()
    for s in seeds:
        value = s["windows"][window]
        check_stats(value)
        counts.update(value["counts"])
        masks.update(value["masks"])
    observed = [s for s in seeds if s["windows"][window]["counts"]["mature_samples"]]
    only = [s for s in seeds if s["windows"][window]["counts"]["plant_only"]]
    confirmed = [s for s in seeds if s["windows"][window]["counts"]["confirmed_plant_only"]]
    purchased = [s for s in seeds if s["seed"]["birth_tick"] > WINDOWS[window]]
    points = [s["windows"][window]["first_confirmed"] for s in confirmed]
    return {"counts": counts, "mature_masks": masks, "distinct_mature_seeds": len(observed),
            "distinct_post_plant_only": len(only), "distinct_confirmed_plant_only": len(confirmed),
            "confirmed_seed_outcomes": dict(Counter(s["seed"]["outcome"] for s in confirmed)),
            "confirmed_parent_ids": sorted({s["seed"]["parent"] for s in confirmed}),
            "confirmed_landing_columns": sorted({s["seed"]["column"] for s in confirmed}),
            "first_confirmed_tick": min((p["tick"] for p in points), default=None),
            "purchase_cohort": {"purchases": len(purchased),
                "outcomes": dict(Counter(s["seed"]["outcome"] for s in purchased))}}


def analyze_case(root, arm, saved):
    split = parent.order.parent.parent.parent.split_census
    rows, _, _ = split(gap.read_trace(root/f"traces/{arm}.sites.jsonl.gz"), "optional", "seed-sites")
    records = {p["id"]: p for p in saved["lineages"]}
    seeds = saved["seeds"]
    lookup = {seed_key(s): {"seed": {k: s[k] for k in ("parent", "birth_tick", "column", "generation",
                         "species", "outcome", "end_tick", "child_id")},
                         "windows": {w: empty_stats() for w in WINDOWS}} for s in seeds}
    require(len(lookup) == len(seeds), "duplicate lifetime key")
    births, sample_counts, lifetime_masks = defaultdict(list), Counter(), defaultdict(Counter)
    for s in seeds:
        births[s["birth_tick"]].append(s)
    site_stats = {w: {"checkpoints": 0, "hypothetical_column_samples": 0, "masks": Counter(),
                     "plant_only_columns": 0, "plant_only_columns_with_mature_seed": 0,
                     "full_checkpoints": 0, "full_with_dead_checkpoints": 0} for w in WINDOWS}
    active, last, previous_births = [], -STEP, 0
    for row in rows:
        tick = row["tick"]
        require(tick == last+STEP and tick <= STOP, "incomplete/reordered site stream")
        parent.check_rule(row, arm)
        context = validate_sites(row, records, previous_births)
        active = [s for s in active if s["end_tick"] is None or s["end_tick"] > tick]
        active.extend(births[tick])
        aligned_bank(row, active, records)
        for native, s in zip(row["seeds"], active, strict=True):
            key = seed_key(s)
            sample_counts[key] += 1
            if native["age"] >= 8:
                lifetime_masks[key][str(native["blockers"])] += 1
            if tick > AFTER:
                point = witness(row, native, context)
                for window, begin in WINDOWS.items():
                    if tick > begin:
                        observe(lookup[key]["windows"][window], point)
        for window, begin in WINDOWS.items():
            if tick <= begin:
                continue
            stats = site_stats[window]
            ready_columns = {s["column"] for s in row["seeds"] if s["age"] >= 8}
            stats["checkpoints"] += 1
            stats["hypothetical_column_samples"] += 28
            stats["masks"].update(str(s[0]) for s in row["sites"])
            only = {c for c, site in enumerate(row["sites"]) if site[0] == 8}
            stats["plant_only_columns"] += len(only)
            stats["plant_only_columns_with_mature_seed"] += len(only & ready_columns)
            stats["full_checkpoints"] += len(row["plants"]) == 8
            stats["full_with_dead_checkpoints"] += len(row["plants"]) == 8 and any(p["dead"] for p in row["plants"])
        last, previous_births = tick, row["births"]
    require(last == STOP and len(rows) == saved["site_checkpoints"], "truncated parent sites")
    for s in seeds:
        check_lifetime(s, sample_counts[seed_key(s)], lifetime_masks[seed_key(s)])
    details = list(lookup.values())
    windows = {w: {"seeds": summary(details, w), "sites": site_stats[w]} for w in WINDOWS}
    for w in WINDOWS:
        require(site_stats[w]["full_checkpoints"] == saved["sites"]["windows"][w]["plant_full"] and
                site_stats[w]["checkpoints"] == (STOP-WINDOWS[w])//STEP and
                sum(site_stats[w]["masks"].values()) == site_stats[w]["hypothetical_column_samples"],
                "parent site totals differ")
    parents = {}
    for identity in sorted({s["parent"] for s in seeds}):
        selected = [s for s in details if s["seed"]["parent"] == identity]
        parents[str(identity)] = {"lineage": records[identity], "post_boundary_born": records[identity]["birth_tick"] > AFTER,
                                  "windows": {w: summary(selected, w) for w in WINDOWS}}
    print("Audited saved allocation blockers:", arm, flush=True)
    return {"seed_lifetimes": len(seeds), "all_retained_samples": sum(sample_counts.values()),
            "all_mature_samples": sum(sum(v.values()) for v in lifetime_masks.values()),
            "windows": windows, "parents": parents, "seeds": details,
            "context": {"final": saved["outcomes"]["final"], "new_cohort": saved["new_cohort"]}}


def analyze(root, saved):
    return {"rule": RULE, "baseline_manifest_sha256": BASELINE_SHA, "baseline_portable_sha256": PORTABLE_SHA,
            "experimental_native_calls": 0, "training_calls": 0, "frames_reused": len(saved["frames"]),
            "stop": STOP, "windows_exclusive_start": WINDOWS,
            "cases": {a: analyze_case(root, a, saved["cases"][a]) for a in parent.ARMS},
            "limits": ["Repeated retained-seed samples are not independent germination opportunities.",
                       "Removed germinations/expiries have no post-step seed observation.",
                       "Confirmed means a code-order inference in no-birth steps, not a new native attempt trace.",
                       "Extra slots would alter sequential admission, moisture, spacing and competition.",
                       "No counterfactual birth, survival or broad environment qualification is claimed."]}


def analysis_sources():
    paths = sorted((experiment.ROOT/"sim").glob("*.py"))+[experiment.ROOT/PROTOCOL, experiment.ROOT/"sim/CMakeLists.txt"]
    return {str(p.relative_to(experiment.ROOT)): experiment.digest(p) for p in paths}


def check_build_registration(original, current, sha):
    anchor = REGISTRATION_ANCHOR.encode()
    require(hashlib.sha256(original).hexdigest() == sha and original.count(anchor) == 1 and
            current == original.replace(anchor, REGISTRATION.encode()+anchor), "unexpected historical CMake change")


def check_parent(root):
    gap.parent.shadow.check_frozen(root, BASELINE_SHA)
    require(experiment.digest(experiment.ROOT/PORTABLE) == PORTABLE_SHA, "portable parent changed")
    with tarfile.open(root/"source.tar.gz") as archive:
        original = archive.extractfile("sim/CMakeLists.txt").read()
    for name, sha in experiment.read_json(root/"analysis-sources.json").items():
        if name == "sim/CMakeLists.txt":
            check_build_registration(original, (experiment.ROOT/name).read_bytes(), sha)
        else:
            require(experiment.digest(experiment.ROOT/name) == sha, "historical analysis dependency changed: "+name)
    native = parent.native.native_hashes(root/"source.tar.gz")
    require(all(experiment.digest(experiment.ROOT/n) == sha for n, sha in native.items()), "native source changed")
    capture = parent.check_capture(root)
    require(experiment.read_json(root/"timings.json")["calls"] == capture["calls"], "capture timings changed")
    saved = experiment.read_json(root/"results.json")
    require(saved == parent.analyze(root), "historical analysis differs")
    require(experiment.read_json(experiment.ROOT/PORTABLE) == {**saved, "manifest_sha256": BASELINE_SHA,
            "full_results_sha256": experiment.digest(root/"results.json"),
            "timing": experiment.read_json(root/"timings.json")}, "portable parent differs")
    prefix = experiment.ROOT/PORTABLE.removesuffix("-summary.json")
    require(experiment.digest(prefix.with_suffix(".png")) == experiment.digest(root/"contact-sheet.png"), "overview changed")
    for frame in saved["frames"]:
        require(experiment.digest(prefix.with_name(prefix.name+"-frames")/(frame["id"]+".png")) ==
                experiment.digest(root/frame["png"]), "parent frame changed")
    return saved, native


def verify(root):
    sources = analysis_sources()
    saved, native = check_parent(root)
    result = analyze(root, saved)
    require(result == analyze(root, saved), "repeated allocation audit differs")
    require(sources == analysis_sources() and all(experiment.digest(experiment.ROOT/n) == sha for n, sha in native.items()),
            "analysis/native source changed")
    gap.parent.shadow.check_frozen(root, BASELINE_SHA)
    require(experiment.digest(experiment.ROOT/PORTABLE) == PORTABLE_SHA, "portable changed during audit")
    return {**result, "analysis_sources": sources, "native_sources": native}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, default=experiment.ROOT/"artifacts/garden-renewal-canopy-transmission-v1")
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--output", type=Path)
    target.add_argument("--check", type=Path)
    args = parser.parse_args()
    root = args.baseline.resolve()
    if args.output:
        require(not args.output.exists() and not args.output.resolve().is_relative_to(root), "choose fresh output outside parent")
    result = verify(root)
    if args.output:
        experiment.write_json(args.output, result)
    else:
        require(experiment.read_json(args.check) == result, "portable allocation audit differs")
    print("Verified allocation-only audit; zero new experimental native calls", flush=True)


if __name__ == "__main__":
    main()
