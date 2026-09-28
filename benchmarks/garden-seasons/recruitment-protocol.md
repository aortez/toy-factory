# Seasonal recruitment and recovery: read-only protocol v1

Base: merged PR #33 (`480d261`). This pass diagnoses normal, device-sized
ecology before selecting a treatment. No rule, controller, capacity, watering,
fitness, model or firmware change is part of this collection.

## Fixed panel and questions

Reuse all four weather seeds from the 128-day seasonal panel (`0x73656132`):
`ed52188b`, `4f0b9240`, `a9c30c19`, `0bb887d6`, both rain-fed layouts and both
reference policies. Compare combined seasons with steady climate: 32 trajectories,
not 32 independent weather replicates. These are exploratory reused worlds,
not held-out qualification data.

Observe the actual sequential seed checks in the first year `(0, 16]` and final
year `(112, 128]`, in Garden days. A single replay per trajectory records both
windows and daily hashes throughout the intervening ordinary replay. Retain
the earlier full birth/death histories, and reconcile all observed germinations,
expirations and daily states against that panel.

Questions, in order:

1. Is there physically admissible space (spacing, plant slots and node slots)?
2. Are any such columns also wet, lit and warm enough for a mature seed at the
   exact time germination runs? Report overlapping blockers, not additive causes.
3. When usable space exists, is a mature seed actually there? Separate no mature
   seed, failed landings, and openings consumed by earlier checks in the same step.
4. Does any living parent's scattering support include those columns? This is a
   geometric possibility, **not** proof of a flowering/affordable seed purchase,
   a likely RNG outcome, or viability after placement. Dormancy still applies.
5. Do the actual recruits survive a full day and produce day-surviving offspring?
   Include early deaths, end-of-run censoring and species/family loss.

An open-column step is a repeated temporal sample, not a distinct vacancy or an
independent trial. Seeds do not move after landing in this control. A missing
landing is not itself a counterfactual rescued plant.

## Implementation and acceptance

Make the existing caller-owned exact seed audit available to ordinary host
builds, while keeping it compiled out of Zephyr. Reuse the production germination
and dispersal functions. Do not add authoritative fields, callbacks, RNG draws,
device storage, or a second simulation implementation.

- Test ordinary versus audited stepping byte-for-byte, including all climates,
  sequential competition, cold/dormancy/expiry, invalid input and output errors.
- Verify all 129 daily hashes per trajectory against the retained seasonal panel;
  reconcile every successful attempt with its saved child's birth and ancestry.
- Validate step completeness, stage/seed accounting and exact outcome/blocker
  consistency; expiry is not a failed eligibility check.
- Repeat the first-seed seasonal runs (both layouts/policies), requiring identical
  trace bytes and analysis. Freeze source, binary and parent-report digests.
- Render the fixed first-seed rainfed/adaptive pair at days 16 and 128 through
  the production renderer and verify daily world hashes and framebuffer CRCs.
- Retain compact summaries and a report in Git; compressed raw traces stay in
  ignored artifacts. Run native/default, opt-in research and firmware checks.

## Treatment boundary

Use the diagnosis to propose one isolated change with predeclared matched
before/after gates. Wider scattering is a candidate only if the observed spatial
opportunities support it; older nonseasonal results were mixed. No automatic
promotion, forced coexistence, smart placement into vacant sites, new hazard,
training run or repeated parameter search follows this read-only pass.
