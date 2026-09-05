# `theorem-experiment-map.v1`

`theorem-experiment-map.v1` records how theorem-side anchors relate to numerical
or control evidence without collapsing all relations into equivalence.

Top-level fields:

- `map_format_version`
- `map_id`
- `theorem_object_label`
- `entries`

Each entry must contain:

- `theorem_anchor_id`
- `theorem_anchor_label`
- `relation_type`
- `primary_artifact_refs`
- optional `supporting_artifact_refs`
- optional `caveat_flags`
- optional `notes`

Allowed `relation_type` values:

- `direct_theorem_anchor`
- `direct_numerical_support`
- `supportive_case`
- `control_support`
- `formal_clarification`

Interpretation discipline:

- use `direct_theorem_anchor` for theorem-object-defining materials
- use `direct_numerical_support` only where the committed evidence directly
  supports the relevant theorem-facing claim
- use `supportive_case` when the relation is illustrative or bounded
- use `control_support` for false-positive / trustworthiness links
- use `formal_clarification` for hierarchy, frozen-slice, or proposition-layer links
