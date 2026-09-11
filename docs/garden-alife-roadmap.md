# Garden A-life roadmap

[GitHub issue #30](https://github.com/aortez/toy-factory/issues/30) tracks milestone
status and experiment notes. This document records the agreed direction,
acceptance gates, and design constraints. Update the issue with evidence as
work lands; it is the authoritative completion checklist.

Status as of 2026-09-11: foundation tools and the saved-model screenshot/gallery
bridge exist, including uncommitted work on `green-garden`. Environment
qualification is underway. The [nighttime-growth comparison](../benchmarks/garden-longevity/night-growth.md)
improves early survival with a host-only decision probe, but does not establish
broad sustained renewal. Per-generation trainer capture, parallel training, and
the optional live viewer are not implemented.
The [seed-establishment audit](../benchmarks/garden-longevity/establishment.md)
now follows seed outcomes and maps reachable planting opportunities. The
[broader-dispersal comparison](../benchmarks/garden-longevity/dispersal.md) improves
establishment but not durable lineages consistently. It remains an explicit
host-only build variant; device/default scattering and water uptake are unchanged.
The [water-headroom experiment](../benchmarks/garden-longevity/water-headroom.md)
reduces water-shortage deaths and improves offspring survival fractions, but
late renewal falls as spacing and node capacity constrain establishment. Neither
experiment has been promoted to firmware or qualifies the environment by itself.
The [combined uptake/scattering test](../benchmarks/garden-longevity/combined-ecology.md)
completes the four-condition panel. Full-cycle offspring survivors rise to 227
across 48 worlds, but there are only two births in the final eight cycles;
durable-parent results remain policy-dependent. The node pool is completely
full for over 99% of that late window on average for adaptive and the veto
policy. Next proposed discussion: separate live tissue demand and reclamation
from spatial crowding before a capacity or turnover experiment. No new rule,
capacity increase, training run or qualification milestone follows automatically.

## Goal and order

Build a small autonomous ecology in which acquiring light/water, allocating
resources, surviving, reproducing, and decomposing have meaningful consequences.
First establish that the environment supports sustainable and varied behavior.
Then train controllers on the host and run frozen models on PicoSystem.
Continuous on-device controller evolution is a later experiment, separate from
the existing inheritance and mutation of plant traits.

The order is:

1. Qualify the environment, alongside a minimal model replay/screenshot bridge.
2. Define and validate the training objective.
3. Scale host training without changing its results.
4. Deploy and measure qualified controllers on the device.
5. Investigate inherited controller variation and unattended evolution.

Visual review is part of experiment evidence, not a final presentation task.
A full interactive training application is optional. Discuss substantial
ecology, observation/action, and objective changes before implementing them;
do not train around a known environmental or accounting defect.

## Foundations and current limitations

Available building blocks:

- deterministic shared host/device simulation, compact observations/actions,
  recurrent policy memory, and a fixed-point neural model interface;
- rain-fed environments with fixed startup resources and independent seeded
  weather, without gardener actions or ongoing scripted irrigation;
- matched evaluation, lifetime/cohort metrics, resource traces, and frozen
  experiment bundles with hash-verified selected replays;
- the production host renderer, native image output/PNG workflow, and an SDL
  player for existing scenes;
- serial evolutionary search and portable, CRC-protected final-model artifacts.

The [experiment workflow](garden-experiments.md) collects evidence; it does
not train. The trainer currently saves only the final model, with per-generation
fitness and fingerprints in its report. The normal scene player/image runner
does not yet load an arbitrary saved model under the exact evaluation setup.
The dedicated [visual-review tool](garden-visual-review.md) now supports exact
saved-model headless replay and timeline-verified screenshot galleries.

The initial local rain-fed baseline covered 48 trials (eight seeds, two
planting layouts, three policies) through 24 cycles, with six verified detailed
replays. Neural model `dc5e849d` ended nonviable in 3/16 runs; adaptive ended
nonviable in 0/16. This does not establish sustained descendant reproduction,
environmental balance, or learned generalization. The baseline lives locally
at `artifacts/garden-matches-baseline/`; it is ignored, not published evidence.
Preserve reproducible findings in versioned notes when accepting milestones.

## 1. Environment qualification

Create a small, versioned condition suite before running a large search.
Use deterministic weather/initial conditions, no gardener in scored runs, and
matched seeds for every policy comparison. Begin with controls varying light
and shade, water supply, and planting density, plus representative combinations.
Do not add unrelated biological systems simply to manufacture complexity.

Compare adaptive/reference policies with deliberately simple decision probes:
waiting, resource acquisition, growth allocation, or reserve behavior. A probe
such as conserving energy overnight tests a hypothesis; it is not automatically
a permanent rule or a feature that the neural controller must be handed.

Acceptance evidence must address:

- **Sustainability:** descendants survive full cycles and produce viable
  descendants of their own over multiple cycles and seeds. Founder longevity,
  raw birth count, and a nonempty final seed bank are insufficient alone.
- **Decision value:** matched interventions change measurable outcomes, and
  failures can be separated into environmental impossibility, insufficient
  observations/actions, and poor policy choices.
- **Pressure and variety:** resource access and crowding produce understandable
  tradeoffs rather than an always-winning scripted action.
- **Accounting:** rainfall, runoff, uptake, photosynthesis, upkeep, growth,
  reproduction, death, and reclamation have consistent declared semantics.
  Audit reset/seed-bank loopholes and capacity saturation. Current live-step
  resource checks do not reconstruct terminal budgets after death clears
  telemetry; close or explicitly bound that diagnostic gap.
- **Generalization:** conclusions use more than one fortunate seed/layout.
  Paired layouts sharing a seed are not independent statistical replicates.

Record hypotheses, suite version, seeds, horizons, acceptance criteria, numeric
outcomes, representative images, counterexamples, and remaining uncertainty.
Choose acceptance thresholds before selecting winning models, rather than
retrofitting a threshold to one attractive run.

## 2. Required visual review

### Minimum: screenshots of every generation's champion

A *search generation* is a trainer iteration, not a plant's biological
generation. Capture the initial model (generation zero) and the best-so-far
champion after every completed search generation. An unchanged champion still
gets an indexed gallery entry; identical model/image files may be deduplicated.

The first implementation should:

1. Persist the model, fitness, and generation identity before visual replay.
   Reconstruct evaluation worlds using the exact model, scenario, seed, weather
   version and horizon; do not substitute the playable scene's default policy.
2. Replay a small, fixed review panel. A reasonable initial panel is both
   rain-fed layouts at one predeclared review seed, with checkpoints in early
   daylight, after the first night, and late in the horizon. Clamp/deduplicate
   checkpoints for short test runs and record the actual ticks.
3. Render through the shared production snapshot/raster path, save native
   240 x 240 PNGs, and retain canonical framebuffer CRCs. Verify world hashes
   against equivalent headless evaluation; screenshot capture must not alter
   world state.
4. Generate a browsable contact sheet/gallery linking the native images and
   model. Label generation, model fingerprint, scenario, seed, tick/cycle,
   relevant survival/reproduction metrics, world hash, framebuffer CRC, and
   source/environment provenance. Nearest-neighbor enlargement can improve
   readability but must not replace the native capture.
5. Retain empty or failed gardens. Use the same review panel and checkpoints
   across generations so manual comparisons are meaningful, rather than
   selecting whichever frame makes each model look best.

Use dedicated, declared review seeds distinct from training and final test
seeds. Manual inspection informs model selection, so review images are not
untouched test evidence. Additional automatically selected successes/failures
are useful but must be labeled as selected examples, not an unbiased panel.

Capture on/off must yield identical training champions, fitness histories,
and evaluation hashes. Models passed to capture are immutable. Use bounded
queues and explicit retention limits; if rendering lags, retain replay jobs
durably or apply backpressure. Report pending/failed captures and never claim
the requested per-generation gallery is complete when entries are missing.

### Optional: real-time foreground viewing

Later, allow a normal-speed, pauseable/stepable foreground replay of a frozen
champion while background workers train headlessly at maximum speed. Keep a
model pinned for observation if desired, or adopt a new champion at an explicit
replay boundary. This is an independent, unscored observer world, not a slower
worker whose visual results influence fitness. Label its generation/model,
seed, and replay progress accordingly.

The renderer currently owns a process-global framebuffer. Give rendering one
owner, preferably a separate replay/capture process, rather than calling it
concurrently from training workers. Do not expose a live mutable worker world
to the viewer. Closing, pausing, or changing viewer cadence must not change
training decisions or seeds. Interactive experiments are separate from scored
runs. No streaming-video server or browser frontend is required initially.

## 3. Training objectives and experimental discipline

After environment qualification, select an objective that rewards sustainable
descendants rather than only short-term survival, raw births, or a brief
establishment gate. The existing training fitness and diagnostic replay-selection
order are different things; changing one must not silently change the other.

Define cohort denominators and follow-up eligibility for full-cycle survival
and reproducing descendants. Expose early deaths, recent births, extinction,
and available reproductive opportunity instead of hiding them in a single
score. Retain simple controls and matched before/after evaluations.

Specify training, validation, manual-review and final-test roles, seeds,
horizons, model/source identity, and stopping/model-selection rules. Audit
reward loopholes before scaling. Keep the final test set reserved until model
selection is over. Visual appeal is useful evidence but not proof of fitness.

## 4. Training throughput

Keep a dedicated optimized host-training build separate from safety-checked
correctness builds. Parallelize whole candidate evaluations first, leaving
individual worlds serial:

- generate mutations from the generation's fixed parent in canonical RNG order;
- give each worker its own worlds, observer counters, and immutable model input;
- select results in candidate order, preserving current strict-improvement
  tie behavior, independent of completion order;
- finish the generation before mutating the next parent.

Add a bounded worker-count option and verify identical champions, fitness
histories and hashes at 1/2/4/8/16 workers and with capture enabled/disabled.
Measure throughput, memory, queue pressure and rendering/diagnostic overhead;
do not assume hardware threads provide linear speedup.

A local three-repeat spot check on the Ryzen 7 9800X3D evaluated one frozen
neural model across 16 rain-fed worlds, each for 24 cycles: median 4.70 seconds
in the existing unoptimized UBSan build and 0.606 seconds in a separate Release
build. That is about 5,200x and 40,500x normal simulation pace, respectively,
not a host-versus-RP2040 maximum CPU benchmark. Build/container startup and
rendering were excluded; default/Release evaluation and trace outputs matched.
Formal saved scaling evidence remains a milestone, not a promised multiplier.

## 5. Device deployment

Load/integrate a selected saved controller and verify corresponding host/device
world states and intended pixels under matched supported conditions. Measure
PIM559 RAM, model flash use, inference/update deadlines, and physical behavior.
Host equivalence is not proof of device timing or USB/display reliability.

No host trainer, capture buffers, worker pool, or UI dependency belongs in
firmware. The first deployment target is autonomous ecology with fixed
controller weights, not on-device training.

## 6. Later inherited-controller experiments

Existing plant-trait inheritance is not neural-weight evolution. Separately
design bounded controller inheritance/mutation, model storage, and lineage
attribution. Use accelerated host runs to examine sustained viability,
diversity, and extinction before attempting unattended device evolution.
Persistence and recovery need their own resource and correctness decisions.

## Evidence and maintenance

Use issue #30 for milestone status and links to experiments, commits, and PRs.
Keep this plan synchronized when the design or acceptance gates change.
Promote important local-bundle findings into versioned notes without treating
ignored artifacts as remotely available. New phases are not permission to skip
discussion of substantive changes.

Related material:

- [Garden implementation contract](garden-simulator.md)
- [Matched experiment collection and replay](garden-experiments.md)
- [Host simulator and model search](host-simulator.md)
- [Lifetime and resource investigations](../benchmarks/garden-longevity/README.md)
- [General bring-up roadmap](roadmap.md)
