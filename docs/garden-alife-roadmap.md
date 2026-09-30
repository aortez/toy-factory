# Garden A-life roadmap

[GitHub issue #30](https://github.com/aortez/toy-factory/issues/30) tracks milestone
status and experiment notes. This document records the agreed direction,
acceptance gates, and design constraints. Update the issue with evidence as
work lands; it is the authoritative completion checklist.

The [recruitment checkpoint guide](garden-recruitment-checkpoint.md) defines the
current review scope, production/research boundary and outstanding limitations.
The [earlier foundation guide](garden-merge-checkpoint.md) records PR #31.
Consolidation does not close this roadmap or qualify the ecology. Further adult
resource tracing is follow-up work, not a requirement to keep expanding this PR.

PR #31 merged the foundation/research checkpoint. The immediate correctness
follow-up addresses age wrap and natural-death resource receipts; see
[long-run correctness](garden-long-run-correctness.md). The next implementation
adds [deterministic winter/drought and longer seed viability](garden-seasons.md),
with matched host controls and recovery checks. It supplies resource-driven
turnover, not a new branch-pruning action. Environmental qualification, seasonal
training objectives and durable diversity remain open.

The [seasonal v1 follow-up](../benchmarks/garden-seasons/README.md) adds explicit
seasonal controller evaluation/replay, ancestry and seed-bank diagnostics, a
fresh eight-year panel and one isolated shorter-drought comparison. The latter
fails its predeclared renewal-retention gate and is not promoted. Seasons support
real descendant reproduction, but diversity and spatial recruitment remain
limitations. This bounded implementation/evidence pass does not close the broader
qualification gates below; no new fitness or model is adopted.

The [seasonal recruitment follow-up](../benchmarks/garden-seasons/recruitment.md)
now observes exact germination checks in 32 matched normal-ecology worlds.
All 16 late seasonal worlds have usable space, but 5,014 of 5,038 open steps
have mature seeds without a successful landing. One isolated wider-scattering
screen improves late-birth worlds 8/16 → 10/16, day survivors 30 → 36 and durable
descendant parents 6 → 8. It passes the predeclared exploratory gates, but crowded
layouts regress and diversity remains 1/16 multi-species endpoints.
The [fresh eight-seed confirmation](../benchmarks/garden-seasons/dispersal-confirmation.md)
now passes the same aggregate gates: late-birth worlds 17/32 → 21/32, full-day
survivors 14 → 20, late durable parents 0 → 1 and historical parents 163 → 211.
However, four weather seeds lose late survivors, adaptive loses one, survival
fractions fall and all 32 seasonal endpoints retain just one viable species.
Keep narrow scattering on device. The
[saved-history offspring audit](../benchmarks/garden-seasons/offspring-outcomes.md)
now reconciles all 128 trajectories: 17/37 eligible wide late seedlings die
within a day (15 outside active drought/dim light), while 18/20 day survivors
have no germinated child recorded yet. Most non-durable late survivors remain
alive, and not every adverse seed block loses survivors through extra mortality.
The [fixed seedling-resource replay](../benchmarks/garden-seasons/seedling-resources.md)
now reconciles five selected plants across six matched worlds. The energy failure
spends 63 of its 74 available energy on growth before sunset; the water failure
spends 65 of its 76 water on growth despite abundant energy. Surviving examples
fund much more growth from income. All historical states, repeated traces and
resource budgets match; twelve rendered checkpoints are retained. The subsequent
[first-day reserve counterfactual](../benchmarks/garden-seasons/seedling-reserve.md)
rescues both failures through day 128 and retains the existing survivor. One
pre-existing parent dies later in the water treatment, with unchanged final
population counts and single-species endpoints. The water rescue also starts
with an energy veto, and the wet-root exception admits no otherwise-blocked bid.
The [fixed component comparison](../benchmarks/garden-seasons/seedling-components.md)
now separates the rescues: energy-only rescues #35; water-only rescues #41.
Neither alone rescues both, while #39 survives every arm. Energy-only merely
delays #41's water death; water-only has the same later founder #5 death as
combined. One wetter-root exception is exercised, without evidence that it is
necessary. All twelve runs repeat, legacy controls match byte-for-byte, and
no focal has a germinated child by day 128. The subsequent
[all-offspring screen](../benchmarks/garden-seasons/seedling-population.md) applies
the same combined rule to every new offspring in all 32 known-seed seasonal
worlds. It passes all nine aggregate gates: late day survivors 20/37 → 33/44,
late durable parents 1 → 2, historical durable parents 211 → 271. All 64 runs
repeat and saved controls match. But five worlds lose late survivors, two weather
blocks regress, and 31/33 late survivors have no child. Viable multi-species
endpoints rise 0 → 2 solely through banked shrub seeds; every endpoint remains
single-living-species, with no living shrub endpoint under treatment. The
[fresh reserve confirmation](../benchmarks/garden-seasons/seedling-confirmation.md)
now passes the same nine gates on eight new weather seeds: late full-day survival
38/71 → 55/62, late durable parents 5 → 6 and historical durable parents 276 → 285.
All 64 fresh runs repeat with unchanged native binaries/rules. Reproduction
remains uneven: ten worlds and three weather blocks lose historical parents,
ground-cover parents fall 112 → 100, and 48/55 late survivors have no child.
All fresh endpoints retain only one viable species, including the seed bank.
Next discuss a read-only saved-trace audit separating seed production,
germination and child survival before further tuning. No ecology, default, model
or qualification milestone is promoted; the adapter remains explicit and host-only.
The [read-only reproductive funnel](../benchmarks/garden-seasons/reproduction-funnel.md)
now follows all 3,892 seeds in the 64 fresh traces, including posthumous births,
and reconciles every established-parent cohort. Of 55 guarded late survivors,
35 never produced a seed, thirteen have pending seeds only, six have a
day-surviving child and one has a living youngster. Thirty-three of the 35
nonproducers had flower tissue; exact maturity/resources/bank eligibility is
not logged at the production decision. Equal-age views retain this production
gap without dropping parents that died. Next discuss a bounded host-only
production-gate observer with unchanged replay hashes, not another policy tweak.
The [exact production-gate audit](../benchmarks/garden-seasons/production-gates.md)
now replays the same 64 trajectories twice, matching every saved ecology state
and all 3,892 seed productions. The eight-slot bank is full in 5,947/5,999
ready-flower daylight/cooldown-clear visits for guarded late nonproducers.
Thirty-one of those 35 parents have a bank-only failed opportunity; two also
always lack energy during their windows, and two have no ready flower. The
observer is host-only and defaults remain unchanged. Next discuss a bounded
eight-versus-sixteen bank experiment with the same lifespan and resource rules,
measuring establishment, durable renewal, diversity and costs. No capacity
intervention or ecology qualification is claimed by this diagnostic.
The [isolated sixteen-slot screen](../benchmarks/garden-seasons/seed-bank-capacity.md)
now changes only bank capacity in the same 32 guarded seasonal worlds. Historical
durable parents rise 285 → 401 and late survivors 55 → 63, but late durable
parents fall 6 → 4 and the late survival fraction drops 55/62 → 63/73. It fails
two predeclared gates and remains an explicit host-only option. The larger bank
is full in 97.90% of closing post-step samples. Fifty-seven of 132 shared
incumbents die earlier, and shrubs have no viable endpoint; one flower/ground-
cover mixed endpoint appears. All 64 trajectories repeat, eight-slot controls
match the earlier confirmation byte-for-byte, and independent raw reanalysis
agrees. Measured native storage rises 160 bytes/world and 16 bytes/snapshot;
all 115 default and 117 older-research CTests pass, with unchanged firmware and
no flash. Next discuss saved-history bank ownership/residence, seed outcomes and
incumbent resource costs, not a larger capacity or promotion. Environmental
qualification and durable diversity remain open.
The [saved-trace bank diagnosis](../benchmarks/garden-seasons/seed-bank-diagnosis.md)
now follows all 4,966 seeds and matched resource windows for all 132 shared
incumbents, with zero new experimental trajectories. In the sixteen-slot arm, eventual
expiry consumes 60.69% of occupied slot-time; dry/spacing/light constraints dominate
retained mature seed samples. However, 805/1,368 births are posthumous and 472
germinations wait at least sixteen days. Family concentration improves somewhat,
while shrubs remain absent from the closing bank. Seven of 57 earlier-death
incumbents spend no more on seeds; all 21 later-lived incumbents spend more, so
extra reproductive spending is not an isolated causal explanation. Every budget
and seed interval reconciles, offline reanalysis repeats, and 116 default / 118
older-research CTests pass. The proposed drift follow-up was superseded by the
discussion of placement as an agent behavior: first connect branch geometry to
where its seeds land, without moving seeds after they land.
The [producing-flower origin screen](../benchmarks/garden-seasons/flower-origin.md)
now implements that mechanic as an isolated host option with no extra RAM. In the
same 32 guarded eight-slot worlds, births fall 1,009 → 839, historical durable
parents 285 → 265, closing durable parents 6 → 2, and closing survival 55/62 →
30/34. Four gates fail. Ground cover gains historical durable parents, while
flowers/shrubs lose them; no living coexistence is established. All 64 trajectories
repeat, base controls match prior evidence, raw reanalysis agrees, and 118 default
/ 119 older-research CTests pass. No default promotion, training or device flash.
This establishes a growth-to-placement consequence, not learned placement.
The [exact flower-site audit](../benchmarks/garden-seasons/flower-sites.md) now
observes all 3,576 saved purchases without changing a trajectory. In flower-origin
worlds, 1,310/1,710 purchases have only one eligible flower, including every flower-
species purchase. Another flower opens otherwise closed reach at 39 purchases;
373 have open soil outside every eligible flower's reach, and 967 have none open
anywhere at production. Cold/capacity exclusions barely change those classes.
However, 465 seeds in the globally blocked group later germinate and 145 offspring
become durable parents. Current-site blockage is not a safe release veto. All
observed traces repeat, every saved state matches, raw reanalysis agrees, and 120
default / 120 older-research CTests pass; the bounded host observer adds no world
or firmware RAM. No rule change, training, promotion or flash. Current purchase
snapshots do not establish a bound on learned growth, timing or lifetime fitness.
The [exact seed-wait audit](../benchmarks/garden-seasons/seed-waits.md) now follows
16,553,918 germination checks on all 64 unchanged trajectories. Of the 465
initially world-closed seeds that germinate, 345 need a spacing release through
verified dead-neighbor reclamation, but only seven germinate immediately at
that release. Water/light are the final blockers for 456; cold affects 215
earlier but never clears last. Median waiting time is 7.875 Garden days. Of the
342 expired seeds in that cohort, 244 never see spacing open after dormancy;
pending seeds remain censored. Moisture recovery coincides with rain in 178/179
final water crossings, without attributing exact cell-level water causality.
Solar movement and canopy changes remain confounded in shaded-light recovery.
All captures repeat, every original ecology hash matches, raw reanalysis agrees,
and 121 default / 121 older-research CTests pass. No core change or device flash.
Next discuss a compact landing-neighborhood observation contract: distinguish
slow establishment-space occupancy from fast water/light windows, reuse current
tip-local signals/solar context/memory, and define sensing/storage costs before
adding neural inputs or reproductive actions. No present-site veto, drift,
future-outcome observations or automatic promotion.
The [landing-neighborhood contract](garden-landing-observation.md) now specifies
eight signals for a stem tip and each growth endpoint: current spacing/dead-only
occupancy, water/light and four causal resource/opportunity traces. History is
anchored to soil columns and sampled once pre-growth, not once per tip query.
The proposed virtual sensor deliberately shares recent terrain history, separate
from the existing eight-byte private plant memory. Host and Cortex-M0+ layout
checks give 316 bytes per-world cache, a 52-byte packet and a weights-only NN
extension budget of 208 bytes. Thirteen design-reference tests exercise geometry,
joint history, query-order independence, reset and layout; all 122 default and
122 older-research CTests passed at that design-only checkpoint.
The subsequent [host-only shadow observer](../benchmarks/garden-seasons/landing-shadow.md)
now implements the cache/projector without changing policies or neural inputs.
Sixteen fixed 128-day worlds repeat exactly; all 524,304 saved world hashes and
160,477 bids match, and Python independently reproduces every trace update and
packet. Available candidate signals differ in 29,513 / 39,049 flower-origin
queries (75.6%), versus zero under base-origin; dead-only readings are rare and
absent in the closing window. World/snapshot storage stays unchanged; the
316-byte cache/52-byte packet layouts hold on ARM. Full host diagnostic timing
is 319.3 versus 233.8 ms for the declared 128-day case, including defensive
validation—not target timing or worst-case active-bid cost. Raw reanalysis,
124 default / 123 older-research CTests and the firmware build pass; no flash.
The [host-only versioned encoding](garden-landing-encoding.md) is now implemented;
[replay results](../benchmarks/garden-seasons/landing-encoding.md) retain all
802,385 encodings from the same 16 worlds. The legacy 77 bytes remain unchanged,
with a 49-byte extension supporting off/current/history and dead-only ablation.
Current-only distinguishes 22,626 / 39,049 flower-origin choices (57.9%), history
29,513 (75.6%); most added distinctions are small, with only fourteen extra
queries crossing a sixteen-count separation threshold. This is extension-only
variation, not information independent of the legacy inputs or useful fitness.
Native/reference repeatability, three unchanged 32-day legacy-controller worlds,
unchanged v1 model files, host/ARM layout and 126 default / 124 older-research
tests pass. The subsequent [host-only inference checkpoint](garden-landing-inference.md)
now implements the 1,416-byte extended model, explicit v1 import, separate
CRC-protected 1,448-byte file, bounded accumulators and complete cache-aware
run checkpoints. All 3,072 zero-extra decision comparisons and three 32-day
worlds match v1; 512 extended decisions agree with independent Python arithmetic.
Nonzero inputs demonstrably alter choices/memory, and six checkpoint continuations
repeat with world/cache rollback on errors. All 128 default / 124 older-research
CTests and focused wide/flower tests pass at that checkpoint.
The [subsequent replay/evaluation tools](garden-landing-tools.md) add explicit
TGL2 reference/import/inspect/replay commands, exact retained lifetime accounting,
and matched fixed-checkpoint screenshot bundles with independent repeats and
frozen-binary verification. Models fix their masks; loading never overrides
them. No new fitness score is introduced at that checkpoint.
The [bounded landing training pilot](garden-landing-training.md) now connects
complete audited lineage/seed histories to the existing individual-minimum
renewal objective, adds deterministic extended-model mutation and saves every
generation with separate review worlds and screenshots. Its
[fixed protocol](../benchmarks/garden-seasons/landing-training-protocol.md)
limits the comparison to 63 candidate evaluations across three masks and three
search seeds, followed by an exact capture-free repetition. The player, old
trainer, firmware and ecology defaults still use unchanged paths. Pilot evidence
must be reviewed before any longer search, objective adjustment or promotion.
The [completed pilot](../benchmarks/garden-seasons/landing-training.md) repeats
exactly with capture disabled. Current-only finalists pass all 16 review
endpoint checks in all three searches, versus zero of three off/history
finalists, but still leave 7–9 of 16 review windows without credited renewal.
No mode sustains credit in every window of every review world.
The [completed broader validation](../benchmarks/garden-seasons/landing-validation.md)
retains all nine training-selected finalists across four additional seeds:
19 labeled variants (18 distinct files), 304 primary worlds and 76 review frames.
Its [explicit ablation tooling](garden-landing-validation.md) changes only the
stored mask and outer CRC, never weights. All three current-only finalists retain
established descendants at all 64 endpoints, but 32–33 windows still earn zero
renewal credit. Same-weight current inputs improve two finalists' aggregate
results and worsen one; removing only history hurts all three history-trained
models, while removing all added inputs helps two. Results and every screenshot
repeat exactly, including independent frozen verification. No reselection,
training, promotion or device change. Next proposal: separate signal groups and
fixed-value controls to distinguish environmental information from activation
shifts before expanding training. Steady-climate renewal remains particularly weak.
The [completed signal-content probe](../benchmarks/garden-seasons/landing-signals.md)
now runs those controls: three unchanged current-only finalists, ten probes,
16 reused conditions, 480 primary worlds and sixty fixed review frames. Live
and neutral controls match the prior trajectories; exact one-worker repetition
and frozen verification retain every result. Some fully fixed added inputs
match survival and improve aggregate credit, but hide individual losses and
steady-world stalls. This weakens a simple information-use interpretation of
the earlier zeroing result, not a reason to discard sensing. No steady world
in any probe earns credit in all four windows. All legacy sensing and role
gating remain, and water/light were tested jointly. No training, reselection,
ecology/default change or promotion. Next discuss a bounded same-state decision
trace to separate individual signal contributions and activation shifts before
another training budget. The fixed protocol is exhausted; do not tune constants
against this panel.
The [completed same-state decision trace](../benchmarks/garden-seasons/landing-decisions.md)
now records 135,839 policy queries, samples 1,992 decisions and checks all 31,872
native probe outputs with independent integer arithmetic. The 48 original live
results and raw traces repeat exactly, including frozen verification. No probe
changes action category in the 976 sampled stem decisions, but rankings,
priorities and next memory can change. Added light weights are absent in one
controller; another's common-water unit stays at zero despite changed sums.
Raw-neutral water 128 is outside all observed common-water ranges. This explains
some activation shifts, not useful adaptation, and does not qualify the
environment or controllers. Full root/stem, phase and condition evidence is
retained. Next discuss a small matched live-versus-fixed-input training pilot
with equal capacity and a predeclared comparison panel; do not change encoding,
ecology or device defaults automatically. No training or promotion in this pass.
The [subsequent matched live/fixed-input training pilot](../benchmarks/garden-seasons/landing-controls.md)
uses the unchanged current-only architecture, initial model and paired mutation
budgets: 42 candidates, 368 scored runs and 72 generation-review images. All
earlier live-search candidates and trajectories reproduce. On four unused
evaluation seeds, live beats fixed in one of three paired aggregates and loses
two, failing the predeclared replication/climate gate. The old live finalists'
established endpoint coverage falls from 64/64 on the previous panel to 40/64,
48/64 and 56/64; fixed inputs are not a general solution either. No steady world
has credit in every late window. Full one-worker/capture-free repetition matches
exactly. Next discuss a bounded multi-seed training panel with fresh evaluation
seeds before increasing model size or extending the single-seed search. No
controller, encoding, objective, ecology or device change is promoted.
Independent frozen verification also reproduces all model bytes, scored runs
and 72 generation-review frames. Portable records and score/selection/pixel
regression checks retain both successes and failures.
The [bounded five-seed follow-up](../benchmarks/garden-seasons/landing-multiseed.md)
is now complete: the same 42-candidate budget with 20 training conditions per
candidate, followed by old/new finalists on 16 shared fresh conditions. Broader
live training wins two of three aggregate comparisons through terminal-tier
gains and loses one; fixed training loses two and ties one. All five changed
finalists have less weakest-window renewal credit. Neither breadth gate passes
(live 6/9, fixed 0/9); the secondary multi-live/fixed gate also fails (8/9).
No steady world under any evaluated variant has credit in all four windows.
The 1,136 scored worlds repeat exactly with one worker/captures off; independent
frozen replay reproduces all model bytes, records and 72 images. Full portable
ledgers, matched comparisons, mutation/selection/pixel regressions and an
independent replay receipt are retained. No larger network, longer training,
score/ecology change or promotion. Next discuss a bounded saved-ledger diagnosis
of survival gains versus renewal losses before allocating another search budget.
The [saved-ledger renewal audit](../benchmarks/garden-seasons/landing-renewal-audit.md)
is now complete: all 224 evaluated histories / 896 late windows re-score
unchanged, with exact repeated and independent frozen analysis and no native
calls. All 390 persistent-but-zero windows have seed purchases, but some only
from founders. The improved live / 34 and / 35 each have 26 such steady windows:
208 carried-in seeds expire in each, while their 3 and 14 new seedlings die
before first-day establishment. Pending 32-day seeds are not failures.
Aged-out descendants and founder children explain surviving occupancy without
fresh renewal credit. All five changed finalists have fewer eligible
child/window intersections in their own weakest windows; this is exact
accounting, not a causal intervention. The ledger cannot distinguish moisture,
light, spacing or capacity blockers. Next discuss a small matched germination
and first-day seedling trace, retaining successful/regressing controls, before
changing the environment, objective or training budget. No promotion.
The [matched recruitment trace](../benchmarks/garden-seasons/landing-recruitment-trace.md)
now covers twelve fixed old/new live cases. All 192 late-expiring steady seeds
are spacing-blocked at every mature check, with overlapping moisture/light
failures and no plant/node capacity blocks. Open columns occur elsewhere for
all 343 late expiries across both climates, but parent reach is not established.
Among 127 late-born children, 55 establish and 72 die: 43 water-only, 22 energy-only
and seven combined. Exact first-day budgets separate initial stores, uptake,
overflow, upkeep, growth, reproduction and discarded resources; all reconcile.
Historical results/scores, untraced controls, repeated traces and independent
frozen replays match. Bounded host-only instrumentation adds no authoritative
state or policy inputs; 141 UBSan host tests pass. Next inspect placement
opportunity versus actual dispersal reach before a placement-only comparison,
keeping first-day resource policy separate. No ecology/score/model promotion.
Environmental qualification and durable diversity remain open.

The [parent-specific reach follow-up](../benchmarks/garden-seasons/landing-reach.md)
is complete on the same twelve unchanged worlds. Of 192 late-expiring steady
seeds, 170 have every reachable column spacing-blocked at every mature check;
only 22 ever have reachable alternatives. Seasonal alternatives occur for
80/151 seeds; 44 are persistently spacing-blocked across their whole support.
Only six steady and 21 seasonal expired seeds have open reachable alternatives
at purchase. Reflection often reduces six choices to three distinct columns.
Parent traits are captured at purchase rather than inferred from mutated seeds.
All 806 purchases and 4,592,849 events reconcile, prior traces match byte-for-byte,
and repeated/untraced/independent frozen replays preserve results and scores.
Next discuss a placement-range-only A/B using the existing wider-scattering
candidate, fixed model bytes/ecology/score otherwise, retaining contrary cases
and measuring renewal and first-day survival rather than germination alone.
No intervention or promotion yet; resource management remains separate.

The [fixed-model narrow/wide screen](../benchmarks/garden-seasons/landing-range.md)
is now complete and fails the predeclared gates. The 24 paired worlds preserve
the ordinary histories, unchanged scoring, model bytes and initial biology.
Late births rise 127 → 268 but survivors only 55 → 60; first-day deaths rise
72 → 208. Steady survivors and credit worsen, while one seasonal window loses
all established descendants, lowering its primary tier despite more total
credit. There are five paired score wins and seven losses, with no new empty
world. The existing wide option also changes range-aware observation projection;
this is not a physical-placement-only intervention holding neural inputs fixed.
All 24 final screenshots and complete budgets are retained. Keep narrow defaults;
next discuss a bounded first-day establishment/resource-allocation experiment
under ordinary ecology, not another range tune or a combined intervention.

The [first-day allocation diagnosis](../benchmarks/garden-seasons/landing-establishment.md)
uses those saved ordinary traces without native runs. Water-only deaths almost
never expand roots (42/43); their growth-water spending is overwhelmingly on
shoots (2,050/2,070 units). A fixed one-eighth-day comparison, before any death,
retains the root/survival association and its exceptions. All 29 energy-related
deaths occur in the dark, a distinct timing problem. Proposed next: the existing
water-only first-day reserve probe, with its wetter-root exception, on the same
frozen controllers and ordinary ecology. Preserve priority/memory semantics,
measure unchanged renewal and survival by climate, and retain possible stalls
and regressions. No intervention is implemented or promoted by this diagnosis.

The [water-only reserve screen](../benchmarks/garden-seasons/landing-water.md)
now completes that comparison and fails its gates. Late survivors rise 55 → 60,
but steady survivors fall 4 → 1 and a seasonal day-128 checkpoint loses all
established descendants. Both climate score keys worsen. Water-only deaths
fall 43 → 28 while energy-related deaths increase; cohorts diverge, so these
are not individually matched rescues or conversions. Of 1,282 selected guarded
WAITs, 680 have a funded wetter-root alternative that loses arbitration. The
adapter intentionally preserves refused-bid priority and winner-only memory.
All controls, traces, pixels and budgets repeat; independent frozen verification
and 148 ordinary host CTests pass. Retain the host-only probe and its negative
evidence, not a default change. Next discuss saved-receipt arbitration stalls
before any separate policy comparison; keep energy timing and retraining apart.

The [offline refusal-streak diagnosis](../benchmarks/garden-seasons/landing-stalls.md)
now resolves those 680 opportunities into 174 finite streaks, with median two
decisions and maximum 25. Immediate continuation is root growth in 66, shoot
growth in 70, or continued WAIT without a funded wetter root in 38. Of 77
affected children, 38 survive and 39 die; 73 first encounter the conflict before
root expansion. Fifty-nine grow roots afterward, but 21 of those still die.
All five affected steady children die, without establishing a causal rescue.
All 262 late-child histories and resource budgets recompute, with eight new
offline tests; no new policy or experimental trajectories. Proposed next:
eligibility-aware arbitration using unchanged reserve thresholds and normal
priority/ties among remaining bids, genuine WAIT handling and winner-only memory.
Do not force roots or combine energy/timing changes; agree the bounded comparison
and fallback semantics before implementing.

The [eligible-arbitration comparison](../benchmarks/garden-seasons/landing-arbitration.md)
now implements that single host-only change with a versioned probe identity and
all-bid receipts. Highest-priority eligible proposals win; genuine WAIT remains
eligible, and all-refused fallback preserves the original winner's memory.
Late survivors rise 60 → 62 and water-only deaths fall 28 → 8, but births fall
135 → 101 and the seasonal renewal key regresses. Both baseline comparisons
fail: ordinary steady survival remains four versus one, and a new seasonal
single /34 day-128 gap replaces the veto's single /35 gap. There are 252 changed
late selections: 114 root extensions and 138 genuine WAITs. No eligible bid is
left unused by a forced fallback. Exact controls, repeated traces/pixels,
independent frozen verification and 151 ordinary host CTests pass. No default
or device promotion. Next inspect saved histories around the gap and opposing
/35 outcomes to separate seed
supply, establishment and older-descendant loss before another intervention.

The [offline turnover diagnosis](../benchmarks/garden-seasons/landing-turnover.md)
now separates those cases across all 24 histories and 96 periods. Single /34's
day-128 gap is 2.0391 days with seeds continuously present: old plants die,
three recruits fail energy-related, and the next wave establishes after the
checkpoint. Even rescuing the first wave would confirm too late under its
observed birth times. Adult death resource causes are not recorded. Single /35
has a 41.3164-day birth-to-birth interval despite 7–8 banked seeds; five complete
seed lifetimes are always spacing-blocked. Multi /35 instead shows repeated
seedling failures under the veto. Eight tests and an independent sampled oracle
validate gap/credit accounting, censoring and immutable inputs. No new native
runs, policy or scoring changes. Proposed next: read-only adult resource and
concurrent seed-blocker traces on the frozen single /34 pair, with trace-off
parity, before choosing another intervention.

Research checkpoint: the [read-only topology census](../benchmarks/garden-longevity/renewal-topology.md)
finds only zero or one conservative terminal-shedding candidate at each of eight
fixed snapshots. At the full endpoint, 136 of 146 exhausted leaf nodes support
descendants; just one is eligible, and none is eligible and zero for a full day.
Simple terminal shedding is not a meaningful storage fix here. Close this bounded
investigation without a pruning policy and consolidate the branch for review;
substantial structural turnover needs a separate design discussion. Environment
qualification remains incomplete, not a prerequisite for merging a clearly
scoped foundation/evidence checkpoint.

Status as of 2026-09-23: foundation tools and the saved-model screenshot/gallery
bridge exist, checkpointed locally in `a1c419f` on `green-garden`, followed by
founder-independence in `bbb6307`. The subsequent bounded-renewal training A/B
and independent replication, followed by frozen-model transfer, 8/16-world
coverage and frozen-finalist return comparisons, plus the offline cohort audit
and eight-day startup diagnostic, reciprocal founder-controller swap and
single-neighbor follow-up, fourth-seed counterfactual, offline seed-forecast audit
and the fixed phase-aware shadow forecast, exact dark-budget audit and native
dark-spending-guard comparison, frozen four-world 64-day panel, residual-death audit
and two isolated purchase vetoes, followed by the retry-aware FINISH diagnostic
and its saved-trace recruitment and full-night capacity shadow audits, followed
by the bounded full-night growth-guard A/B, rescued-parent seed audit and
controlled named-gap comparison, its exact germination-check trace and isolated
post-gap wet-germination A/B, its saved-trace seedling-budget diagnostic and
bounded dawn-FINISH deferral, reserve-aware handoff and saved-trace reproductive
access audit, followed by post-noon rotating purchase-order and spacing A/Bs
and the saved establishment-light audit, fractional-canopy A/B and saved
allocation-blocker audit, eight-versus-sixteen admission A/B and saved
node-pressure/incumbent-death audit, bounded full-pool action A/B and saved
shedding-feasibility audit and bounded read-only topology census,
are complete and uncommitted; neither checkpoint was pushed by the agent.
The replication does not reproduce the initial objective
advantage. Broader coverage gives modest gains on one review panel but does not
uniformly repair the earlier failure cross: R1 W/N loses 7.73%, R2 gains 8.89%
with seed sensitivity, reduced fresh late credit and worse species retention.
The offline audit separates timing/mortality tradeoffs and early species losses:
five of R2 W's seven eventual monocultures are present before scoring starts.
The startup trace now identifies overnight adult energy exhaustion and a separate
water-starved shrub seedling. N's surviving founder shrub stays below an upkeep
step that W crosses. The reciprocal swap now shows that only the N/N combination
survives: N in W has lower sunset reserves despite small size, while W in N dies
and also changes its neighbors' fates. The single-neighbor follow-up finds
separate income and automatic-seed-spending paths to early death, plus one
later failure and one surviving swap. The targeted fourth-seed veto rescues
the observed shrub through day eight, but transfers the available bank slot
and 48-energy expense to the ground-cover, which dies earlier. The offline
forecast audit now finds that the existing gate would allow the shrub purchase:
it predicts 224 sunset energy versus 187 actual, missing the quantized light
cutoff. It would reject the ground-cover purchase. Separately, the full
zero-income interval requires 259/296 upkeep energy for these bodies versus
256 storage, so transient shortages cannot simply be forbidden. The subsequent
phase-aware shadow forecast improves sunset estimates across all 112 purchases,
but later spending breaks 103 windows' assumptions and even unchanged-body
prefixes have large morning errors. It is not a qualified survival gate. The
subsequent exact dark-budget audit avoids those estimates: all 66 complete clean
outcomes match, including shortages that remain survivable through the interval.
Of nine expense records crossing the local fatal boundary, seven are growth and
two seeds. The subsequent [host-only dark spending guard](../benchmarks/garden-longevity/renewal-dark-guard.md)
now changes deaths 12 → 0 in the fixed eight-day comparison and retains all five
founders and all three species. Births fall 14 → 2, though, and neither guarded
descendant produces seeds. Only one growth attempt and eight retries of one
FINISH are rejected; no seed/renewal denials occur. All 637 native forecasts,
the exact old control and twenty fixed calls/repeats verify. This is a survival
gain in one selected world, not qualified generational renewal. The subsequent
[frozen four-world, 64-day panel](../benchmarks/garden-longevity/renewal-dark-panel.md)
now reduces natural deaths 45 → 21 without patches and 51 → 33 with patches,
but the patched `abf7af73` pair worsens 13 → 17. Patched closing births improve
9 → 11 and full-day survivors 7 → 9, while whole-run durable descendant parents
fall 18 → 11. Both unpatched arms have no closing births despite continuing seed
production. Guarded three-species endpoints improve 0/4 → 2/4 in each condition,
not universal coexistence. All 128 fixed native calls, 32,536 guard forecasts,
48 repeated frames and full repeated analysis verify; 70 default and 67 control
CTests plus both guard suites pass. Of 397 denials, 184 already have a fatal
projected budget before spending; all are growth/FINISH, with none for seeds or
renewal. That [offline mortality audit](../benchmarks/garden-longevity/renewal-dark-failures.md)
now finds 35 guarded energy deaths already projected fatal at dark entry, 15
energy deaths just beyond the forecast and four water deaths. All 35 in-window
death times match exactly; 31 lack reserves that would fit in storage, while
four bodies cannot survive the interval even at the cap. The adverse patched
world adds four under-reserved flowers and one post-dawn shrub death after day
16. Last-daylight receipts isolate a 32 → 33-node extension and a paid FINISH
as specific mechanisms worth testing, not yet proven rescues. All 7,689 windows,
1,100,869 valid-prefix comparisons, repeated analysis and 71 host CTests pass;
no new experimental native calls. The subsequent
[isolated purchase comparison](../benchmarks/garden-longevity/renewal-purchase-veto.md)
rescues flower 21 through day 64: its extension is deferred until affordable,
it makes 34 seeds and has one long-lived child. The FINISH veto only delays
payment one ecology step; flower 22 dies at the same tick. Extension lowers
natural deaths 17 → 14 and raises durable descendant parents 5 → 6, but loses
shrubs (three endpoint species → two), lowers living exposure and adds a late
natural death. Control and FINISH endpoints match. All 24 declared calls,
exact prefixes/repeats, 13,405 forecasts, 374,175 live budgets, nine native images
and 72 default CTests verify. The subsequent
[retry-aware FINISH diagnostic](../benchmarks/garden-longevity/renewal-finish-retry.md)
now refuses both remaining uncovered attempts and hands back to the unchanged
guard. Flower 22 survives through day 64, produces 29 seeds, and has four
offspring (two die young, two survive a full day and remain alive). FINISH pays
after dawn at 72,210, and stress recovers to zero at 72,540. Whole-world natural
deaths rise 17 → 21, full-day survivors 16/25 → 18/31, and durable descendant
parents 5 → 7. Shrubs disappear, living exposure falls 1.94%, and closing natural
deaths rise 0 → 1. Neither pre-existing neighbor lifetimes nor the old control/
one-shot outcomes change. All 24 calls, 13,780 forecasts, 372,464 live budgets,
nine repeated native images and 73 default CTests verify. The subsequent
[offline recruitment audit](../benchmarks/garden-longevity/renewal-recruitment.md)
now accounts for the death delta: one saved old flower versus five additional
later offspring deaths. Post-intervention births rise 8 → 13, but full-day
survivors rise only 6/7 → 7/13; all six retry deaths occur before a day and enter
the dark interval already projected fatal, with exact predicted timing. Four
are under-reserved; two exceed what full stores can support overnight. All 46
new shrub seeds expire, and every mature snapshot is spacing-blocked. The
rescued flower occupies the control replacement shrub's column-20 site;
the original shrub's patch death is unchanged, and its final seeds expire at
134,820. Post-step blockers are not decision-stage receipts. All 1,053 seed
purchases, 249,557 mature observations, 247,501 live budgets and 74 default
CTests reconcile, with zero new experimental native runs. The subsequent
[full-night capacity shadow audit](../benchmarks/garden-longevity/renewal-night-capacity.md)
now covers all 16 panel trajectories and the retry case separately. With 37
upkeep payments and seven survivable shortages, the 64 → 65-node transition
raises minimum reserves from 240 to 270, beyond the 256 cap. Four first paid
crossings identify four guarded energy deaths; one complete lifetime is shared
between conditions, leaving three distinct histories. Forty-four subsequent
unsafe extensions are not separate rescue opportunities. Fifty of 54 guarded
deaths and all 96 control deaths remain unflagged. The retry case flags children
28 and 34, not the four smaller under-reserved early deaths. All 2,077,277 live
resource checks, exact repeated analysis, frozen source/capture hashes and 75
default CTests pass. No rule is enforced or new experimental native run made.
The subsequent [full-night growth-guard A/B](../benchmarks/garden-longevity/renewal-capacity-guard.md)
now rescues two targeted plants through day 64, while the third dies six
simulation seconds later: its 64-node body could survive at full stores, but
enters night with 237 energy against a 240 minimum. The two survivors make 43
seeds with no offspring. Across the four selected worlds, natural deaths fall
32 → 29, births 60 → 57, full-day survivors 43/58 → 40/55, and durable descendant
parents 9 → 8. Closing births/survivors and species sets do not improve. The
new guard refuses 7,895 attempts on three plants; those plants never commit
another EXTEND/FINISH, though the two survivors maintain leaves and reproduce.
All 64 fixed calls, exact rebuilt controls, isolated prefixes, 964,282 resource
budgets, repeated analysis and 24 native images verify; 76 default, 73 control
and 74 treatment CTests pass. The negative control is unchanged throughout.
The subsequent [rescued-parent seed audit](../benchmarks/garden-longevity/renewal-rescued-seeds.md)
now finds 40 expired seeds, three pending and no germinations. All 10,171 mature
observations have a pre-existing living spacing occupant, independently of
post-step light/water masks. None relies on dead tissue or self-spacing. The
shrub's entire dispersal support, columns 3–9, is excluded by two surviving
founders. All 2,060 seeds and 500,004 mature snapshots in the four traces
reconcile; repeated analysis/portable checks and all 77 default CTests pass.
No new experimental native calls or behavior changes occurred in that audit.
The subsequent [controlled named-gap comparison](../benchmarks/garden-longevity/renewal-controlled-gap.md)
exports founder flower 1 at day 12. It enables one new shrub to germinate and
survive through day 64, but founder shrub 2 wins the opening, not rescued shrub
7. The latter produces 20 seeds versus 15 without a child; two reach spacing-free
columns but expire with light/moisture blockers throughout their mature snapshots.
Whole births rise 4 → 5 and full-day survivors 3/4 → 4/5, with natural deaths
unchanged at two and one explicit export. One flower family disappears; closing
births and durable descendant parents remain zero. All 24 fixed calls, unchanged
controls/prefixes, 1,025 seeds, 221,701 live budgets, eight repeated native images,
portable checks and 78/76 default/experimental CTests verify. The subsequent
[exact germination trace](../benchmarks/garden-longevity/renewal-germination-trace.md)
confirms no wet-and-lit overlap across the two seeds' 496 mature checks, despite
free spacing/capacity. Their water-only/light-only/both tallies are 41/91/116 and
37/96/115; the successful founder seed has moisture 34 and light 97 at its first
eligible check. One post-step mask differs after growth, without changing the
failed outcome. Four exact repeated calls, 1,044 saved-state checkpoints, 8,336
ordered visits, portable verification and 79/77 default/experimental CTests pass.
The subsequent [post-gap wet-germination A/B](../benchmarks/garden-longevity/renewal-wet-germination.md)
now removes only the immediate light gate after the same day-12 export. Post-gap
births rise 1 → 5 and full-day survivors 1/1 → 3/5, but four treatment recruits
die of energy shortage. Rescued shrub 7 has two children; one lives 2.555 days,
neither produces seeds. Historical full-day descendant parents with a full-day
child improve 0 → 1, but there is no enduring new family branch. Both arms
finish with seven living plants, the same species/family counts and one living
post-gap recruit. All 31,744 actual mature seed checks in each closing window
are spacing-blocked; births remain zero. All 28 fixed calls/repeats, 1,027 seed
lifetimes, 220,984 resource budgets, eight native images, portable verification
and 80/79 default/experimental CTests pass. The new rule is explicitly host-only,
disabled on reset and off in normal builds; it is not promoted. Next discuss a
read-only comparison of the first few nights of all six post-gap recruits,
separating startup timing/spending from later growth and maintenance failures.
The [seedling budget diagnostic](../benchmarks/garden-longevity/renewal-seedling-budget.md)
now finds that both early deaths have zero recorded photosynthetic income:
64 startup energy becomes 28/36 and 32/32 growth/upkeep, with adequate water.
Both later deaths survive darkness but fail the first dawn maintenance at
stress 7. One survivor tolerates an extra shortage; the other earns enough dawn
income to pay immediately. All six fixed three-day/death histories reconcile,
including 3,183 live budgets, four unreconstructed terminal steps and 15 dark
windows. All 25,156 focal live steps through day 64, repeated portable analysis
and 81/80 default/experimental CTests verify, with zero new experimental native
calls or rule changes. Next discuss an isolated, retry-aware deferral of child
12's last eight-energy FINISH through the first dawn maintenance, before any
general dawn-margin policy or reserve increase. This is not yet a demonstrated
rescue or a solution to the separate startup/spacing failures.
The [bounded dawn-FINISH test](../benchmarks/garden-longevity/renewal-dawn-finish.md)
now postpones death by one maintenance interval, 68,340 → 68,400, rather than
rescuing the target. Ten refusals keep eight energy through dawn; after release,
the pending FINISH spends eight of nine energy at stress 7 just before upkeep.
No target seeds or offspring result, and day-64/closing population counts do
not improve. All 24 fixed calls, exact old control and transaction prefix,
221,022 live budgets, eight native images, portable verification and 82/82
default/experimental CTests pass. Next discuss a bounded reserve-aware handoff
for this same FINISH: pay only while retaining one maintenance bill, with a
first-noon endpoint. No resource grants, broader policy, retraining or promotion.
That [reserve-aware handoff](../benchmarks/garden-longevity/renewal-dawn-reserve.md)
now rescues shrub 12 through day 64. Three additional refusals retain one upkeep
bill; FINISH pays eight from 19 at 68,445, leaving 11, and stress recovers at
68,760. Forty-six later nights still cause survivable stress. Its only seed
expires without offspring; the two later seedlings in the old runs never appear.
Births/deaths fall 9/6 → 7/4, full-day survivors 6 → 4 and reproducing-descendant
credit 1 → 0. Final living/species/family counts and zero closing births remain
unchanged. All 36 fixed calls, exact historical/prefix/repeat checks, 331,756
live budgets, twelve native frames, portable verification and 83/83 normal/
experimental CTests pass. Next discuss a read-only reproductive-opportunity and
bank-access audit of these saved trajectories. This is one selected causal
rescue, not a qualified general gate or an ecosystem-renewal improvement.
The [reproduction-access audit](../benchmarks/garden-longevity/renewal-reproduction-access.md)
now identifies a separate allocation constraint. On 259 closing checks, rescued
shrub 12 passes every independently observable prerequisite: 189 start with a
full seed bank, and on 70 earlier parents take the available slots. The final
safety guard remains unevaluated on those turns. Every one of 128 closing
expiries is replaced immediately, with no germination; the target's sole
lifetime seed is spacing-blocked by established shrub 9. All 331,756 live
budgets, 1,541 purchases, repeated offline/Docker checks and 84/84 default/
experimental CTests verify, with zero new experimental native calls or rule
changes. Next discuss a bounded, deterministic rotating purchase-order A/B
after first noon, preserving all costs, gates and capacity. Allocation access
and establishment are separate outcomes; more purchases cannot stand in for
survival or durable descendants. This proposed ordering change is not yet built.
That [rotating-order comparison](../benchmarks/garden-longevity/renewal-seed-order.md)
now raises target purchases 1 → 42 (0 → 13 late), with identical stress/lifetime
and final stores. Its extra energy cost replaces overflow; extra water uptake
covers the water fee. Allocation changes, but establishment does not: all 10,405
mature target-seed observations have stable living spacing blockers. All 28
columns are spacing-blocked throughout the post-noon window, despite one free
plant slot. Whole births/deaths remain 7/4 and late births zero; every lineage's
survival history is unchanged. All 16 fixed calls, historical control, exact
prefixes/repeats, 221,468 live budgets, four native images, independent portable
checks and 85/86 default/experimental CTests pass. Next discuss establishment
and competition mechanics, including what should allow seedlings to challenge
stable adults. More bank capacity, order tuning or training alone cannot
create planting space in this saved state. Rotation stays host-only/off by
default; no broader ecological rule is changed or qualified by this result.
The subsequently approved [spacing comparison](../benchmarks/garden-longevity/renewal-seed-spacing.md)
holds rotation and all other rules fixed, reducing minimum distance three → two
only after the shared noon. It admits 19 new seedlings, six full-day survivors
among 17 eligible, and ten closing births. But 16 new seedlings and three
incumbents die, including the only flower; no post-boundary parent has a child
surviving a day within the horizon. The plant array is full at 93.6% of later
checkpoints, without node-capacity blockage. There is no shared-root-cell
exposure in audited live steps; do not attribute mortality to uptake ordering.
All 20 declared calls, historical control/prefixes/repeats, six native images,
231,407 live budgets, independent portable checks and 86/88 default/experimental
CTests verify. One analysis-only recovery canonicalizes historical witness-set
ordering; no native runs were repeated or observations replaced. Next examine
seedling light/energy trajectories and flower loss using the saved traces.
This establishes opportunity in one selected world, not sustainable succession
or broad environment qualification. The opt-in stays host-only/off by default.
The subsequent [saved light/spending audit](../benchmarks/garden-longevity/renewal-establishment-light.md)
now separates zero usable light from fractional income: five seedlings have zero
live-step numerator; a sixth accumulates only 248/255 of an energy unit. All six
spend their 64 startup energy on shoots and upkeep, not roots. However, five of
six first-day survivors also exhaust startup energy before reaching light, so a
blanket shade-growth veto is not supported. At unchanged body size, flower 5's
final-day income falls to 280 versus 732 in control; sampled illumination and
condition decline, 12 otherwise eligible renewal observations lack energy, and
eight consecutive energy shortages end its life. All 19 seedlings and both
matched flowers are audited with no terminal-budget invention or new
experimental captures. Next discuss one bounded canopy-transmission A/B,
preserving nighttime zero production and judging descendant survival plus
adult/species losses. That read-only audit itself changes no light rule, model
or firmware.
The subsequently approved [fractional-canopy comparison](../benchmarks/garden-longevity/renewal-canopy-transmission.md)
keeps zero nighttime production and every non-optical rule fixed. Both new
seedlings survive, and flower 5/shrub 12 survive, but only two seedlings establish
instead of nineteen. New full-day survivors fall six → two; neither new plant
has a germinated child. Incumbent deaths fall three → one, endpoint species and
families rise 1/2 → 2/3, and post-boundary plant-slot occupancy reaches 99.0%.
The candidate fails both predeclared renewal gates while passing retention gates;
it is not broader environment qualification. Historical control and prefixes,
all 20 repeated captures, six native images, 243,005 live budgets and independent
portable checks pass, along with 88/91 default/experimental CTests. Terminal
cleared budgets remain unknown. The flag resets off, is explicitly disabled in
normal builds and rejects firmware. Next audit allocation-only versus overlapping
spacing/moisture blockers from saved traces before designing a bounded capacity
or competition comparison. No new capacity, forced deaths, training, promotion,
commit, push or device flash.
The subsequent [saved allocation audit](../benchmarks/garden-longevity/renewal-allocation-blockers.md)
separates post-step queries from narrowly justified no-birth code-order evidence.
There are 53 distinct candidate seeds with allocation-only rejection: 52 expire,
one later germinates. Seven belong to the successful new shrub 13 and all expire.
Of 5,542 confirmed observations, 5,538 have eight living occupants. The candidate's
other new shrub 14 has no allocation-only evidence: all three seeds are also
spacing-blocked. All 1,034 lifetimes, 256,010 retained-seed observations and
247,759 mature observations reconcile; no new experimental native calls, models
or images. Parent/repeated/new analysis, independent Docker checks and 89/92
default/experimental CTests pass. A pre-export snapshot/exit-timestamp distinction
was corrected in the new audit with a regression test; frozen evidence is intact.
Next proposal: a fixed eight-versus-sixteen host plant-slot diagnostic after the
shared checkpoint, keeping 512 nodes, eight seeds, light, costs, spacing, weather,
controllers and horizon unchanged. Test whether descendants establish and renew
or pressure simply moves to nodes/resources. No capacity change or forced death
is implemented or promoted; more births alone would not qualify the environment.
The approved [plant-slot comparison](../benchmarks/garden-longevity/renewal-plant-slots.md)
now completes that fixed eight-versus-sixteen test. Post-boundary births rise
2 → 27, full-day survivors 2 → 17 and new full-day parents with a full-day child
0 → 6; generation four is reached. The trade-off is six incumbent deaths rather
than one and two surviving founder families rather than three. All other rules,
512 nodes and eight seeds remain fixed. Plant storage peaks at 12, but nodes
are full at 65.4% of post-boundary samples, including the final 4.05 days; all
endpoint nodes are living. Both reproduction gates pass and both incumbent/
family-retention gates fail, so this remains a mixed selected-world result.
90/94 default/experimental CTests, exact historical control/prefixes, all 20
captures, six images, 266,066 live budgets and independent portable checks pass.
Host storage/diagnostics grow by 2,048 bytes; firmware/default capacity remains
eight. Next discuss an offline node ownership/denied-growth and incumbent-death
audit using these saved histories, not a larger node pool or capacity sweep.
No training, promotion, commit, push or device flash.
The approved [saved node/death audit](../benchmarks/garden-longevity/renewal-node-pressure.md)
reconciles 23,552 ownership transitions and 209,462 post-boundary live budgets.
All 512 endpoint nodes belong to 11 living plants (171 roots, 341 shoots); all
23 post-boundary dead plants have been reclaimed. Four plants retain 14 tips.
Code-order reconstruction finds 17,001 full-entry plant-steps with tips,
immediate resource affordability and no renewal, but these are not rejected
EXTEND requests: cooldown and the uncalled policy choice remain unknown.
The pre-policy capacity gate suppresses non-allocating WAIT/FINISH too; leaf
renewal still works, with 1,978 successes at full occupancy.
Four incumbent fatal stress episodes start with water shortage and two with
energy shortage. Terminal flags alone misclassify shrub 7's water-led episode.
The four water-led plants make no discretionary payments in their final day;
their old/lit leaf samples all fail the renewal water-reserve threshold, while
leaf condition decays. Five dead incumbents were already tipless at the split,
so the growth gate is not their proximate cause. Two energy-led plants buy more
seeds and enter night with lower energy reserves; no rescue is inferred.
Parent/repeated/Docker verification, 15 focused cases and 91/95 default/experimental
CTests pass, with zero new research captures. Next discuss a bounded full-pool
non-allocating-action A/B with unchanged node capacity, without claiming it
solves adult water/energy deficits. Body recycling and water rules remain
separate design questions; no defaults, fitness, training or firmware change.
The approved [full-pool action comparison](../benchmarks/garden-longevity/renewal-full-pool.md)
keeps the same sixteen-slot control and 512-node/eight-seed limits. The new
transaction boundary permits non-allocating actions while refusing allocating
winners before payment/private-state commit, without a fallback. In the fixed
world it commits 6,224 WAITs and refuses 6,060 EXTENDs, but selects no FINISH or
geometrically exhausted EXTEND. The mechanism gate fails; new full-day survivors
fall 17 → 16, durable new parents stay at six, and the same six incumbents die.
More births (27 → 29) and generation five do not override those gates; both
generation-five seedlings are too recent for full-day evaluation. Endpoint
nodes fall 512 → 417 amid changed turnover and more deaths, not FINISH-driven
reclamation. The unchanged night-growth wrapper accounts for 6,220 of the WAITs.
Historical control/prefixes, all 20 captures, six images, 286,700 live budgets,
1,036 seed lifetimes and independent Docker checks reconcile; 57 terminal budgets
remain unknown. 92/97 default/experimental CTests pass. Host-only diagnostics
add 148 bytes per instrumented world, with no device build or performance claim.
Keep this result negative and off by default. Next discuss living-body turnover:
identify what saved observations can say about unproductive terminal structure,
what topology evidence is missing, and whether safe local shedding would reclaim
meaningful storage. Define safety/costs before implementing it; do not force
FINISH, add RAM, retrain or treat water shortages as solved. No commit or push.
The approved [saved shedding-feasibility audit](../benchmarks/garden-longevity/renewal-shedding-audit.md)
finds 146 zero-condition living leaf nodes at the full control endpoint, including
110 continuously zero for at least a day; the candidate has 56/46. These are
optimistic storage bounds, not removable-node counts: parent/child topology and
leaf/flower/tip overlap are not recorded. Zero condition is not permanent loss:
268/287 full-day-zero episodes in the two arms later end in paid renewal. Mature
`active_leaves` must not be mistaken for healthy leaves. Leaf ordinal tracking
checks 8,738,097 transitions and 6,780 renewals without new native research calls.
The all-zero-leaf bound covers four-node headroom at every sampled node-blocked
checkpoint, but guaranteed safe recovery remains zero without topology; no
rescued births or paid upkeep savings are inferred. Parent/repeated/Docker
checks, 14 focused cases and 93/98 default/experimental CTests pass. The embedded-C
review records stable compaction, reference remapping, retained child counts and
action-stage safety requirements; the existing UI prune tool only tags tips.
Next proposal: a bounded read-only host topology census on the original sixteen-
slot control, with identical physical hashes, before choosing a shedding action
or costs. Do not stack the failed full-pool rule, delete renewing/internal tissue,
add a persistence buffer, contract stems or prune roots implicitly. No native
source, ecology, capacity, default, training, firmware, commit or push changes.
The subsequent [topology census](../benchmarks/garden-longevity/renewal-topology.md)
now exports node links/roles and base/previous-tip references at eight predeclared
ticks in the original sixteen-slot control. All 194,270 original trace records
remain byte-identical with capture off/on; three fixed native calls, repeated
analysis and independent Docker verification pass. At first full pool and the
peak 166-zero-leaf snapshot, only one node passes the conservative structural
filter. At the 146-zero-leaf endpoint, 136 are internal; only one is eligible,
and it has been zero for less than a day. No sampled full pool recovers the four
slots needed for germination. 95/100 default/experimental CTests pass; no shared
world, ecological rules, device defaults or firmware changed. Do not implement
simple shedding from this result or silently expand into internal contraction.
The next checkpoint is consolidation/review of the branch, with unresolved
ecology work explicit rather than waiting for the entire A-life roadmap.
Removing a neighbor changes light/water/capacity too, not spacing alone.
Do not adopt a permanent size quota, relax spacing or infer improved renewal
from adult rescues. Retry handling, dawn recovery and current reserve shortages
remain separate limitations.
Keep the rule host-only and off by default; do not promote a policy, change
fitness or resume training from this diagnosis.
Environment qualification is underway. The [nighttime-growth comparison](../benchmarks/garden-longevity/night-growth.md)
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
The [bounded-renewal training A/B](../benchmarks/garden-longevity/renewal-training.md)
now compares the unchanged v2 selector with the explicit individual-minimum
selector, using identical original/first-generation models and a fixed
three-generation budget. Final B beats final A by 18.2% on the fresh review
minimum-period component, winning 7/8 worlds, both schedule groups and all four
blocked seed omissions. B's 9.1% gain over the original is less robust: one
schedule is slightly worse and one seed omission reverses the gain. B2 reviews
better than B3 despite B3's training improvement; no retrospective model selection
is made. Single-species worlds rise from 3/8 original to 6/8 B (7/8 A).
All 868 declared native processes, full capture-disabled search repeats, 64
independently repeated frames, 55 default and 50 experimental CTests pass.
Existing ecology, native fitness, runner defaults and firmware stay unchanged.
This is evidence to replicate the objective with independent search streams and
fresh world/schedule combinations, not model promotion or environment qualification.
The [independent replication](../benchmarks/garden-longevity/renewal-replication.md)
now uses two new mutation streams, fresh training worlds/schedules and separate
fresh review worlds with schedule-held-out disturbance seeds. B's final
minimum-period review credit loses to A by **10.9% / 8.8%** in R1/R2; both schedules
and all blocked seed omissions agree in each replica. B's training gains over
original are 18.5% / 17.9%, but review falls 12.1% / 7.9%. R2 B2 reviews better
than B3; no retrospective selection is made. All finalists retain established
descendants and positive credit in every period, but single-species worlds rise
from 1/8 original to 4–5/8. All 1,736 fixed native calls, four full search repeats,
128 independently repeated images, 56 default and 51 experimental CTests verify.
The prior advantage is not robust to this fresh panel. Keep defaults unchanged;
next discuss frozen-model world/schedule cross-evaluation to locate the transfer
gap before more training. No adoption, model promotion or qualification milestone.
The [frozen-model world/schedule cross](../benchmarks/garden-longevity/renewal-transfer.md)
now completes the missing TR/RT cells for the original and all four finalists,
reusing TT/RR without training. Both B finalists beat the original on training
worlds under either schedule set, but lose on review worlds under either set.
Their normalized world-set contrasts stay negative under every paired seed
omission; individual review losses are not all omission-robust. R1 B/A loses in
TR/RT by 5.78% / 22.57%; R2 gains 11.15% in TR and nearly ties (−0.27%) in RT.
Schedule interactions differ, so this is not a schedule-only or weather-only
explanation. All 300 declared native calls, 120 complete new trial repeats,
40 independently repeated frames and 100 focused Python tests pass. All scored
endpoints retain established descendants, without zero-credit periods, but
variety remains mixed. Discuss a coverage-only training A/B with broader world
sampling, unchanged score/ecology/search budget and a separate fresh review
panel; do not promote a model, tune fitness or close qualification milestones.
The [fixed 8/16-world renewal comparison](../benchmarks/garden-longevity/renewal-coverage.md)
now reuses both narrow searches and trains matched wide counterparts, keeping
score, ecology, schedules and mutation budget unchanged. W3/N3 fresh-review
minimum credit improves **2.75% / 7.54%** in R1/R2. R1's gain reverses under one
schedule and one omission; R2's holds under both schedules and all omissions.
Both wide finalists beat the original, but R2 loses 7.97% on the added training
subset under both schedules and every omission. Species variety does not improve;
founder-family outcomes differ. All 2,084 new native calls, two full wide-search
repeats, 256 independently repeated images and 114 focused Python tests pass.
W uses twice as many training evaluations per candidate, not extra mutants.
Eight fresh review seeds still form one shared panel; unchanged R1 N3 now gains
23.57% over original after losing on the prior panel. Discuss a frozen-finalist
check on that earlier world/schedule cross, reusing original/narrow evidence;
do not interpret this result as broad transfer, default adoption or qualification.
The [frozen-finalist return check](../benchmarks/garden-longevity/renewal-return.md)
now measures both W3 models on the earlier cross, reusing original/N3 controls.
On old RR, R1 W/N loses **7.73%**, R2 gains **8.89%**; omitting one seed reverses
each sign. R1 W/original loses 18.92% under both schedules and every omission;
R2's +0.25% splits by schedule and reverses under two omissions. R1 W/N loses in
all four cells; R2 gains in TT/RT/RR but loses 12.07% in TR. R2's old RR fresh
late credit falls 29.15%, offset by more carry-in credit under the age-capped
rule; single-species endpoints rise from 4/8 N to 7/8 W. Broader sampling does
not consistently repair transfer or produce a generally richer garden. All
224 declared native calls, 96 complete new trial repeats, 40 repeated images
and 126 focused Python tests pass; both source bundles and portable evidence
verify. No retraining, ecological change or promotion. Discuss a saved-ledger
audit of paired gains/losses, confirmation timing, mortality and species turnover
before changing coverage or cross-world aggregation.
The [offline cohort audit](../benchmarks/garden-longevity/renewal-cohorts.md)
now reconciles all forty old-RR histories and 160 periods without native runs.
R1 W has more qualifying late children (30 → 33), but later confirmations reduce
available credit; R2 W has fewer (40 → 32), offset by stronger carry-in. Minimum
switching explains why improvement at N's worst period need not improve the new
minimum. Five of R2 W's seven final monocultures already exist before day 62;
all shrubs disappear by about day two, while N retains shrubs in two matched
conditions through day 192. Living-species losses can recover from pending seeds,
so the audit retains exact loss/recovery times separately from final retention.
All 219 focused Python tests, frozen native annotations, credit identities,
timelines, repeated analysis and portable export verify. No new screenshots,
native calls, training or score/ecology changes. Discuss a first-eight-day
resource/decision trace on matched `0d983a80` with original and R2 N/W before
reward changes or more training; causal water/light/energy histories are absent
from these saved ledgers.
The [eight-day startup diagnostic](../benchmarks/garden-longevity/renewal-startup.md)
now reuses the frozen native inspector/replayer and all three fixed models on
that selected world. W's two founder shrubs exhaust energy on the second night
despite full water, with no nighttime growth/reproduction/renewal spending.
N retains one 55-node shrub (seven energy per upkeep charge); W builds 59 nodes
(eight per charge) and dies before income recovers. N still briefly reaches zero
energy, using stress tolerance to survive. W's replacement shrub makes seven
shoot extensions but no root extension, then dies with full energy and zero
water. Day-eight populations are original 4 across two species, N 8 across three,
W 6 flowers only. All 244 focused tests, 30 fixed native calls, complete trace
repeats, saved history prefixes and twelve repeated native images verify.
An analyzer metadata compatibility error was corrected offline with sealed
captures and separately retained revised source; no extra native calls or
invented capture timings. This is an inspected-case explanation, not qualification
or a fitness change. That motivated the reciprocal founder-controller diagnostic.
The [reciprocal swap](../benchmarks/garden-longevity/renewal-swap.md) is now complete
on the same eight-day world: only N on shrub 2 in an N garden survives. Both
counterfactuals die of energy shortage near day 1.8. N in W has 54 nodes and
seven-unit upkeep, but 185 rather than 205 sunset energy; its reconciled daytime
budget includes one extra 48-energy seed purchase. W in N still builds 59 nodes
and eight-unit upkeep. That one-founder change also pushes the original
ground-cover from 56 to 57 nodes; it dies, and the endpoint is flowers-only.
All 58 experimental-host CTests, three focused default-build tests, forty fixed
native calls, exact full-trace controls/repeats and sixteen repeated native
frames pass. This is a total controller/background effect with feedback, not
proof of purely physical cooperation: global node-pool tie ordering can also
change. This motivated one-neighbor-at-a-time swaps with fixed focal N.
That [single-neighbor diagnostic](../benchmarks/garden-longevity/renewal-neighbors.md)
is now complete using the exact saved native tools: changing either ground-cover
3 or far-right flower 5 alone kills shrub 2 at tick 6,840. Shrub 4's swap causes
a later tick-26,040 death; flower 1's swap retains the focal shrub at day eight.
All stay below the eight-unit upkeep step. Ground-cover reduces focal daylight
income without an extra seed; the far-right-flower world has a spare bank slot
at 4,260, allowing automatic seed spending blocked in the full-bank control.
It finishes the second daylight with four purchases and 187 versus 205 energy.
Equal-recorded-bid-set ordering differences occur in three cases during night
WAITs, including the survivor; they are not isolated as the cause of death.
All 128 renewal-family tests, forty new native calls, complete repeats and
sixteen new/eight copied native checkpoint pairs verify; no C/header or native
binary change. This motivated the accepted
[fourth-seed counterfactual](../benchmarks/garden-longevity/renewal-seed-veto.md).
An explicit host-only/off-by-default option suppresses only founder 2's fourth
purchase and retries in its second daylight. All 16,775 rebuilt control records
match saved evidence; the intervention first diverges exactly at tick 4,620.
The shrub retains 48 energy, has 235 rather than 187 at sunset, survives through
day eight and has three living direct offspring. No focal growth bids change.
But founder ground-cover 3 immediately buys a seed in the available bank slot,
losing 48 energy and dying at tick 6,600 instead of 14,340. The endpoint changes
from four flowers/three ground-cover to one flower/five shrubs, with six rather
than seven living plants. This is a scoped causal rescue with feedback, not a
general ecology improvement. All 61 OFF-build CTests, six focused ON-build
suites, 65 default-build CTests, twenty fixed native calls and eight repeated
native checkpoints verify.
The subsequent [offline forecast audit](../benchmarks/garden-longevity/renewal-seed-forecast.md)
is complete: at the observed tick-4,620 purchases the general gate approves
the shrub (224 forecast / 187 actual sunset energy) and rejects the ground-cover
(209 / 183). Both actually earn only seven further energy; the forecast credits
44/33. Its half-current-income assumption misses the integer light cutoff;
no additional spending, overflow or body change explains the error. The rescued
shrub clears night but incurs stress 1 during dawn recovery, then recovers.
Thirty-seven guaranteed zero-income payments cost the fixed bodies 259/296
energy against a 256 cap, so uninterrupted energy sufficiency is not a suitable
unexamined survival requirement. All 32 focused Python tests, frozen-source
checks, saved-bundle verification and exact repeated analysis pass; zero new
native calls. This motivated the
[fixed phase-aware shadow predictor](../benchmarks/garden-longevity/renewal-phase-forecast.md),
now evaluated on all 112 saved purchases with no fitted parameters. Sunset mean
absolute error improves from 28.66 to 15.62 over 101 paired checkpoints; on the
27 still-assumption-valid sunsets it improves from 16.70 to 3.30. It predicts the
two known late-purchase death ticks exactly. However, 103 windows have subsequent
optional spending, 27 have body/mature-leaf changes, and unchanged-body prefixes
still include a 148-energy morning overestimate. Twenty supported death-labelled
windows yield two predicted and eighteen missed deaths; they overlap across
parents and all misses have a prior assumption break. No fully observed,
assumption-valid survivor controls remain, so the clean subset does not validate
a survival classifier. Two zero-light anchors are unsupported and nine windows
right-censored. All 53 focused tests and repeated, hash-verified offline analysis
pass; no new native calls or rule changes. The subsequent
[exact dark-budget audit](../benchmarks/garden-longevity/renewal-dark-budget.md)
covers 170 of 1,525 spending steps plus 68 systematic evening states. All 66
complete assumption-valid outcomes and every valid-prefix energy/stress sample
match exactly; 15 clean evening intervals incur shortages but remain alive at
the boundary. Seven growth and two seed expense records turn local budgets from
alive to fatal, with shared/repeated events explicitly retained. Five of those
growth records cross an upkeep tier. Most other spending lies outside the
immediately guaranteed-dark interval, and later spending/upkeep/water changes
still invalidate one-time projections. All 87 focused tests, frozen-source
checks and repeated offline export pass; zero new native calls. Next discuss a
host-only/off-by-default guard across optional expenses in this interval, without
claiming morning survival or causal rescues from local arithmetic. No permanent
quota, broader gate, new training or default change was adopted.
The 16-bit moisture summary
intentionally saturates, so use actual cell totals. Separately, fix and test the
unsaturated living-plant age counter before
runs reaching 256 days; this unchanged-ecology comparison stops at 192.
No columns are permanently protected; small patches preserve most of the garden
at each event, without retargeting empty hits or assisting recovery. Discuss
these findings before adopting permanent ecology or expanding the neural contract.
No default rule, firmware
capacity change, training run or qualification milestone follows automatically.
Prior tools/experiments through exact recruitment recovery are checkpointed
locally in `a1c419f`, and founder independence in `bbb6307`. The new host-only
bounded-renewal selector, fixed A/B, independent replication, frozen-model transfer,
8/16-world coverage comparison, frozen-finalist return check, offline cohort
audit, startup diagnostic, reciprocal swap, single-neighbor follow-up, fourth-seed veto,
offline seed-forecast audit, phase-aware shadow forecast and
corresponding notes are the subsequent uncommitted work.

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

The general [experiment workflow](garden-experiments.md) collects evidence;
separate bounded pilot runners perform training and preserve every generation's
model and screenshots. The original general trainer still saves only the final
model, with per-generation fitness and fingerprints in its report. The normal
scene player/image runner does not yet load an arbitrary saved model under the
exact evaluation setup.
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
  Audit reset/seed-bank loopholes and capacity saturation. Opt-in
  [natural-death receipts](garden-long-run-correctness.md) now reconcile the
  terminal resource clear; legacy live-step analyzers and forced patch/gap
  deaths retain their separate accounting boundaries.
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
