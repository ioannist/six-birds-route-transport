# Lens-Axis Row

## Purpose

`lens-axis-row.v1` defines the per-point output row for the bounded lens-axis campaign, including tuple-level metrics, support-relation diagnostics, and quotient-backed feasibility results.

## Versioning

- Version field: `row_format_version`
- Initial value: `lens-axis-row.v1`

## Data model

Required fields:
- `row_format_version`
- `search_id`
- `point_id`
- `axis = "lens"`
- `source_pica_campaign_config_path`
- `produced_export_bundle_path`
- `packaging_surface_summary_path`
- `discovered_context_family_path`
- `fixed_mechanism_label`
- `fixed_packaging_family_label`
- `lens_projection_family_ids`
- accepted-context / event / proposal counts
- `same_slice_non_nested_lens_pair_count`
- `baseline_hard_only`
- `all_accepted_proposals`
- selected packaging surface counts
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
- quotient witness candidate IDs must be unique
- support-relation counts must be non-negative integers

## Identifier conventions

- `point_id` matches one point from `lens-axis-search.v1`
- `search_id` matches the parent search

## Cross-file reference rules

- `lens_projection_family_ids` must reference projection families from the parent config
- `quotient_feasibility_summary_path`, when present, must point to a `quotient-feasibility-result.v1` artifact set

## Examples

```json
{
  "row_format_version": "lens-axis-row.v1",
  "search_id": "lens_axis_example",
  "point_id": "lens_control",
  "axis": "lens",
  "source_pica_campaign_config_path": "experiments/configs/pica/pilot-exp104-p6-row-all-n64.json",
  "produced_export_bundle_path": "results/results/20260329T000000Z--lens_axis_example/pica-export-bundle.json",
  "packaging_surface_summary_path": "results/search/20260329T000000Z--lens_axis/derived/packaging-surface-summary.json",
  "discovered_context_family_path": "results/search/20260329T000000Z--lens_axis/derived/families/lens_control/discovered-context-family.json",
  "event_package_path": "results/search/20260329T000000Z--lens_control_package_build/event-package.json",
  "provenance_classification": "admissible",
  "fixed_mechanism_label": "exp104_p6_row_all_n64",
  "fixed_packaging_family_label": "bridge_default_packaging_selector",
  "lens_projection_family_ids": ["obs_primary", "band3_primary"],
  "accepted_context_count": 4,
  "accepted_singleton_event_count": 8,
  "accepted_proper_coarse_event_count": 12,
  "accepted_shared_event_proposal_count": 6,
  "accepted_proper_coarse_proposal_count": 2,
  "accepted_lens_diverse_proper_coarse_proposal_count": 2,
  "same_slice_non_nested_lens_pair_count": 1,
  "baseline_hard_only": {
    "exact_structural_status": "feasible",
    "exact_feasible": true,
    "exact_respecting_tuple_count": 4,
    "exact_failure_reason": null,
    "gpd_str_status": "solved",
    "gpd_str": 0.0,
    "gpd_str_reason": null,
    "gpd_stat_status": "unsolved",
    "gpd_stat": null,
    "gpd_stat_reason": "not_computed"
  },
  "all_accepted_proposals": {
    "exact_structural_status": "feasible",
    "exact_feasible": true,
    "exact_respecting_tuple_count": 4,
    "exact_failure_reason": null,
    "gpd_str_status": "solved",
    "gpd_str": 0.0,
    "gpd_str_reason": null,
    "gpd_stat_status": "unsolved",
    "gpd_stat": null,
    "gpd_stat_reason": "not_computed"
  },
  "quotient_witness_status": "no_quotient_obstruction",
  "selected_packaging_sources": ["p5_from_p4"],
  "selected_packaging_operator_count": 1,
  "selected_packaging_family_count": 1,
  "packaging_support_slice_count": 96,
  "support_relation_kind_counts": { "same_support_relabeling": 2 },
  "candidate_classification": "extendable_candidate",
  "claim_level_supported": "same_slice_non_nested_structure",
  "run_ids": { "pilot_seed_0": "run_results_20260329t000000z_lens_axis_seed_0" },
  "artifact_paths": {
    "event_package": "results/search/20260329T000000Z--lens_control_package_build/event-package.json"
  }
}
```

## Validation notes

- later figure/table builders rely on the row carrying both candidate classification and quotient witness status explicitly
