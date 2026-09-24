# Full-pool actions: fixed host-only comparison

Freeze before outcome capture. Follow the saved node-pressure audit, not a
capacity increase or adult-survival intervention.

## Single intervention

Both arms use the previous sixteen-plant admission trajectory, including its
shared eight-slot prefix through tick 69120, with 512 nodes and eight seeds.
Only the `nonallocating` arm enables `--full-pool nonallocating` after tick
69120 inclusive (first eligible ecology step 69135).

When the pool is full, allow the existing growth-policy arbitration to run
under the same resource eligibility, cooldown and leaf-renewal precedence.
The selected WAIT/FINISH may execute under existing action/expense guards.
If the selected EXTEND has an available candidate and would allocate a node,
refuse it before expense, RNG, memory, growth phase, previous-tip or committed
telemetry updates. No fallback to another bid, forced FINISH or priority change.
An EXTEND with no geometrically available candidate retains its existing
non-allocating exhausted-tip behavior and cost; do not reinterpret it as a new
action. Guards on all paid non-allocating actions remain unchanged.

Record full-pool selected actions and allocation refusals separately from
ordinary energy/maintenance guards. Diagnostic storage must be bounded and
overflow detected. Configuration is per-world, reset off, outside the physical
hash and explicitly included in trace/frame metadata. Firmware rejects the
option; ordinary build scripts explicitly disable it.

No change to light, spacing, uptake, weather, tissue/plant lifetimes, costs,
controllers, model routing, seed order, fitness or automatic gardening.

## Frozen evidence and budget

- Parent `artifacts/garden-renewal-plant-slots-v1`, manifest
  `1cec5406f4f595972fde3cfea355d9f8c6c712fb279112d81f8e0ec3a77e0d3b`.
- Parent portable SHA256
  `5aca6ec16c07185aeb857f9267537e7346b0510b2dd7abd7f8f4977395059c82`.
- Node-pressure audit SHA256
  `f9f90fc58ac6976ef9c4d62144a7067370fe09a713600e94768d9c376381f778`.
- Reuse the parent's **sixteen** arm, `rainfed-crowded` seed `0d983a80`, N
  background/descendants, W founder 5, unchanged model bytes and routing.
- Horizon 245760 (64 garden days); closing window `(184320,245760]`.
- Exactly 20 research native calls: world/site traces in both arms, each
  repeated, and frames at 69120, 72960, 245760 in both arms, each repeated.
  Six predefined images. Regression tests are separate.
- Rebuilt control raw traces and frames must match the frozen sixteen arm
  byte-for-byte before candidate capture. Both arms must have equal physical
  prefixes through 69120, ignoring only the new configuration metadata.
- Preserve raw evidence and freeze protocol/source/binary/model/build receipts.
  Verify native change scope and reproduce every historical control result.
  Analysis recovery must never trigger recapture or replace observations.

## Evaluation, fixed before outcomes

Mechanism gate: at least one committed non-allocating FINISH or existing
exhausted-EXTEND at full entry, with no over-allocation or unaccounted cost.
Report WAITs separately; an uncalled baseline policy has no hypothetical
request to compare. Distinguish policy selection, allocation refusal, later
guard refusal and committed action.

For a positive selected-world signal, also require no regression from the
saved sixteen-arm control: at least 17 new full-day survivors, at least six
new full-day parents with full-day-surviving children, at most six incumbent
deaths, at least two endpoint species and two endpoint founder families.
Report all births/deaths, closing renewal, endpoint cohort, node/plant pressure,
seed lifetimes, live budgets and unknown terminal budgets regardless of gates.
Compare incumbents by stable pre-split identity; never pair new descendants
across divergent trajectories solely by numeric ID.

This is neither broader environment qualification nor a promised rescue for
tipless incumbents. Do not retune thresholds or run a sweep following results.

## Validation and stop

Strict warnings/UBSan; disabled/default behavior, exact activation boundary,
512/one-past bounds, both arbitration modes, WAIT/FINISH and geometric-exhaustion
behavior, actual-allocation refusal, state/expense preservation, existing guard
refusal, cooldown/leaf precedence, reset, isolation, parser/dependency/firmware
rejection and diagnostic bounds. Run default/experimental suites; repeat native
captures and analysis; independently verify the portable export and inspect all
six images. Update report/roadmap/issue #30. Stop uncommitted/unpushed with no
training, default promotion, extra horizon, extra research run or device flash.
