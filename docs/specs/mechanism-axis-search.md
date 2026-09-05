# mechanism-axis-search

## Purpose

`mechanism-axis-search.v1` defines the bounded campaign format for comparing theory-points in mechanism space while holding lens, projection, packaging-policy, and evaluation conventions fixed as much as practical.

## Versioning

- `search_format_version`: must equal `"mechanism-axis-search.v1"`

## Data model

Required fields:

- `search_id: str`
- `points: list[MechanismAxisSearchPoint]`
- `projection_families: list[FrozenSliceProjectionFamily]`
- `active_projection_family_ids: list[str]`
- `selected_protocol_step_ids: list[str]`
- `selected_step_indices: list[int]`
- `fixed_lens_family_label: str`
- `fixed_packaging_policy_label: str`
- `event_generation_thresholds`
- `shared_event_inference_thresholds`
- `candidate_classification_thresholds`
- `adequacy_floor`

Optional fields:

- `claim_ceiling: "mechanism_dependence" | "nontrivial_multicontext_structure" | "package_conflict_tension"`
- `output_category: str`
- `output_label: str | null`
- `metadata: dict[str, MetadataValue]`

Per-point optional fields:

- `quotient_feasibility_audit_artifact`
  This points to a committed quotient-audit template whose same-slice selection and witness settings may be rebound to freshly built mechanism-axis artifacts.

Invariants:

- `point_id` values must be unique.
- `active_projection_family_ids` must resolve against `projection_families`.
- The config is mechanism-axis only and must not encode claim levels above the TH1 mechanism ceiling.

## Identifier conventions

- `search_id` is unique within the repo-level search registry.
- `point_id` is unique within one mechanism-axis campaign.

## Cross-file reference rules

- Each point references a committed `pica-pilot-campaign`.
- Later `mechanism-axis-row` outputs must carry the same `search_id`.
- If `quotient_feasibility_audit_artifact` is present, the runner may override only the source artifact paths while preserving the committed same-slice witness definition.

## Example

```json
{
  "search_format_version": "mechanism-axis-search.v1",
  "search_id": "mechanism_axis_example",
  "points": [
    {
      "point_id": "control",
      "pilot_config_artifact": "experiments/configs/pica/pilot-exp120-frozen-slice-control.json",
      "preparation_id": "prep_pica_default",
      "protocol_id": "protocol_pica_multiscale_scan",
      "trajectories": 24,
      "seed_list": [0]
    }
  ],
  "projection_families": [
    {
      "projection_id": "obs_primary",
      "label": "observation label",
      "source_field": "observation_label",
      "projection_kind": "packaging_outcome",
      "allowed_roles": ["primary_context"],
      "projection": {
        "projection_mode": "observation_label"
      }
    }
  ],
  "active_projection_family_ids": ["obs_primary"],
  "selected_protocol_step_ids": ["protocol_pica_multiscale_scan_step_1"],
  "selected_step_indices": [1],
  "fixed_lens_family_label": "observable_row_record_algebra_v1",
  "fixed_packaging_policy_label": "bridge_default_packaging_selector"
}
```

## Validation notes

- Later runners rely on the config to mean “mechanism varies, lens/projection/packaging-policy fixed as much as practical”.
- The adequacy floor must be explicit because mechanism-axis negative results are only meaningful when packaging-surface change is actually exercised.
