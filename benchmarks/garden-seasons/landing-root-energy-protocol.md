# Energy after one root: prospective protocol

Test whether protecting overnight energy after the same initial root purchase
changes the three observed energy-starved seedling failures. Keep both successful
seedlings as harm checks. This is a selected-case counterfactual, not a population
policy, qualification result or training run.

## Fixed inputs and rule

Use the five cases, model, climate, placement, water guard, node budget and
reproduction order from [the root-choice protocol](landing-root-choice-protocol.md).
The controls are its root-choice **candidates**, not its original controls.

| Order | Lineage | Birth/root tick T | Column | Role |
| --- | ---: | ---: | ---: | --- |
| fixed | 45 | 859860 | 25 | successful harm check |
| fixed | 46 | 905595 | 3 | successful harm check |
| rotating | 48 | 899130 | 27 | failed seedling |
| rotating | 49 | 906570 | 12 | failed seedling |
| rotating | 50 | 906720 | 27 | failed seedling |

Both arms buy the same root at T. Only the candidate subsequently adds energy
eligibility, for that living offspring born at T, at ecology ages 2 through 256
inclusive. It switches off at age 257 (T+3840). Do not gate the birth purchase:
otherwise the energy rule could prevent the root we are trying to hold constant.
No persistent fired flag, extra random draw, resource grant, changed model,
destination reordering, action substitution or memory edit.

Reuse `toy_factory_garden_reserve_forecast` unchanged. WAIT remains eligible;
paid night actions are ineligible. During daylight, forecast the post-action
node count and ordinary species/vigor price, maintenance `max(1,ceil(nodes/8))`,
remaining daylight maintenance and 32 night maintenance charges. Credit half
the current energy income over remaining pre-sunset steps. Require energy after
the action to cover one maintenance charge and projected sunset energy to cover
night maintenance. This is the existing local heuristic, not future-world
knowledge or a guarantee of survival. No parameter search.

Apply this as another eligibility condition **before** normal priority arbitration,
alongside the unchanged node-budget and water checks. Do not turn the highest
rejected proposal into a WAIT that blocks lower-priority eligible proposals.
Keep the existing all-ineligible fallback and ordinary growth executor.

Pin root-choice results SHA-256
`d29470fc81efc4c111ead315a159bb8e7caac7fb0e2b75f7b7ec0a40c1861b9f`
and raw-bundle manifest
`e2925f56da731485dd5df50ee9fe297256ece271e5bc58026b6199a5b4f5ae7b`.
Retain its earlier pinned inputs and model SHA-256
`f2dc989380339614dc512f64f11f2bf03f7079c465c4c9bd18895044ec3e1567`.

## Budget and verification

Exactly 40 native experiment calls: five independent cases, two arms, four calls
each. Capture the common post-root state at T, first-day checkpoint T+3840,
and day-256 full trace plus exact repeat. Trace stand/resources over
`[T-15,983040]`. Unit/integration tests are separate. No additional native
experiment calls or tuning after inspecting results.

Freeze protocol, source, executable, build configuration and inputs in a fresh
no-clobber bundle before collection. No source edits during collection. Verify
common post-root normalized JSON and exact pixels; controls must reproduce the
saved root-only day-one/end states, pixels and complete overlapping traces.
Repeats must match JSON, pixels and both traces exactly. Existing unconfigured
fingerprints and trace schemas remain unchanged; use a new energy trace schema
and candidate fingerprint.

Independently recompute every energy eligibility receipt, check its target/age
scope, and check allocation against combined eligibility and normal first-wins
priority. Reconcile first-day resource budgets, record the sunset/dawn boundary,
and inspect survival after the guard switches off and through day 256. Preserve
all five results, shortages, morphology, reproduction, offspring and nonfocal
effects, including adverse outcomes and censoring. Do not equate newly diverged
descendants by cross-arm lineage number.

Save portable focal receipts, raw repeated traces, a screenshot gallery, offline
reanalysis and corruption tests. No firmware/default-policy change or promotion
from this hindsight-selected panel alone.
