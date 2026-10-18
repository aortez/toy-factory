# Seed waiting-period diagnosis (read-only)

Freeze before collection. No change to ecology, seed placement, reproduction,
controller observations/actions, defaults or device firmware is proposed here.

## Cohort and controls

Replay all 64 saved flower-origin screen trajectories: eight shared weather
seeds, two layouts, two controllers and two origin arms, through Garden day 128.
Keep the eight-slot bank, wide scattering and offspring first-day reserve guard.
Reuse all 3,576 seed identities and purchase-site classes from the flower-site
audit, pinned by decompressed SHA-256
`0023876df42885ebdaae940ab13af3e442434f93cb3c51c1ddd4075a6f39c18d`.
The existing origin ledger supplies seed resolution and offspring outcomes.

Primary descriptive cohort: flower-origin seeds purchased when every soil
column was blocked (967 seeds; 465 germinated). Retain other purchases, both
arms, all individual worlds and weather/layout/controller/species partitions.
Expired seeds are observed failures to germinate within the 32-day lifetime;
pending seeds are right-censored, not failures. No selection by best run.

## Exact observation and phase boundaries

Use the existing caller-owned seed observer, through a new `--seed-waits` mode
of the host production collector. Do not change the authoritative step or
observer. Capture all sequential checks, resource values, blocker masks and
stage inventories. Expiration precedes checking: its zero-filled resource/mask
fields are **not an open site** and must never enter germination exposure counts.
Purchase sites are post-final-light-refresh snapshots; waiting sites are exact
sequential checks after rain, transport, uptake, decomposition and maintenance,
before growth and the final light refresh. Keep those phases distinct.

Match every ecology state hash/count to the old full trace; reconcile every
attempt in bank order against the previous bank, seed ledger and new births.
Reconstruct spacing/capacity from unreclaimed plants plus earlier same-step
germinants. Check moisture >=12, light >=80, age >=8, non-cold conditions,
plant count <8 and node count <=252 independently. Verify stage inventories
against removed dead plants, births, growth and purchases. Repeat all captures
byte-for-byte in new build/output directories; retain old bundles untouched.

## Measurements and attribution limits

Retain per-seed run-length encoded exact masks (including the global-dim-light
flag), first/first-mature/last check, terminal adjacent-check pair, and every
spacing release with the removed neighbor IDs. Summarize waiting-age bands,
mature-check exposure to each overlapping constraint, and the exact mask on
the check immediately preceding germination. That mask identifies the **last
remaining constraint(s)**, not every condition needed over the seed's lifetime.
Keep multiple simultaneous changes as combinations.

Distinguish globally dim light (climate-adjusted sun <80) from insufficient
ground light while the unobstructed sun is bright enough. A threshold crossing
in the latter class is not automatically tissue removal: solar angle and
strength also change. For water clearance retain coincident world rain and
reclamation; neither is a causal attribution of water at that specific cell.
Spacing can clear only when the blocking occupied plant slots are reclaimed;
verify the exact IDs disappeared and were already dead. Death alone does not
free the slot. Cold clearance is directly observed, separate from winter's
light effect. No replay intervention, future-leaking policy or causal fitness
claim. If deciding between rain, redistribution, uptake and decomposition needs
another observer, state that limitation rather than guessing.

## Evidence and decision

Retain portable per-seed histories and a recomputable summary, source/build/input
hashes, raw trace identities, malformed-input and censoring tests. Verify the
ordinary collector output is unchanged without the new option. Run focused
native/noninterference and host regression tests. No device testing is needed
for a host-only observation that leaves core sources unchanged.

Use the results to propose the smallest useful next investigation or AI signal.
Do not automatically add a current-site veto, seed drift, expiry change,
capacity increase or new controller action.
