# Shared Event Candidates

## Purpose
This spec defines the validated intermediate output of shared-event inference from discovered contexts and observable source data. It records scored candidate pairs, acceptance status, probe-signature diagnostics, and optional mapping into a built event package.

## Version
- Version field name: `candidates_format_version`
- Initial value: `"shared-event-candidates.v1"`

## Data model
A shared-event-candidates file ties one discovered-context-family artifact to either source `substrate-run` artifacts or a PICA export bundle. Candidate rows are inferred from accepted contexts only. Matching is observable-driven: candidate events come from the generated event family of accepted contexts, and scores are derived from event-conditioned probe signatures over other accepted contexts with the same preparation/protocol.

## Field table
| Field | Required | Type | Constraints |
| --- | --- | --- | --- |
| `candidates_format_version` | yes | string | Must equal `"shared-event-candidates.v1"`. |
| `inference_id` | yes | string | Stable identifier for one inference result. |
| `inference_mode` | yes | string | `structural_primary` or `legacy_statistical_primary`. |
| `source_discovered_context_family_artifact` | yes | string | Normalized repo-relative path to the input discovered-context-family file. |
| `source_run_artifacts` | conditional | array<string> | Non-empty list of normalized repo-relative raw substrate-run paths for `source_mode = "substrate_runs"`. |
| `source_mode` | yes | string | Either `substrate_runs` or `pica_export_bundle`. |
| `source_bundle_artifact` | conditional | string | Repo-relative PICA export bundle path for `source_mode = "pica_export_bundle"`. |
| `thresholds` | yes | object | Explicit inference thresholds and proposal policy. |
| `candidate_rows` | yes | array<object> | Finite list of all scored candidate singleton-event pairs. |
| `diagnostics_summary` | yes | object | Aggregate counts and accepted proposal IDs. |
| `built_event_package_artifact` | no | string | Optional repo-relative path to a built event-package file derived from accepted candidates. |
| `metadata` | no | object | Optional technical metadata map with scalar values or flat string arrays. |

### `thresholds` object
| Field | Required | Type | Constraints |
| --- | --- | --- | --- |
| `min_common_probes` | yes | integer | Positive minimum number of common admissible probe contexts. |
| `min_conditioning_count` | yes | integer | Positive minimum conditioning sample count per event/probe signature. |
| `min_probe_atom_support_count` | yes | integer | Positive minimum retained probe-atom count needed for inclusion in the probe-image event. |
| `max_mean_tv` | yes | number | Maximum accepted mean TV score in `[0, 1]`. |
| `exact_tolerance` | yes | number | Exact-style per-probe TV tolerance in `[0, 1]`. |
| `proposal_constraint_kind` | yes | string | Proposal kind to emit in the built package, `"soft"` by default. |

### `candidate_rows` entries
| Field | Required | Type | Constraints |
| --- | --- | --- | --- |
| `candidate_id` | yes | string | Unique stable candidate row ID. |
| `left_context_id` | yes | string | Accepted context ID for the left candidate event. |
| `right_context_id` | yes | string | Accepted context ID for the right candidate event. |
| `left_event_id` | yes | string | Event ID for the left candidate event. |
| `right_event_id` | yes | string | Event ID for the right candidate event. |
| `left_outcome_id` | yes | string | Stable left event outcome key derived from sorted retained atom IDs. |
| `right_outcome_id` | yes | string | Stable right event outcome key derived from sorted retained atom IDs. |
| `left_event_kind` | yes | string | One of `empty`, `singleton`, `proper_coarse`, or `full`. |
| `right_event_kind` | yes | string | One of `empty`, `singleton`, `proper_coarse`, or `full`. |
| `left_event_atom_ids` | yes | array<string> | Sorted retained source atom IDs forming the left event; empty only for `left_event_kind = "empty"`. |
| `right_event_atom_ids` | yes | array<string> | Sorted retained source atom IDs forming the right event; empty only for `right_event_kind = "empty"`. |
| `left_event_size` | yes | integer | Must equal `len(left_event_atom_ids)`. |
| `right_event_size` | yes | integer | Must equal `len(right_event_atom_ids)`. |
| `left_is_proper_coarse` | yes | boolean | `true` iff the left event is a proper non-singleton coarse event. |
| `right_is_proper_coarse` | yes | boolean | `true` iff the right event is a proper non-singleton coarse event. |
| `left_support_count` | yes | integer | Observable same-slice support size for the left source event. |
| `right_support_count` | yes | integer | Observable same-slice support size for the right source event. |
| `shared_support_count` | yes | integer | Size of the shared observable support used to compare the two source events. |
| `support_relation_kind` | yes | string | One of `identical_support`, `same_support_relabeling`, `cross_support_match`, `crosscutting_match`, or `disjoint_support_match`. |
| `common_probe_ids` | yes | array<string> | Probe context IDs used for scoring. |
| `common_probe_count` | yes | integer | Must equal `len(common_probe_ids)`. |
| `probe_comparisons` | yes | array<object> | Per-probe support counts, normalized distributions, and TV distances. |
| `structural_match` | yes | boolean | Primary structural pass/fail result over the common valid probes. |
| `structural_mismatch_count` | yes | integer | Number of common probes with differing probe-image events. |
| `structural_mismatch_reasons` | yes | array<string> | Explicit mismatch reasons such as `probe_image_mismatch:<probe_context_id>`. |
| `mean_tv` | no | number | Mean TV across common probes for non-insufficient rows. Secondary metadata only. |
| `max_tv` | no | number | Maximum per-probe TV across common probes for non-insufficient rows. Secondary metadata only. |
| `approx_score` | no | number | Mean TV across common probes for non-insufficient rows. |
| `confidence` | no | number | `1 - approx_score`, clipped into `[0, 1]`, for non-insufficient rows. |
| `exact_consistent` | no | boolean | `true` iff all per-probe TVs are within `exact_tolerance`. |
| `insufficient_data` | yes | boolean | Marks rows with too few admissible common probes. |
| `accepted` | yes | boolean | Whether the row passed the thresholded mutual-best policy. |
| `rejection_reasons` | yes | array<string> | Explicit rejection reasons when `accepted = false`. |
| `proposed_proposal_id` | no | string | Proposal ID emitted into the built package for accepted rows. |

### `probe_comparisons` entries
| Field | Required | Type | Constraints |
| --- | --- | --- | --- |
| `probe_context_id` | yes | string | Accepted probe context ID used for the comparison. |
| `left_conditioning_count` | yes | integer | Non-negative conditioning support count for the left event. |
| `right_conditioning_count` | yes | integer | Non-negative conditioning support count for the right event. |
| `left_support_counts` | yes | object | Counts by retained probe atom ID for the left-conditioned signature. |
| `right_support_counts` | yes | object | Counts by retained probe atom ID for the right-conditioned signature. |
| `left_probe_image_atom_ids` | yes | array<string> | Retained probe atom IDs in the left probe-image event. |
| `right_probe_image_atom_ids` | yes | array<string> | Retained probe atom IDs in the right probe-image event. |
| `left_probe_image_event_kind` | yes | string | One of `empty`, `singleton`, `proper_coarse`, or `full`. |
| `right_probe_image_event_kind` | yes | string | One of `empty`, `singleton`, `proper_coarse`, or `full`. |
| `structural_valid` | yes | boolean | Marks that both source/probe conditionings met the structural support threshold. |
| `structural_match` | yes | boolean | `true` iff the two probe-image events are equal. |
| `structural_mismatch_reasons` | yes | array<string> | Explicit mismatch reasons when `structural_match = false`. |
| `left_distribution` | yes | object | Normalized finite distribution over retained probe atoms for the left event. |
| `right_distribution` | yes | object | Normalized finite distribution over retained probe atoms for the right event. |
| `tv_distance` | yes | number | Total variation distance between the two normalized probe distributions. |

### `diagnostics_summary` object
| Field | Required | Type | Constraints |
| --- | --- | --- | --- |
| `total_candidate_pair_count` | yes | integer | Must equal `len(candidate_rows)`. |
| `structurally_valid_candidate_pair_count` | yes | integer | Count of rows with `structural_match = true`. |
| `accepted_candidate_pair_count` | yes | integer | Accepted row count. |
| `insufficient_data_candidate_pair_count` | yes | integer | Insufficient-data row count. |
| `rejected_candidate_pair_count` | yes | integer | Rejected non-insufficient row count. |
| `accepted_proposal_ids` | yes | array<string> | Proposal IDs for accepted rows in output order. |

## Invariants
- Structural-primary acceptance must be driven by discovered contexts, generated event families, and probe-image equality across admissible downstream probes.
- Hidden-state IDs must not appear in candidate matching, thresholding, or accepted proposal logic.
- TV/confidence metadata are secondary; they may rank or summarize candidates but must not replace the primary structural gate in `structural_primary` mode.
- Candidate rows may reference any generated event kind, but degenerate kinds such as `empty` and `full` may be excluded from matching by policy.
- Proper coarse events must carry explicit retained atom IDs and event sizes.
- Support-relation diagnostics must be observable-only and derived from aligned same-slice support, never from hidden-state IDs.
- `candidate_id` values must be unique.
- `common_probe_count` must equal `len(common_probe_ids)`.
- `probe_comparisons[*].probe_context_id` must match `common_probe_ids` in order.
- `accepted_proposal_ids` must match accepted candidate rows in output order.
- `source_discovered_context_family_artifact`, `source_run_artifacts`, `source_bundle_artifact`, and `built_event_package_artifact` must be normalized repo-relative paths when present.

## Validation notes
- Reject malformed or hidden-state-based provenance fields.
- Reject duplicate candidate IDs or proposal IDs.
- Reject invalid probability maps or TV distances outside `[0, 1]`.
- Reject inconsistent diagnostics-summary counts.
- Reject accepted rows without `proposed_proposal_id`.
