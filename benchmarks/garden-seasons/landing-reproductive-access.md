# Late replacements are ready, but lack reproductive opportunities

The seven surviving late replacements are not stuck without flowers or water.
In the saved day-256–288 histories, they have **4,567 reproduction visits where
every prerequisite except seed-bank space passes**. Only two buy a seed. Both
seeds remain pending at day 288; every mature check is blocked by plant capacity
and spacing. Readiness, seed-bank access and successful recruitment are distinct
constraints here.

This completes the [frozen offline audit](landing-reproductive-access-protocol.md)
of the [day-288 follow-up](landing-followup.md). It uses the same seven identities
in five worlds, retaining all 32 primary worlds as context. The configurations
share one weather seed, not 32 independent environmental replicates. No native
simulation, training, ecology, firmware or evaluation-gate change was made.

## Readiness versus actual access

Each plant has 8,192 ecology observations and 992 daylight production-cadence
visits. Ready flowers are present on 6,906 of the combined 6,944 cadence/daylight
visits. Two young plants initially have no flower; both become ready at tick
983235, about 0.051 days after the boundary. Every focal plant reaches its
32-node construction limit within 0.21 days of the boundary. The two purchasers
briefly have spent flowers after producing; no focal sample has an immature flower.

| Existing configuration / plant | Eligible except bank | Bank full at entry | Earlier buyers fill opening | Purchases |
|---|---:|---:|---:|---:|
| Fixed, dawn, focal allocation, wide+wick / 30 | 647 | 645 | 2 | 0 |
| Fixed, dawn, ordinary allocation, wide / 33 | 659 | 656 | 3 | 0 |
| Fixed, dawn, ordinary allocation, wide / 34 | 627 | 624 | 3 | 0 |
| Rotating, dawn, focal allocation, wide / 33 | 692 | 689 | 2 | 1 |
| Rotating, dawn, ordinary allocation, wide / 33 | 649 | 645 | 4 | 0 |
| Rotating, dawn, ordinary allocation, wide / 34 | 627 | 623 | 4 | 0 |
| Rotating, daylight, focal allocation, wide+wick / 30 | 666 | 662 | 3 | 1 |
| **Total** | **4,567** | **4,544** | **21** | **2** |

“Wide” is the existing broader-dispersal capped-uptake arm; “wick” adds the
existing wicking rule. “Focal allocation” names the earlier root-allocation
probe, not a new intervention on these seven plants. All three access columns
partition the otherwise-eligible visits. The 21 losses are individual plant
visits at 14 distinct world/tick events, not 21 independent openings.

Energy falls below the recorded reproduction reserve on 2,341 of the 6,944
cadence/daylight visits. Some blockers overlap, so these are not exclusive
causal categories. Water never fails its reproduction threshold: the smallest
observed water margin is 365 units. Every seed purchase reconciles to exactly
48 energy and 24 water, and all seven full resource histories conserve their
stores from the boundary through the final step. Being eligible at an instant
does not prove an additional purchase would be safe for the parent.

All five focal worlds end **every** observed ecology step with eight banked
seeds. Their 40 old seeds expire during the window and 40 replacements are
purchased; only two belong to the focal cohort. Rotating traversal still has
missed openings. This records who bought first, not what would happen under
a different allocation schedule.

## The two seeds do not yet find room to establish

Both purchases occur at tick 1082820, day 281.984375. At the cutoff they are
only 6.015625 days old: **pending, not expired or proven unable to germinate**.
Each has seven dormant checks followed by 1,533 mature checks.

| Actual landing / parent | Plant-capacity blocked | Spacing blocked | Node-capacity blocked | Light blocked | Cold blocked | Moisture blocked |
|---|---:|---:|---:|---:|---:|---:|
| Column 18 / rotating dawn focal-wide plant 33 | 1,533 | 1,533 | 0 | 1,246 | 334 | 0 |
| Column 12 / rotating daylight focal-wide+wick plant 30 | 1,533 | 1,533 | 1,533 | 1,371 | 334 | 0 |

These are overlapping blocker counts, not additive shares. The broader-cap
seed has enough node capacity but still lacks a plant slot and adequate
spacing. The combined-rule seed lacks all three. Changing only seed-bank
allocation therefore does not remove the observed establishment barriers.
Nor would increasing only the plant limit remove the spacing and node limits.
Seeds remain at their purchased columns; alternative sites are not relocation
opportunities.

Across all 32 worlds, the audit reconciles 260 new purchases, 256 expiries and
four germinations. The bank occupies 2,097,149 of 2,097,152 possible post-step
slot samples. Seeds aged 16–under-32 days account for 1,048,372 occupied samples;
seeds whose parents are already dead account for 21,501. The focal plants'
two seeds account for 3,082. These describe residence, not a recommendation
to discard old seeds or shorten viability.

## Verification and retained evidence

The [portable evidence](landing-reproductive-access-results.json.gz), about
6.35 MiB, retains all ordered production visits, all seven resource/body
histories, their boundary anchors and both seeds' purchase and check records.
Reanalysis independently reconstructs blocker masks, fixed/rotating order,
bank conservation, seed ownership/ages, resource continuity and exact costs.

Raw extraction checks complete stand/adult/reach framing and clocks, climate,
all 2,097,149 extension seed attempts and all 260 purchase records. Adult and
reach checks must agree, including sequential changes after a germination.
The runtime/observer hashes refer to the captured source archive; verification
does not require future working-tree C files to stay frozen. Non-focal raw
seed-site maps are authenticated and checked during extraction, but are not
duplicated in the portable file. Rechecking those maps needs the raw bundle.

Sixteen regression tests cover cohorts, order, simultaneous gates, flower
states, debits, continuity, expiry, pending fates, sequential germination,
tampering and fresh-output protection. All four selected Docker CTests pass
(this audit, follow-up, bank access and seed spending). A second full raw extraction in Docker,
with subprocess launches forbidden, produces byte-identical portable output.
Commands are in the [tool guide](../../docs/garden-landing-tools.md#audit-late-replacements-reproductive-access).

| Artifact | SHA-256 |
|---|---|
| Frozen protocol | `e7aff6d00dd604d649703b5d78563b859b72ef95728ab190f4b9c69f4f2504f4` |
| Input follow-up | `b13ce089efa12b431f48a35499be93e7cf7af83a636006b2898b283762e12336` |
| Raw manifest | `4b544d137a9ec8f2da3afdfb4b23ee3a300422fb871e10a267527b2f7fcbb1df` |
| Portable audit | `1db7c619a4acd770e36dccfd108c8d75369c9dbcd3153b98273f51b6024b5f39` |

## Next decision: test response to one controlled vacancy

The saved extension contains no deaths or reclaimed plant slots. More seed
readiness alone cannot establish renewal in a full, static stand. A useful
next experiment is a **paired, host-only turnover diagnostic**: unchanged
control versus one predeclared older non-focal plant killed by a deterministic
harvest-like event, with ordinary decomposition retained. Keep weather, model,
seed inventory, viability, placement and all pool sizes unchanged. Track which
seeds use the resulting opportunity, whether a focal parent gains access, and
whether any replacement survives and reproduces—not just whether a birth occurs.
Unlike the earlier immediate-export diagnostic, this would retain the dead body
until normal reclamation. Removing a plant also changes shade and resource
competition, so this is a response-to-disturbance test, not capacity in isolation.

Freeze the event's timing, selection rule and follow-up before running it.
This would test the response to an opportunity, not justify routine harvesting,
stronger winter or a new default hazard. It is a proposal, not an experiment
performed here. The earlier 12/16 harm-screen failures remain unresolved and
no rule is promoted.

Follow-through: the [completed single-death comparison](landing-disturbance.md)
now tests this proposal with normal decomposition, five paired worlds and
exact repeat/observer checks. It separates one-time refill from lineage renewal.
