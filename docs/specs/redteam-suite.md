# redteam-suite

Technical schema for compact adversarial suite configs consumed by the T27 red-team runner.

## Version field

- `suite_format_version = "redteam-suite.v1"`

## Required top-level fields

- `suite_id`: stable suite identifier
- `cases`: non-empty list of case entries; T27 committed suite uses at least three
- `metadata`: optional flat metadata map

## Case entry fields

- `case_id`: stable case identifier
- `adversarial_type`: one of:
  - `hidden_label_smuggling`
  - `schedule_protocol_residue_artifact`
  - `flattenable_route_mismatch`
  - `bad_shared_event_proposals`
- `runner_mode`: one of:
  - `structural_only`
  - `hidden_record_intervention`
  - `flattening_intervention`
  - `sec_audit`
- `asset_refs`: normalized repo-relative input asset paths
- `expected_issue_type`: short technical description of the adversarial issue
- `expected_framework_response`: optional expected response label
- `classification_thresholds`: optional case-specific thresholds/flags
- `notes`: optional technical notes

## Runner mode asset requirements

- `structural_only`: requires `asset_refs.instance`
- `hidden_record_intervention`: requires `asset_refs.intervention`
- `flattening_intervention`: requires `asset_refs.intervention`
- `sec_audit`: requires `asset_refs.instance` and `asset_refs.trace`

## Response labels

- `flagged`
- `corrected`
- `partially_flagged`
- `partially_corrected`
- `not_flagged`

## Semantics

- The suite runner wraps existing structural / audit / intervention reporters.
- Unsupported metrics remain status-tagged rather than coerced to numeric zero.
- A case may honestly land in `not_flagged` if the current automated framework does not mark the adversarial issue.
