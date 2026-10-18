# Arbitration follow-up: supply, establishment and turnover

**The day-128 failure is a gap between generations, not a shortage of seeds.**
The /35 cases reveal two different problems: a long wait for germination in
single /35, and repeated first-day failures in multi /35. Improving first-day
survival does not by itself guarantee continuous established descendants.

This is an offline diagnosis of the [arbitration screen](landing-arbitration.md):
all 12 worlds, both arms, 24 complete histories and 96 scoring periods. It runs
no new simulation or training and changes no controller, ecology, score or
device firmware. The screen's failed retention gates remain failed.

## The single /34 day-128 gap

Times below are Garden days; plant IDs belong only to the eligible arm of
`single-s6d697834-live--rainfed-crowded-seasonal-940cfdc4`.

| Time | Observed event |
|---|---|
| 104.852–104.855 | Plants 25–28 are born; all survive their first day. |
| 126.625–126.813 | All four die, aged about 21.8–22.0 days. |
| 126.813 | The last established descendant dies. Eight banked seeds remain. |
| 127.066–127.074 | Three replacements (29–31) germinate. |
| 127.438–127.609 | All three die before their first-day confirmation. |
| 127.852–127.855 | Plants 32 and 33 germinate; both survive their first day. |
| 128.000 | Checkpoint: two young plants, three seeds, no established descendant. |
| 128.852 | Plant 32 confirms; established-descendant presence resumes. |

The gap is exactly `[486960,494790)` logic ticks: **2.0391 Garden days**.
There are 3–8 banked seeds throughout it. Some of the gap has no living plant,
but it is never biologically empty. The veto arm instead has established
plants 28 and 29 alive at day 128; these IDs are not matched individuals across
arms.

The three failed seedlings have measured first-day resource shortages:
29 dies short of energy and water; 30 and 31 die short of energy. Their deaths
occur at sun phases 220, 184 and 176, when even unattenuated sunlight is below
the photosynthesis threshold. Their energy accounts reconcile:

| Plant | Initial energy + collected | Growth spending | Paid upkeep | Final |
|---|---:|---:|---:|---:|
| 29 | 64 + 131 | 120 | 75 | 0 |
| 30 | 64 + 119 | 135 | 48 | 0 |
| 31 | 64 + 121 | 144 | 41 | 0 |

These are observed budgets, not proof that stopping a particular growth
decision would rescue them. None crosses below one maintenance payment at a
growth purchase before its first energy shortage; the shortage develops over
time. Nor can these first-day traces identify what killed the **older** plants:
adult resource histories were not recorded. Do not label those deaths as water,
energy or winter-caused from their timing alone.

There is also a hard timing limit: with the observed births and older deaths
fixed, saving the first replacement wave would produce its earliest
confirmation at **128.066**, still after the checkpoint. A seedling-only rescue
would shorten the gap but would not remove this terminal failure. Earlier
recruitment or longer overlap with the older generation is needed under those
fixed timings; a new policy could also change the trajectory.

## The opposing /35 outcomes

The following cohort is births in **(126,158]**, with complete one-day follow-up.
It is not a count of confirmations occurring in that same window.

| Seasonal model | Veto: births / survivors / deaths | Eligible: births / survivors / deaths |
|---|---:|---:|
| Single /35 | 17 / 8 / 9 | 3 / 1 / 2 |
| Multi /35 | 14 / 1 / 13 | 11 / 5 / 6 |

**Single /35 has a germination bottleneck.** In the eligible arm, no new plant
appears between births at days 127.8672 and 169.1836: a 41.3164-day birth-to-birth
interval. At every intervening ecology sample, 7–8 seeds remain banked and
living plants remain. Thirteen seeds are purchased and twelve expire during
those no-birth samples. This is not a failure to produce seeds.

Five complete seed lifetimes fit entirely inside that interval. All five
expire after 32 days; every one of their 8,184 mature checks includes the
spacing blocker at its actual landing column (8 or 10). Other blockers overlap.
Each also has some checks with an open site elsewhere, but that diagnostic
does not prove the controller could reach that site or that a seed placed
there would survive. These five seeds establish persistent local site blockage,
not a complete explanation of every waiting seed.

**Multi /35 has many failed recruits under the veto.** Of its 14 births in
(126,158], seven die energy-short and six water-short; only one confirms.
Eligible selection has eleven births, five confirmations and six deaths
(three energy-only, three combined). These are divergent cohorts, not six
individually matched rescues. The eligible arm still has established-descendant
gaps at other times; its improvement is not uninterrupted renewal.

## Keep the whole panel in view

Between days 62 and 192, the veto has **six** established-descendant gaps and
eligible selection has **eight**, all in seasonal worlds. Their summed sample
exposures are 43,515 and 60,375 logic ticks. Every gap recovers within the saved
horizon; none is biological extinction. Only one gap per arm intersects a
scoring checkpoint, illustrating what endpoint checks do and do not measure.
These gap counts are diagnostics, not a replacement fitness function.

The seasonal loss is not just the newly noticed /34 checkpoint. Unchanged
weakest-period bounded-age credits are:

| Model | Veto | Eligible | Difference |
|---|---:|---:|---:|
| Single /33 | 125,685 | 81,315 | −44,370 |
| Multi /33 | 163,260 | 25,695 | −137,565 |
| Single /34 | 162,210 | 162,225 | +15 |
| Multi /34 | 121,620 | 10,995 | −110,625 |
| Single /35 | 185,250 | 85,530 | −99,720 |
| Multi /35 | 109,455 | 235,590 | +126,135 |

The sum falls by 266,130 ticks. The full audit retains all periods, established
deaths, seed cohorts, and the split between living descendants still earning
bounded-age credit and those that have aged out. First-day confirmation,
established presence and ongoing renewal remain distinct measurements.

## Next bounded investigation

Before another policy, add a **read-only adult resource trace** to frozen
replays of the single /34 pair around the old cohort's loss. Capture energy,
water, actual uptake, upkeep, growth/reproduction spending and stress, plus
seed blockers at the same times. Verify tracing leaves state and pixels
unchanged. That would show where reserves are lost and whether earlier
recruitment was locally blocked. A separate intervention would still be needed
to test a rescue.

Do not add an energy guard, widen dispersal, change germination timing or retrain
in that same step. The present evidence identifies seedling energy failures and
persistent blocked seed sites, but lacks the adult accounting needed to explain
the continuity failure. A later policy comparison still needs ordinary and
experimental controls and the unchanged whole-panel retention checks.

## Reproduction and evidence

```sh
make host-audit-landing-turnover \
  GARDEN_LANDING_TURNOVER_OUT=artifacts/new-turnover.json.gz
docker compose run --rm -T firmware python3 -W error \
  sim/garden_landing_turnover.py \
  --verify benchmarks/garden-seasons/landing-turnover-results.json.gz
docker compose run --rm -T firmware python3 -W error \
  sim/test_garden_landing_turnover.py
```

The Make target needs only the build image, not a native build. Output is
exclusive/no-clobber. The [portable audit](landing-turnover-results.json.gz)
recomputes from the pinned arbitration archive; no artifact-directory traces
are required. Input SHA-256:
`7e3a88e1077f0944b84c412675a6bfabc1b531da6bf21844f62be68ac7b4bec7`.
Audit SHA-256:
`3b80b7aef4a4d8337c6b0e439b016474326c7e2eb16758d144315c1cd1894f97`.

Eight tests cover exact birth/death/confirmation boundaries, credit expiry,
seed-only versus empty states, censored recovery, contained seed-mask evidence,
corrupt receipts, unchanged scores, no-clobber and byte-identical regeneration.
An independent sample-by-sample oracle checks gap coverage and bounded-age
credit across all 24 worlds; the analyzer is tested with native execution
disabled. Adult death resource causes are explicitly marked `not-recorded`.
Sample spans are `[first_tick,end_exclusive)` on the 15-tick ecology grid; an
interval reaching the horizon includes its final sample and ends at stop+15.
Birth-to-birth elapsed time and no-birth sample exposure differ by one step.
