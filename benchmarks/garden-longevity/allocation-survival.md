# Survival-confirmed production: useful allocation signal, not offspring success

The approved follow-up removes the **zero-shortage veto** while keeping the
observation windows, establishment gate, weights and cap unchanged. Both native
productive survivors now beat WAIT in their individual cases. WAIT still wins
every aggregate comparison because the alternatives die early in most cases.
No formula has been installed in the trainer.

This is an offline rescore of the same six already inspected development cases,
not new native simulation, training, or held-out validation. The prior diagnostic
already established the parent-survival counts. The
[protocol](allocation-survival-protocol.md) was frozen before this revised scoring
pass; neither the original [objective results](allocation-objectives.md) nor the
underlying [allocation controls](allocation-challenge.md) was changed.

## One changed term

The revised score is `G + L + lambda * G * P`:

- `G`: alive at the first future dawn and age one day.
- `L`: fraction of shared post-birth sample times alive, including the dead
  remainder in the denominator.
- `P`: distinct plant-age day bins containing a seed purchase followed by a
  fully observed additional day of parent survival, capped at four bins / four.
- `lambda`: nominal 1/4, with the unchanged 1/8 and 1/2 sensitivity checks.

Only `P` differs from the previous zero-shortage term `Q`. Death at confirmation
fails it; confirmation at the last observed alive sample qualifies. Incomplete
patch/horizon follow-up earns no observed credit and remains censored, not a
failure. Resource shortages remain visible diagnostics but earn or remove no
points. The signal is **survival-confirmed seed purchases**, not germination or
durable offspring. Body size, reserves, action counts and child births are not
additional reward terms.

## Native results

At nominal weight, WAIT scores 2.0 in both productive cases:

| Producer | Fully confirmed purchases | Confirmed age-day bins | Zero-shortage score | Revised score |
|---|---:|---|---:|---:|
| Wet-root rescue | 5 of 7; 2 patch-censored | 0, 1, 2, 3 | 2.125 | **2.250** |
| Bank-16 frozen NN without early-root bootstrap | 12 of 15; 3 horizon-censored | 1, 2, 3, 4, 5, 6 | 2.000 | **2.250** |

The rescue has 4.585938 scored days before its fixed patch; the bank-16 case
has eight. Equal scores do not mean equally long demonstrated persistence.
Both reach the four-bin cap. The latter's tie with WAIT becomes a win at all
three weights. The rescue already won and now receives the full capped bonus.
The other four cases contain no seed producers and their scores are unchanged.

The nominal equally weighted means are WAIT **1.933187**, frozen candidate
0.734840, wet-root 0.408683, reference 0.368629. Across old and new formulas,
WAIT leads **10/10** aggregate variants and **60/60** leave-one-case-out rankings.
For the three new variants alone, that is 3/3 and 18/18. All original scores,
ties and aggregate comparisons reproduce exactly.

**Important limitation:** all 24 native arms receive exactly the same revised
score as capped raw-seed credit at each weight. Both producers reach both caps;
everyone else produces no seeds. This panel demonstrates removal of the
shortage veto, but cannot empirically demonstrate that delayed credit improves
policy selection over raw seeds. That distinction appears only in the arithmetic
challenge fixtures below. These mixed reference contexts are not a single
deployable policy, nor are these selected cases independent replicates.

Resource histories have not improved merely because the score changed. After
first reproduction, the bank-16 plant still has eight energy-shortage checks,
longest streak two and peak stress two. Before reproduction, it had seven
consecutive water-shortage checks and reached stress seven. Keep both facts
visible; this is not proof of indefinite stability or uniformly mild stress.

## How much parent survival does the bonus buy?

For two established plants with the same common window, one an inactive
survivor, the producer ties when its lost alive-sample fraction equals
`lambda * P`. Thus the nominal full bonus can offset **two of eight observed
Garden days** of parent survival. Losing less wins; losing more loses. Exact
sample arithmetic, not rounded continuous death times, determines equality.

| Bonus weight | One confirmed bin: break-even lost days | Four or more bins: break-even lost days |
|---|---:|---:|
| 1/8 | 0.25 | 1 |
| 1/4 | 0.50 | 2 |
| 1/2 | 1.00 | 4 |

These are arithmetic exchange rates for an eight-day window, **not observed
death outcomes, guarantees that a body can attain those bins, or an approved
tolerance for death**. For the shorter rescue window, the nominal full-cap
exchange is 1.146484 days. The JSON records each case's exact values.

A parent dying after establishing successful descendants need not be an
ecological failure. But **none of these continuations germinated a child**, so
seed purchases alone do not establish such a justification. Lowering the
bonus changes the exchange rate without resolving this missing evidence.

## Arithmetic challenges, not native trajectories

Nominal scores from hand-built evidence:

| Fixture | Raw seeds | Revised survival confirmation |
|---|---:|---:|
| Inactive eight-day survivor | 2.000000 | 2.000000 |
| Durable producer across four bins | 2.250000 | 2.250000 |
| First-day burst, then early death | 1.394043 | 1.144043 |
| Survives, but all seeds in one age-day bin | 2.250000 | 2.062500 |
| Unconfirmed end-of-window burst | 2.250000 | 2.000000 |
| Confirmed producer dying near the horizon | 2.247559 | 2.247559 |

The last example still beats inactivity at all three weights. Full-day
confirmation is a delay, not a promise to survive the rest of the experiment.

Two additional checks expose remaining semantics:

- A repeatedly shortage-flagged survivor receives the same production score as
  a shortage-free survivor. This is intentional under `P`; the synthetic evidence
  does not establish that such a history is reachable in the actual ecology.
- Purchases only 15 logic ticks apart, straddling an age-day boundary, count as
  two bins and score 2.125. A single-bin burst counts once. Day bins limit credit
  but do **not** enforce regularly spaced production. No binning fix is bundled
  into this confirmation-only experiment.

## Implementation and verification

`sim/garden_allocation_survival.py` adds an offline collector/reviewer on top of
the unchanged original scorer. It revalidates the native bundle and original
objective bundle, reproduces all old results, and appends the three revised
variants, per-purchase statuses, score deltas and break-even survival budgets.
Shortage/death/reproduction diagnostics remain in the output. Old bundles,
scripts, protocol and exported results are unchanged.

All **88 CTests pass** across default / bank-8 / bank-16 builds (42 + 23 + 23).
The new Python suite has 18 cases covering confirmation boundaries, shortages,
censoring, bins/caps, exact break-even ties, unchanged old scores, and baseline
immutability. Existing native/trainer smoke tests are regression checks, not a
new training experiment. No C/C++ source, model ABI, firmware or ecology changes
were made for this task.

```sh
# Requires the two original local frozen bundles; choose a NEW output directory.
docker compose run --rm firmware python3 sim/garden_allocation_survival.py \
    --output artifacts/garden-allocation-survival-new

# Reproduce exact old/new scores, resource diagnostics and survival tradeoffs.
docker compose run --rm firmware python3 sim/garden_allocation_survival.py \
    --verify artifacts/garden-allocation-survival-v1

# Optional export; existing paths are refused.
python3 sim/garden_allocation_survival.py \
    --verify artifacts/garden-allocation-survival-v1 \
    --export artifacts/allocation-survival-review.json
```

The new bundle contains five artifacts and a snapshot of 409 source files;
manifest SHA-256:
`65307826079e5c478a0d853c85b46e94962bb428b0c3822b4564f089c4f1ecdd`.
The [complete JSON export](allocation-survival-summary.json) retains all ten
variants, six leave-one-out panels, native evidence and nine explicitly
synthetic fixtures. The ignored source bundles are not shipped in a fresh
checkout; this report, protocol and export are the portable review material.

## Recommended next step

Keep `P` as a short-horizon allocation diagnostic, not the final A-life fitness.
We now know what removing the veto does and the implied parent-survival tradeoff;
another weight adjustment on these same cases cannot establish offspring success.

Next, connect this signal to **actual day-surviving descendants**, starting with
the existing longer-run lineage evidence rather than another broad sweep. Keep
an inactive survivor, a seed-producing parent with no established offspring,
and a parent with established offspring distinct. Retain reproductive
opportunity, natural deaths and censoring, and explicitly distinguish
parent-survival credit from descendant success before selecting a training
objective. The earlier [recruitment diagnostic](recruitment-sites.md) already
shows that seed supply and usable vacancies are different constraints; this
follow-up should reuse that evidence, not assume seed counts measure recruitment.
