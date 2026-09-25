# Full-night body capacity: a size warning, not a survival guarantee

The advisory check detects growth that commits a body to an energy bill it
cannot survive overnight, even with full stores. It is entirely offline: no
growth was refused, no model was trained and no firmware/default was changed.
The [protocol](renewal-night-capacity-protocol.md) was
[recorded in issue 30](https://github.com/aortez/toy-factory/issues/30#issuecomment-5747863885)
before computing the new aggregate results. These are reused development
trajectories, not independent qualification data.

Across the full panel, the check flags **four observed plant lifetimes**, all
ending in energy death. One is duplicated in the shared-prefix conditions, so
this is **three distinct lifetimes**, not four independent successes. It leaves
**50 of 54 guarded natural deaths** unflagged. This is a real but narrow hole in
the current guard, not the main explanation for garden mortality.

## Why the boundary is 64 → 65 nodes

The complete guaranteed-zero-income interval contains **37 upkeep payments**.
With zero starting stress and sufficient water, a plant may miss seven; the
eighth unpaid payment is fatal. Energy upkeep is `ceil(nodes / 8)`, and storage
holds at most 256 energy. Therefore the minimum full-night reserve is:

```text
minimum reserve = ceil(nodes / 8) × (37 − 7)
```

| Body | Upkeep per payment | Minimum reserve | Fits in storage? |
| --- | ---: | ---: | --- |
| 57–64 nodes | 8 | 240 | Yes |
| 65–72 nodes | 9 | 270 | No |

The calculation permits survivable shortages; demanding payment of the whole
night's energy bill would incorrectly exclude some viable bodies. The exact
iterative reference agrees with the separate closed-form check for all 512
legal body sizes. It uses the phase-117 anchor, excludes the first possibly
productive morning step, and assumes no spending or body change during the
interval. No particular amount of morning income is promised.

This is deliberately different from the existing spending guard. That guard
asks whether the *current* resources and proposed expense can survive the
*remaining immediately dark* interval. The new check asks whether storage could
ever fund a *complete* dark interval for the proposed body, independent of the
current phase, energy, identity or species. It can therefore flag a daytime
commitment before the spending guard's horizon begins.

## Main panel: all four seeds, both conditions and arms

The audit covers **11,668 paid node-adding extensions**, **323 observed plant
records** and **1,954,739 checked live resource steps** across all 16 trajectories.
Counts below preserve the original conditions; shared prefixes are not
independent replications.

| Condition / arm | Paid extensions | First unsafe crossings | Later unsafe extensions | Flagged natural deaths / all natural deaths |
| --- | ---: | ---: | ---: | ---: |
| No patches / control | 2,562 | 0 | 0 | 0 / 45 |
| No patches / guard | 1,960 | 1 | 18 | 1 / 21 |
| Patches / control | 3,641 | 0 | 0 | 0 / 51 |
| Patches / guard | 3,505 | 3 | 26 | 3 / 33 |

There are **48 flagged paid extensions**, but only **four first crossings**.
Counting all 48 as separate preventable deaths would be wrong. No flagged plant
survives to the endpoint or is patch/trace-censored here; those outcomes are
still supported and all unflagged plant records remain in the export.

| Guarded world / child | First crossing tick / phase | Body at next full-night anchor | Energy there | Observed energy death |
| --- | --- | ---: | ---: | ---: |
| `0d983a80`, shrub 7, both conditions | 37,605 / 11 | 83 nodes | 250 | 40,980 |
| `58e36558`, ground-cover 12, patches | 134,940 / 100 | 70 nodes | 245 | 137,280 |
| `beda710e`, ground-cover 15, patches | 138,765 / 99 | 68 nodes | 214 | 140,880 |

All are descendants. Their first full-night follow-ups match the exact dark
energy/stress reference, without assumption breaks. Every crossing occurs
outside the current immediate-dark forecast horizon. None lies in the closing
day-48–64 window. The shrub produces one lifetime seed but no observed offspring;
the two ground-cover plants produce no seeds.

The shrub illustrates the horizon distinction particularly well: the existing
guard **already refuses eight 64 → 65 proposals during the previous night**,
then permits growth when possible income returns at phase 11. It subsequently
reaches 83 nodes, whose full-night minimum reserve is 330 energy, and dies the
following night. The identical lifetime appears in both conditions before
patches begin; their complete per-lineage audit records match.

Among the guarded arms' **321 already-denied positive-node proposals**, the
capacity check would also flag 16 newly-unsafe and ten already-unsafe proposals.
The 16 are the same eight shrub attempts duplicated across conditions. These
26 receipts group into four lineage/index/body records (22 additional receipts
within those groups); none is an additional paid crossing. The 295 other denied
proposals concern bodies that fit the capacity test but fail the existing
current-budget guard.

The controls never grow past 64 nodes despite their 96 natural deaths. Among
the guarded arms' 50 unflagged deaths, 46 are energy and four are water failures.
Thus passing this size check plainly does not imply adequate reserves or a
viable long-term policy. The existing guard changes later ecological histories;
the newly observed oversized bodies do not establish that the guard itself is
generally harmful.

## Supplemental retry case

The retry-aware FINISH trajectory is separate from the main panel, not another
independent world. Among its **1,291 paid node-adding extensions**, the check
flags two first crossings and four later extensions on those already-oversized
bodies. Both first crossings occur while the immediate-dark forecast is still
unsupported because another daylight step could earn income:

| Child | First 64 → 65 crossing | Phase | Energy just after growth | First dark entry | Observed death |
| --- | ---: | ---: | ---: | ---: | ---: |
| Ground-cover 28 | 154,305 | 111 | 204 | 154,395 | 155,880 |
| Ground-cover 34 | 215,790 | 114 | 249 | 215,835 | 217,920 |

Their actual dark-entry bodies reach 68 and 66 nodes. Both first complete dark
windows have exact energy-death predictions with no assumption break. Eleven
later positive-node proposals for child 34 are already denied by the ordinary
guard; these are not eleven additional plants or newly identified crossings.

The other four post-intervention first-day deaths—flowers 26, 27 and 29, plus
ground-cover 31—remain **unflagged**. Their bodies fit within storage capacity,
but their actual night-entry reserves do not. Overall, the check covers only
**2 of the retry run's 21 natural deaths**; the other 19 are retained in the
output. Neither flagged child produces a seed. The already-documented loss of
shrubs is not addressed by this size check.

## What the audit does and does not count

- The shared denominator is actual paid EXTEND actions that append a node.
  Paid FINISH and blocked EXTEND do not increase body size and are excluded.
  The embedded-C contract review confirmed this distinction, the old-body
  maintenance ordering, the energy cap and the stress-death threshold.
- Selected positive-node proposals already refused by the current guard have
  their own denominator. Their hypothetical post-payment energy is not an
  observed debit: the portable receipt's `paid` field remains false.
- Repeated denied receipts are grouped by lineage, logged selected-node index
  and body size, with counts and first/last records. The index is a packed-array
  location, not a permanent physical-tip identity across reclamation. The
  groups and later unchanged-trace extensions are not independent rescues.
- Every plant is retained, including unflagged deaths, patch deaths and plants
  alive at the endpoint. Follow-up distinguishes the first full dark interval
  from a partial current night, deaths before its anchor, and patch/endpoint
  censoring. Natural terminal resource telemetry is cleared and is not invented.
- A flagged body may still reproduce before dying; lifetime seed and offspring
  outcomes are retained. Structural inviability is not by itself a verdict on
  reproductive fitness, nor a reason to impose a permanent ecology rule.

## Verification and portable evidence

- Both complete frozen bundles re-verify: the panel's guard/resource/tip ledgers,
  repeated captures and 48 frames, plus both retry reference trajectories,
  intervention receipts and nine frames. No experimental native binary was run.
- The new 17-trajectory analysis runs twice and matches exactly. Current native
  sources match the retry archive; each bundle keeps its own frozen native
  revision. Input manifests/artifacts and analysis-source hashes remain unchanged.
- The supplemental case adds **122,538 live resource checks**, for **2,077,277**
  across the new audit. It is not pooled into the panel totals or called an
  independent world. All six selected early deaths from the recruitment audit
  remain represented, with only children 28 and 34 crossing the boundary.
- **13 new unit tests** and **all 75 default host CTests** pass. Tests include
  every legal body size, reserve/tier boundaries, partial-night differences,
  FINISH/blocked/newborn action accounting, receipt disagreement, repeated
  denials, censored anchors, unflagged deaths and corrupt/truncated input.
- The generated [portable summary](renewal-night-capacity-summary.json) is
  byte-identical to the verified artifact (950,751 bytes), SHA-256
  `fb4d4a628bea19270e8cfea8f5f2e1a5a2ca0dd270d4d40bf64a881033edabae`.
  The existing panel and retry images remain the visual record; none were
  generated or selectively recaptured for this offline study.

## Next proposal

Discuss a small **host-only, off-by-default A/B** that refuses only node-adding
growth failing this capacity check, alongside the unchanged current dark guard.
Do not bundle larger energy stores, changed maintenance, seed/FINISH rules,
spacing changes or training. Measure survival, repeated rejected growth,
remaining useful actions, descendant reproduction and species retention.

The key unknown is behavioral: refusing a purchase changes later decisions,
resources and neighbors. The shadow audit locates commitments worth testing;
it cannot show that refusing them rescues a plant or improves the whole garden.
Reserve-poor smaller plants and dawn recovery remain separate problems.
