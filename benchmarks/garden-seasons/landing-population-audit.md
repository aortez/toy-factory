# Why the population dawn candidate regresses

The failed seed does not support simply increasing the dawn reserve again.
Its matched offspring have **fewer** resource deficits, but the candidate creates
different later cohorts. Those descendants include both first-night failures
after construction and mature bodies that cannot sustain their recorded upkeep.
Recent seed spending does not explain their energy failures.

This follows the [saved population screen](landing-population.md) and the
[fixed offline audit protocol](landing-population-audit-protocol.md). It uses
only weather `f7ee4528`, both reproduction orders and both arms: four existing
worlds, zero new simulations or training. The dawn candidate remains host-only,
off by default and unqualified. No ecology, policy, model or firmware changed.

## The first intervention changes shape, not just speed

Common plant 9 is born at 403365 in column 24. At 403545 the candidate declines
the eight-to-nine-node extension. It grows from another tip at 403560, just
one ecology step later; the control's next growth is at 403590. These are
different subsequent decisions and body paths, not the same body uniformly
delayed by one step.

| Common plant 9 | Daylight control | Dawn candidate |
| --- | ---: | ---: |
| First flower tick | 406515 | 404100 |
| Seed purchase tick | 406860 | 406860 |
| Seed landing column | 17 | 19 |
| Seed outcome | expires at 529740 | germinates at 457320 |
| Parent death tick | 457020 | 457020 |

The candidate flowers 2415 ticks earlier. It pays the same 48 energy and 24
water for its single seed; its child eventually dies without producing a seed.
The parent dies from water shortages in both arms, discarding 252 energy at
death. Earlier flowering is not equivalent to durable renewal.

Plant 9 is not the sole source of divergence. The first unequal seed purchase
is another matched plant's: candidate plant 8 at 406740, before plant 9's seed.
The first unequal birth is at 414180, from parent 10; that candidate-only child
dies at 415560, also the first unequal death event. The comparison uses recursive
ancestry, birth time, species and site, not numeric IDs after divergence.
Future germination/expiry is not used to label a purchase unequal retroactively.

## Matched offspring improve; later cohorts differ

Both orders have the same eight matched offspring. Their unpaid energy falls
11 → 0 units and water 177 → 168; maintenance opportunities are 16591 → 16642.
Founders' resource totals and exposures are unchanged. Matched birth identity
does not establish equal later genomes, bodies, neighbors or opportunities.

All remaining offspring belong to unmatched ancestry/site/time cohorts:

| Order / arm | Unmatched offspring | Maintenance opportunities | Unpaid energy | Unpaid water |
| --- | ---: | ---: | ---: | ---: |
| Fixed / control | 13 | 35967 | 4 | 131 |
| Fixed / candidate | 29 | 50707 | 76 | 421 |
| Rotating / control | 18 | 44587 | 109 | 148 |
| Rotating / candidate | 27 | 47949 | 129 | 391 |

The increase is not just more living-plant exposure. Among these unmatched
cohorts, fixed-order unpaid energy per thousand opportunities increases
0.111 → 1.499 and water 3.642 → 8.303. Rotating order changes energy
2.445 → 2.690 and water 3.319 → 8.154. These are different populations, not
individual rescue/harm estimates or independent weather replicates.

## Construction is only one failure mode

The following counts cover all offspring shortages, including matched plants.
A recent expenditure means a recorded debit in the preceding 3840 ticks,
including the shortage tick, clipped to the plant's birth.

| World | Energy-shortage bills / unpaid units | Bills / units with neither recent growth nor seed spending |
| --- | ---: | ---: |
| Fixed / control | 6 / 15 | 0 / 0 |
| Fixed / candidate | 36 / 76 | 16 / 53 |
| Rotating / control | 37 / 120 | 26 / 89 |
| Rotating / candidate | 47 / 129 | 34 / 113 |

Every energy shortage with recent construction is within the first day of life.
No offspring energy shortage in any of these four worlds follows seed spending
in the preceding day. That rules out a recent seed debit as their immediate
accounting explanation, not every indirect effect of earlier reproduction.

Some first-night failures also outlast the first globally productive light.
For example, candidate plant 15 first misses energy upkeep at phase 28, with
global strength 125 and nine active leaves, but zero energy uptake. Candidate
16 first misses at phase 24, strength 104, with three active leaves and zero
uptake. Reserving until global sunrise or its first productive quantum is not
the same as funding maintenance until that particular canopy earns enough.
These observations do not identify whether self-shading or neighbors caused
the attenuation.

### A mature body that a bigger opening balance cannot fund

Fixed-order candidate plant 28 is born at 648405. At its first energy shortage,
916200, it has 30 nodes and 14 roots; it dies at 916620 after eight consecutive
missed energy payments. Its final body has no active tips. It has no unpaid
water and no growth or seed spending in the retained 909120..916620 window.

The energy accounting is exact: **111 opening + 364 income − 2 overflow −
473 paid upkeep = 0 closing**. Upkeep due is 504, leaving 31 unpaid units.
Backward accounting with a 256-unit storage cap finds no possible opening
balance that could fund that recorded window, even with construction and
reproduction costs omitted. The observed income sequence/body path is held
fixed; this is not a simulated rescue or a claim that a different plant could
never survive there.

Across that window, climate light is 40–62% and the surviving samples have eight
active leaves. Recorded energy income is 364 versus a loose unshaded actual-body
upper bound of 1528, excluding the terminal sample. Both dim seasonal light and
attenuated canopy income matter to the accounting; the trace cannot partition
self-shading, live-neighbor shade or dead-body shade. The upper bound is not an
achievable no-shade world and does not identify a safe new rule.

The rotating candidate's plant 28 has the same birth identity but survives this
spell and dies later, at 978540. Its terminal window also cannot be funded by
any opening balance under the same capped, frozen-income calculation. Neither
this pattern nor mature energy failures are unique to the candidate: the
rotating control also has such terminal windows.

## Water deficits also extend beyond recent purchases

Fixed-order candidate water shortfalls include 176 bills / 456 unpaid units
with neither growth nor seed spending in the previous day. Rotating candidate
has 168 / 429. Their control counterparts are 104 / 254 in each order. Other
water failures do have recent spending; the bundle retains all of them.

There is still water elsewhere in the aggregate soil when many plants miss
payments. That does not establish that their roots could access it. Root-cell
moisture and competing uptake identities are absent, so neither “the whole
world ran dry” nor “a particular neighbor stole it” follows from these traces.

## Next decision

Keep the population qualification failure. Do not tune another universal dawn
buffer or change the seed bank on this evidence. Separate **first-night purchase
safety** from **adult resource viability**; a construction gate cannot by itself
protect a finished body through every later change in light and soil access.

The next bounded diagnostic should attribute uptake at the mature failure
windows: per-leaf light and self/live-neighbor/dead-body attenuation, plus
per-root moisture and consumption order. Reuse these pinned worlds and first
prove the added observer leaves decisions, ledgers and pixels unchanged. That
would tell us whether the next useful intervention concerns morphology,
resource access or an observation/action the controller lacks. It would require
a separately agreed replay/instrumentation step; this audit does not run it.

## Reproduction and verification

`make host-audit-landing-population` reads the saved raw bundle, without a build
or native simulation. Set `GARDEN_LANDING_POPULATION_AUDIT_OUT` to a fresh output
directory; `GARDEN_LANDING_POPULATION_OUT` locates the original raw input. The
portable result contains all selected raw excerpts and recomputable summaries.

```sh
docker compose run --rm -T firmware python3 sim/garden_landing_population_audit.py \
  --verify benchmarks/garden-seasons/landing-population-audit-results.json.gz
docker compose run --rm -T firmware python3 sim/garden_landing_population_audit.py \
  --verify artifacts/garden-landing-population-audit-v1 --verify-raw
```

| Artifact | SHA-256 |
| --- | --- |
| [Portable audit](landing-population-audit-results.json.gz) | `c40da0fc11e0a9e7cb1480faa0cbaaa328c758ddea8681d7f8981084244cf461` |
| Audit manifest | `06bf174551423a05fd88c8ec7a30be63ef1956d79861c8e152ce79e5051223d9` |
| Audit protocol | `42669be1174610d541d2a45fb512aba61b16c0c9cd9977d770588f02cd82de18` |
| Population input | `c823c7b9d1c19d476403a5741a6ff25996ad60847f4340e2207ba2260091fa2a` |
| Population raw manifest | `9e6322e3ae8709c94f7c4d6d762783214a735b9104848b3ccc5e3a4f7a15a58a` |

All eight selected full trace hashes and every plant's complete resource budget,
payment count and shortage event were checked against the original population
summary. Raw re-extraction and portable verification pass. The portable file
retains 70439 plant samples across 123 within-world plant histories and 150
merged windows, covering all 1038 shortage payment events, including founders.
The audit source archive contains 2291 files. Overlapping windows are merged;
the histories and windows are not independent trials.

Fourteen focused audit tests pass, including independent forward/backward
funding checks, cohort identity, solar-window boundaries, missing/corrupt data,
frozen outcomes and verification with process execution prohibited. The
postcapture checker additionally validates the focal first-day growth gates
and arbitration; it does not change the extracted data or historical outcomes.
All four offline CTest entries (population, dawn, light and energy audits) pass
in 36.12 seconds with four workers. Documentation links and `git diff --check`
also pass; the Make target is listed in help and has no build prerequisite.
The prior full 183-test native run belongs to the population experiment, not
this offline-only step.
