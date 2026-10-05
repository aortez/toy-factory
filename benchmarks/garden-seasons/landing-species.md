# Construction-cap species and allocation audit

The cap changes **which species reproduce**, not just how cheaply the same
plants survive winter. Seasonal flower reproduction disappears, while ground
cover supplies most of the improved renewal. In steady weather, long-lived
founders keep occupying the planting space: four worlds produce seeds but no
offspring at all.

This is offline analysis of all twelve pairs from the
[32-node construction screen](landing-growth.md): six frozen controllers,
steady and seasonal weather, through day 192. Both arms retain water-eligible
arbitration. No new worlds, training, policy, scoring or device changes are
introduced. The original failed retention gates remain failed.

## Survival is not reproduction

All counts below are across the six seasonal worlds, over days 0–192. A seed
purchase is not a birth; a first-day survivor is not necessarily a reproducing
adult. Arrows mean uncapped → cap 32.

| Species | Seeds purchased | Offspring born | Offspring surviving their first day | Fresh late renewal confirmations |
| --- | ---: | ---: | ---: | ---: |
| Flower | 416 → 0 | 162 → 0 | 88 → 0 | 59 → 0 |
| Shrub | 0 → 48 | 0 → 17 | 0 → 9 | 0 → 7 |
| Ground cover | 7 → 399 | 5 → 219 | 0 → 128 | 0 → 100 |

The last column keeps the existing objective: qualifying confirmations in
days (62,190], including the confirmed nonfounder-parent requirement. It is
not the same cohort as the first-day column. The previously reported late
birth cohort still has 61 → 107 first-day survivors; the cap's 107 are seven
shrubs and 100 ground-cover plants. All uncapped late survivors are flowers.

Only founders can be matched individually across treatments. Their initial
identities and biology are equal; descendants have diverged ancestry, placement
and birth times and must not be paired by numerical ID.

- Uncapped seasonal shrubs (12 founders) and ground cover (six founders) all
  die before age one day. Capped ground-cover founders live about 39.5 days;
  capped shrubs live about 39.5–56.1 days.
- Capped seasonal flowers all live about 55.8–56.1 days, but none purchases a
  seed. Uncapped, three flower founders die before one day; eight die around
  day 56 and one around day 103.4. Nine purchase seeds.
- In steady weather, all 26 capped founders survive the entire 192-day
  horizon, versus six of 26 uncapped. Their actual eventual lifespans are
  unknown. Only two of ten capped flower founders purchase seeds in steady
  weather; none of those seeds germinates.

Thus the treatment already changes establishment and competition in the first
day. It is not an isolated adult winter-maintenance test. The archive does not
contain founder first-day resource receipts, so it cannot attribute those
early deaths to energy, water or particular rejected actions.

## Seedling allocation and longer survival

Exact-age, living-only bodies at age one day, across seasonal descendants:

| Arm / species | Observed bodies / births | Nodes | Roots | Active leaves | Energy / water due per payment |
| --- | ---: | ---: | ---: | ---: | ---: |
| Uncapped flower | 88 / 162 | 36–37 | 20–22 | 8 | 5 / 2 |
| Capped shrub | 9 / 17 | 32 | 7–18 | 13–24 | 4 / 2–4 |
| Capped ground cover | 128 / 219 | 32 | 3–16 | 14–28 | 4 / 2–4 |

Ranges are per plant, not averages. Maintenance demand is computed using the
existing rules: energy is ceil(nodes/8), water is ceil(above-ground nodes/8).
These are not amounts actually paid under shortage. The audit also retains
age-1/8-day bodies and reconciled first-day resource accounts. Dead plants do
not contribute morphology; same-step death leaf fields describe decomposition,
not productive foliage. Missing cohorts are not zero-valued bodies.

The seasonal comparison is strongly survivor- and species-conditioned. There
are no capped flower descendants or uncapped shrub descendants to compare;
all five uncapped ground-cover offspring die before day one. Do not read this
table as a within-species causal root/leaf allocation effect.

At the already-traced day-125 winter scene, all four uncapped adults are
flowers (36 nodes, 20 roots, eight active leaves); the three capped adults are
ground cover (32 nodes, 7–12 roots, 19–24 active leaves). Energy upkeep is
320 → 256 per plant per day, while water upkeep is 128 → 192–256. These adult
receipts confirm the energy/water tradeoff in that scene, but not a rescue of
the same individuals. The [original report](landing-growth.md) retains the
longer earlier drought gap as a counterexample.

Longer fixed-age survival also differs:

| Seasonal cohort | Alive at age 1 day | Alive at age 8 days | Alive at age 32 days |
| --- | ---: | ---: | ---: |
| Uncapped flower descendants | 88 / 162 | 82 / 161 | 54 / 150 |
| Capped shrub descendants | 9 / 17 | 9 / 17 | 5 / 17 |
| Capped ground-cover descendants | 128 / 219 | 123 / 217 | 9 / 173 |

Each denominator includes only births early enough for that entire age to be
observable by day 192, even when a later-born plant's early death is known.
Death exactly at the target age is failure. The excluded later births are
counted separately in the artifact. Birth-season exposure and ancestry differ:
these are descriptive cohorts, not matched survival probabilities. More late
renewal has not demonstrated uniformly longer descendant lifespans.

## Why four steady worlds stall

The single and multi /33 and /35 capped steady worlds each retain all five
founders, produce 48 seeds, lose 40 to expiry, and end with eight pending seeds.
They have zero births and zero deaths. All **1,561,760** recorded mature-seed
checks include the spacing blocker; none includes plant- or node-capacity
blockage. Light and moisture can be blocked at the same time, so this does
not prove spacing is the only restriction or that removing it would suffice.

There is real seed supply, but persistent occupancy prevents recruitment at
the recorded sites. The full seed bank is not evidence of missing seed
production. In the other two capped steady worlds, offspring do appear, but
the existing objective still awards zero late renewal credit in all 24 steady
periods. Environmental turnover and founder-independent renewal remain open.

## Next bounded question

Why do capped seasonal flowers live for roughly 56 days without producing a
single seed? Code review supplies a hypothesis, not the answer: the cap turns
allocating EXTEND into WAIT, not FINISH. Flowering requires finishing a stem
at a species-specific depth (flower 12, shrub 10, ground cover 8). The neural
adapter still prioritizes FINISH at maximum depth or when no site is available.
A still-extendable stem halted short of maturity might never flower.

The saved archive has no founder tip-depth/proposal or flowering/reproduction
gate receipts. Other explanations include resource eligibility and seed-bank
competition. The next proposed experiment is a bounded, matched founder
trace of construction and reproduction gates, covering successful uncapped
seed purchases and the corresponding capped history. Reuse existing audit
hooks where possible, preserve exact replay/observer parity, and trace before
trying a growth-policy change. Do not force flowering, enlarge the cap, alter
weather or retrain on the strength of the current correlation alone.

That [founder trace is now complete](landing-founders.md): all twelve capped
seasonal flower founders form no flower nodes through death. Eleven stop
below flowering depth and one reaches it without finishing; 763 reproduction
visits have no other blocker. The two fertile capped steady founders provide
counterexamples, finishing their shoots before exhausting the node budget.
No growth policy was changed to obtain these observations.

## Reproduction and checks

[`sim/garden_landing_species.py`](../../sim/garden_landing_species.py) pins the
input SHA, checks species inheritance and seed/child ledgers, reconciles
first-day budgets and the focused adult receipts, and recomputes all 24 score
histories. Species credit partitions sum to the unchanged objective. All
twelve worlds and three original baseline comparisons remain in the
[portable diagnosis](landing-species-results.json.gz), including the seasonal
multi /34 loss in total credit (1,146,195 → 785,580).

```sh
make host-audit-landing-species \
  GARDEN_LANDING_SPECIES_OUT=artifacts/new-species-audit.json.gz
docker compose run --rm -T firmware python3 -W error sim/garden_landing_species.py \
  --verify benchmarks/garden-seasons/landing-species-results.json.gz
```

Output is exclusive-create; verification is read-only. Seven unit tests cover
independent census and fixed-age counts, species/credit partitions, the saved
counterexamples, overlapping blockers, death/censor boundaries, corruption,
input identity, no-clobber and exact portable recomputation. Native execution
is forbidden by a mock during the analysis test.

All **156 ordinary host CTests pass** under UBSan (154.54 seconds), including
the existing construction/adult observer parity tests and the new offline
audit suite. The local log is `artifacts/garden-species-validation.log`.
`git diff --check` and the new Make target's help/dry-run checks pass.

- Frozen construction input SHA-256:
  `9027651cd3da4d8a9a8703ef7a78d4ecc351faef35ece5fe4f2ee43f5605d2da`.
- Species diagnosis SHA-256:
  `75b24238cf6d3bbf9bd303b0b6794fabafac3a6c0d955f7af6f09f7238d3ec49`.

This is reused exploratory evidence, not unseen validation or ecology
qualification. No firmware, model or training default is promoted.
