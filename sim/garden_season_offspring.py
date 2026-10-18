#!/usr/bin/env python3
"""Read-only offspring outcome audit of the frozen scattering confirmation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from garden_season_confirmation import DAYS, SEEDS, summarize
from garden_season_recruitment import digest, identity
from garden_seasons import DAY_TICKS, life_summary, require

INPUT_SHA256 = "2e6a1eb37d7eee860120f762c05f4c1b5e5f045b52cc942e229005aefaec6d7f"
RESOURCES = {3: "energy", 5: "water", 7: "both"}
SPECIES = ("flower", "ground-cover", "shrub")
END = DAYS * DAY_TICKS
METRICS = ("births", "eligible", "censored", "censored_dead", "first_day_deaths",
           "day_survivors", "no_child", "child_without_day_survivor", "durable_parents",
           "nondurable_alive", "nondurable_dead", "nondurable_with_young_child",
           "early_age_quarter", "early_age_half", "early_age_day") + tuple(
    f"early_{resource}_{weather}" for resource in RESOURCES.values()
    for weather in ("ordinary", "drought", "dim"))


def validate_history(case: dict) -> tuple[dict, dict]:
    plants = {p["id"]: p for p in case["plants"]}
    deaths = {d["id"]: d for d in case["deaths"]}
    require(len(plants) == len(case["plants"]) and len(deaths) == len(case["deaths"]),
            "Duplicate birth/death identity")
    require(set(deaths) == {p["id"] for p in plants.values() if p["death_tick"] is not None},
            "Missing/extra death event")
    for plant in plants.values():
        born, died, parent = plant["birth_tick"], plant["death_tick"], plant["parent"]
        require(0 <= born <= END and born % 15 == 0 and plant["species"] in SPECIES,
                "Invalid birth/species")
        if parent:
            require(parent in plants and plants[parent]["birth_tick"] < born and
                    plant["generation"] == plants[parent]["generation"] + 1 and
                    plant["family"] == plants[parent]["family"] and
                    plant["species"] == plants[parent]["species"], "Invalid parent history")
        else:
            require(born == 0 and plant["generation"] == 0 and plant["family"] == plant["id"],
                    "Invalid founder history")
        if died is not None:
            event = deaths[plant["id"]]
            require(born < died <= END and died % 60 == 0 and event["tick"] == died and
                    all(event[k] == v for k, v in plant.items()), "Changed death identity/timing")
            require(event["flags"] in RESOURCES, "Unknown terminal shortage flags")
            climate = event["climate"]
            day = died // DAY_TICKS
            daily = case["daily"][day]["climate"]
            following = case["daily"][min(day + 1, DAYS)]["climate"]
            # Seasonal light tapers within a day; use the event's actual value,
            # not the daily census value, when classifying its terminal weather.
            require({k: v for k, v in climate.items() if k not in ("light_percent", "cold")} ==
                    {k: v for k, v in daily.items() if k not in ("light_percent", "cold")},
                    "Death/daily climate disagreement")
            lower, upper = sorted((daily["light_percent"], following["light_percent"]))
            require(lower <= climate["light_percent"] <= upper and
                    climate["cold"] == (climate["light_percent"] < 65), "Invalid intra-day light/cold")
            require(not (climate["drought"] and climate["light_percent"] < 100),
                    "Overlapping hazard categories")
    return plants, deaths


def cohort(plants: dict, deaths: dict, start: int) -> dict:
    def survives(plant):
        boundary = plant["birth_tick"] + DAY_TICKS
        return boundary <= END and (plant["death_tick"] is None or plant["death_tick"] > boundary)

    children = {ident: [] for ident in plants}
    for plant in plants.values():
        if plant["parent"]:
            children[plant["parent"]].append(plant)
    species = {name: dict.fromkeys(METRICS, 0) for name in SPECIES}
    for plant in plants.values():
        if not plant["parent"] or plant["birth_tick"] < start:
            continue
        counts = species[plant["species"]]
        counts["births"] += 1
        if plant["birth_tick"] + DAY_TICKS > END:
            counts["censored"] += 1
            counts["censored_dead"] += plant["death_tick"] is not None
            continue
        counts["eligible"] += 1
        if not survives(plant):
            counts["first_day_deaths"] += 1
            age = plant["death_tick"] - plant["birth_tick"]
            bucket = "quarter" if age <= DAY_TICKS // 4 else "half" if age <= DAY_TICKS // 2 else "day"
            counts["early_age_" + bucket] += 1
            event = deaths[plant["id"]]
            climate = event["climate"]
            weather = "drought" if climate["drought"] else "dim" if climate["light_percent"] < 100 else "ordinary"
            counts[f"early_{RESOURCES[event['flags']]}_{weather}"] += 1
            continue
        counts["day_survivors"] += 1
        offspring = children[plant["id"]]
        if any(survives(child) for child in offspring):
            counts["durable_parents"] += 1
        else:
            counts["no_child" if not offspring else "child_without_day_survivor"] += 1
            counts["nondurable_alive" if plant["death_tick"] is None else "nondurable_dead"] += 1
            counts["nondurable_with_young_child"] += any(
                child["birth_tick"] + DAY_TICKS > END and child["death_tick"] is None
                for child in offspring)
    totals = sum_counts(list(species.values()))
    saved = life_summary(plants, END, start)
    require(totals["births"] == saved["births"] and totals["eligible"] == saved["eligible"] and
            totals["censored"] == saved["too_young"] and totals["day_survivors"] == saved["cycle_survivors"] and
            totals["durable_parents"] == saved["durable_parents"], "Changed cohort partition")
    return {"totals": totals, "species": species}


def sum_counts(items: list[dict]) -> dict:
    return {key: sum(item[key] for item in items) for key in METRICS}


def aggregate(cases: list[dict]) -> dict:
    return {"worlds": len(cases), "windows": {window: {
        "totals": sum_counts([case["windows"][window]["totals"] for case in cases]),
        "species": {species: sum_counts([case["windows"][window]["species"][species] for case in cases])
                    for species in SPECIES}} for window in ("whole", "closing")}}


def analyze(report: dict) -> dict:
    cases = {}
    for arm, entries in report["cases"].items():
        cases[arm] = []
        for case in entries:
            plants, deaths = validate_history(case)
            cases[arm].append({**{k: case[k] for k in ("mode", "scenario", "policy", "seed")},
                               "identity": identity(case), "windows": {
                                   "whole": cohort(plants, deaths, 0),
                                   "closing": cohort(plants, deaths, 112 * DAY_TICKS + 1)}})
    return {"cases": cases,
            "groups": {mode: {arm: aggregate([c for c in rows if c["mode"] == mode])
                              for arm, rows in cases.items()} for mode in ("steady", "seasonal")},
            "seasonal_partitions": {field: {value: {
                arm: aggregate([c for c in rows if c["mode"] == "seasonal" and c[field] == value])
                for arm, rows in cases.items()} for value in values}
                for field, values in (("scenario", ("rainfed", "rainfed-crowded")),
                                      ("policy", ("baseline", "adaptive")), ("seed", SEEDS))}}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("artifacts/garden-seasonal-wide-confirmation/results.json"))
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    require(digest(args.input) == INPUT_SHA256, "Changed frozen confirmation input")
    report = json.loads(args.input.read_text())
    compact = summarize(report)
    compact["full_report_sha256"] = INPUT_SHA256
    require(compact == json.loads((root / "benchmarks/garden-seasons/dispersal-confirmation-summary.json").read_text()),
            "Changed compact confirmation evidence")
    result = {"protocol": "seasonal-offspring-outcomes-v1", "input_sha256": INPUT_SHA256,
              "analyzer_sha256": digest(Path(__file__)),
              "protocol_sha256": digest(root / "benchmarks/garden-seasons/offspring-outcomes-protocol.md"),
              **analyze(report)}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x") as stream:
        stream.write(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result["groups"], indent=2))


if __name__ == "__main__":
    main()
