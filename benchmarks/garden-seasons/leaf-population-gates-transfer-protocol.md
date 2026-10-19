# Scheduled repair gates on a second weather seed

Repeat the [four day-608 arms](leaf-population-gates-long-protocol.md) on
rainfed weather seed `59818bc3`. Its shrub founder is dead before day 208,
but descendants 7 and 18 remain alive. Test whether the repair interventions
benefit this family too, without changing timing, ecology, growth, or scoring.
This is a second selected case from the existing panel, not an unseen random
sample or a training run.

## Conditions and budget

Use the authenticated frozen runtime and W2 growth controller. All plants use
Search 1 through day 208. Strictly after tick 798720, only founder family 2,
including later offspring, receives its assigned repair model until day 608.
Keep the same `none`, `light`, `condition`, and `both` derivations: restore
hidden unit 0, unit 1, or both from fixed wear, leaving all other Search 1
weights, shifts, costs, and copied growth memory unchanged.

Run every arm with resource logging on and off: eight calls, two workers,
180 seconds per call, a 900-second collection budget, and at most 24 MiB
retained output per call. Stop on failures or verification mismatches;
retain attempts without retries or roster expansion. Development tests and
preflight are separate. The native command is `--gate-transfer`; existing
`--gate` and `--gate-long` keep their original seed and endpoints.

Capture complete state, history, and native pixels at days 0, 32, 192, 208,
220, 222, 224, 256, 384, 512, and 608. Freeze resource and seed-blocker tracing
at day 256, retaining the existing allocation bounds. Continue complete
birth, death, ancestry, and seed outcome ledgers through day 608.

## Required checks

Authenticate the original population archive by SHA256
`3aae48b92ed9787f9dc1601052330cdbf96ed9d72f3d845e0b9932d50112af49`.
Match its Search 1 rainfed case at days 0, 32, and 192 for every arm, and at
day 608 for the unchanged arm. Compare complete population records only after
validating and explicitly removing the intervention envelope. Keep full `TGR1`
identity in stored results, including exact derived model bytes and the seed
already encoded in the underlying simulation state.

Require identical underlying state, history, and pixels across all arms
through day 208, and matching resource/seed trace prefixes through that day.
Check day-208 ancestry against the original complete ledger. Require every
logging-on/off pair to match full state, history, and pixels at all captures;
check resource conservation, leaf condition accounting, and trace coverage
against the day-256 state. Reject a mismatched seed, model, horizon, archive,
roster, or trace. Keep earlier archives and their offline verifiers working.

Snapshot the prospective protocol, source files, exact derived models, binary
digest, process receipts, and preflight results. Use strict warnings, UBSan,
native ownership/boundary tests, and offline archive validation. Do not execute
archived source during verification or modify frozen runtime files.

## Measurements and interpretation

Report survival of the two shrubs alive at the switch, subsequent family
status, extinction or seed-only intervals, new births, age-32 establishment,
young survivors, generation depth, and seed outcomes. Keep old descendants
separate from post-switch births. Compare all three founder families, including
competitor losses and final population composition.

Use the unchanged renewal objective: births in `(192,576]`, six 64-day windows
capped at two qualifying children each, followed through day 608. Both child
and its non-founder parent must survive their own first 32 days. Report the
existing descendant occupancy tie-breaker separately. Because the first 16
days precede intervention, identify any renewal credits originating there;
do not attribute shared-prefix credits to the treatment.

Compare with the earlier seed without pooling away their differences. This
case may show survival without renewal, no rescue, or competitive displacement.
Do not promote a controller, change firmware defaults, expand the experiment,
or adjust the objective based on a favorable result alone.
