# Identify the lost winter leaf income

Status: **FROZEN before passive replays**. The [saved energy history](landing-energy-history.md)
locates a mature plant's deficit in lower winter light income after equal full
stores, with unchanged demand and no further spending. Determine which recorded
leaf illumination and shade sources account for that loss, without changing
the simulation rules.

## Fixed pair and capture budget

Keep the selected fixed-order, dawn-guard, focal-root, capped-uptake pair without
wicking. The target is plant 20, born at tick 590640 at column 3. Pin the energy
history result at SHA-256
`ad05d00dce06ffdfbf5208586dfa03aed07277f0ec2f9ef77f83d78e842540a8`
and its original late-dispersal result at
`390669aba064732072c82e2170ad1d6f7872612710bc1c6501ad3351c8ad3b62`.
Use the source bundle whose manifest hashes to
`4a94df9dcc4f53c980e3631b58dc3fd853c3f03a68678d335127ab09f7a83001`.

Perform **two full-horizon passive replays**, one per archived executable:
ordinary `cap` and broader `wide-cap`, through tick 983040. Reuse their archived
model bytes, build settings and native binaries; do not rebuild or change
ecology, training, weather, controller, seed placement rules or device defaults.
Only replace the existing uptake-observation window with two inclusive windows:
**974400–976305** for the winter daylight period and **978240–979230** for the
following dawn through the observed shared refill. At 15-tick spacing these are
128 and 67 observations per arm.

Keep all other arguments and trace bounds unchanged. Require exact original
results, final pixels and compressed stand, adult, direction and reach traces.
The earlier experiment already retained determinism repeats; these two new
calls establish observer neutrality, not independent replication. Stop on a
neutrality or provenance failure. Do not run additional long trials or tune
parameters in response to the outcomes.

Archive binaries, model, source provenance, capture arguments and all new raw
traces in a fresh output bundle. Preserve existing artifacts. Analysis and
verification must be separately callable without launching simulations.

## Reconstruct actual leaf income

Validate complete uptake trace framing and exact window coverage. Retain the
observed sun, all shade sources and leaf records, and the full light field.
Reconstruct per-cell shade using center/neighbor contributions, edge clipping
and the 255 opacity cap. Reconstruct the additive ray caster with its signed
rounding, boundary exit and 24-unit ambient floor. Require every light cell to
match the observation and each leaf's income to equal `local_light // 64`.

Link source lineage and live/dead state to the ledger. Match all living plants'
leaf counts and energy income to the actual pre-maintenance adult receipts,
using the preceding step for pre-growth leaf counts. Reconcile the target's
receipts with the pinned complete energy history. Root/soil data remain in the
raw uptake trace but are not a new water-attribution analysis.

Compare target leaf coordinates as multisets, retaining duplicate cells rather
than matching mutable node indices. Also compare target-owned shade geometry.
If geometry differs, retain that result rather than attributing every difference
to neighbors. Report exact per-leaf light and income differences in the first
recorded income divergence, and account for total differences over morning,
afternoon and the following dawn/refill window. Retain improvements and ties,
not only leaves that lose income.

## Diagnose shade without simulating removals

On each saved geometry compute light with no shade, self shade only, without
self shade, without other living plants and without decomposing bodies.
Separately remove each observed source lineage's shade and report the resulting
target income change, keeping the actual sun, leaf positions and other sources
fixed. Preserve full source identities and their birth/death/site context.

These are instantaneous frozen-geometry diagnostics, not predictions of plant
removal, changed growth, changed seed outcomes or survival. Single-owner gains
are generally non-additive because cell saturation, ambient floors and integer
income thresholds interact; do not sum them as an allocation of the observed
loss. At the first actual loss, retain the complete shade contributions on each
affected leaf's ray, including clipping and floor effects.

## Decision boundary and validation

The result should distinguish target morphology, self-shading, living-neighbor
shade and dead-body shade, and establish whether integer thresholds amplify
the observed loss. This remains one selected history from the complete panel,
not a generalization or rule-promotion test. No ecology fix follows automatically.

Save a compact portable result, exact source/trace identities and a report.
Test argument isolation, field reconstruction, signed-ray/edge handling,
saturation and threshold interactions, source identity/geometry, complete
coverage, neutrality, tamper rejection and fresh-output protection. Recompute
the result offline, independently reextract the new raw bundle, and require
byte-identical repeated analysis exports with subprocess launching forbidden.
