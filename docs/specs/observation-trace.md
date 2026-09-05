# Observation Trace

## Purpose
This spec defines the technical contract for recording observations against an event-package instance, including per-context outcomes, repeated reads, downstream probes, and route metadata. It is a compact trace format for later validation and analysis.

## Version
- Version field name: `trace_format_version`
- Initial value: `"observation-trace.v1"`

## Data model
An observation trace is a JSON object with one optional instance link and a finite list of observation records. Repeated-read sequences, downstream probe signatures, and route-conditioned endpoint observations are attached as explicit arrays rather than inferred from free-form text.

## Field table
| Field | Required | Type | Constraints |
| --- | --- | --- | --- |
| `trace_format_version` | yes | string | Must equal `"observation-trace.v1"`. |
| `trace_id` | yes | string | Unique within the repository; lowercase snake_case or `trace_*`. |
| `instance_id` | no | string | When present, must reference an event-package instance ID. |
| `instance_artifact` | no | string | Optional repo-relative path to the linked instance artifact. |
| `observations` | yes | array<object> | Non-empty finite list of observation records. |
| `repeated_read_sequences` | no | array<object> | Optional repeated-read records grouped by context. |
| `downstream_probes` | no | array<object> | Optional probe signatures and payload summaries. |
| `route_observations` | no | array<object> | Optional route-conditioned endpoint distributions for RM analysis. |
| `route_trace` | no | object | Optional route-trace metadata container. |
| `metadata` | no | object | Optional technical metadata map with scalar values or flat string arrays. |

### `observations` entries
| Field | Required | Type | Constraints |
| --- | --- | --- | --- |
| `context_id` | yes | string | Must identify a context in the linked instance when `instance_id` is present. |
| `atom_ids` | yes | array<string> | Non-empty list of observed atom IDs for that context. |
| `status` | no | string | Optional observation status such as `"observed"` or `"inferred"`. |
| `count` | no | integer | Optional non-negative count associated with this observation. |
| `probability` | no | number | Optional finite probability in `[0, 1]`. |

### `repeated_read_sequences` entries
| Field | Required | Type | Constraints |
| --- | --- | --- | --- |
| `context_id` | yes | string | Must identify a context in the linked instance when applicable. |
| `reads` | yes | array<array<string>> | Non-empty sequence of repeated reads; each inner array is one readout over atom IDs and may be empty, singleton, or multi-outcome. |

### `downstream_probes` entries
| Field | Required | Type | Constraints |
| --- | --- | --- | --- |
| `probe_id` | yes | string | Probe family identifier. `(event_id, probe_id)` pairs must be unique within one trace. |
| `event_id` | no | string | Required for SEC-bearing probe records; must reference an event ID in the linked instance when linkage validation is used. |
| `context_id` | no | string | Optional redundant context ID; when `event_id` is present it must match the event context. |
| `signature` | yes | string | Stable probe signature label. |
| `outcome_counts` | no | object | Optional finite map from probe outcome ID to non-negative integer count. |
| `outcome_probabilities` | no | object | Optional finite map from probe outcome ID to probability in `[0, 1]`. |
| `payload` | no | object | Optional machine-facing probe payload summary. |

### `route_trace` object
| Field | Required | Type | Constraints |
| --- | --- | --- | --- |
| `route_id` | no | string | Stable route identifier. |
| `steps` | no | array<string> | Ordered route labels or stage names. |
| `notes` | no | string | Optional route note. |

### `route_observations` entries
| Field | Required | Type | Constraints |
| --- | --- | --- | --- |
| `preparation_id` | conditional | string | Exactly one of `preparation_id` or `macrostate_id` must be present. |
| `macrostate_id` | conditional | string | Exactly one of `preparation_id` or `macrostate_id` must be present. |
| `route_id` | yes | string | Explicit route identifier used for RM comparisons. |
| `endpoint_id` | yes | string | Explicit endpoint identifier for the compared output family. |
| `context_id` | no | string | Optional context ID when the endpoint is a context readout. |
| `outcome_counts` | no | object | Optional finite map from endpoint outcome ID to non-negative integer count. |
| `outcome_probabilities` | no | object | Optional finite map from endpoint outcome ID to probability in `[0, 1]`. |

## Identifier conventions
- `trace_id` identifies one trace record.
- `instance_id` links the trace back to the source instance.
- `instance_artifact` is a repo-relative path to the linked instance file when file-level provenance is needed.
- `context_id` and `atom_ids` reuse the same ID space as the linked instance.
- `event_id` on a downstream probe links the probe signature to an event already defined in the instance.
- `probe_id` identifies a downstream probe family, and `(event_id, probe_id)` identifies one event-conditioned signature record.
- `preparation_id` or `macrostate_id` identifies the explicit shared start condition for route comparisons.
- `route_id` identifies the explicit route under that start condition.
- `endpoint_id` identifies the compared endpoint distribution family.
- All IDs are case-sensitive and referenced by string equality, not by position.

## Invariants
- `observations` must contain at least one record.
- `instance_artifact`, when present, must be a normalized repo-relative path.
- If `instance_id` is present, every `context_id` and `atom_ids` entry must be valid for that instance.
- `count`, when present, must be a non-negative integer.
- `probability`, when present, must be finite and lie in `[0, 1]`.
- `reads` must preserve read order.
- A repeated-read step may be `[]`, `["a0"]`, or `["a0","a1"]` depending on whether the step records zero, one, or multiple simultaneously observed outcomes.
- `(event_id, probe_id)` pairs must be unique within a trace.
- A downstream probe may carry `outcome_counts` or `outcome_probabilities`, but not both.
- A route observation must carry exactly one of `preparation_id` or `macrostate_id`.
- A route observation may carry `outcome_counts` or `outcome_probabilities`, but not both.
- `metadata` values must be JSON scalars or flat string arrays only.

## Minimal valid example
```json
{
  "trace_format_version": "observation-trace.v1",
  "trace_id": "trace_demo_001",
  "instance_id": "inst_demo_001",
  "instance_artifact": "experiments/instances/inst_demo_001.json",
  "observations": [
    {
      "context_id": "ctx_a",
      "atom_ids": ["a1"],
      "count": 8,
      "probability": 0.8
    },
    {
      "context_id": "ctx_b",
      "atom_ids": ["b1", "b2"],
      "status": "observed"
    }
  ],
  "repeated_read_sequences": [
    {
      "context_id": "ctx_a",
      "reads": [["a1"], [], ["a1", "a2"]]
    }
  ],
  "downstream_probes": [
    {
      "event_id": "event_a1",
      "context_id": "ctx_a",
      "probe_id": "probe_001",
      "signature": "sig:stable",
      "outcome_counts": {
        "hit": 8,
        "miss": 2
      }
    }
  ],
  "route_observations": [
    {
      "preparation_id": "prep_001",
      "route_id": "route_alpha",
      "endpoint_id": "endpoint_readout",
      "context_id": "ctx_a",
      "outcome_counts": {
        "x0": 7,
        "x1": 3
      }
    }
  ],
  "route_trace": {
    "route_id": "route_main",
    "steps": ["read", "probe", "record"]
  },
  "metadata": {
    "source": "bootstrap"
  }
}
```

## Validation notes
- Reject empty `observations`.
- Reject duplicate `(event_id, probe_id)` pairs.
- Reject `instance_id` links whose contexts or atom IDs are unknown to the linked instance.
- Reject non-repo-relative `instance_artifact` paths.
- Reject negative counts or probabilities outside `[0, 1]`.
- Reject `reads` entries that contain non-string atom IDs or duplicate atom IDs within one read step.
- Reject downstream probes that carry both `outcome_counts` and `outcome_probabilities`.
- Reject route observations that do not carry exactly one of `preparation_id` or `macrostate_id`.
- Reject route observations that carry both `outcome_counts` and `outcome_probabilities`.
- Reject non-scalar values in `metadata`.
