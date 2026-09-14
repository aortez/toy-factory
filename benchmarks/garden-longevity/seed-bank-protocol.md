# Seed-bank capacity experiment (predeclared)

Single variable: maximum ungerminated seeds **8 versus 16**. Host only, 512 body
nodes, eight plant bodies. No firmware/default promotion or model training.

Run the same fixed `rainfed-crowded` worlds `b61837dc` and `c7f54e18`, each with
`neural-no-night-growth` and `neural-reserve-growth` (`energy-reserve-v1`). Use
the frozen `dc5e849d` model, selective leaf maintenance, wide-v1 dispersal,
headroom-v1 water uptake, drainage off, and fresh-1 patch schedule `0xe4d65e6f`.
Keep all seed costs, scattering, lifetime, dormancy, eligibility, growth rules,
rain and patch scheduling unchanged; never retarget empty patch hits.

Eight runs (four pairs), each reset through 192 Garden days (737280 logic ticks).
Closing window: days 160–192. Do not extend beyond this horizon; the known
plant-age wrap at 256 days is outside this experiment. Record whole-run outcomes
too, and native screenshots at days 64, 128 and 192 for every run.

Primary observations, reported per pair rather than only pooled:

- Closing offspring births, full-day survivors with complete follow-up, and
  full-day survivors that themselves have a full-day-surviving child.
- Exact pre-germination open steps used/missed, mature seed blockers, and
  seed placements; these are step/check counts, not independent vacancies/seeds.
- Parent reproduction energy/water expenditure, natural deaths, stress,
  below-seed-cost stores, living plant occupancy and environmental patch hits.
- Whole-run and closing seed production, expiration and bank occupancy.

More births/seeds alone is not success. Improved surviving offspring without
losing durable reproduction or materially harming parents warrants a wider
panel; mixed results call for explanation, not automatic promotion. Four pairs
are mechanism probes, not a statistical qualification panel.

Freeze source/binaries/model/cache/protocol in a new ignored bundle. Re-run the
eight-seed side and require exact frozen world/site rows and boundary identity.
Check the two capacities share a hash prefix through the first extra bank slot;
after that, reproduction spending and RNG divergence are expected. Independently
replay screenshots, reconcile full ecology/seed lifetimes and live-step budgets,
and verify exact closing seed attempts against ordinary stepping. Preserve all
failed output and record manifest SHA and commands in the final report.
