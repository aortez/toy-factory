# Dawn exposure combines boundary access and worn foliage

The original shrub's dawn rays encounter only its own foliage before leaving
the left boundary or reaching the ambient floor. The relocated shrub encounters
both itself and founder flower 1. But shadows are not the whole lower-canopy
problem: even with all shading omitted at the recorded leaf conditions, the
relocated lower leaves contribute only 22.33 energy, versus the original lower
canopy's observed 82.75.

All four [planned replays](leaf-population-canopy-protocol.md) completed in
19.46 seconds. All 44 checkpoints, four final records, previous diagnostics,
and pixels match the [foliage archive](leaf-population-foliage.md) byte-for-byte.
Neither trajectory, controller, ecological rule, nor firmware default changed.

## The left edge provides a short dawn light path

The trace covers 32 ecology steps in `(152.75,152.875]`, ending at the seed-bank
opening. Each leaf contributes one ray per step; co-located leaves remain
separate energy consumers.

| Actual ray termination | Original shrub 19 | Relocated shrub 17 |
|---|---:|---:|
| Left boundary | 531 | 8 |
| Top of canopy grid | 0 | 401 |
| Ambient floor reached first | 237 | 423 |
| Total leaf samples | 768 | 832 |

Every one of the original's 256 column-zero samples exits left. Those eight
leaves contribute 75.4% of its fractional dawn energy. Leaving the grid stops
further attenuation; it does not extinguish the remaining light. Some rays
encounter self-shade before exiting, so boundary access is not synonymous with
fully unshaded light.

No neighboring plant contributes opacity along the original's visited dawn
paths. On the relocated plant's paths, the contributing lineages are itself
and founder flower 1, whose base is at column 4. Raw opacity summed over visited
cells is 31,467 from itself and 9,448 from the flower. These are repeated ray
exposures, not unique leaf counts or an additive partition of lost energy:
per-cell saturation, the ambient floor, and energy bands cap their effects.
Paths that reach the ambient floor are not counted as boundary exits merely
because extending the geometric line would eventually cross an edge.

These observations establish which rays are attenuated in the recorded worlds,
not how either body would develop if transplanted. Position, age, structure,
repair history, and neighbors still differ between the two trajectories.

## Removing shade cannot restore worn lower leaves

The optical calculations below keep every recorded leaf's position and
condition fixed while omitting selected sources from the opacity field.
They are snapshot calculations, not additional simulated trajectories.

| Shade retained | Original whole canopy | Relocated whole canopy | Relocated lower canopy |
|---|---:|---:|---:|
| All recorded sources | 158.42 | 84.76 | 7.12 |
| Self only | 158.42 | 124.92 | 14.41 |
| Neighbors only | 289.11 | 143.80 | 12.56 |
| None | 289.11 | 196.80 | 22.33 |

Values are `sum((light // 64) * condition) / 255`, before the plant-wide carried
remainder and integer conversion. The observed rows reconcile exactly with the
previous 159 and 84 integer income. The two source-removal gains need not add
up: shadows overlap and light-to-energy conversion is quantized.

The relocated lower canopy's unshaded numerator is just 5,693, compared with
its observed 1,816 and the original lower canopy's observed 21,101. Increasing
light alone at those conditions cannot recover the lower-canopy gap. Most of
the relocated plant's optical recovery comes from its healthier upper leaves.

Neighboring shade still matters to the immediate purchase budget. Omitting it
raises the relocated whole-canopy numerator from 21,613 to 31,854. With the
recorded starting remainder 36, that gives 125 rather than 84 gross energy.
Holding the recorded starting store and expenses fixed gives
`116 + 125 - 32 = 209` before purchase, just above the 208 threshold instead
of the observed 168. This narrow accounting crossing does not predict a
successful replay: changing light can alter decisions, subsequent conditions,
and competition for the seed bank.

## The repair audit separates darkness from missed windows

The subsequent [offline repair audit](leaf-population-repair-opportunities.md)
finds that all 146 visits to the relocated lower leaves fail the model's light
gate. Nine leaves never reach the required brightness that day; six have short
qualifying windows but are not selected during them. None is repaired, versus
nine lower-leaf repairs in the original shrub. No new simulations were needed.

Next observe a full 13-day selection-phase cycle in the unchanged trajectories
before choosing an intervention. With a fixed 26-leaf body, selection shifts
relative to daylight each day; these one-day misses need not persist.

The current evidence does not justify changing boundary rules or suppressing
competition. It identifies a real neighbor-shadow cost and an independent
fixed-condition limit, but not why those lower leaves became so worn or whether
renewing them would repay its resource cost and additional shading.

## Reproduce and verify

The host adapter appends a projection entry point to a build-directory copy of
the authenticated world source. It uses the original progress, wear, and shade
builder functions on a private pre-step world copy. The real simulation and
frozen runtime files are untouched; the unsupported maintenance uptake-audit
guard remains intact. Before accepting each sample, the adapter compares its
sun and all 392 light cells with actual uptake light at the repair callback.
This avoids attributing sources from the later, already-modified callback body.

Independent Python reconstruction matches all 25,088 recorded grid cells and
all 1,600 focal leaf samples. It preserves signed Q4 ray rounding, neighboring
cell contributions, saturation, and early termination. The evidence retains
every source, actual path, and fixed-snapshot optical calculation.

Seven host suites passed in 144.10 seconds, followed by ten preparation tests.
Native tests cover input preservation, maturation immediately before wear,
dead foliage, invalid timing, allocation/output failure, incomplete records,
reset, no allocation while stepping, and a corrupted full-grid result that
latches an error. Twelve focused analysis tests cover geometry, overlap,
corruption, body-order joins, exact archived findings, and byte-identical
offline archive round-trip. All 167 analysis tests pass in 47.25 seconds.
Archived programs are never executed by verification.

```sh
docker compose run --rm -T host-player python3 -B \
  sim/experiments/leaf_population/population_canopy.py unpack \
  benchmarks/garden-seasons/leaf-population-canopy-results.json.gz \
  artifacts/garden-population-canopy-review-v1

docker compose run --rm -T host-player python3 -B \
  sim/experiments/leaf_population/population_canopy.py verify \
  artifacts/garden-population-canopy-review-v1
```

Use a fresh unpack directory. The archive
(`leaf-population-canopy-results.json.gz`, kept locally) is 677,487 bytes with
SHA-256 `bffc7454ca81b41470461c493b6a8a2260072fe485aab4dadefffc99e24171e1`. It
retains collection-time source snapshots, the prospective protocol, preflight
receipts, and all four unchanged replays. No collection retry was needed.