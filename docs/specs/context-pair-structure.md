# Context Pair Structure

## Purpose
`context-pair-structure.v1` records observable-only structural relations between accepted PICA-native contexts, including whether one context refines another or whether the pair is genuinely incomparable on the shared row index set. The same format also carries frozen-slice admissibility and package-conflict diagnostics used by later packaging-conflict searches.

## Versioning
- Version field: `structure_format_version`
- Initial value: `context-pair-structure.v1`

## Data model
Required top-level fields:
- `structure_format_version: string`
- `search_id: string`
- `row_count: int`
- `rows: list[context-pair-structure-row]`

Required row fields:
- `point_id`
- `preparation_id`
- `protocol_id`
- `left`
- `right`
- `relation_type`
- `shared_row_count`
- `left_assignment_count`
- `right_assignment_count`
- `left_block_count`
- `right_block_count`
- `same_step`
- `same_frozen_slice`
- `primary_identity_admissible`
- `packaging_conflict_supported`
- `commutator_support_pairs`
- `primary_packaging_conflict_admissible`
- `packaging_conflict_admissibility_class | null`
- `admissibility_reason | null`

Allowed `relation_type` values:
- `equal`
- `left_refines_right`
- `right_refines_left`
- `incomparable`
- `disjoint_or_unaligned`

## Identifier conventions
- `search_id` identifies the parent closure-diverse campaign
- `point_id` identifies the campaign point
- `left.context_id` and `right.context_id` identify accepted contexts from the discovered context family
- `projection_id` identifies the observable projection family when present

## Cross-file reference rules
- `left.context_id` and `right.context_id` must exist in the discovered context family for the same point
- `search_id` must match the parent `pica-closure-diverse-search` result bundle

## Observable vs debug fields
Required observable fields:
- context source metadata
- relation type
- shared-row and block counts

Optional/debug fields:
- `notes`
- `flags`
- commutator support identifiers

## Minimal valid example
```json
{
  "structure_format_version": "context-pair-structure.v1",
  "search_id": "demo_closure_diverse",
  "row_count": 1,
  "rows": [
    {
      "point_id": "demo_point",
      "preparation_id": "prep_pica_default",
      "protocol_id": "protocol_pica_multiscale_scan",
      "left": {
        "context_id": "ctx_demo_left",
        "level_id": "level_l0",
        "resolution_id": "resolution_k_4",
        "closure_id": "closure_demo_k_4",
        "lens_id": "lens_demo_k_4",
        "protocol_step_id": "protocol_pica_multiscale_scan_step_1",
        "step_index": 1,
        "projection_id": "obs_primary",
        "projection_field": "observation_label"
      },
      "right": {
        "context_id": "ctx_demo_right",
        "level_id": "level_l0",
        "resolution_id": "resolution_k_4",
        "closure_id": "closure_demo_pkg_k_4",
        "lens_id": "lens_p5_k_4",
        "protocol_step_id": "protocol_pica_multiscale_scan_step_1",
        "step_index": 1,
        "projection_id": "obs_primary",
        "projection_field": "observation_label"
      },
      "relation_type": "incomparable",
      "shared_row_count": 4,
      "left_assignment_count": 4,
      "right_assignment_count": 4,
      "left_block_count": 3,
      "right_block_count": 3,
      "same_step": true,
      "same_frozen_slice": true,
      "primary_identity_admissible": true,
      "packaging_conflict_supported": true,
      "commutator_support_pairs": ["[P1,P5]", "[P4,P5]"],
      "primary_packaging_conflict_admissible": true,
      "packaging_conflict_admissibility_class": "primary_packaging_conflict",
      "admissibility_reason": "same_slice_closure_or_lens_difference_with_relevant_p5_commutator_support",
      "flags": ["non_nested"]
    }
  ]
}
```

## Validation notes
Machine-checkable invariants:
- version string matches `context-pair-structure.v1`
- `row_count == len(rows)`
- all count fields are non-negative
- all IDs and projection fields are non-empty
- `same_step` is explicit for every row
- `same_frozen_slice` is explicit for every row
- `primary_identity_admissible` is explicit for every row
- package-conflict support fields are explicit for every row
