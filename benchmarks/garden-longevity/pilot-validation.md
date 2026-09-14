# Frozen-controller follow-up: a small, fragile aggregate win

The pilot winner `fa0c2cd8` beats the original `dc5e849d` by **4.45%** in rewarded
renewal time across this additional panel, but wins only **9/16** matched pairs.
Three of eight leave-one-world-seed-out comparisons reverse the overall ranking.
The evidence does not justify promoting it as a generally superior controller.
It also ends with fewer coexisting species more often.

[Predeclared protocol](pilot-validation-protocol.md) ·
[Selected native comparisons](pilot-validation-gallery.md) ·
[All scores, cohort records, hashes and timings](pilot-validation-summary.json)

## Fixed comparison

Eight additional world seeds × two existing patch schedules × two frozen
controllers = **32 scored trials**. Every trial runs the identical 512-node,
eight-seed rainfed-crowded ecology through day 192, scoring (158,190] with the
same two-day terminal follow-up. The models and native evaluator/replayer are
copied byte-for-byte from the original pilot. No mutations, ecology changes,
native rebuilds, new firmware work, gardener or irrigation.

Fresh-1 (`e4d65e6f`) is the pilot's training patch pattern; fresh-2 (`17c29444`)
is a second existing pattern. Both use the same eight new reset/weather seeds.
Neither the old development nor old review worlds enters the new panel statistics.
This is diagnostic follow-up, not a final untouched test: keep the small sample
and prior controller selection visible. No p-values or independence claims for
the two schedules sharing a world seed.

## Numeric result

All 32 endpoints contain established descendants (terminal tier 1). Therefore
recent live time of newly established children of established non-founder parents
is the deciding component. Percentages below apply to that component, not a
scalar conversion of the whole lexicographic fitness.

| Panel | Original renewal ticks | Winner renewal ticks | Change | Winner's pairs |
|---|---:|---:|---:|---|
| Fresh-1 | 1,272,000 | 1,194,405 | −6.10% | 5 wins / 3 losses |
| Fresh-2 | 1,242,450 | 1,431,825 | +15.24% | 4 wins / 4 losses |
| Both | 2,514,450 | 2,626,230 | +4.45% | 9 wins / 7 losses |

The full overall keys are `[1,16,2514450,13293480,42,72]` for the original and
`[1,16,2626230,14137650,46,62]` for the winner: minimum terminal tier, summed tiers,
renewal ticks, all-descendant ticks, renewing parents, new establishments.

| World seed | Fresh-1 renewal delta | Fresh-2 renewal delta |
|---|---:|---:|
| `a5a3bb6c` | +33,150 | +145,965 |
| `56b77147` | +1,065 | +321,195 |
| `03cc2e9f` | −156,345 | −110,970 |
| `b08e6511` | +26,190 | −47,745 |
| `2f7ac3ab` | +98,940 | +47,895 |
| `1a685a80` | +43,905 | −112,170 |
| `0d113458` | −78,660 | +13,515 |
| `7cfc4d9c` | −45,840 | −68,310 |

Removing **both schedules together** for `a5a3bb6c`, `56b77147`, or `2f7ac3ab`
makes the aggregate favor the original. The remaining deltas are −67,335,
−210,480 and −35,055 ticks, respectively. Removing any of the other five seeds
retains the winner. The fresh-2 `56b77147` gain alone exceeds the overall net
gain of 111,780 ticks. A positive sum hides substantial condition sensitivity.

## What the cohort data explains

The scorer now has an independent host-side explanation layer, without changing
the score: each eligible child records confirmation time, parent class, available
time through day 190, credited live time, natural/patch death and follow-up fate.
Four confirmation-time bins reconcile exactly with each native C score. Numeric
lineage IDs are never treated as paired identities across divergent controllers.

| Confirmation-window measure | Original | Winner |
|---|---:|---:|
| New establishments, including founder offspring | 72 | 62 |
| Children eligible for later-generation renewal credit | 60 | 58 |
| Available ticks after confirmation, summed over credited children | 3,802,965 | 3,693,225 |
| Credited live ticks | 2,514,450 | 2,626,230 |
| Available ticks lost after death before the window ends | 1,288,515 | 1,066,995 |
| Credited children alive at day 190 | 36 | 39 |
| Credited children naturally dead / patch-dead by day 190 | 9 / 15 | 5 / 14 |

The net gain reconciles as **221,520 fewer lost ticks minus 109,740 fewer
available ticks = 111,780**. This is an arithmetic attribution, not a causal
claim about water uptake, light, spacing or specific neural parameters. The
winner produces slightly fewer credited children but retains more observed
post-confirmation live time overall. Availability mixes child count and birth
timing; it is not a matched lifespan experiment.

The distinct **seed-purchase cohort (158,190], followed through day 192** has:

| Seed-cohort measure | Original | Winner |
|---|---:|---:|
| Purchases | 4,125 | 4,088 |
| Germinations | 109 | 79 |
| Expiries | 4,016 | 4,009 |
| Children surviving their first full day | 71 / 109 (65.14%) | 60 / 79 (75.95%) |
| First-day natural failures / patch-censored | 37 / 1 | 18 / 1 |

Every purchased seed resolves and every germinated child has complete potential
first-day follow-up. Fewer recruits with a better survival fraction is not the
same as more successful recruits. These counts differ from the confirmation
window because the cohorts select by different timestamps. No additional site,
water or light telemetry was collected; the data does not establish why fewer
seeds germinated.

### A deliberately important founder distinction

Under fresh-2 / `56b77147`, both controllers have four new establishments.
The original's four are direct offspring of surviving founders, so its renewal
component is **zero**, despite ongoing reproduction and 621,060 descendant ticks.
The winner's four have established non-founder parents, giving **321,195 renewal
ticks**. This follows the frozen objective's preference for continued generations;
it is not missing births or an extinction claim. The original retains three
species here while the winner ends with flowers alone.

### Why the earlier review result was negative

The original pilot's saved review pairs are reanalyzed separately, not added to
the new panel. For `72657632`, the winner has two germinations and two established
children from the seed cohort versus eight germinations and four establishments
for the original. Its confirmations arrive around days 172.03 and 186.89;
the original also has early successes around 160.91 and 166.89. The winner's
credited children survive through day 190, but fewer and later recruits leave
80,985 renewal ticks versus 215,670. One winner child dies during follow-up,
which is recorded separately and does not erase its earlier observed time.

For `6c696665`, the winner instead establishes three children rather than two,
with two much earlier confirmations, raising renewal ticks 77,460 → 166,065.
This is a concrete explanation of the opposing score outcomes, not proof of
their underlying resource/collision causes.

## Diversity and visual review

Single-species endpoints increase from **7/16 to 12/16**. Two original-controller
worlds retain all three species; none of the winner's does. Single-founder-family
endpoints increase from **5/16 to 7/16**. Those are final living populations, not
a claim that every other species has vanished from the seed bank or that earlier
diversity never existed. Diversity is diagnostic, not rewarded by v2.

The [gallery](pilot-validation-gallery.md) shows the predeclared largest gain and
loss from each schedule, original on the left and winner on the right. It includes
the flower-only winner against a mixed original garden. These are deliberately
outcome-selected day-192 snapshots, not representative samples or a substitute
for the full cohort records. All eight images match evaluator checkpoints and
repeat pixel-for-pixel in independent native replays.

## Validation and cost

All **143 CTests** pass: default 47, pilot environment 40, seed-reserve bank-8 28,
bank-16 28. Nine new pure-Python cases test attribution/window/parent boundaries,
malformed scores and fixed panel coverage; native integration also checks the
second patch identity while rejecting it under the original pilot's default.
The original pilot still verifies unchanged. No C or firmware source changed.

Every one of the 32 native trials matches Python scoring and an independent
day-192 replay. All ledgers, contribution sums, pairs, leave-one-seed-out results
and historical-review explanations reproduce on verification. Executable/model
hashes match the frozen pilot; source/input hashes remained stable during runs.
Collection refuses existing/out-of-scope targets and publishes no complete
manifest until the full panel and required images pass.

Serial collection took **148.95 seconds**, including independent final replays
for every trial and double-rendering eight selected frames. The 32 scored native
calls totaled **60.66 seconds**, median **1.90 s** per 192-day trial. The frozen
bundle contains 105 artifacts / **13.42 MiB**, excluding its manifest. This is
host experiment throughput, not measured device FPS. No new native extinction
or seed-only terminal case appeared; synthetic coverage remains relevant there.

## Next discussion

There is useful selectable variation, but not a stable winner across conditions.
Avoid another objective rewrite just to reverse these particular rankings. Before
another training run, decide whether coexistence is a requirement or whether
dominant specialists are acceptable: the current objective explicitly favors
later-generation persistence, not diversity. If diversity remains diagnostic,
a small training pilot using multiple development seeds **and both schedules**,
plus a separate predeclared review panel, is the next practical experiment.
If coexistence matters, agree on how to evaluate it before adding reward terms.
Neither option is implemented here; both model files remain frozen.

## Reproduce or verify

The original full pilot bundle is required for collection. Its exact native
binaries already include the optimized, assertion-enabled UBSan build; this
follow-up needs no new build or host dependencies beyond the existing tools.

```sh
docker compose run --rm firmware python3 -W error sim/garden_pilot_validation.py \
  --output artifacts/garden-pilot-validation-repeat
python3 -W error sim/garden_pilot_validation.py \
  --output artifacts/garden-pilot-validation-v1 --verify
python3 -W error benchmarks/garden-longevity/review-pilot-validation.py \
  --bundle artifacts/garden-pilot-validation-v1 --export artifacts/paired-review
```

Verification rescans the saved evidence without running new simulations. Export
produces portable JSON, a labeled gallery and eight native PNGs under a fresh
prefix. Sources/protocol are frozen in the raw bundle; report/export code was
added afterward. Work remains uncommitted on `green-garden`; no push or deployment.

Bundle manifest SHA-256:
`72abe5ba419b280ad02c5a9dd912b06f4caf27d6f08132d683b966824d161815`.
