# Sunset forecast: optimistic income, plus a separate dawn/storage limit

The existing reserve gate would **approve the observed shrub purchase that
preceded its death**, but reject the ground-cover's transferred purchase. Its
flat half-income estimate overstates the last daylight income. Separately,
requiring uninterrupted energy sufficiency would be too strict for these mature
bodies: the zero-income interval costs more than their storage can hold.

[Audit protocol](renewal-seed-forecast-protocol.md) ·
[Verified data](renewal-seed-forecast-summary.json) ·
[Prior intervention and screenshots](renewal-seed-veto.md)

This is a shadow calculation at two **already observed** decisions, using only
the frozen eight-day traces. It is not a rollout with the general gate enabled,
nor a new survival or training qualification. No simulation, model, forecast,
ecology or device setting changed.

## What the current forecast sees

Both purchases occur at tick **4,620**, sun phase **116**, strength **67**. The
gate runs after current-step income, upkeep, growth and renewal, so only the seed
debit is added back to reconstruct its input. Current income is not credited a
second time. The saved C implementation and existing Python reference agree on
integer flooring, cap-before-upkeep order, the sunset payment, and the subsequent
31 night payments excluding dawn.

| Quantity | Control shrub 2 | Veto-case ground-cover 3 |
|---|---:|---:|
| Energy before / after actual seed purchase | 249 / 201 | 248 / 200 |
| Nodes / upkeep per payment | 55 / 7 | 59 / 8 |
| Current income per ecology step | 8 | 7 |
| Forecast remaining daylight income | 44 | 33 |
| Actual remaining daylight income | 7 | 7 |
| Remaining upkeep through sunset | 21 | 24 |
| Forecast sunset energy | 224 | 209 |
| Actual sunset energy | 187 | 183 |
| Remaining-night reserve target | 217 | 248 |
| Forecast margin over that target | +7 | −39 |
| Actual margin below that target | −30 | −65 |
| Existing gate's decision at this observed state | Allow | Reject |

The forecast credits eleven future income steps at `floor(current_income / 2)`:
`11 × 4 = 44` for the shrub and `11 × 3 = 33` for the ground-cover. It charges
upkeep at phases 120, 124 and 128. Actual bodies stay unchanged and there is
**no further growth, renewal, seed spending or energy overflow** before sunset.
Thus the entire **37 / 26 energy overestimate** comes from income, not a hidden
expense or a payment off-by-one.

This does not mean enabling the general gate from reset would reach these same
states or reproduce these deaths. Earlier purchases and shared bank occupancy
would change. The no-purchase contexts are the same parents in the opposite
saved traces, not independently isolated parent-only interventions.

## Why half-income is still optimistic

At tick **4,635**, strength drops to **64** and both plants earn seven more energy.
At **4,650**, strength is **60**; their income becomes zero and stays zero until
after dawn. The light solver subtracts shade from sun strength. Leaf uptake uses
**`floor(cell_light / 64)` before condition weighting**, so even a perfect,
unshaded leaf produces nothing when global strength is below 64. Fractional leaf
condition accounting cannot recover light already rounded to zero.

The forecast keeps adding half the earlier income through phase 127 despite
this known light threshold. A half-sized constant is not a conservative bound
on a rapidly disappearing, quantized resource. Shade, ray angle and leaf condition
can make the productive interval shorter; the global threshold alone guarantees
this particular zero-income interval.

## Night funding and dawn recovery are different questions

The forecast's 31 night payments cover **(4,800, 6,705]**. Dawn at **6,720** is an
additional payment, and light is still too weak to provide income. The first
globally productive strength returns at **6,885**, phase 11. Upkeep at 6,720,
6,780 and 6,840 therefore still has to come from storage or incur stress.

The no-purchase shrub illustrates the distinction:

- Sunset energy **235**, minus **217** night upkeep, leaves **18** before dawn.
- Dawn costs seven, leaving **11**; the next payment leaves **4**.
- At 6,840 it pays the remaining four of the seven owed and reaches **stress 1**.
- It earns seven at 6,885, then earns six and pays seven at 6,900, clearing stress.
  At 7,140 it has **97 energy / stress 0**.

The purchased shrub instead reaches its first post-purchase shortage at 6,420
and dies at **6,840**, before productive light returns. The purchased ground-cover
first runs short at 6,180 and dies at **6,600**, before dawn. Its no-purchase
context also experiences shortages but remains alive throughout this audit,
with energy 53 / stress 3 at 7,140. A shortage is not itself a death verdict.

The resource ledgers distinguish **required** from **paid** upkeep. For example,
the purchased shrub owes 217 across the complete night but can pay only 187.
The ground-cover dies during that window: only its 119 live steps are reconciled,
with 232 required / 183 paid; the death step and subsequent hypothetical payments
are not presented as observed spending. Death clears income and stores, so neither
its terminal step nor the shrub's terminal step is reconstructed.

## Storage prevents a simple zero-shortage rule

Between the last potentially productive step at **4,635** and the next at
**6,885**, there are **37 maintenance payments** with guaranteed zero energy
income: three before/at sunset, 31 during night and three after/at dawn.

| Fixed body, no optional spending | Energy required | Storage cap | Minimum unfunded energy even starting full |
|---|---:|---:|---:|
| 55 nodes, upkeep 7 | 259 | 256 | 3 |
| 59 nodes, upkeep 8 | 296 | 256 | 40 |

These are **fixed-body storage lower bounds**, not fabricated post-death resource
ledgers or predictions that either plant must die. All observed live samples in
this interval retain those body sizes and have zero income. The rescued shrub
actually starts the interval full and incurs exactly the three-unit shortage.
Survival uses the existing stress grace/recovery mechanism: successful maintenance
reduces stress; repeated shortages can reach the death threshold of eight.

This is an important constraint on the next proposal. Simply expanding a
"fully fund everything" reserve through productive dawn could prohibit purchases
for bodies that can survive transient shortages. Conversely, funding only the
nominal night does not guarantee survival. The investigation has **not** established
a safe stress allowance or a general reproductive policy.

## Verification and reproduction

`sim/garden_renewal_seed_forecast.py` verifies the entire prior bundle, reconstructs
both purchases, reconciles four observed trajectories and separately exposes
the heuristic's arithmetic. It repeats analysis exactly and checks the portable
JSON. Forecast, native light/world and shared accounting sources are hash-matched
to the frozen capture; the summary also records its analysis/protocol hashes.

**32 focused Python tests pass**, including 15 new boundary/accounting cases:
current-step exclusion, cap-before-upkeep, income flooring, sunset/night endpoints,
purchase identity, optional spending, missing samples, partial payment, death
censoring and the zero-income/storage bound. The forecast's existing C boundary
fixtures were checked through the Python reference; no native executable was
rerun or newly claimed as tested. Full saved-data verification also passes with
subprocess execution explicitly disabled. `git diff --check` passes.

```sh
# Offline only; no inspector, replayer, trainer or firmware execution:
python3 -W error sim/garden_renewal_seed_forecast.py \
  --check benchmarks/garden-longevity/renewal-seed-forecast-summary.json
PYTHONPATH=sim python3 -W error -m unittest \
  test_garden_renewal_seed_forecast test_garden_seed_reserve test_garden_renewal_startup
```

`--output NEW.json` writes a fresh summary without overwriting an existing file
or modifying the frozen bundle. Source bundle manifest SHA-256 remains
`dd44e765e15d4be5ed0c5c99273699718358ac8e5790af838162121620bcb5ae`.
There were **zero new native simulation/replay calls**, training runs or deployments.
The existing host-only veto and general gate remain off by default. Work remains
uncommitted; nothing was pushed.

## Next proposal

Discuss a **sun-phase-aware shadow forecast through productive morning**, reporting
predicted deficits and stress separately from an approve/reject policy. Compare
it against **all purchases in the existing saved traces**, not just these two
outcome-selected examples, before any native gate experiment. Keep body changes,
optional spending, storage overflow and death-censored outcomes visible.

That would test whether we can predict the resource trajectory usefully before
choosing how much risk automatic reproduction should take. No new coefficient,
stress allowance, rule, training objective or firmware promotion is adopted here.
