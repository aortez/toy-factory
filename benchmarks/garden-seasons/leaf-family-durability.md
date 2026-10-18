# Repair policy durability through day 1376

Both frozen learned repair controllers retain a mean renewal advantage through
day 1376 on all four weather seeds from the [earlier comparison](leaf-family-generalization.md).
The late-period score is 0.084722 for fixed wear, 0.431250 for Search 1 and
0.277778 for Search 2: about 5.09 and 3.28 times the control. No candidate family
in any policy's matches becomes newly extinct after day 608.

All 123 planned research calls completed in 32.8 minutes. Archived references,
all 96 early-history comparisons, all 24 serial confirmations and portable
archive verification pass. There is no further training or model selection.

## Renewal across equal length periods

The [fixed protocol](leaf-family-durability-protocol.md) keeps all 32 founder
roles per policy: four weather seeds, three rainfed founders and five crowded
founders per seed. One founder family uses the candidate controller in each
world; every other family retains the selective resident controller. W2 growth,
its memory, seasonal ecology and the absence of a gardener remain unchanged.

Each period contains six 64-day birth windows, followed by 32 days to establish
the final children. The score counts actual children of non-founder parents,
with both parent and child surviving 32 days, capped at two credits per window.
Seed/layout conditions have equal weight, then all founder roles within each
condition have equal weight. Extinct and zero-score families remain included.

| Birth period | Observation endpoint | Fixed wear | Search 1 | Search 2 |
|---|---:|---:|---:|---:|
| Early, (192,576] | 608 | 37/120 = 0.308333 | 179/360 = 0.497222 | 73/180 = 0.405556 |
| Middle, (576,960] | 992 | 1/9 = 0.111111 | 31/72 = 0.430556 | 529/1440 = 0.367361 |
| Late, (960,1344] | 1376 | 61/720 = 0.084722 | 69/160 = 0.431250 | 5/18 = 0.277778 |

Both finalists pass the prespecified durability criterion: strictly greater
mean late renewal than fixed wear. Search 1 is almost flat between the middle
and late periods. Search 2 declines, but its late score remains above control.
Neither controller maintains its early score everywhere or improves every role.

## Renewal is distinct from survival and occupancy

| Late period or day 1376 measurement | Fixed wear | Search 1 | Search 2 |
|---|---:|---:|---:|
| Families with any qualifying late renewal | 11/32 | 23/32 | 21/32 |
| Families renewing in the closing window | 6/32 | 20/32 | 10/32 |
| Families renewing in every late window | 0/32 | 6/32 | 1/32 |
| Paired roles improved / tied / regressed against control | — | 22 / 7 / 3 | 19 / 9 / 4 |
| Living families | 26/32 | 23/32 | 24/32 |
| Dormant families with pending seeds only | 0/32 | 0/32 | 0/32 |
| Extinct families | 6/32 | 9/32 | 8/32 |
| New extinctions after day 608 | 0 | 0 | 0 |
| Equally condition-weighted extinction rate | 18.33% | 25.83% | 25.00% |
| Mean established-descendant occupancy | 0.714562 | 0.554999 | 0.654250 |

Fifteen of the control's 26 surviving families earn no late renewal credit.
All 23 surviving Search 1 families renew at least once; three of Search 2's
24 survivors do not. These survivor counts explain the outcome but do not
replace the full-roster scoring denominator.

The control's established-descendant occupancy rises from 0.589185 early to
0.714562 late while its renewal score falls from 0.308333 to 0.084722. A garden
can remain occupied without sustaining generational replacement. The learned
controllers' lower occupancy therefore does not negate their renewal advantage.

The earlier survival cost also remains: Search 1 lost three more families than
control in net terms before day 608, and Search 2 lost two more. No new losses
appear in the extension, but that does not recover the families already gone.
Extinction requires no living family member and no pending family seed; it is
reported separately, not added as a new fitness penalty.

## Late renewal by weather

Each row averages its two layouts equally and all founder roles within each
layout equally. These are the same weather seeds as the previous panel, not a
new held-out weather test.

| Weather seed | Fixed wear | Search 1 | Search 2 |
|---|---:|---:|---:|
| `58d7d6ca` | 0.225000 | 0.700000 | 0.394444 |
| `9a903368` | 0.013889 | 0.433333 | 0.275000 |
| `6b9c1a3e` | 0.041667 | 0.230556 | 0.225000 |
| `59818bc3` | 0.058333 | 0.361111 | 0.216667 |

Search 1 improves all eight individual seed/layout conditions. Search 2 improves
seven: its first seed's rainfed mean is 11/36 versus the control's 1/3. Both
improve all four combined seed means, with no selection between the finalists.

## Isolated host horizon extension

The old replay and scorer deliberately rejected horizons beyond day 608. The
longer executable is a separate build from the authenticated v8 snapshot, with
only the maintenance and daylight time ceilings raised to day 1376 and the
daylight callback-count guard raised from 2048 to 6144. The latter limits a
diagnostic counter; it does not change seed production or plant resources.
Two CLI rejection fixtures use the new one-past-end tick. No ecological source,
model weight, firmware default or original build is changed.

Eleven replay, family-routing, owned-state, neural and maintenance-run contract
suites pass. The separate legacy daily-report/command fixtures retain their
day-608 schema and are not rebuilt for this experiment. The two changed staged
C headers pass the repository formatter's dry-run check.

The isolated Python scorer preserves the existing arithmetic and exactly matches
all 96 archived early scores and their aggregates before research. Seventeen
preflight tests cover late-window boundaries, strict 32-day survival, first-
generation exclusion, the per-window cap, exact occupancy, family ownership,
future-event censoring, full rosters and bounded scheduling.

All extended runs start from reset. Every complete day-608 lineage, seed,
ownership and death-cause prefix matches its archive exactly after censoring
future events. This reconstructs histories, not earlier world state or pixels.
The three separately executed day-608 anchors reproduce complete archived stdout,
canonical state and pixels byte-for-byte under the new executable.

The extended panel reaches at most 252 lineage records and 525 seed records,
well below the unchanged capacities of 4096 and 65536. The first build preparation
passed its contract tests but failed while recording a binary in the wrong
subdirectory. That attempt remains in `artifacts/garden-leaf-durability-tools-v1`;
the corrected fresh v2 preparation completed before any research calls.

## Verification and evidence

The research comparison took 1965.027 seconds from first submission to the last
process receipt. All 123 calls completed without a failed research call, retry,
replacement or budget extension: three archived anchors, 96 extended matches
and 24 serial repeats without capture. Each repeat matches its captured run
after removing only the framebuffer CRC field. All source and model identities
remain frozen, and the original pilot and four-weather archives are unchanged.

The [8.99 MiB evidence archive](leaf-family-durability-results.json.gz) contains
1771 file entries backed by 1623 unique blobs, including complete raw histories,
99 original captures, process receipts, model bytes, the protocol/scoring source
snapshot, the compiled runtime's complete staged sources and binaries, build/test
receipts and four comparison sheets. It is 9,421,818 bytes compressed and
42,353,552 bytes with its file entries expanded. Raw results remain in
`artifacts/garden-leaf-durability-v1`.

Fourteen offline archive tests pass, covering exact roundtrip and published
pixels, altered runtime sources or binaries, changed models/scorer, corrupted
pixels, derived scores, unsafe paths, late preflight, violated submission/serial
ordering and failed attempts presented as complete. Verification reconstructs
all scores and evidence bindings without executing a simulator or requiring the
ignored native build directories. It uses the repository sources and the two
authenticated companion archives named in the protocol.

Each day-1376 sheet has fixed wear, Search 1 and Search 2 from left to right.
Rows 1–3 are rainfed founders 1–3; rows 4–8 are crowded founders 1–5. Native
240-by-240 tiles are neither rescaled nor selectively omitted:

- [Weather 58d7d6ca](frames/leaf-family-durability-58d7d6ca.png).
- [Weather 9a903368](frames/leaf-family-durability-9a903368.png).
- [Weather 6b9c1a3e](frames/leaf-family-durability-6b9c1a3e.png).
- [Weather 59818bc3](frames/leaf-family-durability-59818bc3.png).

All four sheets verify against the retained native pixels. They show whole
gardens, including resident competitors; a populated screenshot does not prove
that the candidate family survived or renewed.

```sh
python3 sim/experiments/leaf_durability_report/collect_durability.py \
  --check benchmarks/garden-seasons/leaf-family-durability-results.json.gz \
  --images benchmarks/garden-seasons/frames
docker compose run --rm -T firmware env PYTHONDONTWRITEBYTECODE=1 \
  python3 -m unittest discover -s sim/experiments/leaf_durability_report -p 'test_*.py'
```

SHA256 identities:

- Protocol: `e19a647a20f7a7c4d34163c22bdd49c4bd8a56e1cb06444836fcaabbfd765695`.
- Evidence: `5dc495ec0e33f83c121b1c6eaa09603033bd824476e175c8a72f347ef272744f`.
- New host executable: `5d30e3c1058e4b38b89d01c3068865c192ffd8723b319982bf590bd3dc959a57`.
- New build receipt: `257319b73ed129c95bf99690e93ddb561b2bdf369f3747fa55be3cf834569774`.

## Scope of the result

This closes the bounded duration question for the repair-learning prototype:
the mean renewal advantage is still present much later, rather than ending at
the original evaluation cutoff. It is not a guarantee of indefinite stability,
survival in arbitrary layouts or stability when every competing family uses
the same learned controller.

Keep both finalists, the control and the documented early losses. The evidence
now supports checkpointing this repair-learning result before expanding neural
control into growth or increasing the search budget. A useful next product step
is [interactive host replay of the frozen policies](../../docs/garden-research-playback-plan.md)
for visual review. The plan preserves the research runtime and defines parity
checks before integration; implementation and firmware promotion are not part
of this experiment.
