# Maintenance increase forecast audit protocol

Audit the saved first-day energy forecasts before changing any reserve rule.
Use all five focal cases and both arms from the completed root-energy comparison,
including both successful harm checks. This is a retrospective accounting audit
of a selected panel, not a new policy test or independent validation panel.

## Frozen input and scope

Input: `landing-root-energy-results.json.gz`, SHA-256
`dca98970b1efbd6552df4796c280fcb0883bc959f226d569531353a760abe778`.
Validate that input using its existing offline checker. Retain its ten focal
first-day histories, saved second-day follow-up, and long-run outcomes.

Select every executed paid daylight growth decision in the first day
`birth <= tick < birth+3840`. Identify allocations that cross a maintenance
boundary: 8→9, 16→17 or 24→25 nodes. Also retain every first-day decision with an
otherwise node-budget- and water-eligible proposal to cross such a boundary,
including energy-rejected and lower-priority proposals. Count these opportunities
once per decision, not once per tip. Do not infer execution from a forecast alone.

Preserve all ten arm histories. Identify exact duplicate captured focal histories
after removing observational energy-gate annotations, and report both raw and
deduplicated counts. These paired, overlapping worlds are not independent trials.
Do not select only the two known failures or compare descendants by reused IDs.

## Accounting questions

For each paid decision, recompute the forecast and verify the selected bid,
ordinary growth fees and actual allocation. Compare the forecast with the next
sunset, using saved follow-up only. Retain deaths at/before sunset as failures to
reach that endpoint, not zero-income full windows; mark missing follow-up censored.

Reconcile actual sunset energy from the post-action balance, subsequent income,
maintenance, paid growth, reproduction, overflow and death discard. Decompose
prediction error into those contributions, including the forecast's 256-energy
cap. Distinguish intervals with later paid growth from intervals without it.
Also report the observed next dawn, night transfers and any shortages; do not
equate a fixed-body forecast with the whole future policy's resource use.

Report phase before noon (phase <64) versus noon/afternoon (64..127), and whether
actual sunset stores cover the forecast's nominal night requirement. For boundary
crossings, retain the full bid and relevant accounting receipts. Calculate the
post-action margin with *zero* future-income credit as an accounting baseline.
Count known successful actions that this stricter test would refuse. This is a
same-state arithmetic comparison, not a simulated rescue or policy recommendation.

## Outputs and limits

Export every selected event, every threshold opportunity, case summaries, pooled
and deduplicated summaries, input/protocol/source hashes and corruption tests.
Offline verification must reproduce the complete result from the pinned input.
Keep existing artifacts intact and use a fresh no-clobber output directory.

Budget: **zero native simulation calls, zero training, zero new screenshots**.
No firmware/model/ecology changes, parameter search, promotions, commits or pushes.
Use the findings to propose the next bounded comparison, not to implement it.
