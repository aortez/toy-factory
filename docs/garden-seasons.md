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
default-build horizon now permits 256 days. The evaluator also accepts an
explicit `--climate` with `--rainfed`, with a 256-day maximum; its default and
the trainer remain **steady**. Matched experiment bundles, diagnostic replays,
seed-site audits and saved-model galleries propagate that setting and check
climate metadata as well as state hashes. No fitness or model weights change.
The archived research build retains its separate 192-day inspector limit.

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

The [physical PIM559 check](../benchmarks/garden-seasons/README.md#physical-pim559-check)
flashed the fast-display image and reproduced smoke/mature, winter and first-spring
state/framebuffer checkpoints, including byte-identical winter/spring screenshots.
It also records an independent shell prompt-redraw parsing race encountered during
long USB replay. After host-reader hardening and regression tests, the ordinary
54,030-tick lifecycle replay passes without retries or a recovery harness.
This is device compatibility evidence, not ecological qualification.

## Reproduce the comparison

```sh
make host-seasons-garden GARDEN_SEASONS_OUT=artifacts/my-seasons \
  GARDEN_SEASONS_ARGS="--days 64 --trials 2 --jobs 2 --seed-audit --screenshots"
```

Output must be a new directory. This runs the same two fixed world seeds across
two layouts, baseline/adaptive policies, and four matched climates: 32 worlds,
64 days each. Gardener and irrigation are off; all arms use long-lived seeds.
`results.json` includes daily censuses, natural-death observations, final-year
births, living-plus-seed extinction checks, and source/binary hashes. The
optional screenshot panel uses the first predeclared seed, not outcome-ranked
worlds, with days 3, 5, 14 and 16 replayed through the production renderer and
verified against census hashes and framebuffer CRCs.

Protocol v2 additionally keeps immutable parent/founder histories, living and
viable-seed species/family counts, full-day offspring cohorts, and descendant
parents with a full-day-surviving child. Closing cohorts include births strictly
after the last year's start; births without a full day of possible follow-up
are censored. Seeds alone are not evidence of successful renewal. `--seed-audit`
replays every ecology step and summarizes the final year's post-step germination
blockers, checking every daily hash against the first pass. These are overlapping
blocker observations, not exact germination-decision receipts or causal rescues.
Use a predeclared `--seed-base` for a fresh panel. All policies/layouts receive
the same offered rain for a given seed and climate; the collector checks this.

Evaluate an existing saved model (omit `--candidate-model` for built-in references):

```sh
make host-experiment-garden GARDEN_EXPERIMENT_OUT=artifacts/seasonal-model \
  GARDEN_EXPERIMENT_ARGS="--climate seasonal --cycles 32 --trials 2 --trace-pairs 1 --candidate-model artifacts/model.tgm"
make host-gallery-garden GARDEN_GALLERY_BUNDLE=artifacts/seasonal-model \
  GARDEN_GALLERY_OUT=artifacts/seasonal-model-gallery \
  GARDEN_GALLERY_ARGS="--checkpoint 19200 --checkpoint 53760 --checkpoint 61440"
```

For the lightweight evaluator target, set `GARDEN_EVAL_RAINFED=1` and
`GARDEN_EVAL_CLIMATE=seasonal`; use `GARDEN_EVAL_TICKS=245760` for 64 days.
Keep each output distinct. Evaluation is opt-in, not an assertion that the
seasonal environment or old trained models are qualified for training/deployment.

## Bounded follow-up protocol

The initial 64-day diagnostic panel is repeated without behavior changes; a
fresh base `0x73656132`, four seeds, both layouts/policies and all climates then
runs for 128 days. The working default remains 256 nodes and eight seeds.
One isolated worktree tests drought duration **1–2 days** instead of 2–4,
leaving onset, winter, rain generator, resource rules and policies unchanged.
Steady/winter trajectories must remain identical; all arms must match through
day four. No other candidate is searched in this pass.

Before seeing that treatment, the screen is: no new extinction, more endpoints
with multiple viable species, and no reduction in the number of worlds with
closing-year births, closing full-day offspring survivors, or historical durable
descendant parents. If it passes the original panel, compare the same criteria
on the fresh 128-day panel, additionally retaining its closing durable parents.
A failed screen is retained as evidence, not promoted or followed by repeated
parameter searching. Larger dispersal, allocation or mortality redesigns require
discussion and are outside this PR.

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

The [bounded follow-up](../benchmarks/garden-seasons/README.md) now records ancestry,
uniform blocker sampling, terminal death receipts and a fresh 128-day panel.
Combined weather produces late successful descendant parents in some worlds,
but most endpoints remain single-species and many seeds remain spacing-blocked.
A shorter-drought test improves some diversity/late-cohort counts while reducing
historical durable parents; it fails the predeclared screen and is not promoted.
This pass is complete without changing weather severity or training objectives.
Default small-pool and experimental large-pool ecology remain distinct environments.

## Validation

`make check` passed standalone checks, all 100 default host tests and a pristine
Zephyr firmware build. `make host-research-check` passed all 105 tests in the
representative 512-node research configuration. Tests cover repeatable schedules,
mode isolation, year/seed variation, boundaries, rain accounting, cold seed
deferral, post-drought germination, expiry at the extended deadline, malformed
CLI options, native replay identity and partial-frame reconstruction of labels.
The follow-up also covers cohort censoring, failed tuning gates, complete matched
panels, and seasonal evaluator/saved-model gallery/seed-audit propagation.

The firmware links 257,596 bytes of flash and 223,004 bytes of main RAM: +924
flash bytes and +8 RAM bytes versus the preceding correctness build. The
separate 8 KiB Core 1 reservation is unchanged. These are linker measurements,
not a new hardware timing or stack-high-water qualification. No device was
flashed for this work. The deterministic 16-image host panel was hash/CRC
checked; the seasonal dry, cold and spring-recovery frames were visually reviewed.
