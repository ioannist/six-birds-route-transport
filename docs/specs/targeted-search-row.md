# Targeted Search Row

## Purpose
This spec defines the machine-readable row/output shape for targeted endogenous nonextendability search results.

## Version
- Row version field name: `row_format_version`
- Table version field name: `table_format_version`
- Initial values:
  - `targeted-search-row.v1`
  - `targeted-search-results.v1`

## Row content

Each row records at minimum:

- point/config identifiers
- raw run, discovered-context-family, and built package paths
- provenance audit classification
- accepted context / event / proposal counts
- accepted coarse-proposal count
- baseline hard-only evaluation
- all-accepted-proposals evaluation
- SEC / RM / CCD summaries or explicit statuses
- deterministic candidate classification
- underlying run IDs and artifact paths
- notes / flags

## Evaluation blocks

Both `baseline_hard_only` and `all_accepted_proposals` carry:

- exact structural status
- exact feasibility flag
- exact respecting tuple count
- `gpd_str` status / value / reason
- `gpd_stat` status / value / reason

Statuses must remain explicit; unsupported or unsolved quantities must not be coerced to numeric zero.

## Candidate classifications

Allowed values:

- `strongly_nonextendable_candidate`
- `weakly_frustrated_candidate`
- `extendable_candidate`
- `trivial_or_nonrecording`
- `inconclusive`

## Table content

The top-level results table records:

- `table_format_version`
- `search_id`
- `row_count`
- `rows`
- optional metadata

It is the validated JSON companion to the emitted CSV.
