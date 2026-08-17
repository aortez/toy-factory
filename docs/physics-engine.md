# Physics engine design

Toy Factory's physics engine is a deterministic, bounded 2D simulation for the
RP2040. Every milestone must run through the same platform-neutral C code on the
host and device, remain remotely stepable at exact tick boundaries, and produce
stable authoritative hashes.

This document describes the intended architecture and the first collision-lab
milestone. Later milestones may revise measured capacities, but they must retain
the ownership, determinism, and overload contracts defined here.

## Hardware and scheduling budget

The first collision-lab build uses 152,716 bytes of the linker's 263 KiB RAM
region. Its 115,200-byte framebuffer and 3,840-byte display transfer buffer
dominate that footprint. The fixed-capacity physics world occupies 5,208 bytes,
and the linked image retains roughly 114 KiB of headroom. On the PIM559, routine
sampled collision-lab updates took 1.9-2.1 ms. A clean 20-second run observed a
6.269 ms maximum within the 8.333 ms tick budget, backlog one, and zero skipped
or over-budget ticks.

The initial engine targets are:

- exact 120 Hz authoritative updates;
- no heap allocation or capacity growth after initialization;
- at most 4 ms for a representative physics update on the PIM559;
- at most 32 KiB of physics state and scratch storage before larger features;
- stable replay for at least 10,000 ticks on the host and RP2040;
- immutable renderer snapshots that do not expose live world state; and
- explicit counters or errors for every bounded-capacity failure.

Physics quality never changes in response to elapsed wall time. Presentation
may coalesce snapshots, but simulation does not reduce solver iterations, skip
contacts, or silently select a cheaper model when the device is busy.

## Numeric model

The first engine uses signed Q16.16 fixed-point values:

- position: pixels;
- linear velocity: pixels per simulation tick;
- linear acceleration: pixels per simulation tick squared;
- unit vectors, material coefficients, and inverse mass: dimensionless; and
- time: exactly one 1/120-second tick per call.

Per-tick velocity avoids dividing every integration by 120 and makes each
authoritative update self-contained. Products and divisions use checked ranges
and 64-bit intermediates. Signed overflow, invalid shifts, and implementation-
defined structure hashing are forbidden. Integer square root and normalization
have explicit coincident-point behavior.

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
are each only 2 KiB. Contacts are scratch results from the current update and
are excluded from the authoritative hash; body state, static geometry, numeric
configuration, and game tick count are hashed field by field in stable order.

Bodies and shapes receive stable numeric identifiers. Array order is never
derived from addresses, hash tables, allocation order, or unstable sorting.
Remote pause, reset, input injection, exact stepping, framebuffer capture, and
state hashing continue to cross the acknowledged main-thread request queue.

## Collision pipeline

Each update performs these bounded phases in order:

1. validate public state and input before mutation;
2. apply acceleration and semi-implicit Euler integration;
3. clamp velocity to the configured vector-speed limit;
4. enumerate candidate pairs in stable order;
5. generate circle-circle and circle-segment contacts;
6. apply bounded positional correction;
7. run a fixed number of sequential-impulse velocity iterations; and
8. publish counters and the newest immutable state.

The first milestone uses brute-force candidate enumeration. At its small body
count this is simpler than a spatial index and doubles as the correctness
oracle for the next broad-phase implementation. The planned optimized broad
phase is a uniform screen-space grid with deterministic pair deduplication.
Native tests must prove that its candidate set contains every brute-force
intersection before firmware selects it.

Contacts carry a stable normal, penetration depth, restitution target, and
accumulated normal/tangent impulses. The solver applies friction and restitution
without allocating per-pair vectors. Exactly coincident centers use an explicit
identifier-based normal instead of random jitter.

## First milestone: collision lab

The flashable collision lab contains:

- six differently sized dynamic circles;
- four arena boundaries and two diagonal static ramps;
- gravity plus D-pad-directed global acceleration;
- circle-circle and two-sided circle-segment collision;
- restitution, friction, positional correction, and a fixed impulse solver;
- old/new dirty footprints for every moved circle, merged when they overlap; and
- body, candidate, contact, solver, timing, and deterministic-hash diagnostics.

The milestone compile-time capacities are 12 dynamic circles, eight static
segments, and enough contacts for every possible body-body and body-segment
combination at those limits. They are deliberately higher than the canonical
demo population, so contact exhaustion cannot partially update a valid world.
These are milestone limits, not the eventual product scale.

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
- stable coincident-center handling;
- arena containment over long replay;
- deterministic reset and 10,000-tick replay;
- authoritative hash changes and reset recovery; and
- undefined-behavior sanitizer execution.

The device sequence runner confirms the native state golden and coherent
framebuffer CRC on the PIM559. The first accepted right-30/up-15 sequence reaches
tick 45 with state hash `6a25b6d6` and framebuffer CRC-32 `c62eb3a0` on repeated
device runs. The clean timing interval described above completes the initial
no-skipped/no-over-budget performance acceptance.

Scenario shapes and measurement discipline are informed by the earlier
[allan.pizza physics work](https://github.com/aortez/aortez.github.io/pull/14):
keep a brute-force oracle, use seeded sparse/clustered/mixed-radius/boundary/
coincident/moving fixtures, distinguish candidate count from true contacts,
and time pipeline stages separately. The browser engine's dynamic object graph,
floating-point response, random runtime fragmentation, and variable frame delta
are design references rather than code to port.

## Planned extensions

1. Add angular state, oriented boxes, SAT narrow phase, and two-point contact
   manifolds.
2. Replace production brute force with a proven uniform-grid broad phase while
   retaining the reference implementation in native tests.
3. Add hinges, motors, sliders, springs, conveyors, sensors, and sleeping.
4. Add capsules and a position-based rope/soft-body subsystem with deliberate
   rigid-body coupling.
5. Evaluate bounded granular materials and approximate gravity or magnetic
   fields as separate gameplay systems.

Each extension must leave behind a playable device demo, a deterministic host
replay, an exact device sequence, and updated RAM/tick-time evidence.
