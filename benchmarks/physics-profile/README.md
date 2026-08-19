# PIM559 physics profiling baselines

These profiles were captured on a production Pimoroni PicoSystem PIM559 with
its RP2040 running at 125 MHz. Each mode receives 120 unmeasured warm-up ticks
followed by the same bounded input replay; the recorded artifact states its
measured tick count. Timing covers isolated physics steps with rendering and
snapshot publication disabled.

## Revolute-chain scaling

The current chain aggregate contains schema-version-4 device results and is in
[pim559-chain-scaling-2026-08-18.json](pim559-chain-scaling-2026-08-18.json).
It was captured in one USB session with:

```sh
make profile-chain CHAIN_LINKS=4,6,8 CHAIN_PROFILE_TICKS=1000 \
  CHAIN_PROFILE_OUT=benchmarks/physics-profile/pim559-chain-scaling-2026-08-18.json
```

| Links | Grid mean | Grid p95 | Grid maximum | Reference mean | Joint visits/tick | Maximum anchor error | Budget violations |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 4 | 1,559 us | 1,856 us | 2,022 us | 1,298 us | 28 | 0.495 px | 0 |
| 6 | 2,202 us | 2,560 us | 2,672 us | 1,912 us | 42 | 1.314 px | 0 |
| 8 | 2,819 us | 3,200 us | 3,252 us | 2,601 us | 56 | 51.867 px | 0 |

The controlled fixture uses centered short boxes, neutral downward gravity, no
static segments, and collision filtering between adjacent links. Every grid
and reference run ended with the same authoritative hash and exact persistent
state. Anchor error is sampled after each profiled step, outside its timed
region.

There is no CPU timing knee through the engine's current eight-joint capacity:
even the maximum 8-link step used only 39% of the 8.333 ms budget. The measured
solver-quality knee is between six and eight links. Seven velocity passes plus
one position pass kept six links within 1.314 pixels, but the eight-link chain
stretched by 51.867 pixels. All 56 revolute-solver visits changed an impulse on
every 8-link tick, so the solver had not converged. The next joint milestone
should spend some of the available CPU headroom on convergence quality before
raising capacity.

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
