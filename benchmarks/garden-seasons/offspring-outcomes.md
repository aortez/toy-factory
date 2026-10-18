# Extra germination does not guarantee establishment

Read-only audit of all 128 trajectories from the
[fresh scattering confirmation](dispersal-confirmation.md), following the
[fixed outcome protocol](offspring-outcomes-protocol.md). No additional native
simulation, intervention, training or firmware change was needed.

There are two distinct limitations: many extra seedlings die quickly, and most
late survivors have not produced a germinated child by the endpoint. Do not
combine these into one presumed weather or controller failure.

## Reconciled seasonal offspring cohorts

Each column below describes 32 seasonal worlds. Whole-run and final-year columns
are overlapping birth cohorts, not independent observations.

| Stage | Whole run, narrow | Whole run, wide | Final year, narrow | Final year, wide |
|---|---:|---:|---:|---:|
| Descendant births | 697 | 1,077 | 22 | 50 |
| Full day of possible follow-up | 691 | 1,064 | 16 | 37 |
| Died on/before the full-day boundary | 249 | 470 | 2 | 17 |
| Survived that boundary | 442 | 594 | 14 | 20 |
| Of survivors: no germinated child observed | 244 | 340 | 14 | 18 |
| Of survivors: child, but none survived a day yet | 35 | 43 | 0 | 1 |
| Of survivors: durable parent | 163 | 211 | 0 | 1 |

The three rows after survival partition the surviving cohort exactly. A child
can germinate after its parent's death; these counts include such recorded
children rather than requiring a living parent at germination. A durable parent
and at least one child each survived a complete day.

The narrow arm has six recent births with insufficient follow-up; wide has
thirteen, **one of which has already died**. This known death remains in the
censored group to preserve the predeclared survival denominator. Thus there
are 18 observed early deaths among all wide late births, but 17 among the 37
eligible for the screen's full-day check. Censored does not mean successful.

Whole-run day survival falls **64.0% → 55.8%**. Among offspring that do survive
a day, the fraction recorded as durable parents is more similar:
**163/442 (36.9%) → 211/594 (35.5%)**. Wider scattering yields more absolute
survivors and parents, but no corresponding efficiency gain in these cohorts.
The changed plants cannot be matched by numeric ID across arms; these are
matched-world aggregates, not treatment effects on the same individual.

## What kills eligible young offspring?

For the 17 wide **final-year eligible** first-day deaths:

| Recorded terminal shortage | Ordinary seasonal light, no active drought | Active drought | Seasonally dim light | Total |
|---|---:|---:|---:|---:|
| Energy only | 8 | 0 | 1 | 9 |
| Water only | 7 | 0 | 1 | 8 |
| Both | 0 | 0 | 0 | 0 |

Narrow has two such deaths, both energy-only: one ordinary and one under dim
light. The wider cohort is not simply dying during the active drought interval:
**15/17** deaths occur with neither active drought nor seasonally reduced direct
light. Dry soil, depleted stores and past hazards can still affect these plants.
The final shortage flag is not a lifetime resource budget or a causal attribution
to climate.

Six of the 17 wide deaths occur within a quarter day of germination, another six
by half a day, and five between half and one day. These are elapsed ages,
**not first-night classifications**; the saved summary has no per-step sun,
root access, storage or controller-purchase history.

The whole-run pattern is also mostly early energy failure: narrow has
215 energy-only / 33 water-only / one combined first-day death; wide has
372 / 93 / five. Of the 470 wide eligible first-day deaths, 319 occur under
ordinary conditions, nine during drought and 142 under seasonal dimming.
These are event counts, not hazard rates adjusted for population or exposure.

Seasonal light tapers within days. The audit uses each death's recorded light
and drought state; it checks day/year/season/mode against daily snapshots and
bounds light with neighboring daily values. Treating daily light as constant
would misclassify some autumn/winter events.

## Species, policies and remaining reproduction

| Final-year cohort | Births, narrow → wide | Day survivors | Durable parents |
|---|---:|---:|---:|
| Flowers | 21 → 39 | 13 → 14 | 0 → 0 |
| Ground cover | 1 → 8 | 1 → 5 | 0 → 1 |
| Shrubs | 0 → 3 | 0 → 1 | 0 → 0 |

The wider rule adds little late flower survival despite many more births.
Ground cover supplies four of the six additional late survivors and the only
late durable parent. This is more informative than labeling every additional
birth a gain in continuing renewal; all 32 endpoints still retain only one
viable species each.

Baseline accounts for **15/17** wide eligible late first-day deaths and all eight
water-only ones. Its eligible late births rise 8 → 29 and survivors 7 → 14.
Adaptive has eight eligible births under each rule, with first-day deaths
1 → 2 and survivors 7 → 6. Thus baseline experiences both the large germination
gain and most of the additional losses; this does not establish which purchase
decision or spatial condition caused them.

The four weather-seed blocks with fewer late survivors have different accounting:

- `4f0b9246`: eligible births 4 → 1, early deaths 1 → 0, survivors 3 → 1.
- `c629bb62`: eligible births 3 → 2, no early deaths, survivors 3 → 2; another
  wide birth is too recent, so raw births remain four in both arms.
- `20e1353b`: eligible births 3 → 2, one early death in each arm, survivors 2 → 1.
- `82deacfc`: two eligible births in each arm, early deaths 0 → 2, survivors 2 → 0.

A mortality-only explanation therefore does not account for every regression.
All weather/layout/policy partitions and matched cases are retained in the
[machine-readable audit](offspring-outcomes-summary.json).

Of the 19 wide late day survivors not yet classed as durable parents, **17 remain
alive** at the endpoint. Eighteen have no germinated child recorded; the remaining
one has a living child too young for its own full-day check. In the narrow arm,
13/14 analogous survivors remain alive, all without a recorded child. Missing
offspring is not proof of sterility, lack of seed production or permanent
failure: retained seeds and living plants may reproduce after the observation
window. The eight-year endpoint is not a fixed-age parental follow-up.

Steady controls show a similar early-establishment cost without a seasonal
hazard: eligible first-day deaths **118/200 → 201/314**, day survivors
**82 → 113**, durable parents **15 → 18**. Late renewal remains zero versus
one birth which dies within half a day. Simply removing current hazards is not
demonstrated to solve establishment or continuing renewal.

## Verification and reproduction

The input full-report SHA-256 and its equality to the published compact evidence
are checked before analysis. Every birth, founder, parent generation/family,
death identity/timestamp/shortage flag and climate observation reconciles.
All cohort partitions reproduce the original lifetime and censor totals.

Five unit cases, with boundary and malformed-input subcases, cover exact-day
death, censored living/dead offspring, child survival, later parental death,
age/weather/resource bins, intra-day light/cold, missing/duplicate records and
partition aggregation. Two independent invocations of the offline audit produce
byte-identical output; no native processes are invoked. The retained JSON is
byte-identical to that output, SHA-256
`8e996c6235f6be743728b3e1eacf13af482f13c47320e497153b469b4f85491c`.
All **105 default host tests**, **108 research tests**, standalone checks,
the host-player smoke test and a pristine firmware build pass. No new firmware
memory is used. The exact full input is also retained in the
[compressed histories](dispersal-confirmation-histories.json.gz), and an audit
from the decompressed repo archive reproduces the retained JSON byte-for-byte.

```sh
docker compose run --rm -T firmware bash -c '
  set -e -C
  mkdir -p artifacts
  gzip -dc benchmarks/garden-seasons/dispersal-confirmation-histories.json.gz \
    > artifacts/recovered-confirmation.json
'
docker compose run --rm -T firmware python3 -W error sim/garden_season_offspring.py \
  --input artifacts/recovered-confirmation.json \
  --out artifacts/new-offspring-outcomes.json
cmp artifacts/new-offspring-outcomes.json benchmarks/garden-seasons/offspring-outcomes-summary.json
```

The recovered input and output paths must not already exist. Alternatively,
use the original `artifacts/garden-seasonal-wide-confirmation/results.json`
directly with `--input`. The derived JSON retains matched-case, species and
subgroup accounting; the compressed input supplies the full lifetime histories
and frozen provenance needed to reproduce it without new simulation calls.

## Follow-up

The [fixed seedling resource replay](seedling-resources.md) now implements the
diagnostic proposed below. It reconciles five focal plants in six matched worlds,
without changing rules or selecting replacements for an absent counterpart.
Its limiting-resource spending evidence motivates a separate counterfactual;
it does not itself demonstrate rescue.

### Original next proposal

Keep wider scattering experimental. The next useful step is a small, predeclared
matched replay with per-step seedling light, water uptake, upkeep, reserves and
growth purchases. Include an energy-only and a water-only early failure from the
ordinary-weather portion, along with a surviving seedling for context. This can
distinguish a poor landing site from a body/controller that spends or grows beyond
its resources. Do not assume either explanation, change germination thresholds,
weaken hazards or add survival subsidies from these terminal flags alone.

Longer parental follow-up and seed-fate accounting remain separate questions
for the living non-reproducing cohort. No ecology, fitness, controller, default
or qualification milestone changes as a result of this diagnostic.
