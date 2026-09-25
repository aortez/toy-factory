# Phase-aware shadow forecast: fixed saved-purchase audit

Follow-up to the [two-purchase forecast audit](renewal-seed-forecast.md). The
selected world and its outcomes are already known; this is diagnostic calibration,
not held-out validation, training or a test of a gate-enabled garden.

## Evidence and scope

Use **all purchases** in the two eight-day traces of
`artifacts/garden-renewal-seed-veto-v1`, manifest SHA-256
`dd44e765e15d4be5ed0c5c99273699718358ac8e5790af838162121620bcb5ae`.
Pre-calculation inventory: **52 control + 60 veto = 112 purchase records**, two
with zero current income at sun phase 120. Both traces share the same world and
a common prefix; events, overlapping horizons and repeat parents are not
independent experiments. Do not add worlds, fit coefficients or select a better
variant after seeing the result. Zero new native simulation/replay calls,
training, deployment, commits or pushes.

## One predictor, fixed before evaluation

At each actual purchase, reconstruct the existing gate's decision point and
start the shadow ledger **after** that 48-energy purchase. Do not double-count
current-step income or upkeep. Derive sun strength from the frozen C formula:
`24 + floor((min(phase, 128-phase) * 231 + 32) / 64)` during daylight,
24 otherwise. Define the unshaded light tier `Q = floor(strength / 64)`.

For a positive decision-point tier, predict future income as
`floor(current_income * future_Q / current_Q)`. This has no fitted multiplier,
history window or future observations. It retains the observed rate at the same
tier and guarantees zero income when global light is below 64. It is **not** a
conservative bound: actual shade, ray angle, leaf condition and maturation differ
across the day. If current tier is zero, report an unsupported anchor; do not
invent a rate or drop its purchase/outcome record.

Project through **noon following the next dawn** (unwrapped phase 320), with
fixed current body/upkeep and no further optional spending. Apply the 256 cap
before upkeep, every fourth ecology step, including sunset and dawn. Record
unpaid upkeep, shortage payments, peak stress and first predicted energy-stress
death (threshold 8). Successful payments reduce stress as in the existing C
rules. Predicted death is absorbing: no resurrection or later collected income.
Separately retain the anchored potential-income curve for error diagnosis.

This is **energy-only stress conditional on sufficient water**, not a forecast
of rain, roots or water competition. Flag actual water shortages rather than
interpreting this as a complete plant-survival model. No approve/reject policy,
stress allowance or change to the existing general reserve gate is introduced.

## Evaluation and accounting

- Verify every purchase against cooldown, spent flowers, seed-bank append and
  energy/water ledgers. Verify the calculated sun curve against every saved census.
- Compare the existing forecast and this candidate at the same sunset. Report
  signed/absolute energy errors, not merely whether the original gate approved.
- Follow actual resources and stress through the fixed next-noon horizon, or the
  trace endpoint/death if earlier. Record body/mature-leaf changes, subsequent
  growth, renewal, seeds and water shortages. Mark the first assumption break.
- Report both all available live samples and the prefix **before** the first
  assumption break. Aggregate by trace, and retain every purchase's identity and
  metrics. Body changes include node/root/leaf/active-leaf counts; ordinary wear
  and changing shade remain unmodeled income error, not silently corrected inputs.
- Compare predicted and observed deaths only with explicit follow-up coverage;
  retain right-censored cases and do not label them survivors. Separately report
  comparisons with no recorded assumption break before death/horizon.
- Reconcile every actual live-step budget and stress transition. Death clears
  resource telemetry: preserve its observed timing/cause, but never reconstruct
  its income or resource debits. No post-death spending is treated as observed.
- Repeat analysis exactly; pin old and new analysis provenance, export portable
  data, add synthetic boundary/censoring/no-future-input tests and update issue 30.

Forecast errors after later optional spending/body changes are explanatory, not
evidence that denying this particular purchase would rescue a parent. Neither
agreement on these reused traces nor aggregate error reduction qualifies a
runtime policy. Discuss the findings before any richer predictor or native gate
experiment.
