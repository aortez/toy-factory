# Node saturation and incumbent deaths are separate problems

Read-only follow-up to the [eight-versus-sixteen plant-slot test](renewal-plant-slots.md),
under the [fixed audit protocol](renewal-node-pressure-protocol.md). No new research
simulation, model, image, parameter change or firmware deployment.

The larger admission limit unlocks reproduction, but moves pressure onto living
node storage. Its six incumbent deaths do not have one common explanation:
four fatal stress episodes start with water shortage and two with energy shortage.
The full-node growth gate is overbroad, but correcting it is not evidence of a
rescue for those incumbents.

## Who holds the nodes?

Both arms start the audited window at tick 69,120 with seven living plants and
379 nodes. The complete post-boundary node ledger is:

| Node accounting | Eight slots | Sixteen slots |
| --- | ---: | ---: |
| Starting nodes | 379 | 379 |
| Seedling allocations, four per birth | +8 | +108 |
| Later growth allocations | +106 | +856 |
| Whole-dead-plant reclamation | −64 | −831 |
| Endpoint nodes | **429** | **512** |

All 23 candidate post-boundary dead plants have been reclaimed by the endpoint.
The remaining 512 nodes are **171 roots and 341 shoots, all living**, owned by
11 plants. Ten descendants hold 476 nodes; surviving founder flower 5 holds 36.
Four plants retain a total of 14 tips; seven are tipless. All eleven have zero
stress at the endpoint. Leaves, flowers and tips are flags on nodes, not extra
allocations. Here "living" means owned by a living plant, not that every node
is productive: even a condition-zero leaf remains allocated. The saved
whole-plant reclamation path does not recycle such tissue from a living owner.

The candidate first fills the pool at tick 80,940 with ten living plants. There
are four uninterrupted full runs, totaling 7,703 of 11,776 post-change checkpoints
(65.4%). The final run starts at 230,220 and reaches the fixed 245,760 endpoint:
4.05 garden days. Its owner/node/tip inventory is unchanged at those two ends.
The last birth was 225,885 and the last death 228,780; neither extrapolate beyond
the saved horizon nor call this permanently stable.

Dead tissue is therefore not the endpoint bottleneck. Faster decomposition alone
cannot free any of those final nodes. More plant slots alone also cannot admit
a four-node seedling into that full pool.

## What actually stalls?

The audit follows the native order: reclamation, four-node seedling allocations,
then growth in dense plant-array order. Each preceding plant's allocation affects
the next plant's entry count. Every transition reconciles exactly.

The candidate is already full at seed-bank entry on **7,699** steps, not the
7,703 implied by blindly using post-step fullness. Four final allocations fill
the pool later in those steps. A post-step seed blocker is not an earlier
rejection receipt.

There are **17,001 live plant-steps** with a full pool at that plant's growth
entry, existing tips, sufficient immediate growth resources and no successful
leaf renewal. There are no saved growth bids on those steps. This is exposure,
not 17,001 rejected EXTEND requests: growth cooldown is not exported, and the
policy's hypothetical choice is unknown.

Code review explains the absence of bids: `grow_plants()` checks total node
capacity **before calling the growth policy**, suppressing WAIT and FINISH as
well as allocation. FINISH clears an existing tip and may mark an existing
shoot as flowering; it does not allocate a node. Leaf renewal is earlier and
remains available: **1,978 renewals succeed at full growth-entry occupancy**.
Reproduction and maintenance also continue; the simulation itself has not hung.

All seven incumbents' node counts remain unchanged throughout both post-boundary
histories. Six, including five of the eventual deaths, are already tipless at
the split. Shrub 7 retains three tips until death. Thus a blocked new growth
allocation is not the proximate explanation for the five tipless deaths.

## What preceded the six deaths?

For each candidate death, compare the same absolute 255 live ecology steps in
both arms: `(death−3840, death)`. Exclude the terminal step, whose income and
stores are cleared by death. All six final stress episodes comprise eight
consecutive maintenance failures, with stress rising from one to eight.

| Incumbent | Death tick | First shortage in fatal episode | Terminal shortage flags | Water income, control → candidate | Energy income, control → candidate |
| --- | ---: | --- | --- | ---: | ---: |
| Shrub 2 | 199,860 | Water | Water | 325 → 205 | 2,380 → 943 |
| Shrub 4 | 214,200 | Energy | Energy | 448 → 471 | 2,288 → 2,351 |
| Shrub 6 | 192,960 | Water | Water | 399 → 118 | 2,450 → 1,391 |
| Shrub 7 | 144,840 | Water | Energy | 485 → 143 | 2,715 → 2,655 |
| Shrub 9 | 206,520 | Energy | Energy | 360 → 459 | 2,004 → 1,889 |
| Shrub 12 | 194,760 | Water | Both | 429 → 266 | 1,895 → 641 |

**Do not classify the whole fatal episode from the last flags.** Shrub 7's water
payments fail first; energy then runs out, and its terminal water payment happens
to succeed. Shrub 12 similarly accumulates water stress before also exhausting
energy. Both are different from the energy-led deaths of 4 and 9.

### Water and leaf upkeep interact

The four water-led plants make **no seed purchases, growth payments or leaf
renewals** during their matched final day. Their water stores are already low
at its start, and recorded intake is below maintenance demand.

They encounter 27, 43, 5 and 53 sampled old, well-lit leaves respectively; every
one fails the selective-renewal policy's water-reserve threshold. This threshold
is stronger than merely being able to pay a renewal's five-water price. No
renewal is proposed, rather than a proposed renewal being rejected by the node
pool. The controls renew 10, 11, 10 and 2 leaves.

Light alone is not the explanation. For shrub 6, mean sampled light during
globally productive steps rises **107 → 127**, while sampled leaf condition falls
**119 → 63**. For shrub 12 the corresponding changes are **96 → 129** and
**65 → 18**. These are sampled means, not a whole-canopy light measurement;
exact whole-plant energy income is separately reconciled above. The records
support a water/renewal/leaf-condition feedback, not a claim that all income
loss is caused by shading.

Shrub 2 shares a root cell on 253 of these steps. Shrubs 6, 7 and 12 share none
with other living plants during their matched windows, despite receiving less
water. Root-cell overlap is not a complete water-competition metric: uptake and
soil transport history matter. These snapshots do not identify the neighbor
responsible for a deficit or prove that changing rainfall would improve renewal.

### The two energy-led deaths enter night with less reserve

Shrub 4 has slightly *more* daily energy income than its control but enters
sunset with **215 versus 226** energy; shrub 9 enters with **183 versus 232**.
The candidates buy three seeds each during the matched day, versus one and zero
in the controls. Their last purchases occur at phases 108 and 116, before the
zero-income interval. These are concrete expense/reserve differences, not a
counterfactual proof that cancelling one purchase would rescue either plant.
Existing guards do not guarantee adequate reserves for every subsequent night.

## Validation and evidence

- **23,552** consecutive post-boundary ownership transitions reconcile.
- **209,462** post-boundary live resource budgets reconcile; 24 terminal budgets
  remain explicitly unknown. Parent reanalysis also reproduces the previously
  verified full histories, seed lifetimes, outcomes and images.
- New analysis repeats identically; independent Docker/Python verification
  matches the portable output. The immutable parent and native sources remain
  unchanged. No native research executable is called by this audit.
- **15 focused Python tests**, **91/91 default CTests** and **95/95 experimental
  CTests** pass. Regression tests are separate from research captures.

[Portable summary](renewal-node-pressure-summary.json), SHA-256
`f9f90fc58ac6976ef9c4d62144a7067370fe09a713600e94768d9c376381f778`.
Parent manifest:
`1cec5406f4f595972fde3cfea355d9f8c6c712fb279112d81f8e0ec3a77e0d3b`.
The summary records analysis/native source hashes, ownership snapshots, full
intervals, per-plant exposure, incumbent histories, matched budgets, sampled
light, expense timestamps and final stress sequences.

Current-checkout reproduction, analysis only:

```sh
docker compose run --rm -T --no-deps firmware python3 -W error \
  sim/garden_renewal_node_pressure.py \
  --check benchmarks/garden-longevity/renewal-node-pressure-summary.json
```

Use this wrapper for the current checkout. It permits only this audit's exact
new CMake test registration against the frozen parent's source list; it does
not weaken historical verifiers. `--output` requires a fresh path outside the
parent bundle.

## Next proposal

First discuss a small, host-only **full-pool action A/B**: preserve the 512-node
limit, but let the controller choose non-allocating WAIT/FINISH actions while
still refusing an actual allocation when full. Do not force FINISH, add a size
quota or claim this will save tipless incumbents. Check action/expense/private
state semantics and whether retained tips can finish, then measure renewal and
retention under the same saved environment and horizon.

Live-tissue recycling/body adaptation and water availability are separate design
questions. Neither faster corpse removal nor a larger pool is justified as a
general solution by this audit. The parent's mixed result and failed retention
gates remain unchanged. No promotion, training, commit, push or device change.
