# Packaging-Axis Row

## Purpose

`packaging-axis-row.v1` defines the per-point output row for the bounded packaging-axis campaign, including package-branch diagnostics, tuple-level metrics, and quotient-backed feasibility results.

## Versioning

- Version field: `row_format_version`
- Initial value: `packaging-axis-row.v1`

## Data model

Required fields:
- `row_format_version`
- `search_id`
- `point_id`
- `axis = "packaging"`
- `source_pica_campaign_config_path`
- `produced_export_bundle_path`
- `packaging_surface_summary_path`
- `discovered_context_family_path`
- `fixed_mechanism_label`
- `fixed_lens_label`
- `fixed_projection_family_ids`
- `selected_protocol_step_ids`
- `selected_step_indices`
- `selected_resolution_ids`
- accepted-context / event / proposal counts
- `accepted_packaging_divergent_proposal_count`
- `accepted_packaging_divergent_proper_coarse_proposal_count`
- same-support package-pair diagnostics:
  - `same_support_packaging_divergent_pair_count`
  - `same_step_packaging_divergent_pair_count`
  - `cross_resolution_packaging_divergent_pair_count`
  - `same_support_non_nested_packaging_divergent_pair_count`
- `baseline_hard_only`
- `all_accepted_proposals`
- selected packaging surface counts
- `selector_branch_outcome_counts`
- `support_relation_kind_counts`
- `candidate_classification`
- `claim_level_supported`
- `run_ids`
- `artifact_paths`

Optional fields:
- `event_package_path`
- `provenance_classification`
- quotient-backed fields:
  - `quotient_class_count`
  - `quotient_accepted_only_survivor_count`
  - `quotient_accepted_only_exact_feasible`
  - `quotient_accepted_only_failure_reason`
  - `quotient_natural_pairing_survivor_count`
  - `quotient_natural_pairing_exact_feasible`
  - `quotient_candidate_subset_witness_found`
  - `quotient_candidate_subset_minimal_witness_size`
  - `quotient_witness_status`
  - `quotient_witness_candidate_ids`
  - `quotient_feasibility_summary_path`
- `notes`
- `flags`

Invariants:
- all artifact paths must be repo-relative
- selected step / resolution lists must be unique
- selector-branch and support-relation counts must be non-negative integers
- quotient witness candidate IDs must be unique

## Identifier conventions

- `point_id` matches one point from `packaging-axis-search.v1`
- `search_id` matches the parent search

## Cross-file reference rules

- `fixed_projection_family_ids` must reference projection families from the parent config
- `quotient_feasibility_summary_path`, when present, must point to a `quotient-feasibility-result.v1` artifact set

## Example

```json
{
  "row_format_version": "packaging-axis-row.v1",
  "search_id": "packaging_axis_example",
  "point_id": "packaging_cross_res_k4_k20",
  "axis": "packaging",
  "source_pica_campaign_config_path": "experiments/configs/pica/pilot-exp104-p6-row-all-n64.json",
  "produced_export_bundle_path": "results/search/20260330T191000Z--packaging_axis/derived/merged_bundle/packaging_axis_th5/pica-export-bundle.json",
  "packaging_surface_summary_path": "results/search/20260330T191000Z--packaging_axis/derived/packaging-surface-summary.json",
  "discovered_context_family_path": "results/search/20260330T191000Z--packaging_axis/derived/families/packaging_cross_res_k4_k20/discovered-context-family.json",
  "event_package_path": "results/search/20260330T191000Z--packaging_cross_res_k4_k20_package_build/event-package.json",
  "provenance_classification": "admissible",
  "fixed_mechanism_label": "exp104_p6_row_all_n64",
  "fixed_lens_label": "obs_primary_observation_label",
  "fixed_projection_family_ids": ["obs_primary"],
  "selected_protocol_step_ids": [
    "protocol_pica_multiscale_scan_step_1",
    "protocol_pica_multiscale_scan_step_4"
  ],
  "selected_step_indices": [1, 4],
  "selected_resolution_ids": ["resolution_k_4", "resolution_k_20"],
  "accepted_context_count": 4,
  "accepted_singleton_event_count": 28,
  "accepted_proper_coarse_event_count": 103,
  "accepted_shared_event_proposal_count": 31,
  "accepted_proper_coarse_proposal_count": 22,
  "accepted_packaging_divergent_proposal_count": 31,
  "accepted_packaging_divergent_proper_coarse_proposal_count": 22,
  "same_support_packaging_divergent_pair_count": 4,
  "same_step_packaging_divergent_pair_count": 2,
  "cross_resolution_packaging_divergent_pair_count": 2,
  "same_support_non_nested_packaging_divergent_pair_count": 0,
  "baseline_hard_only": {
    "exact_structural_status": "feasible",
    "exact_feasible": true,
    "exact_respecting_tuple_count": 11,
    "exact_failure_reason": null,
    "gpd_str_status": "solved",
    "gpd_str": 0.0,
    "gpd_str_reason": null,
    "gpd_stat_status": "solved",
    "gpd_stat": 0.0,
    "gpd_stat_reason": null
  },
  "all_accepted_proposals": {
    "exact_structural_status": "infeasible",
    "exact_feasible": false,
    "exact_respecting_tuple_count": 3,
    "exact_failure_reason": "coverage_failure",
    "gpd_str_status": "solved",
    "gpd_str": 3.0,
    "gpd_str_reason": null,
    "gpd_stat_status": "solved",
    "gpd_stat": 0.0,
    "gpd_stat_reason": null
  },
  "quotient_class_count": 11,
  "quotient_accepted_only_survivor_count": 3,
  "quotient_natural_pairing_survivor_count": 11,
  "quotient_witness_status": "accepted_proposal_obstruction",
  "selected_packaging_sources": ["p5_from_p4"],
  "selected_packaging_operator_count": 1,
  "selected_packaging_family_count": 1,
  "packaging_support_slice_count": 96,
  "selector_branch_outcome_counts": {
    "pre_selector_branch": 4,
    "selected_packaging_branch": 4
  },
  "support_relation_kind_counts": {
    "cross_support_match": 2,
    "same_support_relabeling": 29
  },
  "candidate_classification": "strongly_nonextendable_candidate",
  "claim_level_supported": "provenance_admissible_packaging_obstruction",
  "run_ids": {
    "pilot_seed_0": "run_search_20260330t191000z_packaging_axis_seed_0"
  },
  "artifact_paths": {
    "event_package": "results/search/20260330T191000Z--packaging_cross_res_k4_k20_package_build/event-package.json"
  }
}
```

## Validation notes

- later reporting depends on the row carrying both candidate classification and quotient witness status explicitly
- same-support package-branch counts are the main machine-readable bridge back to packaging-axis evidence
