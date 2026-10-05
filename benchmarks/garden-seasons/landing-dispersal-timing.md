# Seeds land in crowded sites because local dispersal is constrained

All 128 seeds purchased by the capped worlds in their final 32 garden days
land at sites that are **already occupied under the spacing rule**. This is
not late-arriving competition spoiling initially clear sites. For 112 of those
purchases, spacing-clear columns exist elsewhere in the world.

The current placement policy already redirects a blocked choice when another
legal choice is clear. Under that implemented rule, these occupied landings
mean every legal choice was blocked. The next useful counterfactual is to
broaden the candidate landing distances while retaining spacing and seed costs.
That is a proposal, not a change made or qualified by this audit.

## What was observed and what was inferred

This offline follow-up uses the [renewal-gate audit](landing-renewal-gates.md)
and its pinned observations, following a [frozen protocol](landing-dispersal-timing-protocol.md).
It covers all 32 primary worlds from the uptake-cap experiment, not repeat
runs. The same eight order/guard/allocation settings and four arms remain;
they share one examined weather seed and controller.

The saved slot census identifies all stored plants, including decomposing
occupants. Their base columns are in the lineage ledger. Reconstructing the
census before each sequential germination check accounts for earlier newborns
in the same step. Every recorded spacing bit and plant-slot count reconciles.
Purchase-time occupancy is exact: growth and reproduction do not move bases,
and no slot compaction occurs between reproduction and trace publication.

However, these traces do not record each parent's dispersal trait or random
draw. Ordinary dispersal offers six signed choices: distances `5 + trait`,
`6 + trait` and `7 + trait`, left or right, with reflection at the edges.
The trait is one of `-2..2` and remains constant in an existing parent.
Mutation changes the seed's genome, not the parent's.

The audit keeps two explicitly separate bounds:

- **Landing-only:** retain every trait consistent with all recorded landings
  by that parent. This uses the full ledger retrospectively; it is not an
  observation available to an online policy.
- **With the placement rule:** additionally require all six choices to be
  blocked whenever the enabled spacing-aware policy bought a seed into a
  blocked site. This is a deduction from the implementation, not an independently
  recorded trait or a test of that policy's correctness.

Some parents remain ambiguous. No trait, random draw, mutation history or
cross-world identity is invented to resolve them.

## Crowding usually predates the purchase

The main window is `(626580, 983040]`. These are purchase cohorts, not repeated
seed-check counts:

| Arm | Purchases | Already blocked at purchase | Initially clear then blocked | Clear through seed exit or observation end |
|---|---:|---:|---:|---:|
| Ordinary | 256 | 177 | 29 | 50 |
| Wicking | 216 | 181 | 9 | 26 |
| Uptake cap | 202 | 177 | 13 | 12 |
| Cap + wicking | 196 | 188 | 0 | 8 |

"Clear through observation" does not mean a child established or survived.
Fates and follow-up are retained separately. Of the 13 cap-only purchases
crowded later, five encounter a sibling and eight encounter another parent's
child. Later competition therefore exists, but it does not explain the
final-period capped seed cohort.

In `(860160, 983040]`, every capped world buys eight seeds into already-blocked
sites. The seeds carried into that final window were also blocked at purchase:
all 1,047,540 final-period mature checks in the two capped arms trace back to
that category. Their purchase contexts are available because the excerpt
starts earlier than the oldest viable final-period seed.

All 64 cap-only final-period purchases have spacing-clear columns elsewhere.
With both rules, 48 do and 16 do not. Those 16 globally spacing-closed purchases
are the fixed and rotating dawn/ordinary-allocation settings. "Spacing-clear"
does not establish adequate moisture, light or pool capacity.

## Most later usable sites are outside the original dispersal reach

At each mature check, the trace records how many hypothetical mature sites
pass all gates, but not their coordinates. The slot census supplies the larger
set of spacing-clear columns. Set-intersection bounds combine that set, the
open-site count, the chosen site's recorded result and each possible trait's
support. A result is classified as no globally open site, definitely unreachable,
definitely reachable, or unresolved.

Final-period counts below retain every setting. Each cell is **definitely
unreachable / checks with any globally open site**, using only the landing-based
trait bounds. Repeated checks of the same seeds are not independent trials.

| Order / guard / allocation | Cap | Cap + wicking |
|---|---:|---:|
| Fixed / daylight / ordinary | 17,720 / 17,720 | 19,184 / 19,184 |
| Fixed / daylight / focal | 17,576 / 17,576 | 16,849 / 19,256 |
| Fixed / dawn / ordinary | 17,609 / 18,915 | 0 / 0 |
| Fixed / dawn / focal | 19,960 / 19,960 | 9,664 / 9,664 |
| Rotating / daylight / ordinary | 17,720 / 17,720 | 19,184 / 19,184 |
| Rotating / daylight / focal | 17,576 / 17,576 | 19,256 / 19,256 |
| Rotating / dawn / ordinary | 18,915 / 18,915 | 0 / 0 |
| Rotating / dawn / focal | 16,456 / 16,456 | 0 / 0 |

For cap-only worlds, 143,532 of 144,838 checks with globally open sites prove
those sites unreachable: **99.1%**. Another 931 prove at least one reachable
site, and 375 remain unresolved. The placement-rule constraint changes none
of these counts.

For cap plus wicking, the landing-only bound proves 84,137 of 86,544 such
checks unreachable: **97.2%**. The remaining 2,407 are unresolved. Applying
the implementation-dependent trait constraint makes those unreachable too;
that stronger conclusion is kept separate from the 97.2% bound. Neither
bound finds a definitely reachable usable site in these combined worlds.

There are also 378,930 cap-only and 437,228 combined checks with no globally
open site at all. A larger dispersal support cannot make an unavailable site
usable at those snapshots, and static bounds do not predict the effects of
changed trajectories.

## The reachable vacancy exception

In fixed order with the dawn guard and ordinary allocation, cap-only parent
17 buys a seed at tick 898260. Its base is column 13, and its recorded landings
uniquely constrain its trait to `+1`. Its six choices are columns
`7, 19, 6, 20, 5, 21`.

At purchase, only columns 0 and 27 are spacing-clear, so every legal choice
is occupied. The seed lands at 19. Later, columns 6 and 7 become spacing-clear,
and the recorded open-site counts prove at least one reachable usable site
on 931 checks. On another 375 the coordinates remain ambiguous. The seed
stays at 19, blocked by plants based at 18 and 21, and remains pending at the
horizon. Seeds do not move or choose again after purchase.

This exception matters: "never reachable" would be too strong. A vacancy
can open later, after the seed has spent its placement decision and bank slot.

## Next bounded experiment

Test one broader support, including nearer and farther candidate distances,
while retaining the spacing-aware choice, spacing threshold, seed costs,
bank size and viability. A natural fixed candidate to discuss is distances
`3..9 + trait` rather than `5..7 + trait`, preserving reflection and applying
the change only at the established late intervention point. This changes
the legal choices; it is not an oracle that sends seeds to any global vacancy.

The older wide-dispersal build cannot simply be switched on here: the current
placement callback explicitly rejects that combination and assumes six
choices. A follow-up needs a separately identified host-only implementation
and compatibility tests, not a flag change in this audit.

Use matched capped histories, retain all settings including globally closed
and pool-saturated cases, and measure established descendants, replacement and
resource harm alongside purchases and births. The evidence motivates that
test; it does not guarantee improvement or justify changing the device.
Keep both water rules and any broader dispersal experiment off by default.

## Reproduce and verify

The [portable result](landing-dispersal-timing-results.json.gz) is about 168 KiB.
It contains purchase slot contexts, spacing-witness runs, mature-check
histograms, per-parent trait bounds and all derived summaries. It references
the existing 23 MiB window excerpt rather than duplicating it.

```sh
make host-audit-landing-dispersal-timing \
  GARDEN_LANDING_DISPERSAL_TIMING_OUT=artifacts/dispersal-timing-fresh.json.gz

python3 sim/garden_landing_dispersal_timing.py \
  --verify benchmarks/garden-seasons/landing-dispersal-timing-results.json.gz --reextract
```

All 20 focused tests and the existing renewal-gate suite pass. Tests cover
all origins/traits, reflected aliases, ambiguous and contradictory constraints,
exhaustive small-set intersection bounds, same-step germination order, retained
dead occupants, sibling/other-parent arrivals, expiry, missing evidence and
no-clobber output. Both compact reanalysis and independent re-extraction from
the pinned windows pass with native process creation forbidden. This step
does not recapture simulations or repeat the preceding raw-trace verification.

The reviewed C implementation files match the hashes in the pinned capture;
the export records those identities. No simulation logic, firmware, model,
ecology or default changed.

| Artifact | SHA-256 |
|---|---|
| Frozen protocol | `b2a4fc11a673028fae591949cd9af67956cdfef040c7ea95cfed937f74537738` |
| Renewal results | `20d269d868b2cc1135e93d4b0f4ebe37ef667e3316d92e280d1d7488b38bd255` |
| Window excerpt | `d7ff641241c1cc0f242e68628648a04ce82e1ffe5046f0a4221a2485b7c61026` |
| Uptake-cap ledger input | `687f354bbeb04b71dc2c8d81b57bccefba0a1f6e2cfa6677f9dd14d517647768` |
| New portable result | `5873783662a03884d5fb0cca1a6c41b36fcb1a3dba35a458838b40755111aa6a` |
