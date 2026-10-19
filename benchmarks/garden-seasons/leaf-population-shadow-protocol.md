# Winter leaf decision comparison protocol

Compare the three frozen repair controllers on identical actual leaf observations
from the shrub family in the existing `58d7d6ca`, `rainfed` population case.
The original run's controller remains authoritative. Alternative decisions are
recorded but never applied. This distinguishes decision differences from the
different plant bodies and resource histories produced by each controller.

## Fixed conditions and budget

Run `initial`, `s1-g3-c4`, and `s2-g3-c1` through day 256, each once with shadow
inference and once without it: six new simulation calls, two workers, at most
180 seconds per call and 900 seconds for collection. Both modes retain the
existing resource and seed trace. Capture days 0, 32, 192, and 256.
Development tests are separate from these six calls. Preserve failed attempts;
do not expand the seed roster, window, horizon, or budget based on results.

Record every leaf-policy observation for founder 2 and its descendants during
`(208,224]` days: the entire 16-day calendar year containing the known winter
founder deaths near day 222.7. Daily bins are `(day,day+1]`; winter bins are
220 through 223. Report founder and descendants separately.

Each row contains logic tick, persistent lineage and parent, current plant/node
indices, all eleven raw leaf features in feature-v1 order, the eight memory
bytes, and all three proposed actions. The bounded host owner holds at most
16 × 256 × 8 = 32768 rows. It allocates only at setup. Diagnostic failure
invalidates the session and prevents successful publication.

## Required checks

The passthrough calls the original controller and returns its exact decision.
For every recorded observation, its action, node, and copied memory must match
the corresponding frozen shadow controller. None of these stateless networks
may modify the input memory. Reset disables diagnostics.

Verify every proposed action independently in Python from the archived model
bytes, using signed division toward zero, clipped inputs, clamped hidden units,
and WAIT on ties. Check identity, chronology, ancestry, and observation coverage.
Daily original-action totals must reconcile with the independent resource trace's
observations, proposals, accepted renewals, and restored leaf condition.

Compare all paired canonical state/history JSON, resource/seed trace, and raw
RGB565 captures byte for byte. Compare those outputs with the prior authenticated
six-call trace archive, including day 256. Keep the frozen runtime and models
unchanged; snapshot the collector, diagnostic sources, and this protocol.

## Interpretation

Report renewal counts and disagreements on each run's actual input distribution,
separately for the full window, winter, and each founder/day. Distinguish a proposed
RENEW from a worn leaf with sufficient energy and water to pay its immediate
cost. Independent action scores are decision margins, not probabilities.

These are read-only action comparisons, not alternate trajectories. More proposed
or immediately affordable repairs do not establish survival benefits or a better
population outcome. No training, model changes, ecology changes, firmware changes,
or device deployment are part of this experiment.
