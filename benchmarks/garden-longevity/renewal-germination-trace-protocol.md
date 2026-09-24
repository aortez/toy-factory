# Open-gap germination checks — fixed observation-only trace

Follow the [controlled gap](renewal-controlled-gap.md) with actual sequential
seed-bank receipts. No model, ecology, rainfall, seed lifetime, spacing, capacity,
or intervention change. This is a selected development-world diagnostic, not
held-out validation or evidence for a general environmental schedule.

## Frozen inputs and window

- Parent bundle: `artifacts/garden-renewal-controlled-gap-v1`, manifest SHA-256
  `6ed1985364c40524565131bcc2684dfb4dc1ad6e80d8c4c47693e871fee2effb`.
- Portable parent SHA-256:
  `0b425bfa990c127cca2ca30b25327ddb62a15813f1210841460dbf6154cac352`.
- Same world `0d983a80`, rainfed-crowded, no gardener or recurring patches;
  same N background (`01b9d94a`), W only for reset founder 5 (`c9ea07fd`),
  no-night-growth routing, selective maintenance, both dark/capacity guards,
  512 nodes and eight plant/seed slots. All other build flags match the parent.
- Both original arms: untouched control, and founder flower 1 exported after
  tick 46,080 at column 3. Preserve the exact original export event/hashes.
- Advance from reset; capture an origin at **49,545**, then every ecology step
  through **57,360** inclusive (522 state checkpoints, 521 audited steps/arm).
  Keep all seeds' ordered visits in the window to check sequential side effects.
- Freeze treatment focal seed keys as `(parent, birth tick, column, generation)`:
  `(7, 49560, 3, 2)`, `(7, 53400, 4, 2)`, `(2, 57240, 5, 1)`.
  The first two mature at 49,680/53,520 and expire at 53,400/57,240;
  the comparison germinates at 57,360 into shrub 10. Match the original ledger,
  not newborn IDs across diverged arms. No replacement targets or time sweep.

## Budget and acceptance

Exactly **four experimental native calls**: control and gap trace, each repeated.
No new frame replays or training; the prior eight genuine native screenshots
remain the visual context. Routine synthetic/native regression fixtures are
outside this experiment budget. Extend only the existing host seed-attempt CLI
to replay focal routing and a named export strictly before the audit origin.
Do not change the authoritative simulation or the observer's kernel API.

Freeze source archive, protocol, binaries, compiler/build flags and models before
capture. Require byte-identical repeats, exactly 522 consecutive checkpoints per
arm, and equality with both saved world and site hashes/counters at every point.
Check the export receipt against the saved boundary. Reconcile all seed ages,
ordered visits, stage inventories, resource thresholds, germinations, expirations,
growth and reproduction using the existing sequential seed-audit validator.
Stop on drift, invalid provenance, missing targets or mismatched outcomes.

For each focal seed, retain all visits with tick, age, raw moisture/light,
actual mask/outcome, sequential index, capacity and world hash. Explicitly
separate expiry (age 256, no resource check) from mature checks (ages 8–255).
Count actual water-only/light-only/both/other blockers, resource extrema and
timing, and differences from post-step seed/site snapshots. For the successful
comparison retain the exact pre-germination resources and post-step debit/site
state. Do not equate a post-birth site's spacing veto with a failed check.
Summarize all-bank control/gap accounting for context, without claiming the
same focal seeds exist in both trajectories.

Repeat the analysis, verify a portable machine-readable export, run the relevant
host regressions, then record results and the next proposal in issue #30 and
the roadmap. Stop uncommitted; no push, firmware deployment, new ecology rule,
or further counterfactual is authorized by this trace.
