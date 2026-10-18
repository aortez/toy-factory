# Frozen model water eligible arbitration screen

`make host-screen-landing-arbitration` compares the existing water guard with
eligibility-aware selection on twelve frozen-model worlds. Only ranking changes:
the same water forecast excludes unaffordable proposals before selection. Genuine
WAIT proposals remain eligible; if everything is refused, the original winner
becomes WAIT. Only the winner commits memory, with the normal first-wins tie order.

```sh
make host-screen-landing-arbitration GARDEN_LANDING_ARBITRATION_OUT=artifacts/my-arbitration-screen
docker compose run --rm -T firmware python3 \
  artifacts/my-arbitration-screen/sim/garden_landing_arbitration.py \
  --verify artifacts/my-arbitration-screen
```

The collector requires ordinary ecology, UBSan, fresh output, and immutable
source/build/input files during collection. Options are `--build DIR --out NEW_DIR
[--jobs 1..4]`; defaults use `build-host` and two workers. Verification accepts no
overrides and uses frozen tools, binary and inputs with one worker.

```sh
toy-factory-garden-landing arbitration-replay model.tgl rainfed-crowded 0x940cfdc4 \
  --climate seasonal --ticks 737280 --water-arbitration eligible --ledger \
  --recruitment-trace NEW-resources.jsonl --water-trace NEW-bids.jsonl \
  --framebuffer NEW.rgb565be
```

Use `veto` for the matched control. Traces are optional but require a ledger;
paths are no-clobber. Both modes have a separate replay identity, rejected by
ordinary training. The old `water-replay` command remains byte-compatible.

Every queried first-day descendant bid is recorded with its local forecast,
priority, tip and memory. The collector recomputes winners, checks shared input
and committed output memory, reconciles growth spending, repeats both traces and
pixels, and requires exact historical veto controls. Final images include every
case. The unchanged renewal gates are evaluated separately against the veto and
archived ordinary baselines. See the [protocol](../benchmarks/garden-seasons/landing-arbitration-protocol.md).

This is host-only research: no firmware hook, trained-model update, resource
threshold tuning or automatic promotion. Better root access alone is not the
acceptance criterion.

The [completed screen](../benchmarks/garden-seasons/landing-arbitration.md) fails
retention despite improved first-day survivor counts; its controls, regressions
and screenshots are retained for the next diagnosis.
