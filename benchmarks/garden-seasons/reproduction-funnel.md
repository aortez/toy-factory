# Establishment improves, but many survivors never produce a seed

The [saved-trace audit](reproduction-funnel-protocol.md) separates the fresh
confirmation's reproduction bottlenecks without running or changing the
simulation. Of 55 established late treatment plants, **35 produce no seed**,
thirteen produce seeds still waiting to germinate, six have a day-surviving
child, and one has a living child still too young for that classification.

The largest observed gap is before seed production. It is not usually an absence
of flower tissue: 33 of those 35 nonproducers have flowers recorded. However,
these snapshots do not identify flower maturity, an available unspent flower,
or the exact resource/capacity gate at the production decision. The next useful
measurement is a host-only production-gate diagnostic, not another policy tweak.

## Scope and event accounting

Read all 64 primary traces from the [fresh reserve confirmation](seedling-confirmation.md),
covering 32 matched seasonal worlds, eight weather seeds, two layouts and two
controllers through day 128. No new worlds, replays, tuning or training are used.
Both arms retain their original wider-scattering ecology and explicit guard
selection; device and normal host defaults remain unchanged.

The native implementation creates seeds after germination, at age zero, at most
once per parent per step. The audit verifies this contract and follows every
`(parent lineage, creation tick)` through the ordered seed bank. Every removal
reconciles with an exact expiry or a new child, including after parent death or
reclamation. Counters, ancestry, daily hashes and the complete saved plant
lifetimes match. The analysis was repeated from raw inputs with identical output.

| All seeds, including founder and short-lived-parent production | Control | Guard |
|---|---:|---:|
| Created | 2,026 | 1,866 |
| Germinated | 1,175 | 1,009 |
| Expired | 596 | 601 |
| Still banked at the horizon | 255 | 256 |
| Germinations at/after parent death | 542 | 468 |

Almost half the births occur at or after parent death. The same-tick case is
well-defined: maintenance/death runs before germination. Ending lineage tracking
at death would miss these descendants. Banked seeds are pending, not failures.
They live for 32 Garden days; seeds produced by closing-year parents cannot
reach expiry within this 16-day closing birth window.

Founders produce 643 → 640 seeds. Established descendants produce 1,353 → 1,226;
other descendants produce 30 → zero. The last category is excluded from the
establishment-conditioned parent funnel, but not from seed/birth accounting.
These are different resulting cohorts, not individually matched descendants.

## Established-parent funnel

An established descendant has survived a full day, with the original strict
death boundary. A durable parent has at least one child that also survived a
full day. These are historical achievements, not a requirement that both remain
alive at the endpoint. Closing-year parents were born strictly after day 112.

Stages are mutually exclusive and describe the furthest observed result. A
parent in the failed-child stage may still have banked seeds or reproduce later.
An alive nonproducer has not produced a seed **yet**; its future is not known.

| Furthest stage at day 128 | All-history control | All-history guard | Closing control | Closing guard |
|---|---:|---:|---:|---:|
| No seed produced | 329 | 424 | 20 | 35 |
| Seeds produced, no child, seeds still pending | 35 | 42 | 9 | 13 |
| Seeds produced, no child, all seeds expired | 43 | 55 | 0 | 0 |
| Children exist, no day survivor, living young child remains | 4 | 4 | 1 | 1 |
| Children exist, no day survivor or living young child | 61 | 29 | 3 | 0 |
| Durable parent | 276 | 285 | 5 | 6 |
| Total established descendants | 748 | 839 | 38 | 55 |

The rule creates 91 more established descendants, but seed-producing parents
are nearly unchanged: **419 → 415**. Established parents produce fewer children
(757 → 643), yet more of those children achieve full-day survival (493/747
eligible → 528/630). Child establishment improves, while the number of parents
getting as far as seed production does not scale with the larger survivor cohort.
This describes the observed populations, not an isolated causal penalty from
the guard.

Of the 424 all-history guarded nonproducers, 359 have died and 65 remain alive;
398 had flower tissue recorded, 26 did not. This is not exclusively a too-young
endpoint population. For closing guarded nonproducers, 29 remain alive and six
have died; 33 had flower tissue, two did not. Of the thirteen closing parents
with pending seeds but no child, ten remain alive and three are dead. These
reconcile the earlier finding of 48 childless late survivors, 39 still alive.

The seven children of established closing treatment parents comprise six
day-surviving children and one living youngster, with no observed early death.
Control has twelve children: five eligible day survivors, six eligible early
deaths and one living youngster. This is the **children-of-late-parents** subset,
not the broader closing birth cohort used by the confirmation's acceptance gates.

## Equal-age views and censoring

The following landmarks use each parent's own age. Include only parents whose
birth plus the landmark is within the recorded horizon, but keep those that
died before that landmark. Events after the cutoff do not contribute. All cohorts
are already conditional on first-day establishment; they are not general fitness
estimates or matched-individual counterfactuals.

| Parent age | Observed parents, control → guard | No seed by that age | Durable by that age |
|---|---|---|---|
| 1 day | 748 → 839 | 478 → 591 | 0 → 0 |
| 2 days | 747 → 839 | 451 → 560 | 19 → 32 |
| 4 days | 746 → 837 | 428 → 544 | 74 → 76 |
| 8 days | 713 → 796 | 380 → 480 | 109 → 104 |
| 16 days | 710 → 784 | 350 → 436 | 165 → 170 |

At age sixteen, 350/710 (49.3%) control and 436/784 (55.6%) treatment parents
have produced no seed. The observed groups include 449 and 521 parents already
dead by that age. Thirty-eight control parents lack calendar follow-up (26 alive,
twelve dead at the horizon), versus 55 guarded parents (45 alive, ten dead).
They are reported as censored, never quietly counted as survivors.

For closing parents at age four, 19/36 control and 34/53 guarded parents have no
seed. Only three control and twelve treatment closing parents have eight days
of follow-up, and none has sixteen days. The compact evidence retains every
landmark and its denominators; zeros in the empty sixteen-day closing group are
not evidence of failure.

## Species, controllers, layouts and adverse worlds

| Species, all established descendants | Established, control → guard | No seed | Durable |
|---|---|---|---|
| Flower | 364 → 435 | 158 → 212 | 128 → 143 |
| Shrub | 122 → 130 | 71 → 82 | 36 → 42 |
| Ground cover | 262 → 274 | 100 → 130 | 112 → 100 |

Ground cover's larger establishment cohort includes more nonproducers while
durable parent count falls. Flower absence alone cannot explain this: 126 of
its 130 guarded nonproducers had flower tissue observed. Actual purchase gates
and flower readiness have not yet been measured.

Baseline no-seed counts are 173/431 → 234/472 established parents, adaptive
156/317 → 190/367. Rainfed is 201/467 → 240/490, crowded 128/281 → 184/349.
All eight weather blocks' no-seed counts rise, but populations and stage mixes
change too; the summary retains their denominators and complete funnels.

The table includes every distinct world that lost late establishment or
historical durable parents in the confirmation (thirteen worlds, with overlap
between the two regression lists). Fractions are **no seed / established
parents**, not probabilities for a common set of individuals. `0/0` is an empty
cohort, not a zero-percent failure rate.

| World | All-history no seed, control → guard | Closing no seed, control → guard | Historical durable, control → guard |
|---|---|---|---|
| Rainfed / baseline / `ed52188c` | 20/50 → 22/39 | 3/4 → 3/4 | 22 → 14 |
| Rainfed / baseline / `4f0b9247` | 22/61 → 22/49 | 3/3 → 4/6 | 30 → 19 |
| Rainfed / baseline / `0bb887d1` | 27/67 → 30/61 | 1/4 → 2/5 | 30 → 25 |
| Rainfed / baseline / `c629bb63` | 10/16 → 11/16 | 0/0 → 0/0 | 5 → 3 |
| Rainfed / baseline / `82deacfd` | 5/21 → 12/27 | 0/2 → 0/0 | 10 → 10 |
| Rainfed / adaptive / `c629bb63` | 8/18 → 8/12 | 0/0 → 0/0 | 8 → 2 |
| Crowded / baseline / `ed52188c` | 7/15 → 7/15 | 1/1 → 0/0 | 3 → 5 |
| Crowded / baseline / `0bb887d1` | 14/22 → 15/22 | 0/0 → 0/0 | 6 → 5 |
| Crowded / baseline / `647001a8` | 8/19 → 11/24 | 2/5 → 2/4 | 8 → 7 |
| Crowded / adaptive / `ed52188c` | 12/21 → 9/18 | 1/1 → 0/0 | 4 → 4 |
| Crowded / adaptive / `a9c30c1e` | 15/32 → 17/34 | 1/1 → 2/2 | 16 → 14 |
| Crowded / adaptive / `647001a8` | 15/28 → 19/35 | 2/4 → 1/4 | 11 → 9 |
| Crowded / adaptive / `c629bb63` | 4/8 → 6/9 | 0/0 → 0/0 | 1 → 0 |

Not every adverse world shares a cause. For example, rainfed/baseline
`82deacfd` loses its closing established cohort altogether; there is no late
surviving parent there to diagnose as a seed nonproducer. Other worlds lose
historical durable parents despite improved closing establishment. The full
per-world funnels remain available without selecting only favorable families.

## What the blocker flags can and cannot say

There are 8,237,511 control and 8,261,707 treatment mature-seed post-step samples.
The most frequent overlapping flags are moisture, spacing and light. For the
treatment, they occur in 7,743,582, 7,406,688 and 6,693,619 samples respectively;
node capacity appears in 391,090, plant capacity in 118,483 and cold in 951,138.
Three treatment and seven control mature snapshots have no blockers at all.

These are **time-weighted observations of waiting seeds**, not independent seed
counts or exact failed-check receipts. Long waits contribute more samples, flags
overlap, and light/space can change after the actual germination check. They do
not identify the cause of seed nonproduction, which happens in a different stage,
nor establish which single change would rescue an ungerminated seed.

## Evidence and verification

The [summary](reproduction-funnel-summary.json) contains all cohorts, age
landmarks, partitions, seed accounting and per-world summaries. The
[portable ledgers](reproduction-funnel-ledgers.json.gz) retain every parent and
all 3,892 seeds, including their creation, disposition, child attribution and
post-step histograms. Their decompressed SHA-256 is
`b420df72e0a4dc64ca6d47817ed1df4a2847e670c5149c45260bbdb2c570ebd0`;
summary SHA-256 is
`95e81a0c02eb3b65dae67e54b5a05420cf7f178f3d73057f1dd56d0881caf879`.
The input confirmation archive is fixed at
`49baf29c3e2976bfdfb0bbbef19240ceadbfc3747d9354dfe6afe3a89fc4f1e5`.

Both passes read the same 64 compressed traces, checking hashes before and after
each audit and source snapshots at start/end. They reconstruct identical output
from 2,097,216 ecology snapshots. All saved daily hashes, birth/death lifetimes
and the earlier established/no-child/durable cohort counts reconcile. No native
simulation is invoked by the analyzer. The eight
[previously verified screenshots](seedling-confirmation.md#fixed-screenshots)
show these exact trajectories and remain unchanged.

Seven focused tests cover production collisions, missing steps, metadata and
counter corruption, seed-bank/child order, exact dormancy/expiry boundaries,
posthumous germination after reclamation, young living/dead children, one-day
survival boundaries, age censoring and future-event leakage, plus portable
evidence. The container offline regression suite ran 55 tests: 51 passed and
four native-only checks were skipped. The newly registered
`garden-season-reproduction-funnel` CTest also passed. No firmware rebuild or
device flash is required for this Python-only analysis and CTest registration.

```sh
python3 sim/garden_season_reproduction_funnel.py collect \
  --bundle artifacts/garden-seasonal-seedling-confirmation \
  --out artifacts/garden-seasonal-reproduction-funnel-new --jobs 4
python3 sim/garden_season_reproduction_funnel.py verify \
  --bundle artifacts/garden-seasonal-seedling-confirmation \
  --out artifacts/garden-seasonal-reproduction-funnel-new --jobs 4
```

Collection requires a new output directory. Full results and verification logs
remain in ignored artifacts under the `garden-seasonal-reproduction-funnel`
prefix. No previous evidence was replaced.

## Next proposal

Instrument the **actual seed-production eligibility stage** in an explicit
host-only observer: mature/unspent flower availability, bank capacity, cooldown,
light, stress and the energy/water reserve comparisons at the decision. Use
unchanged replayed worlds with hash equality to establish that observation has
no effect. Agree the bounded panel/selection before collecting those receipts.

The present audit identifies where progress stops, not which gate should be
relaxed. Preserve the confirmed first-day rule while measuring that distinction.
No new controller, fitness rule or ecology qualification is claimed here.

Follow-up: the [exact production-gate audit](production-gates.md) now observes
these same trajectories without changing their states. It identifies seed-bank
capacity as the sole failed condition at some visit for 31 of the 35 guarded
late nonproducers. No production rule or bank capacity has yet been changed.
