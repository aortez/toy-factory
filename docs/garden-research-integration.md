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

## Population validation

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

### Single-case follow-up

The follow-up traces one matched shrub loss from family accounting down to
individual leaf decisions. Each report keeps its protocol and offline verifier;
its evidence stays local, and earlier versions of this narrative remain in git
history.

| Report | Finding |
|---|---|
| [Family losses](../benchmarks/garden-seasons/leaf-population-losses.md) | Accounts for all 96 founder families offline. Search 1 loses every shrub family; most end in a winter death with an energy-shortage flag, then seed expiry. |
| [Winter trace](../benchmarks/garden-seasons/leaf-population-trace.md) | One matched shrub loss shows winter energy depletion with deteriorating foliage, and seeds continuously blocked by spacing. |
| [Same-observation decisions](../benchmarks/garden-seasons/leaf-population-shadow.md) | On identical inputs, Search 1 passes over 100 affordable founder repairs that fixed wear requests, mostly before winter. Both its light and condition/energy gates contribute. |
| [Repair gates](../benchmarks/garden-seasons/leaf-population-gates.md) | Restoring fixed wear's light gate after day 208 keeps the founder alive through day 256; restoring the condition gate alone does not. No arm adds shrub offspring. |
| [Day-608 follow-up](../benchmarks/garden-seasons/leaf-population-gates-long.md) | Light-only adds one established child. Both gates add six shrubs, including two renewal children, but lose ground cover. |
| [Second seed](../benchmarks/garden-seasons/leaf-population-gates-transfer.md) | Seed `59818bc3` repeats the survival benefit; neither arm shows steady replacement across all scoring windows. |
| [Four-seed panel](../benchmarks/garden-seasons/leaf-population-gates-panel.md) | From the start, light-only earns 16 of 48 capped renewal credits, against 2 unchanged, 10 condition-only and 4 with both gates. |
| [Early handoffs](../benchmarks/garden-seasons/leaf-population-gates-early.md) | Successful arms germinate posthumous replacement seeds just before expiry; the combined arm leaves one spacing-blocked beside a surviving flower. |
| [Purchase sites](../benchmarks/garden-seasons/leaf-population-purchases.md) | Seven of eight focal purchases have no free reachable site. The combined arm's fallback picks two blockers where one-blocker sites exist. |
| [Fewer-blocker placement](../benchmarks/garden-seasons/leaf-population-fallback.md) | Preferring fewer blockers rescues the combined arm, from 0 to 6 renewal credits, but cuts light-only from 8 to 4 and condition-only from 4 to 0. |
| [Placement regression](../benchmarks/garden-seasons/leaf-population-fallback-loss.md) | First replacements live longer, but the next generation fails early on energy, and eight seeds expire spacing-blocked in a congested bank. |
| [Reproduction order](../benchmarks/garden-seasons/leaf-population-reproduction.md) | The final shrub loses 16 opening-tick visits to earlier buyers while eligible, and lacks energy 7 times and water once when its turn has room. |
| [Step budget](../benchmarks/garden-seasons/leaf-population-budget.md) | Skipping the opening-step repair rescues none of the eight misses; resources recover only after the bank fills. |
| [Dawn income](../benchmarks/garden-seasons/leaf-population-dawn.md) | The original shrub has higher income on 96 of 104 matched days and healthier foliage, despite fewer leaves. |
| [Leaf uptake](../benchmarks/garden-seasons/leaf-population-foliage.md) | All 512 uptake steps reconstruct exactly. The original has 1.84 times the dawn light-band exposure and collects 159 against 84 energy before the opening. |
| [Light exposure](../benchmarks/garden-seasons/leaf-population-exposure.md) | The gap is in the lower canopy, about 83 against 7 energy; upper-canopy contributions are nearly equal. |
| [Shadow sources](../benchmarks/garden-seasons/leaf-population-canopy.md) | The relocated shrub is also shaded by founder flower 1. Even unshaded, its lower leaves would earn 22.33 against the original's observed 82.75. |
| [Repair opportunities](../benchmarks/garden-seasons/leaf-population-repair-opportunities.md) | All 146 lower-leaf visits fail only the light gate of 145. Nine leaves never reach it, and six have short windows the selector's rotation misses. |

### What it adds up to

Each step holds up, and together they describe a population-level pattern
rather than a defect specific to this shrub. Search 1 repairs less than fixed
wear, which raises turnover in saturated gardens, and shrubs' shaded lower
canopies depend most on repair. The
[roadmap checkpoint](garden-alife-roadmap.md#current-checkpoint) sets this beside
two earlier comparisons with the same tradeoff and defers the proposed 13-day
selection-phase observation. The fewer-blocker placement rule stays opt-in; the
objective, ecological rules and defaults remain unchanged.

### Repair threshold sweep

The [threshold sweep](../benchmarks/garden-seasons/leaf-population-threshold-sweep.md)
asks whether any setting of the shared repair light gate gives renewal and
variety together. On sixteen fresh weather seeds in both layouts, none of
twelve settings meets the predeclared criteria, and the earlier tradeoff
reproduces: Search 1 has 0.133 late renewal against fixed wear's 0.014 and
loses 72 of 128 founder families against 42. Which species survives a collapse
depends on the rule, so the roadmap now turns to coexistence mechanisms before
any training. The runner's model-file path, described in the
[research viewer guide](garden-research-player.md), replays any 172-byte repair
model on any seed for this kind of comparison.

Environment qualification, joint growth-and-repair improvements, broader search,
and qualified device deployment remain follow-on work under
[issue #30](https://github.com/aortez/toy-factory/issues/30).
