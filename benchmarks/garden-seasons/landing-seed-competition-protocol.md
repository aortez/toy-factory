# Pending-seed competition: bounded offline audit

This is an analysis plan for saved, already observed histories, not a new
preregistered experiment. Separate changes in the winning seed from changes in
the number of seedlings an opening can admit. Finish with a recommendation;
discuss any new experiment before implementing it.

## Inputs and scope

Use all five worlds, control and treatment, from
[paid seed replacement](landing-seed-replacement.md). Preserve every competing
seed and the seven original focal plants and five first recruits, including
non-producers. These selected histories share one weather seed and model;
they are not independent environmental replication.

Pin the replacement capture `landing-seed-replacement-results.json.gz` to
SHA-256 `e856d8877a34747bce4c5ade78e3492acb0f211379ddcb843e4a44a2ec868b4a`
and its raw manifest to
`6f5f737dcb8147a488ad0339a553d7f81823db65d5df8a097332112ff15de465`.
Verify the complete portable capture with its existing verifier. Authenticate
each selected raw stand, adult and reach trace against the pinned capture and
manifest, and check its complete clock/header/footer. Do not claim to repeat
the earlier whole-bundle resource accounting or observer-neutrality tests.

No native simulation, training, deployment, increased capacity, relaxed
dormancy/spacing, additional deaths or policy/rule change belongs to this audit.
Leave the earlier collectors, protocols and results unchanged.

## Windows and evidence

Derive each world's reclamation tick from the preceding second-opening audit;
validate that boundary in both new arms. Derive each arm's closing tick from
its first post-day-288 birth, without extending a window to seek a success.
Retain every ecology step from one step before reclamation through one step
after closing. Retain the actual purchase receipt and stored-plant inventory
for every seed present in that interval, including seeds bought earlier.

Keep exact seed identity (parent plus purchase tick), complete ledger fate,
actual dispersal support including reflected aliases, age, column and all
simultaneous germination blockers. Validate complete seed-check and purchase
coverage, replacements versus expiries, sequential admission order, bank
balances and stored-plant changes. A new purchase is checked only on a later
step. A successful seed consumes capacity before the next seed is checked.

Site masks describe mature seeds at that exact observed check. Check their
spacing, global plant/node capacity, cold and actual-column resource bits.
For each seed, count checks before refill at which a different reachable
column passes every observed site gate. Report mature and dormant seeds
separately: a good site does not bypass eight ecology steps of dormancy.
Retain exact first/last witnesses and the closing-step queue, rather than
collapsing a seed's history to its final fate.

Also report geometric alternatives alone, and the maximum number of
mutually three-column-spaced new bases in the currently clear columns.
Bound immediate admissions by that packing count, free stored-plant slots,
and available four-node seedling capacity. Packing is a geometric bound,
not a guarantee of water, light, survival or later reproduction. Node capacity
at each check is the observed pre-admission count, not an endpoint estimate.

Keep every followed plant's competing seeds and post-onset purchases/children,
including explicit zeros. Use the complete day-320 ledgers to identify later
births and deaths, with pending seeds and 32-day survival still censored where
appropriate. Do not infer that a currently blocked seed is permanently useless.

## Interpretation, output and validation

A legal alternative is an observed same-state opportunity, not a replayed
counterfactual: relocating a seed could change earlier births, shade, water,
later capacity and the rest of the queue. Do not assemble a fictional winning
history by changing its column or trait at each check. Do not favor a selected
lineage merely to make the followed cohort win.

Produce a compact portable evidence artifact, independently recomputed analysis,
tests and a short report. Include all ten histories, input/source hashes and
zero native/training calls. Test missing/reordered checks and windows, seed
identity, dormancy, sequential refill, capacity versus geometry, support aliases,
omitted cohorts and tampered derived results. Verify deterministic regeneration
with subprocess launches forbidden.

Recommend whether pending-seed-aware placement could address the measured
limitation, or whether turnover/capacity deserves the next controlled test.
List any additional controller information such a proposal would require,
without adding observations or starting a new experiment in this task.
