# Shrub repair gates through day 608

Extend the [four scheduled interventions](leaf-population-gates-protocol.md)
through day 608. Determine whether the light-gate survival benefit leads to
new shrub generations or merely keeps existing plants alive. This is a longer
follow-up of the same known case, not a seed panel or training search.

## Fixed conditions and budget

Keep seed `58d7d6ca`, rainfed layout, frozen runtime, W2 growth and memory,
Search 1 competitors, and the four private repair models unchanged. Family 2
receives its assigned variant strictly after day 208, continuing through day
608. No ecology, costs, capacity, firmware, policy defaults, or scoring changes.

Run `none`, `light`, `condition`, and `both`, each with resource logging on and
off: eight calls, two workers, 180 seconds per call, 900 seconds overall, and
24 MiB retained output per call. Keep failed attempts and stop without retries
or roster expansion. Development tests and preflight are separate.

Capture state, complete history, and native pixels at days 0, 32, 192, 208,
220, 222, 224, 256, 384, 512, and 608. Preserve the existing resource trace
through day 256 only; explicitly freeze it before continuing. Do not enlarge
trace allocations. Continue birth, death, ancestry, and seed outcome tracking
through day 608 in both repeats. The original short command remains bounded
at day 256; `--gate-long` opts into the extension at that checkpoint.

## Regression and evidence requirements

Authenticate the earlier gate archive by SHA256
`a73a6f20cf420348fe1684ef73ea0ea081e872586c91287a4c7940064d9147a1`.
Require byte-identical JSON and pixels for every old checkpoint in all eight
runs, plus byte-identical resource traces. Require logging-on/off parity at
every new checkpoint and consistent history prefixes. Retain complete `TGR1`
identity with exact derived model bytes; horizon control and logging do not
change the simulation's canonical state.

Check the extension boundary, repeated calls, failure latching, reset,
unchanged canonical state at extension, no step allocations, frozen trace,
and day-608 limit. Keep strict compiler warnings, UBSan, existing replay and
viewer checks, and independent model/ledger validation. Snapshot sources,
protocol, models, binary digest, process receipts, and preflight. Verify the
compact archive offline without executing its source snapshots.

## Measurements

Report family status and composition, founder and descendant death timing,
seed outcomes, and all post-switch births. Separate existing descendants from
new ones and distinguish age-32 establishment, early death, and still-young
survivors. Record generation depth and births from non-founder parents.

Use the unchanged first renewal score: births in (day 192, day 576], six
64-day windows capped at two qualifying children each, with follow-up through
day 608. A qualifying child and its non-founder parent must each survive
their own first 32 days. Label the first 16 days of this window as preceding
the intervention, and separately report post-day-208 cohorts. Keep descendant
occupancy as the existing tie-breaker, not a replacement for renewal.

Compare all three families because improved shrub survival can redistribute
limited plant slots. Living at day 608 is censored survival, not permanence.
Choose any next experiment only after reviewing this fixed follow-up.
