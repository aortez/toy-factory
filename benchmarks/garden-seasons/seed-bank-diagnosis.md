# Seed-bank diagnosis: long waits at unsuitable sites

Sixteen slots mostly enlarge a waiting queue. Seeds that eventually expire occupy
**60.69% of the bank's whole-run occupied slot-time**, versus 59.49% with eight
slots. Yet old and posthumous seeds also produce many successful descendants:
805 of 1,368 sixteen-slot births happen after the parent dies, and 472 wait at
least sixteen Garden days before germinating. Neither an old seed nor a dead
parent is sufficient evidence that a seed is useless.

Extra reproductive spending is common, but this analysis does **not** isolate it
as the cause of earlier parent deaths. The capacity screen remains mixed and
unpromoted. No simulation, default, controller, lifespan or firmware was changed.

## Scope and denominators

The [frozen plan](seed-bank-diagnosis-protocol.md) analyzes all 32 pairs from the
[eight-versus-sixteen capacity screen](seed-bank-capacity.md): eight weather
blocks, two layouts and two controllers. Both arms keep wide scattering and the
same first-day offspring guard. This pass reads existing files only; it makes
zero new native trajectory calls and does not select new examples or pictures.

All 4,966 seeds are retained. A family's identity is its original founder within
one world, not a numeric ID shared across different worlds. Descendant IDs after
capacity divergence are not matched between arms. Every world's complete family
table, including nonproducers, is retained in the evidence.

Occupation counts post-step seed samples, including creation and excluding
removal. There are 256 ecology samples per Garden day, so 256 seed-samples are
one occupied slot-day. Closing occupation is the calendar interval strictly
after day 112 through day 128, not a cohort selected by seed creation date.
Pending seeds and young offspring are explicitly censored, not declared failed.

## Where the extra space goes

| Measure | Eight slots | Sixteen slots |
|---|---:|---:|
| Occupied seed-samples, whole run | 8,276,635 | 16,493,996 |
| Samples attributable to eventual expiry | 4,923,392 (59.49%) | 10,010,624 (60.69%) |
| Median germination wait, resolved seeds only | 6.95 days | 9.22 days |
| Mean germination wait, resolved seeds only | 9.28 days | 12.28 days |
| Germinations after at least sixteen days | 215 / 1,009 | 472 / 1,368 |
| Median age of pending seeds at horizon | 14.92 days | 16.13 days |
| Closing occupation by seeds aged at least sixteen days | 48.72% | 53.19% |
| Births after the parent's death | 468 / 1,009 | 805 / 1,368 |
| Durable descendants born from posthumous seeds | 198 / 285 | 286 / 401 |

Expiry accounts for 47.86%–75.16% of sixteen-slot occupation across the eight
weather blocks. The effect occurs under both controllers and layouts; it is not
one unfortunate example. Crowded layouts spend 64.36% of sixteen-slot occupation
on eventually expired seeds, versus 57.00% in ordinary rainfed layouts.

The occupation-to-outcome breakdown preserves all outcomes rather than retaining
only germinated or still-living examples:

| Seed/child outcome by day 128 | Eight-slot seeds | Sixteen-slot seeds |
|---|---:|---:|
| Expired | 601 | 1,222 |
| Pending seed | 256 | 510 |
| Young living child without full-day follow-up | 12 | 10 |
| Young dead child without full-day calendar follow-up | 1 | 0 |
| Child died by its full-day boundary | 157 | 229 |
| Day-surviving child, not a durable parent by the horizon | 554 | 728 |
| Day-surviving child with its own day-surviving child | 285 | 401 |

These eventual-outcome labels use future knowledge relative to seed creation.
They cannot be used as admission-policy inputs. Likewise, preserving a seed
beyond its parent's death supports the observed posthumous paths; this is not
an estimate of a counterfactual total after removing and replacing those seeds.

## Family concentration and site conditions

| Closing-bank measure | Eight slots | Sixteen slots |
|---|---:|---:|
| Worlds with at least 75% of occupation from one family | 25 / 32 | 24 / 32 |
| Worlds with all occupation from one family | 23 / 32 | 17 / 32 |
| Occupation share of each world's largest family, pooled | 90.75% | 89.24% |
| Flower-family occupation | 87.35% | 86.25% |
| Shrub-family occupation | 3.10% | 0.00% |
| Ground-cover-family occupation | 9.56% | 13.75% |

Concentration remains high, but doubling capacity does not simply make it worse:
the larger bank retains occupation by more families in several worlds. Family
diversity also does not imply species diversity: multiple flower families can
coexist while shrubs disappear.

For mature seeds still in the bank, overlapping post-step site blockers are:

| Blocker | Eight-slot closing samples | Sixteen-slot closing samples |
|---|---:|---:|
| Insufficient moisture | 95.29% | 95.85% |
| Spacing conflict | 94.43% | 96.60% |
| Insufficient light | 80.69% | 80.60% |
| Cold | 10.55% | 10.55% |
| Node capacity | 6.13% | 9.52% |
| Plant capacity | 4.73% | 2.76% |

Denominators are 1,044,625 and 2,089,039 mature seed-samples. Flags overlap and
must not be summed. Successful seeds leave before these snapshots, so these are
neither percentages of the map nor percentages of exact failed germination
attempts. Closing samples contain no completely unblocked retained mature seed.
Whole-history samples contain just three and four, respectively. Snapshot timing
does not establish that those seeds could have germinated earlier in the step.

The immediate pattern is long residence at dry, crowded and shaded landing
sites, not predominantly exhaustion of plant or node slots. It does not tell us
which one of those overlapping conditions an intervention would actually clear.

## Did extra reproduction cause the earlier deaths?

All 132 shared incumbents are analyzed: 57 die earlier, 21 later and 54 have
unchanged death outcomes. Each pair starts just before the first capacity-caused
divergence and ends at the **first death in either arm**, or day 128 if both
survive. The same calendar window is used for both plants, including any terminal
step. A second view uses its final Garden day, clipped to the initial divergence.

| Matched group | More seed spending with sixteen | Same | Less |
|---|---:|---:|---:|
| Earlier death, 57 plants | 50 | 4 | 3 |
| Later death, 21 plants | 21 | 0 | 0 |
| Unchanged outcome, 54 plants | 47 | 7 | 0 |

The seven earlier-death counterexamples are retained explicitly:

| World / lineage | Seed purchases in matched window, 8 → 16 |
|---|---:|
| rainfed / baseline / `ed52188c` / #6 | 2 → 2 |
| rainfed / baseline / `c629bb63` / #1 | 15 → 12 |
| rainfed / adaptive / `ed52188c` / #1 | 8 → 7 |
| rainfed / adaptive / `a9c30c1e` / #5 | 2 → 2 |
| crowded / adaptive / `4f0b9247` / #5 | 5 → 5 |
| crowded / adaptive / `a9c30c1e` / #1 | 4 → 3 |
| crowded / adaptive / `20e1353a` / #5 | 3 → 3 |

Among the 57 earlier-death plants, seed purchases total 173 → 324 over matched
follow-up. But 34 buy no seeds in their last day; only the other 23 spend more
on seeds then. Their terminal receipts identify 31 energy shortages, 25 water
shortages and one combined shortage. Twenty-two occur during active drought;
the other 35 do not.

Every resource budget includes income, overflow, paid upkeep, growth, seed
costs and terminal discard. For these 57 plants, sixteen-slot seed expenditure
rises by 7,248 energy and 3,624 water. Usable income (income minus overflow) also
rises in aggregate by 5,588 energy and 2,617 water, despite lower raw income.
Spending can free previously overflowing storage; extra expenditure is not
automatically an equal loss of useful reserves. Paid upkeep is not upkeep demand:
lower payments can reflect shortage. Death clears remaining resources, which are
recorded as discard, not invented maintenance costs.

Initial/end/last-live states, first shortage observations within each window,
exact terminal receipts and all stage totals are retained. Window starts can
already be stressed; the first observed shortage is not necessarily the onset of
the plant's lifetime shortage. More seed spending is associated with most earlier
deaths, but also with every later death and most unchanged outcomes. Different
spending timing, shading, competition, uptake and population history remain
entangled. No causal effect of spending alone is claimed.

## Verification and evidence

- All 64 original traces are hash-checked and fully reconstructed against the
  saved population histories and seed ledgers: 2,097,216 ecology snapshots.
- All 4,966 seed residence intervals reconcile exactly to the prior occupancy
  totals. Closing blocker counts come from raw closing records, not prorated
  whole-history aggregates. Ancestry and posthumous births are retained.
- All 132 incumbents, both arms and both matched windows reconcile their stores;
  every seed debit matches its independent creation record. Terminal receipts
  account for cleared resources.
- A second complete read of the unchanged raw traces reproduces the output.
  Neither pass runs the simulation or changes the original capacity evidence.
- Boundary/corruption tests cover creation, resolution, exact expiry, censoring,
  family identity, masks, shared cutoffs, seed costs, terminal discard, missing
  cases and missing incumbents. Portable tests prohibit process execution.
- All 116 default and 118 representative older-research CTests pass. After
  installing retained evidence, the diagnosis and related portable tests are
  rerun. Native source, binaries, ecology and normal defaults remain unchanged;
  no firmware rebuild or device flash was needed in this analysis-only pass.

Regression tests separately execute their existing native fixtures. The zero-
native-run count applies to the new diagnosis, not to those regression checks.

The [portable per-seed/per-incumbent evidence](seed-bank-diagnosis-details.json.gz)
has decompressed SHA-256
`f4472c610dee76ebec46d2ad8b163f1b4af349243cf852586cfcc0921a1704b1`.
The [summary with all partitions and family tables](seed-bank-diagnosis-summary.json)
has SHA-256
`2aaa9d594943103a9e43f5e9d3c4fbaafac270fdb3be3da1d168eaf472449853`.
Source/input/trace hashes are embedded. The unchanged
[eight fixed capacity screenshots](seed-bank-capacity.md#fixed-screenshots)
remain the visual record of these trajectories.

```sh
# Inside the existing firmware container; reads data, does not run firmware.
python3 -W error sim/garden_season_seed_bank_diagnosis.py analyze \
  --bundle artifacts/garden-seasonal-seed-bank-capacity \
  --out artifacts/garden-seasonal-seed-bank-diagnosis-new --jobs 4
python3 -W error sim/garden_season_seed_bank_diagnosis.py verify \
  --bundle artifacts/garden-seasonal-seed-bank-capacity \
  --out artifacts/garden-seasonal-seed-bank-diagnosis-new --jobs 4
```

Analysis requires a new output directory. Verification is read-only and requires
the original raw bundle. Portable CTests need neither that bundle nor native
executables. Raw/output/check logs stay in ignored `artifacts/`.

## Next proposal, not implemented

Discuss a bounded **seed movement/dispersal experiment**, rather than another
capacity increase or a blanket old/dead-parent seed eviction rule. A small,
deterministic environmental drift could let seeds leave persistently unsuitable
landing sites without an oracle that selects fertile cells. Keep lifespan,
resource costs, reserve guard and controller fixed, and measure durable renewal,
species retention and parent mortality against a static-seed control. The
movement cadence/range and control capacity need agreement before implementation;
the existing sixteen-slot result remains failed and off by default. This audit
does not prove drift will work or close environmental qualification.
