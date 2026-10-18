# Light gate restoration preserves shrubs on a second weather seed

Restoring the light gate again keeps the shrub family alive through day 608.
Restoring the condition gate alone does not. However, restoring both gates
does not consistently produce more renewal: light-only scores higher on this
seed, whereas both-restored scored higher in the
[first case](leaf-population-gates-long.md). The survival result repeats; the
ranking of reproductive outcomes does not.

All eight [planned runs](leaf-population-gates-transfer-protocol.md) completed
in 38.760 seconds without failures or retries. Logging-on/off pairs match
complete state, histories, and pixels. All arms share the same trajectory
through day 208, and the unchanged arm reproduces the original archived
population result at day 608.

## Descendants receive the intervention

The rainfed weather seed is `59818bc3`. Its original shrub founder dies at
day 14.765625, long before the intervention. At day 208, only descendants 7
and 18 are alive in that family, with no pending shrub seeds. Ground cover
is already extinct from day 104.109375, leaving flowers and shrubs.

As before, every plant uses Search 1 until day 208. After that point only
family 2 receives the assigned repair variant. The four model derivations,
growth controller and memory, weather rules, costs, spacing, seed lifetime,
and scoring remain unchanged. New offspring inherit the family assignment,
including children of parents that have since died.

## Survival repeats but renewal remains uneven

| Outcome through day 608 | Unchanged | Light restored | Condition restored | Both restored |
|---|---:|---:|---:|---:|
| Living shrub-family members | 0 | 2 | 0 | 2 |
| Family extinction day | 385.9375 | Survives | 386 | Survives |
| New shrubs born after day 208 | 1 | 2 | 1 | 1 |
| New shrubs reaching age 32 | 1 | 2 | 1 | 1 |
| Those new shrubs still alive | 0 | 0 | 0 | 1 |
| Total qualifying renewal children | 2 | 3 | 2 | 2 |
| Qualifying children born after the switch | 1 | 2 | 1 | 1 |
| Renewal credits out of 12 | 2 | 3 | 2 | 2 |

Every credited child and its non-founder parent survives its own first 32
days. All four arms include one credit for lineage 18, born at day 200.9375.
That birth precedes the switch; its age-32 establishment occurs afterward
and succeeds in every arm. It is not a new birth caused by the intervention.
All post-switch offspring have enough follow-up to classify by day 608;
none remains in the young-survivor category.

The six 64-day scoring windows cover births in `(192,576]`, with follow-up
through day 608. Their qualifying counts are:

| Arm | 192 to 256 | 256 to 320 | 320 to 384 | 384 to 448 | 448 to 512 | 512 to 576 |
|---|---:|---:|---:|---:|---:|---:|
| Unchanged | 1 | 1 | 0 | 0 | 0 | 0 |
| Light restored | 2 | 1 | 0 | 0 | 0 | 0 |
| Condition restored | 1 | 1 | 0 | 0 | 0 | 0 |
| Both restored | 1 | 0 | 0 | 0 | 1 | 0 |

Light-only earns `3/12 = 1/4`; the others earn `2/12 = 1/6`. No window exceeds
the two-child cap. These scores describe the existing objective, not a new
survival bonus. Neither surviving arm demonstrates steady replacement across
the interval.

## Which shrubs persist

Light-only preserves both plants present at the switch, lineages 7 and 18.
Its two new children, born at days 254.88671875 and 319.8515625, establish
but later die. At day 608 its living family consists entirely of those two
older plants, despite the higher renewal score.

Both-restored preserves lineage 18 but loses lineage 7 at day 494.828125.
Lineage 18 produces a child at day 511.0546875; that child establishes and
remains alive at day 608. The surviving pair is therefore an old descendant
and a new third-generation descendant, rather than the two original survivors.

Condition-only extends lineage 7's life from day 318.671875 to 366.796875,
but does not save lineage 18 or sustain the family. The unchanged arm's final
child germinates at day 319.05859375, after its parent has died, and lives
until day 366.71875. Its last pending seed then expires at day 385.9375.

The resource trace captures a repeated local distinction. Lineage 18 dies
at day 254.8125 in unchanged and condition-only runs, with eight
energy-shortage steps in the final `(224,256]` reporting window, truncated
at death. It survives through day 256 with zero shortage steps in light-only
and both-restored runs. Detailed resource logging stops there, so later
deaths and recruitment are interpreted from complete life histories, not
unmeasured late resource budgets.

## Comparison with the first seed

In both selected cases, light-only and both-restored retain the shrub family;
unchanged and condition-only lose it. Reproduction is more context-dependent:

| Seed and arm | Post-switch births | Post-switch qualifying renewal children | Living shrubs at day 608 |
|---|---:|---:|---:|
| First seed, light | 1 | 0 | 2 |
| First seed, both | 6 | 2 | 6 |
| Second seed, light | 2 | 2 | 2 |
| Second seed, both | 1 | 1 | 2 |

On this second seed the endpoint flower/shrub/ground-cover counts are 8/0/0
for unchanged and condition-only, and 6/2/0 for both surviving arms. The
interventions prevent a flower-only endpoint. Ground-cover extinction is
shared history from before the switch, not a new treatment effect. In the
first seed, by contrast, ground cover disappeared only in the combined arm.

These are two selected deterministic cases from the existing population
panel, not an unseen random sample. They support testing the light-gate
change more broadly, but do not establish one universally best repair model.

## Next comparison

Test the fixed variants from the beginning across all four archived rainfed
weather seeds, rather than limiting the next test to late rescue. Two of
those seeds have already lost every shrub by day 208 and cannot receive the
current intervention. An earlier-start protocol would include those failures
and test whether the survival benefit holds when growth and competition
diverge from the start.

Predeclare that comparison separately, keep the objective unchanged, and
continue reporting renewal timing, end survival, and competitor outcomes
without blending them into a new score. No additional runs, training, policy
promotion, or firmware changes are included here.

The subsequent [from-start panel](leaf-population-gates-panel.md) completes
this comparison. Light-only leads aggregate renewal, but the survival result
does not hold on every seed, and both-restored performs worse overall than
either single change. Its conditions and evidence are kept separate here.

## Evidence and verification

The 634 KiB archive (`leaf-population-gates-transfer-results.json.gz`, kept
locally) retains eight receipts, 88 state/pixel captures, four resource traces
through day 256, exact model bytes, source and protocol snapshots, binary
digest, and preflight results. The existing trace allocation bounds and day-608
continuation are unchanged. `--gate-transfer` selects only this second case; the
older commands retain their original seed and endpoints.

The collector now shares its bounded execution and archive machinery between
the two day-608 experiments using immutable in-tree recipes. Distinct schemas,
baseline digests, expected command arguments, and seed checks prevent mixing
the cases. Earlier archives still verify and round-trip byte for byte. No
archived source is executed during verification.

All seven replay/viewer preflight suites passed in 91.22 seconds, together
with ten preparation tests. Strict compiler warnings and UBSan remain enabled.
Published-evidence tests check round-trip preservation, wrong-recipe rejection,
shared-prefix credit accounting, resource conservation, and tamper detection.
All 64 population analysis tests pass.

```sh
python3 -B sim/experiments/leaf_population/population_gates_transfer.py unpack \
  benchmarks/garden-seasons/leaf-population-gates-transfer-results.json.gz \
  artifacts/garden-population-gates-transfer-review-v1
python3 -B sim/experiments/leaf_population/population_gates_transfer.py verify \
  artifacts/garden-population-gates-transfer-review-v1
```

Use a fresh output directory. Archive SHA256:
`4c2a1c1522ec0ad696a9214f8b40941f14e3f698d9f5973aed7883b11d5ee175`.
