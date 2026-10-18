# Waiting time priority for seed purchases

Status at declaration: implementation and research calls have not started.
Compare a host-only waiting-time policy with the current purchase-driven cursor
after the [non-buyer diagnosis](landing-nonbuyer.md). This changes access to seed
slots, not resource requirements, seed viability or germination order.

## Fixed policy and common history

Use the six ordered gardens and W2 model from the frozen
[competitive-renewal capture](landing-competitive-renewal-results.json.gz), SHA-256
`099d2550d8037b3148b9c135a53b3fe3d5e971151234fa540ad8dbc6231073dc`.
Both arms retain the fifteen diebacks ending day 304 and the purchase cursor
starting strictly after day 320. All settings, capacities and costs stay fixed.

In the treatment only, replace cursor visit order strictly after **day 384**
with ascending last-successful-purchase tick; a never-buyer uses its birth tick.
Break ties by ascending stable lineage ID. Visit all stored plants in this
order; the existing checks skip ineligible/dead plants and preserve all fees,
flower, cooldown, daylight, stress, resource and bank-capacity gates. No slot is
held for an ineligible plant. Do not modify seed-bank germination order or RNG.

Keep at most eight lineage/timestamp entries in host run state, tracking actual
births and paid purchases from tick zero, including before activation. Reclaim
entries with stored bodies; slot compaction must not transfer another plant's
history. Publish history only on successful steps and include active policy
state in run identity. Zero configuration preserves existing hashes and behavior.
The device world, neural ABI and firmware have no new fields or policy.

## Bounded collection and identity gates

Build one isolated sanitized host executable with the same experimental build
settings as the source capture. Freeze protocol, actual source inputs, executable,
model and build settings before research calls. Unit/short CLI contract fixtures
are implementation tests, not additional panel experiments.

Exactly **48 research calls**, at most two concurrent, in fresh paths:

1. Twelve day-384 anchors, both arms for every garden. Controls must reproduce
   the saved cursor result, full ledgers and pixels exactly. Treatment anchors
   must match after accounting only for the new declared state/hash wrapper.
   Reconstruct waiting timestamps independently from the saved ledgers.
2. Twelve day-512 endpoints, retaining all paired frames. Controls must again
   exactly match the saved cursor endpoints.
3. Twelve exact day-512 repeats, requiring identical results, ledgers and pixels.
4. Twelve day-512 calls without framebuffer capture, requiring identical results
   except the absent framebuffer CRC.

No large per-step traces or training. Preserve failures and stop on a mismatch;
no automatic retry, substitute seed or widened horizon. Store compressed portable
results and all twelve endpoint images. Snapshot actual build/analysis sources,
not previous full bundles. Authenticate collection inputs again at completion.

## Fixed evaluation and interpretation

Reuse the exact `(384,512]` population, cohort and diversity definitions in the
[competitive-renewal protocol](landing-competitive-renewal-protocol.md). Every
anchor is unchanged, so baseline species/family identities are shared. Each
32-day birth window `(384,416]`, `(416,448]`, `(448,480]` must produce a 32-day
survivor, and at least one direct parent–child pair must both be born in that
cohort and survive 32 days. Late births remain separately censored. Individual
adult deaths are recorded, not automatically vetoed.

A broad within-panel signal requires all six treatment worlds viable, at least
four passing renewal, coverage of all three weather seeds and both layouts, and
strictly more renewal-passing worlds than cursor. Any loss of baseline species
or families retained by cursor, or lower variety coverage, is a diversity
tradeoff requiring discussion. Publish all worlds and paired regressions.

Also report primary-cohort buyers, seed purchases and fates, descendants of those
recruits, and waiting-state consistency. More equal purchases alone are not a
renewal success. Do not equate a lineage ID in diverged histories with the same
individual. A positive result requires fresh conditions before generalization;
there is no automatic default promotion, training or firmware deployment.
