# Multi-seed landing training

The [frozen protocol](../benchmarks/garden-seasons/landing-multiseed-protocol.md)
tests training breadth, retaining matched live/fixed added-input profiles.
Five training seeds replace one; architecture, objective, initializer and the
42-candidate budget stay unchanged. Training-world cost is five times higher.
Six old single-seed finalists and six new finalists share four fresh evaluation
seeds. Review images and evaluation results cannot select a winner.
The [completed report](../benchmarks/garden-seasons/landing-multiseed.md) includes
all comparisons, portable model/ledger archives, verification receipts and
generation contact sheets.

Run inside the existing builder, with ordinary research flags off:

```sh
make host-train-landing-multiseed
# Optional fresh output/build overrides:
make host-train-landing-multiseed \
  GARDEN_LANDING_MULTISEED_OUT=artifacts/garden-landing-multiseed-another \
  GARDEN_LANDING_MULTISEED_ARGS='--jobs 4 --build build-host'
```

The output must not exist. Keep all sources and the build unchanged throughout
collection; the collector freezes and checks sources, protocol, input archives,
native binary and build flags. One-worker/capture-free repetition must match
all 1,136 scored worlds and every model byte. Collection retains 72 review
frames in six contact sheets, including failures and unchanged champions.

Independently reproduce the complete frozen bundle, including the images:

```sh
docker compose run --rm -T firmware python3 \
  artifacts/garden-landing-multiseed-v1/sim/garden_landing_multiseed.py \
  --verify artifacts/garden-landing-multiseed-v1
```

The fixed-input profile lives in the experiment record, not the TGL2 file.
Do not replay those finalists as live and call it the same control. Likewise,
old/new training scores aggregate different world counts; use the shared fresh
evaluation for the breadth comparison. Nothing here promotes a model, changes
ecology or deploys firmware. Seeds are development evidence after inspection.
