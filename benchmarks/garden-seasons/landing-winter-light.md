# An offspring shades its parent's winter income

Completed 2026-10-03. In the selected broader-dispersal history, **plant 29 shades
its parent, plant 20, enough to explain every observed target-leaf light and
income difference**. The parent's leaf positions and self-shading are identical
in both worlds. No dead foliage contributes in either observation window.

This is evidence of local parent–offspring competition, not a broken light
calculation or proof that broader dispersal is universally harmful. Both plants
survive. No ecology rule, policy, training configuration or device default changed.

## Two passive replays preserve the original worlds

The [frozen protocol](landing-winter-light-protocol.md) selects the same
fixed-order, dawn-guard, focal-root, capped-uptake pair without wicking as the
[energy-history audit](landing-energy-history.md). Plant 20 was born at tick
590640, column 3, before the late-dispersal intervention.

Exactly two full-horizon replays reused the archived model and native binaries:
one narrow and one broader arm. Only the uptake-observation windows changed.
Both final results, framebuffer bytes and compressed full adult, stand,
direction and reach traces match their historical captures exactly. These are
observer-neutral diagnostic replays, not fresh independent trials.

Each replay records 195 snapshots: the full winter daylight interval at
974400–976305 and the following dawn through shared refill at 978240–979230.
The analysis reconstructs all **152,880 light cells**, checks **20,475 leaf
income records**, and reconciles **2,340 adult resource receipts**. Target
receipts also match the previously saved complete energy history. Root and soil
observations remain in the raw bundle but are not reinterpreted here.

## The additional shade belongs to a surviving child

The target has eight active leaves and unchanged geometry throughout all 390
snapshots. Leaf matching uses coordinate multisets, not mutable node indices.
The narrow world contains four living shade owners; the broader world has eight.
All observed shade comes from living plants.

The relevant additional plant is **lineage 29**, born at tick **652380** at
**column 0**, three columns left of its parent. Its parent is lineage 20 and
its generation is 3. It remains alive through the horizon and has produced
nine seeds. The canopy consequence appears long after its establishment.

On each broader-world snapshot, remove only lineage 29's recorded opacity,
leaving the sun, all target leaves and every other source unchanged. This
restores **all eight target-leaf light values on all 195 snapshots** to their
narrow-world counterparts. The corresponding income totals are:

| Observed period | Narrow actual | Broader actual | Broader with child 29's shade omitted |
|---|---:|---:|---:|
| Winter morning, 64 steps | 189 | 77 | 189 |
| Winter afternoon, 64 steps | 95 | 85 | 95 |
| Following dawn through refill, 67 steps | 455 | 310 | 455 |

The losses are 112, 10 and 145 units: **267 gross energy units in total**.
The saved comparison keeps every leaf, including ties and possible improvements;
this pair has 267 one-unit losing leaf-steps, 1,293 income ties and no improvements.
Its highest leaf, at canopy cell (5, 2), loses no light or income.

These calculations diagnose the recorded geometry. They do **not** predict
what would happen if the child were never born: resources, vacant slots, later
growth and reproduction would all be free to change in that different world.
Gross income is also not retained energy. The preceding store audit accounts
for overflow and finds nine unpaid units followed by full recovery.

## Rays and integer thresholds explain the loss

Light first differs at tick 974415, when neither history earns any energy yet.
The first income difference occurs at **974805**, with source strength 64 and
ray step +7/16 cell per canopy row. At target cell **(3, 12)** the narrow plant
receives light 64 and earns one unit. The broader plant receives the ambient
floor, 24, and earns zero.

The ray encounters three contributions, all from child 29:

| Ray cell (column, row) | Contribution | Opacity |
|---|---|---:|
| (2, 9) | Neighbor spread from a leaf | 8 |
| (1, 7) | Leaf center | 26 |
| (0, 5) | Neighbor spread from a leaf | 8 |

Their sum is 42. The ambient floor caps effective attenuation at 40, producing
`64 - 40 = 24`. There is no cell-saturation clipping along this particular ray.
The portable result retains every ray cell and contribution for all target
leaves at the first income divergence, including floor/early-exit effects.

Integer conversion matters beyond this heavily shaded example. At tick
**974895**, cell **(5, 4)** falls from light **64 to 56**: eight light levels
remove its entire unit of income because each leaf earns `light // 64`.
Other light differences remain inside an income band and cost nothing at that
step. This verifies threshold sensitivity, but does not test or recommend a
fractional-income replacement.

Self-shade still matters in both worlds. In the broader winter morning, no
shade would yield 296 units, removing self-shade alone yields 153, and removing
child 29 alone yields 189, compared with 77 actual. The individual gains of
76 and 112 sum to 188, not the joint gain of 219. **Single-owner removal gains
are not an additive allocation of lost income.** Cell saturation, ambient
floors and integer thresholds make them conditional on the remaining canopy.

## Placement information follow up

The selected deficit now has an exact mechanism: extra surviving offspring
introduce shade, equal winter maintenance then exhausts the parent's reduced
income buffer. This does not explain all sixteen comparisons in the broader
experiment or erase the recruitment benefits that prompted it.

The [completed placement-information audit](landing-placement-information.md)
now finds that column 0 was the only reachable spacing-clear choice. The child
survived 86.11 observed days and made nine seeds, but none established before the
horizon. Their mature checks always failed spacing and almost always found full
plant capacity. The next proposed question is usable vacancies and environmental
turnover across the existing panel. Avoid treating all parent–offspring competition
as a defect or hard-coding an exclusion zone from this one example. Neither this
light diagnosis nor that offline placement audit changes a policy.

## Validation and reproducibility

The 19 new tests cover argument isolation; signed rays and edges; opacity caps,
ambient floors and non-additive thresholds; live/dead identity at the exact
maintenance boundary; duplicate geometry; full trace coverage; historical
neutrality; receipt/provenance tampering; and fresh-output protection.
All pass on the host and in Docker. Four related offline CTest entries pass.
The broader host energy-tool check also passes 70 tests, with four optional
native-integration tests skipped because no integration build was requested.

Portable verification and independent extraction from the new raw bundle pass
with process launching forbidden. Repeating the complete offline export produces
byte-identical output. No runtime C code, model bytes or build settings changed.

The [142 KiB portable result](landing-winter-light-results.json.gz) includes the
light receipts, bounded population receipts, frozen-shade diagnostics and full
capture identities. See [tool instructions](../../docs/garden-landing-tools.md#winter-leaf-light-and-shade)
for capture and offline verification commands. The 2.5 GiB raw capture remains
locally in `artifacts/garden-landing-winter-light-v1`; no prior artifact was removed.

| Artifact | SHA-256 |
|---|---|
| Frozen protocol | `5bf5f7514bd372af33bd36edf5e55e9dbdbc413ff3734f4692f4fd472e4b5a19` |
| New raw manifest | `bc9d7567bfc210e92faf9f5ddd482d4ca66d694512987bff6181f3a9245b817c` |
| Portable result | `4dec6112f5f1c875ed40cfa8515d1581de27c7422311077b7c36cfb49d9d61c6` |
