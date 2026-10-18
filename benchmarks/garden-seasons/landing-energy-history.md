# Lower winter income explains the mature plant energy deficit

Completed 2026-10-03. The selected mature plant's nine unpaid energy units follow
**reduced photosynthetic income, not extra construction or seed spending during
the episode**. Both histories start from full stores, maintain the same body and
leaf counts, and experience the same weather. Lower winter-morning income leaves
the broader-dispersal plant with insufficient energy for the following dawn.

This resolves the immediate resource accounting. The subsequent
[passive leaf-light audit](landing-winter-light.md) identifies a surviving
offspring's shade as the canopy cause in this selected pair. No ecology rule
or default changes are justified yet.

## Selected case and evidence

The [frozen protocol](landing-energy-history-protocol.md) selects the
fixed-order, dawn-guard, focal-root, capped-uptake world, without wicking, from
the [complete sixteen-comparison audit](landing-dispersal-energy-audit.md).
Plant 20 was born before the dispersal intervention, at tick 590640 and column 3,
and survives through tick 983040 in both arms. It is a deliberately selected
diagnostic example, not a fresh or representative trial.

Both original adult traces were rehashed and read through their complete
headers, clocks and footers. Their population censuses and birth identities
match the ledgers. The retained extracts contain **26,161 samples per arm**:
the plant's complete lifetime, with all resource stages, sun, cold, season,
root counts and active-leaf counts. Lifetime budgets, 6,540 payments per arm,
shortfalls and every seed debit reconcile with the preceding audit.

## A shared full store removes the immediate spending ambiguity

The last shared post-step full-energy checkpoint before the deficits is tick
**972045**. Both plants have 256 energy, 512 water and zero stress. Their last
seed purchases were at 967260 in the narrow world and 963480 in the broader
world, before this refill. Neither spends anything on growth or reproduction
between the checkpoint and the later shared full-store recovery.

Earlier reproduction can still affect descendants and shading. The checkpoint
only removes its direct carried-forward energy debit from this accounting
window; it does not erase those ecological effects.

The body remains **32 nodes, 16 roots and eight active leaves** in both histories
throughout the selected interval. Maintenance costs four energy units every
60 logic ticks in each arm. Water accounts are identical throughout the window,
and every water bill is fully paid.

## Income diverges before the next night

After the checkpoint, the first difference occurs at tick **974805**. Both
observe sun phase 27, source strength 64 and cold winter conditions. Narrow
dispersal receives two energy units and broader dispersal receives one. Neither
overflows, so their post-step stores immediately diverge, 80 versus 79. There
is no simultaneous difference in demand, spending or recorded body/leaf counts.

The wider difference accumulates during that morning:

| Period | Narrow gross income | Broader gross income | Energy demand in each arm | Narrow closing store | Broader closing store |
|---|---:|---:|---:|---:|---:|
| Winter morning, ticks 974400–975345 | 189 | 77 | 64 | 231 | 119 |
| Noon and afternoon, ticks 975360–976305 | 95 | 85 | 64 | 230 | 140 |
| Following night, ticks 976320–978225 | 0 | 0 | 128 | 102 | 12 |

The morning costs **112 units of income** relative to the narrow world. During
the afternoon the narrow plant overflows by 32 while the broader plant wastes
none, so the store gap narrows to 90 despite another ten-unit gross income loss.
Both then pay the same 128 units overnight. The broader plant reaches dawn
with only twelve energy units, leaving little time for light income to recover.

The existing kernel converts each active leaf's local light into whole energy
units using integer division by 64. The first divergence coincides with source
strength 64, where modest attenuation can remove a leaf's entire unit of income.
That makes quantization worth examining, but these adult receipts do not show
which leaves cross the threshold or which plants supply their shade.

## The shortfall and recovery balance exactly

At ticks 978420, 978480 and 978540 the broader plant misses four, four and one
energy units, respectively. Its stress rises to three; it does not die. All
water bills are paid. The first subsequent energy bill is fully paid at 978600,
and both energy stores are full again by 979230.

Accounts from immediately after the shared checkpoint through the last deficit:

| Energy item | Narrow | Broader |
|---|---:|---:|
| Initial store | 256 | 256 |
| Gross income | 300 | 172 |
| Overflow | 33 | 1 |
| Retained income | 267 | 171 |
| Growth and seed spending | 0 | 0 |
| Maintenance demand | 436 | 436 |
| Maintenance paid | 436 | 427 |
| Unpaid maintenance | 0 | 9 |
| Final store | 87 | 0 |

The **96-unit retained-income loss** accounts exactly for 87 fewer stored units
plus nine unpaid units. This is an equal-window comparison from equal initial
stores, unlike the earlier lifetime totals whose spending and overflow differed.

By shared refill, the retained-income difference shrinks to nine units because
the narrow plant subsequently discards more incoming energy. That does not erase
the nine unpaid units across three maintenance bills: recovery and prior
shortfalls are separate observations. A terminal image or final store alone
would hide this temporary winter deficit.

## Follow-up: observe leaf light and shade sources

The evidence identifies insufficient recorded energy supply during this episode.
It does not identify the canopy mechanism or establish that the same cause
explains every other comparison. The sixteen-comparison cohort result remains
the broader context; no harm-screen check is relaxed.

The existing host uptake observer already records leaf coordinates, local light,
per-leaf income, the light field and shade sources with lineage identities.
A small **passive replay of each archived arm**, with observations covering the
winter daylight interval and the following dawn, can locate the lost income.
Keep model bytes and ecology unchanged and require replay results, original
adult traces and final pixels to match their captures. The observer needs new
window selection, not a new physics rule.

Reconstruct the actual light field and compare unchanged target-leaf positions
and the sources along their light paths. Separate self-shading, other living
plants and decomposing bodies, and examine the integer income thresholds.
Any shade-removal calculation should be labeled a frozen-geometry diagnostic,
not a prediction of a world where a plant was removed. Those replays are the
proposed next task at the time of this audit; **none ran during this audit**.
That separate two-replay task is now [complete](landing-winter-light.md).

## Validation and portable evidence

All **19 new tests pass** on the host and in Docker. Three related offline CTest
entries pass: this history audit, the cohort energy audit and the earlier
seed-spending audit. Tests cover capped uptake before expenses, shortages,
checkpoint inclusion, missing shared refills, phase/cold boundaries, gross
versus retained income, continuity, seed-ledger reconciliation, body and
environment mismatches, source tampering and fresh-output protection.

An independent energy-store calculation reproduces every selected sample using
the 256-unit cap and ordered maintenance, growth and reproduction debits.
Portable reanalysis, independent raw re-extraction and a byte-identical repeated
export pass with subprocess launching forbidden. Only the two primary adult
traces were reread; historical repeat identities were inherited from the
previously verified capture. No native simulation, training, device operation,
runtime-code edit or default change occurred.

The [636 KiB portable result](landing-energy-history-results.json.gz) includes
the selected raw histories, milestone budgets and chronological phase accounts.
See [tool instructions](../../docs/garden-landing-tools.md#mature-plant-energy-history)
for export and portable/raw verification.

| Artifact | SHA-256 |
|---|---|
| Frozen protocol | `c8fb37a9c3f897d7972009759a2ff4ef44e989c63244d86893c8e49999573c54` |
| Cohort audit input | `998796b9b79732d1a37e62b4a9c145f4b18fa05bde49028d9cbdd15699d4b5fb` |
| Late dispersal input | `390669aba064732072c82e2170ad1d6f7872612710bc1c6501ad3351c8ad3b62` |
| Original raw manifest | `4a94df9dcc4f53c980e3631b58dc3fd853c3f03a68678d335127ab09f7a83001` |
| Energy history result | `ad05d00dce06ffdfbf5208586dfa03aed07277f0ec2f9ef77f83d78e842540a8` |
