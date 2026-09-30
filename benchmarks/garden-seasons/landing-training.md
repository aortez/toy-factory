# Landing-aware renewal pilot

The fixed 63-candidate pilot is complete. **Current-only inputs are the most
consistent survival lead in this panel; sustained renewal is still incomplete.**
No controller, ecology change or device default is promoted.

## What ran

The [predeclared protocol](landing-training-protocol.md) used three search RNG
seeds, three input masks, two generations of three children, and the same
initial controller. Every candidate saw the same four training conditions:
rainfed/crowded × steady/seasonal, world seed `a9c30c1f`, to Garden day 192.
Generation-selected champions were reviewed on the same four conditions with
seed `ed52188c`. These are previously seen development seeds, not a final test.

The existing individual-minimum bounded-renewal objective was reused unchanged.
Four windows cover days (62,94], (94,126], (126,158], (158,190], each with two
days of endpoint follow-up. A first-day-confirmed child of an established
non-founder parent earns at most 32 days of lifetime credit. Historical births,
old sterile survivors and pending seeds do not earn perpetual renewal credit.

## Results

Endpoint success below means an established descendant is present at **all 16
review checks** (four worlds × four window follow-ups). It does not mean those
worlds continuously reproduced. Window counts are listed in search-seed order
`6d697833`, `6d697834`, `6d697835`.

| Inputs | Final champions passing all endpoint checks | Zero-credit review windows, out of 16 | Review worlds with credit in every window, out of 4 |
|---|---:|---|---|
| Off | 0 / 3 | 6, 12, 8 | 1, 1, 2 |
| Current only | 3 / 3 | 7, 9, 7 | 1, 1, 2 |
| Current + history | 0 / 3 | 11, 12, 11 | 1, 1, 1 |

All nine searches improved their training key. All three current-only final
champions also outranked their matched off/history finalists on the aggregate
review key, primarily through more reliable established-descendant presence.
They were selected in generation one and retained in generation two.

However, current-only did **not** solve renewal or uniformly maximize its raw
credit. It still has 7–9 zero-credit review windows, and no more worlds with
credit in all four windows than the off arm. Some steady-climate gardens remain
populated while earning little or no recent renewal credit. The seasonal
galleries show living plants, but the ledger is needed to distinguish turnover
from old bodies.

The history arm is not supported as the next default by this small experiment:
two of its three final review keys are worse than the initial controller, even
though all improve training. This is **not evidence that history is useless**.
History exposes more active parameters under the same mutation schedule; the
pilot mixes information availability with search difficulty and only tests
one short search configuration.

Overfitting is visible within generations. For search seed `6d697834`, both the
off and history arms pass all review endpoint checks at generation one, then
lose that property at generation two while improving training. Review never
overrides training selection; those regressions and their empty screenshots
remain in the record.

## Evidence and reproducibility

- [Summary](landing-training-summary.json): every candidate identity/training
  key, generation selection/RNG state, and finalist per-world outcomes.
- [Complete histories](landing-training-histories.json.gz): all candidate and
  generation-review ledgers, scores and decisions, not just finalists.
- [Model archive](landing-training-models.json.gz): JSON mapping filenames to
  canonical file bytes encoded as hex; the initial TGM1 plus all 63 TGL2 files.
- Nine contact sheets below retain all **108** generation-review frames,
  including empty worlds. Full raw pixels and receipts remain in the local
  immutable bundle at `artifacts/garden-landing-training-v1/`.

The entire search/review repeated with one worker and captures disabled:
models, RNG states, exact ledgers, scores and choices matched. Collection plus
that repetition took **568.95 seconds**. These include diagnostics and process
overhead; this is not device timing or a simulation-only throughput benchmark.

Frozen-bundle manifest SHA-256:
`f1e16d3a495dd04c2cceba9bfcbe67253b4bf1c1b9fee9f50286363268b8f6c2`.
The independent verifier also passed, replaying the same search and all 108
recorded frames (raw pixels, PNGs and contact sheets);
see [workflow and verification commands](../../docs/garden-landing-training.md).
The source snapshot records the collection state; it is not by itself proof
of binary provenance.

Host checks passed: **132 final default / 131 optimized ordinary / 124
older-research CTests**, plus five focused native/inference tests with wide +
flower dispersal. The final default suite includes cross-checks of the retained
model bytes, histories and compact summary, and re-scores all finalist reviews.
The training pilot itself accepts ordinary ecology only. After collection,
its Python CTest registration was restricted to that configuration; this changes
test selection, not the collected binary, scores or simulation. No device flash.

## Fixed generation galleries

Each sheet: columns are days **16 / 192**. Rows are generation 0 rainfed/crowded,
generation 1 rainfed/crowded, generation 2 rainfed/crowded. All use the seasonal
review world `ed52188c`. The ordinary rainfed garden can die while the crowded
one survives; that outcome is retained rather than replaced by a prettier case.

| Search seed | Off | Current only | Current + history |
|---|---|---|---|
| `6d697833` | [Gallery](frames/landing-training-s6d697833-off.png) | [Gallery](frames/landing-training-s6d697833-current.png) | [Gallery](frames/landing-training-s6d697833-history.png) |
| `6d697834` | [Gallery](frames/landing-training-s6d697834-off.png) | [Gallery](frames/landing-training-s6d697834-current.png) | [Gallery](frames/landing-training-s6d697834-history.png) |
| `6d697835` | [Gallery](frames/landing-training-s6d697835-off.png) | [Gallery](frames/landing-training-s6d697835-current.png) | [Gallery](frames/landing-training-s6d697835-history.png) |

## Stop here

The next useful experiment is frozen-controller validation across more weather
seeds, with inference-time input ablation to distinguish useful sensing from
favorable weight changes. Define that panel first. Do not extend this search,
change the fitness function or adopt a winner based on these review results.

Follow-up: the [completed frozen-controller validation](landing-validation.md)
now performs that broader panel and same-weight ablation. The original pilot
results, selected models and protocol above are unchanged.
