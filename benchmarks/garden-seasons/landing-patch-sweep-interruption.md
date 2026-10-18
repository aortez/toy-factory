# Repeated dieback experiment validation checkpoint

This preserves the earlier interruption checkpoint. The
[completed comparison](landing-patch-sweep.md) now records the approved
continuation and final results; the pending-work statements below describe
the state at the interruption, not the current experiment status.

The fixed spatial-dieback experiment is **incomplete, stopped after an auditor
error**. Twelve of its twenty-five native research calls finished: all five
archived baselines, all five new controls, and the first two treatments. The error is
corrected and both saved treatment histories now reconcile offline. No
ecological benefit or failure is concluded from this partial panel.

The [protocol](landing-patch-sweep-protocol.md) remains unchanged. It asks whether
repeated, lineage-neutral openings let post-day-192 plants produce children
that also establish, rather than merely allowing old seeds to refill isolated
vacancies. Pools, controller, weather, resource rules and seed behavior stay
fixed. This is host research, not a default mortality model or device change.

## What stopped collection

The auditor initially expected stored plant age to equal elapsed ecology steps
since the recorded birth. That is true for founders, but an offspring germinates
before the same step's growth phase increments its age. Its stored age is
already one on its birth step. The expected receipt therefore needs an extra
one for offspring, without changing elapsed-time survival calculations.

The ordering is explicit in `src/garden_world.c`: `update_seed_bank` precedes
`grow_plants`, which increments living plant ages. The new host event simply
copies that existing counter. This was an analysis error, not a simulation
error or a reason to change seedling behavior.

Both already-running treatments were retained. No later batch, repeat or
observer-free call launched. No research call was retried. The frozen source
archive, original binaries, complete raw observations and results remain in
`artifacts/garden-landing-patch-sweep-v1`. The corrected analysis was applied
offline, with native process launches forbidden.

The only collector change after capture replaces the offspring age equality
and adds its explanatory comment. Its captured SHA-256 is
`24fb404ec6f437cbb33f8d53468248834d1414e0a3e76274dc3c88426cab3116`;
the corrected source is
`c50c90426ae50da32c6d2abd67db3d20ec4f0ad5c9bcb7c4bd833b20e7fc15ec`.
All captured C and header files are unchanged. The original source archive is
not rewritten to conceal this correction.

## Checks completed

All five archived day-288 results, frames and traces reproduce exactly. All
five new day-320 controls preserve their archived unforced histories and pass
the complete resource, seed, slot and daily-census audit. The first two
treatments now pass the same audit, including every event and imposed resource
discard. Their pre-event observations and ledgers match their paired controls.
These checks do not substitute for the remaining panel or exact repeats.

The new implementation is host-only and transactional. Tests cover empty and
multi-victim patches, young plants, age values above 16 bits, rollback after a
late ledger failure, unchanged off-path results, option exclusions and cohort
boundaries. Thirty native Garden suites and eight focused regression suites
passed; those groups overlap and must not be added into a distinct-test count.
The Python contract suite also checks existing archived observations without
simulating another world. The full-capture test remains skipped until a
complete experiment exists.
The final Python run passes eleven checks and skips only that full-capture
check. Documentation source and 221 local links/anchors were checked; rendered
Markdown layout was not previewed.

The [portable interruption record](landing-patch-sweep-interruption.json.gz)
retains the twelve call receipts, complete ledgers, verified accounting,
original and corrected source identities, raw-file hashes, and the exact
thirteen pending calls. It is explicitly marked interrupted and has no success
verdict. Regression tests recheck it with process launches forbidden. It is
not accepted by the full-capture verifier as a finished experiment.
Its SHA-256 is
`de9d7713a9f9391e0bf52eb8a5f6b01f7339b474bee969270a720f28ca32bde0`.

## Remaining work

Three treatment worlds, all five exact repeats and all five observer-free
treatments remain. Do not replace the existing worlds, retune the schedule or
silently restart with a selected subset. A continuation should preserve all
twelve completed calls and the original binaries, explicitly record this
auditor correction, and run only those thirteen pending calls. Then verify
the complete raw bundle and produce the prescribed ten-image endpoint gallery
and all-five-world comparison.

There is no complete result artifact, gallery or ecological recommendation
yet. No training, flashing, ordinary ecology change, commit or push was part
of this experiment. See the [tool guide](../../docs/garden-landing-tools.md#test-repeated-spatial-dieback)
for the fixed schedule and verification boundaries.
