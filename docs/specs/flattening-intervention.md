# Flattening Intervention

`flattening-intervention.v1` defines a validated intervention input for a compact
before/after completion run in the finite substrate setting.

## Required top-level fields

- `intervention_format_version`
  - must equal `"flattening-intervention.v1"`
- `intervention_id`
- `source_config_artifact`
  - repo-relative substrate-config path
- `preparation_id`
- `before_protocol_id`
- `trajectory_count`
- `seed`
- `completion_policy`
- `route_extraction`
- `discovery_thresholds`
- `shared_event_inference_thresholds`
- `comparison_config`
- `metadata`

## Completion policy

The completion policy must define a deterministic protocol extension:

- `append_action_id`
- `append_repetitions`
- optional `after_protocol_id`

This ticket supports append-only completion. It does not define a generic rewrite
system.

## Route extraction

Route extraction must remain observable-driven and define at minimum:

- `route_lens_id`
- `route_step_index`
- `endpoint_lens_id`
- `before_endpoint_step_index`
- `after_endpoint_step_index`
- `endpoint_id`

Route IDs are derived from observable route-lens labels, not hidden-state IDs.

## Comparison config

The comparison config must record:

- structural-deficit settings
- whether RM should be included
- the material RM decrease threshold used by the conclusion rule

Status fields such as `unsolved`, `insufficient_data`, and `not_applicable` must be
preserved explicitly in the comparison bundle rather than coerced to numeric zero.
