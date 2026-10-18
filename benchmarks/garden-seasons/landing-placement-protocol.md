# Spacing aware seed placement comparison

Test one host-only placement rule on the reserved-shoot policy. Use the same
twelve frozen model/world pairs as the budget screen: six steady and six
seasonal, 192 Garden days, gardener off. Retain the original eligible-32 and
reserved-shoot controls. No training, model changes, range changes, ecology
changes, or renewal-score changes are allowed.

The frozen budget input is `landing-budget-results.json.gz`, SHA-256
`bad5297fa26ad52b93a899e3d0f0fcd3255a6b5e214e1120f68bc3902e455640`.
The motivating reach audit is `landing-budget-reach-results.json.gz`, SHA-256
`93cba7dfac249a4cca2326e6e163b89856f7d0e1268f3ac0a6eb0e3d7ca637aa`.

## Fixed placement rule

At an otherwise ordinary paid seed purchase, use the actual parent's origin
and dispersal trait to enumerate the same six nominal choices. Retain duplicate
columns from boundary reflection; do not deduplicate them. Mark each choice
blocked using the native plant-spacing rule at reproduction time, including
retained dead plant slots. Seeds themselves do not reserve sites.

Let `r` be the existing dispersal RNG draw and `original = r % 6`. This is the
same index selected by ordinary direction/distance arithmetic. If the original
choice is spacing-clear, keep it unchanged. If it is blocked and at least one
choice is clear, form the ascending list of clear **choice indices**, and select
index `(r / 6) % clear_count` from that list using integer division. If every
choice is blocked, retain the original landing. This deterministic mapping
does not claim a mathematically uniform conditional distribution.

Do not veto, delay, discount or refund the seed purchase. Keep the existing
dispersal draw, genome-mutation draws and visual offset. Do not consult moisture,
light, cold, future weather, plant/node capacity, or predicted seedling survival
when selecting a column. All ordinary germination and growth gates still apply.
Keep the same 32-node cap, reserved shoot path, water eligibility, seed costs,
cooldown, dormancy, bank capacity, lifetime and species mechanics.

## Identity and controls

Use explicit `placement-replay --shoot-reserve off|on --seed-placement off|spacing`.
The three fixed arms are eligible/off, reserved/off, and reserved/spacing.
Both off arms must match their archived budget controls after removing only
the new command/configuration identity. They must also match complete raw
recruitment receipts and endpoint framebuffer bytes. Existing budget/growth
commands and their identities remain unchanged.

`GLP1` wraps the underlying `GLB1` run hash, little-endian, followed by placement
version1 and enabled0/1, using FNV-1a. Runtime placement state is caller-owned,
copied with host checkpoints and never added to the persisted world/model ABI.
The callback and observation are absent from the Zephyr policy structure.

## Collection and verification

Freeze this protocol, source snapshot, build configuration, native binary,
models and inputs before collecting the panel. For each of the 36 arm/world
combinations, collect an initial identity and three full replays:

1. Placement, recruitment and reach tracing.
2. An untraced endpoint framebuffer capture.
3. Repeated traces plus endpoint framebuffer.

Require identical repeated result/trace/image bytes, unchanged model bytes,
and historical controls. That is 108 full replays plus 36 initial snapshots,
with zero training runs. Keep all results, including failures. Stop if an
existing bounded ledger overflows rather than silently truncating it.

Validate every placement against the independent integer mapping and original
parent support, each purchase against the seed ledger, and the recorded
spacing mask against the existing reach publisher's post-reproduction site
masks. Spacing does not change between these phases. Validate complete reach
lifetimes against recruitment receipts. Preserve same-state unit tests proving
that placement changes only seed columns at purchase, not RNG, mutation,
resources, cooldown, seed count or world clocks.

Save first-day descendant resource audits and unchanged renewal histories.
Publish endpoint contact sheets for both climates, in fixed world/arm order.
Maintain a portable analysis and a hash-verified local bundle containing full
raw receipts and the frozen executable. No source/build/model/input changes
are allowed during collection.

## Decision gates

Compare reserved/spacing against **both** archived controls, using the existing
gates: retain the score key and late child survivors in each climate, improve
a key or late renewal confirmations, and introduce no earlier or new empty
world. Report individual regressions, births, first-day mortality/shortages,
seed expiries, species outcomes and zero-credit periods alongside the gates.
Additional germinations or avoided occupied landings alone are not success.

Stop after this comparison. Do not tune the mapping, widen dispersal, change
turnover, relax scoring, retrain, or flash hardware in response to this panel.
Even a passing result is an exploratory result on reused worlds, not fresh
validation or automatic promotion to production.
