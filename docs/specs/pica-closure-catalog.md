# PICA Closure Catalog

## Purpose

`pica-closure-catalog.v1` exposes the multilevel and multi-resolution structure that this repo will later consume for context discovery and provenance mapping. It is the bridge artifact that makes levels, resolutions, closures, and lenses explicit without forcing downstream discovery to infer vertical structure from raw observations alone.

## Versioning

- Required field: `schema_version`
- Initial value: `pica-closure-catalog.v1`

## Data model

### Required fields

- `schema_version`
  String. Must equal `pica-closure-catalog.v1`.
- `closure_catalog_id`
  Stable catalog identifier.
- `campaign_id`
- `run_id`
- `point_id`
- `levels`
  Array of level records.
- `resolutions`
  Array of resolution records.
- `closures`
  Array of closure records.
- `lenses`
  Array of lens records.

### Level record required fields

- `level_id`
- `label`
- `role`

### Resolution record required fields

- `resolution_id`
- `level_id`
- `label`
- `role`

### Closure record required fields

- `closure_id`
- `level_id`
- `resolution_id`
- `label`
- `role`

### Lens record required fields

- `lens_id`
- `level_id`
- `resolution_id`
- `closure_id`
- `label`
- `role`

### Optional fields

- `parent_level_id`
- `parent_resolution_id`
- `parent_closure_id`
- `ancestor_lens_id`
- `support_metadata`
  Object with audit/support metadata.
- `notes`
  Array of strings.
- `flags`
  Array of explicit status/limitation labels.
- `debug_metadata`
  Optional internal descriptors. These must not be required bridge inputs.

### Invariants

- Every `resolution.level_id` must exist in `levels`.
- Every `closure.level_id` and `closure.resolution_id` must resolve.
- Every `lens.level_id`, `lens.resolution_id`, and `lens.closure_id` must resolve.
- IDs must be unique within their respective arrays.

## Identifier conventions

- `closure_catalog_id`
  Unique within the bundle.
- `level_id`
  Stable label for one vertical analysis level.
- `resolution_id`
  Stable label for one partition or resolution within a level.
- `closure_id`
  Stable label for one closure candidate or accepted closure object.
- `lens_id`
  Stable label for one observation lens.

## Cross-file reference rules

- The observable ledger must reference only `level_id`, `resolution_id`, `closure_id`, and `lens_id` values that appear here.
- Downstream discovery should use the closure catalog plus the observable ledger to define context families.
- Closure catalog IDs are authoritative; labels are descriptive only.

## Observable vs debug fields

- Required downstream bridge inputs:
  - `levels`
  - `resolutions`
  - `closures`
  - `lenses`
- Optional/internal-only:
  - `support_metadata`
  - `debug_metadata`
  - producer-specific audit internals

## Minimal valid example

```json
{
  "schema_version": "pica-closure-catalog.v1",
  "closure_catalog_id": "closure_catalog_run_triadic_branch_seed123",
  "campaign_id": "campaign_example_v1",
  "run_id": "run_triadic_branch_seed123",
  "point_id": "point_triadic_branch_seed123",
  "levels": [
    {
      "level_id": "level_macro",
      "label": "macro",
      "role": "observed_level"
    }
  ],
  "resolutions": [
    {
      "resolution_id": "resolution_macro_r1",
      "level_id": "level_macro",
      "label": "retained_partition_r1",
      "role": "retained_partition"
    }
  ],
  "closures": [
    {
      "closure_id": "closure_branch_record",
      "level_id": "level_macro",
      "resolution_id": "resolution_macro_r1",
      "label": "branch_record",
      "role": "accepted_closure",
      "support_metadata": {
        "support_kind": "audit_record",
        "support_value": 0.92
      }
    }
  ],
  "lenses": [
    {
      "lens_id": "lens_record_main",
      "level_id": "level_macro",
      "resolution_id": "resolution_macro_r1",
      "closure_id": "closure_branch_record",
      "label": "record_main",
      "role": "observable_lens"
    }
  ],
  "notes": [
    "Contract example closure catalog only."
  ]
}
```

## Validation notes

- Validate referential integrity across levels, resolutions, closures, and lenses.
- Validate uniqueness of all catalog IDs.
- Validate that no observable-ledger-required ID is missing.
