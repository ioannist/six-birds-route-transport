# Substrate Config

## Purpose
This spec defines the finite configuration contract for the autonomous substrate engine: hidden states, preparations, actions, deterministic observation lenses, and named protocols. It is a raw simulation substrate, not a context/event trace.

## Version
- Version field name: `config_format_version`
- Initial value: `"substrate-config.v1"`

## Data model
A substrate config is a JSON object with explicit hidden-state IDs, named preparations as initial distributions, named actions with transition kernels, named deterministic lenses, and named protocols as finite action sequences. Optional defaults provide sampling parameters for CLI execution.

## Field table
| Field | Required | Type | Constraints |
| --- | --- | --- | --- |
| `config_format_version` | yes | string | Must equal `"substrate-config.v1"`. |
| `config_id` | yes | string | Stable config identifier. |
| `states` | yes | array<object> | Non-empty finite list of hidden states. |
| `preparations` | yes | array<object> | Non-empty finite list of named initial distributions. |
| `actions` | yes | array<object> | Non-empty finite list of action kernels. |
| `lenses` | yes | array<object> | Non-empty finite list of deterministic state-to-label readout maps. |
| `protocols` | yes | array<object> | Non-empty finite list of named action sequences. |
| `defaults` | no | object | Optional sampling defaults such as `trajectory_count` and `seed`. |
| `metadata` | no | object | Optional technical metadata map with scalar values or flat string arrays. |

### `states` entries
| Field | Required | Type | Constraints |
| --- | --- | --- | --- |
| `state_id` | yes | string | Unique hidden-state ID. |
| `label` | no | string | Optional human-readable label. |

### `preparations` entries
| Field | Required | Type | Constraints |
| --- | --- | --- | --- |
| `preparation_id` | yes | string | Unique preparation ID. |
| `distribution` | yes | object | Finite distribution over hidden-state IDs; probabilities must sum to 1 within tolerance. |

### `actions` entries
| Field | Required | Type | Constraints |
| --- | --- | --- | --- |
| `action_id` | yes | string | Unique action ID. |
| `transition_kernel` | yes | object | For every hidden state, a finite distribution over next states; each row must sum to 1 within tolerance. |

### `lenses` entries
| Field | Required | Type | Constraints |
| --- | --- | --- | --- |
| `lens_id` | yes | string | Unique deterministic lens ID. |
| `readout_map` | yes | object | Total map from every hidden state ID to exactly one observation label. |

### `protocols` entries
| Field | Required | Type | Constraints |
| --- | --- | --- | --- |
| `protocol_id` | yes | string | Unique protocol ID. |
| `action_ids` | yes | array<string> | Non-empty finite action sequence. |

### `defaults` object
| Field | Required | Type | Constraints |
| --- | --- | --- | --- |
| `trajectory_count` | no | integer | Optional positive default trajectory count for CLI execution. |
| `seed` | no | integer | Optional default RNG seed for CLI execution. |

## Identifier conventions
- `config_id` identifies one substrate config.
- `state_id` identifies one hidden state.
- `preparation_id` identifies one initial distribution over hidden states.
- `action_id` identifies one transition kernel.
- `lens_id` identifies one deterministic observation lens.
- `protocol_id` identifies one finite action sequence.
- All IDs are case-sensitive and referenced by string equality.

## Invariants
- `states`, `preparations`, `actions`, `lenses`, and `protocols` must all be non-empty.
- `state_id`, `preparation_id`, `action_id`, `lens_id`, and `protocol_id` values must be unique within their respective lists.
- Each preparation distribution must reference only known hidden states and sum to 1 within tolerance.
- Each action kernel must define exactly one outgoing row for every hidden state.
- Each action row must reference only known next states and sum to 1 within tolerance.
- Each lens must define exactly one readout label for every hidden state.
- Each protocol must reference only known action IDs and must be non-empty in v1.
- `metadata` values must be JSON scalars or flat string arrays only.

## Minimal valid example
```json
{
  "config_format_version": "substrate-config.v1",
  "config_id": "cfg_demo",
  "states": [
    {"state_id": "s0"},
    {"state_id": "s1"}
  ],
  "preparations": [
    {
      "preparation_id": "prep0",
      "distribution": {
        "s0": 1.0
      }
    }
  ],
  "actions": [
    {
      "action_id": "flip",
      "transition_kernel": {
        "s0": {"s1": 1.0},
        "s1": {"s0": 1.0}
      }
    }
  ],
  "lenses": [
    {
      "lens_id": "binary",
      "readout_map": {
        "s0": "zero",
        "s1": "one"
      }
    }
  ],
  "protocols": [
    {
      "protocol_id": "flip2",
      "action_ids": ["flip", "flip"]
    }
  ],
  "defaults": {
    "trajectory_count": 4,
    "seed": 123
  },
  "metadata": {
    "family": "demo"
  }
}
```

## Validation notes
- Reject empty `states`, `preparations`, `actions`, `lenses`, or `protocols`.
- Reject duplicate IDs within any named list.
- Reject preparation distributions or transition rows that do not sum to 1 within tolerance.
- Reject preparations or actions that reference unknown hidden states.
- Reject action kernels that omit a hidden-state row.
- Reject lenses that do not define exactly one observation for every hidden state.
- Reject empty protocol action lists or unknown action references.
- Reject non-scalar values in `metadata`.
