# Final period germination stalls behind living neighbors

The four zero-credit periods in the [shoot-budget screen](landing-budget.md)
have seeds, but their landing sites remain occupied. **Every one of 261,888
mature seed checks is spacing-blocked by a living plant other than the seed's
parent.** There are 1,779 checks where spacing is the only failed germination
gate. This is a local establishment barrier, not a lack of flowering or seeds.

The two seasonal worlds with nonzero final-period credit are not renewing
successfully either. Their credit comes entirely from older plants. Across all
six reserved-shoot worlds, the final period has one birth and zero new first-day
survivors. By day 190, every living plant has aged out of renewal credit.

This is an offline diagnosis of (day 158, day 190], retaining the eligible-32
control and reserve-32 candidate in all six seasonal worlds. It changes no
model, policy, ecology, score or device firmware and runs no new simulations.
The original screen's failed retention gates remain failed.

## Seed supply is present but local spacing never clears

Each of the four zero-credit worlds starts with eight seeds, expires those
eight, and buys eight replacements during the period. The bank contains eight
seeds at every post-step sample. All replacements remain pending at day 190;
they are not counted as failed complete lifetimes. Their recorded future fates
through day 192 remain separate in the audit.

Each world has 65,472 mature checks, all spacing-blocked. Four or five living
adults persist throughout the period, all already beyond the score's credit-age
limit when it begins.

| Reserved world | Spacing is the only blocker | Blocked mature checks with an open site elsewhere | Distinct ecology samples with those openings |
|---|---:|---:|---:|
| Single /33 | 333 | 3,904 | 490 |
| Multi /33 | 254 | 2,325 | 291 |
| Single /35 | 887 | 4,072 | 511 |
| Multi /35 | 305 | 2,743 | 344 |

Checks count individual seeds; several seeds can be checked in the same
15-logic-tick ecology step. Moisture, darkness and cold frequently overlap with
spacing, but no mature check in these four worlds fails either the plant-slot
or node-capacity gate. More slots alone would not remove the recorded spacing
barrier.

The ordinary spacing rule rejects a column less than three columns from an
occupied plant base. Retained dead plants also count in the native rule.
The audit therefore uses living lineages only as positive witnesses, without
inventing dead-body removal times. Here, living neighbors explain every mature
spacing block, and none is the producing parent. In some control checks no
living witness is available; those remain explicitly unresolved rather than
being silently attributed to a corpse.

An open site elsewhere passes the instantaneous hypothetical mature-seed gates.
It is **not** necessarily within the parent's dispersal range, open at seed
purchase time, or capable of supporting the resulting seedling. The saved
recruitment trace records an open-column count, not those columns' identities
or each parent's full landing support.

## Remaining credit does not mean new recruitment

Births and survivors below use the same (158,190] birth cohort with complete
first-day follow-up. Credits are the unchanged bounded-age renewal metric.

| World | Eligible 32 births / survivors | Reserve 32 births / survivors | Reserve 32 credited ticks |
|---|---:|---:|---:|
| Single /33 | 12 / 6 | 0 / 0 | 0 |
| Multi /33 | 0 / 0 | 0 / 0 | 0 |
| Single /34 | 10 / 6 | 1 / 0 | 144,630 |
| Multi /34 | 0 / 0 | 0 / 0 | 14,715 |
| Single /35 | 11 / 6 | 0 / 0 | 0 |
| Multi /35 | 13 / 5 | 0 / 0 | 0 |

Multi /34 has the same universal mature spacing blockage as the four failed
periods, but a previously established descendant carries 14,715 credit ticks
into the window. Single /34 carries 144,630 ticks from three older descendants.
Neither has any fresh renewal credit. All six reserved worlds still contain
established descendants at day 192; they are surviving, not continually
replacing themselves.

The control is not uniformly healthy: multi /33 and multi /34 also have no
births and only carry-in credit in this window. Across the other four controls,
46 births produce 23 first-day survivors. These are diverged populations, not
matched individual rescues.

### The sole new reserved recruit fails after germination

In single /34, flower seedling 27 germinates in column 27 at day 172.125,
then dies energy-short at day 172.46875, before its first-day confirmation.
Its seed encounters 48 mature moisture-only checks before its successful check;
the other mature checks in that world are spacing-blocked.

Its energy account balances exactly: 64 initial + 94 collected = 120 spent on
growth + 38 paid in upkeep. Water remains at death and is recorded as discarded.
The receipt establishes a first-day energy failure, not proof that a particular
growth veto would rescue it. Finding an unoccupied landing column is therefore
necessary for these blocked seeds but not sufficient for durable renewal.

## Next bounded question

Keep the shoot reservation experimental. Before choosing a placement rule,
reuse the existing parent-specific reach diagnostic on these reserved-shoot
worlds: which openings were reachable under the actual parent's existing
dispersal choices, at purchase and during subsequent seed checks?

That would distinguish missed usable choices from sites outside current reach.
A later isolated placement comparison could retain the same spacing, costs,
seed lifetime, capacities and renewal gates. It must measure first-day and
later renewal outcomes, not just germinations. No such counterfactual has been
run here; globally open sites do not establish a rescue.

The longer-term question remains turnover: keeping old plants alive while
they repeatedly supply blocked seeds is not the intended renewal behavior.
Do not relax credit-age scoring to reclassify those survivors as new renewal.

## Reproduction and verification

The audit reconciles **754,161 seed samples**, including **753,329 mature
checks**, across twelve final-period histories. Expiry happens before a
germination check and is counted separately. Window boundaries retain carry-in
seeds, same-step expiry/replacement, purchases at the final tick, and
right-censored seeds without assigning future outcomes to earlier periods.

Living-neighbor attribution follows native stage ordering: deaths and
decomposition precede seed checks, and earlier germinations in the same step
already occupy space. Exact checksums protect source traces and the exported
windows. All twelve score histories and the selected birth cohorts' first-day
resource receipts recompute; the full screen comparison is retained unchanged.

The [portable seed windows](landing-budget-germination-windows.json.gz) contain
only the selected seed rows, including every empty ecology sample. They were
extracted from and independently compared with all twelve checksum-verified
full recruitment traces. The [portable analysis](landing-budget-germination-results.json.gz)
recomputes without the local bundle or any native executable.

```sh
make host-audit-landing-germination \
  GARDEN_LANDING_GERMINATION_OUT=artifacts/new-germination.json.gz
docker compose run --rm -T firmware python3 -W error sim/garden_landing_germination.py \
  --verify benchmarks/garden-seasons/landing-budget-germination-results.json.gz
# Optional comparison of every exported row against the retained full traces:
docker compose run --rm -T firmware python3 -W error sim/garden_landing_germination.py \
  --extract-from artifacts/garden-landing-budget-v1 \
  --verify benchmarks/garden-seasons/landing-budget-germination-windows.json.gz
```

The Make target requires only the Docker image, not a native build. Outputs
are exclusive/no-clobber. Ten focused tests pass, including corrupt receipt
rejection, dormancy/expiry/window boundaries, same-step births and dead-body
ambiguity, complete frozen-result regeneration, and a separate sample-by-sample
credit oracle. Analysis is tested with native execution disabled.

All **159 ordinary host CTests pass** under UBSan (272.21 seconds). The
standalone portable verifier, Make help/dry-run and `git diff --check` pass.
The local test log is `artifacts/garden-germination-validation.log`. No C source
changed during this audit; the native-stage review informed timestamp and
living-witness checks in the host analysis.

- Budget input SHA-256:
  `bad5297fa26ad52b93a899e3d0f0fcd3255a6b5e214e1120f68bc3902e455640`.
- Extracted window SHA-256:
  `9de2ef4f06c7f435c666d11c75fc7f0211351bdd246161cded3dbbcd6fc61099`.
- Analysis SHA-256:
  `5898dc7f5c5b999f3e729b067fa3b93647a8c9c7e7295b4aa097b9447680bbe4`.

This diagnoses a selected, reused panel; it is not unseen validation of a
controller or qualification of the environment.
