# Garden A-life roadmap

[GitHub issue #30](https://github.com/aortez/toy-factory/issues/30) tracks milestone
status and experiment notes. This document records the agreed direction,
acceptance gates, and design constraints. Update the issue with evidence as
work lands; it is the authoritative completion checklist.

Status as of 2026-09-13: foundation tools and the saved-model screenshot/gallery
bridge exist, checkpointed locally in `a1c419f` on `green-garden`; the subsequent
founder-independence experiment is not yet committed. Environment
qualification is underway. The [nighttime-growth comparison](../benchmarks/garden-longevity/night-growth.md)
improves early survival with a host-only decision probe, but does not establish
broad sustained renewal. Per-generation model preservation and screenshots now
work in the bounded [persistence pilot](../benchmarks/garden-longevity/training-pilot.md);
general trainer capture, parallel training and the optional live viewer remain later work.
The [seed-establishment audit](../benchmarks/garden-longevity/establishment.md)
now follows seed outcomes and maps reachable planting opportunities. The
[broader-dispersal comparison](../benchmarks/garden-longevity/dispersal.md) improves
establishment but not durable lineages consistently. It remains an explicit
host-only build variant; device/default scattering and water uptake are unchanged.
The [water-headroom experiment](../benchmarks/garden-longevity/water-headroom.md)
reduces water-shortage deaths and improves offspring survival fractions, but
late renewal falls as spacing and node capacity constrain establishment. Neither
experiment has been promoted to firmware or qualifies the environment by itself.
The [combined uptake/scattering test](../benchmarks/garden-longevity/combined-ecology.md)
completes the four-condition panel. Full-cycle offspring survivors rise to 227
across 48 worlds, but there are only two births in the final eight cycles;
durable-parent results remain policy-dependent. The node pool is completely
full for over 99% of that late window on average for adaptive and the veto
policy. The [node-ownership audit](../benchmarks/garden-longevity/node-budget.md)
finds zero dead-node occupancy throughout the combined late window; living
tissue owns the pool. Reclamation works, but full storage also skips growth
policy calls even where tips remain. The subsequent [512-node host control](../benchmarks/garden-longevity/node-capacity.md)
removes late node pressure: full-cycle survivors rise 227 → 296 and late births
2 → 25, but the eligible survival fraction falls and 43/45 living endpoint
gardens have no growth tips. Plant slots, spacing, shade and persistent mature
bodies remain constraints. The [tip-lifecycle audit](../benchmarks/garden-longevity/tip-lifecycle.md)
attributes every observed termination to depth limits or blocked continuation;
about 99% of late living plant time is tipless, with automatic resource processing
and seed production continuing. The [maintenance design](garden-maintenance-proposal.md)
now has a [host-only implementation and matched comparison](../benchmarks/garden-longevity/leaf-maintenance.md):
bounded mature-leaf observations, slow wear and paid in-place renewal, using
scripted controls without changing NN features/actions. Renewal benefits lit
leaves, wastes resources in shade and can exhaust scarce water. It improves
adult survival but the selective heuristic can suppress late descendants:
the 256-node veto-growth panel has zero late births/deaths despite ongoing
renewal. Do not treat adult persistence or death-driven replacement as sufficient
qualification. The [96-world competition census](../benchmarks/garden-longevity/maintenance-competition.md)
now traces this limit: selective adults keep producing seeds, but living tissue
fills the 256-node pool; at 512 nodes, spacing/plant slots and ground conditions
leave only four germinations from 900 fully followed late seeds. Three of those
offspring survive a day, none becomes a durable parent within the horizon.
The [paired one-gap assay](../benchmarks/garden-longevity/gap-recovery.md) now
exports one predeclared largest mature adult at day 16, without adding seeds or
returning its stores. Offspring appear in 30/32 gap worlds, with 54/63 eligible
offspring surviving a day, but 27/32 worlds have no births in days 20–24. There
are three durable new parents, not broad sustained succession. Largest-adult
export is a diagnostic control, not the recommended environmental rule.
Do not infer a compulsory lifespan, relaxed spacing or permanent disturbance
from this diagnostic alone.
The approved [recurring patch-death experiment](../benchmarks/garden-longevity/patch-disturbance.md)
now tests two predeclared population-independent schedules, ordinary decomposition
and intact soil/seeds over 64 days. Of 64 disturbed worlds, 63 still produce
offspring in days 48–64, versus 1/32 controls. There are 392/497 full-day survivors
and 60 durable new parents after day 16; 55/64 worlds recover locally at least
twice, with no observed final extinction. Memory/ground limits remain, and
surviving founder-family counts fall. This is an exploratory candidate environment,
not proof of indefinite stability, diverse succession or learnable maintenance.
The [192-day fresh-schedule follow-up](../benchmarks/garden-longevity/disturbance-longevity.md)
is now complete: all 128 disturbed worlds still have births in days 160–192,
versus 2/32 controls, with no observed total extinction. However, 53/128 retain
only one species and 44/128 only one founder family; distinct inherited trait
combinations persist. Decide which kinds of variety the environment should
support rather than equating turnover with coexistence. Four fresh schedules
do not imply independent worlds or held-out model qualification.
The [long-run water-budget audit](../benchmarks/garden-longevity/water-balance.md)
now verifies direct stage inventories across all 160 unchanged worlds. All
7,864,320 ecology steps satisfy transfer checks and all 30,880 daily balances
close with matching prior hashes. Soil wetting is retained rain, not an unexplained
source: disturbed closing gains average 206/83 units per day at 256/512 nodes,
with 27% more root uptake in the larger pool. Late water-shortage exposure is
rare, but not zero everywhere; some worlds still fill while others lose water.
The approved [bottom-drainage A/B](../benchmarks/garden-longevity/bottom-drainage.md)
is now complete and host-only: final soil storage falls in 152/160 pairs, but
disturbed late day-survivor counts change 224 → 225 at 256 nodes and 281 → 268
at 512, with one new extinction in the larger pool. Family/species retention
improves at 256, not broadly at 512; some on worlds end wetter because their
populations use less water or disappear. All 80 tests pass, all off daily rows
match prior baselines and all on population/water replays reconcile. Fixed native
comparisons plus a separately labeled failure review are in the report. Keep
the rule experimental: discuss an energy/water/action failure trace and matched
adaptive/reference-policy comparison before retuning, adopting defaults or
training. A frozen-controller failure does not prove impossible ecology.
The [focused policy/resource comparison](../benchmarks/garden-longevity/drainage-policy.md)
now completes that diagnostic: 40 runs across the failed world and fixed review
world, five schedules, both drainage settings and neural/adaptive growth with
identical night veto/selective renewal. Adaptive survives the prior failed case,
but does not uniformly improve turnover or coexistence. Full traces isolate
overnight energy exhaustion from costly neural-grown bodies (and under-reserved
seedlings), not a broken night veto or simple terminal water starvation. One
72-node plant enters night with 212 energy and loses it all to upkeep, with zero
growth/renewal/reproduction spending after sunset and full water before death.
All 84 tests, frozen neural comparisons and independent replays pass. Discuss
a reserve-aware growth policy experiment next; do not infer a body-size limit,
raise storage, tune drainage or train automatically. No default is promoted.
The approved [reserve-aware growth A/B](../benchmarks/garden-longevity/reserve-growth.md)
now tests that single fixed gate on the same neural weights. All 40 runs and 93
tests pass. The previous extinction is avoided; disturbed late full-day survivors
change 40 → 31 off and 29 → 37 on, with better survival fractions but fewer
births. Cumulative durable parents on drainage fall 99 → 68, and all four
reserve controls have no late newborns despite seed production. The gate changes
body/species trajectories, not just immediate survival. Preserve the fixed rule
for a broader existing seed/capacity A/B before promotion; continuing recruitment
and coexistence remain unqualified. No ecology, storage, weights or defaults
changed, and no firmware deployment follows from this host-only result.
The [full-panel reserve comparison](../benchmarks/garden-longevity/reserve-panel.md)
now broadens that fixed policy to 640 runs: all eight existing seeds, both layouts,
both capacities, five schedules and both drainage settings. Closing survivors
and durable parents improve in all four pooled capacity/drainage groups, with
no new extinction. This does not dominate per-world outcomes: crowded/off late
survivors fall at both capacities, variety is mixed, and controls still lack
sustained turnover. All 98 tests, 320 old-neural comparisons, forty prior focused
comparisons, 1,920 independent replays and 640 native frame checks pass. Keep the
gate experimental. Discuss applying the existing seed-site competition census
to adverse cases before changing vacancy/mortality rules or training. No roadmap
qualification milestone is closed by these exploratory aggregates.
The [crowded recruitment diagnostic](../benchmarks/garden-longevity/recruitment-sites.md)
now replays eight selected cases with full world/seed-site censuses. Mature seeds
are available, but 256-node regressions are storage-bound and 512-node regressions
instead face overlapping spacing, plant-slot, light and surface-water limits.
One observed vacancy releases 46 nodes that existing plants recapture without
a seedling. Better-performing comparisons prevent interpreting snapshot blocker
fractions as a causal ranking. All 105 tests and frozen outcome/replay checks
pass. Discuss exact germination-attempt telemetry around vacancies next; post-step
queries miss openings consumed earlier in the step. No ecology or policy changes,
training, firmware promotion or qualification checkbox follows from this audit.
The [actual germination-check audit](../benchmarks/garden-longevity/seed-attempts.md)
now adds a bounded host-only observer and replays the same eight closing windows.
All 61 births reconcile; 36 occur on steps with no remaining post-step opening.
Most sampled open steps instead have mature seeds at blocked locations. The
fixed 46-node vacancy has no allocation-blocked mature checks before incumbent
growth consumes it. All 113 tests, frozen hashes and frames pass. Discuss a
single-variable seed-bank capacity 8→16 comparison on the four 512-node runs
next, retaining actual survivor/durable-parent and parental-resource metrics.
That [8/16-seed comparison](../benchmarks/garden-longevity/seed-bank.md) is complete
as a guarded host-only capacity option. Three pairs gain closing day-survivors,
but one falls 13 → 4. The standout reserve pair gains 7 → 33 survivors and
0 → 16 durable parents while natural deaths rise 6 → 37 and final occupancy
falls 7 → 4. All 130 tests, frozen baseline/trace checks and 24 native replays
pass. Keep both capacities experimental; discuss lifetime/resource timing in
that high-turnover run before expanding the panel or training. No default,
firmware, model or qualification change follows from this small diagnostic.
The subsequent [offline turnover review](../benchmarks/garden-longevity/turnover.md)
finds that the standout population reproduces genuinely but loses most new
adults within a few days: 33 one-day survivors become 18 four-day survivors and
2/28 eligible eight-day survivors. All 31 closing energy deaths have an
underfunded sunset and no optional nighttime spending; 30 produce seeds during
their final day. Growth-only reserve protection does not govern automatic
reproduction. All 34 default host tests and the unchanged full-world audits
pass. Discuss one sunset-aware reproduction affordability intervention before
further tuning, promotion or training; no intervention is implemented yet.
That approved [seed-reserve A/B](../benchmarks/garden-longevity/seed-reserve.md)
is now complete as a host-only gate. The targeted sixteen-bank reserve case
improves closing natural deaths 37 → 8, energy deaths 31 → 1, eight-day survivors
2/28 → 5/13 and final living plants 4 → 7. Seed output rises 469 → 518; the eight
remaining deaths are seedlings, seven water-starved. The eight-bank counterpart
is entirely unchanged and other panel pairs are mixed/adverse. All 113 tests,
frozen controls, budgets, identities and 48 native frames pass. Two analysis
corrections preserve same-step bank-slot transfers and no-effect cases without
tuning the rule; failed bundles and explicit native-capture reuse remain recorded.
No promotion: discuss seedling water/root diagnostics, including adverse pairs,
and broader validation before further ecology changes or training.
The approved [offline seedling audit](../benchmarks/garden-longevity/seedling-water.md)
now covers all sixteen worlds and 199 closing offspring. Of 44 first-day deaths
involving water shortage, 41 never extend a root; the targeted seven spend
30–50 water on shoots and none on roots. All eight target first-day survivors
reach deeper soil. Three rooted failures and five rootless survivors elsewhere
remain explicit exceptions. All 36 default host tests pass; 39,658 exact live
budgets and frozen provenance checks pass. Next discuss bid/candidate replay and
a bounded early productive-root probe, keeping rain and prices fixed. This is
not a newly implemented policy, expanded training run or promotion.
That [wet-root bid/probe experiment](../benchmarks/garden-longevity/root-bootstrap.md)
is now complete. Four unchanged native replays confirm affordable wet roots lose
to shoots. One fixed late-activation host probe across eight paired gate-on
worlds reduces first-day water-involved deaths 33 → 3 and closing natural deaths
62 → 24. The target changes water deaths 7 → 0, natural deaths 8 → 2 and
sixteen-day survivors 4/10 → 5/8. One water-successful baseline case loses a
one-day survivor to energy shortage; three rooted water failures remain.
All 76 tests, fresh controls, full ledgers and eight new native frames pass.
No promotion or training: next discuss an allocation challenge suite retaining
energy tradeoffs and ongoing root/shoot balance, not another unconditional rescue.
The approved [allocation challenge](../benchmarks/garden-longevity/allocation-challenge.md)
is now implemented: six deliberately selected development cases, exact pre-birth
native world forks, individual-only candidate-model routing, four control arms,
eight-day follow-up and 96 milestone screenshots. All 82 tests, 12,308 frozen
reference samples and 18,816 live target budgets pass; capture/headless records
match. An explicit birth census corrects potential post-reclamation undercounting
without changing any world hashes or pixels. WAIT survives day one in 6/6 but
buys no growth and makes no seeds; early roots can rescue or damage a seedling,
and later ordinary investment succeeds in another case. No direct children
germinate in these continuations. This is infrastructure and an objective
diagnostic, not held-out qualification or a training run. Next agree on a
productive-persistence objective experiment using these opposing controls;
keep full-population/fresh-seed and durable-descendant validation separate.
The approved [objective dry-run](../benchmarks/garden-longevity/allocation-objectives.md)
now compares survival alone, capped raw seeds and capped confirmed productive
days on the unchanged six-case traces. WAIT leads every aggregate sensitivity
and leave-one-case-out ranking; productive versus inactive ties can be broken
within cases. A zero-shortage confirmation requirement erases all fifteen seeds
of an eight-day survivor, despite twelve observed full-day parent survivals after
purchases (three censored). The post-ranking audit distinguishes early severe
water stress from later short, recovered energy shortages. Arithmetic fixtures
also expose the additive bonus's late-collapse tradeoff. All 85 tests and frozen
score/input rechecks pass. No training objective is installed: discuss delayed
survival credit without a zero-shortage veto and the unresolved parent/descendant
tradeoff. No native experiment or environmental change was needed.
The approved [survival-confirmed rescore](../benchmarks/garden-longevity/allocation-survival.md)
now retains full-day parent survival without vetoing shortages. Five rescue
purchases span four confirmed age-day bins; twelve bank-16 purchases span six.
Both reach the unchanged cap and beat WAIT in their own cases. WAIT still leads
all ten aggregate variants and all sixty leave-one-out rankings. The revised
native scores equal raw-seed scores because both producers cap out; their
different semantics are demonstrated only by arithmetic fixtures so far.
At nominal weight, full credit offsets two days of lost parent survival in an
eight-day window. Day-bin boundaries also admit closely timed purchases in two
bins. All 88 CTests and exact old/new result rechecks pass. Keep this as an
allocation diagnostic: next connect it to actual day-surviving descendants
using existing longer-run lineage evidence, with reproductive opportunity and
censoring visible. No new training, ecology change or qualification milestone.
The approved [descendant-outcome join](../benchmarks/garden-longevity/descendant-outcomes.md)
now links purchases, exact germination checks and multi-generation lifetimes in
the eight existing 192-day histories. Closing purchases total 2,074, yielding
61 children, 48 day survivors and six of those with a day-surviving child of
their own. Eleven seedlings die naturally before confirmation, one is
patch-censored and one horizon-censored. A creation-time full-potential subset
keeps recent purchases separate. Thirty-one parents reach the four-bin
production cap without an established child; descendants can also establish
after their parent's death. All 91 CTests and full original-trace/lineage
rechecks pass. No scalar score is introduced. Next agree on a lineage-outcome
evaluation contract centered on established descendants and further reproduction,
with parent survival, opportunity and censoring kept explicit and separate.
The approved [lineage-fitness v1 test](../benchmarks/garden-longevity/lineage-fitness.md)
now implements an offline ordered score: terminal descendant presence, distinct
established renewing parents, newly established descendants, then descendant
occupancy. All 94 CTests pass, including 24 new scoring tests. The eight saved
histories split their four matched conditions two–two; baseline leads the
aggregate, but two leave-one-condition-out comparisons reverse it. Confirmation
timing includes three pre-window births, giving 51 establishments rather than
the earlier purchase cohort's 48. Synthetic challenges expose a preference for
many briefly established offspring over fewer longer-lived ones and one-sample
endpoint sensitivity. Seed-only endings remain unresolved and cannot be dropped
from a ranking. Keep v1 as a fixed candidate, not trainer adoption: next settle
that persistence tradeoff and deterministic seed follow-up, then a bounded
training/review pilot in one frozen environment. No policy promotion, new native
experiment or qualification milestone follows from these offline scores.
The approved [persistence v2 revision](../benchmarks/garden-longevity/lineage-persistence.md)
now puts observed recent offspring live time ahead of parent/establishment
counts. It fixes both one-parent and many-parent brief-offspring counterexamples
and defines a common two-day terminal follow-up; new seed-only continuation at
the deadline is explicitly unconfirmed. A matched 158–190 main-window control
keeps the new clock separate from the original v1 comparison. All 97 CTests
pass, including 28 new tests; full v1 and v2 reanalyses reproduce. Reserve now
wins three native pairs, while baseline narrowly leads the aggregate; removing
fresh-4 reverses it. The targeted score preference is improved, not a robust
policy selection or proof of sustained ecology. Propose a small fixed-v2
learning-signal pilot next, with one explicit host environment, separate
development/review seeds, exact scorer parity and archived generation models
and screenshots. No trainer/default/firmware change or qualification milestone
is included in this offline revision.
The subsequent [two-generation pilot](../benchmarks/garden-longevity/training-pilot.md)
now runs the fixed v2 rule natively in one explicit 512-node/bank-8 environment,
with unchanged-controller control and separate development/review seeds. All seven
candidate models, compact ledgers and generation 0/1/2 champions are archived;
18 native review screenshots match evaluator hashes and independent pixel replays.
The repeated search is byte/score/hash-identical. All 139 CTests pass, including
four configurations and exact C/Python scoring checks. One mutation improves
development renewal time 24.27% but loses 15.72% on the two review worlds overall;
one review seed improves while the other regresses. All endpoints retain established
descendants, but species/family retention is inconsistent. This completes the
bounded learning-signal/visual pipeline experiment, not environment qualification
or model promotion. Next discuss a predeclared broader paired evaluation of these
two frozen controllers across more world seeds and another patch schedule before
expanding evolution or changing the objective. The serial optimized host bundle
took 107.10 seconds and 18.14 MiB; no firmware buffers or device changes.
The approved [frozen-controller follow-up](../benchmarks/garden-longevity/pilot-validation.md)
now compares both unchanged models on eight additional world seeds and two
patch schedules, with 32 exact C/Python/final-replay matches and eight selected
native captures. The winner gains 4.45% aggregate renewal time but wins only
9/16 pairs; three leave-one-world-seed-out rankings reverse the result. Single-
species endpoints rise 7/16 → 12/16. Per-child attribution reconciles count,
confirmation timing and subsequent death; a largest-gain case correctly gives
no later-generation renewal credit to four direct founder offspring. All 143
CTests pass and the original pilot remains unchanged. This is selectable variation,
not robust controller promotion or environment qualification. Next discuss whether
coexistence is required before more training; otherwise use a multi-seed,
mixed-schedule development suite and a separate review panel in the next small
pilot. No native code, model weights or ecology changed in this follow-up.
The agreed next [mixed-condition pilot](../benchmarks/garden-longevity/mixed-training.md)
is now complete, keeping fitness unchanged and diversity diagnostic. Ten models
over three generations use four development seeds × two schedules, with four
different review seeds and 32 native generation captures. Final development
renewal improves 20.76%, while review loses 27.09% and 7/8 paired conditions;
both schedule aggregates and all blocked seed omissions preserve the contrast.
Review single-species endpoints remain 5/8, so diversity alone does not explain
the failed transfer. All 192 scores/repeat records and 32 frame repeats match;
147 CTests pass. A rejected mutation also yields independently replayed native
extinction evidence (seed-only continuation remains separate). No promotion or
qualification milestone: next discuss broader training-world coverage before
adding generations. No native ecology, fitness or device changes in this pilot.
The subsequent [coverage experiment](../benchmarks/garden-longevity/training-coverage.md)
retains the original four training seeds and adds four, with the same original
model, RNG, mutation budget and ecology. The first-generation models/common-world
outputs exactly match the prior run; added conditions reject its earlier winner.
The new final gains 13.22% on training but loses 8.22% versus original on four
fresh review seeds. Compared with the frozen narrow champion on the same review
worlds, its +0.95% aggregate margin has only 2/8 wins and reverses under two
blocked seed omissions. All 360 scored/repeated trials and 40 native images verify;
147 CTests pass, and the old profile/bundle remains unchanged. No promotion or
qualification milestone. Next discuss predeclared offline late-window stability
using existing lifetime records, not another automatic training expansion or
fitness change.
That [offline follow-up](../benchmarks/garden-longevity/window-stability.md) is now
complete: 160 projected scores from 32 existing histories, with five declared
equal-width windows and each window's own two-day follow-up. All three trained
controllers beat the original in the first three windows and lose in the last
two. Broad/narrow also changes sign. Exact adjacent-cohort accounting attributes
most of the largest broad/original reversal to children leaving eligibility;
the unchanged primary still records an 8.22% loss. Eleven new unit cases and six
relevant pure-Python CTests pass; no new native trials or training were run.
No promotion, new fitness or qualification milestone follows. Next discuss a
predeclared sustained-performance evaluation across time, including failure
rules, before another training expansion. Overlapping windows are not independent
replicates and must not be used to select a favorable endpoint after inspection.
The next [sustained-renewal candidate](../benchmarks/garden-longevity/sustained-renewal.md)
tests 32-day bounded-age live credit and four fixed non-overlapping periods using
only the existing 32 review histories. All 128 candidate/v2 cases verify; 17 new
unit tests and seven relevant pure-Python CTests pass. Credit is additive, cannot
reward old sterile survivors indefinitely, and favors steady replacement over
a large synthetic burst. However, taking the weakest period after pooling
worlds hides individual gaps: broad final leads with two zero-credit world-periods,
and narrow beats original only when schedules are pooled despite losing on each
separately. No adoption, promotion, new training, native trial or qualification
milestone follows. Next discuss an individual-continuity requirement before
pooling and its tolerated gaps; no alternative aggregation was installed.
The approved [individual-minimum follow-up](../benchmarks/garden-longevity/individual-renewal.md)
now reaggregates the same 128 unchanged cases. Summing each garden's weakest
period removes the timing benefit from complementary slumps: broad final is
16.76% below original, loses both schedules and all four blocked omissions.
The other trained/original margins are −1.82% (G2) and −5.11% (narrow), with
some omission reversals. All individual pairs and previous views are preserved.
A declared synthetic challenge still lets a strong garden compensate for a
sterile one: this is not an every-world continuity requirement. Fourteen new unit
tests and eight relevant pure-Python CTests pass. No fitness adoption, promotion,
new native trial or training. Next discuss whether sustained gaps are permitted
tradeoffs or should fail a separate reliability requirement before proceeding.
The [stall investigation](../benchmarks/garden-longevity/renewal-stalls.md) now
compares the two affected broad trajectories with original: 375 descendant seeds
expire without germinating in (62,94], while five founder offspring establish.
Spacing and the eight-plant cap dominate sampled blockers; both broad worlds
recover qualifying renewal at days 96.8/103.0. The original itself has only one
qualifying recruit per matched weak period, and one original history has a
32.86-day zero-credit gap crossing the fixed window boundary. Therefore no hard
calendar-gap viability gate is adopted. Forty fixed native processes verify
four census histories, 16 repeated images and four original endpoint anchors;
11 new unit cases and nine focused Python CTests pass. Next discuss a
recruitment-opportunity/recovery diagnostic that distinguishes usable openings,
competition and actual reproductive failure. No ecology, score, training,
promotion, device change or qualification milestone follows automatically.
The [exact recovery diagnostic](../benchmarks/garden-longevity/recruitment-recovery.md)
now resolves these stages using the existing sequential seed observer. During
the two broad zero-credit periods, sites are usable on 785 versus 12 ecology
steps; actual descendant seeds never qualify there, and no descendant loses
eligibility to an earlier seed in the same step. Both later recover, including
one recruit on the very first usable local step. Global slots couple separate
vacancies, and the current NN controls growth rather than direct seed aiming.
Keep renewal outcomes and recovery explanations separate: no opportunity ratio,
calendar-gap gate or new fitness is adopted. Any hard reliability requirement
needs a separately discussed fixed replacement challenge. Twelve native
processes match 65,536 seed steps, 129,028 world/site hashes and 730 old censuses;
13 new unit cases and ten relevant Python CTests pass. No training, model
promotion, ecological change or qualification milestone.
The [founder-independence challenge](../benchmarks/garden-longevity/founder-independence.md)
now removes the remaining founders at day 64, retaining ordinary decomposition,
soil, seeds, descendants and ongoing rain/patch schedules. Sixteen pairs are
exact no-ops because their founders were already gone; the other sixteen lose
37 founders. All actively challenged worlds retain established descendants and
produce new descendant-born full-day survivors (58 → 137 versus controls), with
further-generation links in 14/16 worlds. Removal also frees space and changes
competition, so this does not isolate those mechanisms or justify a permanent
death rule. Keep this as a separate diagnostic and return to bounded-renewal
objective/pilot discussion, not another hard gate. All 144 native processes,
24 independently repeated images, 54 default and 49 experimental CTests pass.
No training, model promotion, ecological change or qualification milestone.
The 16-bit moisture summary
intentionally saturates, so use actual cell totals. Separately, fix and test the
unsaturated living-plant age counter before
runs reaching 256 days; this unchanged-ecology comparison stops at 192.
No columns are permanently protected; small patches preserve most of the garden
at each event, without retargeting empty hits or assisting recovery. Discuss
these findings before adopting permanent ecology or expanding the neural contract.
No default rule, firmware
capacity change, training run or qualification milestone follows automatically.
Prior tools/experiments are checkpointed locally in `4f26187`; the node audit,
capacity/tip audits, maintenance experiment, competition census, gap assay and
recurring-disturbance experiment, longer-horizon diversity follow-up, water-budget
audit, bottom-drainage A/B and focused policy/resource comparison are subsequent
uncommitted work.

## Goal and order

Build a small autonomous ecology in which acquiring light/water, allocating
resources, surviving, reproducing, and decomposing have meaningful consequences.
First establish that the environment supports sustainable and varied behavior.
Then train controllers on the host and run frozen models on PicoSystem.
Continuous on-device controller evolution is a later experiment, separate from
the existing inheritance and mutation of plant traits.

The order is:

1. Qualify the environment, alongside a minimal model replay/screenshot bridge.
2. Define and validate the training objective.
3. Scale host training without changing its results.
4. Deploy and measure qualified controllers on the device.
5. Investigate inherited controller variation and unattended evolution.

Visual review is part of experiment evidence, not a final presentation task.
A full interactive training application is optional. Discuss substantial
ecology, observation/action, and objective changes before implementing them;
do not train around a known environmental or accounting defect.

## Foundations and current limitations

Available building blocks:

- deterministic shared host/device simulation, compact observations/actions,
  recurrent policy memory, and a fixed-point neural model interface;
- rain-fed environments with fixed startup resources and independent seeded
  weather, without gardener actions or ongoing scripted irrigation;
- matched evaluation, lifetime/cohort metrics, resource traces, and frozen
  experiment bundles with hash-verified selected replays;
- the production host renderer, native image output/PNG workflow, and an SDL
  player for existing scenes;
- serial evolutionary search and portable, CRC-protected final-model artifacts.

The [experiment workflow](garden-experiments.md) collects evidence; it does
not train. The trainer currently saves only the final model, with per-generation
fitness and fingerprints in its report. The normal scene player/image runner
does not yet load an arbitrary saved model under the exact evaluation setup.
The dedicated [visual-review tool](garden-visual-review.md) now supports exact
saved-model headless replay and timeline-verified screenshot galleries.

The initial local rain-fed baseline covered 48 trials (eight seeds, two
planting layouts, three policies) through 24 cycles, with six verified detailed
replays. Neural model `dc5e849d` ended nonviable in 3/16 runs; adaptive ended
nonviable in 0/16. This does not establish sustained descendant reproduction,
environmental balance, or learned generalization. The baseline lives locally
at `artifacts/garden-matches-baseline/`; it is ignored, not published evidence.
Preserve reproducible findings in versioned notes when accepting milestones.

## 1. Environment qualification

Create a small, versioned condition suite before running a large search.
Use deterministic weather/initial conditions, no gardener in scored runs, and
matched seeds for every policy comparison. Begin with controls varying light
and shade, water supply, and planting density, plus representative combinations.
Do not add unrelated biological systems simply to manufacture complexity.

Compare adaptive/reference policies with deliberately simple decision probes:
waiting, resource acquisition, growth allocation, or reserve behavior. A probe
such as conserving energy overnight tests a hypothesis; it is not automatically
a permanent rule or a feature that the neural controller must be handed.

Acceptance evidence must address:

- **Sustainability:** descendants survive full cycles and produce viable
  descendants of their own over multiple cycles and seeds. Founder longevity,
  raw birth count, and a nonempty final seed bank are insufficient alone.
- **Decision value:** matched interventions change measurable outcomes, and
  failures can be separated into environmental impossibility, insufficient
  observations/actions, and poor policy choices.
- **Pressure and variety:** resource access and crowding produce understandable
  tradeoffs rather than an always-winning scripted action.
- **Accounting:** rainfall, runoff, uptake, photosynthesis, upkeep, growth,
  reproduction, death, and reclamation have consistent declared semantics.
  Audit reset/seed-bank loopholes and capacity saturation. Current live-step
  resource checks do not reconstruct terminal budgets after death clears
  telemetry; close or explicitly bound that diagnostic gap.
- **Generalization:** conclusions use more than one fortunate seed/layout.
  Paired layouts sharing a seed are not independent statistical replicates.

Record hypotheses, suite version, seeds, horizons, acceptance criteria, numeric
outcomes, representative images, counterexamples, and remaining uncertainty.
Choose acceptance thresholds before selecting winning models, rather than
retrofitting a threshold to one attractive run.

## 2. Required visual review

### Minimum: screenshots of every generation's champion

A *search generation* is a trainer iteration, not a plant's biological
generation. Capture the initial model (generation zero) and the best-so-far
champion after every completed search generation. An unchanged champion still
gets an indexed gallery entry; identical model/image files may be deduplicated.

The first implementation should:

1. Persist the model, fitness, and generation identity before visual replay.
   Reconstruct evaluation worlds using the exact model, scenario, seed, weather
   version and horizon; do not substitute the playable scene's default policy.
2. Replay a small, fixed review panel. A reasonable initial panel is both
   rain-fed layouts at one predeclared review seed, with checkpoints in early
   daylight, after the first night, and late in the horizon. Clamp/deduplicate
   checkpoints for short test runs and record the actual ticks.
3. Render through the shared production snapshot/raster path, save native
   240 x 240 PNGs, and retain canonical framebuffer CRCs. Verify world hashes
   against equivalent headless evaluation; screenshot capture must not alter
   world state.
4. Generate a browsable contact sheet/gallery linking the native images and
   model. Label generation, model fingerprint, scenario, seed, tick/cycle,
   relevant survival/reproduction metrics, world hash, framebuffer CRC, and
   source/environment provenance. Nearest-neighbor enlargement can improve
   readability but must not replace the native capture.
5. Retain empty or failed gardens. Use the same review panel and checkpoints
   across generations so manual comparisons are meaningful, rather than
   selecting whichever frame makes each model look best.

Use dedicated, declared review seeds distinct from training and final test
seeds. Manual inspection informs model selection, so review images are not
untouched test evidence. Additional automatically selected successes/failures
are useful but must be labeled as selected examples, not an unbiased panel.

Capture on/off must yield identical training champions, fitness histories,
and evaluation hashes. Models passed to capture are immutable. Use bounded
queues and explicit retention limits; if rendering lags, retain replay jobs
durably or apply backpressure. Report pending/failed captures and never claim
the requested per-generation gallery is complete when entries are missing.

### Optional: real-time foreground viewing

Later, allow a normal-speed, pauseable/stepable foreground replay of a frozen
champion while background workers train headlessly at maximum speed. Keep a
model pinned for observation if desired, or adopt a new champion at an explicit
replay boundary. This is an independent, unscored observer world, not a slower
worker whose visual results influence fitness. Label its generation/model,
seed, and replay progress accordingly.

The renderer currently owns a process-global framebuffer. Give rendering one
owner, preferably a separate replay/capture process, rather than calling it
concurrently from training workers. Do not expose a live mutable worker world
to the viewer. Closing, pausing, or changing viewer cadence must not change
training decisions or seeds. Interactive experiments are separate from scored
runs. No streaming-video server or browser frontend is required initially.

## 3. Training objectives and experimental discipline

After environment qualification, select an objective that rewards sustainable
descendants rather than only short-term survival, raw births, or a brief
establishment gate. The existing training fitness and diagnostic replay-selection
order are different things; changing one must not silently change the other.

Define cohort denominators and follow-up eligibility for full-cycle survival
and reproducing descendants. Expose early deaths, recent births, extinction,
and available reproductive opportunity instead of hiding them in a single
score. Retain simple controls and matched before/after evaluations.

Specify training, validation, manual-review and final-test roles, seeds,
horizons, model/source identity, and stopping/model-selection rules. Audit
reward loopholes before scaling. Keep the final test set reserved until model
selection is over. Visual appeal is useful evidence but not proof of fitness.

## 4. Training throughput

Keep a dedicated optimized host-training build separate from safety-checked
correctness builds. Parallelize whole candidate evaluations first, leaving
individual worlds serial:

- generate mutations from the generation's fixed parent in canonical RNG order;
- give each worker its own worlds, observer counters, and immutable model input;
- select results in candidate order, preserving current strict-improvement
  tie behavior, independent of completion order;
- finish the generation before mutating the next parent.

Add a bounded worker-count option and verify identical champions, fitness
histories and hashes at 1/2/4/8/16 workers and with capture enabled/disabled.
Measure throughput, memory, queue pressure and rendering/diagnostic overhead;
do not assume hardware threads provide linear speedup.

A local three-repeat spot check on the Ryzen 7 9800X3D evaluated one frozen
neural model across 16 rain-fed worlds, each for 24 cycles: median 4.70 seconds
in the existing unoptimized UBSan build and 0.606 seconds in a separate Release
build. That is about 5,200x and 40,500x normal simulation pace, respectively,
not a host-versus-RP2040 maximum CPU benchmark. Build/container startup and
rendering were excluded; default/Release evaluation and trace outputs matched.
Formal saved scaling evidence remains a milestone, not a promised multiplier.

## 5. Device deployment

Load/integrate a selected saved controller and verify corresponding host/device
world states and intended pixels under matched supported conditions. Measure
PIM559 RAM, model flash use, inference/update deadlines, and physical behavior.
Host equivalence is not proof of device timing or USB/display reliability.

No host trainer, capture buffers, worker pool, or UI dependency belongs in
firmware. The first deployment target is autonomous ecology with fixed
controller weights, not on-device training.

## 6. Later inherited-controller experiments

Existing plant-trait inheritance is not neural-weight evolution. Separately
design bounded controller inheritance/mutation, model storage, and lineage
attribution. Use accelerated host runs to examine sustained viability,
diversity, and extinction before attempting unattended device evolution.
Persistence and recovery need their own resource and correctness decisions.

## Evidence and maintenance

Use issue #30 for milestone status and links to experiments, commits, and PRs.
Keep this plan synchronized when the design or acceptance gates change.
Promote important local-bundle findings into versioned notes without treating
ignored artifacts as remotely available. New phases are not permission to skip
discussion of substantive changes.

Related material:

- [Garden implementation contract](garden-simulator.md)
- [Matched experiment collection and replay](garden-experiments.md)
- [Host simulator and model search](host-simulator.md)
- [Lifetime and resource investigations](../benchmarks/garden-longevity/README.md)
- [General bring-up roadmap](roadmap.md)
