# Run Manifest

## Purpose
This spec defines the technical contract for a reproducible run manifest that records how a command was executed and which input and output artifacts were involved. It is the audit trail for later implementation and review.

## Version
- Version field name: `manifest_format_version`
- Initial value: `"run-manifest.v1"`

## Data model
A run manifest is a JSON object centered on the run identity, execution command, seed, artifact paths, software versions, and terminal status. Paths are repo-relative strings so the manifest remains portable across machines.

## Field table
| Field | Required | Type | Constraints |
| --- | --- | --- | --- |
| `manifest_format_version` | yes | string | Must equal `"run-manifest.v1"`. |
| `run_id` | yes | string | Unique within the repository; lowercase snake_case or `run_*`. |
| `timestamp` | yes | string | RFC 3339 timestamp in UTC. |
| `command` | yes | array<string> | Non-empty argv vector; first element is the executable or entrypoint. |
| `seed` | yes | integer | Deterministic seed used for the run. |
| `input_artifacts` | yes | object | Map from logical names to repo-relative paths. |
| `output_artifacts` | yes | object | Map from logical names to repo-relative paths. |
| `software_version` | yes | object | Version info map. |
| `status` | yes | string | One of `pending`, `running`, `succeeded`, `failed`, `canceled`. |
| `git_commit` | no | string | Optional commit hash. |
| `metadata` | no | object | Optional technical metadata map. |

### `software_version` object
| Field | Required | Type | Constraints |
| --- | --- | --- | --- |
| `python` | yes | string | Interpreter version string. |
| `package` | yes | string | Installed package version string. |
| `tooling` | no | object | Additional tool versions keyed by tool name. |

## Identifier conventions
- `run_id` identifies one execution record.
- Artifact maps use short logical keys such as `instance`, `trace`, `results`, or `log`.
- Artifact values are repo-relative paths, not absolute paths or URIs.
- `git_commit` should be a full or abbreviated hexadecimal commit hash when present.

## Invariants
- `command` must be non-empty.
- `seed` must be an integer.
- All artifact paths must be repo-relative and normalized with forward slashes.
- Output artifact keys must be unique and non-empty.
- `status` must be one of the enumerated values above.

## Minimal valid example
```json
{
  "manifest_format_version": "run-manifest.v1",
  "run_id": "run_demo_001",
  "timestamp": "2026-03-25T00:00:00Z",
  "command": ["python", "-m", "sixbirds_event", "--help"],
  "seed": 12345,
  "input_artifacts": {
    "instance": "experiments/instances/inst_demo_001.json"
  },
  "output_artifacts": {
    "stdout": "results/search/run_demo_001.stdout.txt",
    "stderr": "results/search/run_demo_001.stderr.txt"
  },
  "software_version": {
    "python": "3.10.12",
    "package": "0.0.0",
    "tooling": {
      "pytest": "9.0.2",
      "ruff": "0.15.4"
    }
  },
  "status": "succeeded",
  "git_commit": "deadbeef",
  "metadata": {
    "executor": "local"
  }
}
```

## Validation notes
- Reject empty `command`.
- Reject non-integer `seed` values.
- Reject absolute paths or path URIs in artifact maps.
- Reject unknown `status` values.
- Reject missing required software version keys.

