# PIM559 physics profiling baseline

This baseline was captured on a production Pimoroni PicoSystem PIM559 with its
RP2040 running at 125 MHz. The command was:

```sh
make profile-ab PROFILE_TICKS=2000 \
  PROFILE_OUT=artifacts/physics-profile-pim559-2026-08-17.json
```

Each mode received 120 unmeasured warm-up ticks followed by the same 2,000-tick
input replay. Timing covers isolated physics steps with rendering and snapshot
publication disabled. The complete schema-versioned result is in
[pim559-2026-08-17.json](pim559-2026-08-17.json).

| Mode | Mean | p50 | p95 | p99 | Maximum | Candidate pairs/tick | Budget violations |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Uniform grid | 2,318 us | 2,176 us | 4,352 us | 5,120 us | 5,795 us | 12.3995 | 0 |
| Brute-force reference | 2,742 us | 2,560 us | 4,736 us | 5,376 us | 5,776 us | 76.0 | 0 |

The grid rejected about 83.7% of possible pairs and made the complete step 1.18
times faster on average. Both modes ended at authoritative hash `029cce2f` and
matched field by field. The report estimated 53.728 us of clock-read overhead
per profiled step. Shell stack high-water was 2,823 of 4,096 bytes; the shell
remained responsive after the full benchmark.
