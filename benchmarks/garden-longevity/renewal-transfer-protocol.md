# Frozen-model world/schedule transfer: fixed diagnostic

Complete the missing cells of the replication's world-set × patch-schedule-set
cross, without training, mutations, early-generation selection or score changes.
This is a diagnostic on already inspected models/conditions, not a new held-out
test or an environment-qualification claim.

## Frozen inputs and design

Pin `artifacts/garden-renewal-replication-v1`, manifest SHA-256
`8cc60dbe89f9040457f4abd60e81b2c3f5379dac6987b5b3deb872dcc870a45f`.
Verify it fully. Copy its exact persistence-trial/replay executables, native
source/configuration, selected model bytes, and existing diagonal histories.
Do not rebuild native tools or alter the simulation. Freeze the new Python
runner, this protocol, copied input hashes and native command logs before runs.

| Frozen model | Source replica / arm / candidate | CRC |
|---|---|---|
| Original | R1 / v2 / initial | `dc5e849d` |
| R1 A final | R1 / v2 / g3-c2 | `46fad3c2` |
| R1 B final | R1 / renewal / g2-c1 (retained at G3) | `7ce0ed84` |
| R2 A final | R2 / v2 / g1-c2 (retained at G3) | `f51cb1d4` |
| R2 B final | R2 / renewal / g3-c3 | `01b9d94a` |

Use all previously fixed seeds, in their existing order:

- Training worlds: `b3376513`, `4023af38`, `1558f0e0`, `a61abb6e`,
  `39ee1dd4`, `0cfc84ff`, `1b85ea27`, `6a6893e3`.
- Review worlds: `abf7af73`, `58e36558`, `0d983a80`, `beda710e`.
- Training patch schedules: train-1 `a3b7e953`, train-2 `50a32378`.
- Review patch schedules: review-1 `05d87ca0`, review-2 `b69a372e`.

| Cell | World set | Schedule set | Conditions/model | Evidence |
|---|---|---|---:|---|
| TT | Training | Training | 16 | Reuse exact saved histories |
| TR | Training | Review | 16 | New, independently repeated |
| RT | Review | Training | 8 | New, independently repeated |
| RR | Review | Review | 8 | Reuse exact saved histories |

Five models × 48 conditions = 240 unique model/world/schedule outcomes; 120 are
reused and 120 new. Same seed under different schedules means matched resets,
not switching a schedule mid-run. World seed jointly changes startup/trait/RNG
and weather trajectories; this does not isolate weather alone. Schedule sets
contain only two seeds each and share the same patch generator.

Retain the unchanged 512-node/eight-plant/eight-seed rainfed-crowded ecology,
wide dispersal, headroom uptake, selective maintenance, night-growth veto and
ordinary rain/patch deaths. No gardener, irrigation, founder exit, root bootstrap,
seed reserve, gap intervention, changed neural interface or inherited plant NN.
Every new trial runs through day 192. Keep native v2 (158,190] plus two-day
follow-up, and the existing bounded-renewal periods (62,94], (94,126], (126,158],
(158,190] with their own follow-up and 32-day credit cap. No new scoring gate.

## Fixed calls and visual panel

- 120 new off-diagonal trials + 120 independent complete repeats = 240 trials.
- Fixed screenshots: all five models, all four cells, both schedules per cell,
  at day 192, using the **first canonical seed of each world set** (`b3376513`
  or `abf7af73`). Eight rows × five models = **40 images**.
- RR's ten images and their saved independent raw/JSON repeats are copied from
  the prior verified bundle. TT's ten plus TR/RT's twenty require **30 new
  replays and 30 independent image repeats**.
- Total **300 native processes**, no mutation/training calls or added conditions.
  At most two independent model jobs run concurrently, in separate directories.

Images are anchored before seeing crossed outcomes. Retain failed/empty gardens,
unchanged/reused models, all conditions and both schedules; no outcome-based
image selection, rerun, extra horizon or budget extension. The gallery marks
reused versus new captures and the fixed row/column identity.

## Analysis and verification

Primary: final B versus final A, separately for R1/R2, in all four cells under
the unchanged bounded-renewal ordering. Every finalist versus original is a
mandatory control. Report both score views, survival tiers, per-world minimum
and total credit, zero periods, species/founder-family retention, and native
late-window child and seed-purchase cohorts. Keep both schedules and blocked
world-seed omissions; omissions remove both schedules together.

Training/review world sets have eight/four seeds. Never compare their raw sums
as an effect. For credit-only descriptive contrasts, use the exact mean per
world/schedule condition (sum divided by 16 or eight), preserving rational
numerators/denominators. Survival precedence stays explicit; a credit contrast
cannot override terminal tiers or become a new selection score.

For each matched model comparison and each score view, retain four normalized
candidate-minus-control cell differences, schedule-set shifts within each world
set, world-set shifts within each schedule set, and the difference of those
schedule-set shifts. Report per-world schedule shifts and leave-one-world-seed-out
contrasts, dropping that seed from both of its cells. These are finite-panel
descriptive sensitivities, not independent observations, confidence intervals,
a population-level causal decomposition, or additional model selection.

Reused diagonal annotations and scores must match the replication exactly.
New primary/repeat native JSON must be byte-identical. Validate world/model/
schedule identity, capacities, no interventions, full follow-up, C/Python v2
agreement, every bounded-period oracle/projection and credit additivity. All
40 images must match their ledger endpoints, PNG/raw conversions and independently
repeated pixels; the ten reused images also retain their source hashes. Validate
exact call identities and budget, fixed model provenance and unchanged inputs.
Save current sources, exact copied native sources/configuration, models, full
histories, annotated scores, command/timing logs, and portable verified outputs.
Failed collection retains partial evidence without a completed manifest.

Test the cell partition, reuse mapping, frozen-final identity, unequal-denominator
normalization, interactions and blocked omissions, survival flags, schedule
routing, byte-repeat rejection, frame identity/reuse and exact process budget.
Reverify the input replication; reanalysis/export checks run no native commands.

## Stop and discuss

Stop at the fixed budget and report the complete cross, including mixed results.
Ask whether the losses follow world conditions, schedule seeds or their
combination; do not claim that a world-set association isolates weather, or that
four schedules establish general robustness. Do not adopt/promote a model, tune
the objective/ecology, start training, deploy firmware, commit, push or open a PR.
Preserve existing uncommitted work and record findings in the roadmap and issue #30.
