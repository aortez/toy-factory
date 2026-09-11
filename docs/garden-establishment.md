# Garden seed establishment audit

Replay every candidate/control world in a completed experiment, plus adaptive
if it is not already a control, with an observational seed/site census:

```sh
make host-audit-garden \
    GARDEN_AUDIT_BUNDLE=artifacts/garden-night-growth-probe \
    GARDEN_AUDIT_OUT=artifacts/garden-establishment \
    GARDEN_AUDIT_ARGS="--late-cycles 8"
```

The input [experiment bundle](garden-experiments.md) is never modified. Use a
new output directory. This audits the same model, reset, weather, policy and
horizon, and requires every saved timeline checkpoint to match. It is not a
new fitness function, placement algorithm, or ecology experiment. Test-labeled
bundles are rejected for this exploratory workflow.

## What it observes

`garden-inspect --seed-sites` emits a compact census every ecology step (15
logic ticks / 0.25 seconds), without policy-bid logs. It includes plant ancestry,
seed age and placement, sun/rain, surface moisture/light, and germination
blockers at every one of the 28 soil columns.

The read-only `picosystem_garden_world_seed_sites` API reuses the actual
germination and dispersal helpers. It has caller-owned output, no world storage,
and does not consume random numbers. Each site is queried for a hypothetical
mature seed, so dormancy is excluded from the site mask and retained for actual
seeds. A parent's dispersal bit set enumerates the support of its current rule,
including boundary reflection; it is not a probability distribution or a draw
from its RNG. Dead parents have no future dispersal support.

The analyzer identifies a seed by its parent lineage and creation tick, derived
from age. At most one seed per parent is created in an ecology step. It follows
all seeds from birth, reconciles disappearances with expiry age or new plant
ancestry, and checks aggregate creation/germination/expiry counters. Pending
seeds remain pending at the horizon. Cohorts with a full lifetime of potential
follow-up (256 ecology steps / 64 seconds) are reported separately from recent
births, even if a recent seed has already germinated.

## Interpretation limits

These are **post-step snapshots**. Within each ecology step, seed checks happen
after rain, soil flow, plant uptake and maintenance, but before subsequent
growth, reproduction and the final light update. The census cannot reconstruct
the exact conditions just before every germination decision. A seed may
germinate without any earlier post-step snapshot showing its site as ready;
the tests explicitly cover this. Outcomes are exact; opportunities are
observational upper bounds, not guaranteed germination or offspring survival.
Ready seeds are removed by germination before the census, so remaining-bank
observations are survivor-biased toward blocked seeds. Their blocker percentages
are not failure probabilities for all seeds that were born.

For mature seeds the audit separates:

- **Actual:** its current column meets all site requirements.
- **Anywhere:** at least one column meets them, regardless of dispersal range.
- **Reachable:** such a column lies in the parent's dispersal support recorded
  at seed creation. This can require a different landing choice and knowledge
  of later conditions; no seed is actually moved.

Simultaneously open sites are independent alternatives, not a claim that all
could be occupied together. Blocker histograms retain overlapping moisture,
light, spacing, plant-capacity and node-capacity failures. Exactly one blocker
describes a hypothetical instantaneous single-requirement relaxation, not a
demonstrated improvement after changing that requirement.

Night (sun phase >=128), bright day (remaining phases with sun strength >=128),
and twilight are separate. Thus bright-day light failures cannot be explained
by the unshaded sun being below the current germination threshold of 80. Counts
are repeated observations, not independent seeds or trials. Whole-run and
preselected late-window summaries retain raw denominators.

## Artifacts and verification

`index.md` provides cohort comparisons and per-world, per-column opportunity
maps. `summary.json` retains aggregate histograms and trial references;
`analyses/*.json` retains every seed lifetime and per-trial counters.
`traces/*.jsonl.gz` retains every ecology census. The output freezes source,
inspector, scripts, model bytes, input reports/timelines and provenance hashes.
An incomplete audit has `failure.json` but no completed manifest. Source changes
during collection cause failure rather than mixed provenance.
Maps include extinct worlds too: open sites without any living parent or seed
are not evidence of successful reproduction. Use the conditional bank/cohort
metrics alongside the spatial view.

Reproduce the compressed census and analysis using the frozen executable:

```sh
docker compose run --rm firmware python3 \
    artifacts/garden-establishment/tools/garden_establishment.py \
    --verify artifacts/garden-establishment --case 01
```

Omit `--case` to verify all cases. `--timeout` bounds each native subprocess
(default 120 seconds). This uses the host build container, not the PicoSystem.
