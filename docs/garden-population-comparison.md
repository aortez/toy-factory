# Garden population comparison

Test whether the two frozen repair controllers retain useful generational
renewal when every founder family uses the same controller. The completed
[durability experiment](../benchmarks/garden-seasons/leaf-family-durability.md)
put one candidate family against selective residents. Its results do not answer
this population-level question.

The host session and viewer support population-wide policy assignment. The
matched panel below was specified before collection and has now completed:
see the [results and all captures](../benchmarks/garden-seasons/leaf-population.md).
This work does not train or select a new model, modify the ecology, or promote
a firmware default. The evidence retains the pre-collection protocol snapshot.

## Fixed conditions

Use the authenticated durability runtime and its unchanged W2 growth model,
recurrent growth memory, seasonal climate, rain and resource rules. No gardener,
forced deaths, reseeding, model mutation or mid-run policy replacement is allowed.

| Dimension | Values |
|---|---|
| Repair policy for every family | `initial`, `s1-g3-c4`, `s2-g3-c1` |
| Weather seeds | `58d7d6ca`, `9a903368`, `6b9c1a3e`, `59818bc3` |
| Layouts | `rainfed` with three founders; `rainfed-crowded` with five |
| Endpoint | Day 1376, or 5,283,840 logic ticks |
| Matched capture days | 0, 32, 192, 608, 992, 1376 |

These are the existing weather conditions, not new held-out generalization
evidence. All policies start from reset with identical initial conditions within
each seed/layout pair. The only intervention is repair-policy assignment to all
families rather than one family. Each world's descendants use that same fixed
repair model; ancestry remains separately recorded.

## Run budget and verification

Collect 24 primary runs: three policies times four seeds times two layouts.
Advance each world once through all six capture checkpoints, retaining native
240-by-240 pixels and complete state/history records. Run one unrendered repeat
of each primary condition, giving 48 population calls in total. Repeats must
match complete final JSON after excluding only the framebuffer CRC field.

Use at most four independent worker processes, a 180-second timeout per call,
and a 45-minute collection limit. Preserve failed attempts and stop on a failed
call or verification mismatch; do not silently retry, substitute a seed, or
extend the budget. Save the complete call roster, source/model/binary hashes,
process results and timings before declaring collection complete. Use a fresh
output directory and do not overwrite earlier evidence.

Before collection, pass the host session/viewer tests and all nine archived
single-family parity checks. The latter retain the original day-608 anchors,
day-1376 endpoints and daily-render replays. Unit-test trajectories and these
historical verification calls are separate from the 48 population calls.

## Measurements and interpretation

Reuse the existing renewal arithmetic for each initial founder family, including
families that become extinct. Actual children of non-founder parents qualify
only when both parent and child are alive at age 32 days; a death exactly on
that boundary does not qualify. Count at most two qualifying children per family
in each 64-day birth window. Report the same
three six-window periods as the durability study:

- Early births in days `(192, 576]`, followed through day 608.
- Middle births in days `(576, 960]`, followed through day 992.
- Late births in days `(960, 1344]`, followed through day 1376.

Average founder-family scores equally within each world and seed/layout worlds
equally within each policy. Retain every per-world and per-family result. Families
share a world and are not independent experimental replicates; report paired
weather-seed results without treating the 32 founder roles as 32 independent
worlds. The family-competition training objective remains unchanged.

Alongside renewal, report:

- Living population, births, deaths and established descendants over time.
- Whole-garden extinction and any intervals without living plants, distinguishing
  dormant seed-only states from extinction.
- Living, dormant and extinct founder families, including early losses.
- Living and pending species, seed reserves, and loss of initial diversity.
- Established-descendant occupancy and renewal in each period's closing window.

Use complete ledgers to reconstruct event timelines; screenshots are visual
evidence, not the source of demographic counts. Keep recent offspring without
enough follow-up separate from confirmed deaths and established survivors.
Present every matched capture, including sparse or empty gardens.

This is a descriptive ecological comparison, not a new combined fitness score
or an automatic promotion gate. A renewal advantage may coexist with worse
survival or diversity. Review those tradeoffs before proposing further training,
growth-controller changes, environmental changes or device deployment.

## Implementation boundary

`research_session` remains the exclusive owner of mutable state. Family scope
uses the original frozen family owner. Population scope uses the frozen uniform
replay entry point after checked initialization; models and setup remain private
and immutable. It keeps the ancestry envelope for validation and emits distinct
`TPR1` state and population JSON identities. Errors latch before any successful
record can be published. Frozen sources are rebuilt without modification;
archived binaries are never executed.

## Adapter validation

The population adapter passes all seven session/viewer/analysis CTest suites and the ten
archive-preparation tests. Its native tests include 3,072 exact comparisons with
the checked uniform replay, plus six 64-day trajectories spanning all policies
and layouts, descendants, reused slots and posthumous seeds. A build with
the viewer disabled also passes the session/CLI and analysis checks. The population
HUD and overlay were checked in a headless SDL control-event capture.

All nine single-family archive comparisons still reproduce complete JSON and
native pixels byte-for-byte, including day-1376 daily-render runs. They completed
in 268.0 seconds with the timeline-capable runner; receipts are in
`artifacts/garden-population-family-parity-v2`. These are regression checks, not
results from the planned population panel.

The timeline CLI advances one session through the fixed capture days. Its tests
compare checkpoint state and pixels against independent replays, reject reused
output directories, and preserve partial files on failure. The population scorer
reproduces all 288 archived family scores exactly, including strict age-32
survival and the original window boundaries. Additional tests cover dormant and
extinct families, posthumous seeds, population limits, and bounded collection.
The final analysis/evidence suite contains 20 tests, including archive portability
and exact pixel checks for all eight published comparison sheets.

## Collecting and reviewing evidence

Build with `make host-research-player-build` and run the nine-replay regression
check into a fresh directory before collecting. Use the same built binary for
both commands. The collector verifies that the parity receipt matches the
current binary and adapter sources, then runs the full host session/viewer and
archive-preparation tests before starting the 48-call budget.

```sh
docker compose run --rm -T host-player python3 -B sim/research_player/check_replay.py \
  --binary artifacts/garden-research-player-build-v1/research-replay \
  --out artifacts/garden-population-family-parity-v2
docker compose run --rm -T host-player python3 -B sim/experiments/leaf_population/collect_population.py \
  --binary artifacts/garden-research-player-build-v1/research-replay \
  --parity artifacts/garden-population-family-parity-v2 \
  --out artifacts/garden-population-comparison-v1
```

Every path must be fresh; use a new name for a separately authorized attempt.
The collector submits at most four calls, stops submitting on failure, and
retains outputs from calls already in flight. It compares all final state and
history fields between rendered primaries and unrendered repeats, verifies each
capture's size and CRC, checks every intermediate history against the final
ledger, and confirms matching initial conditions across policies.

The evidence tool recomputes all scores and demographic results offline. It can
also produce a gallery containing all 144 captures or a compressed archive with
deduplicated blobs and file hashes. Neither verification nor unpacking executes
archived programs or imports archived Python code.

```sh
python3 -B sim/experiments/leaf_population/population_evidence.py verify \
  artifacts/garden-population-comparison-v1
python3 -B sim/experiments/leaf_population/population_evidence.py gallery \
  artifacts/garden-population-comparison-v1 artifacts/garden-population-gallery-v1
```

Open the gallery's `index.html` for labeled captures. Each contact sheet has
policies `initial`, `s1-g3-c4`, `s2-g3-c1` from left to right and days
0, 32, 192, 608, 992, 1376 from top to bottom. See
[the viewer guide](garden-research-player.md) for interactive population playback.
All 48 calls and their verification checks passed; the results document the
renewal benefit alongside greater founder-family and species losses.
