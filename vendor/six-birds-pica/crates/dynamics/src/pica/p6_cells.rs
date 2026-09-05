//! # P6 row cells: budget modulation controlled by PICA.
//!
//! P6 (audit/drive) controls the budget ledger — how much "energy" is available
//! for kernel modifications (P1 perturbation, P2 gating). Before PICA promotion,
//! the budget rate and cap were fixed parameters. Now two P6-row cells modulate
//! them based on the system's thermodynamic state.
//!
//! ## Why P6 has 2 informants (not 6)
//!
//! - P6←P1, P6←P2 are **Implicit** (Group I): when P1/P2 modify K, the audit
//!   metrics change automatically on the next refresh.
//! - P6←P3 is **Trivial** (T3): RM IS an audit metric — circular to parameterize
//!   the audit by an audit metric.
//! - P6←P5 is undefined (no clear non-circular action).
//! - P6←P4 (A24) and P6←P6 (A25) are the 2 action cells.
//!
//! ## Output type: P6Scores
//!
//! Both cells produce `P6Scores { budget_rate_mult, budget_cap_mult }`.
//! Combined multiplicatively when both are enabled. Applied to the per-step
//! `drive::replenish()` call: `replenish(budget, rate * rate_mult, cap * cap_mult)`.

use super::scores::P6Scores;
use crate::state::{AugmentedState, DynamicsConfig};

/// A24: P6←P4 — Sector-specific budget rate multiplier.
///
/// Compute mean EP per sector from the active partition. If max sector EP is >2x
/// the mean (one sector is thermodynamically dominant), boost replenishment rate
/// to allow more modifications in that regime. If all sectors have similar EP,
/// rate_mult = 1.0 (no change).
pub fn p6_from_p4(state: &AugmentedState, config: &DynamicsConfig) -> P6Scores {
    let partition = match &state.pica_state.spectral_partition {
        Some(p) => p,
        None => return P6Scores::identity(),
    };

    let kernel = &state.effective_kernel;
    let n = kernel.n;
    let n_clusters = partition.iter().copied().max().unwrap_or(0) + 1;
    if n_clusters < 2 {
        return P6Scores::identity();
    }

    let pi = kernel.stationary(10000, 1e-12);

    // Per-sector EP (matching core path_reversal_asymmetry logic)
    let mut sector_ep = vec![0.0f64; n_clusters];
    for i in 0..n {
        let ci = partition[i];
        if ci >= n_clusters {
            continue;
        }
        for j in 0..n {
            if i == j {
                continue;
            }
            let kij = kernel.kernel[i][j];
            let kji = kernel.kernel[j][i];
            if kij > 1e-15 && kji > 1e-15 {
                sector_ep[ci] += pi[i] * kij * (kij / kji).ln();
            } else if kij > 1e-15 && kji <= 1e-15 {
                // Irreversible edge: large EP contribution (cap at ln(1e13) ≈ 30)
                sector_ep[ci] += pi[i] * kij * 30.0;
            }
        }
    }

    let mean_ep: f64 = sector_ep.iter().sum::<f64>() / n_clusters as f64;
    let max_ep: f64 = sector_ep.iter().cloned().fold(0.0f64, f64::max);

    // If max sector EP is significantly above mean, boost rate
    let ep_boost = config.pica.p6_p4_ep_boost;
    let rate_mult = if mean_ep > 1e-15 && max_ep > ep_boost * mean_ep {
        // Scale: more imbalance → higher rate multiplier
        (max_ep / mean_ep / ep_boost).min(2.0)
    } else {
        1.0
    };

    P6Scores {
        budget_rate_mult: rate_mult,
        budget_cap_mult: 1.0, // A24 doesn't modify cap
    }
}

/// A25: P6←P6 — EP retention feedback cap.
///
/// Compute EP retention ratio: macro_EP / micro_EP(K^τ) ∈ [0, 1].
/// When EP retention is low (macro EP << K^τ EP), the coarse-graining is losing
/// too much thermodynamic information → tighten budget cap to force more
/// conservative modifications. High retention → cap_mult = 1.0 (no constraint).
pub fn p6_from_p6(state: &AugmentedState, config: &DynamicsConfig) -> P6Scores {
    let kernel = &state.effective_kernel;

    // Need L1 audit data for DPI check
    let level1_frob = state.pica_state.level1_frob;
    if level1_frob < 1e-15 {
        return P6Scores::identity(); // No structure yet, no DPI constraint
    }

    // Build macro kernel and compare EP on the same time scale
    if let Some(ref partition) = state.pica_state.spectral_partition {
        let n_clusters = partition.iter().copied().max().unwrap_or(0) + 1;
        if n_clusters < 2 {
            return P6Scores::identity();
        }

        let gap = kernel.spectral_gap();
        let tau = state
            .pica_state
            .active_tau
            .unwrap_or_else(|| crate::observe::adaptive_tau(gap, config.tau_alpha));
        let ktau = six_primitives_core::helpers::matrix_power(kernel, tau);

        // Micro EP of K^tau (one macro step = tau micro steps)
        let pi = kernel.stationary(10000, 1e-12);
        let micro_sigma_tau =
            six_primitives_core::substrate::path_reversal_asymmetry(&ktau, &pi, 10);

        // Macro EP (one step of the coarse-grained kernel)
        let macro_k = six_primitives_core::helpers::build_macro_from_ktau(
            &ktau.kernel,
            partition,
            n_clusters,
        );
        let pi_m = macro_k.stationary(10000, 1e-12);
        let macro_sigma =
            six_primitives_core::substrate::path_reversal_asymmetry(&macro_k, &pi_m, 10);

        // EP retention ratio: how much micro EP survives coarse-graining.
        // Both measured at the same time scale (one macro step = tau micro steps).
        // DPI guarantees ratio ≤ 1. Low ratio means the CG is losing EP information
        // → the dynamics are producing poorly-structured kernels → tighten budget.
        let ep_retention = if micro_sigma_tau > 1e-15 {
            macro_sigma / micro_sigma_tau
        } else {
            1.0 // No micro EP → no information to lose
        };

        let threshold = config.pica.p6_p6_dpi_cap_scale;
        let cap_mult = if ep_retention < threshold {
            // Low EP retention: CG losing too much information → tighten budget.
            // More loss → tighter cap. At retention=0, cap_mult = 0.3 (minimum).
            (0.3 + 0.7 * (ep_retention / threshold)).clamp(0.3, 1.0)
        } else {
            1.0
        };

        P6Scores {
            budget_rate_mult: 1.0, // A25 doesn't modify rate
            budget_cap_mult: cap_mult,
        }
    } else {
        P6Scores::identity()
    }
}

/// Compute combined P6 modulations from all enabled P6-row cells.
pub fn compute_p6_modulations(state: &AugmentedState, config: &DynamicsConfig) -> P6Scores {
    let pica = &config.pica;
    if !pica.any_p6_modulation() {
        return P6Scores::identity();
    }

    let mut all_scores: Vec<P6Scores> = Vec::new();

    if pica.enabled[5][3] {
        all_scores.push(p6_from_p4(state, config));
    }
    if pica.enabled[5][5] {
        all_scores.push(p6_from_p6(state, config));
    }

    if all_scores.is_empty() {
        return P6Scores::identity();
    }

    let refs: Vec<&P6Scores> = all_scores.iter().collect();
    super::scores::combine_p6(&refs)
}

#[cfg(test)]
mod tests {
    use super::*;
    use six_primitives_core::substrate::MarkovKernel;

    fn make_state_with_partition(
        n: usize,
        seed: u64,
    ) -> (crate::state::AugmentedState, DynamicsConfig) {
        use crate::pica::PicaState;
        use crate::state::AugmentedState;
        let kernel = MarkovKernel::random(n, seed);
        let partition = crate::spectral::spectral_partition(&kernel, 4);
        let mut pica_state = PicaState::new(n);
        pica_state.spectral_partition = Some(partition);
        pica_state.level1_frob = 0.5; // non-trivial structure
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
        let mut config = DynamicsConfig::default_for(n, seed);
        config.pica.enabled[5][3] = true; // enable A24
        config.pica.enabled[5][5] = true; // enable A25
        (state, config)
    }

    #[test]
    fn test_p6_identity_when_no_partition() {
        // With no partition, both cells should return identity
        let kernel = MarkovKernel::random(16, 42);
        use crate::pica::PicaState;
        use crate::state::AugmentedState;
        let state = AugmentedState {
            base_kernel: kernel.clone(),
            effective_kernel: kernel.clone(),
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
        let scores = compute_p6_modulations(&state, &config);
        assert!((scores.budget_rate_mult - 1.0).abs() < 1e-10);
        assert!((scores.budget_cap_mult - 1.0).abs() < 1e-10);
    }

    #[test]
    fn test_p6_from_p4_returns_valid_rate_mult() {
        let (state, config) = make_state_with_partition(16, 42);
        let scores = p6_from_p4(&state, &config);
        // rate_mult should be ≥ 1.0 (identity or boost)
        assert!(
            scores.budget_rate_mult >= 1.0 - 1e-10,
            "rate_mult should be >= 1.0, got {}",
            scores.budget_rate_mult
        );
        assert!(
            scores.budget_rate_mult <= 2.0 + 1e-10,
            "rate_mult should be <= 2.0, got {}",
            scores.budget_rate_mult
        );
        // cap_mult should be identity (A24 doesn't modify cap)
        assert!((scores.budget_cap_mult - 1.0).abs() < 1e-10);
    }

    #[test]
    fn test_p6_from_p6_returns_valid_cap_mult() {
        let (state, config) = make_state_with_partition(16, 42);
        let scores = p6_from_p6(&state, &config);
        // cap_mult should be in [0.3, 1.0]
        assert!(
            scores.budget_cap_mult >= 0.3 - 1e-10,
            "cap_mult should be >= 0.3, got {}",
            scores.budget_cap_mult
        );
        assert!(
            scores.budget_cap_mult <= 1.0 + 1e-10,
            "cap_mult should be <= 1.0, got {}",
            scores.budget_cap_mult
        );
        // rate_mult should be identity (A25 doesn't modify rate)
        assert!((scores.budget_rate_mult - 1.0).abs() < 1e-10);
    }

    #[test]
    fn test_p6_combined_with_both_enabled() {
        let (state, config) = make_state_with_partition(16, 42);
        let scores = compute_p6_modulations(&state, &config);
        // Combined: rate from A24, cap from A25
        assert!(scores.budget_rate_mult >= 1.0 - 1e-10);
        assert!(scores.budget_cap_mult >= 0.3 - 1e-10);
        assert!(scores.budget_cap_mult <= 1.0 + 1e-10);
    }
}
