# PICA Campaign Export

## Purpose

`pica-campaign-export.v1` is the campaign-level provenance artifact for a bridge export. It records the campaign label, source configuration, point inventory, and run inventory so downstream consumers can trace discovered contexts and package provenance back to campaign structure without opening raw execution internals.

## Versioning

- Required field: `schema_version`
- Initial value: `pica-campaign-export.v1`

## Data model

### Required fields

- `schema_version`
  String. Must equal `pica-campaign-export.v1`.
- `campaign_id`
  Stable campaign identifier.
- `campaign_label`
  Human-readable technical label.
- `source_config_path`
  Repo-relative path to the PICA campaign or substrate configuration.
- `path_policy`
  String. Initial required value: `repo_relative`.
- `mechanism_summary`
  Object. Must include `substrate_config_id`, `mechanism_family_id`, and may include `enable_matrix_id`.
- `point_inventory`
  Array of point records.
- `run_inventory`
  Array of run records.

### Point record required fields

- `point_id`
- `substrate_config_id`
- `mechanism_family_id`
- `preparation_id`
- `protocol_id`
- `seed`
- `run_id`

### Run record required fields

- `run_id`
- `point_id`
- `run_ledger_path`
- `closure_catalog_path`
- `observable_ledger_path`

### Optional fields

- `notes`
  Array of strings.
- `flags`
  Array of explicit status/limitation labels.

### Invariants

- Every `run_id` in `point_inventory` must appear exactly once in `run_inventory`.
- `source_config_path`, `run_ledger_path`, `closure_catalog_path`, and `observable_ledger_path` must be repo-relative.
- `point_id` values must be unique within the campaign.

## Identifier conventions

- `campaign_id`
  Unique within the export bundle.
- `point_id`
  Stable within a campaign. Recommended semantics: deterministic function of substrate config, preparation, protocol, and seed.
- `substrate_config_id`
  Bridge-level stable identifier for the configuration used to generate the point.
- `mechanism_family_id`
  Bridge-level stable identifier for the mechanism or experiment family.
- `enable_matrix_id`
  Optional but recommended stable identifier for the active mechanism matrix or equivalent activation set.

## Cross-file reference rules

- `run_inventory` points to the concrete run ledger, closure catalog, and observable ledger artifacts for each `run_id`.
- `point_inventory` is summary-level only and must not replace the run ledger.
- IDs remain authoritative; paths are retrieval pointers.

## Observable vs debug fields

- Required downstream bridge inputs:
  - `campaign_id`
  - `point_inventory`
  - `run_inventory`
  - stable configuration identifiers
- Optional/internal-only:
  - campaign notes
  - producer-specific labels beyond the stable IDs

## Minimal valid example

```json
{
  "schema_version": "pica-campaign-export.v1",
  "campaign_id": "campaign_example_v1",
  "campaign_label": "triadic_branch_contract_example",
  "source_config_path": "experiments/configs/substrates/triadic-branch.json",
  "path_policy": "repo_relative",
  "mechanism_summary": {
    "substrate_config_id": "substrate_config_triadic_branch_v1",
    "mechanism_family_id": "mechanism_family_triadic_branch",
    "enable_matrix_id": "enable_matrix_triadic_branch_default"
  },
  "point_inventory": [
    {
      "point_id": "point_triadic_branch_seed123",
      "substrate_config_id": "substrate_config_triadic_branch_v1",
      "mechanism_family_id": "mechanism_family_triadic_branch",
      "enable_matrix_id": "enable_matrix_triadic_branch_default",
      "preparation_id": "prep_default",
      "protocol_id": "protocol_branch_hold_hold",
      "seed": 123,
      "run_id": "run_triadic_branch_seed123"
    }
  ],
  "run_inventory": [
    {
      "run_id": "run_triadic_branch_seed123",
      "point_id": "point_triadic_branch_seed123",
      "run_ledger_path": "experiments/contracts/pica/examples/pica-run-ledger.json",
      "closure_catalog_path": "experiments/contracts/pica/examples/pica-closure-catalog.json",
      "observable_ledger_path": "experiments/contracts/pica/examples/pica-observable-ledger.json"
    }
  ],
  "notes": [
    "Contract example campaign only."
  ]
}
```

## Validation notes

- Validate that `point_inventory` and `run_inventory` keys are internally consistent.
- Validate uniqueness of `point_id` and `run_id` within the file.
- Validate that referenced artifact paths are repo-relative.
