# Renewal stalls at occupied landing sites

The uptake cap conserves water, but the capped worlds are not short of seeds.
In their final 32 garden days, **every mature seed check fails spacing against
another living plant**. Their seed banks remain full or nearly full. Cap plus
wicking eliminates the local moisture gate entirely in that window, without
producing a birth.

This is an offline audit of the [four-arm uptake-cap comparison](landing-uptake-limit.md),
following a [frozen protocol](landing-renewal-gates-protocol.md). It adds no
simulation, training, policy change, firmware update or default change.

## Coverage and timing

All 32 primary worlds are retained: eight settings × ordinary, wicking,
uptake cap, and both. Exact repeat runs are not additional observations.
The settings cross fixed/rotating reproduction order, daylight/dawn guards,
and ordinary/focal-root allocation. They share one previously examined weather
seed and controller; pooled counts below are descriptive, not replication.

The main window is `(626580, 983040]`: 23,764 ecology samples per world.
The nested final-32-day window is `(860160, 983040]`: 8,192 samples per world.
One garden day is 3,840 logic ticks, or 256 ecology steps. Every clock sample,
ordered seed check and production visit is preserved, including steps with
no purchases. The main window covers 6,078,327 seed receipts and 4,633,854
reproduction visits.

## Seeds are supplied, but do not establish

Totals across the eight settings in each arm:

| Arm | Post-intervention purchases / births / expirations | Final-32-day purchases / births / expirations | Final mature checks blocked by spacing | Final mature checks blocked by moisture |
|---|---:|---:|---:|---:|
| Ordinary | 256 / 108 / 148 | 69 / 6 / 63 | 99.71% | 95.01% |
| Wicking | 216 / 61 / 155 | 67 / 4 / 63 | 99.59% | 95.44% |
| Uptake cap | 202 / 36 / 166 | 64 / 0 / 64 | 100% | 6.30% |
| Cap + wicking | 196 / 18 / 178 | 64 / 0 / 64 | 100% | 0% |

Every capped world purchases eight seeds and expires eight in the final
32 days. All begin and end that interval with eight seeds. Thirteen keep
eight seeds at every post-step sample; the other three have seven seeds for
only four samples each, and eight for the other 8,188. No bank empties.

There are 523,768 mature checks in cap-only worlds and 523,772 with both rules.
Every one has a living spacing witness, and every witness is another plant,
not that seed's parent. None requires an unobserved decomposing occupant to
explain the spacing failure. The rule rejects a column less than three grid
columns from an existing plant's base.

These are repeated checks of resident seeds, not independent germination
trials. Dormant checks and expiry receipts are excluded from the percentages.
Expiry does not perform a germination test. Pending seeds are not labeled
failed. Light also blocks roughly 79–86% of capped final-period checks, but
that includes night and seasonal dimming, not just canopy shade. Cold overlaps
about 15.2%. Blocker percentages must not be added as exclusive causes.

## Actual pool capacity does not explain most cases

The seed receipts record actual sequential pool use, including decomposing
plants. Neither plant nor node capacity blocks **any** final-period mature
check in any cap-only world. Capacity does matter in two cap-plus-wicking
settings; in one it blocks every check.

Percentages below use mature seed checks within each world, not elapsed time.
"Open elsewhere" means the chosen site is blocked while at least one of all
28 hypothetical mature sites passes every gate at that same sequential check.

| Order / guard / allocation | Cap: moisture blocked | Both: plant/node capacity blocked | Cap: open elsewhere | Both: open elsewhere |
|---|---:|---:|---:|---:|
| Fixed / daylight / ordinary | 3.7% | 0% | 27.1% | 29.3% |
| Fixed / daylight / focal | 6.9% | 0% | 26.8% | 29.4% |
| Fixed / dawn / ordinary | 7.6% | 0% | 28.9% | 0% |
| Fixed / dawn / focal | 5.0% | 47.1% | 30.5% | 14.8% |
| Rotating / daylight / ordinary | 3.7% | 0% | 27.1% | 29.3% |
| Rotating / daylight / focal | 7.0% | 0% | 26.8% | 29.4% |
| Rotating / dawn / ordinary | 7.6% | 0% | 28.9% | 0% |
| Rotating / dawn / focal | 8.8% | 100% | 25.1% | 0% |

Moisture blocks zero final-period checks in every "both" setting; capacity
blocks zero in every "cap" setting. Spacing is the sole failed gate on
11.9–18.4% of cap-only mature checks. It is sometimes the sole gate in seven
of the eight combined settings, but never in the fully saturated last row.

Open sites occur in all eight cap-only worlds and five combined worlds. This
does **not** prove that a parent can disperse to those columns, that its policy
observes them, or that a child there would survive. Conversely, zero open-site
checks does not mean pool saturation: both dawn/ordinary combined worlds have
no open sites despite never hitting either capacity gate in this interval.

## Reproduction is mostly waiting on an already-full bank

The explanatory denominator is living plants visited on the 60-tick payment
cadence with sun strength above 24. All other visits are still validated, but
routine night/off-cadence failures do not dominate this summary. Flower
availability, cooldown, stress, resource reserves and sequential bank state
are checked at each parent's actual turn, not inferred from the closing bank.

| Arm | Final daylight/payment visits | Bank is the only failed gate | Of those, bank already full before the first visit |
|---|---:|---:|---:|
| Ordinary | 49,020 | 31,678 (64.6%) | 31,510 (99.47%) |
| Wicking | 50,558 | 32,600 (64.5%) | 32,446 (99.53%) |
| Uptake cap | 46,448 | 30,786 (66.3%) | 30,700 (99.72%) |
| Cap + wicking | 51,044 | 34,099 (66.8%) | 33,964 (99.60%) |

Among ready-flower, cooldown-clear visits, bank-only failures account for
68.2% with the cap and 68.4% with both rules. Earlier buyers filling a bank
that began with space explain only 86 and 135 such misses, respectively.
The large observed bank barrier is therefore residence, not chiefly visit
ordering. These counts are not predictions of extra seeds under another rule.

Other constraints remain: energy reserve checks fail on about 30.8% of these
visits in each capped arm, often alongside bank capacity. Water reserve checks
fail on none. A ready flower exists in 97.2% and 97.7% of visits, respectively.
When none is ready, the recorded flowers are spent for that day; no final-period
capped visit lacks flowers or is waiting solely on maturation. Spent flags
reset at dawn, so this is not permanent reproductive exhaustion.

## What this supports next

The water interventions expose a spatial replacement problem: long-lived
plants coexist with seeds waiting at occupied sites, while the bank prevents
most otherwise-ready new purchases. This audit identifies observed gates;
it does not establish that removing a gate improves population renewal.

The next bounded diagnostic should examine **dispersal reachability at purchase
time**: which columns were legal choices, whether all were already occupied,
and whether a chosen site became blocked while the seed waited. Compare those
choices with the observed open-site snapshots. That separates a placement
decision problem from limited dispersal range or world-wide spatial crowding,
before choosing one host-only counterfactual. Measure established descendants
and replacement, not just extra seeds or germinations.

Keep the uptake cap and wicking off by default. Do not infer support for a
larger bank, shorter seed lifespan, indiscriminate seed eviction, or relaxed
spacing from this observational audit alone.

## Reproduction and verification

The [portable results](landing-renewal-gates-results.json.gz) retain every
setting, both windows, exact masks, per-seed fates/witnesses and per-parent
production counts. The [lossless XZ excerpt](landing-renewal-gates-windows.jsonl.xz)
is about 23 MiB and retains the needed observations without unrelated growth
bids. See [tool usage and field layout](../../docs/garden-landing-tools.md).

```sh
make host-audit-landing-renewal-gates \
  GARDEN_LANDING_RENEWAL_GATES_OUT=artifacts/renewal-gates-fresh

python3 sim/garden_landing_renewal_gates.py \
  --verify benchmarks/garden-seasons/landing-renewal-gates-results.json.gz \
  --windows benchmarks/garden-seasons/landing-renewal-gates-windows.jsonl.xz
```

Adding `--bundle artifacts/garden-landing-uptake-limit-v1` re-extracts all
32 worlds from the saved raw traces and requires exact excerpt equality.
Portable reanalysis and raw re-extraction both passed with native subprocess
creation forbidden. All 64 consumed traces were rehashed before and after
reading; complete framing through day 256, seed/lineage inventory, ordered
reproduction, flower counts and resource debits reconcile. This audit does not
repeat the preceding experiment's unrelated source/binary/soil verification.

All 20 focused tests and both existing germination/bank-access offline CTest
suites pass. The focused tests cover window edges, expiry, same-step germination and bank
refill, cold/capacity/site contradictions, fixed/rotated visits, flower counts,
debit corruption, no-clobber output and frozen regressions. Initial extraction
caught a trace-format mismatch: stand traces spell season names while adult
traces use an enum. Explicit conversion and a regression test corrected the
reader; no trace or simulation result was changed.

SHA-256 identities:

| Artifact | SHA-256 |
|---|---|
| Frozen protocol | `43970e04c346e2d43d5d4b3ae7382b6df89651963dc43a6514e8c539fd223a3d` |
| Input uptake-cap results | `687f354bbeb04b71dc2c8d81b57bccefba0a1f6e2cfa6677f9dd14d517647768` |
| Raw input manifest | `7b69ecde2d36817c141811f267c8538a467a0d9120703358c8631b790cbd0857` |
| Portable window excerpt | `d7ff641241c1cc0f242e68628648a04ce82e1ffe5046f0a4221a2485b7c61026` |
| Portable results | `20d269d868b2cc1135e93d4b0f4ebe37ef667e3316d92e280d1d7488b38bd255` |
