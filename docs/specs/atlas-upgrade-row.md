# Atlas Upgrade Row

`atlas-upgrade-results.v1` defines the machine-readable upgraded atlas table.

Required top-level fields:

- `table_format_version`: must equal `atlas-upgrade-results.v1`
- `atlas_id`
- `row_count`
- `rows`

Each row must include:

- `row_format_version`: must equal `atlas-upgrade-row.v1`
- `atlas_id`
- `point_id`
- `config_path`
- `preparation_id`
- `protocol_id`
- `seed`
- `raw_run_path`
- `discovered_context_family_path`
- `accepted_context_count`
- `accepted_singleton_event_count`
- `accepted_coarse_event_count`
- `accepted_shared_event_proposal_count`
- `accepted_coarse_proposal_count`
- `baseline_hard_only`
- `all_accepted_proposals`
- `regime_classification`
- `figure_group_labels`
- `run_ids`
- `artifact_paths`

Optional row fields:

- `event_package_path`
- `provenance_classification`
- `ccd_overall`
- `sec_mean`
- `rm_overall`
- `notes`

`baseline_hard_only` and `all_accepted_proposals` must both preserve:

- exact structural status
- exact feasibility
- exact respecting tuple count
- `gpd_str` status/value/reason
- `gpd_stat` status/value/reason

The committed atlas summary is allowed to record:

- `no_strong_discovered_obstruction_found = true`

when the atlas contains no row meeting the strong discovered-obstruction rule.
