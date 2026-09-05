# Search Sweep

`search-sweep.v1` defines a validated sweep configuration for a compact discovery atlas
run over one or more substrate configs.

## Required top-level fields

- `sweep_format_version`
  - must equal `"search-sweep.v1"`
- `sweep_id`
  - stable identifier for the sweep
- `points`
  - explicit ordered sweep points
- `extraction_thresholds`
  - context-discovery thresholds reused from T16
- `shared_event_inference_thresholds`
  - shared-event inference thresholds reused from T17
- `classification_thresholds`
  - deterministic atlas-classifier thresholds
- `metadata`
  - optional flat metadata map

## Sweep points

Each point must define at minimum:

- `point_id`
- `config_artifact`
  - repo-relative substrate-config path
- `preparation_id`
- `protocol_id`
- `trajectories`
- `seed`

Optional point fields:

- `parameter_overrides`
  - flat machine-readable override metadata for the atlas row
- `notes`

Points are explicit. A config with multiple seeds is represented by multiple point
entries rather than implicit expansion.

## Classification thresholds

The sweep config must record the thresholds used by the deterministic regime
classifier, including at minimum:

- `near_zero_gpd_stat`
- `strong_nonextendable_min_gpd_str`

The classifier must preserve explicit statuses such as `unsolved`,
`insufficient_data`, and `not_applicable` rather than coercing them to numeric zero.
