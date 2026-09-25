# Node ownership and reclamation audit

## Fixed protocol

Follow the [combined ecology experiment](combined-ecology.md) without another
mechanics change. Determine whether the 256-node pool is occupied by living
bodies or delayed reclamation, and whether freeing dead storage could remove
an otherwise isolated seedling allocation blocker.

Use every world in the same four frozen conditions: baseline, wide scattering,
capped uptake, and combined. Each has the unchanged model `dc5e849d`, three
policies, eight weather seeds, both rain-fed layouts and 24 cycles (92,160
logic ticks). Keep the final eight cycles as the late window. This is 48
matched world identities per condition, not 192 independent environments.
No training, firmware change, larger pool, new lifespan or pruning experiment.

`sim/garden_node_audit.py` reuses each bundle's **frozen inspector and model**.
It captures every ecology-step world row, omitting bid logs, and verifies all
existing evaluator checkpoints. No new C telemetry or world storage is needed.
The collector freezes the analysis code, commands, binaries, model, inputs,
world rows and per-trial results; refuses overwrite/test seeds; and supports
exact frozen replay. Do not edit sources during collection.

Measures:

- Disjoint ownership: live roots, live shoots, dead roots, dead shoots, free.
  Leaves/flowers/tips are overlapping flags, not extra objects in the pool.
- A per-lineage ledger reconciles every allocation and whole-plant removal.
  Living tissue cannot silently vanish; dead tissue cannot grow or revive.
- Observed death-to-removal delay; retain unfinished deaths as censored rather
  than incorrectly reporting a completed reclamation time.
- Whole/late occupancy exposure, shortage of four seedling nodes, and whether
  immediate removal of all dead storage would remove that node gate.
- Actual remaining mature seeds whose sole post-step blocker is node capacity,
  including those where dead-node reclamation alone would supply four slots.
- Endpoint per-plant body shape, growth tips and resource state.

Exposure uses state at tick `t` over `[t,t+15)`, with the endpoint excluded.
Means include extinct worlds; live-world denominators will also be reported
where useful. Node-only seed observations are repeated, survivor-biased and
post-step, not independent germination probabilities or an intervention.
Freeing dead storage hypothetically does not remove spacing/light blockers.

## Reproduce

```sh
make host-build
docker compose run --rm firmware ctest --test-dir build-host --output-on-failure

docker compose run --rm firmware python3 sim/garden_node_audit.py \
  --bundle artifacts/garden-water-control --output artifacts/garden-nodes-baseline
docker compose run --rm firmware python3 sim/garden_node_audit.py \
  --bundle artifacts/garden-dispersal-wide --output artifacts/garden-nodes-wide
docker compose run --rm firmware python3 sim/garden_node_audit.py \
  --bundle artifacts/garden-water-capped --output artifacts/garden-nodes-capped
docker compose run --rm firmware python3 sim/garden_node_audit.py \
  --bundle artifacts/garden-water-wide-combined --output artifacts/garden-nodes-combined

docker compose run --rm firmware python3 artifacts/garden-nodes-combined/tools/garden_node_audit.py \
  --verify artifacts/garden-nodes-combined --case 02
```

Use new output paths for repeats. `summary.json` contains summed per-policy
window exposures and case references; divide each exposure by its `steps` for
a mean. Each `analyses/NN.json` also retains the individual reclamation events,
endpoint plants and ledger. `--verify` without `--case` replays every case.

## Results

Completed locally on 2026-09-11, after checkpoint commit `4f26187` on
`green-garden`. The audit additions are not yet committed. Capacity, tissue
lifecycle, binaries, models and device state remain unchanged.

### The late combined pool contains living tissue, not a reclamation backlog

All **48 combined worlds have zero dead-node exposure throughout cycles 16–24**.
There are no pending dead plants at the endpoint. Faster corpse reclamation
therefore cannot free any storage in that observed late window.

Combined late mean allocation, conditioned on worlds having living plants:

| Policy | Worlds alive throughout late window | Live root nodes | Live shoot nodes | Dead nodes | Free slots |
|---|---:|---:|---:|---:|---:|
| Original NN | 13/16 | 130.62 | 124.69 | 0 | 0.69 |
| NN + night-growth veto | 16/16 | 96.09 | 159.86 | 0 | 0.05 |
| Adaptive | 16/16 | 100.25 | 155.65 | 0 | 0.11 |

The three extinct NN worlds are retained in the reports, not dropped from
survival results. Including them makes the NN mean free-slot count **48.56**,
which would misleadingly suggest spare capacity in its surviving gardens.
The roots/shoots split does not, by itself, show that either kind is wasted:
both belong to living plants and both participate in the resource model.

At the endpoint, all 16 veto and all 16 adaptive worlds have 256 living nodes
and at least one remaining growth tip. Ten NN worlds have that same condition;
its other living worlds have 252, 253 and 254 nodes, respectively, with no tips.
Seedlings require four nodes, so the latter two are allocation-blocked even
though the pool is not completely full.

### All four conditions: decomposition works, with little late storage cost

Mean **dead nodes** per world during the final eight cycles; all worlds included:

| Condition | NN | Veto | Adaptive |
|---|---:|---:|---:|
| Baseline | 0.360 | 0.198 | 0.127 |
| Wide only | 1.667 | 0.628 | 0.541 |
| Capped only | 0.132 | 0.076 | 0.106 |
| Combined | 0 | 0 | 0 |

These small time averages do not exclude short earlier bursts. Whole-run mean
dead-node occupancy in combined is 2.37 / 1.91 / 1.12 for NN / veto / adaptive.
In the whole combined run, 43 NN and 59 adaptive node-only seed observations
would gain four slots if dead storage vanished immediately; there are none in
the late window. These are repeated observations, not counts of rescued seeds.

Whole-horizon reclamation ledger:

| Condition | Removed plants | Reclaimed nodes | Dead plants still pending at endpoint |
|---|---:|---:|---:|
| Baseline | 376 | 12,098 | 0 |
| Wide only | 530 | 14,454 | 2 |
| Capped only | 253 | 9,302 | 0 |
| Combined | 257 | 8,947 | 0 |

Combined observed death-to-removal delay is **51–64 ecology steps**, or
**12.75–16 seconds**. Medians: NN 60 steps (15 seconds), veto 59 (14.75 seconds),
adaptive 57 (14.25 seconds). Across all four conditions the complete range is
51–65 steps (12.75–16.25 seconds). The two pending wide-only deaths are censored,
not counted as completed delays or leaks.

The source matches this behavior: `mark_plant_dead()` assigns a per-node
countdown of `48 + maximum_depth - node_depth`; `update_decomposition()` decrements
it each ecology step. `reclaim_plant()` compacts and remaps the complete plant's
nodes once every countdown is zero. Individual faded nodes retain slots until
that whole-plant removal. Within these frozen runs there is no orphaned-node,
unreconciled deletion, or persistent post-decomposition storage in the ledger.
This is not a claim about arbitrary future interventions or damaged worlds.

### Removing dead storage alone does not open the late combined node gate

Fraction of the late window with fewer than four free slots, averaged across
all worlds. Each cell is **observed / hypothetical after all dead nodes removed**:

| Condition | NN | Veto | Adaptive |
|---|---:|---:|---:|
| Baseline | 0% / 0% | 24.36% / 24.19% | 25.00% / 25.00% |
| Wide only | 1.84% / 1.67% | 62.50% / 62.50% | 66.44% / 66.07% |
| Capped only | 6.25% / 6.25% | 54.62% / 54.62% | 57.29% / 56.96% |
| Combined | 75.00% / 75.00% | 99.26% / 99.26% | 99.16% / 99.16% |

Combined has **1,457 / 4,004 / 2,213** late node-only mature-seed observations
for NN / veto / adaptive; **zero** of those would obtain four slots from dead
reclamation. These counts include twilight and use `[start,end)` samples;
they are not the prior bright-day-only seed-audit counts. Only nine late
adaptive observations in wide-only satisfy this instantaneous storage-only
relaxation; none in the other policy/condition pairs. Removing a corpse could
also change spacing or light over time, which this frozen-state calculation
does not model. Earlier interventions could change later trajectories.

### Capacity also prevents controller decisions

`grow_plants()` checks `world->node_count >= PICOSYSTEM_GARDEN_MAX_NODES` before
calling either policy arbitration path. When full, it skips that plant even
if it has live tips and sufficient resources. It also skips under insufficient
resources or a growth cooldown; the audit does not attribute every skipped
decision to capacity. Maintenance, light, rain and reproduction continue.

The combined full-pool-with-live-tips exposure is 62.50% / 99.26% / 99.14% for
NN / veto / adaptive, using all worlds. The NN numerator only covers ten of its
13 living worlds. This is a storage ceiling affecting the policy's opportunity
to act, not evidence that a controller actively chose to stop growing.

Concrete rainfed `9c530b07` veto endpoint (case 02):

| Lineage | Species | Nodes | Roots | Remaining tips | Energy / water |
|---|---|---:|---:|---:|---:|
| 1 | Flower | 36 | 20 | 0 | 251 / 510 |
| 2 | Shrub | 55 | 18 | 0 | 249 / 507 |
| 3 | Ground-cover | 54 | 14 | 0 | 249 / 507 |
| 8 | Flower | 36 | 20 | 0 | 251 / 510 |
| 9 | Shrub | 55 | 18 | 0 | 249 / 507 |
| 11 | Ground-cover | 20 | 11 | 6 | 253 / 510 |

All 256 nodes belong to living plants. The young ground-cover has six tips and
ample stores, but the global gate prevents further decisions. The previous
gallery already shows this exact world; the node audit changes no pixels.
In contrast, the original NN at that seed has seven mature 36-node flowers:
252 nodes, zero tips and four free slots. Allocation alone therefore cannot
explain every quiet garden; spatial seed opportunities remain relevant.

## Validation and evidence

- All 25 normal CTests pass, including the new node-audit unit/integration checks
  with frozen replay. Cases cover ledger arithmetic, disjoint ownership,
  window boundaries, zero-state aggregation, pending deaths, missing/corrupt
  rows, lineage reuse/revival, changed identities, overwrite prevention,
  source-bundle preservation and test-seed rejection.
- 192 censuses contain **1,179,840 world rows**. All **309,756 evaluator
  checkpoints** match: baseline 77,459; wide 77,559; capped 77,361; combined 77,377.
- The four audit inputs have matching seeds, models, settings and 48 world
  identities, with the declared environmental differences. Their saved files
  pass artifact-hash checks. Every observed allocation/removal reconciles.
- Frozen replay independently reproduces case 02 in baseline/capped/combined
  and case 35 in wide-only, including the latter's pending death, with exact
  world-row bytes and identical analysis output.
- The audit uses existing binary output; no new C instrumentation, firmware
  RAM allocation, model change or device deployment. New local artifacts total
  approximately 135 MiB and remain ignored, not published.

Audit manifest SHA-256:

| Condition | SHA-256 |
|---|---|
| Baseline | `577a071ea25df7367a539c72ce3b21f76b29685331010eba211080d61cd26c9d` |
| Wide only | `08393e2fa624ba1b550511d97261367397cde0a5a00a6d318ff4dd2e8f99ce6a` |
| Capped only | `f46f8a7ebe0da52d5b35cb8532d1d3702039fc4c2ce1dc545eabb68f11f1b64c` |
| Combined | `57a09ab4a82b322cad711bf5b50c4933300df94bc29d74a0bfae6128c1ae590c` |

## Decision and next discussion

Do **not** optimize decomposition to solve the combined late-run stop: there
is no dead storage there to recover. This is living-body occupancy under a
finite shared pool, alongside real spacing/shade constraints.

A useful next controlled test would be a **host-only larger-pool control**
(for example 256 versus 512 nodes), keeping bodies/costs/weather/policies fixed,
to see whether it restores durable renewal or merely postpones saturation.
This is a diagnostic proposal, not a device capacity increase or approval to
implement it now. It first requires auditing the one-byte reclamation remap
and capacity assumptions in snapshots/diagnostic tools; changing a macro alone
is unsafe. If healthy mature bodies just fill the larger pool, then discuss
bounded living-tissue turnover or body budgets as deliberate ecological rules.
Do not infer that reducing roots, forcing deaths, or retraining around this cap
is justified by occupancy counts alone. Qualification remains open.
