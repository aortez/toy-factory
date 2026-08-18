# PIM559 physics profiling baselines

These profiles were captured on a production Pimoroni PicoSystem PIM559 with
its RP2040 running at 125 MHz. Each mode receives 120 unmeasured warm-up ticks
followed by the same 2,000-tick input replay. Timing covers isolated physics
steps with rendering and snapshot publication disabled.

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
