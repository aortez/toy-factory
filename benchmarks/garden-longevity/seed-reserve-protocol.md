# Sunset-aware seed reserve: predeclared host A/B

This follows the approved [turnover diagnostic](turnover.md). Hypothesis: an
additional energy affordability check before automatic seed production reduces
late-night adult deaths without eliminating useful reproduction. Exploratory,
not a training or device promotion. Freeze this protocol before the full panel.

## Single intervention

`TOY_FACTORY_GARDEN_SEED_RESERVE=ON` adds `sunset-seed-reserve-v1`. Existing
reproduction conditions, energy/water prices, growth policies, leaf renewal,
storage, body limits, seed placement and environment remain unchanged.

At the reproduction decision point (after upkeep and growth/renewal), subtract
the existing 48-energy seed price. Require at least one current upkeep payment
immediately after purchase. Forecast each subsequent ecology step through
sunset, with fixed current body size and `floor(last_energy_income / 2)` income
per daylight step. Apply the existing 256 storage cap **before** each upkeep;
credit no income at sunset. Any forecast upkeep failure rejects the purchase.
At the post-upkeep sunset require the 31 remaining pre-dawn upkeep payments.
No dawn income, stress grace period, future geometry or weather lookup is used.

This bounded forecast is not a survival guarantee: shading, other spending and
dawn recovery remain uncertain. A full 64-node body can fund exactly the night
from a full pre-sunset store; no arbitrary plant size or lifespan veto is added.
Do not tune the discount, rule or panel after inspecting results this round.

## Matched panel and measurements

Same eight cases as `artifacts/garden-seed-bank`: world seeds `b61837dc` and
`c7f54e18`, baseline no-night-growth and reserve-aware growth policies, seed banks
8 and 16, all with 512 nodes. Rainfed-crowded, selective leaf renewal, wide
dispersal, headroom water, no drainage, no gardener; patch schedule `0xe4d65e6f`.
Use the exact frozen model (CRC `dc5e849d`, SHA-256
`bd9f9c6ba7f5fd17309f917972da5f759c305c077798e1d4ba9a52701e2cd48b`).

Run each case with gate off and on for 192 days (737280 logic ticks), retaining
the closing days (160,192]. The eight off traces must exactly reproduce the
prior frozen worlds and patch boundaries. For each on trace, retain the common
prefix and first divergence; it must be explained by skipped seed purchases,
not an initial world/hash change. A refusal may free a full bank's last slot
for a later, affordable parent in the same sequential step. Verify each affected
parent's exact debit, spent flower and cooldown, unchanged existing seeds and
native append order; do not require the total seed count to fall. Rule identity
is metadata, not mutable world state.

Primary descriptive outcomes: natural energy/water mortality, offspring counts
and survival beyond ages 1/2/4/8/16 days with censoring, common 16-day follow-up
cohort, durable-parent qualification and survival, living occupancy, seed output
and expiry. Include every pair, especially the earlier adverse baseline pair.
No single survivor count or birth rate determines success.

Capture every ecology world state, reconcile lineage and live-step resource
budgets, and retain detailed final-day death histories for the focused reserve
pair under both banks and gates. Native replay frames at days 64,128,192 must
match trace hashes and framebuffer CRCs. Visual review accompanies numbers.
No new seed-site or decision-attempt streams are needed for this resource test;
use world seed counters and actual descendant lifetimes, not inferred vacancies.

Freeze binaries, caches, sources (including dirty files), model, protocol, input
manifest and old traces/analyses/frames. Verify inputs before/after and sources
unchanged during collection. Preserve failed bundles without a completed manifest.

Qualification: forecast price/upkeep/storage/timing boundaries, no RNG/seed/debit
on refusal via real production step, allowed small-body production, host/device
guards, explicit metadata rejection, all default and matched-build CTests,
and independent saved-artifact review. No flashing or training this round.

Audit correction after the first collection attempt: the original first-difference
assertion assumed exactly one fewer seed. At tick 595860 of b61837dc/reserve/8,
parent 43 is refused and parent 55 uses its freed slot. The failed bundle
`artifacts/garden-seed-reserve` is retained. Only this audit interpretation and
its fixtures changed; the forecast, cases, model, outcomes and horizon stay fixed.
The complete rerun uses `artifacts/garden-seed-reserve-v2`.

Second audit correction: c7f54e18/reserve/8 has no refused purchases and matches
the control for the entire horizon (apart from rule metadata). A no-effect result
is valid and retained, not grounds to change the gate or select another world.
The v2 bundle captured all sixteen worlds and 45 frames, but its mandatory-effect
assertion prevented finalization. Preserve both failed bundles. `--reuse` freezes
copies of these captures into `artifacts/garden-seed-reserve-v3`, verifies unchanged
native C/header sources and exact binary/model hashes, reanalyzes all sixteen
worlds, and rechecks the 45 saved frames. Only the three missing native replays
are executed. Commands describe reproduction; `native_reuse` distinguishes saved
captures/frames from newly executed ones. No forecast or outcome tuning occurred.
