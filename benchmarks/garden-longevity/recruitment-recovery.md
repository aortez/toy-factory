# Recruitment recovery: two zero scores, very different opportunities

The [fixed four-trajectory diagnostic](recruitment-recovery-protocol.md) is
complete. Both broad-controller worlds had zero descendant recruitment during
(62,94], but one had **785 usable ecology steps**, the other only **12**.
Descendant seeds never occupied an eligible actual location in either interval.
This is not a germination-order bug, nor a uniform inability to recover.

[Exact event/seed data](recruitment-recovery-summary.json) ·
[Previous matched native gallery](renewal-stalls-gallery.md) ·
[Earlier lifetime findings](renewal-stalls.md)

## What counts as an opening

The exact native trace separates four stages:

| Stage | Meaning |
|---|---|
| Death | Plant is dead, but still occupies its slot, nodes and spacing. |
| Reclamation | Decomposition removes the remaining tissue and releases allocation/spacing. |
| Usable site | A hypothetical mature seed at that column passes all ordinary gates immediately before germination. |
| Successful recruitment | A real seed germinates there and the child survives its first full day. |

Across the 26 hit events in these four trajectories, reclamation takes roughly
**0.219–0.25 simulated days** after death. It does not guarantee immediate
eligibility: surface light/moisture, other plants' spacing and remaining global
capacity still matter. There are 256 ecology steps per simulated day.

These are queries of the production germination path, not a second simulation
or hypothetical rule relaxation. The existing native seed-attempt observer
records each seed's conditions **at its sequential visit**, including changes
caused by earlier successful seeds in the same step. The world/site replays match
its hashes. Source: `seed_germination_blockers`, `update_seed_bank`,
`update_decomposition` and `plant_spacing_is_available` in
[`garden_world.c`](../../src/garden_world.c).

## The original weak interval, now measured at every check

All rows cover **(62,94]**, exactly 8,192 ecology steps. Open steps are repeated
observations with at least one usable column before germination, not distinct
vacancies, independent trials, or a measure of how long an actual seed was ready.
“Descendant” combines established and young seed parents at the attempt tick;
the underlying JSON retains those classes separately.

| Controller / world seed | Open steps | Open steps without a birth | Founder births | Descendant births |
|---|---:|---:|---:|---:|
| Original / `1824c139` | 222 | 220 | 1 | 1 |
| Broad / `1824c139` | **785** | 781 | 4 | **0** |
| Original / `4d5f9ee1` | 17 | 16 | 0 | 1 |
| Broad / `4d5f9ee1` | **12** | 11 | 1 | **0** |

Every open step has mature seeds somewhere in the bank. The broad worlds are
not waiting for a globally empty or wholly dormant bank. Both originals produce
one qualifying descendant recruit; the original first world's founder child
dies before full-day confirmation. All five broad founder children survive.

The two broad worlds contain 45,369 and 47,608 mature descendant seed checks,
respectively. At **725 and 31** checks, some eligible column lies within that
seed parent's dispersal support as recorded at seed creation. Those observations
involve **12 and three distinct descendant seeds**, respectively. None has
landed on an eligible actual column. Support is only a spatial upper bound—not
a probability, a new random draw, or permission to move an existing seed.

There are **zero sequentially displaced descendant checks** in either weak
interval: no mature descendant seed starts the loop at an eligible actual
location and then loses eligibility to an earlier seed's germination. Thus the
zero births here are not explained by that particular processing-order effect.
Competition over earlier steps and the resulting occupancy still matter.

Full-cycle tracing also supplies the phase information missing from daily
snapshots: low light blocks many checks outside bright conditions. The prior
daily censuses always sampled the same sun phase. The open-step figures above
already include the actual light gate. Broad has no moisture or node-capacity
blockers in the traced mature checks; spacing and global plant slots remain
important overlapping constraints. These counts are not per-seed causal shares.

## Three concrete timelines

### An opening remains unused for a while

Broad `1824c139`, patch 8:

- Day **64.828125**: plant 19 dies at column 27.
- Day **65.074219**: reclamation frees its slot and the local site becomes usable.
- Day **66.96875**: founder 5's child 20 germinates at column 27.
- Day **67.96875**: child 20 completes its first day alive.

The first usable-site-to-birth delay is **1.894531 days** of calendar time;
eligibility need not be continuous through the nights. This is successful garden
refilling by a founder, not another generation of descendant replacement.

### An opening is consumed quickly by the founder

Broad `4d5f9ee1`, patch 11:

- Day **80.125**: descendant 18 dies at column 19.
- Day **80.347656**: its occupied allocation is reclaimed.
- Day **80.84375**: a local site becomes usable.
- Day **80.886719**: founder 5's child 20 germinates at column 18.
- Day **81.886719**: child 20 completes its first day alive.

Only **11 ecology-step intervals** separate first eligibility and germination;
the 12 observed open steps include both endpoints. This accounts for every
usable pre-germination step in the broad world's entire weak interval. A long
calendar period with no qualifying renewal did not provide a long usable window.

### The same controller can recover immediately at a later opening

Broad `4d5f9ee1`, patch 13:

- Day **94.90625**: plant 16 dies at column 0.
- Day **95.152344**: the corpse is reclaimed. Another descendant-produced child
  germinates elsewhere at column 27, but dies before its first-day confirmation.
- Day **95.8125**: the local column-0 site becomes usable; descendant 14's child
  22 germinates **on that very first eligible step**.
- Day **96.8125**: child 22 survives confirmation and qualifying renewal resumes.

Both births and their different outcomes are retained. In the other broad world,
qualifying recovery still occurs at day **102.953125**, as previously recorded.
Across (94,126], each broad world has three descendant germinations; three and
two, respectively, survive their full day. This is observed recovery, not proof
of indefinite viability or superior controller performance.

## Why this remains a diagnostic, not the next fitness formula

All **44 scheduled event intervals** in (62,126] are retained: 26 hit plants and
18 hit no living plant. Every hit interval eventually has a usable local site,
but not every local site is refilled before the next patch. Ordinary steps at a
patch's timestamp belong to the preceding interval; the patch happens afterward.
The final interval is censored at day 126, and each child gets only its own
first-day follow-up from the already-validated lifetime history.

Temporal event ownership is not causal attribution. For example, broad
`1824c139` loses its column-27 plant at day 76.098, but column 27 is refilled
after the next patch at day 80.125 has killed a different plant. Original worlds
also refill older holes while a newer local vacancy remains empty. A new plant
elsewhere can consume the global eighth slot and close another otherwise usable
site. A per-patch success/failure label would discard this coupling.

The NN's current action contract controls growth (wait, extend, finish-tip), not
direct seed aiming. Seed location comes from the parent's base, inherited
dispersal trait and deterministic PRNG in `dispersed_seed_column`. Controller
choices affect reproduction and population structure indirectly. These runs do
not isolate what fraction of placement failures a different NN could prevent.

**Recommendation:** retain surviving descendant renewal as the outcome of
interest, and keep opportunity/recovery traces as explanatory diagnostics.
Do not divide fitness by available-site time or turn a calendar gap into automatic
failure on this evidence. Such a ratio would mix inherited placement, crowding,
shared capacity and controller behavior, and could favor very few opportunities.
If we need a hard reproductive-reliability requirement, discuss a separate fixed
replacement challenge with explicit opportunity and follow-up conditions first.
That challenge, any new gate, and adoption of a candidate fitness remain unimplemented.

## Verification and reproduction

**12 unchanged native processes**: four ordinary every-step world censuses and
four seed-site censuses through day 126, plus four exact audits of (62,126].
The 129,028 world/site ticks match hashes; all **65,536 exact seed steps** match
the ordinary worlds and pass sequential accounting. All **730 available previous
censuses** through day 126 match exactly, including post-disturbance samples.
Seed identities/fates and all births match the original day-192 lifetime ledgers.
Patch boundaries and complete schedules match across observers. The native
C/header source set and build configuration match the prior frozen evidence.

**13 new unit cases and ten relevant pure-Python CTests pass.** These cover
event ownership, corpse occupancy, local footprints, hypothetical versus actual
opportunities, sequential competition, dormant/expired entries, parent classes,
confirmation/death boundaries, no-hit intervals, first birth versus first survivor,
and malformed/truncated traces. The existing sequential-validator fixture is also
exercised. The broader native regression suite was not rerun: these matched
diagnostic runs are the native evidence for this task.

Collection and first deterministic reanalysis took **89.68 seconds**, excluding
initial verification/copying and final verification: **36 artifact files / 69.99
MiB**. Manifest SHA-256:
`c25a9fa6fd9fd734b60db84dfc48729d6494bf5300aea41a9573d49be2650e23`.
The portable JSON contains all event timelines, births and first-day outcomes,
exact grouped exposures and individual seed exposure records. Raw compressed
traces remain in the local bundle. No new screenshots were needed; the earlier
16-image gallery remains the visual context.

```sh
# Exactly the fixed diagnostic budget, into a new directory.
python3 -W error sim/garden_recruitment_recovery.py \
  --output artifacts/NEW-recruitment-recovery

# Recheck immutable traces and the portable export; no native execution.
python3 -W error sim/garden_recruitment_recovery.py \
  --output artifacts/garden-recruitment-recovery-v1 --verify \
  --check-export benchmarks/garden-longevity/recruitment-recovery-summary.json
```

`--baseline` and `--build` locate matching inputs elsewhere. Use `--verify --export
NEW_JSON_PATH` for a fresh portable copy; existing exports and bundles are never
overwritten. No simulation rules, fitness, controller weights, firmware/device
state, model qualification, commit or push were changed in this investigation.
