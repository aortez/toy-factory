# Fewer blocker fallback comparison

Test whether choosing a less obstructed destination improves shrub-family
replacement when every reachable seed destination is occupied. This changes
placement control, not ecology or the training objective. No training, firmware
promotion, or parameter search is included.

## Fixed rule

Only founder 2 and its descendants on rainfed weather seed `9a903368` use the new
fallback, starting with the first purchase after tick zero. Run each existing
repair variant (`none`, `light`, `condition`, `both`) unchanged.

Call the original placement policy once. If any active reachable destination
is spacing-clear, retain its result exactly. Otherwise count the stored plants
within fewer than three columns of each active destination, including retained
dead plants. Choose the minimum count. Break ties by scanning cyclically from
the original draw's choice index, preserving reflected aliases. Consume no new
random numbers. Other founder families retain their original placement policy.

Use the frozen dispersal schedule: six active choices through tick 626580,
fourteen afterwards. Count only active entries, never array padding. Do not
use future deaths, resource predictions, or a seed-purchase veto. Prices,
seed lifetime, maintenance, growth, weather, and clear-site daylight selection
are unchanged.

## Bounded comparison

Collect sixteen replays: four repair variants, original versus fewer-blocker
placement, and diagnostics off/on. Each runs through day 608 with the existing
eleven checkpoints at days 0, 32, 192, 208, 220, 222, 224, 256, 384, 512, 608.
Use two workers, 180 seconds per call, a 900-second collection budget, and
24 MiB of output per call. Use a fresh directory and retain failures; do not
silently rerun or replace them.

Diagnostics on adds the existing resource trace through day 256 and all-species
purchase trace during `[30,35)` days. Diagnostics off/on must match complete
simulation state, ancestry, histories, and pixels. The eight original-policy
controls must match the saved purchase comparison byte-for-byte, including
traces. The new policy has its own canonical identity and JSON metadata;
only an explicit validation projection may remove that wrapper.

Baseline archive: `leaf-population-purchases-results.json.gz`, SHA-256
`2d94fda91c831ac484c906588d0c9db5f0400ee031093c7a2aff9ba532b2f24d`.

## Validation and evaluation

Keep authenticated runtime inputs unchanged. Stage separate host-only source
adapters with an explicit borrowed placement-policy parameter; observation
must not activate the policy. Reuse the frozen replay's rollback and output
publication behavior. No mutable world pointer or per-step allocation escapes
the session.

Before collection, run the seven host suites and ten preparation tests. Add
focused checks for clear-site pass-through, six/fourteen-choice boundaries,
all-blocked ties and aliases, retained dead blockers, ancestry routing,
malformed input, callback failures, output preservation, identity, reset, and
logging parity. Freeze the binary, protocol, and source snapshots during runs.

Compare the unchanged renewal-first score: actual children of non-founder
parents, both surviving their own 32 days, capped at two per 64-day window
over `(192,576]`, with follow-up through day 608. Report all six windows,
established descendants, living/dormant/extinct family status, and competitor
families. Germination alone is not success. Use the early purchase trace to
verify the applied rule and describe the handoff, without claiming a specific
unrun counterfactual or generalization beyond this selected weather seed.
