# Founder-independence challenge: fixed host diagnostic

Checkpoint accumulated investigation work before implementation (`a1c419f`).
Question: can descendant lineages continue without their original founder plants,
or is apparent garden persistence dependent on those founders? This is a paired
intervention, not a permanent mortality rule, objective adoption or training run.

## Fixed panel and branches

Use the frozen coverage bundle `garden-training-coverage-v1`, manifest SHA-256
`a9142bff1570b3912b7f7d5dc71dbf4575c3db6df10249cf9b3539643abaf460`.
Four models: original `g0` / `dc5e849d`, broad G2 `g2` / `556a5dd2`, broad final
`g3` / `c7c1b31e`, narrow final `narrow` / `449c35fe`. Four existing review seeds:
`eb300b12`, `1824c139`, `4d5f9ee1`, `fe1dd56f`; fresh-1 `e4d65e6f` and fresh-2
`17c29444`. These are already inspected exploratory conditions, not final-test
holdouts or new independent training seeds. Keep the 512-node, eight-plant,
eight-seed, undrained maintenance environment, night-growth veto, selective leaf
maintenance and frozen weights. No gardener, seed relocation or resource refill.

There are **32 pairs / 64 main trajectories**. Reset/replay the same prefix to
day **64**, after its ordinary step and any scheduled patch. In the exit branch,
mark **all living plants with parent lineage zero** dead via the existing ordinary
patch-death semantics. Preserve their corpses until ordinary decomposition;
their stored energy/water is lost under that existing death rule, not added to
soil. The unchanged branch has no extra mortality. Soil, seed bank, living
descendants, per-plant/world RNGs and weather schedule are unchanged at the
boundary. Recompute light as ordinary death does. Record exact killed IDs,
resource loss and before/after hashes separately from scheduled patch deaths.
If no founders remain, retain the no-op pair; do not invent another target.

Continue ordinary rain **and the existing patch schedule** in both arms through
day **128**, plus the existing two-day follow-up to day **130**. Record natural,
scheduled-patch and founder-exit deaths separately. No extension after seeing
results. An absence of descendants at the split is an observed condition, not
grounds to drop or retarget the case. This intervention both removes seed
producers and releases space/shade/demand; it does not isolate those effects.

## Outcomes, not a new score

Report every pair, by controller and schedule:

- Living established descendants and extinction/seed-only states at days 64,
  96, 128 and 130; original ancestry remains intact after founder reclamation.
- Seeds purchased by descendants **after day 64 through day 128**, germination,
  expiry and full-day child survival with the declared two-day follow-up.
- Seed carry-in versus post-exit purchases, including founder-produced seeds
  left in the bank. Founder-bank seedlings may establish normally but are not
  themselves counted as descendant-produced replacement.
- Further generations: an established post-split child subsequently produces
  another full-day survivor. Report true parent links, not maximum generation
  alone or presumed matching IDs between divergent arms.
- Time to first qualifying new recruit; post-split qualifying first-day
  confirmations in (64,96] and (96,128], and bounded-age renewal credit in those
  two periods using the existing rule, without installing it into the trainer.
- Body/seed counts and matched native images. Extinction, recent births and
  incomplete follow-up remain explicit; survival alone is not independence.

Success is not a universal reliability gate. Compare within each frozen
controller/world pair, and show how many founders/slots each intervention removes.
Different controllers can have different founder occupancy at day 64. Do not
rank controllers as equally challenged solely from raw intervention outcomes.
Do not normalize fitness by opportunity time or silently adopt a failure threshold.

## Fixed capture and validation budget

**144 native diagnostic processes**: 64 current ledger trials; 32 frozen-original
control trials at the same 64/128/130 boundaries; 24 native image replays plus
24 independent repeats. The visual panel is declared now: all four models,
`fresh-2.eb300b12`, both arms at days **64,80,128**. Day 64 means post-intervention
for exit and matched untouched state for control. Keep all 24 images and their
hashes, including uninteresting outcomes. New trial checkpoints include those
capture times only for the optional exit path; ordinary output stays compatible.
Image replays must match same-tick ledger checkpoints or counts/ancestry with
their independent repeated hash; where needed capture-day checkpoints are added
identically to current/frozen ledger comparison through explicit projection,
not by changing native trajectories. No outcome-selected extra captures.

Frozen control output must reproduce current ordinary control output exactly.
All prefix lifetimes, seeds and available hashes agree before exit; compare the
exit event's pre-hash against the matched control split hash. All boundary
invariants and later ordinary stepping must be tested. Independently repeat
every captured framebuffer byte-for-byte and bind replay state to ledger state.
Models, binaries, build configurations, sources, ledgers and commands are pinned
in a fresh immutable bundle. Reanalyze twice, verify artifacts and export a
portable summary/gallery. No commit/push of new experiment work automatically;
only the initial agreed checkpoint is committed. Use issue #30 for results.

Test ordinary death/no-op/error atomicity, founder selection after compaction,
preserved seed/soil/RNG/survivor state, delayed reclamation, event ordering,
prefix equivalence, absence of extra deaths in controls, bounded cohort follow-up,
founder-bank carry-in, parent confirmation, further generations and complete panel
checks. Run default and host-experimental tests with strict compiler warnings;
no firmware deployment is needed for this host-only question.

Stop with a recommendation on founder dependence and whether this assay adds
useful information beyond sustained descendant renewal. No new reliability gate,
model promotion, ecological change or training follows automatically.
