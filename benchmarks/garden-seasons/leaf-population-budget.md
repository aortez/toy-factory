# Missed seed openings are not an immediate repair-spending problem

The step budgets do not support a reproductive-reserve guard as the next fix
for shrub 17. Skipping the repair payment on the opening step would make none
of its eight missed open-bank visits affordable. Five misses follow a full
energy store with no subsequent repair spending. The other three visits fall
in two low-income episodes: energy around day 191 and water around day 199.

All eight regain sufficient resources within the following eighth of a day,
but the bank is full at the first resource-funded visit. This narrows the
[ordered-access diagnosis](leaf-population-reproduction.md): the plant's
resource recovery is poorly timed against brief seed-bank openings. It does
not establish a better policy or explain every later lineage loss.

## Five energy misses survive the storage-cap check

At days 152.875, 161.891, 184.875, 193.891, and 225.891, the plant needs
208 energy but has only 168–192. In each preceding day it earns 1,216–1,370
energy, pays 256 upkeep and 63–90 repair, and loses 870–1,053 to the storage
cap. Critically, it reaches the 256-energy cap after its last repair before
the opening. From that cap point through the miss, repair spending is zero.

These are early-day recovery misses after the intervening night. The budgets
rule out unpaid construction or a recent repair debit as their direct cause.
They also show why adding the preceding day's repair total back to the opening
balance would mislead: an unchanged income trajectory already fills storage
between those repairs and the opening. The trace does not simulate changed
leaf condition or income under a no-repair policy.

## Two other episodes have insufficient income for upkeep

The two day-191 visits are consecutive reproduction ticks in the same opening,
not independent events. Their overlapping preceding-day windows earn 196 and
223 energy against 256 upkeep due. Only 232 upkeep is actually paid in each;
repair costs another 36 and 63. At the first opening, one repair spends 9
energy, reducing the pre-reproduction balance from 53 to 44. Without that
payment, the balance would still be far below 208. The second opening has no
same-step repair and only 50 energy.

The day-199 water miss starts its preceding-day window with 303 water, takes
in 101, pays 256 upkeep and 35 repair, and ends with 113 against the 184
threshold. Its same-step repair spends 5 water; adding that back gives 118,
still insufficient. Even the preceding day's entire repair debit is smaller
than the 71-water gap, before allowing for changed future behavior.

The plant remains at 32 nodes and 26 leaves throughout all 2,244 records.
It pays no construction or seed-purchase costs anywhere in these windows.
These are maintenance and income budgets, not hidden growth expenditures.

## Resources recover after the opportunity has passed

The table uses the actual pre-purchase balances. The energy/water thresholds
are 208/184; they include reserves, not just the 48/24 seed debit. Recovery
means the first later reproduction-cadence visit satisfying both resource
checks. At every listed recovery, the only remaining blocker is a full bank.

| Opening day | Energy / water | Same-step repair E / W | Delay to resource recovery, days |
|---|---:|---:|---:|
| 152.875 | 168 / 508 | 0 / 0 | 0.03125 |
| 161.890625 | 187 / 508 | 0 / 0 | 0.015625 |
| 184.875 | 172 / 508 | 0 / 0 | 0.015625 |
| 191.015625 | 44 / 503 | 9 / 5 | 0.125 |
| 191.03125 | 50 / 508 | 0 / 0 | 0.109375 |
| 193.890625 | 188 / 508 | 0 / 0 | 0.015625 |
| 199.09375 | 243 / 113 | 9 / 5 | 0.046875 |
| 225.890625 | 192 / 508 | 0 / 0 | 0.015625 |

This remains one selected lineage in one weather/placement trajectory. More
resource-funded visits would not guarantee access, and more seed purchases
would not guarantee germination or ongoing replacement. Earlier traces still
show spacing-blocked seeds and a subsequent water-shortage death.

## Next question: why does the successful shrub recover sooner?

Do not add the reserve guard on this evidence. A more targeted next comparison
is dawn income and foliage in original-placement shrub 19 versus experimental
shrub 17. At day 152.875, the original shrub has 240 energy and buys a seed;
the experimental shrub has 168. Both face the same weather and eligibility
thresholds, but have different bodies, foliage condition, neighbors, and
population histories. Start with existing daily budgets, then use a short
matched trace only where they cannot resolve light collection and timing.

That would separate a useful repair/foliage-learning opportunity from a body
or shading constraint. It would not be an isolated causal comparison of
placement, and it would not change storage, prices, eligibility, or the cursor.

The [offline matched-day comparison](leaf-population-dawn.md) now finds higher
energy income on 96 of 104 days and healthier per-leaf condition at 95 day-end
checkpoints in the successful shrub, despite fewer leaves. Its different
position and population history still require a short leaf-level light trace
to separate exposure from condition at the focal dawn.

## Evidence and verification

The [protocol](leaf-population-budget-protocol.md) fixes two day-608 replays
of `9a903368`, condition-only repair, fewer-blocker placement, and diagnostics
off/on. Both calls pass on their first attempt in 13.151 seconds. All 22
checkpoints, both final outputs, and the three existing diagnostic files
match the preceding archive byte-for-byte, including state, history, and
pixels. The authenticated runtime, ecological rules, and defaults are intact.

The added host-only collector records one day before and a quarter day after
each focal visit, deduplicating overlaps. Its bounded storage is allocated
once, with no allocation while stepping. Recording failures latch; incomplete
traces cannot be published. The 1,731,128-byte trace contains 2,244 records,
joins 15 archived opening receipts, and independently reconciles five fully
covered calendar days with the retained daily resource ledger. All eight
focal visits match their earlier receipts exactly.

The [collector and validator](../../sim/experiments/leaf_population/population_budget.py)
checks exact coverage, six payment stages, caps, repair prices, resource and
leaf conservation, consecutive-step continuity, reproduction eligibility,
and daily totals. Native tests cover ownership, allocation/stream errors,
missing/duplicate records, reset, failure latching, and unchanged state.
Seven host suites pass before collection in 165.45 seconds, followed by ten
preparation tests. Ten focused Python tests pass, including offline verification
and exact archive round-tripping with simulator execution forbidden.
The final analysis suite passes all 126 tests in 53.12 seconds. C formatting
and whitespace checks pass as well.

The archive (`leaf-population-budget-results.json.gz`, kept locally) is 435,982
bytes with SHA-256
`ab314a17361fe939525f61c6d340fc45d9a0058f0fb0fdc9c770f432709728ed`. It retains
the protocol, source snapshot, process receipts, test results, captures, raw
traces, and derived summaries. To verify without rerunning:

```sh
docker compose run --rm -T host-player python3 -B \
  sim/experiments/leaf_population/population_budget.py unpack \
  benchmarks/garden-seasons/leaf-population-budget-results.json.gz \
  artifacts/new-budget-evidence
```
