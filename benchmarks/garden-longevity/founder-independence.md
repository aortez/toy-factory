# Founder exit: descendants persist and recruitment increases

The [fixed founder-independence challenge](founder-independence-protocol.md) is
complete. Every genuinely challenged world survived and produced new
descendant-born full-day survivors. Removing founders increased those recruits
from **58 to 137** in the matched panel. This supports founder independence over
the tested horizon, not indefinite viability or a recommendation to kill founders.

[All paired outcomes and provenance](founder-independence-summary.json) ·
[24 matched native screenshots](founder-independence-gallery.md)

## What was tested

Four frozen controllers, four existing review seeds and two existing patch
schedules give **32 pairs**. Both arms replay the same world through day 64.
The exit arm then kills living parent-zero founders through ordinary death,
retaining their corpses for decomposition. Soil, seeds, living descendants and
random-number streams are preserved at the boundary. Ordinary rain and scheduled
patch deaths continue in both arms through day 128, followed by two days of
seed/child follow-up. One simulated day is 3,840 logic ticks, or 256 ecology steps.

The schedules yield two distinct groups; they must not be pooled as 32 active
challenges:

- **Fresh-1: 16 no-op pairs.** No living founders remain at day 64. Their complete
  lineage/seed histories and existing scores are identical between arms. All
  retain established descendants at day 130 and produce further-generation links.
- **Fresh-2: 16 active pairs.** Each loses one to three founders, **37 total**.
  All end with seven or eight living plants at day 130, including established
  descendants. No challenged world becomes extinct or seed-only at the endpoint.

## Matched recruitment results

Only the **16 active fresh-2 pairs** appear in this table. A new recruit comes
from a seed purchased by a descendant in **(64,128]**, survives its first full
day, and satisfies the existing confirmed-parent ancestry rule. The two-day
follow-up closes every seed/child cohort. Founder-bank carry-in is excluded.

| Controller | Founders removed | New recruits, control → exit | Worlds with a further generation, control → exit |
|---|---:|---:|---:|
| Original (`g0`) | 12 | 8 → 34 | 1/4 → 4/4 |
| Broad G2 (`g2`) | 8 | 23 → 38 | 2/4 → 4/4 |
| Broad final (`g3`) | 8 | 11 → 29 | 3/4 → 3/4 |
| Narrow final | 9 | 16 → 36 | 1/4 → 3/4 |
| **Total** | **37** | **58 → 137** | **7/16 → 14/16** |

A further-generation link means one of those established post-split,
descendant-produced children becomes the parent of another confirmed child in
the same bounded seed cohort. This is a real parent link, not maximum generation
or an assumed match between IDs in divergent arms. There are **12 → 40** such
links. New-recruit counts improve in 15/16 pairs and tie in one; this is not a
controller ranking because initial founder occupancy and the resulting removal
burden differ across controllers.

The median time from exit to first qualifying new recruit falls from **18.387
to 2.043 simulated days**. Existing bounded renewal credit rises from 1,282,245
to 5,790,195 ticks in (64,96] and from 2,686,800 to 5,364,075 in (96,128]. These
are explanatory diagnostics, not a new training score.

More recruitment does not mean better survival for each seedling. Descendants
purchase **5,115 → 8,209** new seeds; **74 → 202** germinate, of which **58 → 137**
survive their first day. That survival fraction falls from **78.4% to 67.8%**.
The exit cohort has 65 natural first-day failures, compared with 15 natural and
one scheduled-patch failure in controls. Most seeds still expire without
germinating: 5,041 in controls and 8,007 after exit. No ecological rule was relaxed.

One founder-bank seed establishes after exit in original / `1824c139`. It is
kept in the carry-in cohort and does not count among the 137 descendant-produced
recruits. Its later offspring may qualify normally once it has itself survived
a day. The other founder carry-in seeds expire. Preserving the bank was part of
the challenge, not an unnoticed source of new founder credit.

## Limits and visual review

Broad final / `eb300b12` and narrow final / `eb300b12` each have qualifying new
recruits (seven and eight), but no further-generation link from that new cohort
within this window. Both retain established descendants. This is neither proof
of sterility nor grounds to extend the run after inspecting results.

The fixed screenshots cover all four controllers, fresh-2 / `eb300b12`, both
arms at days 64, 80 and 128. Immediately after exit, the dead founder stems remain
visible; later views show rearranged living plants in their place. The narrow
controller remains visibly dominated by tall flower forms. Images confirm the
intervention and changing structures; ancestry and recruitment claims come from
the ledgers, not appearance. All 24 frames are retained, including both cases
without a further-generation link.

Founder removal simultaneously removes seed producers and changes space, shade
and resource demand. The paired result shows the combined intervention's effect;
it does not isolate which change helped. Surviving descendant bodies, existing
soil, seed bank and the recurring disturbance schedule remain important context.
This is not recovery from an empty world, a sparse-seed startup test, or proof
that permanent mortality is desirable. These previously reviewed seeds are not
untouched test data; the 512-node host ecology is not device qualification.

## Recommendation

Keep founder exit as a **diagnostic**, not a training action, hard viability gate
or replacement for ongoing descendant-renewal measurement. The tested gardens
are not merely being kept alive by their original plants. In this panel, those
plants also compete with succeeding generations.

This closes a useful alternative explanation for apparent persistence. Return
to the bounded descendant-renewal objective discussion and a small, predeclared
training comparison; retain unchanged-world evaluation and this challenge as
separate reports. Do not optimize a score by inserting founder deaths, promote
a controller, or make further ecology changes from this result alone.

## Reproduction and validation

The accumulated investigation was checkpointed first as **`a1c419f`**, not
pushed. This experiment was subsequently checkpointed as **`bbb6307`** before
the [bounded-renewal training A/B](renewal-training.md). Its native helper is host-only,
uses ordinary mortality, checks targeting, and preserves caller state atomically
on error, following the embedded-C guidance. No `src/` simulation code, default
ecology, fitness, model weights or device firmware changed.

The optimized experiment build enables wide dispersal, water headroom, the
combined experiment, 512 nodes and leaf maintenance; drainage, enlarged seed
bank and seed reserve remain off. Assertions stay enabled with `-O2 -g -UNDEBUG`;
strict warnings and UBSan are enabled. Build with:

```sh
docker compose run --rm firmware cmake -S sim -B artifacts/founder-independence-build -G Ninja \
  -DCMAKE_BUILD_TYPE=RelWithDebInfo '-DCMAKE_C_FLAGS_RELWITHDEBINFO=-O2 -g -UNDEBUG' \
  -DTOY_FACTORY_GARDEN_WIDE_DISPERSAL=ON -DTOY_FACTORY_GARDEN_WATER_HEADROOM=ON \
  -DTOY_FACTORY_GARDEN_COMBINED_EXPERIMENT=ON -DTOY_FACTORY_GARDEN_LARGE_POOL=ON \
  -DTOY_FACTORY_GARDEN_LEAF_MAINTENANCE=ON -DTOY_FACTORY_SIMULATOR_SANITIZERS=ON
docker compose run --rm firmware cmake --build artifacts/founder-independence-build --parallel 4
python3 -W error sim/garden_founder_independence.py --output artifacts/NEW-founder-independence
```

The final **54 default and 49 experimental CTests pass**, including 12 Python
cases, C preservation/death/no-op/error/reclamation tests, host/firmware guards,
and native split/repeat/replay checks. All 32 current control ledgers match the
frozen original binary exactly and project to the prior saved full histories.
All exit pre-hashes and pre-intervention ancestry match their paired controls.

The declared **144 native processes** completed in **173.03 seconds**, with no
training. All 24 image replays reproduce pixels and hashes independently; 20
also match same-tick ledger hashes. Four day-80 control images match ledger
population/seed counts plus independent replay hashes; the unchanged control
tool has no checkpoint at that day. This weaker linkage is explicit in the
gallery. Reanalysis and portable-export verification pass.

Ignored local bundle: `artifacts/garden-founder-independence-v1`. It contains
frozen sources, models, configurations, binaries, full ledgers, native frames,
commands and timings. Portable outcomes and PNGs are in the repo; the ignored
raw bundle is not remotely available merely because these notes exist.
Manifest SHA-256:
`a6b435dea702978a7021f4d1440afe193aa312201d0fb7a544df2700ee53951e`.

```sh
python3 -W error sim/garden_founder_independence.py \
  --output artifacts/garden-founder-independence-v1 --verify \
  --check-export benchmarks/garden-longevity/founder-independence
```
