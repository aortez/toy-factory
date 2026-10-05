# Parent reach limits the missed seed opportunities

Most seeds in the reserved-shoot final periods cannot escape occupied
neighborhoods using their parents' existing dispersal choices. Across the six
seasonal worlds, **78 of 97 seeds have every reachable column spacing-blocked
at every mature check in (day 158, day 190]**. Globally open space is therefore
not a sufficient placement diagnosis.

There are missed reachable openings, but they are concentrated in three
worlds. Only **1 of 49 new purchases** has a reachable site passing all
hypothetical mature-seed gates at purchase. Nine purchases instead have a
spacing-clear alternative while their actual landing is spacing-blocked.
That makes occupancy-aware placement a more useful bounded next test than
requiring an immediately germinable site. Neither has been implemented here.

This is the read-only follow-up to the
[final-period germination audit](landing-budget-germination.md), not another
policy screen. All twelve seasonal arm/world results, recruitment traces and
endpoint pixels reproduce exactly. No model, ecology, score or device default
changes; the original shoot-reservation screen remains failed.

## Reachable openings are unevenly distributed

Each seed keeps its actual producing parent's origin and dispersal trait from
purchase, including seeds carried into the window. The six ordinary production
choices retain reflection duplicates; they do not guarantee six distinct sites.
The report counts a site as open only when all instantaneous mature-seed gates
pass at the exact sequential germination check.

| Reserved world | Seeds in window | Seeds with any globally open site | Seeds with any reachable open site | Seeds whose entire support stays spacing-blocked | Blocked checks with a reachable alternative |
|---|---:|---:|---:|---:|---:|
| Single /33 | 16 | 14 | 3 | 12 | 186 |
| Multi /33 | 16 | 16 | 4 | 12 | 339 |
| Single /34 | 17 | 16 | 1 | 16 | 0 |
| Multi /34 | 16 | 15 | 0 | 16 | 0 |
| Single /35 | 16 | 16 | 10 | 6 | 1,434 |
| Multi /35 | 16 | 14 | 0 | 16 | 0 |

The one reachable-open seed in single /34 is the already-observed germination,
not a missed landing. Its only open mature check succeeds. The resulting child
still dies energy-short before its first day, as established by the preceding
resource audit.

Among the four zero-credit worlds (/33 and /35), there are 13,044 blocked
mature checks with a globally open site, but only 1,959 with a reachable
alternative. These occur in 93, 173, 494 and zero distinct ecology samples,
respectively. Several seeds can be checked in one sample, so check counts are
not independent opportunities or predicted additional births.

The 97 seeds comprise 48 that expire during the window, one that germinates,
and 48 still pending at day 190. Nine of the expired seeds and eight of the
pending seeds encounter reachable openings during the window. Pending seeds
are not classified as complete-lifetime failures. All statistics above cover
only the selected interval, not every seed's earlier life.

### A concrete reflected-range trap

In single /33, parent 18 is based at column 2. Its six production choices are
`[8, 8, 9, 9, 10, 10]`. Its twelve carry-in/replacement seeds collectively see
no spacing-clear reachable site in this interval. The earlier audit identifies
the persistent living neighbor at column 9 as a spacing witness. Choosing among
these three distinct columns cannot avoid that neighbor on the observed
trajectory.

The four seeds from parent 20 in the same world have a different support,
`[2, 16, 1, 17, 0, 18]`, and account for all 186 reachable-open checks.
This is why a global opening count cannot substitute for per-parent reach.

## Purchase-time choices are not later opportunities

| Reserved world | New purchases | Actual landing spacing-blocked, with a spacing-clear alternative at purchase | Any fully open reachable site at purchase |
|---|---:|---:|---:|
| Single /33 | 8 | 2 | 0 |
| Multi /33 | 8 | 2 | 0 |
| Single /34 | 9 | 0 | 0 |
| Multi /34 | 8 | 0 | 0 |
| Single /35 | 8 | 5 | 1 |
| Multi /35 | 8 | 0 | 0 |

For example, single /35 parent 22 buys a seed at day 159.875, choosing occupied
column 21. Its support includes spacing-clear columns 11 and 23; column 11 passes
all hypothetical gates at purchase, while column 23 does not. During the seed's
subsequent mature checks, column 23 first opens at day 159.90625, whereas column 11
first opens at day 168.06640625. Instantaneous moisture/light conditions at
purchase are not a forecast of conditions when a seed can germinate.

Purchase masks are recorded after the step's final light refresh; mature
checks use the exact native germination-stage masks. Neither observation is a
guarantee that moving a seed would preserve the later environment or produce a
surviving child. Carry-in purchase observations may predate day 158 and are kept
separate from the 49 purchases in this table.

The eligible-32 controls are retained, not silently replaced by the candidate.
All six have globally open sites during the window; multi /34 has no reachable
openings, while multi /33 has reachable openings but still no births. The other
four controls retain their 46 births and 23 first-day survivors. These are
diverged populations, not matched individual rescues or evidence that every
control is healthy.

## Next bounded experiment

Test a host-only **spacing-aware landing choice within the same six existing
production choices**, with an unchanged fallback when none is spacing-clear.
Preserve parent support, reflection multiplicity, ordinary spacing, resource
costs, dormancy, lifetime, capacities, RNG discipline and renewal scoring.
Do not require moisture/light/cold gates to pass at purchase: the measurements
show that doing so would mostly suppress the question we want to test.

Compare against both frozen eligible and reserved controls across the existing
steady and seasonal panel. Measure germinations, first-day survival and later
renewal, not just avoided occupied landings. Fix the selection and fallback
rules before collecting results; no training or device promotion is warranted.

This cannot supply an alternative for every blocked seed on these saved
histories. Earlier changed landings could nevertheless alter later occupancy,
so the final-window opportunity counts are not a bound on a full-run
counterfactual. If renewal remains stalled, persistent adult occupancy and
environmental turnover remain the larger question. Do not relabel old survivors
as renewal by weakening the score.

## Reproduce and verify

The [predeclared protocol](landing-budget-reach-protocol.md) fixes six seasonal
worlds, both arms, whole-run tracing through day 192, and the (158,190] report
window. There are **36 native replays and zero training runs**: combined reach
and recruitment tracing, no observers with endpoint pixels, and reach-only
repeat with endpoint pixels for each arm/world.

Whole-run purchase identities and every seed check reconcile with the saved
recruitment audit. Final windows reconcile all 754,161 seed samples, including
753,329 mature checks, against the preceding frozen window export. Dormancy,
expiry-before-check, sequential births, endpoint purchases and future outcomes
are treated separately. The new C change only opts `budget-replay` into the
existing read-only reach publisher; ordinary firmware and policy code are
unchanged.

The [portable receipt and analysis bundle](landing-budget-reach-results.json.gz)
contains parent purchases, exact window rows, per-seed site histograms and
open streaks, cohort/outcome summaries, and collection provenance. Its verifier
recomputes window analyses without running a simulator. The retained local
bundle additionally verifies full lifetimes, exact window extraction, repeated
traces, historical recruitment, endpoint pixels and all 98 artifact hashes.

```sh
make host-trace-landing-budget-reach \
  GARDEN_LANDING_BUDGET_REACH_OUT=artifacts/new-budget-reach
docker compose run --rm -T firmware python3 -W error sim/garden_landing_budget_reach.py \
  --verify benchmarks/garden-seasons/landing-budget-reach-results.json.gz
docker compose run --rm -T firmware python3 -W error sim/garden_landing_budget_reach.py \
  --verify artifacts/garden-landing-budget-reach-v1
```

Outputs are fresh/no-clobber. The tests cover observer parity, partial horizons,
unchanged pixels/models, CLI restrictions, malformed support/check rejection,
window censoring, and fixed report counts. This reused panel is diagnosis,
not unseen validation or environment qualification.

All **160 ordinary host CTests pass** under UBSan (447.29 seconds, two workers),
including the six new focused cases. Full-bundle and portable verification,
formatter validation, Make help/dry-run and `git diff --check` also pass.
The local regression log is `artifacts/garden-budget-reach-validation.log`.

- Portable results SHA-256:
  `93cba7dfac249a4cca2326e6e163b89856f7d0e1268f3ac0a6eb0e3d7ca637aa`.
- Local manifest SHA-256:
  `b2c0c3a1852d483466425f2381e507f00b72d2fe3d902a0dbbdba06e2e0d97bc`.
- Frozen native binary SHA-256:
  `988c43c608bb9ebeccc4910b6a9b2cbb3b0cf568355a2c623f4725783fa3dc85`.
