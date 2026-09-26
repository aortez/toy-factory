# Seasonal Garden v1: renewal and controller evaluation

Bounded follow-up to [winter/drought implementation](../../docs/garden-seasons.md).
Default device-sized ecology: 256 nodes, eight plant slots, eight seeds, no gardener
or recurring irrigation. Climate remains v1 (2–4-day drought); no tuning is promoted.

## Fresh eight-year panel

Four predeclared world/weather seeds from base `0x73656132`, two layouts, two
reference policies and four climates: 64 runs of 128 Garden days. Layouts and
policies share seeds; these are four weather replicates, not 64 independent ones.
All 64 worlds retained living plants; none reached an observed empty world.

| Climate | Worlds reproducing in final year | Final-year births | Final-year full-day survivors | Final-year durable parents | Multi-species endpoints, including seeds |
|---|---:|---:|---:|---:|---:|
| Steady | 1/16 | 1 | 0 | 0 | 13/16 |
| Winter | 2/16 | 7 | 3 | 0 | 5/16 |
| Drought | 8/16 | 36 | 30 | 6 | 0/16 |
| Both | 8/16 | 37 | 30 | 6 | 1/16 |

“Final-year” cohorts are born strictly after day 112. A durable parent is a
descendant which survived a full day and had a child which also survived a full
day. Recent births without a full day of possible follow-up are censored. These
are cumulative achievements within the cohort, not a promise of future survival.

The combined arm produces 583 births and 157 historical durable parents over
eight years, versus 100 and eight for steady controls. This demonstrates real
descendant reproduction, but does **not** qualify broad ecological variety:
15/16 combined worlds lose all but one species even counting unexpired seeds.
In 8/16 combined worlds every mature seed observed in the final year was
spacing-blocked. Shade and water blockers often overlap; one combined world also
shows node pressure. Increasing RAM alone would not resolve all of these cases.

Controller decisions matter. On `rainfed / ed52188b`, baseline ends in ground-cover
and adaptive in flowers under identical climate/rain. They produce 15 versus eight
historical durable parents; neither reproduces in the final year. This is a matched
policy comparison, not proof that a particular action caused the difference or
that baseline is generally superior.

## Initial diagnosis and isolated tuning

The original two-seed, 64-day panel was repeated with ancestry and uniform seed
site sampling. Of eight combined worlds, all had one living species; seven also
had only one viable species when seeds were counted. Six had every final-year
mature seed spacing-blocked, with no node-capacity blocker anywhere in that arm.

Selected 8-day death audits (`rainfed / fb4118d5`, baseline and adaptive) reconcile
all 13 natural-death receipts. Baseline's shrub and ground-cover founders die of
energy shortage during spring, before either hazard. Adaptive keeps those founders
until the first drought, when both die water-starved despite retaining substantial
energy: terminal pre-step reserves are 216 and 229 energy, zero water, with six
water upkeep due. These are terminal-step receipts, not complete lifetime budgets.

One isolated worktree of the evaluator checkpoint (rebased as `89cd384`) changes
only drought duration to 1–2 days.
The [exact patch](short-drought.patch) is retained and **not applied to production**.
All 32 day-0-through-4 prefixes and all 16 complete steady/winter negative controls
match exactly, including state histories and trace SHA-256s.

| Combined climate, 64 days | Original | Short drought |
|---|---:|---:|
| Multiple viable species at end | 1/8 | 2/8 |
| Worlds reproducing in final year | 2/8 | 2/8 |
| Final-year full-day offspring survivors | 3 | 5 |
| Final-year durable parents | 0 | 1 |
| Historical durable parents | 15 | 11 |

The candidate fails the predeclared historical-renewal retention gate. It is a
tradeoff, not a universal improvement. No fresh candidate run or second parameter
search follows that failed screen. Keep the original settings; discuss spatial
recruitment/dispersal and the desired renewal/diversity tradeoff separately.

## Real rendered checkpoints

Fixed first fresh seed `ed52188b`, rainfed/adaptive, combined climate. Images come
from the production renderer; each replay matches its recorded world hash and
RGB565 framebuffer CRC. They are not selected for best outcome.

| Winter, day 14 | Spring, day 16 | End of year eight, day 128 |
|---|---|---|
| ![Winter](frames/winter.png) | ![Spring recovery](frames/spring.png) | ![Year eight](frames/year-eight.png) |

The late frame illustrates persistent spatial occupancy; plant survival and a
stocked seed bank are not equivalent to continuing renewal.

## Saved-model bridge

The evaluator, matched bundles, deep traces, seed-site audits and galleries now
carry explicit climate identity/version and seed lifetime. Steady remains the
evaluation default; the trainer and its objective are unchanged.

An existing model, CRC `01b9d94a` (`r2-n.tgm` from prior research), was evaluated
without retraining: two fresh seeds from `0x73656133`, two layouts, 32 days,
combined climate. All 12 evaluator trajectories validate; two selected detailed
replays, eight seed-site audits and 18 real rendered frames reproduce their
recorded hashes, with the gallery additionally replayed byte-for-byte.
This is a workflow/compatibility check, **not model promotion**. The old model
goes extinct in one of four layout/seed cases, versus zero for adaptive.

## Retained evidence and reproduction

- [Fresh 128-day summary](fresh-128.json): all 64 endpoints, per-case cohort and
  blocker metrics, source/binary hashes and original full-report SHA-256.
- [Short-drought screen](short-drought-screen.json): both 32-case panels, named
  gates, exact-prefix/negative-control checks and provenance.
- Full daily/event reports, raw frames and death traces remain in ignored
  `artifacts/garden-seasons-diagnosis`, `artifacts/garden-seasons-fresh-128` and the
  isolated treatment worktree. Frame paths in JSON refer to those original bundles.
- Saved-model bundles remain under `artifacts/garden-seasonal-model-{eval,gallery,sites}`.

```sh
make host-seasons-garden GARDEN_SEASONS_OUT=artifacts/new-baseline \
  GARDEN_SEASONS_ARGS="--days 64 --trials 2 --jobs 4 --seed-audit --screenshots"
make host-seasons-garden GARDEN_SEASONS_OUT=artifacts/new-fresh \
  GARDEN_SEASONS_ARGS="--days 128 --trials 4 --seed-base 0x73656132 --jobs 4 --seed-audit --screenshots"
python3 sim/garden_season_report.py --control artifacts/new-fresh/results.json \
  --out artifacts/new-fresh-summary.json
```

For the treatment, use a separate worktree at `89cd384`, apply the retained patch
with `git apply --unidiff-zero /path/to/short-drought.patch`, build there, and rerun
the baseline command. Summarize with `--control`,
`--candidate` and a new `--out`; the script rejects mismatched panels, changed
negative controls and changed early prefixes. Source/collector changes can alter
byte-level provenance even when authoritative world hashes remain unchanged.

This closes a bounded seasonal-environment implementation and evaluation pass.
It does not close roadmap #30's environment-qualification or training milestones.
All 100 default and 105 research host tests pass; standalone checks and a pristine
Zephyr build also pass. The conservative firmware uses 257,596 bytes of flash and
223,004 bytes of main RAM. The recommended `make build-fast` image uses 263,516
bytes of flash and 255,772 bytes of its 255 KiB main RAM region (5,348 bytes of
linker headroom). Both retain the separate 8 KiB Core 1 reservation. Host-only
evaluation/analysis adds no device storage or model-ABI changes.

## Physical PIM559 check

On 2026-09-25, the device eventually appeared over USB after an interval with no
host attachment events. Both ROM bootloader and normal application enumeration
were observed. The running shell then accepted a software bootloader request,
and the seasonal `build-fast` image flashed and re-enumerated successfully.
This confirms a working update path, not the cause or resolution of the earlier
intermittent connection problem.

The PL022/DMA 62.5 MHz, core-1-rendering image is built from `e6c7078`; its UF2
SHA-256 is `6a7844cd30e4bde113761b465b87020dd95715546e2307e7cf04eda5de3f40d5`.
Two unchanged canned sequences pass on the device:

| Sequence | Tick | State hash | Framebuffer CRC-32 |
|---|---:|---|---|
| `garden-smoke.json` | 930 | `da79a9d8` | `fc95584f` |
| `garden-mature.json` | 3,771 | `f7c895f8` | `1f128cce` |

The ordinary lifecycle runner stopped after a reply without a parseable state
line. A read-only state query found tick 4,230 / `aca05c93`; the failure capture's
CRC `89fd28c0` and that state both match an independent native replay. A local
continuation harness verifies this checkpoint before resuming bounded steps. It
logs unexpected replies and reconciles them with a read-only state query, never
blindly retrying a potentially completed step. USB has remained attached since
the flash; the original malformed reply's contents were not retained.

At tick 38,310 the continuation captured a premature reply containing a battery
log followed by `toy-factory:~$ picosystem game step 120`, but no result. The
read-only query confirmed the completed tick at hash `697eb956`. The original reader
could mistake an asynchronous log's prompt redraw for command completion before
the step response arrives. This explains that captured interruption, not the
earlier USB attachment failure. These checks did not silently retry mutations.

The continued device state also matches the host at drought day 5, tick 19,590 /
`ed7ea849`, and at the reconciled tick 38,310. Both later endpoints pass state and
framebuffer assertions:

| Continued lifecycle checkpoint | Tick | State hash | Framebuffer CRC-32 |
|---|---:|---|---|
| Winter, year 0 / day 14 | 54,030 | `a2d73157` | `7b6918c7` |
| First spring, year 1 / day 0 | 61,440 | `1f28bcf4` | `c86ee370` |

Downloaded winter and spring PNGs are also byte-for-byte identical to their
native reference images. Winter reports light 60% and cold germination blocking;
spring restores light 100% and clears that blocker. Both endpoints have two
living plants, eight banked seeds, five deaths/reclaimed plants, three
germinations and maximum generation one. Seed viability is reported as 32 days.
The spring reference repeats `garden-lifecycle.json`'s actions but extends its
final neutral span to 61,410 ticks (61,440 total), covering one full seasonal year.

Continuation from tick 4,230 through spring, including captures/status queries,
took 637 seconds and required one read-only reply reconciliation. This exercises
bounded USB stepping, not normal presentation cadence or headless throughput;
the pause/step window's reported Hz/fps are not live-performance measurements.

After resetting Garden and restoring physical input, a 3,598-tick live window
held 60.0 Hz simulation and 29.8 fps presentation, with zero skipped or
over-budget updates and maximum backlog one. Complete updates averaged 0.840 ms
and peaked at 8.429 ms; display transfer was 18.351 ms. Main/render stack
high-water marks were 3,932/5,120 and 3,196/5,120 bytes; core 1 reported ready,
no error, and 296/4,096 bytes of stack. The fresh three-plant Garden is left
running with the auto-gardener off and physical controls enabled. This short
live window is a smoke check, not a worst-case scene performance bound.

Local logs, reference JSON, captures, and the continuation harness are retained
in `artifacts/garden-seasons-device`. These input fixtures test deterministic
host/device compatibility; their manual/automatic gardener actions are not the
unassisted rainfed ecology panel above. User playtesting remains separate.

### USB reader follow-up

The host reader now requires an idle prompt at the end of the current terminal
line. It recognizes Zephyr's cursor-left/erase repaint sequence, retains partial
ANSI escapes until complete, and revokes a candidate prompt when a later fragment
adds command text. Existing absolute timeouts and no-retry behavior are unchanged;
there is no firmware/protocol or simulation change.

Seventeen reader tests cover the captured battery-log race, delayed results,
fragmented prompts/ANSI escapes, in-place repainting, legacy prompts, bounded
timeouts, and exactly one command submission on both success and failure.
The ordinary runner then passed the complete 54,030-tick lifecycle replay without
the recovery harness or retries:

```sh
make sim-test SEQUENCE=scripts/sequences/garden-lifecycle.json
# PASS garden-death-decomposition-reclamation: tick=54030 hash=a2d73157 framebuffer_crc32=7b6918c7
```

The fixed-reader run is retained as
`artifacts/garden-seasons-device/reader-fixed-lifecycle.log`. The device was reset
to a fresh Garden with physical controls and real-time scheduling restored.
`make check` passed standalone checks, all 100 default host tests and the pristine
firmware build; `make host-research-check` passed all 105 tests, and
`make host-player-check` passed its dummy-display smoke test. The focused reader,
sequence and capture suites passed 17, 15 and six tests respectively. A host-side
C assertion also received a formatting-only correction during the final checks.
