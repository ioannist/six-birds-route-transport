//! # P1 row cells: modulations that change which rows P1 perturbs and how.
//!
//! P1 (rewrite) perturbs a single row of K. By default, the row is chosen uniformly
//! at random. These 6 cells replace uniform selection with informed targeting — each
//! informant Pj contributes a weight vector saying which rows are most worth perturbing.
//!
//! ## Why P1 has all 6 informants
//!
//! P1 is the most general action primitive — it can rewrite any row arbitrarily.
//! Every other primitive's output is useful for targeting P1:
//! - **P1** itself: avoid re-perturbing rows that haven't settled yet (cooldown)
//! - **P2**: rows left sparse by gating need redistribution (sparsity)
//! - **P3**: rows causing high coarse-graining error should be fixed (RM rewrite)
//! - **P4**: rows near cluster boundaries are most impactful to perturb (boundary)
//! - **P5**: rows with high packaging defect aren't converged yet (defect)
//! - **P6**: don't waste limited budget on rewrites (budget gate)
//!
//! ## Output
//!
//! Each cell returns `P1Scores { row_weights, direction }`. Higher `row_weights[i]`
//! makes row i more likely to be selected. Optional `direction` provides a target
//! distribution to bias the perturbation toward (only A3 uses this).
//!
//! When multiple P1 cells are enabled, their `row_weights` are multiplied element-wise
//! (see `scores::combine_p1`). This means cells *stack*: a row that is both in a
//! high-RM cluster (A3) AND near a boundary (A4) gets the strongest boost.
//!
//! ## Cell inventory
//!
//! | Cell | Informant | Role | Key param |
//! |------|-----------|------|-----------|
//! | A1 | P1 (self) | History cooldown | `p1_p1_cooldown` (steps) |
//! | A2 | P2 (gate) | Sparsity-guided rewrite | (none — reads gate_mask) |
//! | A3 | P3 (holonomy) | RM-directed rewrite | `p1_p3_rm_boost` |
//! | A4 | P4 (sectors) | Sector-boundary rewrite | `p1_p4_boundary_boost` |
//! | A5 | P5 (packaging) | Packaging defect-guided | (none — computes defect) |
//! | A6 | P6 (audit) | Budget-gated suppress | `p1_p6_budget_threshold_frac` |
//!
//! A3 is the most important new cell: it creates **top-down influence** where
//! macro-level route mismatch directs micro-level rewrites toward macro consistency.

use super::config::PicaConfig;
use super::scores::P1Scores;
use crate::state::{AugmentedState, DynamicsConfig};
// NOTE: A3, A4, A5 consume the active partition (produced by P4-row lens cells).
// The partition may be spectral (A15), RM-quantile (A14), packaging (A16), or EP-flow (A17).

/// A1: P1<-P1 — History-guided row selection.
/// Avoid re-perturbing recently rewritten rows (let changes settle).
pub fn p1_from_p1(state: &AugmentedState, pica: &PicaConfig) -> P1Scores {
    let n = state.effective_kernel.n;
    let mut weights = vec![1.0; n];

    if let Some(last_row) = state.pica_state.last_p1_row {
        let steps_ago = state.step.saturating_sub(state.pica_state.last_p1_step);
        if steps_ago < pica.p1_p1_cooldown {
            weights[last_row] *= 0.1; // Suppress recently-rewritten row
        }
    }

    P1Scores {
        row_weights: weights,
        direction: None,
    }
}

/// A2: P1<-P2 — Sparsity-guided rewrite.
/// Rows with many gated (deleted) edges need redistribution — they're becoming degenerate.
pub fn p1_from_p2(state: &AugmentedState, _pat: &PicaConfig) -> P1Scores {
    let n = state.effective_kernel.n;
    let mut weights = vec![1.0; n];

    for i in 0..n {
        let gated_count = state.gate_mask[i].iter().filter(|&&m| !m).count();
        let gated_frac = gated_count as f64 / n as f64;
        weights[i] *= 1.0 + gated_frac; // More gated edges → higher rewrite priority
    }

    P1Scores {
        row_weights: weights,
        direction: None,
    }
}

/// A3: P1<-P3 — Route-mismatch-directed rewrite (top-down influence).
/// Rows in high-RM clusters contribute most to coarse-graining failure.
/// Perturb those rows toward macro-consistent distributions.
pub fn p1_from_p3(state: &AugmentedState, config: &DynamicsConfig) -> P1Scores {
    let n = state.effective_kernel.n;
    let pica = &config.pica;
    let mut weights = vec![1.0; n];
    let mut direction: Option<Vec<Vec<f64>>> = None;

    if let Some(ref cluster_rm) = state.pica_state.cluster_rm {
        if let Some(ref partition) = state.pica_state.spectral_partition {
            // Weight rows by their cluster's RM
            for i in 0..n {
                let ci = partition[i];
                if ci < cluster_rm.len() {
                    weights[i] *= 1.0 + pica.p1_p3_rm_boost * cluster_rm[ci];
                }
            }

            // Direction: compute macro-consistent target for each row.
            // For row i in cluster c, the "ideal" row is one that maps exactly
            // to macro_k[c] when projected through the partition.
            let n_clusters = cluster_rm.len();
            let mut cluster_sizes = vec![0usize; n_clusters];
            for &c in partition.iter() {
                if c < n_clusters {
                    cluster_sizes[c] += 1;
                }
            }

            // Build ONE-STEP macro kernel from current effective kernel.
            // RM weighting still comes from P3's multi-scale machinery, but the
            // directional rewrite target should live on the same one-step timescale
            // as the micro row rewrite to avoid forcing K toward K^tau.
            let mut macro_k = vec![vec![0.0; n_clusters]; n_clusters];
            for i_row in 0..n {
                let ci = partition[i_row];
                if ci >= n_clusters {
                    continue;
                }
                for j_col in 0..n {
                    let cj = partition[j_col];
                    if cj >= n_clusters {
                        continue;
                    }
                    macro_k[ci][cj] += state.effective_kernel.kernel[i_row][j_col];
                }
            }
            for c in 0..n_clusters {
                let row_sum: f64 = macro_k[c].iter().sum();
                if row_sum > 0.0 {
                    for j in 0..n_clusters {
                        macro_k[c][j] /= row_sum;
                    }
                }
            }

            // For each row i in cluster c, target = macro_k[c][cj] * (1/|cj|) for each micro j in cj
            let mut dir = vec![vec![0.0; n]; n];
            for i_row in 0..n {
                let ci = partition[i_row];
                if ci >= n_clusters {
                    continue;
                }
                for j_col in 0..n {
                    let cj = partition[j_col];
                    if cj >= n_clusters || cluster_sizes[cj] == 0 {
                        continue;
                    }
                    dir[i_row][j_col] = macro_k[ci][cj] / cluster_sizes[cj] as f64;
                }
                // Normalize
                let row_sum: f64 = dir[i_row].iter().sum();
                if row_sum > 0.0 {
                    for j in 0..n {
                        dir[i_row][j] /= row_sum;
                    }
                }
            }
            direction = Some(dir);
        }
    }

    P1Scores {
        row_weights: weights,
        direction,
    }
}

/// A4: P1<-P4 — Sector-boundary rewrite.
/// States near cluster boundaries (with high inter-cluster edge weight) get perturbed more.
pub fn p1_from_p4(state: &AugmentedState, pica: &PicaConfig) -> P1Scores {
    let n = state.effective_kernel.n;
    let mut weights = vec![1.0; n];

    if let Some(ref partition) = state.pica_state.spectral_partition {
        for i in 0..n {
            let ci = partition[i];
            // Boundary score: fraction of outgoing weight going to other clusters
            let mut cross_weight = 0.0;
            let mut total_weight = 0.0;
            for j in 0..n {
                if i == j {
                    continue;
                }
                let w = state.effective_kernel.kernel[i][j];
                total_weight += w;
                if partition[j] != ci {
                    cross_weight += w;
                }
            }
            if total_weight > 0.0 {
                let boundary_score = cross_weight / total_weight;
                weights[i] *= 1.0 + pica.p1_p4_boundary_boost * boundary_score;
            }
        }
    }

    P1Scores {
        row_weights: weights,
        direction: None,
    }
}

/// A5: P1<-P5 — Packaging-guided rewrite.
/// States contributing to high packaging defect (not converged) get perturbed.
/// Uses idempotence defect of the packaging endomap as a proxy.
pub fn p1_from_p5(state: &AugmentedState, config: &DynamicsConfig) -> P1Scores {
    let n = state.effective_kernel.n;
    let mut weights = vec![1.0; n];

    // Use active packaging if available, otherwise fall back to spectral partition
    let partition_ref = state
        .pica_state
        .active_packaging
        .as_ref()
        .or(state.pica_state.spectral_partition.as_ref());
    if let Some(partition) = partition_ref {
        let n_clusters = partition.iter().copied().max().unwrap_or(0) + 1;
        if n_clusters < 2 {
            return P1Scores {
                row_weights: weights,
                direction: None,
            };
        }

        // Compute per-row packaging defect: how much does E(E(dist)) differ from E(dist)?
        // Approximate: for each row i, the "packaging" maps i to its cluster center.
        // The defect is the distance between i's row distribution projected twice vs once.
        let gap = state.effective_kernel.spectral_gap();
        let tau = state
            .pica_state
            .active_tau
            .unwrap_or_else(|| crate::observe::adaptive_tau(gap, config.tau_alpha));
        let ktau = six_primitives_core::helpers::matrix_power(&state.effective_kernel, tau);

        let mut cluster_sizes = vec![0usize; n_clusters];
        for &c in partition {
            if c < n_clusters {
                cluster_sizes[c] += 1;
            }
        }

        // Project each row through the lens, then back, then through again
        for i in 0..n {
            let _ci = partition[i];
            // First pass: project row i to macro
            let mut macro_dist = vec![0.0; n_clusters];
            for j in 0..n {
                let cj = partition[j];
                if cj < n_clusters {
                    macro_dist[cj] += ktau.kernel[i][j];
                }
            }
            // Lift back to micro (uniform within clusters)
            let mut lifted = vec![0.0; n];
            for j in 0..n {
                let cj = partition[j];
                if cj < n_clusters && cluster_sizes[cj] > 0 {
                    lifted[j] = macro_dist[cj] / cluster_sizes[cj] as f64;
                }
            }
            // Second pass: evolve lifted by K^tau, project to macro again
            let mut evolved = vec![0.0; n];
            for j in 0..n {
                for k in 0..n {
                    evolved[k] += lifted[j] * ktau.kernel[j][k];
                }
            }
            let mut macro_dist2 = vec![0.0; n_clusters];
            for j in 0..n {
                let cj = partition[j];
                if cj < n_clusters {
                    macro_dist2[cj] += evolved[j];
                }
            }
            // Defect = L1 distance between macro_dist and macro_dist2
            let mut defect = 0.0;
            for c in 0..n_clusters {
                defect += (macro_dist[c] - macro_dist2[c]).abs();
            }
            weights[i] *= 1.0 + defect;
        }
    }

    P1Scores {
        row_weights: weights,
        direction: None,
    }
}

/// A6: P1<-P6 — Budget-aware row targeting.
/// When budget is low, suppress high-EP rows (expensive to modify) and prefer
/// low-EP rows (cheaper modifications). When budget is high, stay neutral.
/// This produces NON-UNIFORM weights, so proportional sampling is affected.
pub fn p1_from_p6(state: &AugmentedState, config: &DynamicsConfig) -> P1Scores {
    let n = state.effective_kernel.n;
    let pica = &config.pica;
    let mut weights = vec![1.0; n];

    let cap = if config.budget_cap > 0.0 {
        config.budget_cap
    } else {
        config.budget_init
    };
    let threshold = cap * pica.p1_p6_budget_threshold_frac;

    if threshold > 0.0 && state.budget < threshold {
        let kernel = &state.effective_kernel;
        let pi = kernel.stationary(10000, 1e-12);

        // Per-row EP contribution: how much entropy each row produces
        let mut row_ep = vec![0.0f64; n];
        for i in 0..n {
            for j in 0..n {
                if i == j {
                    continue;
                }
                let kij = kernel.kernel[i][j];
                let kji = kernel.kernel[j][i];
                if kij > 1e-15 && kji > 1e-15 {
                    row_ep[i] += pi[i] * kij * (kij / kji).ln();
                } else if kij > 1e-15 && kji <= 1e-15 {
                    row_ep[i] += pi[i] * kij * 30.0;
                }
            }
            row_ep[i] = row_ep[i].abs();
        }

        let max_ep = row_ep.iter().cloned().fold(0.0f64, f64::max);
        if max_ep > 1e-15 {
            // Suppression strength increases as budget decreases
            let suppression = (1.0 - state.budget / threshold).clamp(0.0, 1.0);
            for i in 0..n {
                // High-EP rows get suppressed when budget is low
                let ep_frac = row_ep[i] / max_ep; // 0..1
                let factor = 1.0 - suppression * 0.9 * ep_frac;
                weights[i] *= factor;
            }
        }
    }

    P1Scores {
        row_weights: weights,
        direction: None,
    }
}
