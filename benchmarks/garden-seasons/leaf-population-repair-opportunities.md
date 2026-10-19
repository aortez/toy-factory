# Short light windows escape lower-leaf repair selection

The relocated shrub's 15 lower leaves get 146 repair-controller visits during
the recorded day and no repairs: every visit waits because light is below the
model's threshold. Nine leaves never reach the threshold, and six reach it
briefly while another leaf is selected. All nine of its repairs go to the upper
canopy; the original shrub repairs nine lower leaves over the same day.

- Script: `population_repair_opportunities.py` derives this offline from local
  archives; `--out` recomputes and `--check` compares.
- Result, kept locally: `leaf-population-repair-opportunities.json`, SHA256
  `cd020156bc2cc485e2d74e70c91a4078cc44e4870a79344c581feb1b1fb24bd8`.
- Full report in [PR #38](https://github.com/aortez/toy-factory/blob/44b12803cf4f7b966a003bc0857b1bb061fd3374/benchmarks/garden-seasons/leaf-population-repair-opportunities.md).
