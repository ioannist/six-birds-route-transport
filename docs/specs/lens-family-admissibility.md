# Lens-Family Admissibility

## Purpose

`lens-family-admissibility.v1` records which lens / projection families are eligible for primary same-slice lens-axis context generation on a fixed mechanism and packaging surface.

## Versioning

- Version field: `catalog_format_version`
- Initial value: `lens-family-admissibility.v1`

## Data model

Required top-level fields:
- `catalog_format_version`
- `search_id`
- `axis = "lens"`
- `fixed_mechanism_label`
- `fixed_packaging_family_label`
- `row_count`
- `rows`

Required row fields:
- `projection_id`
- `source_field`
- `projection_kind`
- `same_slice_eligible`
- `allowed_roles`
- `allowed_role`

Optional row fields:
- `notes`
- `flags`

Invariants:
- one row per `projection_id`
- `allowed_role` must be a member of `allowed_roles`
- only `packaging_outcome` and `derived_row_outcome` families should be marked `same_slice_eligible = true`

## Identifier conventions

- `projection_id` matches one projection family from the parent search config
- `search_id` matches the parent lens-axis search

## Cross-file reference rules

- the emitted admissibility catalog should be derived from the exact `projection_families` block in the parent config
- rows in `lens-axis-row.v1` must reference only projection IDs present here

## Examples

```json
{
  "catalog_format_version": "lens-family-admissibility.v1",
  "search_id": "lens_axis_example",
  "axis": "lens",
  "fixed_mechanism_label": "exp104_p6_row_all_n64",
  "fixed_packaging_family_label": "bridge_default_packaging_selector",
  "row_count": 2,
  "rows": [
    {
      "projection_id": "obs_primary",
      "source_field": "observation_label",
      "projection_kind": "packaging_outcome",
      "same_slice_eligible": true,
      "allowed_roles": ["primary_context"],
      "allowed_role": "primary_context"
    },
    {
      "projection_id": "macro_gap_diag",
      "source_field": "macro_gap",
      "projection_kind": "closure_summary",
      "same_slice_eligible": false,
      "allowed_roles": ["diagnostic_only"],
      "allowed_role": "diagnostic_only"
    }
  ]
}
```

## Validation notes

- later lens-axis searches may use this catalog to prove that closure-summary and route-summary families stayed out of the primary context pool
