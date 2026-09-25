# Exact germination checks — frozen diagnostic protocol

Declared before collecting the new detailed outcomes. Reuse all eight runs from
the crowded recruitment diagnostic: 256 / crowded b61837dc / fresh-4 and fresh-1;
512 / crowded b61837dc and c7f54e18 / fresh-1; each baseline and reserve, drainage
off, selective maintenance, frozen model dc5e849d. This is a post-hoc diagnostic,
not held-out qualification. No policy, ecology, seed, schedule or capacity tuning.

Replay from reset to day 160 normally, then observe exact seed visits during
days 160–192 (8,192 ecology steps per run). Use the same authoritative seed loop,
with a host-only caller-owned bounded audit buffer, never a global observer or
callback. Keep world layout, hash version, RNG and simulation ordering unchanged.

At each visit retain parent/age/location, nodes/plant slots, actual moisture/light,
blockers, contemporaneous hypothetical-site masks, outcome and newborn lineage.
Expiry precedes checks and is explicitly separate from dormancy/failed checks.
Record node/slot/bank inventories at ecology start, before/after germination,
after growth and after reproduction. Seeds are checked sequentially, not in parallel.

Measure actual mature-check blocker overlap; viable openings before checks versus
post-step openings; openings with no mature seed, or mature seeds but no successful
landing; successful openings consumed within a step; node capacity consumed by
growth after germination. Report bright/twilight/night separately. Keep exact
births and counts, not just fractions. Expired seeds are not failed germination
attempts; repeated checks are not independent seeds or failure probabilities.

Retain the previously observed final vacancy at ticks 721,650–722,670 in the
256-node adverse reserve case as a fixed close-up. Do not replace unsuccessful
comparisons with better examples or infer a counterfactual survivor from an
open site. No ecological intervention is performed.

Verify every closing trace hash/counter against the prior full world/site censuses,
all old disturbance records, exact seed order, stage accounting, newborn identity,
and newly built ordinary replay/final framebuffer equality with the frozen frames.
Native tests cover state equality on/off, zeroed non-ecology output, error output
preservation, expiry, dormancy, sequential competition, capacities and raw thresholds.
Parser tests cover partial-prefix observation and malformed/incomplete streams.
Run existing host tests, default-ecology golden hashes, formatting and host/device
header guards. No firmware deployment is required for this host-only observer.

Freeze sources, build caches, binaries/model, input digests, commands, traces,
analyses and all eight native final screenshots in a new no-overwrite bundle.
Finish source edits before collection. Record results and limitations in the
repo and issue #30; discuss any next ecology change before implementing it.
