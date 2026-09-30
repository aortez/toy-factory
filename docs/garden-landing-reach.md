# Parent-specific landing reach diagnostics

`make host-trace-landing-reach` replays the same twelve fixed cases as the
[recruitment trace](garden-landing-recruitment.md), with unchanged model bytes,
scoring and ecology. It asks whether an open site was within the producing
parent's actual dispersal support, not merely somewhere on the map.

```sh
make host-trace-landing-reach GARDEN_LANDING_REACH_OUT=artifacts/my-reach-trace
docker compose run --rm -T firmware python3 \
  artifacts/my-reach-trace/sim/garden_landing_reach.py \
  --verify artifacts/my-reach-trace
```

Collection accepts `--build`, `--inputs`, `--jobs 1..4` and a fresh `--out`.
Verification accepts no overrides and uses the frozen binary and inputs. Do
not modify source, protocol or build files during collection. The bundle keeps
all raw traces, repeated traces, native results, models, inputs, source snapshot,
build flags and hashes. Traced/untraced results must match the historical worlds;
the existing recruitment trace must also remain byte-identical. This is host
instrumentation only; no firmware memory or authoritative world state is added.

The native `replay` command accepts `--ledger --reach-trace NEW.jsonl`, optionally
alongside `--recruitment-trace OTHER.jsonl`. Files are exclusive-create, and an
error leaves an incomplete trace that the analyzer rejects. Reach tracing is
restricted to ordinary ecology, not experimental wide/flower dispersal.

Each ecology step records:

- Successful purchases: immutable parent ID, actual landing, parent's base and
  dispersal trait, all six direction/distance outcomes including reflection
  aliases, and post-final-light-refresh hypothetical mature-site blockers.
- Sequential seed checks: parent, age, actual column/blockers, fate, child ID
  and the 28 hypothetical mature-site blockers at that exact check. Sites are
  56 lowercase hexadecimal characters (one byte per column); expiry uses null.

The parent is read immediately after reproduction, which cannot kill it,
change its genome or compact its slot. The seed's genome can already be mutated
and must not be used to reconstruct its original landing range. The production
transform is pure; enumerating support consumes no random draws. Six outcomes
are not necessarily six distinct columns or an assertion of exact probability.

The analyzer validates every purchase and check against the existing seed and
lineage ledgers and recruitment histograms. It freezes reach at purchase, even
after the parent disappears. It retains all seeds (including successful and
pending ones), full mature-site-mask histograms, opportunity summaries and
per-column open windows `[checks, first_tick, last_tick, longest_checks]`.
Lengths count consecutive 15-logic-tick ecology samples, not continuous time.
The main cohort remains seeds expiring in (62,190] Garden days, with their whole
32-day lifetimes traced. Dormant checks and pre-check expiry are separate.

An open site must pass all simultaneous gates. A spacing-clear site may still
fail water, light, capacity or cold. Spacing includes retained dead plants.
Purchase snapshots exclude dormancy and precede future germination; later open
sites are observations of the unchanged world. Neither proves that relocating
a seed would rescue it or that its eventual child would survive. These selected
retrospective cases diagnose mechanisms, not generalization performance.

The prespecified scope is in the [protocol](../benchmarks/garden-seasons/landing-reach-protocol.md).
The [retained report](../benchmarks/garden-seasons/landing-reach.md) distinguishes
persistent reach/spacing exclusion from genuinely missed reachable alternatives.
