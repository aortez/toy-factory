# Landing-neighborhood observation contract

Status: **host-only shadow observer**, not an active controller input. The native
sampler in `src/garden_landing.c` implements this contract alongside the
independent [`Python reference`](../sim/garden_landing_contract.py). The
[shadow-check protocol](../benchmarks/garden-seasons/landing-shadow-protocol.md)
tests arithmetic, unchanged trajectories, signal variation and host overhead.
There is no neural feature/codec change, new growth policy, seed-release action,
ecology change or device deployment. The sensing permission below still needs
review before any trained agent consumes these signals.

## Why this sensor

The [waiting audit](../benchmarks/garden-seasons/seed-waits.md) found that space
often clears well before a suitable water/light interval. Among 465 births from
initially world-closed purchases, 345 seeds encountered spacing blockage, but
only seven had spacing as their final blocker. Median waiting time was 7.875
Garden days. An instantaneous open/closed release veto would lose information.

The current observation already contains tip/candidate-local light or moisture,
nearby tissue clearance, body/resource state and solar context. That clearance
is distance to **nodes of the candidate's tissue kind**, not seed-establishment
spacing around plant bases. Shoot candidates do not currently observe surface
water at their possible seed landing sites. Those are different questions.

The raw observation contains `sun_phase`; the current neural encoding exposes
sun **strength and ray direction**, not a direct phase feature. Reuse those
existing features and the eight-byte private plant memory; do not silently claim
that an additional solar-clock input is already encoded.

## Proposed sensing permission

Treat this as an explicit **virtual landing-area sensor**, not a claim about
literal botanical sensing. It reports nearby ground conditions and a short
environmental history at the possible landing sites of a seed. Its history is
shared terrain instrumentation, separate from a plant's learned memory. A new
branch or offspring can query earlier observations of that soil even though
that body did not personally observe them. That is a deliberate capability to
review before exposing it to a trained agent.

Do not provide the full grid, lineage IDs, time remaining until a neighbor dies,
exact decay countdown, future weather, RNG state/draws, eventual seed outcomes,
or an oracle score for a proposed action. The sampler may inspect occupied base
columns and dead/live flags internally; only aggregate features escape.

## Spatial contract: one current tip plus five growth endpoints

For a stem, project a hypothetical seed from the current tip and from each of
its five canonical growth endpoints. This supports both tip selection and
candidate ranking. The source need not already be a fertile flower: the value
means “the footprint **if** a seed were emitted here,” not permission to flower,
a prediction that this tip will be selected, or a replacement for current
first-ready-flower reproduction.

Use the active dispersal rule and the **parent's** dispersal trait:

- Flower-origin: origin is the source x coordinate converted to a soil column.
- Base-origin: every source uses the same parent base column. Moving a tip must
  not falsely advertise a placement benefit in this control.
- Narrow scattering enumerates six nominal direction/distance branches; wide
  scattering enumerates fourteen. Use the existing reflection and clamp rules.
- Keep repeated landing columns with their branch multiplicity. Averaging over
  unique columns would give the wrong edge weighting.
- Average each byte field with integer round-to-nearest, ties upward:
  `(sum + branch_count / 2) / branch_count`. This is **uniform nominal branch
  weighting**, not a conditional probability given the actual RNG. It deliberately
  ignores the negligible modulo bias retained in the diagnostic reach audit.

Root observations and out-of-bounds candidates have zero payload and an explicit
invalid bit. The adapter must use the canonical candidate's `IN_BOUNDS` flag,
including vertical bounds; this reference accepts `None` for such candidates.
In-bounds but occupied growth candidates retain a valid sensor packet; existing
growth-availability flags continue to govern actions. Height does not change
seed scattering in the current engine, and this sensor does not invent that
mechanic.

## Eight byte-valued fields per source

Every row below is averaged over the source's nominal landing branches.

| Field | Per-column meaning before projection |
| --- | --- |
| `space_free` | 255 if no occupied base is within three columns, otherwise 0 |
| `dead_only` | 255 if blocked by dead slots but no living slot, otherwise 0 |
| `water_now` | Current surface-soil moisture, 0–255 |
| `light_now` | Current ground-row illumination, 0–255 |
| `wet_ema` | Recent trace of surface moisture ≥12 |
| `light_ema` | Recent trace of ground illumination ≥80 |
| `wet_light_ema` | Recent trace of both resource thresholds passing **together** |
| `open_wet_light_ema` | Recent trace of both passing while spacing is also free |

Occupied slots include the querying plant and unreclaimed dead plants, exactly
as establishment spacing does. `dead_only` distinguishes visible turnover from
living competition without promising when reclamation will finish. It is not a
fraction of dead plants and does not add to `space_free` to make a complete map.

The joint traces are essential: wet nights alternating with dry sunny days can
have substantial separate wet/light traces but zero simultaneous opportunity.
Mean current water/light can similarly hide a mixture of different landing
columns; they are gradients, not an all-checks-pass flag.

Cold, global plant/node capacity, seed dormancy and seed-bank capacity are not
folded into these fields. `open_wet_light_ema` is a **local habitat signal**, not
a germination guarantee, success probability or fitness estimate. Existing
resource/state features remain separate; add global signals only through an
explicit later contract decision.

## Time contract and ownership

History is anchored to the 28 absolute **soil columns**, never to a plant slot,
node index or a tip's last location. Moving/growing a body projects the relevant
soil history; it does not carry a previous patch's environmental history to a
new location. Slot compaction cannot reassign the cache to another organism.

Proposed integration point: once per ecology step, **after the sequential seed
bank update and before the first plant's growth evaluation**. Capture moisture,
ground light and occupied-base masks together, then freeze them for all growth
bids in that step. Sampling happens even when every plant is on cooldown or no
policy can act. There are no updates inside `observe_tip` or policy callbacks.
Repeated queries, candidate order and the number of active tips cannot change
the sensor state. Only the normal winning bid updates private policy memory.

At that boundary, light is the engine's existing early-step cached illumination;
decomposition/maintenance and germination have since run. Do **not** perform an
extra light solve or silently substitute post-growth/final-refresh light. This
is a named pre-growth sampling phase, not the previous audit's purchase phase
or an earlier seed's exact sequential germination attempt. Same-step germinants
already occupy space and have debited surface water.

Use four bounded per-column exponential traces, updated at **every** ecology
step (256 samples per Garden day). Do not subsample brief resource overlaps:

```text
target = condition ? 65280 : 0        # 255 in unsigned Q8.8 storage
q_next = q + trunc_toward_zero((target - q) / 256)
byte = (q_next + 128) / 256           # integer arithmetic
```

An unsigned implementation can branch on the sign of the difference and shift
its nonnegative magnitude. It need not divide signed negatives or rely on
implementation-defined right shifts. Each trace fits `uint16_t`, stays within
0..65280 and needs no history ring. Truncation has a defined sub-byte dead band;
this is not an exact sliding-window count.

The decay timescale is approximately one Garden day. It retains exponentially
less weight from older observations; it is **not “the percentage of the last
day”**. After one continuously favorable day from zero, its byte value is about
160, not 255. Export a shared warmup count saturated at 256 so the consumer can
distinguish initialization from mature history. At reset, current terrain is
available but histories are zero with zero samples; it is not evidence of a
dry/dark past. Initial capture occurs after scenario setup, not midway through
world initialization.

This short trace cannot forecast an eight-day wait or a neighbor's lifetime.
It represents recent opportunities while occupancy represents a slower current
constraint. Longer memory is not justified or ruled out by this design.

One world owner owns one cache. Reset it on scenario/world reset; sampling must
advance exactly one ecology tick and reject duplicate, skipped or overflowed
ticks without mutation. Pure queries leave output unchanged on invalid input
in the proposed C API. For arbitrary checkpoint/restore, the cache must be
serialized alongside the world or reconstructed by replaying the prefix. Once
a policy consumes it, excluding it from deterministic state accounting would
be a bug. Do not copy a live cache into a fresh world or share one across
independent training workers.

## Layout and compute budget

The test compiles draft layouts with the host compiler and Cortex-M0+ compiler.
These are measured **C layout budgets**, not the Python reference's object sizes
and not a claim that these fields have been added to firmware.

| Proposed storage | Bytes |
| --- | ---: |
| Four `uint16_t` traces ×28 columns | 224 |
| Current water, light and occupancy bytes ×28 columns | 84 |
| Tick, warmup count, version and flags | 8 |
| Shared persistent cache total, per world | **316** |
| One packet: version/valid mask/warmup +6 sources ×8 bytes | **52** |
| Existing observation / hypothetical augmented observation | 104 / 156 |
| Existing encoded features / hypothetical augmented features | 77 / 126 |
| Existing model / weights-only extension budget | 1,204 / 1,412 |

The model estimate adds eight current-source features plus one warmup feature
to the 16-unit common layer, and eight candidate features to the 8-unit
candidate layer: `9×16 + 8×8 = 208` additional weight bytes. With the existing
16-byte file header, a corresponding format would need 1,428 bytes. This is a
budget, **not** a finalized codec/layout or a loadable version-2 model.

Invalid source fields must be neutralized in the future signed-byte encoder,
using existing tissue/in-bounds context and packet validity, rather than treating
an absent root/out-of-bounds sensor as measured drought. Keep history warmup
distinct from current resource values. Define/version that encoding explicitly
before changing the current model/feature ABI (both remain version 1 now).

Per ecology step, the cache needs at most 28×8 occupied-base comparisons and
112 short trace updates. Projection needs fourteen branch contributions per
field in wide mode. The current shoot offsets, together with the tip, span at
most **three distinct soil columns**; memoize those projections within one query
instead of doing six copies. That bounds this part at 3×14×8 =336 field additions
per stem query, plus geometry and rounding. Full-column or per-plant projection
caches are not proposed initially.

The prospective network adds up to 144 common MACs and 320 candidate MACs for a
five-candidate evaluation: 464 extra MACs per such bid, not per frame. The all-tip
path holds both current and best observations, so packet stack growth can be at
least 104 bytes there, plus the 49-byte larger feature buffer and helper scratch.
Exact stack high-water and CPU cost require the implemented C observer and a
target profile; layout arithmetic is not a performance guarantee.

## Shadow checkpoint and gate before any policy trial

1. Implement a host-only, caller-owned sampler at the named pre-growth boundary
   and a pure projector accepting the existing observation plus cache. Reuse
   production dispersal geometry without consuming RNG. Do not add policy
   actions, a seed veto, a new default or a new NN format at this checkpoint.
2. Wrap an unchanged policy to record packets and forward the existing decision
   unchanged. Validate sampling/clearance thresholds, reflection, dead-slot
   overlap, reset/warmup, stable history under reordered bids, invalid outputs,
   and full-world byte equality against ordinary stepping.
3. Run a predeclared bounded shadow panel. Retain exact trajectory hashes and
   repeatability; measure valid packet frequency, differences among candidate
   origins, redundant/constant features, history warmup and observer CPU/stack
   cost. Do not score candidate choices using future offspring outcomes.
4. Review that evidence and the virtual-sensing permission. Only then propose
   the versioned NN extension and controlled ablations: unchanged inputs,
   current landing signals only, then current plus history, all under identical
   ecology. Any policy gain must survive the existing durable-reproduction and
   diversity evaluation rather than a new proxy invented for this sensor.

The base-origin control must produce the same footprint for all source positions.
The flower-origin option remains experimental; this contract does not promote
it. An eventual policy comparison must not confound changed sensory inputs with
changed dispersal mechanics.

## Earlier design-only validation

The 13 reference tests cover occupied/dead overlap, all 28×5 wide origin/trait
combinations against the previous geometry implementation, reflected branch
multiplicity, exact trace recurrence and its precision bound, joint-versus-
marginal history, reset and invalid-step preservation, root/OOB handling,
query-order independence, the three-column bound and compiled layout budgets.
At the design checkpoint all 13 passed with both host and Cortex-M0+ layout
checks, alongside 122 default and 122 older-research CTests. The 178 existing
native C/header hashes then matched the seed-wait checkpoint. The subsequent
shadow implementation changes private world-step observer plumbing and shares
the existing pure dispersal transform; its protocol requires new noninterference
and regression checks. Those earlier results are not evidence for the new code.

```sh
docker compose run --rm -T firmware python3 -W error \
  sim/test_garden_landing_contract.py --cc gcc
docker compose run --rm -T firmware python3 -W error \
  sim/test_garden_landing_contract.py --arm \
  --cc /opt/toolchains/zephyr-sdk-1.0.1/gnu/arm-zephyr-eabi/bin/arm-zephyr-eabi-gcc
```

The embedded-C conventions guided fixed-width bounded storage, explicit sampling
ownership and failure contracts. No firmware build/flash, training, commit or
push was part of that design checkpoint. The shadow checkpoint includes a
firmware build check but still does not flash the device or activate the sensor.
