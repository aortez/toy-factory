# Plenty of zero-condition tissue; safe removability is still unknown

The [saved-trace audit](renewal-shedding-audit-protocol.md) finds a substantial
storage reservoir, but **does not justify automatic pruning**. At the control's
full 512-node endpoint, 146 living leaf nodes have condition zero; 110 have
remained at zero for at least one garden day. Their direct photosynthesis and
shade contributions are zero under the current formulas.

Those nodes are not necessarily detachable: a leaf-bearing node can also support
descendants, retain a growth tip or carry a flower. Furthermore, the same saved
control contains **268 full-day zero-condition episodes that later end in paid
renewal**. Zero condition is neither permanent death nor proof of uselessness.

No simulation rule, native source, model, capacity or device behavior changes.
There are **zero new native research calls**. This audits both arms of the
[full-pool comparison](renewal-full-pool.md), without promoting its negative
candidate or changing the prior qualification verdict.

## What is actually measured

The audit checks every saved ecology census, with separate post-boundary
`(69120,245760]` and closing `(184320,245760]` summaries. Both arms retain
512 nodes, eight seeds and the same sixteen-slot admission rule. One garden day
is 3,840 logic ticks; observations are 15 ticks apart.

`active_leaves` in the inspector counts **mature leaves**, regardless of
condition or available light. Neither `leaves - active_leaves`, nighttime zero
income nor a dry post-uptake root cell is an adequate dead-tissue measurement.
This audit instead reads the actual ordered `leaf.conditions` arrays.

In these unpruned native histories, living nodes only append, and whole-plant
compaction preserves survivors' order. A `(lineage, leaf ordinal)` therefore
identifies a leaf across compaction even though its global node index can change.
The audit checks each ordinal against wear, the scheduled renewal site, exact
restored/worn counters and fresh appended leaves. This identity rule would need
revision if arbitrary live-node removal were introduced.

The persistence interval is **observed post-step zero condition**. At death,
the last live observation ends the spell; cleared terminal resource fields are
not interpreted as live productivity. Endpoint spells remain censored. The
one-day interval is a fixed diagnostic, not a proposed deletion threshold.

## How much storage is represented?

| Saved endpoint | Control | Non-allocating candidate |
| --- | ---: | ---: |
| Living nodes / free nodes | 512 / 0 | 417 / 95 |
| Living roots / shoots | 171 / 341 | 165 / 252 |
| Dead nodes awaiting reclamation | 0 | 0 |
| Living zero-condition leaf nodes | **146** | **56** |
| Zero continuously observed for at least a day | **110** | **46** |
| Zero-condition nodes as share of occupied storage | 28.5% | 13.4% |
| Structurally safe removable count | **Unknown** | **Unknown** |

All endpoint zero-condition leaves belong to shrubs. The surviving flower 5
has none in either arm. Leaves, tips and flowers are overlapping node flags,
not independent allocations to add together.

Both arms first reach 512 nodes at tick **80,940**, with 86 zero-condition leaf
nodes, 67 already continuously zero for a day. At their first maximum-zero full
snapshot, tick **111,000**, both have 166 zero-condition nodes, including 146
in the full-day subset. The snapshot hashes differ, so equal counts do not mean
every private state or later outcome is identical.

| Post-boundary census measure | Control | Candidate |
| --- | ---: | ---: |
| Total checkpoints | 11,776 | 11,776 |
| Completely full checkpoints | 7,703 | 6,539 |
| Zero-condition leaf count at those full checkpoints | 51–166 | 73–166 |
| Checkpoints with fewer than four free nodes | 7,727 | 6,565 |
| Those checkpoints where the optimistic full-day-zero bound covers the shortfall | 7,727 | 6,565 |

The final row asks only: *if every such node could be removed, would the raw
node budget permit four seedling nodes?* It deliberately ignores topology,
flowers/tips, removal costs and competing claims on freed space. It is not a
count of rescued seeds or even safe pruning opportunities. These are post-step
samples, not earlier germination-rejection receipts. Moisture, spacing and
other establishment requirements remain separate.

The **guaranteed safe lower bound is zero**. The reported zero-node counts are
only upper bounds for shedding zero-condition leaf-bearing nodes, not upper
bounds for every conceivable body-recycling scheme.

## Zero leaves often recover

These are spells with at least one zero observation after the boundary, not
necessarily spells that begin after it. A leaf can contribute several spells.
The two trajectories are counted separately; shared-prefix leaves are not
independent experimental replicates.

| Observed zero-condition spells | Control | Candidate |
| --- | ---: | ---: |
| Spells / distinct leaf identities | 756 / 456 | 734 / 432 |
| End in renewal | 425 | 462 |
| End with the owner's death | 185 | 216 |
| Still zero at the endpoint | 146 | 56 |
| Spells lasting at least one observed day | 529 | 518 |
| Full-day spells that subsequently renew | **268** | **287** |

This is direct evidence against labeling every prolonged zero leaf as disposable.
Renewal restores condition to 255; it is not a claim of positive photosynthesis
at that exact time, future survival or positive lifetime net energy. Deleting a
leaf that would otherwise renew changes the subsequent experiment. The longest
observed zero spell exceeds fifty garden days, but its structural role is not
exported, so duration alone does not establish safe removal either.

## Upkeep has steps, not a per-node continuous price

Native maintenance costs per payment are `ceil(plant_nodes / 8)` energy and
`ceil(plant_shoots / 8)` water. Bounds must be calculated per owner and then
summed. Removing one node can save a slot without changing upkeep; removing
one from a 17-node plant crosses an energy-price step, while one from a
16-node plant does not.

| Endpoint hypothetical removal | Control: energy / water price reduction | Candidate: energy / water price reduction |
| --- | ---: | ---: |
| All zero-condition leaf nodes, ignoring safety | 19 / 18 | 6 / 6 |
| Only the full-day-zero subset, ignoring safety | 15 / 13 | 5 / 6 |

These are optimistic instantaneous **price differences per maintenance event**,
not measured saved payments, daily resource totals or survival predictions.
Current total endpoint prices are 70/45 and 56/35 respectively. Any actual
removal policy would affect future observations, income, uptake, renewal,
reproduction and competition; this audit does not simulate those consequences.

## The missing information

| Existing evidence | What it establishes | What it cannot establish |
| --- | --- | --- |
| Per-plant counts and ordered leaf conditions | Ownership, zero-condition quantity, leaf-condition history | Parent links, children, leaf/flower/tip overlap |
| Sampled `leaf-bid` | One site's position, condition, light, resource eligibility | A complete branch graph or all leaves' light histories |
| Growth bids | Proposed actions at evaluated tips | A complete body, terminality of non-tip nodes, exact chosen child placement |
| Root cells | Root positions at cell resolution, depths and post-step moisture | Per-root uptake benefit or safe root-removal decisions |
| Screenshots | Visual appearance | Authoritative topology and controller references |

`TIP` is a growth-role flag, **not** a synonym for structural terminality.
The branch-pending path can leave a tip on a node that already has a child;
FINISH can clear a tip on a childless node. A spent flower is reusable at dawn,
not dead storage. Treat all of these roles independently.

## Safety contract before a removal primitive

The embedded-C review identified concrete requirements, not a ready deletion
implementation:

1. Start with a live, non-base **childless shoot node**. Derive childlessness
   from parent links and cross-check `child_count`; do not trust a tip flag.
   For a conservative first census, protect roots, flowers, active tips and
   pending branches, and count rejected candidates by overlapping reason.
2. Validate the entire operation before mutation. Parents must remain earlier
   in the dense array and belong to the same owner; no live child may retain a
   removed parent. No implicit reparenting, subtree cutting or forced regrowth.
3. Compact in stable order, shifting the parallel `leaf_condition` array too.
   Update global/per-owner node counts, the retained parent's child count,
   every plant's base and previous-tip indices, and clear the vacated tail.
   Swap-with-last is unsafe for the current parent-before-child invariant.
4. A removed previous-tip reference needs explicit semantics, not accidental
   aliasing to the next array element. Do not mutate while a callback/proposal
   borrows node references. Define the action phase and keep diagnostic receipts
   anchored to their original stage/identity rather than silently relabeling
   historical node indices after compaction.
5. Define cost, renewal-versus-shedding choice, future growth at the parent,
   observation changes and scheduling before changing ecology. No resource
   refund, persistence timer, additional device buffer or size quota is implied.

The existing whole-dead-plant compactor is useful reference code, but relies
on removing an entire owner: it never has to repair a retained parent's child
count. It cannot simply be called on a living leaf. `world_is_valid()` checks
parent ordering/ownership and counts, but does not recompute child counts;
a topology census should independently check them.

Also, the UI tool called **prune** merely sets `NODE_PRUNED` on a nearby shoot
tip. The baseline policy uses it as a directional hint and the neural encoder
exposes it as tip state. It does not delete, reclaim or universally stop growth.

Relevant reviewed code: [node representation](../../src/garden_world.h),
[validation, allocation, leaf wear/income, maintenance, reclamation and pruning](../../src/garden_world.c),
[exported census](../../sim/garden_inspect.c),
[growth-policy hints](../../src/garden_agent.c), and
[neural observations](../../src/garden_agent_neural.c).

## Verification and next step

- **8,738,097 leaf-ordinal transitions and 6,780 renewals** reconcile across the
  full saved histories. New analysis repeats exactly; independent Docker
  verification matches the portable output.
- Parent reanalysis reproduces both complete results and six existing images;
  all prior source/native/model/capture receipts remain intact. The only shared
  build change is the exact new Python-test registration. Historical verifiers
  keep their stricter historical-source requirements.
- **14 focused Python tests, 93/93 default CTests and 98/98 experimental CTests**
  pass. The initial audit correctly rejected an unmatched manual-export boundary;
  handling was corrected to respect the saved pre-export census and the one-step-
  later observed absence, with a regression test. No parent evidence was altered.
- No C/header changes, new native research runs, captures, model training,
  ecological qualification, defaults, firmware build/flash, commit or push.

[Portable summary](renewal-shedding-audit-summary.json), SHA-256
`59f1d44ff4b9870b8911337b3fc552ad2f254cde404e9475a418e3e6eb58cdc0`.
Parent manifest:
`c35c3ab8ec8479312e6bf2b14a9a78867a536b72693a5ce492cc6d64bd03a97a`.

Verification at the recorded audit revision, before the topology exporter:

```sh
docker compose run --rm -T --no-deps firmware python3 -W error \
  sim/garden_renewal_shedding_audit.py \
  --check benchmarks/garden-longevity/renewal-shedding-audit-summary.json
```

Use this wrapper for the audit checkout; `--output` requires a fresh destination
outside the immutable parent. It cannot run or recapture the simulator. Its strict
unchanged-native-source requirement intentionally rejects the later inspector
change. See the [topology follow-up](renewal-topology.md) for that revision's
verification command and the now-measured structural eligibility.

**Next proposal:** add a bounded, opt-in host **topology census**, not shedding
yet. Export parent links, owner/leaf ordinal, kind, flags, progress, child counts,
condition and plant references at fixed saved checkpoints; verify identical
physical hashes and derive the true eligible terminal-node count offline.
Use the original sixteen-slot control as the design baseline rather than silently
stacking the failed full-pool intervention. If safe removability is negligible,
do not expand into internal-stem contraction or root pruning without a separate
design discussion. If it is meaningful, discuss the local action and costs before
the next isolated experiment. Water limitations remain a separate problem.
