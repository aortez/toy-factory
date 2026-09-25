# Rescued-parent seed audit — saved-trace protocol

Follow the two full-night-capacity rescues without changing the environment.
Their 15 and 28 lifetime seeds and zero observed offspring are already known;
destinations, expiry/pending outcomes and blocker frequencies have not yet been
aggregated for this audit. These are selected explanatory development cases,
not independent validation.

## Fixed inputs and scope

Use only the completed capacity bundle
`artifacts/garden-renewal-capacity-guard-v1`, manifest SHA-256
`f8e7237a0db166e15fe802c12e78b5a0f76b539fd853888d7fbc2efdc7a33d2f`.
Pin its portable summary SHA-256
`25a11c7b3033aaecdc6f6f5e388953ebe551be2d1072a6c5edf715231052a03e`.
Re-verify all parent captures, source/build hashes, repeated analysis results
and images without executing native binaries.

Analyze these two worlds in both saved arms, through tick 245,760 / day 64:

| World | Target | First capacity refusal | Known treatment seed purchases |
| --- | --- | ---: | ---: |
| `0d983a80`, no patches | Shrub 7 | 37,605 | 15 |
| `58e36558`, patches | Ground-cover 12 | 134,940 | 28 |

Retain the control target's complete seed history too, including an empty
history. Reconstruct **every seed in all four traces** to validate the ordered
bank, counters, child ancestry, per-parent purchases and final pending entries.
Focus the detailed destination/blocker analysis on the two target parents;
keep all whole-world seed lifetimes and whole/closing cohort context.

Zero new experimental native runs, screenshots, training, model mutation,
firmware deployment, ecology/controller changes, commit or push. Only offline
analysis, synthetic tests and evidence/docs are in scope. Update issue 30 and
stop with findings and a next proposal.

## Questions and checks

1. For all 43 treatment seeds: creation tick, destination, age/dormancy,
   germination/expiry/endpoint censoring, and first/last mature observations.
   Reconcile the outcome partition, all per-parent counters and offspring IDs.
   Eight ecology steps of dormancy precede eligibility; expiry at age 256
   happens before a germination check. End-of-trace seeds are not failures.
2. Report destination counts, overlapping blocker masks, spacing occupants
   (living and unreclaimed dead), resource/plant/node limits, and observations
   with no recorded blockers. Separate whole lifetime, since-refusal and
   day-48–64 observations. Repeated snapshots are exposure, not independent
   germination attempts or probabilities. Keep per-seed and per-column results.
3. The logged masks are post-step queries, not decision-stage receipts. Report
   them as such. Separately derive a **stable spacing witness**: an occupant
   within the native exclusion distance, present in the ordinary post-step
   census but born before the current tick, necessarily existed throughout
   this seed-check loop. Reclamation precedes the loop; later growth/seed
   production cannot introduce/remove such a plant. Newborn occupants are
   excluded from that witness. Dead but unreclaimed plants still count.
   This proves a spacing veto when such a witness exists, but its absence
   does not prove a free site. Likewise eight stable occupants prove the
   plant-slot cap was full; a post-step cap alone may include later births.
4. Preserve patch ordering: ordinary and post-patch samples are not separate
   ecology steps, and patches preserve the seed bank. Do not infer exact
   decision-stage light/water, unseen free destinations, probabilities under
   another dispersal rule, or successful counterfactual recruitment.
5. Identify occupants by within-run lineage and location, with parent/self,
   founder/descendant and alive/dead distinctions. Do not match later newborn
   IDs across arms. Verify destination support from the unchanged wide
   dispersal geometry; support is not a probability distribution or RNG replay.

## Verification and stopping rule

Reuse the existing ordered seed-ledger reconstruction without changing its
historical results. Reject inconsistent/ambiguous transitions. Add synthetic
tests for empty controls, expiry/pending boundaries, ordered duplicate seeds,
window separation, stable versus same-step newborn witnesses, dead occupants,
overlapping blockers, destination reflection, corruption and truncation.

Require unchanged native files/input hashes, exact repeated offline results,
portable export verification and proportional host regression tests. Export
complete four-trace seed lifetimes, target details, per-window/column/occupant
summaries and provenance. Use the existing fixed screenshots as visual context;
do not select or create new images for this audit. Stop before implementing any
spacing, lifetime, dispersal or arbitration change.
