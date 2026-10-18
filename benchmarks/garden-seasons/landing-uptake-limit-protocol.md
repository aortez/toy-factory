# Test late storage limited uptake with and without soil wicking

Status: **FROZEN before candidate runs**. The [wicking comparison](landing-wicking.md)
found that selected adults discarded most of their extra uptake. Test whether
leaving surplus in the soil improves survival **and renewal**, with an explicit
check for prolonged incumbency. This follows the earlier [from-start headroom
experiment](../garden-longevity/water-headroom.md), which reduced water deaths
but also reduced turnover. It is not an untested new idea or a promotion gate.

## Fixed rules and histories

Keep ordinary uptake through logic tick 626580. On every subsequent ecology
step, cap each root's uptake at `min(soil, species rate, 512 - stored water)`
before the soil debit. Update storage after each root. The first eligible step
is 626595. Do not reserve space for later upkeep, growth or reproduction, skip
leaves, change processing order, or add RNG or persistent state. Actual uptake
remains observable income; controller weights and input schema stay fixed,
not their subsequent decisions.

Use four separately identified host builds: ordinary, wicking only, uptake cap
only, and cap plus wicking. Wicking retains its exact frozen rule and onset
from the previous test. All other compiled research options remain disabled.
Keep the older from-start headroom experiment unchanged. Device and ordinary
host defaults remain off. Hash and JSON metadata identify each enabled rule
even before intervention.

Pin `landing-wicking-results.json.gz` at SHA-256
`db7f43ee7ca46cbdfff73338b0de1896a91beda5a54132e72bafa4986e04be36`.
Use its eight settings: fixed/rotating seed order, daylight/dawn guards and
ordinary/focal-root allocation. Keep model bytes, weather seed f7ee4528,
983040-tick horizon, native arguments and uptake window 626520–660480 identical.
These are examined histories from one weather seed, not independent held-out
replications. No gardener, training or parameter search.

## Bounded capture and verification

Run **48 full trials**: rebuild and capture the 16 ordinary/wicking controls
once each, and run each of the 16 capped conditions twice. Require the rebuilt
controls to match the archived results, all four compressed traces and terminal
pixels exactly. Require exact candidate repeats. Unit and short integration
tests are separate. Do not run extra long trials, stop early on results, tune,
or retain only favorable cases. Stop and report broken provenance or accounting.

Save full stand, adult and direction traces and the same bounded uptake window.
Keep terminal images without extra screenshot replays. Archive binaries, model,
settings, sources and manifest in a fresh directory. Keep compressed traces and
their original files; preserve earlier bundles. Verify physical observations
through 626580 against each matching control, excluding rule-tagged footers.

Independently reconstruct every observed soil cell transition, per-root debit,
storage change and post-uptake germination withdrawal. A capped root cannot
discard uptake after onset. Rain, transport, evaporation, retained uptake and
soil stocks must balance. Reconcile selected adult and whole-population accounts.
Reuse the pinned controls' previously verified analysis only after exact raw
receipt equality; reextract all new candidate analyses. Both portable and full
raw verification must run offline without invoking native simulations.

## Outcomes and limits

Compare each cap arm with its own uncapped control, plus cap with versus without
wicking. Report all eight settings and the established population non-regression
checks: maintenance shortfalls normalized by payments, terminal population and
species, late living time, descendant seed parents, successful parents,
cumulative one-day and 32-day offspring survivors, and empty-world timing.
Report seeds and births too; neither alone proves sustained renewal.

For the same pre-intervention flowers (daylight lineage 16, dawn lineage 17,
born 590640), retain actual death times, seeds, resources and shortfalls. Compare
both actual lifetimes and a matched window ending at the earliest of the old
639480/644700 endpoint and the two compared deaths. Separate exposure changes
from per-payment effects. Also report births after intervention, births in the
last 32 days, and repeated post-step living-body node/plant occupancy from saved
stand traces to detect incumbency/capacity tradeoffs. Living bodies exclude
decomposing occupants: this is a lower bound on pool use, not exact total pool
saturation. Do not equate occupancy with a causal explanation of every missed birth.

Separate drought-period resource shortfalls and deaths from other periods;
deaths during drought are not automatically caused by drought. Inspect saved
terminal screenshots as qualitative context, not a replacement for turnover
accounts. No default change or device deployment follows from this panel.
