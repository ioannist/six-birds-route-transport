# Commutator Pair Audit — Snapshot Classification

**Source file:** `vendor/six-birds-pica/crates/dynamics/src/pica/commutator.rs`
**Snapshot commit:** `9da175b` (Initial project snapshot through T32)

## Summary

- **Total unordered primitive pairs:** C(6,2) = **15**
- **Pairs emitted by `all_commutators()`:** **3**
- **Real reducers (genuine nontrivial computation):** **3**
- **Explicit zero / placeholder / label-only pairs:** **0** emitted, **12** documented as omitted

## Classification Table

| # | Pair       | Label  | Classification             | Evidence / Function                                                                                                 |
|---|-----------|--------|----------------------------|----------------------------------------------------------------------------------------------------------------------|
| 1 | [P1, P2]  | S3     | **real reducer**            | `commutator_p1_p2()` — applies `p1_random_perturb` and `p2_gate` in both orders, returns Frobenius norm of difference via `commutator_frob()`. Both primitives write K; result is generically nonzero. |
| 2 | [P1, P4]  | S4     | **real reducer**            | `commutator_p1_p4()` — applies P1, then compares `p4_sectors` before vs after. Returns fraction of states that changed sector. Not a Frobenius commutator but a concrete nontrivial computation that is generically nonzero when P1 moves sector boundaries. |
| 3 | [P2, P4]  | S5     | **real reducer**            | `commutator_p2_p4()` — applies P2 gating, then compares `p4_sectors` before vs after. Returns fraction of states that changed sector. Same structure as S4; generically nonzero when gating reshapes partition boundaries. |
| 4 | [P1, P3]  | —      | **read-only / diagnostic-trivial** | P3 is read-only on K (`P3(K) = K`). Source comment lines 24-28: "Its commutator with any action primitive is trivially zero because P3(K) = K." Content captured by Group B diagnostics instead. |
| 5 | [P2, P3]  | —      | **read-only / diagnostic-trivial** | Same as [P1,P3]. P3 does not transform K. Lines 24-28. |
| 6 | [P3, P4]  | —      | **read-only / diagnostic-trivial** | Both are read-only on K. Lines 24-28. |
| 7 | [P3, P5]  | —      | **read-only / diagnostic-trivial** | P3 read-only, P5 idempotent/read-only. Lines 24-28 and 30-31. |
| 8 | [P3, P6]  | —      | **read-only / diagnostic-trivial** | P3 read-only, P6 read-only. Lines 24-28 and 33-36. |
| 9 | [P1, P5]  | —      | **read-only / diagnostic-trivial** | P5 is idempotent and read-only (`e(e(x)) = e(x)`). Lines 30-31. |
| 10 | [P2, P5] | —      | **read-only / diagnostic-trivial** | Same reasoning as [P1,P5]. Lines 30-31. |
| 11 | [P4, P5] | —      | **explicit zero placeholder** | Both are read-only diagnostics; commutator is trivially zero. Line 38: "Both are read-only diagnostics; commutator is trivially zero." |
| 12 | [P5, P6] | —      | **read-only / diagnostic-trivial** | P5 idempotent/read-only, P6 read-only. Lines 30-31. |
| 13 | [P1, P6] | —      | **read-only / diagnostic-trivial** | P6 is read-only. Lines 33-36: "Commuting with it just measures 'does measuring before vs after matter?' which is always zero." |
| 14 | [P2, P6] | —      | **read-only / diagnostic-trivial** | Same as [P1,P6]. Lines 33-36. |
| 15 | [P4, P6] | —      | **read-only / diagnostic-trivial** | Both read-only. Lines 33-36. |

## Notes

- **No config-level row-pair surface names** exist in `PicaConfig`. The commutator module is standalone and invoked unconditionally by the runner at observation time (`main.rs:9434`). The labels S3/S4/S5 appear only in the doc comments of `commutator.rs`, not as configurable surfaces.

- **The PICA `mod.rs` module contradicts the commutator module's read-only classification.** The `mod.rs` header (lines 12-25) explicitly states: *"The original classification treated P4/P5/P6 as 'read-only diagnostics.' This was incorrect — P4's partition is consumed by 6 downstream A-cells and directly shapes the dynamics."* Under the PICA framework, P4/P5/P6 all write to state. However, `commutator.rs` was written under the **older** read-only assumption and was never updated. The 3 implemented commutators remain valid (they do compute real values), but the 12 omitted pairs may not all be trivially zero under the PICA model. This is a known design debt in the snapshot.

- **S4 and S5 use a different metric** than S3. S3 uses `commutator_frob()` (Frobenius norm of kernel difference). S4 and S5 measure fraction-of-states-changed in the partition, which is a discrete metric, not a Frobenius norm. All three are nontrivial computations but they are not directly comparable.

## Conclusion

**In this snapshot, exactly 3 commutator pairs are genuinely real** — `[P1,P2]`, `[P1,P4]`, and `[P2,P4]` — each backed by a concrete function that computes a generically nonzero value from actual primitive application. The remaining 12 pairs are not emitted, not computed, and not wired; they are documented as trivially zero under the read-only assumption that predates the PICA reclassification.
