# Package Conflict Relation

`package-conflict-relation.v1` records one adjudicated package-comparison relation on a frozen-slice/shared-support object.

## Required fields

- `relation_format_version`
- `relation_id`
- `package_conflict_object_ref`
- `left_context_ref`
- `right_context_ref`
- `comparison_mode`
- `same_frozen_support`
- `same_evaluation_regime`
- `divergence_fields`
- `package_action_evidence`
- `relation_level`
- `classification`
- `obstruction_status`
- `primary_refs`

## Relation ladder

`relation_level` is ordered as follows.

1. `projection_difference_only`
2. `lens_mismatch_only`
3. `packaging_surface_divergence`
4. `package_conflict_proper`
5. `packaging_obstruction`

`classification` refines the relation level and records the best current explanation for the relation:

- `projection_difference_only`
- `lens_mismatch_only`
- `selector_branch_package_divergence`
- `operator_or_family_package_divergence`
- `strict_extension_package_conflict`
- `package_conflict_with_obstruction`

`obstruction_status` records whether the compared relation reaches the quotient-backed theorem-facing threshold:

- `none`
- `candidate_subset_quotient_witness`
- `accepted_proposal_obstruction`

## Validation rules

- `relation_format_version` must equal `package-conflict-relation.v1`.
- `package_conflict_proper` and `packaging_obstruction` require `same_frozen_support = true` and `same_evaluation_regime = true`.
- `package_conflict_proper` and `packaging_obstruction` require non-empty `package_action_evidence`.
- `projection_difference_only` and `lens_mismatch_only` cannot carry obstruction.
- `packaging_obstruction` requires `obstruction_status = accepted_proposal_obstruction`.

## Interpretation rule

The distinction between `relation_level` and `classification` is deliberate.

- `relation_level` says how strong the relation is.
- `classification` says what kind of package divergence best explains it.
- `obstruction_status` says whether the theorem-facing global-package failure is present.

This keeps package conflict distinct from both lens mismatch and packaging metadata alone.
