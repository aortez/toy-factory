# Seasonal vacancy recovery protocol

Test whether the persistent descendant stands from the
[placement turnover audit](landing-placement-turnover.md) can recruit and
reproduce after one artificial opening. This is a fixed diagnostic, not a
turnover policy, training run or candidate promotion. Freeze this protocol
before collecting treatment trajectories.

## Fixed worlds and intervention

Use all six seasonal spacing-aware worlds from `landing-placement-results.json.gz`
(SHA-256 `c94d1d8e466dd0e81b399cf7416f353cb5533cb1e8288d33f17719097ef7fa82`).
Use the identical model bytes, `rainfed-crowded`, weather seed `940cfdc4`,
32-node shoot reservation, water-eligible arbitration and spacing-aware
placement. Gardener and irrigation stay off. No changed weather, costs,
germination gates, mutation, RNG draw, seed lifetime or memory reset.

Both arms run from tick zero through day 256 (983,040 logic ticks). Treatment
exports one living plant **after the ordinary day-158 step**, tick 606,720.
Choose the established plant nearest column 14 at that boundary; lowest
lineage ID breaks ties. Selection uses the frozen pre-intervention census,
not a treatment outcome. The fixed identities are:

| Model | Lineage | Column |
|---|---:|---:|
| Single /33 | 20 | 14 |
| Multi /33 | 26 | 18 |
| Single /34 | 17 | 12 |
| Multi /34 | 24 | 15 |
| Single /35 | 28 | 12 |
| Multi /35 | 23 | 14 |

Missing, dead or not-yet-established targets fail the run; never substitute
another plant. Require age strictly greater than one day so first-day
observations are complete before export. Control performs no removal.

Reuse the transactional host export: remove the named body and its stored
resources immediately, compact indices and refresh derived light. Preserve
soil, ordered seed bank (including the exported parent's seeds), RNG, clocks,
natural death/decomposition counters and survivor state. Historical landing
observations are not rewritten; the next ordinary ecology step captures new
conditions before policy decisions. This is not natural death or decomposition
and refunds no resources. Record removal separately in the lifetime ledger.
Removing a body changes shade, uptake and competition as well as spacing;
this is a recovery-after-vacancy test, not spacing in isolation.

## Measurements and decision

Keep the original renewal rule. Report credited exposure in the three windows
(158, 190], (190, 222] and (222, 254], with follow-up through day 256. Removal
ends occupancy/credit but never counts as a natural death. Retain all worlds,
not just successful gaps, and separate credit carried in from new confirmations.

Measure births, first-day survivors, natural deaths, bank supply and seed
blockers. For every child born after the intervention, record parentage,
first-day resource failure or confirmation, subsequent seed purchases, and
whether it has a first-day-surviving child of its own. Distinguish children
of the removed parent, births near the removed column (within two columns),
and recruitment elsewhere. Count post-intervention-born parents with confirmed
children, not simply extra offspring of old occupants. Report final-window
births and confirmations and the last birth to expose another static stand.

An opening without first-day establishment identifies a remaining recruitment
or resource barrier. Establishment without reproduction by replacements is
only a refill. Even a reproducing replacement does not qualify the ecology
without sustained final-window activity and later independent confirmation.
No favourable aggregate overrides an adverse individual world. There is no
automatic policy promotion or parameter search in this pass.

## Collection and verification

Twelve arms, each with three day-256 runs: combined recruitment/reach traces
and endpoint frame; exact repeated traces/frame; and an untraced frame run.
That is **36 full replays**. Capture days 158, 160 and 192 twice in each arm:
**72 additional checkpoint replays**, 108 experimental calls total. Endpoint
frames are already included in the full runs. No extra selected captures.

Require exact repeated JSON, trace bytes and framebuffer bytes, and observer
parity. Day-192 controls must match the archived complete placement results
and pixels. Compare both raw trace prefixes through the ordinary day-158
step, and the export's before hashes against that control checkpoint. Native
tests cover compaction, survivor memory, seeds/resources/counters/cache and
failure rollback; host ledger tests distinguish removal from natural death.
Record binary, source, build, model, protocol and artifact hashes in a fresh
no-clobber bundle. Incomplete runs remain failed evidence, never overwritten.
