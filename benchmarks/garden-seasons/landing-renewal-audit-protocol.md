# Saved-ledger renewal diagnosis v1

Retrospective, descriptive accounting on the completed five-seed training
experiment. No native simulation, retraining, reselection, new evaluation
seeds, ecology changes, scoring changes or firmware deployment.

Input: landing-multiseed-results.json.gz, SHA-256
c68d070a6f6a1859cb88fb90934f68e1928d22d2a79c94ffc9cdece631915bd4.
Audit all fourteen evaluated model/profile variants, all sixteen shared
conditions and all four late windows: 224 histories / 896 world-windows.
Training and manual-review results do not enter this diagnosis. Preserve the
initial and fixed-input controls, not only the improved live finalists.

Revalidate every complete native ledger and recompute its original history,
aggregate and paired comparisons before deriving diagnostics. Retain every
world, with per-model steady/seasonal and all-condition summaries. Compare all
six single/multi finalist pairs; highlight live / 34 and / 35 survival gains
alongside / 33's regression without dropping contrary cases.

## Temporal and cohort conventions

Windows remain (62,94], (94,126], (126,158], (158,190] Garden days, with their
existing two-day endpoint follow-up. Logic-day = 3840 ticks; samples every 15
ticks. Use exact recorded birth/death/purchase/end times, not image inference.

Separate seeds active at window start from purchases during the window.
Project all outcomes to window end + two days before describing germination,
expiry or child establishment. A pending seed is unconfirmed, never a failed
seed. Report whether its whole possible seed lifetime plus child-confirmation
day fits within the follow-up. The seed bank's 32-day lifetime makes the older
one-day-seed funnel assumptions invalid. Exclude follow-up-only purchases from
these two purchase cohorts, but retain them in the endpoint census.

Also count all actual germinations during the window, including those from
earlier purchases. Distinguish founder, established-descendant and unconfirmed-
descendant parents at purchase time. A one-day-established child is not
automatically eligible for renewal credit: its parent must itself be a
one-day-established non-founder. A historically established parent need not
still be alive when its child becomes established.

Partition sampled living-plant occupancy exactly into founders, unconfirmed
descendants, established children of founders, established children of
unconfirmed non-founders, credit-age-eligible descendants, and eligible
descendants that have aged out. Eligible credit ends exclusively 32 days after
the child's one-day confirmation. Eligible occupancy must equal the existing
bounded renewal credit exactly. Retain the inherited terminal tier separately:
it is measured after follow-up, not throughout the preceding window.

Partition child-credit bookkeeping into child count times window width minus
timing exclusion and death loss. For paired minimum-credit deltas use each
world's first weakest window (chronological tie-break), label when the selected
windows differ, and also retain all four matched-window deltas. This is exact
accounting, not a simulated benefit from preventing death or removing age caps.

## Interpretation and verification

Report zero-credit signatures as overlapping observations, not mutually
exclusive causal diagnoses: endpoint-established, no purchases, purchases but
no germinations, first-generation-only established occupancy, aged-out
eligible occupancy, and no sampled established occupancy. Retain seed funnels,
cohort identities, confirmations, endpoint populations and credit components
for further inspection. Zero purchases do not prove policy refusal; expiry
does not identify moisture, light, spacing, plant-slot or node-slot blockers.
The saved ledger lacks those per-attempt observations.

Use arithmetic/boundary fixtures and a direct sampled occupancy oracle.
Repeat the complete analysis, require input immutability, freeze input and
Python sources, independently recompute from the frozen bundle, and retain
portable results plus regression checks. Stop after explaining what these
records establish and what additional observations would be needed; do not
automatically expand the experiment or rewrite the objective.
