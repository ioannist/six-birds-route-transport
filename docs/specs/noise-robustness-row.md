# Noise Robustness Row

`noise-robustness-row.v1` defines one machine-readable robustness row for a fixed target at one noise level.

## Required fields

- `row_format_version`: must equal `noise-robustness-row.v1`
- `sweep_id`
- `target_id`
- `target_type`
- `noise_level`
- `event_package_path`
- `noisy_trace_artifacts`: repo-relative paths to generated noisy traces by metric family
- metric values or explicit statuses for:
  - `gpd_stat`
  - `ccd_overall`
  - `sec_mean`
  - `rm_overall`
- threshold-crossing flags for the current row
- optional baseline structural metadata
- optional notes / flags

## Status handling

Each metric family must preserve explicit status fields:

- `gpd_stat_status`
- `ccd_status`
- `sec_status`
- `rm_status`

Allowed values are:

- `solved`
- `unsolved`
- `scored`
- `insufficient_data`
- `not_applicable`

If a metric is not numerically available, its numeric field must be `null`.

## Baseline structural metadata

If included, fixed-package structural metadata should be recorded as baseline context only, for example:

- `baseline_exact_structural_feasible_hard_only`
- `baseline_gpd_str`

These baseline fields must not be represented as noise-varying metrics unless the package itself is rebuilt.

## Table output

`robustness.json` should store a `noise-robustness-table.v1` object containing:

- `sweep_id`
- `row_count`
- `rows`
- optional metadata

`robustness.csv` should contain the same row information in flattened form.
