# Shrub reproduction misses both capacity and resource timing

Shrub 17 in the fewer-blocker, condition-only run never buys a seed during days
`(128,232]`. On 16 ticks it meets every other check but an earlier plant has
already filled the bank's free slot; on the eight ticks it sees room, it lacks
energy seven times and water once. Its flower is ready every time.

- [Protocol](leaf-population-reproduction-protocol.md).
- Script: `population_reproduction.py`; `run` collects into a fresh directory
  and `verify` checks an unpacked archive.
- Result, kept locally: `leaf-population-reproduction-results.json.gz`, SHA256
  `3258eda497056194975a308f3a8ab79bd8c980afa968cb694b8263033adb226e`.
- Full report in [PR #38](https://github.com/aortez/toy-factory/blob/44b12803cf4f7b966a003bc0857b1bb061fd3374/benchmarks/garden-seasons/leaf-population-reproduction.md).
