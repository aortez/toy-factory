# Frozen-model dispersal-range screen

`make host-screen-landing-range` builds two isolated host executables, then runs
the same twelve fixed old/new live-finalist cases through 192 Garden days under
ordinary and wider dispersal. It does not retrain, change the objective or
modify `build-host`, the player or firmware defaults.

```sh
make host-screen-landing-range GARDEN_LANDING_RANGE_OUT=artifacts/my-range-screen
docker compose run --rm -T firmware python3 \
  artifacts/my-range-screen/sim/garden_landing_range.py \
  --verify artifacts/my-range-screen
```

The ordinary build has all research switches OFF. The treatment enables only
`TOY_FACTORY_GARDEN_WIDE_DISPERSAL`: offsets `5–7 + inherited trait` become
`3–9 + inherited trait`, with the same draw, direction and reflection rule.
This changes both reach and probabilities; no choice consults vacant soil.

The existing landing-observation projection also uses the active range. Thus
weights and feature encoding stay fixed, but range-aware occupancy/water/light
summaries can change even before the first seed lands. This is the coherent
existing range option, not a physical-placement-only intervention with identical
neural inputs. Separating those pathways would require another explicit design.

For explicit builds, invoke `sim/garden_landing_range.py --narrow-build DIR
--wide-build DIR --out NEW_DIR [--jobs 1..4]`. The collector requires matched
compiler/configuration settings and UBSan. Outputs must be fresh. Do not edit
source, protocol, inputs or builds while collecting. Verification accepts no
overrides and uses the frozen tools, binaries and inputs.

The four existing model/ledger archives fix cases and models. Initial biology
must match, while native rule bits and rule-aware identities remain distinct.
Both arms use the same pure rolling-history scorer and individual-minimum
aggregation. The ordinary trainer still rejects experimental ecology; no result
is relabeled as ordinary to bypass that guard.

Each arm retains complete seed/lineage ledgers and exact first-day resource
traces. All narrow histories, scores and raw traces must reproduce the earlier
recruitment panel. Untraced frame capture and repeated traced capture must match
state and pixels. All 24 final frames are retained; six-row sheets per climate
show narrow on the left and wide on the right in fixed case order.

The report compares the unchanged four-window score, late births and first-day
survival/resource shortages, qualifying descendant confirmations, seed
expirations, historical durable parents and biological emptiness. Pending seeds
and recently born children are censored, never silently counted as failures.
First-day survivors alone are not necessarily eligible renewal descendants.

The [prespecified protocol](../benchmarks/garden-seasons/landing-range-protocol.md)
defines the diagnostic screen gates and limitations. More germinations alone
cannot pass. Even a pass is not permission to promote the rule: the cases were
selected retrospectively, and broader confirmation would be a separate step.
The [retained screen report](../benchmarks/garden-seasons/landing-range.md)
includes every paired case, failed/passed gates and both fixed screenshot sheets.
