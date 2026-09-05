# PICA Export Bundle

## Purpose

`pica-export-bundle.v1` is the top-level manifest for one bridge export from PICA into this repo. It ties campaign-level provenance, run ledgers, closure catalogs, and observable ledgers into a single artifact set that downstream ingestion can validate and traverse without relying on in-memory APIs.

## Versioning

- Required field: `schema_version`
- Initial value: `pica-export-bundle.v1`

## Data model

### Required fields

- `schema_version`
  String. Must equal `pica-export-bundle.v1`.
- `export_bundle_id`
  Stable bundle identifier.
- `producer`
  Object with producer metadata. Must include `name`. May include `version`, `commit`, and `build_label`.
- `export_timestamp`
  ISO 8601 UTC timestamp.
- `path_policy`
  String. Initial required value: `repo_relative`.
- `campaign_exports`
  Array of objects with `campaign_id` and `artifact_path`.
- `run_ledgers`
  Array of objects with `run_id`, `campaign_id`, and `artifact_path`.
- `closure_catalogs`
  Array of objects with `closure_catalog_id`, `run_id`, and `artifact_path`.
- `observable_ledgers`
  Array of objects with `observable_ledger_id`, `run_id`, and `artifact_path`.

### Optional fields

- `notes`
  Array of strings.
- `flags`
  Array of explicit status/limitation labels.
- `debug_sidecars`
  Array of optional sidecar descriptors. These must not be required by downstream consumers.

### Invariants

- Every `artifact_path` must be repo-relative.
- Every referenced `campaign_id`, `run_id`, `closure_catalog_id`, and `observable_ledger_id` must be unique within the bundle.
- Every `run_id` referenced by a closure catalog or observable ledger must also appear in `run_ledgers`.

## Identifier conventions

- `export_bundle_id`
  Unique within this repo’s evidence base. Stable across regenerated exports only when the exported contents are intentionally the same contract bundle.
- `campaign_id`
  Campaign-scoped identifier defined by the campaign export.
- `run_id`
  Run-scoped identifier defined by the run ledger.
- `closure_catalog_id`
  Unique identifier for one closure catalog associated with a run.
- `observable_ledger_id`
  Unique identifier for one observable ledger associated with a run.

## Cross-file reference rules

- IDs are authoritative.
- Paths are convenience links for artifact retrieval.
- All cross-file links in bridge manifests use repo-relative paths.
- A consumer must resolve `campaign_id` and `run_id` by ID first, then use `artifact_path` to load the file.

## Observable vs debug fields

- Required downstream bridge inputs:
  - `campaign_exports`
  - `run_ledgers`
  - `closure_catalogs`
  - `observable_ledgers`
- Optional/internal-only:
  - `debug_sidecars`
  - producer build metadata beyond `name`

## Minimal valid example

```json
{
  "schema_version": "pica-export-bundle.v1",
  "export_bundle_id": "pica_export_bundle_example_v1",
  "producer": {
    "name": "pica",
    "version": "example",
    "commit": "example-commit"
  },
  "export_timestamp": "2026-03-26T00:00:00Z",
  "path_policy": "repo_relative",
  "campaign_exports": [
    {
      "campaign_id": "campaign_example_v1",
      "artifact_path": "experiments/contracts/pica/examples/pica-campaign-export.json"
    }
  ],
  "run_ledgers": [
    {
      "run_id": "run_triadic_branch_seed123",
      "campaign_id": "campaign_example_v1",
      "artifact_path": "experiments/contracts/pica/examples/pica-run-ledger.json"
    }
  ],
  "closure_catalogs": [
    {
      "closure_catalog_id": "closure_catalog_run_triadic_branch_seed123",
      "run_id": "run_triadic_branch_seed123",
      "artifact_path": "experiments/contracts/pica/examples/pica-closure-catalog.json"
    }
  ],
  "observable_ledgers": [
    {
      "observable_ledger_id": "observable_ledger_run_triadic_branch_seed123",
      "run_id": "run_triadic_branch_seed123",
      "artifact_path": "experiments/contracts/pica/examples/pica-observable-ledger.json"
    }
  ],
  "notes": [
    "Contract example bundle only."
  ]
}
```

## Validation notes

- Validate `schema_version` exactly.
- Validate uniqueness of bundle-level IDs and path entries.
- Validate that every `artifact_path` is a relative path with no `/tmp/` target.
- Validate that every closure catalog and observable ledger references a declared `run_id`.
