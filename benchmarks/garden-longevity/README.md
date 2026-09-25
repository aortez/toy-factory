# Garden longevity investigation

Start with the [checkpoint review guide](../../docs/garden-merge-checkpoint.md)
for the current conclusions and production/research boundary. The material below
is the chronological evidence record, including rejected hypotheses.

This is the pre-renewal baseline (Garden hash version 4). The subsequent
[renewable-flower comparison](renewal.md) uses the same frozen model and seeds
with the corrected lifecycle. The original observations below remain unchanged.
The following [offspring lifetime investigation](lifetimes.md) holds that corrected
ecology fixed and measures full-cycle survival and durable parent/child pairs.
The [resource-budget investigation](resources.md) then traces individual failures
and tests isolated host-side decision overrides.
The [rainfall experiment](rainfall.md) adds gardener-free seeded environmental
water and moves training to rain-fed plots, while preserving the old diagnostic
suite and frozen-model artifacts for comparisons.
The [nighttime-growth probe](night-growth.md) then holds the rain-fed ecology
fixed: early survival improves, but late seed establishment remains sparse.
The [seed-establishment audit](establishment.md) identifies narrow-dispersal
blind spots alongside overlapping moisture, spacing, shade and capacity limits.
The [wider-scattering comparison](dispersal.md) increases establishment but gives
mixed durable-lineage results, so it remains a host-only experiment.
The [storage-limited uptake test](water-headroom.md) then holds original
scattering fixed: water stress falls, but space/node pressure limits renewal.
The [combined uptake/scattering test](combined-ecology.md) completes the 2×2
comparison: more offspring survive and the gardens fill up, but late renewal
nearly stops as allocation limits join spacing and shade. None of these
experimental variants has been promoted to device/default ecology.
The [node-ownership audit](node-budget.md) then replays every condition without
changes: the late combined pool is entirely living tissue, not delayed corpse
reclamation. The capacity ceiling also prevents growth-policy calls.
The [512-node host control](node-capacity.md) removes that ceiling and raises
full-cycle survivors 227 → 296, but 43/45 living gardens end without growth tips;
spacing, shade and mature-body persistence still limit broad renewal.
The [tip-lifecycle audit](tip-lifecycle.md) then attributes every committed
termination: depth limits or blocked continuation, with no observed unconstrained
finish. Mature plants spend about 99% of late living time without growth-policy
calls, motivating an explicit maintenance-interface discussion.
The [leaf-maintenance trial](leaf-maintenance.md) implements that interface and
compares no renewal, indiscriminate renewal and a selective scripted rule at
both capacities. Adult survival improves, but selective maintenance can leave
almost no late generational turnover. The experiment includes native screenshots
and controlled light/shade/water cases; it remains host-only and unqualified.
The [maintenance-competition census](maintenance-competition.md) replays 96
unchanged worlds and follows seeds into offspring: seed supply continues, but
selective adults exhaust the 256-node pool; at 512 nodes, plant slots, spacing
and ground conditions replace the memory bottleneck. Only four of 900 eligible
late seeds germinate there, motivating a controlled gap-recovery assay;
no lifespan rule or default change follows from this finding.
That [one-gap recovery assay](gap-recovery.md) is now complete: 30/32 perturbed
worlds produce offspring and 54/63 eligible new offspring survive a full day,
but 27/32 worlds have no births in the final four days. Native paired screenshots
show both reorganization and simple replacement.
The subsequent [recurring patch-death experiment](patch-disturbance.md) preserves
ordinary decomposition and uses fixed, population-independent schedules over 64
days. Closing-window births occur in 63/64 disturbed worlds versus 1/32 controls;
392/497 eligible offspring survive a day, with 60 durable new parents. Memory
and ground constraints persist, and founder-family retention falls. The rule
remains host-only; no training or permanent/default disturbance is selected.
The [192-day longevity/diversity follow-up](disturbance-longevity.md) adds four
fresh schedules and a validated sparse population census. All 128 disturbed
worlds still have births in days 160–192, versus 2/32 controls, but 53/128 retain
only one species and 44/128 one founder family. Inherited trait combinations
remain varied; these are different kinds of diversity. Native screenshots also
prompt a secondary long-run water-balance question: many soils accumulate water.
The comparison stops below a discovered 256-day plant-age wrap boundary. Neither
the counter nor ecology is changed by this audit; discuss water balance and the
desired variety before adopting rules or training.
The [long-run water-budget audit](water-balance.md) now replays those same 160
worlds with direct stage inventories. All daily balances/hashes match: wetting
is retained rainfall, not an accounting leak. Disturbed gardens retain a mean
206/83 units per day late at 256/512 nodes; the larger pool takes up about 27%
more water, but neither panel reaches uniform equilibrium. Late shortage flags
are rare, and much of the retained water is accessible to roots.
The subsequent [host-only bottom-drainage A/B](bottom-drainage.md) lowers final
soil storage in 152/160 paired worlds, but is not a universal ecology improvement.
Disturbed closing day-survivor counts are 224 → 225 at 256 nodes and 281 → 268
at 512; the larger pool has one new extinction, followed by water accumulation
without plants. Native paired screenshots and a post-hoc failure review are
included. All 80 tests and independent balance/replay checks pass. Keep drainage
experimental; discuss a policy/resource diagnostic before tuning it, adopting
defaults or training. The age-boundary fix remains separate.
That [focused policy/resource diagnostic](drainage-policy.md) is now complete:
the unchanged adaptive reference plus the same night veto survives the previously
failed drainage case through 192 days. Full traces expose large neural-grown
bodies exhausting energy on overnight upkeep despite abundant stored water;
two final seedlings also enter night under-reserved. All 84 tests pass. The
reference changes species/body composition and does not dominate turnover across
the 40-run panel, so neither controller nor drainage is promoted. Discuss a
reserve-aware growth experiment next, without bundling ecology or storage changes.
The subsequent [reserve-aware growth A/B](reserve-growth.md) is complete: the
same frozen NN with one predeclared affordability gate survives that failure,
and disturbed closing offspring survival fractions improve with drainage off/on.
Actual closing survivors change 40 → 31 off and 29 → 37 on; fewer births and
unchanged late recruitment stagnation in controls prevent calling it a general
ecology win. All 40 native outcomes and adverse cases are retained; 93 tests,
old-baseline checks and independent replays pass. Keep the rule host-only and
frozen; discuss the broader seed/capacity panel before promotion or further tuning.
That [full existing-panel comparison](reserve-panel.md) is now complete: 640 runs,
eight seeds, two layouts and both capacities/drainage settings, with no rule
retuning. Disturbed closing survivors change 224 → 228 and 225 → 246 at 256
off/on, and 281 → 289 and 268 → 284 at 512. Closing durable-parent totals also
improve in all four groups, and no reserve run goes extinct. However, both
crowded/off subsets lose late survivors, per-pair regressions are common, and
variety/control turnover remain unqualified. All 98 tests, 1,920 independent
replays and prior comparisons pass. Native review panels and all paired deltas
are retained. Discuss the existing seed-site diagnostic on those regressions
before more controller/ecology changes or training; defaults remain unchanged.
That [crowded recruitment diagnostic](recruitment-sites.md) now follows eight
selected unchanged runs at every ecology step. Seed production continues;
living-tissue storage pressure dominates at 256 nodes, whereas plant slots,
spacing, shade and surface moisture overlap at 512. A traced vacancy frees 46
nodes that existing plants reclaim without a new seedling. Successful comparisons
and post-step sampling caveats remain explicit. All 105 tests and original
outcome/replay checks pass. Exact germination-attempt visibility is the next
proposed diagnostic before changing ecology or training.
The subsequent [exact germination-check audit](seed-attempts.md) now resolves that
timing issue without changing behavior: 36/61 closing seedlings appear on steps
whose post-step map has no remaining opening. Of 1,380 steps with an opening
before checks, 1,321 have mature seeds but no viable actual landing. The fixed
46-node vacancy has 492 mature checks, none node-blocked and none successful;
spacing/light explain the misses before incumbents refill storage. All 113 tests,
65,544 frozen state hashes and final-frame comparisons pass. A small 8→16
seed-bank A/B at 512 nodes was proposed next, without promotion.
That [8/16-seed host comparison](seed-bank.md) is now complete. Closing day-survivors
change 13 → 4, 5 → 6, 3 → 4 and 7 → 33 across the four fixed pairs. The strongest
reserve result also raises natural deaths 6 → 37 and lowers final living plants
7 → 4; the baseline regression instead has healthier, less-reproductive adults.
Extra bank space costs 160 bytes per host world and 16 per Garden snapshot;
defaults and firmware remain unchanged. All 130 tests, baseline equality checks,
full ledgers and 24 native frame replays pass. Review resource/lifetime timing
in the high-turnover case before promotion or broader training.
That [read-only lifetime/resource follow-up](turnover.md) now shows the standout
run's 33 one-day survivors falling to 18 four-day survivors and 2/28 eligible
eight-day survivors. All 31 closing energy deaths enter night under-reserved,
with unchanged bodies and no optional nighttime spending; 30 reproduced 3–6
times in the preceding day. Reproduction is genuine but adults are short-lived.
The growth reserve gate does not coordinate automatic reproduction spending.
All 34 default host tests and both frozen full-world audits pass; no native
rules changed. Discuss a sunset-aware reproduction-budget A/B, not an arbitrary
lifespan or an assumption that all deaths will disappear.
The approved [sunset-aware seed-budget A/B](seed-reserve.md) now reduces closing
energy deaths 31 → 1 and natural deaths 37 → 8 in that sixteen-bank reserve run;
eight-day survivors improve 2/28 → 5/13 and final living plants 4 → 7. All eight
remaining deaths are seedlings, seven water-starved. Other pairs are mixed or
adverse, and the eight-bank reserve control is completely unchanged. All 113
tests and the frozen controls, resource ledgers and 48 native frames pass.
Two corrected audit assumptions (same-step slot transfer and valid no-effect
runs) are documented with retained failed bundles. Keep the gate host-only;
discuss seedling water/root diagnostics and wider validation before promotion.
The [read-only seedling audit](seedling-water.md) now reconciles 39,658 first-day
budgets across all sixteen worlds: 41 of 44 deaths involving water shortage have
no root extension. All seven targeted failures spend water on shoots while
remaining in one surface cell; all eight first-day survivors reach deeper soil.
Three rooted failures prevent treating that as a universal cure. All 36 default
host tests pass. Discuss a bid-verified early-root policy probe before changing
rain, stores, ecology or training; no new intervention is implemented.
The approved [wet-root bootstrap experiment](root-bootstrap.md) now verifies those
losing bids and tests one fixed host-only intervention, activated after day 160.
Across eight paired worlds, first-day water-involved deaths fall 33 → 3 and
natural deaths 62 → 24; the target improves natural deaths 8 → 2 and sixteen-day
survivors 4/10 → 5/8. One early energy-survival regression and three remaining
rooted water failures prevent universal-policy claims. All 76 tests, fresh
controls, ledgers and eight new frames pass. Keep the probe opt-in and discuss
the allocation/training challenge before promotion or further tuning.
The approved [allocation challenge](allocation-challenge.md) now freezes six
selected pre-birth worlds and evaluates four single-seedling control/candidate
continuations from each. All 82 tests, 12,308 reference samples, 18,816 live
budgets and 96 native frames pass. WAIT survives the first day in all six cases
without productive growth or seeds; root-first rescues one case but harms a
previously established control. Another case succeeds with later ordinary root
investment instead. No children germinate within these follow-up windows.
The saved-model interface is ready for objective experiments, not a new trained
controller or a qualification milestone. See the report for selection bias,
patch censoring and the telemetry-only rerun.
The [objective dry-run](allocation-objectives.md) then compares survival, raw-seed
and confirmed-production bonuses without rerunning worlds or training. WAIT leads
all aggregate sensitivities; the zero-shortage gate rejects a surviving producer,
and synthetic fixtures expose an unresolved late-collapse tradeoff. Delayed
production remains a useful candidate signal, not a selected fitness. All 85 tests
and exact score/seed-follow-up rechecks pass; the report retains every case, ties,
censoring and the post-ranking resource-severity audit.
The [survival-confirmed follow-up](allocation-survival.md) removes that veto
without changing weights or caps. Both producers now beat WAIT within their
cases, but WAIT still wins overall. Both producers cap out, making revised and
raw-seed native scores identical; synthetic fixtures show the remaining
distinctions and loopholes. The nominal full bonus offsets two days of lost
survival in an eight-day window. All 88 tests and frozen old/new score rechecks
pass. Next connect allocation evidence to actual established descendants rather
than treat confirmed seed purchases as successful reproduction.
The [descendant-outcome follow-up](descendant-outcomes.md) now makes that link
using existing 192-day histories. Of 2,074 closing purchases, 61 germinate and
48 children survive a day; six of those establish a day-surviving child of
their own. Thirty-one parents hit the production cap without an established
child. Parent fate, seed expiry, natural seedling death, patch/horizon censoring
and exact reproductive opportunity stay distinct. All 91 tests and complete
trace reanalyses pass. No fitness or training change follows automatically;
the next discussion is a lineage-outcome evaluation contract.
The [lineage-fitness v1 test](lineage-fitness.md) now implements that first
offline candidate and tests it against arithmetic challenges and all eight
saved histories. It orders terminal descendant presence, renewing parents,
establishments and descendant occupancy. All 94 CTests pass. The four paired
conditions split two–two; baseline leads overall but two leave-one-out results
reverse it. The report reconciles 51 confirmation-window establishments with
the old purchase cohort's 48. Short-lived-offspring and endpoint preferences
remain explicit; seed-only endpoints require follow-up. No score is installed
in training, and neither controller is promoted.
The [persistence v2 revision](lineage-persistence.md) replaces count-first
renewal with observed recent offspring live time and a common two-day terminal
follow-up. The brief-offspring counterexamples now lose to longer persistence;
new-generation seed-only endings at the deadline remain explicitly unconfirmed.
All 97 CTests pass, including 28 new cases. In the matched-window native panel,
reserve wins three pairs but baseline narrowly leads the aggregate; excluding
fresh-4 reverses it. Original v1 and all evidence remain unchanged. The proposed
next step is a small fixed-score training/review pilot, not another ecology
sweep or policy promotion; the trainer is still untouched.
The subsequent [two-generation training pilot](training-pilot.md) implements the
fixed v2 loop alongside the guarded legacy trainer, with seven candidate models,
independent C/Python checks, exact repeatability and a
[generation 0/1/2 gallery of 18 native frames](training-pilot-gallery.md).
The winner improves development renewal time 24.27%, but loses 15.72% on the
separate two-world review aggregate. All endpoints retain established descendants;
species/family retention remains inconsistent. All 139 CTests pass. The complete
serial bundle took 107.10 seconds / 18.14 MiB. Do not promote this model: next
discuss a broader paired evaluation of the frozen control and winner before more
evolution. No new ecology or firmware change was made in the pilot.
The [frozen-controller follow-up](pilot-validation.md) adds eight new world seeds
crossed with fresh-1/fresh-2: 32 trials, no mutations. The winner gains 4.45%
overall but wins only 9/16 pairs, loses the fresh-1 aggregate, and loses the
overall comparison when any of three world seeds is removed. Single-species
endpoints increase 7/16 → 12/16. Exact per-child attribution and a
[selected paired gallery](pilot-validation-gallery.md) expose the difference
between first-generation births and continued generational renewal. All 143
tests and every independent final replay pass. Next discuss the diversity
tradeoff before another mixed-schedule training pilot; no model is promoted.
The approved [mixed-condition training pilot](mixed-training.md) keeps fitness
unchanged and diversity diagnostic: ten candidate controllers on four development
world seeds × two schedules, with four separate review seeds. Three generations
raise development renewal 20.76% but lower review renewal 27.09% (1/8 wins).
Both schedule comparisons and all blocked seed omissions retain that contrast.
All 192 scored/repeated trials and [32 generation captures](mixed-training-gallery.md)
verify, with 147 CTests passing. A rejected mutation supplies a real native
extinction case, independently replayed after collection. No controller is
promoted; discuss broader training-world coverage before deeper search.
The [training-coverage comparison](training-coverage.md) doubles development
seeds to eight while preserving the three-generation budget and random stream.
It rejects the earlier first-generation win, but the final champion loses 8.22%
against the original on four fresh review seeds. Against the frozen narrow
champion on these same worlds, it gains only 0.95%, wins 2/8 pairs, and reverses
under two blocked seed omissions. All 360 scored/repeat trials and
[40 native captures](training-coverage-gallery.md) verify; 147 CTests pass.
No promotion: discuss offline time-window stability using the saved histories
before another training expansion or objective change.
The subsequent [offline window check](window-stability.md) scores four frozen
controllers on the same eight review conditions across five declared 32-day
windows. All three trained controllers beat the original in the first three
windows and lose in the last two. Broad versus narrow also reverses; the largest
broad/original reversal is mainly attributable to children leaving the recent
confirmation cohort. All 160 scores and primary-score identities verify, with
11 new unit cases and six relevant pure-Python CTests passing. No new native
worlds, training or objective changes: next discuss how to evaluate sustained
renewal across time without choosing a favorable endpoint retrospectively.
The approved [sustained-renewal candidate check](sustained-renewal.md) replaces
cohort membership with 32-day bounded-age living credit and examines four
non-overlapping periods offline. All 128 cases preserve the original primary
and pass sampled arithmetic/additivity checks. Steady replacement beats a
larger synthetic burst, but the proposed pooled weakest-period ordering hides
individual slumps: broad final leads while two worlds have a full zero-credit
period. Narrow loses within each schedule but wins when schedules are pooled.
Seventeen new unit tests and seven relevant pure-Python CTests pass; no native
runs, training or fitness adoption. Next discuss individual continuity before
pooling rather than treating the new aggregate rank as model improvement.
The subsequent [individual-minimum check](individual-renewal.md) takes each
garden's weakest period before summing worlds. Broad final moves from +26.24%
pooled-minimum credit to −16.76% versus original, losing on both schedules and
under all four blocked omissions. All prior scores/pairs remain unchanged;
only aggregation changes. Complementary slumps lose their pooled timing benefit,
but a strong synthetic garden can still compensate for a sterile one. Fourteen
new unit tests and eight relevant pure-Python CTests pass. No adoption or new
training: next decide whether a full-period gap is a tolerated score tradeoff
or a separate reliability failure.
The [matched stall case study](renewal-stalls.md) traces both zero-credit worlds
against original and adds [16 repeated native images](renewal-stalls-gallery.md).
Broad descendants produce 375 seeds during the weak periods; all expire before
germination, while five founder seedlings establish. Daily observations chiefly
show spacing and the eight-plant cap, not exhausted node capacity. Both broad
worlds later regain qualifying renewal at days 96.8/103.0. This is a recruitment
bottleneck, not sterility/extinction; the originals only recruit one qualifying
child each in the same periods. Forty fixed native processes match all ledger,
census and image checks; 11 unit cases and nine focused Python CTests pass.
No hard calendar-gap gate is adopted. Next discuss opportunity/recovery
measurement around usable openings before changing fitness or ecology.

The [exact recovery follow-up](recruitment-recovery.md) now distinguishes death,
reclamation, usable sites and surviving recruits in the same four trajectories.
The two broad weak periods contain **785 versus 12 usable ecology steps**; neither
has a descendant seed at an eligible actual location or a descendant loss to an
earlier seed in the same step. The second world's later qualifying recruit
germinates on its first usable local step. Twelve native processes verify 65,536
exact seed steps, 129,028 world/site hashes and 730 prior censuses; 13 new unit
cases and ten focused Python CTests pass. All 44 patch intervals, including
no-hits and unsuccessful local refills, remain in the portable data. Keep recovery
as a diagnostic, not an opportunity-normalized score or automatic viability gate;
no training or ecological adjustment was adopted.

The [founder-exit comparison](founder-independence.md) tests 32 matched pairs:
16 already have no founders at day 64 and reproduce exactly; 16 lose 37 living
founders through ordinary death. All actively challenged worlds remain alive
and produce descendant-born full-day survivors (58 → 137 versus controls);
14/16 also produce a further generation from those new recruits. This supports
founder independence within the panel, not indefinite viability or a permanent
mortality rule. Space, shade and resource competition change together. The
report includes all paired outcomes, 24 repeat-verified native frames and the
fixed 144-process protocol. No training, fitness or device change follows.

The [bounded-renewal training A/B](renewal-training.md) now runs the two selectors
from identical initial conditions under a fixed three-generation budget. Final B
beats final A by **18.2%** on fresh review minimum-period credit, with **7/8** paired
wins, both schedule groups and all blocked seed omissions positive. Its **9.1%**
gain over the original is less robust: one schedule and one omission reverse it.
Single-species worlds rise from 3/8 original to 6/8 B, so variety remains a concern.
All 868 native calls, capture-disabled search repeats, [64 native frames](renewal-training-gallery.md)
and 105 CTests verify. The selector is explicit and host-only; no default fitness,
ecology, firmware or model promotion. Discuss independent replication next.

The [independent replication](renewal-replication.md) does **not** reproduce that
advantage. Across two fresh mutation streams, B loses to A on minimum-period
review credit by **10.9% / 8.8%**; both schedule groups and all blocked omissions
agree. Training credit improves, but both B finalists lose to the original on
review and both selectors reduce species variety. All **1,736 native calls**,
four capture-disabled search repeats, [128 native frames](renewal-replication-gallery.md)
and 107 CTests verify. No score or ecology changes: next discuss a frozen-model
world/schedule cross-evaluation to investigate transfer before further training.

That [frozen-model transfer diagnostic](renewal-transfer.md) is now complete.
Both B finalists beat the original on training worlds under either schedule set,
but lose on review worlds under either set. Schedule interactions differ between
replicas: R1 B/A loses in both crossed cells; R2 gains 11.15% in TR and nearly
ties (−0.27%) in RT. Neither schedule-only failure nor weather-only causation is
established. All 300 native calls, 120 full trial repeats, [40 repeated frames](renewal-transfer-gallery.md)
and 100 focused Python tests verify; 120 diagonal histories were reused. No new
training or score/ecology changes. Discuss a coverage-only training A/B with
broader development-world sampling and a separate fresh review panel next.

The [fixed 8/16-world renewal comparison](renewal-coverage.md) now gives modest
fresh-review gains: final W/N minimum credit improves **2.75% / 7.54%** in R1/R2.
R1 reverses under one schedule and one seed omission; R2 holds under both schedules
and all omissions. Both wide models beat the original, but R2 still loses on
the added training subset and species variety does not improve. All **2,084 new
native calls**, both complete wide-search repeats, [256 repeated frames](renewal-coverage-gallery.md)
and 114 focused Python tests verify. Narrow searches were reused; score, ecology,
schedules and mutation budget were unchanged (wide uses twice the evaluation
compute per candidate). Next discuss checking frozen W3 models on the earlier
failure cross, reusing existing controls, without more training or adoption.

The [frozen-finalist return check](renewal-return.md) now finds **no uniform
transfer fix**. On old RR, W/N changes are **−7.73% / +8.89%** for R1/R2, both
sensitive to one blocked seed omission. R2 W only gains 0.25% over original,
with opposing schedule signs; fresh late credit falls and single-species
endpoints rise to 7/8. R1 W/N loses in all four cells; R2 loses in TR despite
gains in TT/RT/RR. All 224 native calls, 96 full repeats,
[40 repeated frames](renewal-return-gallery.md) and 126 focused Python tests
verify. No new training or native changes. Next discuss an offline paired-cohort
audit before changing training coverage, aggregation or defaults.

That [offline cohort audit](renewal-cohorts.md) is complete with **zero new native
calls**. R1's additional late children confirm later; R2 has fewer, offset by
more carry-in credit. Exact minimum-period switching, seed funnels and mortality
attribution reconcile all forty old-RR histories. Five of R2 W's seven eventual
monocultures appear before day 62; shrubs disappear by about day two, while N
retains them in two matched conditions. All 219 focused Python tests and repeated
analysis/export checks pass. Next discuss a short startup-resource trace before
changing rewards or training again; the saved lifetimes do not identify water,
light or energy as the cause of natural deaths.

The [eight-day startup diagnostic](renewal-startup.md) now traces original and
R2 N/W on the selected world. W's founder shrubs exhaust energy overnight despite
ample water; a later shrub seedling instead spends its water on seven shoot
extensions without extending a root. N retains a smaller founder shrub, paying
seven instead of eight energy per upkeep charge, and reaches day eight with all
three species versus W's flowers only. Body geometry/income matters too: equal
34-node flowers enter their first night with different reserves and outcomes.
All 244 focused tests, full trace repeats, saved history prefixes and
[twelve native frames](renewal-startup.png) verify, using exactly thirty calls
and no training or native changes. This motivated the reciprocal focal-shrub
controller swap before fitness changes.

The [reciprocal swap](renewal-swap.md) is now complete: **only N controlling
founder shrub 2 in an N garden survives**. N in W still dies despite remaining
below the higher upkeep step: an extra seed purchase and other daytime budget
differences leave 20 less energy at the second sunset. W in N dies too, and
that one-founder change also shifts the ground-cover over an upkeep step;
the garden becomes flowers-only by day eight. All 58 experimental-host tests,
three focused default-build tests, forty fixed native calls, complete old
control records and [sixteen repeated native frames](renewal-swap.png) verify.
This is a fixed-world controller/background interaction, not general superiority
or proof of cooperation. It motivated the single-neighbor diagnostic before
altering fitness or training again.

The [one-neighbor swaps](renewal-neighbors.md) now show that switching either
the ground-cover or far-right flower alone to W kills the N-controlled focal
shrub near day 1.8. The other shrub causes a later day-6.8 death; the left flower
does not kill it within eight days. The ground-cover case has lower photosynthetic
income without an extra seed; the far-right-flower case has an unused seed-bank
slot permitting extra automatic spending. Three recorded tie-order differences
occur during night WAITs, including in the surviving case, not proof of the
death mechanism. All 128 renewal-family tests, forty new native calls, copied
references and [native image checks](renewal-neighbors.png) pass with no native
source/build changes. This motivated a focal second-daylight fourth-seed veto
as a causal diagnostic, not a permanent quota or a new fitness rule.

The [fourth-seed veto](renewal-seed-veto.md) rescues that shrub through day eight,
with three living direct offspring. Sunset energy rises from 187 to 235, with
identical other daylight budget terms and no changed growth decisions. But the
ground-cover buys a seed in the available bank slot on the same tick: its sunset
energy falls by 48 and it dies earlier. The endpoint changes from four flowers /
three ground-cover to one flower / five shrubs, not a general diversity win.
All 61 control CTests, six focused intervention suites, 65 default CTests, twenty fixed native
calls, full saved-control/prefix checks and [repeated native images](renewal-seed-veto.png)
pass. The probe stays host-only and off by default.

The [offline forecast audit](renewal-seed-forecast.md) finds that the existing
sunset-reserve gate would allow the observed shrub purchase: it predicts 224
sunset energy versus the actual 187. It would reject the ground-cover purchase,
but also overestimates its income (209 versus 183 sunset energy). Both earn only
seven more energy as integer light uptake cuts off before sunset. No extra
spending, overflow or body change explains the discrepancy. Dawn is a separate
constraint: 37 zero-income upkeep payments cost these bodies 259/296 energy,
more than the 256 storage cap, so a blanket zero-shortage requirement would be
too strict. Thirty-two Python tests and repeated, hash-verified offline analysis
pass, with no new native calls or rule changes.

The [fixed phase-aware shadow forecast](renewal-phase-forecast.md) now audits all
112 saved purchases. Mean sunset-energy error falls from 28.66 to 15.62 over
101 paired checkpoints, and from 16.70 to 3.30 on the 27 still-assumption-valid
sunsets. It predicts both known late-purchase death times, but 103 purchase
windows have later spending and morning energy can be overestimated by 148 even
before a recorded assumption break. Only two fully observed, assumption-valid
supported death outcomes and no equivalent survivor controls remain; this is
not a qualified survival policy. Two zero-light anchors are explicitly unsupported,
and nine windows right-censored. All 53 focused Python tests and repeated frozen
analysis/export checks pass, with no new native calls or rule changes. Next
discuss an exact guaranteed-dark-interval budget check, without extrapolating
unknown morning income or granting permission for later expenses.

The [exact dark-budget audit](renewal-dark-budget.md) now covers 170 spending
steps and 68 systematic evening states in those saved traces. Energy/stress
errors are zero on every assumption-valid prefix, and all 66 complete clean
outcomes match, including 15 evening intervals with shortages but living plants.
Nine expense records cross the local alive/dead boundary: seven growth and two
seeds, with shared/repeated events explicitly retained. Growth can spend reserves
and increase recurring upkeep; reproduction is not the only contributor. Most
daylight spending remains outside this check's scope, and future expenses still
break one-time projections. All 87 focused tests, repeated offline export and
frozen-provenance checks pass. No new native calls or runtime changes. Next
discuss a bounded host-only guard across optional spending during this interval;
do not treat local budget differences as proven counterfactual rescues.

That [host-only dark spending guard](renewal-dark-guard.md) now completes the
fixed native comparison. Deaths change **12 → 0**, all five founders survive
and all three species remain, but births fall **14 → 2** and neither guarded
descendant produces seeds within eight days. Both endpoints have seven plants.
Only nine attempts are denied: one founder-5 growth and eight founder-4 FINISH
retries; no seed/renewal denials occur. Downstream competition changes other
founders' fates, so these are not nine independent rescues. All 637 native
forecasts, the complete old control, exact repeats and [native images](renewal-dark-guard.png)
verify; 69 default and 66 control CTests plus both guard-specific suites pass.
Keep this rule experimental. Discuss a fixed multi-world, longer paired panel
that measures descendant reproduction as well as survival before promotion,
further tuning or training.

That [frozen four-world, 64-day panel](renewal-dark-panel.md) is now complete.
Natural deaths fall **45 → 21** without patches and **51 → 33** with patches,
but one patched world regresses **13 → 17**. Patched closing births rise
**9 → 11**, with full-day survivors **7 → 9**, while whole-run durable descendant
parents fall **18 → 11**. Both unpatched arms have zero closing births despite
continuing seed production and no full node pool. The guard retains three
species in 2/4 worlds in each condition, versus none in either control group.
All 128 fixed native calls, 32,536 forecasts, full ledgers, repeated analysis and
[48 fixed native images](renewal-dark-panel-gallery.md) verify. Seventy default
and 67 experimental-control CTests plus both guard suites pass. Of 397 rejected
attempts, 184 were already projected fatal before the expense. Next discuss a
read-only audit of remaining guarded deaths from these saved traces, including
the adverse world, before changing the rule or resuming training. This is reused
review evidence with one focal routing/layout/patch schedule, not qualification.

The [offline residual-death audit](renewal-dark-failures.md) now distinguishes
scope from arithmetic: **35** guarded energy deaths enter the dark interval
already projected fatal, **15** occur just after the horizon, and **four** are
water deaths. All 35 in-window deaths have exact predicted timing. For 31,
adequate dark-entry reserves would fit in storage; four observed bodies cannot
survive that interval even at the cap. Every one of 213 newly-fatal denials is
followed by interval survival; 184 already-fatal denials cover 18 case-specific
plants that die. Shared histories and retries are not independent outcomes.
The adverse patched world adds four under-reserved flowers and one post-dawn
shrub death after day 16. Specific receipts expose a last-daylight 32 → 33-node
extension and a separate paid FINISH. All 7,689 systematic windows, 1,100,869
valid-prefix comparisons, repeated analysis and 71 host CTests verify, with zero
new experimental native calls. The [two isolated expense-veto replays](renewal-purchase-veto.md)
are now complete: skipping the 32 → 33-node extension rescues flower 21 through
day 64 (34 seeds and one long-lived child). Skipping FINISH once merely delays
payment one ecology step, with the same death and final garden. The extension
arm has fewer natural deaths (17 → 14) and more durable descendant parents
(5 → 6), but loses shrubs, reduces living exposure and adds a closing energy
death. All 24 calls, exact prefixes/repeats, 374,175 live budgets,
[nine fixed native screenshots](renewal-purchase-veto.md#fixed-native-screenshots)
and 72 host CTests verify.

The [retry-aware FINISH diagnostic](renewal-finish-retry.md) now bridges the two
uncovered attempts, then hands back to the unchanged guard. Flower 22 survives
through day 64, makes 29 seeds and has four offspring: two energy deaths before
a day, two full-day survivors still alive. The eventual FINISH pays after dawn
at 72,210; stress recovers at 72,540. However, whole-world natural deaths rise
17 → 21, survivors 16/25 → 18/31, and durable descendant parents 5 → 7. Shrubs
disappear from living plants and the seed bank, living exposure falls 1.94%,
and a closing natural death appears. All 24 fixed calls, both byte-identical
frozen references, 13,780 forecasts, 372,464 live budgets,
[nine native images](renewal-finish-retry.md#fixed-native-screenshots) and 73
default CTests verify. No general spending rule, firmware behavior or training
objective is changed.

The [saved-trace recruitment audit](renewal-recruitment.md) now separates the
tradeoffs: the target rescue removes one death, while later offspring add five.
Post-intervention births rise 8 → 13 but day survivors only 6/7 → 7/13. All six
retry deaths occur before a full day; four bodies enter night under-reserved,
two cannot survive the dark interval even from full stores. All 46 newly
purchased shrub seeds expire, with spacing blocked in every mature snapshot.
Flower 22 occupies the control replacement shrub's site; the old shrub's patch
death is unchanged. Seed-bank order/reclamation reconcile rather than showing
a queue bug. All 1,053 seeds, 249,557 mature snapshots, 247,501 live budgets,
repeated analysis and 74 default CTests verify. Next discuss a shadow-only
storage-cap-aware growth check before enforcement; retain under-reserve and
species-retention limits. No new experimental native calls or policy changes.

The [full-night capacity shadow audit](renewal-night-capacity.md) now checks
all 16 saved panel trajectories and the retry case separately. The native upkeep
rules imply a 64/65-node boundary: minimum full-night reserves rise 240 → 270,
above the 256 cap. Among 11,668 paid extensions, four first crossings identify
four guarded energy deaths (one lifetime is duplicated across shared-prefix
conditions); 44 later extensions are not additional rescue opportunities.
Fifty other guarded deaths and all 96 control deaths remain unflagged. The
retry case flags the two oversized seedlings but not four smaller under-reserved
children. All 2,077,277 live budgets, repeated analysis, source/artifact hashes
and 75 default CTests verify. No growth is refused. Next discuss a bounded
host-only A/B, including action stalls and reproduction—not a permanent cap,
new training or firmware promotion.

The subsequent [full-night growth-guard A/B](renewal-capacity-guard.md) rescues
two of three targeted plants through day 64. They maintain leaves and produce
43 seeds but no offspring. The third enters night with 237 energy against a
240 minimum and dies six simulation seconds later than its control. Across
the four selected worlds, natural deaths fall 32 → 29, births 60 → 57,
full-day survivors 43/58 → 40/55, and durable descendant parents 9 → 8.
Closing births and survivors do not improve; species sets are unchanged.
The guard refuses 7,895 attempts on three plants, with no later paid growth
or FINISH on those targets. All 64 fixed native calls, exact controls/prefixes,
964,282 resource checks, [24 repeated images](renewal-capacity-guard.md#fixed-native-screenshots)
and 76/73/74 default/control/treatment CTests verify. Keep it host-only and
off by default. Next discuss following those 43 seeds through site blockers
and expiry in the saved traces, rather than equating adult survival with renewal.

The [rescued-parent seed audit](renewal-rescued-seeds.md) now follows all 43:
40 expire, three remain pending and none germinates. Every one of 10,171 mature
observations has a pre-existing living spacing occupant; none depends on dead
tissue or the rescued parent blocking itself. The shrub's entire possible
dispersal range, columns 3–9, is covered by two surviving founders. Post-step
light/water masks remain distinct from that code-order spacing proof. All
2,060 seeds and 500,004 mature snapshots across four traces reconcile; repeated
analysis/export checks, fourteen new synthetic cases and 77 default CTests pass.
No new experimental native calls or behavior changes. Next discuss a bounded
controlled-gap test, measuring recruitment and first-day survival without
relaxing spacing or treating adult persistence as successful renewal.

The [controlled-gap comparison](renewal-controlled-gap.md) exports founder
flower 1 at day 12, with all models and ecology rules unchanged. One new shrub
establishes at column 5 and survives through day 64, but its parent is founder
shrub 2, not rescued shrub 7. The rescued plant's seeds rise 15 → 20 with no
offspring; two reach spacing-free ground but expire with light/moisture blockers
in every mature snapshot. Births rise 4 → 5, full-day survivors 3/4 → 4/5 and
natural deaths remain two. One flower family disappears; closing births and
durable descendant parents remain zero. All 24 fixed native calls, exact
control/prefixes, 1,025 seeds, 221,701 live budgets,
[eight repeated images](renewal-controlled-gap.md#fixed-native-screenshots),
portable checks and 78/76 default/experimental CTests verify. Next discuss
decision-stage evidence for the two failed open-site seeds before changing
rainfall/lifetime/spacing or tuning an environmental turnover schedule.

The [exact germination trace](renewal-germination-trace.md) confirms that the two
failed open-site seeds never have water and light together in 496 mature checks.
Neither spacing nor capacity blocks them. The successful founder seed has
moisture 34 and light 97 at its first eligible check; its subsequent spacing
mask comes from the newborn itself. One failed-seed snapshot mislabels water-only
as water-and-light after growth, but the exact receipt is still ineligible.
All four repeated native calls, 1,044 saved-state checkpoints, 8,336 ordered
visits, portable checks and 79/77 default/experimental CTests verify. Next discuss
a single-rule germination-light-gate experiment, judged on seedling survival and
descendant reproduction. No ecology change or new training occurred here.

The [post-gap wet-germination A/B](renewal-wet-germination.md) now removes only
the immediate light gate after the identical day-12 export. Post-gap births rise
1 → 5, full-day survivors 1/1 → 3/5, but four treatment recruits die of energy
shortage and each arm retains only one post-gap recruit at day 64. Rescued shrub
7 has two children; one lives 2.555 days, neither reproduces. The historical
full-day reproducing-parent count improves 0 → 1 without an enduring new family
branch. Final living plants remain seven, with the same species/family counts;
all 31,744 mature checks in each closing window are spacing-blocked. All 28
fixed calls/repeats, 1,027 seed lifetimes, 220,984 live budgets, eight native
images, portable checks and 80/79 default/experimental CTests verify. No default
or device promotion. Next discuss an offline comparison of startup spending
and the first few nights of all six post-gap recruits before further rule changes.

The [saved-trace seedling budget audit](renewal-seedling-budget.md) now separates
the failures. Two early deaths have zero recorded income: their 64 startup
energy is split 28/36 and 32/32 between growth and upkeep, despite adequate
water. Two later deaths survive darkness, then fail the first dawn maintenance
at stress 7; survivors have either stress headroom or sufficient dawn income.
Child 12's final eight-energy FINISH is a specific untested deferral opportunity,
not proof of rescue. All six three-day/death windows, 3,183 live budgets, four
explicit terminal omissions, 15 dark windows, repeated portable analysis and
81/80 default/experimental CTests verify. No new native experimental calls,
mechanics or device changes. Next discuss a bounded, retry-aware FINISH deferral
through the first dawn payment.

That [bounded dawn-FINISH deferral](renewal-dawn-finish.md) now delays death by
only one maintenance cycle: 68,340 → 68,400. Ten refusals preserve eight energy
through the first dawn payment, but the later FINISH spends eight of nine energy
at stress 7, just before the next upkeep bill. The target makes no seeds or
offspring; day-64 population and closing renewal counts do not improve. All 24
declared calls, exact control/prefix/repeats, 221,022 live budgets, eight native
images, portable checks and 82/82 default/experimental CTests verify. Next
discuss a reserve-aware handoff for this same pending FINISH, not a general
policy or resource increase. No firmware/default changes or training.

That [reserve-aware handoff](renewal-dawn-reserve.md) now rescues the selected
shrub through day 64. Three additional refusals let FINISH pay eight from 19
energy, retaining 11; stress recovers to zero at 68,760. But its sole seed
expires without offspring. Births/deaths fall 9/6 → 7/4 because two later
seedlings never appear, and full-day survivor counts fall 6 → 4. Final population
and closing births remain seven and zero. All 36 fixed calls, both historical
arms, exact prefixes/repeats, 331,756 live budgets, twelve native images,
portable checks and 83/83 default/experimental CTests verify. Next discuss a
read-only reproductive-opportunity/bank-access audit before generalized policy
or training. No default, device or resource changes.

That [saved-trace access audit](renewal-reproduction-access.md) now separates
eligibility from ordered bank capacity. In reserve's closing 16 days, shrub 12
passes the independent prerequisites on 259 checks: 189 find the bank already
full and 70 lose the available slots to earlier parents. The final safety guard
is not evaluated on these blocked turns. All 128 closing expiries are replaced
immediately, with zero germination; the target's sole lifetime seed is also
spacing-blocked by shrub 9. All 331,756 live budgets and 1,541 purchases reconcile;
repeated analysis, independent Docker verification and 84/84 default/experimental
CTests pass. Zero new experimental native calls or rule changes. Next discuss a
bounded rotating purchase-order A/B, keeping capacity, gates and spacing fixed,
and score survival/establishment rather than more seed purchases alone.

That [rotating-order A/B](renewal-seed-order.md) now changes target purchases
1 → 42, including 0 → 13 late, without changing its survival or complete stress
history. Extra energy spending replaces overflow; water uptake funds the added
water cost. But all 10,405 mature target-seed observations are spacing-blocked,
and no offspring result. Both arms still make 513 seeds, have seven births/four
deaths, and zero late births. All 28 planting columns are spacing-blocked at
every post-noon checkpoint despite a free plant slot. All 16 fixed calls,
historical control, repeats/prefixes, 221,468 live budgets, four native images,
portable checks and 85/86 default/experimental CTests verify. Next discuss
establishment/competition mechanics; do not infer renewal from redistributed
seed purchases or promote this host-only rule.

The [approved spacing A/B](renewal-seed-spacing.md) now tests establishment.
With identical rotating purchases, reducing base spacing three → two after the
shared checkpoint permits 19 new seedlings; six of 17 eligible survive a day.
However, 16 new seedlings and three incumbents die, and the flower/founder-5
family disappears. Ten closing births replace the previous zero, but none of
the new parents has a full-day-surviving child within the horizon. Plant slots
are full at 93.6% of post-boundary checkpoints; no node-capacity blockage is
observed. Shared-root-cell exposure is zero in audited live steps, so this run
does not demonstrate direct uptake-order contention. All 20 native captures,
repeat/prefix checks, six images, 231,407 live budgets and independent portable
verification pass; 86/88 default/experimental CTests pass. Keep spacing
host-only/off. Next audit seedling light/energy and flower loss before changing
further mechanics or resuming training.

The [saved light/spending audit](renewal-establishment-light.md) now follows all
19 new seedlings and compares flower 5 at matching ticks/leaf sites. Five
seedlings have zero live-step photosynthesis numerator; a sixth accumulates only
248/255 of one energy unit before dying. Their 64 startup energy goes entirely
to shoot growth and upkeep, with ample water. Five of six first-day survivors
also exhaust startup energy before reaching light, so a blanket shade-growth
veto could block successful escapes. The flower's final-day income is 280 versus
732 in control, at constant body size; dimmer sampled leaves and lower condition
accompany 12 missed energy-limited renewal opportunities and eight terminal
energy shortages. No new experimental captures or mechanics. Discuss a bounded
canopy-transmission A/B that preserves nighttime zero production and judges
descendant survival and adult/species losses, not birth counts alone.

The [approved fractional-canopy A/B](renewal-canopy-transmission.md) now completes
that comparison. Both candidate seedlings survive and the flower/shrub 12 are
retained, but new full-day survivors fall six → two and neither new plant has a
germinated child. Incumbent losses fall three → one and endpoint species/families
rise 1/2 → 2/3; the eight plant slots are full at 99.0% of later checkpoints.
This is a mixed survival improvement, not continuing-renewal qualification.
All 20 fixed calls, historical control/prefixes/repeats, six native images,
243,005 live budgets and independent portable verification pass, as do 88/91
default/experimental CTests. Night still produces zero energy; default builds
and firmware are unchanged. Next separate allocation-only seed blocking from
overlapping space/moisture gates in the saved traces before a capacity or
competition experiment. No further light tuning, training or default promotion.

The [saved allocation audit](renewal-allocation-blockers.md) now establishes a
specific bottleneck: 53 distinct candidate seeds encounter code-order-confirmed
allocation-only rejection; 52 expire and one later germinates. Seven are shrub
13's offspring seeds, all expired. Of 5,542 confirmed observations, 5,538 have
eight living occupants, so slow dead-tissue reclamation is not the main cause.
Most other observations overlap spacing/moisture gates; shrub 14's three seeds
are always also spacing-blocked. All 1,034 seed lifetimes reconcile, with zero
new research captures or native changes; repeated/Docker checks and 89/92
default/experimental CTests pass. Next discuss one host-only eight-versus-sixteen
plant-slot diagnostic with the same 512 nodes and other rules, evaluating
further-generation survival and displaced pressure rather than births alone.
No capacity change or promotion is implemented by this audit.

The subsequent [eight-versus-sixteen plant-slot A/B](renewal-plant-slots.md)
keeps 512 nodes and all other rules fixed. It unlocks real descendant renewal:
new full-day survivors **2 → 17**, new full-day parents with a surviving child
**0 → 6**, maximum generation **2 → 4**. But incumbent deaths rise **1 → 6**
and endpoint founder families fall **3 → 2**. Plant occupancy peaks at 12, while
all 512 nodes are occupied at 65.4% of later checkpoints and throughout the
final 4.05 garden days. All endpoint tissue is living. The predeclared retention
gates fail, despite improved reproduction: keep this host-only/off by default.
Historical control/prefixes, 20 repeated captures, six images, 266,066 live
budgets and independent Docker verification pass; 90/94 default/experimental
CTests pass. Next discuss a saved-data node ownership/denied-growth and incumbent
death audit before changing allocation, body size or the node budget.

The [saved node/death audit](renewal-node-pressure.md) now separates these issues.
All 512 endpoint nodes are living; four plants retain 14 tips. The global
capacity gate suppresses even non-allocating WAIT/FINISH, although leaf renewal
continues. Four fatal incumbent stress episodes start with water shortage and
two with energy shortage; five of the six deaths involve already-tipless bodies.
The water-led plants stop renewing leaves under the water-reserve rule, so
declining energy production is not simply worse light. All 23,552 ownership
transitions and 209,462 live budgets reconcile; repeated/independent checks,
15 focused tests and 91/95 default/experimental CTests pass. No new research
captures or native changes. Next discuss a bounded full-pool action A/B, keeping
512 nodes and treating adult resource deficits as a separate problem.

The subsequent [full-pool action A/B](renewal-full-pool.md) allows the policy to
run without permitting new allocation beyond 512 nodes. It commits **6,224 WAITs**
and transactionally refuses **6,060 allocating EXTENDs**, but selects **no FINISH**
or exhausted EXTEND. Most WAITs are the existing night-growth wrapper converting
EXTEND. New full-day survivors fall **17 → 16**, durable new parents stay at six,
and all six previously lost incumbents still die. More births and less endpoint
node occupancy accompany changed turnover, not successful tip completion. Both
the mechanism and survivor gates fail: keep this host-only/off by default.
All 20 captures, historical control/prefixes, six images, 286,700 live budgets
and independent portable checks reconcile; 92/97 default/experimental CTests
pass. No training or device changes. Next discuss whether safe local shedding
of unproductive living structure could reclaim useful storage, establishing
topology/measurement needs before implementing pruning or changing capacity.

The [saved shedding-feasibility audit](renewal-shedding-audit.md) finds **146
zero-condition leaf nodes** at the full 512-node control endpoint, including
**110 continuously zero for at least a day**. These are not known-safe deletions:
the traces lack parent/child links and overlapping node roles, and **268**
full-day-zero control episodes later renew. The candidate has 56/46 endpoint
zero/day-zero nodes and 287 such recoveries. Guaranteed safe recovery remains
zero; optimistic headroom and per-owner upkeep bounds are not rescued seedlings
or measured resource savings. All 8,738,097 leaf-ordinal transitions and 6,780
renewals reconcile; parent/repeated/independent verification and 93/98 CTests
pass. No new native research calls or ecology changes. Next measure true
terminality with a bounded, observationally neutral topology census before
implementing a local shedding action. The existing gardener prune tool is a
tip hint, not storage reclamation.

The [read-only topology census](renewal-topology.md) closes that question:
**136 of 146** exhausted endpoint leaf nodes support descendants. Only **one**
passes the conservative terminal-removal filter, and it has been zero for less
than a day. There are zero or one candidates at each of eight fixed checkpoints;
no sampled full pool gains the four slots needed for a seedling. The large raw
zero-leaf count is mostly structural storage, not detachable leaves. All 194,270
original trace records match byte-for-byte with capture off/on; three fixed
native calls, repeated/independent analysis and 95/100 CTests pass. No pruning or
ecology change is warranted from this evidence. Consolidate the branch for review;
larger structural turnover requires a separate design discussion.

The first trained neural champion keeps every watered held-out garden alive
through 24 day/night cycles. Reproduction stops before the end of the test,
however, and most surviving plants are founders. Survival alone overstates
progress toward an ecosystem with continuing generational turnover.

## Reproduce

The baseline champion was produced from the repository root with:

```sh
make host-train-garden
```

This investigation used model payload CRC-32 `dc5e849d`, model-file SHA-256
`bd9f9c6ba7f5fd17309f917972da5f759c305c077798e1d4ba9a52701e2cd48b`.
The training settings were 8 generations, population 16, 2 trials per scenario,
7,680 ticks per trial, 32 mutations per offspring, and base seed `0x74726169`.
Running that command with changed ecology can produce different weights. Keep
the saved model/training report for a paired comparison instead of overwriting
them. The model was frozen throughout the investigation; held-out results were never
used to select another model.

```sh
docker compose run --rm firmware python3 benchmarks/garden-longevity/run.py \
  --output artifacts/garden-longevity-heldout \
  --trials 32 --seed 0x686f6c64 --jobs 3
```

The runner refuses an existing output directory. Choose a new directory for a
rerun. It verifies the model envelope/CRC against the training report, checks
that held-out seeds exclude both training seeds, freezes the model and training
report, and records source/binary/model hashes in `provenance.json`. Complete
evaluator reports are `cycles-02.json` through `cycles-24.json`; `summary.json`
contains aggregates and differences between horizons. Raw outputs remain under
the ignored `artifacts/` directory.

One Garden cycle is 256 ecology steps, 3,840 authoritative ticks, or 64 simulated
seconds. Thus the longest trial covers 92,160 ticks and 25 minutes 36 seconds.
The 32 seeds are paired across all three policies and all three existing scene
layouts. Shorter horizons replay prefixes of the same trajectories; the 1,440
runs are not 1,440 independent environments. The entire sweep took about 79
seconds on this host using three concurrent evaluator processes under UBSan.
This is host throughput, not a PicoSystem performance measurement.

## Results

At 24 cycles:

| Scenario | Policy | Gardens with living plants | Mean final living plants | Highest generation reached |
| --- | --- | ---: | ---: | ---: |
| Unassisted | Baseline | 0/32 | 0 | 0 |
| Unassisted | Adaptive | 0/32 | 0 | 0 |
| Unassisted | Neural champion | 0/32 | 0 | 0 |
| Irrigated | Baseline | 30/32 | 1.97 | 2 |
| Irrigated | Adaptive | 32/32 | 3.69 | 2 |
| Irrigated | Neural champion | 32/32 | 1.13 | 11 |
| Crowded, irrigated | Baseline | 31/32 | 2.50 | 2 |
| Crowded, irrigated | Adaptive | 32/32 | 4.19 | 1 |
| Crowded, irrigated | Neural champion | 32/32 | 2.00 | 1 |

There were no seed-only survivors at these final checkpoints. All unassisted
trials were already extinct by cycle 2, for all policies. These plots receive
initial watering but no ongoing external water. Irrigated plots receive 8 water
units at every column every 960 ticks, independent of policy and population.

The neural irrigated lineage progression was:

| Cycles | Mean living plants | Cumulative established offspring, all 32 trials | Maximum generation | Trials with new births since previous checkpoint |
| ---: | ---: | ---: | ---: | ---: |
| 2 | 1.28 | 67 | 2 | 32 |
| 4 | 1.25 | 88 | 4 | 13 |
| 8 | 1.19 | 109 | 8 | 8 |
| 16 | 1.13 | 116 | 11 | 2 |
| 24 | 1.13 | 116 | 11 | 0 |

Crowded neural gardens reach 71 established offspring in aggregate by cycle 2,
then produce no more births. By cycle 24 every crowded neural garden contains
exactly two founder flowers. Irrigated neural gardens retain all 32 founder
flowers and just four descendant ground-cover plants across three trials.
No neural shrubs survive. Adaptive irrigated gardens retain all three species
in every trial, although their reproduction also stops.

Between cycles 16 and 24, **all three policies in all scenarios** record zero
new births, deaths, seeds, and policy decisions. Maintenance and resource/light
updates still run; plants with no remaining growth tips have no policy decisions
to make. No late activity was hidden by sampling only the final population.

## Why the populations become quiet

[`garden_inspect.c`](../../sim/garden_inspect.c) is the maintained host-only observer
linked to the existing pure simulation core (formerly `inspect.c` here).
It prints JSONL at initial state, cycle boundaries, and birth/death changes,
including plant ancestry, resources, growth tips, flowers, and spent flowers.
It does not change the simulation or policy. Build it after `make host-build`:

```sh
docker compose run --rm firmware cc \
  -std=c11 -Wall -Wextra -Werror -Wconversion -Wsign-conversion \
  -fsanitize=undefined -fno-sanitize-recover=undefined \
  -Isrc -Isim sim/garden_inspect.c \
  build-host/libtoy_factory_simulator_core.a \
  -o artifacts/garden-longevity-heldout/inspect

docker compose run --rm firmware artifacts/garden-longevity-heldout/inspect \
  artifacts/garden-longevity-heldout/champion.tgm \
  irrigated neural-candidate 0xa7b5ccea \
  > artifacts/garden-longevity-heldout/trace-irrigated-neural-a7b5ccea.jsonl
```

The representative seed `a7b5ccea` was also traced with the crowded neural
scenario and the irrigated adaptive policy. All 15 trace checkpoint hashes
(three trajectories times five horizons) match the corresponding evaluator
reports exactly.

A further replay of all 64 watered neural trials matched every terminal hash.
All 100 surviving plants have zero growth tips: 96 founder flowers and four
descendant ground-cover plants. The two 37-node ground-cover survivors have
used all four flowers each. The other two have 43 and 45 nodes, retain unused
flowers, and require 288 and 264 reproduction energy respectively, exceeding
the 256-unit storage cap with their own reserve traits. Thus both terminal
conditions below also occur among the neural survivors.

The deepest lineage, irrigated neural seed `a7b5ccea`, has its generation-11
ground-cover birth at tick 41,520 (cycle 10.8125). That plant dies at tick 44,220
(cycle 11.515625). Its generation-12 seed never germinates; the lineage's final
seed expires at tick 46,680 (cycle 12.15625). Later survival belongs to the
original founder flower, not that ground-cover lineage.

The surviving founder has 36 nodes, 20 root nodes, 8 leaves, zero growth tips,
and one flower that has already produced its seed. At cycle 24 it has 251
energy, 510 water, and zero stress. Both founder flowers in the crowded trace
have the same structure and resources. Two existing mechanics explain these
terminal structures:

1. A flower produces only one seed, tracked by `FLOWER_SEEDED`. There is no
   automatic flower renewal or regrowth after all tips finish. Resource-funded
   maintenance can keep that fully grown plant alive without age-driven death.
2. Larger plants can require more energy to reproduce than they can ever store.
   With the default reserve trait, reproduction requires
   `48 + max(96, ceil(node_count / 8) * 40)` energy, while storage caps at 256.
   The adaptive trace's 57-node shrub and 59-node ground-cover each require 368
   energy. Both retain unspent flowers, but the energy gate is unreachable at
   those body sizes. A default-trait plant crosses this limit above 40 nodes.

These conclusions follow from `update_reproduction`, `plant_can_reproduce`,
`unseeded_flower_index`, and `update_plant_maintenance` in
[`garden_world.c`](../../src/garden_world.c), plus the traced structures. They
are not evidence of a host stall or a neural-only failure.

## Implications for the next experiment

The champion has useful early reproductive behavior, but is not generally
better than adaptive: it preserves fewer plants and loses species diversity.
Generation depth describes historical progress and does not prove continued
reproduction. Likewise, the existing "established offspring" gate only requires
age 5 ecology steps (1.25 seconds), no stress, and an active leaf. It does not
require that offspring survive a complete day/night cycle or reproduce.

Before a longer training search, discuss lifecycle changes that permit ongoing,
resource-funded reproduction and review the reserve/storage mismatch. Possible
choices include flower renewal, bounded regrowth, and eventual tissue turnover;
they change the ecology and should be designed explicitly. Then evaluate
late-window births, descendants surviving a complete cycle, and surviving
founder/species lineages alongside total survival. Keep a separate held-out
seed set when tuning or selecting models.

This baseline investigation left ecology, fitness ordering, neural weights, firmware,
and device state unchanged. It tested unseen seeds in the existing layouts,
through 24 cycles; it does not establish behavior in arbitrary layouts or
indefinitely long runs.

Validation: all 13 existing host CTests passed. The inspector compiled with
strict conversion warnings and UBSan, and passed the repository formatter.
