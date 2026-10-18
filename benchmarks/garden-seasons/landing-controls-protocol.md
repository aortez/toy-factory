# Matched live/fixed landing training v1

Frozen before collection. This is a bounded host learning experiment, not a
controller promotion, ecology change, or final generalization qualification.

## Question and two arms

Does training with varying added landing inputs outperform an equal-parameter
controller trained with fixed added inputs at this small search budget?

Both arms use current-only TGL2, flags=0, ordinary 256-node/eight-plant/eight-seed
ecology, gardener/irrigation off, and unchanged legacy sensing and recurrence.
Start both from the exact original legacy controller (payload CRC 01b9d94a,
SHA-256 fab9b6d97de88a970d63bb8af8fc336d076bb3d0ae6867b307290209abf85cf2), imported
with zero extension weights. No starting finalist is selected from later probes.

- Live: occupancy=live, resources=live.
- Fixed: occupancy=occupied, resources=low. Replace space-free, dead-only,
  water-now and light-now with raw zero at every valid source. After the existing
  subtract-128 encoding, each active field is -128, not zero. The control thus
  retains nonzero extra-input offsets and their mutable weights. Root and absent
  sources remain masked; body/source validity is not removed. History fields
  remain masked in both arms. This is not a blind controller.

Use the existing explicit host probe adapter; do not change model bytes to
install overrides or add a new inference/encoding path. This all-zero raw
constant is a simple common nonzero neural baseline, not a tuned empirical
mean or the best constant from the previous outcome panel. Equal parameter
count and mutation schedules do not imply equal effective dimensionality or
optimization difficulty; the fixed columns are redundant by design.

## Budget, objective and splits

Reuse the original individual-minimum renewal objective and exact arithmetic:
four windows (62,94], (94,126], (126,158], (158,190] Garden days, two days of
follow-up, horizon 192 days / 737280 logic ticks. Maximize the existing
lexicographic terminal-tier/minimum-window-credit/total-credit key. No new
selection tie-breaker, score, reward or stopping condition.

Three paired search RNG seeds: 6d697833, 6d697834, 6d697835. Two generations,
three children per generation plus the initial model: seven evaluations per
arm/seed, **42 total**. Mutate each generation's incumbent in canonical child
order: 32 legacy mutations then 16 extension mutations, same existing RNG and
clipping. Config/scales/masks do not mutate. Strict improvement only; ties retain
the incumbent or first strict winner. Random draws remain paired; models and
trajectories can diverge once training selects different parents.

Training world seed a9c30c1f, both rainfed layouts and steady/seasonal climates:
four conditions per candidate. Manual review seed ed52188c, same four conditions,
for each generation's training-selected champion. Both are reused development
seeds. Review never selects models or extends the budget.

After all searches finish, evaluate their six final champions on **four unused
evaluation seeds**, both layouts and both climates (16 conditions each):
b6b2db49, 56aa3924, 20588d83, 0cf65b97. These are the first four xorshift32 outputs
from 6c766631 (shifts 13,17,5); they were absent from source/evidence notes before
this protocol. Also evaluate the common initial model under both profiles on
all sixteen conditions. No best finalist is chosen from evaluation results.
These seeds become development evidence once inspected, not a reusable
untouched final test set.

Primary comparison: fixed-trained/fixed-input control versus live-trained/live-
input candidate, paired by search RNG seed. Report the unchanged aggregate key,
world wins/ties/losses, terminal tiers, zero-credit windows, and seed/layout/
climate slices. Also report each final model against its same-profile initial
control. Tentative support for a consistent live-input advantage requires a
strict aggregate win in all three pairs AND in both climate slices of every
pair, without lowering either of the first two aggregate terminal-tier key
components in those comparisons. Otherwise report mixed/no consistent support
at this budget. Individual losses must still be disclosed. Three search seeds
and shared environmental cases do not support broad significance claims.

## Required controls, images and provenance

Generation-zero biological results and scores must agree across profiles and
seeds. The live arm must exactly recover all original current-only candidate
model bytes, mutation receipts, parent/selection history, biological records
and scores. Native diagnostic run hashes legitimately differ between GSP1 and
the original GLR1; do not compare those as interchangeable identities.

Capture every generation's champion, including generation zero, on both
seasonal manual-review layouts at days 16 and 192: **72 images**, arranged in
six contact sheets. Retain failures and unchanged champions. Each capture must
match a headless replay; no image quality enters selection. No evaluation-seed
images are requested or selected after reading outcomes.

Retain all 42 candidate model files, parents and RNG receipts, all 368 full
training/review/evaluation results and ledgers, per-world scores, comparisons,
and frame receipts. Primary captures add 72 replay calls plus 36 short headless
checks. Repeat the entire search/review/evaluation with one worker and captures
off, requiring exact JSON and model bytes. Independently rerun the frozen
bundle including every image. Freeze native binary, sources, protocol, input
archives and build flags before collection; source/build edits invalidate it.
Partial/failed/nonrepeatable records fail closed. Preserve portable evidence
and regression checks; do not rely on ignored local artifacts alone.

Stop after this one fixed experiment and review. No constant sweep, retraining
extension, sensing redesign, ecology adjustment, firmware flash or promotion.
