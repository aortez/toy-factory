# Open soil is usually outside steady-world parents' reach

The [fixed reach trace](landing-reach-protocol.md) answers the question left by
the [recruitment trace](landing-recruitment-trace.md): **170 of 192 late-expiring
steady-world seeds had every reachable column spacing-blocked at every mature
check**. Open soil elsewhere was real, but unreachable with that parent's
ordinary dispersal range. Only 22 ever had a reachable viable alternative.

Seasonal worlds are more mixed. Eighty of 151 late-expiring seeds had reachable
alternatives; 71 never did, including 44 with persistent spacing blocks across
their entire support. The other 27 sometimes had spacing-clear reachable soil
but never a column passing all simultaneous gates.

This is a diagnosis of twelve selected historical worlds, not a placement
intervention or an estimate of the effect of changing dispersal. Models,
ecology, scoring, firmware and all actual trajectories remain unchanged.

## Same cases, parent-specific support

Reuse exactly the previous twelve 192-day old/new live-finalist cases. Capture
the producing parent's base and dispersal trait at each purchase, before it
can disappear. Enumerate the six ordinary direction/distance outcomes with
the shared production transform. The seed's inherited trait may already be
mutated and is not authoritative for where that seed was placed.

Reflecting an out-of-bounds direction can alias the opposite choice. Of the
192 steady-cohort seeds, 135 have only three distinct reachable columns, two
have five and 55 have six. Multiplicity is retained; six choices are not always
six destinations or an assertion of exact probabilities.

Then inspect those frozen support columns at every exact sequential seed check
through the seed's lifetime. Sites include all overlapping moisture, light,
capacity, spacing and cold gates. Spacing includes retained dead plants until
reclamation. Dormant checks and pre-check expiry are not mature opportunities.

## Complete late-expiry lifetimes

The cohort remains seeds expiring in (62,190] Garden days, with all 32 days
traced, not just scoring-window follow-up. Counts are seeds with at least one
qualifying mature check, not independent environmental observations.

| Cohort | Expired seeds | Open somewhere | Open within parent reach | Never open within reach | All reachable columns always spacing-blocked |
|---|---:|---:|---:|---:|---:|
| Six steady worlds | 192 | 192 | 22 | 170 | 170 |
| Six seasonal worlds | 151 | 151 | 80 | 71 | 44 |

All reachable openings here are alternatives to the actual landing: an actual
fully eligible mature seed would have germinated rather than expired.

| Finalist | Steady reachable / expired | Seasonal reachable / expired |
|---|---:|---:|
| single /33 | 9 / 32 | 8 / 28 |
| multi /33 | 3 / 32 | 13 / 28 |
| single /34 | 3 / 32 | 17 / 23 |
| multi /34 | 4 / 32 | 18 / 27 |
| single /35 | 2 / 32 | 13 / 24 |
| multi /35 | 1 / 32 | 11 / 21 |

Reachable alternatives pass every gate on 16,819 of 1,571,328 mature checks in
steady worlds, and 16,792 of 1,235,784 seasonal checks. These are repeated
observations of banked seeds, not unique gaps or opportunities independent of
each other. Global openings occur on 260,626 and 125,232 checks respectively.

At the post-purchase snapshot, only six steady and 21 seasonal expired seeds
have a fully eligible reachable alternative. Later opportunities do not imply
that an immediate wet/lit-site selector could have seen them. Purchase maps
are hypothetical mature-site snapshots after final light refresh; the actual
new seed is still dormant.

## Two contrasting examples

In multi /34's steady `rainfed/5aa2b327` world, parent 1 is rooted at column 4
with dispersal trait zero. Its choices are `[9,9,10,10,11,11]`: only columns
9–11. Twenty-seven late-expiring seeds come from this parent, all with every
reachable column persistently spacing-blocked. For one seed bought on day
34.890625 and expiring on day 66.890625, columns 0, 1, 7, 13–15 and 21–27
are each open at some check, but none is in its support. Rerolling the same
six choices cannot find a different region of soil in this unchanged world.

Conversely, multi /35's steady crowded world has one genuinely missed reachable
alternative among its 32 late expiries. Parent 10 at column 11 has choices
`[6,16,5,17,4,18]`. Its day-37.921875 purchase lands at 18; columns 4, 5 and 6
are all open in the purchase snapshot. Column 4 is open at 1,271 subsequent
mature checks, with a longest run of 94 ecology samples. Destination selection
could matter in cases like this, but that is not the dominant steady-world
pattern. No relocation was performed, and seedling survival is not established.

## Next bounded experiment

Test a **placement-range-only A/B** before adding destination selection. Reuse
the existing host-only wider-scattering rule (`5–7 + trait` to `3–9 + trait`),
with the same single random draw, reflection rule and inherited offset. Keep
spacing, rainfall, seed lifespan, capacities, network bytes and fitness fixed.
Do not steer seeds toward globally visible gaps or move banked seeds.

This is an existing candidate with [earlier evidence](recruitment.md), not a new
rule invented from these traces; those earlier policies/panels do not establish
its benefit for the current trained finalists. Start with these same matched
diagnostic cases and retain the regressing /33 and successful seasonal controls.
Evaluate late renewal, first-day survivors, seed expiries, resource deaths and
empty-world regressions, not merely more germinations. A broader fresh panel
would still be needed before promotion. No A/B treatment is implemented here.

The range change will also redistribute choices, not just add destinations.
It may worsen useful landings. The separate first-day resource failures from
the previous trace remain unresolved; changing placement must not be conflated
with a growth/reserve-policy change or claimed to solve them.

## Verification and evidence

- [Protocol](landing-reach-protocol.md), [workflow/schema](../../docs/garden-landing-reach.md),
  [readable summary](landing-reach-summary.json) and [portable full results](landing-reach-results.json.gz).
- All twelve complete results and historical scores match, as do twelve
  untraced controls and twelve repeated reach traces. Existing recruitment
  traces remain byte-identical, including all first-day resource samples.
- Independent frozen-tool replay reproduces all twelve new traces and results;
  all 303 frozen artifact hashes recheck. The bundle is
  `artifacts/garden-landing-reach-v1`.
- 806 purchases and 4,592,849 seed events reconcile over 589,824 ecology samples.
  Outcomes are 439 expired, 271 germinated and 96 pending; pending is not failure.
  Full per-seed mature-site histograms and column open-window summaries are
  retained, not just the late failures selected for discussion.
- Host-only bounded, read-only publishing follows the embedded-C conventions.
  Tests cover mutated seed traits, reflection, non-mutation, invalid input,
  partial horizons, no-clobber, corrupt traces, expiry/censoring and portable
  report reconciliation. No world-layout, RNG, controller-ABI or firmware change.
- The complete **144-test UBSan host suite passes**, including the profiling
  smoke test enabled in this isolated build. Log:
  `artifacts/garden-landing-reach-tests.log` (70.94 seconds). Formatter and
  `git diff --check` pass. This is not a firmware rebuild or device performance test.

Frozen manifest SHA-256:
`0c08a37256b2e42d6f7d553b860448d26975599ea2431442274f44e6cb288656`.
