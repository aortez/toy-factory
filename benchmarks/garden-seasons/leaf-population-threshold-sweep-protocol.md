# Repair light threshold across whole populations

Does any setting of the repair light gate give sustained renewal and variety
together when every family shares one controller? Map late renewal and
founder-family survival across the light gate on fresh weather, with fixed wear
and both learned finalists as reference points. This is a diagnostic sweep: no
training, deployment choice, ecological rule or objective change follows from it
automatically.

## Fixed conditions and budget

Use the authenticated frozen research runtime (archive SHA256
`5dc495ec0e33f83c121b1c6eaa09603033bd824476e175c8a72f347ef272744f`), W2 growth
and memory, seasonal climate, rain-fed startup resources and no gardener. Keep
eight plant slots, the eight-seed bank, spacing, seed lifetime, prices and every
ecological rule unchanged. Every founder family and descendant uses the assigned
repair model. Run both existing layouts: `rainfed` with three founders and
`rainfed-crowded` with five. Stop at day 1376, as in the
[population comparison](leaf-population.md).

Use sixteen fresh weather seeds: the first four SHA256 bytes, read
little-endian, of `toy-factory/garden-repair-threshold-sweep-v1/weather-01`
through `-16`:

`457e75c9`, `2329528f`, `bccf8ae5`, `466abb4d`, `2333b716`, `fcc7033a`,
`9a1bb399`, `9e1ec5d9`, `3d1e9311`, `9b290248`, `e40447bc`, `705fba59`,
`53bf5dc8`, `b9d2f4f3`, `4248d45e`, `965d3b72`.

Before any run, a whole-word search of all 3,751 tracked files outside this
sweep, including decompressed archives, finds none of these tokens. They are
new conditions, distinct from every training, validation and diagnostic seed.

Build twelve light gates from fixed wear by changing only hidden unit 0's bias
to `64 × T` for light-feature threshold `T`. The condition gate stays at
192 or less and every other weight, shift and cost is unchanged. An exhaustive
check of all 65,536 light/condition pairs with the exact fixed-point network
proves each rule, and the existing gate decomposition proves that no other
input can change the decision. Light 64 is the first productive band; `T = 0`
also repairs in darkness and `T = 128` never repairs. `light-065` is
byte-identical to fixed wear, and `light-071` matches Search 1's light gate for
a 21-leaf shrub. Search 1 and Search 2 run unchanged.

| Policy | Repairs when light is at least | Model SHA256 |
|---|---:|---|
| `light-000` | 0 | `5e36de481d3e2d0e0937e33699097ca550d88aa0591cac7afca06835c2a2490f` |
| `light-032` | 65 | `839aa4e7d9cf7c04ec9d82ad5fd322f05ea51bd54b926d9614640bfc856f1ec4` |
| `light-048` | 97 | `bcefa0b3266692f3e5ad5ee035b9003e96c9e0f3dd5dbc25e1c826224d25bb3b` |
| `light-056` | 113 | `d75420bf92d2469ce2f8546bab038de32de879d45cb561636e4965e720720160` |
| `light-061` | 123 | `4a6cd53d091e52d555b24aff629cde6ccc09255cac06f5f14af8a50cf8f75d82` |
| `light-065` (fixed wear) | 131 | `be37b3c3c10356e9b58922893aa875b598517a898dcc2b7bad39edac11f22d75` |
| `light-068` | 137 | `88c91b29accb5a28ae889c5079c27c5a2a3924910012cc5e07f9722e424b19a9` |
| `light-071` | 143 | `0badfa4697fe01dd529f89c6fbd343fd34084202221f1269464ce74a306d12b3` |
| `light-074` | 149 | `e07dc8c41bf6309e8786cd4d0f32561420b394392c290e3c94b57384c0623568` |
| `light-080` | 161 | `e0cbaa81ecba8ee62f276831cedaf64f6ab450f472099325479a5b86b8b66aeb` |
| `light-096` | 193 | `8276c78051fb1fd86e5bf0d6301da0eb9b7eab09a48283581f6f38fe24f800e4` |
| `light-128` | never | `617f2bbac879dbe13530484eacbd10c6980fe241bb05eddfc9e7a57cecfa93a3` |
| `s1-g3-c4` (Search 1) | — | `8ad9cc95d8b5469b5bdd3159b9d69598da8973b9a79df813dce626f257a7caa1` |
| `s2-g3-c1` (Search 2) | — | `70634b853f9d0b1e46d2ca40130d1aeabeaa75bdf91ef10307e072dff6ebb1c7` |

Run 14 policies × 16 seeds × 2 layouts: 448 unrendered calls, plus three
anchors. Use twelve workers, 300 seconds per call and a 90-minute collection
budget. Stop on the first failed call or validation mismatch, retaining every
attempt, with no retries, substitutions or extensions. Builds and unit tests
are separate from the scientific calls.

## Identity and validation

Each call runs `research-replay MODEL.tlf SEED LAYOUT 5283840 all` through the
custom-model path. Named models stay restricted to the documented seeds; a
custom model accepts any seed, and its JSON and canonical state carry the exact
model bytes. Before collection, the custom path must reproduce the archived
`58d7d6ca` rainfed population runs for fixed wear, Search 1 and Search 2
(archive SHA256 `3aae48b92ed9787f9dc1601052330cdbf96ed9d72f3d845e0b9932d50112af49`)
in every field except the framebuffer CRC.

Validate every output with the existing population record checks: schema,
conditions, model identity, canonical envelope, and complete ancestry and seed
ledgers. Analyze each world with the unchanged population scorer. Snapshot this
protocol, the sweep module, the model codec, the research player sources, the
binary digest and every model digest. The offline check revalidates every
retained output and recomputes the analysis without executing the simulator.

## Outcomes and interpretation

Give each of the 32 worlds equal weight within a policy. Report late renewal
with the unchanged arithmetic: actual children of non-founder parents born in
`(960,1344]`, both surviving their first 32 days, at most two credits per family
in each 64-day window, followed through day 1376, with every initial family in
the denominator. Report variety as extinct founder families at day 1376 (of
128), single-species gardens (of 32), mean retained species and gardens
retaining shrubs. Report viability as gardens with any interval without living
plants. Also report early and middle renewal, closing-window families, births,
establishment and early deaths.

Give 95% bootstrap intervals over the sixteen weather seeds, resampling both
layouts of a seed together, with 10,000 draws and a fixed generator seed. Include
paired differences from Search 1's late renewal and fixed wear's family losses.
The intervals describe uncertainty; the decision uses the point estimates.

A light setting delivers both if, on this panel:

1. no garden has an interval without living plants;
2. its late renewal is at least Search 1's;
3. its extinct founder families are at most fixed wear's; and
4. its single-species gardens are at most fixed wear's.

The panel reproduces the earlier tradeoff if Search 1's late renewal exceeds
fixed wear's and Search 1 loses more founder families.

- If some light setting delivers both, the shared light-gate controller can
  give renewal and variety together here, and the open gap is the objective and
  evaluation setting. Discuss evaluating candidates in the whole-population
  setting with variety in the score.
- If none does, no setting of this gate gives both. Discuss coexistence
  mechanisms, such as per-species strategies, niche differences or capacity,
  before any training.
- If the tradeoff is not reproduced, report that. The sweep still maps the
  gate, and the earlier tradeoff becomes evidence specific to its four seeds.

This is one weather panel. Seeds also drive plant randomness, and families in a
garden are not independent replicates. Do not pick a deployment default, tune
the gate further, or train from this sweep.
