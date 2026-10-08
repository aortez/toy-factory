# Recruit seeds stall at purchase and establishment

The saved day-512 histories separate two problems: most new recruits never buy
a seed, and none of the five seeds bought by new recruits germinates. Two expired
seeds encounter a full living population throughout their mature checks. A third
also overlaps a population vacancy, but its landing remains blocked by a living
neighbor. The fourth leaves a short interval needing a passive trace of stored
plant slots and germination checks. One seed remains pending, not failed.

This is an offline audit of every recruit born in `(384,512]` across both arms
and all six gardens of the [competitive-renewal follow-up](landing-competitive-renewal.md).
It adds no simulation calls, intervention, training or default change. The
original renewal criteria and failed cursor harm gate remain unchanged.

## Purchase access is still uneven

Primary recruits are born in `(384,480]`; later recruits lack 32 days of
potential follow-up at the endpoint. Counts include all recruits, not only
survivors or seed buyers.

| Arm and birth cohort | Recruits | Seed buyers | Seeds bought | Children by day 512 |
| --- | ---: | ---: | ---: | ---: |
| Fixed primary | 3 | 0 | 0 | 0 |
| Cursor primary | 5 | 3 | 5 | 0 |
| Fixed late | 3 | 0 | 0 | 0 |
| Cursor late | 4 | 0 | 0 | 0 |

All three primary fixed-order recruits die without buying a seed, although two
survive 32 days. Of the two primary cursor recruits without purchases, S2 ordinary
plant 40 dies before age 32; plant 41 remains alive at age 97.02 days with no seed
purchases. The latter is not merely a very recent recruit. The seven late births
remain alive and purchase-free at the endpoint; their short follow-up is retained
rather than scored as failed reproduction.

The ledgers establish purchases, not purchase eligibility. They cannot separate
lack of flowers or resources, reproduction cooldown and light gates, or seed-bank
competition for a plant that never buys. Cursor access alone has not made every
long-lived recruit reproductive.

## A population vacancy is not necessarily a usable landing

S1 and S2 are weather seeds `3a7e45e6` and `366928c6`. All five recruit seeds are
in the cursor arm. Garden days below are rounded; the
[portable audit](landing-recruit-seeds-results.json.gz) retains exact integer ticks.

| Garden and parent | Seed purchase to end | Landing column | Mature checks with living headcount below eight at this seed's turn | Finding |
| --- | --- | ---: | ---: | --- |
| S1 ordinary 51 | 432.891 to 464.891 | 4 | 0 | Expired; living capacity alone excludes all checks. |
| S1 ordinary 51 | 464.891 to 496.891 | 16 | 528 | Expired; plant 42 at column 15 blocks spacing throughout the vacancy. |
| S2 crowded 35 | 425.156 to 457.156 | 15 | 0 | Expired; living capacity alone excludes all checks. |
| S2 crowded 35 | 457.156 to 489.156 | 15 | 63 | Expired; stored-slot timing remains unresolved before an older seed fills the site. |
| S2 crowded 36 | 489.156 to observation at 512 | 24 | 0 | Pending; full living population at all 5,841 observed mature checks. |

Each expired seed has 8,184 mature check steps: age eight is included, but age
8,192 expires before germination is checked. The pending seed's nominal expiry
is day 521.156, outside this capture. Its future fate is unknown.

In S1 ordinary, parent 51 dies at day 494.828 at column 9. Its remaining seed is
at column 16, one column from living plant 42. The minimum plant spacing is three
columns, so freeing the parent's site does not free this seed's landing. The
528 checks span about 2.06 Garden days; spacing is sufficient to prevent
germination, regardless of any additional capacity, water, cold or light blocker.

In S2 crowded, parent 35 dies at day 478.750 at column 24. An older seed from
parent 31 germinates at column 15 at day 478.996, producing plant 36. The recruit's
seed is also at column 15. Parent 31 bought its seed on day 447.031, before
parent 35's purchase on day 457.156, so it is visited first in the stable seed
bank. At that refill step, its child restores eight living plants and blocks the
later seed's landing. There are 64 steps with fewer than eight living plants
before the seed loop, but only 63 at the recruit seed's own turn.

Those 63 earlier checks are **unresolved**, not 63 valid opportunities. Dead
tissue retains a stored plant slot until decomposition finishes. Living counts
and base columns do not reveal that release time, node capacity, soil moisture,
light or cold. No living neighbor rules out column 15 during those checks, but
that does not establish that the recruit's seed could have germinated.

## Reconstruction and limits

The audit uses the captured implementation's stage order: decomposition and
natural maintenance deaths precede seed checks; germination visits the existing
bank in purchase order; growth and new seed purchases follow. It includes births
earlier in the same loop at each focal seed's turn. It excludes the purchase
step, dormant steps and the expiry step, includes a germination step, and clips
pending seeds at day 512. Parent death does not end a seed's independent life.
There are no imposed deaths after day 304 in these histories.

Eight living plants prove a plant-capacity blocker. A living neighbor within
three columns proves a spacing blocker. These are sufficient exclusions, not
complete blocker masks, and may overlap. Fewer living plants and no nearby
living neighbor prove neither a free stored slot nor germination eligibility.
Every recruit, seed interval, same-step refill and censoring status is retained.

## Next bounded diagnostic

The [subsequent handoff diagnostic](landing-seed-handoff.md) completes the
two frozen replays: the dead parent retains its slot and nodes throughout the
63 checks, and the older seed germinates in the reclamation step. The proposal
below describes the scope selected from this offline audit.

Trace the S2 crowded cursor history around day 478.750 through the refill at
478.996, including one ecology step before and after. Observe stored plant
slots, decomposition/reclamation, and the existing per-seed blocker checks.
This can distinguish a corpse retaining the only slot from a usable opening
that the recruit's seed fails to take before the older seed wins. Keep the
existing endpoint result as the replay identity check; do not change seed
priority, expiry, capacities or survival rules as part of this diagnosis.

Purchase eligibility of long-lived non-buyers remains a separate question.
Neither this audit nor the proposed short trace qualifies the environment for
training or establishes that a different queue order would improve renewal.

## Reproduction and validation

The [tool guide](../../docs/garden-landing-tools.md#recruit-seed-audit) provides
the offline Make target and verifier. Seventeen focused tests cover dormancy,
expiry, pending endpoints, posthumous seeds, same-step ordering, strict spacing,
overlapping exclusions, imposed-death rejection, complete cohort coverage,
capture tampering and non-overwriting deterministic exports. Published evidence
recomputes with process creation forbidden. The focused CTests and original
day-512 bundle verification also pass.

The compressed result is 2,241 bytes. No source archive, trace tree or new image
bundle is duplicated. The captured native sources match the inspected stage,
spacing and seed-bank rules; their identities are retained in the audit, without
requiring future working-tree C files to remain unchanged.

| Evidence | SHA-256 |
| --- | --- |
| Frozen day-512 input | `099d2550d8037b3148b9c135a53b3fe3d5e971151234fa540ad8dbc6231073dc` |
| Recruit seed audit | `f9b379e0097f285cd27465b82bf0a8f7ac8986caf15c058f322a8fd770eeabcf` |
