# Crowded recruitment diagnostic: frozen protocol

Declared before collecting detailed site outcomes. This is a post-hoc explanation
of the completed reserve panel, not an independent generalization test.

Eight host-only runs, 192 Garden days each, both frozen policies per pair:

| Capacity | World / patch schedule | Reason selected from existing closing-day survivors |
|---|---|---|
| 256 | crowded `b61837dc` / fresh-4 | Adverse: baseline 7 → reserve 1 |
| 256 | crowded `b61837dc` / fresh-1 | Comparison: same world, different schedule, 4 → 8 |
| 512 | crowded `b61837dc` / fresh-1 | Adverse: baseline 13 → reserve 5 |
| 512 | crowded `c7f54e18` / fresh-1 | Comparison: same schedule, largest positive crowded/off gain, 3 → 7 |

All use drainage **off**, selective leaf maintenance, the previous combined host
ecology, model CRC `dc5e849d`, and unchanged `neural-no-night-growth` versus
`neural-reserve-growth` (`energy-reserve-v1`). Replay the verified executables
from the completed 256/512 reserve bundles. No training, firmware deployment,
policy retuning, ecological changes, or age-counter changes.

Collect world and seed-site censuses every ecology step, including both sides of
every prescribed disturbance. Keep ordinary pre-patch rows in the seed ledger;
count post-patch state separately for patch-follow-up observations. Analyze whole
run and days 160–192, split into bright day (sun strength ≥128), twilight, night.

Measure overlapping actual-seed blockers (water, light, nodes, plant slots,
spacing), mature-seed supply, hypothetical open columns, individual and joint
spatial-limit relaxations, seed creation/expiration/germination, censored seed
lifetimes, adult resources and dead-node occupancy. Record patch hits, exact
reclamation delays, first sampled opportunities and births before the next patch.

Post-step site masks are **not** the exact conditions at germination attempts:
germination precedes growth, reproduction and the final light update. Hypothetical
relaxations neither change the simulation nor demonstrate offspring survival.
Do not interpret repeated snapshots as independent trials or no post-step opening
as proof that no transient opening occurred. Dispersal support is not probability.

Checks: per-step world/site hashes, both event boundaries, prior sparse-census
hashes and final/lineage/cohort equality; frozen executable/model/source digests;
independent day-64/128/192 replay hashes and final RGB565 CRC/byte equality.
Preserve all traces, event records, analyses and native screenshots in a new
no-overwrite artifact bundle. Final paired screenshots use all eight runs at day
192. Tests cover overlapping blockers, dormancy/supply, identity mismatch,
truncation, event boundaries, and native observer neutrality.
