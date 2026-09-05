# Axis Claim Ladder

## Purpose
`axis-claim-ladder.v1` defines the ordered shared claim-strength vocabulary used across the hierarchy program. Later tickets must report not only whether a point is interesting, but the strongest claim level it supports under this ladder.

## Versioning
- Version field: `ladder_format_version`
- Initial value: `axis-claim-ladder.v1`

## Data model
Required fields:
- `ladder_format_version`
- `ladder_id`
- `levels`

Optional fields:
- `metadata`

### `levels`
Each level entry must provide:
- `level`
- `order_index`
- `short_label`
- `supported_axes`

Optional:
- `notes`

Required ordered levels:
1. `mechanism_dependence`
2. `nontrivial_multicontext_structure`
3. `same_slice_non_nested_structure`
4. `package_conflict_tension`
5. `bounded_negative_result`
6. `provenance_admissible_strong_obstruction`

Invariants:
- every level appears exactly once
- `order_index` matches the shared order above
- the ladder is monotone and total

## Identifier conventions
- `ladder_id` names a reusable ladder contract, not a particular experiment run.
- `short_label` should be stable enough for later tables and figure legends.

## Cross-file reference rules
- `three-axis-search-config` and `three-axis-search-row` files reference this ladder via `claim_ladder_ref`.
- Later axis-specific search summaries should report their strongest supported `level` values from this file.

## Minimal valid example
```json
{
  "ladder_format_version": "axis-claim-ladder.v1",
  "ladder_id": "three_axis_default_claim_ladder",
  "levels": [
    { "level": "mechanism_dependence", "order_index": 0, "short_label": "mechanism dependence", "supported_axes": ["mechanism", "lens", "packaging"] },
    { "level": "nontrivial_multicontext_structure", "order_index": 1, "short_label": "multicontext structure", "supported_axes": ["mechanism", "lens", "packaging"] },
    { "level": "same_slice_non_nested_structure", "order_index": 2, "short_label": "same-slice non-nested", "supported_axes": ["lens", "packaging"] },
    { "level": "package_conflict_tension", "order_index": 3, "short_label": "package conflict tension", "supported_axes": ["packaging"] },
    { "level": "bounded_negative_result", "order_index": 4, "short_label": "bounded negative", "supported_axes": ["packaging"] },
    { "level": "provenance_admissible_strong_obstruction", "order_index": 5, "short_label": "strong obstruction", "supported_axes": ["packaging"] }
  ],
  "metadata": {
    "program": "three_axis_hierarchy"
  }
}
```

## Validation notes
- Reject ladders that omit any shared level.
- Reject ladders whose `order_index` does not match the shared order.
- Later row validation may use the ladder order plus axis ceilings to reject over-strong default claims.
