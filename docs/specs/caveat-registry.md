# `caveat-registry.v1`

`caveat-registry.v1` records the drafting-facing caveats that bound the current
claim strength of the evidence pack.

Top-level fields:

- `registry_format_version`
- `registry_id`
- `entries`

Each entry must contain:

- `caveat_id`
- `scope`
- `label`
- `statement`
- `primary_artifact_refs`
- optional `supporting_artifact_refs`
- optional `caveat_flags`
- optional `notes`

Allowed `scope` values:

- `theorem`
- `mechanism`
- `lens`
- `packaging`
- `controls`
- `general`

Interpretation:

- caveats are not negative findings by themselves
- they are explicit claim-boundary markers for later paper drafting
- they must preserve distinctions such as campaign outcome versus flagship
  witness and strong accepted result versus narrow comparison surface
