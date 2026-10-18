# Repair durability evidence checkpoint

The [durability report](../../../benchmarks/garden-seasons/leaf-family-durability.md)
records the frozen policies through day 1376. This checkpoint retains its
archive, all four comparison sheets, the earlier four-weather archive and
model-source pilot archive, and the exact Python source dependencies required
for offline verification. It does not change the normal simulator or firmware.

From the repository root, verify the evidence and published pixels with:

```sh
python3 sim/experiments/leaf_durability_report/collect_durability.py \
  --check benchmarks/garden-seasons/leaf-family-durability-results.json.gz \
  --images benchmarks/garden-seasons/frames
```

The four focused Python suites are `leaf_durability`, `leaf_durability_report`,
`leaf_generalization`, and `leaf_generalization_report`. For example, use the
existing builder image without installing host dependencies:

```sh
docker compose run --rm -T firmware env PYTHONDONTWRITEBYTECODE=1 \
  python3 -m unittest discover \
  -s sim/experiments/leaf_durability_report -p 'test_*.py'
```

Verification does not run a simulator, need a native build directory, or require
network access. The checker and all 57 tests across the four suites pass in a
clean Git-tree export mounted read-only, with no local artifacts and networking
disabled. The historical experiment/build scripts retain references to
their original local inputs; this evidence checkpoint is not a clean-checkout
launcher for another experiment. The archive contains the complete compiled
runtime source snapshot, models and build receipts for a separate reconstruction.

The [research playback plan](../../../docs/garden-research-playback-plan.md)
proposes using that snapshot for a host-only interactive viewer. The wider
uncommitted research backlog remains separate from this checkpoint.
