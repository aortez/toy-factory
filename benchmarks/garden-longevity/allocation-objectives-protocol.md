# Allocation objective dry-run v1

Compare objective formulas against the already inspected six-case allocation
challenge, **without new native simulation, model search or ecology changes**.
This is an exploratory objective-design exercise, not preregistered blind data:
the control outcomes are known. Freeze these definitions before extracting seed
timings, delayed-parent outcomes, scores or rankings. Do not tune weights to make
a preferred controller win this panel.

Input: the complete `artifacts/garden-allocation-v2` bundle, SHA-256
`a7cb927521ab5188a1a1622cbfda4ffdd9d930843403fcc9b3cbe43774f98738`.
Retain every case and all four arms, including no-effect duplicates. `candidate`
is the old frozen NN without a bootstrap on that seedling, not a trained model.

## Common observation window

For each case use the same, policy-independent deadline: the first scheduled
patch covering the seedling's fixed base column, or its eight-day horizon.
If a patch ends observation, score only through the ordinary ecology sample
**before** that tick. Do not use a policy's own death to shorten its denominator,
remove failed cases, or impute survival after a patch. Print actual window length
and reason beside the normalized score; a shorter window is not eight-day proof.
Cases with less than a full day of shared follow-up are unscorable, not zeros.
There are no such cases expected in this fixed panel; validate this explicitly.

Let:

- `G` be 1 if the plant is alive at its first future dawn and age one day,
  otherwise 0. No extrapolation across censoring.
- `L` be the fraction of ordinary post-birth ecology sample times in that shared
  window at which the plant is alive. Exclude the birth sample. A natural death
  at a sample time counts as not alive; dead/reclaimed remainder stays in the
  denominator. This is discrete observed survival, not continuous-time hazard.
- `R` be the number of actual seed purchases in the shared window, capped at 4
  and divided by 4. Purchases are reconciled with existing resource ledgers.
- `Q` be the number of **distinct plant-age day bins** with at least one seed
  purchase followed by a full additional day alive, with no observed energy/water
  shortage at maintenance samples in `(purchase, purchase + one day]`; cap at 4
  bins and divide by 4. Day bins are `floor((purchase - birth) / 3840)`.
  The purchase's post-step reserves remain visible but are not themselves points.

For each seed retain whether that extra day was confirmed, naturally failed,
resource-short, patch-censored or horizon-censored. A censored seed earns **no
observed bonus yet**, but is not labeled a failure. No claims about unobserved
future survival. Multiple purchases in one bin cannot increase `Q` past one.

## Three objective variants

1. **Survival:** `G + L`.
2. **Raw seed bonus:** `G + L + lambda * G * R`.
3. **Confirmed productive days:** `G + L + lambda * G * Q`.

Use nominal `lambda = 1/4`, and report both `1/8` and `1/2` as predeclared
sensitivity checks, not a weight search. Exact rational arithmetic defines ties;
rounded decimals are presentation only. Cap/weights are provisional design
choices, not inferred biological constants. No root/shoot count, size, stored
resource, leaf count, photosynthesis or action-frequency reward is added.

Show within-case ties/ranks and a descriptive equally weighted six-case mean;
also omit each case in turn to detect a ranking driven by one favorable example.
The mixed reference arms are controls, not one deployable population policy.
The cases share seeds/history and are not independent replicates. Do not fit
weights, claim significance or pick a deployable controller from these means.

## Arithmetic challenge fixtures (not native ecology runs)

Before reading the new rankings, test:

- Equally durable productive versus inactive bodies.
- A first-day seed burst followed by natural death versus a durable inactive body.
- Excess seed purchases in one bin versus repeated confirmed productive days.
- Death exactly at seed-confirmation time; shortage despite remaining alive.
- Confirmation crossing patch or horizon boundaries; patches before one day.
- Short early natural death cannot improve `L` by reducing its own denominator.
- Cap enforcement, reward independence from shape/stores/actions, and stable ties.
- A confirmed producer dying near the horizon can still beat inactivity under
  these additive formulas: expose that residual tradeoff, do not hide it.

The real panel has no germinated children, so it cannot discriminate a
descendant-based objective. The synthetic fixture outcomes are arithmetic tests,
not evidence that those behaviors are reachable or safe in the current ecology.
Record natural deaths, resources, reproduction and censoring separately. Reject
claims of objective readiness if the controls/fixtures leave known loopholes;
no trainer wiring or promotion follows automatically from a ranking.
