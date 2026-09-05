# Exact Crosscheck Result

`exact-crosscheck-result.v1` defines the machine-readable output table for a
cross-check bundle.

Required top-level fields:

- `result_format_version`: must equal `exact-crosscheck-result.v1`
- `crosscheck_id`
- `row_count`
- `rows`

Each row must include:

- `row_format_version`: must equal `exact-crosscheck-row.v1`
- `crosscheck_id`
- `target_id`
- `target_type`
- `evaluation_mode`
- `backend_label`
- `crosscheck_status`: `solved`, `unsolved`, or `not_applicable`
- `blocking_proxy`

Solved rows must additionally include:

- `package_path`
- `feasibility_status`: `feasible` or `infeasible`
- `exact_respecting_tuple_count`
- `model_artifact_path`
- `summary_artifact_path`
- `note_artifact_path`

Optional solved-row fields:

- `exact_selected_tuple_count`
- `solution_artifact_path`

Non-applicable or unsolved rows may include:

- `applicability_reason`

`blocking_proxy` must include:

- `status`
- `blocking_proposal_ids`
- `single_proposal_results`

Each `single_proposal_results` entry records:

- `proposal_id`
- `feasibility_status`
- `exact_respecting_tuple_count`
- `exact_selected_tuple_count`
- `reason`

The committed discovered obstruction slot is allowed to appear as:

- `crosscheck_status = not_applicable`
- `applicability_reason = no_strong_discovered_candidate`
