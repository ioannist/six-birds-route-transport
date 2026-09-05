# Packaging-Axis Search

## Purpose

`packaging-axis-search.v1` defines the bounded fixed-mechanism, fixed-lens campaign format for comparing same-support packaging branch / operator / family variation with quotient-backed feasibility as the default theorem-facing exact backend.

## Versioning

- Version field: `search_format_version`
- Initial value: `packaging-axis-search.v1`

## Data model

Required fields:
- `search_format_version: str`
- `search_id: str`
- `fixed_pilot_config_artifact: str`
- `preparation_id: str`
- `protocol_id: str`
- `trajectories: int`
- `seed_list: list[int]`
- `points: list[{point_id, selected_protocol_step_ids, selected_step_indices, selected_resolution_ids, allow_cross_resolution_pairs?, notes?}]`
- `projection_families: list[FrozenSliceProjectionFamily]`
- `fixed_projection_family_ids: list[str]`
- `fixed_mechanism_label: str`
- `fixed_lens_label: str`
- `event_generation_thresholds`
- `shared_event_inference_thresholds`
- `candidate_classification_thresholds`
- `adequacy_floor`

Optional fields:
- `include_natural_pairing_control: bool`
- `quotient_subset_search_enabled: bool`
- `quotient_max_subset_size: int`
- `quotient_stop_at_first_witness: bool`
- `provenance_required: bool`
- `claim_ceiling: str`
- `output_category: str`
- `output_label: str | null`
- `metadata: object`

Invariants:
- all points share the fixed mechanism/configuration and fixed projection family set
- every `fixed_projection_family_id` must exist in `projection_families`
- every point must declare at least one selected step and one selected resolution
- points may use same-step package-divergent comparisons or cross-resolution package strict-extension comparisons, but support must stay fixed
- quotient subset search size must be positive

## Identifier conventions

- `search_id` is unique within the repo search namespace
- `point_id` is unique within one packaging-axis campaign
- `projection_id` is unique within one search config

## Cross-file reference rules

- `fixed_pilot_config_artifact` must be repo-relative
- rows emitted by `packaging-axis-row.v1` must carry the same `search_id`
- `packaging-family-admissibility.v1` should be derived from the fixed packaging branch vocabulary observed on the same merged bundle

## Example

```json
{
  "search_format_version": "packaging-axis-search.v1",
  "search_id": "packaging_axis_example",
  "fixed_pilot_config_artifact": "experiments/configs/pica/pilot-exp104-p6-row-all-n64.json",
  "preparation_id": "prep_pica_default",
  "protocol_id": "protocol_pica_multiscale_scan",
  "trajectories": 24,
  "seed_list": [0],
  "points": [
    {
      "point_id": "packaging_control_same_step_k4",
      "selected_protocol_step_ids": ["protocol_pica_multiscale_scan_step_1"],
      "selected_step_indices": [1],
      "selected_resolution_ids": ["resolution_k_4"]
    }
  ],
  "projection_families": [
    {
      "projection_id": "obs_primary",
      "label": "observation label",
      "source_field": "observation_label",
      "projection_kind": "packaging_outcome",
      "allowed_roles": ["primary_context"],
      "projection": { "projection_mode": "observation_label" }
    }
  ],
  "fixed_projection_family_ids": ["obs_primary"],
  "fixed_mechanism_label": "exp104_p6_row_all_n64",
  "fixed_lens_label": "obs_primary_observation_label",
  "event_generation_thresholds": {
    "event_basis_mode": "singleton_plus_small_unions",
    "event_algebra_mode": "conservative_truncation",
    "max_full_powerset_atom_count": 4,
    "max_union_size": 2,
    "min_event_support_count": 1,
    "min_event_support_fraction": 0.0,
    "include_empty_and_full_in_truncation": false,
    "match_empty_for_inference": false,
    "match_full_for_inference": false
  },
  "shared_event_inference_thresholds": {
    "inference_mode": "structural_primary",
    "min_common_probes": 1,
    "min_conditioning_count": 3,
    "min_probe_atom_support_count": 1,
    "max_mean_tv": 1.0,
    "exact_tolerance": 1e-6,
    "proposal_constraint_kind": "soft"
  },
  "candidate_classification_thresholds": {
    "strong_nonextendable_min_gpd_str": 1.0,
    "near_zero_gpd_stat": 1e-6,
    "min_accepted_coarse_proposal_count": 1
  },
  "adequacy_floor": {
    "min_total_point_count": 3,
    "min_admissible_built_package_count": 2,
    "min_points_with_proper_coarse_events": 1,
    "min_points_with_accepted_proper_coarse_structural_proposals": 1,
    "min_points_with_same_support_packaging_divergent_pairs": 1,
    "min_points_with_dual_mode_difference": 1,
    "min_points_with_nontrivial_quotient_result_recorded": 1
  }
}
```

## Validation notes

- later tickets may rely on cross-resolution being explicit at the point level rather than hidden inside package diagnostics
- provenance admissibility is a primary success criterion for this axis, not a post-hoc add-on
