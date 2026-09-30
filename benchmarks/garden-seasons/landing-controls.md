# Matched live/fixed-input training

**This small pilot does not show a consistent advantage from varying added
landing inputs.** Live-trained/live-input controllers win one paired evaluation
and lose two against fixed-trained/fixed-input controllers. The new world seeds
also expose survival failures hidden by the earlier development panel. Neither
arm solves sustained steady-climate renewal, and no controller is promoted.

## What was held equal

The [predeclared protocol](landing-controls-protocol.md) uses two current-only
networks with identical architecture, starting weights and mutable parameter
count. The live arm receives real added readings. The fixed arm replaces all
four added current readings with raw zero at valid sources, which encodes as
**-128**, not zero. Its extra weights can therefore learn fixed offsets. Legacy
observations, recurrence, source/body gating and real sensor caches remain.
The fixed arm is not blind; redundant fixed columns still change effective
optimization difficulty. This controls extra fixed offsets, not every possible
search-difficulty difference.

Both start from the original legacy controller with zero extension weights,
not a later selected finalist. Three paired search RNG seeds, two generations
and three children give **42 candidate evaluations**. Each child gets 32 legacy
and 16 extension mutations in the original order. Only strict improvements on
the unchanged renewal objective select parents. Ecology, scoring, inference,
encoding and device defaults are unchanged; no C changes were needed.

Training uses one old world seed across both layouts and climates. The separate
old review seed supplies four scored conditions and four screenshots for each
generation's champion. Only after all searches finish do the six finalists and
two initial-profile controls run the **four previously unused evaluation seeds**
across sixteen conditions each. There are 168 training, 72 review and 128
evaluation results: **368 scored runs**, plus the capture checks. Search seeds
and environmental cases are paired, not independent pooled replicates.

The live searches recover every earlier current-only candidate model, mutation
receipt, selected parent, biological trajectory and score. All initial-profile
controls also agree. Explicit GSP1 diagnostic hashes distinguish profiles; the
older GLR1 hash is not substituted for that identity.

## New-seed results

Controller labels abbreviate the final two digits of the search seed. Each
endpoint count is out of **64 checks: sixteen worlds times four late windows**,
not 64 independent worlds. Credit is the unchanged sum of each world's weakest
window, in simulation ticks. Primary ordering considers terminal tiers before
credit; an aggregate win is not a majority vote across worlds.

| Pair | Established endpoints: live / fixed | Weakest-window credit: live / fixed | Live world wins / ties / losses | Aggregate winner |
|---|---:|---:|---:|---|
| 33 | 40 / 32 | 428,430 / 208,725 | 6 / 7 / 3 | live |
| 34 | 48 / 63 | 246,375 / 528,090 | 6 / 1 / 9 | fixed |
| 35 | 56 / 56 | 67,035 / 201,330 | 5 / 3 / 8 | fixed |

The same winner holds in both climate aggregates for each pair, so only pair 33
passes its three consistency checks. The predeclared overall gate requires all
three pairs and both climates to favor live without terminal-tier losses:
**three of nine checks pass; the gate fails**. All seed/layout slices and
individual regressions remain in the evidence.

Important qualifications:

- **33 is not a promotion candidate just because it wins its pair.** The initial
  controller has 48 established endpoints, versus live's 40 and fixed's 32.
  Both trained variants rank below the initial controller on this panel. Live
  also loses the crowded-layout aggregate against fixed despite its overall win.
- **34's fixed finalist is different from its live finalist.** Training selects
  fixed `g2-c2` versus live `g1-c2`; both improve their same-profile initial
  aggregate, but fixed ranks higher on evaluation. Its remaining endpoint is
  living-but-unestablished, not observed extinct. Its 63 established endpoints
  still coexist with 35 zero-credit windows out of 64 and only three worlds
  with credit in every window.
- **35 retains equal endpoint coverage but different renewal.** Fixed's
  weakest-window credit is 201,330 versus live's 67,035; total credit is
  3,505,110 versus 3,042,690. The rainfed-layout aggregate favors live, while the
  crowded layout favors fixed. There is no uniform per-world winner.

The final live models previously had 64/64 established endpoints on the earlier
validation seeds. The unchanged models now have **40/64, 48/64 and 56/64** on
these new seeds; their remaining checks are observed-extinct endpoints. This
is direct evidence of panel sensitivity, not a behavior change caused by the
new runner. Even the initial controller has sixteen observed-extinct checks.

No steady-climate world, under any of the six finalists or either initial-profile
control, earns renewal credit in all four windows. Finalists retain 24–29
zero-credit steady windows out of 32 each. Endpoint survival and durable
replacement remain separate properties.

## Selection and visual review

All models were selected on training results only. Final champions:

| Pair | Live | Fixed |
|---|---|---|
| 33 | g1-c0 | g1-c0 |
| 34 | g1-c2 | g2-c2 |
| 35 | g1-c1 | g2-c1 |

Pair 33 even selects identical model bytes under the two profiles. Its outcome
difference is therefore an input-profile difference for that selected model;
pairs 34/35 combine differing training-selected weights and input profiles.
No evaluation-based reselection, extra generation or constant sweep followed.

All **72 review images** were inspected. Each sheet has days 16 and 192 as its
two columns; rows are generation 0 rainfed/crowded, then generation 1, then
generation 2. The fixed review seed is `ed52188c`, seasonal climate. Empty
generation-zero crowded gardens are retained, as are the fixed-34 generation-1
crowded failure and fixed-35 generation-1 rainfed failure. Later selected models
can populate these review worlds, but those images do not demonstrate reliable
new-seed performance or sustained renewal. Populated scenes still mostly contain
tall flowering stalks, not demonstrated durable morphological variety.

| Pair | Live gallery | Fixed gallery |
|---|---|---|
| 33 | [All generations](frames/landing-controls-s6d697833-live.png) | [All generations](frames/landing-controls-s6d697833-fixed.png) |
| 34 | [All generations](frames/landing-controls-s6d697834-live.png) | [All generations](frames/landing-controls-s6d697834-fixed.png) |
| 35 | [All generations](frames/landing-controls-s6d697835-live.png) | [All generations](frames/landing-controls-s6d697835-fixed.png) |

## Evidence and reproduction

- [Summary](landing-controls-summary.json): complete paired comparisons and
  slices, selected histories, endpoint/renewal diagnostics and provenance.
- [Full results](landing-controls-results.json.gz): every candidate's training
  results, every generation's review results, all final/initial evaluation worlds
  and their exact biological ledgers and scores, including failures.
- [Models](landing-controls-models.json.gz): initial legacy file and all 42
  canonical candidate files, including losing candidates.
- [Gallery receipts](landing-controls-gallery.json.gz): all 72 native captures,
  model/profile identities, state hashes, framebuffer CRCs and sheet layout.
- [Host workflow](../../docs/garden-landing-controls.md).

Collection and the complete one-worker, capture-free repeat took **504.58 seconds**.
All results, mutation RNG states, selected models and canonical bytes matched.
This includes analysis/process/capture overhead and concurrent regression tests,
not device timing or isolated headless throughput. The frozen local bundle is
`artifacts/garden-landing-controls-v1/`; manifest SHA-256:
`9b498ea254b8417b1cf2366032147de9d40c09cd45f2f6cac8eedef4041f8229`.
Sources and native build stayed fixed throughout collection. Documentation and
retained-evidence tests were added afterwards; a source snapshot alone is not
proof of reproducible binary provenance.

Independent frozen verification reproduces all 42 candidates, 368 scored runs,
model bytes and every capture, raw pixel buffer, PNG and contact sheet exactly.
The portable artifacts above retain that complete evidence, not just winners.
Retained-evidence tests rescore every candidate/review/evaluation world,
reconstruct training-only selection and all comparisons, inspect every canonical
model, and recover each gallery tile's RGB565 pixels to check its framebuffer
CRC. All eight focused tests pass, including malformed identities, source-change
rejection, matched RNG receipts and capture/worker equivalence.
The final optimized ordinary-ecology suite passes **137/137 CTests** in 54.96
seconds with undefined-behavior sanitizers; `git diff --check` also passes.
This experiment adds host orchestration and evidence only. Native C, firmware
and device state are unchanged, so no device flash or timing claim is involved.

## Stop and next proposal

The budget is exhausted. This result does not show that sensing is useless or
that fixed inputs are generally preferable. It shows that the earlier gains
were not a replicated, robust live-information advantage at this search depth.
The effective search landscapes differ, and three searches are a small sample.

The clearest next issue is **training-condition coverage**: all candidates were
selected on one environmental seed, while new seeds expose substantial failures.
Next discuss a bounded multi-seed training comparison before increasing model
size or simply running longer on the same seed. Retain the fixed-input control,
freeze the training/evaluation split before collection, and reserve new seeds
for evaluation. The seeds inspected here are now development data. Do not alter
the sensors, objective, ecology or device model automatically.
