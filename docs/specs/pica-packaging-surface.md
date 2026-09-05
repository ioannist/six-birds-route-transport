# pica-packaging-surface

## Purpose
Defines the machine-readable summary surface for packaging-axis observability across one resolved PICA export bundle, combining packaging source, operator, family, and support-slice diversity into one reusable artifact.

## Versioning
- `schema_version`: `pica-packaging-surface.v1`

## Data model
- Required fields:
  - `schema_version: string`
  - `bundle_artifact: repo-relative path`
  - `export_bundle_id: string`
  - `packaging_operator_catalog_artifacts: array<repo-relative path>`
  - `packaging_selection_ledger_artifacts: array<repo-relative path>`
  - `distinct_packaging_operator_count: integer`
  - `distinct_packaging_family_count: integer`
  - `source_counts: object<string, integer>`
  - `selected_operator_counts: object<string, integer>`
  - `selected_family_counts: object<string, integer>`
  - `support_slice_count: integer`
- Optional fields:
  - `notes: array<string>`
  - `flags: array<string>`
  - `artifact_refs: object<string, repo-relative path>`
- Invariants:
  - counts are non-negative
  - artifact paths are repo-relative
  - source/operator/family counts are computed from the linked ledgers/catalogs, not independent free text

## Identifier conventions
- `export_bundle_id` is the authoritative linkage key back to the bundle.
- Operator/family/source identifiers remain whatever the linked catalog and selection ledger define; the surface does not rename them.

## Cross-file reference rules
- The bundle references the raw operator catalog(s) and selection ledger(s).
- This summary is derived from those raw artifacts and must not invent identifiers absent from them.
- Later packaging-axis searches may use this summary for screening, but must resolve raw ledgers for exact row-level evidence.

## Examples
```json
{
  "schema_version": "pica-packaging-surface.v1",
  "bundle_artifact": "experiments/contracts/pica/examples/pica-export-bundle.json",
  "export_bundle_id": "pica_export_bundle_example",
  "packaging_operator_catalog_artifacts": [
    "experiments/contracts/pica/examples/pica-packaging-operator-catalog.json"
  ],
  "packaging_selection_ledger_artifacts": [
    "experiments/contracts/pica/examples/pica-packaging-selection-ledger.json"
  ],
  "distinct_packaging_operator_count": 1,
  "distinct_packaging_family_count": 1,
  "source_counts": {
    "p5_from_p4": 1
  },
  "selected_operator_counts": {
    "packaging_operator_p5_from_p4": 1
  },
  "selected_family_counts": {
    "packaging_family_p5": 1
  },
  "support_slice_count": 1
}
```

## Validation notes
- Later packaging-axis work depends on source, operator, and family remaining distinct fields.
- A bundle with zero packaging artifacts may still validate, but later packaging-axis tickets must treat that as insufficient surface rather than positive evidence.
