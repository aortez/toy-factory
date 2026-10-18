# Frozen root allocation comparison

**Status: implemented for the fixed capture below.** Test whether prioritizing an
affordable root when water income has no maintenance surplus helps a matched
water-failing descendant before its construction budget is exhausted. This is
a host-only diagnostic, not training, a new default or population qualification.
The budget is sixteen native experiment calls with no parameter sweep.
Results belong in a separate report; this protocol remains frozen after capture.

## Why this test

The [direction audit](landing-directions.md) found that plant 9 adds one root
and twenty-seven shoots, finishing at 32 nodes with three roots. Legal,
affordable root bids lose to shoots during construction. Its final recorded
day earns no water, and it dies at 457020 with substantial energy left.
The [first-day direction follow-up](landing-root-direction-audit.md) also shows
why collecting more water alone is an inadequate objective: extra uptake can
be lost to overflow or alter later shoot decisions without improving renewal.

A pure priority calculation on the saved decisions finds these opportunities:

| Baseline guard | First changed focal choice | Nodes and roots before purchase | Water income per ecology step | Water bill per four steps | Energy income per step | Post-root energy bill per four steps |
| --- | ---: | --- | ---: | ---: | ---: | ---: |
| Daylight | 406695 | 29 nodes, 3 roots | 1 | 4 | 7 | 4 |
| Dawn | 406755 | 29 nodes, 3 roots | 1 | 4 | 15 | 4 |

Both have an existing flower, and both can buy the unchanged root proposal
to `(201,161)`, whose observed moisture is 18. The normal price is seven
energy and five water. Pre-purchase stores are respectively `(105,290)` and
`(162,293)`. These are not emergency purchases after stores reach zero.
Waiting for an actual shortage would miss the available construction budget.

At these snapshots, current water income merely matches upkeep. Energy income
covers the proposed body's maintenance, and the existing reserve checks also
pass. These facts motivate the test; they do not establish that the new root
will remain productive or that the changed body will survive.

## One bounded priority rule

Scope the treatment to the living non-founder identified by lineage **9** and
birth tick **403365**, from age two onward. Validate its expected initial
identity: parent 4, generation 1, column 24, shrub. This is an explicit
diagnostic selector, not a new observation supplied to a learned policy.
Do not apply the preference to its descendants or other plants.

Consider only the model's existing ROOT EXTEND bids that actually allocate a
node below maximum depth and pass all existing eligibility rules. Let `Iw`
and `Ie` be the current observation's last water and energy income, each per
ecology step. Let `Mw` and `Me` be the ordinary maintenance bills for the
post-root body. Maintenance occurs every four ecology steps. Prefer the root
only when all of the following hold:

1. `4 * Iw <= Mw`: water income has no maintenance surplus at its current rate.
2. `4 * Ie >= Me`: energy income currently covers the post-root maintenance rate.
3. The first legal destination in the model's existing ordering has positive
   moisture. Do not search for a wetter destination or reorder candidates.
4. The normal upfront prices, node budget, shoot-path reservation, first-day
   water guard and applicable energy, afternoon, daylight and dawn guards pass.

Set qualifying priority to `max(original_priority, INT16_MAX - 2)`. This leaves
the model's mandatory maximum-depth and blocked-tip closure priorities
(`INT16_MAX` and `INT16_MAX - 1`) above the boost. Never lower an already-higher
priority. Multiple boosted roots retain ordinary traversal tie-breaking; this
does not choose the wettest root or preserve their relative neural priorities.
An existing higher-priority bid may still win.

Use wide integer intermediates. The factor four converts time units; it is not
a tuned reserve horizon. This is an instantaneous-rate diagnostic, not a
four-sample average or forecast of future weather, soil or canopy income.
Do not borrow hypothetical uptake to pay for construction. The new root first
has an uptake opportunity on a later ecology step.

Preserve every other decision field, candidate order, action, price, memory
proposal and RNG draw. Normal winner-only memory/RNG advancement follows the
new winner, so later decisions can differ. Do not try to hold a diverged neural
state artificially fixed. Birth-time root preference remains unchanged.

The existing observations already contain income, maintenance, body counts,
stores and candidate moisture. No neural feature ABI change, new recurrent
state, moving-average cache or new action is needed for this diagnostic.

## Why the first test is focal

An unrestricted version of this predicate also finds an opportunity for plant
6 at 30975, long before plant 9 is born. Applying it population-wide could
change parentage and recruitment before the motivating individual exists.
The focal scope keeps an identical physical history up to the first changed
purchase and directly tests one individual's allocation choice.

Both reproduction orders share these early histories. Offline checks find two
changed winning choices on the original daylight first-day trajectory and
three on the original dawn trajectory. Complete first-day bid records, including
WAIT opportunities, agree with the paid-event scan. Only the first predicted
change is a paired same-state effect. Later listed opportunities are **not**
predictions of what a changed simulation will do.

These calculations do not run a simulation or claim a rescue. A successful
focal result would justify proposing a separate population-wide test, not
silently broadening this one or selecting a different focal plant after failure.

## Fixed panel and controls

Retain weather `f7ee4528`, seasonal rainfed-crowded, no gardener or irrigation,
the frozen model, eight plant slots, 256 shared nodes, 32 nodes per plant,
eight seed-bank slots and the existing seed placement/lifetime rules.
Keep the existing all-offspring birth preference and full daylight guard chain.

Use four historical baseline worlds: fixed/rotating reproduction order crossed
with daylight/dawn protection. Rotation still begins after tick 606720.
For each world, run the new focal preference off/on, each with an exact repeat,
through day 256 (`983040` logic ticks): **4 × 2 × 2 = 16 calls**. Unit tests are
separate; no extra checkpoint search, parameter sweep or adaptive extension
is included. This is one selected weather seed, not fresh qualification.

In every arm, `--root-wet-direction` remains disabled. The failed direction
heuristic is not part of the new treatment. Each control must match the full
historical result, stand/resource/direction traces and final pixels from the
corresponding direction-off world.

| Pinned evidence | SHA-256 |
| --- | --- |
| [Historical worlds and repeats](landing-root-direction-results.json.gz) | `18f81abb8f76fc0a2fb4bf1e86b6b659984cadc9b2f507382187075a56b9122b` |
| Historical raw manifest | `814b0af751397b91db4d618ef6606dac466eb30916013ce82827e61ee4924a0e` |
| [Paid construction receipts](landing-directions-results.json.gz) | `ceb1b8a5ab527eb42b635d87b795c646a1afbed493b896917897ec7ef55dab63` |
| [Complete focal first-day bids](landing-population-audit-results.json.gz) | `c40da0fc11e0a9e7cb1480faa0cbaaa328c758ddea8681d7f8981084244cf461` |
| Model | `f2dc989380339614dc512f64f11f2bf03f7079c465c4c9bd18895044ec3e1567` |

Freeze the final protocol, source, executable and build settings before capture.
Write to a fresh no-clobber bundle and preserve failed captures. Repeats must
match results, complete traces and pixels. No policy tuning during capture.

## Implementation boundary and verification

Use a small host-only pure priority helper with explicit focal configuration,
separate from the existing all-offspring guard scope. Reuse the current budget,
water and energy assessors; do not create a second set of spending rules.
Keep the world executor as mutation authority. Configuration and decisions
must remain unchanged on failure; no hidden process-global or observer-owned
state may affect decisions.

Add an opt-in CLI setting and a distinct run identity containing the rule
version and focal selector. Reject an invalid selector, incompatible scope
and combination with the wetter-direction treatment before opening outputs.
Unconfigured identities and trace bytes must remain unchanged. No firmware
configuration or default policy changes are part of the implementation.

The setting is `--root-allocation-focal`; version one fixes the six identity
fields above, with no CLI knob for choosing another plant. The immutable
configuration is stored separately from the population guard configuration.
Run identity wraps the existing identity with `GLA1`, the version and all six
selector fields as little-endian 32-bit words. Opt-in stand bids add an
`allocation` receipt for active scope, root eligibility, preference and current
water income; existing receipts already include energy income, post-root bills,
endpoint moisture, priorities and all spending guards. Unconfigured streams
retain their old schema and exact bytes.

Run `make host-probe-landing-root-allocation` for the frozen panel. The Python
tool's `--verify` accepts either the full raw bundle or portable results without
executing the simulator. Unit fixtures and short CLI integration tests are
separate from the sixteen full-horizon experimental calls.

Record eligibility, current incomes, post-root bills, chosen endpoint moisture,
raw/applied priority and the eventual winner for every observed bid. Validate
the predicate independently in Python, including all nonfocal no-ops and losing
boosts. Preserve complete resource/reproduction receipts and trace framing.
Require identical physical prefixes through the first changed purchase's
pre-action state. Later comparisons must distinguish changed cohorts from
matched individuals.

Test both equality boundaries, one-unit violations, zero income, dry/blocked
endpoints, full node budgets, flower reservation, every existing guard, birth
and founder exclusions, wrong lineage/birth, lifetime scope, ordinary ties,
terminal closure precedence, already-high priorities and disabled exact no-ops.
Test complete decision/world/memory preservation and rollback/recovery. Then
run proportional host regressions, complete raw and portable verification,
and inspect all paired final screenshots. Do not flash the device for this test.

## Outcomes and stopping rule

For the focal plant, report paid root/shoot allocations and closures, first
flower/seed timing, every energy/water shortage, complete income/overflow/spending
balances, lifespan, seeds and successful offspring. Compare resource accounts
over equal exposure as well as full lifetimes. An earlier death that removes
later bills is not an improvement; more raw uptake or an extra root is not
itself success.

Use unpaid resource units per maintenance opportunity for shortage rates, as
in the existing population analysis. Successful focal offspring are children
with the existing one-day survival confirmation; preserve censoring for younger
children at the endpoint. Report unavailable rates rather than treating zero
exposure as success.

Also retain the existing whole-population harm checks, without changing their
thresholds: living plants/species, one- and 32-day survivors, seed-producing and
successful parents, founder and closing-window credit, empty-population timing,
and both exposure-normalized offspring shortage rates. Report every pair,
including unfavorable results. No aggregate gain may hide a failed pair.

To justify a broader trial, require a strict focal improvement in water-shortage
rate or survival in at least one pair, no earlier focal death, no worse focal
energy-shortage rate, no loss of focal seeds or successful offspring in any
pair, and all existing population harm checks passing. Otherwise stop and
discuss the failure; do not add another reserve, change the selection or tune
the threshold in this capture. Even a clean pass remains a selected diagnostic,
not evidence of autonomous renewal or deployment safety.
