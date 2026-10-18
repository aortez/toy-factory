# Reachable space and affordability sometimes coincide—but the bank is full

The complete [second-opening](landing-second-opening.md) windows contain **49
eligible plant-visits with reachable, capacity-compatible space**. Of those,
35 also have a reachable column passing all current mature-seed gates. Every
one faces a seed bank that was already full before reproduction began. None
loses an otherwise-qualified spatial opportunity to an earlier buyer on that
same tick, and neither followed cohort buys a seed during these openings.

That is narrower than saying bank capacity explains every failure. Energy
protection blocks many earlier visits; some plants cannot reach the cleared
space. The 35 fully overlapping visits all belong to two plants in W5, not
35 independent trials. They are evidence for a bounded bank-renewal experiment,
not proof of its safety or a reason to lower reserves.

This [frozen offline analysis plan](landing-opening-opportunities-protocol.md)
uses existing traces only. No new simulations, training, firmware changes,
additional deaths, capacity increases or default-policy changes were made.
The five selected histories share one model and weather seed; the earlier
12/16 harm-screen failures remain unresolved.

## Count the opening, not the tick that closes it

Each interval starts when the second victim's body is reclaimed and ends
**before** the first germination that restores eight plants. Germination runs
before reproduction, so the closing tick cannot offer a plant slot to a later
seed purchase. The preceding and closing records remain separate evidence.
Controls use the same calendar intervals but retain eight plants throughout.

| World | Reclamation day | Refill day, excluded | Ecology steps | Daylight production-cadence visits per parent |
| --- | ---: | ---: | ---: | ---: |
| W1 | 288.246094 | 288.859375 | 157 | 6 |
| W2 | 288.246094 | 288.859375 | 157 | 6 |
| W3 | 288.253906 | 288.894531 | 164 | 9 |
| W4 | 288.246094 | 288.875000 | 161 | 7 |
| W5 | 288.246094 | 289.906250 | 425 | 40 |

These total 1,064 ecology steps per arm. All seven original focal plants and
five first recruits remain in the audit, giving 2,446 parent-visits per arm:
1,382 original-focal and 1,064 first-recruit. Their 149 daylight cadence visits
split 81/68. Night and off-cadence observations are retained, not silently
dropped. No control has capacity-compatible space during these intervals.

## Every followed parent, including non-producers

“Space” requires a reachable column passing spacing and global plant/node
capacity. “Eligible” requires every production gate except the bank, including
ready flowers and protected resource balances. The last column additionally
requires suitable observed ground light, moisture and temperature for a
**mature** seed at at least one reachable column.

| World / parent | Cohort | Dispersal trait | Daylight visits with space | Also eligible | Also passes current mature-seed gates |
| --- | --- | --- | ---: | ---: | ---: |
| W1 / 30 | Original focal | Unknown, bounded | 6 | 0 | 0 |
| W1 / 31 | First recruit | Unknown, bounded | 6 | 0 | 0 |
| W2 / 33 | Original focal | Unknown, bounded | 6 | 0 | 0 |
| W2 / 34 | Original focal | Unknown, bounded | 0–6 | 0 | 0 |
| W2 / 35 | First recruit | Unknown, bounded | 6 | 0 | 0 |
| W3 / 33 | Original focal | Unknown, bounded | 0 | 0 | 0 |
| W3 / 34 | First recruit | −1 | 9 | 1 | 0 |
| W4 / 33 | Original focal | 0 | 7 | 0 | 0 |
| W4 / 34 | Original focal | 0 | 0 | 0 | 0 |
| W4 / 35 | First recruit | Unknown, bounded | 7 | 0 | 0 |
| W5 / 30 | Original focal | 0 | 40 | 24 | 17 |
| W5 / 31 | First recruit | −1 | 40 | 24 | 18 |
| Total | Both cohorts | Fixed-trait bounds | 127–133 | 49 | 35 |

Five traits are recorded in actual purchases anywhere in the retained
day-288–320 history. Seven are unobserved because those parents never buy a
seed there. For them, all five legal traits, −2 through +2, are evaluated
separately; bounds cover each **fixed trait's whole-window count**, never a
different trait chosen at each step. Reflected/clamped choice aliases are
preserved. A trait can be shared across arms only for the same pre-event
lineage with validated common history. No unrecorded random draw is invented.

Thus unknown traits affect some reachability counts, but not the 49 and 35
qualified-visit totals. Every first recruit can reach some spatially legal
column during every daylight cadence visit, regardless of its unknown trait.
All five first recruits having spatial access does not mean they can all pay.

## Timing separates three constraints

The earlier report correctly found insufficient energy at the two winning
new-seed purchase instants. Examining the whole opening adds what those two
snapshots could not show:

- In W1/W2/W4, every followed parent's daylight cadence visit fails the
  protected energy threshold. The bank is also full. Removing the bank gate
  alone would not legalize those purchases.
- W3's first recruit 34 becomes eligible at tick 1,109,340 with 233 energy
  against a requirement of 208. It can reach clear space, but current ground
  light still fails and the bank entered full. W3's original focal 33 also
  becomes eligible once, but cannot reach clear space under any legal trait.
- In W5, original focal 30 and first recruit 31 each have 24 eligible,
  spatially compatible visits. Seventeen and eighteen respectively also pass
  every current mature-site gate. Their production blocker is exactly
  bank-full; no earlier buyer fills a same-tick opening on any of them.

Across all 149 daylight parent-visits, 99 fail the energy threshold. None fails
water, flower readiness, cooldown, stress or generation; energy and bank can
overlap. The remaining 50 pass every non-bank gate, but W3's unreachable focal
visit leaves 49 with space. These counts are not mutually exclusive causal
shares, nor a prediction of 49 extra purchases after a rule change.

W5's first joint opportunity is tick 1,109,340 (day 288.890625): focal 30 has
208 energy and can reach column 12; first recruit 31 has 242 and can reach
columns 12 and 13. Both require 208 and face eight banked seeds. In contrast,
at the eventual winning purchase on tick 1,113,120, both are again below the
energy threshold; first recruit 31 is visited before the winner while a bank
slot is still available. Different moments have different limiting gates.

A newly purchased seed still needs eight ecology ticks of dormancy. Current
site viability is neither a forecast of its later light nor a guarantee of
landing or establishment. All maps come from same-step observed mature-seed
checks, with matching censuses, no intervening germination/growth changes and
agreement with post-purchase maps where available. We do not substitute a
recomputed future canopy for the actual observed light.

## Evidence and checks

The [portable result](landing-opening-opportunities-results.json.gz), about
244 KiB, retains both arms' complete opening rows, ordered visitors, boundary
records, all trait witnesses, per-trait counts and relevant visit receipts.
It first revalidates the entire preceding portable audit; no raw bundle or
native executable is needed. Captured C/observer identities are pinned;
prior capture and audit implementations remain unchanged.

The [tool guide](../../docs/garden-landing-tools.md#audit-opportunities-during-the-second-opening)
documents the Make target and standalone verification. Fresh output paths are
required. Regeneration with subprocess launches prohibited is byte-identical
to the retained result. All four focused Docker CTests pass (50 Python cases):
this audit's 14 new cases, the unchanged second-opening audit, reproductive
access and bank-access suites. Tests cover exclusive closing boundaries,
complete cohorts, fixed-trait uncertainty, reflected choice aliases, compatible
site phases, ordered-bank distinctions, tampering and fresh-output protection.
An initial alias-order expectation in a synthetic fixture was corrected to
the existing left/right-per-distance order; no simulation code changed.
Python compilation, Make dry-run/help and `git diff --check` also pass.

| Artifact | SHA-256 |
| --- | --- |
| Offline protocol | `b877336aa89cd6fb9495eef18a35e979d95338b65f46818cb203566d79ded7b9` |
| Input second-opening audit | `bf54ecec747fcd8e87501d068dce76c98696529651e3950d5cf8fdb7856b5d26` |
| Opportunity audit | `5ea9fab6e1a8d4d5a9fc4aa90683959851d331196bb7192cbf9b47bc46d019ce` |

## Proposed next experiment—not a promoted rule

Test **paid replacement of a parent's own spacing-blocked seed** as an isolated
host-only bank-renewal probe. The useful case is W5's first recruit, which owns
a seed at column 14 blocked by a surviving neighbour while columns 12/13 are
reachable. W3's first recruit also owns a blocked seed. This would ask whether
a living parent can respond to newly available space without taking another
parent's bank slot.

Before running, freeze the trigger and one deterministic selection rule: only
while bank-full, with current capacity-compatible reachable space and an owned
spacing-blocked seed; charge the normal fresh-seed cost, retain all reserve
and dormancy checks, and never refund or relocate the old seed for free. Use
the existing dispersal mechanism, not future light, later fates or a preferred
lineage. Keep eight bank slots, 32-day viability, weather and both death events.
Retain every world and followed parent, including those without an owned seed.

This is a hypothesis, not an implementation commitment or evidence of success.
The [earlier bank audit](landing-bank-access.md) showed that old seeds can be
valuable, including after parental death. A currently blocked seed is not
proven permanently useless. Measure displaced-seed outcomes against unchanged
controls, extra resource spending, parental survival, established descendants
and all regressions; retain repeat and observer-neutrality checks. More seed
purchases alone would not pass. Discuss/freeze that bounded comparison before
changing simulation rules; do not shorten all seed lifetimes, increase pools
or weaken spending protection to manufacture a result.
