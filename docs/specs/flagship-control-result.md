# Flagship Control Result

`flagship-control-result.v1` stores the per-case and bundle-level trustworthiness verdicts for the flagship control suite.

Required top-level fields:

- `result_format_version`
- `bundle_id`
- `cases`
- `overall_bundle_verdict`
- `artifact_refs`
- optional `notes`

Each `cases[]` entry records:

- `case_id`
- `case_type`
- `source_refs`
- `hidden_record`
- `flattening`
- `robustness`
- `final_verdict`
- `artifact_refs`
- optional `notes`

Each control summary records:

- `applicability_status`
  - `completed`
  - `not_applicable`
- `verdict`
  - `survived`
  - `weakened`
  - `disappeared`
  - `not_applicable`
  - `inconclusive`
- optional `reason`
- `pre_control`
- optional `post_control`
- optional `run_id`
- `artifact_refs`
- `first_crossings`
- optional `notes`

`pre_control` and `post_control` are `FlagshipMetricSnapshot` objects with:

- `witness_classification`
- `exact_feasible`
- `survivor_count`
- optional `failure_reason`
- optional `quotient_class_count`
- optional `uncovered_atom_count`
- `gpd_str`
- `gpd_stat`

Each metric field is an explicit status/value pair:

- `status`
  - `solved`
  - `unsolved`
  - `insufficient_data`
  - `not_applicable`
- optional `value`
- optional `reason`

Bundle-level verdicts:

- `all_applicable_flagships_survived`
- `mixed_outcomes`
- `some_disappeared`
- `mostly_not_applicable`

Semantics:

- `pre_control` and `post_control` preserve the same quotient-backed theorem object that generated the accepted flagship claim.
- For robustness, `post_control` keeps the accepted proposal set and quotient exact result fixed while updating trace-sensitive diagnostics.
- `not_applicable` is explicit and never treated as survival.
