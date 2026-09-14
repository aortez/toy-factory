# Lineage fitness v1: an executable candidate, not trainer adoption

The first lineage-based evaluation function is implemented and tested against
synthetic challenges and the eight frozen 192-day native histories. It measures
actual established descendants and further reproduction, rather than using seed
purchases as a proxy. **It is not wired into training.**

The [contract](lineage-fitness-protocol.md) was frozen before computing these
rankings. The saved cases were already inspected during earlier investigations,
so this is exploratory objective design, not held-out validation. No weights,
environment, controller, or simulator behavior changed during this experiment.

## What the function rewards

During `(Garden day 160, day 192]`, maximize this integer tuple, left to right:

`(terminal tier, renewing parents, new establishments, descendant live ticks)`

- **Terminal tier:** 1 for a living established non-founder at the endpoint;
  0 for living plants without an established non-founder; -1 for no living
  plants and no pending seeds. No living plants but pending seeds means
  `needs-followup`, not an assumed success or extinction.
- **Renewing parents:** distinct non-founder parents that survived their own
  first day and have a child completing its first day alive inside the window.
  Each parent counts once. Older parents count; they need not still be alive
  when their child is confirmed.
- **New establishments:** children completing their first day alive inside
  the window, including children of founders. Later death does not revoke that
  observed event.
- **Descendant live ticks:** observed occupancy of established non-founders
  during the window, including older descendants. Sample every 15 logic ticks;
  one Garden day is 3,840 ticks. This is not an estimate of unobserved lifespan.

There is no direct reward for purchases, body size, stores, actions, generation
numbers, or founder longevity. Parent links, seed-to-child identities and
lifetimes must reconcile. Natural death, patch censoring and recent births
remain explicit. Seed-only endings prevent a suite from claiming a ranking;
they cannot silently disappear from its denominator.

For matched suites, compare minimum terminal tier first, then the sums of
terminal tiers, renewing parents, establishments and descendant live ticks.
Thus successes elsewhere cannot offset an observed extinction. See the protocol
for exact same-tick boundaries and follow-up semantics.

## Results on the saved native histories

Baseline means the frozen `neural-no-night-growth` controller; reserve means
`energy-reserve-v1`. Both retain model `dc5e849d`, drainage off, selective leaf
maintenance and the original bank-8 settings. The two capacities are experimental
configurations, not a single selected training environment.

All eight endpoints have established descendants, no living founders and eight
pending seeds. They therefore all have terminal tier 1; none requires seed-only
follow-up. That branch is covered by synthetic tests, not these native results.

| Capacity / seed / schedule / policy | Renewing parents | Establishments | Descendant live ticks |
|---|---:|---:|---:|
| 256 / b61837dc / fresh-4 / baseline | 5 | 7 | 754,155 |
| 256 / b61837dc / fresh-4 / reserve | 1 | 1 | 715,800 |
| 256 / b61837dc / fresh-1 / baseline | 2 | 4 | 736,395 |
| 256 / b61837dc / fresh-1 / reserve | 5 | 8 | 738,990 |
| 512 / b61837dc / fresh-1 / baseline | 7 | 14 | 749,325 |
| 512 / b61837dc / fresh-1 / reserve | 4 | 7 | 844,020 |
| 512 / c7f54e18 / fresh-1 / baseline | 3 | 3 | 966,540 |
| 512 / c7f54e18 / fresh-1 / reserve | 4 | 7 | 918,255 |

Each controller wins two of the four paired conditions. In every pair, renewing
parent count decides the rank. At 512 / b61837dc, the baseline wins despite
having less descendant occupancy; at 512 / c7f54e18, reserve wins despite having
less occupancy. Those are consequences of the declared priority, not arithmetic
errors or an independent demonstration that faster turnover is preferable.

The aggregate keys are:

- Baseline: `(1, 4, 17, 28, 3206415)`.
- Reserve: `(1, 4, 14, 23, 3217065)`.

Baseline ranks first on 17 versus 14 renewing parents, although reserve has
slightly more descendant occupancy. Removing either baseline-winning condition
reverses the aggregate result. Removing either reserve-winning condition keeps
baseline first. **This panel does not establish a robust policy winner.**

### Why 51 establishments, rather than the previous 48?

The previous [descendant audit](descendant-outcomes.md) followed seeds purchased
inside the closing window. This function instead follows **first-day
confirmations inside the window**. Three additional children were born just
before day 160 and confirmed afterward:

- `512.44.fresh-1.off.neural`, child 84: birth 614,040, confirmation 617,880.
- `512.44.fresh-1.off.reserve`, child 64: birth 614,040, confirmation 617,880.
- The same reserve history, child 65: birth 614,130, confirmation 617,970.

The boundary is tick 614,400. The old 48 and the three extra confirmations give
51; there is no new birth or changed simulation. Likewise, the 31 renewing
parents here include older generations. They are not the old audit's six
closing-cohort children that themselves went on to establish a child.

## Adversarial arithmetic: what works and what remains questionable

These fixtures are **hand-built scoring histories, not native policy runs**.
They test semantics and expose preferences without claiming that a controller
can realize every history.

| Four-day scoring-window fixture | Key `(tier, renewal, establishment, live ticks)` |
|---|---|
| Founder survives, no descendants | `(0, 0, 0, 0)` |
| Founder makes seeds but none establish | `(0, 0, 0, 0)` |
| Old sterile descendant persists | `(1, 0, 0, 15360)` |
| Child and grandchild establish | `(1, 1, 2, 11550)` |
| Same, but parent later dies | `(1, 1, 2, 7710)` |
| Reproductive burst, then observed extinction | `(-1, 1, 2, 3960)` |
| Founder dies with a pending seed | `needs-followup`, no key |
| Established parent with one long-lived child | `(1, 1, 1, 23055)` |
| Same parent, four children dying just after age one day | `(1, 1, 4, 15420)` |

The intended improvements work: seed spam earns nothing by itself; observed
extinction loses to survival; established child credit can outlive its parent;
and ancestry is not reset when a parent is reclaimed.

But the last two rows expose an important remaining preference: **v1 rewards
four brief establishments more than one longer-lived child**. One extra renewing
parent also outranks any gain in lower components. Lexicographic order eliminates
adjustable weights, not the underlying value judgments. It is not automatically
a durable-lineage objective merely because its events involve descendants.

An endpoint fixture also changes terminal tier when a descendant dies just one
sample earlier, despite only 15 fewer occupancy ticks. Founder-only survival
ties seed production without establishment, which could be a learning plateau
for a controller that cannot yet reproduce. The available frozen model does
reproduce, but that does not prove its mutations have a useful learning signal.

## Verification and reproduction

`sim/garden_lineage_fitness.py` is an offline reference scorer, collector and
reviewer. It first reproduces the complete frozen descendant analysis from the
original world/site, seed-attempt and resource evidence. It exports all scored
identities/events, terminal states, paired/aggregate/leave-one-out ranks and
arithmetic fixtures. It neither runs a simulator nor modifies a model.

All **94 CTests pass** across default / bank-8 / bank-16 builds (44 + 25 + 25).
The new Python suite has 24 tests covering lifetime/window/patch boundaries,
parent death, unresolved follow-up, ancestry/order invariance, seed spam,
aggregation, exact ties and the deliberately retained adverse tradeoffs.
Existing trainer smoke tests are regression checks, not a new training search.

Full reanalysis checks 198 original artifacts, 393,224 world/site checkpoints,
65,544 exact-attempt checkpoints, 12,386 seed lifetimes and 2,601,285 live resource
steps. The new five-artifact bundle snapshots 419 source files. Its manifest
SHA-256 is `3229d3962af2298a303a9b68cfe43a390112a185c3edad7a5091f1fd64fcb3e8`.
The [portable JSON](lineage-fitness-summary.json) includes the complete score
evidence and manifest identity. Native pixels are unchanged; the existing
[recruitment contact sheet](recruitment-sites.png) remains the visual reference.

```sh
python3 -W error sim/test_garden_lineage_fitness.py

# Requires the original local recruitment, attempts and descendant bundles.
# Use a new output path; existing bundles are never overwritten.
docker compose run --rm firmware python3 sim/garden_lineage_fitness.py \
    --output artifacts/garden-lineage-fitness-new

docker compose run --rm firmware python3 sim/garden_lineage_fitness.py \
    --verify artifacts/garden-lineage-fitness-v1

# Optional fresh export, only after complete reanalysis succeeds.
python3 sim/garden_lineage_fitness.py \
    --verify artifacts/garden-lineage-fitness-v1 \
    --export artifacts/lineage-fitness-review.json
```

Ignored native bundles are not part of a fresh checkout. The protocol, report,
JSON and synthetic unit tests are portable; full native reanalysis needs those
bundles. Prior analysis outputs remain unchanged.

## Next decision

Keep this version as a fixed reference, not a selected trainer objective.
Before integration, resolve the short-lived-offspring versus sustained-lineage
preference and define deterministic follow-up for seed-only endings. A focused
next revision should be judged against these same counterexamples, not tuned
to make either existing controller win.

Then freeze one experimental environment and a small training/review panel,
and run a bounded pilot with saved models and deterministic screenshots. The
purpose is to see what optimizing the score actually produces, not keep adding
diagnostics indefinitely. No environment-qualification milestone, firmware
change, training run, commit or push is part of this scoring task.
