# Fixed repair policies on additional weather

Test whether the two [wear-initialized finalists](leaf-family-wear-pilot.md)
retain their mean family-renewal gains on additional weather, while reporting
family extinction separately. This follows the user's instruction to continue
the proposed fixed-policy comparison on 17 October 2026. Keep the day-608
horizon: varying duration as well would confound this weather comparison.

## Fixed policies and conditions

Use exactly the archived `initial`, `s1-g3-c4` and `s2-g3-c1` models from
`leaf-family-wear-pilot-results.json.gz`, SHA256
`baace2fd65ce2f725cbbe2d022b1ec96bcea119bee44e9fcf82f806b4b0ebb50`.
These are fixed wear, Search 1 and Search 2, respectively. Keep the verified
owned runtime, W2 growth and its memory, candidate-founder family routing,
selective resident competitors, seasonal rain, no gardener, capacities and all
physiology unchanged. No learning, model selection, ecological intervention,
firmware deployment or git publication is part of this comparison.

Use four seeds in this order: `58d7d6ca`, `9a903368`, `6b9c1a3e`, `59818bc3`.
Derive each from the first four SHA256 bytes, little-endian, of
`toy-factory/leaf-family-generalization-v1/weather-1` through `weather-4`.
Before any simulator calls, scan published JSON, compressed JSON, Markdown and
Python under benchmarks, docs and sim for hexadecimal/decimal seed tokens.
Exclude only this experiment's own files, preserve the inventory and hashes,
and stop for review on a prior occurrence; never silently choose replacements.

On each seed evaluate rainfed founders 1–3 and crowded founders 1–5, all with
all three policies. Keep the original exact renewal-first objective: six
64-day birth windows in (192,576], actual child and non-founder parent both
surviving 32 days, at most two credits per window, followed through day 608.
Average the eight seed/layout conditions equally, then founder roles equally
within each condition. Established-descendant occupancy stays secondary.

## Budget and checks

| Phase | Calls | Execution |
|---|---:|---|
| Archived reference | 3 | Each model on `98a89374`, crowded founder 4, day 608, captured; serial and byte-exact against the previous archive |
| Additional weather panel | 96 | Four seeds, eight roles, three policies; all captured; checked batches of two |
| Serial capture parity | 24 | Each seed/layout/model, founder 1, day 608 without capture; serial, compared with its panel output |
| Total ceiling | 123 | No reuse to enlarge the panel |

Use at most two concurrent research processes, a 180-second per-call timeout,
a 45-minute submission deadline from the first research call, a 256 MiB run
directory ceiling and at least 2 GiB free. Validate each complete batch before
submitting another. Stop on failed/invalid output, changed inputs or a limit;
already-submitted processes may finish within their timeout. Preserve failures.
No retry, resume, automatic extension or evidence deletion. Synthetic preflight
tests make no simulator calls; existing runtime build/test receipts are checked.

Freeze this protocol and orchestration/scoring/checker sources before research.
Retain source, binary and model identities, the seed audit, process receipts,
complete histories, canonical state and all captured framebuffers. Check exact
archived references before the panel. Parity removes only the framebuffer CRC
field; every other state/history field must agree. Save native comparison sheets
for every seed, including zero-score and extinct families. Reconstruct scores,
metrics, roster, limits, references and pixels offline in a portable archive.

## Interpretation

Report each learned policy against fixed wear separately, with exact aggregate
and seed/layout scores, paired role improvements/ties/regressions, founder
survival at days 1, 16 and 32, renewal in the closing window and in every window,
and family status at day 608. A family with no living plant but pending seeds is
dormant, not extinct. Extinction requires no living family member and no pending
family seed; report its last death/seed-resolution tick. Preserve all roles in
the means, including zero scores and extinction.

The prespecified renewal criterion remains strict primary-score improvement
over fixed wear, not occupancy alone. Report raw and equally condition-weighted
extinction rates alongside it; extinction does not become a new fitness term.
New family losses and avoided losses are paired by the same weather/layout/role.
Do not pool these new results into the original pilot's held-out score or choose
between finalists from this panel. Four weather seeds provide a bounded
generalization screen, not independent evidence from 96 different climates or
a population-wide stability guarantee. The result informs the next discussion;
it does not authorize rescue tuning, longer runs, more training or promotion.
