# Mixed-condition training: improvement did not transfer

The three-generation pilot is complete. The final champion improves development
renewing-child live time **20.76%**, but loses **27.09%** on the separate review
panel and loses seven of eight review conditions. Keep it as experimental
evidence, not a promoted controller. Fitness, ecology and firmware are unchanged;
species/founder diversity remained diagnostic throughout.

[Frozen protocol](mixed-training-protocol.md) ·
[All-generation native gallery](mixed-training-gallery.md) ·
[Portable scores, diagnostics and lifetime attribution](mixed-training-summary.json)

## What ran

- Original model `dc5e849d`, exact binaries from the previous pilot; no native rebuild.
- Four new development world seeds × both existing patch schedules; four different
  review world seeds × the same schedules. Review never influences selection.
- Serial (1+3) search for three generations: ten models, 80 development trials.
- Generation zero and all three champions: 32 review trials and native day-192
  captures. No favorable-world filtering, missing generations or early stopping.
- Complete capture-disabled search repeat: another 80 trials, identical model
  bytes, RNG records, full scores, world hashes and champion history.
- 192 scored trials total; repeated runs are not additional independent evidence.
  All 32 review frames also reproduce pixel-for-pixel in separate processes.

Each world runs for 192 Garden days: score (158,190], fixed follow-up to day 192.
All clocks, 512-node/bank-eight capacity, rainfall, selective leaf maintenance,
no-night-growth adapter and disabled drainage/seed-reserve settings are unchanged.
These remain explicit host experiments, not device defaults or independently
evolving per-plant neural controllers.

## Training versus review

All generation champions have established descendants in every endpoint. The
first changing aggregate component is therefore renewing-child live time.

| Generation | Champion / model CRC | Development renewal ticks | Change vs original | Review renewal ticks | Change vs original | Review wins / losses |
|---:|---|---:|---:|---:|---:|---:|
| 0 | initial / `dc5e849d` | 1,530,600 | — | 2,106,780 | — | 0 / 0 (8 ties) |
| 1 | g1-c2 / `5f8c5519` | 1,641,345 | +7.24% | 1,413,240 | −32.92% | 2 / 6 |
| 2 | g2-c2 / `5c6124d9` | 1,845,495 | +20.57% | 1,348,635 | −35.99% | 1 / 7 |
| 3 | g3-c2 / `449c35fe` | 1,848,315 | +20.76% | 1,535,985 | −27.09% | 1 / 7 |

The final step improves development only 0.153% relative to generation 2.
No generation's review aggregate beats the original. The original's stronger
review baseline is visible above: raw totals should not be compared across
different panels as if they were matched worlds.

Final-versus-original schedule comparisons:

| Panel / schedule | Renewal change | Paired wins / losses |
|---|---:|---:|
| Development, fresh-1 | +17.93% | 3 / 1 |
| Development, fresh-2 | +23.22% | 3 / 1 |
| Review, fresh-1 | −24.54% | 0 / 4 |
| Review, fresh-2 | −29.53% | 1 / 3 |

Leave-one-world-seed-out checks remove both schedule conditions together.
The final development gain stays positive in all four omissions; the review
loss stays negative in all four. Thus neither conclusion depends on just one
seed in its own panel. That does **not** make four seeds per panel a large or
representative sample, nor are two schedules on one seed independent worlds.
The schedules are familiar, not held-out disturbance patterns.

Full final keys, in order `[min tier, sum tier, renewal ticks, descendant ticks,
renewing parents, new establishments]`:

| Panel | Original | Final |
|---|---|---|
| Development | `[1,8,1530600,6999480,26,34]` | `[1,8,1848315,7078410,20,33]` |
| Review | `[1,8,2106780,6954495,22,43]` | `[1,8,1535985,7122630,22,32]` |

The portable summary also retains every rejected candidate and every paired
condition, not just these aggregate values.

## What accounts for the review loss?

The unchanged per-child attribution explains the score difference exactly:

| Review confirmation-window measure | Original | Final |
|---|---:|---:|
| Credited later-generation children | 41 | 30 |
| Available post-confirmation ticks | 3,115,500 | 2,064,300 |
| Observed credited live ticks | 2,106,780 | 1,535,985 |
| Ticks lost after death | 1,008,720 | 528,315 |
| New establishments, including uncredited founder offspring | 43 | 32 |
| All-descendant live ticks | 6,954,495 | 7,122,630 |

Available time falls 1,051,200 ticks while death losses fall 480,405 ticks:
net renewal change is **−570,795**. Fewer credited children and their confirmation
times leave less available renewal time; lower subsequent death losses do not
offset that. This is a population/cohort decomposition, not a matched-individual
lifespan experiment or evidence that a particular resource caused the difference.
Overall descendant occupancy actually rises 2.42%, illustrating why simply
keeping a mature-looking garden alive is not the selected renewal objective.

For the separately defined seed-purchase cohort in (158,190], followed through
day 192: purchases change 2,068 → 2,054; germinations 58 → 35; confirmed children
40 → 30; natural early failures 18 → 5. No pending, patch-censored or horizon-
censored cases occur in this purchase cohort. The survival fraction improves
(40/58 → 30/35), while the actual number of successful recruits falls. Its
confirmation count differs from the table because selection is by purchase time,
not child confirmation time.

## Diversity and pictures

Final development single-species endpoints increase **2/8 → 7/8**, but review
single-species endpoints stay **5/8 → 5/8**. Single-founder-family review worlds
decrease **3/8 → 2/8**. Generation 2 has fewer single-species review endpoints
(4/8) yet the worst review renewal score. These diagnostics do not support a
simple rule that monocultures alone explain the failed transfer.

The [gallery](mixed-training-gallery.md) shows genuine shape/species-composition
changes, including thin flower-dominated and broader branching gardens. Every
fixed condition is shown across all four generations. End living-species counts
are not seed-bank extinctions; snapshots are not evidence of active genealogy.
No diversity bonus, quota or tie-breaker was added.

## Real rejected extinction case

Candidate `g3-c1` / `93f6f90a` loses every living plant on world `f9bd207c` under
both schedules. Last death is tick **6780** (1.765625 Garden days); through day
192 there are six deaths, one offspring birth, zero living plants, zero seeds
and zero nodes. Its world key is `[-1,0,0,0,0]`; the eight-condition aggregate is
`[-1,4,1317540,5289810,18,26]`, so it is rejected at the first component.
This is the same seed failing twice, not two independent seed failures.

The complete search repeat reproduces both cases. After collection, an extra
independent production replay of each case also matches world hash **`3cb1e130`**
and framebuffer CRC **`03d208b6`**. This is additional rejected-case verification,
not a new scored trial, review-panel substitution or model selection. Native
extinction now has observed coverage; native seed-only continuation still does
not follow from this case. No death/resource cause was investigated here.

## Reproduce and verify

The original frozen pilot bundle is needed to collect a fresh run:

```sh
python3 -W error sim/garden_mixed_training.py --output artifacts/NEW_MIXED_PILOT
python3 -W error sim/garden_mixed_training.py --output artifacts/garden-mixed-training-v1 --verify
python3 -W error benchmarks/garden-longevity/review-mixed-training.py --export artifacts/NEW_REPORT_PREFIX
python3 -W error benchmarks/garden-longevity/review-mixed-training.py --extinction-check artifacts/NEW_EXTINCTION_CHECK
```

The verifier rechecks all 192 full lifetime/seed scores, candidate ancestry and
canonical tie handling, panel coverage, review generation identities, replay
checkpoints, native raw/PNG equality, source/input fingerprints and diagnostics.
Collection freezes inputs/source before work and publishes a complete manifest
only after full reanalysis; incomplete output is not resumable as a successful run.
The source tar records collection-time sources; this reporter and narrative were
added afterward. Re-verification uses that frozen manifest, not current-source equality.

All **147 CTests** pass: default 48, frozen-ecology host build 41, seed-reserve
eight/16-slot gates 29 each. New nine-test coverage includes fixed split/budget,
missing/extra conditions, paired seed omissions, objective precedence, diversity
not breaking ties, canonical offspring selection, capture callbacks, unchanged
champions, corrupt ancestry/RNG/selection records and review-only diagnostics.
No C source or firmware changes; native builds report no work to do.

Collection wall time: **483.51 seconds**. The 80 development native calls total
151.15 seconds (median 1.869 s, range 0.187–3.515 s; early extinction is faster).
The complete bundle has **344 files / 44.74 MiB**, including ledgers, repeated
candidate files, source snapshot and images. Regression tests overlapped the
start of collection, so these are observed operational timings, not an isolated
host-performance benchmark or measured device FPS.

Bundle: `artifacts/garden-mixed-training-v1`, manifest SHA-256:
`511b26198ed46fbe7e1a5a7893613450613f2cb24b2abea9b2f0ec5ba6fe6fb2`.
Supplementary replays: `artifacts/garden-mixed-training-extinction-v1`.

## Decision and next discussion

Do not promote the new champion or change fitness to rescue this result.
This pilot demonstrates a reproducible mixed-condition search, but not a
generalizable improvement. Four training seeds remain a small selection surface;
one trajectory does not isolate seed coverage, mutation luck, observation limits
or the finite scoring window as the cause.

The next useful direction is **broader training-world coverage before deeper
search**, with a separately declared review panel and the same small mutation
budget. Agree on that scope before running it. More generations on these same
eight conditions would optimize a target that already failed the review check.
Keep diversity diagnostic and discuss any ecology/objective changes separately.
No commit, push, controller promotion or device deployment is part of this run.
