# Multi-seed landing training v1

Frozen before collection. One bounded host experiment, not a promotion or a
change to the ecology, controller architecture, objective or firmware.

## Question and budget

Does broader training experience improve the brittle single-seed finalists on
new worlds, at the same candidate budget? Keep both previous profiles: live
occupancy/resources and fixed occupied/low. Fixed means raw zero, encoded -128
for four active added fields, not a blind controller. Body/source validity,
legacy sensing and recurrence remain. Both use current-only TGL2, flags=0, the
ordinary 256-node/eight-plant/eight-seed ecology and no gardener/irrigation.

Restart all searches from the original legacy initializer, payload CRC 01b9d94a,
SHA-256 fab9b6d97de88a970d63bb8af8fc336d076bb3d0ae6867b307290209abf85cf2,
with zero extension weights. Do not initialize from a successful finalist.
Use search RNG seeds 6d697833, 6d697834, 6d697835, two generations of three
children plus generation zero per profile: 42 candidate evaluations. Keep
32 legacy then 16 added-input mutations, exact RNG/clipping, strict incumbent
improvement and canonical child order. No added tie-breaker or early stopping.

Keep the individual-minimum renewal objective: windows (62,94], (94,126],
(126,158], (158,190], two days follow-up, horizon 192 days / 737280 logic ticks.
The lexicographic key is minimum terminal tier, sum of terminal tiers, sum of
each world's minimum window credit, then total credit. Compute it over the
complete training panel, without rescaling or pooling the renewal windows.

## Fixed splits

Training seeds are the original a9c30c1f plus **all four** previously evaluated
seeds b6b2db49, 56aa3924, 20588d83, 0cf65b97. Each uses rainfed and
rainfed-crowded with steady and seasonal climates: 20 conditions per candidate.
This is five times the training-world cost, **not equal compute** to the
single-seed experiment. Do not directly compare the old/new training keys,
which aggregate different numbers of worlds.

Keep manual-review seed ed52188c, both layouts/climates for each generation's
champion. It never selects candidates. Capture both seasonal layouts at days
16 and 192 for every generation, retaining failures and repeated champions:
72 frames, six contact sheets. Every capture must match a headless replay.

After all searches finish, evaluate all six new finalists, the six frozen
single-seed finalists, and the initial model under both profiles on four fresh
seeds: b6bebb2a, 5aa2b327, 940cfdc4, 7d3b7bde. These are the first four
xorshift32 outputs from 6c766632 (shifts 13,17,5), checked absent from existing
source/notes and decompressed evidence before collection. Both layouts and
climates give 16 conditions per variant, 224 evaluation worlds. The previous
finalists retain their recorded live/fixed profiles; model bytes alone do not
encode fixed overrides. Do not select a best model from evaluation results.
These seeds become development evidence once inspected, not a permanent test.

Frozen single-seed inputs, with SHA-256:

- landing-controls-models.json.gz:
  e99cd1b864d5920b3ddc8b28cb96565228dfd3408f53aa1f1f31aa5a32a2ab7b
- landing-controls-results.json.gz:
  82cb873997a12cbd3401f71dde5d65d9cc60f975454d1cec22d749679ccd246d

Primary comparisons are single versus multi within each profile, paired by
search RNG seed. Report live and fixed separately. For each profile, tentative
consistent breadth improvement requires all three strict aggregate wins and
strict wins in both climate slices of each pair, without decreasing either of
the first two terminal-tier key components. Ties do not pass. Secondary:
multi-live versus multi-fixed with the same gate; also compare all twelve
finalists to their same-profile initial control. Report all world losses,
seed/layout/climate slices, endpoint tiers and zero-credit windows even if an
aggregate improves. No significance or universal generalization claims from
three searches and shared conditions. Do not change the gate after outcomes.

## Checks, retention and stopping

Require identical generation-zero training biology across profiles/searches,
and unchanged generation-zero review versus the previous pilot. All initial
and first-generation model bytes must match the corresponding frozen
single-seed candidates; all mutation RNG schedules remain paired. Later
parents/bytes may differ because the training objective sees more worlds.

Retain 42 new candidate files, six old finalist files, original initializer,
all candidate/parent/receipt records, 840 training + 72 review + 224 evaluation
= **1,136 scored worlds**, full ledgers, scores and comparisons, and all frames.
Captures add 72 replays plus 36 short headless checks. Repeat every scored run
with one worker and captures off: exact result JSON and model bytes required.
Independently rerun the frozen bundle including every image. Freeze all
sources, input archives, native binary, build flags and this protocol before
collection. Source/build changes or incomplete/repeat-mismatched records fail
closed. Retain portable evidence and regression coverage in the repository.

Stop after this single experiment and review. No extra generations, seed
selection, constant tuning, sensing redesign, ecology changes, device flash
or controller promotion within this protocol.
