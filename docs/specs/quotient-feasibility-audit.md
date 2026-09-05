# quotient-feasibility-audit

## Purpose

`quotient-feasibility-audit.v1` configures a quotient-backed exact feasibility audit over an existing discovered event package. It fixes the source artifacts, the same-slice candidate pool used for witness search, and the control/witness proposal subsets to evaluate.

## Versioning

- `audit_format_version`: must equal `"quotient-feasibility-audit.v1"`

## Data model

Required fields:

- `audit_format_version: string`
- `audit_id: string`
- `source_event_package_artifact: repo-relative path`
- `source_discovered_context_family_artifact: repo-relative path`
- `source_shared_event_candidates_artifact: repo-relative path`
- `same_slice_selection: object`

Optional fields:

- `source_package_provenance_artifact: repo-relative path`
- `quotient_context_scope: "all_accepted_contexts"`
- `candidate_pool_mode: "same_slice_candidate_pool"`
- `subset_search: object`
- `forced_candidate_ids: [string, ...]`
- `natural_pairing_candidate_ids: [string, ...]`
- `output_category: string`
- `output_label: string`
- `metadata: object`

`subset_search` requires:

- `enabled: bool`
- `max_subset_size: positive integer`
- `stop_at_first_witness: bool`

Invariants:

- all candidate id lists are unique
- source artifact paths must be repo-relative
- the audit does not alter acceptance; it only changes the exact/global atom basis

## Identifier conventions

- `audit_id` is unique within one audit family.
- `forced_candidate_ids` and `natural_pairing_candidate_ids` reference `candidate_id` values from the saved shared-event candidate table.

## Cross-file reference rules

- `source_event_package_artifact`, `source_discovered_context_family_artifact`, and `source_shared_event_candidates_artifact` must all describe the same committed case.
- `same_slice_selection` is used to form the bounded witness-search candidate pool; it does not shrink the accepted proposal set unless a specific mode explicitly does so.

## Examples

```json
{
  "audit_format_version": "quotient-feasibility-audit.v1",
  "audit_id": "exp104_p6_row_all_n64_seed0_quotient",
  "source_event_package_artifact": "experiments/instances/mechanism-axis/exp104_p6_row_all_n64_seed0/event-package.json",
  "source_discovered_context_family_artifact": "experiments/instances/mechanism-axis/exp104_p6_row_all_n64_seed0/discovered-context-family.json",
  "source_shared_event_candidates_artifact": "experiments/instances/mechanism-axis/exp104_p6_row_all_n64_seed0/shared-event-candidates.json",
  "source_package_provenance_artifact": "experiments/instances/mechanism-axis/exp104_p6_row_all_n64_seed0/package-provenance.json",
  "same_slice_selection": {
    "preparation_id": "prep_pica_default",
    "protocol_id": "protocol_pica_multiscale_scan",
    "protocol_step_id": "protocol_pica_multiscale_scan_step_1",
    "step_index": 1,
    "resolution_id": "resolution_k_4",
    "candidate_event_scope": "singleton_only"
  },
  "candidate_pool_mode": "same_slice_candidate_pool",
  "subset_search": {
    "enabled": true,
    "max_subset_size": 2,
    "stop_at_first_witness": true
  },
  "forced_candidate_ids": [
    "cand_left_group_1__right_package_3",
    "cand_left_group_0__right_package_2"
  ]
}
```

## Validation notes

- The committed EXP-104 audit relies on `candidate_event_scope = "singleton_only"` to bound the witness search.
- Later runners may override only the source artifact paths while reusing the same same-slice selection and forced subset definition.
