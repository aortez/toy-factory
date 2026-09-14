# Training-seed coverage: frozen protocol

Double the prior training panel from four to eight world seeds, while retaining
the same original model, mutation RNG/algorithm, ten-candidate/three-generation
budget, fitness, ecology, schedules and clocks. This is one bounded coverage
comparison, not model promotion or qualification. Preserve the previous pilot.

## Identity and environment

Original model `dc5e849d` and exact native executables come from the first pilot,
manifest `9c9dc94e44cee155b4d8a83276339936d17e97cce4b995259faed4cd31059950`.
The frozen narrow-panel comparison is `g3-c2` / `449c35fe` from the preceding
mixed-condition pilot, manifest
`511b26198ed46fbe7e1a5a7893613450613f2cb24b2abea9b2f0ec5ba6fe6fb2`.
Copy and hash both source manifests and model files; no native rebuild.

Same 512-node/bank-eight rainfed-crowded host ecology: wide-v1 dispersal,
headroom-v1 uptake, leaf-maintenance-v1, selective maintenance, neural-no-night-
growth adapter; gardener/irrigation, drainage and seed reserve OFF. No changes
to controller inputs/actions or plant inheritance. One shared controller per
world, not independently evolving plant neural genomes. Diversity is diagnostic
only, with no reward, constraint or tie-breaking role.

Run every world from reset to day 192 (737280 ticks), score (158,190]
(`606720 < tick <= 729600`), fixed two-day follow-up. Do not approach the known
256-day age boundary. Two existing patch-death-v1 schedules in canonical order:
fresh-1 `e4d65e6f`, then fresh-2 `17c29444`.

## Fixed split and controlled comparison

Training seeds, in order:

- Original four: `5fd2b58f`, `acc67fa4`, `f9bd207c`, `4aff6bf2`.
- Added four: `68d9e00c`, `9bcd2a27`, `ceb675ff`, `7df43e71`, generated with
  `trial_seeds(0x636f7664, 4)`.

Four fresh review seeds: `eb300b12`, `1824c139`, `4d5f9ee1`, `fe1dd56f`, generated
with `trial_seeds(0x62727631, 4)`. New literals had no matches in local reports/docs
before protocol creation; not a claim about all private runs. Old review seeds
do not become training examples. Every seed is crossed with both schedules:
16 training conditions and eight review conditions. Familiar schedules are not
held-out schedules. No final-test set or statistical generalization claim.

Keep search RNG `0x6d697833`, 32 existing native parameter mutations per child,
three offspring of the generation-start incumbent per generation, three
generations. Rank only the unchanged six-component persistence-v2 aggregate
over the 16 training conditions. Strictly better replaces; ties retain the first
incumbent/candidate in canonical order. Keep the full three-generation budget
even if unchanged or poor. No review-driven restart, early stop or seed replacement.

The initial model and first three mutant bytes must match the previous narrow
experiment exactly. Their complete native outputs on the original eight
conditions must match its manifest fingerprints. Later candidate sequences may
diverge if broader coverage selects another parent; that is the experimental
effect, not a promise of identical later mutations.

Evaluate the frozen narrow-panel final champion on the same fresh review panel,
without allowing it into the new search or generation sequence. This is needed
to compare training approaches on matched review worlds rather than comparing
percentages from different panels. It is a historical control, not an extra
search candidate. Original, new generation champions and narrow control all use
the same ecology and replay settings.

## Budget, verification and visuals

- New search: ten candidate models × 16 training conditions = 160 trials.
- Full capture-disabled repeat: another 160 trials; require identical candidate
  bytes, RNG records, full scores, world hashes and champion history.
- Generations 0/1/2/3 on all eight review conditions = 32 trials and captures.
- Frozen narrow reference on all eight review conditions = eight trials/captures.
- Total: **360 scored trials**, of which 160 are reproducibility duplicates;
  **40 required native PNG/RGB565 captures**, all at day 192.

Capture generation review after each completed generation in independent reset
processes. Preserve unchanged champions and failed/empty worlds. Keep the narrow
reference separate and evaluate it after search/repeat. Independently double-render
all 40 frames; require evaluator/checkpoint hashes, byte lengths, CRCs, repeated
pixels and PNG conversion to agree. Gallery rows are the fixed eight review
conditions; columns are generation 0/1/2/3 and the narrow reference.

Every scored trial exports complete bounded lineage/seed ledgers and must match
the existing Python scorer. Reuse one explicit immutable study profile in the
tested runner, preserving the original profile/default and old-bundle verifier.
Test missing/extra conditions, split separation, unchanged champions, selection
precedence, mutation ancestry/RNG and non-selecting reference diagnostics.
Record source/config/model/executable hashes before collection, leave source
unchanged during collection, fail closed on overflow or any mismatch, and only
publish a complete manifest after full artifact reanalysis. Reports are added
afterward. No worker pool or concurrency change in this experiment.

## Interpretation and stop

Report all candidates and generations, original versus added training seed
blocks, full/per-schedule/leave-one-world-seed-out comparisons, and final versus
both original and narrow controllers on the same review panel. Remove both
schedules together when omitting one world seed. Include terminal tiers,
renewal/live-time attribution, establishment/seed cohorts, species/founder-family
histograms, all images, runtime and storage. Images are diagnostic, not fitness.

Broader coverage helps this comparison only if the new final champion improves
the fresh review aggregate relative to the frozen narrow champion. Beating that
champion is not enough to call the model generally better: report whether it also
beats the original, both schedules and individual pairs/omissions. No automatic
promotion follows even if all of those agree. An unchanged champion or failed
transfer is a valid result; do not extend the budget to obtain a win.

Stop after this budget. Discuss the result and limitations of eight training
seeds, four review seeds, one search RNG, familiar schedules and a finite scoring
window before another experiment. No fitness/ecology/default change, commit,
push or device deployment is included.
