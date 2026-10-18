# Water eligible arbitration comparison protocol

Test the single policy change proposed by the [refusal streak diagnosis](landing-stalls.md).
Freeze this protocol before collecting outcomes. This is a bounded host-only
screen, not permission to train, tune, promote, flash, commit or publish.

## Fixed comparison

Use all twelve worlds and six archived single/multi live finalists from the
completed water comparison, through Garden day 192. Pin its portable archive
SHA-256 `9f93b8047cfa6468bb7053d06f11b10dbe459e02fb36d37f1616c1ba56200e9c`
and the source archives from that comparison. All research ecology switches
remain OFF: ordinary dispersal, eight plant/seed slots, 256 nodes, fixed models,
seeded rain, no gardener or irrigation. Use the same UBSan binary for both arms.
Do not change observations, resource costs, weather, capacities or objective.

Control is the existing water-only reserve with post-selection WAIT vetoes.
Treatment uses the identical forecast and ages 1..256 of living descendants,
but excludes failed proposals before ranking. Founders and age 257 onward are
unchanged. Retain four water-upkeep payments, or one for a locally available
wetter-root destination, exactly as specified in the [water protocol](landing-water-protocol.md).
No energy guard, forced root choice, root bonus, threshold sweep or retraining.

## Selection and fallback

Every tip sees the same immutable body and recurrent memory. Select the
highest-priority eligible proposal, using the normal strict-greater, first-wins
tie order. Genuine neural WAIT proposals pass the forecast and compete normally.
Do not encode exclusion using a priority sentinel; every int16 priority is valid.

If no proposal qualifies, take the original highest-ranked proposal and convert
it to WAIT with empty candidate order. This is the existing guard's fallback:
retain that original winner's priority and next memory. Otherwise only the
eligible winner advances recurrent memory. Both paths retain normal single
nonce and growth-phase advancement. Candidate ordering within a bid is unchanged.
Do not retry another destination, credit hypothetical uptake or restrict reproduction.

## Identity and evidence

Use explicit `arbitration-replay` with required `--water-arbitration veto|eligible`.
Both outputs have kind `landing-arbitration-replay`, water config version 2, and
a GWA1 fingerprint including mode. Preserve the ordinary base fingerprint.
Do not alter the prior version-1 water command, GWP1 identities or trace format.
Ordinary training rejects the new replay kind. Firmware has no eligibility hook.

Record all queried bids in the guarded age window, bounded by the node capacity
per step. Retain tip identity/position, shared input memory, each proposed next
memory, priorities, actions, first-available destination forecasts and selected
indices. Verify selected telemetry and committed memory against actual world
state. Publish only after successful step completion. The Python collector
independently recomputes every forecast and winner and reconciles actual growth
with the five-stage resource observer. Losing bids are opportunities, not rescues.

Replay both arms traced, untraced with capture, and traced again with capture.
Require exact results, both trace streams and raw pixels. The veto control must
exactly reproduce historical guarded biology, recruitment trace, water winners,
scoring and image bytes. Retain the archived ordinary controls and their score
comparison; do not treat improvement over a failed guard as success over baseline.

## Measurements and decision

Reuse the unchanged four-window lexicographic renewal score. Count late-child
births in (62,190] with complete first-day follow-up, separately from qualifying
confirmation events in (62,190]. Retain censoring for recent seeds and children.
For both climates separately, require score-key and late-survivor retention,
at least one improved climate key or late qualifying-confirmation count, and no
earlier/new empty world. Empty means no living plant and no banked seed at an
event boundary. Apply these same gates against both the veto control and the
archived ordinary baseline; report each set independently.

Report all twelve pairs, adverse outcomes, births, death causes, resource
budgets, root allocation, seeds and terminal tiers. Quantify switches from the
original winner, winning action/tissue, genuine WAITs and all-refused fallbacks.
Do not match descendant IDs across diverged arms or infer individual rescues.
Even a pass is retrospective screening, not independent confirmation.

Save every final frame and one six-row sheet per climate, veto left and eligible
right in existing single/multi 33, 34, 35 order. Freeze binary, cache, sources,
tools, inputs and protocol, hash-check collection, then independently repeat
the frozen panel with one worker. Use fresh outputs, fail incomplete bundles,
and stop after this comparison without silently adding another intervention.
