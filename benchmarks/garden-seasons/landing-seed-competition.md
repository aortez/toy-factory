# Seed placement can change the race, but each opening has one admission

The offline audit is complete: all ten saved histories have exactly **one free
plant slot** during the opening. Three of the five worlds have enough geometric
space for two mutually separated seedlings, but the eight-plant limit permits
only one. After that admission, no further plant births or deaths occur through
day 320. Pending-seed-aware placement is not the next priority for demonstrating
multi-generation renewal; discuss a bounded turnover test first.

This follows the [paid replacement experiment](landing-seed-replacement.md)
under a [fixed offline analysis plan](landing-seed-competition-protocol.md).
The audit uses saved data only: no new research runs, training, device operation
or ecology change were performed.
These are five selected, correlated histories sharing one model and weather
seed, not a generalization panel. Control and treatment both include the two
previously imposed deaths; the treatment additionally allows paid replacement.

## Space is not the same as admission capacity

At reclamation, every arm has seven stored plants, eight mature pending seeds,
and node room for eight or nine four-node seedlings. The immediate bound is
the minimum of geometric packing, free plant slots and node capacity: **one at
every observed non-expired check before refill**, including checks earlier in
the closing step. A successful seed consumes its slot before the next check.

| World | Initially spacing-clear columns | Maximum geometric placements | Clear columns after refill | Mature seeds with purchase-allowed alternatives, control / treatment |
| --- | --- | ---: | --- | ---: |
| W1 | 3, 4, 13 | 2 | 13 | 3 / 3 |
| W2 | 16, 17, 18, 24 | 2 | 16, 17, 18 | 0 / 0 |
| W3 | 11, 12 | 1 | none | 4 / 2 |
| W4 | 16, 17, 18, 24 | 2 | 16, 17, 18 | 0 / 0 |
| W5 | 12, 13 | 1 | none | 3 / 3 |

Columns are zero-based. Packing requires at least three columns between bases;
it ignores water/light and is not a survival prediction. After refill, the
remaining clear columns in W1/W2/W4 still fail global plant capacity. In W3/W5,
the newly occupied patch also eliminates all spacing-clear columns.

The last column counts distinct seeds, including an eventual winner when it
has another option. At least one different reachable column must pass every
recorded mature-seed gate while the seed is mature and the slot is still free.
It must also have been allowed by the recorded spacing filter at purchase.
This extra check matters: W1 parent 22 has current alternatives but could not
have selected them under that filter at purchase. Reach alone would count four
seeds there instead of three. Reflected support aliases remain in the evidence;
counts use distinct columns, not alias-weighted probabilities.

These are **same-state alternatives, not counterfactual simulation results**.
A different historical landing can change earlier births, water, shade and
later competition. Passing the original purchase filter does not prove that
the seed would remain pending until this opening. Nor does a single-slot bound
rule out downstream survival changes in a different replay.

## What the queues explain

The opening is not waiting for an empty seed bank to acquire its first mature
candidate: all eight initial seeds are mature. Many are at blocked sites.
First recruits in W1/W2/W4 have no seed in these opening windows; their explicit
zero rows remain in the artifact. First recruits in W3/W5 already have older
seeds, and the treatment buys them new ones by replacing those old entries.

In W3 control, recruit 34's old column-10 seed has a reachable, purchase-allowed
column-12 alternative at the closing check. The treatment replaces it before
that check. Its new seed is at column 11 and age one when parent 30's seed wins;
moving the new seed to column 12 would still leave it dormant. The other paid
replacement, parent 28's seed, is only age five. Neither becomes mature before
the recorded refill.

In W5, recruit 31's old column-14 seed has mature alternatives at columns 12
and 13, including two observed checks before its treatment replacement. Its
new column-13 seed is checked **before** the winning seed at refill, but is only
age six and blocked by dormancy alone. Parent 21's seed then germinates at age
ten. At the next step, recruit 31 also faces full plant capacity and spacing.
Changing same-step order cannot make an age-six seed mature.

Replacement creates a newly paid seed; it is not relocation of an old seed
with its maturity preserved. The controls' displaced counterparts ultimately
expire, but that does not make all mature blocked seeds useless in other
histories. Three replacement seeds remain pending at the cutoff, not failed.

The original outcome stands: one new child per world per arm, surviving at
least sixteen days, with 32-day survival censored. No followed first recruit
gains a child. The seven original focal plants and five first recruits are
all retained in each arm, including non-producers and blocked seeds.

## Recommendation: test renewal opportunities before adding seed sensing

Stop tuning placement within this single-opening panel. There are meaningful
placement alternatives, but the panel primarily asks who claims one vacancy;
it cannot establish sustained multi-generation renewal. Faster refill, a
different winning parent, or another purchase is not that goal.

The next proposal is a **fixed, lineage-neutral environmental turnover test**
across several openings, keeping the eight-plant capacity, existing controller,
seed rules and resource costs unchanged. Compare against no additional
turnover, and select the schedule and environmental targeting criterion before
running it—not after seeing which parent loses. Measure successive generations'
established offspring, resource shortfalls, empty-world failures and diversity,
not merely immediate refill. This is a proposal for discussion, not an
implemented mortality rule or a new training run.

Seed-aware placement might later help avoid redundant purchases or influence
competition. It would need local information about pending seeds' locations and
maturity, alongside admission capacity. The existing
[landing observations](../../docs/garden-landing-observation.md) summarize
space/water/light, not this queue. Compact projected mature/dormant seed pressure
could be considered without lineage IDs, future death schedules, future weather
or a guaranteed-success oracle. This audit does not establish the value of
adding those observations; no network interface was changed.

## Evidence and verification

The [portable artifact](landing-seed-competition-results.json.gz), about 86 KiB,
retains 1,904 compact rows and all 15,229 seed checks in the prescribed windows,
including the preceding and following boundary steps. It also retains every
competing seed's actual purchase receipt and stored inventory, complete cohort
references, sequential closing queues, counters and first/last alternative
witnesses. All ten histories are present; no unsuccessful world is dropped.

The offline extractor authenticates all thirty selected stand/adult/reach
traces against the pinned replacement capture and raw manifest, checks their
complete clocks and footers, then retains the bounded windows. Portable
verification rechecks the original capture and derives the analysis again.
Raw verification also reproduces the selected evidence and final gzip byte for
byte with subprocess launches forbidden. This is not a rerun of the previous
whole-bundle resource-accounting or observer-neutrality checks.

The [tool guide](../../docs/garden-landing-tools.md#audit-pending-seed-competition)
documents fresh extraction and portable/raw verification. The twelve new tests
cover packing versus capacity, dormancy, purchase-time filtering, aliases,
complete cohorts/checks, sequential refill, tampering and deterministic output.
Runtime C and the frozen earlier research files are unchanged.

All three focused CTests pass: the new competition audit and the existing
opening-opportunity and seed-replacement suites. The last also executes its
existing native CLI boundary/smoke regressions, separately from the offline
audit. The complete host suite and firmware build were not repeated for these
Python/documentation changes. Make command expansion, whitespace checks and
218 local documentation links/heading anchors pass; Markdown was inspected as
source, not in a rendered preview.

| Artifact | SHA-256 |
| --- | --- |
| Analysis plan | `d321761a612c7528ad1d1bdd213e7450408dedfd4740211e273e9cce5da9719d` |
| Portable result | `176ba276d673084ab1d9d1cbaa5c9325d9429239f594e12a4b106ee2d5e003b6` |
| Input replacement capture | `e856d8877a34747bce4c5ade78e3492acb0f211379ddcb843e4a44a2ec868b4a` |
| Input raw manifest | `6f5f737dcb8147a488ad0339a553d7f81823db65d5df8a097332112ff15de465` |
