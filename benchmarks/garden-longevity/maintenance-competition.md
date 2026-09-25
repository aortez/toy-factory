# Maintenance: persistent adults and offspring opportunity

Protocol declared before the full census, 2026-09-11. This is a diagnostic of
the frozen [leaf-maintenance panel](leaf-maintenance.md), not another ecology.

## Questions and fixed scope

Use all eight seeds and both layouts for the **unchanged night-growth-veto
controller**, comparing none/all/selective maintenance at 256 and 512 nodes:
96 matched worlds. Other growth controllers are outside this diagnostic; do
not generalize the result to every policy or new environment.

- Are seeds scarce, or is the bank full while seeds expire?
- Where could a seed germinate: actual landing, parent-reachable columns, or
  anywhere? Separate overlapping moisture, light, spacing, plant-slot and
  four-free-node requirements. Report bright-day opportunities separately.
- How much pool space belongs to living versus dead tissue? Can nominally
  free plant slots still leave no usable planting column?
- Of late germinations, how many have a full day's possible follow-up, survive
  that day, and subsequently have a full-day-surviving child? Keep recent
  births censored and terminal shortages separate.
- Are maintained parents resource-poor, or retaining occupied sites? Record
  stores, stress, actual seed production and full-bank exposure. Do not infer
  exact pre-reproduction permission from post-step stores or flower counts.

Replay the **frozen inspectors and model**; use their existing world and
seed-site outputs. Compare every ecology-step hash between the two replays and
the final state against the saved evaluator. Reconcile seed identities,
germination/expiry, plant births/deaths, and live-step resource budgets. Freeze
analysis sources, input manifests, binaries, model, traces and results in a
new bundle; reject mixed provenance or changed source during collection.

Horizon: 24 days, 92,160 logic ticks. Late events in `(61,440,92,160]`;
opportunity/occupancy samples are completed-step snapshots in that interval.
Seed follow-up is 3,840 ticks; plant survival is alive at birth+3,840 (death
exactly there fails). Mature-seed blocker counts overlap and are **post-step
snapshots, not exact pre-germination attempts**. Clearing one/all selected bits
is an instantaneous upper bound, not a tested rule change. Parent-reachable
support is frozen at seed creation, not a new dispersal draw.

The old seed-site schema has no leaf-policy label. Bind it to this environment
through the recorded frozen executable/model/arguments and equality with every
explicitly labeled world hash; never accept it solely on its schema number.

Completed: 96 worlds, with 589,920 matching ecology-step hashes, 17,447 seeds
reconciled and 3,395,256 exact living-plant-step resource budgets. Another 1,891
terminal steps clear income/stores and are explicitly excluded from resource
reconstruction. All final hashes, counters and full-follow-up offspring totals
match the frozen evaluator panel. No tissue shedding, seed relocation, spacing relaxation,
forced adult death, reserve change, NN change, retraining or device deployment
was part of this investigation. The embedded-C review kept simulator mutation
and accounting boundaries intact; all new computation is in host-side analysis.

## Result: establishment, not seed scarcity, stops late renewal

Each row pools 16 matched worlds: eight seeds × two layouts. These are fixed
diagnostic seeds, not a newly held-out qualification set. `none` means leaves
still wear but are never renewed, **not** the old non-maintenance ecology.
The controller is the frozen neural model with the nighttime-growth veto;
leaf maintenance remains scripted, not learned.

Late events, days 16–24:

| Nodes | Renewal | Final living | Seeds produced | Seeds expired | Births / deaths | Worlds with no births |
|---|---|---:|---:|---:|---:|---:|
| 256 | none | 93 | 1,023 | 859 | 169 / 164 | 0/16 |
| 256 | all | 117 | 954 | 909 | 42 / 39 | 7/16 |
| 256 | selective | 105 | 1,008 | 1,008 | 0 / 0 | 16/16 |
| 512 | none | 81 | 967 | 769 | 202 / 197 | 1/16 |
| 512 | all | 118 | 1,003 | 954 | 46 / 39 | 7/16 |
| 512 | selective | 120 | 1,028 | 1,024 | 4 / 2 | 14/16 |

Selective renewal keeps adults alive and producing seeds, but those seeds
usually cannot establish. The bank is nonempty at every late snapshot and full
93.87% of the time at 256 nodes, 99.81% at 512. A full bank also prevents further
production; increasing reproduction or reducing its cost is not the first
problem to address here. These are system-wide findings, not a claim that every
individual can afford to reproduce.

Events above include seeds born before the late window. The following table
instead selects **seeds created after day 16 and at least one seed lifetime
before the endpoint**. Recent seeds remain censored, even if their outcomes are
already known.

| Nodes | Renewal | Eligible late seeds | Germinated | Expired | Expired: any site ever open | Expired: reachable site ever open |
|---|---|---:|---:|---:|---:|---:|
| 256 | none | 887 | 137 | 750 | 544 | 413 |
| 256 | all | 838 | 38 | 800 | 140 | 74 |
| 256 | selective | 882 | 0 | 882 | 0 | 0 |
| 512 | none | 845 | 168 | 677 | 631 | 394 |
| 512 | all | 877 | 39 | 838 | 231 | 126 |
| 512 | selective | 900 | 4 | 896 | 124 | 31 |

At 512 nodes, 772/896 expired selective seeds never had a legal column anywhere
in any sampled mature-seed state. Only 31/896 ever had a legal column within
their parent's dispersal support. Thus better landing selection might help some
seeds, but it cannot by itself open the occupied world. These are recorded
opportunities, not proof that an alternative landing would have survived.

## Extra memory moves the bottleneck

Each row has 32,768 completed late world snapshots. Percentages below are pooled
snapshot fractions, not independent trials or failure probabilities. The node
gate needs **four** free nodes for a seedling, not merely one.

| Nodes | Renewal | Node gate | All 8 plant slots occupied | Mean live / dead / free nodes |
|---|---|---:|---:|---:|
| 256 | none | 43.17% | 6.97% | 208.3 / 13.7 / 34.0 |
| 256 | all | 85.88% | 63.00% | 247.7 / 3.2 / 5.1 |
| 256 | selective | 100.00% | 12.50% | 256.0 / 0.0 / 0.0 |
| 512 | none | 0.00% | 4.48% | 207.6 / 14.8 / 289.5 |
| 512 | all | 0.00% | 54.83% | 266.1 / 3.3 / 242.5 |
| 512 | selective | 0.00% | 57.39% | 348.1 / 0.1 / 163.8 |

At 256, every selective garden's late pool is completely living tissue. Faster
corpse reclamation would free nothing. At 512 there is no node gate in any of
these modes, but selective gardens average only 6.66% of bright-day snapshots
with even one legal planting column. Living adults alone exclude **every**
column by the spacing rule in 38.56% of their bright-day snapshots. Nominal free
plant slots do not guarantee usable ground.

The blocker query checks all gates independently. These percentages describe
overlapping flags on **mature seeds at their actual landing columns during
bright daylight**:

| Nodes | Renewal | Seed observations | Moisture | Light | Plant slots | Nodes | Spacing |
|---|---|---:|---:|---:|---:|---:|---:|
| 256 | selective | 64,456 | 24.74% | 43.12% | 11.09% | 100.00% | 90.07% |
| 512 | selective | 65,186 | 52.15% | 56.79% | 57.87% | 0.00% | 98.38% |

Removing one flag does not remove the others. The table below asks a narrower,
instantaneous question: in what fraction of the 9,088 bright-day world
snapshots would **at least one column** be legal after ignoring the indicated
gate(s), leaving everything else unchanged?

| Nodes | Renewal | Unchanged | Ignore node gate | Ignore plant-slot gate | Ignore spacing | Ignore all three space gates |
|---|---|---:|---:|---:|---:|---:|
| 256 | none | 40.07% | 63.27% | 40.28% | 41.68% | 73.16% |
| 256 | all | 9.74% | 19.17% | 10.42% | 11.16% | 87.24% |
| 256 | selective | 0.00% | 71.97% | 0.00% | 0.00% | 95.58% |
| 512 | none | 67.08% | 67.08% | 69.26% | 70.72% | 73.83% |
| 512 | all | 19.18% | 19.18% | 48.33% | 32.39% | 83.99% |
| 512 | selective | 6.66% | 6.66% | 36.29% | 22.91% | 68.16% |

The last column still requires moisture and light. At 512/selective those alone
leave the entire ground unsuitable in 31.84% of bright snapshots. More RAM,
more slots, softer spacing and more favorable landing are distinct hypotheses;
none of these static upper bounds is an implemented or validated solution.
Actual-site-open observations are almost absent because germination consumes
successful seeds before the observer runs; do not interpret that as the absence
of successful attempts. Outcome reconciliation records those births separately.

## A concrete, previously selected garden

The visual panel already used `rainfed / 9c530b07`, selected before this audit.
See its selective row in the [native screenshots](leaf-maintenance.md).

- **256 nodes:** six adults occupy all 256 nodes. Ignoring only the node gate
  would expose a legal column in all 568 late bright snapshots. There are two
  free plant slots, but not enough storage for a seedling.
- **512 nodes:** seven adults occupy 297 nodes, leaving 215 free. Their bases
  are columns `1, 4, 8, 12, 17, 22, 26`. Each excludes itself and ±2 columns;
  together they exclude all 28 columns. Ignoring only spacing would expose a
  legal column in all 568 late bright snapshots. There is one free plant slot.
- Both versions produce **64 late seeds, expire 64 and germinate none**. Their
  banks remain full. The 512-node adults finish with 240–251 energy and 502–510
  water, so this example is not a resource-starved parent population.

This example is not proof that spacing alone explains all worlds: the pooled
tables show plant-slot, light and moisture limits as well.

## Offspring survival and adult persistence

Late **plant births**, not seed creation, define this cohort. An eligible
offspring has at least one full day of possible follow-up. Surviving that day
does not imply being alive at the final endpoint. A durable parent additionally
has a child observed to survive its own first full day.

| Nodes | Renewal | Late births | Eligible | Full-day survivors | Also a durable parent | Recent alive / dead |
|---|---|---:|---:|---:|---:|---:|
| 256 | none | 169 | 141 | 121 | 42 | 22 / 6 |
| 256 | all | 42 | 41 | 32 | 7 | 1 / 0 |
| 256 | selective | 0 | 0 | 0 | 0 | 0 / 0 |
| 512 | none | 202 | 174 | 128 | 51 | 23 / 5 |
| 512 | all | 46 | 40 | 33 | 8 | 6 / 0 |
| 512 | selective | 4 | 4 | 3 | 0 | 0 / 0 |

The four 512/selective births occur in only two worlds. Three remain alive and
survive a day; two of them produce seeds, but none becomes a durable parent by
the endpoint. The fourth dies after 645 ticks (10.75 seconds), with a terminal
water-shortage flag. Exact terminal resource income is unavailable, and this
is too small a cohort to generalize seedling survival. Still, failure to
**germinate at all** is plainly the largest measured loss at this stage.

All 105 final adults at 256/selective were already at least a day old at the
start of the late window, and remain alive throughout it. At 512/selective,
116/120 final adults meet that criterion. The corresponding count is zero for
both no-renewal panels. No renewal obtains much of its turnover through adult
loss; that alone does not make it a better autonomous ecology.

Selective living-plant post-step stores average 178/511 energy/water at 256 and
165/509 at 512, versus caps of 256/512. Some individuals still have poor energy
margins: 6.47% and 10.64% of living snapshots fall below the bare 48-energy seed
cost, and 1.68%/4.48% have nonzero stress. Exact live-step accounting reconciles
renewal, growth, upkeep, seed costs and income. These averages neither imply
every parent is healthy nor reconstruct the stronger **pre-reproduction**
reserve/flower/daylight checks.

## Proposed next experiment: gap recovery, not a lifespan rule

Adult maintenance now does something useful, but there is no demonstrated path
to sustained succession in a small occupied world. Before adding actions,
changing spacing or training a larger neural controller, discuss a **host-only,
paired gap-recovery assay**:

1. Keep an untouched continuation of each selected world.
2. At a predeclared time, create one deterministic adult-sized gap in its paired
   copy. Define adult selection, tissue removal/decomposition, and any water
   release explicitly; do not quietly give seedlings free resources.
3. Keep the existing weather, model, renewal policy, dispersal rules and autonomous
   reproduction. Observe whether seeds naturally colonize the gap, survive and
   reproduce, then whether the world simply fills and stalls again.

That would distinguish an opportunity/recovery problem from a seedling-viability
problem without pretending maintenance itself should kill successful adults.
The intervention would be a diagnostic control, **not yet a permanent disturbance
or compulsory-age mechanic**, and would require a separate agreed protocol.
Leaf shedding alone cannot release the base-spacing reservation or a plant
slot. Environmental disturbance, competitive replacement and structural
remodeling remain design options, not conclusions established by this census.

## Reproduction and provenance

From the repository root, with the completed input bundles retained:

```sh
python3 sim/garden_leaf_competition.py \
  --bundle artifacts/garden-leaf-maintenance-256 \
  --output artifacts/garden-maintenance-competition-256 --jobs 2
python3 sim/garden_leaf_competition.py \
  --bundle artifacts/garden-leaf-maintenance-512 \
  --output artifacts/garden-maintenance-competition-512 --jobs 2
```

Outputs must be fresh directories, under ignored `artifacts/` or outside the
source tree. The runner verifies/copies the frozen inspector, model and cases,
records both exact commands per case, saves compressed world/seed-site traces,
and stores per-case ledgers plus machine-readable `summary.json`. It refuses a
mixed/incomplete veto panel, drifted final state, mismatched intermediate hash,
unreconciled outcome/budget or source changes during collection. It does not
rebuild or mutate the input bundles. Input provenance is from the preceding
experiment; the new source archive describes the **analysis**, not a claim that
the old executable was rebuilt from today's files.

Output manifest SHA-256:

- `artifacts/garden-maintenance-competition-256/manifest.json`:
  `e84ec3c4aec57f7de55e09c448dd24cc5ca61864132d403ca9d6e5667b50aa6a`
- `artifacts/garden-maintenance-competition-512/manifest.json`:
  `2f2b60e5f19b46e7e42803a225e84247a707d9557b52693c27c052b530761fbf`

Input manifest SHA-256:

- 256: `10d971c242f193a472a98d0c0b3b1b2c567a659d43d9e47099f821d03a40fdb8`
- 512: `e5ddb5ba301cf8e8159761542945b9bf900843e31942e8d80f0f59da0b51927a`

All 153 listed artifacts per output bundle were rehashed after completion.
Each copied inspector still matches the corresponding current maintenance
build byte-for-byte. Tests pass: **30 normal CTests, nine at 256 nodes, nine at
512 nodes**. New checks cover lifetime-boundary death/censoring, overlapping
spatial gates, native trace/report agreement, and rejection of wrong hashes,
policy/capacity labels, truncated traces and changed seed-production counts.

This completed report was written after the frozen collection snapshot. Raw
bundles remain local/ignored; the versioned protocol, tables and runner retain
the findings and reproduction instructions. No PicoSystem timing, firmware
deployment, training result or environment qualification is claimed.
