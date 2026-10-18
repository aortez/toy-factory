# Winter energy loss and blocked shrub recruitment

The first additional Search 1 shrub-family loss has two distinct bottlenecks.
Its last living plants run out of winter energy as leaf condition deteriorates;
its two remaining seeds never pass the spacing check before expiring. Increasing
seed lifetime or reducing repair spending is not yet a supported fix.

All six [planned replays](leaf-population-trace-protocol.md) completed in
25.623 seconds. Traced and untraced runs match complete state, history, and
pixels at days 0, 32, 192, and 256. The earlier checkpoints also match the
original population archive exactly, and all histories match its prefixes.
No ecology, model, training objective, or firmware default changed.

## The founder loses energy without spending on repairs

The matched case is founder 2, a shrub at column 13, under weather `58d7d6ca`
in the rainfed layout. All three versions of this founder have 32 body nodes
and 21 leaves during the final winter comparison.

| Founder measurement | Fixed wear | Search 1 | Search 2 |
|---|---:|---:|---:|
| Repairs during days 216 to 222 | 38 | 22 | 23 |
| Total leaf condition at day 222 | 811 | 448 | 508 |
| Stored energy at day 222 | 133 | 98 | 102 |
| Founder dies by day 256 | No | Day 222.72 | Day 222.75 |
| Living family members at day 256 | 2 | 0 | 3 |

The repair window is `(216,222]`; condition is summed across the 21 leaves,
each with a maximum of 255. Search 1 makes its last repairs in the preceding
`(219,220]` interval. It makes no repair proposals in the next two full days
or on its fatal partial day.

From day 222 until its death at day 222.71875, Search 1 starts with 98 energy
and earns 55. Upkeep demands 184, but it can pay only 153. There is no
construction, seed spending, repair spending, or saturation loss in this
interval. Eight maintenance steps have an energy shortage; water upkeep is
fully paid, and 509 water units are discarded at death. This is an energy
deficit, not repair spending exhausting reserves on the final day.

The control enters this interval with better leaf condition and more energy,
makes five repairs during `(222,223]`, and survives. Search 2's original founder
also dies, but other descendants preserve its family. Founder survival and
family renewal are therefore different outcomes even within this one case.

Earlier in the year, all three founders discard substantial energy at the
storage ceiling. Search 1's combination of fewer late repairs, declining leaf
condition, and lower winter income makes repair timing worth investigating.
The surrounding populations differ too, so these comparisons do not isolate
controller decisions from shading or other ecological feedback. The trace
does not prove that forcing extra repairs would prevent the loss.

## Both final seeds are blocked throughout their lifetimes

The last Search 1 shrub dies at day 222.71875. Two family seeds remain, one at
column 15 and one at column 19. They expire at days 224.96875 and 225.1875,
respectively. Each has 8191 actual germination checks; the final expiry step
happens before checks and is excluded.

| Checks with blocker present | Seed at column 15 | Seed at column 19 |
|---|---:|---:|
| Spacing | 8191 | 8191 |
| Plant capacity | 8126 | 8126 |
| Node capacity | 7885 | 7885 |
| Light | 7300 | 7348 |
| Moisture | 1063 | 1088 |
| Cold | 1051 | 1051 |
| Dormancy | 7 | 7 |

Blockers overlap; these rows are not disjoint outcomes. Spacing is the only
blocker that never clears. After the last living family member dies, there
are 42 checks at column 15 and 39 at column 19 where spacing is the sole
remaining blocker. Moisture blocks neither seed during that seed-only period;
cold blocks only its first 31 checks per seed.

The column-19 seed is within two columns of a living ground-cover competitor
at column 21 throughout its checked lifetime. The frozen spacing rule requires
three columns and includes undecomposed dead bodies as well as living plants.
The column-15 neighborhood changes around the winter deaths, so its exact
blocking occupants require a more detailed inventory than these mask counts.

By contrast, the control's seed at column 6 eventually gets one unblocked
check and germinates at day 223.07421875 after 7658 blocked checks. Its offspring
reaches the 32-day establishment milestone just before the end of this trace.
Recruitment depends on a usable opening, not simply having a seed in reserve.

## What to investigate next

Keep both bottlenecks visible, but first inspect the winter repair decisions
under identical observations. A read-only comparison can record the actual
leaf observations and ask all three frozen controllers what they would do,
without applying the alternative decisions. That would separate policy
differences from the fact that their live gardens have already diverged.

This should test whether Search 1 waits when fixed wear would renew a leaf,
and whether those disagreements coincide with low light, declining energy,
or particular leaf conditions. It can guide a later bounded intervention; it
cannot establish that the alternative action would rescue the family.
Seed-placement opportunity is a separate follow-up. Neither a diversity penalty
nor an ecological rule change follows automatically from this single case.

## Evidence and verification

The compact evidence archive (`leaf-population-trace-results.json.gz`, kept
locally) retains all six process receipts, 24 captures with complete state,
three traces, the collection-time sources and protocol, and preflight results.
The traces contain 289, 332, and 700 plant/day rows and 15, 12, and 36 attempted
seeds for fixed wear, Search 1, and Search 2. None reaches a storage bound.

The offline verifier checks every plant/day and seed against lifetime history,
balances energy, water, and leaf condition, checks seed outcome counts, and
reconciles daily histograms with per-seed histograms. Lifetime intervals also
independently bound the no-living-family subsets, allowing ambiguity only at
same-tick births. This additional verification was added after collection;
the recorded sources and results remain unchanged.

Seven host session/viewer suites and ten preparation tests passed before the
six experiment calls. The final population analysis suite includes 36 tests,
including archive round-trip, no-native-execution, and tamper rejection checks.

```sh
python3 -B sim/experiments/leaf_population/population_trace.py unpack \
  benchmarks/garden-seasons/leaf-population-trace-results.json.gz \
  artifacts/garden-population-trace-review-v1
python3 -B sim/experiments/leaf_population/population_trace.py verify \
  artifacts/garden-population-trace-review-v1
```

Use a fresh output directory. Archive SHA256:
`b85e6ac58ee50462a4c025a1c3adb09c496b3f1ac7aa569b27d719737eb40178`.
