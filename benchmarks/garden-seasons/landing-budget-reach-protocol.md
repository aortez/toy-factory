# Frozen parent-reach audit after shoot reservation

This read-only follow-up asks whether seeds blocked in the final seasonal
period had open alternatives inside their producing parents' ordinary
dispersal support. It does not test a placement policy or change ecology.

## Fixed panel and inputs

Use all six seasonal worlds from `landing-budget-results.json.gz`, both
`eligible` and `reserve` arms, in saved order. The input SHA-256 is
`bad5297fa26ad52b93a899e3d0f0fcd3255a6b5e214e1120f68bc3902e455640`.
The matching recruitment window input is
`landing-budget-germination-windows.json.gz`, SHA-256
`9de2ef4f06c7f435c666d11c75fc7f0211351bdd246161cded3dbbcd6fc61099`.
No model selection, mutation, training, seed changes, score changes, or
replacement controls are allowed. All experimental ecology flags remain off.

Run each world through 192 Garden days with the existing host-only
`budget-replay --shoot-reserve off|on` policy. Collect whole-run reach receipts
to retain actual purchase-time parental origins and traits for carry-in seeds.
The report interval is strictly **(158,190] days**, matching the saved final
renewal period. Include carry-in seeds and purchases through its endpoint;
censor outcomes at day190, not at the replay's day192 endpoint.

## Observations and their limits

At purchase, enumerate all six ordinary production choices using the actual
parent's dispersal trait and boundary reflection. Preserve duplicate choices;
they are not six guaranteed distinct columns or an assumed uniform lottery.
Keep this support for the seed's lifetime, even if its parent later dies.
Never reconstruct it from the child's mutated genome.

Purchase site masks are hypothetical mature-site gates after that step's
final light refresh, not admission guarantees. Mature-check masks are taken
at the exact sequential germination point, including earlier births in the
same step. Expiry is checked before site testing and must remain `null`.
Dormant samples must not be counted as mature opportunities.

Compare global open columns with reachable open columns and alternatives to
the actual landing. Report actual purchase-time opportunities separately
from later opportunities, and separate carry-in/purchased and
expired/germinated/pending cohorts. Retain per-column first/last/longest open
streaks and overlapping reasons when every reachable site is blocked.

An open alternative is an opportunity on the **unchanged trajectory**, not
proof of a rescued child, positive first-day survival, or sustainable renewal.
Changing placement would change later occupancy, light, resources and RNG
consumption; any intervention needs its own matched experiment.

## Required parity and evidence

For each of the twelve arm/world combinations run:

1. Combined reach and recruitment tracing; require the entire result and
   recruitment trace bytes to match the historical budget run.
2. No observers, with endpoint pixels; require the historical state and pixels.
3. Reach tracing alone, with endpoint pixels; require identical reach bytes,
   state and pixels to the first two runs.

This is 36 native replays and zero training runs. Validate all whole-run seed
lifetimes against the saved recruitment audit. Independently reconcile each
final-period reach check with the frozen recruitment window, including
sequential identity, actual mask, global-open count, expiry and offspring.

Use fresh output paths and freeze the protocol, source snapshot, binary,
build configuration, model bytes and inputs. Abort if they change during
collection. Retain raw full traces, endpoint pixels, whole-run audits,
portable final-window receipts and audits, and an artifact-hash manifest.
Offline verification must rederive the portable window audits; full-bundle
verification also rechecks complete lifetimes, exact excerpts and all hashes.

Stop after this audit and propose a bounded next test based on its findings.
Do not enable placement changes, retrain, promote a model, or flash hardware.
