# Physics engine design

Toy Factory's physics engine is a deterministic, bounded 2D simulation for the
RP2040. Every milestone must run through the same platform-neutral C code on the
host and device, remain remotely stepable at exact tick boundaries, and produce
stable authoritative hashes.

This document describes the intended architecture and the current deterministic
reciprocal-rope milestone. Later milestones may revise measured capacities,
but they must retain the ownership, determinism, and overload contracts defined
here.

## Hardware and scheduling budget

The recommended fast build uses 250,396 bytes of the linker's 255 KiB Zephyr
RAM region and 221,976 bytes of flash. Its 115,200-byte framebuffer and
3,840-byte display transfer buffer dominate that footprint. The fixed-capacity
physics world is 22,636 bytes, including its 1,024-byte scratch grid, eight
slots each for distance, revolute, and prismatic joints and box sensors, two
12-particle ropes, and bounded pair-event storage. The serialized A/B
workspace is 33,304 bytes, is inactive during
normal play, and avoids placing a second world on a thread stack. The profile
command uses a 5,120-byte shell stack and most recently reached 4,200 bytes. The
856-byte render snapshot and collision traversal raised measured main/render
stack use to 4,016 and 4,044 bytes; both stacks are bounded at 5,120 bytes. The linked
image retains 10,724 bytes of Zephyr RAM headroom. The fast build also places
the physics hot path in SRAM and keeps the collision traversal in a separate,
bounded stack frame; this avoids core-0/core-1 XIP contention while the second
core rasterizes a full scene. Both builds route compiler integer division
through the RP2040's interrupt-safe hardware divider. Physical timing acceptance
is recorded after each candidate/solver configuration passes the native
containment and oracle gates.

The initial engine targets are:

- exact 120 Hz authoritative updates;
- no heap allocation or capacity growth after initialization;
- about 5 ms or less for a representative physics update on the PIM559;
- at most 32 KiB of physics state and scratch storage before larger features;
- stable replay for at least 10,000 ticks on the host and RP2040;
- immutable renderer snapshots that do not expose live world state; and
- explicit counters or errors for every bounded-capacity failure.

Physics quality never changes in response to elapsed wall time. Presentation
may coalesce snapshots, but simulation does not skip contacts or silently select
a cheaper model when the device is busy. The solver may stop before its fixed
iteration ceiling only after a complete pass applies no contact or joint
impulse, which is an exact deterministic fixed point rather than a timing
decision.

## Numeric model

The engine uses signed Q16.16 fixed-point values:

- position: pixels;
- linear velocity: pixels per simulation tick;
- linear acceleration: pixels per simulation tick squared;
- angular velocity: radians per simulation tick;
- unit vectors, material coefficients, and inverse mass: dimensionless; and
- time: exactly one 1/120-second tick per call.

Per-tick velocity avoids dividing every integration by 120 and makes each
authoritative update self-contained. Products and divisions use checked ranges
and 64-bit intermediates. Signed overflow, invalid shifts, and implementation-
defined structure hashing are forbidden. Integer square root and normalization
have explicit coincident-point behavior. Orientation is a wrapping unsigned
32-bit turn phase, so a quarter turn is exactly `0x40000000`. A 65-entry
quarter-wave sine table with deterministic integer interpolation supplies the
box bases; no floating-point library or platform trigonometry participates in
authoritative state.

The first milestone caps speed below the smallest canonical body diameter. This
bounds discrete-collision tunneling while continuous collision detection is
deferred. A later high-speed milestone must add swept tests or fixed substeps
rather than relying on a variable iteration count.

## State and ownership

The priority-0 main thread remains the only owner of authoritative state. The
USB shell is the priority-1 recovery and diagnostic control plane, while the
renderer runs below both at priority 2. Once two or more simulation deadlines
are due, the main loop reserves a one-millisecond recovery window, keeping the
bootloader command responsive without letting routine shell output preempt
on-time simulation. An isolated late tick may catch up first. Shell operations
that require authoritative state enqueue
acknowledged requests and block while the main thread services them. The
platform-neutral layers are:

```text
game input -> game world -> physics world -> immutable render snapshot
```

The physics world owns fixed-capacity body, static-segment, box-sensor,
distance-joint, revolute-joint, prismatic-joint, rope, physical-contact, and
pair-event arrays.
It is stored in static RAM because the application's main and renderer stacks
are deliberately bounded. Contacts are scratch results from the current update
and are excluded from the authoritative hash. The published event array is also
current-step scratch, but prior-active body/body, body/segment, and body/sensor
pair masks are persistent because the next step's event phase depends on them.
Body state, static geometry, sensor configuration, active-pair masks,
persistent joint and rope configuration, rope current/previous particle
positions, sleep masks and quiet counters, the last global acceleration,
numeric configuration, game tick count, and the canonical sensor-entry counter
are hashed field by field in stable order.
Per-step joint endpoints, normals, effective mass, accumulated impulse, and
event payloads are rebuilt scratch state and excluded.

Bodies and shapes receive stable numeric identifiers. Array order is never
derived from addresses, hash tables, allocation order, or unstable sorting.
Remote pause, reset, input injection, exact stepping, framebuffer capture, and
state hashing continue to cross the acknowledged main-thread request queue.
Real-time play publishes immutable snapshots at a deterministic 30 Hz cadence
while authoritative simulation remains at 120 Hz. Pause, reset, redraw, and
exact stepping force a current snapshot, so remote state and framebuffer checks
remain coherent even when presentation is deliberately slower than physics.

## Collision pipeline

Each update performs these bounded phases in order:

1. validate public state and input before mutation;
2. wake bodies when the global acceleration changes, then apply acceleration
   and semi-implicit Euler integration to awake bodies;
3. integrate the wrapping orientation phase and clamp linear/angular speed;
4. compute each box's orientation basis once for the contact pass and reuse each
   static segment's precomputed normal;
5. populate the uniform grid and deduplicate candidate pairs into fixed bitsets;
6. enumerate those candidates in stable body/body, body/segment, and
   body/sensor index order;
7. generate every circle/box/capsule body pairing, circle/box/capsule segment
   contacts, and exact circle/box/capsule sensor overlaps;
8. build deterministic contact/joint islands, propagate wake state, and skip
   constraints whose dynamic participants are all sleeping;
9. apply bounded contact, distance-joint, revolute-joint, and prismatic-joint
   positional correction;
10. run at most seven sequential-impulse contact and joint velocity iterations;
11. integrate fixed-capacity Verlet rope particles, then run six alternating
    length-constraint passes with three interleaved external-collision passes;
12. update whole-island sleep state; and
13. classify pair-level `BEGIN`, `STAY`, and `END` events, then publish counters
    and the newest immutable state.

Production uses a 16 x 16 screen-space grid of 16-pixel cells covering the
half-open range from 0 through 256 on each axis. Each cell stores one 16-bit body
mask, one eight-bit static-segment mask, and one eight-bit box-sensor mask.
The sensor mask occupies existing cell padding, so the grid remains 1,024 bytes.
Inclusive fixed-point AABBs occupy
every touched cell; deduplicated pair masks are then consumed in the same order
as the reference brute-force loops, preserving contact and solver order. Any
geometry outside the grid causes an explicit whole-step brute-force fallback.
The reference step remains callable by native tests, which compare every body,
contact, and authoritative hash over mixed 12-body replays.

## Profiling contract

Every physics step publishes deterministic work counters for possible and
retained pairs, cell insertions and occupancy, split narrow-phase tests,
manifolds and contact points, active contact pairs, sensor overlaps,
contact-event phases, awake/sleeping bodies, sleep/wake transitions, sleeping
contacts/joints, positional-correction visits, solver iterations and visits,
cached and changed contact rows, changed joint impulses, joint, motor, and
limit counts, separate motor/limit row work, spring visits and mutations,
conveyor contacts and tangent-row work, rope population/iterations/constraint
visits/mutations, reciprocal body position/velocity response, particle-collision
possible/candidate/contact/response counts, and unexpected broad-phase
fallbacks.
These counters are fixed-size scratch diagnostics and do not participate in the
authoritative hash.

The platform-neutral step API optionally accepts a caller-provided wrapping
32-bit cycle clock. No Zephyr header or clock is referenced by the physics or
game-world modules. A profiled call divides elapsed cycles into force/integration,
box geometry, grid/reference broad phase, body/body narrow phase, body/segment
narrow phase, body/sensor narrow phase, positional correction, velocity solving,
rope solving, and final clamping.
`other` is the difference between the complete public step and those regions;
it includes state validation plus timing-boundary overhead. `total` covers the
complete valid physics step. The canonical seven-body scene performs 58 clock
reads per measured step; the report includes a back-to-back clock-read delta so
instrumentation cost remains visible rather than silently folded into a result.

`picosystem profile compare [ticks]` operates only while the live simulation is
paused. It resets a separate canonical world, runs 120 unmeasured warm-up ticks,
then replays the same bounded input pattern for the grid and brute-force paths.
`picosystem profile sleep [ticks]` keeps the canonical world under neutral
input so it can settle and measure skipped sleep work. `picosystem profile
chain <links> [ticks]` uses the same machinery with a
deterministic 1-8-link revolute fixture under neutral gravity. Each individual
measured call runs with Zephyr thread preemption locked, while interrupts remain
enabled; the benchmark yields every 32 ticks outside the timed region so USB
and board servicing remain responsive. Rendering and snapshot publication are
absent by design. The two final worlds are checked by both authoritative hash
and field-by-field persistent state comparison.

Stage samples accumulate into 64 fine 32-microsecond bins followed by 64 coarse
128-microsecond bins, covering tails through 10.24 milliseconds without
increasing the fixed RAM footprint. The device reports count, mean, minimum,
histogram-derived p50/p95/p99, exact maximum, and 1/120-second budget violations
without per-tick logging. `make profile-ab` preserves the live run/pause mode
and writes the canonical result. `make profile-sleep` runs the neutral-settle
fixture. `make profile-chain` profiles a comma-separated
set of link counts over one USB session and writes an aggregate result. The
version-12 protocol adds reciprocal rope/body and particle-collision work while
retaining the rope timing stage, maximum segment-length error,
spring/conveyor/sleeping metrics, maximum
revolute-anchor separation, angular-limit violation, prismatic lateral/angular
error, and prismatic-limit violation for each mode. Those quality calculations
run after the measured step, so they do not contaminate the stage timings.
These isolated timings must not be compared directly with the live update value
from `game stats`, which
also contains game-demo and immutable-snapshot work and may be affected by
renderer and scheduler activity. Physical PIM559 baselines are recorded in
[`benchmarks/physics-profile`](../benchmarks/physics-profile/README.md).

Contacts carry a stable point, normal, penetration depth, restitution target,
and accumulated normal/tangent impulses. Box SAT selects from four face axes;
reference/incident edge clipping emits at most two stable manifold points.
Relative contact velocity includes `omega cross radius`, and effective mass plus
impulse application include inverse inertia. The solver applies friction and
restitution without allocating per-pair vectors. Exactly coincident centers use
an explicit identifier-based normal instead of random jitter.

A capsule is a local-X centerline segment swept by a radius. Its persistent
body representation reuses the bounded body array: `half_extent.x` stores the
centerline half-length, `half_extent.y` remains zero, and `radius` stores the
sweep. Public helpers resolve its ordered centerline endpoints and rectangular
shaft vertices. Collision generation uses fixed-point closest features and SAT
axes for capsule/circle, capsule/capsule, capsule/box, capsule/static-segment,
and capsule/box-sensor pairs. The same strict boundary as the existing shapes
applies: exact edge touching is not an overlap. Rotated crossings, endpoint
contacts, and separated-corner AABB false positives therefore do not require a
polygon approximation. Mass remains caller-specified; inverse inertia uses the
capsule's enclosing rectangle as a stable conservative gameplay approximation.

Distance joints are bilateral constraints with a positive target length. Anchor
A is body-local; anchor B is either local to a second body or fixed in world
space when body ID zero is selected. Anchors on bodies must lie inside their
circle, box, or capsule. One bounded positional correction runs before the
velocity pass; the shared seven-pass sequential solver then removes relative
anchor velocity, including angular effective mass and off-center torque. Joint array order is
solver order, and coincident endpoints use a stable joint-ID-derived axis.

An optional spring mode turns the same distance row into a bounded implicit
soft constraint. Angular frequency is expressed in radians per simulation tick,
damping ratio is dimensionless, and the accumulated spring impulse is clamped
to a configured positive per-tick maximum. Preparation derives stiffness,
damping, softness, and bias from the current effective mass. The velocity row
then solves the biased, softened constraint; spring distance error deliberately
skips the hard joint's positional correction. This lets a spring stretch and
settle without changing existing hard distance-joint behavior. Spring
configuration and target distance are authoritative and hashed, while derived
softness, bias, axes, and impulses are scratch. Changing an enabled spring's
target through the public setter wakes both dynamic endpoints.
Accepted frequency is 1/64 through 1/2 radian per tick, damping ratio is zero
through two, and maximum impulse is greater than zero through eight.

Each static segment may also carry a signed surface speed. Positive speed is
defined along its normalized start-to-end tangent, so conveyor direction is
stable even though collision normals may flip for two-sided contact. The belt
velocity changes only the contact's friction target: it never injects normal
velocity or restitution. Friction continues to cap the transferred impulse,
and a zero-friction body receives no conveyor motion. Mutating belt speed wakes
touching bodies; a powered contact prevents its island from sleeping while the
belt remains active. Segment speed is authoritative and hashed, while its
projected contact velocity is rebuilt scratch state.
Surface speed is bounded to plus or minus eight pixels per tick, matching the
engine's global velocity limit.

Revolute joints constrain two anchor points to coincide while allowing relative
rotation. They use the same body/world endpoint convention as distance joints.
Each step rebuilds the two world anchors and a symmetric 2 x 2 effective-mass
matrix, then solves one deterministic Q16.16 vector impulse in each correction
and velocity pass. Multiple joints may reference the same body, so chains and
branching mechanisms do not require a special aggregate type. Directly
connected bodies are excluded from collision generation by default; a joint's
explicit `collide_connected` flag opts that pair back in. Joint configuration
and that policy are authoritative, while world anchors, matrix terms, and
accumulated impulses remain scratch state.

A revolute motor adds a one-dimensional angular velocity row to the shared
projected Gauss-Seidel solver. Its signed Q16.16 target is radians per tick;
positive speed rotates body A counter-clockwise relative to body B. The total
impulse applied by that row during one step is clamped to the configured
positive maximum, so a stalled mechanism has bounded torque rather than an
unbounded velocity correction.

Angular limits are signed Q16.16 radians relative to the two bodies' creation
pose. A limit outside its one-degree slop receives a bounded positional
correction followed by a unilateral velocity row; an equal lower/upper pair is
a bilateral angular lock. Relative-angle conversion explicitly wraps unsigned
turns into the signed half-turn interval, including across zero. Motor and
limit impulses are per-step scratch rather than persistent warm-start state,
so the existing hash and reset contracts remain straightforward.
Angular correction runs during each scheduled revolute position pass, but a
limit alone does not request another whole-chain sweep; extra passes remain
driven by measured hinge-anchor separation.

Prismatic joints constrain anchor A to a rail attached to body B or fixed in
world space. The configured B-space axis is normalized once when the joint is
created. Its creation-pose axial projection and relative angle become the
zeroes for all later queries and limits. The constraint removes lateral motion
and relative rotation while leaving translation along the rail free.

A prismatic motor targets signed pixels per tick; positive speed moves body A
along body B's positive rail axis. Its accumulated per-step axial impulse is
clamped to the configured maximum. Lower and upper travel limits are signed
Q16.16 pixels relative to the creation pose. Lower and upper stops use
unilateral velocity rows, while equal limits form a bilateral axial lock. Up to
four alternating position sweeps correct lateral, angular, and active-limit
error before the shared seven-pass velocity solver handles the lateral,
angular, motor, and limit rows.

The solver caches each rail's lateral, axial, and angular effective masses for
the tick. Every actual solver velocity mutation increments a compact per-body
revision stamp. Contacts and prismatic joints retain the revisions seen after
their most recent solve, allowing later global iterations to skip a row until
another contact or joint changes either body. A conservative extra solve is
allowed if intervening impulses happen to cancel back to the same velocity; an
unchanged revision is always safe to skip. Revision stamps, world-space
geometry, limit state, and accumulated impulses are scratch diagnostics
excluded from the authoritative hash. Fixed-capacity configuration, creation
references, motor targets, limits, and collision policy remain persistent and
are hashed field by field.

## Position-based ropes

The rope subsystem reserves two ropes of at most 12 particles each. Particles
use Verlet position/previous-position state, the world's acceleration, a
255/256 velocity damping factor, and the rigid-body velocity bound. Six fixed
constraint passes alternate forward and reverse segment order; every correction
is capped at eight pixels per pass and coincident particles use an ID-derived
axis. This keeps runtime and overload behavior independent of wall time.

Either endpoint may be free or pinned to a world-space point or a validated
body-local anchor. A body pin is resolved after rigid-body solving on every
rope pass, so a rotating capsule or box carries the attached particle exactly.
Body pins are kinematic by default. Setting `reaction_enabled` makes a pin
reciprocal: its point effective mass includes body translation and rotation,
and segment correction plus radial velocity response is divided between the
particle and body. World endpoints cannot request reaction, and a rope cannot
use two reciprocal endpoints on the same body. Reciprocal body-to-body pins
join the rigid-body sleep graph; settled tethers may sleep, while an actual
rope correction or impulse wakes the affected body.

Collision is separately opt-in. A zero `collision_radius` disables it; a
positive radius from one through eight pixels treats each unpinned particle as
a circle. Three deterministically alternating collision passes are interleaved
with the six length passes. Conservative body bounds and segment AABBs reject
distant pairs before exact circle, box, capsule, and finite-segment tests. A
segment bound includes the particle's previous-to-current sweep; a center path
that crosses the finite segment is restored to its approach side, preventing a
length correction from tunneling through the arena perimeter. Particles collide
only with external rigid bodies and static segments: there is intentionally no
rope self-collision or rope-to-rope collision in this milestone. Static segments
remain immovable. Dynamic bodies
receive the equal-and-opposite normal position and velocity response, including
off-center angular response; rope contacts currently add neither restitution
nor friction. Rope response runs after the rigid contact/joint solver, so a
body moved by a rope is seen by ordinary rigid constraints on the following
tick.

Endpoint reaction flags, collision radius, and every current and previous
particle position are authoritative and hashed. Per-step particle, pass,
constraint, reciprocal-body, and collision counts are diagnostic scratch state.

## Sleeping and wake propagation

A body becomes eligible to sleep after 60 consecutive ticks (0.5 seconds) at
or below 1/64 pixel per tick of linear speed and 1/512 radian per tick of
angular speed. Contacting bodies and body-to-body joints form an undirected
graph each tick. Eligibility uses the minimum quiet count across each connected
component, so a complete island sleeps simultaneously; sleeping sets every
member's linear and angular velocity to exact zero.

Motor-enabled revolute and prismatic islands and bodies touching powered
conveyors never sleep. Springs participate in the ordinary joint graph and may
settle with their whole island. A change in global acceleration wakes every
sleeping body before integration, while an awake body
touching a sleeping island wakes that complete island before correction or
velocity solving. Explicit body wake and motor-target mutation are also
supported. Box sensors are deliberately absent from the wake graph: a sleeping
body continues to generate deterministic sensor `STAY` events without being
woken by observation.

Sleeping bodies remain in the grid, narrow phase, contact lifecycle, and
immutable snapshot. This lets new physical interactions wake them and preserves
sensor/event correctness. Integration, position correction, joint preparation,
and solver visits are skipped only when every dynamic participant in the row is
sleeping. The sleep mask, per-body quiet counters, and last global acceleration
are authoritative and hashed; the island graph is bounded per-step scratch.
Machine Lab renders sleeping bodies blue with white detail, while `status`,
`game stats`, schema-12 profiles, and `make profile-sleep` expose state,
transitions, and skipped constraints.

## Sensors and contact events

A box sensor is a fixed axis-aligned region with a stable nonzero identifier.
It participates in the same grid as physical geometry but never creates a
manifold, applies position correction, or changes velocity. Circle overlap uses
the exact closest point on the sensor box. Oriented-box overlap uses SAT across
the sensor's two axes and the body's two axes. Capsule overlap combines its
shaft and endpoint features against the box. These tests reject corner cases
where two AABBs overlap but the shapes do not. Edge-only touching is not an
overlap, matching the engine's strict physical-contact boundary.

Every current or previously active body/body, body/static-segment, and
body/box-sensor pair emits exactly one pair-level event per step. A newly active
pair emits `BEGIN`, a continuing pair emits `STAY`, and a pair that ceased to be
active emits `END`; inactive pairs emit nothing. A two-point physical manifold
still produces one event. Events are ordered by body A, then ascending body B,
segment, and sensor index. Publication iterates the union of current and prior
active masks, so quiet pairs consume no event-scan work. The fixed 258-record
buffer covers every physical pair plus all 12-by-8 body/sensor pairs, and an
unexpected capacity failure returns `-EOVERFLOW` instead of truncating output.

The canonical sensor has ID 501 and spans a 60 x 20 pixel region. Its `BEGIN`
events increment a saturated game-world entry counter. The sensor configuration,
prior-active masks, and entry counter are authoritative; the current event array
and work counters are scratch. This makes reset, native replay, remote exact
stepping, and device framebuffer assertions agree without retaining redundant
event payloads in the hash.

## Current milestone: reciprocal-rope machine lab

The flashable rigid-body lab contains:

- two dynamic circles, four boxes, and one rotating capsule, including a
  three-box hinged chain and one vertical press;
- four arena boundaries and two diagonal static ramps;
- gravity plus D-pad-directed global acceleration;
- all circle/box/capsule pairings plus finite, two-sided collision between each
  body shape and static segments;
- shape-derived inverse inertia, contact-point angular response, and two-point
  box manifolds;
- restitution, friction, one-to-four adaptive revolute/prismatic position
  sweeps, and a seven-pass-ceiling impulse solver with exact no-change
  termination;
- deterministic 16 x 16 grid filtering with brute-force fallback and oracle;
- a three-box chain joined by one world pin and two body-to-body revolute joints;
- a bounded motor on the world pin, one free middle hinge, and a plus/minus
  one-radian limit on the final hinge;
- a world-anchored prismatic press with a bounded motor that reverses at its
  creation-relative -48/0-pixel travel limits;
- one world-anchored, impulse-limited damped spring and one signed-speed
  diagonal conveyor whose direction is visible in the scene;
- one eight-particle cyan rope with seven 18-pixel segments pinned between the
  rotating capsule and a fixed world anchor, with reciprocal capsule response,
  one-pixel particle collision, six alternating length passes, and three
  collision passes;
- one fixed box sensor with exact circle/box/capsule overlap and a visible entry
  count;
- pair-level `BEGIN`, `STAY`, and `END` events for physical contacts and sensor
  overlaps;
- deterministic contact/joint-island sleeping, physical wake propagation, and
  sensor-only observation without wake;
- blue/white sleeping-body rendering, a yellow spring coil, green conveyor with
  directional chevrons, capsule end caps, a cyan rope, and remote
  mechanics/work diagnostics;
- old/new dirty footprints for every moved body, merged when they overlap; and
- body, filtered/possible-pair, grid occupancy, fallback, contact, sensor/event,
  solver, timing, and deterministic-hash diagnostics.

The milestone compile-time capacities are 12 dynamic bodies, eight static
segments, eight distance joints, eight revolute joints, eight prismatic joints,
eight box sensors, two ropes with up to 12 particles each, two contact points
per candidate manifold, 324 physical contact slots, and 258 pair-event slots:
enough for every possible body-body and body-segment combination at those
limits plus every body/sensor combination. The native capacity test activates
the complete pair universe in one step. The grid/reference oracle fills all 12
body slots while the flashable lab uses
seven to preserve its 120 Hz device budget. The capacities are deliberately
higher than the canonical demo population, so contact exhaustion cannot
partially update a valid world. These are milestone
limits, not the eventual product scale.

The D-pad tilts the acceleration field while preserving neutral downward
gravity. Yellow pins make every revolute anchor visible. Two cyan, render-only
rails show the press stroke without increasing broad-phase or contact work.
A magenta sensor border turns green while occupied, and the `Sxx` header field
counts entries modulo 100 without affecting the underlying saturated counter.
A still performs the asynchronous full-redraw comparison and B keeps the
bounded piezo test. Remote directional input has the same physics meaning as the
physical D-pad.

## Validation scenarios

The native suite covers:

- configuration and one-past-capacity rejection without state mutation;
- free integration and vector-speed clamping;
- equal-mass head-on circle response;
- unequal-mass collision response;
- arbitrary circle-segment bounce and endpoint collision;
- exact axis-aligned and quarter-turn box geometry;
- deterministic angular integration and shape-derived inertia;
- symmetric two-point box-floor manifolds and off-center angular impulse;
- box-box, circle-box, contained-circle, and box-segment response;
- capsule geometry and configuration boundaries; capsule/circle,
  capsule/capsule, capsule/box, and capsule/segment response; rotated crossing,
  exact-touch, endpoint, and separated-corner cases; and exact capsule/sensor
  overlap;
- stable coincident-center handling;
- validation, capacity, world/body endpoints, and stable coincident-endpoint
  handling for distance joints;
- world pendulum, body-to-body link, and off-center angular response over long
  replay;
- spring validation without partial mutation, damped convergence, bounded
  impulse, off-center torque, target mutation and wake, settled sleep, and
  body-to-body island wake;
- validation, capacity, world/body anchors, collision policy, stable hashing,
  and no-mutation failures for revolute joints;
- bounded world/body motors, torque saturation, lower/upper/equal limits,
  creation-pose reference angles, and signed turn wrap;
- validation, capacity, world/body rails, collision policy, stable hashing, and
  no-mutation failures for prismatic joints;
- free slider motion, lateral and angular locking, body-to-body rails, bounded
  motors, impulse saturation, lower/upper/equal travel limits, and motor reversal;
- rope validation and capacity preservation, free Verlet motion, pinned
  world/body endpoints, kinematic and reciprocal body pins, center-of-mass and
  off-center reaction, reciprocal sleep/wake behavior, invalid same-body
  reciprocal rejection, fixed six-pass work, bounded corrections, segment
  convergence, stable hashing, and exact grid/reference persistent-state
  equality;
- opt-in rope-particle collision against circles, boxes, capsules, and static
  segments; conservative pair rejection, equal-and-opposite dynamic-body
  response, bounded work counters, and explicit absence of self-collision;
- a four-link chain with multiple constraints on the middle bodies and bounded
  anchor separation over long replay;
- cell-boundary collisions and distant-pair rejection;
- explicit out-of-grid brute-force fallback;
- exact grid/reference equality for bodies and contacts over 1,000 mixed ticks;
- sensor validation/capacity preservation, circle corner cases, and rotated-box
  SAT rejection;
- physical and sensor `BEGIN`/`STAY`/`END` lifecycle ordering, quiet termination,
  and full 258-event capacity;
- exact 59/60-tick sleep eligibility, frozen zero-velocity persistence, and
  immediate global-acceleration wake before integration;
- whole distance-joint/contact-island sleeping and wake propagation, with
  motorized-island exclusion;
- positive and negative conveyor direction, friction-limited transfer,
  zero-friction isolation, powered-contact wake, and speed mutation;
- sensor `STAY` events across sleep without sensor-induced wake;
- exact grid/reference sensor/event equality over 1,000 mixed ticks;
- arena containment over long replay;
- deterministic reset and 10,000-tick replay;
- authoritative hash changes and reset recovery; and
- undefined-behavior sanitizer execution.

The native canonical reset is `abc2002c`, right-30 is `faaf80f7`, the
right-30/up-15 sequence reaches tick 45 at `aad794a0`, and a 10,000-tick replay
is `cdf463f7`. The bounded replay exercises every shape family and event phase,
never falls back, keeps every hinge and rail within the configured arena
tolerances, and runs exactly 42 rope-length visits per tick. A separate neutral
replay reaches tick 1,723 at `0a0ff729`. The PIM559 reproduced both exact
sequences; its tick-45 framebuffer is `df718839`, and the neutral sleep frame is
`88c2e21e` with one blue/white sleeping body.

Its schema-version-12 isolated 2,000-tick moving profile averaged 4.920 ms for
the grid and 5.313 ms for the brute-force reference, with 5.760/6.144 ms p95
and 6.935/7.470 ms maxima. Neither mode exceeded 8.333 ms, and both ended at
`1600fb06` with exact persistent-state agreement. The grid retained 7.133 of
70 possible rigid pairs per tick. Each tick considered 234 bounded
rope/collider pairs; 5.521 passed swept conservative bounds and 3.457 produced
contacts on average. The eight-particle rope stage averaged 1.661/1.643 ms,
changed 40.034 of its 42 length visits, and held maximum segment-length error to
0.856 pixel. Reciprocal endpoint position correction changed the capsule on
5.078 of six visits per tick; its radial velocity row changed on every tick.

The separate 2,000-tick neutral profile averaged 5.590/5.887 ms, reached
7.056/7.511 ms maxima, and ended at `34a04b59` with exact state agreement and no
deadline violations. Each mode recorded one body sleep transition, 1,039
sleeping body-ticks, and 1,038 skipped sleeping contacts; maximum rope error was
0.034 pixel. Powered belt contact remains awake while ordinary disconnected
islands may sleep.

With 30 Hz real-time snapshot publication and the RP2040 hardware-divider
wrappers, a concurrent full-frame window advanced 5,921 authoritative ticks at
120.0 Hz while presenting at 29.6 fps. It skipped one scheduled tick;
mean/maximum physics time was 6.638/17.326 ms, and the worst backlog was five
ticks. Main, render, and core-1 stack high-water marks were 4,016/5,120,
4,044/5,120, and 360/4,096 bytes.

For comparison, the preceding one-way schema-version-10 rope profile averaged
4.502/5.100 ms, reached 6.749/7.458 ms maxima, and ended at `91744aeb`. It did
not yet feed rope correction back into a body or collide rope particles with
the scene.

For comparison, the preceding schema-version-9 spring/conveyor image's moving
profile averaged 2.718/3.060 ms, reached 4.660/4.872 ms maxima, and ended at
`728d8683`. Its neutral profile averaged 3.630/3.989 ms and ended at
`3d88bb5f`. Those results did not yet include the capsule narrow-phase or rope
stage.

For comparison, the preceding schema-version-8 sleeping image's isolated
1,000-tick moving profile averaged 2.792 ms for
the grid path and 3.117 ms for the brute-force reference, with no budget
violations and exact final state agreement at `46020daa`. The changing input
kept all seven bodies awake. The grid retained 8.017 of 70 possible pairs and
0.685 of seven body/sensor tests per tick. Both modes observed 224 sensor
overlaps and emitted 182 begin, 523 stay, and 182 end events. Maximum
revolute-anchor, angular-limit, prismatic-lateral, prismatic-angular, and
travel-limit errors were 0.814 pixels, 0.0418 radian, 0.0885 pixels, 0.00461
radian, and 0.0651 pixels.

The separate 2,000-tick neutral profile recorded one sleep and one wake
transition. One body was asleep for 664 sampled body-ticks and 663 all-sleeping
contacts skipped correction and solver work; the motorized joint islands
correctly remained awake. Grid/reference state agreed exactly at `ea65ce22`,
with 3.456 and 3.787 ms means. This settled-contact fixture is not a direct
timing comparison with the moving workload. In the preceding sensor/event
image's clean concurrent 4,978-tick window, the SRAM-resident fast physics step
held 120.0 Hz while presenting at 29.8 fps, with zero skipped ticks and a
three-tick worst backlog. Mean/maximum physics time was 4.356/19.664 ms; only
four complete updates exceeded the 8.333 ms budget.

For historical comparison, the preceding revolute motor-and-limit image used
eight bodies, one distance joint, and a four-link chain. Its PIM559 profile
averaged 4.136 ms for the grid path and 4.418 ms for the brute-force reference,
with no budget violations and exact final state agreement at `a554f3c3`.
Maximum revolute-anchor separation was 0.947 pixels and maximum angular-limit
violation was 0.0175 radian. A 20,055-tick live window held 119.9 Hz with seven
skipped ticks while full-frame presentation remained at 29.8 fps. Concurrent
rendering and USB activity made 5,143 updates exceed 8.333 ms, with a 25.008 ms
maximum; faster intervening updates recovered most deadlines.

The first chain-scaling baseline isolated deterministic 4-, 6-, and 8-link
chains at 1.559, 2.202, and 2.819 ms mean. A single position pass held four and
six links to 0.495 and 1.314 pixels but let eight links separate by 51.867
pixels. The current solver now performs one forward position pass, checks every
anchor against a one-pixel target, and adds alternating reverse/forward passes
only as needed, with four as the hard ceiling. This keeps cached impulses as
per-step scratch rather than introducing persistent warm-start state.

The adaptive device profile averaged 1.569, 2.315, and 3.897 ms for 4/6/8
links, using 1.000, 1.172, and 2.552 position passes per tick. Maximum anchor
error was 0.495, 1.118, and 1.158 pixels; the 8-link maximum was 5.188 ms. All
cases remained within 120 Hz and matched the reference state exactly. The
sparse fixture also confirms that broad-phase selection must remain
workload-aware: the reference stayed 0.221-0.267 ms faster because grid setup
outweighed pair rejection.

Scenario shapes and measurement discipline are informed by the earlier
[allan.pizza physics work](https://github.com/aortez/aortez.github.io/pull/14):
keep a brute-force oracle, use seeded sparse/clustered/mixed-radius/boundary/
coincident/moving fixtures, distinguish candidate count from true contacts,
and time pipeline stages separately. The browser engine's dynamic object graph,
floating-point response, random runtime fragmentation, and variable frame delta
are design references rather than code to port.

## Planned extensions

1. Use reciprocal rope/body coupling and bounded particle collision to explore
   soft-body gameplay.
2. Evaluate bounded granular materials and approximate gravity or magnetic
   fields as separate gameplay systems.

Each extension must leave behind a playable device demo, a deterministic host
replay, an exact device sequence, and updated RAM/tick-time evidence.
