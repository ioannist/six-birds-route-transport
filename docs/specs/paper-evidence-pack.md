# `paper-evidence-pack.v1`

`paper-evidence-pack.v1` is the stable top-level paper-facing evidence index.

Required fields:

- `pack_format_version`
- `evidence_pack_id`
- `theorem_experiment_map_ref`
- `flagship_witnesses_ref`
- `best_evidence_by_axis_ref`
- `control_bundle_summary_ref`
- `caveat_registry_ref`
- `theorem_side_anchor_refs`
- `mechanism_evidence_refs`
- `lens_evidence_refs`
- `packaging_evidence_refs`
- `control_bundle_evidence_refs`
- `hierarchy_claim_strength_refs`
- `figure_candidate_refs`
- `table_candidate_refs`
- `transient_gap_resolution`

Path rules:

- every referenced artifact path must be normalized repo-relative
- `figure_candidate_refs` must include `figure_candidates_manifest`
- `table_candidate_refs` must include `table_candidates_manifest`

Gap handling:

- `transient_gap_resolution` must include exactly:
  - `t50_runtime_outputs`
  - `th6_runtime_outputs`
- each value must be one of:
  - `committed_summary_substitution`
  - `fresh_rerun`
  - `not_needed`

Interpretation:

- the pack index is the stable drafting entry point
- it may point to committed summary substitutions when runtime bundles are not
  available in the snapshot
