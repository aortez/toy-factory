# Bounded-renewal training: encouraging pilot, not model promotion

The [predeclared A/B](renewal-training-protocol.md) is complete. Selecting with
individual bounded renewal produces **18.2% more minimum-period renewal credit**
than selecting with persistence-v2 on the fresh review panel, winning **7/8 paired
worlds**. Its **9.1% gain over the original controller** is less robust: one
schedule is slightly worse, and omitting one world seed reverses the gain.
Species variety also falls relative to the original. Keep the objective
experimental and replicate before increasing search effort or promoting a model.

[Both score views and paired evidence](renewal-training-summary.json) ·
[All 64 native generation screenshots](renewal-training-gallery.md)

## Matched experiment

Both arms start from controller `dc5e849d`, the same mutation RNG, eight training
world seeds and two existing disturbance schedules. Each makes three generations
of three offspring, using 32 parameter mutations per offspring. A selects the
unchanged persistence-v2 ordering; B selects the previously tested
[individual-minimum ordering](individual-renewal.md). The four review seeds are
separate from training and were fixed before collection; both schedules are
familiar, not held-out schedules. Review never chooses parents or extends search.

The native environment and binaries are unchanged: rainfed-crowded, 512 nodes,
eight plants/eight seeds, wide dispersal, headroom uptake, selective maintenance,
night-growth veto and recurring patch deaths. No gardener, irrigation, founder
exit, new ecological rule or changed neural interface. One shared frozen neural
controller operates each world; this is not evolution of plant-specific networks.

All worlds run through day 192. A scores (158,190] with two days of follow-up.
B uses four periods, (62,94], (94,126], (126,158], (158,190], each with its own
follow-up and 32-day post-confirmation credit cap. Its lexicographic key is:
minimum terminal tier, sum of terminal tiers, sum of each world's minimum period
credit, then total period credit. This is **not** a hard zero-gap gate or minimum
across worlds. The entire selector is the treatment; its individual components
are not isolated here. One day is 3,840 logic ticks / 256 ecology steps.

## Every generation, under both score views

Entries below are credited logic ticks, summed over 16 training or eight review
conditions; training and review totals have different denominators. All champion
survival prefixes tie: `[1,16]` / `[1,8]` under A and `[1,64]` / `[1,32]` under B.
Thus the displayed components are the first ones that distinguish these models,
not standalone scalar fitness scores. Complete keys and all candidates remain
in the paired data.

| Arm / generation | Model CRC | Training v2 renewal | Review v2 renewal | Training minimum-period credit | Review minimum-period credit |
|---|---|---:|---:|---:|---:|
| Original / A0 / B0 | `dc5e849d` | 3,208,110 | 1,662,030 | 2,876,385 | 1,379,310 |
| A1 | `dc5e849d` | 3,208,110 | 1,662,030 | 2,876,385 | 1,379,310 |
| A2 | `556a5dd2` | 3,239,805 | 1,809,780 | 3,608,670 | 1,239,495 |
| A3 | `c7c1b31e` | 3,632,220 | 1,615,380 | 3,186,945 | 1,272,915 |
| B1 | `9f694f3f` | 2,958,330 | 1,555,770 | 3,360,660 | 1,361,340 |
| B2 | `165d9670` | 3,727,860 | 1,781,940 | 3,390,975 | 1,550,085 |
| B3 | `b5670bb9` | 3,719,655 | 1,816,575 | 3,690,885 | 1,504,635 |

A retains the original in generation one; B accepts their identical first mutant.
Thereafter parent models diverge. A reproduces the previous coverage search
exactly, including every native ledger, model, mutation RNG record and champion.
Both arms reject their respective `g3-c1`, which becomes extinct on training seed
`f9bd207c` under both schedules. Matching candidate labels in later generations
do not imply matching controller bytes.

## Fresh review comparison

All wins/losses in this table use the bounded-renewal ordering. Blocked omissions
remove both schedules for one seed together; they are sensitivity checks, not
independent experiments or confidence intervals.

| Candidate versus control | Minimum-period credit change | Paired wins / ties / losses | Schedule aggregates | Blocked seed omissions |
|---|---:|---|---|---|
| **B3 versus A3 (primary)** | **+18.2%** | **7 / 0 / 1** | Both improve | All four improve |
| B3 versus original | +9.1% | 5 / 0 / 3 | Fresh-1 −8,715; fresh-2 +134,040 ticks | Three improve; omit `decad72f`: −39,105 ticks |
| A3 versus original | −7.7% | 3 / 0 / 5 | Fresh-1 falls; fresh-2 improves | Three fall; one improves |

B3's only paired loss against A3 is fresh-2 / `6d889ca1` (−68,805 minimum-period
ticks). Its fresh-1 / fresh-2 aggregate gains over A3 are +185,535 / +46,185 ticks.
Total bounded credit across all periods is 9,885,570 for B3, 9,170,025 for A3 and
8,727,225 for the original. The primary ordering still uses minima before totals.

B3 also improves the **old** late-renewal component: +12.5% over A3 and +9.3%
over the original, with 5/8 paired wins in both comparisons. Both schedule groups
and all four blocked omissions improve under that old ordering. The reported
gain is therefore not solely a different way of measuring the same selected
model, although neither scoring view establishes indefinite ecological health.

B2 has a larger review minimum-period gain over the original (+12.4%) than B3
(+9.1%), despite B3 improving the training score. We retain the declared final
model comparison, **not** retrospectively select B2 from review. One shared
mutation stream and four review seeds are insufficient to establish reliable
generalization. Familiar disturbance schedules further limit that claim.

## Survival, recruitment and variety

Every original/final review world retains established descendants at the scored
endpoints. The original has two zero-credit world-periods; A3 and B3 have none.
That is a useful observed outcome, not a zero-gap requirement encoded by B.

| Diagnostic across eight review worlds | Original | A3 | B3 |
|---|---:|---:|---:|
| Worlds with just one living species at day 192 | 3 | 7 | 6 |
| Worlds with just one living founder family at day 192 | 3 | 1 | 4 |
| Positively credited children in the native late window | 31 | 28 | 33 |
| Those children still alive at day 190 | 23 | 21 | 23 |
| Descendant seed purchases in (158,190] | 2,048 | 2,026 | 2,038 |
| Those seeds germinating by follow-up | 41 | 38 | 45 |
| Those seeds producing confirmed full-day survivors | 30 | 31 | 34 |
| Those seeds expiring without germination | 2,007 | 1,988 | 1,993 |

The last six rows describe the **native late window**, not the entire four-period
B objective. The child cohort is confirmation-based; the seed cohort is
purchase-based and followed through day 192. They differ legitimately through
carry-in, confirmation timing and follow-up. Two confirmed children each in A3
and B3 receive no positive main-window living credit. No seed-purchase cohort
has pending or horizon-censored outcomes. The saved report retains those
distinctions, early failures, deaths and every individual credited child.

B improves recruitment counts modestly without solving poor seed conversion.
It also does not preserve species variety relative to the original. Compared
with A3, B3 has slightly better species retention but worse founder-family
retention; these are distinct diagnostics. Neither is rewarded by either score.

The fixed gallery contains every arm/generation/condition at day 192, including
A's unchanged first generation. Many final scenes are dominated by tall flower
forms, while earlier scenes include more branching shapes. Images show the
changed structures, not proof of reproductive health or a causal resource story.

## Implementation, validation and provenance

Founder-independence work was committed first as **`bbb6307`**, following
`a1c419f`; neither was pushed here. This A/B work is left uncommitted for review.
The explicit selector adapter lives in the Python pilot runner. The embedded-C
guidance informed the checkpoint boundary checks; no new C or simulation-core
changes were needed. Existing runner defaults, native fitness, ecology and
device firmware remain unchanged. No controller is promoted.

**55 default and 50 experimental CTests pass**, including 13 new selector tests.
The old mixed/coverage bundle verifiers also pass. New checks cover explicit and
default selection, unknown/mixed contracts, intervention rejection, incomplete
panels/follow-up, survival precedence, ties, review isolation and mutation parents.

The declared **868 native processes** completed in **1,615.11 seconds (26.9 min)**:
704 ledger trials, 128 image replays and 36 mutations. No extra training or
post-hoc native challenges were run. Both complete capture-disabled searches
repeat model bytes, ancestry/RNG, scores, native ledgers and champion histories
exactly. All 64 required frames match their native ledger endpoints and repeat
pixel-for-pixel. All bounded periods match the sampled credit oracle and legacy
projection checks. Frozen-bundle reanalysis and portable-export checks pass.

Ignored local bundle: `artifacts/garden-renewal-training-v1`, containing 1,132
artifacts / 189,627,125 bytes excluding its manifest. It freezes the exact prior
native tools/source/configuration, original model, current runner sources,
protocol, settings, all histories/models/images, command logs and timings. The
portable summary/gallery/PNGs are included for the repo; raw ignored artifacts
are not published by committing this report.

Manifest SHA-256:
`61d464b839b2dc988c99c1adb95008b4db8b88a71808991264b5acaf08d43a3f`.

```sh
python3 -W error sim/garden_renewal_training.py \
  --output artifacts/garden-renewal-training-v1 --verify \
  --check-export benchmarks/garden-longevity/renewal-training
```

Next discuss a fixed-budget replication with independent mutation streams and
fresh world/schedule combinations, retaining both objectives and diversity
diagnostics. Do not enlarge the search, change the score or pick a controller
using this review panel. This pilot supports further objective testing; it does
not close environment qualification or authorize device adoption.
