# Returning wide finalists to the old cross: no general transfer fix

The frozen 16-world finalists do **not** consistently repair the earlier
transfer failures. On the old review-world/review-schedule panel, R1 W3 loses
**7.73%** to N3, while R2 W3 gains **8.89%**. R2 only exceeds the original by
**0.25%**, with opposing schedule signs and two losing seed omissions. Its
late-window newly established-child credit falls and species variety worsens.
Broader training helped one search path here, not transfer uniformly.

[Complete paired data and provenance](renewal-return-summary.json) ·
[All 40 native screenshots](renewal-return-gallery.md) ·
[Predeclared protocol](renewal-return-protocol.md)

## Fixed test and reuse

N/W mean eight/sixteen training worlds with the **same bounded-renewal score**,
not the earlier v2/renewal objective arms. This check freezes original
`dc5e849d`, R1 N3/W3 `7ce0ed84` / `502e34a2`, and R2 N3/W3 `01b9d94a` /
`c9ea07fd`. Original and both narrow finalists reuse their earlier
[transfer cross](renewal-transfer.md); wide finalists come from the
[coverage comparison](renewal-coverage.md). There is no new training, mutation,
retrospective generation choice, score change or native rebuild.

Both source bundles reverified before collection. The
[issue #30 protocol](https://github.com/aortez/toy-factory/issues/30#issuecomment-5738996384)
fixed inputs, conditions, comparisons, images and calls before new outcomes.
TT/TR/RT/RR label world-set then schedule-set, using the same eight training
worlds, four old review worlds and two schedules per set. TT/TR have sixteen
conditions/model, RT/RR eight. These inspected conditions are a diagnostic,
**not a fresh qualification panel**.

Five models × 48 conditions give 240 model/world/schedule outcomes: 144 reused
controls and 96 new W outcomes, each with a complete independent repeat. The
32 W TT outcomes also exactly reproduce saved coverage training bytes.
The gallery uses the first canonical world of each set under both schedules
in every cell: 24 control frames/repeats are reused; sixteen W frames are new
and independently repeated. No captures are selected by outcome.

Ecology remains 512 nodes/eight plants/eight seeds, rainfed-crowded, wide
dispersal, headroom uptake, selective maintenance, night-growth veto and ordinary
patch deaths, without gardening or interventions. Runs stop at day 192.
The four bounded periods, full-day confirmation, 32-day credit cap and follow-up
rules are unchanged; native v2 (158,190] remains a separate diagnostic.

## Primary: old RR

All models share bounded survival prefix `[1,32]`, with established descendants
at every scored period endpoint. Percentages concern the first distinguishing
component: the sum of each condition's minimum-period credit. Paired outcomes
use the complete key; omissions drop a world under both schedules.

| Comparison | Minimum credit | Wins / ties / losses | Schedule groups | Blocked omissions |
|---|---:|---|---|---|
| **R1 W3 / N3** | **−7.73%** | 5 / 0 / 3 | Review-1 wins; review-2 loses | Three lose; omit `58e36558`: win |
| **R2 W3 / N3** | **+8.89%** | 4 / 0 / 4 | Both win | Three win; omit `0d983a80`: loss |
| R1 N3 / original | −12.12% | 2 / 0 / 6 | Review-1 loses; review-2 wins | All four lose |
| R1 W3 / original | −18.92% | 2 / 0 / 6 | Both lose | All four lose |
| R2 N3 / original | −7.93% | 3 / 0 / 5 | Both lose | Three lose; omit `beda710e`: win |
| R2 W3 / original | +0.25% | 4 / 0 / 4 | Review-1 loses; review-2 wins | Two win, two lose |

R1 W/N schedule deltas are +120,060 / −277,725 ticks; one review-2 loss
(`58e36558`, −269,355) exceeds its overall deficit. Winning five individual
conditions is compatible with losing the sum. R2 W/N gains +8,460 / +181,335
by schedule; its two `0d983a80` gains total 240,165, exceeding the overall
189,795 gain. Dropping that seed changes the result to −50,370. These are
finite-panel sensitivities, not confidence intervals or independent replications.

R2 W/original totals only **+5,850 ticks across eight conditions** (+731.25
per condition). Its schedules contribute −31,185 / +37,035. Omitting either
`0d983a80` or `abf7af73` changes the result to a loss. R1's loss to original
holds under both schedules and every omission.

## Complete world/schedule cross

Minimum-credit changes, including all mandatory controls:

| Comparison | TT | TR | RT | RR |
|---|---:|---:|---:|---:|
| R1 W3 / N3 | −4.25% | −4.64% | −10.59% | −7.73% |
| R2 W3 / N3 | +4.36% | −12.07% | +16.25% | +8.89% |
| R1 N3 / original | +18.50% | +31.96% | −6.52% | −12.12% |
| R1 W3 / original | +13.47% | +25.83% | −16.41% | −18.92% |
| R2 N3 / original | +17.88% | +24.73% | −11.03% | −7.93% |
| R2 W3 / original | +23.02% | +9.68% | +3.43% | +0.25% |

R1 W/N loses in all four cells; TT/TR/RT losses survive every seed omission,
and RT loses under both schedules. R1 W beats original on training worlds
under either schedule set, but loses on old review worlds under either set.
Its normalized review-minus-training effect relative to original remains
negative under every blocked omission for both schedule sets.

R2 W/N's TT and RT gains and TR loss hold under both schedules and every
omission. RR is positive but sensitive. R2 W/original's small RT gain also
splits by schedule and reverses under two omissions. This is neither simple
dominance nor a schedule-only explanation. World seeds jointly change startup,
traits, RNG and weather; they do not isolate a weather mechanism.

All cross-cell contrasts use exact **per-condition rational means**, not raw
16-versus-eight sums. The data retain schedule/world shifts, interactions,
per-world schedule shifts and blocked omissions under both score views.
Terminal precedence stays explicit: TT/TR prefixes are `[1,64]` for bounded
renewal and `[1,16]` for v2; RT/RR prefixes are `[1,32]` and `[1,8]`.

## The score tradeoff is real, not a repeat mismatch

| W3 / N3 | Cell | Minimum bounded credit | Total bounded credit | Native v2 late credit |
|---|---|---:|---:|---:|
| R1 | TT | −4.25% | +0.51% | −2.74% |
| R1 | TR | −4.64% | −6.64% | +11.68% |
| R1 | RT | −10.59% | −2.09% | +8.02% |
| R1 | RR | −7.73% | −5.67% | −18.11% |
| R2 | TT | +4.36% | +0.43% | +9.23% |
| R2 | TR | −12.07% | −0.86% | +6.87% |
| R2 | RT | +16.25% | +14.66% | +19.43% |
| R2 | RR | +8.89% | +7.42% | −29.15% |

Both RR W/N v2 losses survive every seed omission. R1 loses under both
schedules; R2's review-1 loss outweighs a smaller review-2 gain. R2 W also loses
29.66% to original on v2 late credit. Neither score replaces the declared
primary after seeing these differences.

Bounded credit includes eligible young descendants established before a period
starts, until their 32-day credit expires. V2 late credit counts children newly
confirmed during (158,190]. Exact RR last-period attribution:

| Model | Bounded last-period credit | Newly confirmed within period | Carry-in credit |
|---|---:|---:|---:|
| Original | 3,356,955 | 1,641,075 | 1,715,880 |
| R1 N3 | 3,177,300 | 1,257,420 | 1,919,880 |
| R1 W3 | 2,937,735 | 1,029,645 | 1,908,090 |
| R2 N3 | 3,352,665 | 1,629,270 | 1,723,395 |
| R2 W3 | 3,390,930 | 1,154,325 | 2,236,605 |

Each row reconciles. R2 W's last-period bounded gain of 38,265 combines
**−474,945 fresh ticks and +513,210 carry-in ticks**. Carry-in supplies 65.96%
of that period's credit versus 51.40% for N. This is valid under the unchanged
age-capped rule, not a scoring bug or evidence of indefinite sterile survival.
A better bounded minimum is not equivalent to more newly established late
offspring. All periods and full cohorts remain in the saved evidence.

## Previous fresh review remains separate context

The coverage review has sixteen conditions, old RR eight. Exact mean
minimum-credit ticks per condition make those denominators explicit:

| Model | Old RR mean | Coverage review mean |
|---|---:|---:|
| Original | 290,002.50 | 244,903.125 |
| R1 N3 | 254,846.25 | 302,618.4375 |
| R1 W3 | 235,138.125 | 310,948.125 |
| R2 N3 | 267,009.375 | 240,088.125 |
| R2 W3 | 290,733.75 | 258,182.8125 |

R1 W/N changes from +2.75% on coverage review to −7.73% here; R2 is positive
on both (+7.54% / +8.89%), but old RR is omission-sensitive. Original levels
and model rankings depend on the panel. These are different world sets, not a
matched cross-panel treatment effect. Already-inspected coverage review is
reused without new calls, pooled totals or generation choice.

## Survival, species and native cohorts

All 240 cross outcomes have positive credit in all four periods and established
descendants at scored endpoints; day-192 gardens retain six to eight plants.
These outcomes share world/schedule seeds, not 240 independent environments.
The following old RR diagnostics each cover eight conditions:

| Diagnostic | Original | R1 N3 | R1 W3 | R2 N3 | R2 W3 |
|---|---:|---:|---:|---:|---:|
| Single living species at day 192 | 1 | 5 | 4 | 4 | 7 |
| Single living founder family at day 192 | 1 | 2 | 0 | 3 | 4 |
| Positively credited late-window children | 37 | 30 | 33 | 40 | 32 |
| Those children alive at day 190 | 24 | 20 | 20 | 26 | 21 |
| Descendant seed purchases in (158,190] | 2,068 | 2,034 | 2,045 | 2,071 | 2,037 |
| Those seeds germinating by follow-up | 44 | 40 | 39 | 58 | 47 |
| Those seeds producing full-day survivors | 36 | 32 | 33 | 40 | 33 |
| Those seeds expiring without germination | 2,024 | 1,994 | 2,006 | 2,013 | 1,990 |
| Natural first-day failures | 8 | 8 | 6 | 18 | 14 |

These native late-window cohorts are separate from the four bounded periods.
Confirmation-based children and purchase-based seeds are different cohorts;
their counts need not match. All old RR purchase cohorts have zero pending,
patch-censored and horizon-censored outcomes. Other cells' complete cohorts
and species/family distributions remain in the paired data.

R1 W improves species/family retention relative to N on old RR while losing
credit; R2 W improves bounded credit while reducing variety. Neither implies
a general ecological improvement. The full contact sheet was visually checked:
R1's old-world anchors remain dominated by tall flower stems; R2 W switches
between those stands and lower canopies across schedules. Anchor images show
structure, not the complete diversity distribution or its cause.

## Verification, provenance and next

**126 focused Python tests pass**, including twelve new return tests covering
fixed identities, reused paths, immutable settings, old/fresh panel separation,
exact budgets/commands, tampering rejection, frame reuse, unequal denominators
and isolated concurrent jobs. The new test is registered with CTest; native
CTest suites were not rebuilt/rerun for this Python-only extension.

Exactly **224 new native processes** completed: 96 trial/repeat pairs and
sixteen image/repeat pairs. Reused ledgers match pinned scores/hashes; W TT
matches saved training bytes. Native identities, no interventions, follow-up,
C/Python v2 agreement, bounded-credit oracles, projections and additivity pass.
All forty images match ledger endpoints, independent pixels, PNG conversion
and the regenerated contact sheet. Source/input freezing, full reanalysis and
portable export verification pass.

Collection wall time with two model jobs is **205.94 seconds**; collection plus
analysis is **219.87 seconds**. These exclude initial input verification/copying
and final revalidation/export. Ignored raw bundle
`artifacts/garden-renewal-return-v1` contains **629 artifacts / 212,402,044 bytes**,
excluding its manifest, including copied inputs, native sources/configuration,
runner snapshot, models, full histories/repeats and exact command timings.
Committing notes does not upload that ignored evidence. Manifest SHA-256:
`7b20a1dc42516b6d5c13cb2e5335fea9133cb6084c7811049c3d8c263d3c2b98`.

```sh
python3 -W error sim/garden_renewal_return.py \
  --output artifacts/garden-renewal-return-v1 --verify \
  --check-export benchmarks/garden-longevity/renewal-return
```

This rejects a uniform transfer-fix interpretation, not broader coverage in
general. It does not establish that v2 should replace bounded renewal or that
diversity needs a new reward. Two search streams, one added training set and
small inspected panels cannot settle those questions. The earlier R2 loss on
the added training subset also remains.

**Proposed next discussion:** trace the largest paired gains/losses in saved
histories to confirmation timing, early survival, later deaths and species
turnover, especially R2's carry-in/fresh tradeoff. That can be an offline audit
with no new native runs before deciding whether to change training coverage or
cross-world aggregation. Do not retune scoring or extend training automatically
on these review outcomes. Defaults, firmware, ecology and models remain unchanged;
this work and earlier experiments remain uncommitted.
