# Result Note

## Purpose
This spec defines the technical contract for a compact result note that records run outputs, instance references, metrics, and short technical interpretation. It is a machine-facing result record, not narrative manuscript content.

## Version
- Version field name: `note_format_version`
- Initial value: `"result-note.v1"`

## Data model
A result note is a JSON object keyed by run identity and backed by explicit artifact references. Metrics are scalar-only to keep the initial schema easy to validate and aggregate.

## Field table
| Field | Required | Type | Constraints |
| --- | --- | --- | --- |
| `note_format_version` | yes | string | Must equal `"result-note.v1"`. |
| `note_id` | yes | string | Unique within the repository; lowercase snake_case or `note_*`. |
| `run_id` | yes | string | Must reference a run manifest `run_id`. |
| `instance_ids` | yes | array<string> | Non-empty list of referenced instance IDs. |
| `metrics` | yes | object | Map from metric name to scalar value only. |
| `interpretation` | yes | string | Brief technical interpretation, one short paragraph at most. |
| `caveats` | no | array<string> | Optional list of short technical caveats. |
| `artifact_refs` | yes | object | Map from logical names to repo-relative artifact paths. |
| `metadata` | no | object | Optional technical metadata map. |

## Identifier conventions
- `note_id` identifies one result note.
- `run_id` links the note to a run manifest.
- `instance_ids` link the note to one or more event-package instances.
- `artifact_refs` values are repo-relative paths, not absolute paths.
- Metric names should be stable lowercase snake_case keys.

## Invariants
- `instance_ids` must be non-empty and contain no duplicates.
- `metrics` values must be JSON scalars only: string, number, boolean, or null.
- `artifact_refs` must contain at least one entry.
- `interpretation` must be brief and technical, not a long narrative.
- `artifact_refs` paths must be repo-relative.

## Minimal valid example
```json
{
  "note_format_version": "result-note.v1",
  "note_id": "note_demo_001",
  "run_id": "run_demo_001",
  "instance_ids": ["inst_demo_001"],
  "metrics": {
    "num_contexts": 2,
    "num_events": 2,
    "num_soft_equalities": 1,
    "pass": true
  },
  "interpretation": "The instance is structurally valid and the single soft equality proposal is recorded for later enforcement.",
  "caveats": [
    "No solver has been run yet."
  ],
  "artifact_refs": {
    "run_manifest": "results/search/run_demo_001.manifest.json",
    "trace": "results/search/trace_demo_001.json"
  },
  "metadata": {
    "origin": "bootstrap"
  }
}
```

## Validation notes
- Reject empty `instance_ids`.
- Reject duplicate instance IDs.
- Reject non-scalar metric values.
- Reject empty `artifact_refs`.
- Reject missing `run_id` links when serializing or loading result notes.

