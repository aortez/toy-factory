# Identical roots receive less local water during drying

The two matched failures have **identical root endpoints and uptake limits**
in their allocation control and candidate worlds. No other plant visits those
cells during the measured window. Each target empties every occupied cell on
every observed step, yet the candidate has less opening soil water and receives
less replenishment between steps. After storage overflow, these differences
account exactly for its later **40 or 23 fewer retained water units**.

The [previous audit](landing-seed-spending-audit.md) ruled out an unreplenished
seed debit. This capture further rules out different endpoint coverage or
direct same-cell competition **during this window**. It does not rule out
competition elsewhere in the soil or earlier in the plants' lives.

## Exact replay and scope

The [frozen protocol](landing-drydown-protocol.md) is complete: sixteen full
replays, four baseline cases × two allocation arms × two repeats. All ordinary
results, complete stand/adult/direction traces and final raw pixels match the
archived observer-off allocation runs. Both observed repeats also have
identical uptake traces. The original executable was copied and reused, not
rebuilt; its original source archive is retained separately from the new
Python capture tool's source snapshot.

Each primary arm contains all 217 ecology observations from 626520 through
629760, plus the preceding adult sample for root-coverage checks. Across eight
primary captures, the verifier reconstructs **1736 world steps, 180978 root
visits and 108934 leaf incomes**, including soil and light fields. The fixed
and rotating cases have identical uptake observations for each corresponding
arm: these are two selected paired histories, not four independent findings.

No policy, controller, environment, firmware or device default changed. The
original population harm screens still fail. There were no training runs or
additional full simulations outside the sixteen-call plan.

## Same roots and different supply

Daylight plant 16 has 15 root nodes visiting nine cells; dawn plant 17 has
16 roots visiting eleven. The root-node identifiers differ between allocation
arms, but the ordered endpoints, multiplicities and three-unit uptake limits
are identical. Neither target changes its root layout during capture.

At most **two water units** are present in any target cell before uptake.
One three-unit root could already collect all of them. Additional roots in
that same cell cannot increase this window's collection. The observer records
competition between the plant's own roots, but that is duplicated demand on
the same water, not water lost to a different plant or an additive recovery
opportunity.

The terminal account starts immediately **after** both plants' last shared
512-unit post-uptake store: tick 626580 for daylight, 626520 for dawn. Thus
the first counted root visits are 626595/626535, respectively. All subsequent
income through the common death endpoint occurs inside the captured window.

| Post-anchor account | Daylight control | Daylight candidate | Dawn control | Dawn candidate |
| --- | ---: | ---: | ---: | ---: |
| Opening water in occupied cells at first counted uptake | 2 | 0 | 3 | 0 |
| Net replenishment between later uptake steps | 157 | 113 | 159 | 80 |
| Root collection | 159 | 113 | 162 | 80 |
| Closing soil water in occupied cells | 0 | 0 | 0 | 0 |
| Plant storage overflow | 6 | 0 | 59 | 0 |
| Retained income | 153 | 113 | 103 | 80 |
| Last positive income tick | 629655 | 629505 | 629610 | 629460 |

Here replenishment means the **measured net change** from one post-uptake
soil grid to the next pre-uptake grid. It is not a measurement of rainfall or
diffusion separately. Opening soil water plus that net change equals collected
water exactly; all occupied cells finish empty. Both candidates stop receiving
water ten ecology steps before their controls.

The whole-grid moisture total is insufficient to explain this. At the first
observed dawn sample, the candidate world actually contains **2114** soil water
units versus **2043** in control, while the candidate's own root cells are all
dry. Water somewhere in the world is not necessarily accessible to that body.

## Where retained income changes

Coordinates are zero-based soil column and row. These tables include every
occupied cell, including zeros and the one small improvement. Candidate
overflow is zero throughout the post-anchor interval.

| Daylight cell | Control collected | Control overflow | Candidate collected | Retained change |
| --- | ---: | ---: | ---: | ---: |
| 1 0 | 37 | 1 | 33 | -3 |
| 1 1 | 36 | 0 | 31 | -5 |
| 1 2 | 10 | 0 | 10 | 0 |
| 2 2 | 51 | 3 | 30 | -18 |
| 1 3 | 0 | 0 | 0 | 0 |
| 2 3 | 15 | 2 | 9 | -4 |
| 2 4 | 8 | 0 | 0 | -8 |
| 2 5 | 2 | 0 | 0 | -2 |
| 2 6 | 0 | 0 | 0 | 0 |
| Total | 159 | 6 | 113 | -40 |

| Dawn cell | Control collected | Control overflow | Candidate collected | Retained change |
| --- | ---: | ---: | ---: | ---: |
| 13 0 | 38 | 6 | 31 | -1 |
| 13 1 | 43 | 13 | 20 | -10 |
| 13 2 | 16 | 8 | 9 | +1 |
| 14 2 | 36 | 16 | 20 | 0 |
| 13 3 | 12 | 7 | 0 | -5 |
| 14 3 | 10 | 4 | 0 | -6 |
| 13 4 | 4 | 3 | 0 | -1 |
| 14 4 | 3 | 2 | 0 | -1 |
| 13 5 | 0 | 0 | 0 | 0 |
| 13 6 | 0 | 0 | 0 | 0 |
| 13 7 | 0 | 0 | 0 | 0 |
| Total | 162 | 59 | 80 | -23 |

These retained-income changes reconcile the previous terminal deficits after
shared saturation. Gross loss alone would overstate the effective loss,
especially in dawn control where 59 collected units overflow storage.

## Limits and next question

We have located the immediate difference in **local soil supply**, not root
capacity, root positioning or a rival consuming the same cell first. Simply
adding more uptake capacity to these existing endpoints would collect no
additional water in the observed steps. This does not test placing roots in
other cells, changing storage, or changing the earlier world history.

The other plants and surrounding soil differ between arms. Nearby roots can
affect reservoirs without sharing the target's exact cells, and prior uptake
can affect today's supply. Zero foreign-root overlap is not proof of zero
ecological competition. The current before/after snapshots combine transport,
rain and other between-step processes; they do not allocate the missing
replenishment to a particular cause.

The [completed offline soil audit](landing-soil-audit.md) reconstructs that
update exactly from the saved grids and archived implementation, without new
native calls. Equal rain and reduced lateral inflow account for most of the
gross difference, while deep water remains below these roots without upward
transport. The next question is whether earlier legal root choices could
reach that reservoir within the existing body budget, before proposing a
mechanics change. Do not add another reserve rule or expand training on the
strength of these selected examples.

## Reproduction and verification

The runner preserves complete original traces for all sixteen calls. Portable
results retain every selected world observation and adult receipt, plus all
308 cells' signed water balances and per-consumer uptake totals. Raw-bundle
verification rehashes every artifact and reextracts observations; portable
verification independently recomputes attribution against the pinned earlier
resource histories. Both modes pass and run no native simulations.

All **14 new tests** pass, along with the existing uptake observer, allocation
audit and seed spending audit: **four CTest entries, 56 Python cases** in total.
Checks include missing/changed observations, root coverage, soil conservation,
historical result/trace/pixel tampering, no-clobber output, offline verification,
identical endpoint coverage and fixed/rotating duplicate observations. No C
source changed; this was targeted regression testing, not a rerun of the full
native suite. The archived executable and all three pinned inputs retain their
original hashes.

```sh
make host-trace-landing-drydown  # Fresh output required; uses the archived binary
docker compose run --rm -T firmware python3 sim/garden_landing_drydown.py \
  --verify benchmarks/garden-seasons/landing-drydown-results.json.gz
docker compose run --rm -T firmware python3 sim/garden_landing_drydown.py \
  --verify artifacts/garden-landing-drydown-v1
```

Set `GARDEN_LANDING_DRYDOWN_OUT` to a new capture directory. The Make target has
no build dependency and requires the original allocation bundle, selected with
`GARDEN_LANDING_ROOT_ALLOCATION_OUT`. It refuses to overwrite or resume a bundle.
The portable [results](landing-drydown-results.json.gz) are about 902 KiB; the
local full capture is about 19 GiB. Final pixels match the existing
[allocation gallery](frames/landing-root-allocation.png); these are day-256
endpoints, not new images of the drying interval.

| Artifact | SHA-256 |
| --- | --- |
| Portable results | `2107de1ed88bef2ef66d8b168f4fd8d3338329b02c8dc8aff5b919aa487a6a29` |
| Frozen protocol | `882f7cc411b6e30b3f3a55a6b5f0b0c9ace018e8142570301094f57e2b6b8888` |
| Raw manifest | `affb9fd1765e438bbfa4d7a73017a750654c4ccf5475c629d5c52f09aee48ee9` |
