# Ledger JSONL Schemas

All ledger files are **append-only**. Never modify existing entries — append new entries
with updated status fields. Each line is a valid JSON object.

## hypotheses.jsonl

```json
{
  "id": "HYP-###",
  "layer": 0,
  "status": "proposed|supported|refuted|retracted",
  "claim": "The hypothesis statement",
  "primitives_used": ["P1", "P2"],
  "input_closures": ["CLO-000"],
  "falsification_criterion": "What would disprove this",
  "proposed_experiment": "EXP-###",
  "timestamp": "ISO 8601"
}
```

## experiments.jsonl

```json
{
  "id": "EXP-###",
  "hypothesis_id": "HYP-###",
  "status": "running|complete",
  "description": "What the experiment does",
  "parameters": {
    "scale_range": [32, 64, 128, 256],
    "seed_range": [0, 9]
  },
  "metrics": ["metric_name_1", "metric_name_2"],
  "artifacts_dir": "lab/artifacts/EXP-###/",
  "timestamp": "ISO 8601"
}
```

Status updates are appended as new entries (same ID, new status).

## closures.jsonl

```json
{
  "id": "CLO-###",
  "layer": 0,
  "status": "verified|RETRACTED",
  "description": "What was established",
  "detection_method": "how it was detected",
  "stability_score": 1e-15,
  "robustness_rate": 1.0,
  "epsilon": 1e-6,
  "persistence_threshold": 0.8,
  "supporting_experiments": ["EXP-###"],
  "supporting_runs": ["description of runs"],
  "primitives_involved": ["P1", "P2"],
  "timestamp": "ISO 8601"
}
```

Retractions are recorded as new entries with `"status": "RETRACTED"` and an explanation
in the description field. The original entry is never modified.

## ID Conventions

- Hypothesis: `HYP-###` (zero-padded 3 digits)
- Experiment: `EXP-###`
- Closure: `CLO-###`
- Result run: `RUN-<exp>-<seed>-<scale>-<hash>`
- Lens hypothesis: `LENS-###` (in lens_hypotheses.md, not JSONL)

## KEY_AUDIT_JSON (stdout artifact)

Machine-readable audit records emitted during sweeps alongside existing `KEY_100_*` lines.
Each line is: `KEY_AUDIT_JSON {json}` where `{json}` is a single JSON object.

Schema version 1. Defined in `crates/dynamics/src/audit.rs` (`AuditRecord` struct).

Three tiers:
- **lite**: per-observation snapshot (fast, no extra computation)
- **standard**: per-refresh / end-of-run (partition stats, event counters, cross-layer ratios)
- **rich**: end-of-run (multi-scale scan, full macro diagnostics)

Key fields: `schema_version`, `tier`, `exp_id`, `seed`, `n`, `step`, `pica_config_hash`
(FNV hash of enable matrix + lens_selector), plus tier-specific metric fields
(all `Option<f64>` — `null` when unavailable).

See `lab/ledger/AUDITS_CATALOG.md` for the full metrics inventory and tier specifications.
