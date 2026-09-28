# Producing-flower dispersal: isolated host screen

Freeze before collecting outcomes. Following the bank-residence diagnosis and
discussion of seed placement as a growth consequence, change only the horizontal
origin of seed scattering: plant base versus the actual producing flower. This
is not wind, post-landing drift, directed placement, flower choice, or a new
release action. Height has no new effect. Existing pixel-to-soil-column clamping
and distance reflection at the world's edges apply.

Use the eight-slot wide-scattering control with the unchanged combined first-day
offspring reserve guard. The sixteen-slot trial remains separate and unpromoted.
Keep RNG draws/order, trait mutation, first-ready-flower selection, release
timing, resource costs, 32-day seed viability, germination, weather, controllers,
256 nodes and eight plant slots unchanged. No gardener or irrigation. The option
is host-only, explicitly OFF in ordinary builds and forbidden alongside the
capacity/combined ecology experiments. Do not flash or promote defaults.

## Fixed panel and decision

Use all 32 known confirmation cases: eight weather seeds (`ed52188c`, `4f0b9247`,
`a9c30c1e`, `0bb887d1`, `647001a8`, `c629bb63`, `20e1353a`, `82deacfd`), both
rainfed layouts, baseline/adaptive controllers, seasonal climate, 128 days each.
This is a known-panel screen, not independent validation of a trained policy.

Use the same gates as the capacity screen: closing durable parents must strictly
increase; closing full-day survivors and their survival fraction, historical
durable parents and multi-living-species endpoint count must not decrease. No
matched world may newly become empty or end with no living plants. Final viable
species counts (including seeds) must not fall in any matched world. Closing
cohorts are born strictly after day 112; calendar follow-up censors young births.
A durable parent is a descendant surviving a full day with a child also surviving
a full day. This is a historical achievement, not endpoint survival.

Report seeds, births, expiry/pending, full-bank time, one-/two-day survival,
durability, species, matched-world regressions and identical incumbent deaths.
More births alone is not success. No threshold changes or parameter sweep after
outcomes. Discuss failures as well as any gains before the next experiment.

## Integrity and observation

Build both arms from frozen sources; only FLOWER_DISPERSAL differs. Repeat every
trajectory and require byte-identical compressed traces. Rebuilt base-origin
traces must equal the saved eight-slot capacity controls. Audit all resource
budgets, deaths, ancestry and seed lifecycles. Freeze source/build/input hashes
and reanalyze unchanged raw traces independently of native replay.

At the first state divergence, ignore only the explicit origin metadata and
state hash. The sole state change must be one or more new age-zero seed columns:
all reported plant states, genomes, births, purchases, bids, receipts and other
world fields must agree. Seed-site blocker annotations may change with the new
column. The ordinary trace does not expose hidden RNG or seed genomes; controlled
native fixtures compare complete worlds after normalizing only flower position
and seed column to check those invariants. Match later incumbent deaths only for plants alive at
that shared prefix; never match new descendants by coincident numeric IDs.

The read-only reachable-site query uses the same first mature, unspent flower;
with no such flower it reports no reach. It does not claim resources, cooldown,
or weather permit release. Unit tests exercise selected-flower ownership,
spent/immature/dead flowers, readiness thresholds, all pixel/column boundaries,
trait extremes, edge reflection, support consistency, unchanged RNG/mutation,
seed debit/cooldown, and fixed post-landing positions.

Render eight preselected frames: weather `ed52188c`, baseline, both layouts,
both origins, days 16 and 128. Verify trace state hashes/framebuffer CRCs and
retain PNGs. Base frames must match saved controls. Version bounded portable
histories, ledgers, summary and findings; keep raw traces in ignored artifacts.
