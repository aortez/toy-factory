# Post-noon rotating seed-purchase order: fixed host A/B

Follow the [reproduction-access audit](renewal-reproduction-access.md). Test
allocation separately from establishment, without increasing capacity, changing
costs/gates or giving the focal shrub preferential treatment.

## Frozen inputs and rule

- Parent bundle: `artifacts/garden-renewal-dawn-reserve-v1`, manifest SHA-256
  `ee74ce6b80ff164c5f2358fbcc9829832fac6debebc032086e78b2c52a39f06b`.
- Parent portable SHA-256:
  `2cbf7bb6b4568bce1f022d8ff28d330e473b3ca46ebd031e2a44688ceadb3163`.
- Access audit SHA-256:
  `6a64a9792486ab03267b0d077514c84978e58b062743624625291830cf86fae3`.
- Exactly two arms: `fixed` reproduces the saved reserve arm; `rotating` adds
  only the host-only `maintenance-seed-rotation-v1` rule. Same seed `0d983a80`,
  rainfed-crowded world, N background/descendants, W founder 5, selective leaf
  renewal, night/capacity guards, named founder-1 export and wet germination at
  46,080, reserve-aware FINISH handoff, 512 nodes, eight plants/eight seeds.
- Through tick 69,120 inclusive, visit original plant-array order. Thereafter,
  on a reproduction maintenance tick, start at
  `((tick - 69120) / 60) % plant_count` and visit every slot once, wrapping.
  The first eligible rotation tick is 69,180, start index 1 for count > 1.
  Empty populations and off-cadence steps use index zero. Dead/ineligible slots
  stay in the traversal; no extra turn, bypass, retry or resource grant.
- Never reorder the plant array or seed bank. All other stages and each
  plant's single cooldown decrement remain unchanged. The stateless rotation
  uses only the existing tick and current array length, with no random draws.
  Its opt-in is per-world host experiment configuration, disabled on reset and
  absent from firmware/default builds. Like the existing FINISH diagnostic,
  this selection is recorded separately from the physical world hash.
- Changing population size changes the modulo; fixed phase/count combinations
  can alias. This tests allocation effects, not a general fairness guarantee.

## Fixed capture budget and outcomes

Run through 245,760/day 64. Compare whole-run, first-noon-and-later, and closing
184,320 < tick <= 245,760 outcomes. Do not equate newly assigned lineage IDs
across diverged arms; track the preexisting target 12 and ancestry explicitly.

Exactly **16 experimental native calls**: per arm, world/bid census and seed-site
census, each twice (four calls), plus actual framebuffer replays at 69,120 and
245,760, each twice (four calls). Complete and verify all fixed-arm historical
traces and those two historical frames before starting rotating. No training,
extra world seeds, tuning, device work or outcome-selected screenshots.

Retain all original streams/receipts, immutable source/build/binary/model
fingerprints, derived lineages, seed lifetimes, budgets and per-parent/window
access categories. Check the seed append order against the independently
calculated traversal, fees and native receipts. Keep conservative maturity
unknowns and distinguish bank blocking from an actually evaluated safety guard.

Report purchases by parent, bank release/refill patterns, gate/guard refusals,
resource spending, target survival/stress, all births/deaths, full-day offspring
survival, reproducing descendants and final species/families. Assess germination
and stable spacing witnesses for every target seed. More target seeds alone is
not success; displaced costs/deaths and no new establishment are valid results.

## Validation and stopping

Before collection, test native traversal boundaries, empty/single/full arrays,
wrap/current-count behavior, reset/isolation, full-bank cooldown decrements,
ordinary gates, exact seed fees and multiple available slots using synthetic
worlds. Test CLI misuse and default-build rejection. Test analysis ordering,
input preservation, fixed command inventory and fail-closed evidence handling.
Format changed C; run default and experimental host CTests.

Verify the old control byte-for-byte, candidate prefix through noon (ignoring
only its explicit order metadata), exact repeats, world/site/frame agreement,
resource and lifetime accounting, and immutable inputs before sealing results.
Repeat offline analysis and verify portable export independently in Docker.
Analysis-only recovery may fix tooling, never rerun or replace captured worlds.
Any failure is recorded; no undeclared experimental calls are silently added.

Update the report, roadmap and issue #30. Stop uncommitted and discuss the next
step. Do not promote the rule, loosen spacing/gates or resume training here.
