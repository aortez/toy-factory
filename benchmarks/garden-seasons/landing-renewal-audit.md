# Survival without renewal: saved-ledger diagnosis

The [five-seed training panel](landing-multiseed.md) contains gardens that keep
established plants alive without replacing them. The saved records distinguish
two recruitment stalls: seeds expiring without germination, and seedlings
dying before their first-day establishment check. Missing seed production is
not the whole explanation. Old plants can also persist after their bounded
renewal credit expires; terminal survival and ongoing reproduction are
deliberately different measures.

This is an offline audit, not another experiment. All 224 evaluated histories
and 896 late world-windows are included: initial models, single- and five-seed
finalists, live and fixed inputs, both layouts and climates. Original scores,
comparisons and failed support gates reproduce exactly. No native worlds,
training, selection, ecology changes, score changes or firmware deployment.

## What the surviving gardens are doing

Of 532 zero-credit windows, 390 still have established descendants at their
two-day follow-up: 317 steady-weather and 73 seasonal. All 390 record new seed
purchases. That does **not** mean all descendants reproduce: some windows have
only founders producing seeds.

Among these 390 persistent-but-zero windows, 293 contain living descendants
that have aged out of renewal credit. In 91, the only established descendants
during the window are children of founders, which never qualify for that
credit. These signatures describe occupancy, not the cause of failed renewal;
the endpoint census can also include follow-up births or confirmations.

The two new live-input finalists with improved aggregate survival make the
recruitment problem particularly clear. Each has 26 persistent-but-zero
steady-weather windows, out of 32 steady windows:

| Observation in those 26 windows | Live / 34 | Live / 35 |
|---|---:|---:|
| Seeds already present at window start | 208 | 208 |
| Of those, expired without germinating | 208 | 208 |
| New seeds purchased during the windows | 211 | 222 |
| Purchased by established descendants | 69 | 89 |
| New seeds germinating by follow-up | 3 | 14 |
| Germinated children dying before first-day confirmation | 3 | 14 |
| Windows containing aged-out eligible descendants | 24 | 20 |
| Windows with no purchases by established descendants | 4 | 0 |

All 17 germinations in this table come from established-descendant parents.
The remaining 208 new seeds per finalist are still pending at the respective
follow-up; they are **not** counted as failures. Seeds can live for 32 Garden
days, whereas scoring follows each window for only two extra days. The
carry-in cohorts above, unlike these pending purchases, have observed expiry.

Counts are world-window observations, not independent samples or necessarily
unique seeds across the whole report. A seed can appear first as a purchase
and later as carry-in. The fourteen variants also reuse models and conditions;
initial live/fixed biology and the fixed / 35 old/new pair are exact ties.

One illustrative case is new live / 34, crowded-steady seed `7d3b7bde`. Across
all four late windows, the same four plants remain: founders 1 and 5,
first-generation child 10, and aged-out grandchild 11. There are no births or
confirmations. Each window has eight carried-in seeds expire and eight new
founder-produced seeds remain pending at follow-up. This is seed-bank turnover
without plant turnover, not sustainable renewal. It is a retrospective example,
not a separately selected representative sample.

## Contrary cases and credit accounting

More births alone do not solve establishment. Across all steady windows, live
/ 35 increases births from 1 to 18, but qualifying renewal confirmations only
increase from 1 to 2. Its 14 failed seedlings above explain why that birth
increase is not equivalent to durable renewal. In seasonal worlds its births
increase from 110 to 112 while renewal confirmations fall from 42 to 40.
Live / 34 seasonal births fall 133 → 87 and renewal confirmations 46 → 43.
The regressing live / 33 drops seasonal births 89 → 45 and confirmations
35 → 21; its steady confirmations fall 4 → 0. The complete retained results
include every fixed-input and initializer control as well.

Each credited child/window intersection has an exact arithmetic identity:

`earned = child count × window width − timing exclusion − death loss`

Timing exclusion covers the part outside the child's eligible-age interval;
death loss is the remaining eligible occupancy lost after death. For the
objective's minimum credit, each world selects its **own first weakest window**.
Old and new need not select the same period. The following deltas sum these
sixteen per-world selections; all units except child count are logic ticks.

| Five-seed minus single-seed finalist | Eligible child/window count | Count × width | Timing exclusion | Death loss | Earned credit |
|---|---:|---:|---:|---:|---:|
| live / 33 | -2 | -245,760 | -77,820 | 0 | -167,940 |
| live / 34 | -5 | -614,400 | -393,330 | -129,120 | -91,950 |
| live / 35 | -3 | -368,640 | -317,745 | +11,730 | -62,625 |
| fixed / 33 | -4 | -491,520 | -338,775 | 0 | -152,745 |
| fixed / 34 | -10 | -1,228,800 | -878,295 | +119,205 | -469,710 |
| fixed / 35 | 0 | 0 | 0 | 0 | 0 |

All five changed finalists have fewer eligible child/window intersections in
their selected weakest windows. This is not simply higher mortality: live
/ 34's death-loss term actually decreases. Selected windows differ in 10, 6,
6, 12, 8 and 0 worlds respectively, in table order. Both selected periods and
all four same-period deltas are retained. This accounting is not a causal
decomposition or a simulated benefit from removing death or the age limit.

## Next question, not yet an intervention

The ledger establishes stalled recruitment but does not record per-attempt
moisture, light, spacing, plant-slot or node-slot blockers. Nor does it expose
the first-day resource trajectory responsible for each seedling death. Expiry
alone cannot identify the cause, and surviving plants need not be productive.

Next propose a small, read-only germination and first-day seedling trace on a
fixed matched old/new subset. Preserve models, ecology and scoring; observe
which checks block seeds and what happens to seedlings that do emerge. Include
successful and regressing cases, not just these failures. This should precede
another search budget, a bigger network or an objective/environment change.

## Evidence and verification

- [Protocol](landing-renewal-audit-protocol.md) and
  [repeatable workflow](../../docs/garden-landing-renewal-audit.md).
- [Readable summary](landing-renewal-audit-summary.json): all model/climate
  slices, paired credit accounting and provenance.
- [Full derived audit](landing-renewal-audit-results.json.gz): all 896 windows,
  seed identities/cohorts, parent classes, occupancy and endpoint censuses.
- [Original ledgers](landing-multiseed-results.json.gz): the unchanged input.

The analysis repeats exactly without mutating its input; a separate execution
of the frozen tools independently reproduces all 224 histories, 896 windows
and six paired decompositions. Boundary tests use a direct sampled occupancy
oracle. Portable-data regressions recompute the full audit, original terminal
censuses, parent-class partitions, hashes and highlighted counts.
All seven audit tests and the complete 139-test UBSan host suite pass. The
input archive and all 240 frozen artifact hashes remain unchanged.

Frozen manifest SHA-256:
`47df95fbab6382b95adb13a68c65340c3ab8f1479f96752bcc4174e6c1992b0c`.
