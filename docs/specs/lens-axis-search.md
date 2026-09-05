# Lens-Axis Search

## Purpose

`lens-axis-search.v1` defines the bounded fixed-mechanism campaign format for comparing admissible same-slice lens / projection families on one support object while preserving the quotient-backed feasibility audit used for theorem-object evaluation.

## Versioning

- Version field: `search_format_version`
- Initial value: `lens-axis-search.v1`

## Data model

Required fields:
- `search_format_version: str`
- `search_id: str`
- `fixed_pilot_config_artifact: str`
- `preparation_id: str`
- `protocol_id: str`
- `trajectories: int`
- `seed_list: list[int]`
- `points: list[{point_id, projection_family_ids, notes?}]`
- `projection_families: list[FrozenSliceProjectionFamily]`
- `selected_protocol_step_ids: list[str]`
- `selected_step_indices: list[int]`
- `selected_resolution_ids: list[str]`
- `fixed_mechanism_label: str`
- `fixed_packaging_family_label: str`
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
- all points share the fixed mechanism/configuration and selected same-slice metadata
- every `projection_family_id` referenced by a point must exist in `projection_families`
- `selected_resolution_ids` must not be empty
- quotient subset search size must be positive

## Identifier conventions

- `search_id` is unique within the repo search namespace
- `point_id` is unique within one lens-axis campaign
- `projection_id` is unique within one search config

## Cross-file reference rules

- `fixed_pilot_config_artifact` must be repo-relative
- rows emitted by `lens-axis-row.v1` must carry the same `search_id`
- `lens-family-admissibility.v1` should be derived from the same `projection_families`

## Examples

```json
{
  "search_format_version": "lens-axis-search.v1",
  "search_id": "lens_axis_example",
  "fixed_pilot_config_artifact": "experiments/configs/pica/pilot-exp104-p6-row-all-n64.json",
  "preparation_id": "prep_pica_default",
  "protocol_id": "protocol_pica_multiscale_scan",
  "trajectories": 24,
  "seed_list": [0],
  "points": [
    {
      "point_id": "lens_control",
      "projection_family_ids": ["obs_primary", "band3_primary"]
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
  "selected_protocol_step_ids": ["protocol_pica_multiscale_scan_step_1"],
  "selected_step_indices": [1],
  "selected_resolution_ids": ["resolution_k_4"],
  "fixed_mechanism_label": "exp104_p6_row_all_n64",
  "fixed_packaging_family_label": "bridge_default_packaging_selector",
  "event_generation_thresholds": {
    "event_basis_mode": "singleton_plus_small_unions",
    "event_algebra_mode": "full_powerset",
    "max_full_powerset_atom_count": 6,
    "max_union_size": 3,
    "min_event_support_count": 1,
    "min_event_support_fraction": 0.0,
    "include_empty_and_full_in_truncation": true,
    "match_empty_for_inference": false,
    "match_full_for_inference": false
  },
  "shared_event_inference_thresholds": {
    "inference_mode": "structural_primary",
    "min_common_probes": 1,
    "min_conditioning_count": 3,
    "min_probe_atom_support_count": 1,
    "max_mean_tv": 1.0,
    "exact_tolerance": 1e-9,
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
    "min_points_with_same_slice_non_nested_lens_pairs": 1,
    "min_points_with_dual_mode_difference": 1,
    "min_points_with_nontrivial_quotient_result_recorded": 1
  }
}
```

## Validation notes

- later tickets rely on same-slice selection being explicit through step and resolution IDs
- later tickets may assume all rows in one run share one fixed packaging-family label
