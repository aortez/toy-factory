# Established replacement and adult-loss tracing protocol

Explain two observations from the [vacancy assay](landing-vacancy.md): its
five established early replacements purchased no seeds, while 30 of the 31
old control occupants died close to day 200. This is a read-only follow-up,
not a new ecological treatment, scoring rule, training run or promotion.
Freeze this protocol before collecting the traces.

## Fixed panel and cohorts

Replay all six model pairs in `landing-vacancy-results.json.gz`, SHA-256
`f49fa29abdefbc931bbe57937c90c33c2e51c35c573ce3709c9428cee46c6801`.
Keep its exact models, weather seed, seasonal climate, spacing placement,
32-node shoot reservation, water eligibility, costs, RNG and day-158 export.
Gardener and irrigation remain off. Both arms start at zero and finish at
day 256. No targets are reselected.

Observe every plant from the first ecology step after day 158 through day
218 inclusive: ticks 606735 through 837120, in steps of 15. This captures
all five replacement births and the deaths of all 31 old control occupants,
including the late death of Multi /35 lineage 24. Retain the unsuccessful
Single /33 pair and all other plants, not just the focal successes.

Prespecified focal replacements, all born in (158,190] and surviving their
first day, are Multi /33 lineage 28, Single /34 lineage 26, Multi /34 lineage
25, Single /35 lineage 40 and Multi /35 lineage 29. The old-control cohort
is every living plant at the archived day-158 control census. These identities
come from frozen evidence, not the new traces.

## Measurements and interpretation

Record all growth proposals, shoot-reservation receipts, living bodies and
ordered reproduction visits, together with the existing five-stage resource
trace, soil water and climate. Measure flower formation and readiness,
growth depth and budget denials, all simultaneous reproduction blockers,
bank-only opportunities, purchases and daily resource budgets. Reconcile
each purchase with its lifetime seed ledger entry and the 48-energy,
24-water debit. Reconstruct the ordered bank independently from seed births
and exits; an end-of-step bank count is not the count seen by every parent.

For old control occupants and early replacements, report terminal shortage
flags, the final eight maintenance receipts, paid upkeep versus terminal
discard, and daily uptake, growth and reproductive spending. Inspect the
fixed day-196-to-200 interval and the later day-212-to-216 interval without
moving windows to favour a result. Keep removal distinct from natural death.

Multiple blockers can coexist. A low-numbered short-circuit gate does not
establish causality, nor does a drought flag alone establish water death.
Report trace evidence before proposing an intervention. No counterfactual
rescue claim without a paired experiment. Six controllers sharing one weather
seed do not provide independent weather replication.

## Collection and verification

For each of the twelve arms, run combined stand/resource traces with a
day-256 framebuffer, an exact repeat, and one untraced framebuffer replay:
**36 full replays, no extra checkpoints or selected images**. Require exact
JSON, framebuffer and trace repeat equality and exact full-result/endpoint
pixel agreement with the archived vacancy assay. Reuse its existing gallery.

Validate complete living/resource inventories, ordered seed purchases,
resource conservation, production masks and shoot-budget arithmetic. Test
newborn and corpse handling and traces crossing an export boundary. Preserve
legacy founder-trace output. Store source, binary, build, input, model,
protocol and artifact hashes in a fresh no-clobber bundle; retain failures.
The portable result contains all plants' summaries and focal death receipts;
the local bundle retains full and repeated raw traces for reanalysis without
rerunning simulation.
