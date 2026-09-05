# PICA Pilot Campaign

## Purpose

`pica-pilot-campaign` defines one bounded subprocess-backed wrapper run against `vendor/six-birds-pica/`. The format fixes the vendor root, invocation mode, bounded run settings, and export policy used to normalize vendor output into this repo's bridge-contract artifacts. It distinguishes the bridge-normalization mode from the observable export granularity requested from PICA.

## Versioning

- Version field: `schema_version`
- Initial value: `pica-pilot-campaign.v1`

## Data model

### Required fields

- `schema_version: str`
- `pilot_campaign_id: str`
- `pilot_label: str`
- `source_config_path: repo-relative path`
- `invocation: object`
- `run_settings: object`
- `export_settings: object`
- `campaign_id: str`
- `campaign_label: str`
- `point_id: str`
- `substrate_config_id: str`
- `mechanism_family_id: str`
- `preparation_id: str`
- `protocol_id: str`

### Optional fields

- `enable_matrix_id: str | null`
- `notes: list[str]`
- `flags: list[str]`

### `invocation`

- `vendor_root: repo-relative path`
- `manifest_path: repo-relative path`
- `command_mode: "cargo_runner_release"`
- `cargo_target_dir: repo-relative path`
- `binary_name: str`

### `run_settings`

- `exp_id: str`
- `config_name: str`
- `seed: int`
- `scale: int`
- `timeout_seconds: int`

### `export_settings`

- `export_mode: "adapter_export" | "native_export"`
- `pica_export_mode: "aggregate_summary" | "discovery_grade_per_trajectory"`
- `artifact_output_mode: "run_dir"`
- `path_policy: "repo_relative" | "bundle_relative"`
- `adapter_mode: str | null`

## Invariants

- The wrapper must launch PICA via subprocess only.
- `vendor_root` must point at `vendor/six-birds-pica/` or another repo-relative vendor root.
- `cargo_target_dir` must be outside the vendor tree if the wrapper builds vendor binaries.
- `source_config_path`, `vendor_root`, `manifest_path`, and `cargo_target_dir` must be normalized repo-relative paths.
- `scale` and `timeout_seconds` must be positive integers.
- `adapter_mode` must be non-empty when present.
- `pica_export_mode = "discovery_grade_per_trajectory"` requests a per-trajectory export suitable for later structural probe conditioning.

## Minimal valid example

```json
{
  "schema_version": "pica-pilot-campaign.v1",
  "pilot_campaign_id": "pica_pilot_exp100_baseline",
  "pilot_label": "exp100_baseline_small_wrapper_run",
  "source_config_path": "experiments/configs/pica/pilot-campaign.json",
  "invocation": {
    "vendor_root": "vendor/six-birds-pica",
    "manifest_path": "vendor/six-birds-pica/Cargo.toml",
    "command_mode": "cargo_runner_release",
    "cargo_target_dir": ".cache/pica-target",
    "binary_name": "runner"
  },
  "run_settings": {
    "exp_id": "EXP-100",
    "config_name": "baseline",
    "seed": 0,
    "scale": 32,
    "timeout_seconds": 120
  },
  "export_settings": {
    "export_mode": "adapter_export",
    "pica_export_mode": "discovery_grade_per_trajectory",
    "artifact_output_mode": "run_dir",
    "path_policy": "repo_relative",
    "adapter_mode": "key_audit_json_discovery_grade_v1"
  },
  "campaign_id": "pica_campaign_exp100_baseline",
  "campaign_label": "exp100_baseline_adapter_campaign",
  "point_id": "point_exp100_baseline_seed0",
  "substrate_config_id": "pica_exp100_baseline",
  "mechanism_family_id": "pica_exp100_family",
  "enable_matrix_id": "pica_exp100_baseline_matrix",
  "preparation_id": "prep_pica_default",
  "protocol_id": "protocol_pica_multiscale_scan",
  "notes": [
    "Thin wrapper pilot over vendor/six-birds-pica."
  ],
  "flags": [
    "bounded",
    "adapter_export"
  ]
}
```

## Validation notes

- T37 validation should reject non-repo-relative vendor paths.
- T37 validation should reject embedded/in-process invocation modes.
- T37 validation should reject empty labels, IDs, and non-positive run bounds.
- T37.2 validation should preserve legacy aggregate-summary configs while making discovery-grade export explicit.
