# Confirm spatial dieback across new starting conditions

Freeze this panel before research calls. Test whether the renewal gain from the
[patch-sweep pilot](landing-patch-sweep.md) survives new world seeds and the two
existing rain-fed starting layouts. This is one bounded host confirmation,
not training, schedule optimization or qualification of ordinary ecology.

## Fixed recipe and evidence

Use W2, key `f7ee4528-fixed-candidate-control-wide-cap-trace`, unchanged. It is
the first recipe in the pilot's sorted panel without the historical named-plant
root-allocation selector. That selector matches lineage 9, its exact birth,
ancestry and site; silently treating it as a general rule in fresh worlds would
be misleading. W2 already omits it. Do not add wicking, rotate visits, disable
other guards, select a replacement plant or otherwise modify this recipe.

Use the captured `wide-cap` executable, build settings and model from
`artifacts/garden-landing-patch-sweep-v1`. The portable pilot result is pinned
by SHA-256 `dd5b43c954c9e82b51f1200819bdef6c9287c7e412bdf467964bb95bdd012f64`,
and its raw manifest by
`c48725b1cd3419f3cb9f74c8b3ed6c24dffb13a26a54ecba06d3f582e535caaf`.
Authenticate the selected executable, configuration and model against those
receipts; do not rebuild the simulation. Preserve all old sources and evidence.

The model, seasonal climate rules, node/plant/seed capacities, spending guards,
uptake cap, late dispersal, dormancy and viability remain fixed. The late
uptake/dispersal changes still start at tick 626580. No gardener or ongoing
irrigation. Both arms omit named deaths and paid seed replacement. W2's
experimental safeguards remain a limitation, not newly qualified defaults.

## Six paired cases

World seeds are the first eight hexadecimal digits of SHA-256 over the UTF-8
strings `toy-factory/landing-patch-confirmation-v1/world/N`, for N = 1, 2, 3.
They were generated before simulation, not chosen from successful outcomes:

| Seed label | N | World seed |
| --- | --- | --- |
| S1 | 1 | `3a7e45e6` |
| S2 | 2 | `366928c6` |
| S3 | 3 | `275c8982` |

For each seed, run `rainfed` then `rainfed-crowded`. The first starts with three
founders at columns 4, 13, 22 and 128 units of initial watering per founder.
The second starts with five at 3, 8, 13, 18, 23 and 96 units each. Both have
the existing species mixture. These are bundled starting-condition changes,
not an isolated spacing intervention. The shared seed initializes weather and
world randomness; this is not a weather-only A/B. Matched layouts share a seed
and must not be called six independent environmental replicates.

Control has no prescribed deaths. Treatment uses the unchanged fifteen-event
four-column sweep, days 192 through 304 every eight days, then ends on day 320.
All ages are eligible. Retain empty hits, bodies, normal decomposition and
seed-bank contents. Discard victims' stores without refunds. No rule, horizon,
seed, layout or event may be retuned after observing a case.

## Calls and validation

Exactly 26 research calls, at most two concurrently:

1. Replay the pilot W2 control and treatment at their original seed/layout.
   Both must reproduce results, frame bytes, all traces and resource accounts.
2. Run all six new controls, then all six treatments.
3. Run six exact treatment repeats and six observer-free treatments.

New calls preserve full birth/seed ledgers, reach traces, stand/adult traces
from day 192 through 320, all event receipts and fixed endpoint frames.
Observer-free calls retain ledgers but omit observational traces. Prefix
observations and pre-event ledgers must match within every new pair. Repeats
must match result/frame/trace bytes and accounting; observer-free results and
pixels must match their treatments. Unit tests are separate from the 26 calls.

Require fresh output paths and at least 14 GiB free before collection. Do not
delete older evidence to make room. Retain source snapshots, build/model hashes,
arguments, failures, raw observations and complete portable results. Stop on
execution, provenance, accounting or repeat failure. An already running peer
may finish, but no next batch, retry, replacement case or automatic resume is
authorized by this protocol.

Re-audit the complete raw bundle offline, with no native process launches.
Reproduce the portable compressed result and fixed twelve-frame gallery from
the stored evidence. Gallery rows follow S1/S2/S3, ordinary then crowded;
columns are control/treatment. Review every frame, including empty worlds.

## Measurements and decision

Keep the pilot's primary cohort: all plants born strictly after day 192.
A qualifying pair has a parent and child in that cohort, both confirmed alive
at sixteen days of age. Count actual parent links, not inherited generation
labels. Retain posthumous children and distinguish imposed deaths, natural
deaths and horizon censoring at one, sixteen and thirty-two days.

Report every pair separately, including births, qualifying pairs/parents,
deepest established ancestry, species coverage, seed purchases/fates, capacity,
slot-reclamation delay, young victims and minimum/endpoint living population.
Reconcile natural causes, maintenance shortfalls with exposure denominators,
and resource discards. Do not interpret reduced natural mortality as better
health without accounting for competing imposed deaths and changed lifetimes.

Confirmation passes only if qualifying-pair counts improve in at least two of
three seeds **within each layout**, no case loses qualifying pairs relative to
its control, and all six treatment endpoints retain living plants. An empty
control does not remove its pair from the panel. Report temporary empty periods
and other harms regardless of this narrow gate. No confidence or generality
claim follows from three seeds and one fixed model/recipe.

Finish with a report and recommendation, even if confirmation fails. No broader
search, rule promotion, neural interface change, fitness revision, device
flashing, commit, push or PR mutation is part of this experiment.
