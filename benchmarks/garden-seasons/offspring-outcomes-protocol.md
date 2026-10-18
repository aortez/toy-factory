# Frozen-panel offspring outcome audit

Read-only follow-up to the [fresh scattering confirmation](dispersal-confirmation.md).
Analyze its existing full report, SHA-256
`2e6a1eb37d7eee860120f762c05f4c1b5e5f045b52cc942e229005aefaec6d7f`,
and cross-check the retained compact evidence before analysis. No new native
runs, seeds, controllers, interventions, or ecology changes are part of this audit.

Use all 128 existing trajectories. Report whole-run descendant birth cohorts
and final-year births strictly after day 112, both followed only through day
128. Keep the original full-day eligibility/censoring and durable-parent rules.
The following descriptive partitions are fixed before calculating them:

- Births with less than a full day of possible follow-up are censored, separately
  retaining whether they already died. Do not silently change the screen's
  survival denominator by including these early observed deaths.
- Other offspring either die on/before their full-day boundary, or survive it.
- Partition full-day survivors into no observed germinated child, at least one
  child but no full-day-surviving child, and the original durable-parent class.
- Split eligible first-day deaths by recorded terminal shortage flags
  (energy, water, both), species, and climate at death (ordinary, drought,
  seasonally dim sunlight). Record age buckets up to quarter-day, half-day and
  full-day boundaries. These are elapsed ages, not reconstructed night periods.
- For day survivors which are not durable parents, retain endpoint alive/dead
  and whether any children remain too young to assess. Absent germinated children
  do not imply no seeds were produced or that a dead parent's seeds cannot
  subsequently establish.

Reconcile each partition with the saved lifetime totals, all birth/death records,
parent identities and daily climate records. Seasonal light tapers within days:
check fixed climate fields against the daily census, bound event light against
neighboring daily values, and classify weather using the recorded event light
and drought state, not an assumed constant daily intensity. Keep matched-case rows plus seasonal
policy/layout/weather-seed partitions; these are correlated views of the same
cases, not new replicates. Do not match offspring by numeric ID across arms:
wider scattering changes trajectories and IDs need not denote comparable plants.

Terminal shortage flags describe the final death step, not lifetime budgets or
proof a weather event caused the death. Birth/death timestamps cannot establish
light exposure, root access, purchase decisions, or first-night causality. If
the next decision needs those, stop and discuss a bounded deeper replay with
appropriate observations rather than infer them from this report.

This diagnostic does not alter the confirmation's gates, promote scattering or
qualify training. Retain failed/unhelpful findings as well as useful ones.
