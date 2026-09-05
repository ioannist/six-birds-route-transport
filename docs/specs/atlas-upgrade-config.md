# Atlas Upgrade Config

`atlas-upgrade-config.v1` defines a compact intentional atlas run over a fixed
family of substrate configs.

Required top-level fields:

- `atlas_format_version`: must equal `atlas-upgrade-config.v1`
- `atlas_id`
- `points`
- `extraction_thresholds`
- `coarse_event_generation_thresholds`
- `shared_event_inference_thresholds`
- `provenance_required`
- `candidate_classification_thresholds`
- `figure_output_settings`

Optional top-level fields:

- `output_category`
- `output_label`
- `metadata`

Each point entry must include:

- `point_id`
- `config_artifact`
- `preparation_id`
- `protocol_id`
- `trajectories`
- `seed`

Optional point fields:

- `figure_group`
- `notes`

Semantics:

- every atlas row must preserve both `baseline_hard_only` and
  `all_accepted_proposals` evaluations,
- the atlas runner reuses the existing discovery, package-build, provenance, and
  audit stages rather than reimplementing them,
- if no row satisfies the strong discovered-obstruction rule, the summary must
  record `no_strong_discovered_obstruction_found = true`.
