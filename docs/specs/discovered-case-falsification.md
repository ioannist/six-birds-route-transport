# Discovered Case Falsification

## Purpose
This spec defines the validated input for a thin falsification/stress-test bundle over one selected provenance-admissible discovered case.

## Version
- Version field name: `falsification_format_version`
- Initial value: `"discovered-case-falsification.v1"`

## Required top-level fields

- `falsification_format_version`
- `falsification_id`
- `selected_case`
- `baseline_evaluation`
- `hidden_record`
- `flattening`
- `robustness`
- `verdict_rule_version`
- optional `metadata`

## `selected_case`

The selected discovered-case refs must include stable repo-local paths for:

- event package
- package provenance
- raw substrate run
- discovered-context-family
- shared-event-candidates
- source substrate config
- selection artifact

## `baseline_evaluation`

This block records the baseline build/evaluation metadata for the selected case:

- `preparation_id`
- `protocol_id`
- `trajectories`
- `seed`
- `event_basis_mode`
- `max_union_size`

## `hidden_record` and `flattening`

Each intervention block records either:

- an applicable intervention artifact to run through the existing T19/T20 machinery, or
- `applicable = false` with an explicit reason

This supports honest `not_applicable` outcomes.

## `robustness`

The robustness block records:

- `noise_grid`
- `noise_model`
- `metric_thresholds`

The T32 runner turns this into a one-target T21 sweep over the selected discovered case.

## Evaluation rule

Every falsification bundle must preserve and report both:

1. baseline hard-only evaluation
2. all-accepted-proposals evaluation

The second mode is the primary mode for discovered-case obstruction testing.
