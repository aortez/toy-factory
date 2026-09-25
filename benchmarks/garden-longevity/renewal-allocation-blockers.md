# The eight-plant limit independently blocks descendant establishment

The [saved-trace audit](renewal-allocation-blockers-protocol.md) finds a real
allocation bottleneck in the fractional-canopy run: **53 distinct mature seeds
encounter allocation-only rejection; 52 eventually expire and one later
germinates.** Seven belong to the successful new shrub 13. This is more than
high occupancy alone, but it does not predict how many additional seedlings
would survive if the limit changed.

No new experiment, mechanics, model, screenshot or device change. Both frozen
arms and all seed lifetimes are retained, including failures and pending seeds.

## What can be established from a post-step query

The native seed masks are printed after germination, growth and reproduction.
They are not direct logs of individual germination attempts. A birth can consume
a slot, space and moisture before the final query, so mask `8` alone is not
sufficient evidence of an allocation-only rejection earlier in that step.

The code-order review supplies a narrower inference for **no-birth steps**:

- Rain, transport, uptake, decomposition and plant maintenance occur before
  the seed loop.
- No germination means no later 12-unit surface-moisture debit. Growth and
  reproduction consume plant stores, not soil, and do not move/remove plants.
- Post-step node room also proves room before growth could add nodes.
- These post-boundary runs use wet germination, so the refreshed light grid
  does not affect the germination gate.

For a retained seed aged 8–255, mask `8`, eight non-newborn occupants and no births
therefore support an **allocation-only rejection at its actual loop visit**.
This is a code-order inference from saved state, not a newly recorded attempt.
Birth-step observations remain separate. Expired/germinated seeds have no final
retained-seed query, and dormant seeds are excluded from mature denominators.

## Whole post-change window

Observation window: `(69120,245760]`. These are repeated observations of retained
seeds, not independent opportunities or germination probabilities.

| Measure | Additive control | Fractional transmission |
| --- | ---: | ---: |
| Distinct seeds with mature observations | 380 | 376 |
| Mature retained-seed observations | 89,288 | 91,031 |
| Post-step plant-capacity-only observations | 6,558 | 5,543 |
| Code-order-confirmed allocation-only observations | 6,550 | 5,542 |
| Distinct seeds with confirmed observations | 68 | 53 |
| Their eventual expired / germinated / pending outcomes | 60 / 7 / 1 | 52 / 1 / 0 |
| Plant capacity plus other gates | 76,931 | 84,581 |
| No plant-capacity gate | 5,799 | 907 |

Eight control observations and one candidate observation are allocation-only
**post-step** on birth steps and are not upgraded to exact rejection evidence.
The first confirmed observation in each arm is at tick 70,080.

The candidate's overlapping masks remain important: 52,282 observations combine
plant capacity, spacing and moisture; 24,977 combine plant capacity and spacing;
7,322 combine plant capacity and moisture. The 907 observations without plant
blocking still have moisture and/or spacing blocking. None has a node-capacity
gate, and light is deliberately not a germination gate here.

In the closing window `(184320,245760]`, confirmed exclusive observations are
1,712 for 24 control seeds and 1,450 for 22 candidate seeds. Of those 22 candidate
seeds, 21 expire and one germinates. The issue is not confined to startup.

Exposure cohorts and purchase cohorts differ: 369 candidate seeds are purchased
after the split (359 expire, two germinate, eight remain pending), while 376
have mature observations in that window, including earlier purchases. Do not
use one denominator for the other.

## The two new candidate parents have different constraints

Shrub 13 buys 33 seeds: 32 expire and one remains pending. **Seven distinct seeds
have 582 confirmed allocation-only observations; all seven expire.** Their landing
columns are 6, 15, 16 and 20. Four of the seven have confirmed observations in the
closing window. This demonstrates an allocation obstacle to further-generation
establishment, not just to more founder children.

The first such seed is purchased at 118,920 and lands in column 20. At its first
mature visit, tick 119,040:

- Surface moisture is 25, exceeding the unchanged requirement of 12.
- No incumbent base is within the forbidden spacing distance.
- Node use is 429/512, leaving room for its four seedling nodes.
- All eight occupants are living non-newborns; the only blocker is plant capacity.

It has 151 such observations in three sampled runs, plus 97 observations also
blocked by moisture. Its last allocation-only observation is at age 255, tick
122,745. It expires at 122,760; expiry happens before another germination check.
The 151 observations are one seed waiting repeatedly, not 151 possible children.

Shrub 14 is different: all 721 mature observations of its three seeds are also
spacing-blocked (470 additionally moisture-blocked). Two expire and one remains
pending. There is no allocation-only evidence for this parent's seeds. Raising
the plant limit alone would not remove their observed spacing obstacle.
Post-divergence IDs are arm-local; these are not matched to control IDs 13/14.

## This is mostly living occupancy, not delayed decomposition

Of the candidate's 5,542 confirmed allocation-only observations, **5,538 have
eight living occupants**. Only four involve an unreclaimed dead occupant.
All four concern parent 6's seed in column 21, which later germinates as child 14
at 202,335. Its intervening moisture constraints also remain visible.

The candidate has a full array containing any dead occupant at only 60 of the
11,776 post-boundary checkpoints. Accelerating decomposition therefore would
not address most of this observed allocation-only blocking. This is not a
counterfactual claim that removing a dead plant has no other consequences.

The hypothetical column queries also need their own denominator: 35,595
candidate column-observations are plant-capacity-only, but only 5,303 of those
column-observations contain at least one mature retained seed. Multiple seeds can
share a column. Empty suitable terrain is not an actual seed waiting there.

## Next proposal, not implemented

This supports one bounded **eight-versus-sixteen plant-slot host diagnostic**,
keeping the 512-node pool, eight-seed bank, fractional light, spacing, costs,
weather, controllers and horizon fixed. Preserve the eight-slot rule through
the shared checkpoint so the starting trajectories match. Sixteen is a single
diagnostic choice, not a capacity sweep or a proposed device default.

Judge full-day survival, new parents with surviving children, incumbent/species
retention and whether pressure merely moves to nodes, water or spacing. More
births—or filling a larger array with stable adults—would not demonstrate
sustainable renewal. Freeze that experiment's criteria before capturing it.
Do not force adult deaths, tune opacity or restart training on this audit.

## Evidence and validation

- [Portable audit](renewal-allocation-blockers-summary.json), SHA-256
  `e7c591c0b094c94e788ae9ca91992bbd6f1214123353dd0f38d64c5e7ca7ef37`.
- Immutable parent: `artifacts/garden-renewal-canopy-transmission-v1`, manifest
  `ea243a36dccd49eda1db5cbfc30956ebf281e81013fec5a4adc8e69bc7212b69`.
- All **1,034 seed lifetimes, 256,010 retained-seed observations and 247,759
  mature observations** reconcile with the parent ledger. The existing 32,770
  site checkpoints, parent results and [six native images](renewal-canopy-transmission.png)
  are preserved. No new screenshots or native research captures.
- Original saved-data analysis, repeated new analysis, host output and independent
  Docker verification agree. Native sources and historical analysis dependencies
  are unchanged; only the exact new shared CMake test registration is permitted.
- **17 new synthetic tests**, **89/89 default and 92/92 experimental CTests** pass.
  The first offline pass caught the canonical pre-export snapshot being compared
  against a lifetime exit timestamp as if it were a natural death. The audit now
  handles that distinction explicitly, with a regression test; no captured state
  or earlier results were changed. Cleared terminal resource budgets remain unknown.

```sh
docker compose run --rm --no-deps firmware python3 -W error \
  sim/garden_renewal_allocation_blockers.py \
  --check benchmarks/garden-longevity/renewal-allocation-blockers-summary.json
```

Work remains local, uncommitted and unpushed. Device firmware and defaults are unchanged.

Follow-up: the [fixed plant-slot experiment](renewal-plant-slots.md) has now run.
The command above retains its original source-version requirements; use the
follow-up verifier on the newer experimental checkout. Earlier frozen evidence
has not been rewritten to accommodate the capacity change.
