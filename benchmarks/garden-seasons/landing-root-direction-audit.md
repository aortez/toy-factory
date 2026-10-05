# First day water and flowering after root redirection

The saved first-day receipts explain the early seed timing change in the
[failed wetter-root comparison](landing-root-direction.md). Redirected roots
initially collect extra water, but none of the five founders retains more
water over the full window. The earlier seed is enabled by an earlier ready
flower, **not by clearing a water or energy purchase gate**. Both arms produce
seven seeds during the window. Keep the direction preference experimental.

## Scope and accounting

The [audit protocol](landing-root-direction-audit-protocol.md) selects every
sample from logic tick 15 through 3840 inclusive: 256 ecology steps from
initialization, not a dawn-aligned day. The sun starts at phase 64. There are
five living founders throughout; no births or deaths occur in this window.

All four baseline worlds and both repeats have identical complete prefixes
within each root-direction arm. They provide **one distinct early A/B pair**,
not four independent trials. The portable result retains both full prefixes,
including resources, all bids/endpoints, reproduction visits and body summaries,
plus checksums for all sixteen source prefixes. It reconciles 2,560 plant
samples and 640 maintenance opportunities across the two distinct histories.
There are 30 rewritten bids and 18 changed root purchases in the candidate.

Uptake happens before maintenance, then growth, then reproduction. Thus a new
root can first contribute water on the following ecology step. Water removed
from soil can overflow the plant's 512-unit store; retained income is uptake
minus overflow, not the closing inventory. The captured world and reused
resource-accounting code are unchanged. No new simulation or training ran.

## Extra early uptake mostly becomes overflow

The first redirected root belongs to founder 5 at tick 315. Both arms pay
eight energy and five water, ending at 95 water. At tick 330, plant water
income is three in the old arm and six in the candidate, with zero overflow:
closing water becomes 98 versus 101. This confirms an immediate net resource
benefit, not just a wetter endpoint in an observation.

That benefit does not accumulate into more retained first-day water. Here are
the complete summed accounts for the same five founders and equal exposure.

| Water account | Old ordering | Wetter ordering | Change |
| --- | ---: | ---: | ---: |
| Opening stores | 160 | 160 | 0 |
| Uptake from soil | 6,615 | 6,702 | +87 |
| Storage overflow | 2,945 | 3,053 | +108 |
| Retained income | 3,670 | 3,649 | −21 |
| Maintenance paid | 638 | 637 | −1 |
| Construction and closures | 738 | 742 | +4 |
| Seed spending | 168 | 168 | 0 |
| Closing stores | 2,286 | 2,262 | −24 |

Per-founder changes in retained water are `−5, −4, −1, 0, −11`. None has an
unpaid water-maintenance unit in either arm. Candidate storage overflow starts
earlier for four founders; for example, founder 5 first overflows at 1290
instead of 1380. These accounts support a timing/saturation explanation, not
the claim that all redirected uptake is immediately wasted. They do not
identify individual root contributions: these runs lack per-root uptake traces.

Total energy income increases by 34; 28 overflows and six pays an extra shoot
closure by founder 3. Closing energy and seed spending are unchanged. Founder
4 still has nine unpaid energy units in both arms; no other founder has an
energy shortage during the window. The root preference does not rescue an
early shortage in this pair.

## The earlier seed comes from earlier flowering

Founder 3 first gets a redirected root at 375. Its water income at 390 rises
from eight to ten, both retained. Its first changed shoot purchase follows at
585, from the same tip `(118,106)`: old ordering chooses `(115,100)`, while the
candidate chooses `(118,99)`.

All five local shoot candidates have identical light, clearance and collision
flags across the pair at that decision. The difference is already in the raw
model ranking; the root hook does not rewrite it. Both purchases cost six
energy and four water. The model is responding to a changed history, but the
saved traces do not contain its full observation/recurrent state, so they cannot
isolate water input, root geometry or memory as the cause of that ranking.

| Event | Old ordering | Wetter ordering |
| --- | --- | --- |
| First changed shoot destination at 585 | `(115,100)` | `(118,99)` |
| First ready flower | Tick 855 | Tick 735 |
| Stores before reproduction at 780 | 243 energy, 192 water | 245 energy, 200 water |
| Required stores at 780 | 208 energy, 104 water | 208 energy, 104 water |
| Blocker at 780 | No ready flower, and nothing else | None |
| First seed purchase | Tick 900, column 8 | Tick 780, column 19 |
| Founder 3 seeds by tick 3840 | 3 | 3 |

The candidate's flower is ready at 735, but reproduction cadence delays the
purchase until 780. The old arm similarly waits from 855 until 900. At 780,
the old plant could already afford the seed and all its required reserves;
the missing flower is its sole blocker. Calling this a water-funded seed
rescue would misread the receipts.

Both first seeds later expire without germinating. Across the whole first-day
seed cohort, each arm produces seven seeds: six eventually expire and the
same founder-4 seed at tick 3540 produces matched offspring 6 at 30210.
Timing and placement have changed, but there is no additional successful
first-day recruit. This does not explain away, or causally attribute, the
later population regressions in the 256-day A/B.

## What this changes about the next experiment

Do not add another local-moisture preference yet. Immediate endpoint moisture
can improve a transfer while failing to improve retained income, reproduction
or survival. Even a root-only rule changes later shoot construction indirectly.

The next proposal should address **whole-plant root and shoot allocation**:
water income relative to shoot maintenance, and light income relative to total
maintenance, while preserving a path to a flower. The earlier mature-deficit
audit already identified a 32-node descendant with only three roots; choosing
a wetter direction does not solve that allocation problem. Define a bounded
comparison with unchanged prices, node limits and population checks before
implementing it. Canopy planning remains a separate energy constraint.

The subsequent [proposed root allocation protocol](landing-root-allocation-protocol.md)
defines that comparison: prioritize eligible roots when current water income
has no upkeep surplus and energy covers post-root upkeep. Test only matched
plant 9 first, keeping terminal closures and the existing guards intact. The
four-baseline, sixteen-call panel is designed but has not been implemented or
run. The wetter-direction preference stays disabled.

## Reproduction and verification

```sh
make host-audit-landing-root-direction
docker compose run --rm -T firmware python3 sim/garden_landing_root_direction_audit.py \
  --verify benchmarks/garden-seasons/landing-root-direction-audit-results.json.gz
docker compose run --rm -T firmware python3 sim/garden_landing_root_direction_audit.py \
  --verify benchmarks/garden-seasons/landing-root-direction-audit-results.json.gz \
  --bundle artifacts/garden-landing-root-direction-v1
```

The Make target has no native build/run dependency. Set
`GARDEN_LANDING_ROOT_DIRECTION_AUDIT_OUT` to a fresh output file and
`GARDEN_LANDING_ROOT_DIRECTION_OUT` to the original raw bundle. Export hashes
all 48 compressed input traces against the pinned manifest and result, then
parses only their first-day prefixes. This is not another full 256-day framing
verification; that was completed for the source A/B.

Portable verification checks pinned prefix hashes and recomputes all selected
resource balances, legal rankings, purchases, reproduction gates and summaries.
Raw verification also re-extracts and compares every prefix. Both pass. Two
exports are byte-identical. All twelve focused tests pass, including changed
income, missing/reordered samples, invalid seed gates, forbidden shoot rewrites,
false summaries and proof that portable verification starts no process. Physical
shoot comparisons ignore changes to global node indices and unused fallback
ordering; neither alone counts as changed growth.
The three offline CTest entries for this audit and the preceding population
and dawn audits also pass. The original A/B portable verifier still passes,
and the native executable remains byte-identical to its captured version.

| Artifact | SHA-256 |
| --- | --- |
| [Portable first-day receipts](landing-root-direction-audit-results.json.gz) | `7dafc2ee8ab59bda4d708c9625fa753d4cdb18d92066b737996f769b41f9355e` |
| Audit protocol | `16b8751ffbed49ad831d11d7b227f5fa666e08da67d0c0afd3bb12c3e474725e` |
| Audit implementation | `0ab772c33296b2574e01b56f54824a3ac61ec0be8088c4621ac69e39d9f73daa` |

Firmware, native policy, models and host/device defaults are unchanged. The
full native suite was not rerun for this offline-only addition.
