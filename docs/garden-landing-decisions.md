# Same-state landing decisions

Host-only, read-only follow-up to the [signal panel](garden-landing-signals.md).
The [fixed protocol](../benchmarks/garden-seasons/landing-decisions-protocol.md)
retains all three current-only controllers and the same 16 development conditions.
It is not training, another ecology intervention, or a device/default change.
The [completed report](../benchmarks/garden-seasons/landing-decisions.md) retains
all raw traces, original results and independently recomputed comparisons.

```sh
make host-trace-landing-garden \
  GARDEN_LANDING_DECISIONS_OUT=artifacts/garden-landing-decisions-v1

make host-landing-garden \
  ARGS="trace-replay current.tgl rainfed 0x25185eeb --ticks 737280 --climate seasonal --ledger --trace new-trace.jsonl"
```

`trace-replay` requires a new `--trace` file and a current-only, flags=0 model.
Ordinary replay rejects trace options; trace mode rejects intervention options.
The output JSON is the ordinary live replay result, not a counterfactual world.
The trace header binds the full original model bytes and all probe definitions;
its footer binds the final GLR1 run hash. No file is overwritten. An interrupted
trace is incomplete; do not accept a file without a footer, successful native
exit, matching reference decisions and matching ordinary replay.

Each actual pre-arbitration policy query increments the role/day census. Raw
common-source histograms cover all valid queries. Detailed samples are the first
root and stem query per day, at most 384 samples per 192-day world. These are
stratified samples, not all queries or an unbiased query-frequency estimate.
Days without queries remain absent. Plant-slot/tip indexes are diagnostic
locations, not persistent lineage IDs.

The live policy alone advances state. After its successful step, the collector
evaluates the ten previous group probes and six individual water/light probes
on each captured observation and incoming private memory. Neither hypothetical
memory nor proposals feed back into the simulation. The cache, model bytes,
legacy sensing and body/source-validity gating remain untouched.

An optional read-only callback on the shared run step receives borrowed inputs
and the live proposal. Callback errors preserve run/cache/death/seed outputs.
Observer-owned context is not transactional and must be discarded after a failed
step; the CLI aborts instead of publishing a complete trace. This adds no fields
to the run checkpoint, world, cache or model file and changes no inference code.

The shared independent Python integer reference recomputes every native sample
and probe result, including clipping, ties, direction ordering and forced finish.
Reports separate action, priority, ordering and next-memory changes. A proposal
may lose all-tip arbitration or fail growth constraints; these counts are not
accepted actions, long-term fitness gains or evidence of useful sensing.
The retained `low_clipped_units` / `high_clipped_units` counters mean hidden
outputs equal to 0 / 127, including exact boundary values and quantization;
they do not count only values changed by the clipping operation.

All 48 runs must exactly match their old native results, repeat with one worker,
and pass frozen-bundle verification. Sources/builds stay fixed during collection.
The protocol and source snapshot do not by themselves prove binary provenance.

```sh
docker compose run --rm -T firmware python3 \
  artifacts/garden-landing-decisions-v1/sim/garden_landing_decisions.py \
  --verify artifacts/garden-landing-decisions-v1
```

`GARDEN_LANDING_DECISIONS_ARGS="--jobs 4"` controls independent worker processes
(1–8), not policy behavior. Collection requires a fresh artifacts/external path.
No new screenshots are collected for unchanged worlds; the prior fixed galleries
remain the visual evidence. Discuss results before changing training or sensing.
