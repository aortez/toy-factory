# Frozen landing-controller validation

**Current-only remains the most consistent survival lead on the broader panel,
but its added inputs help two finalists and hurt one under the frozen objective.**
None of these controllers solves sustained renewal. No training, reselection,
ecology adjustment, promotion or device flash was performed.

## Fixed experiment

The [predeclared protocol](landing-validation-protocol.md) retained all nine
final training-selected champions from the [pilot](landing-training.md), not
just its promising current-only arm. Each current champion also ran with its
added inputs off; each history champion ran with history removed and with all
added inputs off. The initial pretrained controller was included as baseline.
Ablation changed only the stored input mode and outer CRC, never weights.

Four additional world/weather seeds crossed with two layouts and steady/seasonal
climates give 16 conditions per variant, each run for 192 Garden days. The
unchanged bounded-renewal objective scores four late windows and their two-day
follow-ups. Ordinary production ecology, gardener and irrigation off throughout.

There are **19 labeled variants, 18 distinct model files, 304 primary worlds and
76 fixed review frames**. Search `6d697835`'s off finalist and history finalist
with all added inputs disabled are byte-identical and produce identical results.
That duplicate is retained for the prespecified comparison, not counted as an
independent controller. This is a development panel, not a final test set.

## Broader survival result, remaining renewal gap

Numbers below are in search-seed order `6d697833`, `6d697834`, `6d697835`.
An established endpoint means an established descendant is present at that
window's follow-up; it does not establish uninterrupted reproduction.
Each finalist has 64 endpoint/window checks across 16 worlds, not 64 independent
weather trials.

| Original input mode | Established endpoints / 64 | Zero-credit windows / 64 | Worlds with credit in all four windows / 16 |
|---|---|---|---|
| Off | 46, 48, 63 | 34, 38, 30 | 5, 6, 7 |
| Current only | **64, 64, 64** | 33, 33, 32 | 5, 6, 5 |
| Current + history | 61, 63, 39 | 33, 34, 43 | 5, 6, 3 |
| Initial baseline | 56 | 33 | 5 |

All three original current-only finalists outrank their matched off-trained
finalists on the aggregate objective. Their paired world wins/ties/losses are
11/2/3, 7/4/5 and 7/3/6: the aggregate result includes individual regressions.
Current-only does not uniformly maximize renewal credit or the number of
worlds with credit in every window. Survival reliability is the clearest gain.

The climate split exposes where most zero credit remains:

| Current finalist | Steady zero-credit windows / 32 | Seasonal zero-credit windows / 32 | Steady / seasonal worlds with credit in every window |
|---|---:|---:|---|
| `6d697833` | 27 | 6 | 0 / 5 |
| `6d697834` | 30 | 3 | 0 / 6 |
| `6d697835` | 28 | 4 | 0 / 5 |

Every steady world still contains an established descendant at every endpoint,
but each has at least one zero-credit window. Populated gardens and sustained
replacement are different achievements. The seasonal conditions generate much
more renewal credit here; these observations alone do not identify the cause of
the steady-world stalls.

## Same-weight ablations

“Original better/worse” uses the unchanged aggregate lexicographic objective.
Paired W/T/L counts compare the original to its ablated version in each world;
they are diagnostics, not majority-vote fitness. Aggregate ordering prioritizes
the weakest endpoint tier, then tier sum, weakest-window credit sum, total credit.

| Trained controller | Ablated to | Original aggregate | Paired W/T/L / 16 | Established endpoints, original → ablated |
|---|---|---|---|---|
| `6d697833` current | Off | Better | 12 / 2 / 2 | 64 → 32 |
| `6d697834` current | Off | Worse | 6 / 5 / 5 | 64 → 64 |
| `6d697835` current | Off | Better | 8 / 3 / 5 | 64 → 56 |
| `6d697833` history | Current | Better | 6 / 4 / 6 | 61 → 55 |
| `6d697834` history | Current | Better | 12 / 2 / 2 | 63 → 20 |
| `6d697835` history | Current | Better | 5 / 7 / 4 | 39 → 30 |
| `6d697833` history | Off | Worse | 7 / 5 / 4 | 61 → 62 |
| `6d697834` history | Off | Better | 5 / 4 / 7 | 63 → 56 |
| `6d697835` history | Off | Worse | 5 / 1 / 10 | 39 → 63 |

Thus the current-only result is not entirely explained by favorable changes to
legacy weights: two controllers lose substantial endpoint coverage when their
added inputs are disabled. But the third survives equally well without them,
and its weakest-window credit sum rises from 357,840 to 440,385 ticks. Its total
credit falls from 5,466,720 to 4,704,810; the existing objective favors the higher
weakest-window sum. No new tie-breaker was introduced.

History is not uniformly useless either. Removing only the history group
(including warmup) worsens all three history-trained controllers, while removing
all added inputs improves two. This is consistent with feature interactions and
activation shifts, not a clean additive contribution from each group.

These results establish dependence under input zeroing, **not proof of useful
interpretation of changing environmental information**. Some cues can act like
role-dependent biases, warmup saturates, and zeroing shifts activation
distributions. Benefits also vary by seed: current finalists `33` and `35` each
lose an individual seed-level aggregate comparison to their own off variant.
The full per-seed/layout/climate breakdown is retained, including those losses.

## Fixed visual review

All sheets use seasonal seed `25185eeb`, days **16 / 192** as columns. Each mode
has ordinary/crowded layout as two successive rows. Current sheets show current
then off; history sheets show history, current, then off. All 76 frames were
inspected, including empty worlds. Some ablation failures are already empty at
day 16. The current finalists are populated in both shown layouts. Many surviving
gardens show tall flowering stalks; some variants show bushier forms. These
snapshots do not demonstrate durable morphological diversity or continuous renewal.

| Search seed | Off | Current only and ablation | History and ablations |
|---|---|---|---|
| `6d697833` | [Gallery](frames/landing-validation-s6d697833-off.png) | [Gallery](frames/landing-validation-s6d697833-current.png) | [Gallery](frames/landing-validation-s6d697833-history.png) |
| `6d697834` | [Gallery](frames/landing-validation-s6d697834-off.png) | [Gallery](frames/landing-validation-s6d697834-current.png) | [Gallery](frames/landing-validation-s6d697834-history.png) |
| `6d697835` | [Gallery](frames/landing-validation-s6d697835-off.png) | [Gallery](frames/landing-validation-s6d697835-current.png) | [Gallery](frames/landing-validation-s6d697835-history.png) |

[Initial baseline gallery](frames/landing-validation-initial.png).

## Evidence and reproduction

- [Compact summary](landing-validation-summary.json): model identities, all
  condition/window outcomes, and paired comparisons by seed, layout and climate.
- [Complete results](landing-validation-results.json.gz): all 304 exact
  lineage/seed histories, scores and comparisons, not only successful worlds.
- [Model archive](landing-validation-models.json.gz): canonical file bytes as
  hex JSON, including all labeled variants and the original TGM1 controller.
- [Gallery receipts](landing-validation-gallery.json.gz): all frame/model
  associations, raw framebuffer CRCs, census and lineage/seed records.
- [Workflow and verification commands](../../docs/garden-landing-validation.md).

The full panel repeated with one worker and captures disabled; exact outputs,
derived model bytes and scores matched. Collection plus repetition took
**524.28 seconds**, including captures, diagnostics and process overhead, with
other checks running concurrently. This is not a device or simulation-only
throughput measurement. The immutable local bundle is
`artifacts/garden-landing-validation-v1/`; its manifest SHA-256 is
`9ee74404c07207470410c8f191cfb80b01c540a97db82ba49568aeff5cec3a59`.
The source snapshot records collection state, not proof of a reproducible build.
Independent frozen verification also passed: all 304 worlds, derived models,
scores and 76 frames (raw pixels, PNGs and contact sheets) reproduced exactly.
Retained-evidence checks rescore every world, compare the compact summary and
canonical model bytes, and reconstruct every gallery tile's RGB565 bytes to
match its recorded framebuffer CRC and headless endpoint.
All **132 optimized ordinary-ecology host CTests** pass, including those retained
evidence checks; the explicit ablation test also passes with isolated wide +
flower dispersal. Docker clang-format and `git diff --check` pass. Collection
sources were frozen throughout; the portable report/evidence and their extra
regression checks were added afterwards. This step changes only host tools,
tests and documentation; no firmware rebuild or device testing was needed.

## Stop and next proposal

The fixed panel is exhausted; no finalist was reselected from these outcomes.
Before a larger search, run a bounded signal-level test on the same saved
controllers: distinguish water/light contributions from occupancy cues and
check whether fixed-value substitutes retain the gains. That would test actual
environmental information more directly than another blanket mask comparison.
Keep the renewal gaps visible; neither a robust survival score nor a populated
screenshot is sufficient for controller promotion.
