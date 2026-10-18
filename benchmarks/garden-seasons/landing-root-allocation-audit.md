# Root allocation changes cohorts and worsens matched water budgets

The population regressions are **not just a change in which plants are born**.
Comparable nonfocal plants also miss more water payments over equal lifetime
windows. Later recruitment and the focal plant's longer lifetime contribute
as well. All four original population harm screens still fail; this audit does
not change their thresholds or justify promoting the allocation rule.

This is an offline analysis of the [completed comparison](landing-root-allocation.md),
following a [fixed audit protocol](landing-root-allocation-audit-protocol.md).
It uses the existing four pairs and exact repeats, with **zero new simulations**,
no training, no policy changes and no device flash.

## Separating cohorts from exposure

Birth matching uses recursive ancestry, birth tick, column and species. A
reused numeric ID is not a match: the daylight worlds match control 21 with
candidate 23, and the dawn worlds match control 14 with candidate 15. There
are 11 matched nonfocal offspring in each daylight pair and 10 in each dawn
pair. Five founders and the focal shrub are accounted for separately.

For every matched pair, the common window ends at the earlier death or the
fixed day-256 endpoint, including any terminal payment. Both arms therefore
face the same number of payment opportunities. Remaining lifetime exposure
is kept in a separate tail. Newborns have no payment at their birth tick;
zero-exposure rates are unavailable, not zero.

| Baseline | Total offspring payment opportunities | Total unpaid water | Unmatched births | Unmatched unpaid water |
| --- | ---: | ---: | ---: | ---: |
| Fixed daylight | 52558 → 60655 | 308 → 397 | 9 → 14 | 76 → 137 |
| Fixed dawn | 67349 → 57208 | 589 → 703 | 26 → 24 | 359 → 444 |
| Rotating daylight | 61178 → 60655 | 325 → 397 | 14 → 14 | 93 → 137 |
| Rotating dawn | 64591 → 64040 | 559 → 793 | 24 → 31 | 329 → 534 |

Unmatched does not mean unrelated: a different birth time or ancestor makes
an offspring unmatched even when it occupies the same site. In fixed dawn,
the changed cohort has fewer births and much less exposure but more unpaid
water. The regression cannot be explained merely by having more plants.

### Exact contributions to the water rate change

Each cell below is that group's candidate unpaid units divided by **all
candidate offspring opportunities**, minus the equivalent control quantity,
scaled by 1000. Columns sum to the observed rate change before rounding.
The [portable results](landing-root-allocation-audit-results.json.gz) retain
integer counts and exact rational values. These are arithmetic contributions,
not percentages, within-group rates or causal responsibility scores.

| Exposure group | Fixed daylight | Fixed dawn | Rotating daylight | Rotating dawn |
| --- | ---: | ---: | ---: | ---: |
| Focal common window | -0.590 | -0.431 | -0.507 | -0.449 |
| Focal extra lifetime | +0.973 | +0.979 | +0.973 | +0.874 |
| Matched nonfocal common windows | +0.174 | +0.731 | +0.617 | +0.258 |
| Matched nonfocal lifetime tails | -0.685 | -0.167 | -0.588 | -0.200 |
| Unmatched births | +0.813 | +2.431 | +0.739 | +3.245 |
| **Total increase per 1000 opportunities** | **+0.685** | **+3.543** | **+1.233** | **+3.728** |

The original rates remain 5.860 → 6.545, 8.745 → 12.288, 5.312 → 6.545 and
8.654 → 12.383 respectively. Changed cohorts make a large positive contribution,
especially with dawn protection. The focal plant's extra lifetime also includes
56/59 missed water units, even though its common-window shortages disappear.
Longer survival is beneficial but exposes it to bills that the dead control
never faces.

## Matched plants also regress

| Guard history | Matched nonfocal plants | Equal payment opportunities per arm | Common-window unpaid water |
| --- | ---: | ---: | ---: |
| Daylight | 11 | 25956 | 165 → 201 |
| Dawn | 10 | 20354 | 178 → 193 |

These shortage results repeat under both reproduction orders. The affected
histories are shared, not four independent demonstrations of neighbor harm.
Matched common-window energy shortages do not increase. Founder accounts are
identical across every comparison.

Whole-lifetime totals conceal some of the regression. Daylight matched
nonfocal plants have **201 unpaid water units in both arms**, but the candidate
dies earlier in several pairs and avoids 18 later opportunities containing
36 unpaid units. In the shared exposure it misses **36 more** units. In dawn,
common-window deficits increase by 15, while different tails reduce that to a
whole-lifetime increase of only two. Earlier death is not a resource rescue.

### An early nearby shrub loses retained water

Plant 11 is born at tick 403365 in column 21, near the focal shrub in column
24. Through the common endpoint 456300, each arm has 883 maintenance
opportunities. Candidate water income first falls below control at 407850
under daylight guards and 407985 under dawn guards, after the focal purchase
at 406695/406755.

| Water account change through 456300 | Daylight | Dawn |
| --- | ---: | ---: |
| Gross income | -115 | -125 |
| Overflow | -109 | -118 |
| Retained income | **-6** | **-7** |
| Construction or reproduction spending | 0 | 0 |
| Paid upkeep | -6 | -7 |
| Unpaid upkeep | +6 | +7 |

Both water accounts end empty. The candidate first misses a payment at
455880; the control first misses at 456000. Candidate death is 456300 versus
456420: **two maintenance intervals earlier**, not a large lifespan collapse.
The recorded construction spending and node/root counts do not change before
death. This is a real matched resource loss, but aggregate receipts cannot
identify the exact soil cells or establish that direct root competition is
the sole mechanism.

### Larger later losses include seed spending

Two affected matches are born at 590640, after the focal candidate has died.
Their changed histories cannot be described as contemporaneous competition
with a living focal shrub. They retain the same construction water spending,
but each candidate spends **24 extra water units on reproduction**.

| Matched plant and shared endpoint | Change in retained water | Extra seed spending | Common unpaid water | Control water still stored |
| --- | ---: | ---: | ---: | ---: |
| Daylight plant 16 through 639480 | -16 | +24 | 0 → 23 | 17 |
| Dawn plant 17 through 644700 | +1 | +24 | 0 → 16 | 7 |

The daylight account balances as 16 fewer retained units plus 24 extra spent
units = 23 missed upkeep units plus 17 fewer stored units. The dawn candidate
actually retains one additional water unit: its 24 extra spent units consume
that gain, 16 units of otherwise-paid upkeep and seven units of stored water.
Its first additional seed payment is at 594780; its first missed upkeep is
at 644280. This is not simply a lifetime shortage of gross uptake.

Other matched plants improve or remain unchanged, and all are retained in the
result. For example, dawn matches 7 and 14/15 miss three and five fewer water
units respectively over common exposure. The report does not turn selected
losses into a claim that every neighbor is harmed.

## Verification and reproduction

The tool verifies all 16 complete adult trace hashes, parses the eight distinct
arm streams, and retains every matched common-window receipt. Deduplication
leaves **47 unique histories and 451036 plant samples** in a roughly 3.1 MiB
portable file. Income, overflow, continuity, birth endowment, construction,
reproduction, upkeep, terminal discard, exposure and shortages reconcile.
Full-lifetime common windows also reproduce the original lifetime accounts.

All **14 focused tests pass**, including recursive identity matching, terminal
and newborn boundaries, changed denominators, zero exposure, earlier-death
masking, corruption rejection and no-process portable verification. The new
CTest registration passes. Raw and portable verification pass, and a second
independent extraction/export is byte-identical. The previous capture and its
protocol retain their original hashes. The full native suite was not rerun:
no C or firmware code changed, and this audit does not execute the simulator.

```sh
make host-audit-landing-root-allocation  # Fresh output path required
docker compose run --rm -T firmware python3 sim/garden_landing_root_allocation_audit.py \
  --verify benchmarks/garden-seasons/landing-root-allocation-audit-results.json.gz
docker compose run --rm -T firmware python3 sim/garden_landing_root_allocation_audit.py \
  --verify benchmarks/garden-seasons/landing-root-allocation-audit-results.json.gz \
  --bundle artifacts/garden-landing-root-allocation-v1
```

Set `GARDEN_LANDING_ROOT_ALLOCATION_AUDIT_OUT` to a new file for repeat exports.
Neither the Make target nor either verification mode builds or runs firmware.
Portable verification also needs the pinned original result in this repository;
raw verification additionally needs the local capture bundle.

| Artifact | SHA-256 |
| --- | --- |
| Portable audit | `5dda8d5f5229690437c5250a718e7fb43cf954fd627ce8ea733607cbcad6e16f` |
| Audit protocol | `ac5cf980980404d01a9e7f639926c83531612db8b08d122913e570eca8d72f2a` |
| Original result | `8877c4e6f7f951ec06c546c5fc6f3e0ea0175a250b70e21596e734cd8fa63d76` |
| Original raw manifest | `b2aab73b6ed9fadf1e28d1dd32e28911202661ca0ff593cc3c1a3641f4195972` |

## Decision and next investigation

Keep the allocation rule focal and experimental. Its individual benefit is
real, and so are the matched water regressions; the later population result
also depends strongly on recruitment and reproduction timing. Do not loosen
the harm screen or infer that an extra root is universally harmful.

The [completed seed-spending follow-up](landing-seed-spending-audit.md) rules
out a persistent inventory debit from those extra purchases: both plants
refill completely within half a garden day. After a later shared saturation,
with no further seed or growth spending, candidates retain 40/23 fewer water
units. Controls skipped the extra seeds only because their banks were full.
The lifetime balances above remain correct, but do not establish that seed
costs caused death. The follow-up proposes passive per-root/soil-cell tracing
during the later dry-down; no new reserve or counterfactual has been run.
