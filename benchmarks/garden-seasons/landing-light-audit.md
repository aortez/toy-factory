# Daylight income audit: dim light, shade and dawn

The remaining plant's final 57-energy forecast error has a concrete explanation:
**50 energy is credited during an interval when even unshaded leaves cannot
photosynthesize**. The other 7 is the error over the brighter interval. This is
exact accounting of the existing heuristic, not a simulated intervention.

One predeclared daylight-aware estimate reduces that final error to 4. Across
all afternoon purchases, however, it becomes more conservative rather than more
accurate overall: mean absolute income error increases from 40.9 to 52.8. It
would also reject one purchase on a surviving trajectory. Test its effect on
spending and survival before adopting it; no rule is changed here.

## Scope and accounting

This follows the [continuous protection comparison](landing-continuous-energy.md)
and its complete saved focal histories. The [prospective protocol](landing-light-audit-protocol.md)
fixes the input, accounting, one diagnostic formula and zero-simulation budget.
The original input checker passes before analysis. No new training, replay,
screenshot, firmware or policy change is involved.

| Coverage | Raw histories | After exact physical-history deduplication |
| --- | ---: | ---: |
| Focal histories | 10 | 6 |
| Ecology samples | 49,152 | 25,091 |
| Paid daylight actions, including FINISH | 298 | 178 |
| Paid night actions | 2 | 2 |
| Dawn windows | 191 | 97 |

Four control/candidate pairs are physically identical after removing only the
energy gates' scope and eligibility annotations. Both distinct rotating-49
histories remain. Deduplication uses the complete lifetime and history, not just
the final state. These histories share worlds and their purchase-to-sunset
windows overlap; neither raw nor deduplicated events are independent trials.

Every sample's energy and water transfers reconcile. All 178 distinct daylight
purchases reach a living sunset in the recorded history; their later nights may
end in death. The two night purchases belong to rotating-49/control after its
guard expires, at ticks 911055 and 911085, costing 9 energy each. They are kept
separate from the daytime forecast, which supplies no night income projection.

Four distinct histories survive to world day 256; rotating 49 dies at age
1.4453125 days in control and 2.5703125 with continuous protection. All focal
plants produce zero seeds. End-of-capture survival is not indefinite survival
or evidence of a reproducing population.

## Why the light threshold matters

In the captured default implementation, each mature leaf independently earns
`floor(local_light / 64)` energy. Ambient light is 24. Consequently, daylight
can be visibly present yet yield no energy. If global unshaded strength is below
64, shading cannot make a leaf productive.

The audit reproduces recorded global strength from phase and seasonal light
percentage using the captured integer arithmetic. Each living, nonbirth sample
also satisfies the instantaneous bound
`income <= active_leaves * floor(global_strength / 64)`.
The relevant light, world, observation, trace and forecast source hashes are
pinned in the results, with leaf-maintenance and canopy-transmission experiments
off. Maturation precedes uptake; new growth is immature and FINISH does not
remove leaves. Birth has no uptake, and terminal samples are excluded from the
leaf-count bound because death changes growth progress after uptake.

### Final purchase in rotating 49

At tick 914415, phase 97, continuous protection allows a root purchase taking
the plant from 31 to 32 nodes. Current income is 5; eight leaves are mature.
The forecast credits half of that income over 30 future pre-sunset samples:
`floor(5 * 30 / 2) = 75`.

| Remaining interval | Samples | Assigned heuristic credit | Actual income |
| --- | ---: | ---: | ---: |
| Globally productive, phases 98–107 | 10 | 25 | 18 |
| Globally unproductive, phases 108–127 | 20 | 50 | 0 |
| Total | 30 | 75 | 18 |

Thus `75 - 18 = 50 + 7`. General events retain this partition in half-energy
units, including the integer-rounding correction. It partitions the aggregate
heuristic; it does not claim that the original code predicts each step's income.

No subsequent growth, reproduction, overflow, discard or upkeep error affects
this purchase-to-sunset window. Energy after purchase is 86; another 18 arrives
and 32 pays upkeep, leaving 72 at sunset. The forecast predicts 129, just over
the nominal 128 needed for the night. The plant dies during that night.

The eight-leaf count stays constant through sunset. Seasonal light percentage
rises from 52 to 55 while the sun sets, and the quantized ray direction changes
six times. Summing the *actual body's instantaneous unshaded bounds* gives 80
energy versus 18 received, a 62-energy attenuation gap. That is a different
comparison from the 57-energy forecast error; do not add the two. It is not a
no-shade simulation: different income could have changed growth and later shade.
The saved trace has no individual leaf positions, local light or occluder IDs,
so it cannot separate self-shade from neighbors or reconstruct a fixed-canopy
raycast. The 7-energy remainder is not assigned to one unobserved mechanism.

## One current-observation-only diagnostic

For noon/afternoon purchases, estimate future global strength using the known
daily sun curve and the current observed attenuation. Keep the original
half-current-income factor, but count only future steps estimated to reach 64.
Morning arithmetic, prices, upkeep, caps and nominal night requirement remain
unchanged. The function accepts only current phase, global strength and income;
future weather, leaf counts and realized income are used only for evaluation.

For the final purchase it estimates nine productive samples, credits 22 and
predicts 76 at sunset. The observed values are ten productive samples, 18 income
and 72 at sunset. Holding attenuation fixed misses the small seasonal improvement
that allows the tenth productive sample. The diagnostic rejects this purchase
because 76 cannot fund the nominal 128-energy night.

Across the 116 distinct noon/afternoon purchases:

| Income forecast measure | Original | Diagnostic |
| --- | ---: | ---: |
| Overestimates | 65 | 5 |
| Largest overestimate | 79 | 7 |
| Mean absolute error | 40.9 | 52.8 |
| Largest underestimate | 187 | 265 |

Absolute error gets smaller for 39 purchases, larger for 66 and stays equal for
11. The diagnostic underestimates 104 windows and exactly matches 7. Only eight
afternoon windows are clean of later spending, overflow, discard and shortages;
their mean absolute error changes from 9.0 to 7.875. Of those eight, just one
improves, four worsen and three stay equal. The 62 distinct morning purchases
are unchanged. All individual errors and changing-leaf counts remain available;
the audit does not select only the favorable examples.

The diagnostic newly rejects ten nonbirth purchases the original forecast
permits: eight in rotating-49/candidate, one in its unguarded control and one in
surviving rotating 50. Nine fall within an actually active gate; birth exemptions
and inactive gates are recorded separately. A rejection on a saved state is
neither a demonstrated rescue nor a demonstrated regression.

The surviving counterexample matters. At tick 910170, phase 70, rotating 50 buys
its twentieth node, another root. Current income is 5; old credit is 142 and new
credit is 97, but actual future income is **300**. The new projected sunset is
84, below the nominal 96-night requirement, so it would reject the purchase.
The recorded plant actually ends that day with 161 despite another 117 spent on
growth and 54 on upkeep, and it survives the next night. Its mature-leaf count
also remains eight. Current income is not a stable predictor of future income
even without an increasing mature-leaf count. Whether delaying this root helps,
harms or has no lasting effect needs a replay.

## Dawn is a separate reserve gap

Of 97 distinct dawn windows, one has upkeep shortages before the first positive
income: rotating-49/candidate at tick 912960. The previous sunset's 128 energy
pays the night exactly and leaves zero at dawn.

The next five maintenance payments, at ticks 913020 through 913260 every 60
ticks, require 20 energy in total and receive none. Global strength first reaches
64 at tick 913290, phase 22, when the plant receives its first 1 energy. The
window records that first income explicitly rather than treating dawn as useful
light. A sixth shortage occurs afterward at tick 913320, as documented in the
[original continuous comparison](landing-continuous-energy.md), before recovery.

This does not by itself explain the later third-night death. It does show that
funding the nominal sunset-to-dawn interval is not the same as funding the entire
unproductive-light interval. The audit separates maintenance due, paid, unpaid
and terminal discard; future missing observations never become invented zeros.

## Next bounded experiment

Test the predeclared afternoon correction as a **spending guard**, not as a
promoted income model. Keep the continuous-energy scope, root treatment,
maintenance-increase check, morning behavior and dawn requirement unchanged.
Use the same five paired cases, historical controls, exact repeats and complete
focal/population ledgers. In particular, retain rotating 50 as the explicit
successful-growth risk check and keep seed production in the outcomes.

That isolates whether removing credit during unproductive late light improves
survival without sacrificing the four existing survivors. Do not simultaneously
add a dawn buffer or tune the half-income factor: those would confound the
result. The dawn funding gap is recorded as a subsequent question. No new
counterfactual or device deployment is performed in this audit.

The subsequent [paired daylight comparison](landing-daylight.md) now completes
this proposal in forty fixed calls. The last failure survives through day 256,
all four previous survivors remain alive, and the risky root is delayed by two
ecology steps. Focal reproduction is still zero and dawn shortages remain;
the report retains altered morphology and population tradeoffs. This does not
retroactively make the diagnostic an unbiased income predictor.

## Evidence and reproduction

`make host-audit-landing-light` writes a fresh bundle; set
`GARDEN_LANDING_LIGHT_AUDIT_OUT=artifacts/new-light-audit` to repeat it. It needs
the saved portable input, not a native build or the original large trace bundle.

```sh
docker compose run --rm -T firmware python3 sim/garden_landing_light_audit.py \
  --verify benchmarks/garden-seasons/landing-light-audit-results.json.gz
docker compose run --rm -T firmware python3 sim/garden_landing_light_audit.py \
  --verify artifacts/garden-landing-light-audit-v1
```

| Artifact | SHA-256 |
| --- | --- |
| [Portable audit](landing-light-audit-results.json.gz) | `80d7c070d41bf0d7c6d6836e342d830fe98b9436cc82ba09a5231bf0f9c5975b` |
| Raw manifest | `d0cf37fe2877aff1a03cf7706d337dd34ab0ed81356f77168ae05900c7f8ffc6` |
| Protocol | `4782adf1d33a02d9eaa8212fe72879d8515c5209598a6fd1d91ac5a61928f223` |
| Frozen input | `143cfbb3a1064cadbe0b46b8c0907684928e7e2dc7e54b0a0502324648c3d1b5` |

Both exports use the same unchanged source and produce byte-identical portable
results. The bundle retains the export-time source archive and patch; this report
and the final artifact checksum assertion were added after capture. Verification
recomputes the complete audit from the pinned input, including balances, light
thresholds, all decisions, dawn receipts, errors and duplicate accounting.

All 18 light-audit tests and 16 existing energy-audit tests pass, with no skips,
as two focused CTest entries. They cover integer boundaries, current-only inputs,
birth/death exclusions, combined arbitration, censored endpoints, dawn payments,
successful-growth risks, source/build restrictions, corruption and no-clobber
exports. Native execution is forbidden in the offline tests. Raw and portable
verification pass. The complete native suite was not rerun for this Python-only
audit; its previous 178-test result belongs to the continuous comparison.
