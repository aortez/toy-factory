# Renewal cohort audit: timing, mortality and early species loss

The old-panel differences are not arithmetic or determinism failures. They
combine **different offspring timing, different post-confirmation losses, and
different species trajectories**. R1 W has more qualifying late children but
later confirmations; R2 W has fewer, with a larger contribution carried into
the late window. Five of R2 W's seven eventual monocultures are already present
before the first scored renewal period. Better minimum credit does not imply
more late recruitment or more variety.

[All 40 histories' attribution and timelines](renewal-cohorts-summary.json) ·
[Fixed audit protocol](renewal-cohorts-protocol.md) ·
[Prior native gallery](renewal-return-gallery.md)

## Scope and accounting

This is an **offline explanation of inspected evidence**, not a fresh test.
The pinned [return check](renewal-return.md) was fully reverified, then its
original, R1 N3/W3 and R2 N3/W3 old-RR histories were copied: five models ×
four worlds × two schedules = forty ledgers. N/W trained on eight/sixteen
worlds with the same objective. There were **zero native calls, training runs,
mutations, replays or new screenshots**. The
[issue #30 protocol](https://github.com/aortez/toy-factory/issues/30#issuecomment-5739197838)
fixed the audit before detailed cohort analysis.

All four periods, their own two-day follow-up, the 32-day credit cap, native v2
and minimum-period aggregation are unchanged. Scores, original controls, both
W/N comparisons, schedules and blocked omissions reproduce the source exactly.
The audit adds individual credit attribution, seed funnels, daily census
reconstruction and exact living-species loss/recovery events.

For fresh and carry-in children separately, each period reconciles:

`live credit = count × period width − timing removed − natural-death loss − patch-death loss`.

Fresh timing removal comes from confirmation after the window starts; carry-in
timing removal comes from the age cap/window intersection. Death losses are
accounting relative to the **actually confirmed cohort**, not causal predictions
of a world where deaths were prevented. Carry-in can include already-dead young
children with zero live credit and explicit lost credit. Early failures that
never confirm belong in separate confirmation/purchase cohorts, not this group.
All child/species/group sums reconcile. IDs are local to each history; matching
plant IDs across different models would be invalid.

## Late credit: timing matters independently of child count

The late confirmation cohort spans (158,190]. Mean confirmation day below is
computed only over eligible newly confirmed children, not all germinations.

| Model | Qualifying fresh children | Mean confirmation day | Available credit | Natural loss | Patch loss | Live credit |
|---|---:|---:|---:|---:|---:|---:|
| Original | 37 | 173.028 | 2,411,895 | 393,990 | 376,830 | 1,641,075 |
| R1 N3 | 30 | 173.564 | 1,893,915 | 77,715 | 558,780 | 1,257,420 |
| R1 W3 | 33 | 177.238 | 1,617,705 | 89,595 | 498,465 | 1,029,645 |
| R2 N3 | 40 | 175.448 | 2,235,765 | 229,125 | 377,370 | 1,629,270 |
| R2 W3 | 32 | 176.421 | 1,669,035 | 27,795 | 486,915 | 1,154,325 |

R1 W has **three more** qualifying children, but their mean confirmation is
3.674 days later. Available credit falls 276,210 ticks; smaller combined death
loss offsets 48,435, leaving the observed **−227,775** fresh-credit change.
This is not simply fewer births or worse survival.

R2 W has **eight fewer** qualifying children, confirming 0.973 days later on
average. Available credit falls 566,730 ticks. Smaller natural loss offsets
201,330, while patch loss grows 109,545: net fresh-credit change **−474,945**.
Combined post-confirmation death loss is actually smaller; it does not explain
the decline by itself. The cohort composition and its available time differ.

R2 carry-in credit, conversely, rises **513,210**: 317,040 more available ticks
plus 196,170 less death-related loss. That more than offsets the fresh decline,
leaving a last-period bounded gain of only **38,265**. These are exact identities,
not evidence of an indefinitely surviving sterile population: the age cap still
expires credit. The objective measures sustained recent descendant occupancy,
not just children newly established within one named window.

The separate late **seed-purchase** cohort tells a related, not interchangeable,
story. R2 purchases change 2,071 → 2,037, germinations 58 → 47, full-day survivors
40 → 33, and natural first-day failures 18 → 14. The germinated cohort's first-day
survival fraction is roughly 69.0% → 70.2%; fewer surviving recruits here mainly
accompanies fewer germinations, not a higher aggregate first-day failure fraction.
This does not identify why seeds expire. Both models leave most purchases expired.
Confirmation cohorts and purchase cohorts differ at boundaries and by parental
eligibility. The export retains all purchases, established-descendant purchases,
unconfirmed-descendant purchases and species partitions separately.

## Fixed explanatory extremes, with original controls

These six labels were chosen from the **already-known score deltas**, using
largest minimum gain/loss and largest v2 late loss per W/N pair, with lexical
ties. They are outcome-selected examples, not representative samples. All
conditions and controls remain in the data.

| Example | Condition | Original minimum | N minimum | W minimum | W − N minimum |
|---|---|---:|---:|---:|---:|
| R1 minimum gain | review-1 / `0d983a80` | 272,370 | 161,820 | 306,450 | +144,630 |
| R1 minimum loss | review-2 / `58e36558` | 333,255 | 437,010 | 167,655 | −269,355 |
| R1 late-credit loss | review-1 / `beda710e` | 297,825 | 223,905 | 188,880 | −35,025 |
| R2 minimum gain | review-2 / `beda710e` | 393,870 | 125,205 | 318,855 | +193,650 |
| R2 minimum loss | review-1 / `abf7af73` | 288,210 | 303,720 | 182,775 | −120,945 |
| R2 late-credit loss | review-1 / `0d983a80` | 272,370 | 245,505 | 369,030 | +123,525 |

R1's strongest gain raises (62,94] credit by **216,975**, through both more fresh
credit (+138,315) and carry-in (+78,660), despite larger patch losses. But W's
weakest period moves to (158,190]: subtract the 72,345 switch difference to get
the actual minimum gain of 144,630. Both N/W end as flower-only stands here;
original still has flowers and ground-cover.

R1's strongest loss shares the same weakest period, (62,94]. Fresh credit
falls 133,365 and carry-in 135,990. Fresh qualifying children fall five → three;
carry-in count stays four, but natural/patch credit losses rise 80,115 / 66,585.
The purchase cohort has eight → four germinations, yet three → zero first-day
natural failures. Again, fewer successful recruits need not mean worse
conditional first-day survival.

R1's largest v2 late loss is **−126,090** on review-1 `beda710e`. Here fresh
children fall four → three, while carry-in gains 180,735, so the same late
bounded period actually improves 54,645. The whole-run minimum still declines
because its bottleneck shifts elsewhere. A single endpoint/window story is
insufficient.

R2's strongest gain repairs N's (62,94] trough by **316,380**: 115,110 more
available credit plus 201,270 less patch-related lost credit. W's weakest
period shifts to (126,158], reducing the minimum improvement to **193,650**.
W is still below original's minimum, and both N/W eventually become
ground-cover-only in this condition.

R2's strongest minimum loss illustrates the opposite switch. W improves N's
weakest period, (126,158], by 43,335, but introduces a worse (62,94] trough.
On that earlier period, fresh credit falls 66,000 and carry-in 67,155; its
fresh qualifying count falls two → one, and carry-in patch loss grows despite
the same carry-in count. The new bottleneck outweighs the improvement at the
old one. W ends flower-only, while N and original retain ground-cover too.

R2's largest v2 late loss is **−191,520** on review-1 `0d983a80`: seven → three
newly confirmed qualifying children. Five carry-in children in each model yield
235,350 more live credit in W through later available credit and lower losses,
so the late bounded total rises 43,830. Yet the population changes from N's
five ground-cover plus three shrubs to W's eight flowers. Original has two
flowers and six ground-cover. This is a changed ecological trajectory, not
just relabeling identical offspring across a window boundary.

## Much of the variety difference starts early

Each row below covers the same eight world/schedule conditions. “Before day 62”
means the final living-species absence has already begun and no subsequent
recovery is observed through day 192; it is not a claim about unseen future runs.

| Model | Single-species endpoints | Of those, already single-species before day 62 | Endpoints retaining shrubs |
|---|---:|---:|---:|
| Original | 1/8 | 0 | 0/8 |
| R1 N3 | 5/8 | 4 | 0/8 |
| R1 W3 | 4/8 | 4 | 0/8 |
| R2 N3 | 4/8 | 0 | 2/8 |
| R2 W3 | 7/8 | 5 | 0/8 |

For R2 W, the early flower-only conditions begin at days **2.781 / 5.797 /
37.766** (with the first two occurring under both schedules). Its shrubs' final
living losses occur between days 1.766 and 2.047 in all eight conditions. R2 N
retains shrubs through day 192 on `0d983a80` under both schedules, so this is not
evidence that shrubs are categorically unable to survive this environment.
The startup controller/trajectory deserves inspection before adding a diversity
reward. The score can respond indirectly to startup outcomes without explicitly
protecting species retention.

Credit composition corroborates the change. R2 fresh late flower credit rises
574,170 → 710,805, ground-cover credit falls 930,345 → 443,520, and shrub credit
falls 124,755 → zero. A population-wide score improvement can accompany a major
shift in which species reproduce and survive. Founder families remain a
different quantity: two surviving flower families are still one species.

Living absence is not necessarily extinction. The audit finds 2 / 4 / 2 / 2 / 8
observed living-species loss/recovery intervals in original / R1 N / R1 W /
R2 N / R2 W. For example, original ground-cover on `58e36558` disappears at
day 2.719 with three pending seeds, then reappears at day 3.059 under both
schedules. R2 W shrubs on `0d983a80` briefly recover from seeds before the last
seedling fails. Exact event times and pending-seed counts prevent those temporary
absences being mistaken for irreversible extinction. Paired schedules sharing
early events are not independent environmental observations.

## Verification, limits and next proposal

**219 focused Python tests pass**, including eighteen new audit tests. They cover
confirmation/death boundaries, age-cap/carry-in accounting, unconfirmed parents,
earlier-period projection without future leakage, species/family separation,
same-tick replacement, seed-bank recovery, minimum switching/ties, fixed extreme
selection, offline collection/export and tampering rejection. The suite is
registered with CTest; native CTests were not rebuilt/rerun for this Python-only
work. During actual collection, native execution entry points were guarded to
raise an error if called.

All forty histories and 160 period decompositions repeat exactly. Original native
scores/checkpoints, saved cohorts, period/species partitions, minimum differences
and terminal census agree; source/input hashes, full reanalysis and portable
export verify. Analysis plus its independent repeat took **10.41 seconds**,
excluding source verification/copying and final revalidation/export.

Ignored bundle `artifacts/garden-renewal-cohorts-v1`: **49 artifacts /
43,798,285 bytes**, excluding manifest, including source snapshot, protocol,
pinned input manifest/results, copied native ledgers and audit output. The portable
JSON is 7,470,072 bytes; no new images or executables were generated. Manifest:
`4dbb7b77cd0e1d46616f99884ec48706d0ee888e653c222bbd756081677aeffa`.

```sh
python3 -W error sim/garden_renewal_cohorts.py \
  --output artifacts/garden-renewal-cohorts-v1 --verify \
  --check-export benchmarks/garden-longevity/renewal-cohorts-summary.json
```

These are conditional cohort identities and reconstructed events, not a causal
diagnosis of water, shade, energy, spacing or neural actions. The saved ledgers
do not contain those complete physical histories; “natural death” is not a
specific mechanism. Selected extremes cannot qualify an environment or model.

**Next proposal:** a short, instrumented startup comparison of original and R2
N/W on matched `0d983a80`, focusing on the first eight garden days: plant energy,
water, growth decisions and early deaths. That should test why N preserves shrubs
while W loses them, before changing fitness, adding a diversity bonus, or spending
more on training. It would require new diagnostic replays and is **not started**
by this offline audit. Firmware, ecology, scoring, defaults and model selection
are unchanged; this and earlier experiments remain uncommitted.
