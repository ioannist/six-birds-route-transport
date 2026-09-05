# Substrate Run

## Purpose
This spec defines the raw output contract for one substrate-engine execution. It records hidden-state trajectories and per-step lens readouts before any later context, event, or route extraction is attempted.

## Version
- Version field name: `run_format_version`
- Initial value: `"substrate-run.v1"`

## Data model
A substrate run is a JSON object tied to one config, one preparation, one protocol, one seed, and one trajectory count. Each trajectory stores the sampled initial state and a finite sequence of state-transition steps with explicit per-step lens observations.

## Field table
| Field | Required | Type | Constraints |
| --- | --- | --- | --- |
| `run_format_version` | yes | string | Must equal `"substrate-run.v1"`. |
| `run_id` | yes | string | Run-registry run ID. |
| `config_id` | yes | string | Source substrate config ID. |
| `config_artifact` | yes | string | Repo-relative path to the source config file. |
| `seed` | yes | integer | Seed used by the run. |
| `preparation_id` | yes | string | Chosen preparation ID. |
| `protocol_id` | yes | string | Chosen protocol ID. |
| `trajectory_count` | yes | integer | Positive number of trajectories in `trajectories`. |
| `trajectories` | yes | array<object> | Non-empty finite list of trajectory records. |
| `metadata` | no | object | Optional technical metadata map with scalar values or flat string arrays. |

### `trajectories` entries
| Field | Required | Type | Constraints |
| --- | --- | --- | --- |
| `trajectory_id` | yes | string | Unique trajectory ID within the run. |
| `preparation_id` | yes | string | Must match the top-level `preparation_id`. |
| `protocol_id` | yes | string | Must match the top-level `protocol_id`. |
| `initial_state_id` | yes | string | Sampled hidden-state start for this trajectory. |
| `steps` | yes | array<object> | Non-empty sequence of per-step transition records. |

### `steps` entries
| Field | Required | Type | Constraints |
| --- | --- | --- | --- |
| `step_index` | yes | integer | Zero-based contiguous index within the trajectory. |
| `action_id` | yes | string | Action executed at this step. |
| `state_before` | yes | string | Hidden state before the action. |
| `state_after` | yes | string | Hidden state after the action. |
| `observations` | yes | object | Map from every configured lens ID to one observation label emitted from `state_after`. |

## Identifier conventions
- `run_id` is the run-registry identifier for the raw simulation run.
- `config_id` and `config_artifact` identify the source substrate config.
- `preparation_id` and `protocol_id` identify the chosen run controls.
- `trajectory_id` identifies one simulated path within the run.
- `action_id`, `state_before`, `state_after`, and lens IDs are referenced by string equality.

## Invariants
- `config_artifact` must be a normalized repo-relative path.
- `trajectory_count` must equal `len(trajectories)`.
- `trajectory_id` values must be unique within one run.
- Every trajectory must reuse the top-level `preparation_id` and `protocol_id`.
- Every trajectory must contain at least one step in v1.
- `step_index` values must form a contiguous zero-based range within each trajectory.
- `observations` must be non-empty for every step.
- `metadata` values must be JSON scalars or flat string arrays only.

## Minimal valid example
```json
{
  "run_format_version": "substrate-run.v1",
  "run_id": "run_search_20260325t000000z_demo",
  "config_id": "cfg_demo",
  "config_artifact": "experiments/configs/substrates/demo.json",
  "seed": 123,
  "preparation_id": "prep0",
  "protocol_id": "flip2",
  "trajectory_count": 1,
  "trajectories": [
    {
      "trajectory_id": "traj_0001",
      "preparation_id": "prep0",
      "protocol_id": "flip2",
      "initial_state_id": "s0",
      "steps": [
        {
          "step_index": 0,
          "action_id": "flip",
          "state_before": "s0",
          "state_after": "s1",
          "observations": {
            "binary": "one"
          }
        },
        {
          "step_index": 1,
          "action_id": "flip",
          "state_before": "s1",
          "state_after": "s0",
          "observations": {
            "binary": "zero"
          }
        }
      ]
    }
  ],
  "metadata": {
    "protocol_length": 2
  }
}
```

## Validation notes
- Reject `config_artifact` values that are not normalized repo-relative paths.
- Reject non-positive `trajectory_count` values or mismatches with `len(trajectories)`.
- Reject duplicate `trajectory_id` values.
- Reject trajectories whose `preparation_id` or `protocol_id` disagree with the top-level run fields.
- Reject empty `steps` lists.
- Reject non-contiguous or non-zero-based `step_index` values.
- Reject empty `observations` maps or empty observation keys/labels.
- Reject non-scalar values in `metadata`.
