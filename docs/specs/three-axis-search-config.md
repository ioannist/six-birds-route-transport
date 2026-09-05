# Three-Axis Search Config

## Purpose
`three-axis-search-config.v1` defines the machine-readable contract for later hierarchy searches. It records which axis is being searched, what must vary versus remain fixed, which metric surface and claim ladder govern the run, and which adequacy-floor thresholds later runners must report against.

## Versioning
- Version field: `config_format_version`
- Initial value: `three-axis-search-config.v1`

## Data model
Required top-level fields:
- `config_format_version`
- `search_id`
- `axis`
- `axis_admissibility`
- `shared_metric_surface_ref`
- `shared_metric_reporting`
- `claim_ladder_ref`
- `adequacy_floor`

Optional top-level fields:
- `candidate_classification_config_ref`
- `notes`
- `flags`
- `metadata`

### `axis`
- Type: string
- Allowed values:
  - `mechanism`
  - `lens`
  - `packaging`

### `axis_admissibility`
- Type: object
- Required fields:
  - `axis`
  - `varied_fields`
  - `fixed_fields`
  - `source_pair_match_fields`
  - `admissibility_requirements`
  - `allowed_outcome_artifacts`
  - `max_claim_level`
- Optional fields:
  - `source_pair_variation_fields`
  - `flags`

Invariants:
- `axis_admissibility.axis` must equal top-level `axis`.
- `varied_fields` and `fixed_fields` must be disjoint.
- `mechanism` configs must vary at least one mechanism/control-space field.
- `lens` configs must vary at least one lens/projection/record-algebra field.
- `packaging` configs must vary at least one packaging/package-selector field.
- Only `packaging` may allow `best-candidate` or `negative-result` as positive end states.

### `shared_metric_reporting`
- Type: object
- Required fields:
  - `required_metric_groups`
- Optional fields:
  - `explicit_statuses_required`
  - `preserve_dual_evaluation`

### `adequacy_floor`
- Type: object
- Meaning: opaque threshold map consumed by later tickets.
- Invariant: must not be empty and values must be JSON scalars.

## Identifier conventions
- `search_id` is unique within the hierarchy program.
- `axis` names the scientific comparison regime, not a runner implementation.
- Field names listed in `varied_fields`, `fixed_fields`, and `source_pair_match_fields` must use the later row/output names that downstream tickets will emit.

## Cross-file reference rules
- `shared_metric_surface_ref` must point to a valid `shared-metric-surface.v1` contract file.
- `claim_ladder_ref` must point to a valid `axis-claim-ladder.v1` contract file.
- `candidate_classification_config_ref` may point to an existing search-spec contract when later tickets reuse its thresholds.
- Later row files must share `search_id` with the originating config.

## Minimal valid example
```json
{
  "config_format_version": "three-axis-search-config.v1",
  "search_id": "hierarchy_packaging_contract_demo",
  "axis": "packaging",
  "axis_admissibility": {
    "axis": "packaging",
    "varied_fields": ["packaging_operator_id", "package_selector_branch"],
    "fixed_fields": ["mechanism_family_id", "lens_family_id", "protocol_step_id", "step_index"],
    "source_pair_match_fields": ["preparation_id", "protocol_id", "protocol_step_id", "step_index", "trajectory_support_scope"],
    "source_pair_variation_fields": ["packaging_operator_id", "package_selector_branch"],
    "admissibility_requirements": ["same_frozen_slice", "same_support_scope", "packaging_difference_required"],
    "allowed_outcome_artifacts": ["best-candidate", "negative-result", "design-inadequate-result"],
    "max_claim_level": "provenance_admissible_strong_obstruction"
  },
  "shared_metric_surface_ref": "experiments/contracts/hierarchy/examples/shared-metric-surface.json",
  "shared_metric_reporting": {
    "required_metric_groups": ["counts", "dual_evaluation", "audits", "support", "context_pair_structure", "axis_admissibility"],
    "explicit_statuses_required": true,
    "preserve_dual_evaluation": true
  },
  "claim_ladder_ref": "experiments/contracts/hierarchy/examples/axis-claim-ladder.json",
  "candidate_classification_config_ref": "docs/specs/packaging-conflict-search.md",
  "adequacy_floor": {
    "min_point_count": 3,
    "min_admissible_points": 2,
    "min_nontrivial_pairs": 1
  }
}
```

## Validation notes
- Reject configs whose axis-specific `varied_fields` omit the required axis vocabulary.
- Reject configs whose `max_claim_level` exceeds the contract ceiling for that axis.
- Reject empty `adequacy_floor`.
- Reject non-repo-relative contract references.
