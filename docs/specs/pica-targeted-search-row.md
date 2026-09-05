# PICA Targeted Search Row

## Purpose
This spec defines the machine-readable row format emitted by the bounded T41 PICA-targeted obstruction campaign. Each row summarizes one committed point, including its produced export bundle, discovered contexts, built package, provenance status, dual evaluation metrics, audit statuses, and final candidate classification.

## Version
- Row version field name: `row_format_version`
- Initial value: `"pica-targeted-search-row.v1"`
- Table version field name: `table_format_version`
- Initial value: `"pica-targeted-search-results.v1"`

## Data model
A targeted-search row records one point’s final downstream state after wrapper execution, PICA-native context discovery, full event-algebra generation, structural shared-event inference, provenance audit, and dual evaluation. Rows are collected into a table object with one row per `point_id`.

## Row field table
| Field | Required | Type | Constraints |
| --- | --- | --- | --- |
| `row_format_version` | yes | string | Must equal `"pica-targeted-search-row.v1"`. |
| `search_id` | yes | string | Non-empty parent search identifier. |
| `point_id` | yes | string | Non-empty point identifier unique within the table. |
| `source_pica_campaign_config_path` | yes | string | Repo-relative path to the committed pilot config used for this point. |
| `discovery_config_path` | yes | string | Repo-relative path to the committed PICA discovery config used for this point. |
| `preparation_id` | yes | string | Stable preparation ID for the point. |
| `protocol_id` | yes | string | Stable protocol ID for the point. |
| `trajectories` | yes | integer | Positive trajectory count. |
| `seed_list` | yes | array<integer> | Non-empty unique seed list used to build the merged bundle. |
| `produced_export_bundle_path` | yes | string | Repo-relative path to the merged multiseed `pica-export-bundle`. |
| `discovered_context_family_path` | yes | string | Repo-relative path to the emitted `discovered-context-family`. |
| `event_package_path` | no | string | Repo-relative built event-package path when package building succeeds. |
| `provenance_classification` | no | string | One of the package-provenance audit classifications when available. |
| `accepted_context_count` | yes | integer | Non-negative accepted-context count. |
| `accepted_singleton_event_count` | yes | integer | Non-negative accepted singleton-event count. |
| `accepted_proper_coarse_event_count` | yes | integer | Non-negative accepted proper-coarse event count. |
| `accepted_shared_event_proposal_count` | yes | integer | Non-negative accepted shared-event proposal count. |
| `accepted_proper_coarse_structural_proposal_count` | yes | integer | Non-negative accepted proper-coarse structural proposal count. |
| `baseline_hard_only` | yes | object | Exact/statistical evaluation block with hard constraints only. |
| `all_accepted_proposals` | yes | object | Exact/statistical evaluation block including all accepted structural proposals. |
| `ccd_status` | yes | string | Explicit audit status for CCD. |
| `ccd_overall` | no | number | CCD summary value when scored. |
| `sec_status` | yes | string | Explicit audit status for SEC. |
| `sec_mean` | no | number | SEC summary value when scored. |
| `rm_status` | yes | string | Explicit audit status for RM. |
| `rm_overall` | no | number | RM summary value when scored. |
| `candidate_classification` | yes | string | One of the targeted-search candidate labels. |
| `run_ids` | yes | object | Non-empty run-registry IDs for the wrapper and downstream stages. |
| `artifact_paths` | yes | object | Non-empty repo-relative artifact map for downstream inspection. |
| `notes` | no | array<string> | Optional technical notes. |

### Dual evaluation block
Both `baseline_hard_only` and `all_accepted_proposals` must contain:
- `exact_structural_status`
- `exact_feasible`
- `exact_respecting_tuple_count`
- `gpd_str_status`
- `gpd_str`
- `gpd_str_reason`
- `gpd_stat_status`
- `gpd_stat`
- `gpd_stat_reason`

These blocks preserve the carry-forward requirement that baseline hard-only and all-accepted-proposals mode remain distinct in every row and summary.

### Table object
| Field | Required | Type | Constraints |
| --- | --- | --- | --- |
| `table_format_version` | yes | string | Must equal `"pica-targeted-search-results.v1"`. |
| `search_id` | yes | string | Non-empty parent search identifier. |
| `row_count` | yes | integer | Must equal `len(rows)`. |
| `rows` | yes | array<object> | Unique rows by `point_id`. |
| `metadata` | no | object | Optional machine-readable table metadata. |

## Identifier conventions
- `search_id` is constant across the table.
- `point_id` is unique within the table and is the authoritative row key.
- `run_ids` keys name the underlying stage runs, for example:
  - `pica_wrapper_0`
  - `context_discovery`
  - `package_build`
  - `provenance_audit`
  - `baseline_statistical`
  - `candidate_statistical`

## Cross-file reference rules
- All artifact/path fields in a row must be normalized repo-relative paths.
- `produced_export_bundle_path` must resolve to a valid `pica-export-bundle`.
- `discovered_context_family_path` must resolve to a valid `discovered-context-family`.
- `event_package_path` must resolve to a valid event package when present.
- `artifact_paths` may duplicate selected row-level paths for convenience, but the row-level named fields remain authoritative.

## Observable vs debug fields
- Row acceptance and classification must be based on observable-first discovery/build outputs and downstream audits.
- Debug-only notes may be included in `notes`, but they must not replace the explicit numeric/status fields used for classification.

## Minimal valid example
```json
{
  "row_format_version": "pica-targeted-search-row.v1",
  "search_id": "pica_targeted_obstruction_t41",
  "point_id": "exp112_col_p2_multiseed",
  "source_pica_campaign_config_path": "experiments/configs/pica/pilot-exp112-col-p2.json",
  "discovery_config_path": "experiments/configs/pica/context-discovery-exp112-col-p2.json",
  "preparation_id": "prep_pica_default",
  "protocol_id": "protocol_pica_multiscale_scan",
  "trajectories": 3,
  "seed_list": [0, 1, 2],
  "produced_export_bundle_path": "results/search/demo/derived/bundles/exp112_col_p2_multiseed/pica-export-bundle.json",
  "discovered_context_family_path": "results/search/demo/discovered-context-family.json",
  "event_package_path": "results/search/demo/event-package.json",
  "provenance_classification": "admissible",
  "accepted_context_count": 4,
  "accepted_singleton_event_count": 9,
  "accepted_proper_coarse_event_count": 3,
  "accepted_shared_event_proposal_count": 0,
  "accepted_proper_coarse_structural_proposal_count": 0,
  "baseline_hard_only": {
    "exact_structural_status": "feasible",
    "exact_feasible": true,
    "exact_respecting_tuple_count": 4,
    "gpd_str_status": "solved",
    "gpd_str": 0.0,
    "gpd_str_reason": null,
    "gpd_stat_status": "solved",
    "gpd_stat": 0.0,
    "gpd_stat_reason": null
  },
  "all_accepted_proposals": {
    "exact_structural_status": "feasible",
    "exact_feasible": true,
    "exact_respecting_tuple_count": 4,
    "gpd_str_status": "solved",
    "gpd_str": 0.0,
    "gpd_str_reason": null,
    "gpd_stat_status": "solved",
    "gpd_stat": 0.0,
    "gpd_stat_reason": null
  },
  "ccd_status": "not_applicable",
  "ccd_overall": null,
  "sec_status": "solved",
  "sec_mean": 0.0,
  "rm_status": "not_applicable",
  "rm_overall": null,
  "candidate_classification": "extendable_candidate",
  "run_ids": {
    "pica_wrapper_0": "run_results_demo_seed0",
    "context_discovery": "run_search_demo_discover",
    "package_build": "run_search_demo_package",
    "provenance_audit": "run_results_demo_provenance"
  },
  "artifact_paths": {
    "export_bundle": "results/search/demo/derived/bundles/exp112_col_p2_multiseed/pica-export-bundle.json",
    "discovered_context_family": "results/search/demo/discovered-context-family.json",
    "event_package": "results/search/demo/event-package.json",
    "package_provenance": "results/search/demo/package-provenance.json"
  },
  "notes": [
    "ccd_not_applicable_without_repeated_read_trace"
  ]
}
```

## Validation notes
- Reject empty or duplicate `point_id` rows in a table.
- Reject empty `run_ids` or `artifact_paths`.
- Reject non-repo-relative artifact paths.
- Reject negative counts or non-positive `trajectories`.
- Reject present audit summary values unless the paired status is `solved` or `scored`.
- Strong discovered-obstruction classification downstream must still satisfy the adequacy-floor logic at the campaign-summary level; a row alone is not sufficient.
