# Exact dark-interval budget: fixed offline audit

Follow the [phase-aware forecast audit](renewal-phase-forecast.md) with a narrower
question: can current stores and stress carry a plant through the **immediately
following guaranteed zero-income interval**, assuming no more optional expenses,
fixed energy upkeep and sufficient water? This is not a morning-income forecast,
runtime gate, training objective or new native experiment.

## Frozen evidence and panels

Reuse both complete eight-day traces in `artifacts/garden-renewal-seed-veto-v1`,
manifest SHA-256
`dd44e765e15d4be5ed0c5c99273699718358ac8e5790af838162121620bcb5ae`.
Pin and reproduce the previous phase audit, summary SHA-256
`f716bc85c47659f03c4b8b7e6fe10c05936a566444feea543879c56a4fb60f6f`.
Do not change this bundle, fit a parameter, add worlds or launch native tools.
The outcomes are already known/reused, not held-out qualification.

Before projection, the complete inventory is:

| Trace | Growth/finish expenses | Renewals | Seeds | Spending steps | Newborn spending steps | Coincident expenses |
|---|---:|---:|---:|---:|---:|---:|
| Control | 703 | 65 | 52 | 814 | 14 | 6 |
| Veto | 547 | 105 | 60 | 711 | 9 | 1 |

Retain every expense, including unsupported anchors. Exactly 86 control / 84
veto spending steps have an immediately following guaranteed-dark interval:
84 growth actions in each trace and two control seed purchases. None of these
covered steps has coincident expenses or is a newborn's first step. For a separate
systematic state panel, evaluate **every living plant at every phase-117 census**
in both traces. This provides evening controls and includes the previously
investigated parents, without pretending their phase-116 purchase already had
a known next-step income. Keep these panels and their counts separate.

## Fixed calculation

Use the existing integer sun formula, verified against every census. Native leaf
uptake cannot yield energy when global strength is below 64: cell light cannot
exceed it, light is divided by 64 before leaf-condition accumulation, and the
saved fractional remainder alone is insufficient to yield a unit.

Start **after the anchor step's income and maintenance**. If its next ecology
step could earn energy, report out-of-scope, not zero income or approval. Otherwise
project until the last step strictly before global strength can next reach 64.
Thus the longest covered interval begins after phase 117 and contains phases
118..255,0..10; phase 11 is excluded. Small early-morning intervals with no
maintenance payments remain explicitly zero-payment checks, not survival tests.

At each future maintenance tick (every 60 logic ticks), debit up to
`ceil(nodes / 8)` energy. A full payment decreases existing stress toward zero;
even a partial unpaid amount increases stress by one. Death at stress eight is
absorbing. Record required/paid/unpaid maintenance, first shortage/death tick,
peak stress and ending state. Do not double-charge the anchor or credit any
income beyond the zero-income boundary. Distinguish all-paid, shortage-but-alive
at the boundary, and energy-stress death. Alive at the boundary **does not mean**
morning recovery is assured.

For each accepted expense, reconstruct its pre/post stores in native stage order:
growth **or** renewal, then seed purchase. Pre-growth uses the previous body
(the four-node seedling for a newborn); post-growth uses the observed new body.
Maintenance in the current step has already charged the old body. FINISH can
spend without adding a node. Renewal/seed preserve body size. Report both
pre/post dark budgets as **local no-further-spending arithmetic**, not a causal
claim that suppressing that action rescues the plant. Declining an action can
change future decisions, bodies, seed-bank competition and RNG consumption.

## Validation and reporting

- Reconcile every live census's energy/water budget, accepted expense counters,
  seed-bank purchases and observed stress; retain newborns, not just founders.
- Compare actual trajectories using the **end-of-step** state, separate from
  intermediate pre/post expense stages. Track later optional spending, changed
  energy upkeep, and water shortage as assumption breaks. Leaf maturation,
  condition, shade and roots alone cannot change guaranteed-zero energy income;
  water stress is still explicitly an exclusion.
- Report complete assumption-valid windows and prefixes strictly before their
  first break, separately from broken/censored windows. Verify observed income
  is zero in every live covered sample. Keep per-step energy/stress errors and
  death-timing comparisons, with independent counts of case-specific deaths.
- Terminal native telemetry is cleared: record death timing/cause, never invent
  terminal income or debit observations. Right-censored outcomes are not survivors.
- Preserve per-record identities, action effects and checkpoints in portable JSON;
  summarize each panel/trace, and disclose shared prefixes and overlapping windows.
- Repeat analysis exactly, hash-check evidence and dependencies, add tests for
  boundary phases, cost ordering, stress recovery, death, missing/corrupt records,
  assumption breaks, censoring and no future-input leakage. Update issue 30/docs.

No runtime promotion, new native run, firmware deployment, commit or push follows
from this audit. Discuss the result before choosing any intervention.
