# Longer adult survival does not sustain the shrub lineage

The condition-only regression under fewer-blocker placement is a
replacement-chain failure, not shorter adult lives. The first replacement shrubs
live longer and buy more seeds, but their next-generation child dies before
establishing; later seeds mostly stay spacing-blocked, and the last adult dies
with no seeds left.

- Script: `population_fallback_loss.py` derives this offline from local
  archives; `--out` recomputes and `--check` compares.
- Result, kept locally: `leaf-population-fallback-loss.json`, SHA256
  `aef6fbd05857ffdf68fd5cba5bc84a75c052886bb1f3aaf54e8054900f8220d7`.
- Full report in [PR #38](https://github.com/aortez/toy-factory/blob/44b12803cf4f7b966a003bc0857b1bb061fd3374/benchmarks/garden-seasons/leaf-population-fallback-loss.md).
