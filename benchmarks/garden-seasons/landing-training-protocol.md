# Landing-aware renewal pilot v1

Frozen before candidate evaluation. This is a bounded development experiment,
not a device-default change or a final test of generalization.

## Fixed question and environment

Can the existing controller make useful progress under the established renewal
objective with landing inputs off, current-only, or current-plus-history?
All three arms use ordinary production ecology, gardener off, no irrigation,
unchanged seasonal/weather code and seed placement. No research build flags.
Start from the previously evaluated legacy controller, payload CRC `01b9d94a`,
SHA-256 `fab9b6d97de88a970d63bb8af8fc336d076bb3d0ae6867b307290209abf85cf2`.
Explicitly import it into each TGL2 mask with zero extension weights. Do not omit
dead-only occupancy. All arms start with identical behavior.

## Objective and clocks

Use the existing `garden-individual-renewal-candidate-v1` implementation without
changing its arithmetic: four windows (62,94], (94,126], (126,158], (158,190]
Garden days, one-day establishment, 32-day maximum credit per confirmed child,
and two days of follow-up per endpoint. Run every world to day 192 (737,280
logic ticks). One Garden day is 3,840 logic ticks / 256 ecology steps.

Maximize the lexicographic key: minimum terminal tier; sum of terminal tiers;
sum of each world's minimum window credit; total window credit. Renewal credit
requires established offspring of established non-founder parents. Seed-only
endpoints remain unconfirmed, not automatically extinct after two days. Old
survivors, total historical births and endpoint plant counts are diagnostics,
not additional tie-breakers. Retain zero-credit windows and per-world outcomes.

## Fixed budget and splits

- Three independent search RNG seeds: `6d697833`, `6d697834`, `6d697835`.
- Three masks: off, current, history.
- Two generations, three children each, plus the initial controller: seven
  candidate evaluations per arm/replicate, 63 total. No extra tuning rounds.
- Training: world seed `a9c30c1f`, both rainfed layouts, steady and seasonal
  climates: four matched conditions for every candidate.
- Manual review: seed `ed52188c`, same four layout/climate combinations, for the
  generation-zero and each generation's training-selected champion. Review
  never affects selection. Both seeds have appeared in development before;
  this is not an unseen final test split.
- Every child starts from that generation's incumbent. Canonical child order;
  strict improvement only. Ties retain the incumbent (or first strict winner).
- Each mutation performs 32 existing legacy parameter mutations, followed by
  16 uniformly selected extension-weight mutations, using the same xorshift32
  stream. Byte deltas are nonzero -8..8, clipped to int8. Legacy mutation is
  unchanged. Config, scales, masks and reserved bytes never mutate.
- The same extension mutations occur in all arms, including masked weights.
  This keeps random draws and legacy perturbations matched until parents
  diverge. Effective search dimensions differ; this pilot does not isolate
  information quality from search difficulty. Equal candidate budgets, not a
  claim that all mutations are equally useful.

## Evidence and stopping

Persist every candidate model, parent, input/output RNG, exact lineage/seed
ledger, per-world score and selected champion. Capture the fixed seasonal
review worlds (both layouts) at days 16 and 192 for every generation, including
generation zero; retain failure/empty images. Rendering runs independently
from evaluation. Repeat the entire search and review without captures; require
identical model bytes, RNG states, histories, scores and champion decisions.

Freeze the binary, model, source snapshot, build flags, protocol and artifact
hashes. Fail closed on missing records, invalid ancestry, ledger overflow,
nonrepeatable output or source changes during collection. A source snapshot is
not by itself proof of binary provenance. Freeze the build before collection.

Stop after the fixed budget, even if every score ties. Inspect the saved images
and compare per-condition changes, including regressions. No default promotion,
ecology adjustment, longer search, new objective or device flashing in this
experiment. A flat result is useful evidence about objective/search reachability.
