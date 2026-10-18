# Afternoon maintenance reserve comparison protocol

Test whether requiring stored energy for afternoon maintenance increases rescues
the two remaining first-night failures without losing the existing rescue or
the two successful checks. This is a diagnostic comparison of selected cases,
not fresh qualification, a population policy or training.

## Frozen inputs and treatment

Use the five cases, model and world from the root-energy comparison. Both arms
buy the same root at birth tick T and run its existing energy eligibility guard
at ecology ages 2 through 256 for that named living offspring born at T. The
control is the previous candidate, not the root-only control.

| Order | Lineage | Birth tick T | Column | Role |
| --- | ---: | ---: | ---: | --- |
| fixed | 45 | 859860 | 25 | successful check |
| fixed | 46 | 905595 | 3 | successful check |
| rotating | 48 | 899130 | 27 | retain previous rescue |
| rotating | 49 | 906570 | 12 | remaining energy failure |
| rotating | 50 | 906720 | 27 | remaining energy failure |

Only the candidate adds this condition: if a daylight EXTEND can allocate a
node, raises `max(1,ceil(nodes/8))`, and the sun phase is at least noon (64),
require post-purchase stored energy to cover the existing forecast's remaining
daylight upkeep plus its night upkeep, with zero future-income credit.
Equality is allowed. Apply at 8→9, 16→17 and 24→25, not as a hard node limit.
The ordinary node budget still applies.

Use current observations only. The ordinary species/vigor price and maintenance
timing are unchanged. WAIT, morning decisions, within-band growth and
nonallocating actions receive no additional restriction. The original energy
guard still rejects paid night growth. The extra guard ends with the original
guard at age 257 (T+3840); the birth/root purchase remains unguarded.
No resource grant, future-world access, model change, priority/destination/memory
rewrite or extra random draw. Combine the new condition with existing budget,
water and energy eligibility before normal first-wins priority arbitration.
Keep the ordinary all-ineligible fallback and executor.

Pin root-energy results SHA-256
`dca98970b1efbd6552df4796c280fcb0883bc959f226d569531353a760abe778`
and its verified raw-bundle manifest
`793e82ab64e589b6fbfcde0c451e28560385a75dc583a0260cfbe8d20f1a26c0`.
Retain earlier pinned inputs and model SHA-256
`f2dc989380339614dc512f64f11f2bf03f7079c465c4c9bd18895044ec3e1567`.
The motivating saved audit is pinned at
`7943e9edb3b2e4c1f8f30925d46bbce1a7d5a5ca8ed7f70ee228f2694fd4e14b`.

## Budget and acceptance of evidence

Exactly forty native experiment calls: five cases, two arms, four calls each.
Capture post-root T, first-day T+3840, day-256 full trace and its exact repeat.
Stand/resource traces span T−15 through 983040. Tests are separate from this
experiment budget. No parameter search, extra experiment calls or cutoff/margin
adjustments after examining outcomes. Retain adverse or unchanged results.

Freeze this protocol, source, executable, build configuration and inputs before
collection in a fresh no-clobber bundle. Do not edit source during collection.
Controls must reproduce all saved candidate checkpoints, pixels and overlapping
traces. Pair prefixes must agree after normalizing configuration identity.
Repeats must agree in JSON, pixels and both traces. Existing trace schemas and
unconfigured identities remain unchanged; add a separate observational schema
and candidate run identity.

Independently recompute the extra condition, scope and combined arbitration for
every captured bid. Record where it first changes a choice, checking matching
prior observations rather than attributing already-diverged decisions to the
guard alone. Reconcile focal resource budgets and follow through the second day
and day 256 after the guard ends. Retain full population outcomes, reproduction,
offspring, seed-bank effects, resource shortages and censoring. Do not match new
descendants by reused cross-arm numeric IDs.

Report all five pairs, with a screenshot gallery, portable receipts, raw traces,
offline reanalysis and corruption tests. Focal survival alone does not establish
renewal; check seed production and confirmed descendants separately. Treat harm
to successful cases or other plants as evidence against promotion. Broader fresh
validation is required even if this selected panel improves. No device/default
policy changes, commit, push or PR changes in this step.
