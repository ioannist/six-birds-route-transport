# Projection-Family Admissibility

## Purpose
`projection-family-admissibility.v1` records which projection families in a frozen-slice PICA search are allowed to generate primary contexts and whether those families actually vary within the selected frozen slice.

## Versioning
- Version field: `table_format_version`
- Initial value: `projection-family-admissibility.v1`

## Data model
Required top-level fields:
- `table_format_version: string`
- `search_id: string`
- `row_count: int`
- `rows: list[projection-family-admissibility-row]`

Required row fields:
- `point_id`
- `projection_id`
- `source_field`
- `projection_kind`
- `allowed_roles`
- `row_count`
- `unique_value_count`
- `varies_within_frozen_slice`

Allowed `projection_kind` values:
- `packaging_outcome`
- `derived_row_outcome`
- `closure_summary`
- `route_summary`

Allowed role values:
- `primary_context`
- `probe_only`
- `diagnostic_only`

## Scientific rule encoded
Primary contexts may be built only from rows where:
- `projection_kind` is `packaging_outcome` or `derived_row_outcome`
- and `allowed_roles` contains `primary_context`

Rows marked:
- `closure_summary`
- or `route_summary`

must not be used as primary shared-event identity sources in frozen-slice obstruction search.

## Minimal valid example
```json
{
  "table_format_version": "projection-family-admissibility.v1",
  "search_id": "demo_frozen_slice",
  "row_count": 2,
  "rows": [
    {
      "point_id": "demo_point",
      "projection_id": "obs_primary",
      "source_field": "observation_label",
      "projection_kind": "packaging_outcome",
      "allowed_roles": ["primary_context"],
      "row_count": 24,
      "unique_value_count": 4,
      "varies_within_frozen_slice": true,
      "flags": ["varies_within_frozen_slice"]
    },
    {
      "point_id": "demo_point",
      "projection_id": "macro_gap_diag",
      "source_field": "macro_gap",
      "projection_kind": "closure_summary",
      "allowed_roles": ["diagnostic_only"],
      "row_count": 24,
      "unique_value_count": 1,
      "varies_within_frozen_slice": false,
      "flags": ["not_primary_context_eligible", "constant_within_frozen_slice"]
    }
  ]
}
```

## Validation notes
Machine-checkable invariants:
- version string matches `projection-family-admissibility.v1`
- `row_count == len(rows)`
- all IDs and `source_field` values are non-empty
- `allowed_roles` is non-empty
- all count fields are non-negative
