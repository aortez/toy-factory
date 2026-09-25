# From purchased seeds to established descendants

The approved offline lineage follow-up is complete. **Survival-confirmed seed
production is not a substitute for successful descendants.** Across the existing
eight histories, 2,074 closing-window purchases yield 61 seedlings, 48 confirmed
day survivors, and six of those survivors with a day-surviving child of their
own. Thirty-one parents reach the four-bin production cap without any observed
established offspring from their closing purchases.

There is also direct evidence that descendant success can outlive its parent:
one child reaches its one-day mark after its parent's natural death, and two
after their parents' patch deaths. A parent's terminal state must not erase
independently observed descendant survival.

This is a new join/reanalysis of **saved native histories**, not new simulations,
training, ecology changes, or a selected fitness. The
[protocol](descendant-outcomes-protocol.md) retains all eight previously selected
development cases from the [recruitment](recruitment-sites.md) and
[exact germination-check](seed-attempts.md) audits. Their outcomes were already
partly inspected; this is not held-out validation or an independent policy ranking.

## Cohort and follow-up

Count seeds **created during (Garden day 160, day 192]**, linking each purchase
to its parent and, if it germinates, its exact child. One Garden day is 3,840
logic ticks. The eight histories run through day 192, but this primary cohort
covers only their closing 32 days.

An established child is alive at age one day. Natural death at that boundary
fails; patch death at/before it censors natural-survival follow-up. Recent
children without a whole observed day remain horizon-censored. Later death does
not undo an already observed day of survival, but remains visible separately.
Seed expiry is failure to germinate, **not seedling death**.

| Stage | All closing purchases | Full potential follow-up subset |
|---|---:|---:|
| Seeds purchased | 2,074 | 1,945 |
| Expired without germinating | 1,949 | 1,885 |
| Still banked at the horizon | 64 | 0 |
| Germinated children | 61 | 60 |
| Children confirmed alive at age one day | 48 | 48 |
| Natural death before/at age one day | 11 | 11 |
| Patch-censored before/at age one day | 1 | 1 |
| Insufficient child follow-up at horizon | 1 | 0 |
| Established children with an established child of their own | 6 | 6 |

The full-potential subset is selected by **creation time**, allowing one maximum
seed lifetime plus one child day before the horizon (two days total). Its one
patch-censored child is still censored; calendar availability does not guarantee
undisturbed observation. The 129 recent purchases contain 64 expiries, 64 pending
seeds and one young child. Known recent outcomes are retained but not mixed into
the full-potential denominator.

All 61 births in the old closing birth-based cohort happen to originate from
closing purchases here; the code explicitly reconciles earlier-created seeds
rather than assuming the two cohorts always coincide. The final-generation
count describes six observed established-and-reproducing children, not six
independent populations or a time-adjusted reproduction rate. Families overlap,
and younger children have less time to reproduce.

## Same seed volume, very different lineage outcomes

Baseline is the frozen `neural-no-night-growth` policy; reserve is the unchanged
`energy-reserve-v1` guard. All use model `dc5e849d`, drainage off and selective
leaf maintenance. These are whole-world histories, not the later single-seedling
candidate intervention or the newer bank-16 configuration.

| Capacity / seed / schedule / policy | Purchases | Births | Day survivors | Of those, with day-surviving offspring |
|---|---:|---:|---:|---:|
| 256 / b61837dc / fresh-4 / baseline | 260 | 8 | 7 | 1 |
| 256 / b61837dc / fresh-4 / reserve | 255 | 1 | 1 | 0 |
| 256 / b61837dc / fresh-1 / baseline | 259 | 4 | 4 | 0 |
| 256 / b61837dc / fresh-1 / reserve | 257 | 8 | 8 | 2 |
| 512 / b61837dc / fresh-1 / baseline | 265 | 17 | 13 | 3 |
| 512 / b61837dc / fresh-1 / reserve | 262 | 11 | 5 | 0 |
| 512 / c7f54e18 / fresh-1 / baseline | 256 | 3 | 3 | 0 |
| 512 / c7f54e18 / fresh-1 / reserve | 260 | 9 | 7 | 0 |

Raw purchases vary only 255–265, while day-surviving children vary 1–13.
This supports measuring establishment directly, not choosing one policy from
these deliberately selected, correlated cases. The existing
[native contact sheet](recruitment-sites.png) remains the visual reference;
no pixels changed in this offline analysis.

## What the parent-production signal misses

Of 115 plants alive at some point during the closing window:

| Closing-purchase outcome | Plants | Reach four confirmed production bins | Alive at horizon |
|---|---:|---:|---:|
| No purchases | 33 | 0 | 11 |
| Purchases, no observed established child | 52 | 31 | 27 |
| At least one established child | 30 | 27 | 15 |

The cap is carried over only as a diagnostic. These are variable-age parents
observed over up to 32 days, **not comparable scalar scores from the eight-day
allocation challenge**. No-purchase plants may grow or have reproduced earlier;
they are not labeled WAIT controllers. Young parents' shorter exposure and
incomplete seed outcomes remain in their records.

There are 1,953 purchases followed by a full additional day of parent survival;
46 lead to established children. Two additional established children come from
purchases whose parent-survival confirmation was patch-censored. Thus parental
confirmation alone neither demonstrates offspring success nor covers all of it.
Among the 48 established children, 28 remain alive at the horizon, six later die
naturally and fourteen later die in patches. One-day establishment is itself
an intermediate milestone, not proof of persistent population replacement.

## Concrete examples

Examples use the protocol's first qualifying `(case key, parent ID)`, not a
post-hoc search for the most dramatic plant:

- **Producer without establishment:** parent 26 in `256.44.fresh-1.off.neural`
  buys twelve closing seeds; ten purchases get parent-survival confirmation
  across five age bins. All twelve seeds expire. Its mature seeds undergo
  129 checks with some other column open, including 102 within recorded
  at-creation dispersal support; none is eligible at its actual location.
- **Producer with establishment:** parent 24 in the same history buys 73 seeds
  and establishes children 34, 35 and 37. It survives the closing window.
- **Natural death with continuing descendants:** parent 21 in
  `256.44.fresh-1.off.reserve` buys 61 seeds and establishes children 33, 35
  and 37. Child 33 establishes child 38. Parent 21 dies naturally at tick
  694,260; child 33 later dies in a patch at 711,450. Grandchild 38 remains
  alive at the horizon after 10.96875 days, with no seed purchases of its own.
  It is also the first qualifying non-producing survivor.

The last example shows both the value and limitation of the extra generation:
the lineage outlives older relatives, but a living grandchild alone does not
demonstrate endless turnover. The records do not establish that those deaths
were a beneficial policy choice or the cause of recruitment.

## Reproductive opportunity is evidence, not a reward adjustment

The join attributes **513,761 exact seed visits**, including 497,338 mature
checks, to the closing seed cohort. Sixty-one actual-location eligible checks
germinate. There are 8,854 mature checks with an opening somewhere else but a
blocked actual seed location. These are repeated checks, not distinct vacancies
or independent germination probabilities.

Of 1,949 expired seeds, 429 encounter an opening somewhere during a mature check;
246 encounter one within recorded at-creation dispersal support. That does not
move the actual seed or demonstrate a counterfactual surviving offspring.
Of 52 producers without an established child, 42 have some mature checks with
an opening somewhere and ten have none. This does not make either group a
clean policy comparison: their bodies also affect shade, spacing and capacity.

Keep these opportunity diagnostics alongside outcomes. Do not normalize away
failure using a policy-dependent denominator or reward hypothetical openings.
The original exact-check audit remains the source for sequential competition
and overlapping blockers.

## Implementation, verification and reproduction

`sim/garden_descendants.py` adds a read-only collector/reviewer and per-seed,
per-parent, per-case and cohort exports. It reanalyzes both old bundles, checks
that their world/site/patch histories are identical, and reconciles all seed
identities, purchase counters, births and opportunity visits. Parent reclamation
does not lose ancestry. It never runs a simulator or assigns fitness.

All **91 CTests pass** across default / bank-8 / bank-16 builds (43 + 24 + 24).
The new Python suite has 23 accounting cases, including natural/patch/horizon
boundaries, posthumous germination, two-generation establishment, cohort
eligibility, expired versus dead, changed/truncated visits and input preservation.
Synthetic tests establish accounting semantics, not native reachability.

Full reanalysis verifies 198 original artifacts, 393,224 world/site checkpoints,
65,544 exact-attempt checkpoints, 12,386 seed lifetimes and 2,601,285 live resource
steps. The new five-artifact bundle snapshots 414 source files. Its manifest
SHA-256 is `529c8ce6cda02dd720c1bac7d6d9a5fdfd316e9cdb4ba84707b1c260f3b11ae1`.
All detailed outcomes are in the [JSON export](descendant-outcomes-summary.json).
Original artifacts, code and reports are retained; no C/C++ source, ecology,
firmware, controller ABI or training fitness was changed by this task.

```sh
# Requires both original local frozen input bundles; choose NEW output paths.
docker compose run --rm firmware python3 sim/garden_descendants.py \
    --output artifacts/garden-descendant-outcomes-new

docker compose run --rm firmware python3 sim/garden_descendants.py \
    --verify artifacts/garden-descendant-outcomes-v1

# Optional portable export, written only after full reanalysis succeeds.
python3 sim/garden_descendants.py --verify artifacts/garden-descendant-outcomes-v1 \
    --export artifacts/descendants-review.json
```

The ignored native bundles are not included in a fresh checkout. This report,
protocol and JSON are the portable review material. Existing native/trainer smoke
tests ran as regression checks; no new experiment, training search or screenshot
capture was performed.

## Recommended next decision

Use **established descendant persistence and further reproduction** as the
candidate A-life outcome, while keeping parent survival and resource stress
separate. Do not make the parent's continued life a prerequisite for counting
observed offspring success. Keep confirmed purchases as an allocation diagnostic,
not the final reproductive reward.

The next bounded step is to freeze a lineage-outcome evaluation contract against
these examples: distinguish no production, production without establishment,
established offspring, and observed further-generation establishment, with
natural deaths, patches and recent births explicit. Agree on that contract
before scalarization or training. These results improve the evidence available
for that discussion; they do not qualify the ecology or select a fitness.
