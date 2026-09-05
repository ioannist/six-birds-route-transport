# quotient-feasibility-result

## Purpose

`quotient-feasibility-result.v1` records the outcome of a quotient-backed global realization audit. It distinguishes the accepted proposal set, the natural pairing control, any forced candidate subset, and the bounded candidate-subset witness search without changing current discovery admissibility.

## Versioning

- `result_format_version`: must equal `"quotient-feasibility-result.v1"`

## Data model

Required fields:

- `result_format_version: string`
- `audit_id: string`
- `source_event_package_artifact: repo-relative path`
- `source_discovered_context_family_artifact: repo-relative path`
- `source_shared_event_candidates_artifact: repo-relative path`
- `quotient_class_ledger_artifact: repo-relative path`
- `quotient_summary: object`
- `accepted_proposal_set_result: object`
- `candidate_subset_witness_result: object`
- `witness_classification: "accepted_proposal_obstruction" | "candidate_subset_quotient_witness" | "no_quotient_obstruction"`

Optional fields:

- `source_package_provenance_artifact: repo-relative path`
- `natural_pairing_result: object`
- `forced_candidate_subset_result: object`
- `notes: [string, ...]`
- `flags: [string, ...]`
- `metadata: object`

Each evaluation block records:

- `mode`
- `candidate_ids`
- `proposal_ids`
- `survivor_count`
- `surviving_quotient_class_ids`
- `exact_feasible`
- optional `exact_failure_reason`
- optional `uncovered_atom_refs`

The subset-search block records:

- `searched_candidate_count`
- `searched_subset_count`
- `max_subset_size`
- `witness_found`
- optional witness ids / failure details

## Identifier conventions

- `audit_id` must match the source audit config.
- `candidate_ids` reference saved candidate-row ids from the shared-event candidate table.
- `proposal_ids` reference admitted proposal ids when the evaluated candidates are accepted.

## Cross-file reference rules

- `quotient_class_ledger_artifact` must point to the ledger used to evaluate all reported modes.
- `accepted_proposal_set_result` always corresponds to the current admitted proposal set and may not silently include rejected candidates.
- `candidate_subset_witness_result` is bounded by the candidate pool defined in the source audit config.

## Examples

```json
{
  "result_format_version": "quotient-feasibility-result.v1",
  "audit_id": "exp104_p6_row_all_n64_seed0_quotient",
  "source_event_package_artifact": "experiments/instances/mechanism-axis/exp104_p6_row_all_n64_seed0/event-package.json",
  "source_discovered_context_family_artifact": "experiments/instances/mechanism-axis/exp104_p6_row_all_n64_seed0/discovered-context-family.json",
  "source_shared_event_candidates_artifact": "experiments/instances/mechanism-axis/exp104_p6_row_all_n64_seed0/shared-event-candidates.json",
  "quotient_class_ledger_artifact": "results/results/20260329T000000Z--quotient_feasibility/quotient-class-ledger.json",
  "quotient_summary": {
    "raw_support_count": 24,
    "quotient_class_count": 13,
    "selected_context_count": 10,
    "selected_context_ids": ["ctx_a", "ctx_b"]
  },
  "accepted_proposal_set_result": {
    "mode": "accepted_only",
    "candidate_ids": [],
    "proposal_ids": [],
    "survivor_count": 13,
    "surviving_quotient_class_ids": ["qclass_0000"],
    "exact_feasible": true,
    "uncovered_atom_refs": []
  },
  "candidate_subset_witness_result": {
    "mode": "candidate_subset_search",
    "searched_candidate_count": 16,
    "searched_subset_count": 136,
    "max_subset_size": 2,
    "witness_found": true,
    "minimal_witness_size": 2,
    "witness_candidate_ids": [
      "cand_left_group_1__right_package_3",
      "cand_left_group_0__right_package_2"
    ],
    "witness_proposal_ids": [],
    "witness_survivor_count": 0,
    "witness_failure_reason": "no_respecting_tuples"
  },
  "witness_classification": "candidate_subset_quotient_witness"
}
```

## Validation notes

- `accepted_proposal_obstruction` is valid only when the accepted proposal set is already quotient-infeasible.
- `candidate_subset_quotient_witness` requires accepted proposals to remain feasible and the bounded subset search to find a witness.
- `no_quotient_obstruction` requires both accepted proposals to remain feasible and the bounded subset search to fail to find a witness.
