# Renewable-flower comparison

Garden hash version 5 removes two terminal reproduction conditions identified
in the [baseline investigation](README.md): permanently spent flowers and
reserves larger than a plant's possible stored resources.

Living flowers renew at dawn and may fund one seed per Garden day. The existing
48-energy/24-water seed costs, four-second per-plant cooldown, daylight and
stress gates, seed lifetime, spacing, and fixed capacities remain in force.
The requested reproduction reserve is capped at
`storage_limit - upkeep - seed_cost`. Uptake precedes upkeep, so the ceiling
must account for that maintenance debit as well as the seed cost. For example,
the traced 57-node shrub's energy gate drops from an unreachable 368 to 248
after upkeep; it pays 48 to make the seed and retains 200. This does not promise
survival through the next night.

No plant/node/seed capacity, body size, persistent world field, growth policy,
trained weight, or fitness ordering changed. The built firmware's static RAM
remains 222,988 bytes, and the Garden world remains 4,340 bytes. Host experiment
bookkeeping gained one seed-state counter; it is not part of firmware state.

## Paired 24-cycle results

The experiment reused the frozen `dc5e849d` neural model and the same 32 seeds
from the baseline, for all three policies and all three layouts. All 192 watered
policy/scenario/seed trajectories retain living plants at cycle 24. All 96
unassisted trajectories are still extinct by cycle 2. External watering was
unchanged.

| Scenario | Policy | Mean final living, before → after | Births in cycles 16–24, before → after | Trials with late births, after |
| --- | --- | ---: | ---: | ---: |
| Irrigated | Baseline | 1.97 → 5.00 | 0 → 46 | 5/32 |
| Irrigated | Adaptive | 3.69 → 5.66 | 0 → 29 | 8/32 |
| Irrigated | Neural champion | 1.13 → 1.69 | 0 → 209 | 31/32 |
| Crowded | Baseline | 2.50 → 4.75 | 0 → 108 | 14/32 |
| Crowded | Adaptive | 4.19 → 5.09 | 0 → 40 | 10/32 |
| Crowded | Neural champion | 2.00 → 2.09 | 0 → 501 | 32/32 |

Birth counts are aggregates across 32 trials. Late reproduction is observed for
each policy/scenario group, not in every individual garden. Baseline irrigated
lineages reach generation 13, adaptive irrigated lineages reach 7, and the frozen
neural irrigated policy reaches 9. Those are historical generation maxima.

The neural crowded group has 500 deaths alongside its 501 late births, and
still loses every shrub and ground-cover population by the final checkpoint.
That is continuing turnover with poor offspring durability. A high birth count
does not establish a good survival strategy. Adaptive retains larger populations
but some gardens become space-limited: the baseline/adaptive batches reach the
256-node ceiling, and many seeds expire before finding viable space. The maximum
observed lineage count is 52, well below the host's 4,096 tracking capacity.

The subsequent [lifetime investigation](lifetimes.md) distinguishes offspring
that survive a whole day/night cycle from the existing 1.25-second establishment gate. Aging,
structural regrowth, selection pressure, and capacity changes remain separate
design decisions. This paired comparison uses the prior evaluation seeds;
future weight selection should retain a fresh held-out set.

## Reproduce and validate

Keep the baseline artifacts, then run against the updated host build:

```sh
make host-build
docker compose run --rm firmware python3 benchmarks/garden-longevity/run.py \
  --model artifacts/garden-longevity-heldout/champion.tgm \
  --training artifacts/garden-longevity-heldout/training.json \
  --output artifacts/garden-longevity-renewal-validated \
  --trials 32 --seed 0x686f6c64 --jobs 3
```

Choose a new output directory if it already exists. The resulting directory
contains raw reports for 2/4/8/16/24 cycles, aggregate/interval summaries,
the frozen input, and source/binary provenance. The sweep completed in about
118 seconds under UBSan with three concurrent processes. Other local builds
were running during part of this sweep; that time is not an A/B performance
measurement or an RP2040 timing claim.

The first sweep exposed an existing evaluator assumption: every mature seed
left in the bank was expected to be blocked. Crowded baseline seed `b738f9be`
has a ready seed at tick 7,740 after the final light update, awaiting the next
germination pass. Report schema 3 now counts `ready` separately, with
`samples = dormant + ready + blocked`. The regression test exercises that exact
world. It changes observation accounting without changing simulation ordering.
The summary command still accepts old schema-2 reports.

Validation passed:

- Focused world tests cover all reserve traits at 4/40/41/57/59/256 nodes,
  exact cost debits, one-unit resource boundaries, zero-growth flower renewal,
  dawn darkness, stress, shared cooldowns, full-bank recovery, and dead flowers.
- `make check`: strict formatting, UBSan world/agent tests, all 13 host CTests,
  deterministic full/damage rendering, and a pristine firmware build.
- `make host-player-check`: rebuilt the interactive player and passed its
  off-screen smoke test. Restart the player to load these lifecycle rules.

Garden sequence hashes were deliberately advanced to version 5. The early
930-tick scene retains identical state diagnostics and pixels; its hash changes
with the contract version. Later fixtures create additional seeds, affecting
state and sometimes pixels. These updated goldens have not yet been replayed
on the PicoSystem; no device flashing was performed for this change.
