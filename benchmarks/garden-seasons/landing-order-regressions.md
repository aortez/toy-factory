# Why rotating reproduction order regressed some gardens

The saved evidence identifies three different mechanisms, not one general
failure of rotation. S34 vacancy changes seed locations and the release/refill
sequence, then retains two incumbents through an extra drought. S35 control
still produces seeds and seedlings late in the run, but those seedlings fail
to establish. M33 control contains a genuine allocation loser despite almost
equal time at every visit rank.

This [retrospective audit](landing-order-regressions-protocol.md) uses the
previous [rotation comparison](landing-order.md) unchanged. There are no new
simulation runs, training runs, rule changes, device writes or promotions.
All twelve world contexts remain in the machine-readable summary; the three
diagnostic pairs were selected in the preceding report, not as a new
qualification panel.

## The first changed allocations

The immediately preceding saved observations and the purchase step's observed
pre-reproduction state match across each focused pair. The first changed buyer
therefore has a directly observed allocation explanation. These observations
do not prove that one purchase alone explains every later difference.

| World | Logic tick | Fixed buyer and seed column | Rotating buyer and seed column |
| --- | ---: | --- | --- |
| S34 vacancy | 649740 | Parent 18, column 11 | Parent 19, column 18 |
| S35 control | 613980 | Parent 25, column 10 | Parent 26, column 23 |
| M33 control | 610860 | Parent 19, column 20 | Parent 26, column 13 |

S/M and 33/34/35 retain the preceding report's controller labels. Parent IDs
refer to the named run. Later cross-arm births are not matched by equal IDs;
the audit records each birth seed and its within-run ancestry instead.

## S34 loses a retry sequence and gains incumbent survival

The first changed rotating seed, at column 18, expires after 32 days. Every
one of its 8,184 mature checks is blocked by both spacing and low moisture.
The corresponding fixed-order purchase at column 11 germinates. Later
allocations also differ, yielding this observed sequence:

| Tick | Fixed order | Rotating order |
| ---: | --- | --- |
| 649740 | Parent 18 buys at column 11 | Parent 19 buys at column 18 |
| 652320 | Parent 19 buys at column 16 | Parent 23 buys at column 12 |
| 656955 | First column-11 seed germinates | Column-12 seed germinates |
| 657000 | Parent 18 refills the slot at column 11 | Parent 23 refills it at column 25 |
| 660975 | Second column-11 seed germinates | No release; bank remains full |
| 661020 | Parent 18 buys at column 12 | No purchase; bank is full on entry |
| 663720 | Column-12 seed becomes the early survivor | No birth; bank remains full |

The rotating column-25 seed eventually germinates at tick 771165, so it is a
delayed recruitment source, not a failed seed. Germination frees a bank slot
even if the resulting seedling later dies. That makes the feedback between
placement, residence and future purchases important: this is not just a
different parent winning an otherwise interchangeable slot.

The fixed early cohort has two energy-shortage deaths followed by one
first-day survivor. The rotating early cohort has two energy-shortage deaths
and no survivor. The fixed survivor produces **no seeds**, so its absence
cannot directly explain the later fall from four to one new reproducing
parents through loss of its own descendants.

There is a separate turnover effect. Two incumbents persist about sixteen
days longer in the rotating run:

| Incumbent | Water entering day 196, fixed → rotating | Death tick, fixed → rotating |
| --- | ---: | ---: |
| Parent 18, column 5 | 492 → 512 | 767820 → 828840 |
| Parent 23, column 18 | 491 → 512 | 767760 → 828900 |

Both pay **zero reproduction water fees during days 196–199** in both arms.
The rotating plants also receive a little early-drought water income, finish
day 199 with six water each, and recover during day 200 before reaching the
death threshold. Their fixed counterparts exhaust water and die. The
observed difference is starting reserves and uptake, not a seed purchase
during that drought. Changed competition is a plausible contributor to the
uptake difference, but these trajectories do not isolate its cause.

At tick 771120, a fixed seed at column 7 germinates after the old occupants
have died and decomposed. The rotating seed with the same purchase parent,
tick and column remains spacing-, moisture- and light-blocked. Parent 18 is
still alive at column 5, within the three-column spacing limit. The rotating
seed ultimately expires. These are purchase-coordinate comparisons, not a
claim that post-divergence seed genomes are identical.

That fixed seed becomes a reproducing parent. Two other fixed reproducing
parents are also born at tick 771120, whereas the rotating world still has
the two incumbents then. Thus lower renewal and longer incumbent survival
coexist. A renewal-only metric should not silently call every longer-lived
adult an ecological failure.

## S35 has late births but no late establishment

Closing confirmations fall from two to zero, but the supply does not stop.
For the interval (222,254], purchases increase from ten to eleven. By day 256,
the fixed purchase cohort has two germinations, one expiry and seven pending
seeds; the rotating cohort has five germinations, one expiry and five pending
seeds. Three of those rotating germinations occur within the closing interval;
two occur later.

| Birth cohort | Fixed first-day outcomes | Rotating first-day outcomes |
| --- | --- | --- |
| Born in (222,254] | 2 survive | 3 die |
| Born in (254,256] | No births | 2 still awaiting follow-up |

The fixed late survivors appear at columns 25 and 3. Rotating seedlings at
columns 27, 12 and 27 die after 0.273, 0.289 and 0.422 garden days respectively.
The two pending seedlings at columns 12 and 27 are only about 0.137 days old
at the final snapshot. They are neither confirmed successes nor failures.

The late births in both runs trace back through the pre-switch incumbent 26,
but their subsequent parents and seed positions differ. The evidence contains
complete within-run ancestry; it does not justify pairing later plants by ID
or claiming that rotation directly killed the two fixed survivors.

**The missing evidence is the late death mechanism.** Resource and germination
traces end at day 218, before these births. The lifetime ledger establishes
their deaths, but not whether energy, water, both, growth spending or shading
caused them. The audit deliberately records the detailed resource cause as
unobserved rather than extending an earlier seedling's diagnosis to them.

## M33 really does miss its useful turns

M33 control's early rotating parent 28 receives 427–428 maintenance visits at
each of six ranks. Its four otherwise-eligible openings instead occur at
zero-based ranks four, four, three and three (fifth, fifth, fourth and fourth
in the visit order). At each one the bank begins with seven
seeds; another parent fills the last slot. All other production gates pass,
including energy and water requirements. The only failure is the now-full
bank, not an immature flower, cooldown or unaffordable seed.

| Opening tick | Parent 28 rank (zero-based) | Earlier buyer | That buyer's seed outcome |
| ---: | ---: | ---: | --- |
| 648900 | 4 | 20 | Germinates; child dies within a day |
| 649260 | 4 | 22 | Germinates; child survives its first day |
| 706920 | 3 | 22 | Expires |
| 721680 | 3 | 22 | Germinates; child dies within a day |

These are real allocation losses, but the winner's seeds are not uniformly
wasted. No receipt reveals where parent 28's unpurchased seeds would have
landed or whether their offspring would have survived. The result supports
investigating allocation timing, not assuming an alternative scheduler would
create four successful children.

## Reproducibility and checks

- [Portable audit](landing-order-regressions-results.json.gz), SHA-256
  `9163a9ba3839ecd07dcc35773d8945aa90830add3ea44e33f201a369bb6a20d6`.
- [Exact event receipts](landing-order-regressions-events.json.gz), SHA-256
  `4da3133d07920636f3bec1492943101dcba0b5219d8f64607e077efa4f68b800`.
- Protocol SHA-256
  `6047f4bbdbfaa9db8f23f566721934fd64c1635f599642c4cd0a90d2ec65749c`.

The portable event file contains 734 arm-step observations: 133 selected
ticks per S34 arm, 115 per S35 arm and 119 per M33 arm. Each observation retains
the exact stand and resource rows. Selection includes the union of relevant
events and their preceding ecology sample, not just successful purchases.
Full source trace hashes, headers, clocks and completion records are checked
when extracting. Independent event validation checks actual traversal, bank
conservation, simultaneous gates, resource debits and adjacent-step continuity.

Re-extraction from the unchanged original bundle matches exactly. Portable
recomputation preserves all twelve contexts and the prior aggregate screening
decision. Ten offline tests cover these results, ancestry links, interval
boundaries, death on the confirmation tick, censoring, corrupt receipts and
no-clobber behavior. All 171 host CTest suites pass with the working tree held
unchanged throughout the run. No firmware C source or runtime setting changes
in this audit; existing [comparison galleries](landing-order.md#saved-screenshots)
remain the visual evidence.

```bash
make host-audit-landing-order-regressions
docker compose run --rm -T firmware python3 sim/garden_landing_order_regressions.py \
  --verify benchmarks/garden-seasons/landing-order-regressions-results.json.gz
docker compose run --rm -T firmware python3 sim/garden_landing_order_regressions.py \
  --extract-from artifacts/garden-landing-order-v1 \
  --verify benchmarks/garden-seasons/landing-order-regressions-events.json.gz
```

The Make target needs no native simulator build and requires a fresh output;
override `GARDEN_LANDING_ORDER_REGRESSIONS_OUT` to choose another destination.

## Next bounded proposal

Keep rotation host-only. The next useful capture is the **unchanged S35
control pair through day 256 with detailed tracing extended from day 218 to
256**. Reproduce the existing results and pixels, retain exact repeats, and
inspect the three failed late seedlings plus both pending seedlings and the
fixed survivors. This would identify resource causes without changing the
allocation rule, ecology, training objective or controllers. Agree on its
small call budget before running it.

That closes a concrete evidence gap before choosing between seedling-budget
work, placement work or allocation changes. An opening-driven allocation
scheme remains a separate possible experiment, not a fix proven by this
audit. Broader multi-weather qualification is still required before promotion.

The [subsequent four-replay capture](landing-late-resources.md) now closes this
gap: all three late failures first suffer water shortages, with two later
also exhausting energy. Their unchanged two-root systems point toward a
bootstrap/allocation investigation, not an already-proven replacement rule.
