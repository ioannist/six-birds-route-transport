# Lens-Axis Cross-Resolution Reconciliation

## Original TH4 contract

- Fixed mechanism/configuration.
- Fixed packaging family as much as practical.
- Same support object.
- Same-slice primary-context comparisons.
- Quotient-backed feasibility audit without changing `structural_primary` admissibility.

## Cross-resolution witness setup

- Witness family: `EXP-104 / P6_row_all / n=64 / seed 0`.
- Support object: aligned trajectories on one committed run.
- Context family: observation-label primary contexts from the same run/support family.
- Resolution pair: `k=4` and `k=20`.
- Accepted-proposal quotient audit: committed and reproducible.

## Relevant theory passages consulted

- `docs/papers/Tsiokos_2026_A_Six_Birds_Eye_View_of_Quantum_Theory_Operational_Closure_Semantics_for_Measurement_Contextuality_and_Record_Stability.tex:748-764`
  - Context change is framed as strict extension / record-algebra change, with contextuality tied to noncommuting closures rather than mere relabeling.
- `docs/papers/Tsiokos_2026_Six_Birds_for_Incompleteness_Fixed_Packages_Package_Change_and_Conditional_Arithmetic_Lift.tex:205-225`
  - Fixed-package and package-change comparisons are defined on the same underlying `X`.
- `docs/papers/Tsiokos_2026_Six_Birds_for_Incompleteness_Fixed_Packages_Package_Change_and_Conditional_Arithmetic_Lift.tex:759-761`
  - The frozen slice is tied to a fixed evaluation regime with `P6` and support axis `P4`; `P3` remains diagnostic-only.
- `docs/papers/Tsiokos_2026_Strict_Theory_Extension_on_a_Lawful_Continuous_Cantor_Shell.tex:223-225`
  - `Q_l` / `U_l` are lens-dependent coarse-graining and reinstatement maps.
- `docs/papers/Tsiokos_2026_Strict_Theory_Extension_on_a_Lawful_Continuous_Cantor_Shell.tex:323-326`
  - Packaging is expressed as a lens-dependent endomap.
- `docs/papers/Tsiokos_2026_Strict_Theory_Extension_on_a_Lawful_Continuous_Cantor_Shell.tex:729-733`
  - `P4 <- P5` forcing can change the lens and expose new packaged strata.

## Adjudication question

Does a same-run, same-support, fixed-evaluation-regime comparison across `k=4` and `k=20` still count as admissible lens-axis context change, or does it violate the TH4 frozen-slice contract by smuggling in stage-only drift?

## Decision

- Final decision: `accepted_as_lens_axis_strict_extension`

## Rationale

- The witness keeps run identity, mechanism family, support rows, and evaluation regime fixed.
- The varying object is the record algebra induced by the admissible observation-label lens family across two resolutions on the same support.
- The witness does not rely on `P3`-only, stage-summary, route-summary, or closure-summary primary contexts.
- The paper language supports strict extension through changed record algebra under fixed support/evaluation conditions; it does not require “same resolution only” as the invariant.
- Because of that, the cross-resolution witness is treated here as a lens-axis strict-extension case, not as an out-of-contract exploratory appendix artifact.

## Closure rule applied

- Accept the cross-resolution witness for TH4 only if:
  - same support is verified,
  - same run is verified,
  - fixed evaluation regime is verified,
  - the quotient-backed accepted proposal set is obstructed,
  - and the projection family remains admissible as a primary lens context.
- Otherwise reject it as `out_of_contract`.
