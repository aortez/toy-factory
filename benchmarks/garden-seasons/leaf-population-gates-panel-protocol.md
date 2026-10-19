# Repair gates from the start across four rainfed seeds

Compare the four fixed repair variants from the first simulation decisions,
instead of rescuing selected surviving families after day 208. Include all
four original rainfed weather seeds, including the two whose shrub families
were already extinct at the previous switch. This tests the variants under
earlier growth and competition, without training or changing the objective.

## Fixed conditions and budget

Use weather seeds `58d7d6ca`, `9a903368`, `6b9c1a3e`, and `59818bc3`, the
rainfed layout, authenticated frozen runtime, and W2 growth policy and memory.
Only founder family 2 receives its assigned repair variant, including every
later descendant. All competitors retain Search 1 throughout. Apply the
variant from the first decision after tick zero until day 608. The initial
world and pixels remain common within each seed; later trajectories may differ.

Keep `none`, `light`, `condition`, and `both` exactly as in the
[earlier comparison](leaf-population-gates-transfer-protocol.md): restore
hidden unit 0, unit 1, or both from fixed wear into private Search 1 copies.
Do not change other weights, costs, growth memory, weather, ecological rules,
capacity, spacing, or seed lifetime. The native command is `--gate-panel`.

Run four seeds times four variants times logging off/on: 32 calls, two workers,
180 seconds per call, 900 seconds for collection, and at most 24 MiB of output
per call. Process one matched off/on pair at a time. Stop on a failed call or
verification mismatch, retaining attempts without retries or roster expansion.
Development tests and preflight are separate from the scientific calls.

Capture complete state, history, and native pixels at days 0, 32, 192, 208,
220, 222, 224, 256, 384, 512, and 608. Keep resource and seed-blocker traces
bounded to day 256, explicitly freezing them before continuation. Track full
ancestry, births, deaths, and seed outcomes through day 608.

## Identity and validation

Keep the `TGR1` envelope and exact derived model, with activation tick zero
encoded in both canonical state and JSON. Retain the seed in the simulation
identity. Existing day-208 commands, archive formats, and results remain intact.
Support only the four listed seeds for the from-start command; do not expose
arbitrary activation times or policies.

Authenticate the original population archive by SHA256
`3aae48b92ed9787f9dc1601052330cdbf96ed9d72f3d845e0b9932d50112af49`.
Every arm must match its initial state and pixels after explicit projection
of the validated intervention envelope. The unchanged arm must also match
the archive at days 32, 192, and 608, and match all retained history prefixes.
Keep full intervention identity in stored outputs, never the projection alone.

Require logging-on/off parity for state, history, and pixels at every capture.
Verify trace conservation and coverage against the day-256 endpoint, and
consistent history prefixes through day 608. Unlike late rescue, do not
require cross-arm parity beyond tick zero. Test routing at zero and day 208,
descendants and newborns, invalid times/seeds, allocation bounds, failures,
reset, earlier archive compatibility, and output preservation.

Snapshot the protocol, code, model bytes, binary digest, receipts, and
preflight results. Use strict compiler warnings, UBSan, and independent
offline validation. Archive verification must not execute archived source.

## Outcomes and interpretation

Use the unchanged first renewal window: births in `(192,576]`, six 64-day
subwindows, at most two qualifying children per subwindow, and age-32
follow-up through day 608. A qualifying child and its non-founder parent
must each survive their own first 32 days. Keep established-descendant
occupancy as the existing tie-breaker, not a new survival score.

Report each seed separately before summarizing across seeds. For each variant,
report shrub family status, founder survival, offspring births and age-32
outcomes, renewal timing and capped credits, young survivors, and generation
depth. Track flower and ground-cover status and population composition too.
Sum capped credits across the four seeds out of 48 for a descriptive panel
summary; do not treat the logging repeats as independent samples.

Compare against the unchanged arm within each seed. Persistent old stands,
brief reproductive bursts, and sustained replacement are distinct outcomes.
The four seeds are previously examined cases, not an unseen validation set.
Leave firmware, policy defaults, and the objective unchanged; choose any
further horizon, training, or deployment only after reviewing this panel.
