# Landing NN input extension v1

This is a host-only **encoding contract**, not neural model v2, a new model file,
or an active policy. The existing observation v4, feature/model/file v1 and
1,220-byte model files remain unchanged. No training or ecology promotion is
part of this checkpoint. The next inference/codec change must explicitly name
this extension version and its input mask.

The [virtual sensing contract](garden-landing-observation.md) still applies:
shared causal soil history, not the plant's private experience; no future
weather, outcomes, exact death countdown, RNG state or hidden IDs. Using these
inputs in a trained policy remains a separate experimental step.

## Layout and ownership

`toy_factory_garden_landing_features` contains the existing 77-byte feature
struct unchanged, followed by a 49-byte extension: nine common inputs and eight
inputs for each of five canonical candidates. Total: **126 bytes**. There is
no flattening/reordering of the old feature tensor and no implicit conversion
to the existing model type. The eight-byte private recurrent memory is separate.

A four-byte configuration records extension version (1), mode, flags and a
zero reserved byte. It is evaluation/model metadata, not four extra NN inputs.
`OMIT_DEAD_ONLY` is the only flag. Unknown versions, modes, flags or reserved
values fail closed. Configuration must be recorded with future model artifacts
and held fixed during an evaluation; switching it changes the policy.

The encoder is pure and caller-owned. Inputs and output may not alias; failure
leaves output untouched, even though the legacy encoder itself zeros its output
on failure. No world, cache, RNG, model, memory or action mutation is permitted.
The caller binds a packet to the right observation and pre-growth phase. A valid
shape alone cannot establish that the packet came from the correct world.

## Field mapping and masks

Common indexes 0..7, and candidate indexes 0..7, follow the raw packet order:
space-free, dead-only, current water, current light, wet EMA, lit EMA, joint
wet/lit EMA, joint open/wet/lit EMA. Common index 8 is history warmup. The common
source is the current stem tip; candidate rows follow the existing canonical
candidate order. Existing tissue/bounds/availability features are retained.

For each enabled, valid byte `v`, encode **`v - 128`** in signed int8. This is a
bijection from 0..255 to -128..127: no saturation, nonlinear amplification,
outcome-informed normalization or loss of one-byte spatial differences. It
does not prove those small differences are useful to a quantized network.

| Mode | Current fields 0..3 | History fields 4..7 | Warmup |
| --- | --- | --- | --- |
| off | zero | zero | zero |
| current | centered valid bytes | zero | zero |
| history | centered valid bytes | centered only after at least one sample | encoded count |

`OMIT_DEAD_ONLY` zeros field 1 in every row without changing other fields, tensor
dimensions or ordering. It allows a later explicit rare-feature ablation. It
is not a silent permanent removal or an extra sensor. Baseline/off may operate
with a null packet. Any supplied packet is validated in **every** mode, including
off and fields masked by the flag.

Root queries and OOB candidate rows have **all extension values zero**, including
root warmup. They must not encode missing readings as -128 (measured drought).
In-bounds but unavailable candidates retain readings; availability is a separate
existing action constraint. Current-only receives no warmup or history clock.

For a valid stem in history mode, common warmup is:

```text
round(samples * 255 / 256) - 128
  = ((samples * 255 + 128) / 256) - 128   # nonnegative integer division
```

`samples` must be 0..256. Zero gives -128; only 256 gives +127. The 257 possible
counts occupy 256 byte codes, so 128 and 129 share a code. At zero samples all
raw history fields must be zero, and encoded histories are **neutral zero**;
they are not evidence of a dry/dark past. At sample one a genuinely zero trace
encodes -128. This makes cold-start absence distinguishable from measured absence.

## Packet validation

Require observer packet v1 and an exact validity mask derived from tissue and
canonical `IN_BOUNDS` flags (not merely x bounds). Invalid raw rows must be all
zero; unknown mask bits are errors. A null packet is invalid outside off mode.
Require zero traces at zero samples and consistent joint ordering:
open/wet/lit <= wet/lit <= each marginal trace. Space-free plus dead-only may
sum to **256**, not just 255, because two exclusive half-mass means independently
round 127.5 upward. Reject greater sums. Checks apply before any ablation mask.

These are structural consistency checks, not reproduction of the entire cache
history. Do not claim that an arbitrary valid packet is an authentic observation.

## Verification plan, frozen before replay analysis

Reuse the complete 16-world shadow panel. Pin its compressed portable history
SHA-256 `24c4623c78ebb752f7236324f5f3d9863387357bc86184c2f0c1d3d1719113da`
and summary `bddedac9f56cc99d7ea61935730d1b4c51ac9cbbc2a326446b8cb15aa1c40239`.
No new world trajectories or selected best cases. Read every original shadow
packet from hash-pinned dense traces, recheck its history/projection with the
independent reference, and replay it through the native encoder and independent
Python encoder for all three modes, plus current/history with dead-only omitted.
The native binary probe uses a synthetic valid legacy context carrying the real
tissue/flags: it checks extension arithmetic, not reconstruction of unrecorded
legacy observation fields. Native trajectory tests separately use full real
observations to compare all 77 old bytes and entire worlds.

Measure per-world/per-day available-choice counts, differing encoded candidates
for each mask, history-only added variation, dead-only-exclusive variation,
and maximum component separation (thresholds 1, 4 and 16 encoded counts).
Retain roots, masked rows, cold-start coverage, empty days and both origin arms;
report whole/warmed/closing windows and weather/layout/controller partitions.
These are information/encoding diagnostics, not fitness scores or independent
biological replicates. Repeat the replay/analysis and retain stream digests.

Test exhaustive byte and warmup ranges, malformed/versioned inputs, transactional
errors, zero-history versus missing-history, root/OOB masking, candidate order,
and unchanged legacy/model files. Check layout/strict warnings with host and ARM
compilers. Run full default and representative research host suites. No target
timing or firmware deployment is needed for isolated host-only encoding files.

### Native test-probe framing

The bounded binary test tool reads 62-byte records: config (4), tissue (1), five
candidate flags (5), packet version/valid (2), LE warmup (2), six raw rows (48).
It writes 53-byte records: LE signed error status (4), then common (9) and five
candidate rows (40) in two's-complement bytes. Failure leaves all 49 bytes at
the caller's 0xa5 sentinel. A partial request or I/O error fails the process;
complete invalid requests return error records so tests can check preservation.
This is a test harness, **not** a model persistence or device transport format.

## Next gate

After the encoding check, design the versioned extended inference/model codec
with explicit legacy import/zero-extra-weight equivalence, integer accumulator
bounds and cache-aware deterministic state accounting. Only then compare trained
input ablations with matched seeds, compute budgets, population and evaluation
rules. Keep dispersal identical within each policy comparison. Encoding coverage
cannot settle whether the sensor improves durable reproduction or diversity.
