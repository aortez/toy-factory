# Placement changes renewal timing, not the late recruitment stall

The two apparent improvements in the [spacing-aware screen](landing-placement.md)
are **older offspring remaining inside the credit window**, not new generations
establishing in the final period. The two new regressions retain living adults
whose credit expired earlier. None of the four focal candidate worlds produces
a child or loses an established plant during days (158, 190].

Exact saved seed checks explain the continuing stall: every reachable choice
for every mature seed in those four candidates remains spacing-blocked. This
is a persistent-occupancy problem in these observed windows, not missing seeds
or a late wave of adult deaths. It does not establish that the stands persist
forever, or that removing an occupant would guarantee a successful replacement.

## Same credit rule, different birth dates

This offline audit retains all six seasonal worlds, both reserve-32 and
spacing-aware arms, and the original scores. The /35 worlds remain as checks
against an explanation fitted only to the changed /33 and /34 results.

| World | Reserve final-period credit | Spacing final-period credit | New births, reserve / spacing |
|---|---:|---:|---:|
| Single /33 | 0 | 50,595 | 0 / 0 |
| Multi /33 | 0 | 22,305 | 0 / 0 |
| Single /34 | 144,630 | 0 | 1 / 0 |
| Multi /34 | 14,715 | 0 | 0 / 0 |
| Single /35 | 0 | 0 | 0 / 0 |
| Multi /35 | 0 | 0 | 0 / 1 |

Credit is summed eligible living-plant logic ticks, not elapsed wall time.
Across all twelve final-period runs there are **zero first-day confirmations,
zero established-plant deaths and zero credit ticks lost to death**. All
positive credit is carried in from offspring born before day 158. Both new
seedlings in the table die before their first-day checkpoint.

The existing rule confirms an eligible child after one day, then credits it
for at most 32 more days. Credit therefore expires at birth + 33 days,
exclusive, even if the plant remains alive.

| Candidate world | Last contributing living child | Birth day | Credit expires |
|---|---|---:|---:|
| Single /33 | #22 | 138.180 | 171.180 |
| Multi /33 | #26 | 130.812 | 163.812 |
| Single /34 | #23 | 121.855 | 154.855 |
| Multi /34 | #24 | 105.949 | 138.949 |

These four plants survive through the recorded day-192 endpoint. The first two
contribute some credit in (158, 190]; the last two have already aged out before
it starts. Thus “closing a zero-credit period” was not equivalent to restoring
continuous renewal. The /33 candidates also return to zero credit before the
period ends.

Neither /33 contributing child came from a redirected seed or has a redirected
child in its ancestry. That does **not** make placement irrelevant: the first
changed purchases occur much earlier, on days 65.047 and 57.984, changing later
competition and observations. Only the purchase prefix through the first
changed landing is matched across arms. Later lineage numbers are not paired
individuals, and ancestry labels are not causal rescue counts.

## Space stays occupied while the bank turns over

The four focal spacing candidates retain five, five, five and six established
plants respectively, and an eight-seed bank throughout the final period.
Each has eight carry-in seeds that expire and eight new purchases still pending
at day 190. Those pending seeds are censored, not counted as future failures.

For those **64 seed episodes and 261,888 mature seed checks**:

- Every actual landing has the spacing blocker, with a recorded living-neighbor
  witness; 1,277 checks have spacing as their only failed gate.
- Every choice within each producing parent's original dispersal support is
  spacing-blocked at every mature check. All 64 seeds have no reachable
  spacing-clear alternative during the window.
- Neither plant-slot nor node-pool capacity blocks any actual landing check.
- Fully open sites elsewhere still occur, on 127–301 distinct ecology steps
  per world. Global space is not necessarily within a seed's parent-specific
  reach, and a planted seed cannot move to a different column.

The native masks establish reachable-site blockage. The living-neighbor
witnesses identify occupancy at the **actual landing**; they are not a complete
reconstruction of living versus retained dead tissue at every alternative.
Light, moisture and cold often fail simultaneously, so the counts do not prove
that removing spacing alone would rescue a seed.

Across all six seasonal candidates, 96 of 97 seed episodes have their entire
reachable support spacing-blocked at every mature check, versus 78 of 97 in
the reserved controls. These are different trajectories and seed cohorts,
not 18 matched seeds made worse. The extra accessible episode is multi /35's
new seedling, which does not establish.

## The two seedling exceptions remain resource failures

Reserve single /34 child #27 is born on day 172.125 and dies energy-short on
day 172.469. Spacing multi /35 child #29 is born on day 171.082 and dies
water-short on day 171.406. Neither expands beyond its initial roots during
its lifetime. Both reach 18 nodes, eight active leaves and two roots before
death; their saved first-day resource accounts reconcile exactly.

These exceptions matter: creating a germination opportunity is not the same
as funding establishment. The /34 regression is not explained by more final
period seedling deaths in the candidate—it has no births there at all.

## Reproduction and verification

The audit runs **no native worlds and no training**. It reuses the frozen
placement result and exact day-(158, 190] recruitment/reach rows extracted
from its checksummed local bundle. Full source clocks, headers, footers,
purchase inventories and hashes are checked during extraction. The portable
analysis checks native masks, same-step seed order, carry-in support,
first-day resource accounts, ancestry and unchanged renewal scores.

- [Portable diagnosis](landing-placement-turnover-results.json.gz), SHA-256
  `989a42a74e7a937f181b002e4660a440212d71c1f5538d073349c5b494d1bb7c`.
- [Exact seed/reach windows](landing-placement-turnover-windows.json.gz), SHA-256
  `4ed8be4e907713886297eba32c8967277b2557e3bd623115b58c0e77e01d0339`.
- Source result SHA-256
  `c94d1d8e466dd0e81b399cf7416f353cb5533cb1e8288d33f17719097ef7fa82`;
  local manifest SHA-256
  `f04e1d84db9b14e415ee13d17393aab4c91c682a85ec01c74779e44ff924a7e7`.

Twelve new tests cover exclusive credit/death boundaries, first-day failures,
right censoring, ancestry, prefix divergence, independent sampled credit and
blocker counts, preserved inputs, frozen counterexamples and byte-identical
no-clobber regeneration. The raw-window extraction also independently verifies
against the original local traces. All five selected CTest suites pass (new
audit, germination, turnover, renewal audit and sustained renewal), as do three
reach-window boundary tests. The host build is current and `git diff --check`
passes. No firmware or ecology default changes.

```sh
make host-audit-placement-turnover \
  GARDEN_LANDING_PLACEMENT_TURNOVER_OUT=artifacts/new-placement-turnover.json.gz
docker compose run --rm -T firmware python3 -W error sim/garden_landing_placement_turnover.py \
  --verify benchmarks/garden-seasons/landing-placement-turnover-results.json.gz
# Optional: re-extract/check against the original local raw bundle, without replay.
docker compose run --rm -T firmware python3 -W error sim/garden_landing_placement_turnover.py \
  --extract-from artifacts/garden-landing-placement-v1 \
  --verify benchmarks/garden-seasons/landing-placement-turnover-windows.json.gz
```

## Next proposal: distinguish a missing opening from failed recovery

Stop tuning placement on these reused worlds. Discuss a small, predeclared
**controlled-vacancy experiment**: one explicit occupant removal at a fixed
time, paired with an unchanged world, then follow recruitment, first-day
survival, reproduction by replacements and any renewed stall. Keep resource
costs, models, weather, seed lifetime and credit rules unchanged. Select
targets and follow-up before collecting results, including the /35 exception.

This would be an artificial diagnostic, not a proposed harvesting schedule,
automatic old-age death or device policy. Removing a plant changes shade,
uptake and competition as well as spacing, so it tests recovery after an
opening—not spacing in isolation. The
[older controlled-gap study](../garden-longevity/renewal-controlled-gap.md)
already showed one replacement followed by another stall under different
rules/models. The current question is whether these seasonal descendant
populations can do more than refill a single vacancy. No such intervention
has been implemented or run in this audit.

Follow-up: the [completed vacancy experiment](landing-vacancy.md) now tests
that proposal. It finds early establishment without reproduction by those
replacements, but also natural turnover in extended controls after day 192.
The lack of deaths in this audit's fixed window must not be extrapolated to
permanent occupancy.
