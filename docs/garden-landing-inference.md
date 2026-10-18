# Host-only landing inference and model format

This checkpoint activates the [landing extension](garden-landing-encoding.md)
inside a separate host inference API. It does not change the existing firmware,
player, trainer, model-v1 reader, or ecological defaults. The saved sensing
evidence is not a trained fitness result.

## Network and ownership

The existing 1,204-byte network stays intact inside an extended model. Add
16 × 9 common weights, 8 × 8 candidate weights, and four configuration bytes:
**1,416 bytes total**, 208 additional signed-byte weights. Add each extra dot
product to the corresponding existing accumulator **before** division/ReLU.
Action, priority, memory, terminal/blocked overrides, and nonce-rotated stable
candidate ties retain the v1 semantics. Root/OOB/history masking follows the
frozen extension contract. Configuration is part of the immutable model, not a
command-line override applied after loading it.

The maximum absolute accumulator bound is 1,000,000 + 49 × 16,384 = 1,802,816
for the common layer and 1,540,672 for candidate fan-in 33; downstream fan-in is
at most 16. All fit int32, including intermediate sums. Use C11 signed division
toward zero, not implementation-defined signed shifts. Every allowed int8
weight is safe with validated v1 biases and shifts. Compile-time bounds must
fail if future layer sizes invalidate this argument.

Explicit import validates a legacy model, copies it, records a chosen mask,
and initializes all additional weights to zero. Normal v2 decode never guesses
or silently imports v1 bytes. Pure inference/import/codec operations are
caller-owned and transactional on errors; non-overlapping buffers are required.

The experimental kernel intentionally leaves the frozen production v1 kernel
untouched. Differential and independent arithmetic tests protect against drift.
If promoted later, a shared internal kernel should replace the duplicated
inference mechanics without changing either external model ABI.

## Canonical file: TGL2

All integers are little endian, signed weights are two's-complement bytes.
The complete file is **1,448 bytes**, with no struct padding or pointers:

| Offset | Size | Contents |
| --- | ---: | --- |
| 0 | 4 | ASCII `TGL2` |
| 4 | 2 | File version 2 |
| 6 | 2 | Header size 16 |
| 8 | 4 | Payload size 1,432 |
| 12 | 4 | Standard CRC-32 of bytes 16..1447 |
| 16 | 1,220 | Complete unchanged v1 model file, with its own validation/CRC |
| 1236 | 4 | Extension version 1, mode, flags, zero reserved byte |
| 1240 | 144 | Common extra weights, hidden-unit major then feature |
| 1384 | 64 | Candidate extra weights, candidate-unit major then feature |

Reject wrong sizes (including trailing data), versions, reserved fields, masks,
CRC, or invalid nested model parameters. Decode publishes only after all checks
pass. Masked weights are retained for explicit later ablations, not silently
normalized to zero. CRC is an accidental-corruption check, not authentication.

## Complete replay state

`toy_factory_garden_landing_run` owns a world, its 316-byte history cache, the
entire model/configuration, and version/build-rule tags. It has no pointers.
Initialize only after complete tick-zero scenario/climate setup, gardener off.
The owned model is fixed for that evaluation. Each step samples at the existing
authoritative pre-growth boundary and lets all bids read the same frozen cache.
On an error, both world and cache roll back; this defensive host path copies
them to scratch storage. No callback keeps a pointer beyond the step.

A same-build value copy is a complete in-memory checkpoint; it includes the
world's private recurrent memory, environmental history, RNGs, model and mask.
This is **not a portable world save-file format** or an untrusted-checkpoint
decoder. Independent runs can live on separate workers; the same run cannot
be mutated concurrently. Changing a mask/model is a new evaluation, not an
invisible mid-run toggle. Do not modify fields behind the run API.

The diagnostic FNV-1a fingerprint covers domain `GLR1`, run version, wide/flower
build flags, existing world hash, cache clock/warmup/version/flags, every Q8.8
trace (trace-major), per-column water/light/occupancy, and canonical model bytes.
Multibyte values use LE bytes, without padding. It remains a finite diagnostic
hash, not collision-free identity; retain source/build hashes for experiments.
The legacy world hash alone is no longer sufficient for history-driven policies.

## Verification gate

Check zero-extra equivalence across masks, tissues, random/extreme models,
private memories, shifts, ties and world trajectories. Independently decode the
container and reproduce extended integer decisions, including nonzero weights
that demonstrably change choices. Check malformed files with recomputed CRCs,
transactional failures, ARM layout/compilation, and continuation from complete
checkpoints before and after an ecology boundary. Keep the same ordinary and
wide/flower mechanics in each comparison; no fitness tuning or training here.

The subsequent [host replay/evaluation tools](garden-landing-tools.md) expose
these APIs with explicit file loading, fixed-checkpoint screenshots and matched
outcome reports. Training integration and matched input ablations remain next.
Do not describe kernel validation as evidence of improved survival,
reproduction or diversity.

## Verified checkpoint

- **3,072 differential decisions** (512 random/extreme legacy cases × three masks
  × two dead-only flags) match v1 after zero-extra-weight import, including
  next memory and candidate ordering. Off mode also works with a null packet.
- **512 extended-network vectors** repeat byte-for-byte and agree with an
  independent Python decoder/integer evaluator. They cover every shift 0..15,
  all three actions, both tissues, bounds/availability, and all six mask/flag
  combinations. Removing the added weights changes 48 complete decisions:
  24 in current mode, 24 in history, zero in off. These are synthetic arithmetic
  checks, not model quality scores.
- A directed fixture changes the preferred candidate through wet history and
  changes private memory through common history. A separate injected-cache
  counterfactual starts with identical worlds but different run fingerprints
  and subsequently different world states. The history input is actually used.
- Three **32-day** seasonal crowded-world runs, one per mask, retain byte-identical
  worlds under imported v1 reference weights. Nonzero-weight runs resume exactly
  from six complete checkpoints around ecology/warmup boundaries. A post-sampling
  callback failure leaves the caller's complete run unchanged.
- File checks cover every single-byte corruption, truncation/trailing bytes,
  malformed metadata and unsafe biases with recomputed CRCs, exact nested v1
  bytes, preservation of masked weights and unchanged output on errors.
- **128 default / 124 representative older-research CTests pass.** The focused
  native/reference tests also pass with wide plus flower-origin dispersal; the
  new run wrapper is deliberately unavailable in incompatible older experiments.
  Existing source files in the v1 inference/codec and landing encoder are untouched.

Host and Cortex-M0+ strict compilation/layout checks pass: model 1,416 bytes,
combined feature tensor 126, cache 316, and complete in-memory run **6,092 bytes**.
No allocation is dynamic. The model is copied into each host run for independent
ownership; this is not a requirement to duplicate models per world on a device.

Standalone ARM GCC 14.3 `-Os` reports individual static frames of 272 bytes for
inference, 1,432 for import, 1,480/1,448 for encode/decode, 6,112 for run init,
4,720 for step, and 1,488 for fingerprinting. These exclude callees and are
**not measured call-chain high-water marks or target performance**. Transactional
copies are intentionally defensive host scaffolding. Do not move this wrapper
onto the device unchanged; target integration needs an explicit scratch/stack
design and measurement. No firmware build change or flash was needed here.

```sh
# Full ordinary regression (build resets experimental switches).
make host-check

# Focused checks in an ordinary host build.
docker compose run --rm -T firmware ctest --test-dir build-host \
  --output-on-failure -R '^garden-landing-neural'
```

The local test builds are `artifacts/build-host-landing-inference` and
`artifacts/build-host-landing-inference-flower`. Build/test logs are retained as
`artifacts/garden-landing-inference-*.log`, with standalone compiler frames in
`artifacts/garden_landing_*-arm.su`. The test sources regenerate the synthetic
vectors deterministically; no new ecological benchmark panel was collected.
