# Garden light and water uptake attribution

The passive observer reproduces all four saved `f7ee4528` population worlds
exactly. Eight full replays—each world with tracing on and off—match the
historical result JSON, complete decision/resource traces and final pixels.
No policy, model, ecology, device behavior or qualification result changes.

The new evidence separates failure modes. Self-shading has the largest
single-class removal effect across the selected histories, but live neighbors
also matter, particularly at first productive morning light. Water shortages
occur with locally dry root cells; the selected histories show no loss from
another plant consuming that same cell earlier in the same step. Neither
finding justifies a universal reserve adjustment or an uptake-order change.

## Capture and accounting

The [frozen protocol](landing-uptake-protocol.md) reuses the
[population screen](landing-population.md) and every window selected by the
[offline shortage audit](landing-population-audit.md). It records all plants
through the union of those windows, not only a chosen failing individual.
The same model, rainfed crowded world, eight plant slots, 256 world nodes,
32-node construction budget, eight seed-bank slots and day-256 endpoint remain.
There are no training runs or extra native experimental calls.

All 38,111 observed world steps reconstruct exactly: 2,688,825 leaf samples,
2,857,757 ordered root visits and 2,721,260 shade-source records. Independent
analysis rebuilds the saturated opacity grid and rounded ray walks, checks
every light cell, replays every root transfer and reconciles plant income and
overflow with the existing resource receipts. The observer uses caller-owned
bounded host storage, publishes only successful steps and is excluded from
device recording/storage. Error rollback and recovery are tested.

Portable evidence retains 70,439 plant samples in the same 123 histories and
150 merged windows, plus complete raw uptake records at all 646 distinct
shortage ticks. These cover the prior audit's 1,038 plant payment events;
several plants can miss payment on the same tick. Full observer traces remain
in the local raw bundle. Windows overlap across plants and orders share early
history; these are not independent trials or equal-exposure treatment groups.

## Shade is not one interchangeable cause

The table sums income across the selected plant windows. Removal gains mean
recalculating the same receiving leaves under the same sun and geometry after
excluding one shade-source class. Cell saturation, the ambient floor and
integer income quantization are preserved.

| World | Actual energy | Gain without self shade | Gain without other live shade | Gain without dead shade | Open-sky upper bound |
| --- | ---: | ---: | ---: | ---: | ---: |
| Fixed control | 62,443 | 86,296 | 4,816 | 195 | 169,288 |
| Fixed candidate | 89,291 | 99,467 | 10,125 | 238 | 216,858 |
| Rotating control | 68,354 | 90,470 | 6,838 | 195 | 182,347 |
| Rotating candidate | 84,901 | 98,535 | 10,672 | 511 | 212,745 |

These gains **overlap and are not additive shares**. They are raw potential
income, not extra retained energy: storage limits and subsequent spending
still matter. This is not a simulation of removing leaves or neighbors, nor
evidence that any such intervention would preserve the recorded body or lives.

For the fixed candidate's mature plant 28, the terminal 909120..916620 window
earns **364** energy against **504** upkeep due. On those same recorded leaves,
removing self-shade gives 994, removing live-neighbor shade gives 733, removing
dead shade leaves 364, and open sky gives 1,528. Its eight leaves occupy canopy
rows 13, 12, 10, 8, 7, 5, 3 and 2; seven are in column 21 and one in column 22.
That narrow geometry makes self-overlap worth investigating. The previously
observed closed tips and zero recent construction remain unchanged; a spending
gate alone cannot repair that already-finished body.

The rotating candidate's terminal plant-28 window similarly earns 422;
without self/live-neighbor/dead shade the corresponding incomes are
1,013 / 696 / 422. Mature deficits are not candidate-exclusive: rotating
control plant 28 earns 393, with corresponding values 765 / 843 / 393.
That control ID is a different birth identity, not a matched individual.

The first-night examples have a different immediate emphasis. At candidate
plant 15's first energy-short payment, tick 460260, global strength is 125 but
nine leaves earn zero. Removing self-shade produces one unit, removing other
live shade three, and removing dead shade zero. Plant 16's first short payment
at 533160 has global strength 104 and three leaves earning zero; removing
live-neighbor shade produces three, while removing self or dead shade still
produces zero. Both orders share these pre-divergence observations. A globally
productive morning is not necessarily productive at a particular canopy.

## Water is locally absent before uptake

The next table partitions the selected roots' nominal uptake capacity, not
their maintenance bills. A root can lack its maximum possible uptake even
while its plant has ample stored water. Overflow is measured separately.

| World | Nominal capacity | Taken | Absent before uptake | Depleted earlier by own roots | Depleted earlier by other plants | Storage overflow |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Fixed control | 378,308 | 11,235 | 363,390 | 3,683 | 0 | 3,303 |
| Fixed candidate | 737,003 | 15,397 | 713,291 | 8,315 | 0 | 4,815 |
| Rotating control | 533,339 | 17,418 | 508,307 | 7,614 | 0 | 6,760 |
| Rotating candidate | 729,098 | 15,463 | 705,198 | 8,437 | 0 | 5,425 |

Already-absent moisture accounts for 98.5–99.0% of this unmet nominal capacity.
The remaining same-step depletion is entirely within each plant's own roots
in these selected histories. Such removal diagnostics are not additional
water that could be allocated independently to every root.

For candidate plant 9's final 256 ecology samples (453195..457020), its roots
take **zero** water: all 2,304 units of nominal capacity are absent before any
root visits. Later terminal windows of candidate plants 15 and 16 likewise
have zero water uptake throughout. Conversely, the fixed candidate's mature
plant 28 takes 663 water in its terminal window, overflows 379 and dies with
510 stored water; its failure is energy, not water.

The pre-uptake soil snapshot follows rain and transport. It cannot distinguish
weather, transport and consumption on previous steps. Zero same-step foreign
depletion does not rule out competition through earlier use or diffusion, and
dry root cells do not mean the entire world's soil is dry. The data do not
support reordering plants' root visits as the next fix.

## Next decision

Keep the population qualification failure and leave defaults unchanged.
The next bounded question should concern construction choices: did these
plants have affordable, legal directions that offered better light or new
soil access, and what did their existing observations reveal at that moment?
The current action interface already ranks candidate endpoints with light,
moisture and neighborhood flags. Inspect the saved choices before adding
another observation or proposing one resource-aware direction-ranking test.
An instantaneous brighter endpoint alone does not establish better daily
whole-plant income, especially after its new leaf shades existing leaves.

This would separate poor use of existing choices from a missing observation
or action. It is a proposal, not an implemented policy or another experiment
in this capture. Prices, reserves, resource supply and light rules stay fixed.

The subsequent [construction direction audit](landing-directions.md) completes
that inspection with a separate passive trace. It finds unused affordable water
opportunities, but not brighter shoot alternatives for the highlighted light
failures; it proposes a root-only comparison without changing this capture.

## Reproduction and verification

`make host-probe-landing-uptake` builds and runs the eight-call capture. Set
`GARDEN_LANDING_UPTAKE_OUT` to a fresh directory; existing output is rejected.
The reusable CLI options are `--uptake-trace NEW.jsonl` and up to 64 ordered,
disjoint `--uptake-window START:STOP` ranges, inside the stand-trace bounds and
aligned to ecology steps. Final completion is explicit; failed files are not
silently overwritten.

```sh
docker compose run --rm -T firmware python3 sim/garden_landing_uptake.py \
  --verify benchmarks/garden-seasons/landing-uptake-results.json.gz
docker compose run --rm -T firmware python3 sim/garden_landing_uptake.py \
  --verify artifacts/garden-landing-uptake-v1
```

The first command checks portable accounting, coverage, all shortage witnesses
and historical neutrality. The second also hashes every raw artifact, checks
the 2,299-file source archive and recomputes all 38,111 observed frames. Both
checks pass, without running a simulator.

| Artifact | SHA-256 |
| --- | --- |
| [Portable result](landing-uptake-results.json.gz) | `ec0b4901a23a3cb449fc77b5eba79e982a94ca9bf837aa0ad9b1d909d3dd9f74` |
| Raw manifest | `a73b453b1ff71ec71f6e3fff9a3884ab63b2f930259a4d1833af9c8e775a9f45` |
| Protocol | `12f62ef1ad96380014882efddd6d8638827a1acb05ca3cb52a75a23af8ed2d63` |
| Native executable | `8e2ecaa6bc92181d102ea9af48ef9b9bca448668d7e667a5865d79843546519e` |
| Build cache | `f93e432ba3d6c2704864bf10ffb3dddcc93e442878d605864862a5180184b0e6` |

The full 185-test host run passed 184 initially; the source-provenance test
correctly rejected a concurrent analysis-file edit, then passed on a stable
tree before capture. All thirteen focused uptake tests now pass, including
frozen findings, corrupt/missing evidence, sparse ranges, the 64-window bound,
no-clobber output and verification with process execution prohibited. The
postcapture changes add tests and this report; they do not alter the frozen
experiment or its analyzer. Native warnings/UBSan, formatting, diff checks and
the Zephyr-preprocessor syntax check pass. No firmware flash or hardware
validation was needed for this host-only observer.
