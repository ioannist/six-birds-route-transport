# Finding Entry

Versioned output format: `finding-entry.v1`

## Purpose

Machine-readable row/entry for one curated finding in the final registry.

## Required fields

| Field | Required | Type | Notes |
| --- | --- | --- | --- |
| `finding_format_version` | yes | string | Must equal `finding-entry.v1`. |
| `finding_id` | yes | string | Stable finding identifier. |
| `category` | yes | string | One of `benchmark`, `discovered_package`, `intervention`, `robustness`, `redteam`, `lean`, `suite`, `claim_support`. |
| `title` | yes | string | Short technical label. |
| `status` | yes | string | Technical status or conclusion. |
| `key_claim_tags` | yes | array | Claim IDs supported by the finding. |
| `primary_artifact_refs` | yes | object | Repo-relative primary artifact refs. |
| `supporting_artifact_refs` | no | object | Repo-relative supporting refs. |
| `key_metrics` | no | object | Flat scalar metrics/statuses. |
| `provenance_classification` | no | string | `admissible`, `partially_supported`, or `unsupported` where applicable. |
| `figure_table_candidate_labels` | no | array | Figure/table candidate labels. |
| `theorem_link_ids` | no | array | Theorem-link IDs relevant to the finding. |
| `best_evidence_flag` | no | boolean | Whether the finding is a best-evidence anchor. |
| `best_evidence_score` | no | number | Optional non-negative ranking score. |
| `notes` | no | array | Technical notes. |
| `flags` | no | array | Limitation/negative-result flags. |

## Notes

- A finding entry may represent a positive result, a negative result, or a limitation.
- Artifact refs must remain repo-relative and stable.
