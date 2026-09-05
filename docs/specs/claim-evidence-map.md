# Claim-Evidence Map

Versioned output format: `claim-evidence-map.v1`

## Purpose

Machine-readable mapping from technical claims to registry evidence entries.

## Required fields

| Field | Required | Type | Notes |
| --- | --- | --- | --- |
| `claim_map_format_version` | yes | string | Must equal `claim-evidence-map.v1`. |
| `claim_count` | yes | integer | Must equal `len(claims)`. |
| `claims` | yes | array | Claim linkage entries. |
| `metadata` | no | object | Flat JSON metadata. |

## Claim linkage entry fields

| Field | Required | Type | Notes |
| --- | --- | --- | --- |
| `claim_id` | yes | string | Stable claim ID such as `C1`. |
| `claim_label` | yes | string | Short technical label. |
| `evidence_entry_ids` | yes | array | Referenced `finding_id` values. |
| `best_evidence_entry_id` | yes | string | Must be one of `evidence_entry_ids`. |
| `theorem_linkage_ids` | no | array | Theorem-link IDs if applicable. |
| `caveat_flags` | no | array | Technical caveats / limitation flags. |

## Notes

- The map is intended to expose best-evidence paths per claim without manuscript prose.
- Caveat flags should preserve limitations such as negative search results or smaller formal witnesses.
