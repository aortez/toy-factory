# Physics engine design

Toy Factory's physics engine is a deterministic, bounded 2D simulation for the
RP2040. Every milestone must run through the same platform-neutral C code on the
host and device, remain remotely stepable at exact tick boundaries, and produce
stable authoritative hashes.

This document describes the intended architecture and the current oriented
rigid-body milestone. Later milestones may revise measured capacities, but they
must retain the ownership, determinism, and overload contracts defined here.

## Hardware and scheduling budget

The oriented rigid-body build uses 164,972 bytes of the linker's 263 KiB RAM
region. Its 115,200-byte framebuffer and 3,840-byte display transfer buffer
dominate that footprint. The fixed-capacity physics world occupies 13,936 bytes,
and the linked image retains roughly 98 KiB of headroom. On the PIM559, a clean
4,136-tick run reported a 4.580 ms current update and 5.449 ms observed maximum
within the 8.333 ms tick budget, backlog one, and zero skipped or over-budget
ticks. The renderer presented at 57.8 fps while authoritative logic held
120.0 Hz.

The initial engine targets are:

- exact 120 Hz authoritative updates;
- no heap allocation or capacity growth after initialization;
- about 5 ms or less for a representative physics update on the PIM559;
- at most 32 KiB of physics state and scratch storage before larger features;
- stable replay for at least 10,000 ticks on the host and RP2040;
- immutable renderer snapshots that do not expose live world state; and
- explicit counters or errors for every bounded-capacity failure.

Physics quality never changes in response to elapsed wall time. Presentation
may coalesce snapshots, but simulation does not reduce solver iterations, skip
contacts, or silently select a cheaper model when the device is busy.

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
5. enumerate candidate pairs in stable order;
6. generate circle-circle, circle-box, box-box, circle-segment, and box-segment
   contacts;
7. apply bounded positional correction;
8. run a fixed number of sequential-impulse velocity iterations; and
9. publish counters and the newest immutable state.

The first milestone uses brute-force candidate enumeration. At its small body
count this is simpler than a spatial index and doubles as the correctness
oracle for the next broad-phase implementation. The planned optimized broad
phase is a uniform screen-space grid with deterministic pair deduplication.
Native tests must prove that its candidate set contains every brute-force
intersection before firmware selects it.

Contacts carry a stable point, normal, penetration depth, restitution target,
and accumulated normal/tangent impulses. Box SAT selects from four face axes;
reference/incident edge clipping emits at most two stable manifold points.
Relative contact velocity includes `omega cross radius`, and effective mass plus
impulse application include inverse inertia. The solver applies friction and
restitution without allocating per-pair vectors. Exactly coincident centers use
an explicit identifier-based normal instead of random jitter.

## Current milestone: oriented rigid-body lab

The flashable rigid-body lab contains:

- three dynamic circles and three differently sized, initially spinning boxes;
- four arena boundaries and two diagonal static ramps;
- gravity plus D-pad-directed global acceleration;
- all circle/box pairings plus finite, two-sided circle/box segment collision;
- shape-derived inverse inertia, contact-point angular response, and two-point
  box manifolds;
- restitution, friction, positional correction, and a fixed impulse solver;
- old/new dirty footprints for every moved body, merged when they overlap; and
- body, candidate, contact, solver, timing, and deterministic-hash diagnostics.

The milestone compile-time capacities are 12 dynamic bodies, eight static
segments, two contact points per candidate manifold, and 324 contact slots:
enough for every possible body-body and body-segment combination at those
limits. They are deliberately higher than the canonical demo population, so
contact exhaustion cannot partially update a valid world. These are milestone
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
- arena containment over long replay;
- deterministic reset and 10,000-tick replay;
- authoritative hash changes and reset recovery; and
- undefined-behavior sanitizer execution.

The device sequence runner confirms the native state golden and coherent
framebuffer CRC on the PIM559. The accepted mixed-shape right-30/up-15 sequence
reaches tick 45 with state hash `908d238c` and framebuffer CRC-32 `31f48288`.
Canonical reset is `5d80846f`, right-30 is `b0f8e409`, and a 10,000-tick native
replay is `70437154`. The clean timing interval described above completes this
milestone's no-skipped/no-over-budget performance acceptance.

Scenario shapes and measurement discipline are informed by the earlier
[allan.pizza physics work](https://github.com/aortez/aortez.github.io/pull/14):
keep a brute-force oracle, use seeded sparse/clustered/mixed-radius/boundary/
coincident/moving fixtures, distinguish candidate count from true contacts,
and time pipeline stages separately. The browser engine's dynamic object graph,
floating-point response, random runtime fragmentation, and variable frame delta
are design references rather than code to port.

## Planned extensions

1. Replace production brute force with a proven uniform-grid broad phase while
   retaining the reference implementation in native tests.
2. Add hinges, motors, sliders, springs, conveyors, sensors, and sleeping.
3. Add capsules and a position-based rope/soft-body subsystem with deliberate
   rigid-body coupling.
4. Evaluate bounded granular materials and approximate gravity or magnetic
   fields as separate gameplay systems.

Each extension must leave behind a playable device demo, a deterministic host
replay, an exact device sequence, and updated RAM/tick-time evidence.
