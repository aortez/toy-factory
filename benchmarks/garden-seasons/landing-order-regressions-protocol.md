# Reproduction order regression audit protocol

Diagnose the completed rotation comparison using saved evidence only. This is
a retrospective investigation of known regressions, not an independent
qualification panel or another intervention. There are zero new simulation
runs, training runs, parameter trials or device writes.

## Inputs and selection

Pin `landing-order-results.json.gz` at SHA-256
`65d240d896f7f6aeb014212fed502479b69e135b921f26d4a288e84b41cc4f32`
and the original bundle manifest at
`9075e770e5005c14ff1e2824626eedf013c3952acd0d7b04eab953809e5296f4`.
Keep all six controllers and both contexts in the summary. Focus detailed
diagnosis on S34 vacancy, S35 control and the unsuccessful early parent in
M33 control, as selected in the preceding report. Keep fixed and rotating
arms, including positive, negative, censored and quiet outcomes.

## Questions and accounting

Find the first changed ordered buyer list after day 158 in each pair. Join
those purchases to their seed positions and eventual child outcomes. Check
the immediately preceding and purchase-step raw observations where available;
do not equate different runs' lineage numbers after divergence. Matching
pre-purchase observations are narrower evidence than a complete world-state
snapshot or proof that one purchase explains every later difference.

For all births in (158,190], report birth seed, parent, column, first-day
outcome, seed production, children and available death-resource receipts.
Trace the observed release and refill sequence leading to S34's fixed early
survivor, and show what the rotating run actually does at those same ticks.
Retain all early seedlings rather than just the eventual survivor.

For the closing period (222,254], separate purchases, germinations, first-day
deaths, confirmations and unresolved follow-up. Include seeds carried into
the period and follow recorded outcomes through day 256. Also report births
after day 254 so an unresolved late seedling is not called a failure. Inspect
the ancestry and seed supply of S35's lost closing confirmations without
inventing matched replacement plants or attributing absent births to death.

For M33's early rotating parent, audit every otherwise-eligible missed opening,
actual rank, earlier buyer, released seed and resulting purchase. Verify bank
conservation, all simultaneous production gates and 48-energy/24-water fees.
Equal time at each rank is not equal access at openings. Opportunity to buy
does not establish where an unpurchased seed would land or whether it would
survive.

## Portable evidence and limitations

Export exact raw stand and resource rows for the three focused pairs at each
seed purchase/exit, plant birth/death and otherwise-eligible opening recorded
between days 158 and 218, plus the immediately preceding ecology sample.
Select the union of ticks across both arms, retaining the boundary sample.
Pin the full source trace hashes, preserve every selected field and order,
and independently validate the sparse event rows. Re-extraction must match
exactly; no-clobber outputs and offline recomputation must be supported.

The full ledger ends at day 256 but detailed resource/germination observations
end at day 218. Explicitly mark unobserved late resource causes and germination
blockers; expiry alone does not identify a blocker. Preserve the original
data and prior screening decision. Add regression tests for event selection,
ancestry, endpoint boundaries, censoring, resource debits, input corruption and
the actual adverse cases. Any new capture or allocation rule needs a separate
bounded proposal after this audit.
