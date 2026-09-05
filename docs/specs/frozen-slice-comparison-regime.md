# `frozen-slice-comparison-regime.v1`

Machine-readable contract for context comparison on one frozen-slice/shared-support object.

Required fields:

- `regime_format_version`
- `regime_id`
- `support_object_ref`
- `theorem_object`
- `held_fixed_fields`
- `varying_fields`
- `supported_axes`
- `allowed_variation_modes`
- `same_support_admissibility_fields`

Boolean requirements:

- `same_support_required = true`
- `same_evaluation_regime_required = true`
- `no_moving_ledger = true`

Interpretation:

- `support_object_ref` points to the fixed comparison base
- `held_fixed_fields` records what must remain fixed
- `varying_fields` records the admissible context-forming variation
- `supported_axes` should describe the axes that naturally live on the fixed support object

`theorem_object` must remain `event_package`.

`supported_axes` currently supports:

- `lens`
- `packaging`

`allowed_variation_modes` currently supports:

- `same_step`
- `cross_resolution_strict_extension`

This contract is for same-system comparison. Mechanism variation is normally
outside this regime because it usually changes the outer support object.
