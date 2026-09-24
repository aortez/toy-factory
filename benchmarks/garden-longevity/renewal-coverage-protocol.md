# Bounded-renewal world coverage: fixed 8/16-world comparison

Test the transfer diagnostic's coverage hypothesis without changing the score,
ecology, schedule sets, mutation streams or candidate budget. N (narrow) and W
(wide) both select by individual bounded renewal; these are not the previous
v2/renewal objective arms. This is one fixed exploratory comparison, not a
general trainer, model-promotion decision or final qualification test.

## Inputs and panels

Pin `artifacts/garden-renewal-replication-v1`, manifest SHA-256
`8cc60dbe89f9040457f4abd60e81b2c3f5379dac6987b5b3deb872dcc870a45f`.
Fully verify it and reuse its exact native tools/configuration, original model
`dc5e849d`, and complete R1/R2 renewal searches including independent repeats.
Those are the N controls; do not rerun or retrospectively select their models.

- N training worlds: `b3376513`, `4023af38`, `1558f0e0`, `a61abb6e`,
  `39ee1dd4`, `0cfc84ff`, `1b85ea27`, `6a6893e3`.
- W adds the first eight `trial_seeds(0x63767432, 8)` outputs: `42f07d93`,
  `b1e4b7b8`, `e49fe860`, `57dda3ee`, `c8290554`, `fd3b9c7f`, `ea42f2a7`,
  `9baf8b63`. No rerolling or seed selection based on results.
- Fresh shared review worlds: the first eight `trial_seeds(0x63767232, 8)` outputs,
  `5a30b7f3`, `a9247dd8`, `fc5f2200`, `4f1d698e`, `d0e9cf34`, `e5fb561f`,
  `f28238c7`, `836f4103`. None selects parents or extends search.
- Unchanged training schedules: train-1 `a3b7e953`, train-2 `50a32378`.
- Unchanged review schedules: review-1 `05d87ca0`, review-2 `b69a372e`.
  Review worlds are fresh; these schedule seeds have already been inspected.
- Matched mutation streams: R1 `d4146f83`, R2 `2700a5a8`. Each begins from the
  original, with three generations × three offspring and 32 parameter mutations
  per offspring. Strict improvements select; ties retain the incumbent, then
  the first canonical better child. W's first three mutant bytes must match N;
  later parents may diverge only through the unchanged selector.

Before writing this protocol, the sixteen new seed literals had no case-insensitive
matches in local sim/docs/benchmarks/artifacts JSON, JSONL, Markdown or Python,
including ignored files. Compressed/private history is not claimed. The prior
four review worlds are not added to training. All sixteen new seeds are distinct
and disjoint from the existing world/schedule/mutation seeds.

N evaluates 16 conditions per candidate; W evaluates 32. Candidate/mutation
budgets are matched, **not evaluation compute**: W uses twice as many training
world evaluations per candidate. Both cover the same two training schedules.
Fresh review covers sixteen conditions, equally for all models/generations.

Retain the 512-node/eight-plant/eight-seed rainfed-crowded ecology, wide dispersal,
headroom uptake, selective maintenance, night-growth veto and ordinary recurring
patch deaths. No gardener, irrigation, intervention, changed neural interface
or inherited plant NN. Native tools are copied, not rebuilt. All trials stop
at day 192. Keep native v2 (158,190] with two-day follow-up, and bounded periods
(62,94], (94,126], (126,158], (158,190], each with its own follow-up, full-day
confirmation and 32-day credit cap. No new diversity reward or hard gate.

## Exact collection budget

- Reuse both complete N searches and their capture-disabled repeats: 640 native
  ledger histories and 36 mutation records from the pinned bundle, no new calls.
- Two W searches: ten candidates × 32 conditions × two replicas = **640 new
  training trials**, plus **640 capture-disabled repeat trials**.
- W mutations: nine × two replicas × primary/repeat = **36 calls**.
- Review G0, G1, G2 and G3 for both N/W and both replicas on all sixteen fresh
  conditions: **256 new review trials**, irrespective of unchanged champions.
- All 256 review endpoints get a day-192 native screenshot and an independent
  image repeat: **512 replay calls**, with all raw/JSON repeats saved.
- Exact new budget: **2,084 native processes**, comprising 1,536 ledger trials,
  512 image replays and 36 mutation calls. At most two independent replica jobs
  concurrently; each replica's native searches/reviews remain serial/private.

Every generation's entire fixed review panel remains visible, including losses,
unchanged champions, single-species worlds and failures. No outcome-selected
screenshots, extra horizons, restarts, added conditions or budget extensions.
Partial failures keep their evidence and do not get a completed manifest.

## Analysis and verification

Primary: final G3 W versus G3 N under the same bounded-renewal ordering, separately
for R1 and R2, on the fresh review panel. Mandatory controls: each final versus
the original, and every generation under both score views. Report terminal
survival tiers before credit; per-world minimum and total bounded credit, zero
periods, schedules, paired counts and blocked world-seed omissions stay visible.
Omissions remove a world seed under both schedules, not independent observations.

For training diagnostics show W/original on the original eight and added eight
worlds separately, alongside N/original on its original panel. Include exact
per-condition mean credit for own-panel scores: 16 versus 32 conditions makes raw
sums incomparable. Do not infer a gain from W's larger total or retrospectively
choose a better review generation. Native late-window child and seed-purchase
cohorts are separate from the four bounded periods. Track species and founder
families separately, without adding either to selection.

Verify N's exact saved searches, common first-generation bytes and original-world
histories, original controls across arms/replicas, full W capture/no-capture
search agreement including bytes, RNG/parents, scores and champion sequence.
Validate native trial identities, capacities, no interventions, follow-up,
C/Python v2 agreement, bounded-period oracles/projections and credit additivity.
All screenshots must agree with native ledger endpoints, independent pixels
and PNG conversions; regenerate/check both combined contact sheets. Freeze
source/input hashes before native work and verify them afterward. Save copied
inputs/native sources/configuration, current runner sources, candidate models,
full histories, exact commands and timings. Verify exact call identities/budget,
not only counts. Reanalysis and export execute no native simulations.

Test split/reuse/budget, unchanged selector/defaults, prefix subset agreement,
paired omissions, unequal-denominator means, exact command and schedule routing,
tampering rejection, capture independence and private concurrent search state.
Reverify the prior replication; do not rebuild native code for a Python-only
study. Record full results, gallery and limitations in the repo/roadmap/issue #30.

## Stop and discuss

Conclude at the fixed budget, including negative or mixed results. Two mutation
streams share one review panel; they are not independent environmental samples.
World seeds bundle startup/traits/RNG/weather, not a weather-only intervention.
Schedule seeds and the broader-panel design were informed by earlier exploratory
work. A single broader panel cannot establish an optimal coverage size or broad
generalization. No automatic default adoption, ecological tuning, larger search,
model promotion, firmware deployment, commit, push or PR. Preserve prior
uncommitted work and discuss the next step first.
