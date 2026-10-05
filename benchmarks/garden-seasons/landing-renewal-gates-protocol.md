# Audit renewal gates after the uptake-cap experiment

Status: **FROZEN before aggregating the new gate results.** Explain the stalled
renewal in the [uptake-cap comparison](landing-uptake-limit.md) using its saved
seed checks and ordered reproduction visits. Run no simulations or training;
change no ecology, controller, firmware or defaults.

## Fixed panel and windows

Pin `landing-uptake-limit-results.json.gz` at SHA-256
`687f354bbeb04b71dc2c8d81b57bccefba0a1f6e2cfa6677f9dd14d517647768`
and the raw capture manifest at
`7b69ecde2d36817c141811f267c8538a467a0d9120703358c8631b790cbd0857`.
Use all 32 primary worlds: ordinary, wicking, uptake cap, and both, across the
eight fixed/rotating × daylight/dawn × ordinary/focal-root settings. Do not
count exact repeats as independent observations. These share one examined
weather seed and controller; they are not independent replication.

Account for every ecology step in `(626580, 983040]`, with `(860160, 983040]`
reported separately as the final 32 garden days. Both are open-left,
closed-right windows with 15 logic ticks per sample and 3840 ticks per garden
day. Retain all seeds overlapping each window, including carry-in and pending
seeds; a purchase on the final tick has no subsequent germination check.

## Seed supply and establishment

Reconcile every sequential seed attempt with the complete seed and lineage
ledgers: identity, age, site, outcome, child, expiry, dormancy and inventory.
Expiry is not a failed germination check. Report purchases, germinations,
expirations, remaining seeds and post-step empty/full bank exposure.

For mature, non-expired attempts retain exact blocker-mask histograms and
overlapping moisture, light, plant-capacity, node-capacity, spacing and cold
counts. Record sole blockers and sample-level exposure as well as repeated
seed-check counts; neither denominator represents independent opportunities.
Validate thresholds against the recorded local resources and actual pool
occupancy, not the previous report's living-body lower bound. Validate cold
against the climate receipt. Distinguish no mature seeds from blocked seeds.

Count checks with a blocked chosen site but at least one open hypothetical
mature site elsewhere. This is the saved sequential snapshot across all 28
columns, not a reachable dispersal choice, a policy observation or a prediction
of establishment. Global cold or pool saturation implies no open site.
Use living lineage positions to identify parent/other spacing witnesses,
including earlier newborns in the same step. A missing living witness is not
proof that spacing is wrong: decomposing plants can still occupy space.

## Reproduction

Reconstruct the bank after ageing/germination and before the first purchase;
then validate every visit in the recorded fixed/rotated order. Recompute all
ten blocker bits, successful purchases, sequential bank occupancy and the
48-energy/24-water debit against resource stages and seed births. Validate
ready/immature/spent flower counts against living body receipts. Spent flowers
reset at dawn; do not interpret them as permanently exhausted organs.

Keep all visits for validation. For explanatory summaries, use living visits
on payment cadence with sun strength above 24. Retain exact simultaneous
masks, each and sole blocker, flower-state counts and per-parent counts.
Separate otherwise-eligible visits blocked by a bank already full at loop
entry from visits where earlier buyers fill it. Also report the ready-flower,
cooldown-clear subset. These are observed checks, not counterfactual births.

## Evidence and decision

Create no-clobber portable excerpts and analysis linked to the frozen input,
protocol and consumed raw traces. Preserve full clocks and visit order while
omitting unrelated growth bids. Rehash the 64 consumed adult/stand traces
before and after extraction and validate full trace framing through day 256.
Do not claim this audit re-verifies unrelated raw artifacts or soil accounting;
those were verified in the preceding comparison.

Support portable-only reanalysis and independent raw re-extraction without any
native executable. Test clock/inventory corruption, expiry and window edges,
sequential germination, cold/site contradictions, flower counts, overlapping
gates, bank release/refill and order, debit mismatches and no-clobber outputs.
Keep all prior evidence. Report all settings, including adverse cases.

Use the result to choose the next bounded diagnostic, not to promote a rule.
Distinguish seed supply, local sites, energy/water reserves, bank access and
actual pool capacity. Observational masks cannot establish that removing one
gate improves successful replacement or long-term survival.
