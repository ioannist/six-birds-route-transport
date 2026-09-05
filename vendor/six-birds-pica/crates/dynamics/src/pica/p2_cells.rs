//! # P2 row cells: modulations that change which edges P2 flips and at what cost.
//!
//! P2 (gate) flips O(n/8) edges per step — setting them to zero and renormalizing.
//! By default, edges are chosen uniformly at random. These 6 cells provide two
//! types of modulation:
//!
//! 1. **Edge weights** (`edge_weights`): bias which edges are selected for flipping.
//!    Higher weight = more likely to be targeted. Used by A7-A11.
//!
//! 2. **Cost multipliers** (`cost_multiplier`): change the budget cost of flipping
//!    specific edges. `0.0` = free, `1.0` = normal, `>1.0` = penalized. Used by A12.
//!
//! ## Why P2 has all 6 informants
//!
//! Edge gating is the primary mechanism for creating emergent structure. Every
//! informant helps target or constrain which edges to cut:
//! - **P1**: don't cut edges in rows that were just rewritten (let changes settle)
//! - **P2**: don't re-flip edges that were just flipped (cooldown)
//! - **P3**: cut edges that contribute to coarse-graining failure (RM-guided)
//! - **P4**: cut inter-cluster edges to sharpen boundaries (spectral-guided, essential)
//! - **P5**: cut edges between different packages (package-boundary)
//! - **P6**: classify flips as repairs or violations, penalize violations (SBRC)
//!
//! ## Cell inventory
//!
//! | Cell | Informant | Role | Key param | Status |
//! |------|-----------|------|-----------|--------|
//! | A7 | P1 (rewrite) | Protect rewritten rows | `p2_p1_protect_steps` | NEW |
//! | A8 | P2 (self) | Flip cooldown | `p2_p2_cooldown` | NEW |
//! | A9 | P3 (holonomy) | RM-guided gating | `p2_p3_rm_boost` | NEW |
//! | A10 | P4 (sectors) | Spectral-guided gating | `p2_p4_inter_boost` | MIGRATED |
//! | A11 | P5 (packaging) | Package-boundary gating | `p2_p5_boundary_boost` | NEW |
//! | A12 | P6 (audit) | SBRC penalty | `p2_p6_sbrc_strength` | MIGRATED |
//!
//! A10 is the **essential** cell — without spectral-guided P2 gating, all macro
//! kernels collapse to rank-1. A10 was originally inline in mixture.rs (EXP-080)
//! and migrated to PICA with identical behavior.
//!
//! A12 (SBRC) was originally the `coupling_signed` flag in mixture.rs (EXP-095).
//! It classifies each flip as a "repair" (strengthens cluster boundaries → free)
//! or "violation" (weakens boundaries → penalized via cost_multiplier).

use super::config::PicaConfig;
use super::scores::P2Scores;
use crate::state::{AugmentedState, DynamicsConfig};
// NOTE: A9, A10, A11 consume the active partition (produced by P4-row lens cells).
// The partition may be spectral (A15), RM-quantile (A14), packaging (A16), or EP-flow (A17).

/// A7: P2<-P1 — Protect recently-rewritten edges.
/// After P1 rewrites a row, protect that row's edges from gating (let the rewrite settle).
pub fn p2_from_p1(state: &AugmentedState, pica: &PicaConfig) -> P2Scores {
    let n = state.effective_kernel.n;
    let nn = n * n;
    let mut edge_weights = vec![1.0; nn];
    let cost_multiplier = vec![1.0; nn];

    // Protect all recently rewritten rows within the cooldown window.
    // Fall back to last_p1_row for backward compatibility if history is empty.
    let mut protected_rows: Vec<usize> = Vec::new();
    if !state.pica_state.recent_p1_rows.is_empty() {
        for &(row, step_written) in &state.pica_state.recent_p1_rows {
            if row < n && state.step.saturating_sub(step_written) < pica.p2_p1_protect_steps {
                protected_rows.push(row);
            }
        }
    } else if let Some(last_row) = state.pica_state.last_p1_row {
        let steps_ago = state.step.saturating_sub(state.pica_state.last_p1_step);
        if steps_ago < pica.p2_p1_protect_steps {
            protected_rows.push(last_row);
        }
    }
    for row in protected_rows {
        for j in 0..n {
            edge_weights[row * n + j] *= 0.1;
            edge_weights[j * n + row] *= 0.1;
        }
    }

    P2Scores {
        edge_weights,
        cost_multiplier,
    }
}

/// A8: P2<-P2 — Flip-history cooldown.
/// Don't re-flip edges that were recently flipped (let changes propagate).
pub fn p2_from_p2(state: &AugmentedState, pica: &PicaConfig) -> P2Scores {
    let n = state.effective_kernel.n;
    let nn = n * n;
    let mut edge_weights = vec![1.0; nn];
    let cost_multiplier = vec![1.0; nn];

    let current_step = state.step;
    for i in 0..n {
        for j in 0..n {
            if i == j {
                continue;
            }
            let last = state.pica_state.last_flip_step[i][j];
            if last > 0 && current_step.saturating_sub(last) < pica.p2_p2_cooldown {
                edge_weights[i * n + j] *= 0.1; // Suppress recently-flipped edges
            }
        }
    }

    P2Scores {
        edge_weights,
        cost_multiplier,
    }
}

/// A9: P2<-P3 — RM-guided edge gating.
/// Edges connecting high-RM clusters contribute to coarse-graining failure → gate them.
pub fn p2_from_p3(state: &AugmentedState, config: &DynamicsConfig) -> P2Scores {
    let n = state.effective_kernel.n;
    let nn = n * n;
    let pica = &config.pica;
    let mut edge_weights = vec![1.0; nn];
    let cost_multiplier = vec![1.0; nn];

    if let (Some(ref cluster_rm), Some(ref partition)) = (
        &state.pica_state.cluster_rm,
        &state.pica_state.spectral_partition,
    ) {
        for i in 0..n {
            for j in 0..n {
                if i == j {
                    continue;
                }
                let ci = partition[i];
                let cj = partition[j];
                // Edge between different clusters: weight by max RM of the two clusters
                if ci != cj {
                    let rm_i = if ci < cluster_rm.len() {
                        cluster_rm[ci]
                    } else {
                        0.0
                    };
                    let rm_j = if cj < cluster_rm.len() {
                        cluster_rm[cj]
                    } else {
                        0.0
                    };
                    let rm_max = rm_i.max(rm_j);
                    // Currently ON? High RM → flip it OFF (gate it)
                    if state.gate_mask[i][j] {
                        edge_weights[i * n + j] *= 1.0 + pica.p2_p3_rm_boost * rm_max;
                    }
                }
            }
        }
    }

    P2Scores {
        edge_weights,
        cost_multiplier,
    }
}

/// A10: P2<-P4 — Spectral-guided gating.
/// Inter-cluster edges get boosted for flip-OFF; intra-cluster edges get suppressed.
/// MIGRATED from the inline code in mixture.rs::p2_step.
pub fn p2_from_p4(state: &AugmentedState, pica: &PicaConfig) -> P2Scores {
    let n = state.effective_kernel.n;
    let nn = n * n;
    let mut edge_weights = vec![1.0; nn];
    let cost_multiplier = vec![1.0; nn];

    if let Some(ref partition) = state.pica_state.spectral_partition {
        for i in 0..n {
            for j in 0..n {
                if i == j {
                    continue;
                }
                let is_inter = partition[i] != partition[j];
                if is_inter {
                    // Inter-cluster: boost for flipping OFF
                    if state.gate_mask[i][j] {
                        // Currently ON → boost to flip OFF
                        edge_weights[i * n + j] *= pica.p2_p4_inter_boost;
                    } else {
                        // Already OFF → suppress (don't flip back ON)
                        edge_weights[i * n + j] *= 1.0 / pica.p2_p4_inter_boost;
                    }
                } else {
                    // Intra-cluster: suppress flipping (keep structure)
                    edge_weights[i * n + j] *= 1.0 / pica.p2_p4_inter_boost;
                }
            }
        }
    }

    P2Scores {
        edge_weights,
        cost_multiplier,
    }
}

/// A11: P2<-P5 — Package-boundary gating with connectivity guard.
/// Cross-package edges get boosted for flip-OFF, but ONLY if the source cluster
/// retains at least 50% of its intra-cluster edges (prevents absorbing states).
/// Same-package OFF edges get a mild boost toward flip-ON (repair connectivity).
pub fn p2_from_p5(state: &AugmentedState, config: &DynamicsConfig) -> P2Scores {
    let n = state.effective_kernel.n;
    let nn = n * n;
    let pica = &config.pica;
    let mut edge_weights = vec![1.0; nn];
    let cost_multiplier = vec![1.0; nn];

    // Use active packaging if available, otherwise fall back to spectral partition
    let partition_ref = state
        .pica_state
        .active_packaging
        .as_ref()
        .or(state.pica_state.spectral_partition.as_ref());
    if let Some(partition) = partition_ref {
        let n_clusters = partition.iter().copied().max().unwrap_or(0) + 1;

        // Compute intra-cluster connectivity and per-state support per cluster.
        let mut intra_on = vec![0usize; n_clusters];
        let mut intra_total = vec![0usize; n_clusters];
        let mut min_out_on = vec![usize::MAX; n_clusters];
        let mut min_in_on = vec![usize::MAX; n_clusters];
        let mut cluster_size = vec![0usize; n_clusters];
        for i in 0..n {
            let ci = partition[i];
            if ci >= n_clusters {
                continue;
            }
            cluster_size[ci] += 1;
            let mut out_on_i = 0usize;
            let mut in_on_i = 0usize;
            let mut out_total_i = 0usize;
            for j in 0..n {
                if i == j {
                    continue;
                }
                if partition[j] == ci {
                    out_total_i += 1;
                    intra_total[ci] += 1;
                    if state.gate_mask[i][j] {
                        intra_on[ci] += 1;
                        out_on_i += 1;
                    }
                    if state.gate_mask[j][i] {
                        in_on_i += 1;
                    }
                }
            }
            if out_total_i > 0 {
                min_out_on[ci] = min_out_on[ci].min(out_on_i);
                min_in_on[ci] = min_in_on[ci].min(in_on_i);
            } else {
                min_out_on[ci] = min_out_on[ci].min(0);
                min_in_on[ci] = min_in_on[ci].min(0);
            }
        }

        let mut safe_cluster = vec![false; n_clusters];
        for c in 0..n_clusters {
            let connectivity = if intra_total[c] > 0 {
                intra_on[c] as f64 / intra_total[c] as f64
            } else {
                1.0
            };
            // Guard requires:
            // 1) global cluster density above threshold
            // 2) every member keeps at least one intra outgoing and incoming ON edge
            // 3) cluster has at least 2 states
            let per_state_ok = min_out_on[c] > 0 && min_in_on[c] > 0;
            safe_cluster[c] = connectivity > 0.5 && per_state_ok && cluster_size[c] >= 2;
        }

        for i in 0..n {
            let ci = partition[i];
            if ci >= n_clusters {
                continue;
            }
            // Only gate cross-package edges if source cluster passes connectivity guard.
            let safe_to_gate = safe_cluster[ci];

            for j in 0..n {
                if i == j {
                    continue;
                }
                let same_package = partition[j] == ci;
                if !same_package {
                    // Cross-package edge
                    if state.gate_mask[i][j] && safe_to_gate {
                        // Currently ON, cluster is well-connected → boost to flip OFF
                        edge_weights[i * n + j] *= pica.p2_p5_boundary_boost;
                    }
                } else {
                    // Same-package edge that is OFF → mild boost to flip ON (repair)
                    if !state.gate_mask[i][j] {
                        edge_weights[i * n + j] *= 1.0 + (pica.p2_p5_boundary_boost - 1.0) * 0.5;
                    }
                }
            }
        }
    }

    P2Scores {
        edge_weights,
        cost_multiplier,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::pica::PicaConfig;
    use crate::state::DynamicsConfig;
    use rand::SeedableRng;
    use rand_chacha::ChaCha8Rng;

    #[test]
    fn test_a7_protects_multiple_recent_rows() {
        let config = DynamicsConfig::default_for(6, 7);
        let mut rng = ChaCha8Rng::seed_from_u64(19);
        let mut state = AugmentedState::new(&config, &mut rng);
        state.step = 103;
        state.pica_state.recent_p1_rows = vec![(1, 100), (3, 95), (5, 80)];

        let mut pica = PicaConfig::none();
        pica.p2_p1_protect_steps = 10;
        let scores = p2_from_p1(&state, &pica);
        let n = config.n;

        assert!(scores.edge_weights[1 * n + 4] <= 0.1);
        assert!(scores.edge_weights[4 * n + 1] <= 0.1);
        assert!(scores.edge_weights[3 * n + 0] <= 0.1);
        assert!(scores.edge_weights[0 * n + 3] <= 0.1);
        // Row 5 is outside protect window.
        assert!((scores.edge_weights[5 * n + 4] - 1.0).abs() < 1e-12);
    }

    #[test]
    fn test_a11_guard_blocks_cross_gating_when_state_disconnected() {
        let config = DynamicsConfig::default_for(4, 11);
        let mut rng = ChaCha8Rng::seed_from_u64(23);
        let mut state = AugmentedState::new(&config, &mut rng);
        // Cluster assignment: {0,1,2} and {3}.
        state.pica_state.active_packaging = Some(vec![0, 0, 0, 1]);

        // Keep >50% intra edges ON in cluster 0, but disconnect state 2's outgoing intra edges.
        // Intra edges in cluster 0: 6 directed edges total.
        // ON edges: 0->1,0->2,1->0,1->2 (4/6 > 0.5), while 2->0 and 2->1 are OFF.
        state.gate_mask[2][0] = false;
        state.gate_mask[2][1] = false;

        let mut cfg = DynamicsConfig::default_for(4, 11);
        cfg.pica.p2_p5_boundary_boost = 2.0;
        let scores = p2_from_p5(&state, &cfg);
        let n = cfg.n;

        // Cross-package edge from cluster 0 should NOT be boosted due to per-state guard failure.
        assert!((scores.edge_weights[0 * n + 3] - 1.0).abs() < 1e-12);
    }
}

/// A12: P2<-P6 — SBRC (Signed Boundary Repair Coupling) penalty.
/// Classifies flips as repairs (free) or violations (penalized).
/// MIGRATED from inline code in mixture.rs::p2_step.
pub fn p2_from_p6(state: &AugmentedState, config: &DynamicsConfig) -> P2Scores {
    let n = state.effective_kernel.n;
    let nn = n * n;
    let pica = &config.pica;
    let edge_weights = vec![1.0; nn]; // No targeting, just cost modification
    let mut cost_multiplier = vec![1.0; nn];

    if let Some(ref l1_group) = state.pica_state.level1_group {
        let frob = state.pica_state.level1_frob;
        for i in 0..n {
            for j in 0..n {
                if i == j {
                    continue;
                }
                let same_group = l1_group[i] == l1_group[j];
                let currently_on = state.gate_mask[i][j];
                // Violation: turning OFF within-group OR turning ON cross-group
                let is_violation_if_flipped =
                    (same_group && currently_on) || (!same_group && !currently_on);
                if is_violation_if_flipped {
                    cost_multiplier[i * n + j] = 1.0 + pica.p2_p6_sbrc_strength * frob;
                } else {
                    // Repair: free
                    cost_multiplier[i * n + j] = 0.0;
                }
            }
        }
    }

    P2Scores {
        edge_weights,
        cost_multiplier,
    }
}
