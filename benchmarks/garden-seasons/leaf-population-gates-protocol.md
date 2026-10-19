# Scheduled shrub repair gate experiment

Test whether Search 1's stricter light and condition thresholds contribute to
the shrub's winter decline. Unlike the preceding read-only
[comparison](leaf-population-shadow.md), these runs apply the alternative
decisions. This is a diagnostic intervention in one known failure case, not
training, generalization evidence, or model promotion.

## Conditions and budget

Use the authenticated frozen runtime, W2 growth controller and its memory,
seasonal rainfed layout, and weather seed `58d7d6ca`. Every family initially
uses `s1-g3-c4`. After day 208, only founder 2 and its descendants receive the
assigned repair variant, including seedlings born later. Other families keep
Search 1. The switch is strictly after logic tick 798720; day 208 is unchanged.
The assigned variant remains active until the endpoint, day 256.

| Arm | Replacement within Search 1 |
|---|---|
| none | No changes |
| light | Hidden unit 0 bias and eleven input weights copied from fixed wear |
| condition | Hidden unit 1 bias and eleven input weights copied from fixed wear |
| both | Both replacements |

Keep every other parameter, shift, output weight, and cost unchanged. All
controllers remain stateless and copy growth memory unchanged. Restoring both
active gates is decision-equivalent to fixed wear; the model bytes still retain
Search 1's unused hidden units. This is not a whole-population fixed-wear run.

Run each arm once with the existing read-only resource/seed trace and once
without it: eight calls, two workers, a 180-second timeout per call, and a
900-second collection budget. Capture native pixels and complete state at days
0, 32, 192, 208, 220, 222, 224, and 256 in both repeats. Keep failed attempts;
stop on a failed call or verification mismatch, without expanding the roster
or silently retrying. Limit each call's retained output to 24 MiB. Development
tests and the preflight suite are separate from the eight experiment calls.

## Identity and required checks

Do not modify prepared frozen sources or archived models. Decode private copies
of the two authenticated models and derive the four variants at setup. Encode
the exact derived model, arm, selected founder, and activation tick in a new
`TGR1` state envelope and `garden-leaf-gate-replay-v1` JSON identity. Preserve
the ordinary population and family formats unchanged. Gate and shadow modes
cannot be combined. Reset disables the intervention and diagnostics.

Test model derivation independently from the archived byte layout. Test routing
before, at, and after the switch, including unrelated families, descendants,
newborns observed before the ancestry update, dead-parent ancestry, failures,
allocation bounds, and output preservation. Match all trace-on/off state,
history, and pixels. All arms must have identical underlying state, history,
resource trace prefixes, and pixels through day 208. The unchanged arm must
match the prior authenticated trace archive at days 0, 32, 192, and 256 after
removing only the explicitly documented intervention envelope.

Snapshot the protocol, sources, model bytes, binary hash, process receipts, and
preflight results. Verify resource and leaf conservation against full histories.
Archive verification is offline and must not execute archived code.

## Measurements and interpretation

Compare founder energy, leaf condition, accepted repairs, resource income and
spending through the winter; record founder death timing, final family status,
seed outcomes, births, and age-32 establishment. Separate descendants born after
the intervention and those already present. Report other families' outcomes
too, because competition can redistribute opportunities. Keep young survivors
without sufficient follow-up distinct from established offspring.

The primary diagnostic is whether a gate change alters the winter energy
budget and founder survival. Family survival and recruitment remain important
secondary outcomes; founder survival alone is not success at generational
renewal. A day-256 survivor is censored, not immortal. The experiment does not
claim the full training objective, which requires a much longer horizon.

Leave firmware, ecological rules, spacing, seed lifetime, training objective,
and policy defaults unchanged. Any longer or broader validation is a separate
next step after reviewing these results.
