# First fixed-panel visual review

The host replay/gallery bridge now connects the frozen experiment evidence to
the production renderer. See [the workflow](../../docs/garden-visual-review.md)
and [tracking issue #30](https://github.com/aortez/toy-factory/issues/30).

## Panel

- Source: local `artifacts/garden-matches-baseline/`, the 24-cycle rain-fed batch.
- Candidate: frozen neural model CRC `dc5e849d`; control: adaptive.
- Seed: `6f47c12c`, the first seed in the recorded batch, not outcome-ranked.
- Both rain-fed planting layouts; ticks 480, 2880, and 92160.
- Twelve native 240 x 240 images; all captured states match evaluator timelines.

```sh
make host-gallery-garden \
    GARDEN_GALLERY_BUNDLE=artifacts/garden-matches-baseline \
    GARDEN_GALLERY_OUT=artifacts/garden-visual-baseline
```

The ignored local gallery contains `index.md`, `contact-sheet.png`, labeled
native PNGs, exact RGB565 frames, reference metrics, frozen tools/models,
source snapshots and provenance. These artifact paths are local, not published
assets; the numeric evidence and interpretation below are retained in the repo.
Use a new output directory when repeating the command.

## What the pictures and counters show

Reset begins at noon. By the first dawn (tick 2880, 48 seconds), the neural
candidate has lost all founders in both layouts, but retains dormant seeds.
The pictured brown growth is dead tissue awaiting decomposition, not an empty
render or a stopped simulation. Descendants subsequently repopulate the world.
The adaptive control retains its founders through the first night.

| Layout / policy | First dawn: living / seed bank | Final: living / living descendants | Final: births / deaths | Durable parents |
|---|---:|---:|---:|---:|
| rainfed / neural | 0 / 2 | 5 / 5 | 15 / 13 | 3 |
| rainfed / adaptive | 3 / 1 | 5 / 2 | 4 / 2 | 0 |
| rainfed-crowded / neural | 0 / 4 | 5 / 5 | 15 / 15 | 3 |
| rainfed-crowded / adaptive | 5 / 1 | 5 / 3 | 5 / 5 | 1 |

Births count germinated offspring, not initial founders. A durable parent and
at least one child each survived a complete cycle; counts persist after death.

| Layout / policy | Dawn world hash | Final world hash | Final framebuffer CRC32 |
|---|---|---|---|
| rainfed / neural | `26d40f47` | `552f4b3b` | `e4acbb38` |
| rainfed / adaptive | `ce3bced3` | `568d22dd` | `4e0a1878` |
| rainfed-crowded / neural | `5ec890bf` | `38c20e77` | `0bed161a` |
| rainfed-crowded / adaptive | `902ecdf9` | `7074e19b` | `f23fbf6b` |

Founder mortality is not necessarily population extinction; a viable seed bank
can bridge generations. Nor do these images prove an intentionally learned
annual strategy, healthy resource economics, or broad neural superiority. The
larger batch already includes neural extinctions absent from its adaptive
control. This panel shows why qualification must follow seeds and descendants
over time instead of judging one instant or only final population counts.

The next investigation should distinguish sustainable turnover from fragile
replacement, with matched resource/decision interventions and explicit cohort
follow-up. No ecology or fitness was changed for this visual baseline.
