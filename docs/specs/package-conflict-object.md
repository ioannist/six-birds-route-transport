# Package Conflict Object

`package-conflict-object.v1` defines the comparison contract used to separate package conflict from projection difference, lens mismatch, and thin packaging metadata.

## Required fields

- `object_format_version`
- `package_conflict_object_id`
- `theorem_object_label`
- `frozen_slice_required`
- `fixed_support_fields`
- `projection_difference_fields`
- `lens_difference_fields`
- `packaging_surface_fields`
- `package_action_fields`
- `minimum_conflict_requirements`

## Semantics

- `fixed_support_fields` records the support object and evaluation-regime identifiers that must remain fixed.
- `projection_difference_fields` records fields that can vary while staying below lens mismatch.
- `lens_difference_fields` records record-algebra differences that may generate non-nestedness without yet implying package conflict.
- `packaging_surface_fields` records observable packaging-surface metadata such as source, selector branch, operator, family, and producer.
- `package_action_fields` is the subset of packaging-surface fields that count as evidence for a distinct package action.
- `minimum_conflict_requirements` records the minimal contract for package conflict proper.

## Validation rules

- `object_format_version` must equal `package-conflict-object.v1`.
- `frozen_slice_required` must be `true`.
- `fixed_support_fields` must include `support_object_id` and `evaluation_regime_id`.
- `packaging_surface_fields` must include `packaging_source`.
- `package_action_fields` must be a subset of `packaging_surface_fields`.
- `minimum_conflict_requirements` must include `package_action_divergence`.

## Interpretation rule

`packaging_source` is informative but not sufficient by itself. The object exists to require one more layer: evidence that distinct package actions are operating on one fixed support object.
