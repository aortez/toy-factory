# Garden construction choices: roots offer the clearer next test

The direction trace reproduces the four historical `f7ee4528` worlds exactly.
It finds legal, affordable wetter root endpoints that the model ranked below
its chosen direction. It does **not** explain the highlighted plants' later
light failures as simply ignoring a brighter shoot endpoint during construction.
No model, resource rule, spending guard or host/device default has changed.

## What was measured

The [frozen protocol](landing-directions-protocol.md) follows the
[uptake attribution](landing-uptake.md), retaining its model, weather,
eight plant slots, 256 world nodes, 32-node construction budget and eight
seed-bank slots. Control and dawn-reserve candidate each run with fixed and
rotating reproduction purchase order, through day 256. These remain failed
population-qualification candidates, not promoted policies.

Exactly eight native experimental calls run each world with the observer on
and off. Every full result, old decision/resource trace and final framebuffer
matches the historical population capture. The new host-only observer records
applied candidate rankings, endpoint light/moisture/clearance and collision
flags, and the plant's existing root-soil-cell coverage. It uses bounded,
caller-owned storage and does not modify proposals, world state or RNG state.

The raw analysis checks all **262,144 world steps, 2,443,220 bids and 9,670,816
candidate endpoints**. Portable receipts retain every paid construction or
tip-closure event: **3,952**, including founders and all later lineages, not just
the focal failures. Per-plant spending and allocation ticks reconcile with the
saved resource/body histories. Raw streams also retain the unpaid bids.

## Existing choices leave some water opportunities unused

Alternatives must be legal and pass the same purchase and resource guards.
The first-day water reserve is recomputed for each endpoint; two alternatives
in each candidate world fail that check and are excluded. Upfront prices and
the selected tip/action do not change in this diagnostic.

For roots, potential uptake is `min(endpoint moisture, species uptake limit)`:
three units for flower/shrub, two for groundcover. For a newly allocated leaf,
potential energy is `endpoint light / 64`, rounded down. Neither quantity is
income actually collected by a hypothetical plant: uptake precedes growth,
and later soil, shade, maintenance, storage and decisions can all change.

| World | Root additions | Higher-uptake alternative | Reused cell, new equally wet/wetter option | Leaf additions | Higher-energy alternative |
| --- | ---: | ---: | ---: | ---: | ---: |
| Fixed control | 303 | 57 | 61 | 267 | 5 |
| Fixed candidate | 476 | 106 | 114 | 390 | 8 |
| Rotating control | 362 | 71 | 74 | 301 | 7 |
| Rotating candidate | 461 | 112 | 113 | 377 | 7 |

Opportunity columns count decisions, not extra resource units, and overlap.
The cell column counts only purchases into an already occupied own-root soil
cell with a legal, affordable new-cell alternative that is no drier. It does
not establish that the new cell would stay wet or improve survival. All paid
allocations take their first-ranked candidate: these misses are lower-ranked
choices, not fallback after an unavailable first choice.

One concrete example is candidate plant 15 at tick **460965**, shared by both
orders. From root tip `(167,149)`, the model ranks straight, right, left. It
buys `(167,155)`, an already occupied soil cell with zero moisture. The right
endpoint `(171,154)` has seven moisture, occupies a new own-root soil cell and
passes the same guards. Both cost seven energy and five water; their immediate
per-root uptake potentials are zero versus three. The left endpoint is blocked
by the plant's own body. This opportunity occurs after that plant's first
energy shortage, so it is not an explanation or rescue of that earlier event.

Moisture is already in the model's endpoint observations. Own-root soil-cell
coverage is new diagnostic information, not a new policy input; existing
near-node collision flags describe a smaller spatial neighborhood. The trace
shows the ranking but does not identify which neural weight caused it.

## The highlighted light failures need a different explanation

Candidate plant 28 makes fourteen shoot additions. At every one, its chosen
endpoint is at least as bright as every legal alternative. Plants 15 and 16
likewise have no brighter legal alternative at any of their fifteen and
fourteen shoot additions. These construction summaries agree across orders;
the histories are correlated, not independent confirmation trials.

Plant 28 completes construction at tick **649245**, with thirty nodes and no
active tips. Its shoot tip closes at maximum depth at 648855, one root tip is
blocked at 649065, and the other reaches maximum depth at 649245. The fixed
world's terminal energy failure comes much later, at 916620. Globally, every
paid closure is explained by maximum depth or blocked directions; none is a
voluntary policy finish while extension remains possible below the depth cap.

This is consistent with the previous self-shading evidence: current endpoint
brightness is not the new body's future whole-canopy income under changing
sun angle, neighbors and weather. Adding another copy of current light to the
observations would not supply that missing information. The diagnostic also
does not prove that any different morphology would survive.

There is a separate allocation limitation. Water-failing candidate plant 9
adds only **one root node versus twenty-seven shoot nodes**; its sole root
addition already has no higher-uptake alternative. A root-direction-only test
cannot directly repair that root/shoot allocation decision. Mature plant 28,
meanwhile, dies with ample water, so better water placement is not a presumed
solution to its energy failure.

## Next bounded question

Test one host-only root-direction change: among legal endpoints that preserve
the current bid's affordability, prefer strictly greater capped uptake
potential, keeping the model's order on ties. Keep shoot choices, tip priorities,
actions, prices, guards, weather, capacities and seed rules unchanged. Do not
turn a currently rejected bid into an eligible one as part of this test.

Use a frozen paired replay with exact controls/repeats, first-effect receipts
and whole-population resource, survival and reproduction accounting. Measure
whether water actually improves and whether the changed growth harms energy
or reproduction. This is a proposed experiment, **not implemented here** or a
claim that wetter-at-purchase is a good long-term policy. Canopy-level light
planning and root/shoot allocation remain separate questions; do not combine
them into this first direction test. No qualification threshold is relaxed.

The subsequent [root-only direction comparison](landing-root-direction.md)
now completes that experiment. All four pairs fail the existing harm checks;
gross water uptake does not consistently become retained water or reproduction.
The candidate remains explicitly opt-in and no default changes.

## Reproduction and verification

`make host-probe-landing-directions` builds and performs the eight-call capture.
Set `GARDEN_LANDING_DIRECTIONS_OUT` to a fresh directory; existing output is
rejected. The reusable host CLI option is `--direction-trace NEW.jsonl`, with
`--stand-dawn` and a stand trace. It uses the stand trace's bounds and requires
an explicit completion footer. Files are created without clobbering old data.

```sh
docker compose run --rm -T firmware python3 sim/garden_landing_directions.py \
  --verify benchmarks/garden-seasons/landing-directions-results.json.gz
docker compose run --rm -T firmware python3 sim/garden_landing_directions.py \
  --verify artifacts/garden-landing-directions-v1
```

Portable verification recomputes every retained construction assessment,
spending/allocation coverage and summary, and checks historical neutrality.
Raw verification additionally hashes every artifact, checks the 2,304-file
source archive and frozen executable/cache, and reanalyzes all four complete
direction streams. Both pass without running a simulator.

| Artifact | SHA-256 |
| --- | --- |
| [Portable result](landing-directions-results.json.gz) | `ceb1b8a5ab527eb42b635d87b795c646a1afbed493b896917897ec7ef55dab63` |
| Raw manifest | `e02c35f51c46662afb01dc630a092a416b93cc88193a1b6d199e1d61222a4ea0` |
| Protocol | `00ae28c7e44e1e6da41f17e008a7bee34ae3bd73cf073f4bce114cee3841315a` |
| Native executable | `1c29057c94d7788d918d1c2df10fa0b8da2236e1b2a27cb6f28dc56e5e5cb221` |
| Build cache | `f93e432ba3d6c2704864bf10ffb3dddcc93e442878d605864862a5180184b0e6` |

All 186 host CTest entries pass on a stable source tree. That run preceded
portable-result promotion; the saved-direction case was then skipped. All
twelve direction tests pass after promotion, and the four focused CTest entries
(directions, uptake, root-choice CLI and native trace contract) pass. They cover
the frozen findings, corrupt/missing evidence,
first-day water guards, canonical endpoints/rankings, bitmap bounds, no-clobber
creation and a full-day observer-on/off comparison. The native trace contract
also tests bounded storage and rejects invalid publication. Postcapture changes
add tests and documentation, not changes to the frozen observer or analyzer.
There was no training, firmware flash or hardware validation for this host-only
diagnostic.
