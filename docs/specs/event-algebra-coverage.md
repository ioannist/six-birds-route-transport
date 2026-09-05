# Event Algebra Coverage

## Purpose
This spec defines the machine-readable completeness report emitted alongside discovery-side event-family builds.

## Version
- Version field name: `coverage_format_version`
- Initial value: `"event-algebra-coverage.v1"`

## Data model
| Field | Required | Type | Constraints |
| --- | --- | --- | --- |
| `coverage_format_version` | yes | string | Must equal `"event-algebra-coverage.v1"`. |
| `source_discovered_context_family_artifact` | yes | string | Repo-relative discovered-context-family source path. |
| `event_algebra_mode` | yes | string | Active generation mode label. |
| `max_full_powerset_atom_count` | yes | integer | Positive auto-mode threshold. |
| `contexts` | yes | array<object> | Per-context completeness records. |
| `notes` | no | array<string> | Technical notes. |
| `flags` | no | array<string> | Technical flags. |

### `contexts` entries
| Field | Required | Type | Constraints |
| --- | --- | --- | --- |
| `context_id` | yes | string | Accepted discovered context ID. |
| `atom_count` | yes | integer | Retained atom count. |
| `expected_full_event_count` | yes | integer | Exact Boolean algebra size `2^|A_c|`. |
| `generated_event_count` | yes | integer | Number of generated events for the context. |
| `event_algebra_complete` | yes | boolean | `true` iff generation equals the full powerset. |
| `coverage_fraction` | yes | number | `generated_event_count / expected_full_event_count`. |
| `generation_mode_used` | yes | string | Concrete mode used for this context. |
| `truncation_reason` | no | string | Explicit reason when incomplete. |
| `notes` | no | array<string> | Optional technical notes. |
| `flags` | no | array<string> | Optional explicit flags such as `incomplete_event_algebra`. |

## Minimal valid example
```json
{
  "coverage_format_version": "event-algebra-coverage.v1",
  "source_discovered_context_family_artifact": "experiments/instances/discovered/pica-exp100-multiseed-contexts/discovered-context-family.json",
  "event_algebra_mode": "full_powerset",
  "max_full_powerset_atom_count": 6,
  "contexts": [
    {
      "context_id": "ctx_example",
      "atom_count": 3,
      "expected_full_event_count": 8,
      "generated_event_count": 8,
      "event_algebra_complete": true,
      "coverage_fraction": 1.0,
      "generation_mode_used": "full_powerset",
      "truncation_reason": null,
      "notes": [],
      "flags": []
    }
  ],
  "notes": [],
  "flags": []
}
```

## Validation notes
- Reject negative counts or coverage fractions outside `[0, 1]`.
- Reject duplicate `context_id` values.
- Reject incomplete contexts with missing `truncation_reason` when the chosen mode is truncating.
