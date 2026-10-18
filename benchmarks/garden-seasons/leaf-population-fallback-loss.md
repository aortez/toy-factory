# Longer adult survival does not sustain the shrub lineage

The condition-only regression is a replacement-chain failure, not a shorter
life for the first replacement shrubs. With the fewer-blocker placement
fallback, those shrubs live longer and buy more seeds, but their next-generation
child dies before establishing. Later seeds mostly remain spacing-blocked;
the final adult eventually dies with no seeds left.

This is an offline diagnosis of the two condition-only trajectories on weather
seed `9a903368` from the [placement comparison](leaf-population-fallback.md).
It uses the retained resource and germination traces through day 256 and
complete histories through day 608. No new simulations, training, or policy
changes were needed. The fallback remains host-only and opt-in.

## The first adults improve, but their replacement fails

Establishment requires survival to age 32. Seed counts below cover each
plant's complete recorded lifetime, not just the resource-trace window.

| Branch | Original placement | Fewer-blocker fallback |
|---|---|---|
| Shrub 16, born day 63.016 | Dies day 151.844; buys 5 seeds | Dies day 198.188; buys 9 seeds |
| Shrub 17, born day 65.906 | Dies day 126.828; buys 1 seed | Dies day 232.219; buys 2 seeds |
| Next-generation child at column 0 | Lineage 19, born day 95.816; dies day 366.922; buys 17 seeds | Lineage 18, born day 97.938; dies day 126.984; buys no seeds |

The last pair represents corresponding branches, not identical plants with
matched bodies or observations. The experimental child lives only 29.047 days.
During the interval `(126,127]`, it earns 99 energy units, pays 239 of 252
units of upkeep, and has eight energy-shortage steps before death. It performs
no leaf renewals; total leaf condition falls from 679 to 71. It has no water
shortage and discards 508 stored water units at death.

The original branch earns 217 energy units in that interval, pays all 256
units of upkeep, and performs seven renewals costing 63 energy. It survives
and recovers afterward. Its interval includes 256 ecology samples versus 252
before the experimental child's death. These measurements establish an energy
failure, but do not isolate shading, body shape, or particular repair decisions
as its cause.

## Most later seeds never get a spacing opportunity

The experimental shrubs buy 11 seeds in `[63,256)`: two germinate and nine
expire. Eight expired seeds are spacing-blocked on all 8,191 germination
checks in their respective lifetimes. Recorded living plants suffice to
explain each of these eight persistent obstructions:

- Three seeds are blocked by the shrubs' own family. Two target columns 7
  and 8 beside shrub 17 at column 7; another targets column 15 beside shrub
  16 at column 14.
- Five are blocked by ground-cover plants: two at column 22 beside lineage
  9 at column 23, and three at column 20 beside lineage 15 at column 18.

These are proven persistent living blockers, not a reconstruction of the full
stored roster. Retained dead occupants can also block sites. Expiry itself is
not a germination check and is excluded from the 8,191 count.

The ninth expired seed, at column 18, does get 90 spacing-free checks. Every
one is moisture-blocked; 35 also lack sufficient light. It expires at day
223.891, leaving no pending family seed for the final 8.328 days before the
last shrub dies. Original placement produces 21 purchases in the same window:
eight germinations, eleven expirations, and two seeds still pending at the
day-256 trace boundary.

## The seed bank is congested, but eligibility remains unobserved

The authenticated frozen maintenance profile has **eight seed slots**, not
the larger limits used by other experiment profiles or player buffers.
Reproduction is automatic; it is not a seed-buying action chosen by the
growth network. Its checks include cooldown, cadence, capacity, stress,
daylight, generation, resource thresholds, and flower readiness.

During `(128,232]`, all 6,625 reproduction-cadence ticks without a seed event
have all eight slots occupied in the experimental run. Another 31 cadence
ticks contain a purchase, expiry, or germination; final histories cannot
establish which plants saw an opening first within those ticks. The original
bank is almost always full too: 6,608 of 6,623 non-event cadence samples.

Actual purchases in this window differ:

| Family | Original placement | Fewer-blocker fallback |
|---|---:|---:|
| Flowers | 8 | 12 |
| Shrubs | 12 | 3 |
| Ground cover | 10 | 15 |

All three experimental shrub purchases belong to shrub 16. Shrub 17 buys
nothing after day 127.109 despite surviving to day 232.219. It has at least
200 energy and 400 water at 91 of 104 daily endpoints, and 103 of those days
are stress-free. These daily aggregates do **not** prove that it was eligible
when a seed slot became available. Bank fullness alone therefore does not
establish a scheduling or fairness bug.

The final adult ultimately runs out of water. Over `(224,232]`, its water
budget is `508 + 1954 income - 2048 upkeep - 375 repair = 39`. In the final
56 ecology samples, it receives no water, spends 15 on repair and 24 on
upkeep, and records eight shortage steps. It still has 252 energy at death.
The replacement chain had already failed: no new child since day 97.938 and
no pending seed after day 223.891.

## Ordered access follow up

The [ordered reproduction comparison](leaf-population-reproduction.md) now
completes this follow-up with four exact-parity replays. Shrub 17 loses 16
opening-tick visits to earlier buyers while otherwise eligible. On its eight
visits with room still available, it fails seven energy checks and one water
check. The next diagnostic examines resource spending around those moments;
capacity, visitation order, repair rules, and placement remain unchanged.

## Reproducible evidence

The
[diagnostic](../../sim/experiments/leaf_population/population_fallback_loss.py)
authenticates the source archive and six input records, validates state
identity, history prefixes, resource conservation, seed costs, and trace
coverage, then derives the published JSON (`leaf-population-fallback-loss.json`,
kept locally) without invoking the simulator. The 131,457-byte JSON has SHA-256
`aef6fbd05857ffdf68fd5cba5bc84a75c052886bb1f3aaf54e8054900f8220d7`.

```sh
docker compose run --rm -T host-player python3 -B \
  sim/experiments/leaf_population/population_fallback_loss.py --check \
  benchmarks/garden-seasons/leaf-population-fallback-loss.json
```

Nine new tests cover exact derivation, frozen capacity, expiry boundaries,
censored outcomes, persistent blockers, ambiguous event ordering, resource
failure, and terminal seedlessness. All 107 analysis tests pass: the direct run
took 60.539 seconds, and the registered CTest rerun took 40.15 seconds. Its
timeout is now 120 seconds to leave scheduling headroom. The saved experiment
archive and frozen runtime remain unchanged.
