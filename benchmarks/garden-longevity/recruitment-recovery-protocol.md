# Disturbance openings and recruitment recovery: fixed diagnostic

Continue the four renewal-stall trajectories, not a new controller comparison or
training panel. Source: `garden-renewal-stalls-v1`, manifest SHA-256
`7e2b0136cfc43babd2d8ffd9442fefe6239eaa3a5ce1a73e588df58ddcb7c1ca`.
Original `dc5e849d` and broad-final `c7c1b31e`; seeds `1824c139` and
`4d5f9ee1`; fresh-2 patch schedule `17c29444`. No policy, ecology, scoring,
capacity, seed-placement, RNG, firmware or device changes. No commit/push.

## Collection fixed before running

Use existing native inspector and seed-attempt binaries with unchanged C/header
sources and the same 512-node/8-seed maintenance build configuration. Pin these
binaries, source snapshot, models, original lifetime ledgers, and previous census
logs in a new bundle. Twelve native processes: for each trajectory, one full
world census and one seed-site census from reset through day 126, and one exact
sequential seed-attempt trace from day 62 through 126 (reset prefix unchanged).
No extra replays, screenshots or stochastic trials; the preceding 16-frame
gallery supplies the visual context. Native captures are serial and immutable.

Require continuous 15-logic-tick ecology samples, complete identical fixed patch
events, world/site hashes at every tick, and exact attempt/world hashes throughout
(62,126]. Validate sequential seed visits, allocation, spacing, dormancy, expiry,
resource checks and germination using the existing seed-attempt validator.
Match every available previous census (including post-patch samples), original
seed identities/fates and birth/death records. Reject divergence; do not explain
an altered trajectory. Reanalyze deterministically before sealing the bundle.

## Diagnostic definitions

- Report both the original weak interval **(62,94]** and recovery interval
  **(94,126]**. Include every scheduled patch in (62,126], including no-hit
  patches; do not select only patches followed by success.
- A death is not yet a vacancy: the dead plant occupies its slot, nodes and
  spacing until reclaimed. Record each victim's actual reclamation tick.
- A **geometric opening** passes slot, node and spacing gates. A **usable site**
  passes all ordinary gates for a hypothetical mature seed at that column, at
  the exact pre-germination stage. This is instantaneous eligibility, not proof
  a real seed exists there or that the resulting child would survive.
- Separate anywhere-open from local-open: local columns are those within two
  columns of a killed plant's base (its former spacing footprint, clipped to
  columns 0–27). A patch does not guarantee such an opening ever becomes usable.
- For actual mature seed attempts, distinguish an open column anywhere, an open
  column within the parent's dispersal support recorded at seed creation, and
  the seed's actual column being open. Support is a spatial upper bound, not a
  new RNG draw, probability or ability to retarget an existing seed.
- Check sequential competition explicitly: a mature seed whose actual column
  was open at the start of the seed loop but is blocked at its own visit has
  lost eligibility to an earlier germination in that step. Do not infer such
  losses from post-step closed sites.
- Each event owns ordinary steps **after its tick through the next event's tick
  inclusive**; that next ordinary step precedes the next patch. The initial
  day-62-to-first-patch interval is left-censored context, not credited to an
  unobserved event. Stop at day 126; the last interval is right-censored.
- List all births in each event interval, local versus elsewhere, parent class,
  birth delay, full-day survival and qualifying descendant renewal separately.
  First-day fate uses only each child's own confirmation deadline (at most day
  127) in the already-validated original ledger, even if another patch happens
  before that deadline. A pending deadline is not a failure. Report first usable
  site, first birth and first surviving recruit; do not assign a later birth to
  multiple overlapping events or claim a causal patch effect without a control.
- Aggregate attempts separately by founder/established/young descendant at the
  attempt tick, and preserve event-level detail. Exposure counts are ecology
  observations, not independent samples or germination probabilities. Include
  failures, no-open intervals, no-hit patches and natural deaths as context.

Test boundary ownership, corpse occupancy, hypothetical versus actual/reachable
opportunities, sequential competition, confirmation/death boundaries and trace
validation. Preserve all prior fitness results. Stop after this explanation and
a concrete next recommendation: no opportunity-normalized fitness, reliability
gate, intervention or new training is automatically adopted by this diagnostic.
