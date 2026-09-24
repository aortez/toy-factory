# Frozen wide finalists: return to the earlier failure cross

Test the accepted next question: do the final 16-world-trained models improve
the earlier transfer failures? No training, mutations, new scoring, alternative
generation selection or native changes. N/W are the eight/sixteen-world arms
of the coverage comparison, both using individual bounded renewal.

## Frozen inputs

Fully verify both bundles before native collection and retain pinned manifests:

- `artifacts/garden-renewal-transfer-v1`: SHA-256
  `0422c3be1c55801ce921014f5314f6cecd655ea34345f140522a15de15b42279`.
- `artifacts/garden-renewal-coverage-v1`: SHA-256
  `c18b16c04a80f5d94973e8f06d7e1ffdafcd8df011f83ca133c3ed917023d780`.

| Model | Frozen source | CRC |
|---|---|---|
| Original | Transfer original / coverage initial | `dc5e849d` |
| R1 N3 | Transfer r1-b / coverage narrow g2-c1 retained at G3 | `7ce0ed84` |
| R1 W3 | Coverage r1/wide/g3-c3 | `502e34a2` |
| R2 N3 | Transfer r2-b / coverage narrow g3-c3 | `01b9d94a` |
| R2 W3 | Coverage r2/wide/g3-c1 | `c9ea07fd` |

Copy exact trial/replay binaries, native source/configuration, model bytes and
reused controls. The two inputs' native binaries/configuration must agree.
Freeze the new runner, protocol, source snapshot and all copied inputs before
execution. Do not rebuild native tools. Verify final-versus-final provenance.

## Panels and exact budget

Keep the [earlier transfer cross](renewal-transfer-protocol.md) exactly:

- Training worlds: `b3376513`, `4023af38`, `1558f0e0`, `a61abb6e`,
  `39ee1dd4`, `0cfc84ff`, `1b85ea27`, `6a6893e3`.
- Old review worlds: `abf7af73`, `58e36558`, `0d983a80`, `beda710e`.
- Training schedules: train-1 `a3b7e953`, train-2 `50a32378`.
- Review schedules: review-1 `05d87ca0`, review-2 `b69a372e`.

World-set first, schedule-set second: TT/TR each have 16 conditions/model;
RT/RR each have eight. All five models therefore cover 240 model/world/schedule
outcomes. The original plus both N models reuse **144** saved outcomes, with
the existing repeats/provenance retained. W models contribute **96 new trials
and 96 complete independent repeat trials**. W's 32 TT outcomes must reproduce
their saved coverage training bytes as an additional deterministic check.

Gallery: first canonical world of each world set (`b3376513` / `abf7af73`),
both schedules, all four cells, all five models at day 192. This gives 40
frames: **24 reused controls** with their raw/JSON repeats, and **16 new W
frames with 16 independent image repeats**. No outcome-selected images.

Exact budget: **224 new native processes**, 192 ledger trials and 32 image
replays; zero mutations/training. At most two concurrent W-model jobs, serial
native calls within each private model job. Retain losses/empty gardens and
partial failure evidence; no retries, added conditions/horizons or extensions.

Retain 512 nodes/eight plants/eight seeds, rainfed-crowded, wide dispersal,
headroom uptake, selective maintenance, night-growth veto and recurring patch
deaths. No gardener, irrigation or intervention. Native v2 (158,190] plus
two-day follow-up and bounded periods (62,94], (94,126], (126,158], (158,190]
with their own follow-up, full-day confirmation and 32-day cap are unchanged.

## Analysis and verification

Primary: **G3 W versus G3 N on old RR**, separately R1/R2, under the unchanged
bounded-renewal ordering. Mandatory: all four cells, both score views, W/N,
W/original and N/original, both schedules and blocked world-seed omissions.
Show full survival precedence, minimum/total credit, zero periods and paired
counts. Preserve exact per-condition rational means for unequal 16/8 panels,
schedule/world shifts, interactions and blocked omissions in the saved data.
These are descriptive finite-panel contrasts, not a causal weather isolation.

Also reuse the coverage comparison's already-inspected fresh review results
as labeled context for the same five models. Keep its sixteen conditions and
old RR's eight separate, using per-condition means when comparing levels.
Do not pool raw sums, call this a fresh qualification test, reselect generations
or infer that the two mutation streams are independent environmental panels.

Keep species and founder-family counts separate. Save native late-window
child/seed-purchase cohorts separately from the four bounded-credit periods.
All copied scores must reproduce their source; TT must match saved training.
New ledger repeats are byte-identical. Verify native identity, capacities,
no interventions, follow-up, C/Python v2 agreement, bounded-period oracles,
projections and credit additivity. Every image must match its ledger endpoint,
independent pixels and PNG conversion; regenerate the complete contact sheet.
Record exact native commands/counts/timing, source/input hashes, full histories,
models, manifests and portable evidence. Verification/export run no native calls.

Test reuse mapping, immutable final identities, input tampering, exact budgets,
command routing, no control reruns, isolated model jobs, frame reuse, old/fresh
panel separation, unequal-denominator means and blocked omissions. Record
results, limitations and a next proposal in repo notes, roadmap and issue #30.
Stop at this budget. No model promotion, further training, firmware deployment,
commit, push or PR without discussion; preserve all earlier uncommitted work.
