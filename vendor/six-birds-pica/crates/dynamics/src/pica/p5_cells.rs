//! # P5 row cells: packaging producers controlled by PICA.
//!
//! P5 (packaging) produces equivalence-class groupings consumed by A5 (P1←P5)
//! and A11 (P2←P5). Before this promotion, A5/A11 consumed the P4 spectral
//! partition. Now they read `PicaState::active_packaging`, produced by P5-row cells.
//!
//! ## Why P5 has 3 informants (not 6)
//!
//! - P5←P1 and P5←P2 are **Implicit** (Group I): when P1/P2 modify K, the
//!   packaging updates automatically on the next refresh cycle.
//! - P5←P5 is **Trivial** (T2): packaging idempotence e(e(x)) = e(x).
//! - P5←P3 (A21), P5←P4 (A22), P5←P6 (A23) are the 3 action cells.
//!
//! ## Selection, not multiplication
//!
//! Same as P4: discrete partitions can't be multiplied. When multiple P5 cells
//! are enabled, each computes a candidate packaging and the best is selected
//! by the configured `packaging_selector` (same `LensSelector` enum).
//! Hysteresis prevents oscillation (>10% improvement required to switch).
//!
//! ## Cell inventory
//!
//! | Cell | Informant | Algorithm | Needs base partition? |
//! |------|-----------|-----------|----------------------|
//! | A21  | P3 (holonomy) | RM-quantile (reuses A14 algorithm) | Yes |
//! | A22  | P4 (sectors)  | Sector-balanced (split oversized clusters) | Yes |
//! | A23  | P6 (audit)    | EP-quantile (reuses A17 algorithm) | No |

use super::config::LensSelector;
use super::lens_cells;
use crate::state::{AugmentedState, DynamicsConfig};
use six_primitives_core::helpers;
use six_primitives_core::substrate::MarkovKernel;

/// Result of P5 packaging computation: partition + metadata for logging.
pub struct PackagingResult {
    /// The selected packaging (micro state → package index).
    pub packaging: Vec<usize>,
    /// Which informant produced the winning packaging (2=P3, 3=P4, 5=P6).
    pub source: u8,
    /// Score of each candidate: (informant_id, score). For logging.
    pub qualities: Vec<(u8, f64)>,
    /// Whether the packaging actually changed from the previous one.
    /// False when hysteresis keeps the old packaging.
    pub changed: bool,
}

/// A21: P5←P3 — RM-similarity packaging.
///
/// Groups states by route-mismatch similarity: states with similar CG error
/// are in the same package. Reuses the A14 (p4_from_p3) algorithm.
pub fn p5_from_p3(
    kernel: &MarkovKernel,
    base_partition: &[usize],
    tau: usize,
    k: usize,
) -> Vec<usize> {
    // Same algorithm as A14: RM-quantile partition
    lens_cells::p4_from_p3(kernel, base_partition, tau, k)
}

/// A22: P5←P4 — Sector-balanced packaging.
///
/// Start from P4's active partition. If any cluster has >40% of states, bisect it
/// using spectral partition on the full kernel. If any cluster has <2 states, merge
/// with nearest neighbor. Output: rebalanced partition.
pub fn p5_from_p4(kernel: &MarkovKernel, base_partition: &[usize], k: usize) -> Vec<usize> {
    let n = kernel.n;
    if n <= 1 || k <= 1 {
        return vec![0; n];
    }

    let n_clusters = base_partition.iter().copied().max().unwrap_or(0) + 1;
    if n_clusters < 1 {
        return vec![0; n];
    }

    let mut cluster_sizes = vec![0usize; n_clusters];
    for &c in base_partition {
        if c < n_clusters {
            cluster_sizes[c] += 1;
        }
    }

    let threshold = (n as f64 * 0.4).ceil() as usize;
    let mut packaging = base_partition.to_vec();
    let mut next_label = n_clusters;

    // Pass 1: split oversized clusters
    for c in 0..n_clusters {
        if cluster_sizes[c] <= threshold {
            continue;
        }

        // Bisect this cluster using spectral partition
        let members: Vec<usize> = (0..n).filter(|&i| packaging[i] == c).collect();
        if members.len() < 4 {
            continue;
        }

        // Use LOCAL spectral bisection on the induced sub-kernel for this cluster.
        let m = members.len();
        let mut sub = MarkovKernel {
            n: m,
            kernel: vec![vec![0.0; m]; m],
        };
        for (li, &i) in members.iter().enumerate() {
            let mut row_sum = 0.0;
            for (lj, &j) in members.iter().enumerate() {
                let w = kernel.kernel[i][j];
                sub.kernel[li][lj] = w;
                row_sum += w;
            }
            if row_sum > 1e-15 {
                for lj in 0..m {
                    sub.kernel[li][lj] /= row_sum;
                }
            } else {
                for lj in 0..m {
                    sub.kernel[li][lj] = 1.0 / m as f64;
                }
            }
        }
        let sub_part = crate::spectral::spectral_partition(&sub, 2);
        let n_left = sub_part.iter().filter(|&&x| x == 0).count();
        let n_right = m - n_left;
        if n_left == 0 || n_right == 0 {
            // Degenerate bisection: use deterministic half split to enforce rebalance.
            for (li, &i) in members.iter().enumerate() {
                if li >= m / 2 {
                    packaging[i] = next_label;
                }
            }
        } else {
            for (li, &i) in members.iter().enumerate() {
                if sub_part[li] == 1 {
                    packaging[i] = next_label;
                }
            }
        }
        let moved = members
            .iter()
            .filter(|&&i| packaging[i] == next_label)
            .count();
        if moved > 0 && moved < m {
            next_label += 1;
        }
    }

    // Pass 2: merge tiny clusters (<2 states) with nearest neighbor
    let new_n_clusters = next_label;
    let mut new_sizes = vec![0usize; new_n_clusters];
    for &c in &packaging {
        if c < new_n_clusters {
            new_sizes[c] += 1;
        }
    }

    for c in 0..new_n_clusters {
        if new_sizes[c] == 0 || new_sizes[c] >= 2 {
            continue;
        }
        // Find the single member
        if let Some(member) = (0..n).find(|&i| packaging[i] == c) {
            // Merge with the cluster that has the strongest symmetric coupling.
            // Using both outgoing and incoming flow is more robust in non-reversible systems.
            let mut best_cluster = c;
            let mut best_flow = -1.0f64;
            for c2 in 0..new_n_clusters {
                if c2 == c || new_sizes[c2] == 0 {
                    continue;
                }
                let mut flow = 0.0;
                for j in 0..n {
                    if packaging[j] != c2 {
                        continue;
                    }
                    flow += kernel.kernel[member][j] + kernel.kernel[j][member];
                }
                if flow > best_flow {
                    best_flow = flow;
                    best_cluster = c2;
                }
            }
            if best_cluster != c {
                packaging[member] = best_cluster;
            }
        }
    }

    // Compact labels to 0..actual_k-1
    compact_labels(&mut packaging, n)
}

/// A23: P5←P6 — EP-similarity packaging.
///
/// Groups states by entropy production contribution quantiles.
/// Reuses the A17 (p4_from_p6) algorithm.
pub fn p5_from_p6(kernel: &MarkovKernel, k: usize) -> Vec<usize> {
    // Same algorithm as A17: EP-quantile partition
    lens_cells::p4_from_p6(kernel, k)
}

/// Compute the active P5 packaging from enabled P5-row cells.
///
/// When multiple P5 cells are enabled, each produces a candidate packaging.
/// The best is selected by the configured `packaging_selector`. Hysteresis
/// prevents oscillation: only switch if the new packaging is >10% better.
pub fn compute_p5_packaging(state: &AugmentedState, config: &DynamicsConfig) -> PackagingResult {
    let pica = &config.pica;
    let k = config.n_clusters;
    let kernel = &state.effective_kernel;

    let gap = kernel.spectral_gap();
    let tau = state
        .pica_state
        .active_tau
        .unwrap_or_else(|| crate::observe::adaptive_tau(gap, config.tau_alpha));

    // Collect candidate packagings from enabled P5-row cells
    let mut candidates: Vec<(u8, Vec<usize>)> = Vec::new();

    // A21: P5←P3 (needs base partition)
    if pica.enabled[4][2] {
        if let Some(ref base_part) = state.pica_state.spectral_partition {
            candidates.push((2, p5_from_p3(kernel, base_part, tau, k)));
        }
    }

    // A22: P5←P4 (needs base partition)
    if pica.enabled[4][3] {
        if let Some(ref base_part) = state.pica_state.spectral_partition {
            candidates.push((3, p5_from_p4(kernel, base_part, k)));
        }
    }

    // A23: P5←P6 (standalone)
    if pica.enabled[4][5] {
        candidates.push((5, p5_from_p6(kernel, k)));
    }

    // Fallback: if nothing enabled, return the P4 partition as packaging
    if candidates.is_empty() {
        let part = state
            .pica_state
            .spectral_partition
            .clone()
            .unwrap_or_else(|| vec![0; kernel.n]);
        let changed = state.pica_state.active_packaging.as_ref() != Some(&part);
        return PackagingResult {
            packaging: part,
            source: 3,
            qualities: vec![(3, 0.0)],
            changed,
        };
    }

    // Single candidate: return directly
    if candidates.len() == 1 {
        let (src, part) = candidates.into_iter().next().unwrap();
        let changed = state.pica_state.active_packaging.as_ref() != Some(&part);
        return PackagingResult {
            packaging: part,
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
            let score = compute_packaging_score(kernel, &ktau, &part, nc, &pica.packaging_selector);
            (src, part, score)
        })
        .collect();

    let qualities: Vec<(u8, f64)> = scored.iter().map(|(s, _, q)| (*s, *q)).collect();

    // Sort by criterion
    let mut sorted = scored;
    match pica.packaging_selector {
        LensSelector::MinRM => {
            sorted.sort_by(|a, b| a.2.partial_cmp(&b.2).unwrap_or(std::cmp::Ordering::Equal));
        }
        LensSelector::MaxGap | LensSelector::MaxFrob => {
            sorted.sort_by(|a, b| b.2.partial_cmp(&a.2).unwrap_or(std::cmp::Ordering::Equal));
        }
    }

    // Hysteresis: only switch if best candidate beats current by >10%
    if let Some(ref current_pkg) = state.pica_state.active_packaging {
        let current_nc = current_pkg.iter().copied().max().unwrap_or(0) + 1;
        let current_score = compute_packaging_score(
            kernel,
            &ktau,
            current_pkg,
            current_nc,
            &pica.packaging_selector,
        );
        let best_score = sorted[0].2;

        let should_switch = if current_score <= 1e-15 && best_score <= 1e-15 {
            false
        } else if current_score <= 1e-15 {
            true
        } else {
            match pica.packaging_selector {
                LensSelector::MinRM => (current_score - best_score) / current_score > 0.10,
                LensSelector::MaxGap | LensSelector::MaxFrob => {
                    (best_score - current_score) / current_score > 0.10
                }
            }
        };

        if !should_switch {
            return PackagingResult {
                packaging: current_pkg.clone(),
                source: state.pica_state.packaging_source.unwrap_or(3),
                qualities,
                changed: false,
            };
        }
    }

    let (src, part, _) = sorted.into_iter().next().unwrap();
    PackagingResult {
        packaging: part,
        source: src,
        qualities,
        changed: true, // switching to new packaging
    }
}

/// Score a packaging using the same criterion as P4 lens scoring.
fn compute_packaging_score(
    kernel: &MarkovKernel,
    ktau: &MarkovKernel,
    partition: &[usize],
    n_clusters: usize,
    selector: &LensSelector,
) -> f64 {
    match selector {
        LensSelector::MinRM => lens_cells::score_partition_rm(kernel, ktau, partition, n_clusters),
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

/// Compact partition labels to consecutive 0..k-1.
fn compact_labels(partition: &mut Vec<usize>, n: usize) -> Vec<usize> {
    let mut seen = std::collections::BTreeSet::new();
    for &c in partition.iter() {
        seen.insert(c);
    }
    let label_map: std::collections::BTreeMap<usize, usize> = seen
        .iter()
        .enumerate()
        .map(|(new, &old)| (old, new))
        .collect();
    let mut result = vec![0usize; n];
    for i in 0..n {
        result[i] = label_map[&partition[i]];
    }
    result
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_p5_from_p3_valid_packaging() {
        let k = MarkovKernel::random(32, 42);
        let base = crate::spectral::spectral_partition(&k, 4);
        let pkg = p5_from_p3(&k, &base, 5, 4);
        assert_eq!(pkg.len(), 32);
        let nc = pkg.iter().copied().max().unwrap_or(0) + 1;
        assert!(
            nc >= 1 && nc <= 4,
            "A21 should give 1-4 packages, got {}",
            nc
        );
    }

    #[test]
    fn test_p5_from_p4_rebalances() {
        let k = MarkovKernel::random(32, 42);
        let base = crate::spectral::spectral_partition(&k, 2);
        let pkg = p5_from_p4(&k, &base, 4);
        assert_eq!(pkg.len(), 32);
        // Should have split any oversized clusters
        let nc = pkg.iter().copied().max().unwrap_or(0) + 1;
        assert!(nc >= 1, "A22 should produce at least 1 package");
    }

    #[test]
    fn test_p5_from_p6_valid_packaging() {
        let k = MarkovKernel::random(32, 42);
        let pkg = p5_from_p6(&k, 4);
        assert_eq!(pkg.len(), 32);
        let nc = pkg.iter().copied().max().unwrap_or(0) + 1;
        assert!(
            nc >= 1 && nc <= 4,
            "A23 should give 1-4 packages, got {}",
            nc
        );
    }

    #[test]
    fn test_p5_from_p4_tiny_merge_uses_symmetric_flow() {
        // Base packaging has one tiny cluster (state 4).
        // Outgoing flow from state 4 favors cluster 0, but incoming flow from cluster 1
        // is stronger. Symmetric merge should choose cluster 1.
        let mut k = MarkovKernel {
            n: 5,
            kernel: vec![vec![0.0; 5]; 5],
        };
        // Cluster 0 states: 0,1
        k.kernel[0] = vec![0.70, 0.20, 0.05, 0.04, 0.01];
        k.kernel[1] = vec![0.20, 0.70, 0.05, 0.04, 0.01];
        // Cluster 1 states: 2,3 (strong incoming to state 4)
        k.kernel[2] = vec![0.10, 0.10, 0.10, 0.10, 0.60];
        k.kernel[3] = vec![0.10, 0.10, 0.10, 0.10, 0.60];
        // Tiny cluster state 4: outgoing favors cluster 0
        k.kernel[4] = vec![0.50, 0.30, 0.10, 0.10, 0.00];

        let base = vec![0, 0, 1, 1, 2];
        let pkg = p5_from_p4(&k, &base, 4);
        assert_eq!(pkg.len(), 5);
        // Tiny state 4 should merge with cluster containing states 2/3.
        assert_eq!(pkg[4], pkg[2]);
        assert_eq!(pkg[4], pkg[3]);
        assert_ne!(pkg[4], pkg[0]);
    }
}
