# Restoring the light gate preserves the shrub through winter

Restoring Search 1's light gate to the fixed-wear gate prevents the selected
founder's death through day 256. Restoring its condition gate alone does not.
Restoring both gates also preserves an existing descendant and eliminates the
founder's energy-shortage steps during the tested winter. None of the arms
produces new shrub offspring after the intervention, so this is evidence for
survival, not yet for continued generational renewal.

All eight [planned calls](leaf-population-gates-protocol.md) completed in
28.051 seconds. The unchanged arm reproduces the archived control. Traced and
untraced pairs match complete state, history, and pixels; all four arms share
the same underlying trajectory through day 208. Frozen sources, original model
files, ecological rules, and firmware remain unchanged.

## A scheduled change within one family

The case is shrub founder 2 in the rainfed layout with weather seed `58d7d6ca`.
Every plant uses Search 1 through day 208. After that point, only this founder
family uses the assigned variant; competitors continue using Search 1. The
intervention remains active through day 256.

The variants copy the light-related hidden unit, the condition/energy-related
hidden unit, or both from fixed wear into a private Search 1 model. All other
weights and costs stay unchanged. This applies actual decisions, unlike the
earlier [read-only comparison](leaf-population-shadow.md). The combined variant
makes the same decisions as fixed wear, but only in this family after the
switch; it is not the earlier whole-population fixed-wear trajectory.

## More repairs alone do not explain the outcome

| Measurement | Unchanged | Light restored | Condition restored | Both restored |
|---|---:|---:|---:|---:|
| Founder repairs during `(208,220]` | 75 | 87 | 98 | 116 |
| Founder energy at day 222 | 98 | 118 | 108 | 130 |
| Founder leaf condition sum at day 222 | 448 | 636 | 563 | 811 |
| Founder death day by endpoint | 222.71875 | Alive at 256 | 222.796875 | Alive at 256 |
| Living shrub-family members at day 256 | 0 | 1 | 0 | 2 |
| New shrub offspring after day 208 | 0 | 0 | 0 | 0 |

All founders have 32 nodes and 21 mature leaves at the day-222 comparison.
Each leaf's condition ranges from 0 to 255. The light-only variant makes fewer
pre-winter repairs than the condition-only variant, yet maintains better foliage
and survives. Counting repairs or read-only disagreements alone would miss this
distinction: which opportunities a controller accepts matters.

During `(208,220]`, all founders pay the same 3072 energy upkeep. Energy income
is 13429, 14098, 13678, and 14419, respectively; repair spending is 675, 783, 882,
and 1044. All finish that interval with 252 stored energy and discard more than
9600 energy at the storage ceiling. The interventions do not simply accumulate
a larger reserve before winter. They change the condition of the foliage that
must continue earning energy as light deteriorates.

During `(220,224]`, light-only makes 17 repairs and survives despite six
energy-shortage steps. Both-restored makes 20 repairs and has no energy-shortage
steps. The unchanged and condition-only founders make no repairs during their
remaining winter lives and die after eight shortage steps each. Their windows
end at death, so cumulative winter income or spending cannot be compared as
equal-duration totals.

This establishes a causal effect of the scheduled family intervention in this
deterministic case. It does not establish that this gate is universally better,
or separate the founder's own repairs from feedback through its relatives and
competitors.

## Survival has not reopened recruitment

The combined variant keeps lineage 14 alive as well as the founder. That child
was born at day 175.078125 and was already established before the switch.
Light-only preserves the founder but loses lineage 14 at day 222.84375.
Both surviving arms end with two pending family seeds, but neither produces a
new shrub during the 48-day follow-up.

Unchanged and condition-only families become extinct at day 225.1875 when their
last seed expires. The slightly later founder death in condition-only does not
change that family outcome. Preserving an old stand is not equivalent to meeting
the project's renewal-first objective.

Other families remain present in every arm. At day 256, flower/shrub/ground-cover
living counts are 3/0/5, 3/1/4, 3/0/5, and 2/2/4. Every garden occupies eight
living slots. Better shrub survival therefore redistributes limited space rather
than increasing final population size. The full evidence retains births, deaths,
establishment, and seed outcomes for all three families.

## Next step

Follow these same four scheduled arms for longer before considering a broader
policy change. A day-608 endpoint would test additional winters and provide time
for new descendants to establish. Retain the day-256 anchor and distinguish
continued founder survival, seed-only intervals, extinction, and actual new
generational renewal. The subsequent
[day-608 follow-up](leaf-population-gates-long.md) now reports those outcomes;
this archive remains the original day-256 evidence.

The frozen whole-population study still provides the broader context: learned
repair improved renewal while losing more families. A rescue of one selected
failure case is a diagnostic result, not grounds to promote a new controller
or change the training objective.

## Evidence and validation

The 483 KiB evidence archive (`leaf-population-gates-results.json.gz`, kept
locally) retains eight receipts, 64 captures, four resource/seed traces, the
prospectively fixed protocol, source snapshots, exact derived models, and
preflight results. The collection had no failures or retries.

Intervention records use `garden-leaf-gate-replay-v1` and `TGR1`. Their identity
includes the variant, selected founder, activation tick, and complete derived
model bytes before the underlying population state. The offline verifier checks
that identity before comparing an explicitly stripped projection with ordinary
population records. It never publishes the projection as an intervention's
complete identity.

All seven host session/viewer suites passed in 93.84 seconds before collection,
along with ten preparation tests. Tests cover exact model derivation, routing
at the switch boundary, unrelated families, descendants, missing/decomposed
parents, allocation and callback failures, reset, output preservation, and
ordinary replay compatibility. The collected traces pass complete resource and
leaf conservation checks. Additional post-collection tests verify published
outcomes, archive round-trip, offline-only verification, and tamper rejection.
All 50 population analysis tests pass.

```sh
python3 -B sim/experiments/leaf_population/population_gates.py unpack \
  benchmarks/garden-seasons/leaf-population-gates-results.json.gz \
  artifacts/garden-population-gates-review-v1
python3 -B sim/experiments/leaf_population/population_gates.py verify \
  artifacts/garden-population-gates-review-v1
```

Use a fresh output directory. Archive SHA256:
`a73a6f20cf420348fe1684ef73ea0ea081e872586c91287a4c7940064d9147a1`.
