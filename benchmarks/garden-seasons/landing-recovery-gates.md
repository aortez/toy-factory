# Replacements flower, but cannot enter the seed bank

All five established early [vacancy replacements](landing-vacancy.md) develop
a ready flower within their first day. They subsequently encounter **3,394
checks where the full eight-slot seed bank is the only reproduction blocker**,
yet purchase no seeds. They are not stuck trying to finish a flower.

Their eventual deaths are a separate resource failure: all five exhaust water
near day 200. The 31 old control occupants also die from water shortage, 30
near day 200 and the remaining plant during the next drought. The receipts
show unpaid water upkeep and eight consecutive water-shortage maintenance
checks, not an inferred cause from a weather label or an empty terminal store.

This completes the [fixed tracing protocol](landing-recovery-gates-protocol.md).
All 36 replays preserve the historical JSON and endpoint pixels. No climate,
controller, scoring, capacity, mortality or firmware rule changed. These six
models share one weather seed; this is diagnosis, not ecological qualification.

## The five seedless replacements

Day numbers are absolute simulation days, not ages. The trace starts immediately
after the day-158 export and includes every focal birth and death. Single /33,
which has no established early replacement, remains in the six-pair panel.

| Vacancy world / lineage | Born | First ready flower | Died | Bank-only checks |
| --- | ---: | ---: | ---: | ---: |
| Multi /33, 28 | 159.8203 | 159.9297 | 199.9844 | 752 |
| Single /34, 26 | 172.8438 | 173.0195 | 199.9531 | 564 |
| Multi /34, 25 | 159.8320 | 159.9414 | 199.9844 | 861 |
| Single /35, 40 | 177.8438 | 178.2383 | 200.0156 | 461 |
| Multi /35, 29 | 159.8672 | 159.9844 | 199.9688 | 756 |

Each reaches 32 nodes with one flower. Four reach stem depth 15 with 16 roots;
Multi /35 reaches depth 14 with 17 roots. Recorded budget denials concern roots,
not stems. Those denials do not prevent the already-formed flowers from being
used by reproduction.

Across all five, there are **5,223 ready-flower, daylight, maintenance-cadence,
cooldown-clear visits**. Every visit sees a full bank. On 3,394 visits all other
gates pass; the rest also fail resource/stress gates. Counts are repeated checks,
not independent opportunities, available bank slots or predicted seed yields.
The audit reconstructs the bank before production from seed births/exits and
then reconciles purchases in visit order, rather than relying on the final
bank size.

This establishes a bank-access barrier in the unchanged trajectories. It does
not yet attribute that barrier to incumbent visit order rather than long seed
residence, nor predict the survival cost or germination success of extra seeds.
The five plants' reproduction debits remain exactly zero.

## What happens around day 200

The recorded climate has a four-day drought over **[196,200)**. The five
replacements enter day 196 with 493–500 stored water, below the 512-unit cap.
They then receive zero water income until death and spend 128 water per full
day on maintenance: two units on each of 64 daily maintenance steps. Growth
and reproductive water spending are zero over that interval.

For example, Multi /33 lineage 28 has this complete balance:

| Day interval | Starting water | Uptake | Paid upkeep | Ending water |
| --- | ---: | ---: | ---: | ---: |
| [196,197) | 497 | 0 | 128 | 369 |
| [197,198) | 369 | 0 | 128 | 241 |
| [198,199) | 241 | 0 | 128 | 113 |
| [199,death] | 113 | 0 | 113 | 0 |

Its final eight maintenance checks all flag water shortage. At death, water
upkeep due is two and paid is zero. Energy is 256 before maintenance, pays
four, and the remaining **252 is terminal discard**, not upkeep or energy
starvation. All five replacements have the same terminal energy/water receipt.
The post-death active-leaf count of zero reflects death flags, not prior loss
of the living canopy's eight active leaves.

The old controls show the same mechanism:

| Control world | Old occupants at day 158 | Death days | Terminal shortage |
| --- | ---: | --- | --- |
| Single /33 | 5 | 199.9063–199.9844 | Water, all five |
| Multi /33 | 5 | 199.8750–200.0469 | Water, all five |
| Single /34 | 5 | 199.9063–200.0938 | Water, all five |
| Multi /34 | 6 | 199.9375–199.9688 | Water, all six |
| Single /35 | 5 | 199.8906–200.0156 | Water, all five |
| Multi /35 | 5 | Four at 199.9063–199.9375; lineage 24 at 215.8438 | Water, all five |

All 31 terminal receipts have water income zero, water upkeep due two and
paid zero; all final eight maintenance checks flag water shortage alone.
Their energy before terminal maintenance ranges from 156 to 256, and each
pays its four-unit energy upkeep. The old plants enter day 196 with 482–512
water. Thirty receive no water income during [196,200); the late survivor
is the exception below. None spends on growth or reproduction in that interval.

The soil's global water total need not be zero: water remains outside the
plants' usable uptake locations. A positive global total is not a resource
guarantee for a particular root system. Similarly, drought ending at day 200
does not immediately replenish every plant; some terminal shortages persist
briefly beyond that boundary.

### The late control is retained, not discarded

Multi /35 lineage 24 starts day 196 at the 512 cap, absorbs 28 more units that
day and overflows 14, leaving 14 after the four-day drought. On day 200 it has
only two shortage checks, then recovers: 753 water uptake funds 125 paid upkeep,
48 in seed purchases, 82 overflow and a final store of 512. It survives the
first death wave and reproduces.

The next drought is **[212,216)**. It starts with 479 water and receives no
uptake before dying at day 215.84375. Its stores fall 479 → 351 → 223 → 95
over the first three days. The last partial day pays the remaining 95; eight
water-shortage checks trigger death. This is not a universal day-200 kill,
age cap or unexplained disappearance.

## Next decision

Keep the ecology unchanged for now. The next bounded task is an **offline
bank-ownership and release audit** of these saved trajectories: distinguish
checks that begin full from checks where earlier parents consume a newly
released slot; identify the resident seeds' owners, ages, eventual outcomes
and posthumous contribution. Then choose whether a fair-access comparison is
warranted, judging offspring establishment rather than purchase counts alone.

There is precedent for both traps: the earlier
[rotating-order experiment](../garden-longevity/renewal-seed-order.md) improved
access without establishment, while the seasonal
[sixteen-slot screen](seed-bank-capacity.md) failed its late-renewal gates.
Neither result automatically transfers to this 32-node/spacing-placement
panel, and neither justifies increasing capacity again by default. The present
water deaths already supply natural turnover; they do not motivate adding an
unrelated mortality rule or changing the score.

That follow-up is now [complete](landing-bank-access.md): 3,378 focal blocks
begin full and 16 lose an opening to earlier buyers. The occupying seeds also
yield 23 posthumous births and 19 first-day survivors. The proposed next test
changes allocation order alone, leaving capacity and viability unchanged.

## Evidence and verification

- [Portable result](landing-recovery-gates-results.json.gz), SHA-256
  `3fabe95f2d3fa20c6a4d1b97074e15d98d3095f13ba038c02fdc3884044df223`.
- Local bundle `artifacts/garden-landing-recovery-gates-v1`; manifest SHA-256
  `08c27340adc56e1acff156d2a7fbcec76f3a4c2b4ef799a8f075834c1b88abb1`.
- Frozen binary SHA-256
  `8659ae843ac3cbeda04411c6f453fc2b4288ebb408de1c8244bc255893c06e0d`;
  protocol SHA-256
  `be5d750e4cae8230197473022267f717c1e7ff2262e1fec670cc3e0a06d55b22`.
- 36 full replays: traced, repeated and plain for each of twelve arms. All
  match archived complete results and day-256 framebuffer bytes. Zero new
  checkpoint or selected-image runs; reuse the [six existing galleries](landing-vacancy.md).
- 184,320 ecology samples, 884,878 living production visits and 885,063
  plant resource samples. Full offline raw reanalysis, ordered purchases,
  stage/inter-step conservation, repeated trace bytes and pixels verify.
- The bounded native collector now supports founder-only and all-plant scopes.
  Legacy founder output remains compatible; no core ecology or firmware code
  was changed for this tracing pass. The full 167-suite host regression run
  passes; focused tests also pin the frozen findings and reject corrupt
  cohorts, accounts, gates and historical parity.

Reproduce with `make host-trace-landing-recovery`, choosing a fresh
`GARDEN_LANDING_RECOVERY_OUT`. Verify without simulation:

```sh
docker compose run --rm -T firmware python3 sim/garden_landing_recovery.py \
  --verify benchmarks/garden-seasons/landing-recovery-gates-results.json.gz
# Use artifacts/garden-landing-recovery-gates-v1 for full raw reanalysis.
```
