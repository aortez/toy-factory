# Long-run water balance

Protocol fixed 2026-09-12, following the secondary soil-wetting observation in
[the 192-day disturbance panel](disturbance-longevity.md). This is an accounting
audit of those existing trajectories, not a new ecology or policy experiment.

Replay all 160 worlds: 16 starting worlds × control/four existing fresh schedules
× 256/512 host node pools, through 192 Garden days. Keep model `dc5e849d`, growth
veto, selective leaf renewal, weather, scattering, uptake and all schedules fixed.
No gardener, irrigation, training, age-counter fix, or firmware deployment.

Use caller-owned host-only inventories around the **actual shared step stages**:
rain, transport/evaporation, root uptake, decomposition, maintenance/death,
germination, growth/leaf renewal and reproduction. No duplicate water solver,
global observer, per-world storage field, or hash change. Validate every ecology
step's transfer directions and soil/plant stage invariants; reconcile daily
cumulative soil, plant and seed-account balances. Exported disturbance stores are
a separate debit, checked against the frozen event ledger. Setup water/stores are
the initial inventory, not recurring inputs.

Seeds have no explicit water field. A separately labeled 24-unit seed-bank
endowment can account for the 24 units debited at seed creation and the 24 units
given to a germinating seedling; expiry discards that notional endowment.
Germination additionally removes 12 units from soil. Do not count the 24-unit
conversion twice or call it new environmental rain. Upkeep and natural death are
one measured stage, as are growth and renewal; do not invent a finer split.

Compare the 32-day windows ending at days 64, 128 and 192. Retain actual soil
changes/rates, rain offered/deposited/runoff, evaporation, uptake and other
transfers, per-world distributions and daily soil-depth profiles. No binary
"equilibrium" cutoff chosen from results. A finite-horizon slowing trend is not
proof of an eventual equilibrium. Water in live-root cells and post-ecology dry
root/shortage exposures distinguish total stock from accessibility, without
claiming a causal explanation for species loss. Unique root cells are counted
once per sample; shortage flags are repeated living-plant samples, not independent
death risks. Exactly-full soil samples are post-step, not peak-during-rain maxima.

Require byte-identical worlds with audit on/off in unit tests; all daily hashes
must match the frozen prior panel. Freeze model, inputs, source, binary, commands,
build cache and analysis with completed SHA-256 manifests. Old screenshots already
represent these unchanged worlds; no new best-world or screenshot selection.

```sh
docker compose run --rm firmware cmake --build artifacts/build-host-leaves-256
python3 sim/garden_water_budget.py \
  --bundle artifacts/garden-disturbance-longevity-256 \
  --build artifacts/build-host-leaves-256 \
  --output artifacts/garden-water-budget-256 --jobs 4
```

Repeat with suffix `512`. Rebuild flags are the existing maintenance/combined
flags documented in [the earlier protocol](patch-disturbance.md#reproduction).
Use new output directories and do not edit sources during collection.

## Results

Completed all 160 unchanged trajectories. Every measured balance closes: this
is retained rainfall, not an unexplained source, overflow, or double-counted
seedling endowment. The environment is an open water budget, not a complete
water cycle. Some gardens approach a wet, runoff-limited state; others still
accumulate, or lose water, during the closing window. There is no uniform
equilibrium at day 192.

### Where the soil water goes

Mean **water units per Garden day**, over days 160–192. Control groups contain
16 worlds each; fresh-schedule groups contain 64. One Garden day is 64 simulated
seconds. Values are per-world means, rounded here; raw integer ledgers close
exactly before rounding.

| Nodes | Arm | Rain offered | Runoff | Evaporation | Root uptake | Germination soil cost | Net soil gain |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 256 | Control | 4,137.98 | 421.87 | 1,774.79 | 1,796.89 | 0.00 | +144.44 |
| 256 | Fresh schedules | 4,137.98 | 200.79 | 1,766.65 | 1,962.77 | 1.44 | +206.34 |
| 512 | Control | 4,137.98 | 84.20 | 1,552.51 | 2,366.85 | 0.09 | +134.34 |
| 512 | Fresh schedules | 4,137.98 | 108.57 | 1,457.54 | 2,486.57 | 2.55 | +82.75 |

`soil gain = offered rain − runoff − evaporation − uptake − germination cost`.
Redistribution preserves the soil total except for surface evaporation. There
is no lower-boundary drainage, upward vertical return, or decomposition-water
return in the current implementation. Sideways flow is bidirectional; vertical
flow is downward only and stops when the lower cell is sufficiently wet.

The evaporation ceiling is 1,792 units/day (28 surface cells × 64 maintenance
intervals). The 256-node gardens nearly reach it. At 512 nodes, roots consume
more water and the surface is more often dry, reducing actual evaporation.
The same frozen policy with additional tissue capacity changes plant demand:
disturbed root uptake is about 27% higher at 512 nodes. This is a capacity-mediated
outcome, not a changed climate or a newly learned strategy.

### Where plant water goes

The separate plant ledger measures upkeep/death and growth/renewal at their
existing combined stages. Root uptake is a soil-to-plant transfer, not itself
a loss from the whole garden. In the disturbed closing window:

| Nodes | Upkeep + natural-death loss/day | Growth + leaf renewal/day | Disturbance-store loss/day | Expired seed endowment/day |
| ---: | ---: | ---: | ---: | ---: |
| 256 | 1,514.84 | 207.45 | 55.58 | 186.23 |
| 512 | 1,968.47 | 264.98 | 62.84 | 188.50 |

Inventory changes in living plants and the seed bank complete this budget;
these rounded rows alone are not expected to equal root uptake. Reproduction
transfers 24 units to the notional seed account; successful germination transfers
24 back to a plant, and seed expiry removes them. The additional 12 soil units
per germination leave the system. Dead bodies return neither stored plant water
nor this spent water during decomposition. All these terms were checked, not
inferred as an unexplained residual. The 24-unit seed account is an analytical
representation, not a new stored resource or mechanic.

### Accumulation is slowing in some worlds, not finished everywhere

Mean soil gain per world during each preceding **32-day** window:

| Nodes | Arm | Ending day 64 | Ending day 128 | Ending day 192 |
| ---: | --- | ---: | ---: | ---: |
| 256 | Control | +13,733.9 | +7,848.6 | +4,622.1 |
| 256 | Fresh schedules | +11,073.2 | +4,904.3 | +6,603.0 |
| 512 | Control | +5,040.8 | +1,925.3 | +4,298.8 |
| 512 | Fresh schedules | +4,908.2 | +1,083.0 | +2,648.2 |

The last window offers somewhat more rain than the two earlier windows, and
disturbances also change demand. Do not extrapolate a constant filling slope
or claim equilibrium from a small endpoint change.

At 256 nodes, 50/64 disturbed worlds gain soil water in the closing window;
individual changes range from −4,985 to +19,921. At 512 nodes, 46/64 gain,
with a range of −12,414 to +19,997. Runoff occurs in 29/64 and 14/64 respectively
(controls: 13/16 and 5/16). The final soil totals and populations are identical
to the earlier panel, including the approximately 97%-full wettest soils.

### Is the water accessible?

The data do not support describing all accumulated water as trapped below
roots. Mean final water per live-root-occupied cell is 181.8/255 at 256 nodes
and 88.3/255 at 512; outside those cells the means are 191.5 and 100.5. These
are means of per-world cell means in the disturbed groups. Root-occupied cells
number 48.9 and 80.0 per world on average. Final surface-row means are 142.2
and 54.4, while bottom-row means are 194.8 and 110.8: deeper soil is wetter, but
the root zones are not universally dry.

During the closing window, the mean fraction of unique live-root-cell samples
that are empty **after** the ecology step is 0.559% at 256 nodes and 4.237% at
512. Empty cells may just have supplied a plant; this is not the same as failed
uptake or a water-shortage death.

Actual water-shortage flags occupy only 0.00676% and 0.05299% of living-plant
samples on average. Some shortage is observed in 6/64 and 29/64 disturbed worlds,
respectively; the largest per-world fractions are 0.159% and 0.301%. Controls
have none at 256 nodes, and a mean 0.00802% at 512. These are repeated post-step
flags among living plants, not independent observations or mortality hazards;
death-step plants are excluded. Water is therefore plentiful for most late
living-plant time in this panel, but not absent as a constraint everywhere.

The uint16 moisture summary is capped during a mean 40.23%/18.52% of closing
steps in disturbed worlds (controls 73.82%/26.23%). Actual cells and controller
local observations remain intact. Use the full cell total for long-run accounting,
not the capped display summary. Post-step fully saturated cells also occur between
the earlier report's daily snapshots, which had missed those times.

## Implications and next discussion

No water-accounting repair is indicated by this panel. The decision is about
environmental pressure: the current rain/uptake/loss rules often permit large
long-lived soil reserves, especially with the smaller tissue budget. Increasing
capacity alone changes demand substantially and does not remove all wet cases.

A small **host-only bottom-drainage A/B**, holding rain, controller, schedules
and all other mechanics fixed, is a reasonable next proposal if we want reserves
to leak away and water acquisition to remain useful. Predeclare a bounded rule
and assess dry cases, offspring survival and turnover alongside stock reduction;
making the picture less blue is not an acceptance criterion. Do not simply reduce
rainfall globally based on the wettest examples, or change rainfall and drainage
together in the first comparison. No drainage rule is implemented by this audit.

Separately, water accounting does not explain or resolve founder/species loss.
Choose whether preserving flower/shrub/ground-cover coexistence is a requirement
or whether inherited variety within a species is enough. There is no controller
weight evolution in these runs. The age-counter boundary near day 256 remains a
separate fix before extending the horizon; it was not crossed or changed here.

## Validation and evidence

- All 62 host CTests pass: 30 normal + 16 per experimental capacity. The initial
  test fixture attempted to use the deliberately disabled experimental trainer;
  it now exports the fixed reference model from the unit fixture, without training.
- Audited/ordinary worlds compare byte-for-byte at every step through 24 days at
  both capacities. Invalid/null/auto-gardener arguments preserve the audit output;
  non-ecology steps return zero observations. Full-cell transport/evaporation and
  firmware/default-build exclusion are tested. New C tools use strict conversion
  warnings and UBSan; changed C/header files pass the formatter.
- All 7,864,320 ecology steps satisfy the measured stage-transfer invariants;
  all 30,880 daily ledgers close, and their hashes match the frozen previous panel.
  Every scheduled environmental loss matches its frozen event record. All final
  actual soil sums match too. Screenshots from the prior panel therefore remain
  the applicable native visual evidence; no new screenshot selection was needed.
- Source/input fingerprints stayed unchanged during collection. Each completed
  bundle's 249 artifact hashes verifies. Raw ledgers retain exact integers;
  summaries retain per-world distributions, rather than only these rounded means.

Local ignored bundles (not published by these notes):

| Nodes | Bundle | Manifest SHA-256 |
| ---: | --- | --- |
| 256 | `artifacts/garden-water-budget-256` | `f500e6a5e19506bcc18f59affbee2f0799cf0ebe0ac96405765ec06fc0ed8838` |
| 512 | `artifacts/garden-water-budget-512` | `3111c2ac05f28382d5d36665c4078ebaa989d1eb6fc5cafec61dfc2d6d2ae726` |

Both freeze model, binary, build cache, prior analyses/manifest, commands, current
source archive, daily inventories and stage totals. The archived copy of this
report is the pre-result protocol. No commit, firmware flash, training run or
ecology promotion accompanies this investigation.
