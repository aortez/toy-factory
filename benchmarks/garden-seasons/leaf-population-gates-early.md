# Early repair differences change seed bank handoffs

On weather seed `9a903368` the repair outcomes depend on which seeds replace the
first shrubs, not simply on how long the founder survives. Light-only and
condition-only each return from a seed-only interval around day 63;
both-restored leaves one seed blocked beside a surviving flower until it expires
on day 66.

- Script: `population_gates_early.py` derives this offline from local archives;
  `--out` recomputes and `--check` compares.
- Result, kept locally: `leaf-population-gates-early.json`, SHA256
  `c18009671baaa875fc902d94ac48fb5289cb466354ae02c027174f4dc145c626`.
- Full report in [PR #38](https://github.com/aortez/toy-factory/blob/44b12803cf4f7b966a003bc0857b1bb061fd3374/benchmarks/garden-seasons/leaf-population-gates-early.md).
