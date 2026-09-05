# PICA Observable Ledger

## Purpose

`pica-observable-ledger.v1` is the row-level observable bridge artifact that later discovery and package-building will consume directly. It records trajectory-step observations keyed by protocol step, level, resolution, closure, and lens, without making hidden-state identity a required input. The format also declares whether the ledger is only an aggregate summary or a discovery-grade per-trajectory ledger that preserves same-support alignment across contexts.

## Versioning

- Required field: `schema_version`
- Initial value: `pica-observable-ledger.v1`

## Data model

### Required fields

- `schema_version`
  String. Must equal `pica-observable-ledger.v1`.
- `observable_ledger_id`
  Stable observable ledger identifier.
- `campaign_id`
- `run_id`
- `point_id`
- `observation_granularity`
  `"aggregate_summary"` or `"per_trajectory"`.
- `cooccurrence_scope`
  `"none"`, `"within_run"`, or `"within_run_and_trajectory"`.
- `trajectory_count`
  Integer count of distinct `trajectory_id` values represented by the ledger.
- `supports_structural_probe_conditioning`
  Boolean readiness flag derived from the actual observable granularity.
- `row_count`
  Integer.
- `rows`
  Array of row records.

### Row record required fields

- `trajectory_id`
- `step_index`
- `protocol_step_id`
- `preparation_id`
- `protocol_id`
- `level_id`
- `resolution_id`
- `closure_id`
- `lens_id`
- `observation_label`

### Row record optional but strongly encouraged fields

- `route_label`
- `phase_label`
- `macrostate_label`
- `observation_payload`
  Flat or nested JSON payload.

### Optional top-level fields

- `notes`
  Array of strings.
- `flags`
  Array of explicit status/limitation labels.
- `debug_sidecars`
  Optional sidecar descriptors for hidden/internal state. These must not be required by downstream consumers.

### Invariants

- `row_count` must equal `len(rows)`.
- `trajectory_count` must equal the number of distinct `trajectory_id` values in `rows`.
- Every row’s `run_id` is inherited from the top-level artifact and must not vary.
- Every `level_id`, `resolution_id`, `closure_id`, and `lens_id` must resolve in the corresponding closure catalog.
- `(trajectory_id, step_index, protocol_step_id, lens_id)` should be unique within the ledger unless the producer explicitly documents multiplicity.
- `supports_structural_probe_conditioning = true` is allowed only when:
  - `observation_granularity = "per_trajectory"`
  - `cooccurrence_scope = "within_run_and_trajectory"`

## Identifier conventions

- `observable_ledger_id`
  Unique within the export bundle.
- `trajectory_id`
  Stable within a run.
- `protocol_step_id`
  Stable within the run and aligned with the run ledger.
- `level_id`, `resolution_id`, `closure_id`, `lens_id`
  Must match the closure catalog exactly.

## Cross-file reference rules

- The observable ledger is linked to the run ledger by `run_id` and to the closure catalog by the structural IDs embedded in each row.
- Later discovery in this repo should consume observable-ledger rows plus the closure catalog, not hidden-state IDs.
- Route-capable interventions may use `route_label` when present, but must preserve `not_applicable` if the field is absent.
- Aggregate-summary ledgers remain valid bridge artifacts, but they are not discovery-grade by default.

## Observable vs debug fields

- Required downstream bridge inputs:
  - all required row fields listed above
- Discovery-grade required inputs for structural inference:
  - `observation_granularity = "per_trajectory"`
  - `cooccurrence_scope = "within_run_and_trajectory"`
  - `supports_structural_probe_conditioning = true`
- Optional/internal-only:
  - `route_label`
  - `phase_label`
  - `macrostate_label`
  - `observation_payload`
  - any hidden-state sidecar references

## Minimal valid example

```json
{
  "schema_version": "pica-observable-ledger.v1",
  "observable_ledger_id": "observable_ledger_run_triadic_branch_seed123",
  "campaign_id": "campaign_example_v1",
  "run_id": "run_triadic_branch_seed123",
  "point_id": "point_triadic_branch_seed123",
  "observation_granularity": "per_trajectory",
  "cooccurrence_scope": "within_run_and_trajectory",
  "trajectory_count": 2,
  "supports_structural_probe_conditioning": true,
  "row_count": 4,
  "rows": [
    {
      "trajectory_id": "traj_0000",
      "step_index": 0,
      "protocol_step_id": "protocol_branch_hold_hold_step_0",
      "preparation_id": "prep_default",
      "protocol_id": "protocol_branch_hold_hold",
      "level_id": "level_macro",
      "resolution_id": "resolution_macro_r1",
      "closure_id": "closure_branch_record",
      "lens_id": "lens_record_main",
      "observation_label": "obs_left_A",
      "route_label": "route_left",
      "phase_label": "phase_branch",
      "macrostate_label": "macro_A",
      "observation_payload": {
        "outcome": "A"
      }
    },
    {
      "trajectory_id": "traj_0000",
      "step_index": 1,
      "protocol_step_id": "protocol_branch_hold_hold_step_1",
      "preparation_id": "prep_default",
      "protocol_id": "protocol_branch_hold_hold",
      "level_id": "level_macro",
      "resolution_id": "resolution_macro_r1",
      "closure_id": "closure_branch_record",
      "lens_id": "lens_record_main",
      "observation_label": "obs_right_B",
      "route_label": "route_left",
      "phase_label": "phase_hold",
      "macrostate_label": "macro_B",
      "observation_payload": {
        "outcome": "B"
      }
    },
    {
      "trajectory_id": "traj_0001",
      "step_index": 0,
      "protocol_step_id": "protocol_branch_hold_hold_step_0",
      "preparation_id": "prep_default",
      "protocol_id": "protocol_branch_hold_hold",
      "level_id": "level_macro",
      "resolution_id": "resolution_macro_r1",
      "closure_id": "closure_branch_record",
      "lens_id": "lens_record_main",
      "observation_label": "obs_left_B",
      "route_label": "route_right",
      "phase_label": "phase_branch",
      "macrostate_label": "macro_B",
      "observation_payload": {
        "outcome": "B"
      }
    },
    {
      "trajectory_id": "traj_0001",
      "step_index": 1,
      "protocol_step_id": "protocol_branch_hold_hold_step_1",
      "preparation_id": "prep_default",
      "protocol_id": "protocol_branch_hold_hold",
      "level_id": "level_macro",
      "resolution_id": "resolution_macro_r1",
      "closure_id": "closure_branch_record",
      "lens_id": "lens_record_main",
      "observation_label": "obs_right_A",
      "route_label": "route_right",
      "phase_label": "phase_hold",
      "macrostate_label": "macro_A",
      "observation_payload": {
        "outcome": "A"
      }
    }
  ],
  "notes": [
    "Contract example observable ledger only."
  ]
}
```

## Validation notes

- Validate exact schema version.
- Validate `row_count`.
- Validate `trajectory_count`.
- Validate that every row contains the required observable fields.
- Validate cross-artifact referential integrity against the run ledger and closure catalog.
- Validate that any debug sidecar references are explicitly marked optional.
- Reject `supports_structural_probe_conditioning = true` when the ledger is not per-trajectory and same-support aligned.
