# Extra seed costs refill before the later water failures

The extra seed purchases **do not leave a persistent water inventory deficit**
in the two selected failures. Both candidates refill to their 512-unit capacity
within half a garden day. Both pairs are full again much later, before the
terminal dry-down, with no subsequent growth or seed spending. After that
shared starting point, candidates retain **40 and 23 fewer water units** than
their controls.

This narrows the [population audit](landing-root-allocation-audit.md): its
lifetime balances are correct, but an extra lifetime seed payment is not
evidence that its unreplenished cost caused the later death. The next useful
measurement is local water supply during dry-down, not another seed reserve
rule based on these two examples.

The [fixed protocol](landing-seed-spending-audit-protocol.md) covers daylight
plant 16 and dawn plant 17 under both reproduction orders, in both allocation
arms. All are born at 590640. Every reproduction visit from birth through
the earlier paired death is retained, including refusals and other plants'
bank arbitration. This is saved-data analysis with **zero new simulations**,
no training, no firmware flash and no policy/default changes.

## Why the candidates buy an extra seed

At both additional purchases, the controls have enough resources, an available
flower and all other gates open. They are refused **only because the seed bank
is full**. The candidates see free bank slots. Values below are immediately
before seed production; each successful purchase costs 48 energy and 24 water.

| Selected history | Purchase tick | Control bank → candidate bank | Control water → candidate water | Water requirement | Control energy → candidate energy | Energy requirement |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Daylight plant 16 | 594660 | 8 → 7 | 498 → 489 | 144 | 208 → 208 | 208 |
| Dawn plant 17 | 594780 | 8 → 5 | 498 → 492 | 104 | 235 → 229 | 208 |

These purchases precede the late reproduction-order change, so their histories
are shared by fixed and rotating worlds. They are two distinct selected events,
not four independent demonstrations. Every simultaneous blocker, non-cadence
visit, cooldown and refusal remains in the [portable results](landing-seed-spending-audit-results.json.gz).

## The costs are replenished

| Selected history | Water after extra purchase | First return to pre-purchase store | First full post-uptake store | Time to full in garden days |
| --- | ---: | ---: | ---: | ---: |
| Daylight plant 16 | 465 | 596460 | 596520 | 0.484375 |
| Dawn plant 17 | 468 | 596445 | 596520 | 0.453125 |

Every other seed purchase in these common windows also refills to capacity.
Both extra seeds eventually expire, at 717540/717660 respectively, without a
child. That does not make them ecologically inert: occupying a bank slot can
still affect other plants' production and later recruitment.

The complete purchase histories also contain a useful difference between
orders. Fixed daylight control/candidate plants produce two/three seeds,
including a purchase by both at 621600. Rotating daylight produces one/two,
without that later purchase. Both orders nevertheless have identical terminal
water accounts after the shared refill below. Dawn produces one/two seeds in
either order. No unfavorable history is omitted.

Earlier seeds have different outcomes too. Daylight's first candidate seed
germinates at 591360 while its control counterpart expires. Dawn's first
control seed germinates at 591300; the corresponding candidate seed germinates
at 705840, after its parent has died. Those children all pass one-day survival
where germination occurs. They are not the extra seeds audited above.

## Later water budgets from equal stores

The anchor is the **last sample before either arm's first water shortage when
both have 512 water immediately after uptake**. Accounting starts at that exact
stage: exclude the uptake already completed, but include that step's maintenance
and all later transfers. This avoids double-counting the anchor's income or
dropping its bill.

| Water account from shared saturation | Daylight control | Daylight candidate | Dawn control | Dawn candidate |
| --- | ---: | ---: | ---: | ---: |
| Anchor tick | 626580 | 626580 | 626520 | 626520 |
| Common endpoint | 639480 | 639480 | 644700 | 644700 |
| Initial water | 512 | 512 | 512 | 512 |
| Subsequent gross income | 159 | 113 | 162 | 80 |
| Overflow | 6 | 0 | 59 | 0 |
| Retained income | 153 | 113 | 103 | 80 |
| Growth and reproduction | 0 | 0 | 0 | 0 |
| Paid upkeep | 648 | 625 | 608 | 592 |
| Unpaid upkeep | 0 | 23 | 0 | 16 |
| Closing water | 17 | 0 | 7 | 0 |

There is no terminal water discard. Daylight's 40-unit retained-income loss
accounts exactly for 23 more unpaid upkeep units and 17 fewer stored units.
Dawn's 23-unit loss accounts for 16 more unpaid units and seven fewer stored
units. The resource deficit develops **after** both earlier seed costs have
been replenished. Both reproduction orders give these same water balances.

Candidate water income stops at 629505 for daylight and 629460 for dawn;
controls receive their last water at 629655/629610. All four have stopped
receiving water by the recorded drought transition at 629760. Candidate
shortages begin much later, at 639060/644280. Their controls have no water
shortages through these common endpoints; this is not a claim that the
controls survive the entire drought.

## What this does and does not establish

The direct explanation “those extra 24 water units remained missing until
death” is contradicted by actual refilling and the later equal-store accounts.
Adding a seed reserve solely to protect those old debits is not supported by
this audit. Total lifetime income and spending obscure the timing of storage
saturation and later scarcity.

This is **not** a skip-seed counterfactual. Reproduction can change bank
occupancy, offspring, soil consumption and the wider population even after
the parent's stores refill. The evidence does not prove that suppressing a
seed would leave later uptake unchanged, nor identify which roots or soil
cells cause the observed income difference. All four original population
harm screens remain failed; no rule is promoted.

## Verification and commands

All 16 complete stand-stream hashes and exact repeats are checked. Eight
unique arm streams supply **27448 selected ecology records**. The tool checks
complete window coverage, traversal order, bank occupancy against the original
seed ledger, all production blockers, flower inventory, target debits and the
pinned resource histories. It recomputes refills and both resource accounts
from the exact post-uptake anchor.

All **15 new tests pass**, along with the preceding audit's 14 tests through
their two CTest entries. Raw re-extraction and portable verification pass;
two independent exports are byte-identical. The original protocols and
results retain their hashes. No C or firmware code changed, and the native
simulation suite was not rerun during this offline task.

```sh
make host-audit-landing-seed-spending  # Requires a fresh output file
docker compose run --rm -T firmware python3 sim/garden_landing_seed_spending_audit.py \
  --verify benchmarks/garden-seasons/landing-seed-spending-audit-results.json.gz
docker compose run --rm -T firmware python3 sim/garden_landing_seed_spending_audit.py \
  --verify benchmarks/garden-seasons/landing-seed-spending-audit-results.json.gz \
  --bundle artifacts/garden-landing-root-allocation-v1
```

Use `GARDEN_LANDING_SEED_SPENDING_AUDIT_OUT` for a new export path. The Make
target has no build dependency. Portable verification needs the pinned original
allocation result and common-window audit from this repo; raw verification also
needs the local allocation capture. The new portable file is about 960 KiB.

| Artifact | SHA-256 |
| --- | --- |
| Seed spending audit | `2a1de1c9c6a2574a6e47d9bd7bb787038a87a4e19a0af4f5e8b6268e3736baef` |
| Audit protocol | `9770b5be42ac6e7d8e7d5e2858b6239d1b4dca4914e6e9aeec9c64cd32289769` |
| Selected reproduction receipts | `5e3ddbf14dc46c127f123d3adc5eb9192b9d8623450c305f3bf4c323637ad55e` |

## Proposed next measurement

Use the existing passive per-root uptake observer over **626520 through
629760**, covering both shared-capacity anchors and the final positive-income
samples. Compare the same four baseline pairs, keeping policies fixed. Record
root locations, soil moisture before/after uptake, uptake limits, consumer order
and overflow to separate already-dry cells from within-step competition and
differences in which cells each body reaches.

The allocation bundle contains stand, adult and direction traces, not those
per-root uptake records. This next measurement therefore requires new passive
replays and a separately frozen capture plan. Require ordinary results, traces
and pixels to match the saved worlds to establish observer neutrality. No new
reserve rule or causal suppression experiment is proposed yet.

The [completed passive capture](landing-drydown.md) now records that window.
All sixteen replays are historically neutral. Both pairs have identical root
endpoints, with no foreign-root visits to those cells; lower local water supply
accounts for the terminal income loss. The remaining question is how the soil
update and surrounding reservoirs produce that lower supply, not an
unreplenished seed debit.
