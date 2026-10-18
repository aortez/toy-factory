# Seed purchases choose among blocked destinations

The purchase-time trace confirms that the contrasting shrub handoffs are not
caused by overlooking a free destination. Seven of eight shrub-family purchases
in days `[30,35)` have no spacing-clear reachable column. In those cases the
existing placement policy retains its original random fallback; the daylight
ranking cannot distinguish the blocked alternatives.

The combined-gates arm chooses a column blocked by two plants, including the
flower founder that remains alive through day 608. Two alternatives have only
one blocker. Their current resources do not distinguish future clearance:
all three relevant blockers have energy 252, water at least 508, and zero
stress when the seed is purchased.

## Comparison and parity

Eight fixed replays cover weather seed `9a903368`, the four existing repair
variants activated at tick zero, and diagnostics off/on. The
[protocol](leaf-population-purchases-protocol.md) fixes the narrow observation
window and the day-608 horizon. All 88 saved checkpoints (JSON and raw pixels),
all eight final histories and canonical states, and all four resource traces
match the previous [from-start panel](leaf-population-gates-panel.md) exactly.
Logging off/on also matches exactly. No policy, ecology, model weights,
training objective, or firmware defaults changed.

| Repair variant | All species purchases | Shrub-family purchases | Shrub purchases with every destination blocked |
|---|---:|---:|---:|
| Unchanged | 10 | 3 | 2 |
| Light | 9 | 2 | 2 |
| Condition | 8 | 2 | 2 |
| Both | 7 | 1 | 1 |

These are four trajectories, not eight independent ecological trials. The
logging repeats check instrumentation parity.

## The terminal purchase with both gates

At day 34, founder 2 buys a seed from column 13 with dispersal trait zero.
Its six active choices are `[8,18,7,19,6,20]`. The existing draw is
3,695,362,768; modulo six selects index 4, column 6. No spacing-clear option
exists, so both the ordinary placement and daylight policy retain that choice.

| Reachable column | Current spacing blockers by lineage | Blocker count |
|---|---|---:|
| 6, selected | Flower founder 1; shrub child 13 | 2 |
| 7 | Shrub child 13 | 1 |
| 8 | Shrub child 13; flower child 14 | 2 |
| 18 | Shrub child 11; ground-cover child 12 | 2 |
| 19 | Shrub child 11; ground-cover child 12 | 2 |
| 20 | Shrub child 11 | 1 |

The flower founder's current age is 34 days. Shrub children 11 and 13 have
recorded ages of 797 and 754 ecology ticks, approximately 3.11 and 2.95 days.
All three are unstressed and nearly full of energy and water. The younger
shrubs later die around day 55, while founder 1 survives the entire replay.
Those later deaths are retrospective labels, not information supplied to the
observer or controller. The actual seed expires at day 66 without germinating.

Columns 7 and 20 would each require fewer current blockers to clear, but this
trace does not establish what a relocated seed would do. It would compete
with other seeds and could change later growth and occupancy.

## Successful seeds also start blocked

The light-only seed bought at day 31.09375 selects column 19, blocked solely
by ground-cover lineage 9. That plant is only 65 ecology ticks old, has energy
236, water 231, and zero stress. It looks healthy, yet later dies at day
62.84375; the seed germinates at 63.0625, just before expiry.

The condition-only seed bought by shrub child 10 at day 31.078125 selects
column 15. The exact roster reveals **two** current blockers: shrub founder 2
at column 13 and ground-cover child 11 at column 17. Both have zero stress;
their energy/water stores are 136/510 and 162/172. Child 11 dies at day
56.09375 and founder 2 at 62.78125. The seed germinates at 63.015625.

By contrast, the unchanged arm has two spacing-clear choices, columns 18 and
19, at its day-31.140625 purchase. Ordinary placement selects 18 and the
daylight policy changes it to 19. The seed germinates quickly, but that child
dies before establishment. A currently free site is useful, not sufficient
for long-term family survival.

Together these observations argue against banning blocked purchases or
assuming that the least healthy or oldest neighbor will vacate soon. They
identify a simpler observable distinction worth testing: how many occupants
must clear for a destination to become usable.

## Next bounded experiment

The [completed fallback comparison](leaf-population-fallback.md) tests this
proposal: it rescues the combined-gates arm but reduces renewal in two others.
The rule remains experimental.

Test a change only to the all-blocked fallback: prefer the reachable column
with the fewest current spacing blockers, retaining the existing draw for
tie-breaking. Leave clear-site behavior, prices, seed lifetime, and repair
models unchanged, and initially apply it only to the focal shrub family.

For example, cyclic tie-breaking from the combined arm's existing index 4
would choose index 5, column 20, instead of column 6. This rule uses no future
lifetimes, and does not refuse a seed purchase. It remains a hypothesis:
blockers can share environmental risks, and a single persistent blocker may
be worse than several short-lived ones. A fixed replay comparison must test
establishment and renewal, not just germination or occupied slots.

## Reproducibility

The evidence archive (`leaf-population-purchases-results.json.gz`, kept locally)
contains all eight native outputs, 34 purchase records, source snapshots,
preflight receipts, and the offline recovery record. SHA-256:
`2d94fda91c831ac484c906588d0c9db5f0400ee031093c7a2aff9ba532b2f24d`. The
native-call interval was 43.559223 seconds with two workers. Preflight passed
all seven host suites in 117.41 seconds and all ten preparation tests. Strict
compiler warnings and undefined-behavior instrumentation were enabled.

The first offline validation failed because the frozen late-dispersal build
reserves fourteen destination slots but only six are active during this
window. The native trace correctly contained six destinations followed by
eight zeros; the parser incorrectly expected a six-element array. The fix
validates the full padded shape and excludes padding from reachability.
No native call was rerun. The original attempt remains intact; the archive
retains its failure record, original files and hashes, and the corrected
validation source separately. No archived code is executed during verification.

```sh
python3 -B sim/experiments/leaf_population/population_purchases.py unpack \
  benchmarks/garden-seasons/leaf-population-purchases-results.json.gz \
  artifacts/new-purchase-evidence
```

The native observer owns bounded storage, borrows the live callback context,
and makes no per-step allocations or additional RNG draws. Tests cover window
boundaries, one-time forwarding, capacity exhaustion, allocation and callback
failures, reset, output errors, and state parity. Python checks independently
reconstruct spacing and active destinations, reconcile every purchase with
the complete seed history, and test archive round-tripping and recovery
record tampering.

All 89 analysis tests pass; the complete analysis suite takes about 40 seconds.
