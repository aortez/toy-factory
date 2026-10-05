# Host landing-model replay and evaluation

For the current review boundary and grouped findings, start with the
[adult resources and renewal checkpoint](garden-adult-resources-checkpoint.md).
This guide is a command reference, not a recommendation to rerun every
historical experiment. Capture commands require fresh outputs and their
declared source/build context; use each report's offline verification path
when reviewing retained evidence without new simulations.

The [experimental TGL2 network](garden-landing-inference.md) now has explicit
host file, replay, and matched-evaluation commands. This is tooling, **not a new
training score or evidence that the added observations improve plant fitness**.
The old trainer/player, firmware, and ordinary ecological defaults are unchanged.
The later [bounded training pilot](garden-landing-training.md) adds `mutate` and
`replay --ledger`, reusing the established renewal score in a separate experiment.
The [frozen validation panel](garden-landing-validation.md) adds explicit
`ablate IN.tgl NEW.tgl off|current` derivation without modifying any weights.
The [signal-content probe](garden-landing-signals.md) adds a separate
`probe-replay` command with explicit occupancy/resource interventions and a
probe-aware identity; ordinary replay and TGL2 files remain unchanged.
The [same-state observer](garden-landing-decisions.md) adds explicit `trace-replay`
with a separate trace file. Its alternative proposals never advance the world;
the normal replay JSON and GLR1 run identity remain unchanged.
The [reach observer](garden-landing-reach.md) adds `replay --ledger --reach-trace`
for parent-specific support and exact sequential site masks, without altering
the world, model or RNG. It can accompany the first-day recruitment trace.
The [adult resource investigation](../benchmarks/garden-seasons/landing-adult-resources-protocol.md)
adds `--adult-trace NEW.jsonl --adult-start TICK --adult-stop TICK` to ordinary,
water-reserve and arbitration replays. It requires `--ledger` and positive,
15-tick-aligned inclusive bounds within the run horizon. It records all living
plants and same-step deaths in that window, including founders and older
descendants; the original first-day trace format stays unchanged.

`make host-trace-landing-adults` replays the fixed diagnostic pair, verifies
historical results and trace-on/off pixels, and captures its prescribed timeline.
Use `GARDEN_LANDING_ADULT_OUT=artifacts/fresh-name` for a new output directory.
No ecology, model weights or scoring rules are changed by these observers.

The [maintenance-aware construction experiment](../benchmarks/garden-seasons/landing-growth-protocol.md)
adds the separate host-only `growth-replay` command. It requires an explicit
`--node-limit off|32`, always uses the experimental water-eligible arbitration,
and records a distinct `GLC1` identity including the cap. At 32 nodes it projects
allocating EXTEND bids to WAIT before water eligibility and ranking; priority
and recurrent memory are preserved. It does not force flowering or remove
tissue. Ordinary commands, model files and device behavior are unchanged.
It accepts `--ledger`, `--framebuffer`, `--recruitment-trace` and the adult trace
window, but not water/reach/decision trace flags. Unsupported caps fail.

`make host-screen-landing-growth` runs the fixed twelve-pair comparison, repeats,
budget checks and prescribed screenshots. Set
`GARDEN_LANDING_GROWTH_OUT=artifacts/fresh-name` for a new collection. This is an
experimental policy comparison, not a training target or promoted device mode.

`make host-audit-landing-species` analyzes those saved results without native
execution. The [species diagnosis](../benchmarks/garden-seasons/landing-species.md)
keeps matched founder lifetimes, species-resolved seed/offspring funnels,
fixed-age survival with follow-up denominators, and living-only seedling
allocation separate from the focused adult receipts. Use
`GARDEN_LANDING_SPECIES_OUT=artifacts/fresh-species.json.gz` for a fresh output.

The [founder investigation](../benchmarks/garden-seasons/landing-founders.md)
adds `--founder-trace NEW.jsonl --founder-start TICK --founder-stop TICK` to
`growth-replay`. It requires `--ledger` and positive, inclusive 15-tick-aligned
bounds within the run horizon. It records raw/projected tip proposals, exact
sequential reproduction gates and living post-step bodies. Proposals are not
necessarily selected or executed. Other replay commands reject these flags.

`make host-trace-landing-founders` collects the same twelve pairs with founder
traces through day 64 and adult resource accounts through day two, repeating
every arm and checking untraced/historical state and pixels. Use
`GARDEN_LANDING_FOUNDERS_OUT=artifacts/fresh-founders` for a new collection.
The saved bundle also supports offline verification without native execution.

The [reserved shoot comparison](../benchmarks/garden-seasons/landing-budget.md)
adds `budget-replay --shoot-reserve off|on`. Both modes retain a 32-node cap
and water eligibility, but reject over-budget bids before priority ranking.
The `on` mode reserves the deepest active shoot's remaining path to its actual
maximum depth until a flower forms. It does not force finishing or change the
neural proposals. `GLB1` identities distinguish these modes from each other
and the legacy `GLC1` projection; ordinary commands and model files are unchanged.

Budget replay accepts the same ledger, image, recruitment, adult and founder
trace options as growth replay, but rejects `--node-limit`. Its founder trace
has a distinct schema and adds per-bid budget receipts. Those receipts report
eligibility, not the selected action. `make host-screen-landing-budget` runs
the fixed four-arm comparison; choose a fresh output with
`GARDEN_LANDING_BUDGET_OUT=artifacts/new-budget-screen`.

The [offline germination audit](../benchmarks/garden-seasons/landing-budget-germination.md)
uses the frozen results and checksummed seed-window excerpts from that screen.
`make host-audit-landing-germination` needs no native build or local simulation
bundle. Set `GARDEN_LANDING_GERMINATION_OUT=artifacts/new-germination.json.gz`
for a fresh, no-clobber output. It retains both reserved and eligibility-only
arms in all six seasonal worlds and leaves every renewal score unchanged.

Budget replay also accepts the read-only `--reach-trace NEW.jsonl` with
`--ledger`, using the same parent-purchase and exact sequential site receipts
as ordinary replay. It does not enable reach tracing for growth/water/probe
modes. `make host-trace-landing-budget-reach` runs the fixed seasonal follow-up;
choose a fresh `GARDEN_LANDING_BUDGET_REACH_OUT=artifacts/new-budget-reach`.
The [parent-reach report](../benchmarks/garden-seasons/landing-budget-reach.md)
separates purchase-time and later opportunities, with carry-in support and
day190-censored outcomes. Its portable result can be verified without replay.

The [spacing-aware comparison](../benchmarks/garden-seasons/landing-placement.md)
adds explicit `placement-replay --shoot-reserve off|on --seed-placement off|spacing`.
It keeps an unblocked ordinary landing, otherwise selects among spacing-clear
choices inside the same parent range, with the original purchase/landing as
the all-blocked fallback. It adds no RNG draw and does not consult weather or
resource gates. This is a host-only experiment, not a trained placement action.
`GLP1` wraps the underlying budget identity; existing replay identities remain
unchanged.

Optional `--placement-trace NEW.jsonl` requires `--ledger` and records the
original RNG, parent support, spacing mask and selected choice at every paid
purchase. Recruitment, reach, adult and framebuffer options remain available;
founder-trace options are rejected. `make host-screen-landing-placement` runs
the fixed three-arm, twelve-world screen with repeat/control checks. Use a fresh
`GARDEN_LANDING_PLACEMENT_OUT=artifacts/new-placement-screen`. The portable
result supports offline verification; the local bundle also verifies full
receipts and every artifact hash. The candidate fails seasonal retention and
is not enabled in ordinary host runs or firmware.

`make host-audit-placement-turnover` diagnoses those saved seasonal pairs with
no native build or simulation. Choose a fresh
`GARDEN_LANDING_PLACEMENT_TURNOVER_OUT=artifacts/new-placement-turnover.json.gz`.
The [turnover report](../benchmarks/garden-seasons/landing-placement-turnover.md)
separates credit expiry from death, checks exact final-period germination/reach
receipts and follows within-run redirection ancestry. The two /33 gains are
older credit, not fresh renewal. The portable inputs suffice for reproduction;
optional `--extract-from` checks the excerpts against the frozen local raw bundle.

`make host-screen-landing-vacancy` follows the
[fixed vacancy protocol](../benchmarks/garden-seasons/landing-vacancy-protocol.md):
six seasonal worlds, unchanged controls, one named adult export on day 158,
and follow-up through day 256. Use a fresh
`GARDEN_LANDING_VACANCY_OUT=artifacts/new-vacancy-screen`. This is host-only
diagnostic intervention, not natural mortality, training or a firmware change.

The underlying `vacancy-replay` takes placement replay's explicit options plus
required `--ledger --vacancy-at TICK --vacancy-lineage ID`. Export occurs after
that ordinary ecology step. Missing/dead targets or age at most one day fail;
there is no replacement target. Body/stores are exported without a refund,
survivor memory and banked seeds remain, and the ledger uses `removal_tick`
separately from `death_tick`. `GLV1` identities include the scheduled event even
in pre-event checkpoints; `placement_run_hash` exposes the underlying identity.
`python3 sim/garden_landing_vacancy.py --verify BUNDLE_OR_RESULTS` checks the
saved evidence without rerunning worlds. A complete local bundle additionally
revalidates raw resource/reach traces, prefix equivalence and repeated pixels.
The [completed result and galleries](../benchmarks/garden-seasons/landing-vacancy.md)
separate early refills from the later natural turnover in unchanged controls.

`make host-trace-landing-recovery` follows the fixed
[recovery-gate protocol](../benchmarks/garden-seasons/landing-recovery-gates-protocol.md).
It replays those twelve historical arms unchanged, observing all plants'
construction, ordered reproduction gates and resource budgets over days
158–218. Select a fresh `GARDEN_LANDING_RECOVERY_OUT=artifacts/new-recovery-trace`.
The native `placement-replay` and `vacancy-replay` commands accept
`--stand-trace NEW.jsonl --stand-start TICK --stand-stop TICK`: inclusive,
positive ecology-aligned bounds within the replay horizon, requiring `--ledger`.
Combine with `--adult-trace` and the same bounds for resource reconciliation,
but not with `--placement-trace`. Existing founder-only commands/formats remain
unchanged; both scopes share one bounded native collector.

`python3 sim/garden_landing_recovery.py --verify BUNDLE_OR_RESULTS` checks
portable historical/cohort/accounting consistency. A full local bundle also
reanalyses every raw stand/resource receipt, verifies ordered purchases and
compares repeated trace and framebuffer bytes, without running simulations.
These are host diagnostics, not controller observations or firmware changes.

`make host-audit-landing-bank-access` then audits the saved ordered visits and
seed ledgers, without a native build or simulation. It separates full-at-entry
blocks from earlier buyers taking available slots, accounts for clipped seed
residence and follows posthumous versus post-export offspring. Select a fresh
`GARDEN_LANDING_BANK_ACCESS_OUT=artifacts/new-bank-access.json.gz`.
See the [protocol and findings](../benchmarks/garden-seasons/landing-bank-access.md).
`python3 sim/garden_landing_bank_access.py --verify RESULTS` recomputes the
portable audit; adding `--extract-from artifacts/garden-landing-recovery-gates-v1`
instead compares the visit excerpt supplied to `--verify` with the original
hash-pinned local traces. Both paths are read-only with respect to the inputs.

`make host-screen-landing-order` follows the frozen
[rotation protocol](../benchmarks/garden-seasons/landing-order-protocol.md).
The [completed comparison](../benchmarks/garden-seasons/landing-order.md) retains
all twelve galleries, positive offspring outcomes and regressed worlds.
Select a fresh `GARDEN_LANDING_ORDER_OUT=artifacts/new-order-screen`. It compares
fixed/rotating reproduction after day 158 in both existing control/vacancy
contexts, keeping model bytes, capacity, fees and seed viability fixed. Run
`python3 sim/garden_landing_order.py --verify BUNDLE_OR_RESULTS` for offline
verification; a full bundle additionally reanalyses raw visits and budgets.

Native `placement-replay` and `vacancy-replay` accept paired optional flags
`--seed-order rotating --seed-order-after TICK`, requiring `--ledger` and a
positive multiple of 60 within the CLI horizon. Omitting both preserves legacy
behavior and identities. Rotation visits the unchanged array from
`((tick - after) / 60) % plant_count` on maintenance ticks strictly after the
boundary. Empty arrays and off-cadence ticks start at zero. No new random draw,
cooldown update, resource exemption or preferred lineage is introduced.

Add `--stand-order` alongside the usual stand trace/bounds to select the
`landing-ordered-stand-trace-v1` schema. It adds `plant_order`, the unrotated
array of lineage IDs, while `reproduction` retains actual visit order. This
allows independent rank checks even after germination, death and compaction.
The original stand/founder formats remain unchanged without this flag.
The host run hash includes the nonzero rotation boundary via a separate GLR1
identity; the physical world hash does not identify this future configuration.

`make host-audit-landing-order-regressions` diagnoses the saved comparison
without a native build or replay. It retains every world in its summary and
audits exact event receipts for S34 vacancy, S35 control and M33 control.
Use a fresh `GARDEN_LANDING_ORDER_REGRESSIONS_OUT=artifacts/new-order-audit.json.gz`.
`python3 sim/garden_landing_order_regressions.py --verify RESULTS` recomputes
the audit from pinned portable inputs. Add
`--extract-from artifacts/garden-landing-order-v1 --verify EVENTS` to compare
the portable event file with an exact re-extraction of the original raw traces.
See the [findings and evidence limits](../benchmarks/garden-seasons/landing-order-regressions.md).

`make host-trace-landing-late` extends detailed observation of the unchanged
S35 control pair to [218,256], with exactly four full calls (fixed/rotating,
each repeated). Use a fresh `GARDEN_LANDING_LATE_OUT=artifacts/new-late-trace`.
The original `artifacts/garden-landing-order-v1` bundle is required for its
day-218 overlap check; the script accepts `--reference PATH` to relocate it.
`python3 sim/garden_landing_late.py --verify BUNDLE_OR_RESULTS` checks saved
evidence offline. Full bundles additionally reanalyse the complete raw traces;
portable results retain all eleven late births and their exact first-day
receipts. See the [water-shortage findings](../benchmarks/garden-seasons/landing-late-resources.md).

`make host-probe-landing-root-choice` tests one early root allocation in three
failed and two successful seedlings, each as an independent control/candidate
pair. Exactly 40 calls cover prefixes, first-day images and repeated day-256
traces. Use a fresh `GARDEN_LANDING_ROOT_CHOICE_OUT=artifacts/new-root-choice`.
The pinned late-resource bundle is required for historical overlap checks;
the script accepts `--reference PATH`. Offline verification uses
`python3 sim/garden_landing_root_choice.py --verify BUNDLE_OR_RESULTS`.
See the [energy/water tradeoff](../benchmarks/garden-seasons/landing-root-choice.md)
and its prospective protocol; this is not a default population policy.

The native `placement-replay` diagnostic accepts paired
`--root-choice-at TICK --root-choice-lineage ID` options, only with `--ledger`
and `--shoot-reserve on`. The tick must be positive and ecology-aligned; it
may lie after a checkpoint's horizon. Detailed observations require
`--stand-choice` instead of `--stand-order`, with the existing stand window
options. Controls can also request this trace format. It records original
and applied priorities and the ordinary water eligibility calculation.
The configuration participates in a distinct `GLQ1` run identity. Neither
omitting the options nor requesting an observational trace changes defaults.

`make host-probe-landing-root-energy` adds the bounded first-day energy comparison
on top of those same root purchases: five independent pairs, exactly 40 calls,
and no training. Use a fresh `GARDEN_LANDING_ROOT_ENERGY_OUT=artifacts/new-root-energy`.
The pinned root-choice bundle supplies historical controls (`--reference PATH`
can relocate it). See the [partial rescue and forecast error](../benchmarks/garden-seasons/landing-root-energy.md).

`--root-energy-reserve` requires the paired root-choice options, ledger and shoot
reservation. It applies only after that root tick to the named living offspring
born at that tick, through ecology age 256. It is additional eligibility before
priority arbitration, not a WAIT rewrite; prices and proposed memory are unchanged.
The candidate adds a `GLE1` fingerprint. Detailed observation requires
`--stand-energy`, which includes local energy-forecast inputs and receipts;
controls can request the same schema without enabling the guard. The older
trace schemas and unconfigured fingerprints are unchanged.

`python3 sim/garden_landing_root_energy.py --verify BUNDLE_OR_RESULTS` checks the
saved comparison offline. If all 40 native captures exist but offline validation
failed, `--reanalyse FAILED_CAPTURE --out FRESH_PATH` can rebuild the report without
executing a simulator. It refuses missing/extra calls, preserves the failed
directory and records separate captured-source and repaired-validator provenance.

`make host-audit-landing-energy` audits those saved first-day forecasts and
maintenance increases, including successful growth and otherwise eligible
opportunities rejected by energy. It invokes no simulator and accepts a fresh
`GARDEN_LANDING_ENERGY_AUDIT_OUT=artifacts/new-energy-audit`. Every paid decision
gets an observed sunset budget with later growth, upkeep, overflow and forecast
cap separated; deaths and missing follow-up are not extrapolated. Both raw and
deduplicated counts remain available. See the
[findings and next proposed comparison](../benchmarks/garden-seasons/landing-energy-audit.md).

`python3 sim/garden_landing_energy_audit.py --verify BUNDLE_OR_RESULTS` recomputes
the audit from its pinned portable input. Bundle verification additionally checks
artifact hashes and the source archive. This audit does not install a new reserve
rule or change default/device behavior.

`make host-probe-landing-afternoon` runs the next five-case, forty-call comparison
against those energy-guarded controls. Use a fresh
`GARDEN_LANDING_AFTERNOON_OUT=artifacts/new-afternoon` and the pinned verified
root-energy bundle (`--reference PATH` can relocate it). The
[prospective protocol](../benchmarks/garden-seasons/landing-afternoon-protocol.md)
fixes the rule, panel and replay budget before collection. The
[completed comparison](../benchmarks/garden-seasons/landing-afternoon.md) records
one additional long-lived survivor and one second-night failure at the age cutoff.

`--root-afternoon-reserve` requires `--root-energy-reserve` and its existing
root-choice/ledger/shoot-reservation options. It adds stored-energy eligibility
only to daylight maintenance increases at/after noon, in the same first-day
scope. `--stand-afternoon` records both the unchanged base energy forecast and
the additional condition; this observational schema can also be used for the
control. The other stand formats are mutually exclusive. Existing formats and
unconfigured identities remain unchanged; the candidate adds a `GLN1` run hash.
`python3 sim/garden_landing_afternoon.py --verify BUNDLE_OR_RESULTS` checks the
comparison offline, including full trace reanalysis for a raw bundle.

`make host-probe-landing-continuous-energy` compares that afternoon candidate
with the same two energy checks kept active beyond the first day. It uses the
same five cases and forty calls, with a fresh
`GARDEN_LANDING_CONTINUOUS_ENERGY_OUT=artifacts/new-continuous-energy` and the
pinned afternoon raw bundle (`--reference PATH` can relocate it). The
[protocol](../benchmarks/garden-seasons/landing-continuous-energy-protocol.md)
fixes scope and evidence requirements before collection.
The [completed comparison](../benchmarks/garden-seasons/landing-continuous-energy.md)
records a delayed third-night failure and four unchanged surviving checks.

`--root-continuous-energy` requires both `--root-energy-reserve` and
`--root-afternoon-reserve`, including their existing requirements. Only the
named living offspring receives continued protection; descendants do not inherit
it. Water protection and the birth-time root purchase remain unchanged. Use the
existing `--stand-afternoon` receipts; the new configuration adds a `GLU1` run
identity, without changing unconfigured formats or behavior. Portable evidence
retains the focal plant's complete history through death or day 256.
`python3 sim/garden_landing_continuous_energy.py --verify BUNDLE_OR_RESULTS`
rechecks the evidence offline. This option remains host-only, never a default.

`make host-audit-landing-light` audits those complete saved focal lifetimes with
no native calls, training or screenshots. Use
`GARDEN_LANDING_LIGHT_AUDIT_OUT=artifacts/new-light-audit` for a fresh directory.
The [protocol](../benchmarks/garden-seasons/landing-light-audit-protocol.md) pins
captured lighting/uptake sources and one current-observation-only diagnostic.
The [completed audit](../benchmarks/garden-seasons/landing-light-audit.md) keeps
all purchases, dawn receipts, successful-growth risks, error distributions and
exact physical-history deduplication. Its same-state alternative does not change
the simulator or demonstrate survival. No original trace bundle or native build
is required. Verify either the raw audit bundle or portable result with
`python3 sim/garden_landing_light_audit.py --verify BUNDLE_OR_RESULTS`.

`make host-probe-landing-daylight` tests that diagnostic as one additional
afternoon spending guard: the same five pairs, forty calls and no training.
Choose a fresh `GARDEN_LANDING_DAYLIGHT_OUT=artifacts/new-daylight` and retain the
pinned continuous-energy raw bundle (`--reference PATH` can relocate it).
The [protocol](../benchmarks/garden-seasons/landing-daylight-protocol.md) freezes
the rule, including the successful-growth risk check. The
[results](../benchmarks/garden-seasons/landing-daylight.md) retain all five
survivors, zero focal seed production, remaining dawn shortages and population
tradeoffs rather than treating survival as renewal.

`--root-daylight-energy` requires `--root-continuous-energy` and all its existing
dependencies. Only the named living offspring is protected, without inheritance
or changes to its birth-time root purchase. The condition applies to paid actions
at phases 64–127 and uses current global strength and income, never future
weather or realized income. The original forecast remains unchanged. The
`GLD1` run identity marks the new condition; unconfigured runs keep old identities.
`--stand-daylight` selects `landing-daylight-stand-trace-v1`, with the existing
receipts plus independent daylight applicability, scope, strength, useful steps,
credit and projected sunset. It works for controls too, is mutually exclusive
with other stand schemas, and is required when tracing the daylight treatment.
Invalid or duplicate flags are rejected before outputs. Boolean-option order
is covered explicitly, including the continuous-energy flag before other options.
`python3 sim/garden_landing_daylight.py --verify BUNDLE_OR_RESULTS` rechecks
portable evidence or complete raw traces offline. No firmware/default change.

`make host-audit-landing-dawn` analyzes saved sunset-to-noon and dawn-to-noon
funding, with no native execution, training or screenshots. Use a fresh
`GARDEN_LANDING_DAWN_AUDIT_OUT=artifacts/new-dawn-audit`. The
[protocol](../benchmarks/garden-seasons/landing-dawn-audit-protocol.md) fixes the
accounting and one current-light diagnostic; the
[results](../benchmarks/garden-seasons/landing-dawn-audit.md) separate first
global light, first income, unpaid maintenance and exact capped funding needs.
Both raw and portable inputs verify with
`python3 sim/garden_landing_dawn_audit.py --verify BUNDLE_OR_RESULTS`.
The minimum reserve assumes the recorded income/body/spending schedule; it is
not a simulated change in plant resources. Diagnostic purchase rejections are
not demonstrated rescues or regressions. That audit adds no policy option.

`make host-probe-landing-dawn` tests the audit's reserve in a fixed forty-call
paired replay; use `GARDEN_LANDING_DAWN_OUT=artifacts/new-dawn-test` for fresh,
no-clobber output. The [protocol](../benchmarks/garden-seasons/landing-dawn-protocol.md)
keeps the daylight candidate as control; the
[results](../benchmarks/garden-seasons/landing-dawn.md) retain resource and morphology
tradeoffs rather than claiming population renewal. Explicit `--root-dawn-reserve` requires
`--root-daylight-energy` and its prerequisites. Only paid afternoon actions gain
an extra condition: fund nominal night plus upkeep through the first estimated
productive morning, rounded up to a maintenance payment. Maintenance increases
must also fund that reserve from the existing stores-only margin. An unavailable
productive-morning estimate rejects the paid bid. No future world data is read.

The `GLM1` identity marks this condition. `--stand-dawn` selects
`landing-dawn-stand-trace-v1`, preserving previous receipts and adding a
`dawn_gate` with applicability, activity, independent permission, availability,
first light/payment phases, reserve, projected margin and optional stores margin.
Zero numeric fields with an unavailable estimate are not a zero-cost allowance.
This schema works for controls and is required when tracing the new treatment;
stand schema flags are mutually exclusive. Invalid/duplicate flags fail before
outputs. `python3 sim/garden_landing_dawn.py --verify BUNDLE_OR_RESULTS` verifies
raw or portable evidence offline. Full focal histories retain actual energy and
water shortage payments, not duplicate samples of stale flags. Old formats and
unconfigured identities, models, ordinary host and device behavior are unchanged.

`make host-probe-landing-population` runs the fixed eight-pair, 32-call
[population screen](../benchmarks/garden-seasons/landing-population-protocol.md).
Its [completed results](../benchmarks/garden-seasons/landing-population.md) fail
qualification; this is experimental tooling, not a recommended default policy.
Use `GARDEN_LANDING_POPULATION_OUT=artifacts/new-population-test` for fresh output.
`placement-replay --root-all-offspring` requires all four existing flags:
`--root-energy-reserve --root-afternoon-reserve --root-continuous-energy
--root-daylight-energy`. It rejects focal tick/lineage settings. Both arms use
the same paid birth-root preference at age one, and the spending checks apply
from age two to every living non-founder, including future descendants.
Add `--root-dawn-reserve` only for the candidate. The GLF1 scope identity precedes
the unchanged condition identities; ordinary replays and firmware stay unchanged.

`python3 sim/garden_landing_population.py --verify BUNDLE_OR_RESULTS` checks
saved evidence without simulation. Raw verification replays the streaming
accounting/choice analysis of every trace; portable verification reconciles
summaries, ledgers, first-effect witnesses and predefined harm checks. Portable
summaries do not contain every bid: retain the raw bundle for complete reanalysis.

`make host-audit-landing-population` reads that bundle without compiling or
running the simulator. Its [offline audit](../benchmarks/garden-seasons/landing-population-audit.md)
separates matched offspring from later cohorts and retains all shortage windows
for `f7ee4528`, both orders/arms. Set `GARDEN_LANDING_POPULATION_AUDIT_OUT` to a
fresh directory. `python3 sim/garden_landing_population_audit.py --verify
BUNDLE_OR_RESULTS` recomputes portable coverage and accounting; add `--verify-raw`
to re-extract from the pinned raw population traces (`--bundle PATH` overrides
their location). Frozen-income funding diagnostics are not alternate worlds.

`make host-probe-landing-uptake` performs the eight-call
[passive uptake comparison](../benchmarks/garden-seasons/landing-uptake.md), using
those same four worlds and all selected failure windows. Set
`GARDEN_LANDING_UPTAKE_OUT` to a fresh directory. It requires exact observer-on/off
and historical result/trace/pixel equality. `python3 sim/garden_landing_uptake.py
--verify BUNDLE_OR_RESULTS` checks saved evidence without simulation; a raw bundle
also reconstructs every observed light field and ordered root transfer.

For an individual placement/vacancy replay, `--uptake-trace NEW.jsonl` requires
one or more `--uptake-window START:STOP` options within `--stand-trace` bounds.
The maximum is 64 ordered, disjoint, inclusive ranges, aligned to 15-tick
ecology steps. The trace records pre-maintenance sun, leaf shade sources,
per-leaf light/income, ordered roots with soil/storage transfers and full
before/after soil and light grids. Lineage IDs survive slot reuse; node indices
are step-local. Files use no-clobber creation and an explicit completion footer.
Unsupported experimental light/uptake modes are rejected. Removal effects on
frozen geometry overlap and must not be added as independent resource shares.

`make host-probe-landing-directions` performs the eight-call
[construction direction audit](../benchmarks/garden-seasons/landing-directions.md)
on those same four historical worlds. Set `GARDEN_LANDING_DIRECTIONS_OUT` to a
fresh directory. All old result/trace/pixel hashes must remain identical with
the observer on and off. `python3 sim/garden_landing_directions.py --verify
BUNDLE_OR_RESULTS` checks saved evidence without simulation; a raw bundle also
rechecks every bid and endpoint, not only the portable paid-event receipts.

The individual CLI option `--direction-trace NEW.jsonl` requires `--stand-dawn`
and a stand trace, and uses its inclusive bounds. It records canonical
endpoints, applied ranking, light/moisture, clearance/collision flags and
pre-execution own-root soil-cell coverage for every bid. The separate stream
does not change the old stand trace. No-clobber creation and explicit completion
framing apply. Alternative assessments preserve the first-day water guard;
brighter/wetter/new-cell opportunities are not simulated rescues or future
income, and no direction policy changes as part of this capture.

`make host-probe-landing-root-direction` runs the separate sixteen-call
[wetter-root comparison](../benchmarks/garden-seasons/landing-root-direction.md).
Set `GARDEN_LANDING_ROOT_DIRECTION_OUT` to a fresh directory. Four historical
worlds each get the preference off/on and an exact repeat, with final paired
screenshots. `python3 sim/garden_landing_root_direction.py --verify
BUNDLE_OR_RESULTS` checks saved evidence without simulation; raw verification
recomputes full population/direction receipts and matching first-effect prefixes.

`make host-audit-landing-root-direction` explains its saved first-day resource
flows and seed timing without a native build or simulation. It reads
`GARDEN_LANDING_ROOT_DIRECTION_OUT` and writes a fresh file selected by
`GARDEN_LANDING_ROOT_DIRECTION_AUDIT_OUT`. All sixteen source prefixes match
within their direction arm; the audit keeps two distinct complete histories,
not four independent early trials. See the [findings and verification commands](
../benchmarks/garden-seasons/landing-root-direction-audit.md).
`python3 sim/garden_landing_root_direction_audit.py --verify RESULTS.json.gz`
recomputes portable accounting; add `--bundle ORIGINAL_RAW_BUNDLE` to verify
source trace hashes and re-extract the prefixes as well.

The opt-in CLI flag `--root-wet-direction` requires `--root-all-offspring` and
its existing daylight guard chain. Dawn protection remains optional. It changes
only already-eligible root EXTEND rankings, including founders; no rejected
bid is made eligible. Ties preserve model order. A stand trace must use
`--stand-dawn`; a direction trace uses `landing-root-directions-v1` and adds
`raw_order` beside the applied `order`. The run fingerprint adds `GLW1` and
`root_wet_direction_probe`. With the flag absent, identities and trace formats
are unchanged. This candidate failed its population comparison and is not a
normal host or device policy.

`make host-probe-landing-root-allocation` runs the separate [focal allocation
protocol](../benchmarks/garden-seasons/landing-root-allocation-protocol.md).
Set `GARDEN_LANDING_ROOT_ALLOCATION_OUT` to a fresh directory. It makes sixteen
full-horizon calls, retaining exact repeats, historical controls, complete
resource and direction receipts, the focal plant's full history and all paired
final frames. `python3 sim/garden_landing_root_allocation.py --verify
BUNDLE_OR_RESULTS` verifies saved evidence without simulator execution.

The opt-in `--root-allocation-focal` flag fixes lineage 9, birth tick 403365,
parent 4, generation 1, column 24 and shrub species. From age two onward it
raises an affordable root bid to at least 32765 only when current water income
has no maintenance surplus, energy income covers post-root upkeep and the
unchanged chosen endpoint is moist. Existing guards still apply; mandatory tip
closures keep their higher priority. No direction, action, memory proposal or
random draw is rewritten. It requires all-offspring daylight guards and rejects
`--root-wet-direction`; any stand trace must use `--stand-dawn`. The distinct
`GLA1` identity includes the full selector. Only enabled traces add `allocation`
receipts. This is a host-only diagnostic, not a firmware/default policy.

`make host-audit-landing-root-allocation` performs the [offline population
decomposition](../benchmarks/garden-seasons/landing-root-allocation-audit.md).
It uses `GARDEN_LANDING_ROOT_ALLOCATION_OUT` as its existing raw bundle and
requires a fresh `GARDEN_LANDING_ROOT_ALLOCATION_AUDIT_OUT` file. There is no
build dependency or simulator execution. It checks repeat hashes, separates
recursive birth matches from changed cohorts, compares equal-lifetime resource
receipts, and reconciles exact contributions to the population shortage rates.

`python3 sim/garden_landing_root_allocation_audit.py --verify RESULTS` checks
the portable audit against the pinned original allocation result. Adding
`--bundle RAW_BUNDLE` also reextracts all matched histories from the complete
hash-checked adult streams. Both modes are offline; neither changes policies
or reruns worlds. The artifact retains 47 deduplicated receipt sequences and
all four comparisons, including the failed population screens.

`make host-audit-landing-seed-spending` follows those two selected failures'
complete saved reproduction histories. It reads the same allocation bundle,
checks full stand-stream/repeat hashes and target resource receipts, then
reports seed gates, actual refills and budgets from the last shared full store.
Set `GARDEN_LANDING_SEED_SPENDING_AUDIT_OUT` to a fresh file. There is no build
dependency or simulator execution. The [results and limits](
../benchmarks/garden-seasons/landing-seed-spending-audit.md) distinguish a
replenished seed debit from later water-income loss.

`python3 sim/garden_landing_seed_spending_audit.py --verify RESULTS` recomputes
the portable summaries using the two pinned allocation result/audit files in
the repo. Add `--bundle RAW_BUNDLE` to reextract the selected reproduction
records. Neither mode runs a skip-seed counterfactual or changes defaults.

`make host-trace-landing-drydown` runs the [bounded passive capture](
../benchmarks/garden-seasons/landing-drydown.md): sixteen replays of the exact
archived allocation executable, with uptake observations only from 626520 to
629760. Ordinary results, complete traces and final pixels must remain identical
to the archived observer-off worlds. It keeps native-build provenance separate
from the current capture tools and validates every root/soil transfer.
There is no build dependency. Set `GARDEN_LANDING_DRYDOWN_OUT` to a fresh
directory and `GARDEN_LANDING_ROOT_ALLOCATION_OUT` to the original raw bundle.

`python3 sim/garden_landing_drydown.py --verify RESULTS_OR_BUNDLE` stays offline.
Portable verification needs the three pinned allocation/common-window/seed
spending files in the repo; raw verification also rehashes the full capture and
reextracts its observations. It never executes the archived binary. The soil
account labels net between-step changes explicitly, not as isolated rainfall
or diffusion measurements.

`make host-audit-landing-soil` performs the [offline soil reconstruction](
../benchmarks/garden-seasons/landing-soil-audit.md). It reads the drying capture
and its archived implementation, then reconstructs rainfall, downward flow,
alternating lateral pairs and surface evaporation between saved grids. Every
cell must match before stage/edge attribution is accepted. No simulator runs
and no build is required. Set `GARDEN_LANDING_SOIL_AUDIT_OUT` to a fresh file;
`GARDEN_LANDING_DRYDOWN_OUT` selects the existing raw capture.

`python3 sim/garden_landing_soil_audit.py --verify RESULTS` checks the portable
account and embedded historical source receipts using the pinned repository
input chain. Add `--bundle RAW_DRYDOWN_BUNDLE` to revalidate the original raw
observations and source archive. Both modes remain offline. Fixed neighborhood
and depth accounts expose local supply constraints; they are not neighbor-removal
or altered-soil-physics counterfactuals.

`make host-audit-landing-root-reachability` performs the [saved root construction
audit](../benchmarks/garden-seasons/landing-root-reachability.md). It reconstructs
the selected roots from birth, reconciles purchases with resource receipts and
later uptake footprints, and computes optimistic endpoint reach under existing
segment limits. There is no build dependency or simulator call.
`GARDEN_LANDING_ROOT_ALLOCATION_OUT` selects the original trace bundle,
`GARDEN_LANDING_DRYDOWN_OUT/native` supplies the archived implementation, and
`GARDEN_LANDING_ROOT_REACHABILITY_OUT` must be a fresh output file.

`python3 sim/garden_landing_root_reachability.py --verify RESULTS` rechecks the
portable evidence and pinned repository inputs without starting a process.
Add `--bundle RAW_ALLOCATION_BUNDLE` to rehash the primary/repeat traces and
reextract the selected histories. The geometric envelopes ignore future
collisions and spending; they prove exclusion, not affordable survival paths.

`make host-probe-landing-wicking` captures the [frozen late upward-transfer
comparison](../benchmarks/garden-seasons/landing-wicking-protocol.md). It builds
ordinary `build-host` and isolated `build-host-wicking` executables, then runs
eight ordinary controls and eight wicking cases with exact wicking repeats
(24 full trials). Set `GARDEN_LANDING_WICKING_OUT` to a fresh capture directory.
The environment changes only after tick 626580: one upward unit per eligible
edge every 60 logic ticks, after lateral flow and before evaporation. There is
no runtime switch. The separate host build has a `WIC1` world-hash tag and
`soil_wicking_probe` JSON metadata, including before the intervention begins;
shared prefixes are compared using physical observations, not tagged hashes.
Normal build scripts explicitly turn this experiment off, and firmware rejects
its header. Do not use the experimental binary as an ordinary training build.

`make host-audit-landing-wicking` reads that capture without running native code
and writes a fresh `GARDEN_LANDING_WICKING_RESULTS` file. It reconstructs each
observed soil transition, including germination withdrawals, and retains
selected-plant and whole-population accounts. Capture and analysis are separate
so an offline analysis can be repeated without adding trials.

```sh
python3 sim/garden_landing_wicking.py --verify RESULTS.json.gz
python3 sim/garden_landing_wicking.py --verify RESULTS.json.gz --bundle RAW_CAPTURE
```

Both verification modes stay offline. The second also rehashes the complete raw
bundle and reextracts its observations. This late intervention on one previously
examined weather seed is a diagnostic, not a from-start or fresh-seed qualification.

`make host-probe-landing-uptake-limit` captures the [frozen four-arm follow-up](
../benchmarks/garden-seasons/landing-uptake-limit-protocol.md): ordinary uptake,
wicking, storage-limited uptake, and both. It rebuilds the two controls and
requires their complete receipts/pixels to match the previous capture, then
runs every capped condition twice (48 full calls total). The cap is active only
after tick 626580 and adds a `ULT1` hash tag plus `uptake_limit_probe` metadata.
It is a separate option from the earlier from-start headroom test. Only the
wicking/cap combination is allowed; default scripts disable both.

`make host-audit-landing-uptake-limit` reconciles saved receipts with up to four
offline reader processes. Override `GARDEN_LANDING_UPTAKE_LIMIT_OUT` and
`GARDEN_LANDING_UPTAKE_LIMIT_RESULTS` for fresh captures/exports. The analysis
retains cell-level water budgets, matched adult windows, population harm checks
and living-body occupancy (a lower bound on pool use, excluding decomposing
bodies). Controls reuse pinned analysis only after exact raw receipt equality.

```sh
python3 sim/garden_landing_uptake_limit.py --verify RESULTS.json.gz
python3 sim/garden_landing_uptake_limit.py --verify RESULTS.json.gz --bundle RAW_CAPTURE
```

Both verification modes are offline; the second also rehashes the complete
bundle and independently reextracts candidate observations. Capture and analysis
are separate so a failed audit never requires extra simulation trials.
See the [completed comparison and screenshots](
../benchmarks/garden-seasons/landing-uptake-limit.md): conserved water improves
individual survival, but the current capped populations do not sustain late renewal.

`make host-audit-landing-renewal-gates` reads the same saved bundle to explain
seed supply, germination sites, actual pool capacity and reproduction gates.
It runs no simulation or build. Override `GARDEN_LANDING_RENEWAL_GATES_OUT`
with a fresh directory; `GARDEN_LANDING_UPTAKE_LIMIT_OUT` selects the raw input.
The [frozen protocol](../benchmarks/garden-seasons/landing-renewal-gates-protocol.md)
covers all 32 primary worlds, excluding repeats, after tick 626580 and in the
final 32 days separately. The input panel is pinned to the previously verified
uptake-cap export. This audit rehashes the 64 consumed adult/stand traces, not
the unrelated artifacts from that experiment.

```sh
python3 sim/garden_landing_renewal_gates.py \
  --verify benchmarks/garden-seasons/landing-renewal-gates-results.json.gz \
  --windows benchmarks/garden-seasons/landing-renewal-gates-windows.jsonl.xz
# Add --bundle artifacts/garden-landing-uptake-limit-v1 to reextract raw observations too.
```

The XZ-compressed JSONL excerpt has a schema/provenance header and one record per
primary world in fixed panel order. Each record keeps its source trace hashes
and every post-intervention row. Header field lists describe the packed row,
visit and resource arrays; seed-attempt arrays retain the adult trace's exact
11-field layout. Resources contain living plants' before/after reproduction
energy and water, flower count and node count. Unrelated growth bids are omitted.
The output directory also retains each per-world excerpt. Verification is
offline and read-only; extraction refuses to overwrite an existing directory.

`make host-audit-landing-dispersal-timing` follows those saved windows to separate
sites blocked when a seed was purchased from sites crowded by later arrivals.
It reconstructs spacing from the actual stored slot census, including dead
occupants and earlier same-step germinations. It also bounds dispersal reach
without inventing the parent traits or random draws omitted from these traces.
Landing-only trait constraints and deductions using the spacing-aware placement
rule remain separate. A globally open site count does not identify its columns;
intersection bounds explicitly preserve that uncertainty.

This command runs no simulation or build and needs no raw bundle or device.
Override `GARDEN_LANDING_DISPERSAL_TIMING_OUT` for a fresh `.json.gz` output.
The [frozen protocol](../benchmarks/garden-seasons/landing-dispersal-timing-protocol.md)
pins the preceding portable results, windows and original lineage ledger.
The new export keeps compact purchase contexts, spacing-witness timelines and
mature-check histograms as well as the derived summaries.

```sh
python3 sim/garden_landing_dispersal_timing.py \
  --verify benchmarks/garden-seasons/landing-dispersal-timing-results.json.gz
# Also independently reread and compare the pinned window observations:
python3 sim/garden_landing_dispersal_timing.py \
  --verify benchmarks/garden-seasons/landing-dispersal-timing-results.json.gz --reextract
```

Both modes are offline. The second re-extracts the existing portable windows,
not the original 64 raw traces; those were checked by the renewal-gate audit.

## Broader late dispersal experiment

`make host-probe-landing-late-dispersal` builds four isolated host variants and
captures the [frozen 48-trial comparison](../benchmarks/garden-seasons/landing-late-dispersal-protocol.md).
It compares ordinary versus late `3..9 + trait` dispersal in the uptake-capped
worlds, with and without wicking. All eight settings remain. Both output paths
must be fresh; this is a bounded experiment, not the ordinary host player.

```sh
make host-probe-landing-late-dispersal
make host-audit-landing-late-dispersal

python3 sim/garden_landing_late_dispersal.py \
  --verify artifacts/garden-landing-late-dispersal-v1.json.gz

# Rehash the raw bundle and independently reextract its observations.
python3 sim/garden_landing_late_dispersal.py \
  --verify artifacts/garden-landing-late-dispersal-v1.json.gz \
  --bundle artifacts/garden-landing-late-dispersal-v1
```

Override `GARDEN_LANDING_LATE_DISPERSAL_OUT` for capture and
`GARDEN_LANDING_LATE_DISPERSAL_RESULTS` for portable analysis. Analysis and
verification never invoke native simulations. Full stand, adult, direction,
reach and bounded uptake traces remain in the local capture bundle; the portable
file includes population/resource accounts and compact purchase/site evidence.
Exact parent traits are observed here, unlike the preceding retrospective audit.

The `TOY_FACTORY_GARDEN_LATE_DISPERSAL` option requires late capped uptake,
allows the existing wicking option, rejects other compiled research rules and
is disabled by the ordinary build wrappers. Its host-only placement observation
has a 14-choice capacity and a 16-bit mask. Active support remains six choices
through onset; high mask bits outside the active support are rejected. The
separate `late_dispersal_probe` JSON marker and `LDS1` world-hash tag identify
the rule even before onset. Device defaults and the older from-start wide
dispersal option remain unchanged.

## Dispersal energy audit

`make host-audit-landing-dispersal-energy` decomposes the saved broader-dispersal
energy regression without running the simulator. It consumes the pinned portable
dispersal and uptake-cap results, not the large raw bundles. It validates all
sixteen original screens, reconstructs maintenance demand from body histories,
and separates prior occupants, later recruitment cohorts and matched exposure.

```sh
make host-audit-landing-dispersal-energy \
  GARDEN_LANDING_DISPERSAL_ENERGY_AUDIT_OUT=artifacts/new-energy-audit.json.gz

# The same offline command needs only the Python standard library:
python3 sim/garden_landing_dispersal_energy_audit.py \
  --out artifacts/another-energy-audit.json.gz

python3 sim/garden_landing_dispersal_energy_audit.py \
  --verify benchmarks/garden-seasons/landing-dispersal-energy-audit-results.json.gz
```

Output paths must be fresh. Verification recomputes the complete audit from its
pinned summaries, including every post-intervention energy event; it is not a
fresh raw-trace extraction. Both export and verification are tested with process
launching forbidden. The [report](../benchmarks/garden-seasons/landing-dispersal-energy-audit.md)
finds both changed cohorts and matched individual regressions. It proposes a
focused read of saved energy receipts before changing another ecology rule.

## Mature plant energy history

`make host-audit-landing-energy-history` reads two saved adult traces for the
selected mature plant from the cohort audit. It validates the full histories,
finds the last common full-energy checkpoint and reconciles income, overflow,
maintenance, growth and seed spending through the deficit and recovery.

```sh
make host-audit-landing-energy-history \
  GARDEN_LANDING_ENERGY_HISTORY_OUT=artifacts/new-energy-history.json.gz

# Portable verification needs the checked-in inputs, not the large raw bundle.
python3 sim/garden_landing_energy_history.py \
  --verify benchmarks/garden-seasons/landing-energy-history-results.json.gz

# Rehash and independently reextract the two original adult traces too.
python3 sim/garden_landing_energy_history.py \
  --verify benchmarks/garden-seasons/landing-energy-history-results.json.gz \
  --bundle artifacts/garden-landing-late-dispersal-v1
```

Override `GARDEN_LANDING_LATE_DISPERSAL_OUT` if the original bundle is elsewhere.
Export requires a fresh destination and may also be invoked directly with
`python3 sim/garden_landing_energy_history.py --bundle PATH --out NEW.json.gz`.
All modes are offline and need only the Python standard library. The
[report](../benchmarks/garden-seasons/landing-energy-history.md) identifies
lower winter income after equal full stores, with no intervening construction
or seed spending. The separate passive capture below identifies the missing
leaf illumination; this history command never launches one.

## Winter leaf light and shade

The [winter-light report](../benchmarks/garden-seasons/landing-winter-light.md)
traces the selected parent's income loss to a surviving offspring's shade.
Capture and analysis are separate commands. Capture reuses two archived binaries
and changes only observation windows; it never rebuilds. It checks exact
historical results, final pixels and all four ordinary traces before completing.
The frozen two-replay capture is already complete; do not run another capture
as part of routine offline review.

```sh
# Original capture command; refuses the existing destination.
make host-trace-landing-winter-light

# Reextract and analyze the selected saved bundle into a fresh file.
make host-audit-landing-winter-light \
  GARDEN_LANDING_WINTER_LIGHT_RESULTS=artifacts/new-winter-light.json.gz

# Portable verification needs checked-in inputs, not the 2.5 GiB raw bundle.
python3 sim/garden_landing_winter_light.py \
  --verify benchmarks/garden-seasons/landing-winter-light-results.json.gz

# Also rehash the complete capture and independently reextract its observations.
python3 sim/garden_landing_winter_light.py \
  --verify benchmarks/garden-seasons/landing-winter-light-results.json.gz \
  --bundle artifacts/garden-landing-winter-light-v1
```

`GARDEN_LANDING_WINTER_LIGHT_OUT` locates the capture bundle and
`GARDEN_LANDING_LATE_DISPERSAL_OUT` locates the original archived native inputs.
Analysis pins this capture's manifest; a different experiment needs a new
protocol rather than silently substituting another bundle. Analysis and
verification use only the Python standard library and cannot launch native
simulations. Standalone capture integrity checking is available through
`garden_landing_winter_light_capture.py --verify PATH`.

The portable result retains all shade sources, leaf records and light fields,
plus the population receipts needed to reconcile income. Raw soil/root records
remain in the capture but are outside this light audit. Node IDs are local to
each snapshot; paired geometry uses coordinate multisets. Shade omission is a
frozen-geometry diagnostic, not a simulated removal or a survival prediction.

## Seed placement information and family renewal

`make host-audit-landing-placement-information` audits the purchase that produced
the shading offspring above, using the original saved late-dispersal traces.
It reconstructs the callback's legal choices and spacing mask without inventing
its unrecorded random draw, then checks establishment and the family's subsequent
seed outcomes. The [report](../benchmarks/garden-seasons/landing-placement-information.md)
separates information available at purchase from post-step site diagnostics and
later canopy effects. Only one reachable choice was spacing-clear; the surviving
child made nine seeds, but none established before the horizon.

```sh
make host-audit-landing-placement-information \
  GARDEN_LANDING_PLACEMENT_INFORMATION_OUT=artifacts/new-placement-information.json.gz

# Portable verification needs checked-in inputs, not the original raw bundle.
python3 sim/garden_landing_placement_information.py \
  --verify benchmarks/garden-seasons/landing-placement-information-results.json.gz

# Also rehash the original sources and traces and independently reextract them.
python3 sim/garden_landing_placement_information.py \
  --verify benchmarks/garden-seasons/landing-placement-information-results.json.gz \
  --bundle artifacts/garden-landing-late-dispersal-v1
```

Override `GARDEN_LANDING_LATE_DISPERSAL_OUT` if the original bundle is elsewhere.
Export requires a fresh destination. All modes use only the Python standard
library, with no native simulation, capture or rebuild. Implementation hashes
pin the captured source archive; future runtime C edits do not invalidate the
historical audit. Analysis-source and input hashes remain checked.

The portable result retains bounded purchase context, full family summaries
and every check for the selected seed and its child's seeds. Raw verification
also reconciles the complete population's purchases/checks. Reflection aliases,
dead stored occupants and pending seeds remain explicit; no scalar fitness
score or isolated-child-removal effect is inferred from the paired histories.

## Vacancy and replacement sequences

`make host-audit-landing-vacancy-sequence` follows deaths, reclamation and
replacement across all 32 primary late-dispersal worlds. It reads saved
stand/reach traces, verifies the complete purchase/check inventory, and retains
compact post-onset observations with the exact sequential check order.

```sh
make host-audit-landing-vacancy-sequence \
  GARDEN_LANDING_VACANCY_SEQUENCE_OUT=artifacts/new-vacancy-sequence.json.gz

# Recompute every vacancy sequence from compact evidence offline.
python3 sim/garden_landing_vacancy_sequence.py \
  --verify benchmarks/garden-seasons/landing-vacancy-sequence-results.json.gz

# Also independently reextract all primary stand/reach traces.
python3 sim/garden_landing_vacancy_sequence.py \
  --verify benchmarks/garden-seasons/landing-vacancy-sequence-results.json.gz \
  --bundle artifacts/garden-landing-late-dispersal-v1
```

Override `GARDEN_LANDING_LATE_DISPERSAL_OUT` to locate the original bundle.
Export refuses existing destinations, including broken symlinks. All modes use
the Python standard library and never launch a simulator. Portable verification
needs the checked-in pinned results, not the large raw bundle. Source archive
hashes describe the captured runtime; analysis-source hashes remain checked.

The [report](../benchmarks/garden-seasons/landing-vacancy-sequence.md) separates
death from slot release, spacing from full pools, original dispersal support
from immovable seed landings, and direct germination from neighboring closure.
Partial refills and unobserved site conditions are not hidden. Compact open-column
bitsets do not retain separate light/moisture blockers for every alternative
column; those remain in the raw site maps.

## Follow late replacements to day 288

`make host-probe-landing-followup` runs the frozen 32-world follow-up, gated on
exact reconstruction of the old day-256 results, pixels and seed-check histories.
It builds the four isolated research variants in Docker and performs 68 native
calls: 32 baseline checks, 32 extensions and four repeats. It does not train,
change ecology, flash the device or extend the general training horizon.

```sh
make host-probe-landing-followup \
  GARDEN_LANDING_FOLLOWUP_OUT=artifacts/new-followup \
  GARDEN_LANDING_FOLLOWUP_RESULTS=artifacts/new-followup-results.json.gz

# Portable reanalysis without the original large raw bundle or any simulator.
python3 sim/garden_landing_followup.py \
  --verify benchmarks/garden-seasons/landing-followup-results.json.gz

# Also reextract all captured follow-up traces and check the frozen source archive.
python3 sim/garden_landing_followup.py \
  --verify benchmarks/garden-seasons/landing-followup-results.json.gz \
  --bundle artifacts/garden-landing-followup-v1

# Re-export an existing completed bundle offline to a fresh destination.
python3 sim/garden_landing_followup.py \
  --export artifacts/garden-landing-followup-v1 \
  --out artifacts/new-followup-export.json.gz
```

Collection needs the original late-dispersal bundle, at least 20 GiB free and
fresh output paths. Override `GARDEN_LANDING_LATE_DISPERSAL_OUT` to locate the
original bundle; the Python CLI accepts `--original` and `--jobs 1..4`. Failed
checks stop the panel without substituting worlds or silently resuming partial
outputs. Existing artifacts are preserved. Verification/export never launch
native simulations. The [report](../benchmarks/garden-seasons/landing-followup.md)
and fixed 32-world gallery distinguish establishment from reproduction.

## Audit late replacements' reproductive access

`make host-audit-landing-reproductive-access` reads the saved day-288 traces;
it does not build or launch a simulator. It separates flower/resource readiness,
ordered seed-bank access and the subsequent germination checks for the seven
previously censored survivors, with all 32 worlds retained as context.

```sh
# Offline extraction from the retained raw follow-up; output must be fresh.
make host-audit-landing-reproductive-access \
  GARDEN_LANDING_REPRODUCTIVE_ACCESS_OUT=artifacts/new-reproductive-access.json.gz

# Portable reanalysis, without the large raw traces or any simulator.
python3 sim/garden_landing_reproductive_access.py \
  --verify benchmarks/garden-seasons/landing-reproductive-access-results.json.gz

# Also re-extract the raw stand/adult/reach records and compare exact evidence.
python3 sim/garden_landing_reproductive_access.py \
  --verify benchmarks/garden-seasons/landing-reproductive-access-results.json.gz \
  --bundle artifacts/garden-landing-followup-v1
```

Override `GARDEN_LANDING_FOLLOWUP_OUT` to locate the pinned raw bundle. The
Python CLI accepts `--bundle PATH --out FRESH.json.gz` for export. Existing
files, directories and broken output symlinks are refused. All modes use only
the Python standard library. Portable verification retains the full production
clock, focal resource receipts and both focal seeds' histories; non-focal raw
site maps require the bundle for rechecking. The [report](
../benchmarks/garden-seasons/landing-reproductive-access.md) distinguishes
pending seeds from failed seeds and opportunity from demonstrated renewal.

## Test a single death with normal decomposition

The [frozen diagnostic](../benchmarks/garden-seasons/landing-disturbance-protocol.md)
uses all five worlds containing the seven late survivors. It kills one named
older non-focal plant just after the day-256 observation, retaining dead tissue
and seeds. This differs from the older immediate-export vacancy experiment.
The event is host-only; ordinary runs and device defaults do not change.

```sh
# Two isolated research builds; exactly 20 full replays, no training.
# Requires the retained original follow-up bundle and fresh output paths.
make host-probe-landing-disturbance \
  GARDEN_LANDING_DISTURBANCE_OUT=artifacts/new-disturbance \
  GARDEN_LANDING_DISTURBANCE_CAPTURE=artifacts/new-disturbance-capture.json.gz

# Verify the committed capture metadata, ledgers and repetition receipts.
python3 sim/garden_landing_disturbance.py \
  --verify benchmarks/garden-seasons/landing-disturbance-capture.json.gz

# Verify the original raw bundle too, without executing its archived binaries.
python3 sim/garden_landing_disturbance.py \
  --verify benchmarks/garden-seasons/landing-disturbance-capture.json.gz \
  --bundle artifacts/garden-landing-disturbance-v1

# Offline re-extraction from that pinned original bundle; no simulation/build.
make host-audit-landing-disturbance \
  GARDEN_LANDING_DISTURBANCE_AUDIT=artifacts/new-disturbance-audit.json.gz

# Portable reanalysis needs no large raw bundle, simulator or third-party Python.
python3 sim/garden_landing_disturbance_audit.py \
  --verify benchmarks/garden-seasons/landing-disturbance-results.json.gz
```

Capture takes `--jobs 1..4` (default 2), requires 10 GiB free, and refuses
existing files/directories and dangling output symlinks. It verifies all five
unchanged controls before starting treatments. A failure stops the batch;
failed artifacts remain, with no automatic resume or replacement world.
The offline audit pins the original capture and raw manifest; a later new
capture must be reviewed explicitly, not silently substituted into this report.

The low-level `placement-replay` options are paired
`--turnover-at TICK --turnover-lineage ID`, with `--ledger`. The tick must be an
ecology boundary within the requested run, and the named plant must be living
and older than one day. The event runs after that tick's observers. Its
`turnover_probe` records discarded stores, target, timing and before/after
hashes; its tagged run identity differs from ordinary placement. The lineage
export labels the imposed death `environmental_death: true`, not starvation or
immediate removal. Lifetime death totals still include it. See the
[paired report and gallery](../benchmarks/garden-seasons/landing-disturbance.md).

## Test a second opening through day 320

The [second-opening protocol](../benchmarks/garden-seasons/landing-second-opening-protocol.md)
retains the first day-256 death in all five worlds, then compares continuation
with another named death at day 288. It tracks all original focal plants and
first recruits through day 320. Old capture/audit implementations stay unchanged;
`garden_landing_window.py` provides explicitly bounded interval accounting for
this follow-up, reusing their horizon-independent validators.

```sh
# Requires the original single-death raw bundle. Choose fresh outputs.
# Builds both research variants, then runs exactly 25 native replays.
make host-probe-landing-second-opening \
  GARDEN_LANDING_SECOND_OPENING_OUT=artifacts/new-second-opening \
  GARDEN_LANDING_SECOND_OPENING_CAPTURE=artifacts/new-second-opening-capture.json.gz

# No simulator needed: verify the retained capture's identities and repeat receipts.
python3 sim/garden_landing_second_opening.py \
  --verify benchmarks/garden-seasons/landing-second-opening-capture.json.gz

# Also authenticate the original raw traces, binaries and source archive offline.
python3 sim/garden_landing_second_opening.py \
  --verify benchmarks/garden-seasons/landing-second-opening-capture.json.gz \
  --bundle artifacts/garden-landing-second-opening-v1

# Offline re-extraction from the pinned original bundle; fresh output required.
make host-audit-landing-second-opening \
  GARDEN_LANDING_SECOND_OPENING_AUDIT=artifacts/new-second-opening-audit.json.gz

# Portable complete resource/bank/seed/descendant reanalysis, without the raw bundle.
python3 sim/garden_landing_second_opening_audit.py \
  --verify benchmarks/garden-seasons/landing-second-opening-results.json.gz
```

The low-level CLI adds paired `--second-turnover-at TICK
--second-turnover-lineage ID` options to a first turnover event. Both require
`--ledger`; the second tick must be later, ecology-aligned and within the run,
with a different living, established target. Maximum replay length is now
1,228,800 logic ticks (320 days), not a changed simulation frequency. The
second event is after its tick's observations and retains normal decomposition.
It exports `second_turnover_probe`, marks both deaths as environmental, and wraps
the first tagged hash with the second event; single-event identities stay intact.

All five day-288 baselines must match the original treatment results, frames and
four traces before the 320-day phases start. All observation rows through day
288 must match; treatment repeats match all traces and untraced treatments match
states/frames. As before, capture requires 10 GiB free, takes `--jobs 1..4`, and
refuses existing paths/symlinks. No automatic resume, retargeting or training.
The audit pins this capture and raw manifest; it will not silently adopt a new
run. See the [paired report](../benchmarks/garden-seasons/landing-second-opening.md).

## Audit opportunities during the second opening

The [offline opportunity audit](../benchmarks/garden-seasons/landing-opening-opportunities.md)
uses the retained second-opening capture and portable accounting, without
raw traces or native executables. It measures overlap of dispersal reach,
current site gates, protected affordability and ordered seed-bank access for
all seven original focal plants and five first recruits in both arms.

```sh
# Offline; choose a fresh output. Uses the existing Docker image, no rebuild.
make host-audit-landing-opening-opportunities \
  GARDEN_LANDING_OPENING_OPPORTUNITIES_OUT=artifacts/new-opening-opportunities.json.gz

# Python standard library only; no container or simulator required.
python3 sim/garden_landing_opening_opportunities.py \
  --verify benchmarks/garden-seasons/landing-opening-opportunities-results.json.gz
python3 sim/test_garden_landing_opening_opportunities.py
```

Each treatment window includes slot reclamation but excludes the closing
germination, which precedes reproduction. Controls retain their eight-plant
state over the same times. Unknown traits are bounded across all five fixed
legal values, not inferred from an offspring or selected per tick. Current
mature-seed viability does not predict a new seed's post-dormancy success.
The audit revalidates prior evidence and refuses changed inputs, incompatible
phases, missing rows, guessed traits and altered summaries. It never launches
a simulator, trains a model or changes rules.

## Test paid replacement of an owned seed

The [frozen replacement protocol](../benchmarks/garden-seasons/landing-seed-replacement-protocol.md)
tests one host-only rule in the same five worlds through day 320. After day
288, a parent may pay the ordinary seed costs to replace its own oldest
spacing-blocked seed, but only with a full bank, reachable clear space and
plant/node capacity. All non-bank production gates remain mandatory. Other
parents' seeds, clear owned seeds, viability, dormancy and reserves are unchanged.

```sh
# Builds/tests both isolated variants; twenty full calls, fresh paths only.
make host-probe-landing-seed-replacement \
  GARDEN_LANDING_SEED_REPLACEMENT_OUT=artifacts/new-seed-replacement \
  GARDEN_LANDING_SEED_REPLACEMENT_CAPTURE=artifacts/new-seed-replacement.json.gz

# Offline portable provenance, ledger, comparison and receipt checks.
python3 sim/garden_landing_seed_replacement.py \
  --verify benchmarks/garden-seasons/landing-seed-replacement-results.json.gz

# Also rederive every post-onset seed/resource transaction and common prefix
# from retained raw traces. Neither verification mode launches a simulator.
python3 sim/garden_landing_seed_replacement.py \
  --verify benchmarks/garden-seasons/landing-seed-replacement-results.json.gz \
  --bundle artifacts/garden-landing-seed-replacement-v1
```

The capture requires 10 GiB free, accepts `--jobs 1..4` (default two), preserves
failed bundles and never automatically resumes or changes a rule. The controls
must reproduce the archived second-opening treatments; repeats match all five
traces and observer-free calls match results and framebuffers. Sources, model,
binaries and settings are saved before the first call. The raw verification
does more than the portable checks: resource totals and first-effect prefixes
are independently rebuilt from the complete streams.

The low-level `placement-replay` option is `--seed-replace-after TICK`. It
requires `--ledger`, `--seed-placement spacing` and a nonzero maintenance-aligned
tick within the run; activation is strictly afterwards. Omission leaves normal
behavior and run hashes unchanged. Enabled runs get a `seed_replacement_probe`
record and a tagged run hash. `--replacement-trace NEW.jsonl` records every
ecology step, including zero replacements, and refuses an existing output.
It also works with the rule off, for controls. A replaced seed has the explicit
terminal fate `replaced`; its fresh successor is a new, fully paid purchase.
The ordinary full-bank blocker remains visible in its production visit, paired
with the replacement receipt. Older analyses that assume every purchase has
zero blockers must not be applied to an enabled run.

This is a research switch, not a normal host or device setting. More purchases
do not establish benefit: compare offspring survival, lost opportunities in
other lineages, matched-parent maintenance and natural mortality.

## Start with an explicit model

```sh
# Docker builds all dependencies. artifacts/ is ignored by git.
make host-build
mkdir -p artifacts/landing-models

# A built-in reference with zero extra weights (a control, not a trained model).
make host-landing-garden \
  ARGS="reference artifacts/landing-models/reference.tgl --mode history"

# Or explicitly import a saved v1 model; its original bytes remain nested intact.
make host-landing-garden \
  ARGS="import artifacts/garden-champion.tgm artifacts/landing-models/champion.tgl --mode history"

make host-landing-garden ARGS="inspect artifacts/landing-models/reference.tgl"
```

Creation requires `--mode off|current|history`; `--omit-dead-only` is optional.
Loading never guesses the format or overrides a stored mask. Imports initialize
all 208 added weights to zero, so changing the mask alone cannot improve an
imported controller. `inspect` reports both CRCs, the fixed mask/flag, and the
number of nonzero added weights. CRCs detect corruption, not authenticity.

Model reads require exactly 1,448 valid bytes. New model and raw-image writes
refuse existing files, directories, and symlinks. An ordinary write/close failure
removes only the newly created partial output. These are exclusive-creation
operations, not crash-durable transactions; callers must own the destination
pathname while writing. Model-read failures preserve the caller's output.

## Replay one world

```sh
make host-landing-garden \
  ARGS="replay artifacts/landing-models/reference.tgl rainfed 0xa9c30c1f --ticks 122880 --climate seasonal --framebuffer artifacts/landing-frame.rgb565be"
```

Both `--ticks` and `--climate` are required; seed must be a nonzero u32.
Layouts are `rainfed` and `rainfed-crowded`; climates are `steady`, `winter`,
`drought`, and `seasonal`. Initial water is still part of scenario setup, but
there is no recurring irrigation or gardener assistance. Supported horizons are
0..1,105,920 logic ticks (288 Garden days). General evaluation and training
wrappers retain their separate 256-day limit. One Garden day is 3,840 logic ticks,
256 ecology steps, or 64 seconds at the device's nominal 60 Hz logic rate.

JSON records the model, climate, build-rule bits (wide=1, flower-origin=2),
ordinary world hash **and cache/model-aware run hash**, warmup, census, accumulated
post-step descendant-live logic ticks, and lifetime totals by species. Optional
capture is the same 240×240 RGB565 big-endian production render used by the old
replayer. It does not advance the simulation. The raster has one owner per
process; parallel batches use independent executable processes, not simultaneous
calls into the process-global renderer.

The landing-aware step now exposes the existing exact natural-death receipts.
The same lifetime ledger as the older evaluator retains birth/death history
after plant-slot compaction; totals must reconcile with the authoritative world
or the command fails. Both complete run and receipt output remain unchanged on
step failure. The 4,096-lineage host ledger fails explicitly on exhaustion,
never silently truncates a report. It is not part of device RAM.

Full-day survivors require a full day of potential follow-up; recent living and
dead offspring are reported separately. A historical durable parent and at least
one child each survived a day. That does not establish current renewal, and an
empty eligible cohort is not a zero-percent survival rate. Pending-seed ancestry,
closing-window fitness, and training selection are not added by this command.

## Compare saved models and capture PNGs

```sh
make host-evaluate-landing-garden \
  GARDEN_LANDING_OUT=artifacts/landing-comparison \
  GARDEN_LANDING_ARGS="--model control=artifacts/landing-models/reference.tgl --model candidate=artifacts/landing-models/champion.tgl --days 32 --climate steady --climate seasonal --seed 0xa9c30c1f --seed 0xed52188c --jobs 2"
```

Choose a **fresh** output directory. The collector retains:

- Frozen executable and models; settings, model metadata, CMake cache, source
  snapshot/hashes, and SHA-256 artifact inventory.
- Every requested case, including failed/empty ecologies; JSON outcomes and
  raw frames plus PNGs at fixed checkpoints. Each capture is independently
  replayed from tick zero and must match state, outcomes, and raw pixels exactly.
- A short comparison report and a per-climate first-seed contact sheet. Other
  seeds' frames are retained too. No best-looking run is selected.

Defaults: both layouts, seasonal climate, seed `0xa9c30c1f`, 32 days, checkpoints
1/16/32, two workers. Repeat `--model LABEL=PATH` (up to four), `--seed` (up to
eight), `--scenario`, `--climate`, and `--checkpoint-day` to choose a panel.
The final day is always included; at most six checkpoints. Names are bounded,
unique labels. These are **development** worlds, not a held-out test set.

Only ordinary ecology and the isolated wide/flower-origin builds are accepted.
For a deliberately built experimental directory, invoke
`python3 sim/garden_landing_evaluate.py --build PATH ...` inside the builder;
the friendly Make targets rebuild ordinary defaults. Never rebuild a frozen
older experiment directory. Keep source/build/model inputs fixed during a run.
Collection detects changed inputs, marks a started failed bundle `FAILED.txt`,
and publishes a complete manifest only after success. It never overwrites an
older bundle or silently resumes partial results.

The source snapshot describes files observed during collection; it is not an
attestation that an arbitrary supplied executable was built from those files.
Build immediately before collecting, then freeze inputs. Exact replay is tied
to the retained binary/model hashes and a compatible host runtime (the builder
container), not a promise of bit-identical rebuilds on every toolchain.

Recheck a **trusted local** bundle without rebuilding or changing its settings:

```sh
docker compose run --rm -T firmware python3 \
  artifacts/landing-comparison/sim/garden_landing_evaluate.py \
  --verify artifacts/landing-comparison
```

Verification checks recorded artifact hashes before executing the saved binary
and regenerates every saved state/frame. SHA-256 inventories detect accidental
edits, not malicious replacement of a bundle and its manifest.

## Gate before training

Tests cover explicit import/format separation, strict CLI bounds, no-clobber
and short-write failures, rollback, old/new lifetime agreement, zero-extra
world/pixel equivalence across all climates, nonzero saved-model influence,
independent repeats, PNG pixels, frozen-bundle verification and tamper rejection.

Next define a bounded, equal-budget host-training comparison of off/current/
history inputs under **identical mechanics**, with frozen seeds and untouched
validation conditions. This tooling supplies replayable model artifacts and
diagnostics; it does not yet train extended networks or add portable world saves.

## Verified checkpoint

All **130 ordinary / 124 representative older-research CTests pass**, plus the
four focused native/file/CLI/reference tests in a wide + flower-origin build.
The CLI tests compare 96 zero-extra captures against the old replayer (three
masks × two layouts × four climates × four checkpoints); world fingerprints,
census and raw pixels match, and capture-free replays have identical outcomes.
Saved nonzero weights influence the authoritative run. Audited and unaudited
landing steps retain byte-identical worlds/caches and the same death receipts
as the old path over three 32-day cases; failure rollback is covered.

The retained local workflow check uses a previously saved v1 controller
(`01b9d94a` payload CRC, SHA-256
`fab9b6d97de88a970d63bb8af8fc336d076bb3d0ae6867b307290209abf85cf2`),
imported separately with off/current/history masks and zero added weights.
Two weather seeds (`a9c30c1f`, `ed52188c`), two layouts and steady/seasonal
climates give **24 runs to day 32**, with **72 captures** at days 1/16/32.
Every capture repeats and the completed frozen bundle verifies independently.
All three masks have identical world fingerprints, census, lifetime outcomes
and pixels in each matched case, as expected for zero-extra imports.

The images also retain the old controller's failures: all four crowded
conditions end with no living plants or seeds, while ordinary rainfed endpoints
have two or three living plants. This small development panel is a workflow
check, not a fresh training result or an ecological promotion gate.

Local outputs are `artifacts/garden-landing-tools-panel/report.md` and its
`gallery/` subdirectory. Regression logs are
`artifacts/garden-landing-tools-{default,research,flower}.log`. Regenerate a
fresh panel with the commands above; no device flash was needed.

The changed `garden_world.c` also compiles with the recorded Zephyr firmware
flags, writing a separate object without changing the existing firmware build.
An additional ad-hoc `-Wextra -Werror` ARM check encounters the pre-existing
enum/type-limits warning in `picosystem_garden_world_set_climate`; that is not
part of the recorded build's warning configuration. This check is not a full
firmware rebuild, stack measurement, or hardware test.
