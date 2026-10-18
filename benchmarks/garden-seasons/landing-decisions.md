# Same-state landing decisions

The added inputs can change priorities, growth-direction rankings and private
memory without changing the requested action category. Water and light affect
the three saved controllers differently. This explains part of the earlier
fixed-input sensitivity; it does **not** establish that the controllers interpret
changing conditions usefully. No training, model selection, ecology change or
device update occurs in this pass.

## Unchanged worlds, hypothetical decisions

The [predeclared protocol](landing-decisions-protocol.md) retains all three
current-only finalists and the same sixteen development conditions: four seeds,
two layouts and two climates, each for 192 Garden days. The live decision alone
advances the world. At a sampled query, sixteen native evaluations reuse exactly
the same observation and incoming memory: the previous ten group probes, plus
individual water/light substitutions at raw 0, 128 and 255. Hypothetical memory
and proposals never feed back into a later decision.

All **48 live results** exactly match the earlier validation results, including
the original model metadata, complete ledgers and GLR1 run hashes. This preserves
the earlier survival and renewal outcomes; it does not repair their substantial
zero-renewal windows.

The observer counted **135,839 actual policy queries** and retained **1,992
samples**, checking all **31,872 native probe results** against an independent
integer reference. The latter total includes 1,992 live controls. Sampling takes
the first root and first stem query per Garden day, with no artificial query on
idle days. These are pre-arbitration proposals, not accepted growth actions.

Controller abbreviations below are the final two digits of their search seeds.
Full model identities and hashes are retained in the summary.

| Controller | Root queries / samples | Stem queries / samples | Stem samples: early / middle / late |
|---|---:|---:|---:|
| 33 | 19,956 / 329 | 18,243 / 314 | 148 / 131 / 35 |
| 34 | 19,319 / 331 | 21,627 / 315 | 144 / 133 / 38 |
| 35 | 20,832 / 356 | 35,862 / 347 | 162 / 149 / 36 |

Early means days 0–31, middle 32–157, late 158–191. First-query sampling is not
an unbiased query-frequency estimate; late-query coverage is especially sparse.
All 1,016 root samples retain identical inputs, decisions and intermediates under
every probe because the added inputs are masked for roots.

## Actual readings are not centered around raw 128

These distributions cover **every valid common-source query**, not just retained
samples. They are query-weighted landing-neighborhood readings, not a uniform
survey of the world or physical water units.

| Controller | Water range / median | Light range / median |
|---|---|---|
| 33 | 0–46 / 6 | 24–255 / 74 |
| 34 | 0–46 / 7 | 24–255 / 79 |
| 35 | 0–73 / 6 | 24–255 / 68 |

Both occupancy fields span 0–255 in every controller's queries; dead-only has
median zero. All histograms and exact count/sum statistics are retained.

The encoder subtracts 128. Thus observed common water inputs occupy -128…-82
for controllers 33/34 and -128…-55 for 35. The old "neutral" raw value 128
lies **outside every observed common-water range** in this panel. Zeroing this
neural input removes a substantial offset; it is not replacing water with its
typical value. This is a reason to control for fixed offsets in training, not
proof that the encoding itself is wrong or that normalization will improve it.

## What reaches a proposal?

No probe changes the action category in any of the **976 sampled stem queries**.
For live inputs, the network's highest action logit is EXTEND in all 976;
structural constraints force six to FINISH, leaving 970 EXTEND proposals. Live
EXTEND-logit margins over the next action range from 1–38, 4–38 and 4–41 for
controllers 33, 34 and 35 respectively. This does not imply all unsampled
decisions, or later decisions in counterfactual worlds, would behave the same.

Here, `water-mid` and `light-mid` replace only that added field at valid sources
with raw 128. Legacy water/light sensing remains live. Each count compares a
probe against the original decision on the identical captured state.

| Controller / probe | Priority changed | Candidate order changed | First available direction changed | Next memory changed |
|---|---:|---:|---:|---:|
| 33 water-mid | 299 / 314 | 27 / 313 | 8 / 313 | 312 / 314 |
| 33 light-mid | 0 / 314 | 0 / 313 | 0 / 313 | 0 / 314 |
| 34 water-mid | 0 / 315 | 262 / 312 | 124 / 312 | 90 / 315 |
| 34 light-mid | 210 / 315 | 147 / 312 | 71 / 312 | 10 / 315 |
| 35 water-mid | 0 / 347 | 0 / 345 | 0 / 345 | 0 / 347 |
| 35 light-mid | 301 / 347 | 29 / 345 | 15 / 345 | 38 / 347 |

Ranking denominators require both proposals to EXTEND. A first-available
direction is still not an accepted, affordable growth action, and priority may
lose all-tip arbitration. Altered next memory is not applied in this experiment.
Complete counts for all sixteen probes, phases, worlds and seed/layout/climate
slices are retained, not just these mid-value examples.

- **33:** all added light weights are zero, so light-only probes are exact
  no-ops by construction. Its common water weights -8 and -6 turn the negative
  centered water input into positive contributions. Replacing water with 128
  removes those contributions. Raw water 0 changes priority in 140/314 samples
  but the first available direction in 0/313; raw 255 changes that direction
  in 8/313. Sensitivity to removing a baseline does not establish useful tracking
  of environmental variation.
- **34:** both fields affect sampled rankings. Water 0/255 changes the first
  available direction in 35/312 and 139/312 samples; light 0/255 changes it in
  80/312 and 84/312. Water affects no sampled priority; light often does. These
  immediate differences are not evidence that the altered direction is better.
- **35:** all three water-only probes change some common preactivations but no
  sampled hidden outputs, proposals or next memory. Its only added common-water
  connection is weight +1 into hidden unit 8, whose bias is -209. Across all
  347 stem samples, the complete live preactivation is -10,572…-7,293; even
  water-high leaves it at -10,321…-7,044. Its activation remains zero. There is
  also a candidate-layer water weight, so this does not prove every water path
  is inactive; the candidate-layer explanation was not investigated. Light
  probes do reach priorities and rankings.

In the live common hidden layer, output-at-zero counts are 1,550/5,024,
1,725/5,040 and 1,515/5,552; none is at 127. The retained fields named
`low_clipped_units` / `high_clipped_units` count outputs at these bounds, including
exact values and quantization. They do not measure only values changed by a
clamp, and these common-layer figures do not describe candidate-layer saturation.

## Evidence, verification and limits

- [Summary](landing-decisions-summary.json): identities, overall and sliced
  counters, per-world query/sample/histogram summaries and hashes.
- [Complete results](landing-decisions-results.json.gz): all original native
  world results and full per-world/phase/probe analyses.
- [Raw traces](landing-decisions-traces.json.gz): world-keyed original JSONL
  strings, retaining exact bytes, model files, incoming tensors, native decisions,
  day/role censuses and all-query histograms.
- [Workflow and verification](../../docs/garden-landing-decisions.md).

The earlier live-gallery first rows remain the visual evidence for these
unchanged trajectories: [33](frames/landing-signals-s6d697833-current-part-1.png),
[34](frames/landing-signals-s6d697834-current-part-1.png),
[35](frames/landing-signals-s6d697835-current-part-1.png).
No new screenshots or counterfactual-world images were taken.

Collection and the single-worker repeat took **90.54 seconds**, including trace
I/O, independent analysis and process overhead; this is not device timing or
simulation-only throughput. Every raw trace and complete result repeated exactly.
Independent frozen verification then reran all 48 worlds and recomputed every
probe comparison. Local bundle: `artifacts/garden-landing-decisions-v1/`;
manifest SHA-256:
`6d3e34ab41575df3f91e555a8334de33d3e26d793bad047716193a5a538dd258`.
Sources and build stayed fixed during collection; documentation, explanatory
comments and retained-evidence tests were added afterwards. A source snapshot
alone is not proof of reproducible binary provenance.

Retained-evidence tests independently recompute all 31,872 probe results, verify
raw trace hashes and complete original-world controls, and reconstruct the
summary. Native tests cover read-only inputs, callback-error rollback and retry,
invalid outputs, I/O failure, and ordinary/observed state equivalence. Short
replays also retain identical captured pixels with tracing enabled or disabled.

The final ordinary-ecology suite passes **136/136 CTests** in 52.32 seconds;
the older-research suite passes **124/124**. The native decision test also passes
in a separate wide + flower-dispersal build. These optimized builds use
undefined-behavior sanitizers. Docker clang-format and `git diff --check` pass.
An earlier test run correctly rejected concurrent documentation edits through
its source-freeze guards; the complete rerun above kept sources fixed.

## Stop and next proposal

The bounded diagnostic is complete. These three shallow-search finalists show
different uses of the added pathways, but this reused development panel does not
establish robust learned sensing or solve steady-climate renewal.

Next discuss a **small paired training comparison of live versus fixed added
inputs**, with equal parameter count, initial weights, search seeds and budget.
Predeclare the fixed-input control, held-out comparison panel, stopping rules and
visual review before collecting results. Preserve body/source gating and legacy
sensing so the comparison asks whether varying added information helps beyond
extra fixed offsets. Keep the objective and ecology unchanged; do not tune
constants against these outcomes or automatically change the encoding. No new
training or promotion is authorized by this report.
