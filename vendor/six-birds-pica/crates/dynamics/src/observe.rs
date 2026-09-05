//! Observation: snapshot the current kernel state and run cascade analysis.
//!
//! Every obs_interval steps, freeze the effective kernel and measure:
//! - Spectral bisection → 2-state lens (for connected kernels)
//! - P4 sectors → multi-state lens (if kernel fragmented)
//! - Adaptive tau → K^tau → macro kernel
//! - Frobenius distance from rank-1
//! - Spectral gap, sigma (arrow-of-time)

use crate::state::{AugmentedState, DynamicsConfig};
use six_primitives_core::helpers;
use six_primitives_core::substrate::{path_reversal_asymmetry, MarkovKernel};

/// A snapshot of the system state at observation time.
#[derive(Clone, Debug)]
pub struct Snapshot {
    pub step: u64,
    pub position: usize,
    pub budget: f64,
    pub phase: usize,
    /// Number of connected components in the effective kernel.
    pub block_count: usize,
    /// Spectral gap of the effective kernel.
    pub eff_gap: f64,
    /// Number of macro states in the observation lens.
    pub macro_n: usize,
    /// Adaptive tau used for K^tau.
    pub tau: usize,
    /// Frobenius distance of macro kernel from rank-1 projector.
    pub frob_from_rank1: f64,
    /// Spectral gap of the macro kernel.
    pub macro_gap: f64,
    /// Sigma_T (arrow-of-time) of the macro kernel.
    pub sigma: f64,
    /// Number of gated (deleted) edges.
    pub gated_edges: usize,
    /// Cross-layer: Level 1 Frobenius distance (0 if coupling disabled).
    pub level1_frob: f64,
    /// P1/P2 acceptance stats at snapshot time.
    pub p1_accepted: u64,
    pub p1_rejected: u64,
    pub p2_accepted: u64,
    pub p2_rejected: u64,
    pub traj_steps: u64,
    /// SBRC: cumulative repair-classified flips in accepted P2 moves.
    pub p2_repairs: u64,
    /// SBRC: cumulative violation-classified flips in accepted P2 moves.
    pub p2_violations: u64,
}

/// Compute adaptive tau from spectral gap: tau = max(1, floor(alpha / gap)).
/// Capped at 10000 to prevent degenerate behavior when gap ≈ 0.
pub fn adaptive_tau(gap: f64, alpha: f64) -> usize {
    if gap <= 1e-12 {
        return 1;
    }
    let tau = (alpha / gap).floor().min(10000.0) as usize;
    tau.max(1)
}

/// Frobenius distance of a stochastic matrix from its rank-1 projector (1 * pi^T).
pub fn frob_from_rank1(kernel: &MarkovKernel) -> f64 {
    let pi = kernel.stationary(10000, 1e-12);
    let n = kernel.n;
    let mut sum_sq = 0.0;
    for i in 0..n {
        for j in 0..n {
            let diff = kernel.kernel[i][j] - pi[j];
            sum_sq += diff * diff;
        }
    }
    sum_sq.sqrt()
}

/// Count gated (deleted) edges in the mask.
fn count_gated_edges(mask: &[Vec<bool>], n: usize) -> usize {
    let mut count = 0;
    for i in 0..n {
        for j in 0..n {
            if !mask[i][j] {
                count += 1;
            }
        }
    }
    count
}

/// Compute the Level 1 audit: macro kernel frob + group mapping projected to micro states.
///
/// 1. Use the provided PICA partition (required — no fallback)
/// 2. Build macro kernel via K^tau through that lens
/// 3. Compute Level 1 spectral bisection of the macro kernel (2 groups)
/// 4. Project back: each micro state gets the Level 1 group of its Level 0 cluster
///
/// `partition` — PICA's active partition. None means no structure yet → returns trivial.
/// `active_tau` — PICA's active tau if available, or None for spectral-gap formula.
///
/// Returns (group_mapping, frob_from_rank1 of macro kernel).
pub fn level1_audit(
    eff: &MarkovKernel,
    config: &DynamicsConfig,
    partition: Option<&[usize]>,
    active_tau: Option<usize>,
) -> (Vec<usize>, f64) {
    let n = eff.n;

    // PICA partition only — no fallback
    let (mapping, macro_n) = match partition {
        Some(part) => {
            let mn = part.iter().copied().max().unwrap_or(0) + 1;
            (part.to_vec(), mn)
        }
        None => return (vec![0; n], 0.0),
    };

    if macro_n < 2 {
        return (vec![0; n], 0.0);
    }

    let eff_gap = eff.spectral_gap();
    let tau = active_tau.unwrap_or_else(|| adaptive_tau(eff_gap, config.tau_alpha));
    let ktau = helpers::matrix_power(eff, tau);
    let macro_k = helpers::build_macro_from_ktau(&ktau.kernel, &mapping, macro_n);
    let frob = frob_from_rank1(&macro_k);

    // Level 1 partition: spectral bisection of the macro kernel
    if macro_n < 3 {
        // Only 2 macro states → each is its own Level 1 group
        let group: Vec<usize> = (0..n).map(|i| mapping[i]).collect();
        return (group, frob);
    }

    let l1_part = crate::spectral::spectral_partition(&macro_k, 2);
    // Project back to micro: micro i → Level 0 cluster c → Level 1 group l1_part[c]
    let group: Vec<usize> = (0..n)
        .map(|i| {
            let cluster = mapping[i];
            if cluster < l1_part.len() {
                l1_part[cluster]
            } else {
                0
            }
        })
        .collect();

    (group, frob)
}

/// Take a snapshot of the current system state.
///
/// Uses PICA's active partition and tau. If PICA hasn't produced a partition yet,
/// reports macro_n=1 (no structure) — we never bypass PICA with a hardwired lens.
pub fn observe(state: &AugmentedState, config: &DynamicsConfig) -> Snapshot {
    let n = config.n;
    let eff = &state.effective_kernel;

    let block_count = eff.block_count();
    let eff_gap = eff.spectral_gap();

    // PICA partition only — no fallback
    let (mapping, macro_n) = if let Some(ref part) = state.pica_state.spectral_partition {
        let mn = part.iter().copied().max().unwrap_or(0) + 1;
        (part.clone(), mn)
    } else {
        (vec![0; n], 1)
    };

    // Use PICA tau if available, otherwise adaptive tau
    let tau = state
        .pica_state
        .active_tau
        .unwrap_or_else(|| adaptive_tau(eff_gap, config.tau_alpha));

    // Macro kernel and its properties
    let (frob, macro_gap, sigma) = if macro_n > 1 {
        let ktau = helpers::matrix_power(eff, tau);
        let macro_k = helpers::build_macro_from_ktau(&ktau.kernel, &mapping, macro_n);
        let frob = frob_from_rank1(&macro_k);
        let mg = macro_k.spectral_gap();
        let pi_m = macro_k.stationary(10000, 1e-12);
        let sig = path_reversal_asymmetry(&macro_k, &pi_m, 10);
        (frob, mg, sig)
    } else {
        (0.0, 0.0, 0.0)
    };

    let gated_edges = count_gated_edges(&state.gate_mask, n);

    Snapshot {
        step: state.step,
        position: state.position,
        budget: state.budget,
        phase: state.phase,
        block_count,
        eff_gap,
        macro_n,
        tau,
        frob_from_rank1: frob,
        macro_gap,
        sigma,
        gated_edges,
        level1_frob: state.pica_state.level1_frob,
        p1_accepted: state.p1_accepted,
        p1_rejected: state.p1_rejected,
        p2_accepted: state.p2_accepted,
        p2_rejected: state.p2_rejected,
        traj_steps: state.traj_steps,
        p2_repairs: state.pica_state.p2_repairs,
        p2_violations: state.pica_state.p2_violations,
    }
}
