# The cap saves maintenance but strands unfinished flower shoots

All twelve capped seasonal flower founders exhaust their construction budget
without forming a flower. Eleven stop below flowering depth; one reaches that
depth but never finishes its shoot. The missing seeds are therefore not just
an inference from resource reserves or a crowded seed bank: **763 reproduction
visits have missing flowers as their only blocker**.

This completes the question raised by the [species audit](landing-species.md),
using the [fixed protocol](landing-founders-protocol.md). The same twelve
model/world pairs run with the existing off/32 construction arms through day
192. Founder traces cover every ecology step through day 64, and adult resource
accounts cover the first two days. All capped seasonal flower lifetimes fit
inside the trace window. Steady survivors remain right-censored at day 64;
their seed and lifetime ledgers still extend through day 192.

No model, growth policy, ecology, score or firmware default changes in this
investigation. Historical results and endpoint pixels remain exact.

## Where construction stops

These are the last observed living bodies of capped flower-species founders,
not averages over changing descendant populations:

| Climate | Founders | Nodes | Roots | Shoot nodes | Maximum stem depth | Flower nodes |
|---|---:|---:|---:|---:|---:|---:|
| Seasonal | 11 | 32 | 20 | 12 | 11 | 0 |
| Seasonal | 1 | 32 | 19 | 13 | 12 | 0 |
| Steady | 4 | 32 | 20 | 12 | 11 | 0 |
| Steady | 2 | 32 | 18 | 14 | 13 | 0 |
| Steady | 2 | 32 | 17 | 15 | 14 | 0 |
| Steady | 2 | 32 | 16 | 16 | 15 | 1 |

The initial shoot node has depth zero. Twelve shoot nodes reach depth 11,
below this species' flowering threshold of 12. Finishing that tip immediately
would still not make a flower. Conversely, reaching depth 12–14 is necessary
but insufficient: the tip must actually finish.

Across the twelve capped seasonal founders' 171,920 living reproduction visits,
no flower is immature, spent or ready: no flower exists at all. The actual
controller proposes allocating shoot EXTEND 170,396 times at the cap, and the
existing projection changes each to WAIT. Post-step bodies confirm that those
shoots remain unfinished. The one depth-12 exception is seasonal multi /35,
founder 1; it also has a still-active root tip and 14,213 projected root bids.

These are tip proposals before water eligibility and priority arbitration,
not 170,396 executed growth actions. Other reproduction blockers often overlap
with missing flowers. The 763 flower-only visits establish that resources,
cadence, light, stress and bank capacity would otherwise have permitted
reproduction at those particular visits; they do not predict the effects of
an untested rescue intervention.

All uncapped flower founders do form flowers. That alone is not success:
seven uncapped flower founders die in the first two days, as described below.

## Two successful capped founders finish the shoot first

The steady counterexamples demonstrate that a complete reproductive shoot can
fit within 32 nodes. They do not wait until the body reaches the cap to finish:

| Steady case / founder | First flower tick | Body when the shoot finishes | First seed tick | Seeds through day 64 / 192 |
|---|---:|---|---:|---:|
| Multi /33, founder 5 | 735 | 27 nodes: 11 roots + 16 shoot | 780 | 8 / 24 |
| Multi /35, founder 1 | 435 | 18 nodes: 2 roots + 16 shoot | 600 | 4 / 12 |

Both shoots reach maximum depth 15 and propose FINISH with priority 32767.
The resulting flower is ready immediately; later root growth fills the body
to 16 roots plus 16 shoot nodes. Thus the successful sequence is **finish a
reproductive shoot, then use the remaining root budget**, not bypass the cap.
The other eight capped steady flower founders form no flower by day 64.

This is a construction-order observation from two frozen cases, not evidence
that every species should receive a fixed 16/16 allocation.

## The cap also prevents observed early energy deaths

The first-two-day adult receipts identify 41 uncapped founder deaths across
the twelve worlds: seven flowers, 22 shrubs and twelve ground-cover plants.
Every death is energy-short without a concurrent water shortage. The capped
arms have no founder deaths in that window.

This replaces the earlier lifespan-only uncertainty with actual resource
receipts. It does not isolate construction spending from later maintenance
and competition, or establish resource causes outside the two-day window.
Removing the cap to restore flowering would discard this observed benefit.

## Next proposed experiment

Test reserving enough construction space for a reproductive shoot **within
the existing 32-node total**, compared with the current cap and uncapped
control. Budget-ineligible bids must participate correctly in selection:
projecting a high-priority root bid to WAIT can still starve a lower-priority
shoot bid. Preserve ordinary finishing semantics and resource charges.

Simply raising the cap to 33 crosses the maintenance boundary:
`ceil(nodes / 8)` rises from four to five energy units per maintenance debit.
It also would not guarantee that the newly available node goes to the shoot.
Forcing FINISH at 32 cannot rescue the eleven depth-11 seasonal founders.

The next test needs all twelve pairs and the unchanged renewal, species and
climate-retention checks. Restoring flowers would not by itself solve the
separate steady-world occupancy/recruitment stall. No reserve policy, forced
FINISH, pruning, retraining or device flash is implemented here.

Follow-up: the [completed reserved-shoot screen](landing-budget.md) restores
flowering and seed production in all 22 flower founders without early founder
deaths, but fails renewal retention. Seasonal late survivors fall 107 → 41 and
steady renewal remains stalled. The reservation therefore stays experimental.

## Reproduction and verification

`growth-replay --founder-trace NEW.jsonl --founder-start TICK --founder-stop TICK`
requires `--ledger` and positive, inclusive 15-tick-aligned bounds within the
run horizon. The observer records actual raw/projected proposals, authoritative
sequential reproduction visits, and living post-step bodies. It does not
evaluate another neural policy or consume an extra random draw.

The host-only step wrapper reuses the existing reproduction audit. World,
cache and audit outputs retain rollback on failure; the caller discards any
partial callback buffer. Trace records are published only after a successful
step. Ordinary replay identities and device behavior are unchanged.

All 24 arms match their archived initial/final results and framebuffer bytes,
an untraced replay, and a repeated traced replay. Both raw trace streams repeat
byte-for-byte. The [portable receipts](landing-founders-results.json.gz) retain
393,216 founder-step rows and 43,426 early adult plant samples, with summaries
that recompute from those records. Offline verification also recomputes all
24 unchanged score histories. Every one of the full bundle's 181 artifact
hashes verifies.

```sh
make host-trace-landing-founders \
  GARDEN_LANDING_FOUNDERS_OUT=artifacts/new-founder-trace
docker compose run --rm -T firmware python3 -W error sim/garden_landing_founders.py \
  --verify benchmarks/garden-seasons/landing-founders-results.json.gz
# Also verify every retained file in the local full bundle:
docker compose run --rm -T firmware python3 -W error sim/garden_landing_founders.py \
  --verify artifacts/garden-landing-founders-v1
```

The fresh, ignored bundle preserves the executable, model bytes, build settings,
protocol, source snapshot, raw traces, endpoint frames and artifact inventory.
Outputs are no-clobber; verification is read-only.

All **157 ordinary host CTests pass** under UBSan (180.97 seconds). Native
coverage checks trace-on/off world and audit parity, unchanged decisions,
purchase counts and complete rollback after callback failure. Five Python
tests cover replay/pixel repeats, clipped windows and death boundaries,
corrupt receipts, argument/file safety, and recomputation of the frozen panel
with explicit regression checks for the construction and early-death findings.
Changed-C formatting, `git diff --check`, and Make help/dry-run checks pass.
The local test log is `artifacts/garden-founders-validation.log`.

- Frozen construction input SHA-256:
  `9027651cd3da4d8a9a8703ef7a78d4ecc351faef35ece5fe4f2ee43f5605d2da`.
- Portable founder result SHA-256:
  `1641f0cb96d3df0753cb3187f522f408ca9887dba23f88e1e4c4bb01671f0d70`.
- Full bundle manifest SHA-256:
  `3930a01b0bb312d3bd20dfa19dca7d341750eeb90c8fb744ea3552f4455bef81`.
- Frozen host binary SHA-256:
  `9fffaedf7000c0bfec044416d781bf4a1e68de1177036a52dc3b7364f081b23b`.

This is a reused exploratory panel, not unseen validation or qualification of
a new controller. No device has been flashed or measured.
