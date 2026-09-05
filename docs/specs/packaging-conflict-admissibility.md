# Packaging-Conflict Admissibility

## Purpose
This contract defines when a same-slice context pair may count as primary package-conflict evidence in commutator-guided search.

## Primary package-conflict rule
A context pair is `primary_packaging_conflict` only when all of the following hold:
- same `preparation_id`
- same `protocol_id`
- same `protocol_step_id`
- same `step_index`
- shared trajectory support exists within the same run family
- both projection families are primary-context eligible
- the pair differs by `closure_id` or `lens_id`
- the pair is supported by at least one nonzero relevant commutator under the active admissibility mode

## Comparative admissibility modes
- `p5_only`
  - relevant support is restricted to the configured `P5` neighborhood
- `p5_p6_combined`
  - relevant support may come from the configured `P5` neighborhood or the widened `P6` neighborhood

Pairs differing only by:
- `projection_id`
- `projection_field`

must not count as primary package-conflict evidence by themselves.

## Admissibility classes
- `primary_packaging_conflict`
- `probe_only`
- `diagnostic_only`

## Required machine-readable fields
Each row in `context-pair-structure.v1` used by package-conflict search must carry:
- `commutator_admissibility_mode`
- `same_frozen_slice`
- `primary_identity_admissible`
- `packaging_conflict_supported`
- `commutator_support_pairs`
- `primary_packaging_conflict_admissible`
- `packaging_conflict_admissibility_class`
- `admissibility_reason`

## Interpretation notes
- non-nestedness alone is not sufficient
- same-slice alignment alone is not sufficient
- projection-only diversity is secondary unless accompanied by closure/lens package-conflict evidence
