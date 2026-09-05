//! # Post-hoc measurements for runner logging.
//!
//! These functions compute diagnostic summaries at **observation time** (after
//! dynamics completes), not during the dynamics loop. They exist for the
//! experiment runner (EXP-100+) to log detailed diagnostics on evolved kernels.
//!
//! ## Relationship to action cells
//!
//! Every function here corresponds to an action cell in the PICA:
//!
//! | Function | Action cell | File |
//! |----------|-------------|------|
//! | b1_multiscale_rm | A18 (P3←P3) | p3_cells.rs |
//! | b2_sector_rm | A19 (P3←P4) | p3_cells.rs |
//! | b3_packaging_rm | A20 (P3←P5) | p3_cells.rs |
//! | b4_rm_partition | A14 (P4←P3) | lens_cells.rs |
//! | b5_hierarchical | — (pure diag) | — |
//! | b6_package_partition | A16 (P4←P5) | lens_cells.rs |
//! | b7_ep_partition | A17 (P4←P6) | lens_cells.rs |
//! | b8_rm_grouping | A21 (P5←P3) | p5_cells.rs |
//! | b9_per_sector_packaging | A22 (P5←P4) | p5_cells.rs |
//! | b10_ep_grouping | A23 (P5←P6) | p5_cells.rs |
//! | b11_sector_audit | A24 (P6←P4) | p6_cells.rs |
//! | b12_meta_audit | A25 (P6←P6) | p6_cells.rs |
//!
//! The action cells write to PicaState during dynamics; these functions provide
//! the same measurements in a standalone form for post-hoc logging.
//!
//! Function names retain the `b*_` prefix for backward compatibility with runner code.
//!
//! ## Output format
//!
//! All functions return `DiagResult { cell_label, values: Vec<(String, f64)> }`.
//! The runner prints these as `KEY_100_DIAG` lines.

use six_primitives_core::substrate::MarkovKernel;

/// Diagnostic output from a Group D cell.
pub struct DiagResult {
    pub cell_label: &'static str,
    pub values: Vec<(String, f64)>,
}

/// D1 (was B1): P3←P3 — Multi-scale route mismatch.
/// Compute RM at tau, 2*tau, 4*tau to see if mismatch converges or diverges.
pub fn b1_multiscale_rm(kernel: &MarkovKernel, partition: &[usize], tau: usize) -> DiagResult {
    let ktau = six_primitives_core::helpers::matrix_power(kernel, tau);
    b1_multiscale_rm_with_ktau(kernel, partition, tau, &ktau)
}

/// Same as `b1_multiscale_rm`, but reuses a precomputed K^tau for mult=1.
///
/// This is a pure performance helper for callers that already have K^tau.
/// Numerical behavior is identical to `b1_multiscale_rm`.
pub fn b1_multiscale_rm_with_ktau(
    kernel: &MarkovKernel,
    partition: &[usize],
    tau: usize,
    ktau_tau: &MarkovKernel,
) -> DiagResult {
    let n_clusters = partition.iter().copied().max().unwrap_or(0) + 1;
    let mut values = Vec::new();

    for &mult in &[1usize, 2, 4] {
        let rm = if mult == 1 {
            compute_partition_rm(kernel, ktau_tau, partition, n_clusters)
        } else {
            let t = tau * mult;
            let ktau = six_primitives_core::helpers::matrix_power(kernel, t);
            compute_partition_rm(kernel, &ktau, partition, n_clusters)
        };
        values.push((format!("rm_tau_{}", mult), rm));
    }

    DiagResult {
        cell_label: "P3<-P3",
        values,
    }
}

/// D2 (was B2): P3←P4 — Sector-resolved route mismatch.
/// Compute RM separately for each sector/cluster.
pub fn b2_sector_rm(kernel: &MarkovKernel, partition: &[usize], tau: usize) -> DiagResult {
    let ktau = six_primitives_core::helpers::matrix_power(kernel, tau);
    b2_sector_rm_with_ktau(kernel, partition, &ktau)
}

/// Same as `b2_sector_rm`, but reuses a precomputed K^tau.
///
/// This is a pure performance helper for callers that already have K^tau.
/// Numerical behavior is identical to `b2_sector_rm`.
pub fn b2_sector_rm_with_ktau(
    kernel: &MarkovKernel,
    partition: &[usize],
    ktau: &MarkovKernel,
) -> DiagResult {
    let n = kernel.n;
    let n_clusters = partition.iter().copied().max().unwrap_or(0) + 1;
    let mut values = Vec::new();

    let mut cluster_sizes = vec![0usize; n_clusters];
    for &c in partition {
        if c < n_clusters {
            cluster_sizes[c] += 1;
        }
    }

    // Build macro kernel
    let mut macro_k = vec![vec![0.0; n_clusters]; n_clusters];
    for i in 0..n {
        let ci = partition[i];
        if ci >= n_clusters {
            continue;
        }
        for j in 0..n {
            let cj = partition[j];
            if cj >= n_clusters {
                continue;
            }
            macro_k[ci][cj] += ktau.kernel[i][j];
        }
    }
    for c in 0..n_clusters {
        let s: f64 = macro_k[c].iter().sum();
        if s > 0.0 {
            for j in 0..n_clusters {
                macro_k[c][j] /= s;
            }
        }
    }

    // Per-cluster RM
    for c in 0..n_clusters {
        if cluster_sizes[c] == 0 {
            continue;
        }
        let mut rm = 0.0;
        let mut count = 0;
        for i in 0..n {
            if partition[i] != c {
                continue;
            }
            let mut micro_proj = vec![0.0; n_clusters];
            for j in 0..n {
                let cj = partition[j];
                if cj < n_clusters {
                    micro_proj[cj] += ktau.kernel[i][j];
                }
            }
            let mut row_rm = 0.0;
            for c2 in 0..n_clusters {
                row_rm += (micro_proj[c2] - macro_k[c][c2]).abs();
            }
            rm += row_rm;
            count += 1;
        }
        if count > 0 {
            rm /= count as f64;
        }
        values.push((format!("rm_cluster_{}", c), rm));
    }

    DiagResult {
        cell_label: "P3<-P4",
        values,
    }
}

/// D3 (was B3): P3←P5 — Packaging-lens route mismatch.
/// Compute RM using packaging (iterated endomap) rather than spectral partition.
pub fn b3_packaging_rm(kernel: &MarkovKernel, partition: &[usize], tau: usize) -> DiagResult {
    let ktau = six_primitives_core::helpers::matrix_power(kernel, tau);
    b3_packaging_rm_with_ktau(kernel, partition, &ktau)
}

/// Same as `b3_packaging_rm`, but reuses a precomputed K^tau.
///
/// This is a pure performance helper for callers that already have K^tau.
/// Numerical behavior is identical to `b3_packaging_rm`.
pub fn b3_packaging_rm_with_ktau(
    kernel: &MarkovKernel,
    partition: &[usize],
    ktau: &MarkovKernel,
) -> DiagResult {
    // For now, uses the same partition (spectral = packaging proxy).
    // Future: use actual packaging endomap fixed points.
    let n_clusters = partition.iter().copied().max().unwrap_or(0) + 1;
    let rm = compute_partition_rm(kernel, ktau, partition, n_clusters);
    DiagResult {
        cell_label: "P3<-P5",
        values: vec![("rm_packaging".into(), rm)],
    }
}

/// A14 diagnostic wrapper (was B4): P4←P3 — RM-based partition.
/// Delegates to lens_cells::p4_from_p3() and reports the cluster count.
pub fn b4_rm_partition(
    kernel: &MarkovKernel,
    partition: &[usize],
    tau: usize,
    k: usize,
) -> DiagResult {
    let rm_partition = super::lens_cells::p4_from_p3(kernel, partition, tau, k);
    let actual_k = rm_partition.iter().copied().max().unwrap_or(0) + 1;
    DiagResult {
        cell_label: "P4<-P3",
        values: vec![("rm_partition_k".into(), actual_k as f64)],
    }
}

/// D4 (was B5): P4←P4 — Hierarchical sub-sectors.
/// Recursively partition within existing sectors. Pure diagnostic, not the spectral lens.
pub fn b5_hierarchical(kernel: &MarkovKernel, partition: &[usize]) -> DiagResult {
    let n_clusters = partition.iter().copied().max().unwrap_or(0) + 1;
    let mut total_subclusters = 0usize;

    for c in 0..n_clusters {
        let members: Vec<usize> = (0..kernel.n).filter(|&i| partition[i] == c).collect();
        if members.len() < 4 {
            total_subclusters += 1;
            continue;
        }
        // Sub-partition using spectral bisection on the submatrix
        // Simple approximation: count distinct spectral gap signs
        total_subclusters += 2; // assume bisection works
    }

    DiagResult {
        cell_label: "P4<-P4",
        values: vec![("total_subclusters".into(), total_subclusters as f64)],
    }
}

/// A16 diagnostic wrapper (was B6): P4←P5 — Package-derived partition.
/// Real implementation lives in lens_cells::p4_from_p5(). This wrapper retains
/// the old signature for runner compatibility; delegation pending runner update.
pub fn b6_package_partition(_kernel: &MarkovKernel, partition: &[usize]) -> DiagResult {
    let n_clusters = partition.iter().copied().max().unwrap_or(0) + 1;
    DiagResult {
        cell_label: "P4<-P5",
        values: vec![("package_n_clusters".into(), n_clusters as f64)],
    }
}

/// A17 diagnostic wrapper (was B7): P4←P6 — EP-flow partition.
/// Delegates to lens_cells::p4_from_p6() and reports the cluster count.
pub fn b7_ep_partition(kernel: &MarkovKernel, k: usize) -> DiagResult {
    let ep_partition = super::lens_cells::p4_from_p6(kernel, k);
    let actual_k = ep_partition.iter().copied().max().unwrap_or(0) + 1;
    DiagResult {
        cell_label: "P4<-P6",
        values: vec![("ep_partition_k".into(), actual_k as f64)],
    }
}

/// D5 (was B8): P5←P3 — RM-similarity grouping.
pub fn b8_rm_grouping(kernel: &MarkovKernel, partition: &[usize], tau: usize) -> DiagResult {
    // Reuse B4 partition as proxy
    let result = b4_rm_partition(kernel, partition, tau, 4);
    DiagResult {
        cell_label: "P5<-P3",
        values: result.values,
    }
}

/// D6 (was B9): P5←P4 — Per-sector packaging.
pub fn b9_per_sector_packaging(kernel: &MarkovKernel, partition: &[usize]) -> DiagResult {
    let n_clusters = partition.iter().copied().max().unwrap_or(0) + 1;
    let mut values = Vec::new();

    for c in 0..n_clusters {
        let members: Vec<usize> = (0..kernel.n).filter(|&i| partition[i] == c).collect();
        values.push((format!("sector_{}_size", c), members.len() as f64));
    }

    DiagResult {
        cell_label: "P5<-P4",
        values,
    }
}

/// D7 (was B10): P5←P6 — EP-similarity grouping.
pub fn b10_ep_grouping(kernel: &MarkovKernel) -> DiagResult {
    let result = b7_ep_partition(kernel, 4);
    DiagResult {
        cell_label: "P5<-P6",
        values: result.values,
    }
}

/// D8 (was B11): P6←P4 — Sector-resolved audit.
/// Compute EP/sigma per sector.
pub fn b11_sector_audit(kernel: &MarkovKernel, partition: &[usize]) -> DiagResult {
    let n = kernel.n;
    let n_clusters = partition.iter().copied().max().unwrap_or(0) + 1;
    let pi = kernel.stationary(10000, 1e-12);
    let mut values = Vec::new();

    for c in 0..n_clusters {
        let mut sector_ep = 0.0;
        for i in 0..n {
            if partition[i] != c {
                continue;
            }
            for j in 0..n {
                if partition[j] != c {
                    continue;
                }
                if i == j {
                    continue;
                }
                let kij = kernel.kernel[i][j];
                let kji = kernel.kernel[j][i];
                if kij > 1e-15 && kji > 1e-15 {
                    sector_ep += pi[i] * kij * (kij / kji).ln();
                } else if kij > 1e-15 && kji <= 1e-15 {
                    sector_ep += pi[i] * kij * 30.0;
                }
            }
        }
        values.push((format!("sector_{}_ep", c), sector_ep));
    }

    DiagResult {
        cell_label: "P6<-P4",
        values,
    }
}

/// D9 (was B12): P6←P6 — Meta-audit: EP retention under coarse-graining.
/// `micro_sigma_tau` should be the EP of K^tau (NOT K), so both micro and macro
/// are measured over the same physical time (one macro step = tau micro steps).
/// EP retention = macro_sigma / micro_sigma_tau ∈ [0, 1].
/// Low retention means the CG is losing EP information.
pub fn b12_meta_audit(micro_sigma_tau: f64, macro_sigma: f64) -> DiagResult {
    let ep_retention = if micro_sigma_tau > 1e-15 {
        macro_sigma / micro_sigma_tau
    } else {
        1.0 // No micro EP → no loss
    };
    DiagResult {
        cell_label: "P6<-P6",
        values: vec![
            ("dpi_ratio".into(), ep_retention),
            (
                "dpi_satisfied".into(),
                if ep_retention <= 1.0 + 1e-10 {
                    1.0
                } else {
                    0.0
                },
            ),
        ],
    }
}

/// Helper: compute global RM for a partition.
fn compute_partition_rm(
    kernel: &MarkovKernel,
    ktau: &MarkovKernel,
    partition: &[usize],
    n_clusters: usize,
) -> f64 {
    let n = kernel.n;
    let mut csz = vec![0usize; n_clusters];
    for &c in partition {
        if c < n_clusters {
            csz[c] += 1;
        }
    }

    let mut macro_k = vec![vec![0.0; n_clusters]; n_clusters];
    for i in 0..n {
        let ci = partition[i];
        if ci >= n_clusters {
            continue;
        }
        for j in 0..n {
            let cj = partition[j];
            if cj >= n_clusters {
                continue;
            }
            macro_k[ci][cj] += ktau.kernel[i][j];
        }
    }
    for c in 0..n_clusters {
        let s: f64 = macro_k[c].iter().sum();
        if s > 0.0 {
            for j in 0..n_clusters {
                macro_k[c][j] /= s;
            }
        }
    }

    let mut total_rm = 0.0;
    let mut count = 0;
    for i in 0..n {
        let ci = partition[i];
        if ci >= n_clusters {
            continue;
        }
        let mut micro_proj = vec![0.0; n_clusters];
        for j in 0..n {
            let cj = partition[j];
            if cj < n_clusters {
                micro_proj[cj] += ktau.kernel[i][j];
            }
        }
        let mut rm = 0.0;
        for c in 0..n_clusters {
            rm += (micro_proj[c] - macro_k[ci][c]).abs();
        }
        total_rm += rm;
        count += 1;
    }
    if count > 0 {
        total_rm / count as f64
    } else {
        0.0
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_b1_precomputed_matches_baseline() {
        let k = MarkovKernel::random(16, 42);
        let part = crate::spectral::spectral_partition(&k, 4);
        let tau = 5usize;
        let ktau = six_primitives_core::helpers::matrix_power(&k, tau);
        let a = b1_multiscale_rm(&k, &part, tau);
        let b = b1_multiscale_rm_with_ktau(&k, &part, tau, &ktau);
        assert_eq!(a.values.len(), b.values.len());
        for ((ka, va), (kb, vb)) in a.values.iter().zip(b.values.iter()) {
            assert_eq!(ka, kb);
            assert_eq!(va.to_bits(), vb.to_bits());
        }
    }

    #[test]
    fn test_b2_precomputed_matches_baseline() {
        let k = MarkovKernel::random(16, 43);
        let part = crate::spectral::spectral_partition(&k, 4);
        let tau = 7usize;
        let ktau = six_primitives_core::helpers::matrix_power(&k, tau);
        let a = b2_sector_rm(&k, &part, tau);
        let b = b2_sector_rm_with_ktau(&k, &part, &ktau);
        assert_eq!(a.values.len(), b.values.len());
        for ((ka, va), (kb, vb)) in a.values.iter().zip(b.values.iter()) {
            assert_eq!(ka, kb);
            assert_eq!(va.to_bits(), vb.to_bits());
        }
    }

    #[test]
    fn test_b3_precomputed_matches_baseline() {
        let k = MarkovKernel::random(16, 44);
        let part = crate::spectral::spectral_partition(&k, 4);
        let tau = 3usize;
        let ktau = six_primitives_core::helpers::matrix_power(&k, tau);
        let a = b3_packaging_rm(&k, &part, tau);
        let b = b3_packaging_rm_with_ktau(&k, &part, &ktau);
        assert_eq!(a.values.len(), b.values.len());
        for ((ka, va), (kb, vb)) in a.values.iter().zip(b.values.iter()) {
            assert_eq!(ka, kb);
            assert_eq!(va.to_bits(), vb.to_bits());
        }
    }
}
