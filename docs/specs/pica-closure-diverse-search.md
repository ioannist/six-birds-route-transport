# PICA Closure-Diverse Search

## Purpose
`pica-closure-diverse-search.v1` defines a bounded PICA-native endogenous-obstruction campaign that searches across multiple observable projection families and records whether accepted contexts are nested, equal, or incomparable before classifying any discovered obstruction candidate.

## Versioning
- Version field: `search_format_version`
- Initial value: `pica-closure-diverse-search.v1`

## Data model
Required fields:
- `search_format_version: string`
- `search_id: string`
- `points: list[pica-closure-diverse-search-point]`
- `projection_families: list[projection-family]`
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
- each point references exactly one committed pilot config
- each point lists one or more projection families
- `seed_list` is unique and non-empty

Projection-family invariants:
- `projection_id` is unique within the config
- `projection` is a valid `PicaObservableProjection`

Adequacy-floor invariants:
- counts are non-negative
- `min_median_accepted_proposal_support` is finite and non-negative

## Identifier conventions
- `search_id` identifies one committed closure-diverse campaign design
- `point_id` identifies one campaign point within the search
- `projection_id` identifies one observable projection family reused across points

Uniqueness scope:
- `point_id` unique within `search_id`
- `projection_id` unique within `search_id`

## Cross-file reference rules
- `pilot_config_artifact` must be repo-relative and point to a committed `pica-pilot-campaign`
- output artifacts produced by the runner are repo-relative and are linked by artifact paths in the emitted search table and run manifest

## Observable vs debug fields
Required observable inputs:
- committed PICA export bundles
- observable projection family definitions
- discovered contexts
- context-pair structure diagnostics

Optional/debug fields:
- notes
- metadata

## Minimal valid example
```json
{
  "search_format_version": "pica-closure-diverse-search.v1",
  "search_id": "demo_closure_diverse",
  "points": [
    {
      "point_id": "demo_point",
      "pilot_config_artifact": "experiments/configs/pica/pilot-exp100-baseline-closure-control.json",
      "preparation_id": "prep_pica_default",
      "protocol_id": "protocol_pica_multiscale_scan",
      "trajectories": 16,
      "seed_list": [0, 1],
      "projection_family_ids": ["macro_gap_q4"]
    }
  ],
  "projection_families": [
    {
      "projection_id": "macro_gap_q4",
      "label": "macro_gap quartiles",
      "projection": {
        "projection_mode": "payload_numeric_bins",
        "payload_key": "macro_gap",
        "bin_edges": [0.35, 0.5, 0.65]
      }
    }
  ],
  "event_generation_thresholds": {
    "event_basis_mode": "singleton_plus_small_unions",
    "max_union_size": 2,
    "min_event_support_count": 1,
    "min_event_support_fraction": 0.0,
    "event_algebra_mode": "full_powerset",
    "max_full_powerset_atom_count": 6,
    "include_empty_event": true,
    "include_full_event": true,
    "match_eligible_event_kinds": ["singleton", "proper_coarse"]
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
  "provenance_required": true,
  "candidate_classification_thresholds": {
    "strong_nonextendable_min_gpd_str": 1.0,
    "near_zero_gpd_stat": 1e-6,
    "min_accepted_coarse_proposal_count": 1
  },
  "adequacy_floor": {
    "min_total_point_count": 1,
    "min_admissible_built_package_count": 1,
    "min_points_with_proper_coarse_events": 1,
    "min_points_with_proper_coarse_structural_proposals": 1,
    "min_points_with_incomparable_context_pairs": 1,
    "min_points_with_dual_mode_difference": 1,
    "min_median_accepted_proposal_support": 3.0
  }
}
```

## Validation notes
Machine-checkable invariants:
- version string matches `pica-closure-diverse-search.v1`
- all `pilot_config_artifact` paths are repo-relative
- all `point_id` values are unique
- all `projection_id` values are unique
- every point references only declared projection families
- adequacy-floor thresholds are finite and non-negative
