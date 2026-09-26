# Garden winter, drought, and seed viability

Initial seasonal mechanics for [roadmap issue #30](https://github.com/aortez/toy-factory/issues/30).
This is a testable environment, not a qualified training curriculum or a claim
of long-term ecological balance. No lightning, flooding, harvesting, fire,
live-branch pruning, temperature field, or new learned controller is included.

## Rules: climate v1, Garden hash v6

One Garden day is 256 ecology steps / 3,840 logic ticks / 64 simulation seconds.
A year is 16 days (17 minutes 4 seconds at real time), starting in spring.
Each named season occupies four days; the names describe the schedule, not
a model of real-world meteorology.

- **Drought:** one uninterrupted summer rain outage per year. Starts on day
  4 or 5 and lasts 2–4 days, ending by day 8. Existing evaporation, root uptake,
  and maintenance continue. There is no extra soil deletion, bottom drainage,
  or direct plant damage. Ordinary showers resume afterward.
- **Winter:** direct sunlight ramps down from day 10 to day 14, then returns
  to full strength at the next spring. The year's minimum is 38–58% of the
  direct beam (unshaded noon strength 111–157 instead of 255). Daily phase,
  ray direction, and the 24-unit ambient floor are unchanged. This first version
  changes intensity, not day length, rain, upkeep, or adult growth rules.
- **Cold germination delay:** below 65% seasonal direct light, seeds gain
  the `COLD` blocker (bit 6). Moisture, local light, dormancy age, spacing and
  both pool capacities are still checked. Cold does not freeze seed aging.
- **Viability:** all seed banks now expire entries at 8,192 ecology steps,
  or 32 days / two years. Initial eight-step dormancy and eight-slot default
  capacity are unchanged. No new seed storage or heap allocation is needed.

Weather seed and year determine drought timing and winter severity using
separate counter-hash domains. Population size, available node slots, gardener
actions, and plant RNG consumption never choose or retarget a hazard. New
years vary, but all runs with the same configuration are reproducible.

Mortality is still the existing energy/water shortage and stress system.
Dead tissue follows ordinary decomposition before its space is reusable.
Winter and drought can cause different shortages, but effects may persist
beyond the event: a plant can run down reserves or die later. Neither event
guarantees a particular number of deaths or immediate free slots.

The small bank is a real constraint: longer-lived seeds retain slots, including
seeds whose landing sites remain shaded or occupied. That is now visible in
the diagnostics; we have not added seed replacement, larger banks, rescue
watering, or forced germination to compensate.

## Integration and controls

The playable Garden in host, browser and firmware uses `seasonal` (winter plus
drought). `COLD`/`DRY` replace the `RAIN` header label when appropriate; the
existing damage renderer invalidates that small region on transitions.
Device statistics and native output report effective conditions. Rendering,
policy observations, photosynthesis, reproduction and rain deposition use the
same effective sun/rain helpers. The 104-byte observation and neural model ABI
are unchanged; controllers see local resources and current sun strength,
not future weather or a new privileged season input.

Bare `garden_world_reset` stays dry and steady. The inspector and replayer
accept `--climate steady|winter|drought|seasonal`, defaulting to steady; their
default-build horizon now permits 256 days. The evaluator and trainer retain
their existing **steady** environments and explicitly report the new seed
lifetime. Seasonal optimization/training integration is a later decision;
we have not silently changed their objectives or historical evidence.

The setter changes climate only at ecology boundaries and refreshes light,
without resetting clocks, soil, plants, or RNGs. Its single-byte world field
uses padding: the default world remains 4,352 bytes and plant remains 100 bytes.
Schedules and current conditions are derived rather than stored per cell.

Hash v6 identifies seed lifetime and climate mode/version. Golden sequences
were regenerated, with lifecycle/generation runs extended into winter to retain
real death/reclamation/reproduction coverage. Old archived hashes and evidence
are not rewritten. Current host traces carry seed lifetime explicitly; readers
of historical records without it retain the old 256-step interpretation.
The persistence pilot's fixed two-day follow-up remains bounded: long-lived
pending seeds are **unconfirmed**, not extinct or established survivors.

## Reproduce the comparison

```sh
make host-seasons-garden GARDEN_SEASONS_OUT=artifacts/my-seasons \
  GARDEN_SEASONS_ARGS="--days 64 --trials 2 --jobs 2 --screenshots"
```

Output must be a new directory. This runs the same two fixed world seeds across
two layouts, baseline/adaptive policies, and four matched climates: 32 worlds,
64 days each. Gardener and irrigation are off; all arms use long-lived seeds.
`results.json` includes daily censuses, natural-death observations, final-year
births, living-plus-seed extinction checks, and source/binary hashes. The
optional screenshot panel uses the first predeclared seed, not outcome-ranked
worlds, with days 3, 5, 14 and 16 replayed through the production renderer and
verified against census hashes and framebuffer CRCs.

Single-world diagnostics:

```sh
make host-build
docker compose run --rm -T firmware \
  build-host/toy-factory-garden-inspect - rainfed adaptive 123 \
  --climate seasonal --ticks 122880
docker compose run --rm -T firmware \
  build-host/toy-factory-garden-replay - rainfed adaptive 123 \
  --climate seasonal --ticks 53760 --framebuffer artifacts/winter.rgb565be
```

The first drought begins after 4–5 real-time minutes; winter takes longer.
The headless tools can advance directly to these checkpoints without waiting
in real time. Manual watering and the auto-gardener remain possible during
play, but invalidate an unassisted survival comparison.

## Initial evidence and next questions

The initial 64-day panel produced:

| Climate | Worlds with living plants at end | Births | Final-year births | Natural deaths |
|---|---:|---:|---:|---:|
| Steady | 8/8 | 34 | 0 | 30 |
| Winter | 8/8 | 91 | 8 | 92 |
| Drought | 8/8 | 115 | 15 | 122 |
| Both | 8/8 | 111 | 8 | 117 |

No world in this panel reached an observed empty living-plus-seed state.
These are pooled counts from a small exploratory panel, not independent
statistical replicates or proof every world keeps renewing. Combined pressure
is not automatically more productive than either component alone.

In particular, combined pressure ended with **one living species in all eight
worlds**, versus 2–3 in the steady controls. Winter retained 1–3 and drought
1–2. Only 5/8 winter, 2/8 drought and 2/8 combined worlds had final-year births.
These are living-species counts, not proof a lineage/species has vanished from
the seed bank. Energy-only / water-only / combined-shortage deaths were
29/1/0 (steady), 88/4/0 (winter), 62/55/5 (drought), and 69/47/1 (both).
The pressures have distinct effects, but the combined environment is strongly
selective and needs further balance/diversity investigation.

Next: examine species/founder persistence and per-season resource/death traces
over more weather seeds and years, inspect recovery visually, and measure seed
bank occupancy/blockers. Do not increase severity merely to obtain deaths or
claim diversity from pooled birth counts. Default small-pool and experimental
large-pool ecology remain distinct environments.

## Validation

`make check` passed standalone checks, all 99 default host tests and a pristine
Zephyr firmware build. `make host-research-check` passed all 104 tests in the
representative 512-node research configuration. Tests cover repeatable schedules,
mode isolation, year/seed variation, boundaries, rain accounting, cold seed
deferral, post-drought germination, expiry at the extended deadline, malformed
CLI options, native replay identity and partial-frame reconstruction of labels.

The firmware links 257,596 bytes of flash and 223,004 bytes of main RAM: +924
flash bytes and +8 RAM bytes versus the preceding correctness build. The
separate 8 KiB Core 1 reservation is unchanged. These are linker measurements,
not a new hardware timing or stack-high-water qualification. No device was
flashed for this work. The deterministic 16-image host panel was hash/CRC
checked; the seasonal dry, cold and spring-recovery frames were visually reviewed.
