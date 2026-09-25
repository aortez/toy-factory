# Seedlings need access to light; the flower loses its energy margin

The saved [spacing comparison](renewal-seed-spacing.md) now has a light/spending
audit. Six of its 19 new seedlings earn no whole energy unit in recorded live
steps. Five have **zero photosynthesis numerator**, not merely an unfortunate
rounding remainder. The sixth reaches useful light just before death, too late
to accumulate one unit. The flower's final-day income falls to **280 versus
732** in the matched control, with lower sampled light and deteriorating leaf
condition. Its body size and upkeep rate never change.

[Protocol](renewal-establishment-light-protocol.md) ·
[Portable evidence for all 19 seedlings and both flowers](renewal-establishment-light-summary.json) ·
[Existing six native screenshots](renewal-seed-spacing.md#native-screenshots)

## Scope and what the light telemetry proves

This is offline analysis of the frozen two-column/control traces: no new
experimental simulation calls, training, mechanics, models or device changes.
All new seedlings, IDs 13–31, are followed until death or day 64, with separate
first-day summaries. Six of 17 eligible survive their first day; the final two
births lack a full scheduled day of follow-up. One of those two already dies.
Flower 5 is compared at matching ticks and leaf coordinates after tick 69,120.
The two final-day windows were declared before analysis, not selected for their
appearance. One garden day is 3,840 logic ticks / 256 ecology steps.

The native photosynthesis calculation sums `floor(light / 64) * condition`
over mature leaves, adds the previous remainder, then divides by 255. It
therefore has four light bands, 0–3; remainder accumulation preserves condition
fractions but not sub-64 light. The audit recovers the exact numerator from
gross income and remainder changes, accounting for wear before uptake.
With every prior leaf still healthy enough to contribute, zero numerator
proves **all those leaves** have band zero, not just the sampled leaf.

The raw observer samples only one mature leaf per ecology step. It gives an
exact light value at that site, not a simultaneous full-canopy map. Fifteen
intervening logic ticks mature every previous leaf; the observed leaf counts
and selected conditions agree with this. The audit does not identify which
neighbor or self-shading tissue blocked a ray. Terminal checkpoints clear
income/stores and are retained without fabricated resource budgets.

## Seedling failures and successful escapes

These six all exhaust their initial 64 energy. Their paid pre-income actions
are exclusively shoot extensions; none spends on root extensions, renewal or
seeds. Water remains available: their final live stores range from 88 to 308.

| Seedling | Shoot extensions | Growth energy | Paid upkeep energy | Exact lifetime light numerator | Bright-sky samples at the ambient floor |
|---|---:|---:|---:|---:|---:|
| 14 | 5 | 35 | 29 | 248 | 32 / 33 |
| 15 | 3 | 24 | 40 | 0 | 45 / 45 |
| 18 | 4 | 32 | 32 | 0 | 41 / 41 |
| 19 | 4 | 32 | 32 | 0 | 12 / 12 |
| 23 | 7 | 56 | 8 | 0 | 31 / 31 |
| 30 | 4 | 32 | 32 | 0 | 7 / 7 |

"Lifetime" here excludes the cleared terminal step. Bright-sky means global
strength at least 64, not that the plant is illuminated. Every listed floor
sample is light **24**, not just below 64. At tick 80,325, seedling 14's sampled
leaf finally receives light 66 at condition 248, adding 248/255 of an energy
unit. The plant dies at 80,340. Merely changing fractional accumulation would
not create extra above-ambient light for the five zero-numerator plants.

All 27 paid extensions among these six have available candidate light below
64. Twenty-six have a maximum of 24; seedling 19's first has a maximum of 44.
These are recorded available choices, not reconstructed chosen destinations.
Refused bids and WAIT decisions are not charged as growth.

However, **waiting for useful light is not yet a demonstrated fix**. Five of
the six first-day survivors—13, 16, 20, 21 and 22—also spend their entire initial
energy on shoots and upkeep before their first recorded income. Their first
income arrives 300–525 ticks after the global sky first permits it, and they
recover. Seedling 29 instead earns at the first possible step, retaining 18
energy. Thus low-light extension can be either an unsuccessful expenditure or
a necessary climb out of shade. A blanket growth veto could remove successful
escapes. These traces do not establish the counterfactual outcome of waiting.

## The flower loses both illumination and renewal opportunities

Flower 5 remains at 36 nodes, 20 roots, eight leaves and zero growth tips in
both arms. Its maintenance rate is five energy and two water per 60 logic
ticks. There is no growth expense or body-size threshold crossing.

| Matched window / arm | Initial energy | Gross income | Overflow | Paid upkeep | Renewal | Seeds | Last live energy |
|---|---:|---:|---:|---:|---:|---:|---:|
| Penultimate day, control | 66 | 644 | 287 | 320 | 36 | 0 | 67 |
| Penultimate day, two-column | 26 | 514 | 134 | 320 | 18 | 48 | 20 |
| Final day, control | 67 | 732 | 339 | 320 | 36 | 48 | 56 |
| Final day, two-column | 20 | 280 | 0 | 282 | 18 | 0 | 0 |

The windows are `(206520,210360]` and `(210360,214200]`. The candidate's final
budget stops at 214,185; its terminal step at 214,200 is unknown, while the
control remains live. Candidate upkeep demand over those 255 live steps is
315, of which 33 is unpaid. The comparison has all 107 bright-sky leaf samples
in each arm; only the candidate's final low-light terminal sample is missing.

In the final window, matching leaf sites/times have lower candidate light on
47 of 107 bright-sky samples, higher on nine, and equal on 51. The summed light
bands fall from 114 to 65; summed sampled conditions fall from 20,833 to 14,129.
These are sample totals, not full-canopy attribution. A changing canopy and
condition both contribute to the measured income difference; no single neighbor
is identified as its cause.

The selective renewal policy needs condition at most 128, light at least 128,
and at least **137 energy / 85 water** for this body. Of 14 final-day samples
that meet the condition/light tests, 12 lack energy. The other two propose
renewal and succeed; no proposal is rejected by the spending guard. The control
has four such samples and renews all four. The candidate buys no seed that day,
although the prior window includes a 48-energy seed expense.

The final failure is eight consecutive energy-shortage maintenance checkpoints
from 213,780 through 214,200. Water does not cause any of them; the last live
water store is 512. This is consistent with a dimmer-canopy / worsening-leaf
condition feedback, not proof that an isolated renewal-rule change rescues it.
Daily summaries and the exact paired final shortage sequence are in the JSON.

## Next experiment to discuss

Test one bounded **partial canopy-transmission** change: preserve night's
zero production, existing resource fees, weather, spacing, storage and frozen
controllers, while testing whether dense daytime shade leaves a viable route
to light. Define the integer rule and basic single-/stacked-leaf light fixtures
before collecting a matched A/B; do not tune several opacity values to this
world's result. Score full-day establishment, continuing descendant reproduction
and adult/species losses, not births alone. Wider validation remains necessary.

This is a proposal, not an implemented light change. The current solver uses
additive shade reductions clamped at the same 24-unit floor as night; simply
turning that floor into energy would also produce energy at night. Greater
initial reserves, a blanket shade-growth veto or a new training campaign are
not conclusions supported by this audit.

## Reproduction and provenance

```sh
python3 -W error sim/garden_renewal_establishment_light.py \
  --check benchmarks/garden-longevity/renewal-establishment-light-summary.json

docker compose run --rm --no-deps firmware python3 -W error \
  sim/garden_renewal_establishment_light.py \
  --check benchmarks/garden-longevity/renewal-establishment-light-summary.json
```

The runner verifies the parent's complete manifest, capture inventory, source/
binary/model receipts, exact old reanalysis and six portable images. It then
performs the new audit twice and checks unchanged inputs. All historical Python
and native files must match; CMake is permitted only the exact new shared Python
test registration, checked against its archived bytes. The initial registration
at EOF was skipped by the experimental build's early return; it was moved before
that return and the numerical audit was regenerated without changing formulas
or observations. The initial export is retained locally as a draft.

The new audit checks **15,390 seedling live budgets** and **19,343 flower live
budgets**, retaining 16 seedling deaths and one flower death without terminal
debits. The parent separately reproduces its 231,407 live-budget checks.
All findings are one selected host-world diagnosis, not a performance benchmark,
firmware qualification, broad ecological result or reason to resume training.

Validation: 17 new offline unit cases pass, including fractional carry,
pre-uptake wear, gross income versus storage, partial leaf observations,
uncommitted bids, winner tie order, terminal accounting, matched leaf sites and
the exact allowed CMake delta. Full Docker CTest runs pass **87/87 default** and
**89/89 experimental**, with the new test registered in both. These are
regression/smoke tests, not additional experimental captures or a training search.
Repeated host analysis and an independent Docker `--check` reproduce the full
portable summary exactly, including the original parent reanalysis. The shared
test-registration correction changes source fingerprints only; its initial and
final numerical audit results are identical.
