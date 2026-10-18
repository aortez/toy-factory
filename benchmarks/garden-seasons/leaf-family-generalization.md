# Repair policy generalization across four weather seeds

Both frozen learned repair controllers improve mean family renewal over fixed
wear on **each of four additional weather seeds**. Across the full panel,
Search 1 gains 61.3% and Search 2 gains 31.5%. Late renewal improves substantially,
but more candidate families become extinct. This is a positive generalization
result for the agreed renewal-first objective, not an improvement in every
survival measure.

All 123 planned runs completed: 96 scored matches, three exact archived
references and 24 serial/capture confirmations. The portable archive and all
comparison-sheet pixels verify offline. No run was retried or added.

## Comparison and scope

The [fixed protocol](leaf-family-generalization-protocol.md) retains the two
[wear-initialized finalists](leaf-family-wear-pilot.md), their fixed wear-aware
initializer, W2 growth and its memory, selective resident competitors and all
ecology. There is no new training, parameter update, model selection or firmware
change. Each match gives one founder family the candidate policy; all other
families use the same fixed resident policy. These are not worlds where every
family uses the learned controller.

Four deterministic weather seeds cover both rainfed layouts and all founder
roles: three in rainfed and five in crowded, for 32 matches per policy. Every
match runs through day 608. Weather seeds come from fixed SHA256 labels, not
from simulation outcomes; an audit found no prior seed tokens in 1,777 published
JSON, compressed JSON, Markdown and Python files outside this experiment.

The objective is unchanged: actual children of non-founder parents, both
surviving 32 days, with at most two credits in each of six 64-day birth windows
in (192,576]. Day 608 supplies the final establishment follow-up. Seed/layout
conditions receive equal weight, and founder roles receive equal weight within
each condition. Descendant occupancy is secondary. Zero-score and extinct
families remain in the means.

## Renewal improves while survival narrows

| Measurement | Fixed wear | Search 1 | Search 2 |
|---|---:|---:|---:|
| Mean renewal score | 37/120 = 0.308333 | 179/360 = 0.497222 | 73/180 = 0.405556 |
| Relative renewal gain | — | +61.3% | +31.5% |
| Roles improved / tied / regressed against fixed wear | — | 20 / 7 / 5 | 19 / 6 / 7 |
| Families with any qualifying renewal | 24/32 | 23/32 | 24/32 |
| Families renewing in the closing window | 6/32 | 15/32 | 13/32 |
| Families renewing in every scoring window | 3/32 | 9/32 | 4/32 |
| Living families at day 608 | 26/32 | 23/32 | 24/32 |
| Extinct families at day 608 | 6/32 | 9/32 | 8/32 |
| Equally condition-weighted extinction rate | 18.33% | 25.83% | 25.00% |
| Mean established-descendant occupancy | 0.589185 | 0.439430 | 0.501183 |

The renewal gain is not just greater occupancy or more families registering a
single success. Search 1 has one fewer family with any qualifying renewal than
fixed wear, yet more than doubles closing-window participation and triples
every-window participation. Search 2 also more than doubles closing-window
participation. Both meet the prespecified strict primary-score improvement
criterion; occupancy falls rather than supplying the gain.

The survival cost is visible early as well. All 32 founders per policy survive
day one. By day 16, 31 fixed-wear founders remain versus 28 under each learned
policy; at day 32 the counts are 25, 21 and 22. Founder death is distinct from
family extinction: descendants or pending seeds can preserve the family.

There are no dormant-only families at the endpoint in this panel. Extinction
requires both zero living family members and zero pending family seeds. The
weighted rates use the same condition/role weights as the score, so they need
not equal the raw fraction of 32 matches.

## Results by weather

Each row averages its two layouts equally, then all roles within each layout.

| Weather seed | Fixed wear renewal | Search 1 renewal | Search 2 renewal | Extinct families in the same order |
|---|---:|---:|---:|---|
| `58d7d6ca` | 0.322222 | 0.497222 | 0.441667 | 1 / 1 / 1 of 8 |
| `9a903368` | 0.363889 | 0.638889 | 0.519444 | 2 / 2 / 2 of 8 |
| `6b9c1a3e` | 0.186111 | 0.366667 | 0.266667 | 2 / 3 / 3 of 8 |
| `59818bc3` | 0.361111 | 0.486111 | 0.394444 | 1 / 3 / 2 of 8 |

Search 1 improves seven of the eight individual seed/layout conditions; Search
2 improves six. Both regress in the last seed's crowded layout. Search 2 also
regresses in the first seed's rainfed layout, although its crowded gain raises
that seed's combined mean.

Search 1 introduces four extinctions where fixed wear preserves the family and
avoids one fixed-wear extinction. Search 2 introduces three and avoids the same
one. The common avoided loss is crowded founder 4 on `58d7d6ca`.

| Newly extinct relative to fixed wear | Search 1 extinction day | Search 2 extinction day |
|---|---:|---:|
| `58d7d6ca`, crowded founder 2 | 64.90625 | — |
| `58d7d6ca`, rainfed founder 1 | — | 126.578125 |
| `6b9c1a3e`, crowded founder 4 | 319.96875 | 79.875 |
| `59818bc3`, crowded founder 2 | 32.9375 | — |
| `59818bc3`, crowded founder 3 | 32.921875 | 47.078125 |

These are the last family death/seed-resolution times, not necessarily founder
death times. Each newly extinct match has zero qualifying renewal in the scoring
windows. That does not imply no prior reproduction: for example, Search 1's
family lost near day 320 reaches generation 11, but still earns no qualifying
32-day parent/child link in the scored windows.

## Day 608 comparison sheets

Each sheet has fixed wear, Search 1 and Search 2 from left to right. Rows 1–3
are rainfed founders 1–3; rows 4–8 are crowded founders 1–5. Tiles preserve the
native 240 by 240 pixels, with all failures included:

- [Weather 58d7d6ca](frames/leaf-family-generalization-58d7d6ca.png).
- [Weather 9a903368](frames/leaf-family-generalization-9a903368.png).
- [Weather 6b9c1a3e](frames/leaf-family-generalization-6b9c1a3e.png).
- [Weather 59818bc3](frames/leaf-family-generalization-59818bc3.png).

The screenshots show whole gardens. A full canopy can belong to resident
competitors after the candidate family has died, so visual fullness is not a
substitute for the family-level metrics. For example, the first sheet's top
right garden is populated despite Search 2's candidate family being extinct.

## Verification and evidence

The comparison took 1,302.165 seconds, or 21.7 minutes, from first submission
through the last process receipt. All runs stayed within the 123-call ceiling,
two-worker limit, 45-minute submission deadline and storage limits. The reference
phase and confirmation phase were serial; the scored panel used checked batches
of two. No failures, retries, continuation or budget extension occurred.

All three archived references reproduce the original stdout, complete histories,
canonical state and pixels byte-for-byte. All 24 serial capture-free repeats
match their captured panel run after removing only the framebuffer CRC field.
Every scored match retains native raw pixels and a checked PNG; all four
comparison sheets are verified against those pixels.

The unchanged runtime's source/binary identities and existing 25-suite build
receipts were rechecked. Fourteen synthetic preflight tests pass, covering
exact score weights, actual renewal links, dormant versus extinct families,
survival boundaries, fixed model identities, complete rosters, batch stopping
and resource limits. Twelve offline archive tests pass, including corrupted
pixels, sources and models; altered derived extinction; late seed audits;
submission/serial-order violations; unsafe paths; and failed attempts presented
as complete results. No new native build or firmware change was needed.

The [2.47 MiB evidence archive](leaf-family-generalization-results.json.gz)
contains 875 file entries backed by 751 unique blobs, including all raw outputs,
99 original captures, process receipts, model bytes, the source/protocol snapshot,
the preflight test receipt, the seed audit and comparison sheets. It is
2,585,013 bytes compressed and 19,370,343 bytes when its file entries are expanded.
Verification uses the repository and the authenticated companion pilot archive,
not ignored native builds or simulation execution:

```sh
python3 sim/experiments/leaf_generalization_report/collect_generalization.py \
  --check benchmarks/garden-seasons/leaf-family-generalization-results.json.gz \
  --images benchmarks/garden-seasons/frames
docker compose run --rm -T firmware env PYTHONDONTWRITEBYTECODE=1 \
  python3 -m unittest discover -s sim/experiments/leaf_generalization_report -p 'test_*.py'
```

SHA256 identities:

- Protocol: `803cd224b1e6f8a9fca9fc51adeaa1a96b6bfa1f0e315fb6c772559afa762957`.
- Evidence: `2b1cc660140437c99ae5e0f8980ef23ecc0f34fde3971c1abf37948e6e832094`.
- Unchanged executable: `a626303a633112082278091f0be04f2a057dbb44f669bf64a540cdda9b0bdc44`.

Raw outputs remain in `artifacts/garden-leaf-generalization-v1`. The original
pilot and crowded diagnostic archives are unchanged. No policy is promoted.

## Interpretation and next decision

The earlier pilot's mean gain now generalizes to four additional weather seeds
without changing a weight. The [winter diagnostic](leaf-family-crowded.md)
remains a genuine failure case, but it does not negate the broader renewal gain.
Nor does the mean gain erase the extra family losses.

Search 1 leads this panel while Search 2 led the previous two-seed validation.
Keep both finalists: switching the preferred model after examining a validation
panel would turn that panel into selection data. Four weather seeds also do
not provide 96 independent climates or establish population-wide stability.
Extinction remains a reported tradeoff, not an added fitness penalty.

The subsequent [day-1376 durability follow-up](leaf-family-durability.md) now
answers the bounded temporal question: both frozen finalists retain a late
renewal advantage on every combined weather mean, with no new family extinction
after day 608. It is a separate matched duration extension, not additional
held-out weather or training. Keep this panel separate from the original pilot's
held-out score and leave firmware defaults unchanged.
