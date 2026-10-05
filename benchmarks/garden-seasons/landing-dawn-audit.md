# Dawn funding audit results

The saved histories confirm a small but real gap between surviving the night and
funding the morning. The two stressed dawns need 21 and 15 energy after the dawn
payment to avoid further shortages on their recorded paths. The second also
arrives at dawn two energy short. First positive income is not necessarily
enough to pay maintenance.

A current-light reserve estimate would restrict five recorded purchases on the
rescued plant and two on another survivor. It is not a guaranteed funding bound:
weather, body growth and delayed leaf income can invalidate its assumptions.
This supports a bounded paired replay, not a default-policy change.

The [protocol](landing-dawn-audit-protocol.md) fixes the input, accounting and one
diagnostic. The audit reads the [daylight comparison](landing-daylight.md), with
zero native calls or training runs. No plant trajectory, C code, firmware or
ecology rule changed.

## Complete coverage without treating duplicates as trials

All ten focal histories contain 53,880 samples. Removing identical complete
physical histories leaves seven histories and 34,908 samples. Those histories
still share some identical early mornings, so the audit also deduplicates whole
dawn-to-noon physical windows separately.

There are 210 recorded mornings, 136 after whole-history deduplication, and
133 distinct morning windows. All reach noon. Only two distinct mornings have
energy shortages; one appears in both rotating-49 arms before they diverge.
There are 211 sunset-to-next-noon windows, including the control's final night
ending in death. Missing future samples after death are not filled with zeros.
These selected, overlapping observations are not independent weather trials.

Across complete mornings, the minimum required opening energy ranges from 6
to 21. The requirement is identical whether including recorded growth and
reproduction or charging only maintenance on the recorded body path: early
maintenance determines the limiting balance in these histories. That does not
mean growth is free or its timing could be changed without consequences.

## The two shortage episodes

Both episodes are from rotating 49. Values below start after the preceding
sunset's maintenance payment. Requirements keep the recorded future income,
body and spending schedule fixed; they do not simulate changed reserves.

| Quantity | Dawn at tick 912960 | Dawn at tick 916800 |
| --- | ---: | ---: |
| Preceding sunset stores | 128 | 126 |
| Nominal night upkeep | 128 | 128 |
| Unpaid at dawn itself | 0 | 2 |
| Energy remaining after dawn | 0 | 0 |
| Required after dawn through noon | 21 | 15 |
| Required at preceding sunset through noon | 149 | 143 |
| Shortfall from actual sunset stores | 21 | 17 |
| First positive income phase | 22 | 16 |
| First positive income amount | 1 | 1 |
| First fully paid maintenance after shortages | 913380 | 917100 |

At the first dawn, five maintenance payments require 20 energy before the first
income at 913290. That first income does not end the shortage episode: the
payment at 913320 is still one energy short. The full recorded morning needs
21 energy after dawn, not just the 20 needed through first light. Six shortage
events occur, with the first fully paid payment at 913380.

At the second dawn, the last afternoon root purchase had projected 128 at sunset,
but only 126 was available. Its two-energy forecast error explains the partly
unpaid dawn payment. The morning then needs another 15: three dark payments
cost 12, and the first one-energy income arrives on a four-energy payment step.
Five shortage events span dawn through tick 917040; maintenance is fully paid
at 917100. There are no further shortages before noon in either episode.

The plant survives both, but avoiding death and funding every payment are
different outcomes. Neither episode is evidence of a missing resource subsidy.

## Useful global light and actual income differ

Global strength first reaches 64 at phases 11–22 across these mornings. Actual
income sometimes starts later, as late as phase 40. Three distinct early windows
show that distinction:

| Plant and dawn tick | First globally useful phase | First income phase | Opening stores | Required stores |
| --- | ---: | ---: | ---: | ---: |
| Rotating 48 at 901440 | 13 | 26 | 23 | 6 |
| Rotating 49 at 909120 | 18 | 40 | 29 | 9 |
| Rotating 50 at 909120 | 18 | 37 | 27 | 9 |

All three have enough reserves and no morning energy shortages. Global light is
a necessary condition for this build's integer leaf uptake, not a sufficient
condition for income from the current plant. The audit does not assign these
delays to unrecorded individual leaf positions or occluders.

## One current observation diagnostic

At each paid afternoon decision, hold current attenuation constant and use the
known daily sun curve to estimate the next morning's first globally useful
phase. Round that phase up to a maintenance boundary and reserve the current
post-action upkeep through that payment, without crediting morning income.
An estimate that never reaches useful light is explicitly unavailable; it is
not silently given a default buffer. No such unavailable estimate occurs among
the candidate's 78 recorded active afternoon purchases.

Compare this extra reserve with the existing projected-sunset margin and, for
maintenance increases, the separate stores-only margin. The calculations are
inactive references on controls; only the daylight candidate's purchases are
classified as newly restricted.

| Candidate | Active afternoon purchases | Newly restricted purchases |
| --- | ---: | ---: |
| Fixed 45 | 20 | 0 |
| Fixed 46 | 8 | 0 |
| Rotating 48 | 16 | 0 |
| Rotating 49 | 19 | 5 |
| Rotating 50 | 15 | 2 |

Rotating 49's affected ticks are 910425, 910980, 914130, 914325 and 914400.
The first two increase maintenance; later ones include a shoot extension,
FINISH and root extension. At tick 910980 the current-light estimate reserves
20, but the following morning actually requires 21. It predicts useful global
light at phase 20 rather than the observed phase 22, even with the same upkeep
rate. Rounding to a payment boundary does not guarantee a conservative result.

Across all 78 candidate purchase observations, the estimate is below the later
morning requirement 40 times, equal eight times and above it 30 times. Errors
range from −11 to +9. These comparisons include subsequent body growth, not
only light-prediction error; multiple purchases refer to the same later morning.
They are not 78 independent tests of a policy.

The successful-growth risks are rotating 50's FINISH at 910140 and root
extension at 910530. The first has a projected sunset of 109 against a nominal
night cost of 96; adding the estimated 15 reserve would reject it. Actual sunset
stores reach 206. The later extension's stores-only margin is 3 against an
estimated 20 reserve. That plant has 78 energy after dawn and no shortage.
Rejecting either recorded action does not prove harm, but preserving this
survivor must remain an explicit check in any replay.

## Accounting and validation

Uptake is capped at 256 before maintenance, growth and reproduction. The audit
checks that ordering against captured sources, reconstructs maintenance due from
the pre-maintenance node count and four-step cadence, and distinguishes due,
paid, unpaid and terminal discard. Persistent shortage flags between payments
are not counted as additional events.

Minimum opening reserves are calculated backward over the frozen schedule.
At each step, required energy after uptake is future need plus this step's
costs; more than 256 is unfundable. Otherwise subtract that step's gross income,
with a floor of zero. This recalculates cap effects rather than treating observed
overflow as a fixed cost. Tests compare the backward minimum against an
independent forward search over all possible opening balances. Maintenance-only
calculations retain the recorded body path while omitting its growth cost.
Terminal discard is not a cost to fund. Dead/censored windows yield requirements
only over the observed prefix, not a claim of survival beyond it.

## Proposed next comparison

Test this one predeclared diagnostic as an additional afternoon spending check
in the same five pairs. Keep the current daylight guard as control, retain
historical checkpoints and exact repeats, and change no morning rules, birth
roots, subsidies, model, bank capacity or ecology. Restrict the treatment to the
same named offspring rather than generalizing it to the population.

Measure the actual shortage events, survival, growth delays, reproduction and
other plants' outcomes. Preserve rotating 50 as the successful-growth risk check.
The test should determine whether repeated decisions with the extra margin
improve the paths, not assume the forecast is a guarantee. Define unavailable
estimates explicitly before running; do not select a fallback after observing
results. This comparison has not been implemented or run in the audit.

The subsequent [paired dawn-reserve comparison](landing-dawn.md) now tests this
diagnostic without tuning: it removes rotating 49's energy shortages and retains
all five survivors. Rotating 50 has fewer water shortages but fewer final roots;
focal seeds and population life/seed ledgers do not improve.

## Reproduction and evidence

`make host-audit-landing-dawn` writes a fresh bundle. Set
`GARDEN_LANDING_DAWN_AUDIT_OUT=artifacts/new-dawn-audit` to repeat it. Only the
pinned portable inputs are needed; there is no simulator build, USB connection
or original large trace-bundle requirement.

```sh
docker compose run --rm -T firmware python3 sim/garden_landing_dawn_audit.py \
  --verify benchmarks/garden-seasons/landing-dawn-audit-results.json.gz
docker compose run --rm -T firmware python3 sim/garden_landing_dawn_audit.py \
  --verify artifacts/garden-landing-dawn-audit-v1-final
```

| Artifact | SHA-256 |
| --- | --- |
| [Portable audit](landing-dawn-audit-results.json.gz) | `6cdfc3ae4318042a6d40d983f369463771e9f326f86a3a7c75a2d67003ee3c88` |
| Final raw manifest | `98c34cc0d4bb7a54990665748019c2fc5b6e80d432e6b2881ffd601799b9593d` |
| Protocol | `bec1f80a596198a8fe28eddf43aa5e3504761b65950bf9e35c9eb336a7fbc7da` |
| Frozen input | `9e2acb8cf141e75307020c0b854c3a76611942cec615c21b95db750c97d7748b` |

The final pair of exports is byte-identical and retains export-time source
archives and patches. An earlier pair is retained too; stricter invalid-input
validation was added between the pairs, with identical analysis results. This
report and the final artifact assertion were added after export. No additional
native simulation was used for any export or verification.

All 16 dawn-audit tests pass without skips, alongside the 18 light-audit and
16 energy-audit tests: three passing focused CTest entries in 34.29 seconds.
Raw and portable reanalysis pass, including source-archive verification.
Tests cover capped funding, cadence, current-only estimates, unavailable cases,
death/censoring, corruption, read-only inputs and no-clobber output. The full
native suite was not rerun for this Python-only step; the preceding 180-test
result belongs to the daylight comparison.
