# Survival-confirmed production dry-run v1

Follow up the allocation objective comparison by changing **only seed
confirmation**: require a full additional day of parent survival, but do not
veto credit for resource shortages. This is an exploratory rescore of already
inspected development data. The prior diagnostic already established 5/7 and
12/15 full-day parent survivals for the two producers; this is not a blind test.
Freeze this protocol before calculating the revised scores. Do not train, change
the environment, search weights, promote a model, or wire a fitness into training.

## Inputs and unchanged definitions

- Native allocation bundle: `artifacts/garden-allocation-v2`, manifest SHA-256
  `a7cb927521ab5188a1a1622cbfda4ffdd9d930843403fcc9b3cbe43774f98738`.
- Original objective bundle: `artifacts/garden-allocation-objectives-v1`, manifest
  SHA-256 `59a22c88d87bb7f66c6509f02d7efcb97ded37ce692284e851deafa645c4aa49`.
- Reverify both, including exact original score reproduction. Preserve the old
  bundles, scripts, definitions and exports unchanged.
- Retain all six cases and all four arms. Keep the original common exogenous
  patch/horizon windows, establishment gate `G`, alive-sample fraction `L`, raw
  seed term `R`, zero-shortage term `Q`, and their seven score variants unchanged.
  Birth samples are excluded; dead time stays in the common denominator. Windows
  shorter than one day are unscorable, not zero or imputed survival.

## Single revised term

Let `P` be the number of distinct plant-age day bins with at least one seed
purchase followed by a **fully observed additional day alive**, capped at four
and divided by four. Bins remain `floor((purchase - birth) / 3840)`.

Score `G + L + lambda * G * P`, with nominal `lambda = 1/4` and the unchanged
`1/8` and `1/2` sensitivities. Use exact fractions for comparisons and ties.
This is a parent-survival-confirmed **purchase** signal, not successful offspring.

Natural death at or before confirmation fails it. Confirmation exactly at the
last observed alive sample qualifies. Follow-up crossing a patch/horizon earns
no observed bonus and remains labeled censored, not failed. Shortages, resource
stores, body shape, action count and child births do not affect this score;
retain the native shortage severity, death and reproduction diagnostics.

Compare all ten variants within cases, in descriptive equal-case means, and in
each leave-one-case-out panel. Explicitly retain ties. The reference contexts
differ and cases share history: these are not independent trials or deployable
population-policy rankings. Report changes from the zero-shortage formula, not
only which arm wins. No outcome-dependent weight/cap adjustment follows.

## Arithmetic challenge cases and interpretation

Retain all earlier hand-built fixtures; add a repeatedly shortage-flagged survivor
and a burst straddling two age-day bins. Test that shortages cannot change `P`,
that multiple purchases within one bin cannot multiply credit, and that adjacent
bins can still reward two closely timed purchases. These are formula tests, not
new native simulations or proofs those strategies are reachable.

Keep the late-collapse counterexample. For an established producer versus an
established inactive survivor, calculate the break-even lost alive-sample time
as `lambda * min(confirmed bins, 4) / 4 * common window length`. Report one-bin
and full-cap examples at all three weights. This is a descriptive arithmetic
tradeoff, **not** a new survival-first objective or a chosen tolerance for death.

This experiment can test score semantics and the removal of a shortage veto.
It cannot resolve the value of a parent dying after successful reproduction:
these continuations have no germinated children. Do not claim sustainable
generational success, objective qualification or training readiness. Record a
bounded next decision supported by the results rather than silently starting
model search or changing the ecology.
