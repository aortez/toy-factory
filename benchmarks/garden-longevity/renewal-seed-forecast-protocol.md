# Saved-purchase sunset-forecast audit

This is an outcome-selected, offline follow-up to the
[fourth-seed veto](renewal-seed-veto.md), not a blinded test or a new rollout.
The observed deaths and purchase transfer are already known. No coefficients,
ecology rules, models, training objectives or device defaults change here.

## Fixed evidence and questions

Use only `artifacts/garden-renewal-seed-veto-v1`, manifest SHA-256
`dd44e765e15d4be5ed0c5c99273699718358ac8e5790af838162121620bcb5ae`.
Verify the complete saved bundle and require the forecast/resource-accounting
sources to match its frozen sources. **Zero new native calls**, including frame
replays; no training, mutation, deployment, commit or push.

At tick **4,620**, evaluate the existing `sunset-seed-reserve-v1` forecast at:

1. Founder shrub **2**'s actual fourth purchase in `control`.
2. Founder ground-cover **3**'s actual transferred purchase in `veto`.

Use the same parents in the opposite traces as observed no-purchase context,
not as independent plant-only counterfactuals. Reconstruct decision-point energy
by adding the actual 48-energy debit to the post-step census; verify purchase,
spent-flower, cooldown, seed-parent and resource ledgers. Current-step income
and upkeep have already happened and must not be counted again.

Reuse the existing Python accounting reference, checking its timing and integer
arithmetic against the frozen C implementation. Record its decision, projected
sunset energy, upkeep and reserve, then compare predicted versus actual income,
overflow, upkeep, growth, renewal and further seed spending during **(4,620,
4,800]**. Expose each ecology step, including the sunset payment. Do not explain
forecast error by extra spending unless the trace actually contains it.

Separate **(4,800, 6,705]**, the forecast's remaining-night horizon, from the
**6,720** dawn payment and subsequent recovery through **7,140**. There are 31
night upkeep payments after sunset, excluding dawn. Distinguish required upkeep
from actual paid upkeep when stores run short. Never reconstruct income or
spending on a death step: death clears telemetry; mark that step unaccounted and
stop the live ledger. Retain living checkpoints, shortages and death timing.

## Verification and interpretation

Repeat the offline calculation and compare exact portable JSON. Add boundary,
missing-sample, actual-purchase, cap/order, optional-spending and death-censoring
tests. Do not change the forecast to fit these two examples.

This answers whether the existing gate would reject **these observed bids** and
where its resource estimate errs. It cannot show what enabling the gate from
reset would do: earlier purchases, shared bank slots and downstream ecology
could all change. The forecast explicitly excludes dawn recovery and is not a
survival guarantee. Any revised gate or broader validation panel is a separate
proposal requiring discussion.
