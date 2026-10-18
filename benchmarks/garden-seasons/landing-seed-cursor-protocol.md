# Purchase driven seed priority comparison

Compare fixed reproduction order with a persistent purchase-driven cursor in
the six gardens from the day-352 dieback follow-up. The question is whether
broader access to the existing eight seed slots produces more established
offspring, not simply more buyers. This is a host-only diagnostic, with no
training, new hazard events, firmware deployment or default promotion.

## Fixed panel and interval

Use the unchanged W2 model and build settings, seeds `3a7e45e6`, `366928c6`
and `275c8982`, each in ordinary and crowded rain-fed layouts. Both comparison
arms retain the fifteen original spatial dieback events at days 192–304.
They are continuations of the prior **treatment** histories; “fixed” below
does not mean the old no-dieback control.

Keep weather, construction/resource guards, placement choices, seed fees,
32-day viability, eight plants, eight seeds and 256 nodes unchanged. No
gardener, irrigation, soil wicking, named-parent preference or paid seed
replacement is enabled. Activate the cursor strictly after day 320 and end
both arms at day 384. Freeze this protocol before experimental calls.

The primary birth cohort is `(320,352]`. Every member then has complete
potential follow-up through ages sixteen and thirty-two days. Births after
352 are secondary observations, with censoring retained. Preserve all six
pairs regardless of outcome.

## Cursor semantics

Store the last successful buyer's stable lineage ID in the host run, initially
zero. On each maintenance step strictly after activation, begin reproduction
at the living plant with the lowest ID greater than that buyer; wrap to the
lowest living ID when no successor remains. Visit every stored plant once
in the existing cyclic array order. Do not reorder plant storage, growth,
uptake, seed aging or germination.

After successful purchases, retain the last buyer in that step's actual visit
order. A full bank, failed prerequisites, empty population or a step with no
purchase leaves the cursor unchanged. A removed buyer does not reset it;
new plants enter the order under their new IDs. Preserve all ordinary
reproduction costs, cooldowns, random draws and seed placement. Do not reserve
space for an ineligible plant. Other rotation modes and seed replacement
are incompatible with this opt-in mode.

Cursor configuration and state belong to run identity, not the world/model
ABI. Every step publishes world, cache and cursor together on success;
failure must leave them and caller-owned audit outputs unchanged. Observer
presence must not affect cursor advancement.

## Calls and evidence

Exactly 36 planned calls, six per phase:

1. Cursor-configured day-320 anchors, checked against all six saved treatment
   histories. Only the explicit cursor identity wrapper may differ; worlds,
   ledgers, boundary observations and pixels must match.
2. Fixed-order day-352 anchors matching the complete saved treatment results
   and observed day-320-to-352 trace segment.
3. Fixed-order day-384 runs.
4. Cursor day-384 runs.
5. Exact traced cursor repeats through day 384.
6. Cursor runs without file observers through day 384.

Anchor phases gate every longer experimental call. Record stand, adult and
reach traces for traced calls, with stand/adult windows starting at day 320.
Retain all twelve day-384 comparison frames in fixed panel order. Authenticate
source snapshots, model, binary, build configuration, arguments, results and
compressed/restored trace bytes. Compress and verify each trace before
removing its redundant raw representation. Do not overwrite any old bundle
or automatically retry a failed experiment.

## Outcomes and checks

Primary outcomes are sixteen-day and thirty-two-day survivors in the fixed
birth cohort, and distinct parents of those established offspring. Report
per-pair counts before aggregates. Also retain all births, seed outcomes,
surviving ancestry, established parent–child pairs, occupancy and endpoints.

A positive diagnostic requires more sixteen-day survivors in at least two
pairs, no pair losing primary sixteen-day survivors, no extra death of a
plant living at day 320, and no additional endpoint species loss or empty
world relative to fixed order. Thirty-two-day outcomes, extra natural deaths,
young mortality, paid costs and energy/water shortage exposure remain visible
even if the diagnostic passes. A diagnostic pass is not environmental
qualification or permission to train.

Independently reconcile the cursor from observed successful purchases, every
ordered bank visit, sequential seed admission and complete ledgers. Balance
resource flows and terminal discard during `(320,384]`. Check repeat results,
trace bytes and frames, plus observer-free results and pixels. Any missing
history, changed anchor, bookkeeping discrepancy or observer dependence stops
the run without interpreting partial output as a completed comparison.
