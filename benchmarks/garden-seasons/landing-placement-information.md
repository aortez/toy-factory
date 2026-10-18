# The shading offspring had only one clear landing site

The placement decision behind the [winter shading case](landing-winter-light.md)
had only one reachable, spacing-clear column: **column 0**. A light-aware ranking
of clear choices alone could not have picked a different site. The child then
survived for **86.11 garden days** and made nine seeds, but none germinated before
the recorded horizon. Its seed checks reveal a later lack of usable space.

This is the completed [frozen offline audit](landing-placement-information-protocol.md)
of the fixed-order, dawn-guard, focal-root, capped-uptake pair without wicking.
It reconstructs parent 20's purchase at tick 652260 and child 29's establishment
and family history through tick 983040, or garden day 256. It uses saved traces
only: no new simulation, training, ecology rule or host/device default change.

## What the placement policy actually receives

This seed-placement policy is a hand-written spacing filter, not the neural
growth controller. The captured [callback contract](../../src/garden_agent.h)
supplies the parent ID, existing random draw, logic tick, origin column,
dispersal trait, candidate columns and their spacing-blocked bits. Its immutable
context holds configuration and an optional audit destination, not the world,
neural weights or growth memory.

The inputs reveal that column 0 is three columns left of this parent. They do
not provide canopy geometry, measured light, shadow ownership, soil resources
or the future child's morphology. The clock could support time or season
inference; it is not itself a view of neighboring canopies.

The [selector](../../sim/garden_landing_placement.c) keeps an unblocked original
choice. Otherwise it redirects to a clear choice using the same random draw,
retaining repeated entries caused by edge reflection. If every choice is
blocked, it keeps the original. The API can return any valid choice index,
including a blocked site; it cannot return an arbitrary destination or a valid
WAIT/decline-purchase action. An error aborts the step rather than vetoing a
purchase. This call occurs after reproduction eligibility and before child
genome mutation; the resulting seed costs the usual 48 energy and 24 water.

## Why the existing selector chose column zero

At the purchase, the four stored plants have bases at columns 3, 12, 8 and 20.
All four are living. Parent 20's recorded dispersal trait is zero, giving these
fourteen signed choices after reflection:

```text
0, 6, 7, 7, 8, 8, 9, 9, 10, 10, 11, 11, 12, 12
```

Only choice index 0 passes the three-column spacing requirement. Globally,
columns 0, 15, 16, 17, 23, 24, 25, 26 and 27 are spacing-clear, but none besides
0 is in this parent's support. The blocked-choice bitmap is 16382. Enumerating
the selector's fourteen repeating random residues returns column 0 every time.
This is forced by the enabled spacing filter, not by the API or hardware.

The actual random draw was not recorded in this capture. The selected index
can be deduced as 0, but the records cannot distinguish an original choice of
0 from a blocked choice redirected there. No random draw is invented.

The later post-step site map also marks column 0 open. It marks eight of the
nine globally spacing-clear columns fully open; column 17 fails light. These
are instantaneous germination diagnostics, **not callback inputs or predictions
of an alternative child's future canopy**. Plant bases and stored slots do not
change during reproduction, so the spacing reconstruction still describes the
callback's stage.

There is no same-tick control purchase to pair with this one. The control
parent's next purchase is at 652320, landing at column 9 and eventually expiring.
Other births already differ between the two worlds, so neither purchase is an
isolated alternative-site experiment.

## The selected seed established without a resource failure

The seed receives eight checks, one every fifteen logic ticks. The first seven
fail only dormancy. At tick 652380, its first mature check has moisture 13,
light 154, four stored plants, 106 nodes and no cold condition. It passes every
gate and becomes child 29. The moisture and light thresholds are 12 and 80;
there is also room for the new plant and its four initial nodes.

The admission receipt excludes the newborn from its own spacing/capacity test;
the post-step population then includes it. This was successful establishment,
not an immediately shaded or resource-starved seedling.

## The child contributed survival but not another generation

Both histories contain parent 20's earlier child 22, which lived 54,300 ticks
and made no seeds. The broader world additionally contains child 29, still
alive after 330,660 ticks at the horizon. One garden day is 3,840 logic ticks.

| Recorded family outcome through day 256 | Control | Broader dispersal |
|---|---:|---:|
| Descendants born | 1 | 2 |
| Descendants living at the horizon | 0 | 1 |
| Total descendant lifetime in garden days | 14.14 | 100.25 |
| Parent 20 seed purchases | 21 | 15 |
| Descendant seed purchases | 0 | 9 |
| Grandchildren born | 0 | 0 |

Child 29 accounts for the additional 86.11 observed days and all nine descendant
seeds. Five expire; four remain pending when the record ends. Pending seeds are
censored observations, not proven future failures. Across the whole family,
the control has one germinated, fourteen expired and six pending seeds; the
broader world has two germinated, fifteen expired and seven pending seeds.

The survival and seed production are real contributions, even though sustained
renewal is not demonstrated. Conversely, fewer parent purchases in the broader
world are not an isolated causal cost of child 29: the whole histories differ.
The parent's earlier diagnosed nine unpaid energy units do not by themselves
establish that rejecting this child would improve family fitness. No scalar
fitness score or relaxed harm threshold is introduced here.

## Later seeds could not reach a usable vacancy

Child 29's nine seeds receive 54,392 checks: 63 dormant checks, five expiry
records and **54,324 mature site checks**. Every mature check fails spacing at
the actual landing, and none has even a spacing-clear alternative within that
seed's recorded dispersal support.

| Blocker at the actual seed site | Mature checks |
|---|---:|
| Spacing | 54,324 |
| Eight plant slots occupied | 54,323 |
| Insufficient light | 45,994 |
| Insufficient moisture | 8,085 |
| Cold | 7,928 |
| Node capacity | 0 |

These blockers overlap; do not sum them. The checks are repeated observations
of nine seeds, not 54,324 independent trials.

Only one mature check finds any globally spacing-clear or fully open column:
at tick 660120, with seven plant slots occupied, column 27 is open. Child 29's
trait is minus one, and its reflected choices reach only columns 2 through 8.
Its actual seed at column 6 fails moisture, light and spacing. The next step
adds the eighth plant at column 26; every subsequent mature check of these
nine seeds finds full plant capacity and no globally spacing-clear column.

Thus a more informed local ranking would not fix these recorded opportunities
either. This does not predict what another dispersal rule, waiting action or
future environmental disturbance would do.

## Turnover and usable vacancies follow up

The [completed vacancy-sequence audit](landing-vacancy-sequence.md) now traces
all 32 capped and broader-dispersal worlds. All 153 post-onset deaths are
reclaimed within 0.20–0.25 garden days; broader worlds have 89 replacements in
newly clear columns, and 26 of those replacements produce a germinated child.
The selected family's stall therefore is not the whole panel's story. Physical
vacancies, free plant slots and viable seed landings remain distinct, with
several final openings censored by the day-256 horizon.

The [broader-dispersal report](landing-late-dispersal.md) already counts full
populations and scarce late openings. The follow-up adds the sequence from
death through decomposition and site recovery to a reachable seed opportunity,
not another endpoint census. Earlier [vacancy work](landing-vacancy.md) also
found later natural turnover under different rules; a quiet window must not
be mistaken for permanent occupancy.

Do not infer a canopy exclusion zone, purchase veto, larger plant pool or wider
support from this case. Successful offspring competing with their parents are
not automatically a defect. No experimental rule is qualified or promoted.

## Verification and reproduction

The extractor reads both worlds' complete stand, adult and reach traces,
checking their hashes, headers, clocks and footers. It reconciles all 174 seed
purchases and 1,039,250 seed checks against the original ledger and saved reach
summaries. The portable result keeps ten context rows per world, the complete
family summaries, and 54,400 detailed check rows for the selected seed and its
child's nine seeds.

All 23 new tests pass on the host and through Docker. They cover reflection
aliases, selector ambiguity, spacing boundaries and dead occupants, stage
timing, complete seed histories, ancestry, pending outcomes, provenance and
receipt tampering, and fresh-output protection. All four related offline CTest
entries pass. Portable verification and independent raw extraction pass with
process launching forbidden; a repeated complete export is byte-identical.

Implementation identities refer to the captured executable's pinned source
archive, not to whatever runtime C files a future checkout contains. Analysis
source hashes remain checked. Previous artifacts are preserved.

The [690 KiB portable result](landing-placement-information-results.json.gz)
and checked-in inputs support offline reanalysis without the large raw bundle.
See [tool instructions](../../docs/garden-landing-tools.md#seed-placement-information-and-family-renewal)
for export, portable verification and independent raw verification commands.
The original bundle is `artifacts/garden-landing-late-dispersal-v1`.

| Artifact | SHA-256 |
|---|---|
| Frozen protocol | `1b8a6a6d648334a0eafb1ad7a8468c98c6b185ddd3888d5cb3bdeb17367dc482` |
| Original raw manifest | `4a94df9dcc4f53c980e3631b58dc3fd853c3f03a68678d335127ab09f7a83001` |
| Portable result | `e856950a8dc4d7dfb2d6b8871d306a8cebe60e159d55da00d52c814516951c48` |
