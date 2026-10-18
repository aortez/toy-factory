# Decomposition retains capacity until the older seed germinates

The recruit's seed had no usable opening during the 63 checks left unresolved
by the [offline audit](landing-recruit-seeds.md). Its dead parent retained a
plant slot and 32 nodes throughout those checks. The older seed germinated in
the same ecology step that decomposition released them. By the recruit seed's
turn, the population was full again and its landing was occupied.

This closes the selected seed-establishment diagnosis without changing the
simulation. It does not establish that another germination order would improve
renewal, explain purchase-free recruits, or qualify the environment for training.

## The handoff within one ecology step

The [predeclared diagnostic](landing-seed-handoff-protocol.md) follows the cursor
arm of S2 crowded, seed `366928c6`, with W2 and all previous settings unchanged.
The recruit is parent 35; its competing older seed belongs to parent 31. Both
seeds target column 15. Parent 35 itself occupied column 24.

| Point in the history | Stored plants | Stored nodes at seed check | Result |
| --- | ---: | ---: | --- |
| Death at day 478.750 through the check before reclamation | 8, including dead parent 35 | 254 | Both plant and node capacity block germination. |
| Day 478.996, older seed's turn | 7 | 222 | Parent 35 has been reclaimed; the older seed germinates as plant 36. |
| Same step, recruit seed's later turn | 8 | 226 | The new seedling occupies a slot and the landing; the recruit seed is blocked. |

There are 63 ecology steps between death at tick 1,838,400 and reclamation at
tick 1,839,345: 0.24609375 Garden days. Decomposition runs before maintenance,
so the death-step seed check still sees the newly dead body. Its stored nodes
are retained until whole-body reclamation. At 254 nodes, a seedling requiring
four more cannot fit within the 256-node limit, independently of the eight-plant
limit. Reclamation removes exactly 32 nodes; germination then adds four.

The older seed is first in the bank's visit order; the recruit seed is fifth.
The older seed sees no blockers, moisture 231 and light 158. Its germination
consumes 12 moisture units. The recruit seed subsequently sees moisture 219,
the same light, and plant-capacity plus spacing blockers—not a water shortage.
Later growth adds another node, so the next ecology step sees 227 nodes rather
than 226. The verifier keeps these phases separate.

The winning seed is age 8,183 of its 8,192-step lifetime: just nine ecology steps
remain before expiry. This is a concrete use of persistent seeds, not evidence
that shortening their lifetime or reversing their order would help. The losing
recruit seed ultimately expires at day 489.156, as already recorded.

## Capacity was not the only simultaneous blocker

All 63 formerly unresolved checks are mature, unexpired visits. The complete
masks show overlapping restrictions:

| Blocker combination | Checks |
| --- | ---: |
| Plant capacity, node capacity, low light and cold | 13 |
| Plant capacity, node capacity and low light | 39 |
| Plant capacity and node capacity | 11 |

Thus plant capacity and node capacity each block all 63 checks; light blocks
52, and cold blocks 13. There are no moisture, dormancy or spacing blockers in
that interval. Spacing becomes a blocker only when plant 36 establishes at the
shared landing. These counts do not mean that capacity was the only restriction
or that a living-population vacancy was a valid germination opportunity.

## Exact replays and compact evidence

Both planned replays use the original saved executable and model. They run to
day 512 but retain only the declared 66-step observation window, including the
steps immediately before death and after refill. Both complete result objects,
lifetime ledgers and endpoint pixels match the original capture. Adult and
stand traces also match byte for byte between replays. The original capture's
observer-free endpoint remains the comparison; no additional control run,
rebuild, firmware flash or rule change occurs.

The [portable evidence](landing-seed-handoff-results.json.gz) retains both call
receipts and one byte-identical copy of each raw trace. All 527 seed visits are
joined to their seed lifetimes in order. The offline verifier reconciles stored
plant IDs, live bodies, carried dead-node counts, resource stages, climate,
spacing and earlier germinations within each step. No unwindowed trace or source
archive is duplicated. The local bundle occupies about 2.6 MiB; the portable
result is 38,572 bytes.

Seventeen focused tests pass, including missing dead slots, premature reclamation,
incorrect node counts, omitted boundary steps, within-loop spacing/order,
post-germination growth, altered receipts and non-overwriting exports. Portable
and full-bundle verification run with process creation forbidden. The handoff,
recruit-seed and competitive-renewal CTests pass; earlier evidence and frozen
protocols remain unchanged. The [tool guide](../../docs/garden-landing-tools.md#seed-handoff-diagnostic)
contains reproduction and verification commands.

## Next question is purchase eligibility

Follow-up: the [full-life non-buyer diagnostic](landing-nonbuyer.md) now answers
the question below with two exact passive replays. This handoff protocol and
its seed-establishment findings remain unchanged.

The four expired recruit seeds now have sufficient observed explanations:
capacity throughout for two, a persistent living-neighbor spacing exclusion for
one, and retained dead-body capacity followed by a same-step competing refill
for the fourth. The fifth seed is still pending at day 512 and remains censored.
This closes these establishment cases, not the overall renewal problem.

The next bounded question is why S2 ordinary cursor plant 41 remains alive for
97.02 Garden days without buying a seed. A purchase-eligibility audit should
distinguish flower readiness and resource/cooldown gates from a full bank or
visit priority before choosing another intervention. No such collection or
policy change is part of this diagnostic.

| Evidence | SHA-256 |
| --- | --- |
| Frozen diagnostic protocol | `3b840bf0a18061a537de342446b657ef9f8df6a81a89768c7c342bb0aaaf9134` |
| Two-call capture | `e8f8b26d9bfbce145f88ea0e899b999236c60571fae0c0b31286eb0aec00e56c` |
| Local bundle manifest | `f103c843333b087006e899ca95e5cd536aeaae2ffa7a11e4c6b8880c6960bb46` |
| Portable handoff result | `1ec11c85ac1070f8c96bafe2e759655f98162dc55b90b824c537dd9bbadbaffc` |
