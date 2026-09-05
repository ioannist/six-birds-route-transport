# Audits Catalog

Machine-readable reference for every audit metric in the Six Birds codebase.
Organized by source location, then by audit tier.

## 1. Existing Metrics Inventory

### 1.1 Snapshot fields (`crates/dynamics/src/observe.rs` — `Snapshot` struct)

Computed at `obs_interval` cadence during `run_dynamics()`.

| Field | Layer | Category | Cost | Primitives | Notes |
|-------|-------|----------|------|------------|-------|
| `step` | dynamics | metadata | cheap | — | simulation clock |
| `position` | trajectory | metadata | cheap | — | current micro state |
| `budget` | budget | budget/drive | cheap | P6 | KL cost budget remaining |
| `phase` | dynamics | holonomy | cheap | P3 | protocol phase (0..cycle_len) |
| `block_count` | effective kernel | structure | moderate | P4 | weakly connected components |
| `eff_gap` | effective kernel | structure | moderate | spectral | spectral gap of K_eff |
| `gated_edges` | effective kernel | structure | cheap | P2 | count of deleted edges |
| `macro_n` | macro | structure | cheap | P4 | cluster count in active partition |
| `tau` | macro | holonomy | cheap | P3 | adaptive power used for K^τ |
| `frob_from_rank1` | macro kernel | structure | expensive | P4,P3 | ‖M − 1·π^T‖_F |
| `macro_gap` | macro kernel | structure | expensive | spectral | spectral gap of macro kernel |
| `sigma` | macro kernel | directionality | expensive | P6 | path-reversal asymmetry (σ_π) |
| `level1_frob` | macro (L1) | structure | expensive | P4 | frob at Level 1 cross-layer audit |
| `p1_accepted` | dynamics | budget/drive | cheap | P1 | cumulative P1 accepts |
| `p1_rejected` | dynamics | budget/drive | cheap | P1 | cumulative P1 rejects |
| `p2_accepted` | dynamics | budget/drive | cheap | P2 | cumulative P2 accepts |
| `p2_rejected` | dynamics | budget/drive | cheap | P2 | cumulative P2 rejects |
| `traj_steps` | dynamics | metadata | cheap | — | cumulative trajectory steps |
| `p2_repairs` | dynamics | budget/drive | cheap | P2,P6 | SBRC repair-classified flips |
| `p2_violations` | dynamics | budget/drive | cheap | P2,P6 | SBRC violation-classified flips |

### 1.2 DynamicsTrace metadata (`crates/dynamics/src/mixture.rs`)

Recorded once at end of run.

| Field | Layer | Category | Cost | Primitives |
|-------|-------|----------|------|------------|
| `final_kernel` | effective kernel | structure | — | — |
| `final_pat_state_lens_source` | PICA state | metadata | cheap | P4 |
| `final_pat_state_lens_qualities` | PICA state | metadata | cheap | P4 |
| `final_pat_state_packaging_source` | PICA state | metadata | cheap | P5 |
| `final_pat_state_packaging_qualities` | PICA state | metadata | cheap | P5 |
| `final_pat_state_active_tau` | PICA state | holonomy | cheap | P3 |

### 1.3 Diagnostic cells (`crates/dynamics/src/pica/diag_cells.rs`)

Post-hoc measurements on evolved kernels. Called by runner at end of run.

| Function | PICA cell | Output keys | Layer | Category | Cost | Primitives |
|----------|----------|-------------|-------|----------|------|------------|
| `b1_multiscale_rm` | A18 | rm_tau, rm_2tau, rm_4tau | macro | holonomy/RM | moderate | P3,P4 |
| `b2_sector_rm` | A19 | rm_c0, rm_c1, … | macro | holonomy/RM | moderate | P3,P4 |
| `b3_packaging_rm` | A20 | rm_packaging | macro | holonomy/RM | moderate | P3,P5 |
| `b4_rm_partition` | A14 | rm_partition_k | partition | holonomy/RM | expensive | P3,P4 |
| `b5_hierarchical` | diag | total_subclusters | partition | structure | moderate | P4 |
| `b6_package_partition` | A16 | package_n_clusters | partition | structure | cheap | P5 |
| `b7_ep_partition` | A17 | ep_partition_k | partition | directionality | expensive | P4,P6 |
| `b8_rm_grouping` | A21 | (delegates to b4) | partition | holonomy/RM | expensive | P3,P5 |
| `b9_per_sector_packaging` | A22 | sector_c_size | packaging | structure | cheap | P4,P5 |
| `b10_ep_grouping` | A23 | (delegates to b7) | partition | directionality | expensive | P5,P6 |
| `b11_sector_audit` | A24 | sector_c_ep | partition | directionality | expensive | P4,P6 |
| `b12_meta_audit` | A25 | dpi_ratio, dpi_satisfied | macro | information | cheap | P6 |

### 1.4 Runner KEY_* lines (`crates/runner/src/main.rs`)

Emitted to stdout during sweeps. Phase 3 PICA characterization keys:

| Key | Fields | When emitted |
|-----|--------|-------------|
| `KEY_100_DYN` | seed, scale, cell, enabled, max_dyn_frob, p2_rate, repair_frac, budget, p1_acc/rej, p2_acc/rej | per-run dynamics summary |
| `KEY_100_LENS` | seed, scale, cell, source (P3\|P4\|P5\|P6), qualities | end-of-run P4 state |
| `KEY_100_PKG` | seed, scale, cell, source, qualities | end-of-run P5 state |
| `KEY_100_TAU` | seed, scale, cell, tau (pat:N \| spectral) | end-of-run tau source |
| `KEY_100_MACRO` | seed, scale, cell, level, macro_n, frob, gap, sigma_pi, sigma_u, max_asym, cyc_mean/max, n_chiral, trans_ep, n_trans, n_absorb, entries | end-of-run macro kernel |
| `KEY_100_COMM` | seed, scale, cell, [P1,P2], [P1,P4], [P2,P4] | end-of-run commutators |
| `KEY_100_DIAG` | seed, scale, cell, B1..B12 values | end-of-run Group B diagnostics |

Earlier experiment keys (EXP-087..099): `KEY_DYN`, `KEY_DYNSUMMARY`, `KEY_3LADDER_L0/L1/L2`, `KEY_P094_LEVEL/DIAG/UNIF/CHIRAL/DPI`, `KEY_097_DIAG`, `KEY_099_DIAG`.

### 1.5 Commutator norms (`crates/dynamics/src/pica/commutator.rs`)

| Commutator | Measures | Cost |
|-----------|----------|------|
| S3: [P1,P2] | Frobenius norm of P1∘P2 − P2∘P1 | expensive |
| S4: [P1,P4] | Frobenius norm of P1∘P4 − P4∘P1 | expensive |
| S5: [P2,P4] | Frobenius norm of P2∘P4 − P4∘P2 | expensive |

---

## 2. Audit Tiers

### 2.1 Lite (per observation interval)

Fast metrics. No eigen solves beyond what `observe()` already computes.

**Required fields** (all already exist in Snapshot):

| Metric | Source |
|--------|--------|
| step, position, budget, phase | Snapshot |
| eff_gap, block_count, gated_edges | Snapshot |
| macro_n, tau, frob_from_rank1, macro_gap, sigma | Snapshot |
| level1_frob | Snapshot |
| p1_accepted/rejected, p2_accepted/rejected, traj_steps | Snapshot |
| p2_repairs, p2_violations | Snapshot |

### 2.2 Standard (per refresh cycle / end-of-run)

Includes RM vectors and partition/packaging summaries.

**Required fields:**

| Metric | Source | New? |
|--------|--------|------|
| cluster_rm (per-cluster RM vector) | PicaState.cluster_rm | existing |
| packaging_rm (per-package RM vector) | PicaState.packaging_rm | existing |
| lens_source, lens_qualities | PicaState | existing |
| packaging_source, packaging_qualities | PicaState | existing |
| active_tau | PicaState | existing |
| active_p6_rate_mult, active_p6_cap_mult | PicaState | existing |
| partition_min_size, partition_max_size | spectral_partition | **new** |
| partition_entropy, partition_effective_k | spectral_partition | **new** |
| packaging_min_size, packaging_max_size | active_packaging | **new** |
| packaging_entropy, packaging_effective_k | active_packaging | **new** |
| partition_flip_count, packaging_flip_count, tau_change_count | PicaState counters | **new** |
| macro_gap_ratio (macro_gap / eff_gap) | derived | **new** |

### 2.3 Rich (end-of-run only)

Heavier diagnostics including multi-scale scan and full Group B.

**Required fields:**

| Metric | Source | New? |
|--------|--------|------|
| All Standard-tier fields | — | — |
| sigma_ratio (macro sigma / micro sigma at tau) | derived (needs K^τ) | **new** |
| B1..B12 diagnostic cells | diag_cells.rs | existing |
| commutator norms (S3, S4, S5) | commutator.rs | existing |
| sigma_u (true finite-horizon σ with uniform initial) | audit.rs | existing |
| max_asym (Frobenius asymmetry) | helpers | existing |
| cyc_mean, cyc_max, n_chiral | helpers | existing |
| trans_ep, n_trans | helpers | existing |
| n_absorb | helpers | existing |
| multi_scale_scan: for each k in {2,4,8,16,…,min(64,n/2)} | **new** |
|   — k, macro_gap, sigma_pi, max_asym, cyc_mean, cyc_max, n_chiral, frob | per-k | **new** |
| full macro kernel entries | helpers | existing |

---

## 3. Machine-Readable Emission

### KEY_AUDIT_JSON

One JSON line per audit record. Schema version 1.

```
KEY_AUDIT_JSON {"schema_version":1,"tier":"lite","exp_id":"EXP-108","seed":0,"n":64,"step":5000,...}
```

See `crates/dynamics/src/audit.rs` for the `AuditRecord` struct definition.
Emitted at observation cadence (lite), at end-of-run (standard + rich).

Existing `KEY_100_*` lines are unchanged and continue to be emitted.
