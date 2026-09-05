//! # P4 row cells: lens/partition producers controlled by PICA.
//!
//! P4 (sectors) produces the partition (lens) consumed by 6 downstream A-cells:
//! A3, A4, A5 (P1 row) and A9, A10, A11 (P2 row). Before PICA reclassification,
//! the spectral partition was hardwired outside PICA. Now it's A15 (P4←P4), one of
//! four lens cells in the P4 row of the Primitive Interaction Closure Algebra.
//!
//! ## Why P4 has 4 informants (not 6)
//!
//! - P4←P1 and P4←P2 are **Implicit** (Group I): when P1/P2 modify K, the
//!   partition updates automatically on the next refresh cycle. No explicit code.
//! - P4←P3 (A14), P4←P4 (A15), P4←P5 (A16), P4←P6 (A17) are the 4 action cells.
//!
//! ## Selection, not multiplication
//!
//! Unlike P1/P2 cells (which combine scores multiplicatively), P4 cells produce
//! **discrete partitions** that can't be multiplied together. When multiple P4
//! cells are enabled, each computes a candidate partition and the best is
//! **selected** by a configurable `LensSelector` criterion:
//!
//! - `MinRM`:   lowest global route mismatch (most CG-consistent)
//! - `MaxGap`:  largest macro spectral gap (best time-scale separation)
//! - `MaxFrob`: highest macro Frobenius deviation (most structured)
//!
//! **Hysteresis**: the system only switches to a new lens if it beats the current
//! one by >10% on the selected criterion. This prevents oscillation when two
//! lenses are nearly equivalent.
//!
//! ## Cell inventory
//!
//! | Cell | Informant | Role | Needs base partition? |
//! |------|-----------|------|-----------------------|
//! | A14  | P3 (holonomy) | RM-quantile partition | Yes (uses RM, which needs a partition) |
//! | A15  | P4 (self)     | Spectral partition (canonical) | No (bootstraps from eigenvectors) |
//! | A16  | P5 (packaging)| Row-similarity partition | No (uses K^τ row cosine similarity) |
//! | A17  | P6 (audit)    | EP-flow partition | No (uses stationary distribution) |
//!
//! A15 is the **canonical lens** — it's the only cell that existed pre-PICA (as
//! hardwired code in `refresh_informants()`). It's also the only cell guaranteed
//! to produce a meaningful partition on any kernel. Other cells provide alternative
//! perspectives that may be more informative for specific dynamics regimes.

use super::config::LensSelector;
use crate::state::{AugmentedState, DynamicsConfig};
use six_primitives_core::helpers;
use six_primitives_core::substrate::MarkovKernel;

/// Result of P4 lens computation: partition + metadata for logging.
pub struct LensResult {
    /// The selected partition (micro state → cluster index).
    pub partition: Vec<usize>,
    /// Which informant produced the winning partition (2=P3, 3=P4, 4=P5, 5=P6).
    pub source: u8,
    /// Score of each candidate: (informant_id, score). For logging.
    pub qualities: Vec<(u8, f64)>,
    /// Whether the partition actually changed from the previous one.
    /// False when hysteresis keeps the old partition.
    pub changed: bool,
}

/// A14: P4←P3 — RM-quantile partition.
///
/// Groups states by route-mismatch similarity: states with similar CG error
/// are placed in the same cluster. Requires a base partition to compute per-row
/// RM values (cannot bootstrap without one).
pub fn p4_from_p3(
    kernel: &MarkovKernel,
    base_partition: &[usize],
    tau: usize,
    k: usize,
) -> Vec<usize> {
    let n = kernel.n;
    if n <= 1 || k <= 1 {
        return vec![0; n];
    }

    let n_base = base_partition.iter().copied().max().unwrap_or(0) + 1;
    let ktau = helpers::matrix_power(kernel, tau);

    // Build macro kernel from base partition
    let mut macro_k = vec![vec![0.0; n_base]; n_base];
    for i in 0..n {
        let ci = base_partition[i];
        if ci >= n_base {
            continue;
        }
        for j in 0..n {
            let cj = base_partition[j];
            if cj >= n_base {
                continue;
            }
            macro_k[ci][cj] += ktau.kernel[i][j];
        }
    }
    for c in 0..n_base {
        let s: f64 = macro_k[c].iter().sum();
        if s > 0.0 {
            for j in 0..n_base {
                macro_k[c][j] /= s;
            }
        }
    }

    // Per-row RM contribution
    let mut row_rm = vec![0.0; n];
    for i in 0..n {
        let ci = base_partition[i];
        if ci >= n_base {
            continue;
        }
        let mut micro_proj = vec![0.0; n_base];
        for j in 0..n {
            let cj = base_partition[j];
            if cj < n_base {
                micro_proj[cj] += ktau.kernel[i][j];
            }
        }
        for c2 in 0..n_base {
            row_rm[i] += (micro_proj[c2] - macro_k[ci][c2]).abs();
        }
    }

    // If RM is flat (no variation), return base partition unchanged
    let rm_min = row_rm.iter().cloned().fold(f64::INFINITY, f64::min);
    let rm_max = row_rm.iter().cloned().fold(f64::NEG_INFINITY, f64::max);
    if rm_max - rm_min < 1e-9 {
        return base_partition.to_vec();
    }

    // k-way partition by RM quantiles
    let mut sorted: Vec<(usize, f64)> = row_rm.iter().copied().enumerate().collect();
    sorted.sort_by(|a, b| a.1.partial_cmp(&b.1).unwrap_or(std::cmp::Ordering::Equal));
    let chunk = (n + k - 1) / k;
    let mut partition = vec![0usize; n];
    for (rank, &(idx, _)) in sorted.iter().enumerate() {
        partition[idx] = (rank / chunk).min(k - 1);
    }

    partition
}

/// A15: P4←P4 — Spectral partition (canonical lens).
///
/// Sign-based clustering from the top-d eigenvectors of K (d = ceil(log2(k))).
/// This is the canonical lens: it bootstraps from eigenvectors without needing
/// any pre-existing partition.
pub fn p4_from_p4(kernel: &MarkovKernel, k: usize) -> Vec<usize> {
    crate::spectral::spectral_partition(kernel, k)
}

/// A16: P4←P5 — Package-derived partition.
///
/// Clusters states by cosine similarity of their K^τ row distributions.
/// States that "go to similar places" after τ steps belong to the same package.
/// Builds a row-similarity stochastic matrix and applies spectral partition to it.
pub fn p4_from_p5(kernel: &MarkovKernel, tau: usize, k: usize) -> Vec<usize> {
    let n = kernel.n;
    if n <= 1 || k <= 1 {
        return vec![0; n];
    }

    let ktau = helpers::matrix_power(kernel, tau);

    // Build similarity matrix: S[i][j] = cosine similarity of K^tau rows
    let norms: Vec<f64> = (0..n)
        .map(|i| ktau.kernel[i].iter().map(|x| x * x).sum::<f64>().sqrt())
        .collect();

    let mut sim = vec![vec![0.0; n]; n];
    for i in 0..n {
        for j in 0..n {
            if norms[i] < 1e-15 || norms[j] < 1e-15 {
                sim[i][j] = if i == j { 1.0 } else { 0.0 };
            } else {
                let dot: f64 = (0..n).map(|l| ktau.kernel[i][l] * ktau.kernel[j][l]).sum();
                sim[i][j] = (dot / (norms[i] * norms[j])).max(0.0);
            }
        }
    }

    // Row-normalize to stochastic matrix
    for i in 0..n {
        let row_sum: f64 = sim[i].iter().sum();
        if row_sum > 0.0 {
            for j in 0..n {
                sim[i][j] /= row_sum;
            }
        }
    }

    // Apply spectral partition to the similarity kernel
    let sim_kernel = MarkovKernel { n, kernel: sim };
    crate::spectral::spectral_partition(&sim_kernel, k)
}

/// A17: P4←P6 — EP-flow partition.
///
/// Groups states by entropy production contribution quantiles.
/// States with similar thermodynamic role (similar EP contribution) cluster together.
pub fn p4_from_p6(kernel: &MarkovKernel, k: usize) -> Vec<usize> {
    let n = kernel.n;
    if n <= 1 || k <= 1 {
        return vec![0; n];
    }

    let pi = kernel.stationary(10000, 1e-12);

    // Per-state EP contribution: sum_j pi[i] * K[i][j] * ln(K[i][j]/K[j][i])
    // Matches core path_reversal_asymmetry: irreversible edges get capped contribution
    let mut ep_contrib = vec![0.0; n];
    for i in 0..n {
        for j in 0..n {
            if i == j {
                continue;
            }
            let kij = kernel.kernel[i][j];
            let kji = kernel.kernel[j][i];
            if kij > 1e-15 && kji > 1e-15 {
                ep_contrib[i] += pi[i] * kij * (kij / kji).ln();
            } else if kij > 1e-15 && kji <= 1e-15 {
                ep_contrib[i] += pi[i] * kij * 30.0;
            }
        }
    }

    // k-way partition by EP quantiles
    let mut sorted: Vec<(usize, f64)> = ep_contrib.iter().copied().enumerate().collect();
    sorted.sort_by(|a, b| a.1.partial_cmp(&b.1).unwrap_or(std::cmp::Ordering::Equal));
    let chunk = (n + k - 1) / k;
    let mut partition = vec![0usize; n];
    for (rank, &(idx, _)) in sorted.iter().enumerate() {
        partition[idx] = (rank / chunk).min(k - 1);
    }

    partition
}

/// Score a partition by global route mismatch (lower = better CG consistency).
pub fn score_partition_rm(
    kernel: &MarkovKernel,
    ktau: &MarkovKernel,
    partition: &[usize],
    n_clusters: usize,
) -> f64 {
    let n = kernel.n;

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

/// Compute a score for a partition using the configured selector criterion.
fn compute_lens_score(
    kernel: &MarkovKernel,
    ktau: &MarkovKernel,
    partition: &[usize],
    n_clusters: usize,
    selector: &LensSelector,
) -> f64 {
    match selector {
        LensSelector::MinRM => score_partition_rm(kernel, ktau, partition, n_clusters),
        LensSelector::MaxGap => {
            let macro_k = helpers::build_macro_from_ktau(&ktau.kernel, partition, n_clusters);
            macro_k.spectral_gap()
        }
        LensSelector::MaxFrob => {
            let macro_k = helpers::build_macro_from_ktau(&ktau.kernel, partition, n_clusters);
            crate::observe::frob_from_rank1(&macro_k)
        }
    }
}

/// Compute the active P4 partition from enabled lens cells.
///
/// When multiple P4 cells are enabled, each produces a candidate partition.
/// The best is selected by the configured `LensSelector`. Hysteresis prevents
/// oscillation: the system only switches if the new lens is >10% better.
///
/// Fallback: if no P4 cells are enabled, uses spectral partition (A15 behavior).
pub fn compute_p4_partition(state: &AugmentedState, config: &DynamicsConfig) -> LensResult {
    let pica = &config.pica;
    let k = config.n_clusters;
    let kernel = &state.effective_kernel;

    let gap = kernel.spectral_gap();
    let tau = state
        .pica_state
        .active_tau
        .unwrap_or_else(|| crate::observe::adaptive_tau(gap, config.tau_alpha));

    // Collect candidate partitions from enabled P4-row cells
    let mut candidates: Vec<(u8, Vec<usize>)> = Vec::new();

    // A14: P4←P3 (needs base partition to compute RM)
    if pica.enabled[3][2] {
        if let Some(ref base_part) = state.pica_state.spectral_partition {
            candidates.push((2, p4_from_p3(kernel, base_part, tau, k)));
        }
    }

    // A15: P4←P4 (standalone, canonical)
    if pica.enabled[3][3] {
        candidates.push((3, p4_from_p4(kernel, k)));
    }

    // A16: P4←P5
    if pica.enabled[3][4] {
        candidates.push((4, p4_from_p5(kernel, tau, k)));
    }

    // A17: P4←P6
    if pica.enabled[3][5] {
        candidates.push((5, p4_from_p6(kernel, k)));
    }

    // Fallback: if nothing enabled, use spectral
    if candidates.is_empty() {
        let part = crate::spectral::spectral_partition(kernel, k);
        let changed = state.pica_state.spectral_partition.as_ref() != Some(&part);
        return LensResult {
            partition: part,
            source: 3,
            qualities: vec![(3, 0.0)],
            changed,
        };
    }

    // Single candidate: return directly
    if candidates.len() == 1 {
        let (src, part) = candidates.into_iter().next().unwrap();
        let changed = state.pica_state.spectral_partition.as_ref() != Some(&part);
        return LensResult {
            partition: part,
            source: src,
            qualities: vec![(src, 0.0)],
            changed,
        };
    }

    // Multiple candidates: score and select
    let ktau = helpers::matrix_power(kernel, tau);
    let scored: Vec<(u8, Vec<usize>, f64)> = candidates
        .into_iter()
        .map(|(src, part)| {
            let nc = part.iter().copied().max().unwrap_or(0) + 1;
            let score = compute_lens_score(kernel, &ktau, &part, nc, &pica.lens_selector);
            (src, part, score)
        })
        .collect();

    let qualities: Vec<(u8, f64)> = scored.iter().map(|(s, _, q)| (*s, *q)).collect();

    // Sort: for MinRM lower is better; for MaxGap/MaxFrob higher is better
    let mut sorted = scored;
    match pica.lens_selector {
        LensSelector::MinRM => {
            sorted.sort_by(|a, b| a.2.partial_cmp(&b.2).unwrap_or(std::cmp::Ordering::Equal));
        }
        LensSelector::MaxGap | LensSelector::MaxFrob => {
            sorted.sort_by(|a, b| b.2.partial_cmp(&a.2).unwrap_or(std::cmp::Ordering::Equal));
        }
    }

    // Hysteresis: only switch if best candidate beats current partition by >10%
    if let Some(ref current_part) = state.pica_state.spectral_partition {
        let current_nc = current_part.iter().copied().max().unwrap_or(0) + 1;
        let current_score =
            compute_lens_score(kernel, &ktau, current_part, current_nc, &pica.lens_selector);
        let best_score = sorted[0].2;

        let should_switch = if current_score <= 1e-15 && best_score <= 1e-15 {
            // Both scores near zero — no reason to switch
            false
        } else if current_score <= 1e-15 {
            // Current is degenerate, any positive candidate is better
            true
        } else {
            match pica.lens_selector {
                LensSelector::MinRM => {
                    // Lower is better: switch if best is >10% lower
                    (current_score - best_score) / current_score > 0.10
                }
                LensSelector::MaxGap | LensSelector::MaxFrob => {
                    // Higher is better: switch if best is >10% higher
                    (best_score - current_score) / current_score > 0.10
                }
            }
        };

        if !should_switch {
            // Current partition is good enough, keep it
            return LensResult {
                partition: current_part.clone(),
                source: state.pica_state.active_lens_source.unwrap_or(3),
                qualities,
                changed: false,
            };
        }
    }

    let (src, part, _) = sorted.into_iter().next().unwrap();
    LensResult {
        partition: part,
        source: src,
        qualities,
        changed: true, // switching to a new partition
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_p4_from_p4_matches_spectral() {
        let k = MarkovKernel::random(32, 42);
        let part = p4_from_p4(&k, 2);
        let direct = crate::spectral::spectral_partition(&k, 2);
        assert_eq!(part, direct, "A15 should wrap spectral_partition exactly");
    }

    #[test]
    fn test_p4_from_p3_valid_partition() {
        let k = MarkovKernel::random(32, 42);
        let base = crate::spectral::spectral_partition(&k, 2);
        let part = p4_from_p3(&k, &base, 5, 2);
        assert_eq!(part.len(), 32);
        let nc = part.iter().copied().max().unwrap_or(0) + 1;
        assert!(
            nc >= 1 && nc <= 2,
            "A14 should give 1-2 clusters, got {}",
            nc
        );
        for &c in &part {
            assert!(c < nc);
        }
    }

    #[test]
    fn test_p4_from_p5_valid_partition() {
        let k = MarkovKernel::random(32, 42);
        let part = p4_from_p5(&k, 5, 2);
        assert_eq!(part.len(), 32);
        let nc = part.iter().copied().max().unwrap_or(0) + 1;
        assert!(
            nc >= 1 && nc <= 2,
            "A16 should give 1-2 clusters, got {}",
            nc
        );
    }

    #[test]
    fn test_p4_from_p6_valid_partition() {
        let k = MarkovKernel::random(32, 42);
        let part = p4_from_p6(&k, 2);
        assert_eq!(part.len(), 32);
        let nc = part.iter().copied().max().unwrap_or(0) + 1;
        assert!(
            nc >= 1 && nc <= 2,
            "A17 should give 1-2 clusters, got {}",
            nc
        );
    }

    #[test]
    fn test_score_partition_rm_nonnegative() {
        let k = MarkovKernel::random(32, 42);
        let part = crate::spectral::spectral_partition(&k, 2);
        let ktau = helpers::matrix_power(&k, 5);
        let nc = crate::spectral::n_clusters(&part);
        let rm = score_partition_rm(&k, &ktau, &part, nc);
        assert!(rm >= 0.0, "RM should be non-negative, got {}", rm);
        assert!(rm < 2.0, "RM should be bounded, got {}", rm);
    }

    #[test]
    fn test_p4_from_p3_4way() {
        let k = MarkovKernel::random(64, 42);
        let base = crate::spectral::spectral_partition(&k, 4);
        let part = p4_from_p3(&k, &base, 5, 4);
        assert_eq!(part.len(), 64);
        let nc = part.iter().copied().max().unwrap_or(0) + 1;
        assert!(
            nc >= 2 && nc <= 4,
            "A14 4-way should give 2-4 clusters, got {}",
            nc
        );
    }

    #[test]
    fn test_p4_from_p6_4way() {
        let k = MarkovKernel::random(64, 42);
        let part = p4_from_p6(&k, 4);
        assert_eq!(part.len(), 64);
        let nc = part.iter().copied().max().unwrap_or(0) + 1;
        assert!(
            nc >= 2 && nc <= 4,
            "A17 4-way should give 2-4 clusters, got {}",
            nc
        );
    }
}
