# Long-lived non-buyer diagnostic protocol

Status at declaration: no diagnostic replay has run. This passive follow-up to
the [seed handoff diagnostic](landing-seed-handoff.md) investigates purchase
eligibility, not germination order or a change to the ecology.

## Fixed scope

Use S2 ordinary (`366928c6-rainfed`), cursor arm, from the frozen day-512
competitive-renewal capture. Plant 41, a child of 36 at column 24, was born at
tick 1,593,525 and remains alive at tick 1,966,080 without buying a seed.
These are previously recorded ledger facts, not diagnostic outcomes.

Record its entire observed life, inclusive ticks **1,593,525..1,966,080** every
15 logic ticks. Use the existing `--stand-trace --stand-dawn` observer: all
ordered reproduction visits, stored plant order, morphology and growth bids.
No new C instrumentation, unwindowed observer, rebuilding, training, firmware
deployment, model change or rule intervention is planned.

## Replay validity and storage

Run exactly two identical frozen histories through day 512. Match both complete
result objects (including all lifetime ledgers) and framebuffer bytes to the
original observer-free endpoint. Match the two raw traces byte for byte.
Authenticate the original executable, model, build settings, source archive
and manifest before and after collection. Preserve failures; no automatic retry.

Reference those original inputs instead of duplicating their bundle. Losslessly
gzip each newly generated trace, verify its decompressed hash and byte count,
then remove only its redundant raw copy. Keep process/argument receipts, file
hashes, and a portable excerpt containing every reproduction visit plus every
focal body and growth bid. Full compressed traces remain locally available to
check extraction. Outputs must be fresh; allow at least 2 GiB temporary space.

## Analysis and limits

Reconcile every visit with the lifetime and seed ledgers, including seed-bank
releases before reproduction and earlier buyers within each step. Check the
successful-purchase cursor against stored order. Preserve overlapping blockers:
cooldown, maintenance cadence, bank capacity, death, stress, daylight, generation
limit, energy, water and ready flower. Separate intrinsic ineligibility, bank
full at entry, openings consumed by earlier buyers, and actual purchases.

Report complete lifetime coverage, flower/body changes, resource ranges, and
eligibility at bank openings. Growth bids are explanatory context, not proof
that a different growth policy would work. Do not turn overlapping gate counts
into mutually exclusive causes, infer a counterfactual from visit order alone,
or generalize this selected plant to the six-world panel. A further intervention
requires a separate proposal; existing renewal criteria and defaults stay fixed.
