# Saved-ledger renewal audit

This read-only host analysis explains the completed five-seed landing-training
panel. It runs **no native worlds**, selects no controller and changes no score
or ecology. The [protocol](../benchmarks/garden-seasons/landing-renewal-audit-protocol.md)
fixes the input identity, all 224 histories / 896 windows, temporal conventions
and required checks.

The [completed diagnosis](../benchmarks/garden-seasons/landing-renewal-audit.md)
documents seed expiry, first-day seedling losses and aging without renewal,
including the limits of what the saved ledgers can explain.

```sh
make host-audit-landing-renewal
# Use a fresh output directory for a later reproduction:
make host-audit-landing-renewal \
  GARDEN_LANDING_RENEWAL_OUT=artifacts/garden-landing-renewal-audit-another
```

No host build is required; the existing Docker image supplies Python. The
input is the pinned, retained `landing-multiseed-results.json.gz` archive.
Keep sources unchanged during collection, which revalidates native ledgers and
all original scores, repeats the derived analysis, checks input immutability
and saves a frozen source/input bundle. Independently verify it with:

```sh
docker compose run --rm -T firmware python3 \
  artifacts/garden-landing-renewal-audit-v1/sim/garden_landing_renewal_audit.py \
  --verify artifacts/garden-landing-renewal-audit-v1
```

The audit separates purchase cohorts from germination events, crops outcomes
to each window's two-day follow-up, and never labels pending 32-day seeds as
failed. Exact living-plant occupancy distinguishes founder children from
later-generation eligible and aged-out descendants. The latter's sampled
credit must equal the unchanged objective exactly.

Zero-credit signatures overlap; they are not causal labels. Ledger expiry
alone cannot distinguish moisture, light, spacing, plant capacity or node
capacity. Aggregate seed-cohort counts are window observations: a seed may
appear first as a purchase and later as carry-in. Minimum-credit accounting
uses each world's first weakest window and explicitly notes when the old/new
windows differ. It is not a hypothetical intervention or new fitness function.
