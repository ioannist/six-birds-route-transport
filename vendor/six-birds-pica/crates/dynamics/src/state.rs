//! Augmented state and configuration for the self-modifying dynamical system.

use crate::pica::{PicaConfig, PicaState};
use rand::Rng;
use rand_chacha::ChaCha8Rng;
use six_primitives_core::primitives;
use six_primitives_core::substrate::MarkovKernel;

/// The full state of the dynamical system.
///
/// Contains both FAST variables (position) and SLOW variables (kernel, gate mask).
/// The effective kernel = base_kernel gated by gate_mask.
pub struct AugmentedState {
    /// Base kernel before gating (P1 modifies this).
    pub base_kernel: MarkovKernel,
    /// Gate mask: true = edge kept, false = edge deleted (P2 modifies this).
    pub gate_mask: Vec<Vec<bool>>,
    /// Effective kernel = gated(base_kernel, gate_mask). Cached, recomputed on P1/P2.
    pub effective_kernel: MarkovKernel,
    /// Current micro state (FAST variable).
    pub position: usize,
    /// P3 protocol phase (cycles 0..protocol_cycle_len).
    pub phase: usize,
    /// P6 modification budget.
    pub budget: f64,
    /// Total steps taken.
    pub step: u64,

    /// Counters for diagnostics.
    pub p1_accepted: u64,
    pub p1_rejected: u64,
    pub p2_accepted: u64,
    pub p2_rejected: u64,
    pub traj_steps: u64,
    /// SBRC: cumulative count of repair-classified flips in accepted P2 moves.
    pub p2_repairs: u64,
    /// SBRC: cumulative count of violation-classified flips in accepted P2 moves.
    pub p2_violations: u64,

    // === PICA state ===
    /// Primitive Interaction Closure Algebra cached informant data.
    pub pica_state: PicaState,
}

/// Configuration for the dynamical system.
pub struct DynamicsConfig {
    /// State space size.
    pub n: usize,
    /// Mixture weight: trajectory step (FAST, dominant).
    pub p_traj: f64,
    /// Mixture weight: P1 kernel perturbation (SLOW).
    pub p_p1: f64,
    /// Mixture weight: P2 gate flip (SLOW).
    pub p_p2: f64,
    /// Mixture weight: P4 sector update (diagnostic).
    pub p_p4: f64,
    /// Mixture weight: P5 packaging (noop).
    pub p_p5: f64,
    /// Mixture weight: P6 extra budget replenishment.
    pub p_p6: f64,
    /// Budget replenishment rate per step.
    pub budget_rate: f64,
    /// Initial budget.
    pub budget_init: f64,
    /// P1 perturbation strength.
    pub p1_strength: f64,
    /// Number of edges to flip per P2 step (scales with n).
    pub p2_flips: usize,
    /// Minimum row entropy for viability (in nats).
    pub min_row_entropy: f64,
    /// Maximum self-loop weight for viability.
    pub max_self_loop: f64,
    /// P3 protocol cycle length (1 = no protocol).
    pub protocol_cycle_len: usize,
    /// Total dynamics steps.
    pub total_steps: usize,
    /// Observation interval (take snapshot every N steps).
    pub obs_interval: usize,
    /// Adaptive tau alpha parameter (tau = max(1, floor(alpha / gap))).
    pub tau_alpha: f64,
    /// Budget cap (budget cannot exceed this). 0.0 = no cap.
    pub budget_cap: f64,
    /// Number of clusters for spectral partition (2 = bisection, 4/8 = multi-state).
    pub n_clusters: usize,
    /// RNG seed.
    pub seed: u64,

    // === PICA config ===
    /// Primitive Interaction Closure Algebra configuration.
    pub pica: PicaConfig,
}

impl DynamicsConfig {
    /// Default config for a given scale and seed.
    pub fn default_for(n: usize, seed: u64) -> Self {
        let ln_n = (n as f64).ln();
        DynamicsConfig {
            n,
            p_traj: 0.90,
            p_p1: 0.03,
            p_p2: 0.03,
            p_p4: 0.01,
            p_p5: 0.01,
            p_p6: 0.02,
            budget_rate: ln_n * 0.01,
            budget_init: n as f64 * ln_n,
            p1_strength: 0.1,
            p2_flips: (n / 8).max(1),
            min_row_entropy: 0.1 * ln_n,
            max_self_loop: 1.0 - 1.0 / n as f64,
            protocol_cycle_len: 100,
            total_steps: n * 2000,
            obs_interval: n * 20,
            tau_alpha: 0.5,
            budget_cap: 0.0,
            n_clusters: 2,
            seed,
            pica: PicaConfig::none(),
        }
    }

    /// Normalized mixture weights as array [traj, p1, p2, p4, p5, p6].
    pub fn mixture_weights(&self) -> [f64; 6] {
        let total = self.p_traj + self.p_p1 + self.p_p2 + self.p_p4 + self.p_p5 + self.p_p6;
        [
            self.p_traj / total,
            self.p_p1 / total,
            self.p_p2 / total,
            self.p_p4 / total,
            self.p_p5 / total,
            self.p_p6 / total,
        ]
    }
}

impl AugmentedState {
    /// Initialize from a random kernel.
    pub fn new(config: &DynamicsConfig, rng: &mut ChaCha8Rng) -> Self {
        let base_kernel = MarkovKernel::random(config.n, config.seed);
        let gate_mask = vec![vec![true; config.n]; config.n];
        let effective_kernel = base_kernel.clone();
        let position = rng.gen_range(0..config.n);

        AugmentedState {
            base_kernel,
            gate_mask,
            effective_kernel,
            position,
            phase: 0,
            budget: config.budget_init,
            step: 0,
            p1_accepted: 0,
            p1_rejected: 0,
            p2_accepted: 0,
            p2_rejected: 0,
            traj_steps: 0,
            p2_repairs: 0,
            p2_violations: 0,
            pica_state: PicaState::new(config.n),
        }
    }

    /// Initialize from a given kernel (for ladder stacking: macro kernel as input).
    pub fn new_from_kernel(
        kernel: MarkovKernel,
        config: &DynamicsConfig,
        rng: &mut ChaCha8Rng,
    ) -> Self {
        let n = kernel.n;
        let gate_mask = vec![vec![true; n]; n];
        let effective_kernel = kernel.clone();
        let position = rng.gen_range(0..n);

        AugmentedState {
            base_kernel: kernel,
            gate_mask,
            effective_kernel,
            position,
            phase: 0,
            budget: config.budget_init,
            step: 0,
            p1_accepted: 0,
            p1_rejected: 0,
            p2_accepted: 0,
            p2_rejected: 0,
            traj_steps: 0,
            p2_repairs: 0,
            p2_violations: 0,
            pica_state: PicaState::new(n),
        }
    }

    /// Recompute effective kernel from base + gate mask.
    pub fn recompute_effective(&mut self) {
        self.effective_kernel = primitives::p2_gate(&self.base_kernel, &self.gate_mask);
    }
}
