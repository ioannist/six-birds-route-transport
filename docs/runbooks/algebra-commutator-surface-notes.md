# Algebra Commutator Surface Notes

This note is for the agent working in `six-birds-algebra`.

Its purpose is narrow:
- summarize what was learned while extending the vendored PICA commutator surface in `six-birds-event-package`
- suggest a safe order for adding missing pairs in the algebra repo
- avoid pushing search-specific assumptions into the algebra repo

## Current practical lesson

The easiest way to expand pair coverage without breaking local contracts is:

1. keep the existing implemented pairs stable
2. add one neighborhood at a time
3. give each new pair a reducer with a clear operational meaning
4. export the new rows in the same machine-readable shape as existing rows
5. add one regression check that proves the new pair is present in the emitted panel

Do not start by trying to redesign the full algebra layer.
Start by extending the measured surface in small, semantically legible increments.

## Recommended order

The most natural next order is:

1. finish one neighborhood completely
2. then move to the next

Given the current split between repos, the most useful order is:

1. complete the `P5` neighborhood
   - `[P1,P5]`
   - `[P2,P5]`
   - `[P4,P5]`
   - `[P3,P5]`
   - `[P5,P6]`
2. then revisit the `P3` neighborhood
   - `[P1,P3]`
   - `[P2,P3]`
   - `[P3,P4]`
   - `[P3,P6]`

Reason:
- `P5` is already visibly relevant to package conflict
- `P3` and `P6` are likely where route/audit interactions become informative
- `P3/P5` and `P5/P6` are the most plausible currently-missing links if packaging is context-relative rather than intrinsic

## Reducer standard

For each missing pair, use one explicit reducer and document which class it belongs to:

- `kernel_commutator`
- `partition_change_proxy`
- `packaging_change_proxy`
- `audit_sensitivity_proxy`
- `route_sensitivity_proxy`

Do not treat all nonzero reducers as the same kind of object.
The row should carry enough metadata that downstream users can distinguish:

- genuine kernel-order dependence
- versus a derived comparison over labels, partitions, budgets, or routes

## Safe implementation rule

Only promote a missing pair from placeholder to implemented when all three are true:

1. the reducer has a concrete operational interpretation
2. the reducer is normalized or at least scale-legible
3. the emitted value can be explained without handwaving

If a pair does not yet meet that bar, keep it as an explicit placeholder.
An honest placeholder is better than an artificial metric.

## Export rule

Keep the output panel explicit over the full pair space, but mark pair status clearly:

- implemented reducer
- explicit placeholder zero
- reserved / not yet instrumented

The important thing is to prevent downstream code from confusing:

- “measured zero”
- with
- “construction-trivial placeholder”

## Cross-repo note

The event-package repo now carries a real `P5`-side surface and a real `P6`-side surface in the vendored copy:

- `[P1,P5]`, `[P2,P5]`, `[P4,P5]`
- `[P1,P6]`, `[P2,P6]`, `[P4,P6]`

That does **not** mean the algebra repo should mirror the event-package repo blindly.
It does mean there is now a concrete reference implementation showing:

- a safe way to add new pair rows
- a safe way to keep existing rows intact
- and a safe way to export mixed commutator/proxy rows without changing downstream schema shape

## Main scientific caution

Packaging-side observables look useful, but they may be context-relative derived features rather than intrinsic primitive labels.

So:
- adding more `P5` pairs is worthwhile
- but it should not be assumed in advance that `P5` alone closes the algebra question

That is exactly why `P3,P5` and `P5,P6` are high-value next candidates.

## Minimal success condition

A good next step in the algebra repo is not “full closure.”

A good next step is:

- add one or two missing pairs with clear semantics
- emit them in the existing panel
- verify that the new rows are present and numerically stable on a bounded slice
- then reassess support patterns before adding more

That keeps the surface expanding without losing interpretability.
