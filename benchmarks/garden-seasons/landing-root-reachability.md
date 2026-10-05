# Root depth limits exclude the deep water reservoir

Both selected plants already reach the deepest soil row permitted by their
current root depth limits. Earlier direction choices cannot take them into the
next row, even in an optimistic calculation that ignores collisions, resource
costs and the body budget. The 89–92% of water previously found below their
roots is also below their maximum possible row, not merely below a poorly
chosen body.

The limitation extends beyond these two plants: the bottom two of eleven soil
rows cannot be reached by any currently allowed species/genome combination.
Those rows contain 54–59% of all remaining soil water in these saved worlds.
This identifies a constraint in the environment and body rules, not evidence
that changing soil physics would necessarily improve survival.

This [frozen audit](landing-root-reachability-protocol.md) follows the
[soil reconstruction](landing-soil-audit.md). It uses saved histories only:
zero new simulations, training runs, C changes, firmware builds or flashes.
All four order/guard cases and both allocation arms are retained.

## Segment depth does not equal soil depth

A seedling starts with two root endpoints five pixels below the soil surface,
at segment depth one. Each extension moves down five pixels diagonally or six
pixels vertically. Soil cells are eight pixels tall. Thus the optimistic
maximum penetration for a depth limit `D` is `5 + 6 * (D - 1)` pixels, not
`8 * D`. The existing neural controller forces a tip to finish at its limit,
independently of its learned action scores.

| Selected plant | Root segment limit | Actual deepest endpoint below surface | Optimistic deepest endpoint | Actual and maximum soil row |
| --- | ---: | ---: | ---: | ---: |
| Daylight lineage 16 | 9 | 49 pixels | 53 pixels | 6 |
| Dawn lineage 17 | 10 | 57 pixels | 59 pixels | 7 |

Rows are zero-based: row seven begins 56 pixels below the surface and row eight
begins at 64. Straighter paths could gain four or two pixels, respectively,
but not another soil row. Enumerating all in-bounds endpoints from both initial
roots, and from every recorded root bid, gives the same bound. No recorded
opportunity can reach a row deeper than the final actual roots.

Maximum root segment depth is the species baseline minus the genome's stature
trait. That trait ranges from minus two to plus two. Even the most permissive
ordinary combinations stop at these rows:

| Species | Largest allowed root segment limit | Deepest possible soil row |
| --- | ---: | ---: |
| Flower | 12 | 8 |
| Shrub | 11 | 8 |
| Ground cover | 9 | 6 |

The deepest possible flower endpoint is 71 pixels below the surface. Row nine
starts at 72 pixels; row ten starts at 80. Neither can host a root endpoint
under these rules. Uptake samples endpoint cells, not a radius below the tip.
Changing controller weights cannot bypass this forced termination; evolving
within the existing genome bounds still cannot reach those bottom two rows.

## The deepest tips stop before running out of resources

The audit reconstructs each root from birth through the shared-capacity anchor,
including every extension and closure. The resulting endpoint multiplicities
match every subsequent recorded uptake grid. Control and candidate have
identical root geometry in each guard comparison.

| Deepest tip closure | Tick | Body nodes before closure | Energy available and price | Water available and price |
| --- | ---: | ---: | --- | --- |
| Daylight control and candidate | 591420 | 29 of 32 | 252 available, 8 charged | 306 available, 5 charged |
| Dawn control | 591450 | 30 of 32 | 256 available, 9 charged | 396 available, 5 charged |
| Dawn candidate | 591450 | 30 of 32 | 256 available, 9 charged | 405 available, 5 charged |

Each closure is a maximum-depth finish, not a failed purchase or collision.
The current executor charges a finish action even though it adds no node.
All these expenses agree with the saved resource accounts.

By tick 591510, both bodies reach the 32-node limit: daylight has 15 roots and
17 shoot nodes, while dawn has 16 of each. Their second root remains an active
tip at segment depth six. The body budget blocks further construction there;
some later bids also fail energy guards. This can restrict coverage within
reachable rows, but relaxing that budget alone cannot take either root below
the plant's segment limit.

There is consequently no affordable deeper-row path to price in this panel:
geometry excludes it before affordability is considered. The audit does not
assume an altered path would preserve future income, competition, maintenance
or collision clearance. Existing shallow water might still be used better;
that is a different claim from accessing the deep reservoir.

## How much water lies outside the limits

These are post-uptake totals at tick 629760, the end of the preceding drying
window. Each below-limit stock is unchanged from its earlier shared-capacity
anchor.

| History | Total soil water | Below this plant's maximum row | In bottom two rows beyond every allowed genome | Share in bottom two rows |
| --- | ---: | ---: | ---: | ---: |
| Daylight control | 2227 | 1986 | 1193 | 53.6% |
| Daylight candidate | 2100 | 1923 | 1146 | 54.6% |
| Dawn control | 1936 | 1740 | 1134 | 58.6% |
| Dawn candidate | 2050 | 1833 | 1200 | 58.5% |

These row totals are not promises of accessible income. The optimistic
endpoint envelope contains only 29/27 water units for daylight and 57/27 for
dawn at this endpoint, across control/candidate. That envelope permits
mutually incompatible paths and ignores obstacles and costs; it is an upper
bound on spatial reach, not a body that could collect all of that water. Nor
does water present at this late snapshot prove that it was available during
earlier construction.

Combined with the absence of upward flow, the bottom-layer result explains why
whole-world water can remain high while these roots receive almost nothing.
It does not assign the control/candidate inflow difference to a particular
neighbor, or establish the first historical cause of depletion.

## Proposed next experiment

Controller-only changes cannot access this deep stock under the present
limits. I recommend discussing a small, host-only comparison of the existing
soil rules against **bounded upward water transfer**, conserving transferred
water rather than adding irrigation. Keep root geometry, genomes, body limits,
rain, reserve policies and controllers unchanged so the comparison isolates
transport.

The comparison should measure water by depth, actual root income and both
selected and whole-population survival/reproduction. A wetter shallow layer
alone is not a success criterion: we still want drought, competition and useful
rooting choices. Enlarging root depth limits is another possible experiment,
but would mix reach with construction costs and the existing body budget.
Neither experiment nor a default change is implemented here.

Follow-up: the [bounded late wicking comparison](landing-wicking.md) is now
complete. It improves supply and slightly extends selected lifetimes, but
passes none of the eight whole-population non-regression screens. The geometric
exclusion above remains valid; changing transport is not sufficient by itself.

## Reproduction and verification

`make host-audit-landing-root-reachability` performs the extraction and audit
without building or running a simulator. It requires the original allocation
bundle and the archived native source retained by the drying capture. Its
output must be fresh; prior files and symlinks are refused.

```sh
make host-audit-landing-root-reachability
docker compose run --rm -T firmware python3 sim/garden_landing_root_reachability.py \
  --verify benchmarks/garden-seasons/landing-root-reachability-results.json.gz
docker compose run --rm -T firmware python3 sim/garden_landing_root_reachability.py \
  --verify benchmarks/garden-seasons/landing-root-reachability-results.json.gz \
  --bundle artifacts/garden-landing-root-allocation-v1
```

The portable [results](landing-root-reachability-results.json.gz) are about
760 KiB. They retain 19160 selected body observations, all 15720 root bids
alongside the competing shoot bids, 116 paid root actions, geometric witnesses,
soil accounts, raw trace hashes and twelve exact archived source files. Raw
extraction checks complete trace framing and the hashes of primary and repeat
stand/direction files. Portable verification rechecks the pinned repository
input chain and independently rebuilds the root geometry and accounts without
launching a process.

Fixed and rotating root accounts duplicate after excluding lifetime metadata;
daylight lifetime seed counts differ and remain preserved. The duplicated root
histories are not independent replications. No general survival benefit is
inferred from the two selected plant pairs.

All 17 new tests pass, as do all five related CTest entries covering 75 Python
cases. Portable and raw-trace verification pass. Two independent final exports
are byte-identical. This is targeted offline validation, not a new full-suite
or firmware qualification.

| Artifact | SHA-256 |
| --- | --- |
| Root reachability results | `9ee2de6709856f1df93a6a4ae51f7029421ce03dce25162e0bb3a6c0f4f1011a` |
| Frozen protocol | `d91fe984fac5b09fdb742945622e83909ee0bdd73b44ee98f761fd743d193c68` |
| Unchanged soil audit input | `bd5066879c513a2d4af58773014d70d39da931584b40eafbe4f6d27d07898a55` |
