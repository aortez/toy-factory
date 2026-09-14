# Proposed mature-plant maintenance experiment

Status: **first host-only slice implemented and compared**, 2026-09-11. See the
[fixed protocol, results and native screenshots](../benchmarks/garden-longevity/leaf-maintenance.md).
The default ecology, firmware and neural model ABI are unchanged. The [tip audit](../benchmarks/garden-longevity/tip-lifecycle.md)
finds that the current policies construct finite bodies and then stop receiving
calls. With 512-node diagnostic headroom, roughly 99% of late living plant time
is tipless; leaves/roots keep working and flowers keep reproducing automatically.
The [A-life roadmap](garden-alife-roadmap.md) still requires meaningful ongoing
decisions and sustained descendant success, not merely long-lived founders.

## Recommended first slice: renew leaves in place

Introduce a slow, deterministic decline in **mature leaf condition** and one
paid action to renew a selected leaf at its existing node. Keep roots, geometry,
depth caps, plant slots, spacing, weather and reproduction unchanged initially.
Do not add an age deadline that forcibly kills a healthy plant.

The intended tradeoff is concrete: spend finite energy/water on a well-lit leaf,
save reserves for the night or offspring, or stop investing in a shaded leaf.
An ignored canopy gradually loses productive area; if income no longer covers
existing upkeep, the existing shortage/stress/death/decomposition path applies.
Healthy maintenance can extend life; death is not the reward for successful
maintenance. This is a hypothesis to test, not a guarantee of useful behavior.

Renewal should not allocate a node, free a branch, reset plant age, change ancestry,
restore seedling starting resources, clear a flower's spent flag, or produce a
seed. In-place renewal is intentionally smaller than structural remodeling and
can work even when the node pool is full. It does **not** solve spatial crowding
by itself. A successful adult may still occupy a plant slot indefinitely.

Use consistent physical semantics: leaf condition controls productive leaf area,
so declining condition reduces both light collection and foliage shading under
one documented integer rule. Other tissue/body costs remain explicit. Do not
silently reuse `growth_progress`: it already serves visible growth and corpse
decomposition timing, advances at a different cadence, and belongs in snapshots.

## Controller boundary

Separate **where/when a controller may observe** from **whether its chosen action
is affordable**. Current `grow_plants()` checks the generic growth cost and pool
space before calling a policy. That gate cannot govern maintenance: a tipless,
poor, or allocation-blocked plant must still be able to observe and WAIT, and a
full node pool must not forbid allocation-free renewal.

Extend the concept of an observation target from "active tip" to a typed site:
growth tip or mature leaf. Reuse body-relative position, local light, stores,
maintenance pressure and recurrent memory where appropriate; add leaf condition
and renewal cost explicitly. Do not disguise a mature leaf as a fake growth tip
or invent values for tip-only features. Keep fixed-size caller-owned inputs.

Bound candidate work and commit at most **one action per plant per ecology step**.
The existing step is 4 Hz; it need not move to the 60 Hz rendering/logic cadence.
Prototype a deterministic rotating mature-leaf sample alongside the growth
opportunities, rather than bidding every mature node on every step. Sampling
must progress even on WAIT and must not consume the ecology/weather RNG. Measure
whether sampling latency gives the controller adequate opportunity to maintain
the largest bodies before selecting a permanent bound.

Every proposal sees immutable observations and the same prior controller memory;
only the selected proposal commits memory and changes the world. Resource costs,
target validity and allocation needs are checked by the world for that action.
Insufficient resources must leave tissue/stores unchanged. Diagnostics distinguish
proposals, accepted actions, debits and actual condition changes.

## Compatibility and resource budget

The existing neural model has a fixed three-action head and versioned features.
Do not reinterpret its 1,204-byte payload as a controller that understands leaf
condition or renewal. First use an explicit scripted maintenance policy; later
version the observation/features/action head and model codec deliberately. Retain
the old growth model as a clearly labeled legacy/control path, not a supposedly
trained maintenance policy.

With the experimental mechanism disabled, preserve the old simulation, RNG use,
model behavior and hashes exactly. With it enabled, new condition state and
action semantics need an explicit environment/hash identity. The legacy policy
can be a "no renewal" control in that environment; its poor outcome would not
mean that old weights were corrupted or that maintenance learning failed.

A bounded side array with one condition byte per node would cost 256 bytes in
the default world, or 512 in the larger diagnostic build. This is a design
estimate, not a measured complete implementation. Adding one byte directly to
the current ten-byte aligned node may introduce padding. Include site-selection
state, snapshot/render/cache effects, stack work and any extra telemetry in the
actual RAM/CPU measurement; do not quote the condition array as total cost.

Condition must initialize on allocation/reset, follow nodes through compaction,
and have explicit dead/non-leaf values. No heap, hidden global world state or
per-lineage unbounded history belongs on the device. Keep detailed traces on the
host. Do not promote the 512-node condition to firmware as part of this work.

## Experiment order and acceptance checks

1. **Controller access:** prove a bounded maintenance observation is offered to
   living tipless/resource-poor plants, even with a full node pool. Keep ecology
   unchanged while testing scheduling, immutable bids and action validation.
2. **One lifecycle mechanism:** add leaf condition and paid renewal in an
   explicit host-only environment. Fix wear cadence, renewal cost and recovery
   timing from measured existing leaf income/upkeep, declare them before the
   comparison, and keep reproduction/geometry/capacities unchanged.
3. **Scripted controls:** compare no renewal, indiscriminate renewal, and a
   light/condition/reserve-aware rule on matched worlds. Add controlled light,
   shade and water cases so "always renew everything" is not assumed to be a
   meaningful task. Inspect numeric budgets and native screenshots over time.
4. **Then decide:** only extend the NN/model format or add root/structural
   renewal after ongoing decisions have measurable value without accounting
   exploits. Repeat the useful condition at 256 nodes and measure device costs
   before any deployment/default change.

Checks must include exact wear/debit accounting, failed-action atomicity,
deterministic replay, node-remap/reset boundaries, valid dead-state behavior,
consistent shading and snapshot ownership, and unchanged legacy controls.
Run beyond a single wear/recovery period. Report mature maintenance activity,
resource margins and stressed/failed plants, plus the existing eligible offspring,
durable parent, extinction and late-renewal measures. Saving one adult is not
equivalent to an ecosystem supporting continued generations.

This first slice deliberately postpones root turnover, selective branch shedding,
new buds/reorientation, nutrient recycling, and compulsory lifespan. They may be
useful later, but changing them together would obscure what leaf maintenance
actually contributes. The linked protocol declares the first wear rate, renewal
cost, sampling/precedence rule and reserve heuristic; none is a qualified default.
The comparison establishes a useful adult-maintenance action, not a superior
selective policy or a completed sustainable-ecology milestone.
