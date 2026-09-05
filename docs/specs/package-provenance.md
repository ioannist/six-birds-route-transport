# Package Provenance

`package-provenance.v1` is a machine-readable sidecar for an event package.

It records admissible origin coverage for:

- contexts
- events
- equality proposals

The format is intended for designed benchmark packages, discovery-derived packages, and intervention-derived refinements.

## Required top-level fields

- `provenance_format_version`
  Must equal `package-provenance.v1`.
- `package_artifact`
  Repo-relative path to the event-package JSON under audit.
- `package_id`
  Package instance ID.
- `provenance_mode`
  Explicit provenance mode such as `designed_master_model`, `designed_explicit_witness`, `derived`, or `intervention_derived`.
- `source_artifacts`
  Repo-relative source artifact map referenced by the provenance entries.
- `context_entries`
  Coverage entries for every context ID in the package.
- `event_entries`
  Coverage entries for every event ID in the package.
- `proposal_entries`
  Coverage entries for every proposal ID in the package.
- `metadata`
  Optional flat metadata.

## Entry shape

Each context / event / proposal entry contains:

- the object ID
- `origin_kind`
- one or more `source_refs`
- optional `pica_ref` inside each `source_ref`
- optional `source_context_id`
- optional `source_atom_ids`
- optional ancestor ID
- optional `refinement`
- optional notes

## `source_refs`

Each source reference contains:

- `artifact`
  Repo-relative path to the supporting source artifact.
- `source_kind`
  Explicit support label such as `designed_context`, `derived_atomic_outcome`, `derived_shared_event_match`, `ancestor_proposal`, or `intervention_proposal_assignment`.
- `source_item_id`
  Optional source-local ID when item-level resolution is available.

## Refinement provenance

Refinement entries are required for intervention-style or split/refined objects when applicable.

`refinement` contains:

- `ancestor_id`
- `residue_field_name`
- `residue_value`
- `source_artifact`

This is the explicit admissibility hook for route-split or residue-split package structure.

## PICA-backed source references

When a provenance entry is backed by a PICA export bundle, each `source_ref` may carry a `pica_ref` object in addition to the existing `artifact` and `source_kind` fields.

`pica_ref` contains:

- `export_bundle_id`
- `campaign_id`
- `run_id`
- `observable_ledger_id`
- `closure_id`
- `lens_id`
- `level_id`
- `resolution_id`
- `preparation_id`
- `protocol_id`
- at least one of:
  - `protocol_step_id`
  - `step_index`
- optional `source_row_filters`

### PICA row-filter contract

`source_row_filters` keys must be actual `PicaObservableRow` field names.
The canonical allowed set is:

- `trajectory_id`
- `step_index`
- `protocol_step_id`
- `preparation_id`
- `protocol_id`
- `level_id`
- `resolution_id`
- `closure_id`
- `lens_id`
- `observation_label`
- `route_label`
- `phase_label`
- `macrostate_label`

Synthetic or composite identifiers (such as `context_id`) must **not** appear as
row-filter keys unless they are actual fields on `PicaObservableRow`.

The provenance audit explicitly counts unknown row-filter fields via
`unknown_row_filter_field_count` and treats their presence as a provenance error
that blocks `admissible` classification.

These fields make PICA-backed source references first-class provenance objects without requiring hidden-state identifiers.

## Intended audit semantics

A provenance manifest is expected to provide:

- complete context/event/proposal coverage
- resolving source references where practical
- explicit ancestry for refinement-derived objects
- explicit retained-atom unions for coarse events when applicable
- explicit event-algebra mode and event-kind notes for generated empty/full/proper-coarse events when applicable

Missing coverage, unresolved sources, or unsupported refinement metadata are preserved explicitly by the provenance audit rather than coerced into a pass.

## Structural shared-event proposal provenance

When a proposal is accepted from structural-primary shared-event inference, its provenance notes should record at minimum:

- `inference_mode:structural_primary`
- accepted source event IDs
- accepted source retained atom IDs
- one or more `common_probe_id:...` notes

This keeps accepted discovery-side proposal identity tied to explicit observable probe signatures rather than only to aggregate statistical closeness.
