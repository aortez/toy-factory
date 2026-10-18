# Dawn exposure explains this missed opening

Original-placement shrub 19 collects 159 energy during the focal dawn;
fewer-blocker shrub 17 collects 84. The original has 1.84 times the summed
usable light bands, while light-weighted leaf condition is almost the same:
46.5% versus 45.8%. Neither plant repairs or grows during this interval.

This refines the [earlier daily comparison](leaf-population-dawn.md). The
original shrub does have healthier foliage overall, but that average includes
leaves receiving no productive light. At this particular dawn, the recorded
exposure difference dominates the income accounting. It is not evidence that
condition is unimportant throughout the day or that changing placement alone
would reproduce this benefit.

## The dawn balance closes exactly

The fixed interval is `(152.75,152.875]` days: sunrise through the focal
seed-bank opening, 32 ecology steps. Both plants experience the same sun
phase and strength at every step.

| Dawn measurement | Original shrub 19 | Fewer-blocker shrub 17 |
|---|---:|---:|
| Leaves | 24 | 26 |
| Energy at sunrise | 113 | 116 |
| Summed light bands, before condition weighting | 341 | 185 |
| Light-weighted condition, fraction of maximum | 46.46% | 45.81% |
| Unweighted mean leaf condition | 46.75% | 29.45% |
| Gross energy income | 159 | 84 |
| Upkeep paid | 32 | 32 |
| Repair, construction, storage overflow | 0 | 0 |
| Energy at the reproduction visit | 240 | 168 |
| Required energy | 208 | 208 |
| Energy after reproduction | 192 | 168 |

The original starts three energy behind, earns 75 more, and reaches the
opening 72 ahead. It then spends 48 on a seed. Its post-purchase 192 is not
the eligibility balance; the visit uses 240. The experimental shrub misses
the threshold by 40. Both have sufficient water, but the original garden has
two open seed slots at this visit versus one in the experimental garden.
These are still different population histories, not a controlled race for
identical openings.

The light-weighted condition is
`sum(band * condition) / (255 * sum(band))`, where `band = light // 64`.
Thus the relevant weighted numerators are 40,397 and 21,613. Including the
carried fractional remainders reconstructs every integer income and its new
remainder exactly. A leaf in light band zero contributes neither energy nor
weight to this measure, even if it is healthy.

The original has 321 leaf-step samples in a productive light band, versus
179 experimentally, with respective band-2 counts of 20 and 6. Its mean
light band per leaf-step is 0.444 versus 0.222. This is not an advantage from
having more leaves; it has fewer.

## The whole day tells a different story

| Calendar day 152 | Original | Fewer-blocker |
|---|---:|---:|
| Summed light bands | 2,329 | 2,322 |
| Light-weighted condition | 62.74% | 53.89% |
| Gross income | 1,462 | 1,252 |
| Storage overflow | 1,023 | 915 |
| Repairs | 15 | 9 |
| Seed purchases | 1 | 0 |
| Energy at day end | 252 | 252 |

Over the complete day, total light-band exposure is nearly equal and the
condition weighting matters more. Both discard substantial income at the
storage cap. Daily productivity therefore hides the time-sensitive shortage:
income later in the day does not retroactively buy a seed at the dawn opening.

The shrubs also differ in position, body shape, age, neighbors, and prior
repair history. The original's leaves occupy light-grid columns 0–2; the
experimental shrub's occupy 7–9. This trace records the light reaching them,
not the identity of each shadow caster. It cannot yet separate boundary
geometry, self-shading, and neighbors. Condition also affects shading, so
the exposure and condition terms are an accounting decomposition, not
independent causal interventions.

## Validation and retained evidence

The [protocol](leaf-population-foliage-protocol.md) fixes four unchanged
day-608 replays: original/fewest placement crossed with diagnostics off/on,
condition-only repair, rainfed weather seed `9a903368`. All four finished in
18.95 seconds after seven host suites passed in 133.86 seconds and all ten
runtime-preparation tests passed.

All 44 checkpoints, four final outputs, and the three existing diagnostics
match the authenticated reproduction archive byte-for-byte, including pixels.
The two new traces contain all 512 expected uptake samples. Each verifies
the per-leaf wear timing, unchanged focal body across compaction, exact
fractional income, six energy payment points, the daily resource ledger,
and every focal reproduction-opening receipt. No kernel patches or simulation
defaults changed.

The host-only collector uses one bounded allocation, no step allocations,
and refuses incomplete or failed traces. It forwards the existing repair
decision unchanged. The ordinary firmware and viewer remain untouched.

The evidence archive (`leaf-population-foliage-results.json.gz`, kept locally)
is 597,673 bytes with SHA-256
`7462461ae0057387c2e5d1cb68fb61ab5b6671f3601640ecd1cac32b51ce5cf2`. It includes
pinned sources/protocol, process receipts, captures, original diagnostics,
foliage traces, and derived summaries. Local collection occupies about 9 MiB at
`artifacts/garden-population-foliage-v1`.

Verify offline in a fresh directory without running a simulator:

```sh
docker compose run --rm -T host-player python3 -B \
  sim/experiments/leaf_population/population_foliage.py unpack \
  benchmarks/garden-seasons/leaf-population-foliage-results.json.gz \
  artifacts/garden-population-foliage-verified-v1
```

Ten focused tests cover scope, missing/duplicate rows, coordinates, compaction,
individual wear hidden by unchanged totals, exact income, payment stages,
independent receipts, weighted versus unweighted condition, and the published
results. Published verification and exact archive repacking forbid subprocess
execution; archived code is never executed.
The final offline analysis suite passes all 146 tests in 44.26 seconds.
Formatting, whitespace, and local documentation links also pass.

## Next: locate the lost morning exposure

The completed [offline spatial map](leaf-population-exposure.md) localizes the
gap to the lower canopy: about 83 versus 7 fractional energy, compared with
nearly equal upper-canopy contributions. Both reduced exposure and worn leaves
matter in that region. The original's leftmost column supplies 75.4% of its
dawn contribution. Next attribute actual shadow sources and boundary crossings
before choosing a growth, placement, or repair intervention. Do not train a
new controller or relax resource rules from this one case.
