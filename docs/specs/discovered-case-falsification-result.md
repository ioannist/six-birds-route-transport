# Discovered Case Falsification Result

## Purpose
This spec defines the machine-readable result/output format for a discovered-case falsification bundle.

## Version
- Result version field name: `result_format_version`
- Initial value: `"discovered-case-falsification-result.v1"`

## Required result content

Each result records at minimum:

- falsification ID
- selected case ID
- selected source refs
- provenance audit classification
- baseline hard-only evaluation
- baseline all-accepted-proposals evaluation
- available SEC / CCD / RM statuses
- hidden-record sub-run summary
- flattening sub-run summary
- robustness sub-run summary
- final verdict
- key artifact refs
- notes / flags

## Supported verdicts

Allowed final verdict values are:

- `survived`
- `weakened`
- `disappeared`
- `no_baseline_obstruction`
- `inconclusive`

## Intervention summaries

Hidden-record and flattening sub-run summaries must preserve:

- `applicability_status`
- `outcome`
- `reason`
- run/artifact refs when completed

This allows a committed selected case to say explicitly that a particular falsification path was `not_applicable`.

## Robustness summary

The robustness sub-run summary records:

- applicability status
- run/artifact refs
- first-crossing data
- notes

Statuses from unavailable metrics must remain explicit rather than coerced to numeric zero.
