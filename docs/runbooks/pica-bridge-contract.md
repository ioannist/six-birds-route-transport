# PICA Bridge Contract

## Role split

- `vendor/six-birds-pica`
  Generative backend. It runs substrate campaigns, produces multilevel closure structure, and exports observable ledgers plus campaign/run metadata.
- This repo
  Event-package frontend. It consumes exported artifacts for discovery, shared-event inference, provenance-backed package building, admissibility auditing, obstruction evaluation, and later cross-checking.

## Artifact flow

1. PICA exports one `pica-export-bundle`.
2. The export bundle points to one or more `pica-campaign-export` artifacts.
3. Each campaign export inventories point IDs and run IDs.
4. Each run ID resolves to one `pica-run-ledger`, one `pica-closure-catalog`, and one `pica-observable-ledger`.
5. Later tickets in this repo ingest those bridge artifacts to build discovered contexts and provenance-backed event packages.

## Exported files and their purpose

- `pica-export-bundle`
  Top-level manifest for one export package. Declares the artifact set and stable IDs.
- `pica-campaign-export`
  Campaign-level provenance and point/run inventory.
- `pica-run-ledger`
  Per-run execution metadata, trajectory count, protocol-step metadata, and links to observable records and closure metadata.
- `pica-closure-catalog`
  Vertical structure artifact exposing levels, resolutions, closures, and lenses.
- `pica-observable-ledger`
  Row-level observable records used directly by this repo’s discovery pipeline.

## Stable identifier policy

- IDs are authoritative.
- Paths are retrieval pointers.
- Paths in bridge manifests are repo-relative.
- Required stable IDs in the bridge:
  - `export_bundle_id`
  - `campaign_id`
  - `point_id`
  - `run_id`
  - `substrate_config_id`
  - `mechanism_family_id`
  - `enable_matrix_id` when available
  - `preparation_id`
  - `protocol_id`
  - `trajectory_id`
  - `level_id`
  - `resolution_id`
  - `closure_id`
  - `lens_id`
  - `protocol_step_id`
  - `observable_ledger_id`

## Observable-first rule

- Required bridge inputs for downstream discovery and evaluation are:
  - observable ledgers
  - closure catalogs
  - campaign/run provenance
- Hidden or internal state may appear only as optional debug sidecars or optional debug fields.
- Hidden or internal state must never be required for:
  - context extraction
  - shared-event inference
  - provenance-backed package building
  - event-package evaluation

## Downstream consumer map

- Context discovery consumes:
  - `pica-run-ledger`
  - `pica-closure-catalog`
  - `pica-observable-ledger`
- Shared-event inference consumes:
  - `pica-observable-ledger`
  - `pica-closure-catalog`
  - discovered contexts generated in this repo
- Package provenance consumes:
  - `pica-export-bundle`
  - `pica-campaign-export`
  - source IDs copied into package provenance entries
- Admissibility audit consumes:
  - event-package provenance produced from the bridge artifacts
- Route-capable interventions may consume:
  - `route_label` fields from the observable ledger when present

## Later ticket consumers

- `T36`
  Implement typed schemas and validation for the bridge artifacts.
- Later ingestion ticket(s)
  Load bundle/campaign/run/closure/observable artifacts into repo-local models.
- Later discovery ticket(s)
  Build discovered context families from observable ledgers plus closure catalogs.
- Later provenance ticket(s)
  Map package provenance entries back to bridge artifact IDs and paths.

## Not part of the bridge

- Direct Python bindings into PICA
- PyO3 coupling
- In-memory runtime APIs
- Hidden-state identity as a required input
- Solver outputs, obstruction decisions, or package evaluations emitted by PICA

## Operational note

The bridge is artifact-based first. PICA generates the world and emits evidence artifacts. This repo reads those artifacts and judges the resulting event-package structure.
