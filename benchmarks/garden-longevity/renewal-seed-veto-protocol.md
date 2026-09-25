# Single-founder fourth-seed veto protocol

Accepted after the [single-neighbor diagnostic](renewal-neighbors.md), before
collecting outcomes. Test whether suppressing the additional late seed purchase
rescues founder shrub 2 in the far-right-flower swap. This is a fixed-world causal
probe, not a proposed reproduction rule, training run or device change.

## Fixed intervention and control

Keep world `0d983a80`, reset `e663996c`, patch schedule `05d87ca0` (first event day
16), and eight days / 30,720 logic ticks. Founder 5 uses saved W `c9ea07fd`; every
other plant, including observed founder 2 and all descendants, uses saved N
`01b9d94a`. Keep the previous 512-node, eight-plant/eight-seed, rainfed-crowded,
wide-dispersal, headroom-uptake, selective-leaf, night-growth-veto configuration.
No gardener, drainage or broad sunset seed-reserve gate.

Rebuild two separate host configurations from the same source:

- **Control:** diagnostic compile option OFF (the default).
- **Veto:** explicit host-only compile option ON. Immediately before an otherwise
  eligible seed purchase consumes RNG/resources, suppress it only if its parent
  is reset founder lineage 2 and has already purchased three seeds in its second
  daylight, logic ticks `[2880, 4800)`. Ordinary spent-flower flags, cleared at
  dawn, count that day's purchases; living flower nodes are not individually
  reclaimed. Suppress all retries during that interval, not just one tick.

No refund, energy injection, forced seed deletion, artificial cooldown, new
observations or controller/memory change. Other parents, descendants and all
other times keep ordinary reproduction. Downstream bank/RNG/ecological feedback
is allowed and must be retained. Tag the intervention in census/replay metadata.
Guard against device builds and incompatible ecology options.

## Validation and frozen evidence

Pin prior neighbor bundle manifest
`ca91af24f73667e34f686d6a97ce0a5613b94f9f0aea55f5be7dffe7b41fbdcc`.
Copy its models, full far-right-flower trace, common native frames and source/build
provenance. Before interpreting outcomes, require the rebuilt OFF control to
match every old trace record and both shared checkpoints (days 2 and 8) exactly.
Require the ON trace to match control through the first veto, removing only its
declared diagnostic metadata. Expect the first divergence at the saved fourth
purchase, tick 4,620; a different first divergence is a failed isolation check,
not a new outcome to explain away.

Test the real production path: three purchases allowed, fourth/retries blocked;
founder identity after compaction; noninheritance; daylight endpoints; other
days/parents; unchanged RNG, flower flag and cooldown on veto; ordinary resource
and eligibility checks still apply. Build with strict warnings and UBSan.
Run the ordinary host regression suite in the OFF configuration, with targeted
production/guard tests in both configurations. Build/unit validation is separate
from the fixed outcome panel below.

Each case gets two full ecology traces and repeated native frames at ticks
**4800, 6720, 7680, 30720** (second sunset, following dawn, day 2, day 8):
**4 traces + 16 replays = 20 new native diagnostic calls**. No N/N rerun, new
world, model mutation, training, longer horizon or added experimental case.
Seal source, commands, binary/model hashes and raw results before analysis;
retain failures without automatic outcome reruns.

Reconcile live resource budgets, committed growth decisions, controller routing,
seed purchases, repeats and trace/frame state. Preserve the terminal-step
cleared-income limitation. Record first divergence; focal resources, body and
stress at sunset/dawn; early and eight-day survival; offspring and whole-world
species census. Keep all outcomes and native screenshots, not just a rescue.

## Interpretation and stopping rule

Survival improvement establishes an effect of this scoped purchase suppression
with downstream feedback, not that every neighbor failure is reproductive or
that a three-seed quota is a good general design. Lack of rescue is also useful:
do not silently widen the veto, add reserves, retune costs or train around it.
The ground-cover's lower-income/no-extra-seed failure remains separate.

Report findings and discuss the next bounded proposal. No default/fitness change,
training, deployment, commit or push is included.
