# Physics engine design

Toy Factory's physics engine is a deterministic, bounded 2D simulation for the
RP2040. Every milestone must run through the same platform-neutral C code on the
host and device, remain remotely stepable at exact tick boundaries, and produce
stable authoritative hashes.

This document describes the intended architecture and the current uniform-grid
rigid-body milestone. Later milestones may revise measured capacities, but they
must retain the ownership, determinism, and overload contracts defined here.

## Hardware and scheduling budget

The profiling build uses 190,652 bytes of the linker's 263 KiB RAM region and
151,952 bytes of flash. Its 115,200-byte framebuffer and 3,840-byte display
transfer buffer dominate that footprint. The fixed-capacity physics world is
15,024 bytes, including its 1,024-byte scratch grid and per-step deterministic
work counters. The serialized A/B workspace is 21,360 bytes, is inactive during
normal play, and avoids placing a second world on a thread stack. The profile
command's 4,096-byte shell stack measured a 2,823-byte high-water mark. The
linked image retains roughly 77 KiB of RAM headroom. Physical timing acceptance
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
iteration ceiling only after a complete pass applies no normal or tangent
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
renderer runs below both at priority 2. A main loop that has already missed its
next deadline reserves a one-millisecond recovery window, keeping the
bootloader command responsive without letting routine shell output preempt
on-time simulation. Shell operations that require authoritative state enqueue
acknowledged requests and block while the main thread services them. The
platform-neutral layers are:

```text
game input -> game world -> physics world -> immutable render snapshot
```

The physics world owns fixed-capacity body, static-segment, and contact arrays.
It is stored in static RAM because the application's main and renderer stacks
are deliberately bounded. Contacts are scratch results from the current update
and are excluded from the authoritative hash; body state, static geometry,
numeric configuration, and game tick count are hashed field by field in stable
order.

Bodies and shapes receive stable numeric identifiers. Array order is never
derived from addresses, hash tables, allocation order, or unstable sorting.
Remote pause, reset, input injection, exact stepping, framebuffer capture, and
state hashing continue to cross the acknowledged main-thread request queue.

## Collision pipeline

Each update performs these bounded phases in order:

1. validate public state and input before mutation;
2. apply acceleration and semi-implicit Euler integration;
3. integrate the wrapping orientation phase and clamp linear/angular speed;
4. compute each box's orientation basis once for the contact pass and reuse each
   static segment's precomputed normal;
5. populate the uniform grid and deduplicate candidate pairs into fixed bitsets;
6. enumerate those candidates in stable body/segment index order;
7. generate circle-circle, circle-box, box-box, circle-segment, and box-segment
   contacts;
8. apply bounded positional correction;
9. run at most seven sequential-impulse velocity iterations; and
10. publish counters and the newest immutable state.

Production uses a 16 x 16 screen-space grid of 16-pixel cells covering the
half-open range from 0 through 256 on each axis. Each cell stores one 16-bit body
mask and one eight-bit static-segment mask. Inclusive fixed-point AABBs occupy
every touched cell; deduplicated pair masks are then consumed in the same order
as the reference brute-force loops, preserving contact and solver order. Any
geometry outside the grid causes an explicit whole-step brute-force fallback.
The reference step remains callable by native tests, which compare every body,
contact, and authoritative hash over mixed 12-body replays.

## Profiling contract

Every physics step publishes deterministic work counters for possible and
retained pairs, cell insertions and occupancy, split narrow-phase tests,
manifolds and contact points, positional-correction visits, solver iterations
and visits, changed-contact impulses, and unexpected broad-phase fallbacks.
These counters are fixed-size scratch diagnostics and do not participate in the
authoritative hash.

The platform-neutral step API optionally accepts a caller-provided wrapping
32-bit cycle clock. No Zephyr header or clock is referenced by the physics or
game-world modules. A profiled call divides elapsed cycles into force/integration,
box geometry, grid/reference broad phase, body/body narrow phase, body/segment
narrow phase, positional correction, velocity solving, and final clamping.
`other` is the difference between the complete public step and those regions;
it includes state validation plus timing-boundary overhead. `total` covers the
complete valid physics step. The canonical eight-body scene performs 46 clock
reads per measured step; the report includes a back-to-back clock-read delta so
instrumentation cost remains visible rather than silently folded into a result.

`picosystem profile compare [ticks]` operates only while the live simulation is
paused. It resets a separate canonical world, runs 120 unmeasured warm-up ticks,
then replays the same bounded input pattern for the grid and brute-force paths.
Each individual measured call runs with Zephyr thread preemption locked, while
interrupts remain enabled; the benchmark yields every 32 ticks outside the
timed region so USB and board servicing remain responsive. Rendering and
snapshot publication are absent by design. The two final worlds are checked by
both authoritative hash and field-by-field persistent state comparison.

Stage samples accumulate into 64 fine 32-microsecond bins followed by 64 coarse
128-microsecond bins, covering tails through 10.24 milliseconds without
increasing the fixed RAM footprint. The device reports count, mean, minimum,
histogram-derived p50/p95/p99, exact maximum, and 1/120-second budget violations
without per-tick logging. `make profile-ab` preserves the live run/pause mode,
emits a concise comparison, and writes the complete version-1 JSON artifact.
These isolated timings must not be compared directly with the live update value
from `game stats`, which also contains game-demo and immutable-snapshot work and
may be affected by renderer and scheduler activity. The first physical PIM559
baseline is recorded in
[`benchmarks/physics-profile`](../benchmarks/physics-profile/README.md).

Contacts carry a stable point, normal, penetration depth, restitution target,
and accumulated normal/tangent impulses. Box SAT selects from four face axes;
reference/incident edge clipping emits at most two stable manifold points.
Relative contact velocity includes `omega cross radius`, and effective mass plus
impulse application include inverse inertia. The solver applies friction and
restitution without allocating per-pair vectors. Exactly coincident centers use
an explicit identifier-based normal instead of random jitter.

## Current milestone: uniform-grid rigid-body lab

The flashable rigid-body lab contains:

- four dynamic circles and four differently sized, initially spinning boxes;
- four arena boundaries and two diagonal static ramps;
- gravity plus D-pad-directed global acceleration;
- all circle/box pairings plus finite, two-sided circle/box segment collision;
- shape-derived inverse inertia, contact-point angular response, and two-point
  box manifolds;
- restitution, friction, positional correction, and a seven-pass-ceiling impulse
  solver with exact no-change termination;
- deterministic 16 x 16 grid filtering with brute-force fallback and oracle;
- old/new dirty footprints for every moved body, merged when they overlap; and
- body, filtered/possible-pair, grid occupancy, fallback, contact, solver,
  timing, and deterministic-hash diagnostics.

The milestone compile-time capacities are 12 dynamic bodies, eight static
segments, two contact points per candidate manifold, and 324 contact slots:
enough for every possible body-body and body-segment combination at those
limits. The native oracle fills all 12 body slots while the flashable lab uses
eight to preserve its 120 Hz device budget. The capacities are deliberately
higher than the canonical demo population, so contact exhaustion cannot
partially update a valid world. These are milestone
limits, not the eventual product scale.

The D-pad tilts the acceleration field while preserving neutral downward
gravity. A still performs the asynchronous full-redraw comparison and B keeps
the bounded piezo test. Remote directional input has the same physics meaning
as the physical D-pad.

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
- stable coincident-center handling;
- cell-boundary collisions and distant-pair rejection;
- explicit out-of-grid brute-force fallback;
- exact grid/reference equality for bodies and contacts over 1,000 mixed ticks;
- arena containment over long replay;
- deterministic reset and 10,000-tick replay;
- authoritative hash changes and reset recovery; and
- undefined-behavior sanitizer execution.

The native canonical reset is `b20aaf3a`, right-30 is `cb18185d`, the mixed-shape
right-30/up-15 sequence reaches tick 45 at `7272656f`, and a 10,000-tick replay
is `a64cb9ef`. The bounded replay reduces 76 possible pairs to between one and
29 grid candidates, reaches 22 contacts, never falls back, and preserves the
three-pixel arena tolerance. The PIM559 reproduced the tick-45 hash and a
coherently presented framebuffer CRC-32 of `11bbf436`. A reset 3,692-tick
physical window ran at 119.9 Hz with zero skipped ticks and one isolated
over-budget update; the sampled update was 5.724 ms and the observed maximum was
19.848 ms.

Scenario shapes and measurement discipline are informed by the earlier
[allan.pizza physics work](https://github.com/aortez/aortez.github.io/pull/14):
keep a brute-force oracle, use seeded sparse/clustered/mixed-radius/boundary/
coincident/moving fixtures, distinguish candidate count from true contacts,
and time pipeline stages separately. The browser engine's dynamic object graph,
floating-point response, random runtime fragmentation, and variable frame delta
are design references rather than code to port.

## Planned extensions

1. Add hinges, motors, sliders, springs, conveyors, sensors, and sleeping.
2. Add capsules and a position-based rope/soft-body subsystem with deliberate
   rigid-body coupling.
3. Evaluate bounded granular materials and approximate gravity or magnetic
   fields as separate gameplay systems.

Each extension must leave behind a playable device demo, a deterministic host
replay, an exact device sequence, and updated RAM/tick-time evidence.
