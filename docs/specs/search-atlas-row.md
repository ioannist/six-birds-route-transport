# Search Atlas Row

`search-atlas.v1` defines the machine-readable atlas bundle emitted by a search sweep.
The atlas contains ordered row objects, one per sweep point.

## Atlas wrapper fields

- `atlas_format_version`
  - must equal `"search-atlas.v1"`
- `sweep_id`
- `row_count`
- `rows`
  - ordered list of atlas rows
- `metadata`
  - optional flat metadata map

## Required atlas row fields

Each row must contain at minimum:

- `row_format_version`
  - must equal `"search-atlas-row.v1"`
- `sweep_id`
- `point_id`
- `config_path`
- `preparation_id`
- `protocol_id`
- `trajectories`
- `seed`
- `raw_run_path`
- `discovered_context_family_path`
- `event_package_path`
  - nullable when no package was built
- `accepted_context_count`
- `accepted_shared_event_proposal_count`
- `exact_structural_status`
- `exact_structural_feasible_hard_only`
- `exact_respecting_tuple_count`
- `gpd_str`
- `gpd_stat_status`
- `gpd_stat`
- `gpd_stat_reason`
- `ccd_status`
- `ccd_overall`
- `sec_status`
- `sec_mean`
- `rm_status`
- `rm_overall`
- `regime_classification`
- `run_ids`
- `artifact_paths`
- `notes`

## Status discipline

Rows must preserve explicit status values rather than manufacturing numeric zeros for
unsupported results.

Examples:

- `gpd_stat_status = "unsolved"` with `gpd_stat = null`
- `rm_status = "not_applicable"` with `rm_overall = null`
- `sec_status = "insufficient_data"` with `sec_mean = null`

## Provenance

`run_ids` and `artifact_paths` must identify the underlying run-registry artifacts used
to produce the row so the atlas remains auditable point by point.
