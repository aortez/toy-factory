# Exact seed checks: missed landings and consumed vacancies

The [fixed eight-run audit](seed-attempts-protocol.md) is complete. Read-only
tracing now observes the **actual sequential germination checks**, not just
the later site map. Every observed state and final native frame matches the
[previous crowded diagnostic](recruitment-sites.md). No ecology, policy, model,
seed schedule or authoritative state layout changed.
Progress is recorded on [issue #30](https://github.com/aortez/toy-factory/issues/30#issuecomment-5649378426).

The useful distinction is now explicit: some openings are successfully consumed
within a step, while many others persist without a viable seed landing. This is
not evidence that germination ignores eligible seeds or loses opportunities to
growth earlier in the same step—**germination runs before existing-plant growth**.

## What was added

`src/garden_seed_audit.h` exposes a host-maintenance-only step wrapper. Its
caller-owned observation buffer is 468 bytes on the tested host build, bounded
to eight seed visits. No callback, global observer, heap allocation, extra RNG
draw or world field is introduced. The embedded-C conventions guided the bounded
ownership and error/state-preservation checks; the new header rejects default
and Zephyr builds. Core hooks compile out of the device/default configuration.

For each visit, the trace records parent, age after increment, location, species,
generation, nodes/plant slots, moisture/light, blockers, hypothetical mature-seed
sites at that exact moment, outcome and newborn identity. Expired seeds are
removed before checking eligibility and explicitly separated from failed checks.
Inventories bracket decomposition/maintenance, germination, growth and reproduction.
Within a step, a successful seed can block a later seed by consuming nodes, a
plant slot, spacing, or surface water; the analysis checks that sequence.

The narrow `toy-factory-garden-seed-attempts` executable supports the two frozen
neural policies, rain-fed layouts, selective leaf maintenance and the existing
patch schedule. It replays normally until a requested start tick, then observes.
It is not a second ecology implementation. The Python audit reconciles its output
against saved native worlds/sites and rejects identity, ordering, accounting,
outcome and completeness discrepancies.

## Closing-window results

Same eight cases, drainage off, model `dc5e849d`, 192-day horizon. Observation
covers days 160–192: 8,192 ecology steps per run. These previously selected cases
are diagnostic comparisons, not held-out qualification.

“Open before” is a **sampled step** with at least one eligible hypothetical
mature-seed column just before germination. It is not a distinct vacancy: the
same opening can recur for many steps. “Missed” additionally has mature seeds
undergoing checks but no germination. The final column counts seedlings born on
steps whose **post-step** map has no open column anywhere.

| Capacity / seed / schedule / policy | Open before | Missed | Germinations | Born despite no post-step opening |
|---|---:|---:|---:|---:|
| 256 / b61837dc / fresh-4 / baseline | 88 | 81 | 8 | 4 |
| 256 / b61837dc / fresh-4 / reserve | 91 | 90 | 1 | 0 |
| 256 / b61837dc / fresh-1 / baseline | 82 | 78 | 4 | 0 |
| 256 / b61837dc / fresh-1 / reserve | 141 | 134 | 8 | 3 |
| 512 / b61837dc / fresh-1 / baseline | 675 | 658 | 17 | 11 |
| 512 / b61837dc / fresh-1 / reserve | 273 | 262 | 11 | 6 |
| 512 / c7f54e18 / fresh-1 / baseline | 3 | 0 | 3 | 3 |
| 512 / c7f54e18 / fresh-1 / reserve | 27 | 18 | 9 | 9 |

Across 65,536 observed ecology steps there are 523,645 seed visits: 2,012 expire
before checking, 14,497 are dormant checks, and 507,136 are mature checks. There
are **61 germinations in 59 steps**; two steps produce two seedlings. All fully
eligible checked seeds germinate. Of 1,380 steps with an opening, **1,321 have
mature seeds but no successful landing**; none lacks mature seeds globally.
These repeated checks/steps are not independent seeds or failure probabilities.

**36 of the 61 germinations occur on steps ending with no open column.** The
512-node c7f54e18 baseline is the clearest example: all three observed openings
are consumed and disappear from the post-step census. This resolves the earlier
“zero sampled openings, yet three births” observation without changing the world.

The exact bright-day blocker measurements remain close to the earlier snapshot
measurements. In the 512 adverse baseline → reserve pair, spacing appears on
93.6% → 96.3% of mature checks, light on 71.1% → 77.5%, surface water on
62.1% → 77.0%, plant slots on 27.8% → 47.2%, and nodes on 0% → 0%.
These overlap. Actual bright-day openings fall 609 → 270 steps, versus 601 → 265
in the post-step maps. Observation timing explains missed transient openings,
but does not erase the underlying difference between those two trajectories.

Counts, phase-separated windows, blocker histograms and every successful check
are retained in [the exported summary](seed-attempts-summary.json). Offspring
survival/durable-parent results are unchanged and remain in the prior report;
more germinations alone is not qualification.

## The fixed 46-node vacancy, now observed directly

The protocol retained the earlier 256 / b61837dc / fresh-4 / reserve close-up:
ticks **721,650–722,670**, inclusive, 69 ecology samples. Ordinary decomposition
releases 46 nodes. Before growth closes the four-node seedling gate:

- 492 mature checks occur. **None is node- or plant-slot-blocked.**
- 457 include spacing; 263 include light; 65 include insufficient surface water.
  These overlap. The 35 checks without spacing are blocked by light alone.
- Some column is eligible on 65 steps. All 65 have mature seeds, but none at an
  eligible actual location. There are no successful checks.
- Six old seeds expire and six new seeds are produced during this window; it
  is not only a static bank waiting with no fresh landings.
- Existing-plant growth allocates 43 nodes, leaving only three free at the end.
  The prior trace subsequently shows all 46 freed nodes recaptured by incumbents.

Thus the missed opportunity is confirmed at the decision points, not inferred
from an after-the-fact picture. All sixteen closing-window instances where growth
closes the node gate occur after germination checks on steps with no birth.
Reserving nodes could extend a future window, but would not make those already
blocked seed locations viable on the same step. No counterfactual survival claim
follows from these measurements.

## Proposed next experiment—not implemented

A useful single-variable test is **8 versus 16 seed-bank slots**, initially on
the same four 512-node runs with frozen policies. That leaves node storage,
eight plant slots, spacing, dispersal, lifetime, weather and mortality rules alone,
while testing whether more simultaneous seed locations use existing openings.
The 256-node pool has a separate hard bottleneck, so it should not be the first
place to interpret this as a general remedy.

This is a hypothesis, not a demonstrated improvement. A larger bank can increase
parental reproduction spending, alter RNG trajectories and increase crowding or
offspring deaths. Compare actual opening use, parent energy/water costs, eligible
day survivors and durable parents—not merely seed volume or births. If sustained
renewal does not improve, do not promote it. Discuss/approve the experiment before
changing the ecological capacity; no gardener or smart seed relocation is proposed.

## Verification, provenance and reproduction

All **113 CTests** pass across default, maintained 256/512, and drained 256/512
builds (33 + 24 + 24 + 16 + 16), with strict host warnings/UBSan, formatter checks
and default golden hashes. New native fixtures exercise capacity boundaries,
expiry versus dormancy, sequential competition, raw thresholds, invalid inputs,
unchanged output on error and byte-for-byte tracing neutrality over 18 days.
Synthetic parser fixtures cover successful sequential checks; the small native
reference-model smoke case has no seeds, so it separately exercises empty-bank,
prefix, identity, stage and truncation handling. The real eight-run audit covers
all 61 native successes and all mature/expired checks against frozen references.

The eight runs match **65,544 saved world/site hashes**, all 240 original patch
records (including the unobserved prefix), seed identities/order, newborns and
inventory changes. Newly built ordinary replay hashes, frame CRCs and raw RGB565
bytes match all eight frozen final frames. The native contact sheet is identical
to the [prior paired screenshot](recruitment-sites.png); duplicate repo images
are unnecessary, and all new captures remain in the bundle.

Bundle: `artifacts/garden-seed-attempts`; all 87 artifact digests verify.
Manifest SHA256:
`0615e91b550b20ce60050f76b6bce5d7beef8902123ebbeaa9053e0e5c37eacb`.
The original source snapshot has 345 files. This report, compact export and
read-only review helper are post-collection artifacts.

```sh
docker compose run --rm firmware cmake --build artifacts/build-host-leaves-256
docker compose run --rm firmware cmake --build artifacts/build-host-leaves-512
python3 sim/garden_seed_attempts.py \
  --baseline artifacts/garden-crowded-recruitment \
  --build-256 artifacts/build-host-leaves-256 \
  --build-512 artifacts/build-host-leaves-512 \
  --output artifacts/garden-seed-attempts
python3 benchmarks/garden-longevity/review-seed-attempts.py \
  --reanalyze --output artifacts/seed-attempts-review.json
```

Output directories/files must be new. The reviewer verifies digests and can
reconcile all frozen traces again without executing a simulator. Audit code
changed, but ecological behavior, weights and defaults did not. No device flash,
training experiment, commit or push was performed.
