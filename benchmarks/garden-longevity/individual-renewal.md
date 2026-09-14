# Individual continuity: remove the pooled timing benefit, expose remaining tradeoffs

Taking each garden's weakest period **before** combining worlds removes the
previous benefit from noncoincident slumps. On the unchanged review histories,
the broad final goes from a 26.24% pooled-minimum advantage to a **16.76%
individual-minimum deficit** versus original. It loses on both schedules and
under all four blocked seed omissions. Its three individual-world wins and five
losses remain identical: only group aggregation changed.

This candidate better represents individual continuity, but it is **not a
guarantee that every garden renews**. A sufficiently productive garden can still
compensate for another world's zero minimum. That limitation is explicitly
demonstrated below; no hard gate was silently added.

[Frozen protocol](individual-renewal-protocol.md) ·
[Portable comparisons, world minima and arithmetic challenges](individual-renewal-summary.json)

## Unchanged inputs, one aggregation change

The [sustained-renewal bundle](sustained-renewal.md) supplies the same 128 verified
world-period cases: four controllers × eight review conditions × four consecutive
32-day periods, (62,94], (94,126], (126,158], (158,190]. Two-day follow-up,
32-day bounded-age credit, ancestry and original survival tiers are unchanged.
The already inspected review panel is not a new final-test set.

The new key maximizes:

1. Minimum terminal tier across every world-period endpoint.
2. Sum of those tiers.
3. Sum of each world's minimum credited ticks across the four periods.
4. Total credited ticks over all worlds and periods.

Equal keys remain ties. Equal world counts make integer sums equivalent to
averages for ranking. The old third component took the minimum *after* summing
worlds. This is the only selector change; no credit, population, diversity or
failure threshold was added. **No new native worlds, training or screenshots.**

## Fixed panel results

All controllers retain the same survival prefix `[1,32]`. Tick values below sum
plant occupancy, not CPU time. Different world minima may occur in different
periods; the new component deliberately retains those weak periods individually.

| Controller / CRC | Old pooled minimum | Sum of individual minima | Difference vs original under new rule | Worlds with a zero minimum |
|---|---:|---:|---:|---:|
| Original `dc5e849d` | 1,779,285 | 1,635,480 | — | 0 / 8 |
| Broad G2 `556a5dd2` | 2,186,640 | 1,605,690 | −1.82% | 0 / 8 |
| Narrow final `449c35fe` | 2,172,795 | 1,551,855 | −5.11% | 0 / 8 |
| Broad final `c7c1b31e` | 2,246,100 | 1,361,415 | −16.76% | 2 / 8 |

This reverses the previous pooled ranking (broad final, G2, narrow, original).
It does not undo real total productivity: broad final still has 9,771,510 total
credit ticks versus original's 8,686,710. The candidate deliberately puts each
garden's weak-period behavior before that total.

| Candidate / control | New minimum-component change | Individual wins / losses | Fresh-1 / fresh-2 direction | Blocked omissions retaining overall direction |
|---|---:|---:|---|---:|
| G2 / original | −1.82% | 4 / 4 | − / + | 2 / 4 |
| Narrow / original | −5.11% | 3 / 5 | − / + | 3 / 4 |
| Broad / original | −16.76% | 3 / 5 | − / − | 4 / 4 |
| Broad / narrow | −12.27% | 3 / 5 | − / − | 4 / 4 |
| Broad / G2 | −15.21% | 3 / 5 | − / − | 4 / 4 |

There are no paired ties. Each blocked omission removes both schedules for one
world seed. G2 and narrow remain close enough to original that their comparison
changes under some omissions. Do not read this panel as proving a universal
ranking or choose a model from it for promotion.

## Where the broad/original reversal comes from

For each panel, the old pooled minimum is at least as large as the sum of
individual minima. Call the difference the pooling gap. The gaps are:

| Controller | Pooling gap, ticks |
|---|---:|
| Original | 143,805 |
| G2 | 580,950 |
| Narrow final | 620,940 |
| Broad final | 884,685 |

The broad/original old margin **+466,815**, less the gap difference **740,880**,
equals the new margin **−274,065** exactly. This is removal of an aggregation
benefit, not newly lost plant lifetime or a changed native trajectory.

The same new margin is the sum of these matched per-world minimum differences:

| Condition | Broad minus original minimum ticks |
|---|---:|
| fresh-1 / `eb300b12` | −218,250 |
| fresh-1 / `1824c139` | −33,165 |
| fresh-1 / `4d5f9ee1` | +26,025 |
| fresh-1 / `fe1dd56f` | +45,090 |
| fresh-2 / `eb300b12` | +11,055 |
| fresh-2 / `1824c139` | −57,390 |
| fresh-2 / `4d5f9ee1` | −38,850 |
| fresh-2 / `fe1dd56f` | −8,580 |
| **Total** | **−274,065** |

The two zero-minimum worlds are not the whole explanation: the largest single
loss is the nonzero fresh-1 `eb300b12` minimum. The zeros still refer to absent
qualifying renewal during (62,94], not extinction or necessarily zero births.
No resource cause is inferred from this credit accounting.

New minimum sums and total credit add exactly across disjoint schedule panels.
With tied survival tiers, losses on both schedules cannot turn into a win when
combined under this rule. The earlier narrow/original pooling paradox is absent:
under the new aggregation narrow loses fresh-1, narrowly wins fresh-2, and loses
overall. These schedule results changed too, because each schedule also combines
four gardens whose weakest periods need not coincide.

## Constructed challenges: improvement and a remaining limitation

All ten prior synthetic histories retain their exact single-world keys, including
steady-over-burst, sterile survival, and recovered/unconfirmed/extinct follow-up.
They are constructed arithmetic cases, not native reachable-world claims.

For the two complementary-slump gardens, the old continuity component was
122,880 ticks. The new component is **zero**, correctly reflecting that each
garden has zero-credit periods; their unchanged total is 491,520 ticks.

The one additional declared challenge compares a threefold replacement garden
plus a sterile garden against two ordinary steady-replacement gardens:

| Synthetic panel | Sum of individual minima | Total credit | Zero-minimum gardens |
|---|---:|---:|---:|
| Threefold replacement + sterile | 357,120 | 1,463,040 | 1 / 2 |
| Steady replacement + steady replacement | 238,110 | 975,390 | 0 / 2 |

The first panel still wins. Moving the minimum inside each world prevents
different *times* from compensating for one another within that world's score;
it does not prevent a larger minimum in another *world* from compensating for a
zero. This distinction is visible without choosing any new threshold or gate.

## Decision still to make

This is a more direct candidate for rewarding individual weak-period performance.
Before installing it as training fitness, decide whether a full-period renewal
gap should merely lower a score or fail a separate reliability requirement.
The current rule permits cross-world tradeoffs. A hard or prioritized continuity
requirement would change that behavior and needs its own explicit design,
including seed-bank recovery and legitimate bursty/seasonal reproduction.

No additional aggregation, gate, threshold sweep or training run was tested here.
The evidence remains diagnostic; original primary results, ecology, weights,
native executables and device state are unchanged. Non-overlapping periods still
share trajectories rather than being independent replicates.

## Verification and reproduction

**14 new unit tests and eight relevant pure-Python CTests pass.** Checks include
all ten inherited synthetic scores, the new compensation example, numeric and
credit-ledger consistency, complete contracts/panels, tied minima, input
preservation, world-order invariance, single-world identity, exact paired delta
attribution, disjoint schedule additivity and blocked omissions. The previous
sustained bundle was fully reverified before copying its score ledger.

The new analysis reproduces all previous aggregate views and previous pooled
comparisons, and every individual pair remains identical. All 128 credited
world-period inputs are unchanged. The new verifier checks aggregation from the
fingerprinted prior score ledger; original lifetime/source verification remains
anchored in that prior bundle. No native regression simulations were rerun.

Aggregation plus deterministic repeat: **0.161 seconds**, excluding initial
baseline verification/copying and final verification. Eight artifact files,
**5.62 MiB**, including copied prior results and a source snapshot. Manifest SHA-256:
`6e38dc4d155c405afed717ae8f62a609995d7cc03999c73c2d9ae50b5f47b06e`.

```sh
# Requires the frozen sustained-renewal bundle; uses a fresh artifacts directory.
python3 -W error sim/garden_individual_renewal.py \
  --output artifacts/NEW-individual-renewal

# Recompute and verify this analysis and the portable export, without native runs.
python3 -W error sim/garden_individual_renewal.py \
  --output artifacts/garden-individual-renewal-v1 --verify \
  --check-export benchmarks/garden-longevity/individual-renewal-summary.json

# Verify original sampled lifetime credit in the prior bundle too.
python3 -W error sim/garden_sustained_renewal.py \
  --output artifacts/garden-sustained-renewal-v1 --verify
```

`--baseline` can locate the same fingerprinted source elsewhere. Add
`--verify --export NEW_JSON` to create another portable export; existing files
are never overwritten. Only the previous [day-192 gallery](training-coverage-gallery.md)
is available; no earlier-period images are implied.
