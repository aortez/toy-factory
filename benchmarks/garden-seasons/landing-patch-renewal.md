# Winter deaths and blocked recruitment after dieback

The only replacement born after day 320 dies from **energy shortage, not lack
of water**. Meanwhile, unused plant slots have three different explanations:
spacing leaves no valid gap, the world is already at its plant/node limits,
or the queued seeds cannot reach the available sites. Fixed seed-bank access
concentrates purchases among a few parents even when other plants are ready.

This audit follows the [day 352 observation extension](landing-patch-followup.md).
It covers all twelve saved histories during `(320,352]`, plus the complete
observed lives of S1 ordinary treatment plants 46, 47 and 48. S1, S2 and S3
retain seeds `3a7e45e6`, `366928c6` and `275c8982`; ordinary/crowded are the two
existing layouts. There are three weather seeds, not twelve independent
environmental trials. The W2 recipe, eight plant slots, eight seeds, 256 nodes,
32-node construction guard and finite dieback schedule are unchanged.

## Successive occupants of column 9 run short of energy

Plant 46 dies at day 334.781, aged 31.879 days. After its remains are reclaimed,
plant 48 germinates at day 336.891 in the same column. Its parent is plant 47
in column 1, not plant 46. Plant 48 dies at day 350.813, aged 13.922 days.
Neither occupant buys a seed during its lifetime.

Both reach 32 nodes, with 16 roots and eight active leaves. Their mature
energy upkeep is four units every maintenance step, or 256 units per full
Garden day. Their water upkeep is two units per maintenance step. Growth
and reproduction spending are both zero during the final winter decline.

| Plant and day | Opening energy | Income | Storage overflow | Upkeep paid | Closing energy |
| --- | ---: | ---: | ---: | ---: | ---: |
| 46, day 332 | 256 | 329 | 151 | 256 | 178 |
| 46, day 333 | 178 | 175 | 0 | 256 | 97 |
| 46, day 334 through death | 97 | 76 | 0 | 173 | 0 |
| 48, day 348 | 256 | 370 | 128 | 256 | 242 |
| 48, day 349 | 242 | 197 | 60 | 256 | 123 |
| 48, day 350 through death | 123 | 58 | 0 | 181 | 0 |

Each death follows eight consecutive energy-short maintenance payments.
Water remains at 512 immediately before the terminal payment; upkeep takes
two and death discards the remaining 510. The zero active-leaf count in the
terminal observation is a consequence of death, not evidence that leaf loss
preceded starvation. The last living observation for each still has eight
active leaves.

Plant 46 had survived an earlier, nonfatal six-payment energy shortage in
winter on day 318. Its eventual death is therefore not a first-day admission
failure. Plant 48 reaches the same aggregate body size quickly, then fails
in its first winter. The adult death mechanism is unpaid upkeep accumulating
stress; the separate cold flag blocks seed germination rather than directly
killing adults.

Parent 47 provides a useful within-world comparison: it also has 32 nodes,
16 roots and eight active leaves, but never incurs a shortage and buys three
seeds. On day 349 it collects 395 energy units versus plant 48's 197, while
both owe 256 upkeep. It ends that day with 242 energy rather than 123. Equal
node/leaf counts do not imply equal productive light exposure or traits.
These aggregate receipts establish the energy deficit and its timing; they
do not separate individual leaf shading from genetic or geometric differences.

## Empty capacity is not necessarily a usable landing

Each row below covers 8,192 ecology steps in `(320,352]`. “Clear columns”
means the three-column minimum base-spacing rule allows a new base there;
it ignores weather and global capacity. “Viable steps” counts steps where
at least one recorded seed check finds some column passing **all** site gates,
including light, moisture, cold and capacity. It does not mean a seed is
actually lying there. Seeds do not move after landing.

| Treatment | Living plants | Spacing-clear columns | Viable steps | Recruitment explanation |
| --- | --- | --- | ---: | --- |
| S1 ordinary | 5–6 | 22–27 throughout; 9 after reclamation | 2,504 | Queued parents cannot reach 22–27. A new seed reaches 9, but its child later starves. |
| S1 crowded | 8 | 27 | 0 | Plant and node capacity block germination. |
| S2 ordinary | 7 | 27 | 1,994 | None of the queued parents' recorded choices reaches 27. |
| S2 crowded | 8 | 24 | 0 | Plant capacity is full; the remaining node room is below a seedling's four-node requirement. |
| S3 ordinary | 7 | None | 0 | Base spacing covers every column despite one unused plant slot. |
| S3 crowded | 6 | 23–27 | 2,375 | None of the queued parents' recorded choices reaches those columns. |

S1 ordinary temporarily retains a dead slot: living/stored occupancy is
`6/6` for 7,347 steps, `5/6` for 126, and `5/5` for 719. Decomposition, not
the instant of death, releases column 9. Plant 46 is reclaimed at tick
1,286,505; plant 48 germinates at 1,293,660 and is reclaimed at 1,348,065.
The right-hand gap remains separate from that local replacement sequence.

Two older seeds from parent 47, already lying in columns 8 and 5, each have
135 mature checks when column 9 would be an allowed alternative. They stay
where they landed. The successful seed is a distinct purchase at tick
1,293,540, placed in column 9 and germinating eight ecology steps later.
All 270 reachable-alternative checks in the treatment panel concern column 9;
none reaches the unused right-hand gaps. An alternative passing today's
germination gates would still not guarantee sixteen-day survival.

The controls corroborate the distinction. Four are at eight plants throughout.
S2 crowded has seven plants but no spacing-clear column. S2 ordinary has
seven plants and an available column 27, viable on 1,789 steps, but none of
its queued parents can reach it. None has a new birth or death.

Across treatments there are 392,817 mature seed checks; controls have 392,832.
These are repeated observations of resident seeds, not independent seeds or
success trials. Spacing, light, moisture, cold and capacity flags can overlap.
The portable evidence retains complete masks and denominators, including
dormancy and expiry checks separately.

## Seed-bank ownership restricts which parents can try

The eight seeds present at day 320 in each history all expire without
germinating. Treatments buy 49 new seeds and controls buy 48; one treatment
seed germinates and all other new seeds remain pending at day 352. Thus seed
production continues, but neither seed purchases nor unused adult capacity
ensures recruitment.

In S3 crowded treatment, plants 31 and 39, at columns 5 and 0, buy six and
two new seeds respectively. The complete queued cohort's recorded dispersal
choices never go beyond column 14, while the open area begins at column 23.
Plants farther right receive no new seeds:

| Parent | Base column | New purchases | Eligible visits finding bank full on entry | Eligible visits losing to earlier buyers |
| --- | ---: | ---: | ---: | ---: |
| 35 | 14 | 0 | 718 | 6 |
| 37 | 17 | 0 | 663 | 3 |
| 38 | 20 | 0 | 677 | 3 |

“Eligible” here means every recorded reproduction gate except seed-bank
capacity passes. Losing to an earlier buyer means the bank had room when
reproduction began, but that room was taken before this parent's visit.
All eight release steps in this world end with a full bank again. The saved
ordered visits identify an allocation barrier, not merely missing flowers
or resource-poor parents. They do not prove that changing the buyer would
produce a surviving child.

The same concentration occurs in S1 ordinary treatment: plants 40 and 47
make all nine new purchases. Its complete queued cohort reaches at most
column 16, leaving columns 22–27 outside those parents' support. In S2
ordinary treatment, queued support reaches at most column 19, short of
column 27. This does not establish a reach limit for every living plant;
it describes the parents actually represented in the bank.

## Evidence and verification

The [offline auditor](../../sim/garden_landing_patch_renewal.py) and its
[twelve tests](../../sim/test_garden_landing_patch_renewal.py) authenticate the
day-352 capture and manifest, validate clocks and sequential seed admission,
reconcile ordered purchases, and balance the three focal plants' resource
budgets through birth, growth, reproduction and death. The
[tool guide](../../docs/garden-landing-tools.md#audit-winter-deaths-and-unfilled-space)
documents reproduction and verification.

The [portable evidence](landing-patch-renewal-results.json.gz) is about 7 MiB,
with SHA256 `be16ab16d0b784586ac9ccd34ad4f822f1f9bda4ada55d46b66b03fa3e9f89f7`.
It contains every tail queue and reproduction visit, actual purchase/support
witnesses, all three focal resource histories, derived accounts and source
identities. No raw trace duplicate or new source archive is created.
Original captures, manifests and compressed traces remain unchanged.

All twelve tests pass, including reproducible gzip output, omitted or reordered
observations, changed off-column gates, sequential birth census, terminal
resource conservation and existing-output rejection. Portable analysis and
compressed-trace re-extraction run with process launches forbidden. No native
simulation, training, firmware change or rule promotion belongs to this audit.

## Next proposal

Test **seed-bank access**, keeping the current resource costs, dispersal
limits, weather and memory capacities fixed. A bounded host-only comparison
should ask whether giving currently excluded eligible parents purchasing
opportunities yields new offspring that survive sixteen days. More purchases
or more evenly shared purchases would not count as success by themselves.

The [earlier clock-based rotation](landing-order.md) improved some worlds but
regressed others; its [audit](landing-order-regressions.md) also found plants
that missed useful openings despite nearly equal time at each rank. Do not
silently reuse that policy as a qualified fix. Discuss a purchase-driven
round-robin cursor, advancement rules and a fixed comparison/follow-up window
before implementation. Preserve every history, mortality and species losses.

This experiment would address reachable but unseeded gaps, not promise to
repair worlds already full or completely covered by spacing. Continuing
environmental turnover remains a separate lever. Winter mortality need not
be removed merely because one local replacement fails; first establish
whether the environment gives other surviving lineages meaningful chances
to reproduce. No next intervention is implemented or predeclared here.
