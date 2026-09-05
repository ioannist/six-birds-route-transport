# Exact Crosscheck

`exact-crosscheck.v1` defines a compact config for independent exact feasibility
cross-check runs.

Required top-level fields:

- `crosscheck_format_version`: must equal `exact-crosscheck.v1`
- `crosscheck_id`: stable run/config identifier
- `targets`: non-empty list of target entries
- `backend_label`: exact backend identifier, for example `scipy_milp_v1`
- `blocking_analysis`: blocking-proxy settings

Optional top-level fields:

- `output_category`
- `output_label`
- `metadata`

Each target entry must include:

- `target_id`
- `target_type`: `benchmark` or `discovered_candidate`
- `evaluation_mode`: `hard_only` or `all_proposals`

Applicable targets must also include:

- `package_artifact`: repo-relative path to an `event-package-instance`

Non-applicable slots may instead include:

- `applicability_override_status`: currently `not_applicable`
- `applicability_reason`
- `package_artifact: null`

`blocking_analysis` currently supports:

- `single_proposal_leave_one_out`: boolean

Semantics:

- `hard_only` enforces only hard equality proposals.
- `all_proposals` enforces both hard and soft equality proposals exactly.
- The cross-check backend must be solver-independent from the repo’s brute-force
  exact solver.
- The intended exact formulation is a binary cover problem over respecting
  context-tuples.
