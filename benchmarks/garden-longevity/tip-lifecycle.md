# Tip termination and mature-body control investigation

## Fixed protocol

Follow the [node-capacity control](node-capacity.md) without changing mechanics.
Explain how active tips disappear, whether ending growth is a learned choice or
a geometric constraint, and how much living time passes without growth-policy
calls. Do not equate tipless with dead, infertile, or a frozen simulator.

Replay all 48 matched world identities in **each** combined-256 and combined-512
bundle: original NN, night-growth-veto NN and adaptive; eight weather seeds;
both layouts; 24 cycles / 92,160 ticks; final eight cycles as the late window.
Keep the same frozen model, weather, costs, capacities and policies as each
reference. No gardener, retraining, new action, lifespan, or firmware change.

Host bids now include observation-provided maximum depth, tip index, and a
diagnostic schema version. No simulation struct, hash, policy or observation
contract changes. `garden_node_audit.py --tips --inspector ...` reuses the node
collector with a separately frozen diagnostic inspector and retains bid rows.
Normal node audits still use their input bundle's frozen inspector.

`garden_tip_audit.py` counts only committed winners: maximum priority, first
offered on ties. It checks the existing action counters/last-winner fields and
the actual node/tip delta. A losing FINISH bid is not a terminated tip. The
per-world ledger is:

`initial tips + newborn tips + branch tips − terminations − death-cleared tips = final tips`

Separate termination observations into depth limit, no available growth
candidate, and policy FINISH with an available candidate. Depth takes precedence;
retain boundary and own/foreign proximity flags even when they overlap. These
are conditions at execution, not raw neural logits or alternate-policy outcomes.
In particular, the neural adapter can override the learned action before logging.
Trace actual exhaustion times and last decisions per lineage. Once tipless,
require no subsequent decision or spontaneous reactivation while alive. Retain
death-cleared tips separately and censor still-living tipless durations at the
horizon. Whole/late exposure holds post-step state over `[start,end)`; events
are counted in `(start,end]`.

Verify all evaluator checkpoints and compare the node ledger and every world
row against the prior node-only censuses. Selected frozen replays must reproduce
the new diagnostic bytes exactly. Keep existing screenshots as visual evidence:
this investigation must not change their worlds or pixels.

## Reproduce

Build the normal and two combined inspectors using the flags from
[node-capacity.md](node-capacity.md), then:

```sh
docker compose run --rm firmware python3 sim/garden_node_audit.py \
  --bundle artifacts/garden-water-wide-combined --output artifacts/garden-tips-256 \
  --tips --inspector artifacts/build-host-water-wide-combined/toy-factory-garden-inspect
docker compose run --rm firmware python3 sim/garden_node_audit.py \
  --bundle artifacts/garden-capacity-512 --output artifacts/garden-tips-512 \
  --tips --inspector artifacts/build-host-garden-512/toy-factory-garden-inspect
docker compose run --rm firmware python3 artifacts/garden-tips-512/tools/garden_node_audit.py \
  --verify artifacts/garden-tips-512 --case 02
```

Use fresh output paths; do not edit sources during collection. Both `--tips`
and `--inspector` are required together. The output freezes tools, source,
inspector, model, input reference and full traces; `analyses/NN.json` contains
`tips.terminations`, `tips.lineages`, totals and exposure windows. `summary.json`
adds policy aggregates without replacing the original node-ownership results.

## Design questions to resolve after measurement

- What should happen when a tip is temporarily obstructed versus permanently
  at its species/trait depth limit? Reopening every blocked tip could create
  costly retries without changing mature-body maintenance.
- The current controller is a growth controller: it is only invoked at active
  tips and is gated by affordability of growth. A future maintenance controller
  must still observe a tipless or resource-poor plant; action-specific validation
  must keep resource debits authoritative and failure atomic.
- Leaves and roots currently remain functional indefinitely while the plant
  lives. Existing upkeep and reproduction debits continue automatically. Adding
  tissue wear and a repair/replace choice is a new ecology, not a diagnostic fix.
- The gardener's current prune tool only marks an existing shoot tip; it does
  not remove a branch or free nodes. It is not an existing autonomous tissue
  replacement mechanism waiting to be exposed.
- Changes to controller inputs/actions require an explicit version/legacy-model
  story, deterministic selection and remapping of sites, bounded RAM/work, and
  checked energy/water/material accounting. Do not reinterpret old model outputs.
- Successful mature-body maintenance need not imply generational turnover.
  Plant slots, spacing, shading and opportunities for offspring remain separate
  acceptance checks. Do not add compulsory death merely to increase birth counts.

## Results

Completed locally on 2026-09-11, after checkpoint `4f26187`; additions remain
uncommitted/unpushed. No ecology, model, hash or firmware changes in this step.

### Finishing is constrained by geometry in every observed case

Committed tip terminations across 16 worlds per policy in each condition:

| Nodes | Policy | At depth limit | Below limit, no available candidate | Below limit, available continuation | Tips cleared by death |
|---|---|---:|---:|---:|---:|
| 256 | Original NN | 741 | 90 | 0 | 369 |
| 256 | Veto | 965 | 124 | 0 | 276 |
| 256 | Adaptive | 886 | 116 | 0 | 87 |
| 512 | Original NN | 1,030 | 156 | 0 | 395 |
| 512 | Veto | 1,494 | 277 | 0 | 441 |
| 512 | Adaptive | 1,268 | 206 | 0 | 236 |

At 512 nodes, **3,792/4,431 (85.6%)** occur at maximum depth and the other
**639/4,431 (14.4%)** have no available continuation. All are committed FINISH
actions; there are no failed extensions in these panels. There is no observed
voluntary finish below the depth limit with an available growth position. This
does not reveal the NN's raw pre-guard choice at a constrained tip, or prove
that another controller could not choose a different earlier body shape.

The 512 blocked-tip observations include an own-tissue proximity blocker in
632/639 events, a foreign-tissue blocker in 132/639, and out-of-bounds candidate
directions in 99/639. These overlap and are not counterfactual rescue counts.
No event has all directions out of bounds: at least one in-bounds candidate is
blocked by tissue. Removing another plant would not necessarily free every
blocked tip, and cannot relax the independent depth limit.

The species/trait depth caps are deliberate finite-geometry constraints, not
RAM limits. Every growth move is upward for shoots or downward for roots;
finished tissue has no autonomous reactivation action. Removing the caps or
retrying blocked growth would be a morphology change, not mature maintenance.

### Nearly all late living time has no controller work to do

Tipless exposure is measured in **living plant-steps**, not whole-world samples.
Extinct plants do not dilute the denominator. Late committed actions include
WAIT bids that win, not all inference calls offered by all tips.

| Policy | Late living time without tips, 256 → 512 | Late committed actions, 256 → 512 | Tipless / living endpoint plants at 512 |
|---|---:|---:|---:|
| Original NN | 82.83% → 99.94% | 0 → 59 | 102/102 |
| Veto | 62.54% → 98.58% | 30 → 2,123 | 122/124 |
| Adaptive | 73.36% → 99.34% | 10 → 788 | 113/113 |

The 256 condition also skips calls with tips present because its pool is full.
With 512, larger bodies can finish developing and then leave the growth-policy
interface entirely. There are no later policy calls or spontaneous tip
reactivations on any lineage after it becomes tipless. At the endpoint, 337/339
living plants and 43/45 living worlds are completely tipless. During the whole
late window, 31/45 living worlds have no committed calls at all (34/48 when the
three already extinct worlds are included).

Among tipless plants still alive at the endpoint, median age at last-tip
termination is NN **17 seconds**, veto **62 seconds**, adaptive **63.25 seconds**.
Median time subsequently alive without tips is roughly **21 minutes** in all
three policies. These are survivor-conditioned, horizon-censored durations,
not typical lifetimes of all germinated plants; failed seedlings remain in the
other lifetime analyses.

**7,631 of 8,190 seeds (93.2%)** in the 512 panel are produced by plants already
tipless at the previous ecology step. The corresponding 256 count is
6,842/7,995 (85.6%). Resource collection, automatic upkeep and renewable flowers
continue; "no policy calls" is not a simulation stall. Reproduction is automatic
and does not require a mature-body decision. Counts use the existing seed
cooldown transition, consistent with the resource audit, not new telemetry.

Concrete retained example: rainfed `9c530b07`, veto, 512 nodes. Its final seven
plants all lose their tips by tick **31,530** (8 minutes 45.5 seconds after reset).
There are no growth-policy decisions over the remaining **16 minutes 50.5 seconds**
of the run. It keeps its living canopy and continues seed production. Its
endpoint image is the unchanged frame 014 from the capacity gallery.

### Verification and provenance

- 28/28 normal CTests and the two-build capacity integration pass. The new
  synthetic tests cover first-wins ties, losing finish bids, branch creation,
  successful/failed extension, newborn growth, death clearing tips, censored
  tipless time, missing metadata, corruption and truncation.
- The two audits match **154,813 evaluator checkpoints** and all **96 node
  ledgers**. Every one of **589,920 world rows** is byte-identical to the prior
  frozen node-only censuses, including fields outside the state hash. Only the
  additional diagnostic bid metadata and retained analysis differ.
- Four independently repeated frozen audits reproduce exact trace and analysis
  bytes: 256 case 02; 512 cases 02, 18 and 34. Native renderer/world inputs remain
  unchanged; the previous verified screenshot galleries remain applicable.
- All dynamic traces/models/collectors are local ignored artifacts, not published
  evidence. Protocol and numeric findings are retained here in versioned notes.

| Bundle | Manifest SHA-256 |
|---|---|
| `artifacts/garden-tips-256` | `1373a85e369b3c5c0d0d840e9a6cbc189552e1e584998febaf15aa62ce10c01f` |
| `artifacts/garden-tips-512` | `85d58b34cfea25af568a3b166284a5633a9cb09280bf273890f78d4b2ff9f35d` |

## Conclusion

The current interface trains **construction decisions**, not continued mature
plant management. The observed finality is largely intentional species geometry
plus permanent living tissue and an active-tip-only controller interface. More
training cannot select a mature-body action that does not exist.

The next recommended experiment is [bounded leaf renewal](../../docs/garden-maintenance-proposal.md):
let mature plants make a resource-dependent decision to renew productive tissue
in place. Start with leaves and a scripted policy before expanding roots,
structural shedding/regrowth, or NN actions. This is a proposal, not an implemented
lifecycle change or evidence that turnover/qualification has been solved.
