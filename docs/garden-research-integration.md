# Garden research and viewer integration

This integration combines the recruitment and adult-resource research
checkpoints, the frozen repair-policy durability result, and the interactive
host viewer. It preserves the research evidence without promoting an experimental
ecology or a learned controller to ordinary host or PicoSystem defaults.

## What is ready

- Recruitment and adult-resource diagnostics, bounded intervention tools, and
  their positive and negative evidence are checkpointed. Start with the
  [recruitment guide](garden-recruitment-checkpoint.md) and
  [adult-resource guide](garden-adult-resources-checkpoint.md) for those historical
  review boundaries and validation results.
- Both frozen repair-policy finalists retain a mean renewal advantage through
  day 1376 in the [durability comparison](../benchmarks/garden-seasons/leaf-family-durability.md).
  They also retain more early family extinctions than the fixed wear-aware
  control. Neither finalist is selected as a replacement default.
- The [research viewer](garden-research-player.md) rebuilds the authenticated
  frozen sources and models from committed evidence. It supports pause, exact
  stepping, accelerated playback, reset, screenshots with complete state records,
  and read-only family highlighting.
- The README includes a native 240-by-240 populated Garden capture. Family
  highlighting affects the viewer only; saved captures keep the original pixels.

The viewer does not execute archived binaries or need historical experiment
directories. Ordinary `make host-play` and the firmware remain separate from
this frozen research runtime.

## Review and checks

Review the evidence conclusions and their limits first, then the
[playback contract](garden-research-playback-plan.md), the
[session ownership boundary](../sim/research_player/research_session.h), and the
[viewer and its tests](../sim/research_player/). The session adapter keeps mutable
simulation ownership private. Its family overlay follows ancestry through births,
deaths, pending seeds, and reused plant slots.

```sh
make check
make host-research-check
make host-player-check
make host-research-player-check
```

CI runs these checks in parallel firmware, research, and viewer jobs, including
the isolated late Garden configurations and alternate display firmware builds.
The viewer checks include strict C warnings,
undefined-behavior sanitization, actual SDL input events, source/model integrity,
capture safety, and highlighted/unhighlighted simulation and pixel parity.
The longer archived-replay check is documented in the viewer guide.

Some intermediate research working files remain local and are deliberately
outside this integration. They are not required to build or use the viewer.
Earlier reports retain their original experiment scope and historical validation
counts; they are not claims that every intermediate experiment is included here.

## Population validation and the next research question

The earlier comparisons put one candidate founder family against fixed-rule
resident families. The [population comparison](../benchmarks/garden-seasons/leaf-population.md)
now tests all-fixed-wear, all-Search-1, and all-Search-2 populations through day
1376 under the same deterministic weather without a gardener or new training.

All 48 calls passed, including exact rendered/unrendered repeats. Both learned
policies retain higher mean late renewal, and no garden becomes empty. They
also lose more founder families and species; Search 1 ends with one species in
four of eight gardens. The report retains every family and all 144 captures.
Opt-in population playback and timeline capture are available in the host viewer
and runner; defaults and the family-competition training objective are unchanged.

The [offline loss diagnostic](../benchmarks/garden-seasons/leaf-population-losses.md)
accounts for all 96 founder families without new simulation calls. Search 1
loses all shrub families; six of its eight additional losses occur after
descendants establish. Most terminal sequences combine a winter death with an
energy-shortage flag and subsequent seed expiry. The subsequent
[six-run trace](../benchmarks/garden-seasons/leaf-population-trace.md) preserves
state and pixels and identifies two bottlenecks in one matched shrub loss:
winter energy depletion with deteriorating foliage, and seeds continuously
blocked by spacing. The subsequent
[same-observation comparison](../benchmarks/garden-seasons/leaf-population-shadow.md)
records 27,906 observations without changing any state or pixels. Search 1
passes over 100 affordable founder repairs that fixed wear requests on identical
inputs, mostly before winter. Its light and condition/energy thresholds both
contribute. The subsequent
[eight-run intervention](../benchmarks/garden-seasons/leaf-population-gates.md)
restores each gate separately after a shared day-208 history. Restoring light
preserves the founder through day 256; restoring both also preserves an existing
descendant. Condition alone does not prevent extinction. No arm produces new
shrub offspring by day 256. The
[day-608 follow-up](../benchmarks/garden-seasons/leaf-population-gates-long.md)
separates the longer outcomes: light-only produces one established direct child;
both-restored produces six new shrubs, including two qualifying renewal children.
The combined arm also loses ground cover, while light-only retains all three
families. This is one selected case, not generalization evidence. An offline
check finds that seed `59818bc3` still has two shrub descendants at the day-208
switch, while the other two archived rainfed seeds have already lost that
family. The [second-seed comparison](../benchmarks/garden-seasons/leaf-population-gates-transfer.md)
repeats the survival benefit: light-only and both-restored keep shrubs alive,
while unchanged and condition-only lose them. Light-only earns more renewal
credit here, unlike the first seed; its new offspring later die, whereas the
combined arm retains a later-generation child. Neither arm demonstrates steady
replacement across all scoring windows. The subsequent
[from-start four-seed panel](../benchmarks/garden-seasons/leaf-population-gates-panel.md)
completes 32 calls through day 608, including families already extinct at the
old switch. Light-only earns 16 capped renewal credits out of 48, compared
with 2 unchanged, 10 condition-only, and 4 both-restored. Light-only and
condition-only each retain two shrub families; both-restored retains one.
Light-only has qualifying births in all six scoring windows on one seed,
but fails earlier than unchanged on another. Combining the gates is not
uniformly beneficial, and occupied plant slots do not imply ongoing renewal.
The [early-life diagnosis](../benchmarks/garden-seasons/leaf-population-gates-early.md)
uses the existing traces to identify the contrasting handoffs. Successful
arms germinate posthumous replacement seeds just before expiry; the combined
arm leaves a seed continuously spacing-blocked beside a surviving flower.
Both successful seeds were blocked at purchase too, so prohibiting blocked
purchases would discard useful seed-bank bets. The subsequent
[purchase-time trace](../benchmarks/garden-seasons/leaf-population-purchases.md)
confirms that seven of eight focal purchases have no free reachable site.
The combined arm's terminal fallback chooses two blockers, including the
persistent flower, despite alternatives with one blocker. Current resource
stores and stress do not clearly distinguish these occupants. Eight native
replays retain exact archived state/history/pixel parity; a padded-array
validation error was corrected offline without rerunning them. The
[fewer-blocker comparison](../benchmarks/garden-seasons/leaf-population-fallback.md)
then tests that placement fallback in sixteen fixed calls on the same weather
seed. It rescues the combined-gates family and earns six renewal credits,
but light-only falls from eight to four and condition-only from four to zero.
The condition-only relocated seed germinates at the same time as before;
its later lineage disappears. The [offline diagnosis](../benchmarks/garden-seasons/leaf-population-fallback-loss.md)
shows longer-lived first replacements but an early next-generation energy
failure, eight continuously spacing-blocked seed expirations, and a congested
eight-slot seed bank. The subsequent
[ordered reproduction trace](../benchmarks/garden-seasons/leaf-population-reproduction.md)
resolves eligibility at openings with four exact-parity replays: the final
shrub loses 16 opening-tick visits to earlier buyers while otherwise eligible,
but lacks energy seven times and water once on its eight visits with room
still available. Both runs buy 30 seeds in the window; the experimental family
gets three versus twelve originally. The subsequent
[step-budget trace](../benchmarks/garden-seasons/leaf-population-budget.md)
retains exact parity and shows that skipping the opening-step repair would
rescue none of the eight misses. Five follow a full energy store without later
repair spending; the other visits fall in energy/water income shortages. Each
regains sufficient resources only after the bank is full. The
[offline dawn comparison](../benchmarks/garden-seasons/leaf-population-dawn.md)
finds higher income on 96 of 104 matched days and healthier foliage at 95
day-end checkpoints in the successful original shrub, despite fewer leaves.
The subsequent [leaf-level trace](../benchmarks/garden-seasons/leaf-population-foliage.md)
reconstructs all 512 focal uptake steps exactly. During dawn, the original
has 1.84 times the light-band exposure but nearly equal light-weighted leaf
condition, collecting 159 versus 84 energy before the opening. Neither repairs
during that interval. Across the full day, exposure is nearly equal and
condition weighting differs. The [offline spatial map](../benchmarks/garden-seasons/leaf-population-exposure.md)
then localizes the gap to the lower canopy: about 83 versus 7 fractional
energy, while upper-canopy contributions are nearly equal. Eight of the
experimental shrub's lower leaves never receive productive dawn light, five
receive it but contribute nothing, and only two contribute energy. The
[dawn source trace](../benchmarks/garden-seasons/leaf-population-canopy.md)
then matches all 25,088 light-grid cells and preserves exact archived replay
parity. The original encounters only self-shade before leaving the left edge
or reaching the ambient floor; the relocated shrub also encounters founder
flower 1. Even without any shading at its recorded conditions, its lower leaves
contribute only 22.33 fractional energy versus the original's observed 82.75.
Neighbor shade also matters: omitting it yields a narrowly sufficient opening
budget under fixed recorded expenses, not a simulated outcome. The subsequent
[offline repair audit](../benchmarks/garden-seasons/leaf-population-repair-opportunities.md)
reconstructs all 512 decisions without new simulations. All 146 visits to the
relocated lower leaves fail only the light gate: nine leaves never reach the
required brightness, while six have short qualifying windows missed by the
selector. None is repaired, versus nine lower-leaf repairs originally. Next
observe a full 13-day selection-phase cycle before changing selection or
decisions; one day's missed windows need not persist. Different
positions, ages, and population histories remain confounded. Keep the
placement policy opt-in; the objective, ecological
rules, and defaults remain unchanged.

Environment qualification, joint growth-and-repair improvements, broader search,
and qualified device deployment remain follow-on work under
[issue #30](https://github.com/aortez/toy-factory/issues/30).
