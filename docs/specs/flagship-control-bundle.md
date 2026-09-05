# Flagship Control Bundle

`flagship-control-bundle.v1` defines a compact closure-oriented falsification bundle over committed flagship obstruction cases.

Required top-level fields:

- `bundle_format_version`
- `bundle_id`
- `flagship_cases`
- `verdict_rule_version`
- `metadata`

Each `flagship_cases[]` entry records:

- `case_id`
- `case_type`
  - `mechanism_witness`
  - `lens_flagship`
  - `packaging_flagship`
- `source_refs`
  - `discovered_context_family_artifact`
  - `event_package_artifact`
  - `package_provenance_artifact`
  - `shared_event_candidates_artifact`
  - `quotient_feasibility_summary_artifact`
  - `source_pica_bundle_artifact` when robustness is applicable
- `hidden_record`
- `flattening`
- `robustness`
- optional `baseline_metric_overrides`
- optional `notes`
- optional `metadata`

`hidden_record` and `flattening` reuse the intervention applicability structure:

- `applicable`
- optional `intervention_artifact`
- optional `reason`

`robustness` records:

- `applicable`
- `noise_grid`
- `noise_model`
- `metric_thresholds`
- `trace_families`
- optional `reason`

`baseline_metric_overrides` may supply pre-recorded diagnostic metrics for the committed flagship case:

- optional `gpd_str`
- optional `gpd_stat`

Each metric override has:

- `status`
- `value`
- optional `reason`

Semantics:

- The decisive pre/post obstruction backend remains the quotient-feasibility result already attached to the flagship theorem object.
- Hidden-record and flattening may be marked `not_applicable` explicitly when no same-support intervention preserves the committed theorem object.
- Robustness applies deterministic trace perturbation without changing the accepted proposal set or quotient backend.
