# Fixed all-offspring first-day reserve screen

Freeze this protocol before collecting treatment outcomes. Extend the unchanged
[combined reserve rule](seedling-reserve-protocol.md) to every newborn offspring,
following the [component comparison](seedling-components.md). This is an
exploratory extension on known weather seeds, not a fresh confirmation or training
run. No thresholds, ecology or device defaults are promoted.

## Fixed panel and candidate

Use all 32 **wide-scattering seasonal** worlds from the retained
[eight-seed confirmation](dispersal-confirmation.md): rainfed/rainfed-crowded,
baseline/adaptive, and seeds `ed52188d`, `4f0b9246`, `a9c30c1f`, `0bb887d0`,
`647001a9`, `c629bb62`, `20e1353b`, `82deacfc`. There are eight weather blocks,
not 32 independent weather replicates. Run all pairs through day 128 (491,520
logic ticks), keeping the same 256-node/eight-plant/eight-seed ecology and seasonal
climate. Both arms use one isolated host binary. Narrow scattering remains the
normal host/device default.

Control: unchanged base policy. Treatment: both existing reserve checks apply
to every living non-founder at ages 1..256 ecology samples, birth inclusive and
the full-day boundary exclusive. Ages 257 onward and all founders use the base
policy. Preserve candidate ranking, priority, arbitration and proposed memory;
rejected paid proposals become WAIT. Keep the existing wet-root exception and
energy night veto. No added resources, changed seed spending, gardener, irrigation,
capacity increase, neural training or individual selection after seeing outcomes.
Expose `--seedling-reserve all` explicitly; retain numeric-ID behavior and
disabled defaults. Reject single-component experiments with the all-offspring
selector in this bounded implementation.

## Checks and retained evidence

Repeat all 64 full traces byte-for-byte. Check all 32 control daily hashes,
lifetimes, deaths and seasonal histories against the frozen earlier wide worlds.
The six previously saved full control/combined named-seedling traces must also
match byte-for-byte with the new binary before collecting the broader panel.
Freeze sources, binaries and flags at start/end; do not change them mid-run.

At every ecology sample, check cohort eligibility, age/forecast arithmetic,
effective decisions, winner/priority consistency, all live resource budgets and
exact terminal receipts. Check complete identical prefixes before the first
changed bid, and equal external climate/light/rain schedules afterward. Reconcile
birth ancestry, deaths, missing/reclaimed plants and daily outcomes. Do not match
numeric offspring IDs between diverged worlds; match only initial founders.

Keep all lifetimes, daily histories, terminal receipts and per-lineage intervention
counts in a portable compressed archive. Raw full traces and their repeats stay
in ignored artifacts. Render the first seed, baseline policy, both layouts and
both arms at days 16 and 128: eight fixed images, not attractive-case selection.
Check native state hashes, RGB565 CRCs and PNG hashes; inspect the images.

## Outcomes and fixed screening gates

Use both the full history and the closing-year birth window (strictly after day
112). Keep denominators: eligible births have a full day of possible follow-up;
death on the one-day boundary fails, and younger births are censored, not survivors.
A durable descendant parent must itself survive a full day and have at least one
germinated child which survives a full day. Also report two-day eligibility/
survival, early-death resource/weather categories, survivors without a child,
living/dead founders, population/seed/species endpoints, seeds created/expired and
transient empty worlds at every ecology sample.

Primary question: does first-day protection improve **continuing renewal** rather
than simply keeping more initial descendants alive? The aggregate exploratory
screen passes only if all the following hold:

1. Retain closing-year birth worlds, full-day survivors and durable parents;
   retain historical durable descendant parents and multi-species endpoints.
2. Strictly improve at least one closing-year measure above (birth worlds,
   full-day survivors, durable parents).
3. Do not lower the closing-year eligible survival fraction. Compare exact
   numerator/denominator cross products; a nonempty control cohort and empty
   treatment cohort fails, while a previously empty cohort is reported separately.
4. No newly empty world (living plants and viable seeds both zero) and no new
   zero-living-plant endpoint compared with its paired control.

These are exploratory retention gates, not a fitness function or promotion
permission. Show increased/unchanged/decreased worlds for each metric, and
aggregate by weather seed, layout and controller so aggregate gains cannot hide
adverse blocks. Report founder turnover as an outcome, not an automatic veto:
replacement can be useful, but survival without reproduction is insufficient.
Even a passing screen needs discussion of adverse worlds and fresh confirmation.

Stop after this fixed panel, whether positive, mixed or negative. Do not tune
thresholds, replace bad seeds, extend only favorable runs, or start training.
Run boundary/error/default-identity tests and default/research/player/firmware
regressions before reporting. Keep all earlier evidence unchanged.
