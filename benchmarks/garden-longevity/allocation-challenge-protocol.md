# Allocation challenge v1 — development cases, not a fitness function

Freeze this protocol before collecting new fork outcomes. The six cases are
deliberately selected from inspected root-bootstrap evidence, not held-out
validation. Do not claim independent trials or use this panel as a final test.

| Case | Frozen world | Root probe in history | Lineage | Birth tick | Purpose |
|---|---|---|---:|---:|---|
| wet-root-opportunity | c7f54e18.reserve.16 | off | 65 | 617805 | Recover missed wet-soil investment |
| rooted-water-baseline | b61837dc.neural.16 | on | 92 | 621480 | Continue balancing after first root |
| rooted-water-bank8 | b61837dc.reserve.8 | on | 66 | 625410 | Same failure with smaller seed bank |
| rooted-water-bank16 | b61837dc.reserve.16 | on | 68 | 636945 | More roots alone were insufficient |
| energy-tradeoff | c7f54e18.neural.8 | off | 38 | 618300 | Retain the known energy regression |
| established-control | c7f54e18.neural.8 | off | 39 | 626100 | First later full-day survivor; avoid damaging success |

Replay the frozen reference model and environment through birth minus 15 logic
ticks, then copy the entire pointer-free native world in memory. No serialization
ABI, water injection, reset, invented seedling or moved plant. Verify checkpoint
hash and an unchanged reference continuation against the frozen world trace.
Each arm starts from that same checkpoint, including weather, neighbors, RNGs,
soil, seed bank, model memory and diagnostics. The selected lineage does not yet
exist; the harness must confirm its ordinary birth at the declared tick.

Only the named seedling's growth policy changes. Neighbors and its descendants
retain the reference policy; mature-leaf renewal stays selective. This isolates
an individual allocation opportunity, not a whole-population policy deployment.
Neighbor *states* can diverge through ecological interaction. No descendant-ID
matching after divergence. Continue for eight days from birth, preserving fixed
patch disturbances; report patch death separately, not as natural starvation.

Controls: unchanged reference; wet-root bootstrap for the selected seedling;
always-WAIT growth; and the same saved neural model without the root override.
The last arm tests candidate-model loading/routing, not new training. All neural
arms keep their case's existing night/energy guard. WAIT is an intentionally
degenerate growth control, not an override of automatic metabolism or renewal.
An explicit candidate model can replace the same-model arm using the existing
feature/action ABI, without receiving case IDs, global world state or future
weather. Selectors are harness state only.

Report a vector, **not a scalar reward or pass/fail optimization target**:

- Natural death cause/time, fixed-patch death/time, horizon survival; strict
  survival beyond first dawn, one day and eight days. Include follow-up status.
- Actual root/shoot/finish/wait decisions, live-step resource income, growth,
  upkeep, renewal and seed spending; resource checks close exactly while alive.
  Terminal clearing is unaccounted, never interpreted as a resource debit.
- Active leaves, body size, energy/water reserves at milestones; seed production
  and actual germinated children. A seed is not a viable descendant.
- Full world hashes and population counters, matched checkpoint provenance,
  and native milestone screenshots. Rendering must not change world state.

Eight-day survival alone cannot distinguish a useful policy from indefinite
waiting; seed count alone can favor exhausting the parent. Do not pick weights
after observing control outcomes. Next discuss these controls and an objective
before any mutation search. Broader world-level and fresh-seed validation remain
necessary; this suite does not qualify the environment or promote a model.
