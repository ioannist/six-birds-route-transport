# PICA Pilot Result

## Purpose

`pica-pilot-result` records the outcome of one wrapper-driven bounded PICA run. The result captures the subprocess command, return code, stable bridge artifact paths, bridge validation status, the requested PICA export granularity, and the headline counts extracted from the resolved bundle.

## Versioning

- Version field: `schema_version`
- Initial value: `pica-pilot-result.v1`

## Data model

### Required fields

- `schema_version: str`
- `pilot_run_id: str`
- `pilot_config_path: repo-relative path`
- `vendor_root_path: repo-relative path`
- `wrapper_command: list[str]`
- `command_mode: "cargo_runner_release"`
- `export_mode: "adapter_export" | "native_export"`
- `pica_export_mode: "aggregate_summary" | "discovery_grade_per_trajectory"`
- `observation_granularity: "aggregate_summary" | "per_trajectory"`
- `cooccurrence_scope: "none" | "within_run" | "within_run_and_trajectory"`
- `supports_structural_probe_conditioning: bool`
- `return_code: int`
- `success: bool`
- `bridge_validation_status: "validated" | "failed"`
- `stable_artifacts: object`
- `summary_counts: object`

### Optional fields

- `adapter_mode: str | null`
- `notes: list[str]`
- `flags: list[str]`

### `stable_artifacts`

- `export_bundle: repo-relative path`
- `campaign_export: repo-relative path`
- `run_ledger: repo-relative path`
- `closure_catalog: repo-relative path`
- `observable_ledger: repo-relative path`
- `stdout: repo-relative path | null`
- `stderr: repo-relative path | null`

### `summary_counts`

- `campaign_count: int`
- `run_count: int`
- `closure_count: int`
- `lens_count: int`
- `observable_ledger_count: int`

## Invariants

- `wrapper_command` must be the actual subprocess command used for the PICA run, not an in-process import path.
- Stable artifact paths must point to bridge-contract artifacts produced in stable repo-local locations.
- `bridge_validation_status = "validated"` means the produced `pica-export-bundle` loaded successfully through the T36 importer.
- `success = true` requires a non-failing wrapper subprocess outcome and successful bridge artifact production.
- Discovery-grade positive cases should report `observation_granularity = "per_trajectory"` and `supports_structural_probe_conditioning = true`.

## Minimal valid example

```json
{
  "schema_version": "pica-pilot-result.v1",
  "pilot_run_id": "run_results_20260326t140000z_pica_pilot",
  "pilot_config_path": "experiments/configs/pica/pilot-campaign.json",
  "vendor_root_path": "vendor/six-birds-pica",
  "wrapper_command": [
    ".cache/pica-target/release/runner",
    "--exp",
    "EXP-100",
    "--seed",
    "0",
    "--scale",
    "32",
    "--config",
    "baseline"
  ],
  "command_mode": "cargo_runner_release",
  "export_mode": "adapter_export",
  "pica_export_mode": "discovery_grade_per_trajectory",
  "adapter_mode": "key_audit_json_discovery_grade_v1",
  "observation_granularity": "per_trajectory",
  "cooccurrence_scope": "within_run_and_trajectory",
  "supports_structural_probe_conditioning": true,
  "return_code": 0,
  "success": true,
  "bridge_validation_status": "validated",
  "stable_artifacts": {
    "export_bundle": "results/results/20260326T140000Z--pica_pilot/pica-export-bundle.json",
    "campaign_export": "results/results/20260326T140000Z--pica_pilot/pica-campaign-export.json",
    "run_ledger": "results/results/20260326T140000Z--pica_pilot/pica-run-ledger.json",
    "closure_catalog": "results/results/20260326T140000Z--pica_pilot/pica-closure-catalog.json",
    "observable_ledger": "results/results/20260326T140000Z--pica_pilot/pica-observable-ledger.json",
    "stdout": "results/results/20260326T140000Z--pica_pilot/stdout.txt",
    "stderr": "results/results/20260326T140000Z--pica_pilot/stderr.txt"
  },
  "summary_counts": {
    "campaign_count": 1,
    "run_count": 1,
    "closure_count": 4,
    "lens_count": 4,
    "observable_ledger_count": 1
  },
  "notes": [
    "Thin subprocess wrapper executed vendor/six-birds-pica."
  ],
  "flags": [
    "adapter_export"
  ]
}
```

## Validation notes

- T37 validation should reject empty subprocess command arrays.
- T37 validation should reject non-repo-relative stable artifact paths.
- T37 validation should reject negative summary counts and mismatched success/validation combinations.
- T37.2 validation should reject `supports_structural_probe_conditioning = true` when the result does not report per-trajectory, within-run-and-trajectory exports.
