# Recruitment stalls: persistent spacing blocks, then resource failures

The [fixed matched trace](landing-recruitment-trace-protocol.md) is complete.
In the six selected steady-weather replays, **all 192 seeds expiring in the
late interval were spacing-blocked at every mature check**. Moisture and light
often blocked them simultaneously. Neither plant-slot nor node capacity blocked
any of these late-expiring seeds, including in the six seasonal replays.

Seedlings that did emerge faced a separate establishment problem: among 127
late-born children, 55 survived their first day and 72 died. Final maintenance
receipts identify 43 water-only, 22 energy-only and seven combined shortages.
This is not a finding that all gardens need more RAM, or that removing spacing
would rescue these seeds. It localizes the failed checks and resource losses
in a deliberately selected diagnostic subset.

## Scope and controls

All three searches contribute both their single-seed and five-seed live-input
finalist, with unchanged archived model bytes. Per search, the saved audit
selects the first lexicographic steady case containing a persistent-zero window
with a failed seedling, plus the first seasonal case where both models renew
but the new model has fewer late renewal confirmations. This gives twelve
192-day worlds; it includes the regressing /33, not only aggregate winners.

| Search suffix | Steady case | Seasonal case |
|---|---|---|
| 33 | crowded, `7d3b7bde` | crowded, `940cfdc4` |
| 34 | rainfed, `5aa2b327` | crowded, `940cfdc4` |
| 35 | crowded, `5aa2b327` | crowded, `940cfdc4` |

These are retrospective informative cases, not independent replicates or a
fresh generalization panel. No new ranking, training, selection, objective,
ecology or firmware change. Each replay matches its original complete result
and score; historical live/live GSP1 identity is recomputed from the ordinary
GLR1 fingerprint rather than discarded during comparison.

## Seeds: local exclusion rather than a full global pool

The late-expiry cohort is seeds whose observed expiry falls in (62,190]
Garden days. Their entire 32-day lifetimes are traced, not just the scoring
window's two-day follow-up. Dormant checks and the final expiry event are
excluded from mature-check statistics. Pending seeds are not failures.

| Late-expiring cohort | Seeds | Spacing blocked at every mature check | Mature checks | Seeds with an open column elsewhere at some blocked check |
|---|---:|---:|---:|---:|
| Six steady old/new worlds | 192 | 192 | 1,571,328 | 192 |
| Six seasonal old/new worlds | 151 | 82 | 1,235,784 | 151 |

In steady worlds, light blocks 70.6–75.6% and moisture 90.6–94.8% of mature
checks, depending on the replay. These overlap the 100% spacing blockage;
they are not competing exclusive explanations. Seasonal checks similarly
overlap spacing, moisture, light and cold. Every late-expiring seed has at
least one blocked check when some hypothetical mature column elsewhere passes
all gates, but **the trace does not establish that its parent could reach that
column**, or that it would still be viable after a dispersal change.

The current ordinary spacing rule excludes columns less than three cells from
any retained plant base. That includes dead plants until their slots are
reclaimed, not only living plants. These traces do not identify which specific
neighbor caused each spacing block. Global pool availability does not imply
that the actual landing column is available.

## Seedlings: spending and income timing both matter

The late-birth cohort is children born in (62,190], followed individually to
birth+one day or earlier death. A first-day survivor is not automatically an
eligible rolling-renewal descendant; that also depends on its parent. The
following counts therefore are not substituted for the original fitness score.

| Profile/search | Steady confirmed / died | Seasonal confirmed / died |
|---|---:|---:|
| single / 33 | 1 / 3 | 7 / 9 |
| multi / 33 | 0 / 1 | 6 / 3 |
| single / 34 | 1 / 1 | 12 / 17 |
| multi / 34 | 1 / 3 | 8 / 4 |
| single / 35 | 1 / 0 | 11 / 17 |
| multi / 35 | 0 / 1 | 7 / 13 |

All 127 late-born children receive some energy income before death or their
first-day cutoff. The problem is not universally zero photosynthesis from
birth. Examples from multi /34's steady world show distinct mechanisms:

- Child 26 dies from energy shortage at age 0.551 days. Its 64 initial energy
  plus 55 income fund exactly 64 growth and 55 upkeep. It discards 40 water on
  death. It has two roots and five active leaves just before death.
- Child 27 dies from water shortage at age 0.203 days. Its 24 initial water
  plus 54 uptake fund 65 growth and 13 upkeep. It still has 253 energy when it
  dies, and never expands beyond its two initial root nodes.
- Child 29 dies from energy shortage at age 0.672 days despite collecting
  821 energy. Of 64 initial plus 821 income, 421 overflow storage, 336 fund
  growth and 128 fund upkeep. Its final income is zero and it discards 508
  water. Cumulative daytime income alone does not guarantee survival through
  the later no-income interval.
- Child 28 survives its whole first day, expands to 22 roots, and finishes
  with 89 energy and 510 water. It spends more water on growth than child 27
  (180 versus 65) but receives far more uptake (1,013 versus 54).

Thus “stop growing” or “give every seedling more resources” is not yet a
qualified fix. Growth can both consume reserves and build the body that brings
in future income. These are different seedlings and environments, not matched
policy counterfactuals. Dead plants' leaf maturity is reset during decomposition;
the leaf counts above deliberately use the last living sample.

## Recommended next bounded step

Investigate **placement opportunity versus dispersal reach** first. We now know
that the actual seed sites stay locally excluded while viable columns sometimes
exist elsewhere. Determine whether those alternatives are reachable under the
parent's actual dispersal support before choosing a placement-only comparison.
Keep spacing distance, rainfall, model size and fitness unchanged for that
comparison; retain the successful and regressing controls. Do not silently
turn the gardener into a seed-placement assistant or assume a hypothetical
open column is an accessible action.

Keep first-day resource management as a separate follow-up: the new exact
budgets can test a narrowly defined growth/reserve policy without conflating it
with where seeds land. No such intervention is implemented here.

## Verification and retained evidence

- [Protocol](landing-recruitment-trace-protocol.md) and
  [workflow/schema](../../docs/garden-landing-recruitment.md).
- [Readable summary](landing-recruitment-trace-summary.json): every world,
  blocker/shortage totals, identities and verification provenance.
- [Full portable results](landing-recruitment-trace-results.json.gz): complete
  replays, per-seed mask histograms, all first-day stage trajectories and budgets.

The frozen bundle at `artifacts/garden-landing-recruitment-v1` also retains raw
compressed traces, binary, build settings, inputs and source. All research flags
are off. Twelve traced runs, twelve untraced controls and twelve exact repeats
match; a separate frozen-tool execution reproduces all twelve traces again.
The audit reconciles **4,592,849 seed events** (4,592,410 actual checks), 589,824
ecology samples and 40,175 first-day plant samples. Both resource budgets balance
at every sample, including birth endowments, overflow and discarded death stores.

The resource observer uses bounded caller-owned buffers and publishes outputs
only on success; native tests cover full world/cache equality and rollback after
an internal failure. The complete 141-test UBSan host suite passes; portable
regressions also re-score all twelve worlds, recompute every child budget and
reconcile report counts. No device deployment or performance claim.

Frozen manifest SHA-256:
`ba22339088f42a8d0708128e776a274346c8eeb84e9fda2d8551512240e47278`.
