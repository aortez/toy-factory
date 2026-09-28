#!/usr/bin/env python3
"""Export portable recruitment evidence or recheck every exact receipt offline."""

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

from garden_season_recruitment import analyze, capture, digest, identity
from garden_seasons import DAY_TICKS, require


def portable_reference(case: dict) -> dict:
    return {**{k: case[k] for k in ("mode", "scenario", "policy", "seed", "plants", "closing_lifetimes")},
            "daily": [{k: row[k] for k in ("hash", "births", "deaths", "seeds_created", "seeds_expired")}
                      for row in case["daily"]]}


def check_trace(stream, case: dict, saved: dict) -> None:
    checksum = hashlib.sha256()

    def lines():
        for line in stream:
            checksum.update(line.encode())
            yield line

    actual = analyze(iter(lines()), case, 16 * DAY_TICKS, 112 * DAY_TICKS, 128 * DAY_TICKS)
    require(checksum.hexdigest() == saved["trace_sha256"], "Changed trace bytes")
    # Normalize JSON's string object keys, including numeric mask histograms.
    actual = json.loads(json.dumps(actual))
    require(actual == {k: saved[k] for k in actual}, "Changed receipt analysis")


def verify(evidence: dict, raw: Path | None = None, build: Path | None = None) -> None:
    require(evidence["protocol"] == "seasonal-recruitment-evidence-v1", "Wrong evidence format")
    audit = evidence["audit"]
    refs = {identity(c): c for c in evidence["references"]}
    require(len(refs) == len(audit["cases"]) == 32 and set(refs) == {identity(c) for c in audit["cases"]},
            "Incomplete/duplicate portable panel")
    for saved in audit["cases"]:
        case = refs[identity(saved)]
        if raw is not None:
            with gzip.open(raw / saved["trace"], "rt") as stream:
                check_trace(stream, case, saved)
            if identity(saved) in audit["repeated"]:
                with gzip.open(raw / "repeats" / saved["trace"], "rt") as stream:
                    check_trace(stream, case, saved)
        if build is not None:
            with tempfile.TemporaryDirectory() as temporary:
                replay = capture(build.resolve() / "toy-factory-garden-recruitment-audit",
                                 Path(temporary), case, 128 * DAY_TICKS)
                require(replay["trace_sha256"] == saved["trace_sha256"], "Native replay diverged")
                with gzip.open(Path(temporary) / replay["trace"], "rt") as stream:
                    check_trace(stream, case, saved)
    print("Verified all 32 portable references, receipt analyses and requested repeats/replays")


def export(panel_path: Path, raw: Path, wide: Path, output: Path) -> None:
    parent = json.loads(panel_path.read_text())
    audit = json.loads((raw / "summary.json").read_text())
    treatment = json.loads((wide / "results.json").read_text())
    require(digest(panel_path) == audit["parent_sha256"] == treatment["parent_sha256"],
            "Unmatched original panel")
    controls = [c for c in parent["cases"] if c["mode"] in ("steady", "seasonal")]
    from garden_season_dispersal import screen
    require(screen(controls, treatment["cases"]) == treatment["screen"], "Changed treatment screen")
    evidence = {"protocol": "seasonal-recruitment-evidence-v1", "exporter_sha256": digest(Path(__file__)),
                "audit_input_sha256": digest(raw / "summary.json"),
                "treatment_input_sha256": digest(wide / "results.json"),
                "audit": audit, "references": [portable_reference(c) for c in controls],
                "wide": {k: v for k, v in treatment.items() if k != "cases"}}
    evidence["wide"]["cases"] = [
        {**{k: c[k] for k in ("mode", "scenario", "policy", "seed", "environment", "trace_sha256",
                              "lifetimes", "closing_lifetimes", "closing_births", "empty_day", "seed_audit")},
         "daily_hashes": [r["hash"] for r in c["daily"]], "final": c["daily"][-1],
         "deaths": len(c["deaths"])} for c in treatment["cases"]]
    verify(evidence, raw=raw)
    require(not output.exists(), "Refusing to overwrite evidence")
    destinations = []
    for prefix, bundle, report in (("recruitment", raw, audit), ("wide", wide, treatment)):
        for frame in report["frames"]:
            source = bundle / frame["png"]
            require(digest(source) == frame["png_sha256"], "Changed captured image")
            target = output.parent / "frames" / (prefix + "-" + source.name)
            require(not target.exists(), "Refusing to overwrite frame")
            destinations.append((source, target))
    output.parent.mkdir(parents=True, exist_ok=True)
    for source, target in destinations:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    # Frame paths inside the native reports describe the original bundles.
    evidence["published_frames"] = [str(target.relative_to(output.parent)) for _, target in destinations]
    output.write_text(json.dumps(evidence, indent=2) + "\n")
    print(f"Exported {output} (sha256 {digest(output)})")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    write = commands.add_parser("export")
    for option in ("panel", "raw", "wide", "out"):
        write.add_argument("--" + option, type=Path, required=True)
    read = commands.add_parser("verify")
    read.add_argument("--summary", type=Path, required=True)
    read.add_argument("--raw", type=Path, help="Reanalyze retained compressed receipts without native calls")
    read.add_argument("--build", type=Path, help="Recreate all 32 exact traces using the portable references")
    args = parser.parse_args()
    if args.command == "export":
        export(args.panel, args.raw, args.wide, args.out)
    else:
        if args.raw is None and args.build is None:
            parser.error("Verification requires --raw and/or --build")
        verify(json.loads(args.summary.read_text()), args.raw, args.build)


if __name__ == "__main__":
    main()
