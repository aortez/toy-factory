# High-turnover follow-up: real reproduction, short-lived adults

This is a **read-only, post-hoc diagnostic** of the [seed-bank comparison](seed-bank.md),
not a new simulation experiment. Full lifetime context is retained for all eight
runs; detailed resource tracing focuses on the `c7f54e18` reserve-aware 8/16-seed
pair. The worlds, model, policies, weather, patches and existing screenshots are
unchanged. Nothing was flashed or trained.

Progress note: [issue #30](https://github.com/aortez/toy-factory/issues/30#issuecomment-5650610170).

The larger-bank population really does reproduce across generations. However,
its strong one-day-survivor result mostly does **not** translate into persistent
adults. A repeated overnight energy failure explains most closing natural deaths.
Short lifetimes are not inherently invalid A-life behavior; the question is
whether these resource failures are the behavior we want, rather than whether
we can maximize a single survival or birth count.

## Follow offspring beyond their first day

Offspring born during days 160–192, alive strictly beyond the stated age:

| Age reached | Eight seeds: survivors / eligible | Sixteen seeds: survivors / eligible |
|---|---:|---:|
| 1 day | 7/9 | 33/38 |
| 2 days | 7/9 | 33/38 |
| 4 days | 5/9 | 18/38 |
| 8 days | 3/7 | 2/28 |
| 16 days | 1/4 | 0/16 |

Eligibility requires sufficient time from birth to the fixed day-192 horizon.
Deaths exactly at an age boundary are not survivors, matching the previous
one-day definition. Young censored plants are not counted as failures.

To remove the changing-denominator issue, restrict births to **days (160,176]**:
all have a full 16-day follow-up. The same four eight-bank offspring yield
4, 4, 3, 2, 1 survivors at ages 1/2/4/8/16. The same sixteen larger-bank offspring
yield 15, 15, 9, 2, 0. Of those sixteen, fourteen die naturally and two in fixed
patches by age sixteen days. This is not just late births being censored.

The sixteen-seed run's 16 previously reported “durable parents” remain valid
under that metric: parent and at least one child each survive a day. But six
parents are already dead when the child reaches its qualifying age, and only
one of the sixteen parents remains alive at the horizon. Seeds can outlive their
parents; the metric never required simultaneous or indefinite survival.

The other six runs are retained in [the exported summary](turnover-summary.json).
For context, closing eight-day survivors / eligible change 6/14 → 2/8 for
b61837dc/baseline, 5/10 → 4/7 for b61837dc/reserve, and 3/3 → 2/4 for
c7f54e18/baseline. These descriptive outcomes are not an independently selected
validation panel or an argument to replace the score with another single age.

## The predominant failure is at the end of the night

The larger-bank run has 37 natural deaths in days 160–192:

- **31 energy-shortage deaths**, all at sun phases 248, 252, 0, 4, 8 or 12
  (late night through early dawn). All had reproduced; median age at death is
  3.922 days. This is primarily adult turnover, not immediate seedling failure.
- **Six water-shortage deaths**: four seedlings younger than one day, plus two
  adults aged 4.266 and 7.129 days. None produced a seed in its last day.

For every one of the 31 energy deaths:

- The last sunset snapshot has 56–64 body nodes and 182–223 energy.
- Body size stays unchanged from that sunset through the last living sample.
- Growth, seed production and paid leaf renewal spend **zero** energy after
  that sunset. The nighttime growth veto is working.
- Routine upkeep is seven or eight energy every four ecology steps. Since the
  sunset snapshot is **after** its upkeep debit, 31 further payments remain
  before dawn. Each plant is already **23–66 energy short** of funding those
  payments. Dawn itself adds another upkeep debit, with little immediate income.
- Energy falls to 0–4 by the last living sample, while water remains 285–512.
  Terminal zero water is a death-state clear, not evidence that these plants
  also ran out of water.

Thirty of the 31 produced **3–6 seeds during their preceding day**. Last-day
growth and renewal spending also occur in some cases. Daylight energy income is
substantial and much overflows the 256-unit store; daytime income alone does not
guarantee energy will remain at sunset. The one exception, lineage 121, produces
no seed in its last day and still dies under-reserved. Reproduction is therefore
a promising intervention point, not a proven explanation for every failure.

The eight-bank control has four closing energy deaths and two water deaths.
Its four energy deaths have the same nighttime-budget issue, with post-sunset
shortfalls of 18–22 energy; three of those plants never reproduced. Increasing
bank capacity did not invent this failure mode, and suppressing late reproduction
alone cannot be assumed to eliminate it.

## A concrete lifetime: lineage 102

Born at tick 602445, parent 100. It produces eleven seeds over its life, including
four in its last day. The last seed is at tick 615060, sun phase 108. It dies at
tick 617340, age 3.879 days. Its final night has **no optional energy spending**.

| Tick | Sun phase | Energy | Water | Stress | Observation |
|---:|---:|---:|---:|---:|---|
| 615360 | 128 | 204 | 505 | 0 | Post-upkeep sunset; 64 nodes, upkeep 8 |
| 616320 | 192 | 76 | 505 | 0 | Nighttime upkeep consumes the stored energy |
| 616860 | 228 | 4 | 505 | 0 | Less than one full upkeep payment remains |
| 616920 | 232 | 0 | 505 | 1 | First failed payment of this night |
| 617220 | 252 | 0 | 505 | 6 | Repeated shortages |
| 617280 | 0 | 0 | 505 | 7 | Dawn arrives without recovery |
| 617340 | 4 | cleared | cleared | 8 | Death; terminal income/stores are not recoverable |

The 204 sunset energy funds only 25 complete eight-unit payments plus four
units of the next payment, versus 31 payments needed before dawn. The recorded
live-step budget reconciles exactly. No terminal-step consumption is fabricated.

## Turnover is not a single endpoint spike

Fixed 32-day windows across the same 192-day history:

| Days | Eight seeds: births / natural deaths | Sixteen seeds: births / natural deaths |
|---|---:|---:|
| 0–32 | 5 / 0 | 19 / 15 |
| 32–64 | 4 / 1 | 17 / 11 |
| 64–96 | 9 / 3 | 8 / 4 |
| 96–128 | 3 / 1 | 27 / 23 |
| 128–160 | 6 / 2 | 31 / 29 |
| 160–192 | 9 / 6 | 38 / 37 |

Scheduled patch deaths remain separate, and occupied patches can differ after
the worlds diverge. This is repeated reproduction and replacement, not merely
a batch of young plants created just before the measurement horizon. The
[existing native panels](seed-bank.md#native-visual-review) show the associated
reorganization and final large gap; no new screenshot or simulator run is needed
to audit these lifetimes.

## What the code explains—and what remains a hypothesis

The source review confirms that `energy-reserve-v1` guards **growth decisions**.
Automatic reproduction uses its own reserve rule; its desired reserve is capped
so a full mature plant can still afford a seed. That cap is intentional, but it
does not promise enough energy for the coming night. Paid leaf maintenance is
another separate consumer. The current growth-only forecast is therefore not
a shared guarantee covering all subsequent spending.

The observed sequence supports testing a **sunset-aware affordability check
before automatic seed production**, with both the model and other rules held
fixed. Compare full lifetime curves, seed/offspring output and parental survival,
including the bank-eight control and the original adverse pair. Do not reduce
everything to births or one-day survivors. This would be a new intervention
requiring discussion/approval; no new veto, size cap, lifespan, storage capacity
or model feature was implemented here.

Crucially, these traces cannot establish what the same parents would have done
without a seed debit: fewer seeds alter later competition and RNG histories.
They identify an accounting/timing failure and a testable intervention, not a
completed causal A/B. Natural lifespan limits or more energy storage would be
different experiments, not necessary conclusions from this audit.

## Reproduction and checks

New Python-only offline analyzer `sim/garden_turnover.py`, five focused unit
tests, and `review-turnover.py` verify age-boundary censoring, parent/child
qualification, malformed/truncated traces and terminal-state handling. The
embedded-C skill guided the read-only review of upkeep ordering and death-state
clearing; **no C/header, model, world or firmware source changed this turn**.
All 34 default host CTests pass, including the new analyzer test; the native
build required no recompilation. Other experimental native suites were not
rerun because their sources and execution were unchanged.

Both detailed worlds are rechecked against the prior full world/resource audit:
98306 world rows, every living-step budget, all lifetime transitions, and all
43 closing natural deaths reconcile. Saved analyses for all eight runs retain
their original one-day/durable results. An independent read-only reanalysis
reproduces the newly saved results.

Local ignored bundle: `artifacts/garden-turnover`, 17 recorded artifacts and
360 source fingerprints. Manifest SHA-256:

`4f72662238bea74e98b3c89ccbc50ef9aa6091cee5d03477ec21a59ada504703`

It freezes copies of the eight original analyses, two world traces and patch
boundaries, the input manifest, source archive and new output. Full last-day
maintenance histories, age checkpoints and daily budgets are retained; the
versioned export omits only the bulk histories. Daily occupancy in this new
trace pass is sampled **before** a same-tick patch, unlike the earlier aggregate
post-patch occupancy; it is explicitly not substituted for that old metric.

```sh
python3 sim/test_garden_turnover.py
python3 sim/garden_turnover.py --output artifacts/garden-turnover-new
python3 benchmarks/garden-longevity/review-turnover.py \
  --reanalyze --output artifacts/turnover-review-new.json
```

New output paths must not exist. No replay, training or continuation beyond the
192-day horizon occurs. The known 256-day age-counter wrap remains separate.
