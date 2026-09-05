# `three-axis-evidence-index.v1`

Minimal supportive index for the committed evidence used by the three-axis
context memo.

The index is not a runtime synthesis result. It is a compact registry of
committed theory sources and committed axis evidence assets so later paper-facing
notes do not depend on transient `results/results/...` outputs.

Required top-level fields:

- `index_format_version`
- `index_id`
- `theory_sources`
- `axes`
- `notes`

`theory_sources` entries should record:

- `label`
- `path`
- `role`

`axes` must contain `mechanism`, `lens`, and `packaging`.

Each axis entry should record:

- `campaign_assets`
- `flagship_assets`
- `current_evidence_summary`
- `claim_ceiling`
- `caveat_flags`

The `lens` entry may also include a `subregime_assets` block when both a
same-step bounded-negative subregime and a cross-resolution accepted-obstruction
subregime need to be preserved.
