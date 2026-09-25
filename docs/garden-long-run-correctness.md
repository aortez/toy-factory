# Garden long-run age and terminal resource accounting

Follow-up to the merged foundation/research checkpoint in PR #31 and
[roadmap issue #30](https://github.com/aortez/toy-factory/issues/30).
This changes no resource prices, weather, reproduction, mortality or capacity
rules. It does not qualify the ecology or introduce a new training objective.

## Lifetime age

The authoritative plant age is now a saturating 32-bit ecology-step counter.
Crossing 65,535 no longer makes an old plant appear newborn or unestablished.
The counter still advances at the same point in the step: germinating seedlings
start at one, and plants dying during maintenance do not advance on that step.
Seed-bank age remains 16-bit; seeds expire at 256 steps, well before overflow.

The policy observation keeps its 104-byte layout and 16-bit age field, capped
at 65,535. Existing neural model files and policy interfaces are unchanged;
host plant exports carry the full age. At `UINT32_MAX` the authoritative age
saturates rather than wrapping. This does not remove the separate limits on
global tick counters, lineage IDs, or bounded experiment horizons.

Garden hash v5 retains its existing low age word. When any plant has a nonzero
high word, an `AGE1`-tagged extension hashes all plant high words in owner order.
Existing pre-wrap hashes are unchanged; different long ages remain represented.
This follows the existing optional state-extension convention. Archived runs
remain tied to their recorded sources; no historical evidence is rewritten.

Reordering the widened field uses existing padding: the default host plant
record remains 100 bytes, Garden world 4,352 bytes, and observation 104 bytes.
The pristine firmware build still links 222,996 bytes in the main RAM region
(85.40%), plus the separately reserved 8 KiB Core 1 region. This is linker
accounting, not a fresh device timing or stack-high-water measurement.

## Natural-death receipts

Death still clears live stores/income and starts ordinary decomposition. The
new host-only `picosystem_garden_world_step_death_audit` captures the final
resource transfers before that clear. It calls the same step implementation
and adds no authoritative fields, persistent history, callbacks in the world,
or firmware audit buffer.

The caller-owned output has at most one receipt per existing living plant.
Receipts identify the immutable lineage, not the compactable owner slot, and
record pre-step stores, exact income, overflow, upkeep due/paid, resources
discarded on death, pre-maintenance stress and terminal shortage flags. Income
is 16-bit here, so the normal saturated eight-bit income telemetry is not used
to reconstruct a terminal budget. Remaining water/energy is **discarded**, not
mislabelled as upkeep or a new soil refund.

The audit replaces output only on success, including an empty result on
non-ecology ticks. Output and world must not alias. As with ordinary stepping,
an internal simulation error need not roll back the world. The gardener must
be off. Only natural maintenance deaths are covered; forced patch/gap deaths
are separate interventions and are rejected by the new trace mode.

Example, keeping dependencies in Docker:

```sh
make host-build
mkdir -p artifacts
docker compose run --rm -T --no-deps firmware \
  build-host/toy-factory-garden-inspect - rainfed baseline 0x9c530b07 \
  --ticks 30720 --death-audit > artifacts/garden-deaths.jsonl
docker compose run --rm -T --no-deps firmware \
  python3 sim/garden_deaths.py artifacts/garden-deaths.jsonl
```

Every ecology world sample carries `death_audit_version: 1`; `death` records
precede the matching post-step world sample. The analyzer checks every natural
death against its previous living sample, maintenance arithmetic, stress,
shortage flags and death counters. Missing, duplicate or inconsistent receipts
fail analysis. Totals are **terminal-step totals only**, not whole-run budgets.
The legacy live-step/leaf experiment analyzers retain their historical behavior;
use this dedicated checker for the new receipt stream. It accepts plain or
gzip-compressed traces in both default and maintenance research builds.

The inspector without `--death-audit` keeps the original output. Tests compare
complete diagnostic-on/off traces after removing only the new receipts and
version marker, as well as comparing authoritative worlds byte-for-byte.

## Validation

Validation: `make check` passed (97 default host CTests, standalone checks and
pristine firmware build); `make host-research-check` passed all 102 CTests.
The native panel reconciled 15 default and 35 maintenance-build deaths with
unchanged control traces. Focused fixtures cover age boundaries/saturation,
both resource shortages, recovery, overflow, 300-unit income, multiple deaths,
owner compaction and invalid calls. No device was flashed for this change.

## Next ecology discussion

The next proposed route to freeing space is **environmental pressure**—winter,
another hazard, or resource scarcity—rather than a new controller pruning
action. Discuss a deterministic schedule and its survival/recovery tradeoffs
before implementing it. Seeds, adult survival and decomposition should all be
considered; a harsh event that merely empties the world is not evidence of
sustainable renewal. No seasonal/hazard rule is part of this fix.
