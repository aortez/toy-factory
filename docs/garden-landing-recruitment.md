# Matched germination and first-day resource trace

This host-only diagnostic replays twelve fixed old/new model/case combinations
from the saved evaluation panel. It adds no policy input or world state and
changes no ecology or scoring. The [protocol](../benchmarks/garden-seasons/landing-recruitment-trace-protocol.md)
fixes case selection, accounting and verification before collection.

The [completed report](../benchmarks/garden-seasons/landing-recruitment-trace.md)
documents persistent spacing blocks and separate energy/water establishment
failures, including successful controls and limits on causal interpretation.

```sh
make host-trace-landing-recruitment
# Every collection needs a fresh output directory:
make host-trace-landing-recruitment \
  GARDEN_LANDING_RECRUITMENT_OUT=artifacts/garden-landing-recruitment-another
```

Keep sources unchanged during collection. It freezes models, inputs, binary,
build flags and sources, checks original historical scores/fingerprints, repeats
traces byte-for-byte and compares tracing-disabled execution. Verify separately:

```sh
docker compose run --rm -T firmware python3 \
  artifacts/garden-landing-recruitment-v1/sim/garden_landing_recruitment.py \
  --verify artifacts/garden-landing-recruitment-v1
```

For a custom read-only replay, use the native CLI:

```sh
build-host/toy-factory-garden-landing replay MODEL.tgl rainfed 0x1234 \
  --ticks 737280 --climate steady --ledger --recruitment-trace NEW.jsonl
```

The trace file must not exist. This option requires `--ledger` and is exclusive
with signal interventions and decision-alternative traces. Normal replay JSON
and all hashes remain unchanged. A failed process invalidates its entire trace.

## Compact JSONL schema

Header: `{"schema":"landing-recruitment-trace-v1"}`. Each ecology step has
`tick`, `seeds` and `plants`, even when both lists are empty. A final completion
record includes the exact stop tick. The analyzer requires every sample.

Seed check arrays contain, in order: parent ID, age in ecology ticks, column,
blocker mask, moisture, light, occupied plant slots, nodes, outcome, child ID,
and number of hypothetical mature open columns. Outcomes are 0 waiting,
1 expired, 2 germinated. Expired entries undergo no check: moisture/light/mask
are placeholders and open-column count is -1. Seed identity is parent plus
`tick - age * 15`. Blocker bits 0..6 are dormancy, moisture, light, plant capacity,
node capacity, spacing and cold. They overlap; no single cause is assigned.

Descendant records cover birth through birth+3840 ticks inclusive, ending at
death or the run horizon if earlier. `stages` contains five snapshots after
uptake, maintenance, germination, growth and reproduction; each snapshot is
`[energy, water, stress, flags, node_count]`. Pre-birth snapshots are null.
`uptake` contains energy/water tuples of
`[before, actual_income, overflow, upkeep_due, upkeep_paid, discarded]`.
The last three fields apply only to the natural-death step; for surviving
plants upkeep is the difference between uptake and maintenance snapshots.
`roots` and `active_leaves` describe the post-step body, not uptake-time light.

The analyzer balances every first-day resource transfer and reconciles every
seed sample/fate against the complete lifetime ledger. Pending seeds are
censored; blockage counts do not predict the effect of removing a rule.
