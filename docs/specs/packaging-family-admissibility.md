# Packaging-Family Admissibility

## Purpose

`packaging-family-admissibility.v1` records which packaging selector-branch outcomes are eligible for primary same-support package-conflict comparisons on a fixed mechanism and fixed primary lens.

## Versioning

- Version field: `catalog_format_version`
- Initial value: `packaging-family-admissibility.v1`

## Data model

Required top-level fields:
- `catalog_format_version`
- `search_id`
- `fixed_mechanism_label`
- `fixed_lens_label`
- `row_count`
- `rows`

Required row fields:
- `packaging_operator_id`
- `packaging_family_id`
- `packaging_source`
- `selector_branch_outcome`
- `same_support_eligible`
- `allowed_roles`
- `allowed_role`

Optional row fields:
- `notes`
- `flags`

Invariants:
- one row per `(packaging_operator_id, packaging_family_id, packaging_source, selector_branch_outcome)` tuple
- `allowed_role` must be a member of `allowed_roles`
- selector-branch outcomes such as `selected_packaging_branch` and `pre_selector_branch` may share the same operator / family IDs when the scientific variation comes from selector outcome rather than catalog identity

## Identifier conventions

- `search_id` matches the parent packaging-axis search
- `selector_branch_outcome` is the branch-level identity used by package-pair diagnostics

## Cross-file reference rules

- the emitted admissibility catalog should be derived from the fixed merged bundle and packaging-selection ledger used by the parent search
- rows in `packaging-axis-row.v1` must reference only selector-branch outcomes present here

## Example

```json
{
  "catalog_format_version": "packaging-family-admissibility.v1",
  "search_id": "packaging_axis_example",
  "fixed_mechanism_label": "exp104_p6_row_all_n64",
  "fixed_lens_label": "obs_primary_observation_label",
  "row_count": 2,
  "rows": [
    {
      "packaging_operator_id": "packaging_operator_p5_from_p4",
      "packaging_family_id": "packaging_family_p5",
      "packaging_source": "p5_from_p4",
      "selector_branch_outcome": "selected_packaging_branch",
      "same_support_eligible": true,
      "allowed_roles": ["primary_context_pair", "probe_only"],
      "allowed_role": "primary_context_pair"
    },
    {
      "packaging_operator_id": "packaging_operator_p5_from_p4",
      "packaging_family_id": "packaging_family_p5",
      "packaging_source": "p5_from_p4",
      "selector_branch_outcome": "pre_selector_branch",
      "same_support_eligible": true,
      "allowed_roles": ["primary_context_pair", "probe_only"],
      "allowed_role": "primary_context_pair"
    }
  ]
}
```

## Validation notes

- later packaging-axis searches may rely on this catalog to prove that projection-only or stage-only differences were kept out of the primary package-conflict pool
