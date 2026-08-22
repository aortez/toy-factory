# PIM559 physics profiling baselines

These profiles were captured on a production Pimoroni PicoSystem PIM559 with
its RP2040 running at 125 MHz. Each mode receives 120 unmeasured warm-up ticks
followed by the same bounded input replay; the recorded artifact states its
measured tick count. Timing covers isolated physics steps with rendering and
snapshot publication disabled.

## Reciprocal rope and particle collision

The current schema-version-12 reports are
[pim559-rope-interaction-2026-08-22.json](pim559-rope-interaction-2026-08-22.json)
and
[pim559-rope-interaction-neutral-2026-08-22.json](pim559-rope-interaction-neutral-2026-08-22.json).
They were captured from the recommended dual-core image with:

```sh
make profile-ab PROFILE_TICKS=2000 \
  PROFILE_OUT=benchmarks/physics-profile/pim559-rope-interaction-2026-08-22.json
make profile-sleep PROFILE_TICKS=2000 \
  SLEEP_PROFILE_OUT=benchmarks/physics-profile/pim559-rope-interaction-neutral-2026-08-22.json
```

The canonical rope now reacts against its capsule endpoint and gives every
unpinned particle a one-pixel collision radius. Six alternating length passes
contain three interleaved external-collision passes:

| Mode | Mean | p50 | p95 | p99 | Maximum | Candidates/tick | Budget violations |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Uniform grid | 4,920 us | 4,864 us | 5,760 us | 6,144 us | 6,935 us | 7.133 | 0 |
| Brute-force reference | 5,313 us | 5,248 us | 6,144 us | 6,528 us | 7,470 us | 70.0 | 0 |

Both modes ended at `1600fb06` with exact authoritative-state agreement. The
grid rejected 89.8% of rigid candidate pairs and was 1.08 times faster overall.
The rope stage averaged 1,661/1,643 us, visited exactly 42 length constraints,
and held maximum segment error to 0.856 pixel. Each tick considered 234 bounded
rope/collider pairs; 5.521 passed the swept conservative bounds and 3.457
produced contacts on average. Reciprocal correction visited the capsule
endpoint six times and changed it 5.078 times per tick; the radial velocity row
visited and changed once per tick.

The neutral fixture preserves the reciprocal endpoint and collision workload
while letting ordinary rigid islands settle:

| Mode | Mean | p50 | p95 | p99 | Maximum | Sleeping body-ticks | Budget violations |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Uniform grid | 5,590 us | 5,632 us | 6,528 us | 6,912 us | 7,056 us | 1,039 | 0 |
| Brute-force reference | 5,887 us | 5,888 us | 6,784 us | 7,168 us | 7,511 us | 1,039 | 0 |

Both neutral modes ended at `34a04b59` with exact state agreement, recorded one
body sleep transition, and skipped 1,038 sleeping contacts. Maximum rope error
was 0.034 pixel. Shell stack high-water was 4,200 of 5,120 bytes in both
reports.

The image also routes compiler integer division through the RP2040's
interrupt-safe hardware divider and publishes real-time snapshots at the
panel's 30 Hz full-frame rate. A 5,921-tick concurrent window held 120.0 Hz with
one skipped tick while presentation averaged 29.6 fps. Mean complete update,
physics, and snapshot times were 6.880, 6.638, and 0.242 ms; the worst backlog
was five ticks. Main, render, and core-1 stack high-water marks were
4,016/5,120, 4,044/5,120, and 360/4,096 bytes.

## Capsules and one-way position-based rope

The preceding schema-version-10 reports are
[pim559-capsules-rope-2026-08-21.json](pim559-capsules-rope-2026-08-21.json)
and
[pim559-capsules-rope-neutral-2026-08-21.json](pim559-capsules-rope-neutral-2026-08-21.json).
They were captured from the recommended dual-core image with:

```sh
make profile-ab PROFILE_TICKS=2000 \
  PROFILE_OUT=benchmarks/physics-profile/pim559-capsules-rope-2026-08-21.json
make profile-sleep PROFILE_TICKS=2000 \
  SLEEP_PROFILE_OUT=benchmarks/physics-profile/pim559-capsules-rope-neutral-2026-08-21.json
```

The canonical fixture replaces one circle with an exact rotating capsule and
adds one eight-particle rope pinned between that body and the world:

| Mode | Mean | p50 | p95 | p99 | Maximum | Candidates/tick | Budget violations |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Uniform grid | 4,502 us | 4,480 us | 5,376 us | 5,504 us | 6,749 us | 6.951 | 0 |
| Brute-force reference | 5,100 us | 4,992 us | 5,888 us | 6,144 us | 7,458 us | 70.0 | 0 |

Both modes ended at `91744aeb` with exact authoritative-state agreement. The
rope always used six alternating passes and visited all 42 adjacent-particle
constraints per tick; 40.236 visits changed particle state on average. Its
isolated stage averaged 1,157 us on the grid run and 1,154 us on the reference
run. Six passes held maximum segment-length error to 0.534 pixel. The complete
production step retained 3.83 ms of mean and 1.58 ms of worst-case headroom
against the 8.333 ms simulation deadline.

The neutral fixture combines rope motion, settling rigid bodies, and the
powered conveyor:

| Mode | Mean | p50 | p95 | p99 | Maximum | Sleeping body-ticks | Budget violations |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Uniform grid | 5,346 us | 5,376 us | 6,912 us | 7,680 us | 7,936 us | 398 | 0 |
| Brute-force reference | 5,949 us | 5,888 us | 7,808 us | 8,320 us | 8,628 us | 398 | 18 |

Each mode recorded one body sleep transition, 710 conveyor contact-ticks, six
rope passes and 42 rope-constraint visits per tick, and exact final agreement
at `7d4ae8ca`. Maximum segment-length error was 0.038 pixel. The production grid
path stayed inside its deadline; the brute-force diagnostic oracle exceeded it
on 18 of 2,000 samples. Shell stack high-water was 4,160 of 5,120
bytes for both reports.

## Springs and conveyors

The preceding schema-version-9 reports are
[pim559-springs-conveyors-2026-08-21.json](pim559-springs-conveyors-2026-08-21.json)
and
[pim559-springs-conveyors-neutral-2026-08-21.json](pim559-springs-conveyors-neutral-2026-08-21.json).
They were captured from the recommended dual-core image with:

```sh
make profile-ab PROFILE_TICKS=1000 \
  PROFILE_OUT=benchmarks/physics-profile/pim559-springs-conveyors-2026-08-21.json
make profile-sleep PROFILE_TICKS=2000 \
  SLEEP_PROFILE_OUT=benchmarks/physics-profile/pim559-springs-conveyors-neutral-2026-08-21.json
```

The moving canonical fixture contains one impulse-limited damped spring and one
signed-speed diagonal conveyor:

| Mode | Mean | p50 | p95 | p99 | Maximum | Candidates/tick | Budget violations |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Uniform grid | 2,718 us | 2,688 us | 3,584 us | 3,840 us | 4,660 us | 7.043 | 0 |
| Brute-force reference | 3,060 us | 3,072 us | 3,840 us | 4,096 us | 4,872 us | 70.0 | 0 |

Both modes ended at `728d8683` with exact authoritative-state agreement. The
grid was 1.13 times faster. Each tick visited the spring seven times and 1.111
visits changed its impulse on average. The fixture recorded ten conveyor
contact-ticks, 70 conveyor solver visits, and 34 changed conveyor impulses in
each mode. Maximum revolute-anchor, angular-limit, prismatic-lateral,
prismatic-angular, and travel-limit errors were 0.802 pixels, 0.0175 radian,
0.0547 pixels, 0.0140 radian, and 0.0730 pixels.

The neutral fixture exercises powered conveyor contacts and ordinary island
sleeping together:

| Mode | Mean | p50 | p95 | p99 | Maximum | Sleeping body-ticks | Conveyor contacts | Budget violations |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Uniform grid | 3,630 us | 3,584 us | 5,376 us | 5,888 us | 6,175 us | 398 | 710 | 0 |
| Brute-force reference | 3,989 us | 3,968 us | 5,760 us | 6,400 us | 6,511 us | 398 | 710 | 0 |

Each mode recorded one body sleep transition, skipped 794 sleeping contacts,
and ended at `3d88bb5f` with exact state agreement. Powered belt contact did not
put an active body to sleep, while the spring remained part of the ordinary
sleep graph. Shell stack high-water was 3,896 of 5,120 bytes for both runs.

## Deterministic sleeping and wake propagation

The preceding schema-version-8 reports are
[pim559-sleeping-2026-08-19.json](pim559-sleeping-2026-08-19.json) and
[pim559-sleeping-neutral-2026-08-19.json](pim559-sleeping-neutral-2026-08-19.json).
They were captured from the recommended dual-core image with:

```sh
make profile-ab PROFILE_TICKS=1000 \
  PROFILE_OUT=benchmarks/physics-profile/pim559-sleeping-2026-08-19.json
make profile-sleep PROFILE_TICKS=2000 \
  SLEEP_PROFILE_OUT=benchmarks/physics-profile/pim559-sleeping-neutral-2026-08-19.json
```

The moving canonical fixture continuously changes directional input, keeping
all seven bodies awake while providing a direct comparison with the preceding
contact-event profile:

| Mode | Mean | p50 | p95 | p99 | Maximum | Candidates/tick | Budget violations |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Uniform grid | 2,792 us | 2,688 us | 3,712 us | 4,352 us | 4,832 us | 8.017 | 0 |
| Brute-force reference | 3,117 us | 2,944 us | 4,096 us | 4,608 us | 5,295 us | 70.0 | 0 |

Both modes ended at `46020daa` with exact authoritative-state agreement. The
grid was 1.12 times faster overall. Maximum revolute-anchor, angular-limit,
prismatic-lateral, prismatic-angular, and travel-limit errors were 0.814 pixels,
0.0418 radian, 0.0885 pixels, 0.00461 radian, and 0.0651 pixels.

The neutral fixture isolates settling and skipped sleep work:

| Mode | Mean | p50 | p95 | p99 | Maximum | Sleeping body-ticks | Sleeping contacts | Budget violations |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Uniform grid | 3,456 us | 3,456 us | 4,480 us | 4,864 us | 5,392 us | 664 | 663 | 0 |
| Brute-force reference | 3,787 us | 3,712 us | 4,736 us | 5,248 us | 5,695 us | 664 | 663 | 0 |

Each mode recorded one body sleep and one body wake transition and ended at
`ea65ce22` with exact state agreement. Motorized joint islands remained awake,
so this fixture skips a resting contact rather than joint rows. Its settled
contact population differs from the moving fixture, so the two means are not a
before/after speedup comparison. Shell stack high-water was 3,856 of 5,120
bytes.

## Box sensor and contact lifecycle events

The preceding schema-version-7 canonical result is in
[pim559-contact-events-2026-08-19.json](pim559-contact-events-2026-08-19.json).
It was captured from the recommended dual-core image with:

```sh
make profile-ab PROFILE_TICKS=1000 \
  PROFILE_OUT=benchmarks/physics-profile/pim559-contact-events-2026-08-19.json
```

The seven-body Machine Lab adds one fixed box sensor and pair-level `BEGIN`,
`STAY`, and `END` events for physical contacts and sensor overlaps. The fast
image places its 16,480-byte inlined physics step in SRAM so core 0 does not
compete with core-1 rasterization for XIP flash.

| Mode | Mean | p50 | p95 | p99 | Maximum | Candidates/tick | Sensor tests/tick | Budget violations |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Uniform grid | 2,723 us | 2,560 us | 3,584 us | 4,224 us | 4,722 us | 8.017 | 0.685 | 0 |
| Brute-force reference | 2,998 us | 2,944 us | 3,968 us | 4,352 us | 5,017 us | 70.0 | 7.0 | 0 |

Both modes ended at hash `1d58dedd` with exact authoritative-state agreement.
The grid rejected 88.5% of possible pairs and was 1.10 times faster overall.
Each mode observed 224 sensor overlaps and emitted 182 begin, 523 stay, and 182
end events over the measured replay. Maximum revolute-anchor, angular-limit,
prismatic-lateral, prismatic-angular, and travel-limit errors were 0.814 pixels,
0.0418 radian, 0.0885 pixels, 0.00461 radian, and 0.0651 pixels. Shell stack
high-water was 3,856 of 5,120 bytes.

In a clean concurrent 4,978-tick device window, simulation held 120.0 Hz with
zero skipped ticks while full-frame presentation remained at 29.8 fps. Mean
complete-update, physics, and snapshot-publication times were 5.046, 4.356, and
0.689 ms. Four updates exceeded 8.333 ms; the maximum was 20.427 ms and the
worst scheduler backlog was three ticks.

## Motorized prismatic joint and contact cache

The preceding schema-version-6 canonical result is in
[pim559-prismatic-joint-2026-08-19.json](pim559-prismatic-joint-2026-08-19.json).
It was captured with:

```sh
make profile-ab PROFILE_TICKS=1000 \
  PROFILE_OUT=benchmarks/physics-profile/pim559-prismatic-joint-2026-08-19.json
```

The seven-body Machine Lab combines a powered three-link revolute chain with a
world-anchored vertical press. The press motor reverses at its creation-relative
-48/0-pixel stops. Contact and prismatic solver rows retain compact per-body
velocity revision stamps, so later global passes skip a row until one of its
bodies changes velocity.

| Mode | Mean | p50 | p95 | p99 | Maximum | Candidates/tick | Cached contacts/tick | Budget violations |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Uniform grid | 3,535 us | 3,328 us | 4,992 us | 5,504 us | 6,379 us | 7.332 | 1.265 | 0 |
| Brute-force reference | 3,662 us | 3,456 us | 4,992 us | 5,632 us | 6,227 us | 63.0 | 1.265 | 0 |

Both modes ended at hash `4ed9cc6f` with exact authoritative-state agreement.
The grid rejected 88.4% of possible pairs and was 1.04 times faster overall.
The cache skipped 1,265 of 4,767 scheduled contact visits while 2,646 visits
changed an impulse. Maximum revolute-anchor separation was 0.814 pixels;
maximum revolute-limit, prismatic-angular, and prismatic-limit violations were
0.0418 radian, 0.00461 radian, and 0.0651 pixels. Maximum prismatic lateral
error was 0.0885 pixels. Quality sampling ran after each timed step. Shell stack
high-water was 3,848 of 5,120 bytes.

In a concurrent 3,798-tick device window, simulation held 119.2 Hz while the
full-frame renderer presented at 29.8 fps. Mean physics time was 5.788 ms, eight
ticks were skipped, and the worst backlog was five ticks. A settled sampled
tick skipped 16 of 42 scheduled contact visits.

## Revolute motors and angular limits

The preceding schema-version-5 canonical result is in
[pim559-joint-motors-2026-08-18.json](pim559-joint-motors-2026-08-18.json). It
was captured with:

```sh
make profile-ab PROFILE_TICKS=1000 \
  PROFILE_OUT=benchmarks/physics-profile/pim559-joint-motors-2026-08-18.json
```

The four-link mechanism drives its world pin at 1/96 radian per tick with a
bounded 1/8 angular impulse per tick. Its final body-to-body hinge is limited
to -1 through +1 radian relative to the creation pose; the two middle hinges
remain free.

| Mode | Mean | p50 | p95 | p99 | Maximum | Candidates/tick | Anchor error | Limit violation | Budget violations |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Uniform grid | 4,136 us | 4,224 us | 5,760 us | 6,400 us | 7,001 us | 9.956 | 0.947 px | 0.0175 rad | 0 |
| Brute-force reference | 4,418 us | 4,480 us | 5,888 us | 6,656 us | 7,137 us | 76.0 | 0.947 px | 0.0175 rad | 0 |

Both modes ended at hash `a554f3c3` with exact authoritative-state agreement.
Each tick visited one motor through all seven velocity passes. The angular
limit was active for 0.889 velocity visits and 1.001 position visits per tick
on average. Quality sampling ran after the timed step. The grid rejected 86.9%
of possible pairs and was 1.07 times faster on average. Shell stack high-water
was 3,680 of 4,096 bytes.

## Adaptive revolute-joint convergence

The preceding schema-version-4 results are in
[pim559-joint-convergence-2026-08-18.json](pim559-joint-convergence-2026-08-18.json)
and
[pim559-chain-convergence-2026-08-18.json](pim559-chain-convergence-2026-08-18.json).
They were captured with:

```sh
make profile-ab PROFILE_TICKS=1000 \
  PROFILE_OUT=benchmarks/physics-profile/pim559-joint-convergence-2026-08-18.json
make profile-chain CHAIN_LINKS=4,6,8 CHAIN_PROFILE_TICKS=1000 \
  CHAIN_PROFILE_OUT=benchmarks/physics-profile/pim559-chain-convergence-2026-08-18.json
```

The solver always performs one revolute position pass. It continues, alternating
forward and reverse storage order, only while an anchor remains more than one
pixel apart, with a hard ceiling of four passes. The deterministic visit count
therefore records the actual adaptive work.

| Links | Single-pass mean | Adaptive mean | Adaptive maximum | Position visits/tick | Single-pass error | Adaptive error | Budget violations |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 4 | 1,559 us | 1,569 us | 2,082 us | 4.000 | 0.495 px | 0.495 px | 0 |
| 6 | 2,202 us | 2,315 us | 4,094 us | 7.032 | 1.314 px | 1.118 px | 0 |
| 8 | 2,819 us | 3,897 us | 5,188 us | 20.416 | 51.867 px | 1.158 px | 0 |

Four links remain on one pass, so their mean cost increases by only 10 us.
Six links average 1.172 passes and improve modestly. Eight links average 2.552
passes: mean cost rises by 1.078 ms, but maximum anchor separation falls by
97.8%. The 8-link maximum still uses only 62.3% of the 8.333 ms budget. Every
grid/reference pair ends with an identical hash and persistent state.

The canonical eight-body, six-segment scene averaged 3,539 us on the grid and
3,793 us on the reference, compared with 3,578/3,866 us before the change. Its
grid p95 was 5,376 us, maximum was 7,354 us, mean joint-position work was 5.012
visits per tick, and maximum anchor error was 0.930 pixels. It had no timing
violations and exact grid/reference agreement. Shell stack high-water was 3,504
of 4,096 bytes.

## Single-pass revolute-chain scaling baseline

The baseline chain aggregate contains schema-version-4 device results and is in
[pim559-chain-scaling-2026-08-18.json](pim559-chain-scaling-2026-08-18.json).
It was captured in one USB session with:

```sh
make profile-chain CHAIN_LINKS=4,6,8 CHAIN_PROFILE_TICKS=1000 \
  CHAIN_PROFILE_OUT=benchmarks/physics-profile/pim559-chain-scaling-2026-08-18.json
```

| Links | Grid mean | Grid p95 | Grid maximum | Reference mean | Velocity visits/tick | Maximum anchor error | Budget violations |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 4 | 1,559 us | 1,856 us | 2,022 us | 1,298 us | 28 | 0.495 px | 0 |
| 6 | 2,202 us | 2,560 us | 2,672 us | 1,912 us | 42 | 1.314 px | 0 |
| 8 | 2,819 us | 3,200 us | 3,252 us | 2,601 us | 56 | 51.867 px | 0 |

The controlled fixture uses centered short boxes, neutral downward gravity, no
static segments, and collision filtering between adjacent links. Every grid
and reference run ended with the same authoritative hash and exact persistent
state. Anchor error is sampled after each profiled step, outside its timed
region.

There was no CPU timing knee through the engine's current eight-joint capacity:
even the maximum 8-link step used only 39% of the 8.333 ms budget. The measured
solver-quality knee is between six and eight links. Seven velocity passes plus
one position pass kept six links within 1.314 pixels, but the eight-link chain
stretched by 51.867 pixels. All 56 revolute-solver visits changed an impulse on
every 8-link tick, so the solver had not converged. The adaptive result above
spends that available CPU headroom only when the measured anchor error requires
it.

The brute-force reference is faster in this deliberately sparse fixture. With
only 6, 15, or 28 possible body pairs and no segments, uniform-grid population
costs more than it saves. The grid remains valuable in the denser canonical
scene below.

## Multi-link revolute-joint lab

The preceding schema-version-3 result is in
[pim559-revolute-joint-2026-08-18.json](pim559-revolute-joint-2026-08-18.json).
It was captured with:

```sh
make profile-ab PROFILE_TICKS=1000 \
  PROFILE_OUT=benchmarks/physics-profile/pim559-revolute-joint-2026-08-18.json
```

| Mode | Mean | p50 | p95 | p99 | Maximum | Candidate pairs/tick | Budget violations |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Uniform grid | 3,578 us | 3,456 us | 5,504 us | 6,784 us | 7,539 us | 10.544 | 0 |
| Brute-force reference | 3,866 us | 3,712 us | 5,632 us | 6,784 us | 7,693 us | 76.0 | 0 |

The grid rejected about 86.1% of possible pairs and made the complete step 1.08
times faster on average. Both modes processed one distance joint and four
revolute joints per tick, filtered the three directly connected body pairs, ran
35 joint-solver visits, ended at authoritative hash `5d658f9f`, and matched
field by field. The report estimated 65.136 us of clock-read overhead per
profiled step. Shell stack high-water was 3,360 of 4,096 bytes.

## Distance-joint lab

The current schema-version-2 result is in
[pim559-distance-joint-2026-08-17.json](pim559-distance-joint-2026-08-17.json).
It was captured with:

```sh
make profile-ab PROFILE_TICKS=2000 \
  PROFILE_OUT=benchmarks/physics-profile/pim559-distance-joint-2026-08-17.json
```

| Mode | Mean | p50 | p95 | p99 | Maximum | Candidate pairs/tick | Budget violations |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Uniform grid | 2,173 us | 1,824 us | 4,480 us | 5,888 us | 6,816 us | 9.913 | 0 |
| Brute-force reference | 2,382 us | 2,016 us | 4,608 us | 5,888 us | 6,987 us | 76.0 | 0 |

The grid rejected about 87.0% of possible pairs and made the complete step 1.10
times faster on average. Both modes processed one distance joint per tick, ran
seven joint-solver visits, ended at authoritative hash `5a85725f`, and matched
field by field. The report estimated 60.720 us of clock-read overhead per
profiled step. Shell stack high-water was 2,896 of 4,096 bytes.

## Uniform-grid lab before joints

The earlier schema-version-1 result remains in
[pim559-2026-08-17.json](pim559-2026-08-17.json) so changes can be compared
against the pre-joint solver:

| Mode | Mean | p50 | p95 | p99 | Maximum | Candidate pairs/tick | Budget violations |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Uniform grid | 2,318 us | 2,176 us | 4,352 us | 5,120 us | 5,795 us | 12.400 | 0 |
| Brute-force reference | 2,742 us | 2,560 us | 4,736 us | 5,376 us | 5,776 us | 76.0 | 0 |

That scene's grid rejected about 83.7% of possible pairs and produced a 1.18x
mean speedup. Both modes ended at authoritative hash `029cce2f`. Its estimated
clock-read overhead was 53.728 us per profiled step, and shell stack high-water
was 2,823 of 4,096 bytes.
