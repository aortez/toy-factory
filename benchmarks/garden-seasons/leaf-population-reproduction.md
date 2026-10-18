# Shrub reproduction misses both capacity and resource timing

Shrub 17 in the fewer-blocker, condition-only run never purchases a seed during
`(128,232]` days. On 16 ticks when the bank had room earlier in the same
reproduction pass, it meets every non-capacity check but an earlier plant has
already filled the slot. On the eight ticks when it actually sees room, it
lacks energy seven times and water once. Its flower is ready in every one of
these visits.

Thus neither capacity nor daily resource balance alone explains the failure.
The shrub is often eligible when the bank is full, and ineligible when its
turn comes with room. This resolves the access question from the
[offline replacement diagnosis](leaf-population-fallback-loss.md), without
changing the simulation or establishing which policy change would help.

## The ordered receipts expose the missed chances

All 6,656 reproduction-cadence ticks in the window are covered. Shrub 17 is
blocked only by capacity on 2,142 of its visits, including 16 visits on ticks
with an earlier opening. The 31 opening-tick visits partition as follows:

| What shrub 17 sees at its visit | Ticks |
|---|---:|
| Bank filled earlier; all other checks pass | 16 |
| Bank filled earlier; energy also insufficient | 6 |
| Bank filled earlier; water also insufficient | 1 |
| Bank still has room; energy insufficient | 7 |
| Bank still has room; water insufficient | 1 |

The plant needs 208 energy and 184 water to qualify. These are the existing
eligibility thresholds, not the seed debit. The eight open-bank visits are:

| Day | Energy | Water | Failed resource check |
|---|---:|---:|---|
| 152.875 | 168 | 508 | Energy |
| 161.891 | 187 | 508 | Energy |
| 184.875 | 172 | 508 | Energy |
| 191.016 | 44 | 503 | Energy |
| 191.031 | 50 | 508 | Energy |
| 193.891 | 188 | 508 | Energy |
| 199.094 | 243 | 113 | Water |
| 225.891 | 192 | 508 | Energy |

For example, at day 152.875 shrub 17 is visited first. It has a ready flower,
no cooldown or stress, sufficient light and water, but only 168 of the required
208 energy. Flower founder 1 subsequently buys the available seed slot. At
day 159.015625, shrub 17 instead has 252 energy and 508 water, but ground-cover
lineage 8 has already filled the slot before its visit.

The frozen runtime already enables a last-buyer cursor after day 48. It starts
the next reproduction pass at the living lineage succeeding the last buyer,
wrapping if necessary, then traverses physical slots cyclically. This is not
a fixed-first-slot explanation, nor evidence that the cursor was disabled.
The receipts show actual ordering and eligibility; they do not simulate a
different order.

## Both runs buy thirty seeds but distribute them differently

The original run has 48 cadence ticks where at least one plant sees space;
the fewer-blocker run has 31. These are ticks, not independent slot openings:
an unfilled slot may remain available across consecutive ticks. There are
18 opening ticks without a purchase in the original and only one in the
fewer-blocker run. Both make 30 purchases in the window.

| Family | Original placement purchases | Fewer-blocker purchases |
|---|---:|---:|
| Flowers | 8 | 12 |
| Shrubs | 12 | 3 |
| Ground cover | 10 | 15 |

All three experimental shrub purchases belong to shrub 16. In the original
run, shrub 19 supplies nine of the family's twelve purchases. It sees room
on 28 ticks and has the same 208-energy and 184-water thresholds as experimental
shrub 17. At days 152.84375 and 152.859375 it has insufficient energy, but the
slot remains available; at day 152.875 it reaches 240 energy and buys it.
Later, a longer opening likewise lasts until its day-191.09375 purchase.

These are different plants in different population trajectories. They show
how resource recovery and competitor readiness interact, not an isolated
effect of repair, placement, or body geometry. More seed purchases would also
not by themselves establish successful germination or long-term replacement.

## Next diagnostic

Trace short, bounded resource-budget windows around the eight open-bank visits
above. Account for income, upkeep, growth, and leaf-repair spending at the
actual steps, then determine whether repair consumes a useful reproductive
reserve or whether the plant simply cannot earn enough in time. Daily totals
cannot settle that ordering question.

Keep capacity, seed prices, eligibility thresholds, cursor behavior, and repair
policy unchanged for that diagnostic. A reproductive-reserve guard is only a
possible subsequent experiment; this comparison does not prove it would improve
survival or renewal.

The subsequent [step-budget comparison](leaf-population-budget.md) is complete.
No same-step repair addback rescues a missed opening; five energy misses follow
a full store with no later repair debit, and the other visits fall in low-income
episodes. All eight recover resources only after the bank is full again.

## Reproducible evidence

The [protocol](leaf-population-reproduction-protocol.md) fixes four replays:
original/fewer-blocker placement crossed with diagnostics off/on, condition-only
repair, weather seed `9a903368`, and a day-608 endpoint. All four calls succeed
on their first attempt in 27.571 seconds, after seven host suites pass in
129.62 seconds and ten preparation tests pass. The 44 checkpoints and four
final outputs match the preceding experiment byte-for-byte, including state,
history, and pixels; resource and purchase traces also remain identical.

The new trace uses the existing reproduction hook. It allocates bounded
session-owned storage once, retains no mutable simulation pointers, and adds
no allocation during stepping. Opening receipts preserve all visits, including
those after the slot fills. Full-bank ticks remain represented by blocker-mask
histograms. Output stops on exhausted bounds or recording errors.

The [collector and validator](../../sim/experiments/leaf_population/population_reproduction.py)
independently reconstruct pre-reproduction bank occupancy from seed lifetimes,
check living-plant coverage and ordered occupancy, reconcile every purchase
with the ledger, and check receipt masks against aggregate histograms. The
new traces occupy 91,099 bytes for original placement and 60,332 bytes for
fewer-blocker placement.

The evidence archive (`leaf-population-reproduction-results.json.gz`, kept
locally) is 521,271 bytes with SHA-256
`3258eda497056194975a308f3a8ab79bd8c980afa968cb694b8263033adb226e`. It includes
the protocol, source snapshot, process receipts, preflight results, raw
captures, and derived summaries. Unpacking verifies without executing archived
code or rerunning simulations:

```sh
docker compose run --rm -T host-player python3 -B \
  sim/experiments/leaf_population/population_reproduction.py unpack \
  benchmarks/garden-seasons/leaf-population-reproduction-results.json.gz \
  artifacts/new-reproduction-evidence
```

Nine new Python tests include exact archive round-tripping with subprocesses
forbidden, synthetic ordered-access cases, malformed receipt rejection, and
the measured resource gaps. Native tests cover bounds, incomplete recording,
allocation and stream errors, reset, latched failures, no step allocation, and
state parity. Frozen runtime inputs, ecological rules, and firmware defaults
remain unchanged. All 116 analysis tests pass in the final CTest run (43.28
seconds); formatting, whitespace, and local documentation links also pass.
