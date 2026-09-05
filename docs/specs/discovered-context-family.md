# Discovered Context Family

## Purpose
This spec defines the validated intermediate output of context discovery from either raw substrate runs or PICA export bundles. It records observable-driven candidate keys, accepted contexts, rejected candidates, threshold diagnostics, and an optional event-package skeleton for later shared-event inference.

## Version
- Version field name: `family_format_version`
- Initial value: `"discovered-context-family.v1"`

## Data model
A discovered context family is a JSON object keyed to one or more source `substrate-run` artifacts or one source `pica-export-bundle`. Candidate keys are built from observable metadata only. Legacy run-based discovery uses `preparation_id`, `protocol_id`, `lens_id`, and `step_index`. PICA-native discovery may additionally populate `level_id`, `resolution_id`, `closure_id`, and `protocol_step_id`. Accepted contexts contain retained atomic outcomes and diagnostics; rejected candidates record explicit rejection reasons.

## Field table
| Field | Required | Type | Constraints |
| --- | --- | --- | --- |
| `family_format_version` | yes | string | Must equal `"discovered-context-family.v1"`. |
| `family_id` | yes | string | Stable identifier for one discovery result. |
| `source_run_artifacts` | yes | array<string> | Non-empty list of normalized repo-relative `substrate-run` paths. |
| `source_mode` | no | string | Either `substrate_runs` or `pica_export_bundle`. Defaults to `substrate_runs`. |
| `source_bundle_artifact` | no | string | Required repo-relative `pica-export-bundle` path when `source_mode = "pica_export_bundle"`. |
| `thresholds` | yes | object | Explicit extraction thresholds used for acceptance/rejection. |
| `accepted_contexts` | yes | array<object> | Finite list of accepted observable candidate contexts. |
| `rejected_candidates` | yes | array<object> | Finite list of rejected candidate keys with explicit rejection reasons. |
| `diagnostics_summary` | yes | object | Aggregate counts and rejection-reason summary. |
| `event_package_skeleton_artifact` | no | string | Optional repo-relative path to a schema-valid event-package skeleton derived from accepted contexts. |
| `metadata` | no | object | Optional technical metadata map with scalar values or flat string arrays. |

### `thresholds` object
| Field | Required | Type | Constraints |
| --- | --- | --- | --- |
| `min_trajectory_count` | yes | integer | Positive minimum trajectory count per candidate key. |
| `min_atom_count` | yes | integer | Positive minimum retained atomic-outcome count. |
| `min_atom_support_count` | yes | integer | Positive minimum support count per retained outcome. |
| `min_atom_support_fraction` | yes | number | Minimum retained-outcome support fraction in `[0, 1]`. |
| `min_coverage` | yes | number | Minimum fraction of trajectories covered by retained outcomes. |
| `max_batch_tv` | yes | number | Maximum allowed batch-marginal TV stability proxy. |
| `max_persistence_flip_rate` | no | number | Optional maximum allowed next-step outcome change rate. |
| `batch_count` | yes | integer | Positive number of deterministic batches used for batch-TV diagnostics. |

### `accepted_contexts` entries
| Field | Required | Type | Constraints |
| --- | --- | --- | --- |
| `context_id` | yes | string | Unique accepted context ID. |
| `candidate_key` | yes | object | Observable discovery key with `preparation_id`, `protocol_id`, `lens_id`, and `step_index`. |
| `atomic_outcomes` | yes | array<object> | Non-empty list of retained atomic outcomes. |
| `diagnostics` | yes | object | Extraction-time diagnostics for this accepted context. |
| `source_metadata` | no | object | Optional explicit PICA source metadata for PICA-native accepted contexts. |

### `candidate_key` object
| Field | Required | Type | Constraints |
| --- | --- | --- | --- |
| `preparation_id` | yes | string | Explicit preparation ID from the raw substrate runs. |
| `protocol_id` | yes | string | Explicit protocol ID from the raw substrate runs. |
| `lens_id` | yes | string | Explicit lens ID from the raw substrate runs. |
| `step_index` | yes | integer | Explicit step index from the raw substrate runs. |
| `level_id` | no | string | Optional PICA level ID for multi-layer discovery. |
| `resolution_id` | no | string | Optional PICA resolution ID for multi-layer discovery. |
| `closure_id` | no | string | Optional PICA closure ID for multi-layer discovery. |
| `protocol_step_id` | no | string | Optional stable protocol-step identifier. |

### `atomic_outcomes` entries
| Field | Required | Type | Constraints |
| --- | --- | --- | --- |
| `outcome_id` | yes | string | Context-local atom ID derived from an observed lens label. |
| `observation_label` | yes | string | Raw observed lens label retained as an atomic outcome. |
| `support_count` | yes | integer | Non-negative count of supporting trajectories. |
| `support_fraction` | yes | number | Support fraction in `[0, 1]`. |

### `diagnostics` object
| Field | Required | Type | Constraints |
| --- | --- | --- | --- |
| `trajectory_count` | yes | integer | Number of trajectories contributing to the candidate key. |
| `retained_atom_count` | yes | integer | Number of retained atomic outcomes. |
| `coverage_fraction` | yes | number | Fraction of trajectories covered by retained outcomes. |
| `empirical_entropy` | yes | number | Entropy of the retained outcome distribution. |
| `batch_tv_max` | yes | number | Maximum pairwise TV across deterministic trajectory batches. |
| `persistence_flip_rate` | no | number | Optional fraction of trajectories whose lens outcome changes at the next step. |
| `row_count` | no | integer | Optional PICA row count when discovery uses observable-ledger rows rather than substrate trajectories. |
| `support_by_retained_atom` | no | object | Optional retained-label support counts keyed by retained atom label. |

### `source_metadata` object
| Field | Required | Type | Constraints |
| --- | --- | --- | --- |
| `source_mode` | yes | string | For PICA-native contexts, `pica_export_bundle`. |
| `source_kind` | yes | string | Explicit extraction kind, such as `pica_multilayer_group`. |
| `export_bundle_id` | yes | string | Resolved source export bundle ID. |
| `campaign_id` | yes | string | Resolved source campaign ID. |
| `run_ids` | yes | array<string> | Non-empty unique list of contributing run IDs. |
| `observable_ledger_ids` | yes | array<string> | Non-empty unique list of contributing observable-ledger IDs. |
| `level_id` | yes | string | Source level ID. |
| `resolution_id` | yes | string | Source resolution ID. |
| `closure_id` | yes | string | Source closure ID. |
| `lens_id` | yes | string | Source lens ID. |
| `preparation_id` | yes | string | Source preparation ID. |
| `protocol_id` | yes | string | Source protocol ID. |
| `protocol_step_id` | yes | string | Source protocol-step ID. |
| `step_index` | yes | integer | Source step index. |
| `projection_mode` | yes | string | Observable projection mode used for extraction. |
| `projection_field` | yes | string | Label field or payload key used by the projection. |
| `projection_bin_edges` | no | array<number> | Sorted finite bin edges when payload binning is used. |

### `rejected_candidates` entries
| Field | Required | Type | Constraints |
| --- | --- | --- | --- |
| `candidate_key` | yes | object | Observable candidate key. |
| `rejection_reasons` | yes | array<string> | Non-empty list of explicit rejection reasons. |
| `diagnostics` | yes | object | Same diagnostics object used for accepted contexts. |
| `source_metadata` | no | object | Optional PICA source metadata for rejected PICA-native candidates. |

### `diagnostics_summary` object
| Field | Required | Type | Constraints |
| --- | --- | --- | --- |
| `candidate_count` | yes | integer | Total accepted plus rejected candidate count. |
| `accepted_context_count` | yes | integer | Must equal `len(accepted_contexts)`. |
| `rejected_candidate_count` | yes | integer | Must equal `len(rejected_candidates)`. |
| `rejection_reason_counts` | yes | object | Count of each recorded rejection reason. |
| `accepted_context_ids` | yes | array<string> | Accepted context IDs in output order. |

## Identifier conventions
- `family_id` identifies one discovery result bundle.
- `candidate_key` is always defined from observable metadata only. Legacy discovery uses preparation, protocol, lens, and step. PICA-native discovery may additionally use level, resolution, closure, and protocol-step IDs.
- `context_id` is a stable derived ID for one accepted candidate key.
- `outcome_id` is a context-local atom identifier derived from an observed lens label; it is not a hidden-state ID.
- `source_bundle_artifact` is authoritative when `source_mode = "pica_export_bundle"`.
- `event_package_skeleton_artifact`, when present, points to a schema-valid event-package instance with no inferred shared-event equalities yet.

## Invariants
- `source_run_artifacts` must be a non-empty list of normalized repo-relative paths.
- `source_mode = "substrate_runs"` requires non-empty `source_run_artifacts`.
- `source_mode = "pica_export_bundle"` requires `source_bundle_artifact`.
- Hidden-state IDs are not part of accepted/rejected candidate definitions in this format.
- `accepted_contexts` may be empty, but every accepted context must have at least one retained atomic outcome.
- `context_id` values must be unique across `accepted_contexts`.
- `candidate_count` must equal accepted plus rejected counts.
- `accepted_context_count` must equal `len(accepted_contexts)`.
- `rejected_candidate_count` must equal `len(rejected_candidates)`.
- `accepted_context_ids` must match the accepted context IDs in output order.
- `rejection_reasons` must be explicit and non-empty.
- `metadata` values must be JSON scalars or flat string arrays only.

## Minimal valid example
```json
{
  "family_format_version": "discovered-context-family.v1",
  "family_id": "family_demo",
  "source_run_artifacts": [
    "experiments/instances/smoke/substrate-runs/stochastic-two-state-seed123.json"
  ],
  "source_mode": "substrate_runs",
  "thresholds": {
    "min_trajectory_count": 10,
    "min_atom_count": 2,
    "min_atom_support_count": 2,
    "min_atom_support_fraction": 0.0,
    "min_coverage": 0.9,
    "max_batch_tv": 0.35,
    "max_persistence_flip_rate": 0.8,
    "batch_count": 2
  },
  "accepted_contexts": [
    {
      "context_id": "ctx_prep0_flip6_occupancy_step0",
      "candidate_key": {
        "preparation_id": "prep0",
        "protocol_id": "flip6",
        "lens_id": "occupancy",
        "step_index": 0
      },
      "atomic_outcomes": [
        {
          "outcome_id": "atom_one_1",
          "observation_label": "one",
          "support_count": 12,
          "support_fraction": 0.6
        },
        {
          "outcome_id": "atom_zero_2",
          "observation_label": "zero",
          "support_count": 8,
          "support_fraction": 0.4
        }
      ],
      "diagnostics": {
        "trajectory_count": 20,
        "retained_atom_count": 2,
        "coverage_fraction": 1.0,
        "empirical_entropy": 0.97,
        "batch_tv_max": 0.2,
        "persistence_flip_rate": 0.7
      }
    }
  ],
  "rejected_candidates": [
    {
      "candidate_key": {
        "preparation_id": "prep0",
        "protocol_id": "cycle5",
        "lens_id": "phase",
        "step_index": 0
      },
      "rejection_reasons": [
        "insufficient_trajectory_count",
        "trivial_context"
      ],
      "diagnostics": {
        "trajectory_count": 4,
        "retained_atom_count": 1,
        "coverage_fraction": 1.0,
        "empirical_entropy": 0.0,
        "batch_tv_max": 0.0,
        "persistence_flip_rate": 1.0
      }
    }
  ],
  "diagnostics_summary": {
    "candidate_count": 2,
    "accepted_context_count": 1,
    "rejected_candidate_count": 1,
    "rejection_reason_counts": {
      "insufficient_trajectory_count": 1,
      "trivial_context": 1
    },
    "accepted_context_ids": [
      "ctx_prep0_flip6_occupancy_step0"
    ]
  },
  "event_package_skeleton_artifact": "results/search/demo/event-package-skeleton.json",
  "metadata": {
    "observable_only": true
  }
}
```

## Validation notes
- Reject non-repo-relative `source_run_artifacts` paths.
- Reject `pica_export_bundle` families without `source_bundle_artifact`.
- Reject malformed or hidden-state-based candidate keys.
- Reject empty `rejection_reasons`.
- Reject accepted contexts with duplicate `outcome_id` values.
- Reject inconsistent summary counts.
- Reject non-repo-relative `event_package_skeleton_artifact` paths.
- Reject non-scalar values in `metadata`.
