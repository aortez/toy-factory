# Fixed first-day maintenance-reserve counterfactual

Follow the [read-only seedling replay](seedling-resources.md), without promoting
any ecology or device default. Freeze this protocol before collecting treatment
outcomes. One candidate, no parameter search or replacement of adverse cases.

## Panel and scope

Use exactly the three previously selected **wide-scattering** worlds: energy
failure `rainfed / baseline / a9c30c1f`, lineage 35; water failure
`rainfed-crowded / baseline / ed52188d`, lineage 41; survivor
`rainfed-crowded / adaptive / 4f0b9246`, lineage 39. Each treatment is paired with
its own unchanged world, not a different narrow-scattering plant. The source
selection and retained focal histories remain unchanged.

Run combined seasonal climate through day 128, with the same 256-node/eight-plant/
eight-seed ecology and wider scattering. No gardener, irrigation, body editing,
germination change, weather adjustment, seed-spending veto or neural training.
Only the named offspring's growth decisions can change, during ages 1–256
ecology samples (birth inclusive, full-day boundary exclusive). Founders, other
lineages and ages 257 onward retain their base policy. An explicit CLI option
enables the host-only adapter; absence of it preserves normal output/state.

## One fixed rule

Use only the existing observation and the base proposal. Preserve arbitration,
candidate ranking, priority and proposed recurrent memory. WAIT stays WAIT.
An unaffordable paid proposal becomes WAIT with its candidate list cleared.
This retains base arbitration, including the possibility that a vetoed high-
priority WAIT wins over another tip; do not silently change that mechanism.

Energy: reuse the existing `energy-reserve-v1` forecast without retuning. It
charges the proposed action, estimates post-extension upkeep, credits half of
current energy income across remaining daylight, and requires projected sunset
stores to cover a full night. It also requires one immediate upkeep charge after
spending and rejects paid night actions. The income credit is a heuristic, not
future knowledge or proof that the reserve will actually be adequate.

Water: charge the existing species-specific growth cost and require four
post-action water upkeep charges to remain, with no speculative water-income
credit. For an EXTEND, add one to non-root node count only for a non-root tip
with an available candidate. FINISH does not add a node. Water upkeep is the
ceiling of post-action non-root nodes divided by eight.

Root exception: if the base proposal's first available ranked destination is a
soil cell with moisture at least the water growth cost and strictly greater than
the current root tip's moisture, allow one water upkeep charge instead of four.
Do not reorder candidates, invent a root action or override the energy guard.
This uses visible current moisture, not a promise of future uptake or exclusive
access. Duplicate/invalid candidate rankings fail before applying any changes.

## Checks and outcomes

Before interpreting treatment, require each new disabled trace to match the
earlier full trace byte-for-byte, including all historical states. Retain source,
binary and configuration hashes at collection start/end. Repeat all six runs
byte-for-byte; stop on inconsistency. The only treatment difference is the
explicit focal option, never different binaries or climate settings.

Validate every override's lineage, age, original proposal, forecast and WAIT
transformation. Every pre-intervention state and every unmodified decision
prefix must match its paired control. Reconcile live resource budgets and exact
terminal receipts, avoiding inferred income from cleared dead-plant fields.

Primary diagnostic outcomes: focal survival at one and two full days, exact
death time/shortage if any, resource income/spending/upkeep, body size and actual
root/shoot actions. Successful establishment requires being alive at the full-day
boundary, not merely reaching the original death time. A two-day observation is
a durability check, not ecological qualification. Retain later focal death or
survival through day 128, not only the selected checkpoints.

Report existing neighbors' fates (IDs already alive before focal birth), including
earlier deaths through day 128. Later offspring IDs are not matched across
diverged worlds. Record world births/deaths and final living/viable species.
Never call a focal rescue a cost-free gain if it worsens existing neighbors.

Render both arms at the focal one-day and two-day boundaries, twelve fixed
frames total; check audited state hashes and RGB565 framebuffer CRCs. Keep
portable focal histories, checkpoints, summary, image checksums and controls;
full raw traces remain in ignored artifacts. Add boundary/error/default-identity
tests and run default/research/player/firmware regressions.

Stop after this candidate's panel and report positive, negative or mixed evidence.
No promotion or further rule modification follows without discussing the result.
