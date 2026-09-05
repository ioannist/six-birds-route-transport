# Lens-Axis Cross-Resolution Adjudication

## Purpose

`lens-axis-cross-resolution-adjudication.v1` records whether a committed cross-resolution witness remains inside the lens-axis contract after explicit theory reconciliation against the paper's frozen-slice, strict-extension, and package-change language.

## Versioning

- Schema kind: `lens-axis-cross-resolution-adjudication`
- Version field: `adjudication_format_version`
- Initial version: `lens-axis-cross-resolution-adjudication.v1`

## Data model

Required fields:
- `adjudication_format_version: string`
- `witness_case_id: string`
- `source_discovered_context_family_artifact: repo-relative path`
- `source_event_package_artifact: repo-relative path`
- `source_package_provenance_artifact: repo-relative path`
- `source_quotient_feasibility_audit_artifact: repo-relative path`
- `same_support_status: boolean`
- `same_run_status: boolean`
- `same_evaluation_regime_status: boolean`
- `same_step_status: boolean`
- `cross_resolution_status: boolean`
- `theory_alignment_flags: string[]`
- `consulted_paper_refs: string[]`
- `final_adjudication: "accepted_as_lens_axis_strict_extension" | "rejected_as_out_of_contract"`
- `rationale_notes: string[]`

Optional fields:
- `source_lens_family_admissibility_artifact: repo-relative path`
- `metadata: object`

Invariants:
- accepted adjudication requires `same_support_status = true`
- accepted adjudication requires `same_run_status = true`
- accepted adjudication requires `same_evaluation_regime_status = true`
- accepted adjudication requires `cross_resolution_status = true`
- accepted adjudication requires `same_step_status = false`

## Identifier conventions

- `witness_case_id` is unique within the repo-local witness family.
- Source artifact paths are authoritative and repo-relative.

## Cross-file reference rules

- The adjudication consumes a committed `quotient-feasibility-audit.json`.
- It must point to the committed `discovered-context-family.json`, `event-package.json`, and `package-provenance.json` used by the closure path.
- If present, `source_lens_family_admissibility_artifact` should point to the admissibility catalog governing the witness family.

## Example

```json
{
  "adjudication_format_version": "lens-axis-cross-resolution-adjudication.v1",
  "witness_case_id": "exp104_p6_row_all_n64_cross_res_k4_k20",
  "source_discovered_context_family_artifact": "experiments/instances/lens-axis/exp104_p6_row_all_n64_cross_res_k4_k20/discovered-context-family.json",
  "source_event_package_artifact": "experiments/instances/lens-axis/exp104_p6_row_all_n64_cross_res_k4_k20/event-package.json",
  "source_package_provenance_artifact": "experiments/instances/lens-axis/exp104_p6_row_all_n64_cross_res_k4_k20/package-provenance.json",
  "source_quotient_feasibility_audit_artifact": "experiments/instances/lens-axis/exp104_p6_row_all_n64_cross_res_k4_k20/quotient-feasibility-audit.json",
  "source_lens_family_admissibility_artifact": "experiments/instances/lens-axis/exp104_p6_row_all_n64_cross_res_k4_k20/lens-family-admissibility.json",
  "same_support_status": true,
  "same_run_status": true,
  "same_evaluation_regime_status": true,
  "same_step_status": false,
  "cross_resolution_status": true,
  "theory_alignment_flags": [
    "same_support_rows_fixed",
    "cross_resolution_strict_extension",
    "paper_aligned_strict_extension"
  ],
  "consulted_paper_refs": [
    "docs/papers/Tsiokos_2026_A_Six_Birds_Eye_View_of_Quantum_Theory_Operational_Closure_Semantics_for_Measurement_Contextuality_and_Record_Stability.tex:748-764"
  ],
  "final_adjudication": "accepted_as_lens_axis_strict_extension",
  "rationale_notes": [
    "The witness keeps mechanism and support fixed while varying resolution/lens on the same run."
  ],
  "metadata": {
    "quotient_witness_classification": "accepted_proposal_obstruction"
  }
}
```

## Validation notes

- The closure path relies on the adjudication being explicit, stable, and machine-readable.
- Later tickets may treat accepted adjudications as in-contract lens-axis witnesses and rejected adjudications as exploratory-only artifacts.
