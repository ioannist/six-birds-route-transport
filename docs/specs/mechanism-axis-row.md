# mechanism-axis-row

## Purpose

`mechanism-axis-row.v1` defines the comparable per-point output row for mechanism-axis campaigns, including shared evaluation metrics, packaging-surface summaries, candidate classes, and mechanism-side claim levels.

## Versioning

- `row_format_version`: must equal `"mechanism-axis-row.v1"`
- table wrapper version: `"mechanism-axis-results.v1"`

## Data model

Required row fields:

- `search_id`
- `point_id`
- `axis = "mechanism"`
- `source_pica_campaign_config_path`
- `produced_export_bundle_path`
- `packaging_surface_summary_path`
- `discovered_context_family_path`
- `accepted_context_count`
- `accepted_singleton_event_count`
- `accepted_proper_coarse_event_count`
- `accepted_shared_event_proposal_count`
- `accepted_proper_coarse_proposal_count`
- `baseline_hard_only`
- `all_accepted_proposals`
- `selected_packaging_sources`
- `selected_packaging_operator_count`
- `selected_packaging_family_count`
- `packaging_support_slice_count`
- `changed_packaging_surface_relative_to_control`
- `candidate_classification`
- `claim_level_supported`
- `mechanism_signal_kind`
- `run_ids`
- `artifact_paths`

Optional row fields:

- `event_package_path`
- `provenance_classification`
- `quotient_class_count`
- `quotient_accepted_only_survivor_count`
- `quotient_natural_pairing_survivor_count`
- `quotient_candidate_subset_witness_found`
- `quotient_witness_classification`
- `quotient_witness_candidate_ids`
- `quotient_feasibility_summary_path`
- `notes`
- `flags`

Invariants:

- `claim_level_supported` must remain within the mechanism-axis ceiling.
- `artifact_paths` must be normalized repo-relative paths.
- Packaging-source values must be unique within the row.
- Quotient-feasibility diagnostics are theorem-object summaries only and do not override the mechanism-axis claim ceiling.

## Identifier conventions

- `point_id` must match the corresponding config point.
- `run_ids` name the wrapper/build/audit/statistical runs used to produce the row.

## Cross-file reference rules

- A row references artifacts emitted from the corresponding mechanism-axis run.
- The row’s packaging summary must resolve to a valid packaging-surface summary built from the same export bundle.

## Example

```json
{
  "row_format_version": "mechanism-axis-row.v1",
  "search_id": "mechanism_axis_example",
  "point_id": "control",
  "axis": "mechanism",
  "source_pica_campaign_config_path": "experiments/configs/pica/pilot-exp120-frozen-slice-control.json",
  "produced_export_bundle_path": "results/search/example/derived/control/pica-export-bundle.json",
  "packaging_surface_summary_path": "results/search/example/derived/control_packaging_surface_summary.json",
  "discovered_context_family_path": "results/search/example/derived/control_family.json",
  "accepted_context_count": 2,
  "accepted_singleton_event_count": 2,
  "accepted_proper_coarse_event_count": 1,
  "accepted_shared_event_proposal_count": 1,
  "accepted_proper_coarse_proposal_count": 1,
  "baseline_hard_only": {
    "exact_structural_status": "feasible",
    "exact_feasible": true,
    "exact_respecting_tuple_count": 2,
    "gpd_str_status": "solved",
    "gpd_str": 0.0,
    "gpd_stat_status": "solved",
    "gpd_stat": 0.0
  },
  "all_accepted_proposals": {
    "exact_structural_status": "feasible",
    "exact_feasible": true,
    "exact_respecting_tuple_count": 1,
    "gpd_str_status": "solved",
    "gpd_str": 0.0,
    "gpd_stat_status": "solved",
    "gpd_stat": 0.0
  },
  "selected_packaging_sources": ["p5_from_p4"],
  "selected_packaging_operator_count": 1,
  "selected_packaging_family_count": 1,
  "packaging_support_slice_count": 24,
  "changed_packaging_surface_relative_to_control": false,
  "candidate_classification": "extendable_candidate",
  "claim_level_supported": "nontrivial_multicontext_structure",
  "mechanism_signal_kind": "control_like",
  "run_ids": {
    "pica_wrapper_seed_0": "20260328T000000Z--control"
  },
  "artifact_paths": {
    "export_bundle": "results/search/example/derived/control/pica-export-bundle.json"
  }
}
```

## Validation notes

- Later figure/table builders can use `claim_level_supported`, `candidate_classification`, `provenance_classification`, and the packaging-surface fields directly without re-deriving semantics.
- Even if a row is numerically strong, later summaries must respect the mechanism-axis claim ceiling.
