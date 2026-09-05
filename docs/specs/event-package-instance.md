# Event Package Instance

## Purpose
This spec defines the finite data contract for a single event-package instance: a bounded set of contexts, atoms, derived events, and proposed cross-context event equalities with audit metadata. It is intentionally structural only and does not prescribe any solver behavior.

## Version
- Version field name: `instance_format_version`
- Initial value: `"event-package-instance.v1"`

## Data model
An event-package instance is a JSON object with finite arrays for contexts and events, plus a list of equality proposals that reference those event IDs. All identifiers are local to the instance and must be stable strings.

## Field table
| Field | Required | Type | Constraints |
| --- | --- | --- | --- |
| `instance_format_version` | yes | string | Must equal `"event-package-instance.v1"`. |
| `instance_id` | yes | string | Unique within the repository; lowercase snake_case or `inst_*`. |
| `contexts` | yes | array<object> | Non-empty. Each context must declare atoms. |
| `events` | yes | array<object> | Non-empty. Each event must be a subset of atoms from exactly one context. |
| `equality_proposals` | yes | array<object> | May be empty. Each proposal references existing event IDs. |
| `weights` | no | object | Optional relaxable-constraint weights keyed by `weight_key`. Numeric, non-negative. |
| `notes` | no | string | Optional free-form technical notes. |
| `metadata` | no | object | Optional instance-level metadata map. Values must be JSON scalars or flat string arrays. |
| `audit` | yes | object | Audit metadata container. |

### `contexts` entries
| Field | Required | Type | Constraints |
| --- | --- | --- | --- |
| `context_id` | yes | string | Unique within the instance; lowercase snake_case or `ctx_*`. |
| `label` | no | string | Human-readable short label. |
| `atoms` | yes | array<object> | Non-empty and finite. |

### `atoms` entries
| Field | Required | Type | Constraints |
| --- | --- | --- | --- |
| `atom_id` | yes | string | Unique within the parent context; lowercase snake_case or `a_*`. |
| `label` | no | string | Short human-readable label. |

### `events` entries
| Field | Required | Type | Constraints |
| --- | --- | --- | --- |
| `event_id` | yes | string | Unique within the instance; lowercase snake_case or `ev_*`. |
| `context_id` | yes | string | Must reference an existing context. |
| `atom_ids` | yes | array<string> | Subset of the atom IDs in the referenced context; empty subset is allowed; order is not semantically meaningful. |
| `label` | no | string | Short human-readable label. |

### `equality_proposals` entries
| Field | Required | Type | Constraints |
| --- | --- | --- | --- |
| `proposal_id` | yes | string | Unique within the instance; lowercase snake_case or `eq_*`. |
| `left_event_id` | yes | string | Must reference an existing event. |
| `right_event_id` | yes | string | Must reference an existing event. |
| `constraint_kind` | yes | string | Either `"hard"` or `"soft"`. |
| `weight_key` | no | string | Required when `constraint_kind` is `"soft"` and must reference `weights`. |
| `notes` | no | string | Optional short technical rationale. |

### `audit` object
| Field | Required | Type | Constraints |
| --- | --- | --- | --- |
| `created_at` | yes | string | RFC 3339 timestamp. |
| `created_by` | no | string | Actor or process identifier. |
| `source` | no | string | Origin tag such as a command name or pipeline stage. |
| `checksum` | no | string | Optional content checksum for the serialized instance. |

## Identifier conventions
- `instance_id` identifies the whole record.
- `context_id` identifies a finite test context inside the instance.
- `atom_id` identifies one atomic outcome inside exactly one context.
- `event_id` identifies a subset of atoms within one context.
- `proposal_id` identifies a proposed equality between two events.
- Cross-object references must use the referenced object ID string, not positional indexes.
- IDs are case-sensitive and must be unique within their declared scope.

## Invariants
- Every context must contain at least one atom.
- Every event must reference exactly one context.
- Every `atom_id` in an event must exist in the referenced context.
- `atom_ids` must contain no duplicates.
- `equality_proposals` must not reference missing event IDs.
- `hard` proposals must omit `weight_key`.
- `soft` proposals must include `weight_key`, and the key must exist in `weights`.
- `weights` values must be finite non-negative numbers.

## Minimal valid example
```json
{
  "instance_format_version": "event-package-instance.v1",
  "instance_id": "inst_demo_001",
  "contexts": [
    {
      "context_id": "ctx_a",
      "label": "context A",
      "atoms": [
        { "atom_id": "a1", "label": "atom 1" },
        { "atom_id": "a2", "label": "atom 2" }
      ]
    },
    {
      "context_id": "ctx_b",
      "label": "context B",
      "atoms": [
        { "atom_id": "b1", "label": "atom 1" },
        { "atom_id": "b2", "label": "atom 2" }
      ]
    }
  ],
  "events": [
    {
      "event_id": "ev_a_1",
      "context_id": "ctx_a",
      "atom_ids": ["a1"]
    },
    {
      "event_id": "ev_b_1",
      "context_id": "ctx_b",
      "atom_ids": ["b1", "b2"]
    }
  ],
  "equality_proposals": [
    {
      "proposal_id": "eq_001",
      "left_event_id": "ev_a_1",
      "right_event_id": "ev_b_1",
      "constraint_kind": "soft",
      "weight_key": "w_eq_001"
    }
  ],
  "weights": {
    "w_eq_001": 0.5
  },
  "notes": "demo instance",
  "metadata": {
    "tag": "bootstrap"
  },
  "audit": {
    "created_at": "2026-03-25T00:00:00Z",
    "created_by": "bootstrap",
    "source": "manual"
  }
}
```

## Validation notes
- Reject duplicate IDs within each declared scope.
- Reject events whose `context_id` does not exist.
- Reject events whose `atom_ids` are not a subset of the referenced context atoms.
- Reject equality proposals that reference missing events.
- Reject soft proposals missing a matching `weights` entry.
- Reject non-scalar values in `metadata` and non-finite numeric weights.
