# Renewal objective replication: training gains do not transfer

The [fixed replication](renewal-replication-protocol.md) **does not reproduce the
earlier objective advantage**. The bounded-renewal-selected finalist loses to its
persistence-v2 counterpart on fresh review minimum-period credit in both
independent mutation streams: **−10.9% in R1 and −8.8% in R2**. Both review
schedules and every blocked seed omission agree within each replica. Keep the
objective experimental; investigate transfer before increasing search effort.

[All paired scores, cohorts and provenance](renewal-replication-summary.json) ·
[Both generation galleries and all 128 native screenshots](renewal-replication-gallery.md)

## What changed, and what did not

R1 (`d4146f83`) and R2 (`2700a5a8`) are independent mutation streams. Each starts
matched A/v2 and B/bounded-renewal searches from original `dc5e849d`, with three
generations of three offspring and 32 parameter mutations per offspring. The
first three mutant bytes and evaluated worlds agree within each A/B pair.
Subsequent parent choices may diverge. Strict improvements select; ties retain
the incumbent, then the first canonical better child.

Both replicas share eight fresh training world seeds crossed with two fresh
patch schedules. Four separate fresh review seeds use two different schedules,
absent from training. Neither the world seeds nor patch seeds overlap between
roles. Seeds, comparisons and budget were fixed before execution and recorded
on [issue #30](https://github.com/aortez/toy-factory/issues/30#issuecomment-5659128069).
Review never chooses parents, extends search or triggers restarts. Shared review
worlds are not independent environmental samples across replicas.

Native tools, original model and simulation configuration are exact copies from
the preceding A/B. The 512-node/eight-plant/eight-seed rainfed ecology is unchanged:
wide dispersal, headroom uptake, selective maintenance, night-growth veto and
ordinary recurring patch deaths. No gardener, irrigation, founder removal,
changed observation/action contract or plant-specific neural inheritance.
Changing world seeds changes seeded trajectories, not the climate rules.

The objectives are unchanged. A scores (158,190] with two-day follow-up. B uses
four 32-day periods from day 62 to 190, each with its own follow-up, first-day
confirmation rules and 32-day post-confirmation credit cap. Its key prioritizes
terminal survival, then the sum of each world's minimum-period credit, then
total credit. There is no hard zero-gap gate, diversity reward or opportunity
normalization. All worlds stop at day 192, below the known 256-day age boundary.

## Every generation under both score views

Values are credited logic ticks; one day is 3,840 logic ticks / 256 ecology
steps. Training sums cover 16 conditions, review sums eight: their magnitudes
are not directly comparable. All champion survival prefixes tie, `[1,16]` /
`[1,8]` for v2 and `[1,64]` / `[1,32]` for B. The displayed components are the
first that distinguish these champions, not scalar replacements for the full
lexicographic keys. Complete keys, total bounded credit and rejected candidates
remain in the portable data.

| Replica / arm / generation | Model CRC | Training v2 renewal | Review v2 renewal | Training minimum-period credit | Review minimum-period credit |
|---|---|---:|---:|---:|---:|
| All G0 / original | `dc5e849d` | 3,417,360 | 1,641,075 | 4,041,225 | 2,320,020 |
| R1 A1 | `dc5e849d` | 3,417,360 | 1,641,075 | 4,041,225 | 2,320,020 |
| R1 A2 | `725f7eca` | 3,745,080 | 1,619,325 | 4,825,530 | 2,349,210 |
| R1 A3 | `46fad3c2` | 3,863,025 | 1,379,325 | 4,136,490 | 2,288,895 |
| R1 B1 | `a14ea8b7` | 3,216,870 | 1,249,095 | 4,634,685 | 1,773,615 |
| R1 B2 | `7ce0ed84` | 3,555,480 | 1,257,420 | 4,788,810 | 2,038,770 |
| R1 B3 | `7ce0ed84` | 3,555,480 | 1,257,420 | 4,788,810 | 2,038,770 |
| R2 A1 | `f51cb1d4` | 3,874,140 | 1,122,900 | 4,489,245 | 2,342,895 |
| R2 A2 | `f51cb1d4` | 3,874,140 | 1,122,900 | 4,489,245 | 2,342,895 |
| R2 A3 | `f51cb1d4` | 3,874,140 | 1,122,900 | 4,489,245 | 2,342,895 |
| R2 B1 | `f51cb1d4` | 3,874,140 | 1,122,900 | 4,489,245 | 2,342,895 |
| R2 B2 | `caaf9cbe` | 3,675,750 | 1,387,605 | 4,600,455 | 2,650,965 |
| R2 B3 | `01b9d94a` | 3,522,000 | 1,629,270 | 4,763,985 | 2,136,075 |

B improves its training minimum-period credit over the original by **18.5% in
R1 and 17.9% in R2**, while its review value falls **12.1% and 7.9%**. Improving
the declared training objective is not evidence of transfer to this review panel.
R2 B2 reviews better (+14.3% versus original) than B3, despite B3's training
improvement. We **do not retrospectively select B2** using review. R1 B3 simply
retains B2, and R2 A retains its first-generation champion through the end;
their repeated images are deliberately included.

## Primary and control comparisons

All entries use the bounded-renewal ordering on the same eight review conditions.
Omissions remove one world seed under both schedules together. They measure
sensitivity, not independent repetitions or confidence intervals.

| Comparison | Minimum-period change | Paired wins / ties / losses | Schedule aggregates | Blocked seed omissions |
|---|---:|---|---|---|
| **R1 B3 / A3** | **−10.9%** | **3 / 0 / 5** | Both lose | All four lose |
| **R2 B3 / A3** | **−8.8%** | **3 / 0 / 5** | Both lose | All four lose |
| R1 B3 / original | −12.1% | 2 / 0 / 6 | Review-1 loses; review-2 wins | All four lose |
| R2 B3 / original | −7.9% | 3 / 0 / 5 | Both lose | Three lose; omit `beda710e`: win |
| R1 A3 / original | −1.3% | 4 / 0 / 4 | Review-1 loses; review-2 wins | Two lose; two win |
| R2 A3 / original | +1.0% | 4 / 0 / 4 | Both win | Three win; omit `abf7af73`: loss |

R1 B/A schedule deltas are **−216,600 / −33,525** minimum-period ticks. R2's are
**−44,550 / −162,270**. Every individual pair and omission is retained, including
the worlds where B improves. Do not combine the two replicas into sixteen
independent review worlds: the underlying eight conditions and original control
are shared.

The old late-window view is different: R1 B loses to A in aggregate (4/8 paired
wins), while R2 B gains **45.1%** over A (7/8 wins, both schedules and all omissions
positive). Nevertheless every final model is below the original on that old
late-renewal aggregate. R2's late-window improvement over A does not rescue its
predeclared multi-period loss. An endpoint or late-window-only interpretation
would miss this distinction.

## Survival, cohorts and variety

All original/final review worlds retain established descendants at the scored
endpoints, with **no zero-credit periods**. The primary losses are quantitative
renewal losses, not extinctions, missing follow-up or calendar-gap failures.

| Diagnostic across eight review worlds | Original | R1 A3 | R1 B3 | R2 A3 | R2 B3 |
|---|---:|---:|---:|---:|---:|
| Single living species at day 192 | 1 | 5 | 5 | 4 | 4 |
| Single living founder family at day 192 | 1 | 3 | 2 | 1 | 3 |
| Positively credited late-window children | 37 | 40 | 30 | 33 | 40 |
| Those children alive at day 190 | 24 | 25 | 20 | 20 | 26 |
| Descendant seed purchases in (158,190] | 2,068 | 2,064 | 2,034 | 2,052 | 2,071 |
| Those seeds germinating by follow-up | 44 | 73 | 40 | 42 | 58 |
| Those seeds producing full-day survivors | 36 | 42 | 32 | 33 | 40 |
| Those seeds expiring without germination | 2,024 | 1,991 | 1,994 | 2,010 | 2,013 |

The last six rows concern the native **(158,190]** cohort, not all four B periods.
Children are confirmation-based; seeds are purchase-based and followed through
day 192. Carry-in and follow-up explain different counts. R1 B has one confirmed
child without positive main-window credit. No purchase cohort has pending,
horizon-censored or first-day patch-censored outcomes. Natural first-day failures
are 8 original, 31 R1 A, 8 R1 B, 9 R2 A and 18 R2 B. Full individual child/death
and seed-fate records remain available; higher germination alone is not success.

Neither selector preserves the original species variety in this panel. Founder
families tell a different story and are not interchangeable with species counts.
Both full galleries were visually checked: R1 B shifts many scenes toward tall
flower stands, while R2 changes between flower and bushier forms across generations.
Matching unchanged-model columns repeat exactly. Images show structure, not
proof of reproduction or which resource caused the changes.

## What this establishes, and the next question

The prior pilot's +18.2% B/A gain is **not a repeatable advantage in this fresh
panel**. The selector is measurable and can improve training credit, but the
training/review gap is substantial. This is not proof that bounded renewal is
universally worse: there are only two search streams, one shared environmental
panel and a small fixed mutation budget. Fresh worlds and fresh patch schedules
change together, so this experiment does not isolate which axis exposes the gap.
It also does not separate weather variation from the other effects of a world seed.

Next discuss a **frozen-model transfer diagnostic**, with no additional training:
cross the existing training/review world sets with the existing training/review
schedule sets. Reuse the two already measured combinations; measure the two
missing combinations for the original and four finalists. That can distinguish
sensitivity to world conditions, patch schedules and their combination before
changing fitness, adding diversity constraints or broadening training. Do not
promote R2 B2 after inspecting review, adopt a hard gate or tune away this result.

## Reproduction and verification

The explicit immutable study profile now carries separate training/review patch
schedules and a per-search mutation seed. Native command validation, review
capture, selection, diagnostics and reanalysis all use the declared role. Old
default records and scoring outputs remain unchanged. Two complete replicas run
concurrently in private directories; each search/world remains serial, with no
mutable global RNG or profile switching. This is not a general parallel trainer.

**56 default and 51 experimental CTests pass**, including eight new profile,
schedule-routing, concurrent-isolation, repeated-search and rejection tests.
Previous mixed, coverage and A/B bundles still verify, including the old portable
A/B export. No C, simulation-core or firmware changes were required.

Exactly **1,736 native processes** completed: 1,408 ledger trials, 256 frame
replays and 72 mutation calls. Recorded collection wall time is **1,586.37 seconds
(26.44 minutes)**, excluding initial input verification/copying and final bundle
verification. R1/R2 recorded 1,544.13 / 1,586.13 seconds while running concurrently;
this is not a controlled parallel-speedup benchmark.

All four complete capture-disabled searches reproduce model bytes, full native
ledgers, RNG/parent history, scores and champion sequence. Original training and
review controls agree across all four searches; each replica's common mutation
prefix agrees across A/B. Every bounded period matches its sampled credit oracle
and independent legacy projection. All **128 PNGs** match ledger endpoint hashes
and independently repeated raw pixels. Frozen-input/source checks, complete
bundle reanalysis and portable-export verification pass.

Ignored raw bundle: `artifacts/garden-renewal-replication-v1`, **2,256 artifacts /
409,765,392 bytes**, excluding its manifest. It freezes previous/native and current
runner sources, protocol, inputs/configuration, all candidate models, full ledgers,
images, native commands and timings. Portable results and 128 PNGs are prepared
for the repo; ignored raw evidence is not uploaded by committing these notes.
Manifest SHA-256:
`8cc60dbe89f9040457f4abd60e81b2c3f5379dac6987b5b3deb872dcc870a45f`.

```sh
python3 -W error sim/garden_renewal_replication.py \
  --output artifacts/garden-renewal-replication-v1 --verify \
  --check-export benchmarks/garden-longevity/renewal-replication
```

Prior checkpoint remains `bbb6307` on `green-garden`; the preceding A/B and this
replication remain uncommitted. No extra search, default-objective adoption,
ecological change, model promotion, deployment, commit, PR or push. Environment
qualification remains open.
