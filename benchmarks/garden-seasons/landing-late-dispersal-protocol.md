# Test broader late dispersal in the capped garden worlds

Status: **FROZEN before candidate runs**. The [purchase and reach audit](landing-dispersal-timing.md)
found that every late capped purchase landed in an already crowded site, and
most later usable sites were outside the original parent's reach. Test whether
one broader support improves renewal without unacceptable resource or population
harm. This is an examined-history diagnostic, not a promotion or training run.

## Fixed intervention and random mapping

Keep ordinary distances `5..7 + parent trait` through logic tick 626580.
Afterwards use `3..9 + parent trait`, in both directions, preserving the existing
edge reflection and final clamp. The first eligible ecology step is 626595.
No seeds already in the bank move. Parent traits, seed mutation, seed costs,
spacing threshold, bank size, viability and all other ecology remain unchanged.

For the existing dispersal draw `r`, the ordinary choice is `r % N`, where
`N` is six before onset and fourteen afterwards. Ordered choices are left,
right at each successive distance. This is the existing distance/sign transform
with seven distances instead of three, not preservation of the old six-way draw
after onset. The spacing-aware policy keeps an unblocked original choice;
otherwise it selects `clear[(r / N) % clear_count]`, retaining reflected aliases.
If every choice is blocked it keeps the original choice. No extra random draw,
new state, arbitrary global destination, or moisture/light oracle is introduced.

Use a separate host-only late-dispersal compile option, disabled by default and
rejected in Zephyr. Identify its version, onset and distances in JSON and the
world hash even before onset. The old from-start wide-dispersal experiment
remains unchanged and cannot be combined with this one. Only late uptake
limiting, with optional existing soil wicking, may accompany the new option.

## Panel and capture budget

Pin `landing-uptake-limit-results.json.gz` at SHA-256
`687f354bbeb04b71dc2c8d81b57bccefba0a1f6e2cfa6677f9dd14d517647768`.
Keep all eight settings: fixed/rotating reproduction order, daylight/dawn guard,
and ordinary/focal root allocation. Compare narrow versus broader late dispersal
in both cap-only and cap-plus-wicking worlds. Keep model bytes, weather seed
f7ee4528, 983040-tick horizon and all existing native arguments unchanged; add
only the non-mutating reach observer. No gardener, training or parameter search.

Run **48 full trials**: 16 rebuilt narrow controls once, and 16 candidates twice.
Require controls to match their pinned results, all four existing compressed
traces and terminal pixels exactly. Require candidate repeats to match all five
traces, results and pixels. Keep every setting, including globally closed and
pool-saturated cases. Short unit/integration checks are outside this full-run
budget; do not run extra long trials or tune after seeing outcomes.

Capture full stand, adult, direction and reach traces, plus the unchanged bounded
uptake window. The reach observer records actual parent traits, reflected choices,
purchase-time site masks and every germination check's site masks. Save terminal
images without screenshot replays. Archive binaries, model, settings, sources
and receipts in a fresh bundle; preserve all previous bundles. Compare physical
traces through onset, excluding rule-tagged footers. Stop on broken provenance,
prefix equality, determinism or accounting.

## Outcomes and interpretation

Report all sixteen paired comparisons. Reuse established whole-population harm
checks: maintenance shortfalls normalized by payments, living population and
species, late living time, seed-producing and successful descendant parents,
one-day and 32-day offspring survival, and empty-world timing. Report births,
purchases and their final-32-day counts, distinguishing survival censoring.
Also report post-onset birth cohorts and their survival and reproduction.

Verify each recorded purchase's support and spacing-aware outcome against the
stored slot census, including decomposing occupants. Reconcile purchases and
seed exits with the ledger. Report already-blocked landings and globally clear
spacing alternatives in post-onset and final-32-day windows. New offspring and
extra seeds alone do not establish sustained renewal. Wider support changes
probabilities as well as reach; results do not isolate those effects.

Reextract candidate resource and population accounts, and the bounded soil
budget. Reuse control analyses only after exact historical raw equality.
Keep a compact portable result and offline verification that never starts the
native simulator; verify original raw receipts separately. Inspect the terminal
gallery as qualitative context. Do not change defaults, flash the device or
promote a new rule based on this single-weather-seed panel.
