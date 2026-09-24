# More recruits, poorer first nights, and a closed shrub site

The retry-aware FINISH rescue changes **which plants occupy the garden**, not
just whether one flower survives. More offspring are born, but a smaller
fraction survives its first day. Shrubs fail to establish successors rather
than suffering an additional adult death. Both findings come from the saved
control/retry traces; no new experimental native runs or rule changes were made.

The [scope](renewal-recruitment-protocol.md) was
[recorded in issue 30](https://github.com/aortez/toy-factory/issues/30#issuecomment-5747756895).
This reuses one already-inspected world, not an independent validation panel.

## Where the additional deaths come from

The whole-world natural-death change **17 → 21** separates exactly into:

- Founders: **3 → 3**; no change.
- Offspring born before the intervention: **13 → 12**; flower 22 is rescued.
- Offspring born after the intervention: **1 → 6**; five additional deaths.

Thus **−1 + 5 = +4**. No other pre-intervention plant loses lifetime. The later
IDs are separate within-run identities, not matched individuals across arms.

| Born after tick 69,885 | Control | Retry-aware |
| --- | ---: | ---: |
| Births | 8 | 13 |
| Full-day eligible offspring | 7 | 13 |
| Full-day survivors | 6 | 7 |
| Natural deaths before a full day | 1 | 6 |
| Later scheduled patch deaths | 1 | 2 |
| Living at day 64 | 6 | 5 |
| Recent living child without full-day follow-up | 1 | 0 |

There are both **more opportunities and poorer observed survival**: six of
seven eligible control offspring survive a day, versus seven of thirteen in
the retry arm. The control's day-64 newborn is censored, not a failure. Whole-run
and closing-window cohorts still reconcile to the previous report; this table
isolates the post-intervention cohort instead of mixing it with old plants.

Four of the retry arm's six early deaths happen at **column 14**, where two
flowers and then two ground-cover seedlings fail before a later ground-cover
survives. The other early deaths occur at columns 26 and 23. This is a cluster
of failed establishments, not six established adults displaced by the rescue.

## The first night, not water or seed spending

All six post-intervention retry deaths are energy deaths inside the first dark
interval. Every dark-entry forecast predicts the exact death tick, with no
subsequent body/cost change breaking its assumptions. None spends energy on
seeds or leaf renewal before dying, and water is not the terminal shortage.

| Retry child | Species / column | Nodes at dark entry | Energy at dark entry | Minimum energy for this fixed dark interval |
| --- | --- | ---: | ---: | --- |
| 26 | Flower / 14 | 29 | 109 | 120 |
| 27 | Flower / 14 | 14 | 4 | 60 |
| 28 | Ground-cover / 14 | 68 | 156 | Cannot survive even at the 256 cap |
| 29 | Flower / 26 | 13 | 31 | 60 |
| 31 | Ground-cover / 14 | 45 | 88 | 180 |
| 34 | Ground-cover / 23 | 66 | 250 | Cannot survive even at the 256 cap |

These minima hold the observed body and zero starting stress fixed and permit
survivable shortages. They are not a promise of dawn recovery or a demonstrated
rescue under altered spending.

There are two distinct problems:

1. **Too little reserve for a viable body.** Four children could survive that
   interval within storage capacity, but enter it below the required reserve.
   Flowers 27 and 29 germinate late in daylight (phases 92 and 100), collect only
   40 and 54 energy respectively over their observed live budgets, and spend
   90 and 81 on growth before dying. Their initial endowment is 64 energy.
2. **A body too expensive for the store.** Ground-cover 28 and 34 reach the
   nine-energy upkeep tier. Even full stores cannot carry those fixed bodies
   through the remaining 37 maintenance payments with fewer than eight
   consecutive shortages. Child 34 enters with 250 energy—almost full—and
   still dies. Extra daytime income alone cannot solve that fixed-body night.

The guard is arithmetically correct but starts after these commitments have
already been made. This audit does not assume a particular earlier purchase
veto would rescue any of these six plants. Cleared terminal income/stores are
explicitly excluded from reconstructed live budgets.

## Why the shrubs disappear

The existing shrub 6 actually produces **more** seeds: 66 → 78. But its
post-intervention purchases change **34 → 46**, and those 46 retry seeds all
expire. The three shrub seeds already pending at intervention also expire in
both arms.

The important recruitment path in the control is:

```text
flower 22 dies; its column-20 site becomes free
    → shrub 6's seed germinates at column 20 (tick 76,425; child 26)
        → that shrub later establishes children at columns 27 and 14
```

In the retry run, flower 22 remains at column 20 throughout the follow-up. Its
existing spacing exclusion covers columns **18–22**. All later seeds from shrub
6 land in columns 18–24. Of their **11,408 mature post-step observations**:

| Observed blocker | Seed observations |
| --- | ---: |
| Spacing | 11,408 / 11,408 |
| Eight occupied plant slots | 10,482 / 11,408 |
| Insufficient light | 8,836 / 11,408 |
| Insufficient moisture | 1,789 / 11,408 |
| Node capacity | 0 / 11,408 |

Blockers overlap. Flower 22 appears among spacing occupants in 8,432 of these
observations. Five seeds land exactly at column 20 and each expires; there,
flower 22 is the only spacing occupant, but plant capacity is also full in
every recorded mature snapshot. Removing one blocker is therefore not a
demonstrated germination or survival counterfactual.

These are **post-step snapshots**, after seed checks and later growth/light
updates—not the actual decision-stage receipts. The reconstructed control seed
illustrates the distinction: its last snapshot at 76,410 says plant capacity
is full, but it germinates at 76,425 after a dead plant is reclaimed. The audit
does not turn snapshot counts into germination probabilities or claim to have
measured hypothetical free sites.

Shrub 6 dies in the same scheduled patch at **131,595** in both runs. In the
retry arm it has no living shrub successor; its last three pending seeds
expire, and the final shrub seed disappears at **134,820**. The control's
replacement shrub and its two children remain alive at day 64. Although the
old parent produced twelve extra seeds in the retry arm, **total seed production
by all shrubs falls 137 → 93** because that later reproductive branch never
appears. More seed production by one parent is not continued reproduction by
the family.

## Verification and limits

- The frozen parent manifest, native sources, exact reference trajectories,
  repeated frames and resource analysis are re-verified without new data
  collection. The two-arm audit then runs twice and matches exactly.
- **1,053 seed purchases** reconcile to **57 germinations, 980 expiries and 16
  seeds remaining**. All per-parent production and child ancestry agree with
  the independently saved lineages. **249,557 mature seed snapshots** and
  **247,501 live plant budgets** are checked across the pair.
- Seed identities/ages are reconstructed from creation ticks and bank order,
  not invented logged IDs. The embedded-C contract review confirmed expiry
  precedes germination, removals preserve order, and reproduction appends new
  seeds afterward. Mature same-column duplicates follow that order; conflicting
  transitions fail. Patch samples do not age seeds twice.
- Ten new synthetic tests cover ordering, duplicates, simultaneous expiry/
  germination/creation, dormancy/lifetime boundaries, corruption, truncation,
  patch seed preservation and full-day censoring. **All 74 default host CTests
  pass**. Routine regression fixtures are separate from the zero-new-experiment
  budget; no new training campaign or firmware change was made.
- Full reconstructed seed records, cohorts and post-intervention child budgets
  are in the [portable summary](renewal-recruitment-summary.json), SHA-256
  `5eae378e57a8b15766a8b56fa2693a9958c9255cae6b8a72ec852a77a348ba75`.
  The [existing native images](renewal-finish-retry.md#fixed-native-screenshots)
  remain the visual evidence; no new images were generated or selected.

```sh
python3 -W error sim/garden_renewal_recruitment.py \
  --check benchmarks/garden-longevity/renewal-recruitment-summary.json
```

## Next proposal

Keep spacing and germination rules unchanged for now. Losing shrubs here is a
real occupancy/recruitment tradeoff, not evidence of a broken seed-bank queue.
The narrower unresolved mechanics issue is committing to an unaffordable body
before the dark guard applies.

First discuss a **shadow-only, storage-cap-aware growth check**: would an
extension make the body's full-night upkeep unsurvivable even with full energy
and zero stress? Audit it on the saved panel before any enforcement. This
addresses the two intrinsically oversized children without guessing future
photosynthesis; it deliberately does not solve the four smaller under-reserved
children or guarantee species coexistence. No hard node ceiling, new guard,
fitness change, commit, push or deployment is adopted by this audit.
