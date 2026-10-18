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

CI runs these checks along with the isolated late Garden configurations and
alternate display firmware builds. The viewer checks include strict C warnings,
undefined-behavior sanitization, actual SDL input events, source/model integrity,
capture safety, and highlighted/unhighlighted simulation and pixel parity.
The longer archived-replay check is documented in the viewer guide.

Some intermediate research working files remain local and are deliberately
outside this integration. They are not required to build or use the viewer.
Earlier reports retain their original experiment scope and historical validation
counts; they are not claims that every intermediate experiment is included here.

## Next research question

The completed comparisons put one candidate founder family against fixed-rule
resident families. They do not establish population-wide stability when every
family uses a learned controller.

After integration, define a bounded matched comparison of all-fixed-wear,
all-Search-1, and all-Search-2 populations under deterministic weather without a
gardener or additional training. Retain family extinctions, established offspring,
seed reserves, and renewal across winters alongside matching screenshots. This
is ecological validation, not a change to the family-competition training
objective. Fix the conditions and run budget before execution.

Environment qualification, joint growth-and-repair improvements, broader search,
and qualified device deployment remain follow-on work under
[issue #30](https://github.com/aortez/toy-factory/issues/30).
