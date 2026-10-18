# Reduced lateral flow limits water supply to the matched plants

The saved grids account for the missing water without another simulation.
Both arms receive the same rain, but the candidate plants receive **35 and 79
fewer water units through sideways flow**, plus 11 and 6 fewer through downward
flow. Overflow and evaporation explain the difference between these gross
losses and the previously measured **40 and 23 fewer retained units**.

The reconstruction also exposes a model constraint: soil water moves downward
and sideways, **never upward**. At the end of this window, 89–92% of all soil
water lies below each selected plant's deepest root. Those deep stocks cannot
wick back into the shallower root cells under the current rules.

This is an exact account of the selected histories, not a new rescue experiment
or a qualification of the allocation policy. The [frozen protocol](
landing-soil-audit-protocol.md) uses only the preceding [drying capture](
landing-drydown.md): no native calls, training, C changes, firmware build or
device flash. The four order/guard cases are retained, but fixed and rotating
observations still duplicate; there are two distinct paired histories.

## Reconstruction matches every recorded cell

The Python audit independently reconstructs 216 adjacent updates in each of
eight primary arm captures: **1728 transitions and 532224 cell comparisons**.
Every predicted pre-uptake grid matches the recorded one exactly. No residual
is assigned to an imagined process.

The archived C implementation supplies the rules and their order:

1. Counter-based weather and the seasonal drought gate determine rain.
2. Rain is added to surface cells with byte saturation.
3. Downward transfers run in place, from the top row toward the bottom.
4. Lateral transfers alternate between even and odd neighboring pairs.
5. Surface evaporation removes one unit from nonempty cells every fourth step.
6. The already-recorded root uptake follows.

Transport requires the source to exceed the destination by at least two units.
Its integer transfer is at least one, at most 12 downward or four sideways.
The downward divisor is four; the lateral divisor is eight. Preserving in-place
order, pair parity and rounding matters; a simultaneous averaging stencil is
not the implemented model.

All transitions have gardener/irrigation disabled and bottom drainage off.
The complete lineage records contain no germination inside this window, which
would otherwise remove surface water after the uptake observer. Every recorded
adult soil total agrees with its post-uptake grid. The initial transition into
626520 is unavailable and is not reconstructed.

The stage grids and boundary transfers below are **reconstructed**, not new
native instrument readings. Exact agreement at every saved endpoint and the
preserved, hash-checked historical implementation support that reconstruction.

## The missing water enters through neighboring cells

These accounts start at the shared-capacity anchor's **post-uptake soil**:
626580 for daylight, 626520 for dawn. They include the first following soil
update and exclude the anchor's completed uptake. Internal transfers between
two target root cells cancel; flow entries count only crossings of the whole
root footprint's boundary. Both opening and closing root-cell water are zero.

| Post-anchor root-cell account | Daylight control | Daylight candidate | Dawn control | Dawn candidate |
| --- | ---: | ---: | ---: | ---: |
| Direct rain deposited | 36 | 36 | 36 | 36 |
| Downward inflow | 33 | 22 | 26 | 20 |
| Lateral inflow | 96 | 61 | 109 | 30 |
| Outflow across either boundary | 0 | 0 | 0 | 0 |
| Surface evaporation | 6 | 6 | 9 | 6 |
| Root collection | 159 | 113 | 162 | 80 |
| Plant storage overflow | 6 | 0 | 59 | 0 |
| Retained income | 153 | 113 | 103 | 80 |

The late shower supplies two units per surface column per step from 629160
through 629415 inclusive in every arm. Different rain is not the source of
this window's difference. Daylight loses 35 lateral plus 11 vertical units;
six fewer overflow units reduce the effective loss to 40. Dawn loses 79 lateral
plus six vertical units, but evaporates three fewer and overflows 59 fewer,
leaving a retained loss of 23.

Actual edge receipts show how low neighboring stocks stop replenishment. At
626595, daylight's downward edge from soil cell (2,1) to (2,2) transfers one
unit in control: source two, destination zero. Candidate source one and
destination zero fail the same two-unit gradient gate. That edge supplies
33 units in control and 22 in candidate over the account. For dawn, the lateral
edge (12,1) to (13,1) supplies 19 versus two; its first difference at 626550 has
control source four and candidate source one, both with destination zero.
Coordinates are zero-based column and row.

All boundary attempts are retained, including zero transfers and unchanged
edges. These examples identify the immediate gradients behind lost inflow;
they do not establish which earlier plant or event created those gradients.

## Deep stock is not accessible water for these bodies

| History at 629760 after uptake | Deepest root row | Total soil water | Water below that row | Share below roots |
| --- | ---: | ---: | ---: | ---: |
| Daylight control | 6 | 2227 | 1986 | 89.2% |
| Daylight candidate | 6 | 2100 | 1923 | 91.6% |
| Dawn control | 7 | 1936 | 1740 | 89.9% |
| Dawn candidate | 7 | 2050 | 1833 | 89.4% |

Soil rows run from zero at the surface to ten at the bottom. Each below-root
total is unchanged from its corresponding anchor. The target cells finish
empty despite that deep stock. This does not prove that other cells in the
upper rows are accessible, or that a different root body could not reach the
deeper layer. It does show why whole-world moisture is a poor measure of water
available to these particular bodies.

The surrounding population also matters to the interpretation. In the fixed
four-cell Manhattan neighborhood around the daylight roots, another candidate
plant collects 49 units; no other control plant collects there. Around dawn's
roots, the two-cell neighborhood contains 49 units of other-plant collection
in candidate and zero in control. These are actual neighboring consumers, not
same-cell overlap. The neighborhoods also start with different water stocks,
and their boundary flows differ. Removing a neighbor would change those flows;
its measured consumption is not a causal allocation of the target's deficit.
All four predefined radii, including zero and unchanged cases, are in the data.

## What to investigate next

The trace agrees with the implemented transport; there is no unexplained water
accounting discrepancy in this interval. The missing refill comes primarily
from weaker lateral inflow, while a large deep reservoir remains below the
observed roots. Earlier competition and inherited soil differences are still
possible causes; this audit does not identify the first divergence.

The subsequent [root reachability audit](landing-root-reachability.md) now
finds that both plants already reach their maximum possible soil row. Their
deepest tips finish at the segment limit with resources and body slots still
available. Even the deepest allowed genome cannot reach the bottom two soil
rows. This supports discussing a bounded upward-transfer experiment, not a
claim that such a change would rescue the plants. No deeper-root intervention,
capillary variant, larger body allowance or new reserve rule is implemented.

## Reproduction and verification

`make host-audit-landing-soil` writes a fresh audit file without a build or
simulation. It reads the archived implementation from
`GARDEN_LANDING_DRYDOWN_OUT` and writes to `GARDEN_LANDING_SOIL_AUDIT_OUT`.
The portable [results](landing-soil-audit-results.json.gz) are about 364 KiB.
They include the original native capture metadata and seven exact source
files, reconstructed stage grids, all-cell balances, boundary receipts,
fixed neighborhood accounts and depth profiles. Earlier capture files are
unchanged; no new full-size raw bundle was created.

```sh
make host-audit-landing-soil  # Fresh output file required
docker compose run --rm -T firmware python3 sim/garden_landing_soil_audit.py \
  --verify benchmarks/garden-seasons/landing-soil-audit-results.json.gz
docker compose run --rm -T firmware python3 sim/garden_landing_soil_audit.py \
  --verify benchmarks/garden-seasons/landing-soil-audit-results.json.gz \
  --bundle artifacts/garden-landing-drydown-v1
```

Portable verification rederives the account from the pinned drying capture and
its repository input chain. Optional raw verification also rehashes the prior
bundle, reextracts its observations and checks the implementation archive.
Both modes pass without executing a simulator. Two independent exports are
byte-identical. All 15 new audit tests pass, including altered-source and
altered-receipt rejection. The four related CTest entries pass all 58 Python
cases. This is targeted host-side audit validation, not a new firmware or full
native-suite qualification.

| Artifact | SHA-256 |
| --- | --- |
| Soil audit results | `bd5066879c513a2d4af58773014d70d39da931584b40eafbe4f6d27d07898a55` |
| Frozen audit protocol | `d538cc50adedc5710dfb62985bc4dd73ed1ec28ec98b4d6004025b93a116912a` |
| Unchanged drying input | `2107de1ed88bef2ef66d8b168f4fd8d3338329b02c8dc8aff5b919aa487a6a29` |
