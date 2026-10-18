# Trace the first additional shrub family loss

## Question and fixed case

Explain the resource deficit and recruitment barriers in the first additional
Search 1 shrub loss identified by the [offline family diagnostic](leaf-population-losses.md).
The case is weather `58d7d6ca`, rainfed layout, founder 2 at column 13.
This is a reproducible diagnostic selection, not a representative population
sample or a training evaluation.

Run each frozen uniform policy (`initial`, `s1-g3-c4`, `s2-g3-c1`) through
day 256, once with tracing disabled and once enabled. Keep W2 growth, recurrent
memory, seasonal weather, seed lifetime, and all ecological rules unchanged.
No gardener, intervention, search, model selection, or device deployment.

## Data and interpretation

Capture complete state/history and native pixels at days 0, 32, 192, and 256
in both members of each pair. Require exact traced/untraced matches, exact
matches against the original captures through day 192, and the same history
prefix as the original day 1376 run at every checkpoint.

Trace founder 2 and all descendants by persistent lineage, not compacted plant
slot. Normalize the existing audit receipts with the frozen checked maintenance
reader. Retain per-lineage daily energy/water income, saturation losses,
endowment, upkeep due/paid, construction, seed spending, repair spending,
death discard, and starting/ending reserves. Also retain leaf condition,
repair counts, shortage counts, and maximum stress. Daily intervals are
`(day * 3840, (day + 1) * 3840]` logic ticks.

Retain actual seed-check mask histograms per seed and per day, including the
subset with no living family member at that sequential check. Distinguish
expiry, which occurs before checks, from a zero blocker mask. Record light and
moisture ranges and the counts of checks at which each hypothetical mature site
is open. An open hypothetical site does not establish that a parent could have
placed a seed there. Trace entries cover attempted seeds; seeds purchased on
the final tick remain in the complete history but have not yet been checked.

Blocker bits, least significant first: dormancy, moisture, light, plant capacity,
node capacity, spacing, cold. Multiple blockers may coincide. Mask counts count
checks, not independent seeds, and must not be added as disjoint outcomes.
Energy conservation includes repair separately from construction; leaf condition
conservation separates new tissue endowment from restoration.

## Bounds and failure handling

Six experiment calls total, at most two workers, 180 seconds per call, and
15 minutes for the six-call collection after preflight. Run one policy pair at
a time. Stop submitting after failure; retain partial outputs and the failure
receipt. No silent retry, substituted case, or expanded horizon.

Tracing allocates bounded host storage once: at most 4096 plant/day rows,
1024 attempted seeds, and 256 daily seed histograms. Exhaustion or invalid
receipts latch session failure and prevent successful publication. Reset disables
tracing. Ordinary sessions retain their existing horizon and allocation behavior.
Reject an experiment output larger than 24 MiB per call; do not emit per-tick
dumps. Existing directories, files, and symlinks must not be overwritten.

Before collection, run the seven host session/viewer suites and ten archive
preparation tests. Record source, frozen runtime, model, and executable identity.
After collection, verify every day's resource and leaf conservation, full
plant/day and seed-attempt coverage, ancestry, terminal outcomes, and paired
state/pixel equality. Keep all six calls and their captures in a compact archive.

## Decision after the trace

Separate observed accounting and gates from causal hypotheses. Repair spending
does not itself prove waste; a blocked seed does not establish that removing one
gate would permit recruitment. Use the trace to choose a narrowly scoped next
diagnostic or intervention, and discuss any ecological or training change first.
