# Matched landing recruitment trace v1

Read-only, retrospective diagnosis of the retained five-seed evaluation panel.
No training, reselection, score/ecology change or firmware deployment. Preserve
the six live finalists (single/multi, search seeds 6d697833/34/35), using their
exact archived TGL2 bytes. All research ecology flags remain OFF.

Choose two cases per search from the saved renewal audit, before new traces:

- Steady: first lexicographic case with a new-finalist persistent-zero window
  containing a purchased seed's child that died before first-day confirmation.
- Seasonal: first lexicographic case where both old/new have positive late
  renewal confirmations and the new finalist has fewer confirmations.

This fixes steady cases to crowded/7d3b7bde for /33, rainfed/5aa2b327 for /34,
crowded/5aa2b327 for /35; the seasonal case is crowded/940cfdc4 for all three.
Replay both old and new in each: twelve 192-day worlds. Selected informative
cases are not independent samples or a fresh performance/generalization panel.
Keep the regressing /33 and successful seasonal recruitment, not only failures.

For each world, require exact JSON equality with tracing disabled and a second
traced replay, including model, world/cache fingerprint, lifetime and seed
ledgers. Reconcile against the frozen historical result and score. Historical
GSP1 live/live identity differs from ordinary GLR1: validate live/live explicitly
and compute the GSP1 fingerprint from GLR1 rather than ignoring state identity.
Repeat raw trace bytes exactly. Independently replay the frozen bundle.

Trace every sequential seed check, including age, all simultaneous blockers,
moisture, light, slot/node counts and hypothetical open-site count. Expiry occurs
before checks: its zero resource fields are NOT measurements, and it contributes
no blocker sample. Match by immutable parent and purchase tick, not bank slot.
Verify every expected sample and resolved fate against the complete ledger.
Separate dormant from mature checks; retain overlapping masks, never assign a
single causal blocker. Pending seeds remain right-censored, not failures.

Trace each descendant from its birth through birth+one Garden day inclusive,
or natural death / horizon if earlier. Use immutable lineage IDs after slot
compaction. Five resource snapshots occur after uptake, maintenance, seed
admission, growth and reproduction. Actual unsaturated uptake/overflow receipts
are retained before death-only compaction. Existing maintenance-death receipts
supply final upkeep and discarded stores; live upkeep is the stage difference.
Birth endowments, upkeep, growth, reproduction and discarded stores must balance
exactly for both resources. Absence at pre-birth stages is null, never zero.
Dead plants contribute no further first-day samples. Report post-step roots and
active leaves as morphology, not pre-uptake illumination measurements.

Retain full per-seed histograms and first-day trajectories, grouped summaries
and all contrary outcomes. Highlight seeds expiring in (62,190] and offspring
born in (62,190], matching the previous late-window scope; distinguish complete
seed lifetimes from two-day scoring follow-up. Blockers can identify failed
checks but do not predict a rescue from removing any one rule. Resource receipts
can identify shortage/spending, not prove an alternative policy would survive.

Fresh output only; incomplete files invalidate a run. Freeze protocol, pinned
inputs, Python sources, binary and build flags. Guard source/build/input hashes
through collection and verify all artifacts on independent replay. Test stage
boundaries, rollback, no-clobber, complete sample inventories, trace-disabled
equivalence, corrupt/incomplete trace rejection and portable evidence. Stop
after reporting what was learned and proposing the next bounded change.
