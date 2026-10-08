# The cursor adult loses winter income, not its seed reserve

The extra adult death in the [seed-priority comparison](landing-seed-cursor.md)
is explained by **30 fewer energy units during the final winter drawdown**.
Its earlier seed expense was replenished within five ecology steps. There is
no late construction or reproduction spending to veto. The timing and unchanged
adult bodies strongly implicate shade from the newly established neighbor;
the saved traces cannot identify individual shadow-casting leaves.

This is a retrospective, offline diagnosis of S2 ordinary (`366928c6-rainfed`),
plant 37. It adds no simulation runs or ecology changes. The original harm gate
still fails; explaining a regression does not change its classification.

## Equal starting reserves, unequal winter income

Plant 37 remains at 32 nodes, 16 roots and eight active leaves until death.
Maintenance costs four energy and two water every 60 logic ticks. Both arms
have the same weather. At day 381.15625, both fill their energy storage to 256
before maintenance, then finish the step with 252 energy, 510 water and no
stress. This is the cursor adult's last full-energy uptake step.

The following accounts use exactly the same interval in both arms:
**(381.15625, 382.8125]**, ending at the cursor adult's death.

| Energy account | Fixed order | Cursor |
| --- | ---: | ---: |
| Starting reserve | 252 | 252 |
| Photosynthetic income | 172 | 142 |
| Overflow | 0 | 0 |
| Construction and reproduction | 0 | 0 |
| Maintenance due | 424 | 424 |
| Maintenance paid | 424 | 394 |
| Maintenance unpaid | 0 | 30 |
| Ending reserve | 0 | 0 |

Both consume 212 water units for maintenance with no water shortfall. The
cursor adult dies with 510 water units discarded. It first misses an energy
payment at day 382.703125: two units unpaid, followed by seven payments with
four unpaid each. Stress reaches eight at day 382.8125.

The fixed-order adult also reaches zero energy at that same endpoint, but it
has paid every bill and has zero stress. It receives one energy unit on the
**very next ecology step**, day 382.81640625, and remains alive at day 384.
Zero storage by itself is therefore not evidence of starvation: payment timing
and accumulated stress matter.

## The seed expense was recovered much earlier

Plant 37's only cursor-arm seed purchase is at day 360.921875. It pays 48 energy
and 24 water, finishing with 204 energy and 486 water. Water fills on the next
ecology step; energy fills on the fifth, at day 360.94140625. Both arms then
have identical reserves and zero stress. The seed remains pending at day 384.

The later shared full-energy state at day 381.15625 also rules out an unrecovered
48-unit debit as the direct cause of the terminal deficit. Refunding or vetoing
that expense does not address the observed loss of winter income. This does
not assert that changing reproduction has no other effects on the population.

## The income gap follows the new neighbor

The only new plant in this garden is 39, born to parent 35 at day 328.921875 in
column 27, three columns right of adult 37. The first paired income difference
appears at day 329.07421875, sun phase 83: fixed order earns 14 energy, the
cursor earns 12. The new neighbor then has 23 nodes and eight active leaves.
This precedes plant 37's own seed purchase by more than 31 days.

All seven pre-existing adults retain their original node, root and active-leaf
counts while alive, and spend zero on construction throughout the observation
window. Plant 39 is the only new growing body before the death. Weather, the
focal adult's active-leaf count and its maintenance costs match between arms.

Initially the lost income is surplus: over **(329,330]**, income is 1,062 versus
949, but overflow falls by the same 113 units. Both pay 256 energy upkeep and
finish with 252 stored. At the last winter, that buffer is gone. Both still
have 108 energy at day 382, but income subsequently differs by 30 units,
with no overflow to absorb the difference. The first income difference after
that noon is at day 382.03125, sun phase 72.

The captured implementation calculates each active leaf's income as integer
`light / 64`, after ray-cast shading and seasonal light reduction. Winter can
turn modest attenuation into a lost whole energy unit per leaf. This makes
shade competition a strong explanation, not yet a measured attribution to
plant 39's individual leaves. The stand traces record morphology counts and
tip identities, not the complete positions, light grid or shade sources needed
to separate neighbor shade from self-shade ray by ray.

## Next check

Use the existing passive `--uptake-trace` / `--uptake-window` observer for this
one matched pair. Retain a short window around the neighbor's establishment
and the final winter drawdown; require both replays' endpoint states, ledgers
and pixels to match the saved comparison. The observer already records leaf
positions, incident light and shade sources with lineage IDs.

Then reconstruct the recorded light calculation offline and omit only plant
39's shade contributions from those same states. That can measure whether its
shadow accounts for the missing income without deleting a competitor, changing
water access or inventing a survival rescue. A same-state light calculation is
not a long-run counterfactual. Decide whether the resulting competition is
desirable before adding protection or changing the evaluation gate.

## Evidence and checks

The [portable diagnosis](landing-cursor-energy-results.json.gz) retains both
complete focal histories, population morphology changes, matched daily budgets,
the terminal receipts and the original trace identities. Daily budgets use
open-left, closed-right intervals starting at solar noon; the last interval
stops at the paired death boundary and is explicitly partial.

Four saved gzip traces (stand and resources in each arm) were authenticated
against the original capture, including restored bytes, clocks and footers.
Independent re-extraction reproduces the diagnosis with native process launches
forbidden. Five tests cover portable recomputation, matched horizons, terminal
discard, missing/reordered samples, altered transfers and interval boundaries.
The same five tests pass through the Docker CTest target.

The [tool guide](../../docs/garden-landing-tools.md#diagnose-the-cursor-adult-death)
has reproduction commands. Added compressed evidence is **259,162 bytes**;
no original artifacts were rewritten or removed.

| Identity | SHA-256 |
| --- | --- |
| Original cursor capture | `cf6ba820eee40259fcaededb7188708517a8b282541ac78ff4b292f68d43af8a` |
| Offline diagnosis | `60d9d2d2a581cd1fd10183935eb21d1c549c077dbb8f9bf3ebbc0676b324664c` |

No firmware, default ecology, controller, training objective or capacity changed.
