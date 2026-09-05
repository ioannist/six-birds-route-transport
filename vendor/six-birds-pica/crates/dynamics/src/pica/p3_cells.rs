//! # P3 row cells: modulations that adjust mixture weights + adaptive tau.
//!
//! ## P3 row overview (4 action cells)
//!
//! P3 (holonomy) in its action role controls the **mixture weights** — the
//! probabilities with which P1-P6 are chosen each step — and the **adaptive tau**
//! (time-scale for coarse-graining evaluation).
//!
//! | Cell | Informant | Output | Description |
//! |------|-----------|--------|-------------|
//! | A13  | P6 (audit)    | P3Scores | Frob-modulated explore/consolidate mixer |
//! | A18  | P3 (holonomy) | writes active_tau + P3Scores::identity() | Multi-scale RM → tau adjustment |
//! | A19  | P4 (sectors)  | P3Scores | Per-sector RM → sector-dependent mixing |
//! | A20  | P5 (packaging)| P3Scores | Packaging quality → mixing bias |
//!
//! P3←P1 and P3←P2 are **Implicit** (Group I): when P1/P2 modify K, RM changes
//! automatically on the next refresh. P3←P3(self-scale) is **Trivial** (T1).
//!
//! A13 was MIGRATED from `protocol.rs::audit_mix` with identical behavior.

use super::config::PicaConfig;
use super::scores::P3Scores;
use super::PicaState;
use crate::state::{AugmentedState, DynamicsConfig};

/// A13: P3<-P6 — Frob-modulated mixture weights.
/// When macro structure is boring (low frob), boost exploration (P1, P2).
/// When structure is interesting (high frob), boost consolidation (traj, P5).
/// MIGRATED from protocol.rs::audit_mix.
pub fn p3_from_p6(state: &AugmentedState, pica: &PicaConfig) -> P3Scores {
    let frob = state.pica_state.level1_frob;
    let f = (frob / pica.p3_p6_frob_scale).clamp(0.0, 1.0);
    let boring = 1.0 - f;
    let interesting = f;

    let strength = pica.p3_p6_mixer_strength;

    // Indices: [0]=traj, [1]=P1, [2]=P2, [3]=P4, [4]=P5, [5]=P6
    P3Scores {
        weight_multipliers: [
            1.0 + strength * interesting, // traj: consolidate when interesting
            1.0 + strength * boring,      // P1: explore when boring
            1.0 + strength * boring,      // P2: explore when boring
            1.0,                          // P4: unchanged
            1.0 + strength * interesting, // P5: consolidate when interesting
            1.0,                          // P6: unchanged
        ],
    }
}

/// A18: P3←P3 — Multi-scale RM → adaptive tau.
///
/// Compute RM at τ, 2τ, 4τ. The trend tells us whether tau is appropriate:
/// - **Converging** (RM decreases with scale): tau is good → keep it
/// - **Diverging** (RM increases with scale): tau is too large → halve it
/// - **Stable** (RM roughly constant): tau is at the sweet spot
///
/// Writes `active_tau` to PicaState. All tau consumers should read from there.
/// Returns P3Scores::identity() since this cell doesn't modulate mixture weights.
pub fn p3_from_p3_tau(
    state: &mut PicaState,
    kernel: &six_primitives_core::substrate::MarkovKernel,
    config: &DynamicsConfig,
) {
    let partition = match &state.spectral_partition {
        Some(p) => p.clone(),
        None => return, // no partition yet, can't compute RM
    };

    let n = kernel.n;
    let n_clusters = partition.iter().copied().max().unwrap_or(0) + 1;
    if n_clusters < 2 {
        return;
    }

    // Base tau from spectral gap
    let gap = kernel.spectral_gap();
    let base_tau = crate::observe::adaptive_tau(gap, config.tau_alpha);

    // RM at τ, 2τ, 4τ
    let mut rm_values = [0.0f64; 3];
    for (idx, mult) in [1usize, 2, 4].iter().enumerate() {
        let t = (base_tau * mult).min(config.pica.p3_p3_tau_cap);
        let ktau = six_primitives_core::helpers::matrix_power(kernel, t);
        rm_values[idx] = compute_rm_for_partition(&ktau, &partition, n, n_clusters);
    }

    // Determine trend: converging, diverging, or stable
    let d1 = rm_values[1] - rm_values[0]; // change from τ to 2τ
    let d2 = rm_values[2] - rm_values[1]; // change from 2τ to 4τ

    let new_tau = if d1 > 0.05 && d2 > 0.05 {
        // Diverging: RM increasing with scale → tau too large, halve it
        (base_tau / 2).max(1)
    } else if d1 < -0.05 && d2 < -0.05 {
        // Converging: RM decreasing → tau could be larger, keep current (conservative)
        base_tau
    } else {
        // Stable: at the sweet spot
        base_tau
    };

    state.active_tau = Some(new_tau.min(config.pica.p3_p3_tau_cap));
}

/// A19: P3←P4 — Per-sector mixing weights.
///
/// Read per-sector RM from `cluster_rm`. If the walker's current sector has high RM,
/// boost P1/P2 (need more modification). If low RM, boost trajectory (let structure settle).
pub fn p3_from_p4(state: &AugmentedState, config: &DynamicsConfig) -> P3Scores {
    let partition = match &state.pica_state.spectral_partition {
        Some(p) => p,
        None => return P3Scores::identity(),
    };
    let cluster_rm = match &state.pica_state.cluster_rm {
        Some(rm) => rm,
        None => return P3Scores::identity(),
    };

    // Which sector is the walker currently in?
    let pos = state.position;
    if pos >= partition.len() {
        return P3Scores::identity();
    }
    let my_cluster = partition[pos];
    if my_cluster >= cluster_rm.len() {
        return P3Scores::identity();
    }

    let my_rm = cluster_rm[my_cluster];

    // Compute mean RM across clusters
    let n_clusters = cluster_rm.len();
    if n_clusters == 0 {
        return P3Scores::identity();
    }
    let mean_rm: f64 = cluster_rm.iter().sum::<f64>() / n_clusters as f64;

    // Relative RM: >1 means this sector is worse than average
    let rel = if mean_rm > 1e-15 {
        my_rm / mean_rm
    } else {
        1.0
    };
    let boost = config.pica.p3_p4_sector_boost;

    // rel > 1 → high RM → need more exploration
    // rel < 1 → low RM → structure is good, consolidate
    let explore_signal = ((rel - 1.0) * boost).clamp(-boost, boost);

    P3Scores {
        weight_multipliers: [
            1.0 - explore_signal * 0.3, // traj: less when exploring
            1.0 + explore_signal * 0.5, // P1: more when exploring
            1.0 + explore_signal * 0.5, // P2: more when exploring
            1.0,                        // P4: unchanged
            1.0 - explore_signal * 0.2, // P5: less when exploring
            1.0,                        // P6: unchanged
        ],
    }
}

/// A20: P3←P5 — Packaging-derived mixing bias.
///
/// Read per-package RM from `packaging_rm` (computed on `active_packaging`).
/// If the walker's current package has high RM, boost P1/P2 for modification.
/// If low RM, boost trajectory to let structure settle.
///
/// Unlike A19 (which reads spectral partition + cluster_rm), A20 reads the
/// packaging partition + packaging_rm, providing an independent signal.
pub fn p3_from_p5(state: &AugmentedState, config: &DynamicsConfig) -> P3Scores {
    let partition = match &state.pica_state.active_packaging {
        Some(p) => p,
        None => return P3Scores::identity(),
    };
    let package_rm = match &state.pica_state.packaging_rm {
        Some(rm) => rm,
        None => return P3Scores::identity(),
    };

    let pos = state.position;
    if pos >= partition.len() {
        return P3Scores::identity();
    }
    let my_package = partition[pos];
    if my_package >= package_rm.len() {
        return P3Scores::identity();
    }
    let my_rm = package_rm[my_package];

    let n_packages = package_rm.len();
    if n_packages == 0 {
        return P3Scores::identity();
    }
    let mean_rm: f64 = package_rm.iter().sum::<f64>() / n_packages as f64;
    let rel = if mean_rm > 1e-15 {
        my_rm / mean_rm
    } else {
        1.0
    };
    let boost = config.pica.p3_p4_sector_boost; // reuse same param

    let explore_signal = ((rel - 1.0) * boost).clamp(-boost, boost);

    P3Scores {
        weight_multipliers: [
            1.0 - explore_signal * 0.3,
            1.0 + explore_signal * 0.5,
            1.0 + explore_signal * 0.5,
            1.0,
            1.0 - explore_signal * 0.2,
            1.0,
        ],
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::pica::PicaState;
    use crate::state::AugmentedState;
    use six_primitives_core::substrate::MarkovKernel;

    fn make_test_state(n: usize, seed: u64) -> (AugmentedState, DynamicsConfig) {
        let kernel = MarkovKernel::random(n, seed);
        let mut pica_state = PicaState::new(n);
        // Give it a spectral partition
        let partition = crate::spectral::spectral_partition(&kernel, 4);
        let n_clusters = crate::spectral::n_clusters(&partition);
        pica_state.spectral_partition = Some(partition);
        // Give it cluster_rm
        pica_state.cluster_rm = Some(vec![0.1; n_clusters]);
        let state = AugmentedState {
            base_kernel: kernel.clone(),
            effective_kernel: kernel,
            gate_mask: vec![vec![true; n]; n],
            position: 0,
            budget: 10.0,
            step: 0,
            phase: 0,
            p1_accepted: 0,
            p1_rejected: 0,
            p2_accepted: 0,
            p2_rejected: 0,
            traj_steps: 0,
            p2_repairs: 0,
            p2_violations: 0,
            pica_state,
        };
        let config = DynamicsConfig::default_for(n, seed);
        (state, config)
    }

    #[test]
    fn test_p3_from_p3_tau_writes_active_tau() {
        let kernel = MarkovKernel::random(16, 42);
        let config = DynamicsConfig::default_for(16, 42);
        let partition = crate::spectral::spectral_partition(&kernel, 4);
        let mut pica_state = PicaState::new(16);
        pica_state.spectral_partition = Some(partition);
        assert!(pica_state.active_tau.is_none());
        p3_from_p3_tau(&mut pica_state, &kernel, &config);
        // A18 should have written active_tau
        assert!(pica_state.active_tau.is_some());
        let tau = pica_state.active_tau.unwrap();
        assert!(tau >= 1);
        assert!(tau <= config.pica.p3_p3_tau_cap);
    }

    #[test]
    fn test_p3_from_p3_tau_no_partition_noop() {
        let kernel = MarkovKernel::random(16, 42);
        let config = DynamicsConfig::default_for(16, 42);
        let mut pica_state = PicaState::new(16);
        // No partition → should be a no-op
        p3_from_p3_tau(&mut pica_state, &kernel, &config);
        assert!(pica_state.active_tau.is_none());
    }

    #[test]
    fn test_p3_from_p4_returns_valid_scores() {
        let (state, config) = make_test_state(16, 42);
        let scores = p3_from_p4(&state, &config);
        // All multipliers should be positive
        for &w in &scores.weight_multipliers {
            assert!(w > 0.0, "weight_multiplier must be positive, got {}", w);
        }
    }

    #[test]
    fn test_p3_from_p4_identity_without_partition() {
        let kernel = MarkovKernel::random(16, 42);
        let state = AugmentedState {
            base_kernel: kernel.clone(),
            effective_kernel: kernel,
            gate_mask: vec![vec![true; 16]; 16],
            position: 0,
            budget: 10.0,
            step: 0,
            phase: 0,
            p1_accepted: 0,
            p1_rejected: 0,
            p2_accepted: 0,
            p2_rejected: 0,
            traj_steps: 0,
            p2_repairs: 0,
            p2_violations: 0,
            pica_state: PicaState::new(16),
        };
        let config = DynamicsConfig::default_for(16, 42);
        let scores = p3_from_p4(&state, &config);
        // Without partition, should return identity
        for &w in &scores.weight_multipliers {
            assert!((w - 1.0).abs() < 1e-10);
        }
    }

    #[test]
    fn test_p3_from_p5_returns_valid_scores() {
        let (mut state, config) = make_test_state(16, 42);
        // A20 now reads active_packaging + packaging_rm (not spectral_partition + cluster_rm)
        let partition = state.pica_state.spectral_partition.as_ref().unwrap().clone();
        let n_clusters = crate::spectral::n_clusters(&partition);
        state.pica_state.active_packaging = Some(partition);
        state.pica_state.packaging_rm = Some(vec![0.1; n_clusters]);
        let scores = p3_from_p5(&state, &config);
        for &w in &scores.weight_multipliers {
            assert!(w > 0.0, "weight_multiplier must be positive, got {}", w);
        }
    }

    #[test]
    fn test_p3_from_p5_identity_without_packaging() {
        let (state, config) = make_test_state(16, 42);
        // No active_packaging → should return identity
        let scores = p3_from_p5(&state, &config);
        for &w in &scores.weight_multipliers {
            assert!(
                (w - 1.0).abs() < 1e-10,
                "should be identity without packaging"
            );
        }
    }

    #[test]
    fn test_p3_from_p4_high_rm_boosts_exploration() {
        let (mut state, config) = make_test_state(16, 42);
        let n_clusters = state.pica_state.cluster_rm.as_ref().unwrap().len();
        // Set cluster 0 RM very high, others low
        let mut rm = vec![0.01; n_clusters];
        rm[0] = 1.0; // much higher than mean
        state.pica_state.cluster_rm = Some(rm);
        // Place walker in cluster 0
        let part = state.pica_state.spectral_partition.as_ref().unwrap();
        let pos_in_c0 = (0..16).find(|&i| part[i] == 0).unwrap_or(0);
        state.position = pos_in_c0;

        let scores = p3_from_p4(&state, &config);
        // High RM → explore signal > 0 → P1 boost > 1.0
        assert!(
            scores.weight_multipliers[1] > 1.0,
            "P1 weight should be boosted for high RM sector, got {}",
            scores.weight_multipliers[1]
        );
    }
}

/// Helper: compute global RM for a partition (used by A18).
fn compute_rm_for_partition(
    ktau: &six_primitives_core::substrate::MarkovKernel,
    partition: &[usize],
    n: usize,
    n_clusters: usize,
) -> f64 {
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
