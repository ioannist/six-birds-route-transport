# Lean Finite Obstruction Witness

This note records the Lean-side finite obstruction witness used for the minimal
global-realization scaffold.

## Witness shape

- Contexts: `left`, `right`
- Atom type: `Bool`
- Constraints:
  - `left:{true}` is paired with `right:{true}`
  - `left:{true}` is paired with `right:∅`

## Lean result

The theorem `SixBirdsEvent.TwoContextWitness.no_totalGlobalRealization`
shows that no nonempty finite family of global atoms can satisfy the constraints
while covering every atom in every context.

## Semantics alignment

- `GlobalAtom` assigns one atomic outcome to each context.
- `EventConstraint` records one hard event-pair membership constraint.
- `SatisfiesConstraint` requires left/right event-membership agreement.
- `TotalGlobalRealization` requires a nonempty finite family of satisfying
  global atoms that covers every atomic outcome in every context.

## Scope

This runbook is Lean-only scaffolding. It does not modify Python models,
experiment assets, or paper content.

## Build

```sh
cd lean && lake build
```
