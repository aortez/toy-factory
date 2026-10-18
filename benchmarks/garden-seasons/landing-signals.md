# Landing signal-content probes

**Fixed-value controls weaken a simple “more sensing is better” explanation.
Fixed inputs can preserve survival and sometimes improve the score, with
important individual regressions.** No tested setting solves sustained renewal
on this panel, and no model or setting is promoted. This pass adds host-only
diagnostics, not training or a device change.

## Fixed experiment

The [predeclared protocol](landing-signals-protocol.md) uses all three current-only
training-selected finalists, unchanged, across the same 16 development conditions
as [broader validation](landing-validation.md). Ten probes separate occupancy
from water/light and replace groups with fixed values. There are **480 primary
worlds**, each lasting 192 Garden days, plus a one-worker repeat and 60 fixed
review frames. Ecology, scorer, weights, legacy sensing and gardener-off settings
remain unchanged. This is not a fresh generalization panel or controller search.

Occupancy is `(space_free, dead_only)`; resources are `(water_now, light_now)`.
Raw unsigned readings are centered by subtracting 128 before inference. Thus
`neutral` occupancy and `mid` resources, both `(128,128)`, give zero neural input;
raw zero gives **-128**, not zero. Fixed `occupied` occupancy is `(0,0)`, `open`
is `(255,0)`; resources `low` / `high` are `(0,0)` / `(255,255)`. Neutral is a
synthetic mask, not a physical average. Substitutions affect a packet copy only;
the cache retains real measurements. Root/absent/out-of-bounds gating remains.

## All outcomes, not just the helpful settings

Each cell below gives **established descendant endpoints / 64; aggregate change
versus that controller's live inputs**. The discussion abbreviates controllers
by the last two digits of their search seeds. `+` / `-` indicate the unchanged
lexicographic objective, not a majority of world wins. Each world contributes
four endpoint/window checks;
these are not 64 independent weather trials.

| Probe (occupancy, resources) | `6d697833` | `6d697834` | `6d697835` |
|---|---|---|---|
| live (live, live) | 64; control | 64; control | 64; control |
| water-light-only (neutral, live) | 64; + | 64; + | 64; - |
| occupancy-only (live, mid) | 32; - | 64; + | 64; - |
| neutral (neutral, mid) | 32; - | 64; + | 56; - |
| occupied (occupied, live) | 64; - | 64; + | 60; - |
| open (open, live) | 64; - | 64; + | 40; - |
| low-resources (live, low) | 64; - | 56; - | 40; - |
| high-resources (live, high) | 40; - | 56; - | 48; - |
| fixed-occupied (occupied, mid) | 32; - | 64; + | 64; + |
| fixed-open (open, mid) | 32; - | 64; + | 55; - |

The last cell also has one endpoint with living but unestablished descendants
and eight with no living descendant. Complete tiers, histories and all
world/seed/layout/climate comparisons are retained, including losses.

Three useful observations:

- **Controller 33:** zeroing water/light cuts established endpoints from 64 to
  32, but the prespecified raw-low constants retain all 64. Live resources still
  score better: weakest-window credit sum 358,065 versus 338,550 ticks, and
  zero-credit windows 33 versus 38. Its added light weights are all zero, so
  this resource substitution changes only its added water contribution.
  Removing occupancy while keeping resources improves the aggregate, yet loses
  three of four seed-level comparisons.
  The earlier zero-mask failure is not proof that changing resource readings
  are necessary for endpoint survival.
- **Controller 34:** even fully fixed added inputs can outrank live inputs.
  Fixed-open retains all 64 endpoints and raises weakest-window credit sum
  357,840 → 795,720, but total credit falls 5,466,720 → 5,360,820; worlds with
  credit in every window fall 6 → 4, and five of sixteen worlds score worse.
  Occupied occupancy with live resources also helps all four seed aggregates,
  but still loses three individual worlds. These are different compromises,
  not uniformly better controllers.
- **Controller 35:** fixing either group alone worsens the aggregate, yet
  fixing both to occupied/mid slightly improves it: weakest-window credit sum
  555,750 → 581,190, with all 64 established endpoints. It wins only three
  worlds, ties five and loses eight. Total credit falls 6,087,330 → 5,560,380,
  zero-credit windows rise 32 → 36, and **all 32 steady-climate windows** now
  have zero credit. Group contributions cannot be read as independent benefits.

Across all thirty controller/probe variants, **no steady-climate world earns
credit in all four windows**. Among the original live controllers, 32–33 of 64
windows earn zero credit. Populated screenshots, endpoint survival and durable
replacement remain separate properties. The objective remains unchanged;
these coverage gaps are reported separately.

## What this establishes—and does not

Fixed added-input settings can match endpoint coverage and exceed aggregate
scores in some tested controllers. That weakens a simple “extra environmental
information caused the gains” interpretation of the earlier ablations. It does
not show that live information is useless, or that these constants are good
policies outside this reused development panel. Fixed packets still convey
body-role/source-validity gating; the 77 legacy inputs and recurrent controller
remain active. None is a blind controller.

Water and light were substituted together, not independently. Not every fixed
combination was tested, notably fully fixed low/high-resource combinations.
Arbitrary constants also shift activation distributions. There are no new
independent training seeds or significance claims, and no selection from these
outcomes. In ordinary base-origin ecology, valid candidate landing packets
describe the same base-centered dispersal neighborhood; this is not evidence
of learned flower-site placement in the separate flower-origin experiment.

## Fixed visual review

All sixty frames were inspected. Every sheet is seasonal seed `25185eeb`, day
192; ordinary/crowded layouts are the two columns. Part 1 rows: live,
water-light-only, occupancy-only, neutral, occupied. Part 2 rows: open,
low-resources, high-resources, fixed-occupied, fixed-open. Empty failures are
retained. Most populated snapshots show tall flowering stalks, with differences
in density and location rather than demonstrated durable morphological variety.
The single late checkpoint cannot establish continuous renewal.

| Controller | Part 1 | Part 2 |
|---|---|---|
| `6d697833` | [Gallery](frames/landing-signals-s6d697833-current-part-1.png) | [Gallery](frames/landing-signals-s6d697833-current-part-2.png) |
| `6d697834` | [Gallery](frames/landing-signals-s6d697834-current-part-1.png) | [Gallery](frames/landing-signals-s6d697834-current-part-2.png) |
| `6d697835` | [Gallery](frames/landing-signals-s6d697835-current-part-1.png) | [Gallery](frames/landing-signals-s6d697835-current-part-2.png) |

## Evidence and reproduction

- [Summary](landing-signals-summary.json): identities, complete per-world
  diagnostics and all 27 paired comparisons by seed/layout/climate.
- [Complete results](landing-signals-results.json.gz): all 480 histories and
  unchanged renewal scores, including every failure.
- [Models](landing-signals-models.json.gz): the three original canonical files
  as hex JSON, byte-identical to their pinned pilot inputs.
- [Frame receipts](landing-signals-gallery.json.gz): all sixty capture results,
  framebuffer CRCs and sheet associations.
- [Host workflow and verification](../../docs/garden-landing-signals.md).

The complete panel repeated with one worker and captures disabled; exact results,
scores and model bytes matched. Live and all-neutral probes also match the prior
current/off biological records. Collection plus repetition took **710.94 seconds**,
including process/scoring/capture overhead, with regression checks running
concurrently; this is not simulation-only throughput or device timing. The
frozen local bundle is
`artifacts/garden-landing-signals-v1/`; manifest SHA-256:
`a16d4e20f4f7a56d69c9536002be1ee01471f29cf91cde4ef6d75c2cc4c94f1d`.
Independent frozen verification passed: all 480 worlds, original model bytes,
scores and all 60 captures (raw pixels, PNGs and six contact sheets) reproduce
exactly. Sources and builds stayed frozen during collection; the portable report and its retained
evidence tests were added afterwards. A source snapshot is not proof of a
reproducible build.

Retained-evidence checks rescore all 480 worlds, match live/neutral controls,
validate the compact summary and every original model, and reconstruct RGB565
pixels from every gallery tile to check its CRC and headless endpoint.
All **134 optimized ordinary-ecology host CTests** pass, including those retained
evidence checks. All **124 older-research CTests** also pass, as does the focused
native signal test with isolated wide + flower dispersal. These builds use
undefined-behavior sanitizers. Docker clang-format and `git diff --check` pass.

The explicit host probe owns its configuration in the copied run and includes it
in a separate GSP1 diagnostic identity. Invalid configuration and failed steps
preserve state and audit outputs. Ordinary replay and model files do not acquire
implicit overrides. This pass does not change firmware or require a device flash.

## Stop and next proposal

The fixed experiment is exhausted. Do not promote a constant or controller from
this panel or start an open-ended search. Next, discuss a bounded **same-state
decision trace**: record actual water/light and occupancy ranges, then compare
live and fixed-input bids on exactly the same observations and private memory,
without feeding counterfactual decisions back into the world. Separating water
from light and inspecting activation shifts would make the next training choice
better grounded; it would still be a diagnostic, not a fitness or causality proof.
