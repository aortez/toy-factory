# Reproductive shoot construction budget protocol

Test whether reserving a shoot completion path within 32 nodes restores flower
fertility while retaining the useful maintenance savings. This is one host-only
comparison on the same twelve frozen model/world pairs, not training or device
qualification. Keep ecology, eight seed slots, model bytes, weather, resource
costs, gardener-off setup, the 192-day horizon and renewal scoring unchanged.

## Fixed treatments

Use four arms. The existing unlimited and projected-32 arms must reproduce
their archived results and endpoint pixels exactly. A new eligible-32 control
rejects allocating bids that would exceed 32 nodes before priority ranking,
rather than converting each such proposal to WAIT. A new reserve arm uses that
same eligibility and additionally reserves a shoot completion path.

For a plant without any formed flower, choose its deepest active shoot, with
lowest node index breaking ties. Read that tip's actual maximum depth through
the existing observation API, including genome effects. The remaining path
cost is maximum depth minus current depth, clamped at zero. An allocating bid
qualifies only when its new node plus the remaining path fit within 32 nodes.
Extending the selected shoot consumes one of those reserved nodes. Other
shoots and roots must leave that space available.

Release the reservation once any flower has formed, or when no shoot remains.
Do not fabricate a FINISH action, remove tissue, grant resources, change neural
priorities or recurrent memory, or consume another random draw. This rule
reserves capacity, not resources or guaranteed access to an unoccupied site.
It does not promise that a controller will choose its eligible shoot.

Combine budget eligibility with the existing water eligibility for both new
arms. Preserve first-wins priority arbitration and the existing all-ineligible
fallback: only the original winner advances memory/nonce as WAIT. Nonallocating
cleanup, FINISH, and intrinsic WAIT bids retain their usual eligibility and
charges. The two new arms have distinct GLB1 identities; legacy GLC1 identities
and ordinary replay remain unchanged.

## Evidence and decision

Freeze protocol, binary, settings, models, inputs and source hashes before
collection. The construction input SHA-256 is
`9027651cd3da4d8a9a8703ef7a78d4ecc351faef35ece5fe4f2ee43f5605d2da`.
Collect full lifetime/seed ledgers, first-day descendant resource receipts,
founder construction and reproduction through day 64, and all-plant adult
resource accounts through day two. Reconcile budget arithmetic and the leader
against same-step tip queries; distinguish proposed from executed actions.

Repeat both new arms with traces, and replay without traces. Require exact
results, trace bytes, endpoint pixels and unchanged models. Rebuild both
legacy controls and require archived state, founder records and endpoint
pixels. Save every case, including failures, with a portable result and a
checksummed full bundle. Capture all four endpoints per world and a fixed
day-two reserve-versus-eligible panel to inspect early construction.

Compare reserve against eligible-32 to isolate the added reservation, and
against projected-32 and unlimited to retain the original question. Keep the
archived ordinary and veto baselines as additional comparisons. Reuse the
existing gates: retain score key and late child survivors in both climates,
improve a key or renewal confirmations, and introduce no earlier or new empty
world. Report species-resolved seeds, surviving children, final living species,
founder flowering and early mortality alongside those gates. Do not substitute
flower count or founder longevity for durable renewal.

Stop after this fixed comparison. If fertility improves but renewal or
retention fails, report that outcome without retuning the budget, forcing
flowering, relaxing gates or promoting a device policy.
