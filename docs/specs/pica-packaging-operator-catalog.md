# pica-packaging-operator-catalog

## Purpose
Defines the machine-readable catalog of packaging operators and packaging families exposed from a PICA export bundle so later packaging-axis searches can compare producer identity, operator identity, and family identity without collapsing them.

## Versioning
- `schema_version`: `pica-packaging-operator-catalog.v1`

## Data model
- Required fields:
  - `schema_version: string`
  - `packaging_operator_catalog_id: string`
  - `export_bundle_id: string`
  - `campaign_id: string`
  - `run_id: string`
  - `point_id: string`
  - `row_count: integer`
  - `rows: array<object>`
- Row required fields:
  - `packaging_operator_id: string`
  - `packaging_family_id: string`
  - `packaging_source: string`
  - `producer_id: string`
  - `operator_label: string`
  - `family_label: string`
  - `operator_kind: string`
- Row optional fields:
  - `parameter_digest: string|null`
  - `support_metadata: object`
  - `notes: array<string>`
  - `flags: array<string>`
- Invariants:
  - `row_count == len(rows)`
  - `packaging_operator_id` is unique within one catalog
  - operator, family, and producer identifiers are non-empty and must not be collapsed into one field by contract

## Identifier conventions
- `packaging_operator_catalog_id` is unique within one export bundle.
- `packaging_operator_id` is the stable selected package-action identity used for comparison across runs in one campaign family.
- `packaging_family_id` is a broader grouping that may contain multiple operators.
- `producer_id` identifies the upstream producer/source route and may coincide with neither operator nor family.

## Cross-file reference rules
- `export_bundle_id` must match the enclosing `pica-export-bundle`.
- The bundle references this file through `packaging_operator_catalogs[*]`.
- `pica-packaging-selection-ledger` rows must use `packaging_operator_id` and `packaging_family_id` values present here.
- `pica-packaging-surface` summaries aggregate one or more catalogs of this kind.

## Examples
```json
{
  "schema_version": "pica-packaging-operator-catalog.v1",
  "packaging_operator_catalog_id": "packaging_operator_catalog_example",
  "export_bundle_id": "pica_export_bundle_example",
  "campaign_id": "campaign_example",
  "run_id": "run_example",
  "point_id": "point_example",
  "row_count": 1,
  "rows": [
    {
      "packaging_operator_id": "packaging_operator_p5_from_p4",
      "packaging_family_id": "packaging_family_p5",
      "packaging_source": "p5_from_p4",
      "producer_id": "p4",
      "operator_label": "p5 from p4",
      "family_label": "p5",
      "operator_kind": "bridge_selector_outcome",
      "parameter_digest": "abc123def456",
      "support_metadata": {
        "selector_token": "p5"
      }
    }
  ]
}
```

## Validation notes
- Later tickets may rely on stable operator/family IDs, so bridge-level identity derivations must be explicit and reproducible.
- Catalog rows may be bridge-derived, but if they are bridge-derived the derivation rule must be encoded in metadata/notes rather than implied.
