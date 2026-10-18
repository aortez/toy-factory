# Fixed first-day reserve component comparison

Freeze this follow-up before collecting new outcomes. The
[combined reserve trial](seedling-reserve.md) rescued two selected failures, but
the water example also received an energy veto. Separate those components; do
not retune the rule or select replacement examples.

## Panel and interventions

Use exactly the same three wide-scattering, seasonal, 128-day worlds:

| Example | Layout / base policy / seed | Focal lineage | Birth tick | One / two day captures |
|---|---|---:|---:|---|
| Energy failure | rainfed / baseline / a9c30c1f | 35 | 434565 | 438405 / 442245 |
| Water failure | rainfed-crowded / baseline / ed52188d | 41 | 433305 | 437145 / 440985 |
| Survivor | rainfed-crowded / adaptive / 4f0b9246 | 39 | 468045 | 471885 / 475725 |

Four arms per world: disabled control, unchanged combined guard, energy-only,
and water-only. All use one binary and the same seeds, weather and 256-node /
eight-plant / eight-seed capacity. The combined and disabled traces must reproduce
the previous frozen full traces byte-for-byte before interpreting the new arms.

The original [rule and thresholds](seedling-reserve-protocol.md) are unchanged.
Energy-only enforces the energy forecast (including the paid-night veto), ignoring
the water test. Water-only enforces the water floor and its existing wetter-root
exception, ignoring the energy forecast **including its paid-night veto**. Both
forecasts are still logged for audit, but only the selected component decides.
Combined requires both as before. Preserve base arbitration, priority, candidate
ranking, proposed recurrent memory, and WAIT transformation/clearing. Do not
promote a root or select a different winning tip.

Only the named offspring's ages 1..256 are eligible, birth inclusive and the
full-day boundary exclusive. No founder protection, later-age intervention,
germination changes, added resources, seed-spending gate, new training, firmware
changes or default promotion. The explicit host option requires a focal ID;
omitting a component retains the old combined behavior and trace format.

## Evidence and interpretation

Repeat all twelve runs byte-for-byte. Freeze sources, binaries and flags at
collection start/end. Validate all live budgets, terminal receipts, forecast
arithmetic, effective component decisions, cohort boundaries and matched
pre-intervention prefixes. Reconcile complete first-/second-day focal ledgers,
then retain lifetime and daily histories through day 128. Preserve adverse and
unchanged cases; do not stop a treatment at the old death tick.

Report one-day/two-day survival, later death or survival to the fixed horizon,
body/root/leaf counts, resource income and spending, unmet upkeep, direct veto
counts, and whether the wet-root exception actually admits a bid. Track all
fourteen pre-birth neighbors by identity, especially the water example's parent
#5, plus world births/deaths, final population, viable species and focal
germinated children. Do not match newly diverged offspring by numeric ID.

Render only the two new arms at the fixed one-/two-day boundaries (twelve new
images), using the shared production renderer and checking state hashes and
framebuffer CRCs. The previous twelve combined/control images remain frozen.
Retain portable histories, summaries, provenance and image checksums; keep raw
full traces in ignored artifacts. Add component-selection/boundary/error tests
and run default, research, player and firmware regressions.

This is a selected three-example mechanism test, not an unbiased population
confirmation. Survival is not reproduction; replacing a founder may be useful
turnover without increasing population or diversity. Stop after this fixed
panel to discuss whether either component or their combination warrants a wider
test. No threshold search or ecological promotion follows automatically.
