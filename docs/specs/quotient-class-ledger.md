# quotient-class-ledger

## Purpose

`quotient-class-ledger.v1` records the same-slice Leibniz quotient used by quotient-feasibility audits. It stores the selected context family, the aligned support members, the resulting quotient classes, and each class's induced atom assignment in every selected context.

## Versioning

- `ledger_format_version`: must equal `"quotient-class-ledger.v1"`

## Data model

Required fields:

- `ledger_format_version: string`
- `ledger_id: string`
- `source_discovered_context_family_artifact: repo-relative path`
- `source_event_package_artifact: repo-relative path`
- `source_shared_event_candidates_artifact: repo-relative path`
- `source_bundle_artifact: repo-relative path`
- `source_observable_ledger_artifacts: [repo-relative path, ...]`
- `same_slice_selection: object`
- `quotient_context_scope: "all_accepted_contexts"`
- `raw_support_count: integer`
- `quotient_class_count: integer`
- `selected_context_ids: [string, ...]`
- `quotient_classes: [object, ...]`

Optional fields:

- `notes: [string, ...]`
- `flags: [string, ...]`
- `metadata: object`

`same_slice_selection` requires:

- `preparation_id`
- `protocol_id`
- `protocol_step_id`
- `step_index`
- optional `resolution_id`
- `candidate_event_scope: "singleton_only" | "all"`

Each `quotient_classes[]` entry requires:

- `quotient_class_id`
- `member_trajectory_ids`
- `induced_context_atom_assignments`
- optional `induced_context_labels`
- optional `notes`

Invariants:

- `quotient_class_count == len(quotient_classes)`
- `raw_support_count >= quotient_class_count`
- all selected context ids and quotient class ids are unique
- each quotient class must have at least one member trajectory

## Identifier conventions

- `ledger_id` is unique within one audit run.
- `quotient_class_id` is unique within one ledger.

## Cross-file reference rules

- `source_discovered_context_family_artifact` identifies the accepted contexts that induce the quotient.
- `source_event_package_artifact` identifies the package whose atoms must be covered by surviving quotient classes.
- `source_shared_event_candidates_artifact` identifies the proposal pool used by the corresponding audit.

## Examples

```json
{
  "ledger_format_version": "quotient-class-ledger.v1",
  "ledger_id": "audit_exp104_ledger",
  "source_discovered_context_family_artifact": "experiments/instances/mechanism-axis/exp104_p6_row_all_n64_seed0/discovered-context-family.json",
  "source_event_package_artifact": "experiments/instances/mechanism-axis/exp104_p6_row_all_n64_seed0/event-package.json",
  "source_shared_event_candidates_artifact": "experiments/instances/mechanism-axis/exp104_p6_row_all_n64_seed0/shared-event-candidates.json",
  "source_bundle_artifact": "experiments/instances/mechanism-axis/exp104_p6_row_all_n64_seed0/pica-export-bundle.json",
  "source_observable_ledger_artifacts": [
    "experiments/instances/mechanism-axis/exp104_p6_row_all_n64_seed0/pica-observable-ledger.json"
  ],
  "same_slice_selection": {
    "preparation_id": "prep_pica_default",
    "protocol_id": "protocol_pica_multiscale_scan",
    "protocol_step_id": "protocol_pica_multiscale_scan_step_1",
    "step_index": 1,
    "resolution_id": "resolution_k_4",
    "candidate_event_scope": "singleton_only"
  },
  "quotient_context_scope": "all_accepted_contexts",
  "raw_support_count": 24,
  "quotient_class_count": 2,
  "selected_context_ids": ["ctx_left", "ctx_right"],
  "quotient_classes": [
    {
      "quotient_class_id": "qclass_0000",
      "member_trajectory_ids": ["traj_0000"],
      "induced_context_atom_assignments": {
        "ctx_left": "atom_group_0_1",
        "ctx_right": "atom_package_0_1"
      },
      "induced_context_labels": {
        "ctx_left": "group_0",
        "ctx_right": "package_0"
      }
    }
  ]
}
```

## Validation notes

- All artifact paths must be normalized repo-relative paths.
- Later tickets may rely on `induced_context_atom_assignments` to reconstruct event membership without re-reading the raw observable ledger.
