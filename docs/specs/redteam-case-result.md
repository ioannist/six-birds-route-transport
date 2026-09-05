# redteam-case-result

Technical schema for machine-readable red-team case outputs and the suite-level results table.

## Row version field

- `row_format_version = "redteam-case-result.v1"`

## Table version field

- `table_format_version = "redteam-results.v1"`

## Required row fields

- `suite_id`
- `case_id`
- `adversarial_type`
- `input_asset_refs`
- `attempted_metrics`
- `exact_structural_status`
- `gpd_stat_status`
- `ccd_status`
- `sec_status`
- `rm_status`
- `framework_response`
- `run_ids`
- `artifact_paths`
- `note_path`

## Optional row fields

- `exact_structural_feasible_hard_only`
- `gpd_str`
- `gpd_stat`
- `gpd_stat_reason`
- `ccd_overall`
- `sec_mean`
- `rm_overall`
- `intervention_conclusion`
- `explanatory_flags`

## Status semantics

- `solved`
- `unsolved`
- `scored`
- `insufficient_data`
- `not_applicable`

These statuses must be preserved explicitly. Unsupported metrics are not converted to numeric zeros.

## Framework response semantics

- `flagged`: current automated outputs clearly mark the adversarial issue
- `corrected`: an existing intervention runner resolves the issue with clear before/after evidence
- `partially_flagged`: diagnostics move in the expected direction but remain mixed or incomplete
- `partially_corrected`: intervention weakens rather than removes the issue
- `not_flagged`: the current automated framework does not clearly mark the issue

## Table semantics

- `rows` contains one validated row per adversarial case
- `row_count` must equal `len(rows)`
- all rows share the same `suite_id`
