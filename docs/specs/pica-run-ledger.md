# PICA Run Ledger

## Purpose

`pica-run-ledger.v1` is the per-run execution manifest for the bridge. It provides enough stable metadata for downstream discovery to reconstruct context candidates from observable records while keeping the observation table itself in the separate observable ledger artifact.

## Versioning

- Required field: `schema_version`
- Initial value: `pica-run-ledger.v1`

## Data model

### Required fields

- `schema_version`
  String. Must equal `pica-run-ledger.v1`.
- `run_id`
  Stable run identifier.
- `campaign_id`
- `point_id`
- `substrate_config_id`
- `mechanism_family_id`
- `preparation_id`
- `protocol_id`
- `seed`
  Integer.
- `trajectory_count`
  Integer.
- `protocol_steps`
  Array of protocol-step records.
- `closure_catalog_id`
- `closure_catalog_path`
- `observable_ledger_id`
- `observable_ledger_path`

### Protocol-step record required fields

- `step_index`
  Integer, zero-based.
- `protocol_step_id`
  Stable step reference.

### Protocol-step optional fields

- `stage_label`
- `action_label`

### Optional fields

- `enable_matrix_id`
- `notes`
  Array of strings.
- `flags`
  Array of explicit status/limitation labels.
- `debug_sidecars`
  Optional sidecar descriptors. These must never be required by downstream consumers.

### Invariants

- `protocol_steps` must be ordered by `step_index`.
- `step_index` values must be unique within a run.
- `protocol_step_id` values must be unique within a run.
- `closure_catalog_path` and `observable_ledger_path` must be repo-relative.

## Identifier conventions

- `run_id`
  Unique within the export bundle. Recommended semantics: deterministic function of point ID and seed.
- `protocol_step_id`
  Stable within the run. Recommended semantics: `{protocol_id}_step_{step_index}`.
- `observable_ledger_id`
  Stable observable table identifier for this run.
- `closure_catalog_id`
  Stable multilevel structure identifier for this run.

## Cross-file reference rules

- `observable_ledger_id` and `observable_ledger_path` must match the corresponding observable ledger artifact.
- `closure_catalog_id` and `closure_catalog_path` must match the corresponding closure catalog artifact.
- `protocol_step_id` is authoritative for step linkage; `step_index` is the ordered convenience field.

## Observable vs debug fields

- Required downstream bridge inputs:
  - run identity and provenance fields
  - `trajectory_count`
  - `protocol_steps`
  - closure catalog and observable ledger references
- Optional/internal-only:
  - `debug_sidecars`
  - producer-specific runtime metadata not needed for reconstruction

## Minimal valid example

```json
{
  "schema_version": "pica-run-ledger.v1",
  "run_id": "run_triadic_branch_seed123",
  "campaign_id": "campaign_example_v1",
  "point_id": "point_triadic_branch_seed123",
  "substrate_config_id": "substrate_config_triadic_branch_v1",
  "mechanism_family_id": "mechanism_family_triadic_branch",
  "enable_matrix_id": "enable_matrix_triadic_branch_default",
  "preparation_id": "prep_default",
  "protocol_id": "protocol_branch_hold_hold",
  "seed": 123,
  "trajectory_count": 2,
  "protocol_steps": [
    {
      "step_index": 0,
      "protocol_step_id": "protocol_branch_hold_hold_step_0",
      "stage_label": "branch"
    },
    {
      "step_index": 1,
      "protocol_step_id": "protocol_branch_hold_hold_step_1",
      "stage_label": "hold"
    }
  ],
  "closure_catalog_id": "closure_catalog_run_triadic_branch_seed123",
  "closure_catalog_path": "experiments/contracts/pica/examples/pica-closure-catalog.json",
  "observable_ledger_id": "observable_ledger_run_triadic_branch_seed123",
  "observable_ledger_path": "experiments/contracts/pica/examples/pica-observable-ledger.json",
  "notes": [
    "Contract example run only."
  ]
}
```

## Validation notes

- Validate exact schema version.
- Validate monotone `step_index` order and uniqueness.
- Validate that the referenced closure catalog and observable ledger IDs are present in the corresponding artifacts.
- Validate repo-relative artifact paths.
