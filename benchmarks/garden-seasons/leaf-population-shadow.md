# Winter repair decisions on identical observations

The learned repair controllers do choose differently from fixed wear on the
same leaf observations. In the selected Search 1 shrub, most differences occur
before winter, while energy and water are plentiful. The final decline is not
explained by an inability to afford those earlier repairs.

All six [planned runs](leaf-population-shadow-protocol.md) passed in 24.474 seconds.
The 27,906 recorded observations reproduce unchanged state, history, resource
traces, and pixels from the earlier [winter trace](leaf-population-trace.md).
No alternative actions were applied, and no model, ecology, or firmware changed.

## Comparing decisions without changing the garden

The case remains shrub founder 2 and its descendants, seed `58d7d6ca`, rainfed
layout. Each of the three population runs advances to day 256 under its original
controller. During days `(208,224]`, the diagnostic asks all three frozen networks
what they would do on each identical leaf observation and memory value.

The columns below are proposed renewals, not outcomes from switching controllers.
Each row uses a different run's actual founder observations.

| Actual trajectory | Observations | Fixed wear proposals | Search 1 proposals | Search 2 proposals |
|---|---:|---:|---:|---:|
| Fixed wear | 4096 | 134 | 25 | 27 |
| Search 1 | 3767 | 175 | 75 | 57 |
| Search 2 | 3775 | 167 | 90 | 73 |

Every founder proposal in this table could pay its immediate renewal cost.
The diagonal entries are actual accepted repairs. Off-diagonal entries are
read-only predictions: applying an alternative repair would reset that leaf's
condition, spend resources, and change later observations. These counts are
therefore not the number of repairs an alternative trajectory would perform.

Descendants are retained separately in the evidence. Their observation counts
are 237, 3743, and 12288 across the three trajectories. Some Search 2 descendant
proposals cannot pay the immediate cost; the verifier distinguishes proposals
from accepted repairs rather than assuming every RENEW succeeds.

## Search 1 passes over affordable earlier repairs

On Search 1's founder trajectory, fixed wear proposes all 75 repairs Search 1
actually makes, plus 100 additional repairs. At those 100 disagreements,
stored energy ranges from 168 to 256 and water from 509 to 512. Renewal costs
9 energy and 5 water. Ninety-seven disagreements precede winter; only three
fall in `(220,224]`.

The frozen network makes the difference inspectable. Its output depends on
two active hidden units: one combines light with mature-leaf count and renewal
water cost; the other combines leaf condition with stored energy and renewal
energy cost. With these frozen output weights, WAIT scores zero and RENEW
scores `1 - hidden[0] - hidden[1]`. Both units must be zero to choose RENEW.

Of those 100 rejected fixed-wear opportunities:

- 26 have only the light-related unit active.
- 60 have only the condition/energy-related unit active.
- 14 have both active.

These are exact network calculations, not inferred biological motives. For this
21-leaf founder, Search 1 needs observed light of at least 143, versus 131 for
fixed wear. At the observed disagreement energy levels, it also waits until
leaf condition reaches 188 or 190, versus fixed wear's 192. Higher stored
energy makes that condition threshold slightly stricter; this is not a simple
low-energy reserve guard. Thresholds use the network's clipped integer features
and division toward zero, not a floating-point approximation.

For example, at day 220.98046875 the observed leaf has condition 135, light 139,
energy 192, and water 512. Fixed wear and Search 2 choose RENEW; Search 1 chooses
WAIT. The Search 1 light-related hidden unit is 2 and its other active output
unit is zero, giving RENEW a score of -1 against WAIT's zero.

## The final low light interval is shared

The distinction is smaller once the Search 1 founder is already declining.
Across its winter observations, fixed wear proposes three repairs, Search 1
zero, and Search 2 one. All three opportunities occur in `(220,221]`.
During `(221,222]`, its maximum observed leaf light is 125. From day 222 until
death at 222.71875, the maximum is 104. Even fixed wear's light threshold is
not met, so merely substituting that controller in the final interval would
not request a repair on the recorded inputs.

The control's better foliage and higher winter income remain consistent with
an earlier repair-timing advantage, but this comparison does not establish that
additional early repairs would rescue Search 1. Its neighboring population and
earlier trajectory have already diverged. Family survival also depends on
recruitment: the previous trace's continuously spacing-blocked seeds are still
a separate bottleneck.

## Next experiment

A useful bounded intervention would separate the two decision changes: retain
the Search 1 controller but restore only the fixed-wear light gate, restore
only its condition gate, or restore both. Compare those actual trajectories
against unchanged Search 1 under this same case, keeping costs, growth, memory,
weather, spacing, and all other ecological rules fixed.

That would test whether earlier decisions alter the winter energy budget and
founder survival, while still checking descendant establishment and family
survival. A rescue in this diagnostic case would motivate broader validation,
not immediate model promotion. No such intervention has been run here.

## Evidence and verification

The compact archive (`leaf-population-shadow-results.json.gz`, kept locally)
contains all six receipts, 24 captures, six resource traces, three observation
streams, the prospective protocol, collection-time source snapshots, and
preflight results. The largest stream contains 16063 rows, below the 32768-row
bound. Collection had no failures or retries.

The native hook forwards the original decision and checks its action, node,
and memory against its frozen shadow counterpart. Independent Python inference
recomputes all 83,718 proposed actions. Daily recorded observations, original
proposals, accepted repairs, and restored condition reconcile with the resource
trace. All paired canonical state and pixels match, including exact prior
archive bytes at days 0, 32, 192, and 256.

Seven host session/viewer suites passed before collection in 83.33 seconds,
along with ten preparation tests. Native checks include an additional 11,520
step-by-step shadow/uniform state comparisons across the three policies,
allocation and callback failures, bounds, reset, and unchanged capture output.
Post-collection tests verify archive round-trip, offline-only operation, the
network explanation above, and rejection of changed or missing observations.
All 44 population analysis tests pass. The collection-time source snapshots
remain unchanged.

```sh
python3 -B sim/experiments/leaf_population/population_shadow.py unpack \
  benchmarks/garden-seasons/leaf-population-shadow-results.json.gz \
  artifacts/garden-population-shadow-review-v1
python3 -B sim/experiments/leaf_population/population_shadow.py verify \
  artifacts/garden-population-shadow-review-v1
```

Use a fresh output directory. Archive SHA256:
`330a8a77f395410f0b7b9dd157ffc7c80fd8f1ece3670c0a0461d522572e40f3`.
