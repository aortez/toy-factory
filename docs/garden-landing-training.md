# Landing-aware renewal training

Host-only development experiment, separate from the older endpoint-count trainer.
The [frozen protocol](../benchmarks/garden-seasons/landing-training-protocol.md)
defines the objective, model, worlds, mutation, splits and stopping rule. No
ecology, player or firmware defaults change.
The [completed pilot report](../benchmarks/garden-seasons/landing-training.md)
records promising current-only survival results alongside persistent renewal
gaps; it does not recommend promoting a controller.

The native landing command now supports:

```sh
make host-landing-garden ARGS="mutate parent.tgl child.tgl 0x6d697833 32 16"
make host-landing-garden ARGS="replay child.tgl rainfed 0xa9c30c1f --ticks 737280 --climate seasonal --ledger"
```

`mutate` takes legacy and extension mutation counts (0..4096 each; at least one
nonzero). It preserves masks/config/scales; the model and RNG are caller-owned
and unchanged on failure. Files are exclusive creates, never overwritten.
Legacy mutations retain their existing draw order and clipping. Extension
weights use the same bounded signed-byte perturbations, after the legacy draws.
Masked extension weights mutate too; disabling sensing does not skip RNG draws.

`--ledger` adds complete lineage lifetimes and seed purchases/outcomes to JSON.
Exact death and seed receipts are collected from the same authoritative step,
before compaction can hide them. The host ledger retains 4,096 lineages and
65,536 purchases; exhaustion aborts the trial, never silently truncates it.
Its memory is host-only, not a proposed device allocation. The world, cache,
policy decisions, ecology RNG and rendered pixels are unchanged by accounting.
Collector errors abort the trial; partial diagnostic appends are not reusable.

Scoring reuses the existing individual-minimum bounded-renewal Python modules
directly: four 32-day windows and two days of follow-up, stopping at day 192.
Plant/seed counts and lifetime totals remain diagnostics, not tie-breakers.
Pending seeds retain their real 32-day lifetime, including in the two-day
follow-up. Every seed, birth and death must reconcile before scoring.

## Run the pilot

```sh
make host-train-landing-garden \
  GARDEN_LANDING_TRAIN_OUT=artifacts/garden-landing-training-v1
```

The default input is the previously saved controller at
`artifacts/garden-seasonal-model-eval/models/candidate.tgm`. A fresh clone needs
that research artifact, or an identical copy supplied with
`GARDEN_LANDING_TRAIN_ARGS="--input /path/to/candidate.tgm"`.
Its SHA-256 is checked; a different controller needs a different protocol.
The [retained model archive](../benchmarks/garden-seasons/landing-training-models.json.gz)
also contains `initial.tgm` and all candidates as hex-encoded canonical file
bytes, so this input need not be lost with an ignored local artifacts directory.
The output directory must be new. Ordinary ecology is required; research
build flags are rejected. `--jobs 1..8` changes only independent world workers.

The run saves all 63 candidate evaluations, model files, parent/RNG receipts,
per-world histories and generation-selected champions. Separate review worlds
never select models. Seasonal review images cover both layouts at days 16 and
192 for generations 0/1/2, including failures: 108 frames. An entire second
search with one worker and no captures must match model bytes and every result.
No restart, extra sweep or adoption is automatic.

Open `search/report.md` in the completed output for the tables and galleries.
The manifest hashes frozen tools, binary, models, build flags, source snapshot
and artifacts. `FAILED.txt` marks incomplete collection. A snapshot records the
source at collection; it is not proof the binary was compiled from that source.
Use a freshly built binary, and do not edit sources or rebuild during collection.

To independently rerun a **trusted local** bundle (this executes its binary):

```sh
docker compose run --rm -T firmware python3 \
  artifacts/garden-landing-training-v1/sim/garden_landing_training.py \
  --verify artifacts/garden-landing-training-v1
```

Verification repeats mutation, selection, ledger scoring and every saved frame,
in addition to checking artifact hashes. These are development worlds, not an
unseen final test. Three search seeds and this small fixed budget can show
workflow correctness and suggest leads; they cannot establish broad superiority
of one input mode or qualify a controller for device use.
