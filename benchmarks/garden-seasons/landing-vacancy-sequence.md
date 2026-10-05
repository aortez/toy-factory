# Natural turnover and replacement in the capped garden worlds

Natural turnover is present in all 32 saved worlds. After the dispersal
intervention, **153 plants die and all 153 are reclaimed**. Decomposition takes
0.20–0.25 garden days, so slow cleanup is not the main renewal bottleneck in
this panel. Broader dispersal usually reoccupies released space, and many
replacement plants reproduce. An empty column can nevertheless wait a long time
for a free plant slot elsewhere.

This completes the [frozen vacancy sequence audit](landing-vacancy-sequence-protocol.md)
proposed after the [selected offspring analysis](landing-placement-information.md).
It uses eight existing settings with four arms: capped uptake, cap plus wicking,
and each with broader late dispersal. The primary interval is `(626580, 983040]`,
approximately garden days 163.17–256; the late interval is days `(224, 256]`.
All worlds share one weather seed. These are examined histories, not independent
weather replicates or a new generalization test. No native simulation, training,
rule, fitness threshold or device default changes.

## Death and reclamation are different events

The captured implementation runs decomposition before maintenance and seed
germination. A plant that dies in maintenance still occupies its plant slot
and spacing exclusion. Only when its remaining tissue countdowns reach zero
is its slot reclaimed. A seed may germinate in that same reclamation step;
a post-step population count alone would miss the temporary opening.

The 153 deaths produce 140 release events because some corpses finish together.
Every release creates at least one newly spacing-clear column. Delays from death
to reclamation range from 765 to 975 logic ticks, or 0.199–0.254 days. There are
no unfinished post-onset corpses at the horizon.

Seventy-six deaths occur during drought, 57 in autumn and 20 in winter; eight
occur while the cold flag is set. These describe timing, not isolated causes.
The implementation accumulates stress from unpaid maintenance; drought removes
rainfall and winter reduces light/delays germination, rather than issuing a
scripted death command. No weather-off counterfactual was run here.

## Broader dispersal usually reoccupies released space

A release event groups slots reclaimed at the same tick. Its newly clear columns
are compared with the immediately preceding stored census, including dead
occupants. Each column is followed until a newborn occupies or excludes it,
or the horizon. A neighboring seedling can close a vacancy without planting at
the vacated column itself.

| Post-onset outcome | Cap | Cap and wicking | Broader cap | Broader cap and wicking |
|---|---:|---:|---:|---:|
| Deaths and reclaimed slots | 46 | 21 | 56 | 30 |
| Release events | 42 | 19 | 51 | 28 |
| Events with germination in a newly clear column | 25 | 15 | 40 | 25 |
| No such germination but all columns closed by neighboring births | 10 | 0 | 10 | 0 |
| No such germination and some columns still clear at the horizon | 7 | 4 | 1 | 3 |
| Events retaining any clear column, including partial refills | 16 | 8 | 2 | 3 |

The three rows classifying germination/neighboring closure partition the release
events. The last row overlaps them: a partially refilled event can still retain
clear ground. One seedling may close columns from several release events, and
one event can admit several seedlings. Event counts are not plant counts.

Among the broader worlds, five release events retain any clear column. Four
opened within roughly the final day, so their incomplete refill is strongly
horizon-limited. The fifth is an older column in the rotating, dawn-guard,
focal-root, cap-plus-wicking world; it is never observed fully viable before the
horizon. This does not show that the entire wider panel lacks turnover or needs
stronger winter mortality.

Site viability is sampled when seeds are checked; an expired seed supplies no
site census. Here, all 760,448 post-onset world-steps have at least one non-expiry
site observation. A historical alternative column is not an action a banked
seed can take: seeds stay where they landed.

## Replacement plants contribute more than germination counts

These counts deduplicate seedlings planted in newly released columns. They
exclude births in preexisting openings; neighboring closure creates no second
replacement credit. Survival is censored at day 256.

| Replacement outcome | Cap | Cap and wicking | Broader cap | Broader cap and wicking |
|---|---:|---:|---:|---:|
| Unique replacement seedlings | 34 | 17 | 58 | 31 |
| Confirmed 32-day survivors | 30 | 11 | 44 | 18 |
| Died before the 32-day checkpoint | 4 | 6 | 9 | 11 |
| Still too young to evaluate at 32 days | 0 | 0 | 5 | 2 |
| Produced seeds | 21 | 6 | 34 | 13 |
| Produced a germinated child | 12 | 1 | 21 | 5 |
| Produced a child that survived its first day | 10 | 1 | 19 | 5 |

Thus 47 of 89 broader-world replacements produce seeds, and 26 have a germinated
child. This is actual lineage activity, not merely older survivors receiving
continued credit. It does not establish indefinite renewal, weather robustness
or preservation of every incumbent's resources.

Across the whole populations, the final 32 days contain zero births in either
narrow arm, seven in broader cap and four in broader cap plus wicking. Only
11 of 32 worlds have a death in that interval; six broader worlds have births.
Quiet intervals should not be extrapolated to permanent occupancy. The earlier
broader-dispersal harm screen remains unchanged and unpassed in twelve of
sixteen comparisons.

## A clear column can wait for a slot elsewhere

One sequence in the fixed-order, dawn-guard, ordinary-root pair makes this
distinction concrete. In both narrow and broader worlds, plant 25 dies at tick
917040 and is reclaimed at 917985. Columns 6 and 7 become spacing-clear and
are observed viable immediately.

In the broader world, a banked seed germinates at column 21 in that same step,
using the freed eighth slot. The local gap remains clear. A different seed is
bought at column 6 at tick 921120, but **all 3,883 unsuccessful mature checks
include the full-plant-pool blocker**. On 671 checks that is its only blocker.
Neither spacing nor node capacity blocks this particular seed; light, moisture
and cold sometimes overlap the slot limitation.

At tick 979485, two other corpses are reclaimed. Two seeds germinate sequentially,
one at column 21 and this seed at column 6. The latter becomes plant 34, with
less than one garden day left in the record. Its seed waited about 15.20 days
since purchase; the gap existed about 16.02 days since reclamation. The narrow
world never fills columns 6 or 7 before the horizon, despite some historical
purchase supports including them. Neither world lets banked seeds relocate.

This is a recorded sequence, not an intervention isolating every cause. Across
the panel, node capacity also matters: it blocks 261,888 broader-cap and 360,334
broader-cap-plus-wicking mature checks in the final period, overlapping other
blockers. More plant slots alone would not remove the 256-node constraint.

## Next test persistence beyond the current cutoff

The next proposed experiment is a bounded matched follow-up through two more
16-day seasonal cycles, ending at day 288. Keep the same model, weather identity,
ecology and harm checks. Follow late replacements' survival, reproduction and
pending seeds; do not add stronger drought, aging, a larger pool or a new
placement rule merely to create more visible activity.

The host replay enforces a 256-day ceiling, so this first requires a small
host-side horizon/ledger-safety change, with regression checks against the
saved day-256 prefix before accepting longer runs. Freeze the panel and stopping
point before collecting results. This audit does not implement or run that
extension, and no experimental rule is promoted. The subsequent
[day-288 follow-up](landing-followup.md) now completes this proposed check;
its results are separate from this frozen offline audit.

## Verification and reproducibility

The extractor reads all 32 primary stand and reach traces through complete
headers, clocks and footers. It reconciles 2,700 purchases and 16,640,021 seed
checks with the pinned purchase records, fates and mature-site histograms.
Live body IDs, stored array order, sequential births and the deterministic
climate schedule are checked independently. Runtime source identities refer
to the captured implementation, not future working-tree C files.

The [597 KiB portable result](landing-vacancy-sequence-results.json.gz) retains
every stored-identity transition and a lossless run-length encoding of the
post-onset compact seed observations: identity, actual blocker mask and fully
open column bitset. It distinguishes empty/expiry-only checks, original support
from actual landing, adjacent closure, partial refill and censoring. Full raw
site-mask histograms are reconciled during extraction; the compact result does
not expose every alternative column's individual light/moisture blocker.

All 23 new tests pass on the host and in Docker, alongside three selected
offline CTest entries. Portable reanalysis, independent raw re-extraction and
byte-identical repeated export pass with process launching forbidden. No
runtime C changed and no prior artifact was removed. See the
[tool instructions](../../docs/garden-landing-tools.md#vacancy-and-replacement-sequences)
for fresh-output export and verification commands.

| Artifact | SHA-256 |
|---|---|
| Frozen protocol | `bd0eecb124ebeeca6150625eebc4711b04af5afd2da45f4ebc49977b16ef9b29` |
| Original raw manifest | `4a94df9dcc4f53c980e3631b58dc3fd853c3f03a68678d335127ab09f7a83001` |
| Portable result | `f58fe1034af55a12349abfbd717ce69581bb4991824d1ae17ded88be36aff135` |
