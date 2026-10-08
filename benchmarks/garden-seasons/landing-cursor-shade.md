# Neighbor shade explains the cursor adult winter energy loss

Plant 39's shadow accounts for **all 30 missing winter energy units** in adult
37, the extra death in the [cursor comparison](landing-seed-cursor.md).
Removing only that neighbor's shade in the recorded states restores exactly
the fixed-order income, with no residual difference. The focal leaves and all
other shade sources match between arms throughout the sampled pre-death history.

This confirms the local light-competition mechanism behind the
[energy diagnosis](landing-cursor-energy.md). It does not establish survival in
a newly simulated world without that shade. No ecology or controller changed,
and the original experiment's no-additional-adult-death gate still fails.

## One pair and two observation windows

The [protocol](landing-cursor-shade-protocol.md) fixes two replays of S2 ordinary
(`366928c6-rainfed`) using the original executable and model. Both run to day
384, adding only the existing passive uptake observer. Complete results and
endpoint pixels match their saved originals. All 13,799 overlapping stand
observations in each arm also match exactly.

The observer records 704 samples per arm in two short windows. All **1,408
light grids** reconstruct from their shade sources and sun rays. Every recorded
leaf's light and integer income reconcile; focal totals also match the original
resource histories. Across all 703 paired pre-death samples, the focal leaf
coordinates match, and excluding plant 39 leaves exactly the fixed-order shade
sources. The final sample, after the cursor death, is checked but excluded from
paired-canopy attribution.

| Income interval | Samples | Fixed order | Cursor | Cursor with only plant 39 shade omitted |
| --- | ---: | ---: | ---: | ---: |
| Establishment window, ticks 1263045–1267200 inclusive | 278 | 1,379 | 1,266 | 1,379 |
| Terminal winter account, ticks (1463640,1470000] | 424 | 172 | 142 | 172 |

Residual income differences are zero at **every** compared sample, not merely
in the summed totals. The establishment window loses 113 income units over 29
steps. The winter account loses 30 over 24 steps; both arms start with the same
252-unit energy reserve and face 424 units of maintenance. The earlier diagnosis
retains the complete resource balance and eight failed payments.

## Two leaves cross the income threshold

The terminal loss occurs in afternoon sun phases 72–99 on day 382, before the
night's reserve exhaustion. Only these two of the adult's eight leaves lose
income in the terminal account:

| Leaf node | Canopy column and row | Lost energy units |
| --- | --- | ---: |
| 171 | 25, 7 | 21 |
| 173 | 25, 5 | 9 |

At the first affected step, day 382.03125, leaf 171 receives light **58** with
the neighbor and **66** without its shade. Income is integer `light / 64`, so
that eight-unit illumination difference changes income from one energy unit
to zero. At the last affected step, its light is 24 versus 64, again zero versus
one energy unit. There is no leaf movement, additional upkeep or late purchase
needed to explain the loss.

The calculation rebuilds opacity from the remaining sources before ray casting.
It does not subtract the neighbor's opacity from an already saturated grid,
which could overstate the light restored. No plant, root, water demand, seed
or resource balance is changed in the replay itself.

## Implication for the next experiment

This is a measured competition cost of broader recruitment, not an unrecovered
seed expense or evidence of an accounting error. Adding an adult-protection
exception would suppress that interaction. For an A-life environment where
organisms must obtain resources to survive, the next decision is whether to
allow competitive displacement in future acceptance criteria.

The recommendation is to allow such deaths while testing **sustained renewal,
population viability and diversity** over a predeclared follow-up. Agree and
freeze those criteria before running it. Keep this experiment's failed gate
and individual harm in the record; do not retroactively label it a pass or
start training on the strength of a two-run diagnostic. Long-run population
effects and environmental qualification remain unresolved.

## Reproduction and retained evidence

The [portable result](landing-cursor-shade-results.json.gz) includes the complete
windowed observations, commands, original result identities and per-leaf losses.
The [tool guide](../../docs/garden-landing-tools.md#attribute-the-cursor-neighbor-shadow)
provides collection and offline verification commands. The collector uses fresh
outputs and preserves failures. Verification cannot launch native processes.

Validation passes:

- Two replays match the original results, frames and 27,598 total stand rows.
- Independent offline verification authenticates the full bundle, restores
  compressed trace hashes and repeats all light calculations and stand comparisons.
- Nine new tests cover rays, saturation, quantization, corrupt evidence,
  missing/reordered samples, exact interval bounds and observer-only arguments.
  The five preceding energy tests and six existing attribution tests also pass.
- The two new offline CTest targets pass in Docker; no firmware was rebuilt or flashed.

The bundle `artifacts/garden-landing-cursor-shade-v1/` is about **219 MiB**,
mostly the unchanged 212 MiB historical source archive, which includes the
previously recorded generated build files. New compressed traces total
**3,846,991 bytes**, restoring exactly 218,739,480 raw bytes. Only these newly
generated raw duplicates were removed after verification; all four gzip traces
and their restoration receipts remain. No earlier artifact was removed.
The portable result adds 414,726 bytes.

| Identity | SHA-256 |
| --- | --- |
| Protocol | `a4a11318b2759c69b2ecc6d803a2cd3e9913dbfff6fe3f919181c4f2ce5016ac` |
| Local bundle manifest | `b713cd3f8804e61132bf0cdd4dcca3ae6703b9d1b66d37354b8755d72c5dda0d` |
| Portable result | `909f1deaefa5d1cc3cd9a3d9bd7c2ae91248d317bc45b3ae424310acbde33226` |

The original frozen executable, model, runtime source archive and build settings
are unchanged. No new fitness objective, capacity increase or ecology default
is introduced.
