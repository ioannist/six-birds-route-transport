# Hidden Record Intervention

`hidden-record-intervention.v1` defines a validated input contract for a before/after
intervention run that exposes a previously hidden residue variable as an explicit
record-admissible field in an augmented event package.

## Required top-level fields

- `intervention_format_version`
  - must equal `"hidden-record-intervention.v1"`
- `intervention_id`
  - stable identifier for the intervention asset
- `before_instance_artifact`
  - repo-relative path to the source event-package instance
- `route_source_artifact`
  - repo-relative path to an observation trace carrying explicit route residue
- `residue_field_name`
  - field name made explicit by the intervention, for example `"route_id"`
- `residue_values`
  - finite ordered list of residue values used for context splitting
- `selected_context_ids`
  - context IDs in the before package that should be duplicated once per residue value
- `augmentation_policy`
  - technical policy label; v1 expects `"split_contexts_by_residue"`
- `proposal_residue_assignments`
  - explicit mapping from original proposal IDs to the residue values on which copied
    proposals should be created
- `comparison_config`
  - explicit run settings for before/after reruns
- `metadata`
  - optional flat metadata map

## `proposal_residue_assignments`

Each entry must contain:

- `proposal_id`
- `residue_values`
  - non-empty subset of the top-level `residue_values`
- `copied_constraint_kind`
  - optional override; if omitted, copied proposals inherit the source
    `constraint_kind`

This metadata controls proposal rewriting in the augmented package. The runner must
not infer residue assignment heuristically.

## `comparison_config`

The comparison config must support at minimum:

- `allow_relax_hard`
- `hard_proposal_relax_weight`
- `include_rm`

These settings control the structural-deficit reruns and optional RM reruns.

## Output expectations

The intervention runner consumes this input plus the referenced assets and produces a
bundle containing at minimum:

- `augmented-instance.json`
- `before-stat.json`
- `after-stat.json`
- `comparison-summary.json`
- `comparison-note.md`
- `result-note.json`
- `run-manifest.json`

The runner may also write additional provenance artifacts such as a route-refined
after-trace used for RM.
