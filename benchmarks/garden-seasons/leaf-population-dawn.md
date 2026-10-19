# The successful shrub has healthier foliage despite fewer leaves

Original-placement shrub 19 has higher energy income than fewer-blocker shrub 17
on 96 of the 104 matched days in `[128,232)`, and higher mean leaf condition at
95 day-end checkpoints, with 24 leaves against 26. Leaf count alone does not
explain its earlier reproductive readiness.

- Script: `population_dawn.py` derives this offline from local archives; `--out`
  recomputes and `--check` compares.
- Result, kept locally: `leaf-population-dawn.json`, SHA256
  `4fd7f8d23ac5358014ed845fb9c0c832f04c9c6b956a78f4deee945610d1c8ba`.
- Full report in [PR #38](https://github.com/aortez/toy-factory/blob/44b12803cf4f7b966a003bc0857b1bb061fd3374/benchmarks/garden-seasons/leaf-population-dawn.md).
