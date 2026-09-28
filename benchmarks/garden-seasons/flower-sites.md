# Flower reach at seed-production opportunities

**Flower selection is a small lever at the current release times; habitat and
growth geometry account for most closed reach.** This is a read-only diagnostic,
not a policy trial. All 64 observed trajectories exactly match the saved
[origin-screen](flower-origin.md) worlds. No release, growth, dispersal, default
or device behavior changed.

The [fixed protocol](flower-sites-protocol.md) covers every one of the 3,576 saved
seed purchases: 1,866 base-origin and 1,710 flower-origin, across the same 32 cases
per arm through day 128. Weather is shared across layouts/controllers; this is
eight weather replicates, not 64 independent environments. Geometry is captured
before the producing flower is marked spent; site constraints use the same
step's normal final light refresh. We are not using stale pre-growth shade.

## Where could a seed land?

Primary result: flower-origin worlds. “Open” means all current germination checks
pass for a hypothetical mature seed, excluding dormancy. It is not a guarantee
that a newly released seed will establish later.

| At a successful seed purchase | Whole run | Purchases after day 112 |
| --- | ---: | ---: |
| Selected flower can reach an open site | 331 (19.36%) | 17 |
| Selected flower cannot, but another eligible flower can | 39 (2.28%) | 2 |
| No eligible flower reaches an open site, but one exists elsewhere | 373 (21.81%) | 39 |
| No column in the world is currently open | 967 (56.55%) | 90 |
| Total purchases | 1,710 | 148 |

The bank-capacity condition is already satisfied at these purchases. We do not
sample all potential release times, bank-blocked attempts or times after waiting;
the result is conditional on the existing automatic release schedule.

Ignoring cold and node/plant capacity barely changes the picture: the four local
habitat counts are 332, 40, 376 and 962. Moisture, light and spacing therefore
explain most of the closed sites **at these sampled times**. Cold is present at
eight purchases, node capacity at four, and plant-slot capacity at none. These
overlapping limits are not independent causal failure counts. Spacing includes
unreclaimed dead plant slots, as the actual engine does.

Of all purchases, 1,310 (76.61%) have only one eligible flower. Late in the run,
that is 129/148 (87.16%). This is a count of mature, unspent flowers at purchase,
not a claim that those plants have only one flower in their entire bodies.

| Species, flower-origin arm | Purchases | Only one eligible flower | Another flower opens otherwise closed reach |
| --- | ---: | ---: | ---: |
| Flower | 1,014 | 1,014 | 0 |
| Shrub | 197 | 95 | 14 |
| Ground cover | 499 | 201 | 25 |

Flower choice can still be an interesting behavior for shrubs/ground cover. It
cannot solve the flower species' present placement problem at these moments,
because there is no alternative eligible flower to choose.

## Reach versus landing weight

There are fourteen nominal direction/distance branches in this wide-scattering
experiment. Edge reflection can map several branches to the same soil column;
distinct reachable columns are not equally weighted. We retain every flower's
support and compute exact branch weights over all nonzero 32-bit xorshift outputs,
including the tiny modulo bias.

Under that **uniform-reference** distribution, average open-landing weight is
4.60% for the selected flower and 5.77% for the best currently eligible flower.
In the closing purchase window it is 3.14% versus 4.87%. These are hypothetical
snapshot scores using full-world information, not measured germination rates,
learned-policy performance, or an upper bound on lifetime fitness.

Another flower has strictly greater reference weight at 105/1,710 purchases; six
of those differences are only 1–2 outputs out of 4,294,967,295 and are practically
negligible. Only 39 purchases change from zero to nonzero reach. The corresponding
local-habitat counts are 106 and 40. Late in the run, nine purchases have greater
weight available and two have newly open reach; both late newly-open cases occur
in one world. All ties, zero-gain worlds and per-world partitions are retained.

For reference, base-origin purchases have class counts 466 / 121 / 296 / 983.
The “flower reach available” category there is a hypothetical relocation,
**not** a selectable behavior under the base-origin rule. Even its first flower
can offer a different origin. On the base trajectories, average actual-origin
open weight is 6.10%; relocating to the best eligible flower gives 5.88%. Do not
pair diverged descendants by numeric IDs or treat these as a flower-choice trial.

## Current blockage is not future failure

Among the 967 flower-origin seeds produced while **every column** was blocked:

- 465 eventually germinated.
- Of those offspring, 145 became durable parents: they survived a full day and
  produced a child that also survived a full day.
- 342 seeds expired and 160 remained pending at the horizon.

Those 465 births represent more than half of the arm's 839 births. A site can
become usable while its seed waits. A current-site veto would therefore reject
many purchases that succeeded on the saved trajectories. That is not a causal
prediction of the outcome after introducing a veto, since the population and
future resources would then change.

Closing **purchases** are different from closing **births** in the previous
reports. Of the 148 purchases after day 112, 134 are still pending at day 128;
none could yet reach the 32-day expiry boundary. Do not count these censored seeds
as failed reproduction or compare snapshot classes as unbiased success rates.

## Decision and next proposal

Do not add a global “only release onto currently good soil” rule or promote a
flower-selection policy from this audit. Selection has some opportunity, but most
current purchases have no choice, unreachable openings or no present opening.
This does not rule out a trained controller growing a different body, nor a
different release schedule creating different opportunities.

Next proposed investigation: follow the saved seeds through their waiting periods
and identify which constraints clear before germination—water returning, shade
clearing, neighboring tissue decomposing, or combinations. That would help decide
which changing environmental signals are useful to a growth/reproduction agent,
rather than treating present blockage as permanent failure. Any new action,
observation or intervention should be discussed after that result.

## Implementation and integrity

The embedded-C conventions guided a bounded, caller-owned observer: 2,588 bytes
of host diagnostic storage, no world fields, callbacks, allocations or extra RNG
draws. The existing production draw is recorded for checking only; it is not an
agent observation. Eligible flowers are bounded by the existing 256-node pool.
Site masks are checked independently against moisture/light thresholds, spacing,
capacity and cold, and against all saved seed masks after the final light refresh.

Every ecology state hash and seed-creation count matches its frozen original:
2,097,216 observed states across 64 worlds. All observation traces repeat
byte-for-byte; independent raw reanalysis reproduces the per-purchase evidence
and summary. All 3,576 purchases reconcile with their seed ledger and later
offspring outcome. No original experiment bundle or binary was overwritten.

Validation passes:

- Four focused native tests in each diagnostic build, including full-world
  noninterference, eligibility/ownership, final bank slot and maximum flower array.
- Nine Python checks with paired builds and installed portable evidence, including
  unchanged legacy collector output, site classes, weights, censoring and malformed inputs.
- All 120 default and 120 older-research CTests; focused evidence regressions
  also pass after installing the retained archive.
- Normal firmware build: still 257,596 bytes flash, 223,004 bytes main RAM and
  8 KiB core-1 RAM. World/snapshot sizes and the previous screenshots are unchanged.

No device flash, commit, push or default promotion was performed.

## Reproduction and evidence

Use two new build directories with the same ecological flags as the saved
origin experiment: all host research defaults OFF, wide scattering ON in both,
flower dispersal ON only in the flower arm. RelWithDebInfo, sanitizers ON,
player/profiling OFF. Build `toy-factory-garden-production-audit`,
`toy-factory-garden-flower-audit-test` and `toy-factory-garden-capacity-test`.
The optional collector mode is `--flower-sites`; its version-2 header explicitly
labels geometry fields and the post-light-refresh sampling phase. Version-1
output remains unchanged without that option.

```sh
docker compose run --rm -T firmware python3 sim/garden_season_flower_sites.py collect \
  --out artifacts/garden-seasonal-flower-sites --jobs 4
docker compose run --rm -T firmware python3 sim/garden_season_flower_sites.py verify \
  --out artifacts/garden-seasonal-flower-sites --jobs 4
```

Defaults select `artifacts/build-host-flower-sites-{base,flower}` and the original
`artifacts/garden-seasonal-flower-origin` bundle. Collection requires a new output
directory. Verification reanalyzes saved observations, without replaying simulation
trajectories; it runs the small storage-test executable for build verification.

Raw traces remain in ignored artifacts. Portable
[purchase/site/geometry evidence](flower-sites-purchases.json.gz) and the
[summary with source/build/input hashes and partitions](flower-sites-summary.json)
are retained here. SHA-256 identities:

- Decompressed purchase evidence: `0023876df42885ebdaae940ab13af3e442434f93cb3c51c1ddd4075a6f39c18d`.
- Summary bytes: `2717f9c361e37152fb9f28d49742d60935385d519ec07cc2f57db55baa8d3076`.
