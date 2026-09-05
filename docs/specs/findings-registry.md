# Findings Registry

Versioned output format: `findings-registry.v1`

## Purpose

Machine-readable final registry over refreshed repo-local evidence and committed static artifacts.

## Required fields

| Field | Required | Type | Notes |
| --- | --- | --- | --- |
| `registry_format_version` | yes | string | Must equal `findings-registry.v1`. |
| `registry_id` | yes | string | Stable registry identifier. |
| `evidence_refresh_run_ids` | yes | object | Map from refresh component key to run ID. |
| `evidence_refresh_summary_paths` | yes | object | Repo-relative summary paths for refreshed components. |
| `entry_count` | yes | integer | Must equal `len(entries)`. |
| `entries` | yes | array | List of `finding-entry.v1` objects. |
| `claim_evidence_map_path` | yes | string | Repo-relative path to `claim-evidence-map.json`. |
| `flagship_examples_path` | yes | string | Repo-relative path to `flagship-examples.json`. |
| `figure_candidates_path` | yes | string | Repo-relative path to `figure-candidates.json`. |
| `table_candidates_path` | yes | string | Repo-relative path to `table-candidates.json`. |
| `theorem_experiment_links_path` | yes | string | Repo-relative path to `theorem-experiment-links.json`. |
| `best_evidence_paths_path` | yes | string | Repo-relative path to `best-evidence-paths.json`. |
| `summary_counts` | yes | object | Flat metric/status counts. |
| `status_flags` | yes | array | Registry-wide negative/limitation flags. |
| `metadata` | no | object | Flat JSON metadata. |

## Notes

- The registry may aggregate both committed static artifacts and fresh stable repo-local run outputs.
- It must not point final evidence refs at temporary `/tmp/...` smoke outputs.
- Negative and limitation findings remain explicit registry content rather than being filtered out.
