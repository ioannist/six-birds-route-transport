# PICA Discovery Readiness

## Purpose

`pica-discovery-readiness.v1` reports whether a resolved PICA export bundle preserves enough same-support observable structure to support later structural shared-event inference. It distinguishes aggregate-summary bundles from discovery-grade per-trajectory bundles.

## Versioning

- Version field: `schema_version`
- Initial value: `pica-discovery-readiness.v1`

## Data model

### Required fields

- `schema_version: str`
- `bundle_artifact: repo-relative path`
- `export_bundle_id: str`
- `pica_export_mode: "aggregate_summary" | "discovery_grade_per_trajectory"`
- `observation_granularity: "aggregate_summary" | "per_trajectory"`
- `cooccurrence_scope: "none" | "within_run" | "within_run_and_trajectory"`
- `run_count: int`
- `trajectory_count: int`
- `closure_count: int`
- `lens_count: int`
- `step_count: int`
- `context_key_count: int`
- `context_pair_count: int`
- `context_pairs_with_shared_trajectory_support: int`
- `context_pairs_with_probe_conditioning_potential: int`
- `supports_structural_probe_conditioning: bool`
- `readiness_classification: "discovery_grade_ready" | "discovery_grade_inadequate"`

### Optional fields

- `notes: list[str]`
- `flags: list[str]`
- `artifact_refs: dict[str, repo-relative path]`

## Invariants

- `bundle_artifact` and every `artifact_refs` value must be normalized repo-relative paths.
- `supports_structural_probe_conditioning = true` is allowed only when:
  - `observation_granularity = "per_trajectory"`
  - `cooccurrence_scope = "within_run_and_trajectory"`
- `readiness_classification = "discovery_grade_ready"` requires:
  - `supports_structural_probe_conditioning = true`
  - `context_pairs_with_shared_trajectory_support > 0`
  - `context_pairs_with_probe_conditioning_potential > 0`

## Minimal valid example

```json
{
  "schema_version": "pica-discovery-readiness.v1",
  "bundle_artifact": "experiments/contracts/pica/pilot/exp120_discovery_grade/pica-export-bundle.json",
  "export_bundle_id": "pica_pilot_exp120_discovery_grade_bundle",
  "pica_export_mode": "discovery_grade_per_trajectory",
  "observation_granularity": "per_trajectory",
  "cooccurrence_scope": "within_run_and_trajectory",
  "run_count": 1,
  "trajectory_count": 24,
  "closure_count": 4,
  "lens_count": 4,
  "step_count": 4,
  "context_key_count": 4,
  "context_pair_count": 6,
  "context_pairs_with_shared_trajectory_support": 6,
  "context_pairs_with_probe_conditioning_potential": 6,
  "supports_structural_probe_conditioning": true,
  "readiness_classification": "discovery_grade_ready",
  "notes": [
    "Contract example only."
  ],
  "flags": [
    "discovery_grade_per_trajectory"
  ],
  "artifact_refs": {
    "summary": "results/results/20260328T000000Z--pica_discovery_readiness/pica-discovery-readiness-summary.json"
  }
}
```

## Validation notes

- Reject negative counts.
- Reject invalid artifact paths.
- Reject structurally impossible readiness claims.
- Keep aggregate-summary bundles valid, but classify them as discovery-grade-inadequate.
