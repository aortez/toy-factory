# Saved node-pressure and incumbent-death audit

Scope fixed before detailed analysis: read the two saved `renewal-plant-slots`
arms only, through tick 245760. No new simulation, training, model, rule,
parameter, horizon, device deployment, or defaults promotion.

Parent manifest SHA256:
`1cec5406f4f595972fde3cfea355d9f8c6c712fb279112d81f8e0ec3a77e0d3b`.
Parent portable summary SHA256:
`5aca6ec16c07185aeb857f9267537e7346b0510b2dd7abd7f8f4977395059c82`.

## Questions and fixed windows

- Who owns the 512 nodes? Count living/dead, roots/shoots, incumbent/new
  ownership, tips, allocation and whole-plant reclamation in both arms.
- Reconstruct node occupancy at seed-bank entry and at each plant's growth
  stage from consecutive censuses, birth allocations, reclamation and growth.
  Verify against saved growth bids; an end-of-step full pool alone is not
  evidence of an earlier rejected request.
- Count full-pool exposure with remaining tips and without successful leaf
  renewal. Cooldown is not exported: do not call this exclusive allocation
  rejection, or infer the unobserved action a policy would have requested.
- Compare all seven incumbents present at tick 69120, using whole post-change
  histories and the same absolute final-day windows before each candidate
  death. Audit energy/water budgets, maintenance shortages, sampled light,
  leaf condition, node/tip histories and shared-root-cell exposure.
- Report terminal maintenance flags and stress progression, but do not invent
  terminal-step income or expense: death clears these fields before census.

Post-change window: `(69120,245760]`. Closing window: `(184320,245760]`.
One garden day: 3840 logic ticks. Ecology checkpoints: every 15 ticks.
Final-day death windows: `(death_tick-3840,death_tick)`, omitting the terminal
step and comparing both arms at identical ticks. Ownership snapshots: split,
first post-change full checkpoint, beginning of the final uninterrupted full
interval (if any), endpoint.

## Interpretation and validation

This is a selected-world mechanism audit, not a new treatment comparison.
Node pressure, light, moisture, competition and death correlations cannot
establish which single rule change would help. Incumbent death may be normal
turnover; retain the parent's declared outcome gates unchanged.

Verify the immutable parent bundle, portable summary and native source;
reproduce its saved analysis; reconcile every audited ownership transition
and live resource budget; repeat this audit and check identical output.
Allow only the new audit's exact CMake test registration against the parent
build file. Add focused synthetic/malformed-input tests. Keep new output
outside the parent bundle. No new native research calls.
