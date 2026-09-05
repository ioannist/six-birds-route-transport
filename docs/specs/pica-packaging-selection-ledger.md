# pica-packaging-selection-ledger

## Purpose
Defines the row-level packaging selection ledger for observable support slices so later packaging-axis searches can compare selected operators and families on aligned run/preparation/protocol/step/closure support.

## Versioning
- `schema_version`: `pica-packaging-selection-ledger.v1`

## Data model
- Required fields:
  - `schema_version: string`
  - `packaging_selection_ledger_id: string`
  - `export_bundle_id: string`
  - `campaign_id: string`
  - `run_id: string`
  - `point_id: string`
  - `row_count: integer`
  - `rows: array<object>`
- Row required fields:
  - `selection_row_id: string`
  - `run_id: string`
  - `point_id: string`
  - `preparation_id: string`
  - `protocol_id: string`
  - `protocol_step_id: string`
  - `step_index: integer`
  - `level_id: string`
  - `resolution_id: string`
  - `closure_id: string`
  - `packaging_operator_id: string`
  - `packaging_family_id: string`
  - `packaging_source: string`
  - `selection_status: "selected" | "candidate" | "not_available"`
- Row support scope:
  - at least one of `trajectory_id` or `support_group_id` must be present
- Row optional fields:
  - `lens_id: string|null`
  - `candidate_operator_ids: array<string>`
  - `support_scope_metadata: object`
  - `candidate_set_metadata: object`
  - `notes: array<string>`
  - `flags: array<string>`
- Invariants:
  - `row_count == len(rows)`
  - `selection_row_id` is unique within one ledger
  - support indexing must be explicit at run/preparation/protocol/step/closure granularity or finer

## Identifier conventions
- `selection_row_id` is unique within one ledger and should remain stable under repeated exports of the same run family.
- `support_group_id` groups rows that share the same support slice even if they remain trajectory-level within that slice.

## Cross-file reference rules
- `export_bundle_id` must match the enclosing bundle.
- `packaging_operator_id` and `packaging_family_id` must resolve to a row in the paired operator catalog.
- Provenance entries may refer to `packaging_selection_ledger_id`, `packaging_selection_row_id`, `packaging_operator_id`, `packaging_family_id`, and `packaging_source`.
- `pica-packaging-surface` summaries aggregate rows from one or more ledgers of this kind.

## Examples
```json
{
  "schema_version": "pica-packaging-selection-ledger.v1",
  "packaging_selection_ledger_id": "packaging_selection_ledger_example",
  "export_bundle_id": "pica_export_bundle_example",
  "campaign_id": "campaign_example",
  "run_id": "run_example",
  "point_id": "point_example",
  "row_count": 1,
  "rows": [
    {
      "selection_row_id": "selection_row_example",
      "run_id": "run_example",
      "point_id": "point_example",
      "preparation_id": "prep_default",
      "protocol_id": "protocol_scan",
      "protocol_step_id": "protocol_scan_step_0",
      "step_index": 0,
      "trajectory_id": "traj_0000",
      "support_group_id": "run_example:step0:closure_pkg",
      "level_id": "level_l0",
      "resolution_id": "resolution_k_2",
      "closure_id": "closure_pkg_k_2",
      "lens_id": "lens_p5_k_2",
      "packaging_operator_id": "packaging_operator_p5_from_p4",
      "packaging_family_id": "packaging_family_p5",
      "packaging_source": "p5_from_p4",
      "selection_status": "selected",
      "candidate_operator_ids": [
        "packaging_operator_p5_from_p4"
      ]
    }
  ]
}
```

## Validation notes
- The ledger must honestly represent actual support granularity; if trajectory-level packaging selection is unavailable, the contract should use `support_group_id` rather than inventing per-trajectory identity.
- Later tickets will rely on these rows for frozen-slice packaging comparisons, so run/protocol/step linkage must be machine-checkable.
