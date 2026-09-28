# Landing sensor: NN encoding checkpoint

The [versioned input extension](../../docs/garden-landing-encoding.md) is now
implemented and independently checked. It preserves the existing 77 feature
bytes and adds 49 bytes: nine common inputs and eight per candidate. Existing
models, model files, inference, ecology and device defaults are unchanged.
This is a host-only encoding step, **not a trained-policy result**.

The encoder offers off, current-only and current-plus-history masks, plus an
explicit dead-only-field ablation. Valid bytes map exactly to signed bytes by
subtracting 128. Root/OOB readings, disabled channels and unsampled history are
neutral zero; warmup distinguishes missing from measured history. Current-only
does not receive the history clock. Fixed caller-owned storage and transactional
errors keep ownership and failure behavior explicit.

## What the saved panel shows

Replay covers every packet from the existing 16 fixed 128-day shadow worlds:
**160,477 bids × five masks = 802,385 encodings**. Native output agrees exactly
with the independent Python encoder, repeats byte-for-byte, and a separate full
verification reproduces the retained report. No new trajectories or favorable
cases were selected. Both weather seeds, layouts, controllers and origin arms
remain present, including roots and days without bids.

For the flower-origin arm, 39,049 stem queries have at least two **available**
growth candidates. For each query, separation is the largest signed-byte
difference between any available candidates in any enabled landing field.

| Input mask | Separation ≥1 | Separation ≥4 | Separation ≥16 |
| --- | ---: | ---: | ---: |
| Off | 0 | 0 | 0 |
| Current only | 22,626 (57.9%) | 19,407 (49.7%) | 17,381 (44.51%) |
| Current + history | 29,513 (75.6%) | 21,507 (55.1%) | 17,395 (44.55%) |
| Current, dead-only omitted | 22,602 | 19,357 | 17,298 |
| Current + history, dead-only omitted | 29,512 | 21,469 | 17,312 |

History distinguishes **6,887 additional queries** whose current landing
readings are identical. The added coverage falls to 2,100 queries at a four-count
threshold and just 14 at sixteen counts. Thus most newly distinguishable choices
have small margins; exact input-byte preservation does not establish that a
quantized network can use them effectively. Threshold gains can also include
queries which already had smaller current-only separation.

These numbers describe the **landing extension only**, not the full 126-byte
input. Existing geometry/local inputs can already distinguish candidates, and
the analysis does not establish information independent of those inputs. Counts
are query-weighted descriptive coverage, not independent ecological replicates,
action preferences, successful landings or fitness improvements.

After day one, current versus history coverage is 19,415 / 32,089 (60.5%) versus
24,777 / 32,089 (77.2%). In the final sixteen days it is 594 / 740 (80.3%) versus
642 / 740 (86.8%), with much less activity. History adds some one-count coverage
in each weather/layout/controller partition. The base-origin arm correctly has
zero positional separation in all 43,690 eligible queries, regardless of mask.

Removing dead-only loses all extension separation in 24 current-only queries
and just one history-enabled query. It also changes some larger margins, so
retain it as an explicit experimental ablation rather than silently concluding
it cannot matter. Closing-window results are identical with it omitted.

No real stem query in this panel occurs with zero cache samples. Cold-start
semantics therefore rely on exhaustive fixtures, not claimed natural coverage.

## Compatibility and verification

- All 256 raw values and 257 warmup counts are tested, including the one warmup
  quantization collision, zero-history versus missing-history, invalid packets,
  masked-field validation, root/OOB/unavailable candidates and candidate order.
- Separate native tests use complete real observations for baseline, adaptive
  and existing neural controllers over 32 Garden days each. Encoding every bid
  under every mode/flag preserves all 77 legacy bytes, private memory, packets,
  cache and entire world trajectories. Saved v1 model bytes remain unchanged.
- Full suites pass: **126 default and 124 representative older-research CTests**.
  The focused suite also checks the retained portable report after collection.
- Host and Cortex-M0+ layout/strict-warning checks confirm 4 metadata bytes,
  49 extension bytes and 126 combined feature bytes. Metadata is not an input;
  recurrent memory and the existing 316-byte observer cache are separate.
- Standalone ARM GCC 14.3 `-Os` compilation reports a 168-byte encoder frame and
  12-byte source-helper frame. These are individual static frames, not call-chain
  high-water marks, additional persistent RAM or target timing. No flash or
  firmware behavior change is part of this checkpoint.

## Retained evidence and replay

- [Portable daily histograms and encoded first-stem fixtures](landing-encoding-histories.json.gz)
- [Recomputed summaries, source/build hashes and stream identities](landing-encoding-summary.json)
- [Standalone encoder static frames](landing-encoding-stack.txt)

The portable history is about 155 KiB compressed. It preserves all 2,048 daily
records and first-stem samples, but cannot replace every-bid native verification.
The latter uses the original dense traces in `artifacts/garden-landing-shadow/`
and the frozen probe in `artifacts/build-host-landing-encoding/`. Request and
response streams are reproducible from those inputs; their hashes are retained,
not redundant full binary copies. Prior shadow evidence and executables remain
untouched. The encoding contract and analyzer were frozen before replay.

```sh
# Native/reference, layout, malformed-input and portable-evidence checks.
docker compose run --rm -T firmware python3 -W error \
  sim/test_garden_landing_features.py \
  --build artifacts/build-host-landing-encoding --cc cc

# Requires the original dense shadow bundle and matching frozen build/sources.
docker compose run --rm -T firmware python3 -W error \
  sim/garden_landing_encoding.py verify \
  --out artifacts/garden-landing-encoding \
  --build artifacts/build-host-landing-encoding --jobs 4
```

## Next step

Implement the host-only versioned extended inference/model codec, with explicit
legacy import and zero-extra-weight equivalence, bounded integer accumulators,
and deterministic state accounting that includes the shared history cache.
Then compare trained input ablations with matched seeds, compute budgets and
unchanged dispersal/ecology. Durable reproduction and diversity remain the
objectives; byte-level sensor coverage is only a prerequisite for that test.
