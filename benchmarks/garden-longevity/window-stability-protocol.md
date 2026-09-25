# Late-window ranking stability: frozen offline protocol

Analyze existing complete lifetime/seed records only. No native simulations,
training, mutation, image captures, fitness/ecology edits, controller promotion,
commit or deployment. The primary (158,190] result remains primary regardless
of the alternative-window findings. Freeze these settings before computing them.

## Inputs and scope

Use the coverage bundle with manifest SHA-256
`a9142bff1570b3912b7f7d5dc71dbf4575c3db6df10249cf9b3539643abaf460`.
Verify its full provenance and unchanged original-score/replay checks first.
Copy its manifest, results, and the 32 selected review histories into a fresh
analysis bundle, with their original fingerprints. Do not modify any input.

Four frozen controllers: original generation 0 `dc5e849d`, broad generation 2
`556a5dd2`, broad final generation 3 `c7c1b31e`, narrow final `449c35fe`.
Generation 1 duplicates generation 0 and is not counted again. Use every existing
review condition: world seeds `eb300b12`, `1824c139`, `4d5f9ee1`, `fe1dd56f` crossed
with fresh-1 `e4d65e6f` and fresh-2 `17c29444`. These are already inspected review
worlds, not a fresh test set. No training-panel or rejected-mutant sweep is added.

## Five declared windows

Use equal-width 32-day main windows, with eight-day shifts:

| Main interval (start excluded, end included) | Terminal follow-up deadline |
|---|---:|
| (126,158] | day 160 |
| (134,166] | day 168 |
| (142,174] | day 176 |
| (150,182] | day 184 |
| (158,190] — original primary | day 192 |

Day = 3840 ticks; ordinary sampling step = 15 ticks. All full source histories
were collected through day 192 with their original closing-count start at day
158. Validate those full original records before projecting them to each earlier
deadline. Hide purchases/births after the deadline, future deaths and seed
resolutions; recount seed totals and closing counts for the new start. This is
a lifetime projection, not a reconstructed native world or a new world hash.

Then apply unchanged persistence-v2 scoring with each window's exact two-day
follow-up. Do not accidentally give earlier windows the day-192 terminal state
or use future seed outcomes. Independently compute the five-component key from
the full timestamps with a separate direct arithmetic implementation, and require
agreement for every projected score. Require full primary-score equality against
the saved coverage results. Never pool different windows into one fitness key.

## Comparisons and explanation

There are 32 histories × five windows = **160 offline world scores**, zero new
native trials. For every window report all four aggregate keys and five fixed
comparisons: generation-2/original, broad-final/original, narrow-final/original,
broad-final/narrow-final, broad-final/generation-2. Include per-condition
win/tie/loss, per-schedule aggregates, and leave-one-world-seed-out results,
removing both schedules of a seed together. Retain terminal tiers and ties.

For each controller/window report exact credited child counts, available
post-confirmation time, time lost after death, credited occupancy and purchase
cohorts using the existing explanation helper. For broad-final versus original
and narrow-final, compare adjacent-window per-child contributions within each
controller: leaving, entering and retained confirmation-cohort contributions.
Reconcile all changes exactly; do not match lineage IDs between controllers or
infer light/water causes from lifetime records.

Describe sign changes and stable/unstable comparisons without statistical
independence claims: adjacent windows overlap 24 of their 32 days, and all
windows derive from the same deterministic trajectories. Temporal differences
can reflect real changing ecology as well as cohort boundaries; this does not
identify stochastic noise or prove a particular objective change is needed.
No cherry-picked best window, retrospective model selection, cross-window
averaging, replacement primary result or new recommended fitness is produced.

## Validation and stop

Test all existing arithmetic fixtures, projection non-mutation and future-event
exclusion, exact confirmation/death boundaries, expired/pending seeds, finite
follow-up, direct-key parity, complete fixed panels, primary-score preservation,
and adjacent-window contribution reconciliation. Preserve source/protocol/input
hashes, complete per-world scores and attributable transitions; publish a complete
manifest only after deterministic reanalysis succeeds. Exports may be generated
after collection. Earlier-window screenshots are unavailable without replay and
will not be fabricated; the previous day-192 gallery remains the visual reference.

Stop after these five windows and discuss whether the evidence warrants a
separately designed training objective or evaluation protocol change. Do not
automatically start another search or choose the most favorable window.
