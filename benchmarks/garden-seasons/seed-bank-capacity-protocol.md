# Isolated seasonal eight-versus-sixteen seed-bank screen

Freeze this plan before collecting treatment outcomes. This is a known-panel
screen motivated by the [production-gate audit](production-gates.md), not a fresh
confirmation or default promotion. Use the same 32 seasonal worlds through day
128: the eight weather seeds from `seedling-confirmation`, both rainfed layouts,
and baseline/adaptive controllers. Retain every world and adverse result.

Both arms use the already measured wide-scattering candidate and unchanged
combined first-day energy/water reserve guard for every offspring. Change only
the compile-time seed capacity: eight versus sixteen. Keep 256 nodes, eight plant
slots, 32-day seed viability, dormancy, resource costs/reserves, weather, growth,
germination, seed ordering, mutation and all controller logic fixed. No gardener,
irrigation, replacement policy, training, firmware change or flash. Normal builds
explicitly disable the isolated host-only option; it cannot be combined with the
older multi-feature ecology experiment or compiled into Zephyr.

## Predeclared decision criteria

Use established descendants, not seeds produced, as the objective. A durable
parent is a descendant that survived a full day and produced a child that also
survived a full day. Closing cohorts are born strictly after day 112; young
births without a full day's calendar follow-up are censored. A durable count is
a historical achievement, not a promise that the parent is still alive.

The candidate passes this screen only if all of these hold:

1. Closing durable parents strictly increase over the eight-slot guarded control.
2. Closing full-day survivors and their survival fraction do not decrease.
3. Whole-history durable parents do not decrease.
4. No matched world newly becomes empty (no living plants or seeds), and no new
   zero-living endpoint appears.
5. Final viable-species counts, including seeds, do not fall in any matched world;
   the number of multi-living-species endpoints does not decrease.

Report births, eligible/censored cohorts, one-/two-day survival, early deaths,
natural deaths, parent reproduction, living/viable species, seed creation,
germination/expiry/pending outcomes and occupancy. Partition by weather, layout,
controller and species; retain per-world regressions. More deaths can follow more
births, so do not gate on the unnormalized death count. Instead also compare
deaths of the identical living incumbents at the first capacity-caused divergence
and report earlier deaths explicitly. Do not match newly diverged descendants
merely because their numeric lineage IDs happen to coincide.

Report full-bank and seed-occupancy samples over the whole run and closing year,
explicitly as post-step observations, not actual failed production checks. Measure
native world/snapshot storage and hashing/rendering at the last seed slot. A
passing aggregate screen does not establish diversity or justify device adoption;
a failure is retained without changing thresholds or starting a parameter search.

## Reproducibility and integrity

Build both arms from one frozen source snapshot, differing only in the isolated
capacity option. Capture every ecology step with growth bids and exact natural-
death receipts. Repeat all 64 trajectories and require byte-identical traces.
Rebuilt eight-slot traces must match the saved guarded confirmation byte-for-byte.
All capacity-independent states/bids/deaths must match up to the first additional
seed purchase; at that first divergence the sixteen-slot bank must exceed eight,
retain the same first eight seeds and add only new age-zero seeds. Shared
incumbent identities and external weather must still match at that point.

Reconcile every live/terminal resource budget, seed creation/removal, offspring
ancestry, lifetime and per-day state. Retain portable histories/seed ledgers and
source/build/trace hashes, and rerun analysis from unchanged raw inputs. Tests
must reject malformed capacities, missing/changed records, non-capacity prefix
changes and incomplete panels; preserve default eight-slot behavior and the
separate old large-bank experiment.

Render eight fixed frames: first weather seed `ed52188c`, baseline controller,
both layouts, both capacities, days 16 and 128. Match native state hashes and
framebuffer CRCs and retain PNGs for manual review. Eight-slot frames must also
match the saved guarded confirmation frames. Do not select pictures after seeing
results. Raw traces stay in ignored artifacts; version the bounded findings and
portable evidence. Discuss the result before a fresh panel or any policy change.
