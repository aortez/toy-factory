# What changes while a seed waits?

**Space often clears first; water and light align later.** A site's current
blocker and the final trigger for germination are different things. This audit
changes no simulation rules, controller inputs/actions or device behavior.

The [fixed protocol](seed-waits-protocol.md) follows all 3,576 purchases from the
[flower-site audit](flower-sites.md), on the same 64 saved trajectories through
day 128. It records 16,553,918 actual germination checks, excluding expiration
events (which do not check the site). Both origin arms, every world and the
weather/layout/controller/species partitions are retained. There are eight
shared weather replicates, not 64 independent environments.

## The 465 germinations that motivated this audit

In flower-origin worlds, 967 seeds were purchased when no soil column was
currently suitable. Of those seeds, 465 germinated, 342 expired and 160 remained
pending. The resulting 145 durable parents remain the previously measured
outcome, not a new result from changing a policy.

Here is the exact blocker mask on the check immediately before germination:

| Last remaining constraint(s) | Germinations |
| --- | ---: |
| Ground light only | 277 |
| Surface moisture only | 173 |
| Both moisture and light | 6 |
| Spacing only | 7 |
| Initial dormancy only | 2 |
| Total | 465 |

Thus 456/465 (98.1%) finish waiting at a water/light threshold crossing. That
does **not** mean space, winter or node storage were unimportant earlier.

| Constraint encountered before those births | Seeds affected | Median interval from last blocked check to germination |
| --- | ---: | ---: |
| Moisture | 465 | 8 ecology ticks (0.031 Garden days) |
| Light | 446 | 1 ecology tick (0.004 days) |
| Spacing | 345 | 314 ecology ticks (1.23 days) |
| Cold | 215 | 2,313 ecology ticks (9.04 days) |
| Node capacity | 115 | 891 ecology ticks (3.48 days) |
| Plant-slot capacity | 0 | — |

These are overlapping histories, not independent causes. The intervals start
at the **last blocked check**, one ecology tick before the observed clearance;
they are not the total duration of blockage. A seed can become blocked again
as neighbors establish, so only the final clearance precedes its birth.

The median total wait is 2,016 ecology ticks, or **7.875 Garden days**. The 90th
percentile is 23.89 days and the longest successful wait is 31.96 days, close to
the 32-day expiry boundary. Of the 465 births, 62 wait less than a day, 84 wait
1–4 days, 206 wait 4–16 days and 113 wait at least 16 days. This is genuinely a
seed-bank process, not just a brief delay before spawning a plant.

## What we can attribute

**Spacing:** all 345 successful seeds that encountered spacing blockage have
verified clearance events. The blocking plant IDs disappear from occupied
slots after their dead tissue decomposes. Death alone does not free spacing.
Only seven births happen immediately at that final spacing clearance; the rest
also need another suitable water/light opportunity. Reclaimed neighbors can be
parents or unrelated plants; the diagnostic does not assume ancestry.

**Water:** 179 births have moisture among their final blockers. In 178 of them,
the world deposits rain during that same ecology step; none coincides with a
plant reclamation. This is a strong temporal association, **not proof that the
new rain directly supplied that specific cell**. Transport, uptake and earlier
stored water also contribute. The remaining case crosses moisture 11→12 and
light 79→83 without contemporaneous rain or reclamation, after spacing cleared
219 ecology ticks earlier. Its resources were observed, not inferred from a
post-birth snapshot.

**Light:** 283 births have light among their final blockers. For 180, even the
unobstructed, climate-adjusted sun was previously below the germination
threshold. For 103, the sun was already bright enough but the ground remained
too shaded. That latter category does not isolate decomposing leaves: changing
solar angle/strength and changing canopy can all alter illumination. This audit
does not claim a count of births caused by disappearing shade.

**Winter:** 215 successful seeds encountered cold, but none germinated on the
first check after cold cleared. On these histories, subsequent constraints
still mattered. Winter also changes sunlight; its cold gate and dimming effect
must not be conflated. Zero final cold-triggered births does not establish that
removing winter would have no effect.

## Compare failures without treating pending seeds as failures

Among the 342 expired seeds in this initially world-closed cohort, 244 never
had an unblocked spacing check after dormancy. Across all their mature checks,
spacing blocks 97.48%, moisture 94.59% and light 76.73%. For the successful
cohort, those figures are 73.74%, 90.37% and 82.83%, respectively.

These are overlapping, residence-time-weighted check frequencies, **not causal
failure fractions**. Longer-waiting seeds contribute more checks. In particular,
one should not conclude from successful seeds' larger light-blocked fraction
that darkness helps. Pending seeds have their own separate summary and retain
their shorter observed age; they are never counted as expired.

The same broad final-trigger pattern appears in both layouts, both controllers
and every weather partition. In the entire flower-origin arm (839 births), the
last mask is light-only 466 times, moisture-only 283, both 8, spacing-only 18,
dormancy-only 61, dormancy+light 1, spacing+light 1 and spacing+moisture+light 1.
For base-origin worlds (1,009 births), those final masks are light-only 553,
moisture-only 351, both 16, spacing-only 7 and dormancy-only 82. This is
descriptive consistency, not an additional independent replication panel.

## Implication for the agent

Keep the distinction between **slow neighborhood opportunity** and **fast
resource windows**. Do not add an instantaneous “soil must be open now” release
veto: it would discard many seeds that later establish on these trajectories.
Nor does this justify unconditional drift, longer viability or extra capacity.

The next proposal is to design a small landing-neighborhood observation contract
for reproduction-aware growth before changing the neural ABI or release rules:

- Represent nearby occupied establishment space separately from local water
  and ground illumination. Tip clearance alone describes a different problem.
- Reuse the existing solar clock, local resource observations and policy memory;
  distinguish a periodic dark interval from persistently shaded ground.
- Consider a compact recent wet/light history at potential landing regions,
  rather than declaring currently dark or dry soil permanently unusable.

First specify the sampling location, timing, storage cost and what the agent can
actually sense. The audit's full-world plant IDs, future outcomes, exact RNG draw
and future weather are diagnostic evidence, not proposed observations. Whether
new signals improve durable reproduction still needs a controlled policy trial.

## Integrity, tests and reproduction

The embedded-C skill guided reuse of the existing bounded caller-owned observer.
Only the host collector gains a `--seed-waits` mode; neither the world step nor
the observer core changed. Version-1 production and version-2 flower-site output
remain byte-identical to the frozen binaries in both diagnostic builds.

All 2,097,216 ecology state hashes and creation counts match the saved originals.
Every check reconciles in sequential bank order with the old seed/offspring
ledger. Spacing includes unreclaimed dead slots and earlier same-step births;
stage inventories independently reconcile decomposition, germination, growth
and purchases. Every capture repeats byte-for-byte, and raw reanalysis exactly
reproduces all per-seed histories and summaries. World/storage sizes match the
prior builds. Original experiment artifacts were not overwritten.

Validation passes: nine Python checks with each paired build and the retained
portable evidence; native seed-observer full-world noninterference tests in
both builds; all 121 default and 121 older-research CTests. Focused portable
evidence and prior flower/origin regressions also pass after evidence installation.
No firmware build or flash was needed for this host-only collector addition.
No commit, push, training or default promotion was performed.

Build new `artifacts/build-host-seed-waits-{base,flower}` directories using the
previous origin experiment's flags: all research defaults OFF, wide scattering
ON in both and flower dispersal ON only in the flower arm. RelWithDebInfo,
sanitizers ON, player/profiling OFF. Build `toy-factory-garden-production-audit`,
`toy-factory-garden-capacity-test` and `toy-factory-garden-seed-audit-test`.

```sh
docker compose run --rm -T firmware python3 sim/garden_season_seed_waits.py collect \
  --out artifacts/garden-seasonal-seed-waits --jobs 4
docker compose run --rm -T firmware python3 sim/garden_season_seed_waits.py verify \
  --out artifacts/garden-seasonal-seed-waits --jobs 4
```

Collection requires a new output directory. Verification reanalyzes saved raw
traces without rerunning the simulation trajectories (the small storage-test
binary is still used for build verification). The origin bundle is the default
source of the unchanged full-world traces.

Portable [per-seed histories](seed-waits-histories.json.gz) retain every exact
mask interval, first/first-mature/terminal checks and spacing releases. The
[summary](seed-waits-summary.json) includes source/build/input hashes, all
partitions and per-world records' identities. Raw repeated traces stay in
ignored artifacts. SHA-256 identities:

- Decompressed history: `da5c93df965ab9516c1eeebf00619e3d8a782c2add23ba7f395e1a5b43036c9d`.
- Summary bytes: `5d089e00e11e180bb1cb18c7143a05e67c0db0c0bed9c440ac58d61f38b640c2`.
