# Structural Shared-Event Inference

## Purpose
This spec defines the structural-primary shared-event inference mode used after full event-algebra generation. The primary acceptance rule is probe-image equality across admissible downstream contexts; total variation and confidence scores remain secondary metadata for ranking and reporting.

## Versioning
- Version carrier: `SharedEventInferenceThresholds.inference_mode`
- Primary mode value: `structural_primary`
- Legacy compatibility mode: `legacy_statistical_primary`

## Data model
- Inference inputs:
  - one validated `discovered-context-family`
  - one generated `discovered-event-family`
  - either raw substrate runs or a resolved PICA export bundle
- Inference outputs:
  - `probe-indistinguishability-signatures.json`
  - `shared-event-candidates.json`
  - provenance-backed accepted proposals in the built event package

### Required threshold fields
- `inference_mode`
- `min_common_probes`
- `min_conditioning_count`
- `min_probe_atom_support_count`
- `max_mean_tv`
- `exact_tolerance`
- `proposal_constraint_kind`

### Structural rule
For candidate events `E` and `F` from admissible source contexts, define admissible downstream probe contexts as other accepted contexts with the same `preparation_id` and `protocol_id`, excluding the two sources. For each common structurally valid probe context `P`, compute:

`Img_P(E) ⊆ A_P`

as the retained probe atoms with support at or above `min_probe_atom_support_count` after conditioning on `E`.

The candidate pair passes the primary rule iff:
- there are at least `min_common_probes` common structurally valid probes, and
- `Img_P(E) = Img_P(F)` for every such probe.

## Identifier conventions
- Candidate IDs are stable row identifiers of the form `cand_<left_event_id>__<right_event_id>`.
- Accepted proposal IDs are stable identifiers of the form `proposal_<left_event_id>__<right_event_id>`.
- Probe-image signatures are keyed by `(source_event_id, probe_context_id)`.

## Cross-file reference rules
- `shared-event-candidates.json` references the source discovered-context family and the built package.
- `probe-indistinguishability-signatures.json` references the same discovered-context family and raw-run or PICA bundle sources.
- Accepted proposal provenance must reference both:
  - the shared-event candidate artifact
  - the source bundle/raw-run artifacts used to compute the signatures

## Observable vs debug fields
- Required observable inputs:
  - source context retained atoms
  - event retained-atom sets
  - downstream probe retained atoms
  - observable conditioning counts and probe-image atom sets
- Optional secondary/debug fields:
  - per-probe TV distances
  - mean/max TV
  - confidence scores
- Hidden-state IDs are not allowed in acceptance, rejection, or ranking logic.

## Minimal valid example
```json
{
  "inference_mode": "structural_primary",
  "min_common_probes": 1,
  "min_conditioning_count": 3,
  "min_probe_atom_support_count": 1,
  "max_mean_tv": 0.15,
  "exact_tolerance": 1e-6,
  "proposal_constraint_kind": "soft"
}
```

## Validation notes
- In structural-primary mode, accepted candidate rows must have `structural_match = true`.
- `probe_image_mismatch:<probe_context_id>` style rejection reasons are preferred when common probes disagree.
- Secondary TV metadata may be absent only for insufficient-data rows.
