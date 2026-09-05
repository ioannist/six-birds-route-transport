# Lens-axis final outcome

## Purpose

This format records the closed lens-axis conclusion after TH4 finalization. It preserves the bounded same-step negative subregime, promotes one cross-resolution strict-extension case as the canonical flagship, and exposes the machine-readable refs needed by later findings and paper-facing layers.

## Versioning

- Schema kind: `lens-axis-final-outcome`
- Version field: `final_outcome_format_version`
- Initial value: `lens-axis-final-outcome.v1`

## Data model

### Required fields

- `final_outcome_format_version`: string, must equal `lens-axis-final-outcome.v1`
- `lens_axis_id`: string
- `final_axis_status`: string
- `canonical_flagship_case_id`: string
- `same_step_table_artifact`: repo-relative path to the preserved same-step regime table
- `same_step_negative_summary_artifact`: repo-relative path
- `same_step_negative_outcome_artifact`: repo-relative path
- `cross_resolution_search_config_artifact`: repo-relative path
- `cross_resolution_package_build_summary_artifact`: repo-relative path
- `cross_resolution_provenance_summary_artifact`: repo-relative path
- `cross_resolution_quotient_summary_artifact`: repo-relative path
- `accepted_only_survivor_count`: non-negative integer
- `natural_pairing_survivor_count`: non-negative integer
- `accepted_proposal_obstruction`: boolean
- `final_claim_level`: one of the supported lens-axis claim levels
- `regimes`: non-empty list of regime rows

### Optional fields

- `accepted_only_failure_reason`: string or null
- `notes`: list of strings
- `flags`: list of strings
- `metadata`: flat metadata mapping

### Regime row fields

- `regime_label`: string
- `varies`: string
- `fixed`: string
- `candidate_class`: shared TH1 candidate class
- `quotient_witness_status`: `accepted_proposal_obstruction` | `candidate_subset_quotient_witness` | `no_quotient_obstruction`
- `flagship_artifact`: repo-relative path
- `control_artifact`: repo-relative path or null
- `notes`: list of strings
- `flags`: list of strings

### Invariants

- `regimes` must be unique by `regime_label`
- all artifact fields must be normalized repo-relative paths
- `accepted_proposal_obstruction = true` requires the canonical cross-resolution quotient summary to record an accepted obstruction
- the same-step regime may remain bounded-negative while the final axis status is obstruction-bearing

## Identifier conventions

- `lens_axis_id` identifies one closed axis statement
- `canonical_flagship_case_id` identifies the one case later findings should cite as the main lens-axis witness
- `regime_label` is unique only within one final outcome file

## Cross-file reference rules

- `same_step_table_artifact` and the same-step summary/outcome artifacts must refer to the bounded same-step TH4 run
- `cross_resolution_search_config_artifact` must point to the canonical obstruction-producing lens-axis config
- the cross-resolution package-build, provenance, and quotient-summary artifacts together define the flagship witness bundle

## Example

```json
{
  "final_outcome_format_version": "lens-axis-final-outcome.v1",
  "lens_axis_id": "lens_axis_th4_final",
  "final_axis_status": "closed_with_cross_resolution_accepted_obstruction",
  "canonical_flagship_case_id": "cross_res_all_steps",
  "same_step_table_artifact": "experiments/instances/lens-axis/th4_same_step_negative/lens-axis.json",
  "same_step_negative_summary_artifact": "experiments/instances/lens-axis/th4_same_step_negative/lens-axis-summary.json",
  "same_step_negative_outcome_artifact": "experiments/instances/lens-axis/th4_same_step_negative/negative-result.json",
  "cross_resolution_search_config_artifact": "experiments/configs/pica/lens-axis-cross-res-matching-campaign.json",
  "cross_resolution_package_build_summary_artifact": "experiments/instances/lens-axis/th4_cross_res_all_steps/package-build-summary.json",
  "cross_resolution_provenance_summary_artifact": "experiments/instances/lens-axis/th4_cross_res_all_steps/provenance-audit-summary.json",
  "cross_resolution_quotient_summary_artifact": "experiments/instances/lens-axis/th4_cross_res_all_steps/quotient-feasibility-summary.json",
  "accepted_only_survivor_count": 10,
  "natural_pairing_survivor_count": 13,
  "accepted_only_failure_reason": "coverage_failure",
  "accepted_proposal_obstruction": true,
  "final_claim_level": "provenance_admissible_strong_obstruction",
  "regimes": [
    {
      "regime_label": "same_step_bounded_negative",
      "varies": "same-step lens/projection family",
      "fixed": "mechanism and support fixed",
      "candidate_class": "weakly_frustrated_candidate",
      "quotient_witness_status": "candidate_subset_quotient_witness",
      "flagship_artifact": "experiments/instances/lens-axis/th4_same_step_negative/lens-axis.json"
    },
    {
      "regime_label": "cross_resolution_strict_extension",
      "varies": "cross-resolution obs_primary comparison",
      "fixed": "same mechanism and support fixed",
      "candidate_class": "strongly_nonextendable_candidate",
      "quotient_witness_status": "accepted_proposal_obstruction",
      "flagship_artifact": "experiments/instances/lens-axis/th4_cross_res_all_steps/quotient-feasibility-summary.json",
      "control_artifact": "experiments/instances/lens-axis/th4_cross_res_all_steps/quotient-feasibility-summary.json"
    }
  ]
}
```

## Validation notes

- later findings should trust `canonical_flagship_case_id`, not infer the flagship from path names
- the regime table is the authoritative explanation for why the same-step negative and cross-resolution obstruction are not contradictory
- natural-pairing control may be referenced through the shared quotient summary artifact rather than a separate file
