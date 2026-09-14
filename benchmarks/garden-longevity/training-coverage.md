# Training coverage: selection changed, transfer remains weak

Doubling the development world seeds from four to eight changed which mutations
were accepted, but did not produce a reliably better controller. On the same
fresh review worlds, the broad-panel final champion is **0.95%** ahead of the
previous narrow-panel champion in renewing-child live time, yet wins only **2/8**
conditions and loses that advantage in two of four blocked seed omissions.
It remains **8.22% below the original controller**. No model is promoted.

[Frozen protocol](training-coverage-protocol.md) ·
[All-generation and narrow-reference gallery](training-coverage-gallery.md) ·
[Portable scores, comparisons and cohort attribution](training-coverage-summary.json)

## Controlled experiment

Same original model `dc5e849d`, native executables, mutation RNG `6d697833`,
32 mutations per offspring, three offspring per generation, three generations,
fitness, clocks and host ecology. The only training change was adding four
world seeds to the previous four, crossed with both existing schedules.
Four fresh review seeds are separate from both training and old review seeds.

The frozen narrow champion `449c35fe` was also evaluated on these fresh review
worlds. It was never a new search candidate or a generation champion. This
matched comparison avoids treating results from different review panels as
evidence that broader training helped.

Budget: 160 development trials, 160 exact capture-disabled repeat trials,
32 generation review trials/captures, eight narrow-reference trials/captures.
All **360 scored trials** and **40 required native images** completed. The
duplicates are reproducibility checks, not independent search observations.
All conditions, including failed and unchanged cases, are retained.

The first four model files (original plus three first-generation mutations) and
all 32 native outputs on their common conditions match the preceding narrow
pilot's fingerprints exactly. Therefore the first selection difference is due
to the additional training conditions, not a changed executable or random stream.

## Additional coverage rejects the earlier first-generation win

The earlier accepted mutation `g1-c2` / `5f8c5519` has:

| Training seed block | Renewal change vs original | Wins / losses |
|---|---:|---:|
| Original four seeds × two schedules | +7.24% | 5 / 3 |
| Added four seeds × two schedules | −16.82% | 3 / 5 |
| Full eight-seed panel | −5.34% | 8 / 8 |

The larger panel rejects all three first-generation mutations and retains the
original. Generation 2 consequently mutates the original instead of the narrow
run's first-generation winner. Later model bytes differ as expected because
their parents differ. This is the effect of selection, not a determinism failure.

## Generations and matched review

All search-generation champions retain established descendants in every training
and review endpoint. Renewing-child live time is the first changing aggregate
fitness component; percentages below refer to that component, not a scalar reward.

| Generation | Champion / CRC | Training renewal ticks | Change vs original | Fresh review renewal ticks | Change vs original |
|---:|---|---:|---:|---:|---:|
| 0 | initial / `dc5e849d` | 3,208,110 | — | 1,602,570 | — |
| 1 | initial / `dc5e849d` | 3,208,110 | 0% | 1,602,570 | 0% |
| 2 | g2-c2 / `556a5dd2` | 3,239,805 | +0.99% | 1,535,280 | −4.20% |
| 3 | g3-c2 / `c7c1b31e` | 3,632,220 | +13.22% | 1,470,900 | −8.22% |
| Historical narrow reference | `449c35fe` | Not reevaluated on this training panel | — | 1,457,100 | −9.08% |

Final training gains are positive on both original and added seed blocks:
**+21.87% / +5.32%**, with **7/8 / 4/8** paired wins respectively. The total
training gain survives all eight leave-one-world-seed-out omissions. This is
training-panel consistency, not generalization.

Final review comparisons:

| Baseline / schedule | Broad-final renewal change | Broad-final wins / losses |
|---|---:|---:|
| Original, fresh-1 | −30.05% | 0 / 4 |
| Original, fresh-2 | +15.19% | 3 / 1 |
| Original, both | −8.22% | 3 / 5 |
| Narrow final, fresh-1 | −18.49% | 0 / 4 |
| Narrow final, fresh-2 | +19.51% | 2 / 2 |
| Narrow final, both | +0.95% | 2 / 6 |

Blocked omissions remove both schedules for the specified seed. The review loss
versus the original remains negative in all four omissions. The small +13,800
tick gain versus the narrow final becomes:

| Removed review world seed | Remaining broad-minus-narrow renewal ticks |
|---|---:|
| `eb300b12` | −68,835 |
| `1824c139` | +54,870 |
| `4d5f9ee1` | +86,505 |
| `fe1dd56f` | −31,140 |

The protocol's aggregate comparison is narrowly positive, but schedule/pair/
omission checks do not support calling it reliable. One search stream and four
review seeds do not establish whether broad training generally helps or hurts.
The schedules are familiar, not held-out environmental patterns.

## More credited recruits, but worse retention

On this fresh review panel, the broad final has more eligible recent children
than the original but loses more of their potential live time after death:

| Confirmation-window measure | Original | Broad final | Narrow final |
|---|---:|---:|---:|
| Credited later-generation children | 29 | 34 | 33 |
| Available post-confirmation ticks | 2,040,690 | 2,338,110 | 2,148,405 |
| Observed credited live ticks | 1,602,570 | 1,470,900 | 1,457,100 |
| Ticks lost after death | 438,120 | 867,210 | 691,305 |
| Credited children alive at main-window end | 22 | 21 | 22 |
| New establishments, including uncredited founder offspring | 33 | 36 | 36 |

Relative to original, available time increases **297,420** ticks while death
losses increase **429,090**: exact net **−131,670**. Relative to narrow, available
time increases **189,705**, losses increase **175,905**: exact net **+13,800**.
This explains the arithmetic, not the resource cause or matched-individual
lifespans. Founder offspring, confirmation timing and subsequent natural/patch
deaths remain distinct in the complete per-child summary.

For the separately selected purchase cohort (158,190], followed to day 192:
original / broad / narrow produce **42 / 47 / 44** germinations and **31 / 33 / 33**
confirmed children, with **11 / 14 / 11** natural early failures. There are no
pending or horizon-censored purchases. These confirmation counts differ from
the table because cohort membership is by seed purchase time rather than child
confirmation time. More purchases or initial establishment alone would miss
the later live-time loss.

All-descendant review occupancy is 6,972,915 / 7,112,025 / 7,085,145 ticks for
original / broad / narrow. The higher occupancy of both trained controllers
does not imply better continuing renewal under the unchanged objective.

## Diversity and visual review

Single-species living endpoints: original **2/8**, broad final **5/8**, narrow
final **5/8**. All eight broad-final review worlds retain two living founder
families; original/narrow each have two single-family worlds. Species count,
founder-family count and active renewal are different diagnostics, not bonus points.
Living endpoint counts do not establish seed-bank extinction.

The gallery contains eight fixed rows with columns **generation 0 / 1 / 2 / 3 /
narrow reference**. The first two columns intentionally repeat: their model
files, review ledgers and raw pixels are identical. Other columns show real
shape/composition changes, including branching and thin flower-dominated gardens.
All 40 images are native 240×240 shared-renderer output at day 192; snapshots
are not proof of sustained genealogy or early-lifecycle behavior.

## Rejected extinction and correctness

Mutation `g3-c1` / `9afd8001` becomes extinct on `f9bd207c` under both schedules.
Last death is tick **6840**; final state has two offspring births, seven deaths,
zero plants/seeds/nodes. Its world key is `[-1,0,0,0,0]` and aggregate
`[-1,12,3201345,11792220,49,70]`, so selection rejects it at the first component.
Both repeats agree. Separate post-collection production replays also match
world hash **`b9f9e912`**, framebuffer CRC **`03d208b6`**. This is one seed's
failure under two schedules, not two independent world-seed failures. The
resource cause was not investigated; native seed-only continuation is separate.

All **147 CTests** pass across four existing configurations (48/41/29/29).
The mixed-runner unit suite now has 13 tests, adding immutable profile/split
checks, complete 16-condition coverage, separate original/added comparisons
and non-selecting frozen-reference diagnostics. Both old and new bundles
verify after the refactor; old exported scores, cohorts, diagnostics and timings
are unchanged. No C, firmware, native executable or ecology edits were made.

The runner rechecks all 360 complete ledgers against Python fitness, generation
ancestry and RNG, exact capture/no-capture equality, common-prefix fingerprints,
reference identity, all replay checkpoints and raw/PNG conversion. All 40 frames
independently reproduce byte-for-byte. Source/settings are frozen before collection;
full reanalysis must pass before publication of a complete manifest.

## Reproduction and operational cost

```sh
python3 -W error sim/garden_mixed_training.py --study coverage --output artifacts/NEW_COVERAGE_RUN
python3 -W error sim/garden_mixed_training.py --output artifacts/garden-training-coverage-v1 --verify
python3 -W error benchmarks/garden-longevity/review-mixed-training.py --bundle artifacts/garden-training-coverage-v1 --export artifacts/NEW_REPORT_PREFIX
python3 -W error benchmarks/garden-longevity/review-mixed-training.py --bundle artifacts/garden-training-coverage-v1 --extinction-check artifacts/NEW_EXTINCTION_CHECK
```

The original pilot and frozen narrow-pilot bundles are required for collection.
The default collection profile remains the prior narrow `mixed` study; verification
selects its fixed profile from the saved rule. No arbitrary seed tuning/resume
or worker pool is introduced. Reporter/gallery machinery is shared between the
two profiles; no copied second training implementation or global-setting patching.

Complete collection took **839.29 seconds** (~14 minutes), with **540 files /
77.60 MiB**. The 160 development native calls total **309.45 seconds**, median
**1.955 s**, range **0.292–3.391 s**. Regression tests overlapped the start and
some timings varied with host load: these are operational observations, not
isolated throughput benchmarks or measured device FPS.

Bundle: `artifacts/garden-training-coverage-v1`, manifest SHA-256:
`a9142bff1570b3912b7f7d5dc71dbf4575c3db6df10249cf9b3539643abaf460`.
Supplementary verification: `artifacts/garden-training-coverage-extinction-v1`.
The report was added after the frozen collection; no previous bundle was changed.

## Decision and next discussion

Keep the original controller and unchanged objective; do not promote either
trained final. Coverage demonstrably filtered an early narrow-panel win, but
its final matched advantage is tiny and seed/schedule-sensitive. Increasing
training depth or coverage again is not automatically justified by this run.

Next discuss an **offline time-window stability check using the saved lifetime
records**: are these controllers consistently better/worse over several declared
late windows, or are rankings driven by which renewal/death events fall in this
particular window? That could distinguish persistent behavior differences from
timing sensitivity without another search, new simulation, or silently changing
fitness. Predeclare windows before analysis, keep the existing result primary,
and do not select a favorable window afterward. No such check was run here.

No commit, push, model promotion, device deployment or new qualification
milestone follows from this bounded experiment.
