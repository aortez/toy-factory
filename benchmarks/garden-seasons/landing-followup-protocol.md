# Follow late garden replacements through day 288

Status: **FROZEN before new native outcomes**. Extend the existing capped garden
panel by exactly two 16-day seasonal cycles. The question is whether the young
replacements and pending seeds identified by the
[vacancy audit](landing-vacancy-sequence.md) persist and reproduce, rather than
whether a new environmental intervention can create more activity.

## Fixed conditions and run budget

Keep all 32 primary worlds: the original eight order, guard and root-allocation
combinations in each of `cap`, `cap-wick`, `wide-cap` and `wide-cap-wick`. These
share weather seed `f7ee4528`; they are not 32 independent weather replicates.
Keep the saved model, build options and intervention onset at tick 626580.
Change only the landing CLI ceiling from 256 to 288 days. Do not change the
general evaluator/training horizon, ecology, aging, capacity, placement, fitness,
device defaults or firmware. Keep the original harm checks; this follow-up is
not permission to waive or re-score them.

Pin the original portable result at SHA-256
`390669aba064732072c82e2170ad1d6f7872612710bc1c6501ad3351c8ad3b62`
and the vacancy result at
`f58fe1034af55a12349abfbd717ce69581bb4991824d1ae17ded88be36aff135`.
The original raw manifest is
`4a94df9dcc4f53c980e3631b58dc3fd853c3f03a68678d335127ab09f7a83001`.

Allow 68 panel simulations, excluding ordinary unit/boundary tests: 32 rebuilt
day-256 identity checks, 32 day-288 replays, and four exact day-288 repeats.
Repeat the fixed-order, dawn-guard, ordinary-root-allocation world in every arm,
chosen before outcomes. Run no training. Stop on a failed identity, incomplete
trace, exhausted diagnostic ledger or sanitizer error; do not substitute worlds.
Do not automatically extend the stopping point or tune parameters afterward.

## Identity checks and retained evidence

All 32 day-256 checks must pass before launching any extended world. Match the
entire saved result, including world/run hashes, complete lineage/seed ledgers,
and exact framebuffer bytes by SHA-256. Capture the full reach trace and compare
it to the original; compare the final stand, adult and direction rows exactly.
The latter three traces can be restricted to tick 983040 to avoid duplicating
large earlier histories. Omit the earlier bounded uptake observer; it is not a
rule. Independently verify unchanged simulation and observer source identities.

Re-simulate from tick zero, not an invented portable save state. Day 288 is tick
1105920. Retain full reach traces and stand/adult/direction traces over the
inclusive interval 983040..1105920. The shared boundary row must match the
day-256 check. Every reach row through day 256 must match the original prefix;
only its final completion record is different. Truncating extended event ledgers
at day 256 must exactly recover the saved ledgers, including purchase counts
and seeds that were then pending. Capture final pixels for every primary run
and the four repeats, with a fixed-order gallery for manual review.

Keep exact arguments, binaries, build settings, model, source archive, results,
trace framing and artifact hashes. Preserve existing artifacts and use fresh
outputs. Bounded trace windows reduce disk demand without deleting evidence.

## Followed cohorts and new interval

Freeze cohort membership from the saved day-256 ledgers. Follow all offspring
born in (224,256], all direct replacements previously classified as censored at
32 days, and every seed pending at day 256. Report survival to ages 1, 16 and
32 days, deaths, seed purchases, germinated children and children surviving one
day. Preserve exact identity; do not select only successful plants. Distinguish
ever producing a seed/child from reproduction during the extension.

For the new interval (256,288], report births, deaths, reclaimed plant slots,
living/stored occupancy, seed purchases and bank outcomes. Count concurrent
reclamation separately from births, retain dead stored occupants, and reconcile
these counts with the complete ledgers and trace clocks. Summarize by arm and
retain per-world records so different guards and allocators are not hidden.
New offspring can still be censored at day 288; the frozen old cohorts cannot
be censored for a 32-day survival outcome. Report maximum lineage/purchase
ledger usage against the existing 4096/65536 host limits.

## Verification and interpretation

Test the new CLI maximum and one-past rejection, trace-window bounds and
observational equivalence. Retain existing age-wrap and ledger-exhaustion tests.
Test prefix truncation, pending-seed resolution, age-boundary deaths, cohort
membership, complete panels, trace framing, repeats and tamper detection.
Reanalyze captured results offline, with native launching forbidden, before
publishing a portable result and concise report. Distinguish a bounded recorded
renewal sequence from sustained ecological diversity or a validated controller.
Propose the next decision from the observations; do not promote a rule here.
