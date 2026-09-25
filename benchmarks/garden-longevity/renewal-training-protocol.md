# Persistence versus bounded-renewal training: fixed A/B protocol

Founder-independence work was checkpointed first as `bbb6307` (not pushed).
Test whether optimizing the already investigated bounded-renewal ordering improves
sustained recruitment on a separate review panel. This is one small matched
training comparison, not ecological adoption, model promotion or a final test.

## Frozen environment and inputs

Use the original model `dc5e849d` and exact native mutation/trial/replay binaries
from `garden-training-coverage-v1`, manifest SHA-256
`a9142bff1570b3912b7f7d5dc71dbf4575c3db6df10249cf9b3539643abaf460`.
Verify that bundle completely and pin/copy its manifest, model, tools and build
configuration. Do not rebuild native tools or change the world simulation.

Same rainfed-crowded, 512-node/eight-plant/eight-seed, undrained host environment;
wide dispersal, headroom uptake, selective leaf maintenance, neural night-growth
veto, existing plant-trait inheritance and one frozen shared controller per
world. No gardener, irrigation, seed reserve, founder exit, gap export, root
bootstrap or changed observations/actions. Diversity is diagnostic only.
Both arms keep existing rain and recurring patch-death schedules:
fresh-1 `e4d65e6f`, then fresh-2 `17c29444`.

Run each world from reset through day 192 (737280 logic ticks). The native
ledger keeps its original (158,190] scoring window and two-day follow-up; the
Python candidate selector projects earlier periods from the same full history.
No run approaches the known 256-day plant-age boundary.

## Split and search budget

Eight training seeds, unchanged and in order:
`5fd2b58f`, `acc67fa4`, `f9bd207c`, `4aff6bf2`,
`68d9e00c`, `9bcd2a27`, `ceb675ff`, `7df43e71`.

Four fresh review seeds from `trial_seeds(0x726e7631, 4)`:
`78a542dc`, `8bb188f7`, `decad72f`, `6d889ca1`.
Check these literals against prior local source/reports before collection and
record the scope of that check. Cross every seed with both schedules: **16
training conditions and eight review conditions**. Review never enters automated
selection. Existing heavily inspected review worlds do not become training
examples or an untouched final test. Familiar schedules are not held-out ones.

Each arm starts from the same original controller and search RNG `0x6d697833`.
Run three generations of three offspring each, with 32 existing native parameter
mutations per offspring: **ten candidate evaluations per arm**, including the
initial model. All offspring come from the generation-start parent. Strictly
better replaces it; exact ties keep the incumbent, then the first better child
in canonical order. No review-driven restart, early stop, extra mutation sweep,
seed replacement or budget extension, even for unchanged/poor champions.

The two arms' initial model and first three mutant bytes must agree. A's entire
training search, all raw ledgers, model bytes and mutation RNG records must
reproduce the frozen coverage run. Later B parents/mutants can diverge because
the selector differs. That is the tested effect, not a failure to match draws.

## Explicit experimental selectors

**A: persistence-v2.** Retain the exact existing native/Python world score and
aggregate over the 16 training conditions at (158,190]. No rewriting of old
bundles or default runner behavior.

**B: individual bounded renewal.** Reuse the tested 32-day post-confirmation
living-time credit and four fixed periods: (62,94], (94,126], (126,158], (158,190].
Each period has its own existing two-day terminal follow-up. Credit only offspring
of an established non-founder parent, with the existing first-day confirmation
and sample-boundary rules. A child's lifetime contribution is capped at 32 days;
old surviving bodies cannot supply perpetual credit.

Maximize the existing four-component individual-minimum key, lexicographically:

1. Minimum existing terminal tier across all world-period endpoints.
2. Sum of those terminal tiers.
3. Sum over worlds of each world's minimum credited time across four periods.
4. Total credited time across worlds and periods.

This is not a zero-gap gate, minimum across worlds, diversity reward, intervention
bonus or opportunity-normalized score. Strong worlds can still compensate for
weak ones; retain per-world minima, zero periods and terminal outcomes explicitly.
The entire proposed selector (time credit, multi-period survival and aggregation)
is the treatment; this experiment does not isolate their individual effects.
Compute both score views for every candidate and review model, but only the
arm's declared training key selects. The new objective is an explicit host pilot
adapter; existing runner defaults, native fitness and firmware stay unchanged.

## Capture and verification budget

- Two searches × ten candidates × 16 conditions = **320 training trials**.
- Repeat each complete search with review/capture disabled = **320 repeat trials**.
- Two arms × four generation champions × eight review conditions = **64 review
  trials and 64 required native PNG/RGB565 captures**, all at day 192.
- Independently repeat every frame: another 64 replay processes.
- Total **704 ledger trials + 128 image replays + 36 mutation calls = 868 native
  processes**. Reanalysis/verification uses saved evidence, not extra training.

Preserve generation 0 and every completed generation, including unchanged models
and empty/failed gardens. Review/capture runs after each generation in independent
reset processes. Each arm's capture/no-capture runs must match candidate model
bytes, full score histories, mutation ancestry/RNG, native ledgers and champion
sequence exactly. Preserve both copies. Gallery rows are the eight fixed review
conditions; columns are A generations 0/1/2/3, then B generations 0/1/2/3. Native
frames must match ledger endpoint hashes, counts, CRCs, repeated pixels and PNGs.

Native v2 scores must match Python. Every bounded period must match its sampled
credit oracle and independent legacy projection; period credit must add to the
combined interval. Fully reanalyze all candidate/review histories, selection,
pair comparisons and split contracts. Test opt-in/default behavior, unknown
selectors, missing/extra conditions, late/incomplete follow-up, mixed contracts,
ties, survival precedence, review isolation and mutation parent selection. Reject
intervention-tainted trials. Re-run previous mixed/coverage bundle verifiers.

Pin sources, protocol, selectors, settings, binaries, model inputs, native command
logs and configurations before collection; freeze them during the run. Failed
collection retains partial evidence and cannot publish a complete manifest.
Export verified portable summaries/gallery/PNGs outside the immutable raw bundle.

## Report and stop

Primary comparison: final B versus final A on the fresh review panel under the
declared bounded-renewal key, with original versus each final as mandatory
controls. Report both scoring views for every generation on training/review;
both schedule groups; individual paired wins/ties/losses; and blocked
leave-one-world-seed-out comparisons, removing both schedules together.

Report terminal survival tiers, renewal minima/total/zero periods, seed outcomes,
full-day survivor cohorts and species/founder-family retention. Retain complete
credit/lineage evidence for interpretation; screenshots do not prove fitness.
An own-score training gain alone is not success. A review improvement is exploratory
evidence for this objective and finite panel, not reliable generalization from
one search RNG or a license to promote a model. If survival tiers differ, report
that precedence instead of interpreting only a later numeric component.

Stop after this budget regardless of the outcome. No additional founder challenge
is run here; its existing report stays a separate diagnostic. No permanent ecology,
default objective, worker pool, model promotion, PR, push, device deployment or
automatic final commit. Record results on issue #30 and discuss next steps.
