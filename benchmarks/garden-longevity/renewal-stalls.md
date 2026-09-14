# Renewal stalls: seeds are produced, but descendant seedlings cannot establish

The two zero-credit broad-controller cases are **not sterile or extinct**.
During (62,94], their descendants produce **375 seeds; all 375 expire without
germinating**. Five founder-produced seedlings do establish. The stall is at
seedling recruitment, before first-day survival or the scoring ancestry check.
Qualifying renewal later resumes in both worlds.

This is a real failure to recruit descendant offspring during that interval,
but not evidence that these gardens cannot remain viable. A hard calendar-window
renewal gate would conflate unsuccessful recruitment in a crowded garden with
reproductive incapacity. Keep the candidate scores diagnostic for now.

[Frozen protocol](renewal-stalls-protocol.md) ·
[Labeled native gallery](renewal-stalls-gallery.md) ·
[Full timelines, parent funnels and resource observations](renewal-stalls-summary.json)

![Original and broad controllers at days 62, 78, 94 and 110](renewal-stalls.png)

Columns: days **62, 78, 94, 110**. Rows: seed `1824c139` original/broad, then
seed `4d5f9ee1` original/broad. All use fresh-2. These four trajectories were
selected because of the two known stalls, not as an unbiased model comparison.
The native images show mostly tall flowers in the broad worlds, versus more
branching ground-cover plants in the original worlds. They do not by themselves
prove reproductive health; the lifetime and seed records supply that evidence.

## Where the reproductive chain breaks

Seed-purchase cohorts below use (62,94] with outcomes followed through day 96.
"Descendant seeds" includes seeds from both established and not-yet-established
descendants at purchase; these subgroups remain separate in the portable data.
Full-cycle establishment and qualifying ancestry are checked separately.

| Controller / seed | Descendant seeds purchased | Descendant seeds germinated / fully confirmed | Founder seeds germinated / fully confirmed | Unchanged bounded renewal ticks in (62,94] |
|---|---:|---:|---:|---:|
| Original / `1824c139` | 132 | 1 / 1 | 1 / 0 | 57,390 |
| Broad / `1824c139` | 183 | 0 / 0 | 4 / 4 | 0 |
| Original / `4d5f9ee1` | 92 | 1 / 1 | 0 / 0 | 46,395 |
| Broad / `4d5f9ee1` | 192 | 0 / 0 | 1 / 1 | 0 |

Broad's 183 seeds split into 177 from already established descendants and six
from young descendants; its other 192 split 191/1. All expire. Thus this is not
only a scoring rule excluding otherwise successful grandchildren. There are
**no descendant-produced germinations to count** in either purchase cohort.
All five successful broad-controller seedlings have founder 5 as their parent.
They add first-generation plants, not another generation of replacement.

The original does better in this interval, but barely: only one qualifying
recruit in each matched world, despite 224 descendant seeds combined. This
environment is recruitment-limited for both controllers, not simply broken for
one controller or incapable of producing any offspring.

## The observed blockers are principally space and population capacity

The current native garden has a hard **eight-plant slot limit** in
[`garden_world.h`](../../src/garden_world.h). Germination separately checks
plant slots, node capacity, seed dormancy, surface moisture/light and plant
spacing in [`garden_world.c`](../../src/garden_world.c). These are independent
gates: having room in the 512-node pool does not imply a free plant slot.

Daily observations at days 62 through 94, inclusive:

| Broad world | Checks with eight living plants | Daily node range / 512 | Non-dormant descendant seed observations | Spacing blocked | Plant-capacity blocked | Moisture / light / node-capacity blocked |
|---|---:|---:|---:|---:|---:|---:|
| `1824c139` | 24 / 33 | 235–283 | 171 | 171 | 139 | 0 / 0 / 0 |
| `4d5f9ee1` | 33 / 33 | 270–305 | 165 | 160 | 165 | 0 / 2 / 0 |

These are **seed observations at daily samples**, not unique seed-fate counts or
fractions of elapsed time. Blockers can overlap. They do not prove that every
seed spent its entire life under the same blocker, but they directly identify
the constraints active at those samples. In the first world, spacing still
blocks sampled seeds when there is a spare plant slot.

Sampled mature flower descendants retain active leaves and flowers, usually high
water stores and little or no stress. More decisively, their paid-seed records
show reproduction continuing throughout the interval. The garden is not simply
waiting without reproductive organs or unable to afford any seeds. No extra
light/water cause is inferred from sparse resource snapshots.

There **are** openings: the broad worlds have four and one recorded patch deaths
during (62,94], respectively. So full capacity is not a blanket excuse that no
opportunities existed. The lineage competition, seed placement and timing of
those opportunities matter; all successful recruits in this interval happen
to come from the remaining founder. No counterfactual intervention was run to
isolate which placement or queue effect caused each failed seed.

## Both broad worlds recover later

| Broad world | Last pre-gap bounded credit expires | First later qualifying child | Full-cycle confirmation |
|---|---:|---|---:|
| `1824c139` | day 61.875 | child 25 of descendant 15, generation 3 | day 102.953 |
| `4d5f9ee1` | day 49.8125 | child 22 of descendant 14, generation 2 | day 96.8125 |

These are observed finite-horizon recoveries, not evidence of indefinite
sustainability. Both occur after further patch deaths. In the second world,
another descendant-produced seedling is born at day 95.152 but dies before
confirmation; child 22 then survives its full day. The timeline distinguishes
that early failure from the later successful recruitment.

In (94,126], each broad world germinates three seeds purchased by established
descendants; three and two children, respectively, survive confirmation. The
score's long zero period therefore does not mean permanent lineage sterility.
Older established descendants were alive and producing seeds while outside
the score's 32-day credit age limit.

Calendar boundaries remain important even for a simple zero-credit gate. The
original `4d5f9ee1` world has no bounded-age credit from day 49.0625 until its
next qualifying confirmation at day 81.921875—about **32.86 days**—yet earns
positive credit in the selected (62,94] window. It should not be labeled
universally continuous just because this particular window includes its recovery.

## What this means for the next decision

**Do not install "zero renewal in a calendar block = nonviable" as a hard gate
on this evidence.** Keep true extinction distinct from crowded, attempted but
unsuccessful reproduction. Likewise, do not reward seed production alone: these
375 unsuccessful seeds illustrate why births and survival still matter.

The next useful design is an opportunity/recovery diagnostic: when a disturbance
creates a usable opening, how long until a descendant-produced offspring takes
it and survives? A free plant slot alone is insufficient if spacing or the local
seed site blocks recruitment. Record those opportunity constraints separately,
without automatically forgiving a controller's own poor placement or competitive
performance. Discuss that definition before adding another score or changing
capacity, dispersal, mortality, seed lifetime or the training environment.

No reliability gate, new fitness, ecological adjustment, model selection or
training was introduced here. These selected cases do not establish that the
broad controller is better than original. Their existing primary and candidate
scores remain unchanged.

## Verification and reproduction

Four unchanged trajectories, **40 native processes**: four population-inspector
runs through day 192, 16 native image replays plus 16 independent reset/repeats,
and four headless day-192 anchors. All 16 frames match byte-for-byte on repeat;
all match their same-tick census hashes. All four anchor hashes/counts match the
original saved experiment. The 1,109 distinct census ticks collectively match
the saved lifetime/seed counts and living IDs; duplicate disturbance ticks use
their final post-disturbance sample.

The inspector source and entire C/header source set match the frozen coverage
snapshot; its build configuration matches exactly. The frozen production replayer
is copied without modification, and inspector/model/input hashes are pinned.
Native code and firmware are unchanged. The renderer retains its own process
and checks that capture did not mutate the world.

**11 new unit cases and nine relevant pure-Python CTests pass.** Tests cover
parent classification, confirmation/death boundaries, per-window follow-up,
future-event exclusion, recovery, original counters, post-patch census matching,
frame identity/CRC, sampled blockers and the fixed process budget. The broader
native regression suite was not rerun; the 40 matched diagnostic runs are the
new native evidence in this task.

Collection after initial verification/copying: **40.93 seconds**, 105 artifact
files, **21.35 MiB**. Frozen manifest SHA-256:
`7e2b0136cfc43babd2d8ffd9442fefe6239eaa3a5ce1a73e588df58ddcb7c1ca`.
Portable export includes all four timelines, seed funnels, structural/resource
observations, 16 PNGs, a gallery and post-collection daily blocker summaries.
Raw census logs and independent framebuffer repeats remain in the local bundle.

```sh
# Replay exactly the fixed diagnostic budget into a new directory.
python3 -W error sim/garden_renewal_stalls.py \
  --output artifacts/NEW-renewal-stalls

# Reanalyze/check existing evidence and portable files, without new native runs.
python3 -W error sim/garden_renewal_stalls.py \
  --output artifacts/garden-renewal-stalls-v1 --verify \
  --check-export benchmarks/garden-longevity/renewal-stalls
```

Collection requires the original coverage bundle and matching inspector build;
`--baseline` and `--inspector` can locate them elsewhere. Export to a fresh prefix
with `--verify --export NEW_PREFIX`; neither frozen evidence nor exports are
overwritten.
