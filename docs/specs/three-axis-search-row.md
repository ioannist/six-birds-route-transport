# Three-Axis Search Row

## Purpose
`three-axis-search-row.v1` defines the comparable row format later mechanism-axis, lens-axis, and packaging-axis searches will emit. Each row names the axis, records the fixed versus varying fields for one point, carries the shared metric surface directly or by reference, and states the strongest claim level the row supports under the shared ladder.

## Versioning
- Version field: `row_format_version`
- Initial value: `three-axis-search-row.v1`

## Data model
Required fields:
- `row_format_version`
- `search_id`
- `point_id`
- `axis`
- `source_asset_refs`
- `fixed_field_summary`
- `varying_field_summary`
- `claim_ladder_ref`
- `candidate_classification`
- `claim_level_support`
- `best_evidence_eligible`

Exactly one of:
- `shared_metric_surface_ref`
- `shared_metric_surface`

Optional fields:
- `outcome_artifact_kind`
- `flags`
- `notes`

### Field semantics
- `source_asset_refs`: repo-relative source/config/artifact refs used to build the row.
- `fixed_field_summary`: compact machine-readable summary of what was held fixed.
- `varying_field_summary`: compact machine-readable summary of what changed on this axis.
- `candidate_classification`: shared class vocabulary only; later tickets may refine thresholds per axis.
- `claim_level_support`: strongest shared claim level supported by the row under default axis ceilings.
- `best_evidence_eligible`: figure/table readiness flag for downstream reporting.

Invariants:
- `fixed_field_summary` and `varying_field_summary` must be disjoint.
- `mechanism` rows may not claim beyond `nontrivial_multicontext_structure`.
- `lens` rows may not claim beyond `same_slice_non_nested_structure`.
- Only `packaging` rows may claim `best-candidate` or `negative-result` outcomes.

## Identifier conventions
- `search_id` links a row back to its config.
- `point_id` is unique within a later row table.
- `source_asset_refs` keys should name contract-stable assets such as `config`, `context_family`, `event_package`, or `bundle`.

## Cross-file reference rules
- `claim_ladder_ref` must resolve to a valid `axis-claim-ladder.v1` file.
- If `shared_metric_surface_ref` is present, it must resolve to a valid `shared-metric-surface.v1` file.
- If `shared_metric_surface` is embedded, it is authoritative for the row and must match the contract file structure exactly.

## Minimal valid example
```json
{
  "row_format_version": "three-axis-search-row.v1",
  "search_id": "hierarchy_packaging_contract_demo",
  "point_id": "demo_packaging_point",
  "axis": "packaging",
  "source_asset_refs": {
    "config": "experiments/contracts/hierarchy/examples/three-axis-search-config.json",
    "bundle": "experiments/contracts/pica/pilot/exp120_discovery_grade/pica-export-bundle.json"
  },
  "fixed_field_summary": {
    "mechanism_family_id": "exp120_discovery_grade",
    "lens_family_id": "observable_row_record_algebra_v1",
    "protocol_step_id": "step_1",
    "step_index": 1
  },
  "varying_field_summary": {
    "packaging_operator_id": "package_branch_selector",
    "package_selector_branch": "branch_alpha"
  },
  "claim_ladder_ref": "experiments/contracts/hierarchy/examples/axis-claim-ladder.json",
  "shared_metric_surface": {
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
    "rm": { "status": "not_applicable", "value": null, "reason": "rm_diagnostic_only" },
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
    "flags": ["example_row"],
    "metadata": { "report_group": "demo" }
  },
  "candidate_classification": "weakly_frustrated_candidate",
  "claim_level_support": "package_conflict_tension",
  "outcome_artifact_kind": "design-inadequate-result",
  "best_evidence_eligible": false,
  "flags": ["table_ready_contract"],
  "notes": ["uses_embedded_metric_surface"]
}
```

## Validation notes
- Reject rows missing both metric-surface forms or providing both at once.
- Reject rows whose `claim_level_support` exceeds the default ceiling for their axis.
- Reject rows that report packaging-class outcomes on `mechanism` or `lens`.
