# Provenance Audit Result

`provenance-audit-result.v1` is the machine-readable output of the package provenance audit.

It summarizes:

- provenance coverage
- unsupported items
- missing or unresolved source references
- refinement warnings
- final admissibility classification

## Required top-level fields

- `audit_format_version`
  Must equal `provenance-audit-result.v1`.
- `package_artifact`
  Repo-relative path to the audited event package.
- `provenance_artifact`
  Repo-relative path to the provenance sidecar when supplied, otherwise `null`.
- `package_id`
  Package instance ID.
- `audit_status`
  Current version uses `completed`.

## Coverage counts

- `context_total_count`
- `context_covered_count`
- `context_missing_count`
- `event_total_count`
- `event_covered_count`
- `event_missing_count`
- `proposal_total_count`
- `proposal_covered_count`
- `proposal_missing_count`

## Unsupported / unresolved counts

- `unsupported_context_count`
- `unsupported_event_count`
- `unsupported_proposal_count`
- `missing_source_ref_count`
- `unresolved_source_ref_count`
- `refinement_warning_count`

## Flags and classification

- `suspicious_refinement_flags`
  Auxiliary warnings, for example refinement-like IDs without admissible refinement support.
- `admissibility_classification`
  One of:
  - `admissible`
  - `partially_supported`
  - `unsupported`
- `artifact_refs`
  Repo-relative references to the summary, note, result note, and manifest written by the audit run.
- `notes`
  Optional explicit audit notes such as `no_provenance_manifest_supplied`.

## Intended interpretation

- `admissible`
  Complete covered package with resolving provenance and no unsupported refinement.
- `partially_supported`
  Some valid provenance exists, but coverage or source resolution is incomplete.
- `unsupported`
  No provenance, major coverage gaps, unresolved refinement support, or other provenance failures.
