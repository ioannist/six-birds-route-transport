# Probe Indistinguishability Signature

## Purpose
This spec defines the machine-readable structural signature table produced during structural-primary shared-event inference. Each row records the probe-image event induced by conditioning a source event on a downstream probe context.

## Versioning
- Version field name: `signatures_format_version`
- Initial value: `"probe-indistinguishability-signature.v1"`

## Data model
Top-level fields:
- `signatures_format_version`
- `inference_id`
- `source_discovered_context_family_artifact`
- `source_run_artifacts` or `source_bundle_artifact`
- `source_mode`
- `thresholds`
- `signature_rows`
- `metadata`

### `signature_rows` fields
- `source_event_id`
- `source_context_id`
- `probe_context_id`
- `probe_image_atom_ids`
- `probe_image_event_kind`
- `conditioning_support_count`
- `support_by_retained_probe_atom`
- `structural_valid`
- optional `probe_distribution`
- optional `notes`
- optional `flags`

## Identifier conventions
- `source_event_id` is the generated event ID from the source context event algebra.
- `probe_context_id` is the accepted downstream probe context ID.
- The natural uniqueness key is `(source_event_id, probe_context_id)`.

## Cross-file reference rules
- `source_event_id` must resolve inside the generated discovered-event family used by the inference run.
- `source_context_id` and `probe_context_id` must resolve inside the linked discovered-context family.
- `thresholds` must match the thresholds embedded in the sibling `shared-event-candidates.json`.

## Observable vs debug fields
- Required observable fields:
  - conditioning support count
  - support by retained probe atom
  - probe-image retained atom set
  - structural-valid flag
- Optional debug/support fields:
  - normalized probe distribution
  - notes and flags

## Minimal valid example
```json
{
  "signatures_format_version": "probe-indistinguishability-signature.v1",
  "inference_id": "infer_demo",
  "source_discovered_context_family_artifact": "experiments/instances/discovered/demo/discovered-context-family.json",
  "source_run_artifacts": [
    "experiments/instances/smoke/substrate-runs/demo.json"
  ],
  "source_mode": "substrate_runs",
  "source_bundle_artifact": null,
  "thresholds": {
    "inference_mode": "structural_primary",
    "min_common_probes": 1,
    "min_conditioning_count": 3,
    "min_probe_atom_support_count": 1,
    "max_mean_tv": 0.15,
    "exact_tolerance": 1e-6,
    "proposal_constraint_kind": "soft"
  },
  "signature_rows": [
    {
      "source_event_id": "event_ctx_a__atom_left",
      "source_context_id": "ctx_a",
      "probe_context_id": "ctx_probe",
      "probe_image_atom_ids": ["atom_probe_left"],
      "probe_image_event_kind": "singleton",
      "conditioning_support_count": 3,
      "support_by_retained_probe_atom": {
        "atom_probe_left": 3,
        "atom_probe_right": 0
      },
      "structural_valid": true,
      "probe_distribution": {
        "atom_probe_left": 1.0
      },
      "notes": [],
      "flags": []
    }
  ],
  "metadata": {
    "observable_only": true
  }
}
```

## Validation notes
- `probe_image_atom_ids` must be unique.
- Non-empty probe-image kinds must carry non-empty atom IDs.
- `probe_distribution` must sum to `1` within tolerance when present.
- Signature tables are semantics-light: they validate artifact structure, not theorem-level identity claims.
