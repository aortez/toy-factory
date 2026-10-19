# Repair policies across whole garden populations

Every family in a garden used the same repair controller through day 1376: fixed
wear, Search 1 or Search 2. Search 1's late renewal score is 5.50 times the
fixed-wear control and Search 2's is 3.35 times, and none of the 24 gardens
becomes empty or extinct. The benefit costs diversity: Search 1 loses 19 of 32
founder families and ends with one species in four of its eight gardens, while
the control loses 11 and keeps at least two species in every garden.

Eighteen follow-ups trace one of Search 1's shrub losses; the
[evidence index](README.md) lists them. The
[threshold sweep](leaf-population-threshold-sweep.md) retests the tradeoff on
fresh seeds.

- [Protocol and collection steps](../../docs/garden-population-comparison.md).
- Scripts: `collect_population.py` collects; `population_evidence.py` verifies
  an unpacked archive, and its `gallery --sheets-only` redraws the contact
  sheets.
- Watch a run:
  `make host-play-research ARGS="--policy s1-g3-c4 --founder all --speed 256"`.
- Result, kept locally: `leaf-population-results.json.gz`, SHA256
  `3aae48b92ed9787f9dc1601052330cdbf96ed9d72f3d845e0b9932d50112af49`.
- Full report in [PR #38](https://github.com/aortez/toy-factory/blob/44b12803cf4f7b966a003bc0857b1bb061fd3374/benchmarks/garden-seasons/leaf-population.md).
