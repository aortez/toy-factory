# Garden allocation challenge

This host-only diagnostic forks six **already inspected development cases** from
identical pre-birth worlds and follows a selected seedling for eight days. It
does not train, assign fitness, or deploy firmware. See the
[protocol](../benchmarks/garden-longevity/allocation-challenge-protocol.md) and
[results/screenshots](../benchmarks/garden-longevity/allocation-challenge.md).

## Run or review

The collector needs the local, frozen `artifacts/garden-root-bootstrap` bundle
with manifest SHA-256
`aaf2ebd117045b817822394126c196dae49c0f6f749d684f48003f00f01ab7e8`.
It verifies and freezes the reference model, exact case histories and build
configuration. These ignored experiment histories are **not included in a fresh
checkout**; the versioned report/summary/images are the portable review material.

Build both explicit experimental variants with the existing Docker builder:

```sh
for bank in 8 16; do
    large_bank=OFF
    if [ "$bank" = 16 ]; then large_bank=ON; fi
    docker compose run --rm firmware cmake -S sim \
        -B "artifacts/seed-reserve-build-on-$bank" -G Ninja \
        -DCMAKE_BUILD_TYPE= \
        -DTOY_FACTORY_SIMULATOR_SANITIZERS=ON \
        -DTOY_FACTORY_GARDEN_WIDE_DISPERSAL=ON \
        -DTOY_FACTORY_GARDEN_WATER_HEADROOM=ON \
        -DTOY_FACTORY_GARDEN_COMBINED_EXPERIMENT=ON \
        -DTOY_FACTORY_GARDEN_LARGE_POOL=ON \
        -DTOY_FACTORY_GARDEN_LEAF_MAINTENANCE=ON \
        -DTOY_FACTORY_GARDEN_BOTTOM_DRAINAGE=OFF \
        -DTOY_FACTORY_GARDEN_LARGE_SEED_BANK="$large_bank" \
        -DTOY_FACTORY_GARDEN_SEED_RESERVE=ON
    docker compose run --rm firmware cmake --build "artifacts/seed-reserve-build-on-$bank"
    docker compose run --rm firmware ctest \
        --test-dir "artifacts/seed-reserve-build-on-$bank" --output-on-failure
done

docker compose run --rm firmware python3 sim/garden_allocation.py \
    --output artifacts/garden-allocation-new
```

The ordinary `make host-build` deliberately restores default ecology and does
not expose this executable. No host compiler or Python dependencies are needed
when using Docker. Outputs must be new directories under `artifacts/`; existing
bundles/frames are never overwritten. Collection freezes binaries, models and
sources, so do not edit the repository while it runs. Two separate native
processes can collect cases concurrently; no renderer/world is shared.

Review a completed bundle without rerunning native simulation:

```sh
docker compose run --rm firmware python3 sim/garden_allocation.py \
    --verify artifacts/garden-allocation-v2

# Optional: also verify the telemetry-only rerun against the first bundle.
python3 benchmarks/garden-longevity/review-allocation-challenge.py \
    --previous-bundle artifacts/garden-allocation-v1
```

The reviewer checks saved artifacts, identity, reference continuations, milestone
frames, headless equivalence and recomputed target ledgers. The completed bundle
contains the projected reference windows and frozen executables, so ordinary
review does not require the large original traces. `result.json` in each case
records exact native commands for a new execution. For native reruns, choose a
new frame directory (or `-` for headless) instead of the populated recorded path.
To rebuild the frozen revision, extract `source.tar.gz` into a separate
worktree/location; do not overwrite the current source tree.

## Evaluate a saved model

```sh
docker compose run --rm firmware python3 sim/garden_allocation.py \
    --candidate-model artifacts/my-candidate.tgm \
    --output artifacts/my-candidate-allocation
```

The same six checkpoints and three controls are retained. The fourth arm uses
the candidate model for the selected seedling only, from its first decision.
It keeps the case's night/energy guard and ordinary selective leaf maintenance,
but **does not apply the early-root bootstrap to the candidate**. With no
`--candidate-model`, it loads the frozen model in that slot as a routing control.
Neural observations/features/actions and recurrent memory ABI are unchanged.

These are explicitly development cases, not a `validation`/`test` split. A model
picked by looking at them has been selected on them. Changing the global policy
from reset would change ancestors and neighbors and is a different evaluation;
children also do not inherit this harness's candidate assignment.

## Evidence layout

- `summary.json`: per-case outcome vector; no scalar fitness or ranking.
- `<case>/result.json`: first future dawn/day-one/day-eight reserves, live
  resource budgets, action counts, natural/patch deaths, seeds and actual child
  germinations, recorded commands and frame metadata.
- `<case>/trace.jsonl`, `headless.jsonl`: full continuation world hashes and
  selected-plant telemetry. Explicit birth census survives parent reclamation.
- `<case>/<arm>.<birth|dawn|day1|day8>.png` and `.rgb565`: native screenshots.
- `contact-sheet.png`, `frames.json`: six-row day-one comparison; columns are
  reference, wet-root, WAIT and candidate, in that order.
- `input/`, `bin/`, `reference.tgm`, `candidate.tgm`, `manifest.json`: checked
  pre-birth/reference windows, build settings, frozen code/model provenance.

Patch death censors later natural-survival follow-up. Terminal death steps clear
income/stores, so their budget is `null`, not a fabricated debit. Seed purchases
are not germinated children; germinated children are not proven durable offspring.
Continuation after the parent's death still observes later direct child births.
Rendering is after ordinary ecology but before any same-tick patch; milestone
ledger values are post-patch when both happen at the same tick.

## Objective dry-run

The [offline objective comparison](../benchmarks/garden-longevity/allocation-objectives.md)
reads the frozen challenge and tests survival, raw-seed and confirmed-productive-
day formulas. It neither runs new worlds nor trains. The report includes fixed
weight sensitivities, leave-one-case-out rankings and synthetic arithmetic
counterexamples; no score is promoted to the trainer. It also explains why a
zero-shortage confirmation gate is not recommended.

The [survival-confirmed follow-up](../benchmarks/garden-longevity/allocation-survival.md)
then changes only confirmation to a full additional day of parent survival.
Both productive cases beat WAIT individually; WAIT still wins overall. It also
quantifies the bonus's survival tradeoff and explains why these capped native
scores cannot distinguish delayed credit from raw seed counts. Run/review it
with `sim/garden_allocation_survival.py`; the original results remain unchanged.
