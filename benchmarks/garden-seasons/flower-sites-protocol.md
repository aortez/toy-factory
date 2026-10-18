# Read-only flower reach at production opportunities

Freeze before collecting outcomes. Diagnose the unchanged
[flower-origin screen](flower-origin.md): all 32 saved cases, both origins,
eight slots, wide scattering, the same offspring reserve guard, seasonal weather,
128 days. No new control policy, training, costs, timing, drift, or default change.
Replaying these worlds with an observer is not a new ecological experiment.

## Exact sampling and denominators

Observe every **successful seed purchase**, not every frame, flower, blocked
attempt or possible later release time. Capture all mature, unspent flowers of
that parent immediately before the selected one is marked spent. Preserve the
existing first-ready selection. Record geometry, dispersal trait, actual origin,
support and the existing production draw, consuming no extra RNG.

Evaluate all 28 hypothetical mature-seed sites after that same ecology step's
normal final light refresh. Growth precedes production; the refresh incorporates
its new shade. Seed purchases themselves do not change soil, geometry, plant
counts or spacing. Explicitly identify this phase; do not use stale pre-growth
light or interpret post-step masks as failed germination attempts. Newly landed
seeds still have dormancy; these are habitat diagnostics, not immediate births.

Retain all production visits and reconcile successful purchases with saved
seed ledgers and post-step records. Keep full-world state hashes for every
ecology tick. Match offspring by parent/creation tick within an arm only.
Closing production means purchases strictly after day 112, not offspring born
after that date. Lifetime outcomes use the existing calendar censoring rules.

## Questions and fixed summaries

For both all germination constraints (except dormancy) and local habitat alone
(moisture, light, spacing), classify each purchase:

1. The actual origin already reaches an open site.
2. It does not, but an eligible flower's origin reaches an open site (necessarily
   a different flower in the flower-origin arm).
3. No eligible flower reaches one, although an open site exists elsewhere.
4. No column in the world is open under that constraint set.

Local-only results ignore winter and node/plant capacity, not soil/light/spacing.
Report those global limits separately. In the base-origin arm, flower relocation
is hypothetical: choosing a different flower alone cannot change the current
base-origin rule. The flower-origin arm is the primary flower-choice diagnostic.

Count flowers and distinct origins, reachable columns and landing-choice weights.
Enumerate the unchanged distance/direction mapping, retaining duplicated landings
from edge reflection. Use exact integer branch weights over the nonzero 32-bit
xorshift outputs as a **uniform-reference** measure, not a claim about the actual
conditional RNG distribution or a policy's knowledge. Compare the first eligible
flower with the best eligible flower under that reference, with ties retained.
The actual draw may be checked diagnostically but is not an agent observation.

Report whole-run and closing counts, all worlds including zero-purchase windows,
and species/controller/layout/weather partitions. Join actual seed germination,
expiry/pending and descendant survival to the current-site classes to show the
limits of this snapshot. Do not infer that a hypothetical alternative would
survive, that waiting is safe, or that local observations give global knowledge.

No promotion gate, sweep or intervention follows automatically. Discuss whether
the evidence motivates flower selection, a timing investigation, or growth/habitat
work; retain results even if flower choice offers little opportunity.

## Integrity and validation

The host-only, caller-owned observer is bounded by existing plant/node capacities,
with no world fields, allocations, callbacks or additional random draws. Test
invalid inputs/output preservation, eligibility boundaries and ownership, dawn
renewal, sequential final-bank-slot admission, full flower-array capacity,
support/edge reflection, costs, final refreshed site masks and full-world
noninterference. Older observer output must remain unchanged without the new mode.

Build two new diagnostic directories from frozen sources, using the same
ecological flags as the corresponding saved origin arm. Freeze protocol,
source/build/input hashes. Repeat every observation trace byte-for-byte and match
every ecology state hash and creation count against the saved raw traces. Reconcile
all 3,576 saved purchases. Reanalyze unchanged raw observations; retain compact
per-purchase geometry/site/outcome evidence and summaries. Existing origin
screenshots remain valid; do not create or select a new attractive picture panel.
Run focused native tests, the default and older-research regressions, and a normal
firmware build. Do not flash or commit without a further request.
