# Fewer blockers help one repair variant and hurt two

Preferring fewer current spacing blockers rescues the shrub family under both
restored repair gates on weather seed `9a903368`, but reduces renewal under the
light-only and condition-only variants. The rule is useful as a controlled
placement experiment, not a general replacement for the existing fallback.

Sixteen replays test four repair variants with original versus fewer-blocker
placement and logging off/on through day 608. Only founder 2 and its descendants
receive the placement change, and only when every reachable destination is
spacing-blocked. Clear-site selection, costs, seed lifetime, growth, repair
models, weather, and firmware defaults remain unchanged. The
[protocol](leaf-population-fallback-protocol.md) fixes the rule and budget.

## Renewal and survival

Each entry shows **original → fewer blockers**. Renewal credits count actual
children of non-founder parents when both survive their own 32 days, capped at
two per 64-day window over `(192,576]`, with follow-up through day 608.

| Repair variant | Renewal credits out of 12 | Established offspring by 608 | Living shrubs at 608 | Living flowers shrubs ground cover at 608 |
|---|---:|---:|---:|---|
| Unchanged | 0 → 0 | 0 → 0 | 0 → 0 | 8/0/0 → 8/0/0 |
| Light | 8 → 4 | 10 → 8 | 4 → 5 | 4/4/0 → 2/5/1 |
| Condition | 4 → 0 | 8 → 2 | 2 → 0 | 2/2/4 → 3/0/5 |
| Both | 0 → 6 | 0 → 12 | 0 → 3 | 4/0/4 → 3/3/2 |

The uncapped qualifying-child counts in the six successive windows are:

| Repair variant | Original | Fewer blockers |
|---|---|---|
| Unchanged | 0, 0, 0, 0, 0, 0 | 0, 0, 0, 0, 0, 0 |
| Light | 2, 1, 1, 2, 1, 1 | 1, 0, 0, 0, 2, 1 |
| Condition | 2, 0, 1, 0, 1, 0 | 0, 0, 0, 0, 0, 0 |
| Both | 0, 0, 0, 0, 0, 0 | 0, 0, 1, 3, 2, 1 |

These are eight trajectories on one selected weather seed, not sixteen
independent ecological trials. Logging repeats test instrumentation parity.
The unchanged-repair arm retains identical underlying state, histories, and
pixels at all eleven checkpoints; only the explicit placement identity differs.

## What changed at the early handoff

With both gates, the day-34 purchase moves from column 6, blocked by two plants,
to column 20, blocked by one. The purchase-time rosters and original draw are
identical. The original seed expires at day 66. The relocated seed germinates
at day 56.86328125 as shrub 15 and survives until day 190.8125, well beyond
establishment. Later descendants reach generation five, and all three founder
families remain alive at day 608.

The condition-only arm exposes the weakness of counting blockers. Its
day-31.078125 purchase moves from column 15, blocked by founder 2 and ground-cover
11, to column 14, blocked only by founder 2. **Both seeds germinate at exactly
day 63.015625.** Removing the extra blocker provides no earlier opening in this
case. Both resulting shrubs establish, but the changed trajectory eventually
loses its last shrub at day 232.21875 with a water-shortage death flag. The
original trajectory retains two shrubs and earns four late renewal credits.
This establishes a placement-policy regression; the specific later resource
and reproduction mechanism still needs diagnosis.

Light-only moves its day-34 seed from column 8 to column 18. The relocated seed
germinates at day 56.8671875 and its child remains alive through day 608. The
older seed at column 19, which germinates successfully under original placement,
instead expires in the changed world. The family retains more living shrubs
but earns fewer renewal credits, with no qualifying births in three middle
windows. Ground cover survives in this arm instead of disappearing.

Together these cases show why germination, occupancy, family renewal, and
competitor survival must remain separate measurements. Fewer blockers can
change the replacement route without improving sustained renewal. Later seeds
and neighbors experience the changed world too; this is not an isolated seed
relocation with all subsequent events held constant.

## Verification and retained evidence

All sixteen native calls passed in 103.953141 seconds with two workers. All
eight original-policy controls match the previous
[purchase comparison](leaf-population-purchases.md) byte-for-byte, including
88 JSON/raw checkpoints, final outputs, and resource/purchase traces. Each
new-policy logging pair also matches exact state, history, and pixels. The
validators reconcile every purchase in the fixed `[30,35)` window and independently
recalculate the chosen blocker minimum and cyclic tie break.

The seven host suites passed in 139.04 seconds, followed by ten preparation
tests. Native checks cover active six/fourteen-choice support, reflected aliases,
dead blockers, stable family ancestry, error rollback, output preservation,
reset, and no per-step allocation. The authenticated runtime remains untouched;
the source adapters pass a separate placement-policy parameter through copies
of the frozen wrappers. Placement is not activated by an observer.

The evidence archive (`leaf-population-fallback-results.json.gz`, kept locally)
is 1,297,032 bytes and includes all 176 captures, complete histories, traces,
source snapshots, and preflight receipts. SHA-256:
`61381e2a5d72106e54212c78715718b1aef289bb91375518db204e6dfe5418ce`. All sixteen
experimental calls succeeded on their first attempt.

```sh
python3 -B sim/experiments/leaf_population/population_fallback.py unpack \
  benchmarks/garden-seasons/leaf-population-fallback-results.json.gz \
  artifacts/new-fallback-evidence
```

Offline verification does not execute archived code. New-policy captures keep
the `TBF1` placement identity outside the existing repair identity; comparison
projections are never published as original-policy results.
All 98 analysis tests pass in 52.294 seconds, including exact archive
round-tripping and the saved positive and negative outcomes. Formatter checks,
whitespace checks, and all 43 local links in the updated guides and reports pass.

## Next investigation

The [offline regression diagnosis](leaf-population-fallback-loss.md) now traces
that loss without new simulations. The first two shrubs live longer and buy
more seeds, but the next-generation child dies before establishing. Eight of
nine later expired seeds stay spacing-blocked throughout their checked lives;
three are blocked by the shrubs' own family. The bank is congested, but saved
histories cannot establish eligibility and visit order when slots open.

Keep the fallback opt-in. Next, collect bounded read-only reproduction receipts
around those openings before changing placement again or expanding the panel.
