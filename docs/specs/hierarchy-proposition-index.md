# `hierarchy-proposition-index.v1`

Compact machine-readable index for the hierarchy proposition layer.

Required top-level fields:

- `index_format_version`
- `index_id`
- `theorem_object_label`
- `entries`

`theorem_object_label` must remain `event_package`.

Each entry must contain:

- `proposition_id`
- `label`
- `kind`
- `statement`
- `support_type`
- `primary_refs`
- `supporting_refs`
- `caveat_flags`

Allowed `kind` values:

- `formal_consequence`
- `non_implication`
- `adjudicated_rule`

Allowed `support_type` values:

- `theory`
- `committed_evidence`
- `theory_and_evidence`

`primary_refs` and `supporting_refs` are repo-relative file paths pointing to
papers, runbooks, specs, or committed evidence assets.
