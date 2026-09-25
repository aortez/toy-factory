# Lineage persistence v2: live offspring time and bounded follow-up

The targeted v1 preference is fixed: **one longer-lived child now beats four
children dying just after establishment**, including when those brief children
come from four different renewing parents. Seed-only endings have an explicit,
fixed observation budget. V1 remains unchanged as a reference; neither score
is installed in the trainer.

The [protocol](lineage-persistence-protocol.md) was frozen before computing new
native scores. This is another offline test of the existing eight histories,
not new simulations, ecology changes, fresh validation or model optimization.

## Revised function

Maximize, left to right:

`(terminal tier, renewing-child live ticks, all-descendant live ticks,
  renewing parents, new establishments)`

The new primary reproduction measure is **observed live time of newly
established children of established non-founder parents**. The child must
complete its first day inside the scoring window. It then contributes one
15-tick sample for each observed alive sample at/after confirmation, up to the
end of the window. This is actual discrete occupancy, not an assumed future
lifespan or a whole reward just for crossing a threshold.

A parent's later death does not revoke its child's contribution. Each child
counts once, not once per ancestor. Children of founders and older established
descendants can contribute to all-descendant occupancy but not this recent
further-generation renewal measure. Distinct-parent and establishment counts
are now tie-breakers after live time, not ways to override it.

Seed purchases, body size, stores, action counts and generation labels still
have no direct reward. V1's exact lineage validation, first-day boundaries and
natural-versus-patch accounting remain in use.

## Fixed two-day follow-up

Every world uses the same **(day 158, day 190]** scoring window and continues
through **day 192** for terminal assessment. One Garden day is 3,840 logic ticks.
The two-day tail allows the maximum one-day lifetime of a seed already pending
at day 190, plus one day to observe any resulting seedling.

The main scoring window remains 32 days long but moves two days earlier than
v1's original experiment. We therefore also rescore unchanged v1 on the new
main window. The JSON retains original v1, matched-window v1 and revised v2
scores separately. Future births, purchases, seed outcomes and deaths cannot
leak into main-window metrics when projecting the recorded histories.

At the common final deadline, terminal tier is:

- **1:** at least one established non-founder is alive.
- **0:** living plants remain without an established non-founder, or only
  pending seeds remain. The latter is explicitly `seed-only-unconfirmed`, not
  successful recovery or observed extinction.
- **-1:** no living plants and no pending seeds: observed extinction.

New seeds produced during follow-up do not extend the deadline. They cannot
earn seed-count, establishment or offspring-time credit retroactively. A
short/truncated history has no comparable score; a suite must not drop it.

This is a bounded evaluation rule, not a complete resolution of all future
lineage fate. A newly produced pending seed can remain unconfirmed at the fixed
deadline. Tier 0 conservatively distinguishes that from known extinction while
ranking it below observed established presence. The cutoff remains sensitive
to a death on the exact final sample.

## Synthetic challenges

These are explicit arithmetic histories, not demonstrated native strategies.
The full original fixture set remains in the export, with synthetic extensions
through the common follow-up deadline and exact unchanged v1 prefixes.

| Fixture | Renewing-child live ticks | All-descendant live ticks | Renewing parents / establishments |
|---|---:|---:|---:|
| One longer-lived child | 7,695 | 23,055 | 1 / 1 |
| Four briefly established children, one parent | 60 | 15,420 | 1 / 4 |
| Four briefly established children, four parents | 60 | 61,500 | 4 / 4 |

All have terminal tier 1. The first now wins both comparisons, whereas v1
favored the higher counts. The extra sterile-parent occupancy in the third
fixture also cannot override better recent offspring persistence.

Other tests cover seed-only expiry, established recovery, death exactly at
confirmation, patch censoring, establishment followed by later collapse, and
fresh-generation seeds remaining unconfirmed. A seed germinating at the last
eligible sample still has a complete first-day follow-up. Successful recovery
during the tail changes terminal status but adds no main-window event credit.

## Results on the saved native histories

Both policies retain model `dc5e849d`, their original bank-8 configurations,
drainage off, selective maintenance, weather and patches. Baseline denotes
`neural-no-night-growth`; reserve denotes `energy-reserve-v1`. The mixed 256/512
capacities remain a diagnostic panel, not a selected training environment.

All worlds have established descendants at both main and follow-up horizons.
Thus terminal tier is 1 for both score versions in this panel. Every one of
the 64 seeds pending at day 190 expires during the follow-up; no such seed
germinates. New purchases account for the pending seeds at day 192. The real
traces exercise expiry accounting, but **seed-only recovery and its alternatives
are covered by synthetic tests**, not demonstrated by these native endings.

| Capacity / seed / schedule | Baseline renewal ticks | Reserve renewal ticks | Matched v1 winner | V2 winner |
|---|---:|---:|---|---|
| 256 / b61837dc / fresh-4 | 323,400 | 100,290 | Baseline | Baseline |
| 256 / b61837dc / fresh-1 | 214,095 | 330,360 | Reserve | Reserve |
| 512 / b61837dc / fresh-1 | 389,640 | 436,305 | Baseline | Reserve |
| 512 / c7f54e18 / fresh-1 | 152,040 | 194,970 | Reserve | Reserve |

The changed third condition illustrates the intended distinction: baseline has
14 establishments and seven renewing parents; reserve has seven establishments
and four renewing parents, but **more accumulated recent offspring life inside
the same window**. This does not imply longer eventual lifespans: birth timing,
death and patch exposure all affect the observation available within a window.

Reserve wins three of four pairs, but baseline's large fresh-4 advantage gives
it a narrow aggregate lead on summed renewal ticks, 1,079,175 versus 1,061,925.
The full aggregate keys are:

- Baseline: `(1, 4, 1079175, 3184365, 17, 28)`.
- Reserve: `(1, 4, 1061925, 3203775, 14, 24)`.

The first two fields are minimum and summed terminal tier, followed by the
remaining score components. Removing fresh-4 reverses the aggregate winner;
the other three leave-one-condition-out comparisons keep baseline first. This
is not a robust general policy ranking, and v2 was not tuned to make it one.

## Verification and reproduction

`sim/garden_lineage_persistence.py` supplies the scorer, validated cutoff
projection, fixed follow-up ledger, paired/aggregate comparisons, collector and
reviewer. The full v1 analysis is reproduced before new scores are computed.
Source/protocol snapshots and artifact hashes preserve the dirty working-tree
state; old bundles, code and reports remain unchanged.

All **97 CTests pass** across default / bank-8 / bank-16 (45 + 26 + 26), including
the new 28-case Python suite. Original fixture prefixes match exactly. A separate
sample-by-sample calculation also matches all eight native renewal-time totals.
Existing trainer smoke tests are regression checks, not a new training search.

Full reanalysis checks 198 original artifacts, 393,224 world/site checkpoints,
65,544 exact-attempt checkpoints, 12,386 seed lifetimes and 2,601,285 live resource
steps. The five-artifact v2 bundle snapshots 424 source files; its manifest
SHA-256 is `e1dc6bf30a6b6df27577d4ea1e55b31a53c13804d8075bb1a1feb8f10ada7b65`.
The [JSON export](lineage-persistence-summary.json) retains scored identities,
main and terminal states, pending-seed follow-up, all score versions and ranks.
Native pixels have not changed; the existing
[recruitment contact sheet](recruitment-sites.png) remains the visual reference.

```sh
python3 -W error sim/test_garden_lineage_persistence.py

# Requires the original local recruitment/attempts/descendant/v1 bundles.
# Choose a fresh output directory; collection never overwrites old artifacts.
docker compose run --rm firmware python3 sim/garden_lineage_persistence.py \
    --output artifacts/garden-lineage-persistence-new

docker compose run --rm firmware python3 sim/garden_lineage_persistence.py \
    --verify artifacts/garden-lineage-persistence-v2

python3 sim/garden_lineage_persistence.py \
    --verify artifacts/garden-lineage-persistence-v2 \
    --export artifacts/lineage-persistence-review.json
```

The protocol, report, JSON and synthetic tests are portable. Full native
reanalysis requires the ignored local bundles, which are not in a fresh checkout.

## What remains, and recommended next step

V2 fixes the targeted count-over-lifetime preference without adding a new
minimum-lifespan threshold or tunable weights. It still measures **summed
population-time**, not a guaranteed lifespan per child: more simultaneously
living descendants can genuinely contribute more. A small positive recent
renewal value still outranks arbitrarily greater sterile occupancy. Event-window
edges and terminal presence remain finite-horizon preferences, not a proof of
indefinite sustainability.

This is enough to propose a **small end-to-end learning-signal pilot**, keeping
v2 frozen. First choose one explicit host environment and fixed development
and separate review seeds; port the score with this Python implementation as
the exact reference. Use a tiny population and a few generations, preserve the
unchanged controller as a control, and save generation-zero/every-generation
models and deterministic screenshots. Check what optimization actually changes
before increasing compute or tuning ecology. Do not call these already inspected
worlds held-out validation or promote a controller from this score comparison.

No trainer integration, new model search, firmware change, commit or push was
performed in this bounded scoring revision.
