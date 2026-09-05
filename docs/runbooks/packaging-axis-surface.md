# Packaging Axis Surface

This runbook defines the bridge contract for treating packaging as a first-class search axis.

- `packaging_source` is the producer/source route that yielded the selected packaging candidate.
- `packaging_operator_id` is the selected package-action identity used for comparison across support slices.
- `packaging_family_id` is the broader grouping used when multiple operators belong to one packaging family.

The bridge must preserve all three layers separately. Small cases may produce the same token in more than one layer, but later tickets must not assume identity collapse.

Required artifacts:
- `pica-packaging-operator-catalog.json`
- `pica-packaging-selection-ledger.json`
- `pica-packaging-surface-summary.json`
- `pica-packaging-source-index.json`

Minimum support indexing:
- `run_id`
- `preparation_id`
- `protocol_id`
- `protocol_step_id`
- `step_index`
- `closure_id`
- `trajectory_id` or `support_group_id`

Bridge/import expectations:
- the export bundle is authoritative for artifact linkage
- operator and family IDs are resolved through the operator catalog
- packaging selection rows are the row-level evidence for later packaging-axis claims
- provenance may attach packaging refs through `packaging_selection_ledger_id`, `packaging_selection_row_id`, `packaging_operator_id`, `packaging_family_id`, and `packaging_source`

Reporting expectations:
- counts of distinct operators and families
- source distribution
- selected operator/family distribution
- support-slice diversity

Later packaging-axis searches should use the summary for screening and the selection ledger for exact evidence.
