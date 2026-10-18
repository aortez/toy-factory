# A fertile recruit loses access to the seed bank

Plant 41 is not failing to develop a flower. It becomes fertile before its first
Garden birthday and passes every reproduction gate except bank capacity on
**1,959 checks**, yet buys no seed during its 97.02-day observed life. On thirteen
checks with an opening at the start of reproduction, an earlier eligible parent
buys first. On nine other openings that reach its turn, energy alone blocks it.

The purchase-driven cursor works as implemented, but does not guarantee access
to every eligible parent. This diagnoses the selected non-buyer; it does not
establish that changing purchase priority would produce surviving descendants.
The [earlier seed handoff audit](landing-seed-handoff.md) still explains why
purchased seeds can fail to establish.

## Whole observed life, not selected moments

The [predeclared protocol](landing-nonbuyer-protocol.md) selects S2 ordinary,
`366928c6-rainfed`, cursor arm, from the day-512 competitive-renewal capture.
Plant 41 is generation four, species zero, parent 36, base column 24. It is born
at tick 1,593,525 (day 414.98046875) and remains alive at tick 1,966,080 (day 512).
Every ecology check is retained: **24,838 inclusive samples**, 15 logic ticks apart.

The first ready flower appears at tick 1,597,065, age **0.921875 days**. The plant
reaches its 32-node construction limit at tick 1,597,485, age 1.03125 days, with
16 roots, maximum stem depth 15 and one flower. Its flower remains ready; it
never pays for a seed and has no reproduction cooldown. The portable record
also retains all 612 focal growth bids, without treating them as a simulated
alternative growth policy.

Of the 24,838 visits, 22,879 fail at least one non-bank gate. The other 1,959 are
otherwise eligible: 1,946 see a bank already full at entry, and thirteen lose
an opening to an earlier buyer. None purchases. These four categories are
mutually exclusive and sum to the complete observed lifetime.

## What happens when a slot is available

There are 26 reproduction steps beginning with seven seeds rather than eight.
They partition as follows; a slot at step entry is not necessarily available
when plant 41 is visited.

| Focal state | Steps | Bank at plant 41's turn | Explanation |
| --- | ---: | ---: | --- |
| Newly born, immature and resource-short | 1 | 7 | Also not a maintenance/reproduction turn; nobody buys. |
| Still immature and resource-short on the next step | 1 | 8 | Parent 35 fills the slot before plant 41. |
| Otherwise eligible | 13 | 8 | Earlier eligible parents fill the opening. |
| Energy-short only | 9 | 7 | Plant 41 gets a real turn with room, but cannot afford the seed. |
| Energy-short and bank-full | 2 | 8 | Earlier buyers fill the slot; energy would also prevent purchase. |

The nine energy-only checks occur with stored energy **135–186**, below the
required **208**. They have a ready flower, enough water, daylight, no stress
and no cooldown. The prior successful buyer is 38 in all nine; the cursor visits
39, then 41, before a later plant buys. The thirteen eligible lost openings have
energy 224 or 252 and require 208. Each has one released slot and one identified
earlier buyer. There is no inferred or missing purchase.

Across the complete window, 25 seeds leave the bank: plant 41's germination at
the first sample and 24 expiries. There are 25 replacement purchases. The bank
ends full on 24,837 samples and with seven seeds only on the birth sample.
Parents 32, 33, 34 and 36 each buy three seeds, parent 35 buys four, and parent
38 buys nine. Parents 39 and 41 buy none. All eight remain living in this window.

Twenty-two of the 24 expired seeds are immediately replaced by the same parent.
Expiry is exactly 32 Garden days after purchase, preserving time of day and
phase within the 16-day seasonal year. This repeats the opening schedule;
it does **not** imply identical weather, stores or every gate on each recurrence.
The cursor advances after actual purchases, so a parent that is resource-short
when its turn has room can still be behind other buyers when it later becomes
eligible. Fair rotation of a start position is not a guarantee of eventual
successful access under time-varying eligibility.

## Overlapping gates are not competing explanations

The complete blocker counts are bank 24,828; off-cadence 18,628; insufficient
energy 13,718; insufficient daylight 12,513; no ready flower 236; stress 48;
insufficient water seven. Cooldown, death and generation-limit blockers are zero.
These overlap heavily, including routine night/off-cadence checks. They must
not be summed or used as shares of a single cause. The opening-by-opening table
above distinguishes actionable access from ordinary ineligibility.

## Replay validity and storage

Exactly two passive replays use the original saved executable, build settings
and W2 model. Both complete result objects, lifetime ledgers and endpoint pixels
match the original observer-free endpoint. The full stand traces are also
byte-identical. No C source, model, ecology rule, capacity, acceptance gate or
device firmware changes; no training or additional control simulation runs.

Each full trace is 69,320,202 bytes, losslessly compressed to 1,133,098 bytes.
Only the verified raw duplicates are removed. The local bundle retains both
compressed traces, excerpts and receipts in **4,497,883 bytes** of file contents;
the original executable and source archive are referenced rather than copied.
The [portable result](landing-nonbuyer-results.json.gz) is **756,387 bytes** and
contains every reproduction visit, focal body and focal growth bid, plus both
call receipts and the derived audit.

The offline verifier independently reconciles gate masks, lifetime coverage,
all seed releases and purchases, own-turn bank counts, cursor order from the
last successful buyer, climate and flower inventory. Full-bundle verification
also decompresses both raw traces and repeats extraction exactly. Seventeen
focused tests cover omitted endpoints, altered order/gates/bank counts, flower
and climate contradictions, provenance, derived summaries and lossless compaction.
All five selected CTest suites pass: non-buyer, seed handoff, recruit seeds,
competitive renewal and bank-access unit tests. Portable and full-bundle checks
also pass with process creation forbidden. Portable excerpt authentication uses
canonical JSON, not recompression with the verifying machine's zlib version.
The [tool guide](../../docs/garden-landing-tools.md#long-lived-non-buyer-diagnostic)
documents collection and offline verification.

## Next proposal: compare access policy, not growth concessions

The selected plant already grows, survives and becomes fertile. The next useful
comparison is a **host-only waiting-time purchase priority**: among currently
eligible parents, prefer the one waiting longest since its last purchase (or
birth for a never-buyer), with deterministic ties. Keep resource checks, seed
costs, capacity, viability and germination rules unchanged. This is a proposal,
not an implemented policy or a demonstrated improvement.

Predeclare the comparison against the current cursor and retain population
survival, species/family retention and sustained parent–child renewal as the
outcomes. More evenly distributed seed purchases alone are not success, and
fairer access could harm an established parent or still produce no descendants
in a full garden. This diagnostic does not revise the original cursor harm gate,
promote defaults, or qualify the environment for training.

This proposal is now followed by the separate
[completed waiting-time comparison](landing-seed-wait.md): more primary-cohort
buyers and one additional 32-day survivor, but no new recruit's children and
no sustained-renewal success. The original diagnostic, protocol and data remain
unchanged.

| Evidence | SHA-256 |
| --- | --- |
| Frozen diagnostic protocol | `3af177622cb218332c75e8713b4fa2b8168423e2902ce74a739835cb93557612` |
| Two-call capture | `ae6916a1705d7446c6d3bbe1a34110266a2c47f598fc43ed044cb679b9e558d4` |
| Local bundle manifest | `6476ed2b0ccc43e7a8f4f14fa9933241b3a25ace6c9057378461c6a77e407c7b` |
| Decompressed canonical excerpt | `e50774d8e5068a638f9f122a000a0da3041a3ceb4fd7383b158714f58a24cd40` |
| Portable diagnostic result | `5b3b2f433257c2c433b2c61e92fc85395f819e1b556a104c863e74675209b79e` |
