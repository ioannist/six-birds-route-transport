# Best Evidence by Axis

## Purpose

`best-evidence-by-axis.v1` records the single best evidence object selected for each axis in the interim hierarchy atlas.

## Versioning

- Version field: `mapping_format_version`
- Initial value: `best-evidence-by-axis.v1`

## Required fields

- `mapping_format_version: str`
- `mapping_id: str`
- `entries: list[{axis, best_evidence_type, best_evidence_status, primary_artifact_refs, reason_for_selection}]`

## Entry semantics

Each entry must record:

- `axis`
- `best_evidence_type`
- `best_evidence_status`
- `primary_artifact_refs`
- optional `supporting_artifact_refs`
- `reason_for_selection`
- `caveat_flags`
- optional `notes`

## Selection rules

- mechanism best evidence may be a committed witness case even when the axis-wide campaign is design-inadequate
- lens best evidence should be the canonical cross-resolution flagship once TH4 is finalized
- packaging best evidence should be the strongest current accepted candidate, while preserving the selector-branch caveat if it still applies
