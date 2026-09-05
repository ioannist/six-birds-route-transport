# Three-Axis Hierarchy Contract

## Purpose
This runbook defines the shared technical vocabulary for the hierarchy program before any axis-specific search runners are implemented.

## Axis definitions
- `mechanism`
  - varies: mechanism family, enable matrix, control-space point
  - holds fixed as much as possible: lens family, packaging policy, frozen-slice support
  - default claim ceiling: `nontrivial_multicontext_structure`
- `lens`
  - varies: lens, projection, record-algebra choice
  - holds fixed: mechanism/configuration, packaging policy as much as possible, frozen-slice support
  - default claim ceiling: `same_slice_non_nested_structure`
- `packaging`
  - varies: packaging operator, package family, package-selector branch
  - holds fixed: mechanism/configuration, lens family as much as possible, frozen-slice support
  - default claim ceiling: `provenance_admissible_strong_obstruction`

## Shared claim ladder
Ordered levels:
1. `mechanism_dependence`
2. `nontrivial_multicontext_structure`
3. `same_slice_non_nested_structure`
4. `package_conflict_tension`
5. `bounded_negative_result`
6. `provenance_admissible_strong_obstruction`

Default ceiling by axis:
- `mechanism` -> `nontrivial_multicontext_structure`
- `lens` -> `same_slice_non_nested_structure`
- `packaging` -> `provenance_admissible_strong_obstruction`

Later tickets may report weaker levels on stronger axes, but they must not silently exceed the default ceiling.

## Shared candidate vocabulary
All later axis searches reuse:
- `strongly_nonextendable_candidate`
- `weakly_frustrated_candidate`
- `extendable_candidate`
- `trivial_or_nonrecording`
- `inconclusive`

Threshold details may remain axis-specific later. The class names are shared.

## Shared metric surface
Every later axis row should report:
- provenance classification
- accepted context and event/proposal counts
- dual exact evaluation blocks:
  - `baseline_hard_only`
  - `all_accepted_proposals`
- audit summaries:
  - `sec`
  - `rm`
  - `ccd`
- support diagnostics
- context-pair structure diagnostics
- axis-admissibility diagnostics

Status-bearing metrics must use explicit statuses:
- `solved`
- `unsolved`
- `insufficient_data`
- `not_applicable`

## Row/report expectations
Later search rows should always expose:
- `axis`
- `point_id`
- source asset refs
- fixed/varying field summaries
- candidate class
- claim level support
- provenance class
- best-evidence eligibility
- notes/flags

Rows may embed the shared metric surface or reference it by path. If both exist, the embedded payload would be ambiguous and is disallowed by contract.

## Outcome artifact vocabulary
Later search tickets may emit:
- `best-candidate`
- `negative-result`
- `design-inadequate-result`

Relationship to adequacy/claim ladder:
- `best-candidate` requires a row that reaches the strongest allowed claim for its axis.
- `negative-result` requires the axis-specific adequacy floor to be met without a strong candidate.
- `design-inadequate-result` is required when the adequacy floor is not met.

## Consumption rule for later tickets
- reuse the exact field names and enum values from the contract models
- do not rename shared metric fields per axis
- extend by adding axis-specific fields, not by mutating shared meanings
- keep cross-file references repo-relative and versioned
