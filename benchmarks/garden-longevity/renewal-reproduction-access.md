# Seed-bank order limits the rescued shrub's reproductive access

The [saved-trace audit](renewal-reproduction-access-protocol.md) finds two
distinct limits after the [reserve-aware FINISH rescue](renewal-dawn-reserve.md):
the shrub rarely gets an available seed-bank slot, and its one actual seed
cannot establish beside an existing neighbor. Survival alone did not solve
either problem. No simulation rules, models or device firmware changed.

In the final 16 days, shrub 12 passes every independently observable
reproduction prerequisite on **259 of 1,024 maintenance checks**. The bank is
already full at reproduction-loop entry on 189; earlier parents fill the
available slots on the other 70. It makes no seeds in that interval. These are
not 259 guaranteed missed purchases: the ordinary dark-spending safety guard
runs after the bank check and is not evaluated for these blocked turns.

## What was reconstructed

All three saved arms run to tick 245,760/day 64, with the same frozen models,
rain, 512-node pool, eight plant slots, eight seed slots and experimental rules
as their parent comparison. There are **zero new experimental native calls**,
training calls, captures or device operations.

The C update order removes expired/germinated seeds first, then performs
reproduction in current plant-array order. Reproduction only appends seeds.
Its entry occupancy is therefore final occupancy minus verified purchases;
each plant sees that count plus purchases by earlier parents. Independent
prior-count-minus-removals accounting, appended-parent order, cooldown resets,
expense receipts and resource debits agree at every step. This does not infer
individual germination-attempt order.

Reproduction is also the last resource-spending stage. Undoing only each actual
seed payment recovers that parent's pre-seed stores. The audit checks cadence,
cooldown, daylight, stress, generation, unspent mature flowers and the existing
body/trait-dependent retained-resource gate. For the mature target, its 61 nodes
and 18 roots require **248 energy and 264 water before purchase**, including
the 48-energy/24-water seed cost. The energy cap is 256; upkeep costs eight.

Flower flags include immature tissue. Prior-step flowers have enough growth
time to prove maturity here; new flags alone do not. An actual native expense
receipt is a separate positive witness. One maintenance check for child 14 in
each old arm remains maturity-unknown; none do in reserve. Terminal steps with
cleared income counters are explicitly excluded from resource reconstruction.

## The target's opportunities

The table partitions the reserve arm's living maintenance checks. Eligibility
here means the prerequisites above, **excluding bank capacity and the final
ordinary safety guard**. These are repeated checks, not unique empty slots.

| Window | Checks | Other prerequisites fail | Bank full at entry | Earlier parents fill it | Actual purchases |
| --- | ---: | ---: | ---: | ---: | ---: |
| Target's whole life | 3,123 | 2,381 | 547 | 194 | 1 |
| First noon onward, tick >= 69,120 | 2,945 | 2,220 | 534 | 190 | 1 |
| Closing, 184,320 < tick <= 245,760 | 1,024 | 765 | 189 | 70 | 0 |

The target is seventh in the array at all its recorded maintenance checks.
In the closing window, the last available slot is taken by parent 2 on 20
otherwise-eligible target checks, parent 4 on 20, parent 5 on 14, parent 6 on
15, and parent 7 on one. There are no target safety-guard refusals with an open
bank. That does not show the guard would permit all the blocked checks.

All 765 remaining closing checks have energy below 248. Darkness overlaps 528
of them and stress overlaps 208; those failure counts must not be summed.
Water, flower availability and cooldown do not fail in this interval. The
threshold and bank order are separate constraints, not alternative explanations
that can be collapsed into one cause.

Across its entire rescued life the target sees an open bank on only four
maintenance checks:

- 72,480, 72,540 and 72,600: energy 53, 85 and 125, all below 248. The first two
  also have nonzero stress. Water is 506 throughout.
- 149,580, sun phase 52: energy 248, water 506, stress zero and seven mature
  unspent flowers. It pays the ordinary 48/24 cost, leaving 200/482.

The old control/defer targets die before first noon. Their whole-life counts
are 165/166 maintenance checks, with 13 otherwise-eligible checks each: 11
full at entry and two filled by earlier parents. Neither buys a seed. Their
after-noon/closing denominators are zero, not failed opportunities.

## A daily expiry/refill schedule, not successful turnover

Every closing-window post-step bank contains eight seeds in all three arms,
but the bank is not continuously full inside each step. In reserve there are
**128 expiries and 128 replacements across 112 release steps**; every release
is filled immediately. Sixteen steps release two seeds. No seeds germinate.
The other 3,984 ecology steps start reproduction with a full bank.

The one-day seed lifetime preserves a repeated release schedule. Reserve
replaces one seed per day at phases 44, 52, 56, 64, 76 and 120, and two at phase
88. Both old arms instead replace one each at 44, 48, 52, 56, 64, 76, 88 and
120, across 128 release steps. The total remains eight seeds per day.

Of reserve's 112 release steps, the target passes the independent prerequisites
on 70 but earlier parents fill the bank. On the other 42 it is ineligible.
At phase 88, for example, two slots can open and both can be filled before its
turn. The archive retains each release, buyer order, parent stores and gates.

| Parent | Array position, one-based | Closing purchases, control/defer | Closing purchases, reserve |
| --- | ---: | ---: | ---: |
| 2 | 1 | 42 | 39 |
| 4 | 2 | 32 | 36 |
| 5 | 3 | 16 | 16 |
| 6 | 4 | 31 | 32 |
| 7 | 5 | 7 | 5 |
| 9 | 6 | 0 | 0 |
| 14 in old arms / 12 in reserve | 7 | 0 | 0 |

The last row describes different individuals, not a matched lineage. Parent 9
also has 278 otherwise-eligible closing checks in reserve, all bank-blocked:
199 full at entry and 79 filled earlier. The ordering effect is not unique to
the rescued target. Which earlier parent buys still varies with its resources,
cooldown, flowers and safety guard; this is not a fixed eight-seed parent roster.

## Access is not establishment

The target's only seed lands in column 11 at 149,580 and expires at 153,420.
All **248 mature observations** have a stable spacing witness: living shrub 9
at column 13, present since tick 45,720. Thirty-one also lack moisture. No
offspring is produced. These are saved post-step observations with a stable
preexisting neighbor, not an invented within-step germination trace.

Nothing here changes the parent result: seven living plants at day 64, zero
closing births/deaths, and lower historical full-day offspring survival in
reserve than in the old arms. Changing seed allocation might distribute
purchases differently, but could also shift energy costs, deaths, random-number
consumption and competitive outcomes. It does not create planting space.

The next proposed experiment is a **host-only deterministic rotating purchase
order**, paired against this exact reserve control, beginning only after the
first-noon handoff window. Keep capacity, costs, resource gates, safety guards,
models, rainfall and spacing unchanged. Measure who gains access, who pays,
survival, germination and durable descendants, not just seed totals. Freeze the
precise rotation and run budget before execution. This is a proposal, not an
implemented policy or evidence that fairer allocation repairs renewal.

## Evidence and validation

- [Portable audit](renewal-reproduction-access-summary.json), SHA-256
  `6a64a9792486ab03267b0d077514c84978e58b062743624625291830cf86fae3`.
- Immutable parent bundle: `artifacts/garden-renewal-dawn-reserve-v1`, manifest
  `ee74ce6b80ff164c5f2358fbcc9829832fac6debebc032086e78b2c52a39f06b`.
- Parent native sources, historical analysis dependencies, repeated captures,
  original saved-data analysis, portable export and existing frames all verify.
  New audit modules are additional dependencies, not replacements for old ones.
- All **331,756 live resource budgets**, **1,541 purchases** and **82,942 living
  maintenance checks** reconcile. Six/six/four terminal steps are not rebuilt.
  Whole-step bank summaries use ticks 15..245,760; they are not the parent's
  left-endpoint occupancy exposure totals. Closing-window counts agree.
- New analysis repeats exactly, and an independent Docker run matches the
  portable file. Eighteen new synthetic tests cover limits, update order,
  releases, maturity, denied spending, malformed evidence and input preservation.
- **84/84 default and 84/84 experimental CTests pass.** The first default run
  had three provenance failures because creation of this portable summary
  overlapped source-snapshot tests. With files stable, the complete suite passes
  unchanged. No provenance guard was disabled.
- Reuse the [parent's actual screenshots](renewal-dawn-reserve.md#actual-native-screenshots).
  No new images or experiments were needed. Work remains uncommitted/unpushed.

```sh
docker compose run --rm --no-deps firmware python3 -W error \
  sim/garden_renewal_reproduction_access.py \
  --check benchmarks/garden-longevity/renewal-reproduction-access-summary.json

# Or choose a fresh path outside the immutable parent bundle:
docker compose run --rm --no-deps firmware python3 -W error \
  sim/garden_renewal_reproduction_access.py \
  --output artifacts/NEW-reproduction-access.json
```
