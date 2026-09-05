# Noise Robustness Sweep

`noise-robustness-sweep.v1` defines a compact seeded noise sweep over fixed event-package asset families.

## Required top-level fields

- `sweep_format_version`: must equal `noise-robustness-sweep.v1`
- `sweep_id`: stable sweep identifier
- `targets`: non-empty list of target specifications
- `noise_grid`: non-empty list of finite noise levels in `[0, 1]`
- `noise_model`: deterministic noise-model configuration
- `metric_thresholds`: explicit per-metric failure thresholds
- `metadata`: optional flat metadata

## Target specification

Each target must include:

- `target_id`
- `target_type`: `benchmark` or `discovered_package`
- `event_package_artifact`: repo-relative event-package path
- `trace_artifacts`: optional repo-relative clean trace paths by metric family:
  - `stat`
  - `ccd`
  - `sec`
  - `rm`
- optional `noise_grid_override`
- optional `metric_threshold_overrides`
- optional `notes`

The runner may include baseline structural metadata for context, but those values are fixed-package metadata rather than swept outputs unless the package is explicitly rebuilt.

## Noise model

`noise_model` must include at minimum:

- `base_seed`
- `distribution_model`
- `ccd_model`

Recommended defaults:

- `distribution_model = "independent_jitter_mix_v1"`
- `ccd_model = "singleton_corruption_v1"`

Distribution-valued traces use deterministic seeded jitter mixing over the original finite support. CCD traces use deterministic seeded singleton-step corruption.

## Thresholds

`metric_thresholds` must provide explicit thresholds for:

- `gpd_stat_failure_threshold`
- `ccd_failure_threshold`
- `sec_failure_threshold`
- `rm_failure_threshold`

Per-target overrides may replace these values.

## Output expectations

The runner emits one robustness row per `(target_id, noise_level)` pair plus sweep-level tables and threshold-crossing summaries. Explicit statuses such as `solved`, `unsolved`, `insufficient_data`, and `not_applicable` must be preserved rather than coerced to numeric zero.
