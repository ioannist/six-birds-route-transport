# Three-Axis Hierarchy Config

## Purpose

`three-axis-hierarchy-config.v1` defines the aggregation input for the interim cross-axis hierarchy atlas. It points at stable mechanism-, lens-, and packaging-axis artifacts and records any synthesis/figure export settings needed by the atlas builder.

## Versioning

- Version field: `config_format_version`
- Initial value: `three-axis-hierarchy-config.v1`

## Required fields

- `config_format_version: str`
- `hierarchy_id: str`
- `mechanism_campaign_summary_ref: str`
- `mechanism_campaign_table_ref: str`
- `mechanism_witness_summary_ref: str`
- `lens_final_summary_ref: str`
- `packaging_campaign_summary_ref: str`
- `packaging_campaign_table_ref: str`
- `packaging_best_candidate_ref: str`

## Optional fields

- `synthesis_settings: object`
- `figure_export_settings: object`
- `output_category: str`
- `output_label: str | null`
- `notes: list[str]`
- `flags: list[str]`
- `metadata: object`

## Semantics

- mechanism refs must preserve the distinction between axis-wide campaign outcome and committed witness case
- lens final summary must already encode the same-step bounded-negative subregime and the cross-resolution flagship obstruction
- packaging refs must preserve the selector-branch caveat on the strongest current packaging evidence
- source refs must be repo-relative and stable enough for aggregation without rerunning the axis searches

## Validation notes

- TH6 must not collapse campaign outcomes, best evidence, and caveats into one field
- the config is aggregation-first; it is not a search sweep or a new experimental campaign
