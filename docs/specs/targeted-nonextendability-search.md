# Targeted Nonextendability Search

## Purpose
This spec defines the validated input for a small targeted search over crafted substrate configs aimed at finding one provenance-admissible discovered package with strong endogenous nonextendability after coarse-event discovery.

## Version
- Version field name: `search_format_version`
- Initial value: `"targeted-nonextendability-search.v1"`

## Required top-level fields

- `search_format_version`
  Must equal `targeted-nonextendability-search.v1`.
- `search_id`
  Stable identifier for the committed targeted family.
- `points`
  Non-empty list of crafted search points.
- `extraction_thresholds`
  Discovery extraction thresholds.
- `coarse_event_generation_thresholds`
  T30 event-basis mode and coarse-event generation thresholds.
- `shared_event_inference_thresholds`
  Shared-event matching thresholds and proposal policy.
- `provenance_required`
  Boolean flag requiring provenance audit classification for candidate claims.
- `candidate_classification_thresholds`
  Deterministic thresholds for candidate labeling.
- `stop_rule`
  Explicit stop rule metadata.
- `metadata`
  Optional flat metadata.

## `points`

Each point records:

- `point_id`
- `config_artifact`
- `preparation_id`
- `protocol_id`
- `trajectories`
- `seed`
- optional `notes`

## Evaluation modes

Every search point is evaluated in two explicit modes:

1. baseline `hard_only`
   - exact feasibility and structural deficit using hard constraints only
2. `all_accepted_proposals`
   - exact feasibility and structural/statistical testing with accepted inferred proposals enforced

Strong endogenous nonextendability claims are assessed only in the second mode.

## Stop rule intent

The committed targeted family is exhaustive for this ticket.

- If one or more `strongly_nonextendable_candidate` rows are found, the runner selects one deterministic best candidate.
- Otherwise it emits a machine-readable negative result and stops.

No adaptive family expansion belongs in this format.
