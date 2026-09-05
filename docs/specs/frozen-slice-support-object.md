# `frozen-slice-support-object.v1`

Machine-readable contract for the fixed support object used by strongest
same-system comparison claims.

Required fields:

- `object_format_version`
- `support_object_id`
- `support_index_kind`
- `support_index_refs`
- `mechanism_family_id`
- `preparation_id`
- `protocol_id`
- `evaluation_regime_id`

Optional but expected source refs:

- `source_config_ref`
- `source_bundle_ref`

Support-scope fields:

- `fixed_protocol_step_ids`
- `fixed_step_indices`
- `fixed_resolution_ids`

Interpretation:

- the object identifies one ledger slice
- later contexts may be generated on this support
- the object is a comparison base, not the event package itself

`support_index_kind` may be:

- `row`
- `trajectory`
- `mixed`

`support_index_refs` should contain stable support identifiers, not derived event
IDs.
