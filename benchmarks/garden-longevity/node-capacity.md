# Host-only node capacity experiment

## Fixed protocol

The [node ownership audit](node-budget.md) found no dead storage to reclaim in
the late combined-ecology worlds. Test whether doubling the living-tissue budget
restores renewal or merely produces larger, static plants. This is a diagnostic,
not a proposal to raise device memory or a claim that more capacity is better.

Compare the frozen **combined 256-node** condition with **combined 512 nodes**.
Keep model `dc5e849d`, original NN / night-growth-veto NN / adaptive policies,
rain-v1, wide scattering, storage-limited uptake, costs and all other rules fixed.
Use the same eight seeds from batch `0x6d617463`, both layouts, 24 cycles
(92,160 logic ticks), final eight cycles as the late window. This is 48 matched
world identities, with shared weather seeds, not 96 independent replicates.
No training, gardener, irrigation, new lifespan, pruning, plant/seed capacity
change, or firmware deployment. Reference: `artifacts/garden-water-wide-combined`.

Before collection, verify the new default and combined-256 evaluators reproduce
both corresponding full-horizon frozen reports byte for byte. Record the same
fixed 24-image panel: seeds `6f47c12c` and `9c530b07`, both layouts, three policies,
ticks 68,760 and 92,160. Retain regressions and extinctions, not just better images.

Measures: full-cycle offspring survivors / eligible offspring; durable parents;
late births and deaths; late seed germination with complete follow-up; node and
plant-slot pressure; live/dead root/shoot ownership; spacing/light/water blockers.
Qualification counts are cumulative and can lag births. More bodies or seeds
alone are not evidence of sustained renewal. Audit observations are repeated,
overlapping post-step states, not independent failure probabilities.

## Index and memory review

The new OFF-by-default `TOY_FACTORY_GARDEN_LARGE_POOL` option requires the explicit
combined host experiment. Headers reject it in firmware. Normal `make host-build`
explicitly disables it. It is not a runtime capacity switch.

Two byte-sized assumptions needed host-only widening: reclamation's old-to-new
node remap and snapshot parent distance. World node indices/counts and snapshot
counts were already 16-bit. Macro-sized buffers and full-node iteration extend
to 512. Compile definitions propagate to consumers of the snapshot ABI.

| Storage | Default / combined 256 | Host experiment 512 |
|---|---:|---:|
| Garden world | 4,352 B | 6,912 B |
| One world node | 10 B | 10 B |
| Scene snapshot | 1,664 B | 3,456 B |
| One snapshot garden node | 5 B | 6 B |
| Reclamation remap scratch | 256 B | 1,024 B |

These are native `sizeof` measurements and the declared remap array, not total
firmware RAM or performance estimates. Framebuffer dimensions are unchanged.
Device/default representations stay compact. Boundary tests exercise 255-crossing
remaps, high seedling indices, long rendered parent edges, exact capacity, and
one-past-capacity rejection without state mutation.

Growth phase remains an eight-bit policy state: every node is still visited by
the 16-bit scan, but the rotating start position at 512 nodes remains in 0–255.
Do not silently widen it: that would also change controller semantics. This trial
tests extra storage under the existing policy, not an optimized 512-node policy.
Environment identity is separate from world hash, so identical early states may
share a hash; reports, inspectors and screenshot replayers must match capacity.

## Reproduce

```sh
make host-build
docker compose run --rm firmware cmake -S sim \
  -B artifacts/build-host-garden-512 -G Ninja \
  -DTOY_FACTORY_GARDEN_WIDE_DISPERSAL=ON \
  -DTOY_FACTORY_GARDEN_WATER_HEADROOM=ON \
  -DTOY_FACTORY_GARDEN_COMBINED_EXPERIMENT=ON \
  -DTOY_FACTORY_GARDEN_LARGE_POOL=ON \
  -DTOY_FACTORY_SIMULATOR_SANITIZERS=ON
docker compose run --rm firmware cmake --build artifacts/build-host-garden-512
docker compose run --rm firmware python3 sim/test_garden_capacity.py \
  --reference-build artifacts/build-host-water-wide-combined \
  --large-build artifacts/build-host-garden-512
docker compose run --rm firmware ctest --test-dir build-host --output-on-failure

docker compose run --rm firmware python3 sim/garden_experiments.py \
  --output artifacts/garden-capacity-512 \
  --dispersal wide-v1 --water-uptake headroom-v1 --combined-experiment --node-capacity 512 \
  --evaluator artifacts/build-host-garden-512/toy-factory-garden-eval \
  --inspector artifacts/build-host-garden-512/toy-factory-garden-inspect \
  --candidate-model artifacts/garden-lifetimes/champion.tgm \
  --control-model artifacts/garden-lifetimes/champion.tgm \
  --candidate-probe no-night-growth-v1 \
  --training-report artifacts/garden-lifetimes/training.json \
  --split exploratory --cycles 24 --trials 8 --seed 0x6d617463
docker compose run --rm firmware python3 sim/garden_ecology.py \
  --control artifacts/garden-water-wide-combined --candidate artifacts/garden-capacity-512 \
  --change node-capacity --late-cycles 8 --output artifacts/garden-capacity-comparison.json
docker compose run --rm firmware python3 sim/garden_node_audit.py \
  --bundle artifacts/garden-capacity-512 --output artifacts/garden-capacity-512-nodes
docker compose run --rm firmware python3 sim/garden_establishment.py \
  --bundle artifacts/garden-capacity-512 --output artifacts/garden-capacity-512-audit \
  --inspector artifacts/build-host-garden-512/toy-factory-garden-inspect
docker compose run --rm firmware python3 sim/garden_gallery.py \
  --bundle artifacts/garden-capacity-512 --output artifacts/garden-capacity-512-gallery \
  --replayer artifacts/build-host-garden-512/toy-factory-garden-replay \
  --include-adaptive --seed 6f47c12c --seed 9c530b07 --checkpoint 68760 --checkpoint 92160
```

Build the combined 256 reference as described in [combined-ecology.md](combined-ecology.md).
CLI capacity flags validate binary identity; they do not modify it. All outputs
refuse overwrite. Keep sources unchanged during collection. Frozen audit/gallery
tools support `--verify`; the experiment supports `--replay`.

## Results

Completed locally on 2026-09-11 after checkpoint `4f26187` on `green-garden`.
This work is uncommitted/unpushed. Device and default capacity remain 256.

### Extra storage helps establishment, but not broad sustained renewal

Totals across 16 worlds per policy; each cell is **256 → 512**:

| Policy | Births | Full-cycle survivors / eligible offspring | Durable parents | Final living plants | Late births / deaths |
|---|---:|---:|---:|---:|---:|
| Original NN | 155 → 188 | 83/155 → 87/188 | 34 → 37 | 99 → 102 | 0/0 → 1/0 |
| NN + night-growth veto | 134 → 203 | 80/134 → 118/201 | 19 → 31 | 104 → 124 | 1/0 → 12/9 |
| Adaptive | 80 → 142 | 64/80 → 91/141 | 16 → 25 | 101 → 113 | 1/0 → 12/11 |

Pooled full-cycle survivors rise **227 → 296**, durable parents **69 → 93**,
and final living plants **304 → 339**. But the eligible survival fraction falls
**61.5% → 55.8%**: opening space also admits more unsuccessful offspring. All
three policy fractions fall; these are different offspring cohorts, not a
matched per-seed survival intervention. Three 512-node offspring are too recent
for a full cycle of follow-up and are excluded from the eligible denominator.
Nonviable worlds remain original NN 3/16, veto/adaptive 0/16.

Paired full-cycle survivor gains / ties / losses across 16 worlds are NN
4/11/1, veto 13/3/0, adaptive 12/3/1. Adaptive durable parents gain in six,
tie in seven and regress in three worlds. Retained counterexample: rainfed
`e59eb9eb`, adaptive, has one more birth but one fewer full-cycle survivor
and two fewer durable parents. Extra storage is not a universal improvement.

The 25 late births occur in only **13/48 worlds**: one NN, seven veto and five
adaptive. All 12 adaptive late births and 11 deaths occur in the rainfed layout;
its crowded layout still has no late births or deaths. NN rainfed likewise has
none; its only late birth is crowded `b61837dc`. Veto late births/deaths split
7/6 rainfed and 5/3 crowded. Most gardens still settle.

Actual late-born *plant* cohorts, with one complete cycle of follow-up:
NN **1/1**, veto **7/10**, adaptive **2/11** survive that cycle. Three recent
births remain excluded. Thus the extra adaptive activity is mostly unsuccessful
replacement, not thriving new generations. These counts join germinated seed
`child_id`/`end_tick` to the node audit's death ledger; births must be after
61,440 and no later than 88,320, and death must be strictly after birth + 3,840.
Do not confuse these with newly qualified cumulative survivors (2/10/2), which
can include offspring born before the late window.

### The node ceiling disappears; mature-body and spatial limits remain

Every ecology-step census in the late window has at least four free nodes:
**zero node-full exposure and zero seed node-allocation blockers** in all 48
worlds. The larger cap is not merely being hit again within this horizon.

| Policy | Late mean live roots | Live shoots | Dead nodes | Free nodes | Endpoint living worlds with zero tips |
|---|---:|---:|---:|---:|---:|
| Original NN, living worlds only | 148.16 | 141.77 | 0 | 222.07 | 13/13 |
| Veto | 130.05 | 212.32 | 0.62 | 169.01 | 14/16 |
| Adaptive | 119.61 | 196.31 | 0.45 | 195.63 | 16/16 |

The NN row excludes its three extinct worlds from storage means, not from the
survival outcomes above. Endpoint living-world node counts range NN 252–368,
veto 266–440, adaptive 244–383. No dead plants remain at the endpoint. Whole-run
reclamation removes 386 plants / 13,465 nodes; observed delays are 51–64 ecology
steps. There is no unresolved removal ledger or storage leak.

**43 of 45 living endpoint worlds have no growth tips at all.** In the reference,
42 living worlds were full with tips remaining. The larger pool lets those
bodies continue toward their existing finite geometry, rather than indefinitely
filling more memory. This endpoint observation does not assign every lost tip
to a specific cause. Source review confirms that `FINISH_TIP` clears the tip;
an extension with no available position also clears it. The NN adapter enforces
finishing at maximum depth or with no available candidate, independently of its
learned action. Current autonomous actions cannot reopen a finished growth tip.
Leaves, water uptake and flowers can continue functioning afterwards; tipless
does not mean dead or infertile. No-tip gardens nevertheless have no growth
policy bids, so their controller is no longer actively managing mature tissue.

Late eight-plant-slot-full exposure increases (exact ecology-step exposure):
NN **50% → 64.89%**, veto **18.01% → 67.88%**, adaptive **0% → 37.50%**.
Endpoint eight-living-plant worlds are NN 11/13, veto 12/16, adaptive 6/16.
Plant capacity alone does not explain the remaining lack of renewal.

Late bright-day remaining mature-seed observations at 512 nodes:

| Policy | Observations | Spacing blocked | Light blocked | Water blocked | Plant-slot blocked | Node blocked |
|---|---:|---:|---:|---:|---:|---:|
| NN | 51,090 | 99.05% | 41.38% | 7.99% | 82.05% | 0% |
| Veto | 65,063 | 97.98% | 73.81% | 39.72% | 68.61% | 0% |
| Adaptive | 64,457 | 91.24% | 75.21% | 29.49% | 37.94% | 0% |

These are overlapping repeated observations, not probabilities. Node removal
does not remove spacing, shading, dry landing sites, or long-lived competitors.
Late-born *seed* germination with full potential seed-lifetime follow-up rises
NN **0/651 → 1/709**, veto **1/876 → 10/903**, adaptive **1/897 → 12/892**.
Of the 708/893/880 expired eligible seeds, only 36/48/108 ever have a reachable
open site in the recorded post-step worlds. An open-site observation is not a
promise the original landing site was open or the resulting plant would survive.

### Numeric and visual checks

All 24 predeclared frames match evaluator state and reproduce exact framebuffer
bytes on a second frozen replay. The gallery looks more developed but remains
mostly unchanged between the two late checkpoints. In the retained rainfed
`9c530b07` veto example, the endpoint gains a seventh plant and a fuller right
canopy: full-cycle offspring survivors rise 3 → 4, but durable parents stay zero
and late births stay zero. Its NN case is unchanged in birth/survival counts;
adaptive gains full-cycle survivors 9 → 11 and durable parents 5 → 7 while still
ending with six plants. Looks and final population do not substitute for the
lineage measurements.

Late mean soil water at 512 nodes is NN 24,841.11, veto 13,483.90, adaptive
14,530.59. No soil-cell saturation or clipped world-water summary was observed.
All **194,057 living plant-steps** in the six selected detailed traces reconcile
with zero water overflow; **61 terminal steps** remain explicitly unreconstructed
because death clears their income telemetry. These are selected-case checks,
not matched aggregate budgets across conditions. The unchanged resource-analysis
guard rejects saturated per-plant income rather than silently estimating it.

Validation:

- 27/27 normal CTests; eight focused large-build tests under UBSan; cross-build
  short-bundle/audit/gallery integration and early-state equality.
- All 32 header combinations (four host flags × firmware marker) accept/reject
  correctly. Wrong capacity labels fail even when early world hashes agree.
- Both full-horizon normal reports and both combined-256 reports are byte-exact
  against their frozen references after the shared-code changes.
- 48 full node ledgers / 294,960 world rows, 8,190 seed lifetimes and 77,436
  evaluator checkpoints per audit agree. Two selected node censuses, one seed
  census, one detailed trace and all 24 images independently replay exactly.

Frozen local artifacts (ignored, not published); manifest SHA-256:

| Bundle | SHA-256 |
|---|---|
| `artifacts/garden-capacity-512` | `9f7f03644db871f767b26e488a721c6bcd1e1f40f5431e05d4ed5de9482ff922` |
| `artifacts/garden-capacity-512-nodes` | `3c7e39742ec0b39820150f1131fc813fa9f145604d922a5572c65d177a55e26f` |
| `artifacts/garden-capacity-512-audit` | `b31e537359dc322e38cf9153667c310cd0d5c8b97342ba6153569bf41e1378f4` |
| `artifacts/garden-capacity-512-gallery` | `2c57f1e6363ac014ce654e6727a5f6366084069cb7b0d02968d8c277d0ee4ceb` |

Paired metrics: `artifacts/garden-capacity-comparison.json`. Exact soil and
selected budgets: `artifacts/garden-capacity-resources.json`, using the same
`soil_summary()` / `budgets()` recipe as the combined test, with the capacity
comparison's environment and combined reference passed explicitly.

## Interpretation and next discussion

256 nodes suppress useful growth and some establishment. 512 provides diagnostic
headroom, but also exposes a second endpoint: persistent mature bodies, exhausted
growth tips, crowded/shaded seed sites and finite plant slots. More memory alone
does not qualify the training environment, and these results do not justify
another capacity increase. Keep both experimental and device defaults unchanged.

Discuss mature-tissue control and turnover next: how a controller can continue
maintaining/replacing its body after growth tips finish, what creates a resource
cost or opportunity for replacement, and what creates space for offspring.
Resource-driven tissue renewal versus forced lifespan is an explicit ecology/API
decision, not an automatic follow-up implementation. Trace the termination
reasons before deciding which behavior should change.
