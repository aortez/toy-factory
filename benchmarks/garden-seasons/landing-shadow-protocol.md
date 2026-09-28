# Landing sensor shadow check

Freeze this protocol, sources and build identities before collecting results.
Implement only the [landing observation contract](../../docs/garden-landing-observation.md)
as caller-owned host diagnostics. No new neural input, policy decision, seed
action, ecology parameter, default, trained model or device deployment.

## Fixed panel

Use the first and last weather seeds of the saved flower-origin panel:
`ed52188c` and `82deacfd`, both rainfed layouts, baseline/adaptive controllers,
and both base/flower origin arms. That is 16 worlds, **two shared weather
realizations**, not 16 independent weather replicates. Run 128 Garden days,
eight seed slots, wide dispersal, seasonal climate and the unchanged first-day
offspring reserve guard. Repeat every capture byte-for-byte in new directories.
Do not select by outcome or train/search parameters.

Pin the original flower-origin evidence using its existing loader and the
seed-waits summary SHA-256
`5d089e00e11e180bb1cb18c7143a05e67c0db0c0bed9c440ac58d61f38b640c2`.
All prior frozen sources must match except `src/garden_world.c` (private audit
plumbing and shared pure geometry) and `sim/CMakeLists.txt` (host targets).
New observer/collector/test files are included in the new provenance.

## Verification

Capture initial terrain and every ecology sample, including ticks with no
policy bids. The sampler runs after seed admission and before growth; cached
light remains the existing early-step light solve. It never recomputes light.
Every bid records its source coordinates, parent trait, canonical bounds and
availability flags, proposed action/priority and the eight-field packet.

Match every authoritative state hash and seed-creation count to the old trace;
also match every bid's identity, coordinates, candidate flags and action/priority.
Reconstruct occupied masks from old live/dead base slots. Independently recompute
every Q8.8 history update and projected packet with the Python contract. Native
tests separately cover the pre-growth phase, germination's water debit, bytewise
world equality, duplicate/skipped samples, rollback, reset, replay, root/OOB
masking, and dead-slot spacing. No future outcomes enter an observation.

## Descriptive measurements

Keep daily per-world histograms for all eight fields, counts of stem/root bids,
valid sources, queries with at least two available growth endpoints, and queries
whose **available** endpoints differ. Also count variation across in-bounds
endpoints separately; invalid zero payloads must never manufacture variation.
Record the largest number of distinct projected origins per query; canonical
shoots should need no more than three. Base-origin queries must have no candidate
variation. Keep one fixed first-stem receipt per day (or null when absent), with
its terrain/history, for manual inspection and portable arithmetic tests.

Report whole-run, warmed (after day one), and closing (last 16 days) aggregates,
plus weather/layout/controller partitions. Do not infer fitness benefit from
spatial variation, count bids as independent ecological replicates, equate EMA
to an exact trailing-day percentage, or call the joint signal a success probability.

Dense traces remain under artifacts with hashes and a raw re-verification mode.
Portable daily histograms/first receipts reproduce aggregate summaries but are
**not** a substitute for replaying the entire dense trace.

## Cost check

Separate Release/unsanitized host build; one declared case: flower-origin,
rainfed-crowded, adaptive, `ed52188c`, 128 days. Five repeats each of ordinary
stepping, sampling only, and sampling plus every-bid projection. Rotate mode
order each repetition, single process at a time, and use process CPU time for
the simulation loop (no per-frame JSON, no final hashing in the timed interval).
Keep all repetitions, identical final hashes and creation counts. This measures
the defensive host adapter, including validation and callback overhead; it is
not an RP2040 timing prediction. Record Release flags and compiler identity.

Check 316-byte persistent cache / 52-byte output layouts with native and ARM
compilers. Report Cortex-M0+ compiler static frame sizes for observer functions
separately from persistent storage; they are not a measured call-chain stack
high-water mark. Run full ordinary/research host suites and a firmware build
because the private world-step plumbing and shared geometry were refactored.
