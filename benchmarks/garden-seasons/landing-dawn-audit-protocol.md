# Dawn funding audit protocol

Measure the remaining dawn reserve gap in the complete saved daylight comparison.
This is read-only accounting, not a new spending policy, training run or simulator
experiment. Keep successful histories as well as the failure and rescue.

## Frozen input and scope

Use all ten focal histories from `landing-daylight-results.json.gz`, SHA-256
`9e2acb8cf141e75307020c0b854c3a76611942cec615c21b95db750c97d7748b`.
Validate the input's complete paired evidence, captured light/maintenance sources
and disabled alternate lighting/maintenance settings before analysis. Preserve
exact histories through death or world day 256. Report raw counts and separately
deduplicated physical histories; treatment annotations are not physical changes.

Account for every observed sunset through the following noon, with explicit
death/capture censoring. Also retain dawns whose preceding sunset is outside the
focal lifetime. Dawn means phase 0, useful global light means strength at least
64, and first positive income means actual leaf income above zero. They are
different boundaries. Do not replace unobserved future values with zeros.

## Resource accounting

Independently recover maintenance due from the pre-maintenance node count and
four-step cadence. Distinguish due, paid and unpaid costs; shortage flags persist
between payments and must not be counted as new shortage events. Uptake precedes
maintenance, growth and reproduction. Preserve the 256-energy storage cap,
overflow, terminal discard, birth exemption and exact sample ordering.

For each morning, retain every sample through noon, including income, costs,
stress and shortages. Record the first globally productive sample and first
positive income, plus maintenance through those points. Calculate the minimum
opening energy needed to fund the recorded schedule through each boundary and
through noon. Do this twice: maintenance only on the recorded body path, and
maintenance plus recorded growth/reproduction. Use a backward capped-balance
calculation, independent of realized paid costs. These are conditional accounting
requirements, not world replays: changed resources could change bodies, choices,
shade, stress and deaths. Terminal discard is not a cost to fund. Dead/censored
windows establish requirements only over the observed prefix.

Link mornings to their observed preceding sunset. Separate a shortfall against
nominal night upkeep from the additional dawn requirement. Report whether exact
night funding, first positive income, or a fully paid maintenance event actually
ends the observed shortage episode; do not infer permanent recovery from one
positive sample. Keep subsequent morning shortages visible.

## One diagnostic before choosing a rule

For paid afternoon decisions, hold the currently observed attenuation constant
on the known daily curve. Let B(q) be the unscaled curve minus ambient 24 and
C be current strength minus 24. Find the first next-morning phase q in 1..64
with `24 + floor(B(q) * C / B(now)) >= 64`. Reserve the current post-action
maintenance cost through the first maintenance boundary at or after q, rounding
q upward to a multiple of four. This also covers the case where the first small
income arrives on a payment step; no forecast morning income is credited.

Use only current phase, global strength and post-action maintenance. An estimate
that never reaches productive light is explicitly unavailable, not silently
assigned a default buffer. This diagnostic is not a guaranteed bound on future
weather, shade or growing maintenance. Do not add a fitted safety factor or a
second alternative after seeing results.

On the daylight candidate's recorded paid decisions, compare the extra reserve
against projected sunset minus nominal night upkeep, and against the stores-only
margin when a maintenance increase invokes that additional check. Report all
newly rejected purchases and all unavailable estimates, including successful
plants. Also retain calculations on controls as inactive references. No proposal
is executed, no changed trajectory is implied, and future realized conditions
are used only to evaluate estimates. Relate diagnostic margins to actual
sunset/dawn accounting without conflating the two.

## Deliverables and limits

Write a fresh no-clobber bundle containing reproducible portable results, source
snapshot and hashes. Verify repeat exports and raw/portable reanalysis. Add tests
for cadence, rounding, cap effects, stage order, first-income shortages, incomplete
windows, scope, corruption and no-clobber behavior; prohibit native calls in the
offline analysis tests. Record the full distribution, not just two stressed
mornings. Keep previous captures unchanged. No C/runtime/default changes, device
deployment, commit, push or PR mutation in this step.
