# PICA Commutator Catalog

## Purpose
`pica-commutator-catalog.v1` records structured commutator diagnostics exported from PICA so downstream discovery and search can query package-conflict evidence without scraping stdout.

## Versioning
- Version field: `schema_version`
- Initial value: `pica-commutator-catalog.v1`

## Data model
Required top-level fields:
- `schema_version: string`
- `commutator_catalog_id: string`
- `campaign_id: string`
- `run_id: string`
- `point_id: string`
- `row_count: int`
- `rows: list[pica-commutator-entry]`

Required row fields:
- `pair_id`
- `primitive_pair`
- `metric_name`
- `metric_value`
- `nonzero`

Optional row fields:
- `notes`
- `flags`

## Required minimum pairs
For package-conflict search the export must cover at least:
- `[P1,P5]`
- `[P2,P5]`
- `[P4,P5]`

Additional pairs may be emitted when available.

## Minimal valid example
```json
{
  "schema_version": "pica-commutator-catalog.v1",
  "commutator_catalog_id": "commutator_catalog_demo_run",
  "campaign_id": "demo_campaign",
  "run_id": "demo_run",
  "point_id": "demo_point",
  "row_count": 3,
  "rows": [
    {
      "pair_id": "[P1,P5]",
      "primitive_pair": "P1/P5",
      "metric_name": "fraction_of_states_whose_package_changed_after_p1",
      "metric_value": 0.25,
      "nonzero": true,
      "flags": ["package_conflict_proxy"]
    }
  ]
}
```

## Validation notes
- `row_count == len(rows)`
- `pair_id` values are unique within a catalog
- `metric_value` is numeric
- all IDs are non-empty
