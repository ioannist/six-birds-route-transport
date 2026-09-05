# Packaging-Conflict Search

## Purpose
`pica-packaging-conflict-search.v1` configures a bounded PICA search that restricts primary shared-event identity evidence to same-slice context pairs backed by structured package-conflict commutator support.

## Versioning
- Version field: `search_format_version`
- Initial value: `pica-packaging-conflict-search.v1`

## Required top-level fields
- `search_format_version`
- `search_id`
- `points`
- `projection_families`
- `source_pair_policy`
- `relevant_commutator_pairs`
- `commutator_admissibility_mode`
- `min_relevant_commutator_value`
- `event_generation_thresholds`
- `shared_event_inference_thresholds`
- `candidate_classification_thresholds`
- `adequacy_floor`

Optional:
- `provenance_required`
- `output_category`
- `output_label`
- `metadata`

## Point fields
Each point must provide:
- `point_id`
- `pilot_config_artifact`
- `preparation_id`
- `protocol_id`
- `trajectories`
- `seed_list`
- `projection_family_ids`
- `selected_protocol_step_ids`
- `selected_step_indices`

## Scientific rules encoded
- Primary contexts come only from projection families whose kind is `packaging_outcome` or `derived_row_outcome`.
- Primary source-pair identity requires a same frozen slice.
- Pairs differing only by projection field are not primary package-conflict evidence.
- `commutator_admissibility_mode` may be:
  - `p5_only`
  - `p5_p6_combined`
- Comparative reruns may execute both modes side by side against the same committed family.
- In `p5_only`, relevant nonzero `P5` commutator support is required for `primary_packaging_conflict`.
- In `p5_p6_combined`, relevant nonzero support may come from the configured `P5` pairs or the widened `P6` surface.
- Strong-candidate classification may treat either `no_respecting_tuples` or `coverage_failure` as genuine nonextendability.
- Accepted proposals must carry a support-relation diagnostic so same-support relabelings can be distinguished from cross-support matches.

## Required outputs
A run must write:
- `packaging-conflict-comparison.csv`
- `packaging-conflict-comparison.json`
- `context-pair-structure.json`
- `projection-family-admissibility.json`
- `pica-commutator-catalog-summary.json`
- `packaging-conflict-comparison-summary.json`
- `packaging-conflict-comparison-note.md`
- `result-note.json`
- `run-manifest.json`

And exactly one of:
- `best-candidate.json`
- `negative-result.json`
- `design-inadequate-result.json`
