# Same-state landing decision trace v1

Freeze before collection. This is a read-only diagnostic, not training, a new
ecology comparison, controller selection, or evidence for promotion.

## Fixed panel

Retain all three current-only final training-selected controllers and all
sixteen conditions from the signal-content protocol: 48 live worlds, each
192 Garden days / 737280 logic ticks. Same ordinary 256-node, eight-plant,
eight-seed ecology; gardener/irrigation off; same weights, masks and seeds.
Pinned model, pilot summary and earlier validation-result hashes are inherited
unchanged from landing-signals-protocol.md. Final JSON, including full
lineage/seed ledgers and GLR1 run identity, must exactly match the earlier
current-mode validation run. No counterfactual decision advances a world.

## Sampling and interventions

Observe actual policy calls before all-tip arbitration. Record total root/stem
query counts by day, including unsampled queries. Record four 256-bin histograms
of raw common-source occupancy/water/light values across all valid common-source
queries. These are query-weighted distributions, not uniformly sampled terrain.

Prespecified samples are the **first root query and first stem query each day**,
where day index = floor((logic_tick - 1) / 3840). Do not force a query on days
without one. Maximum 384 samples/world, 18432 across the fixed panel. This is a
stratified diagnostic, not all queries or an unbiased query sample.
Keep unchanged common/candidate legacy tensors, incoming private memory,
source validity, raw landing packets, tip/plant-slot identifiers, constraints,
nonce, and the live proposal/next memory. Slots are not persistent lineage IDs.

At each sample evaluate sixteen one-shot probes. The first ten are exactly
the previous signal panel, in its original order. Add water-mid, water-low,
water-high, light-mid, light-low, light-high. Single-field probes replace only
that field at every valid landing source, with raw 128, 0, 255 respectively.
Keep source/body-role gating and all other inputs/memory fixed. In particular,
root inputs remain masked. The real sensor cache and legacy sensing stay live.
Do not add tuned constants, reordered values, extra fields or trained models
after reading the outcomes.

## Analysis and acceptance

Use the independent integer inference reference to reproduce every captured
native decision, including all sixteen probe results. Retain raw inputs and
native outputs, not just changed examples. Recompute hidden preactivations,
clipped hidden values and action logits from the unchanged model.

Report sampled action changes, priority changes, candidate-order changes when
both proposals extend, first-available-direction changes, next-memory changes,
and changes in any proposal/decision. Priority is not an action or a win in
arbitration. A direction rank does not guarantee acceptance or affordable growth.
Show root/stem denominators, early (days 0–31), middle (32–157), late (158–191),
and each condition/controller. Report clipping and sensor distributions,
without equating raw activation changes with behavior or fitness.

Repeat all 48 traces with one worker and require byte-identical traces and
complete native results. Freeze binary, sources, protocol and pinned inputs;
collection may not span source/build edits. Independently rerun the trusted
frozen bundle, compare outputs, and reanalyze every retained native sample.
Partial traces, missing footers, mismatched controls, bad native exits and
reference disagreements fail collection. Retain full portable records and
tests that reanalyze them. No new screenshots are needed for unchanged worlds:
link the prior fixed live-controller galleries, rather than imply new visual
evidence. Short old-seed unit fixtures do not select protocol outcomes.

Stop after this bounded trace and report. Immediate same-state sensitivity
does not establish useful environmental interpretation or long-run benefit.
Discuss the next training/representation choice, not another automatic search.
