# PICA Targeted Obstruction Search

## Purpose
This spec defines the validated configuration for the bounded T41 PICA-targeted endogenous-obstruction campaign. It fixes the committed pilot family, the PICA-wrapper settings, the PICA-native discovery and package-building thresholds, the adequacy floor for interpreting negative results, and the stop rule for selecting a best candidate versus emitting a bounded negative or inadequate-search result.

## Version
- Version field name: `search_format_version`
- Initial value: `"pica-targeted-obstruction-search.v1"`

## Data model
A PICA targeted-obstruction search config is a JSON object that names a bounded family of PICA pilot points and one common threshold policy. Each point references one committed PICA pilot config and one committed PICA context-discovery config. The runner executes each point through the wrapper, context discovery, full event-algebra package build, structural shared-event inference, provenance audit, and dual exact/statistical evaluation.

## Field table
| Field | Required | Type | Constraints |
| --- | --- | --- | --- |
| `search_format_version` | yes | string | Must equal `"pica-targeted-obstruction-search.v1"`. |
| `search_id` | yes | string | Non-empty campaign/search identifier. |
| `points` | yes | array<object> | Non-empty list of unique point definitions. |
| `event_generation_thresholds` | yes | object | Event-basis and event-algebra generation settings. |
| `shared_event_inference_thresholds` | yes | object | Structural shared-event inference settings. |
| `provenance_required` | yes | boolean | Whether provenance admissibility is required for strong-candidate status. |
| `candidate_classification_thresholds` | yes | object | Thresholds for strong/weak/extendable classification. |
| `adequacy_floor` | yes | object | Minimum campaign informativeness thresholds. |
| `output_category` | no | string | Optional default run-registry category. |
| `output_label` | no | string | Optional default run-registry label. |
| `metadata` | no | object | Optional machine-readable metadata. |

### `points[]` object
| Field | Required | Type | Constraints |
| --- | --- | --- | --- |
| `point_id` | yes | string | Unique non-empty point identifier. |
| `pilot_config_artifact` | yes | string | Normalized repo-relative path to a committed `pica-pilot-campaign`. |
| `discovery_config_artifact` | yes | string | Normalized repo-relative path to a committed `pica-context-discovery` config. |
| `trajectories` | yes | integer | Positive bounded trajectory count. |
| `seed_list` | yes | array<integer> | Non-empty unique seed list used to produce the merged multiseed bundle for that point. |
| `notes` | no | array<string> | Optional technical notes. |

### `candidate_classification_thresholds` object
| Field | Required | Type | Constraints |
| --- | --- | --- | --- |
| `strong_nonextendable_min_gpd_str` | yes | number | Positive threshold for strong discovered-obstruction classification. |
| `near_zero_gpd_stat` | yes | number | Non-negative near-zero tolerance for statistical deficit. |
| `min_accepted_coarse_proposal_count` | yes | integer | Minimum accepted proper-coarse structural proposal count required for a strong discovered candidate. |

### `adequacy_floor` object
| Field | Required | Type | Constraints |
| --- | --- | --- | --- |
| `min_total_point_count` | yes | integer | Minimum total point count required for an informative campaign. |
| `min_admissible_built_package_count` | yes | integer | Minimum provenance-admissible built-package count. |
| `min_points_with_proper_coarse_events` | yes | integer | Minimum points with accepted proper-coarse events. |
| `min_points_with_proper_coarse_structural_proposals` | yes | integer | Minimum points with accepted proper-coarse structural proposals. |
| `min_points_with_dual_mode_difference` | yes | integer | Minimum points where baseline hard-only and all-accepted-proposals differ on at least one tracked evaluation quantity. |

## Identifier conventions
- `search_id` is the authoritative identifier for the bounded campaign instance.
- `point_id` is unique within the search config and within the emitted result table.
- `pilot_config_artifact` and `discovery_config_artifact` are authoritative repo-relative references to committed configs.
- Wrapper seed runs reuse the point-level `point_id` and append seed-local run labels internally; the merged multiseed export bundle remains authoritative for downstream discovery.

## Cross-file reference rules
- `pilot_config_artifact` must resolve to a valid `pica-pilot-campaign`.
- `discovery_config_artifact` must resolve to a valid `pica-context-discovery` config.
- The runner must emit per-point derived artifacts including:
  - merged `pica-export-bundle`
  - `discovered-context-family`
  - built `event-package`
  - `package-provenance`
- Dual evaluation summaries in the final result table refer to the package built from the discovered contexts at that point.

## Observable vs debug fields
- Required search inputs are limited to PICA export bundles, discovered contexts, generated event algebras, structural shared-event signatures, and provenance/audit artifacts.
- Hidden/internal PICA state must not be used to accept contexts, generate events, infer shared events, or classify strong discovered-obstruction candidates.
- Diagnostic-only outputs such as RM/CCD may be reported as `not_applicable` when the committed observable artifacts do not support those audits.

## Minimal valid example
```json
{
  "search_format_version": "pica-targeted-obstruction-search.v1",
  "search_id": "pica_targeted_obstruction_t41",
  "points": [
    {
      "point_id": "exp100_baseline_multiseed",
      "pilot_config_artifact": "experiments/configs/pica/pilot-campaign.json",
      "discovery_config_artifact": "experiments/configs/pica/context-discovery-exp100-multiseed.json",
      "trajectories": 3,
      "seed_list": [0, 1, 2],
      "notes": [
        "Committed control family from the T37/T38 baseline pilot."
      ]
    }
  ],
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
    "min_conditioning_count": 2,
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
    "min_total_point_count": 4,
    "min_admissible_built_package_count": 2,
    "min_points_with_proper_coarse_events": 2,
    "min_points_with_proper_coarse_structural_proposals": 1,
    "min_points_with_dual_mode_difference": 1
  },
  "output_category": "search",
  "output_label": "pica-targeted-obstruction",
  "metadata": {
    "event_algebra_mode": "full_powerset",
    "inference_mode": "structural_primary"
  }
}
```

## Validation notes
- Reject empty or duplicate `point_id` values.
- Reject non-repo-relative `pilot_config_artifact` or `discovery_config_artifact` paths.
- Reject empty or duplicate `seed_list` entries.
- Reject non-positive `trajectories`.
- Reject negative adequacy-floor thresholds.
- Reject empty `output_category` or `output_label` when present.
- Strong-candidate classification must not be claimed downstream unless `min_accepted_coarse_proposal_count` is satisfied in all-accepted-proposals mode.
