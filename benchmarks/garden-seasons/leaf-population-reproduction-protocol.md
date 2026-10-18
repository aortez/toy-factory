# Ordered reproduction access comparison

Explain why the condition-only shrubs stop buying replacement seeds in the
[placement regression](leaf-population-fallback-loss.md). Observe eligibility
and visitation order without changing capacity, placement, repair, growth,
weather, or the renewal-first objective.

## Fixed comparison

Run four replays: original and fewer-blocker placement on weather seed
`9a903368`, each with diagnostics off/on. Keep the condition-only repair
variant from tick zero, Search 1 growth setup, rainfed environment, and no
gardener. Use the existing eleven checkpoints through day 608. Diagnostics on
also retains the resource trace through day 256 and purchase trace in `[30,35)`.

Use two workers, a 180-second per-call timeout, a 900-second collection budget,
and the existing 24 MiB per-call output limit. Require a new output directory;
retain failed attempts without silently repeating simulations. Freeze sources,
protocol, and binary during collection. No training or firmware deployment.

Baseline: `leaf-population-fallback-results.json.gz`, SHA-256
`61381e2a5d72106e54212c78715718b1aef289bb91375518db204e6dfe5418ce`.

## Bounded read only trace

Reuse the frozen reproduction audit after growth, dawn flower renewal, and
cooldown decrement. Record only reproduction-cadence ticks in `(128,232]`:
6,656 ticks at intervals of 60 logic ticks. Keep per-lineage blocker-mask
histograms for every visit. On ticks where any visit sees fewer than eight
seeds, retain the complete ordered visit list, including later visits that
see the bank full again. Record resources and required thresholds, flower
readiness, cooldown, stress, sunlight, bank occupancy, blockers, and purchase
outcome. At most 128 lineage counters and 512 opening-tick receipts; exhaustion
latches failure rather than truncating evidence. Allocate once at enable,
never while stepping. Do not retain mutable simulation pointers.

An otherwise-eligible visit blocked only by bank capacity is distinct from a
visit with other simultaneous blockers. A later plant losing an opening means
the bank was open earlier in that tick, then filled before its visit while
all its non-bank checks passed. This describes actual ordered checks, not a
counterfactual change of order or a claim that different ordering improves
long-term survival. Full-bank ticks without an opening remain represented in
the histograms.

## Validation

Run the host suites and preparation tests before collection. Cover bounds,
incomplete coverage, mask consistency, ordered occupancy, duplicate visits,
allocation failure, output errors, reset, failure latching, and no step-time
allocation. Preserve authenticated frozen sources; this uses an existing hook
and needs no new core adapter.

Require all four final states and eleven checkpoints each to match the prior
archive byte-for-byte, including histories and pixels. Logging-on/off must
also match; original resource and purchase traces must be unchanged. Reconcile
every new purchase receipt with the complete seed ledger. Reconstruct bank
occupancy at the start of reproduction from seed lifetimes, excluding seeds
removed earlier in the same tick. Check all 6,656 cadence ticks for complete
opening coverage, and reconcile receipt masks against aggregate counters.

Report family and individual access, especially shrub 17, with actual
simultaneous blockers. Decide the next intervention only after examining these
results; no fairness, capacity, or eligibility change is part of this comparison.
