# Combined uptake and scattering experiment

## Fixed 2×2 protocol

The [wider-scattering trial](dispersal.md) improved placement but not consistent
survival; [storage-limited uptake](water-headroom.md) reduced water stress but
left fewer planting opportunities. Test their missing combination before
altering capacities, adding turnover mechanics or retraining controllers.

| Condition | Attempted zero-trait scatter distance | Root extraction |
|---|---|---|
| Baseline | 5–7 cells | Limited by soil/rate; excess storage discarded |
| Wide only | 3–9 cells | Baseline |
| Capped only | 5–7 cells | Also limited by remaining plant storage |
| Combined | 3–9 cells | Storage-limited |

Inheritance offsets, edge reflection, random-draw use, capacities, growth and
reproduction costs, seed lifetime, rain-v1, light and all other mechanics stay
fixed. Model `dc5e849d` and the same original NN / night-growth-veto NN / adaptive
policies run across eight weather seeds from batch `0x6d617463`, both rainfed
layouts, 24 cycles (92,160 ticks). No gardener or training. This makes 48 matched
world identities across four conditions, not 192 independent environments.

Reuse the verified frozen controls: `artifacts/garden-water-control`,
`artifacts/garden-dispersal-wide`, and `artifacts/garden-water-capped`. The current
normal evaluator is also checked against both full-horizon baseline reports.
Existing reports/weights are not overwritten. The final eight cycles remain
the late-renewal window. Existing qualification counts are cumulative thresholds,
not a late-born cohort. Full-cycle survival needs an eligible denominator.

A useful combined result should improve lasting offspring/renewal relative to
the individual changes, not just births or final density. Retain regressions and
extinct worlds, examine each policy/layout, and check node/spacing/light pressure.
The descriptive interaction `combined - wide - capped + baseline` is reported
on each metric's raw scale; it is not significance or proof of biological synergy.

Fixed visual panel: seeds `6f47c12c` and `9c530b07`, both layouts and all three
policies, at ticks 68,760 and 92,160. Compare against the prior galleries; the
second seed is an already known counterexample, not an untouched random sample.

## Reproduce

The combined build requires **all three** explicit CMake options. Both effects
without opt-in, or opt-in without both effects, are rejected. The collector also
requires matching flags; flags validate the binary identity, not runtime toggles.
Normal `make host-build` disables all experiments; firmware rejects them.

```sh
make host-build
docker compose run --rm firmware cmake -S sim \
  -B artifacts/build-host-water-wide-combined -G Ninja \
  -DTOY_FACTORY_GARDEN_WIDE_DISPERSAL=ON \
  -DTOY_FACTORY_GARDEN_WATER_HEADROOM=ON \
  -DTOY_FACTORY_GARDEN_COMBINED_EXPERIMENT=ON \
  -DTOY_FACTORY_SIMULATOR_SANITIZERS=ON
docker compose run --rm firmware cmake --build artifacts/build-host-water-wide-combined
docker compose run --rm firmware python3 sim/test_garden_dispersal.py \
  --narrow-build build-host --combined-build artifacts/build-host-water-wide-combined

docker compose run --rm firmware python3 sim/garden_experiments.py \
  --output artifacts/garden-water-wide-combined \
  --dispersal wide-v1 --water-uptake headroom-v1 --combined-experiment \
  --evaluator artifacts/build-host-water-wide-combined/toy-factory-garden-eval \
  --inspector artifacts/build-host-water-wide-combined/toy-factory-garden-inspect \
  --candidate-model artifacts/garden-lifetimes/champion.tgm \
  --control-model artifacts/garden-lifetimes/champion.tgm \
  --candidate-probe no-night-growth-v1 \
  --training-report artifacts/garden-lifetimes/training.json \
  --split exploratory --cycles 24 --trials 8 --seed 0x6d617463
docker compose run --rm firmware python3 sim/garden_factorial.py \
  --baseline artifacts/garden-water-control --wide artifacts/garden-dispersal-wide \
  --capped artifacts/garden-water-capped --combined artifacts/garden-water-wide-combined \
  --late-cycles 8 --output artifacts/garden-ecology-factorial.json

docker compose run --rm firmware python3 sim/garden_establishment.py \
  --bundle artifacts/garden-water-wide-combined --output artifacts/garden-water-wide-combined-audit \
  --inspector artifacts/build-host-water-wide-combined/toy-factory-garden-inspect
docker compose run --rm firmware python3 sim/garden_gallery.py \
  --bundle artifacts/garden-water-wide-combined --output artifacts/garden-water-wide-combined-gallery \
  --replayer artifacts/build-host-water-wide-combined/toy-factory-garden-replay \
  --include-adaptive --seed 6f47c12c --seed 9c530b07 --checkpoint 68760 --checkpoint 92160
```

Use new output paths for repeats. Do not edit sources during collection. The
factorial tool verifies all four completed bundles and their model/setting
identities before producing paired contrasts; it refuses missing/duplicate
worlds. The individual-condition reports remain available alongside contrasts.

## Results

Completed locally on `green-garden`, 2026-09-11. This is host-only: no default
ecology change, deployment, training or capacity increase. Results and code
remain uncommitted/unpushed at the time of this note.

### More surviving offspring, not sustained renewal

Totals across 16 worlds per policy. Each cell lists **baseline / wide only /
capped only / combined**, in that order.

| Policy | Births (germinations) | Full-cycle survivors / eligible offspring | Durable parents | Final living plants |
|---|---|---|---|---|
| Original NN | 138 / 263 / 108 / 155 | 44/137 · 51/260 · 54/108 · 83/155 | 23 / 23 / 32 / 34 | 55 / 65 / 68 / 99 |
| NN + night-growth veto | 181 / 211 / 135 / 134 | 78/180 · 81/208 · 77/135 · 80/134 | 33 / 26 / 26 / 19 | 79 / 90 / 90 / 104 |
| Adaptive | 78 / 117 / 65 / 80 | 44/78 · 68/114 · 45/65 · 64/80 | 11 / 15 / 11 / 16 | 79 / 96 / 89 / 101 |

A durable parent is an offspring which, along with at least one of its children,
survived a full cycle. These are cumulative counts: the survivors need not still
be alive at the endpoint or coexist. All combined offspring have sufficient
follow-up; no recent-birth denominator is hidden.

The original NN benefits most: combined has more full-cycle offspring survivors
than wide-only in 11 worlds, ties in four, regresses in one; versus capped-only
the split is 12/3/1. But the veto policy loses durable parents versus capped-only
in eight worlds, gains in four and ties in four. Adaptive has fewer full-cycle
survivors than wide-only in seven worlds, gains in four, ties in five. There is
no policy-independent best condition. Final nonviable worlds stay at 3/16 for
the original NN and 0/16 for each other policy in every condition; first-dawn
living totals stay 16, 64 and 64 respectively.

The descriptive interaction in full-cycle survivor counts is +22 / 0 / −5 for
NN / veto / adaptive; in durable parents it is +2 / 0 / +1. This is arithmetic
on the matched panel, not a significance test or a generalization claim.

Combined results split by layout (eight worlds per row):

| Layout | Policy | Births | Full-cycle survivors / eligible | Durable parents | Late births |
|---|---|---:|---:|---:|---:|
| Rainfed | NN | 79 | 40/79 | 18 | 0 |
| Crowded | NN | 76 | 43/76 | 16 | 0 |
| Rainfed | Veto | 78 | 47/78 | 11 | 0 |
| Crowded | Veto | 56 | 33/56 | 8 | 1 |
| Rainfed | Adaptive | 54 | 40/54 | 13 | 1 |
| Crowded | Adaptive | 26 | 24/26 | 3 | 0 |

### Late activity and allocation pressure

Final-eight-cycle totals, again baseline / wide / capped / combined:

| Policy | Births | Newly qualified full-cycle survivors | Newly qualified durable parents | Mean completely-full node-pool time |
|---|---|---|---|---|
| NN | 12 / 46 / 2 / 0 | 2 / 7 / 1 / 0 | 2 / 2 / 1 / 0 | 0% / 1.80% / 0% / 62.50% |
| Veto | 8 / 18 / 4 / 1 | 5 / 4 / 3 / 2 | 5 / 1 / 3 / 2 | 24.05% / 62.50% / 54.60% / 99.26% |
| Adaptive | 5 / 17 / 4 / 1 | 2 / 12 / 1 / 1 | 1 / 5 / 0 / 1 | 18.75% / 65.56% / 44.76% / 99.13% |

Only **two late births and zero late deaths** occur across all 48 combined
worlds. Late seed creation/expiry remains active: NN 744/744, veto 1001/999,
adaptive 1025/1024. The simulator is not stalled. Qualification counts can lag
births, so they are not survival rates of the late-born cohort.

The completely-full-pool measure uses at-most-one-second timeline samples and
includes extinct worlds in its mean. Germination needs four free nodes, so
253–255 occupied nodes can block seedlings without being completely full.
The seed census samples every ecology step and confirms the stronger constraint.

Late-born seeds with a full potential seed lifetime (born after tick 61,440,
through tick 88,320):

| Policy | Baseline germinated / eligible | Wide | Capped | Combined |
|---|---:|---:|---:|---:|
| NN | 10/381 | 39/447 | 2/506 | 0/651 |
| Veto | 6/746 | 16/802 | 4/835 | 1/876 |
| Adaptive | 5/855 | 12/849 | 4/862 | 1/897 |

Combined late bright-day **remaining mature-seed observations**:

| Policy | Observations | Moisture blocked | Spacing blocked | Light blocked | Node blocked | Plant-slot blocked | Only node blocked |
|---|---:|---:|---:|---:|---:|---:|---:|
| NN | 47,128 | 2.95% | 96.23% | 35.60% | 92.51% | 60.02% | 1,233 |
| Veto | 63,635 | 16.68% | 92.25% | 65.61% | 99.51% | 16.03% | 3,651 |
| Adaptive | 65,519 | 10.43% | 88.66% | 66.87% | 99.05% | 0% | 1,865 |

These are overlapping, repeated, post-step and survivor-biased observations,
not independent failure probabilities. Actual germinated seeds have already
left the bank. Node-only observations show that freeing node storage would
remove the sole recorded instantaneous blocker at some actual landing sites;
they do not prove later survival, or that increasing storage alone would restore
renewal. Most observations also fail other checks. Of 651/875/896 expired late
eligible NN/veto/adaptive seeds, only 14/2/1 ever had a reachable open site in
the recorded post-step snapshots.

### Water accounting and visual counterexamples

Combined water-only deaths are 26 / 22 / 0 for NN / veto / adaptive, versus
33 / 68 / 10 baseline and 12 / 21 / 0 capped-only. Combined energy/water deaths
are 2 / 2 / 0. More plants and different placements change the demand; adding
scattering to capped uptake does not reduce every water-death count.

Exact late mean soil water is 26,248.65 / 17,445.76 / 17,941.90. These means
include all worlds; extinct NN worlds retain rain. No cell reaches 255 and no
exact world total exceeds 65,535 during the observed horizon. All **210,376**
checked living plant-steps in the selected detailed combined traces reconcile
with **zero water overflow discard**. **69 terminal steps** remain excluded
because death clears income telemetry; this is not full world conservation.
Selected detailed cases differ between conditions, so their budget totals are
not an unbiased paired policy comparison.

The predeclared gallery is `artifacts/garden-water-wide-combined-gallery/index.md`.
All 24 native frames match evaluator hashes and exact frozen replay bytes.
The panel visually has more occupied columns and largely unchanged plant
structures between its two late checkpoints; numerical traces, not appearance
alone, establish the lack of new births.

Examples retained rather than selecting only wins:

- Rainfed `6f47c12c`, adaptive: combined ends with seven living plants versus
  five capped-only, full-cycle offspring survivors seven versus two, durable
  parents two versus zero; both have zero late births. Combined has no free
  nodes throughout the late window.
- Rainfed `9c530b07`, veto: six final living plants in both capped-only and
  combined, but full-cycle offspring survivors fall five → three and durable
  parents two → zero. Both have zero late births and completely full node pools.
  At the combined endpoint, columns 0 and 1 have moisture 88/87 and light 255;
  node capacity is their only site blocker. This demonstrates an allocation
  constraint without assuming all other positions are viable.
- Rainfed `9c530b07`, adaptive: combined has nine full-cycle offspring survivors
  and five durable parents versus wide-only ten/five, but zero late births
  versus two. A dense, healthy-looking final frame is not proof of renewal.

Resource analysis reuses `soil_summary()` and `budgets()` from
`water-headroom.py`, after `garden_ecology.compare()` validates the combined
environment and frozen artifacts. Reproduce the auxiliary output with:

```sh
docker compose run --rm firmware python3 - <<'PY'
import importlib.util
from pathlib import Path
spec = importlib.util.spec_from_file_location('water', 'benchmarks/garden-longevity/water-headroom.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
root = Path('artifacts/garden-water-wide-combined').resolve()
paired = m.ecology.compare(Path('artifacts/garden-water-control').resolve(), root,
                          m.experiment.COMBINED_ENVIRONMENT, 8)
result = {
    'soil': m.soil_summary(root.with_name(root.name+'-audit'),
                           paired['candidate']['input_manifest_sha256'], 8),
    'selected_budgets': m.budgets(root, 8, True),
    'input_manifest_sha256': paired['candidate']['input_manifest_sha256'],
    'analysis_sha256': m.experiment.digest(Path(m.__file__)),
}
output = Path('artifacts/garden-combined-resources.json')
m.require(not output.exists(), 'output already exists')
m.experiment.write_json(output, result)
PY
```

### Validation and provenance

- All 24 normal host CTests pass under strict compiler warnings/UBSan. Added
  tests cover matched four-condition identities and arithmetic, missing/duplicate
  worlds, missing observations, all eight build/header option combinations and
  firmware rejection. Wide-only, capped-only and combined cross-build integration
  tests also pass:
  both shared rule boundary tests, metadata rejection, audits, screenshots,
  frozen replay, pre-intervention equality and comparison overwrite protection.
- Current normal evaluator reproduces **both** prior full-horizon baseline
  reports byte-for-byte. No control model/report was overwritten.
- Combined census reconciles **7,995 seeds** against **77,377 checkpoints**.
  Frozen audit case 02 replays and reanalyzes exactly; all 24 gallery frames
  separately reproduce state and framebuffer bytes.
- The four-condition analyzer verifies every completed bundle's recorded
  artifacts and pairs all 48 world identities, retaining per-policy/layout data.

Local, ignored artifact identities (SHA-256):

| Artifact | SHA-256 |
|---|---|
| Baseline manifest | `3223ca779afa9e47be5d8f8b8f071295d915949c6f344303f24348521d730f95` |
| Wide manifest | `4e6c55005908ac23320d807cbe1d6defce3a385428ba12c375a096ab55454742` |
| Capped manifest | `cf7a731fc97196a8ca3ecde4a30a015002b5542eb36e98f45489b3bfc4f75a42` |
| Combined manifest | `62bfff06d6c974910a3bc7738d51c57ae08262e9477b8fda207eb02a313c8ff2` |
| Combined audit manifest | `7f261e93b0c43b1a5c15bca40cdca3e44c21a9d835d345485977e39e7465cdb3` |
| Combined gallery manifest | `34531df12a2fdbc2b00775abc59370cea630158041b309152a13b836869b14ed` |
| Four-condition comparison | `cbcd78723e502f8f58cd7a2ffc8bdd8d2fcb8ad253041d92344ae319953670c9` |
| Combined resource analysis | `855740052ad775f202e526bb93128960b8e2c1d7c599d3362b80d3d07f9d5882` |

Source snapshots include the dirty/untracked implementation and predeclared
protocol, not just HEAD. Later prose results are not retroactively inserted
into frozen bundles. These local files are not claimed to be published evidence;
this versioned note retains the numbers and reproduction protocol.

## Decision and next discussion

Keep all experiments explicit and host-only. The combination improves original
NN offspring survival but does not meet the sustained-renewal goal. Lower births
are not intrinsically bad; the concern is near-zero later replacement alongside
an artificial shared storage ceiling. A useful next investigation is **node
ownership and reclamation**: how much is live roots/shoots, how much is dead
tissue awaiting recovery, and whether viable seedlings lack a bounded budget.
Separate that from real space/shade competition before discussing a controlled
capacity or tissue-turnover change. More memory could merely postpone saturation;
forced death would change ecology and should not be added to inflate a score.
No new experiment or large training run follows automatically, and the
roadmap qualification milestones remain open.
