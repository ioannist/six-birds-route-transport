# Discovered Event Family

## Purpose
This spec defines the validated intermediate event-family output used by upgraded package building. It records generated events per accepted discovered context, including full Boolean event algebras when requested and explicitly incomplete truncations otherwise.

## Version
- Version field name: `event_family_format_version`
- Initial value: `"discovered-event-family.v1"`

## Data model
A discovered-event-family file ties one discovered-context-family artifact to either source `substrate-run` artifacts or a PICA export bundle. It records the event-basis mode, event-algebra mode, generated events per accepted context, completeness diagnostics, and optional linkage to a final built event package.

## Field table
| Field | Required | Type | Constraints |
| --- | --- | --- | --- |
| `event_family_format_version` | yes | string | Must equal `"discovered-event-family.v1"`. |
| `event_family_id` | yes | string | Stable identifier for one event-basis build. |
| `source_discovered_context_family_artifact` | yes | string | Normalized repo-relative path to the source discovered-context-family file. |
| `source_run_artifacts` | conditional | array<string> | Non-empty list of normalized repo-relative raw substrate-run paths for `source_mode = "substrate_runs"`. |
| `source_mode` | yes | string | Either `substrate_runs` or `pica_export_bundle`. |
| `source_bundle_artifact` | conditional | string | Repo-relative PICA export bundle path for `source_mode = "pica_export_bundle"`. |
| `thresholds` | yes | object | Explicit event-basis mode and coarse-event generation thresholds. |
| `contexts` | yes | array<object> | Generated event entries for each accepted discovered context. |
| `diagnostics_summary` | yes | object | Aggregate counts of generated, accepted, and rejected event-basis entries. |
| `built_event_package_artifact` | no | string | Optional repo-relative path to a built event package derived from this event basis. |
| `metadata` | no | object | Optional technical metadata map with scalar values or flat string arrays. |

### `thresholds` object
| Field | Required | Type | Constraints |
| --- | --- | --- | --- |
| `event_basis_mode` | yes | string | One of `"singleton_only"` or `"singleton_plus_small_unions"`. |
| `event_algebra_mode` | no | string | One of `full_powerset`, `conservative_truncation`, or `auto`. |
| `max_full_powerset_atom_count` | no | integer | Positive threshold used by `auto`. |
| `max_union_size` | yes | integer | Maximum proper coarse-event union size. Must be at least `2`. |
| `min_event_support_count` | yes | integer | Positive minimum conditioning support count for accepted coarse events. |
| `min_event_support_fraction` | yes | number | Minimum conditioning support fraction in `[0, 1]` for accepted coarse events. |

### `contexts` entries
| Field | Required | Type | Constraints |
| --- | --- | --- | --- |
| `context_id` | yes | string | Accepted discovered context ID. |
| `events` | yes | array<object> | Generated singleton and coarse event entries for this context. |
| `atom_count` | no | integer | Retained atom count for the context. |
| `expected_full_event_count` | no | integer | Exact powerset size `2^|A_c|`. |
| `generated_event_count` | no | integer | Number of generated events for the context. |
| `match_eligible_event_count` | no | integer | Count of accepted events eligible for cross-context matching. |
| `event_algebra_complete` | no | boolean | `true` iff generation equals the full powerset. |
| `generation_mode_used` | no | string | Concrete mode used for this context. |
| `coverage_fraction` | no | number | `generated_event_count / expected_full_event_count`. |
| `truncation_reason` | no | string | Explicit truncation reason when incomplete. |
| `rejection_reason_counts` | no | object | Aggregate rejection counts keyed by explicit reason labels such as `insufficient_support`, `too_large`, or `trivial_full_event`. |

### `events` entries
| Field | Required | Type | Constraints |
| --- | --- | --- | --- |
| `event_id` | yes | string | Stable deterministic event ID derived from context ID and retained atom IDs. |
| `context_id` | yes | string | Must match the containing context entry. |
| `event_kind` | yes | string | One of `empty`, `singleton`, `proper_coarse`, or `full`. |
| `retained_atom_ids` | yes | array<string> | Sorted retained source atom IDs forming the event. Empty only for `event_kind = "empty"`. |
| `event_size` | yes | integer | Must equal `len(retained_atom_ids)`. |
| `conditioning_support_count` | yes | integer | Non-negative support count for the generated event. |
| `conditioning_support_fraction` | yes | number | Conditioning support fraction in `[0, 1]`. |
| `accepted` | yes | boolean | Whether the event basis entry passed support thresholds. Singleton entries are accepted by construction. |
| `match_eligible` | yes | boolean | Whether the event is eligible for shared-event matching. |
| `rejection_reasons` | yes | array<string> | Explicit rejection reasons for rejected coarse-event entries. |

### `diagnostics_summary` object
| Field | Required | Type | Constraints |
| --- | --- | --- | --- |
| `total_event_count` | yes | integer | Must equal the total number of event entries across all contexts. |
| `generated_empty_event_count` | no | integer | Accepted generated empty-event count. |
| `generated_singleton_event_count` | no | integer | Accepted generated singleton-event count. |
| `generated_proper_coarse_event_count` | no | integer | Accepted generated proper-coarse-event count. |
| `generated_full_event_count` | no | integer | Accepted generated full-event count. |
| `match_eligible_event_count` | no | integer | Accepted match-eligible event count. |
| `accepted_singleton_event_count` | yes | integer | Accepted singleton-event count. |
| `accepted_coarse_event_count` | yes | integer | Accepted proper coarse-event count. |
| `rejected_coarse_event_count` | yes | integer | Rejected proper coarse-event count. |
| `accepted_proper_coarse_event_ids` | yes | array<string> | Accepted proper coarse-event IDs in output order. |

## Invariants
- Event generation must use accepted discovered contexts and observable raw-run support only.
- Hidden-state IDs must not appear in event generation, thresholding, or acceptance logic.
- `full_powerset` mode must emit the exact full Boolean algebra for each context.
- Truncation modes must mark the context incomplete and report exact coverage.
- Empty and full events may be generated while still being excluded from proposal matching by `match_eligible = false`.
- Event generation and event matching remain distinct layers: the full Boolean algebra may be generated while only a proper subset is marked `match_eligible`.
- `retained_atom_ids` identify the union basis explicitly; coarse events are not free-floating labels.
- `built_event_package_artifact`, `source_discovered_context_family_artifact`, `source_run_artifacts`, and `source_bundle_artifact` must be normalized repo-relative paths when present.

## Validation notes
- Reject duplicate `context_id` or `event_id` values within the file.
- Reject `proper_coarse` events with `event_size <= 1`.
- Reject `full_powerset` contexts whose `generated_event_count` differs from `expected_full_event_count`.
- Reject inconsistent aggregate counts in `diagnostics_summary`.
