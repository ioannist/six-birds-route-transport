# Three-Axis Hierarchy Row

## Purpose

`three-axis-hierarchy-row.v1` defines one axis summary row inside the hierarchy atlas. Each row must preserve three distinct layers:

1. axis-wide campaign outcome
2. best witness / flagship evidence
3. claim ceiling / caveat structure

## Versioning

- Version field: `row_format_version`
- Initial value: `three-axis-hierarchy-row.v1`

## Required fields

- `row_format_version: str`
- `row_id: str`
- `hierarchy_id: str`
- `axis: "mechanism" | "lens" | "packaging"`
- `axis_campaign_outcome_kind`
- `axis_campaign_outcome_label`
- `best_evidence_type`
- `best_witness_label`
- `best_witness_status`
- `accepted_proposal_obstruction_count: int`
- `candidate_subset_quotient_witness_count: int`
- `no_quotient_obstruction_count: int`
- `claim_level_supported: str`
- `caveat_flags: list[str]`
- `primary_artifact_refs: object`

## Optional fields

- `supporting_artifact_refs: object`
- `notes: list[str]`
- `flags: list[str]`

## Semantics

- `axis_campaign_outcome_kind` records the axis-wide campaign status only
- `best_witness_status` records the strongest current quotient-backed witness status for the axis
- quotient status counts summarize the current axis evidence record, not only the axis-wide campaign
- mechanism rows may have `axis_campaign_outcome_kind = design_inadequate` while still carrying an accepted witness
- lens rows must preserve both same-step bounded negative and cross-resolution obstruction structure
- packaging rows must preserve the selector-branch caveat if the strongest accepted evidence still depends on it
