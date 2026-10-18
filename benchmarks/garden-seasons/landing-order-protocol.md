# Rotating reproduction order comparison

Test whether fixed plant-array order prevents established replacements from
reproducing in the current seasonal garden. This is a bounded host experiment,
not a new training objective or device policy. Freeze this protocol before
collecting experimental trajectories. More purchases alone are not success.

## Fixed panel and intervention

Use all six controllers and both control/vacancy worlds from
`landing-vacancy-results.json.gz`, SHA-256
`f49fa29abdefbc931bbe57937c90c33c2e51c35c573ce3709c9428cee46c6801`.
Retain the frozen model bytes, crowded layout, weather seed `940cfdc4`, seasonal
climate, water-eligible arbitration, 32-node shoot reservation and spacing-aware
seed placement. The existing vacancy arm removes its same predetermined adult
after day 158; the control has no removal. No gardener or irrigation is enabled.

For each of these twelve worlds compare fixed order with deterministic rotation.
The common prefix ends at logic tick 606720 (day 158), including any export.
Rotation starts on the next maintenance tick, 606780. On maintenance ticks
strictly after the boundary, start at
`((logic_tick - 606720) / 60) % current_plant_count`, then wrap once through the
existing array. Otherwise start at zero. Empty arrays have no visits. Retained
dead slots remain in the array and fail the ordinary death gate. Do not reorder
storage, germination or growth, or draw randomness to select the starting rank.

Keep eight seed slots, 32-day seed viability, 48-energy/24-water seed fees,
cooldowns, flowers and all other production gates unchanged. Every plant is
visited once per ecology step and its cooldown is decremented once. The new
host opt-in is independent of the older maintenance-research rotation; reject
conflicting configurations. Default identities and behavior remain unchanged;
enabled run identities include the rotation rule and switch tick.

## Collection and verification

Run to day 256. For each of the 24 trajectories collect a traced run, an exact
repeat and an untraced final-frame run: 72 full replays. Capture one additional
checkpoint at each of days 158 and 192: 48 checkpoint replays, 120 declared
experimental native calls total. Retain final ledgers and all 72 checkpoint/end
images. Final images, results and both trace streams must agree across repeats
and untraced runs. No unrecorded parameter search or additional training occurs.

Trace all plants' ordered production visits, original array indices/lineages,
growth and resource budgets from day 158 through day 218 inclusive, on every
ecology step. The day-158 row is before the post-step export; comparisons never
confuse that with the checkpoint after export. Require fixed results/checkpoints,
pixels, overlapping ordered visits and saved gate/resource summaries to
reproduce historical evidence.
Require fixed/rotating day-158 physical state, cache/model-derived base identity,
ledgers and pixels to match, allowing only declared configuration fingerprints.

Check actual visit indices against the independent rotation formula and the
unrotated array inventory. Reconcile bank releases/purchases, all simultaneous
eligibility masks, and exact 48/24 resource debits. Summarize eligible checks as
full at entry, lost to earlier buyers, or purchased, retaining ineligible checks
separately. Report rank exposure at genuine openings, not just rank exposure
over all ticks; a stateless schedule may alias with recurring release phases.

Archive source/build/binary/model/protocol identities and no-clobber artifacts.
Provide offline reanalysis of saved raw traces and portable summaries. Collection
failure leaves an explicitly incomplete bundle; verification never reruns native
worlds. Keep every model and adverse or quiet outcome in the report.

## Outcomes and decision

The early cohort is all births in (158,190], with first-day follow-up through
day 191 and lifetime seed/child outcomes through day 256. Report first-day
survivors, which of those reproduce, their seed outcomes, and which produce a
first-day-surviving child. The earlier five fixed-arm identities remain historical
descriptions, not matched individuals after divergence. Do not identify rotated
replacements by coincidentally equal lineage numbers.

Also report every post-day-158 birth, first-day death/survival/pending outcome,
new reproducing parents, natural mortality, final living population and the
existing (158,190], (190,222], (222,254] windows. Keep late confirmations/new
reproduction distinct from credit carried by old cohorts. Retain seed and child
right-censoring. Audit resource spending, stress and survival so additional
reproduction is not assumed affordable.

An access gain without surviving children is an allocation result, not improved
renewal. A promising ecological result needs surviving children from early
replacement parents without an aggregate loss of post-boundary reproducing
parents or closing-window confirmations; report all per-world regressions even
if these aggregate checks pass. If the schedule does not distribute actual
openings, report that limitation rather than claiming a fairer allocation rule
was disproved. Do not silently tune another schedule within this comparison.

Six models share one weather seed and are not independent environmental
replicates. Even a positive screen requires later multi-weather/longer-horizon
qualification. No rotation, capacity, viability, model or score change is
promoted by this experiment alone.
