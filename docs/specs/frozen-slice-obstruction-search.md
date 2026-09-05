# Frozen-Slice Obstruction Search

## Purpose
`pica-frozen-slice-search.v1` defines a bounded endogenous-obstruction campaign over discovery-grade PICA exports where primary shared-event identity is restricted to same-step, same-support context pairs and primary contexts are built only from outcome-under-packaging projection families.

## Versioning
- Version field: `search_format_version`
- Initial value: `pica-frozen-slice-search.v1`

## Data model
Required fields:
- `search_format_version: string`
- `search_id: string`
- `points: list[pica-frozen-slice-search-point]`
- `projection_families: list[frozen-slice-projection-family]`
- `source_pair_policy: object`
- `event_generation_thresholds: object`
- `shared_event_inference_thresholds: object`
- `provenance_required: bool`
- `candidate_classification_thresholds: object`
- `adequacy_floor: object`

Optional fields:
- `output_category: string | null`
- `output_label: string | null`
- `metadata: object`

Point invariants:
- each point references exactly one committed `pica-pilot-campaign`
- each point selects one or more `projection_family_ids`
- each point lists one or more `selected_protocol_step_ids`
- each point lists one or more `selected_step_indices`
- `seed_list` is unique and non-empty

Frozen-slice source-pair policy:
- primary source-pair identity requires matching `preparation_id`
- primary source-pair identity requires matching `protocol_id`
- primary source-pair identity requires matching `protocol_step_id`
- primary source-pair identity requires matching `step_index`
- primary source-pair identity requires shared trajectory support within the same run family

Adequacy-floor invariants:
- all threshold counts are non-negative
- `min_median_accepted_proposal_support` is finite and non-negative

## Identifier conventions
- `search_id` identifies one committed frozen-slice campaign design
- `point_id` identifies one campaign point within the search
- `projection_id` identifies one reusable projection family

Uniqueness scope:
- `point_id` unique within the search
- `projection_id` unique within the search

## Projection admissibility rule
Only projection families with:
- `projection_kind = "packaging_outcome"`
- or `projection_kind = "derived_row_outcome"`

and with:
- `allowed_roles` containing `primary_context`

may generate primary contexts for shared-event identity.

Projection families with:
- `projection_kind = "closure_summary"`
- or `projection_kind = "route_summary"`

may be used only as:
- `probe_only`
- or `diagnostic_only`

## Cross-file reference rules
- each `pilot_config_artifact` must be repo-relative
- each `pilot_config_artifact` must resolve to a valid `pica-pilot-campaign`
- output artifacts emitted by the runner are repo-relative and are linked through the table, summary, result note, and run manifest

## Minimal valid example
```json
{
  "search_format_version": "pica-frozen-slice-search.v1",
  "search_id": "demo_frozen_slice",
  "points": [
    {
      "point_id": "demo_point",
      "pilot_config_artifact": "experiments/configs/pica/pilot-exp120-frozen-slice-control.json",
      "preparation_id": "prep_pica_default",
      "protocol_id": "protocol_pica_multiscale_scan",
      "selected_protocol_step_ids": ["protocol_pica_multiscale_scan_step_1"],
      "selected_step_indices": [1],
      "trajectories": 24,
      "seed_list": [0, 1, 2],
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
      "projection": {
        "projection_mode": "observation_label"
      }
    },
    {
      "projection_id": "band3_primary",
      "label": "final_state band3",
      "source_field": "final_state",
      "projection_kind": "derived_row_outcome",
      "allowed_roles": ["primary_context"],
      "projection": {
        "projection_mode": "payload_numeric_bins",
        "payload_key": "final_state",
        "bin_edges": [8, 16]
      }
    }
  ],
  "source_pair_policy": {
    "require_same_preparation_id": true,
    "require_same_protocol_id": true,
    "require_same_protocol_step_id": true,
    "require_same_step_index": true,
    "require_shared_support_scope": true
  },
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
  "provenance_required": true,
  "candidate_classification_thresholds": {
    "strong_nonextendable_min_gpd_str": 1.0,
    "near_zero_gpd_stat": 1e-6,
    "min_accepted_coarse_proposal_count": 1
  },
  "adequacy_floor": {
    "min_total_point_count": 3,
    "min_admissible_built_package_count": 2,
    "min_points_with_proper_coarse_events": 2,
    "min_points_with_primary_same_slice_proper_coarse_structural_proposals": 1,
    "min_points_with_same_slice_non_nested_context_pairs": 1,
    "min_points_with_dual_mode_difference": 1,
    "min_median_accepted_proposal_support": 3.0
  }
}
```

## Validation notes
Machine-checkable invariants:
- version string matches `pica-frozen-slice-search.v1`
- all `pilot_config_artifact` paths are repo-relative
- all `point_id` values are unique
- all `projection_id` values are unique
- every point references only declared projection families
- every point references at least one `primary_context` projection family
- all adequacy-floor thresholds are finite and non-negative
