# Reciprocal founder-controller swap protocol

Accepted after the [startup trace](renewal-startup.md), before collecting swap
outcomes. This is a causal controller intervention on one inspected world, not
held-out qualification, a reward/ecology change, or a training run.

## Fixed four cases

Keep world `0d983a80`, eight garden days (30,720 logic ticks), review-1 patch
schedule `05d87ca0` (first event is day 16), and the exact existing ecology:
512 nodes, eight plants/seeds, rainfed-crowded, wide dispersal, headroom uptake,
selective leaf maintenance, nighttime-growth veto, no drainage or gardener.

Use saved R2 N3 `01b9d94a` and W3 `c9ea07fd`. Starting from reset:

| Case | Founder shrub 2 | Every other plant, including all descendants |
|---|---|---|
| n-in-n | N | N |
| w-in-n | W | N |
| n-in-w | N | W |
| w-in-w | W | W |

Route by stable founder lineage ID, never plant-slot position. No inherited
controller routing: even children of the focal plant use the background model.
All proposals receive the ordinary plant-local observation and memory; routing
must not mutate world state, random streams, genomes, memory or arbitration.
Both models retain the same night veto and selective leaf policy.

## Implementation and checks

Add a small host-only policy adapter shared by inspector and native replayer.
Require reset-time founder existence, matching arbitration/leaf policy, explicit
focal model/ID, and rejection of conflicting diagnostic overrides. Log selected
model CRC on every growth bid, and focal configuration on census/replay records.
Test error/alias boundaries, propagation, routing after compaction, noninheritance,
and input immutability. Firmware and shared simulation mechanics stay unchanged.

Pin startup bundle manifest
`301d0df74768bd4c1a8a3fbe2b26dbc2f5a10025c40c76dd213b0f7b5fbd3467`.
Rebuild only host tools in a separate matching ecology configuration with strict
warnings/UBSan. Compare shared native sources to the pinned archive. Both
same-model routed controls must reproduce **every** prior trace record after
removing only the declared routing metadata, plus all old frame results/bytes.
No outcome interpretation if those neutrality checks fail.

Each case gets two full ecology traces and four independently repeated native
frame replays, at days 0.25, 0.75, 2 and 8: **8 traces + 32 replays = 40 native
diagnostic calls**. Build/unit/CLI validation is separate from this fixed panel.
No extra world seeds, longer runs, mutations or training. Seal commands, timings
and raw results before analysis; retain any failure without automatic reruns.

Reconcile all live resource/leaf/tip accounting using the startup analyzer.
Keep terminal-step income explicitly unreconstructed because death clears it.
Record focal survival, shortage/stress timing, second-sunset reserves, upkeep,
root/shoot geometry, decisions, offspring and whole-world day-eight census.
Compare both focal swaps against their same-background controls. Match only reset
founders across worlds; descendant IDs are not interchangeable.

## Interpretation and stopping rule

If changing only the focal controller changes its survival, that establishes an
effect in this fixed starting world with ecological feedback still permitted.
It does not prove a purely cell-autonomous mechanism: the focal plant can change
neighbors, which can in turn affect it. Opposite-background effects can differ.
Retain both reciprocal outcomes, controls and images, including adverse results.

Report the result and next bounded proposal. Do not add resource gates, prune
bodies, change plant size/storage, rescue the separately observed water-starved
seedling, alter fitness, train, promote defaults, deploy, commit or push here.
