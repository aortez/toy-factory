# Frozen-model transfer: the world panel matters, schedules interact

Both bounded-renewal finalists beat the original on the **training worlds under
either schedule set**, but lose on the **review worlds under either set**.
Changing disturbance schedules alone does not explain the failed replication.
The primary B/A comparison is less uniform: R1 loses when either axis changes;
R2 keeps its advantage on training worlds with review schedules, almost ties on
review worlds with training schedules, and loses on the full review cross.

This supports testing broader development-world coverage before changing the
objective. It does **not** identify weather as the cause or prove a universal
advantage/disadvantage for either selector. These are small, previously inspected
panels, and world seeds change startup, inherited traits, RNG and weather together.

[Complete paired data and exact contrasts](renewal-transfer-summary.json) ·
[All 40 fixed native screenshots](renewal-transfer-gallery.md) ·
[Predeclared protocol](renewal-transfer-protocol.md)

## Fixed design, no new training

The [replication](renewal-replication.md) supplied the original and four unchanged
finalists, exact native binaries, and verified diagonal histories. The protocol
was recorded on [issue #30](https://github.com/aortez/toy-factory/issues/30#issuecomment-5738421067)
before collecting the missing cells. No earlier-generation finalist was substituted.

| Model | Source candidate | CRC |
|---|---|---|
| Original | R1 A initial | `dc5e849d` |
| R1 A | g3-c2 | `46fad3c2` |
| R1 B | g2-c1, retained at G3 | `7ce0ed84` |
| R2 A | g1-c2, retained at G3 | `f51cb1d4` |
| R2 B | g3-c3 | `01b9d94a` |

A was selected by persistence-v2; B by the individual bounded-renewal objective.
All models use the same unchanged 512-node/eight-plant/eight-seed rainfed ecology,
wide dispersal, headroom uptake, selective maintenance, night-growth veto and
ordinary patch deaths. No gardener, irrigation or intervention. All runs stop at
day 192, below the known 256-day age boundary. Both scoring views and their
follow-up rules remain unchanged; no scalar replacement or new gate is introduced.

| Cell | World seeds | Patch schedules | Conditions/model | Evidence |
|---|---|---|---:|---|
| TT | Eight training | Two training | 16 | Reused |
| TR | Eight training | Two review | 16 | New + full repeat |
| RT | Four review | Two training | 8 | New + full repeat |
| RR | Four review | Two review | 8 | Reused |

These are matched resets, not mid-run schedule switches. Five models × 48
conditions gives **240 unique outcomes**: 120 reused and 120 newly measured.
The two model replicas share conditions and original controls; they are not
independent environmental samples.

## Primary: B versus A, separately by replica

Percentages compare the sum of per-world minimum-period credit within each
cell. Paired counts use the complete lexicographic key. Every model ties on
terminal survival: bounded prefixes `[1,64]` for TT/TR and `[1,32]` for RT/RR.
Thus credit is the first differing component here. Do not compare raw sums
between the 16-condition and eight-condition panels.

| Cell | R1 B/A minimum-credit change | R1 wins / ties / losses | R2 B/A minimum-credit change | R2 wins / ties / losses |
|---|---:|---|---:|---|
| TT | +15.77% | 12 / 0 / 4 | +6.12% | 9 / 0 / 7 |
| TR | −5.78% | 6 / 0 / 10 | +11.15% | 10 / 0 / 6 |
| RT | −22.57% | 1 / 0 / 7 | −0.27% | 4 / 0 / 4 |
| RR | −10.93% | 3 / 0 / 5 | −8.83% | 3 / 0 / 5 |

R1's TR, RT and RR losses each hold under both schedules and every blocked
world-seed omission. Its TT aggregate gain survives all omissions, although
train-2 alone favors A. R2's TR gain and RR loss hold under both schedules and
every omission. Its RT result is effectively a fragile near-tie: schedules
disagree, and three of four omissions turn positive. R2's TT gain reverses when
`0cfc84ff` is omitted. These sensitivities are retained, not filtered away.

For additive cross-cell diagnostics, let each cell's difference be the
candidate-minus-control minimum-credit sum divided by its condition count.
The runner preserves exact rational numerators/denominators. Rounded credit-tick
differences per condition are:

| Contrast | R1 B−A | R2 B−A |
|---|---:|---:|
| TT mean difference | +40,770.00 | +17,171.25 |
| TR mean difference | −17,595.94 | +27,176.25 |
| RT mean difference | −74,846.25 | −665.63 |
| RR mean difference | −31,265.63 | −25,852.50 |
| Schedule-set shift on training worlds: TR−TT | −58,365.94 | +10,005.00 |
| Schedule-set shift on review worlds: RR−RT | +43,580.63 | −25,186.88 |
| World-set shift under training schedules: RT−TT | −115,616.25 | −17,836.88 |
| World-set shift under review schedules: RR−TR | −13,669.69 | −53,028.75 |
| Interaction: (RR−RT)−(TR−TT) | +101,946.56 | −35,191.88 |

Schedule effects depend on the world set and model pair; the interaction signs
even differ between replicas. R1's interaction stays positive under all twelve
paired seed omissions. R2's turns positive under one omission. The full data also
retain every individual world's schedule-set shift. Omissions remove both
schedule conditions from both cells containing that world seed. They are
descriptive sensitivities, not independent repetitions or confidence intervals.

## Mandatory original-model controls

All four finalists are compared with the same original, including the A models
whose changes contribute to B/A differences. Percentages again concern minimum
bounded credit, not total bounded credit or the old late-window score.

| Finalist / original | TT | TR | RT | RR |
|---|---:|---:|---:|---:|
| R1 A | +2.36% | +40.06% | +20.73% | −1.34% |
| R1 B | +18.50% | +31.96% | −6.52% | −12.12% |
| R2 A | +11.09% | +12.22% | −10.79% | +0.99% |
| R2 B | +17.88% | +24.73% | −11.03% | −7.93% |

Both B models gain on TT/TR and lose on RT/RR. Their gains on training worlds
hold under both schedules and every blocked seed omission. Their review-world
losses are not all omission-robust: removing `58e36558` flips each RT comparison,
and removing `beda710e` flips R2 B's RR comparison. However, each B/original
**world-set contrast stays negative under all twelve paired omissions, under
either schedule set**. That is the most consistent descriptive transfer pattern
in this cross, not a causal decomposition.

The original itself has higher normalized minimum credit on review worlds than
training worlds under either schedule set: TT/TR/RT/RR means are 252,576.56 /
217,247.81 / 274,700.63 / 290,002.50 ticks. Calling the review panel universally
"harder" would therefore be misleading. Its interaction with the controller matters.

The unchanged v2 late-renewal component tells a different story:

| Comparison | TT | TR | RT | RR |
|---|---:|---:|---:|---:|
| R1 B / A | −7.96% | +14.20% | +5.91% | −8.84% |
| R2 B / A | −9.09% | −5.75% | −10.27% | +45.09% |
| R1 A / original | +13.04% | −16.09% | −18.63% | −15.95% |
| R1 B / original | +4.04% | −4.17% | −13.82% | −23.38% |
| R2 A / original | +13.37% | +0.76% | −8.31% | −31.58% |
| R2 B / original | +3.06% | −5.03% | −17.73% | −0.72% |

All v2 survival prefixes also tie within each cell. This view covers (158,190]
rather than four bounded periods; its relative wins do not override the declared
primary comparison. Both full keys, all total-credit components, schedules,
per-condition pairs and omissions are available in the portable summary.

## Survival, cohorts, variety and images

All 240 outcomes retain established descendants at every scored period endpoint;
none has a zero-credit period. At day 192, every garden has six to eight living
plants. These transfer losses are quantitative renewal differences, not extinctions.

Variety does not improve uniformly. Single-species and single-founder-family
counts at day 192 are shown separately, with the denominator in the cell label:

| Cell | Original species / families | R1 A | R1 B | R2 A | R2 B |
|---|---|---|---|---|---|
| TT (16) | 11 / 7 | 12 / 8 | 9 / 8 | 9 / 1 | 8 / 7 |
| TR (16) | 10 / 5 | 12 / 8 | 7 / 5 | 9 / 1 | 11 / 5 |
| RT (8) | 5 / 3 | 4 / 3 | 6 / 2 | 3 / 2 | 4 / 4 |
| RR (8) | 1 / 1 | 5 / 3 | 5 / 2 | 4 / 1 | 4 / 3 |

The full native late-window child and seed-purchase cohorts are retained for
every model/cell. As a compact check, these are positively credited children
and full-day survivors from seeds purchased in (158,190], followed to day 192:

| Cell | Original children / seed survivors | R1 A | R1 B | R2 A | R2 B |
|---|---|---|---|---|---|
| TT (16) | 69 / 74 | 67 / 67 | 75 / 72 | 73 / 70 | 66 / 72 |
| TR (16) | 63 / 61 | 50 / 51 | 65 / 64 | 61 / 61 | 69 / 73 |
| RT (8) | 38 / 39 | 35 / 37 | 33 / 34 | 34 / 36 | 33 / 42 |
| RR (8) | 37 / 36 | 40 / 42 | 30 / 32 | 33 / 33 | 40 / 40 |

Confirmation-based children and purchase-based seeds are different cohorts;
carry-in and follow-up explain different counts. Neither is the four-period
bounded-credit score. There are no pending or horizon-censored purchase outcomes.
One first-day patch-censored seedling occurs for R1 A in RT,
`train-1.0d983a80`; it is retained explicitly. All germination, expiration,
natural-failure, credited death-state and credit-time records remain available.

The fixed gallery uses the first canonical world seed of each set, both schedules
and all five models, with no outcome-based image choice. All forty frames were
visually inspected. For example, R1 B's anchored training-world stands mix low
canopies and tall stems, while its review-world stands are dominated by tall
flower stems. The world/schedule combinations also change the other controllers'
forms. These endpoint images show structure, not which resource caused the
score changes or whether a visually full garden reproduces well.

## Verification and provenance

**100 focused Python tests pass**, including fifteen new transfer cases covering
fixed model provenance, cell/reuse coverage, exact command budget, unequal-size
normalization, interactions, paired omissions, native repeat rejection, frame
identity/PNG checks and concurrent private model jobs. The new test is registered
with CTest; the native CTest suites were not rebuilt/rerun for this Python-only
extension. The previous replication and its portable gallery reverify.

Exactly **300 native processes** completed: 240 trials (120 primary + 120 complete
repeats) and 60 image replays (30 primary + 30 repeats). Another 120 diagonal
histories and ten independently repeated frames were reused and hash-checked.
New full native JSON repeats are byte-identical. All forty images match ledger
endpoints, raw/PNG conversion and independent pixels; the sheet is regenerated
and byte-checked. Both score views, sampled bounded-credit oracles, legacy
projections, identities, follow-up and no-intervention checks pass. Source and
input hashes stayed unchanged throughout collection.

Collection took **353.05 seconds (5.88 minutes)** with at most two model jobs
concurrent; collection plus analysis took **367.01 seconds**. These exclude
initial input verification/copying and final bundle verification, and are not
a controlled parallel-speedup benchmark. No additional native calls were made
for export or reanalysis.

Ignored raw bundle: `artifacts/garden-renewal-transfer-v1`, **579 artifacts /
149,829,355 bytes**, excluding its manifest. It includes the current runner/source
snapshot, exact previous native sources/configuration and binaries, five models,
protocol, full histories/repeats, frames, command log and timings. Portable results,
gallery and forty PNGs match the verified evidence. The raw bundle is not uploaded
by committing the notes. Manifest SHA-256:
`0422c3be1c55801ce921014f5314f6cecd655ea34345f140522a15de15b42279`.

```sh
python3 -W error sim/garden_renewal_transfer.py \
  --output artifacts/garden-renewal-transfer-v1 --verify \
  --check-export benchmarks/garden-longevity/renewal-transfer
```

## Next discussion

Propose one coverage-only training A/B: keep the bounded-renewal score, ecology,
mutation budget and schedule set fixed, and compare the existing training-world
coverage with a predeclared broader world panel. Use a separate fresh review
panel that never chooses parents; the now-inspected transfer conditions are
development evidence, not a fresh final test. Agree the exact seeds, process
budget and screenshot panel before running it. The current evidence prioritizes
that question but does not prove broader coverage will fix transfer.

Do not change fitness, add a diversity reward, tune weather, retrospectively
select R2 B2 or promote a controller based on this cross. Prior checkpoint stays
`bbb6307` on `green-garden`; the A/B, replication and transfer work remain
uncommitted. No training, firmware deployment, commit, push, PR or qualification
milestone was added by this diagnostic.
