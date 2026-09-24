# Open-gap seeds: water and usable light never coincided

The exact seed-loop receipts confirm that the two rescued-shrub seeds were
never eligible to germinate. Both had space and capacity throughout all 496
mature checks, but **neither ever had enough surface water and light together**.
The founder's later seed did, and germinated on its first eligible check.
This is a resource/timing bottleneck in this selected trajectory, not a missed
germination, a full node pool, or evidence that general renewal is solved.

The [predeclared protocol](renewal-germination-trace-protocol.md) follows the
[controlled-gap comparison](renewal-controlled-gap.md) without changing any
ecology, model, routing, export, weather or seed rule. The only native change
extends the host seed-attempt CLI to replay the existing focal policy and named
export before its capture window. The kernel observer and firmware are unchanged.

## Actual checks, not post-step guesses

All three seeds are shrubs. Tick units are 60 Hz logic ticks; ecology steps are
15 ticks apart and one simulated day is 3,840 ticks. Required surface moisture
is **at least 12**, light **at least 80**, and seed age **at least eight ecology
steps**. Expiry at age 256 happens before any resource check.

| Parent / seed birth / destination | Mature checks | Water only blocked | Light only blocked | Both blocked | All gates pass | Result |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Rescued shrub 7 / 49,560 / column 3 | 248 | 41 | 91 | 116 | 0 | Expires 53,400 |
| Rescued shrub 7 / 53,400 / column 4 | 248 | 37 | 96 | 115 | 0 | Expires 57,240 |
| Founder shrub 2 / 57,240 / column 5 | 1 | 0 | 0 | 0 | 1 | Germinates 57,360 → shrub 10 |

There are no spacing, plant-slot or node-pool vetoes in those mature checks.
Both failed seeds encounter six occupied plant slots out of eight. Node use is
309–318 for the first and 318 for the second, out of 512. Each failed seed has
seven additional dormant checks and a separate, unchecked expiry visit.
The successful seed has seven dormant checks and one mature check.

The actual windows explain why independently counting "wet" and "lit" is
misleading. Endpoints below are inclusive sampled checks, not assertions about
continuous time between samples:

| Failed seed | Light ≥80 | Moisture ≥12 |
| --- | --- | --- |
| Column 3 | 49,725–49,770 (4 checks); 49,890–50,430 (37) | 50,610–51,225 (42); 52,665–53,385 (49) |
| Column 4 | 53,565–54,105 (37 checks) | 55,050–56,145 (74); 56,910–57,225 (22) |

Neither pair overlaps. During the light-qualified checks, moisture reaches only
0–2 at column 3 and 0–10 at column 4. During the wet-qualified checks, light
reaches only 24–51 and 24–47 respectively. The first seed's overall mature
water/light ranges are 0–32 / 24–202; the second's are 0–38 / 24–231.
Those independent maxima do not describe a jointly viable moment.

Night/low sun accounts for 159 light-blocked checks per failed seed. There are
another 48 and 52 light-blocked checks while the sun strength itself is at least
80. The native light solver only subtracts canopy attenuation from sun strength,
so these latter checks also identify shade, not simply waiting out the night.
This observation does not isolate rainfall, drainage, uptake or any individual
plant's contribution to the local water history.

## The successful check and the snapshot correction

At **57,360**, founder shrub 2's seed is age eight and last in the sequential
bank traversal (index 7). Its exact receipt is:

- Moisture **34**, light **97**, six plants, 318 nodes, no blockers.
- Germination creates shrub **10**, with four initial nodes and a 12-unit
  surface-water debit. The post-step site has moisture **22** and light **97**.
- Its post-step mask is **32 (spacing)** because the newborn now occupies the
  location. That mask is an effect of success, not a failed germination check.
- The earlier full trajectory already verified that shrub 10 survives to day
  64. It is a sibling of rescued shrub 7, not shrub 7's child or a new generation
  of successful renewal. No new long-horizon replay was needed here.

The first failed seed also exposes why the old post-step caveat mattered. At
**49,770**, age 14, the actual check has moisture **1**, light **86** and mask
**2 (water only)**. The later snapshot has light **66** and mask **6 (water and
light)** after the growth/light-rebuild stage. Thus its old post-step tally of
40 water-only / 91 light-only / 117 both becomes **41 / 91 / 116** at decision
time. This is the only mask mismatch across the failed seeds' 510 non-expiry
visits, including dormancy. It cannot explain a missed birth: moisture was
already below the required 12. Other small light changes do not cross the gate.

## Whole-bank context in the fixed window

Both arms replay from reset with the original model files and guards. Capture
starts with an unstepped origin at 49,545, then audits 521 ecology steps through
57,360. The treatment's tick-46,080 export receipt still has hashes
`5eea8cea` → `adf1a789` and the original removed resources.

| Window accounting | Control | Named gap |
| --- | ---: | ---: |
| Hash-checked state checkpoints | 522 | 522 |
| Ordered seed visits, including expiry | 4,168 | 4,168 |
| Actual checks / dormant / mature | 4,150 / 119 / 4,031 | 4,150 / 119 / 4,031 |
| Seed purchases / expirations / germinations | 18 / 18 / 0 | 19 / 18 / 1 |
| Mature checks with spacing veto | 4,031 | 3,301 |
| Mature checks with node/plant capacity veto | 0 / 0 | 0 / 0 |
| Germination / growth / reclaimed nodes | 0 / 11 / 0 | 4 / 12 / 0 |

The treatment has five pre-check snapshots with at least one viable hypothetical
site, four without a birth. A viable site elsewhere is not an actual mature seed
at that site. Control has none. Do not match the focal seeds across arms merely
by parent or bank index: the trajectories and purchases have diverged.

## Validation and provenance

- Exactly **four experimental native calls**, two arms each repeated. Stable-gzip
  traces are byte-identical within each pair. No new screenshots or training;
  the [eight prior native frames](renewal-controlled-gap.md#fixed-native-screenshots)
  remain the visual context.
- All **1,044 distinct checkpoints** match the saved world and site hashes,
  counters and seed-bank identities. All **8,336 ordered visits** reconcile
  with the existing sequential stage/identity/resource/outcome validator.
- Rechecked the frozen parent bundle and its prior analysis. Source archives
  restrict native differences to `sim/garden_seed_attempts.c`; the compiler,
  ecology flags, model files and exact intervention are unchanged.
- Nine new synthetic tests and native CLI checks cover missing/reordered data,
  wrong hashes/headers/resources/ages, expiry versus checks, post-birth spacing,
  self-routing neutrality, export timing/parity, and malformed/invalid targets.
  All **79 default and 77 experimental CTests pass**, including existing seed
  observer and smoke tests. Changed C is formatted; `git diff --check` passes.
- Analysis was repeated, then the portable export independently verified.
  Collection of the four native traces took about **0.65 s**; the final pair of
  analyses about **4.94 s**. This excludes prior validation and is not a host
  throughput benchmark. The complete bundle holds 47,417,222 artifact bytes.

Full bundle: `artifacts/garden-renewal-germination-trace-v1`.
Manifest SHA-256:
`57655928565878aabc170f71c59dee54841a859b96915c99c1a2b0cd0b04d635`.
[Portable receipts and summary](renewal-germination-trace-summary.json),
SHA-256 `fecaa15ec70fd9d619eb73313c8907454126146dc03d02d01a4843e523564f4b`.
All 520 focal visits, including the two expirations, are retained there.

## Next proposal — not implemented

Test whether demanding usable light **at the instant of germination** is the
right abstraction. A bounded host-only A/B could keep moisture, dormancy,
spacing, capacity, rainfall, seed lifetime and starting reserves unchanged, but
allow a wet seed to germinate without the immediate light gate. Its seedling
would then have to survive on the existing startup energy until its leaves
earn enough light. Adult light requirements and the neural policies would remain
unchanged. This is a proposal to test a rule, not a claim it will help.

Use first-day survival and subsequent descendant reproduction as acceptance
criteria, with deaths and occupied plant/seed slots as costs. More sprouts alone
could simply fill the gap with doomed seedlings and reduce recruitment. Freeze
the comparison before capture and start with this selected diagnostic; broader
environment qualification would still be needed before promotion or training.
Do not simultaneously lengthen seed lifetime, increase rain or alter spacing.

Work stops uncommitted with an issue-30 update. No firmware deployment or ecology
change occurred during this trace.
