# Shared Metric Surface

## Purpose
`shared-metric-surface.v1` defines the common metric/status block that later mechanism-axis, lens-axis, and packaging-axis searches must all report. It gives one comparable surface for counts, dual exact evaluations, audits, support diagnostics, context-pair structure, and axis-specific admissibility.

## Versioning
- Version field: `metric_surface_format_version`
- Initial value: `shared-metric-surface.v1`

## Data model
Required fields:
- `metric_surface_format_version`
- `accepted_context_count`
- `accepted_singleton_event_count`
- `accepted_proper_coarse_event_count`
- `accepted_shared_event_proposal_count`
- `accepted_proper_coarse_proposal_count`
- `baseline_hard_only`
- `all_accepted_proposals`
- `sec`
- `rm`
- `ccd`
- `support_diagnostics`
- `context_pair_structure_diagnostics`
- `axis_admissibility_diagnostics`

Optional fields:
- `provenance_classification`
- `flags`
- `metadata`

### Shared status metric typing
Audit metrics and numeric diagnostics use:
- `status`:
  - `solved`
  - `unsolved`
  - `insufficient_data`
  - `not_applicable`
- `value`: JSON scalar or `null`
- `reason`: string or `null`

Invariant:
- `value` must be present iff `status = solved`.

### Dual exact evaluation blocks
Both `baseline_hard_only` and `all_accepted_proposals` provide:
- `exact_feasibility_status`
- `exact_feasible`
- `respecting_tuple_count`
- `exact_reason`
- `gpd_str`
- `gpd_stat`

These preserve the repo-wide rule that hard-only and all-accepted-proposals results remain distinct.

### Diagnostics groups
- `support_diagnostics`
- `context_pair_structure_diagnostics`
- `axis_admissibility_diagnostics`

Each group uses explicit statuses rather than forcing missing values into numeric placeholders.

## Identifier conventions
- This file is a reusable contract example or an embedded block inside a row. It does not require its own global ID.
- Later axis-specific search rows should copy field names exactly to preserve comparability.

## Cross-file reference rules
- `three-axis-search-config` may point to a contract example of this file via `shared_metric_surface_ref`.
- `three-axis-search-row` may embed this object directly or reference it by path.
- Later search tables should not rename fields from this surface once adopted.

## Minimal valid example
```json
{
  "metric_surface_format_version": "shared-metric-surface.v1",
  "provenance_classification": "admissible",
  "accepted_context_count": 4,
  "accepted_singleton_event_count": 6,
  "accepted_proper_coarse_event_count": 2,
  "accepted_shared_event_proposal_count": 3,
  "accepted_proper_coarse_proposal_count": 1,
  "baseline_hard_only": {
    "exact_feasibility_status": "feasible",
    "exact_feasible": true,
    "respecting_tuple_count": 12,
    "exact_reason": null,
    "gpd_str": { "status": "solved", "value": 0.0, "reason": null },
    "gpd_stat": { "status": "insufficient_data", "value": null, "reason": "thin_support" }
  },
  "all_accepted_proposals": {
    "exact_feasibility_status": "infeasible",
    "exact_feasible": false,
    "respecting_tuple_count": 2,
    "exact_reason": "coverage_failure",
    "gpd_str": { "status": "solved", "value": 1.25, "reason": null },
    "gpd_stat": { "status": "unsolved", "value": null, "reason": "diagnostic_only" }
  },
  "sec": { "status": "solved", "value": 0.2, "reason": null },
  "rm": { "status": "not_applicable", "value": null, "reason": "diagnostic_only" },
  "ccd": { "status": "insufficient_data", "value": null, "reason": "no_repeated_read_trace" },
  "support_diagnostics": {
    "support_status": "solved",
    "median_event_support": 8.0,
    "median_proposal_support": 6.0,
    "shared_support_scope": "same_run_same_step_trajectory_alignment"
  },
  "context_pair_structure_diagnostics": {
    "diagnostics_status": "solved",
    "equal_pair_count": 0,
    "refinement_pair_count": 1,
    "non_nested_pair_count": 1,
    "disjoint_pair_count": 0
  },
  "axis_admissibility_diagnostics": {
    "diagnostics_status": "solved",
    "admissible_pair_count": 1,
    "fixed_field_match_count": 4,
    "varying_field_difference_count": 2,
    "diagnostic_flags": ["same_slice_packaging_difference"]
  },
  "flags": ["explicit_status_examples"],
  "metadata": { "example": "contract" }
}
```

## Validation notes
- Reject negative counts.
- Reject solved metrics without numeric values.
- Reject numeric values attached to non-solved statuses.
- Reject context-pair or axis-admissibility counts unless their diagnostics status is `solved`.
