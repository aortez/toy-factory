# Seed bank residence and rare allocation openings

The [recovery trace](landing-recovery-gates.md) found five flowering replacements
that never bought seeds. This offline audit separates their **3,394 bank-only
blocks into 3,378 checks that begin full and 16 where an earlier parent takes
the available slot**. Every focal plant misses at least one real opening,
but changing visit order cannot create capacity on the other checks.

Long residence is not simply waste. Of the 73 seeds occupying the bank during
those five replacement lifetimes, 49 eventually expire and 24 germinate.
Twenty-three germinate after their parents die, and **19 of those children
survive their first day**. Twenty of the 24 germinating seeds wait at least
16 days. A fair-access experiment is worth testing; shortening viability or
evicting old seeds is not justified by occupancy alone.

The [protocol](landing-bank-access-protocol.md) fixes all six model pairs,
the existing observation window and the original five focal identities.
Single /33, with no established early replacement, remains in the full panel.
No native simulation, training, ecological change or device write was needed.

## Where the five plants lose access

Each count below has a ready flower, sufficient resources, zero stress and
cooldown, daylight and the correct maintenance cadence. Bank capacity is the
only failed production gate.

| Vacancy world / lineage | Full at entry | Earlier buyer takes space | Actual purchases |
| --- | ---: | ---: | ---: |
| Multi /33, 28 | 749 | 3 | 0 |
| Single /34, 26 | 562 | 2 | 0 |
| Multi /34, 25 | 857 | 4 | 0 |
| Single /35, 40 | 460 | 1 | 0 |
| Multi /35, 29 | 750 | 6 | 0 |
| Total | 3,378 | 16 | 0 |

Those 16 ordering losses are 0.47% of the bank-only checks. In every case,
the bank begins production with seven seeds and one earlier incumbent buys
before the replacement's turn. Fifteen openings come from a seed expiring
on that same step. One is carried from an earlier germination:

- At tick 656,955, a seed from Multi /35 parent 24 germinates, leaving seven
  banked seeds. Nobody buys on that step.
- At tick 657,000, parent 21 buys the open slot before lineage 29, which
  otherwise passes every gate. There is no seed release on this purchase step.

This distinction matters: the final bank count is eight in both cases, but
neither is equivalent to entering the production loop with an already-full
bank. The portable result retains all 16 ordered receipts, earlier buyer IDs
and same-step releases, including the empty release list in the carried case.

These are repeated observed checks, not independent chances or a forecast
of 16 extra seeds. Changing one purchase changes future bank residence,
resource spending and descendants. Only a paired experiment can establish
the later effect.

## Incumbents occupy nearly all available capacity

Across the five focal lifetimes there are 347,544 available post-step
slot-samples, of which **347,498 are occupied and only 46 are empty**: 99.987%
occupancy. Every resident seed belongs to a plant already present at day 158.
The replacements and other newer plants own none of this stock.

| Focal world | Resident seeds | Distinct owners | Largest owner's occupied share | Eventually expire / germinate |
| --- | ---: | ---: | ---: | ---: |
| Multi /33 | 17 | 2 | Parent 20, 52.87% | 13 / 4 |
| Single /34 | 13 | 4 | Parent 21, 49.55% | 8 / 5 |
| Multi /34 | 16 | 4 | Parent 19, 50.00% | 10 / 6 |
| Single /35 | 10 | 2 | Parent 25, 87.50% | 7 / 3 |
| Multi /35 | 17 | 4 | Parent 21, 71.50% | 11 / 6 |

These are distinct seed episodes overlapping each focal life, not the number
of simultaneous slots. Shares use occupied sample time, not seed counts.
One slot-day is 256 occupied post-step samples; the audit clips every seed
to the declared window rather than charging its entire lifetime.

Seeds that eventually expire consume 222,637 of the 347,498 occupied samples
(64.07%). Seeds that eventually germinate consume the remaining 124,861.
Seeds aged 16–under 32 days account for 177,399 occupied samples (51.05%).
Four resident seeds belong to explicitly exported parents; all four expire.
Their 12,706 occupied samples are labeled export, not natural parental death.

## Retained seeds bridge the parental death wave

Of the 24 eventual germinations among seeds present during the focal lifetimes:

- 23 occur after natural parental death: 19 children establish and four die
  in their first day.
- One occurs while its parent is alive; that child dies in its first day.
- None occurs after an explicit parent export.

Twenty germinating seeds are at least 16 days old, and 16 of those children
establish. The oldest successful wait is 31.75 days. These observed recruits
depend on seeds retained long enough to reach a later opening. This does not
predict the complete counterfactual effect of a shorter viability rule; it
does identify useful old seeds that such a rule would discard.

The full twelve-arm audit reaches the same distinction without dropping the
negative world. Its stock cohort consists of every seed occupying a post-step
sample in (158,218], with outcomes followed through day 256:

| All six models | Control | Vacancy |
| --- | ---: | ---: |
| Resident seed episodes | 185 | 210 |
| Expire / germinate / unresolved | 101 / 84 / 0 | 98 / 112 / 0 |
| Germinate after natural parent death | 42 | 44 |
| Of those, first-day survivors | 34 | 40 |
| Germinate while parent lives | 42 | 68 |
| Of those, first-day survivors | 25 | 31 |
| Germinate after explicit export | 0 | 0 |
| Occupied / available slot-samples | 728,124 / 737,280 | 728,835 / 737,280 |

This is a resident-seed cohort, **not every birth through day 256** and not a
new fitness score. Seeds purchased after the trace window are excluded; exits
of observed seeds after day 218 are included in their eventual outcomes.
No resident seed remains unresolved because the 32-day viability horizon
ends before the day-256 follow-up. Six models sharing one weather seed are
still not independent environmental replication.

## Proposed next experiment

Test deterministic rotating production order as one isolated host-only change,
keeping eight slots, 32-day viability, resource fees, placement, weather and
models unchanged. Include both the unchanged-control and vacancy trajectories
for all six models, with a common prefix before the switch. Do not evict seeds,
refund costs or favor a named lineage.

The question is whether distributing rare openings permits the new plants to
reproduce **and produce established offspring**, without harming survival or
later renewal elsewhere. More purchases alone are insufficient. The older
[rotating-order result](../garden-longevity/renewal-seed-order.md) improved access
without establishment, so the current panel needs its own test. A stateless
rotation can also alias with reproduction timing; verify actual visit ranks
and slot access rather than assuming fairness from the algorithm's name.

The subsequent [bounded comparison](landing-order.md) now tests this proposal.
It produces established children from four early replacement parents, but also
retains regressed worlds and missed openings under rotation. This audit itself
remains read-only; no allocation, capacity or seed-lifetime rule is promoted.

## Reproduction and evidence

- [Portable audit](landing-bank-access-results.json.gz), SHA-256
  `fdfb3b5a9f070d03f73d06255a17d87c3bdc9b24fd63783d432878661a81870b`.
- [Exact ordered visit excerpt](landing-bank-access-visits.json.gz), SHA-256
  `b59d9dd4dd2cd01cb0de93df28605f6eb6b7f49c7972bf6ab2834a5ee870ee1b`.
- Protocol SHA-256
  `fcebc44499faa866871f8e2b4ada8020a7f6b2d13a699c922d011ad2222009fa`.
  The input and original local-bundle manifest identities are pinned in the
  protocol and extractor. Earlier evidence is unchanged.
- All 184,320 ordered-step records and 884,878 living visits reconcile with
  frozen summaries. Bank conservation and an independent sampled-residence
  calculation agree. The excerpt was separately re-extracted from all twelve
  original traces and compared exactly, with no simulation.
- Boundary tests cover release/refill order, carried openings, expiry and
  age boundaries, posthumous versus post-export recruitment, first-day death,
  censored follow-up, corrupt clocks/visits/gates and no-clobber outputs.
- All 11 new offline audit tests pass, as does the complete 168-suite host
  regression run. The portable audit also reproduces exactly from saved inputs.

`make host-audit-landing-bank-access` uses portable inputs, without a native
build. Choose a fresh `GARDEN_LANDING_BANK_ACCESS_OUT`. To verify offline:

```sh
docker compose run --rm -T firmware python3 sim/garden_landing_bank_access.py \
  --verify benchmarks/garden-seasons/landing-bank-access-results.json.gz

# Optional: compare the excerpt against the original saved local traces.
docker compose run --rm -T firmware python3 sim/garden_landing_bank_access.py \
  --extract-from artifacts/garden-landing-recovery-gates-v1 \
  --verify benchmarks/garden-seasons/landing-bank-access-visits.json.gz
```
