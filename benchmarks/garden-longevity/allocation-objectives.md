# Allocation objective dry-run: useful signals, not a selected fitness

The approved offline comparison is complete. **None of these formulas is being
installed in the trainer.** A small delayed-production bonus can distinguish
equally durable productive/inactive plants, but a zero-shortage confirmation gate
rejects useful observed behavior. Always-WAIT remains the strongest aggregate
control because the alternatives die early in most of these selected cases.
That is not a reason to inflate a seed bonus until a favored model wins.

This uses the same six cases and 24 control continuations from the
[allocation challenge](allocation-challenge.md). No new native experiment,
model search, weather/price change, firmware change or screenshot capture was
performed. Existing state/CRC/resource evidence was reverified. The data had
already been inspected; definitions were frozen before this new scoring pass,
not before the original outcomes existed. This is exploratory objective design,
not held-out evaluation or a statistical policy ranking.

## Fixed definitions

The [protocol](allocation-objectives-protocol.md) defines:

- `G`: alive at first future dawn **and** age one day (0 or 1).
- `L`: fraction of shared post-birth ecology sample times alive; dead/reclaimed
  time stays in the denominator.
- `R`: seed purchases, capped at four and divided by four.
- `Q`: distinct plant-age days with a seed purchase followed by another full day
  alive **and no maintenance-sample resource shortages**, capped at four and
  divided by four. Multiple seeds in one age-day cannot multiply this credit.

Compare `G + L`, `G + L + λGR`, and `G + L + λGQ`. Nominal `λ = 1/4`; `1/8` and
`1/2` are fixed sensitivity checks. Arithmetic and ties use exact fractions;
decimals below are rounded. Roots, shoots, body size, stored resources, leaf
count, income and action frequency earn no direct points.

A case ends scoring before the first predetermined patch covering its fixed
base column, or at age eight days. Thus the rescue case has 4.585938 scored days,
the established control 7.718750, and the other four have eight. Every arm within
a case shares that same denominator, regardless of its own death. A patch does
not become natural starvation or inferred survival after censoring. Shorter
windows are not eight-day survival evidence.

## Actual control rankings

Descriptive equal-case means, nominal weight:

| Control arm | Survival | Raw seed bonus | Confirmed productive days |
|---|---:|---:|---:|
| Reference histories | 0.368629 | 0.368629 | 0.368629 |
| Wet-root control | 0.367017 | 0.408683 | 0.387850 |
| Always-WAIT | **1.933187** | **1.933187** | **1.933187** |
| Same frozen NN without bootstrap on the selected seedling | 0.693173 | 0.734840 | 0.693173 |

WAIT ranks first for all seven formula/weight combinations and all **42**
leave-one-case-out comparisons. The reference/guard/history combinations differ
by case, and the cases share seeds/history; these arm means do not identify one
deployable population policy or independent replications. No confidence interval,
weight fitting or model promotion is claimed.

Within-case behavior is more informative:

- **Wet-root opportunity:** productive root investment and WAIT have the same
  observed survival. The nominal raw/confirmed bonuses favor the producer over
  WAIT (2.25 / 2.125 versus 2.0).
- **Bank-16 rooted-water case:** the surviving fifteen-seed plant beats WAIT
  under raw seed credit (2.25 versus 2.0), but **ties WAIT under `Q`** (both 2.0).
- The other four cases contain no seed producer. Production bonuses cannot
  distinguish them; safer survival determines the result or leaves a tie.
  The established reference and WAIT remain tied despite different body sizes.

An aggregate WAIT win does not by itself invalidate an objective: a controller
combining productive success in some cases with safer behavior elsewhere might
beat it. These frozen controls do not demonstrate that such a controller is
learnable or that search would escape inactivity. A large bonus that excuses
five failed cases would conceal the problem rather than establish that evidence.

## What delayed credit actually counted

The rescue's seven seeds split into **two confirmed**, three with observed
resource shortages during confirmation, and two patch-censored. The confirmed
seeds occupy two age-day bins. No seed is labeled a natural post-purchase failure.

The bank-16 producer's fifteen seeds all encounter at least one shortage in the
observed part of their following day, so `Q` gives **zero credit**. This includes
three seeds whose complete extra day extends past the horizon: their observed
shortage is known, but their later survival is still censored, not a known death.

### Post-ranking severity check — not a fourth scored variant

The original formulas/rankings were preserved. A separate diagnostic distinguishes
resource flags from parent survival and records the complete sampled shortages:

| Producer | Parent alive one full day after purchase | Later survival censored | Shortages after first seed |
|---|---:|---:|---|
| Wet-root rescue | 5 seeds | 2 patch-censored | 3 energy-shortage checks; longest run 2, peak observed stress 2 |
| Bank-16 same-NN producer | 12 seeds | 3 horizon-censored | 8 energy-shortage checks; longest run 2, peak observed stress 2 |

The bank-16 plant also had seven consecutive water-shortage checks before its
first seed, reaching stress seven. Do not describe its whole lifetime as having
only mild shortages. After reproduction starts, its recorded energy-shortage
checks occur near dawn (sun phases 4–8), with subsequent recovery; it remains
alive at the horizon. These observations do not prove indefinite stability.

**Recommendation:** retain shortage frequency, streaks and stress as diagnostics,
but do not use *zero shortages* as an all-or-nothing definition of productive
survival. A follow-up objective could require observed parental survival after
reproduction while reporting recoverable stress separately. No revised objective
was scored or selected in response to this result.

## Arithmetic challenge cases

These are hand-built score inputs, **not native simulations or demonstrated
reachable strategies**. Nominal weight:

| Fixture | Survival | Raw seed bonus | Confirmed productive days |
|---|---:|---:|---:|
| Inactive eight-day survivor | 2.000000 | 2.000000 | 2.000000 |
| Durable producer across four days | 2.000000 | 2.250000 | 2.250000 |
| First-day seed burst, then early natural death | 1.144043 | 1.394043 | 1.144043 |
| Survives; seeds only in one early burst | 2.000000 | 2.250000 | 2.062500 |
| Unconfirmed seed burst at the horizon | 2.000000 | 2.250000 | 2.000000 |
| Confirmed producer that dies near the horizon | 1.997559 | 2.247559 | 2.247559 |

Delayed credit fixes the immediate-burst and end-of-window examples, and age-day
capping distinguishes repeated production from a single burst. **It does not
guarantee that every surviving inactive plant outranks every naturally dying
producer.** A sufficiently late collapse still wins under both additive bonuses
at all three weights. That is an explicit objective tradeoff, not an arithmetic
bug. Parental death is not necessarily reproductive failure if descendants thrive;
the present panel has zero germinated children and cannot resolve that question.

## Verification and reproduction

All **85 CTests pass**: default 41, bank eight 22 and bank sixteen 22. The new
Python suite contains 19 cases covering exact ties, caps, death at confirmation,
shared denominators, shortage intervals, censoring, birth/dawn boundaries, invalid
data, reward independence from body/actions, and the late-collapse counterexample.
Existing native/trainer smoke tests are regression checks, not new experiments.

```sh
# Requires the frozen local allocation-v2 bundle. Uses no new native runs.
docker compose run --rm firmware python3 sim/garden_allocation_objectives.py \
    --output artifacts/garden-allocation-objectives-new

# Recompute scores, sensitivities, ties and leave-one-out means against input.
docker compose run --rm firmware python3 sim/garden_allocation_objectives.py \
    --verify artifacts/garden-allocation-objectives-v1

# Export to a NEW path, including the separately labeled follow-up diagnostic.
python3 sim/garden_allocation_objectives.py \
    --verify artifacts/garden-allocation-objectives-v1 --export artifacts/objectives-review.json
```

Collection refuses existing outputs, verifies all 229 input artifacts and native
resource/frame evidence, freezes 404 source fingerprints, and checks that sources
and inputs remain unchanged. The score bundle has five artifacts and manifest
SHA-256 `59a22c88d87bb7f66c6509f02d7efcb97ded37ce692284e851deafa645c4aa49`.
The later follow-up diagnostic is computed only for verified export, carries its
tool hash, and does not alter the frozen scores. The [export](allocation-objectives-summary.json)
contains all seven score variants, six leave-one-out panels, per-seed decisions,
full resource/action diagnostics and the separately labeled shortage follow-up.
The code and CMake additions are Python analysis/tests only; the C/C++ sources,
firmware, model ABI and actual trainer fitness are unchanged by this work.

## Next discussion

Keep the limited delayed-production signal, remove the proposed absolute
zero-shortage veto from consideration, and decide what parent/descendant survival
tradeoff we want before another objective experiment or search. The current
controls provide two productive examples but no recruitment success. We should
not claim objective readiness, defeat of inactivity, or durable reproduction
from these rankings alone.
