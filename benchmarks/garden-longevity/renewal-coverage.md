# Broader world coverage: modest review gains, uneven robustness

The fixed 8/16-world comparison improves final review minimum-period credit by
**2.75% in R1 and 7.54% in R2**. R1's small gain reverses under one schedule and
one blocked seed omission; R2's holds under both schedules and all omissions.
Both wide finalists also beat the original on this fresh review panel. This is
encouraging evidence for broader coverage, not a uniform improvement or proof
that transfer is solved.

[All paired scores, cohorts and provenance](renewal-coverage-summary.json) ·
[Both generation galleries and all 256 screenshots](renewal-coverage-gallery.md) ·
[Fixed protocol](renewal-coverage-protocol.md)

## What changed

**Narrow (N)** uses the existing eight training worlds. **Wide (W)** adds eight
predeclared worlds, for sixteen. Both use the same individual bounded-renewal
selector; these are not the earlier v2/renewal objective arms. The complete
R1/R2 narrow searches and their independent repeats are reused from the verified
[replication](renewal-replication.md), without selecting a different generation.

Each wide run starts from original `dc5e849d`, using the corresponding unchanged
mutation stream (`d4146f83` / `2700a5a8`), three generations of three offspring,
32 parameter mutations per offspring, and the same strict-improvement/tie rules.
The first three mutant bytes and their original-world histories reproduce N
exactly; subsequent parents can differ through selection. R1 chooses the same
first-generation mutant; R2 W retains the original while R2 N accepts a mutant.

Both arms keep training schedules `a3b7e953` / `50a32378` and review schedules
`05d87ca0` / `b69a372e`. Eight fresh review worlds, crossed with both review
schedules, evaluate every G0–G3 champion of both arms and replicas. Review never
selects parents, extends the budget or replaces G3 with an earlier champion.
The fresh world-seed literals had no matches in the declared local audit before
the [issue #30 protocol](https://github.com/aortez/toy-factory/issues/30#issuecomment-5738582048)
and code were written. The review schedule seeds were already inspected.

Native binaries/configuration are exact copies, not rebuilt. Ecology remains
512 nodes/eight plants/eight seeds, rainfed-crowded, wide dispersal, headroom
uptake, selective maintenance, night-growth veto and ordinary patch deaths.
No gardener, irrigation, interventions, changed neural interface or inherited
plant NN. Runs stop at day 192, below the known 256-day age boundary. The four
bounded periods, full-day confirmation, 32-day credit cap and separate follow-up
rules are unchanged. Native v2 (158,190] remains a diagnostic view.

Candidate/mutation budgets are matched, **not evaluation compute**: N evaluates
16 world/schedule conditions per candidate, W 32. Review always has sixteen
conditions. Own-training raw sums are not directly comparable across arms.

## Primary and mandatory control comparisons

All final review models have the same bounded survival prefix, `[1,64]`.
The first distinguishing component is the sum of each condition's minimum-period
credit. Percentages below concern that component; paired outcomes use the full
lexicographic key. Omissions remove a world seed under both schedules together.

| Comparison | Minimum-credit change | Wins / ties / losses | Schedule groups | Blocked seed omissions |
|---|---:|---|---|---|
| **R1 W3 / N3** | **+2.75%** | **9 / 0 / 7** | Review-1 loses; review-2 wins | Seven win; omit `5a30b7f3`: loss |
| **R2 W3 / N3** | **+7.54%** | **10 / 0 / 6** | Both win | All eight win |
| R1 N3 / original | +23.57% | 11 / 0 / 5 | Both win | All eight win |
| R1 W3 / original | +26.97% | 11 / 0 / 5 | Both win | All eight win |
| R2 N3 / original | −1.97% | 5 / 0 / 11 | Review-1 loses; review-2 wins | Six lose; two win |
| R2 W3 / original | +5.42% | 11 / 0 / 5 | Both win | All eight win |

R1 W/N schedule deltas are **−53,310 / +186,585** minimum-credit ticks. R2's
are **+226,425 / +63,090**. Both wide/original gains hold across schedules and
omissions, but this does not erase R1's fragile advantage over the narrow model.
R2 N/original changes sign when either `e5fb561f` or `836f4103` is omitted.
These are finite-panel sensitivities, not confidence intervals or independent
replications of the environmental result.

Other score components do not improve uniformly:

| Final W/N comparison | Minimum bounded credit | Total bounded credit | Native v2 late-renewal credit |
|---|---:|---:|---:|
| R1 | +2.75% | −1.88% | −11.84% |
| R2 | +7.54% | +3.65% | +1.16% |

R1's old late-window loss holds under every seed omission; its schedule groups
disagree. R2's small late-window gain also has opposing schedule signs and
reverses under two omissions. V2 survival prefixes tie at `[1,16]`. The declared
primary prioritizes minimum bounded credit before total credit, and is not
replaced after seeing these tradeoffs. Both full score views remain in the data.

## Every generation, including retained models

One credit tick is a 60 Hz logic tick; one garden day contains 3,840 ticks.
Training means below divide by 16 for N and 32 for W; exact rational values are
saved. Review sums all use the same sixteen conditions. Training means still
describe different world sets, so compare each with its own original baseline.

| Replica / arm / generation | Model CRC | Own-training mean minimum credit | Review minimum credit | Review total bounded credit |
|---|---|---:|---:|---:|
| Both N0 | `dc5e849d` | 252,576.56 | 3,918,450 | 23,458,335 |
| Both W0 | `dc5e849d` | 274,009.69 | 3,918,450 | 23,458,335 |
| R1 N1 | `a14ea8b7` | 289,667.81 | 4,490,850 | 23,599,845 |
| R1 N2 | `7ce0ed84` | 299,300.63 | 4,841,895 | 24,601,185 |
| R1 N3 | `7ce0ed84` | 299,300.63 | 4,841,895 | 24,601,185 |
| R1 W1 | `a14ea8b7` | 280,844.06 | 4,490,850 | 23,599,845 |
| R1 W2 | `0f4f52e0` | 283,819.69 | 4,564,545 | 24,106,935 |
| R1 W3 | `502e34a2` | 296,106.56 | 4,975,170 | 24,137,730 |
| R2 N1 | `f51cb1d4` | 280,577.81 | 4,623,900 | 23,535,255 |
| R2 N2 | `caaf9cbe` | 287,528.44 | 4,755,135 | 25,929,000 |
| R2 N3 | `01b9d94a` | 297,749.06 | 3,841,410 | 22,914,735 |
| R2 W1 | `dc5e849d` | 274,009.69 | 3,918,450 | 23,458,335 |
| R2 W2 | `e3eda9f7` | 282,817.03 | 3,988,890 | 22,014,000 |
| R2 W3 | `c9ea07fd` | 291,314.06 | 4,130,925 | 23,751,975 |

R2 N2 again reviews much better than N3 (+21.35% versus original, compared with
N3's −1.97%), despite N3 improving its declared training score. It is not
retrospectively promoted. The W/N generation paths also are not a uniform W
dominance: R2 W's earlier generations review below N's. The primary remains the
predeclared final-vs-final comparison.

The added training worlds expose an important remaining tradeoff. W3's own-panel
gain over original is **8.06% / 6.32%** for R1/R2, but its two equal-size subsets
behave differently:

| Wide model / original | Original eight worlds | Added eight worlds |
|---|---:|---:|
| R1 W1 | +14.69% | −7.93% |
| R1 W2 | +14.82% | −6.03% |
| R1 W3 | +13.47% | +3.45% |
| R2 W1 | 0.00% | 0.00% |
| R2 W2 | +20.83% | −11.84% |
| R2 W3 | +23.02% | −7.97% |

Both W3 original-subset gains hold under both schedules and every omission.
R1's added-subset gain holds under both schedules but reverses when `42f07d93`
is omitted. R2's added-subset loss holds under **both schedules and all eight
omissions**. Sum-based selection can still trade losses in one part of the
training panel for larger gains elsewhere; broader sampling is not a worst-case
guarantee. This result does not authorize changing that aggregation rule.

## Survival, variety, cohorts and visual review

All 256 generation-review records have established descendants at the scored
period endpoints and no zero-credit periods. Their day-192 gardens retain five
to eight living plants. Repeated/unchanged champions are included; these are not
256 independent environmental conditions.

Final diagnostics cover the same sixteen review conditions per column:

| Diagnostic | Original | R1 N3 | R1 W3 | R2 N3 | R2 W3 |
|---|---:|---:|---:|---:|---:|
| Single living species at day 192 | 8 | 8 | 10 | 8 | 9 |
| Single living founder family at day 192 | 5 | 3 | 5 | 2 | 1 |
| Positively credited late-window children | 68 | 54 | 58 | 60 | 66 |
| Those children alive at day 190 | 42 | 43 | 40 | 45 | 49 |
| Descendant seed purchases in (158,190] | 4,128 | 4,109 | 4,106 | 4,101 | 4,081 |
| Those seeds germinating by follow-up | 106 | 74 | 95 | 91 | 78 |
| Those seeds producing full-day survivors | 73 | 54 | 61 | 60 | 67 |
| Those seeds expiring without germination | 4,022 | 4,035 | 4,011 | 4,010 | 4,003 |
| Natural first-day failures | 33 | 20 | 34 | 29 | 10 |
| First-day patch-censored seedlings | 0 | 0 | 0 | 2 | 1 |

The child and purchase cohorts concern native **(158,190]**, not all four bounded
periods. Confirmation-based children and purchase-based seeds differ through
carry-in and follow-up; they are not interchangeable. There are no pending or
horizon-censored purchase outcomes in these final/original cohorts. R2 N's two
patch-censored cases occur in review-2 `d0e9cf34` and `f28238c7`; R2 W's occurs
in review-2 `836f4103`. Full histories retain these outcomes explicitly.

Both wider finalists have more single-species worlds than their narrow controls.
Founder-family retention changes in opposite directions, and cannot stand in
for species variety. Better minimum credit alone does not establish a richer
ecosystem. Both complete contact sheets were visually checked: many reviewed
gardens remain dominated by tall flower stems, with other worlds retaining low
canopies or mixed forms. Retained-model columns repeat exactly. The images show
structure, not proof of reproductive health or resource-level causation.

## Verification and provenance

**114 focused Python tests pass**, including fourteen new coverage tests for
the fixed design, reuse map, immutable profiles, equal per-condition means,
subset/omission logic, command identities/budget, no narrow training calls,
common-prefix bytes, tampering rejection, capture-independent concurrent search
and contact-sheet pixels/row identities. The new suite is registered with CTest;
native CTest suites were not rebuilt/rerun for this Python-only extension.
The previous replication and its portable gallery reverify.

Exactly **2,084 new native calls** completed: 640 wide training trials, 640 full
capture-disabled repeat trials, 36 mutation calls, 256 fresh review trials and
512 image replays. Another 640 narrow trial histories and 36 mutation records
are copied from the pinned replication, not executed again. No extra training,
conditions, captures or horizons were added.

Both wide searches reproduce model bytes, native histories, RNG/parents, scores
and champion sequences with captures disabled. Reused narrow histories match
their source, common prefixes match on original worlds, and original controls
agree across arms/replicas. Native identities, follow-up, no-intervention checks,
C/Python v2 agreement, bounded-credit oracles/projections and credit additivity
pass. All 256 frames agree with ledger endpoints, independent pixels and PNG
conversion; both contact sheets regenerate exactly. Exact command budget,
source/input freezing, full reanalysis and portable export checks pass.

Recorded collection/per-replica verification wall time is **2,050.60 seconds
(34.18 minutes)** with two replica jobs concurrently; R1/R2 record 2,038.02 /
2,050.18 seconds. This excludes initial input verification/copying and final
bundle revalidation/export. It is not a controlled parallel-speedup benchmark,
nor an equal-compute 8/16-world comparison.

Ignored raw bundle: `artifacts/garden-renewal-coverage-v1`, **3,665 artifacts /
702,825,897 bytes**, excluding its manifest. It freezes current sources, exact
native sources/configuration and executables, protocol, copied controls, candidate
models, full histories/repeats, images and command/timing logs. Portable data,
two contact sheets and all 256 PNGs match it. Committing the notes does not upload
the ignored raw evidence. Manifest SHA-256:
`c18b16c04a80f5d94973e8f06d7e1ffdafcd8df011f83ca133c3ed917023d780`.

```sh
python3 -W error sim/garden_renewal_coverage.py \
  --output artifacts/garden-renewal-coverage-v1 --verify \
  --check-export benchmarks/garden-longevity/renewal-coverage
```

## What this establishes, and next

W improves the predeclared final comparison in both mutation streams on this
fresh review panel, more convincingly in R2 than R1. There is only one added-world
panel and one shared review panel, using previously inspected schedule seeds.
The replicas are independent mutation streams, not independent environmental
samples. World seeds change startup, traits, RNG and weather together. None of
this isolates weather or establishes optimal coverage size or broad qualification.

In particular, unchanged R1 N3 now beats original by 23.57%, despite losing on
the preceding review panel. That reversal is a panel change, not an improvement
caused by this training experiment. The earlier failure conditions still matter.

Next propose a **frozen-finalist check on the earlier world/schedule cross**:
evaluate the two new W3 models there and reuse the original/N3 controls already
measured. No more training is needed to ask whether the old transfer failures
actually improved. Agree the exact calls/captures before running it. Do not
retrospectively choose R2 N2, alter the score, add a diversity reward, enlarge
search or promote a controller from this result.

Checkpoint remains `bbb6307` on `green-garden`. The A/B, replication, transfer
and coverage work remain uncommitted. No default/firmware changes, model
promotion, deployment, commit, push, PR or qualification milestone.
