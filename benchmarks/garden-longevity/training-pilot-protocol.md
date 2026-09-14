# Persistence v2 learning-signal pilot: frozen protocol

Run a tiny opt-in host search using the unchanged persistence-v2 ordering. Do
not enable the legacy trainer in experimental builds, change ecology or deploy
a model. This is a development pilot, not environment qualification or a final
generalization test. Freeze this protocol before candidate evaluation.

## Environment and clocks

Use the existing 512-node, eight-seed, wide-v1 dispersal, headroom-v1 water,
leaf-maintenance-v1 host environment, bottom drainage OFF and sunset seed reserve
OFF. Rainfed-crowded reset, selective leaf maintenance, no-night-growth-v1 policy
adapter, no gardener, no irrigation, no root-bootstrap or energy-reserve growth
adapter. Patch-death-v1 uses the existing fresh-1 schedule seed `e4d65e6f`.
These are explicit diagnostic host settings, not a firmware-capacity decision.

Run from reset through 192 Garden days: score (158,190], then fixed terminal
follow-up to day 192. Use exact birth/death timestamps, not the legacy trainer's
different establishment helper. The five-component world and six-component
aggregate keys must match `garden_lineage_persistence.py` exactly. Every trial
exports compact complete seed/lineage records and its final world hash.

Development world seeds: `13579bdf`, `2468ace1`.
Separate manual-review seeds: `6c696665`, `72657632`.
No selection from the review panel; no final test set is claimed. Do not replace
a weak, extinct or uninteresting seed. These literals have no matches in the
versioned/local source reports at protocol creation, but this is not a claim
about all possible prior private runs.

## Search budget and selection

Start from the frozen model CRC `dc5e849d` in the recruitment bundle. Preserve
its bytes and fingerprint. Search is serial deterministic (1+lambda): four
candidates INCLUDING the unchanged incumbent, two generations, three mutations
of the same generation-start parent per generation. Thus seven candidate
models total, evaluated on two development worlds each. No early stopping or
extra search in response to the outcomes. Exact ties retain the first incumbent.

Use the existing trainer's mutation algorithm without changing its draws:
32 parameter mutations per offspring, signed-byte deltas -8..8 excluding zero,
bias deltas -256..256 excluding zero, with existing clipping. Search RNG seed
`70696c32` is separate from world/weather/schedule RNG. Use a dedicated native
mutation tool sharing the extracted implementation with the old trainer;
record RNG state before/after, model bytes, CRC and all candidate scores.

Preserve generation zero and each completed generation's best-so-far model,
including unchanged champions. Reevaluate the unchanged initial controller as
the recorded control; do not silently substitute a later champion. Evaluate
each generation champion on both review worlds, without affecting selection.
Keep failed and empty worlds. No optional worker pool in this pilot.

## Visual and correctness evidence

Capture native 240x240 screenshots at tick 480 (early daylight), tick 2880
(first dawn after night), and tick 737280 (final daylight). Use the existing
production replayer in separate processes, with exactly matching reset, model,
policy, weather and patches. Compare every image's world hash against compact
evaluator checkpoints; validate RGB565 length/CRC. Keep frame/model/generation/
seed/tick identity, PNGs and a contact sheet, even for unchanged or failed gardens.

Before search, test C/Python score parity on all v2 arithmetic fixtures and
native compact-ledger equivalence against saved 512-node recruitment histories.
Verify compact observation is neutral against the existing independent replayer.
Run strict-warning/UBSan tests. Source/model/executable artifacts must be frozen.
Capture does not run inside the scored simulation or share RNG/state with search.

Repeat the complete deterministic search with capture disabled and require
identical candidate model bytes, development scores, champion history and world
hashes. Re-render/check the selected frames independently. Treat the duplicate
run as reproducibility evidence, not more model-search trials. Fail closed on
ledger/score/hash mismatch, capacity exhaustion, missing images or invalid model
data. Do not silently keep a partly completed generation as success.

Use an optimized dedicated host build with UBSan retained and compare known
histories before accepting it. Record build/source identities and timings;
optimization level does not change this experiment's rules. No changes while
collection is in flight. Reports and portable images may be added afterward.

## Interpretation and stop

Report every generation, accepted/rejected mutations, development versus review
outcomes, unchanged-model control, both terminal states, renewal/live-time and
event metrics, species/founder-family presence, runtime and storage. Show the
actual pictures; visual appeal is evidence for discussion, not extra fitness.

Success means a working reproducible end-to-end loop and useful evidence about
its learning signal, not necessarily a better champion. Do not promote a model
on a seven-candidate search. Keep v2's known finite-window and population-time
preferences visible. Stop after this budget and discuss the observed results
before expanding training, changing the score, or adjusting ecology. No commit
or push is included unless separately requested.
