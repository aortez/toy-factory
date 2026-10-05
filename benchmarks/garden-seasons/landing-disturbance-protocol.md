# Single death and vacancy response protocol

Status: **FROZEN before treatment runs**. Test whether the seven late surviving
replacements can use a real vacancy, following the [reproductive-access audit](
landing-reproductive-access.md). This is a response-to-disturbance diagnostic,
not a new fitness score, training environment, scheduled hazard or promotion.

## Fixed worlds and event

Use all five worlds containing the seven `censored_replacements` in the saved
day-288 follow-up. Pin `landing-followup-results.json.gz` at SHA-256
`b13ce089efa12b431f48a35499be93e7cf7af83a636006b2898b283762e12336` and the
reproductive audit at
`1db7c619a4acd770e36dccfd108c8d75369c9dbcd3153b98273f51b6024b5f39`.
All worlds share weather seed `f7ee4528` and the captured model. Keep their
existing fixed/rotating order, daylight/dawn guard, root-allocation probe,
capped uptake, broader dispersal and wicking settings exactly unchanged.

Treatment occurs **after** the ordinary day-256 step and its observer records,
at logic tick 983040. Select the living non-focal plant with the earliest birth
in that saved boundary census; break ties by lowest lineage ID. Do not select
using future treatment performance or substitute another target on failure.

| Order and existing guard/allocation/arm | Focal identities | Target | Column |
|---|---|---:|---:|
| fixed / dawn / focal / wide-cap-wick | 30 | 17 | 13 |
| fixed / dawn / ordinary / wide-cap | 33, 34 | 17 | 13 |
| rotating / dawn / focal / wide-cap | 33 | 20 | 3 |
| rotating / dawn / ordinary / wide-cap | 33, 34 | 17 | 13 |
| rotating / daylight / focal / wide-cap-wick | 30 | 18 | 9 |

All targets were born at tick 590640. Require the named target alive and older
than one day. Call the existing host-only environmental death primitive for
its column, first verifying it selects exactly that one living plant. Record
the event separately from natural deaths and exports. Keep the dead tissue,
slot, spacing exclusion and normal decomposition. Death discards that plant's
stores with no refund. Keep all soil, seed inventory, RNG, survivor state and
landing-memory history. Recompute derived light as the existing primitive
does; later ordinary steps update observations normally. Reject invalid requests
without changing the run, lifetime ledger or output event.

Removing a plant changes shade, resource competition and capacity together.
This is not an isolated capacity effect. There is no additional killing,
gardener, irrigation, seed eviction, relocation, mutation, reset, model change,
weather change, pool enlargement or extension beyond the existing day-288 limit.

## Fixed runs and verification

Twenty full runs from tick zero through 1105920: five unchanged traced controls,
five traced treatments, five exact traced treatment repeats, and five untraced
treatments with endpoint frames. Complete and validate all controls before any
treatment. Controls must match the archived full results, frame bytes and all
four ordinary traces. Treatment and repeat must match each other exactly;
untraced treatment must match result and frame, excluding only absent trace
files. Failed runs remain evidence and stop collection; never silently resume
or replace a world.

Retain stand, adult, direction and reach traces in the same windows as the
follow-up. Treatment reach rows through the event and the common boundary
records must match the old control. Before-event run/world hashes must equal
the saved day-256 identities. Reversing only future events and the explicitly
recorded post-observation death must recover the old day-256 ledgers. Tag the
new option and target in run identity. Unsupported builds reject it explicitly.

Archive sources, models, binaries, build settings, invocation records, hashes,
complete ledgers and frames. Preserve earlier artifacts. Native/CLI tests cover
transactional failures, identity, no-action parity, preserved seeds/memory/RNG,
delayed reclamation, environmental-death classification and observer neutrality.

## Measurements and decision

The primary interval is (256,288], ecology ticks 983055..1105920 in steps of 15.
Boundary traces are pre-event anchors, not post-death observations. Validate
the full clock and seed inventory; distinguish death from actual slot release
and a temporary release from an opening still visible after germination.
Reconcile all births, natural deaths, the single imposed death, purchases and
seed fates to ledgers. Report vacant-column refill, delay to reclamation and
first germination, including births elsewhere that consume the available slot.

For each fixed focal parent, report survival, readiness, ordered bank access,
new seed purchases and all children germinating after the event (including
from pre-event seeds). Separate no purchase, pending/expired seed, germination,
one-day establishment, 16/32-day survival, child reproduction and established
grandchildren. Keep horizon-censoring explicit; a single refill is not sustained
renewal. Track every new recruit, including posthumous children of the killed
plant, and new natural losses among pre-event survivors. Compare resource
shortfalls and terminal living/stored/node counts; no favorable total erases a
regressed individual world.

Reuse ordered bank/resource accounting where applicable. Exclude the imposed
death from natural-mortality comparisons. Existing lifetime totals include
all deaths and must not be relabeled natural. Preserve simultaneous seed gates,
complete viable-seed checks and exact purchase costs. Freeze portable evidence,
a concise per-world report and paired endpoint gallery. Verify raw re-extraction
and portable reanalysis without running the simulator. The earlier 12/16 harm
failures remain unresolved; this experiment cannot promote any rule.
