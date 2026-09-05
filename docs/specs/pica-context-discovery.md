# PICA Context Discovery

## Purpose
This spec defines the validated configuration for PICA-native multi-layer context extraction. It tells the discovery layer which PICA export bundle to load, how to project observable-ledger rows into finite outcome labels, which multi-layer grouping key to use, and which deterministic thresholds govern acceptance or rejection.

## Version
- Version field name: `schema_version`
- Initial value: `"pica-context-discovery.v1"`

## Data model
A PICA context discovery config is a JSON object that points to one bridge-contract `pica-export-bundle` and fixes one observable-only extraction policy. The extractor groups rows by preparation, protocol, level, resolution, closure, lens, and protocol step, then projects one observable label per row before computing retained atoms and extraction diagnostics.

## Field table
| Field | Required | Type | Constraints |
| --- | --- | --- | --- |
| `schema_version` | yes | string | Must equal `"pica-context-discovery.v1"`. |
| `bundle_artifact` | yes | string | Normalized repo-relative path to a `pica-export-bundle`. |
| `selected_run_ids` | no | array<string> | Optional unique subset of run IDs to include. Empty means all runs in the bundle. |
| `selected_point_ids` | no | array<string> | Optional unique subset of point IDs to include. Empty means all points in the bundle. |
| `projection` | yes | object | Explicit observable projection policy. |
| `grouping_key_fields` | yes | array<string> | Must equal the required multilayer key field order. |
| `thresholds` | yes | object | Deterministic extraction thresholds. |
| `notes` | no | array<string> | Optional technical notes. |
| `flags` | no | array<string> | Optional explicit flags. |

### `projection` object
| Field | Required | Type | Constraints |
| --- | --- | --- | --- |
| `projection_mode` | yes | string | One of `observation_label`, `macrostate_label`, `phase_label`, `payload_numeric_bins`. |
| `payload_key` | no | string | Required when `projection_mode = "payload_numeric_bins"`. |
| `bin_edges` | no | array<number> | Required, finite, and sorted when `projection_mode = "payload_numeric_bins"`. |

### `thresholds` object
| Field | Required | Type | Constraints |
| --- | --- | --- | --- |
| `min_row_count` | yes | integer | Positive minimum row count per candidate key. |
| `min_atom_count` | yes | integer | Positive minimum retained atom count. |
| `min_atom_support_count` | yes | integer | Positive minimum support count per retained atom. |
| `min_atom_support_fraction` | yes | number | Minimum retained-atom support fraction in `[0, 1]`. |
| `min_coverage` | yes | number | Minimum retained-support coverage in `[0, 1]`. |
| `max_batch_tv` | yes | number | Maximum allowed deterministic batch TV in `[0, 1]`. |
| `batch_count` | yes | integer | Positive deterministic batch count. |

## Identifier conventions
- `bundle_artifact` is the authoritative input artifact reference.
- `selected_run_ids` and `selected_point_ids` refer to IDs already declared inside the resolved export bundle.
- `grouping_key_fields` is fixed to the multilayer observable key:
  - `preparation_id`
  - `protocol_id`
  - `level_id`
  - `resolution_id`
  - `closure_id`
  - `lens_id`
  - `protocol_step_id`

## Cross-file reference rules
- `bundle_artifact` must point to a valid `pica-export-bundle`.
- The bundle resolver uses bundle references to load `pica-campaign-export`, `pica-run-ledger`, `pica-closure-catalog`, and `pica-observable-ledger` artifacts.
- Run and point selection filters are applied after bundle resolution and before row grouping.

## Observable vs debug fields
- Required discovery inputs are limited to observable-ledger rows plus closure/lens metadata resolved through the bundle.
- Allowed observable projection sources are:
  - `observation_label`
  - `macrostate_label`
  - `phase_label`
  - one numeric `observation_payload` key discretized by explicit bins
- Hidden/internal/debug sidecars are not required inputs for this config and must not affect acceptance decisions.

## Minimal valid example
```json
{
  "schema_version": "pica-context-discovery.v1",
  "bundle_artifact": "experiments/contracts/pica/pilot/exp100_multiseed/pica-export-bundle.json",
  "selected_run_ids": [],
  "selected_point_ids": [],
  "projection": {
    "projection_mode": "payload_numeric_bins",
    "payload_key": "macro_gap",
    "bin_edges": [
      0.35,
      0.5,
      0.65
    ]
  },
  "grouping_key_fields": [
    "preparation_id",
    "protocol_id",
    "level_id",
    "resolution_id",
    "closure_id",
    "lens_id",
    "protocol_step_id"
  ],
  "thresholds": {
    "min_row_count": 2,
    "min_atom_count": 2,
    "min_atom_support_count": 1,
    "min_atom_support_fraction": 0.0,
    "min_coverage": 1.0,
    "max_batch_tv": 1.0,
    "batch_count": 2
  },
  "notes": [
    "Committed T38 multiseed discovery config."
  ],
  "flags": [
    "observable_only"
  ]
}
```

## Validation notes
- Reject non-repo-relative `bundle_artifact` paths.
- Reject unsupported or reordered `grouping_key_fields`.
- Reject `payload_numeric_bins` projection configs without `payload_key` or `bin_edges`.
- Reject unsorted or non-finite `bin_edges`.
- Reject duplicate or empty entries in `selected_run_ids`, `selected_point_ids`, `notes`, or `flags`.
- Reject threshold values outside their allowed ranges.
