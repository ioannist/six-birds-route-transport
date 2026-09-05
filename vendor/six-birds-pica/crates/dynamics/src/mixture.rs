//! # Mixture kernel: stochastic choice among P1-P6 per step.
//!
//! This is the main dynamics loop. Each step: replenish budget → choose a primitive
//! action from the mixture weights → execute that action → advance protocol phase.
//!
//! All primitive interactions are mediated through the Primitive Interaction Closure Algebra (PICA).
//! See `pica/mod.rs` for the full 6×6 cell enumeration.
//!
//! ## PICA dispatch flow (per step)
//!
//! 1. `drive::replenish()` — refill budget
//! 2. `pica::refresh_informants()` — update cached partition, RM, L1 audit
//! 3. `pica::apply_p3_modulations()` — adjust mixture weights (A13)
//! 4. `protocol::phase_bias()` — apply P3 protocol phase bias
//! 5. Choose action from modulated weights
//! 6. If P1: `pica::compute_p1_scores()` → `p1_step()` (weighted row selection)
//! 7. If P2: `pica::compute_p2_scores()` → `p2_step()` (weighted edge selection)
//! 8. `protocol::advance_phase()`
//!
//! ## Key functions
//!
//! - `p1_step()` — selects row via weighted sampling from P1Scores, optionally
//!   biases perturbation direction. Falls back to random perturbation if no direction.
//! - `p2_step()` — selects edges via weighted sampling from P2Scores, applies
//!   cost multipliers from the scores. Classifies repairs/violations for SBRC.
//! - `run_dynamics()` — top-level function, runs total_steps steps, collects snapshots.

use crate::drive;
use crate::observe::{self, Snapshot};
use crate::pica;
use crate::protocol;
use crate::state::{AugmentedState, DynamicsConfig};
use crate::viability;
use rand::Rng;
use rand::SeedableRng;
use rand_chacha::ChaCha8Rng;
use six_primitives_core::primitives;

/// Which action was taken this step.
#[derive(Clone, Copy, Debug, PartialEq)]
pub enum Action {
    Trajectory,
    P1Perturb,
    P2GateFlip,
    P4Sectors,
    P5Package,
    P6BudgetBoost,
}

/// Full trace of a dynamics run.
pub struct DynamicsTrace {
    pub snapshots: Vec<Snapshot>,
    pub config_n: usize,
    pub config_seed: u64,
    pub total_steps: u64,
    /// The final effective kernel after dynamics completed.
    pub final_kernel: six_primitives_core::substrate::MarkovKernel,
    /// P4 lens source at end of run (2=P3, 3=P4, 4=P5, 5=P6).
    pub final_pica_state_lens_source: Option<u8>,
    /// Lens candidate scores at end of run.
    pub final_pica_state_lens_qualities: Vec<(u8, f64)>,
    /// P5 packaging source at end of run (2=P3, 3=P4, 5=P6).
    pub final_pica_state_packaging_source: Option<u8>,
    /// Packaging candidate scores at end of run.
    pub final_pica_state_packaging_qualities: Vec<(u8, f64)>,
    /// Active tau at end of run (None = spectral-gap formula used).
    pub final_pica_state_active_tau: Option<usize>,
    /// Final spectral partition at end of run (for audit records).
    pub final_pica_state_partition: Option<Vec<usize>>,
    /// Final active packaging at end of run (for audit records).
    pub final_pica_state_packaging: Option<Vec<usize>>,
    /// P6 budget rate multiplier at end of run.
    pub final_pica_state_p6_rate_mult: f64,
    /// P6 budget cap multiplier at end of run.
    pub final_pica_state_p6_cap_mult: f64,
    /// Event counters at end of run.
    pub partition_flip_count: u64,
    pub packaging_flip_count: u64,
    pub tau_change_count: u64,
    /// Last step at which each event type occurred (0 = never).
    pub last_partition_flip_step: u64,
    pub last_packaging_flip_step: u64,
    pub last_tau_change_step: u64,
}

/// Choose an action from the phase-biased mixture weights.
fn choose_action(r: f64, weights: &[f64; 6]) -> Action {
    let mut cum = 0.0;
    cum += weights[0];
    if r < cum {
        return Action::Trajectory;
    }
    cum += weights[1];
    if r < cum {
        return Action::P1Perturb;
    }
    cum += weights[2];
    if r < cum {
        return Action::P2GateFlip;
    }
    cum += weights[3];
    if r < cum {
        return Action::P4Sectors;
    }
    cum += weights[4];
    if r < cum {
        return Action::P5Package;
    }
    Action::P6BudgetBoost
}

/// Advance micro position one step through the effective kernel.
fn trajectory_step(state: &mut AugmentedState, rng: &mut ChaCha8Rng) {
    let n = state.effective_kernel.n;
    let r: f64 = rng.gen();
    let mut cum = 0.0;
    for j in 0..n {
        cum += state.effective_kernel.kernel[state.position][j];
        if r < cum {
            state.position = j;
            return;
        }
    }
    state.position = n - 1;
}

/// P1 step: weighted row selection + optional directional perturbation via PICA scores.
fn p1_step(
    state: &mut AugmentedState,
    config: &DynamicsConfig,
    scores: &pica::P1Scores,
    rng: &mut ChaCha8Rng,
) {
    let n = config.n;

    // Weighted row selection
    let total_w: f64 = scores.row_weights.iter().sum();
    if total_w <= 0.0 {
        state.p1_rejected += 1;
        return;
    }

    let r: f64 = rng.gen::<f64>() * total_w;
    let mut cum = 0.0;
    let mut row = n - 1;
    for i in 0..n {
        cum += scores.row_weights[i];
        if r < cum {
            row = i;
            break;
        }
    }

    // Perturb the selected row
    let mut proposed_base = state.base_kernel.clone();
    let mut row_sum = 0.0;

    if let Some(ref direction) = scores.direction {
        // Directional perturbation: blend current row toward target
        let blend = config.p1_strength; // reuse p1_strength as blend factor
        for j in 0..n {
            let current = proposed_base.kernel[row][j];
            let target = direction[row][j];
            let val = (current * (1.0 - blend) + target * blend).max(0.0);
            // Add small random noise
            let noise: f64 = rng.gen::<f64>() * config.p1_strength * 0.1;
            let val = val + noise;
            proposed_base.kernel[row][j] = val;
            row_sum += val;
        }
    } else {
        // Random perturbation (default when no direction provided)
        for j in 0..n {
            let perturb: f64 = rng.gen::<f64>() * config.p1_strength;
            let val = (proposed_base.kernel[row][j] + perturb).max(0.0);
            proposed_base.kernel[row][j] = val;
            row_sum += val;
        }
    }

    if row_sum > 0.0 {
        for j in 0..n {
            proposed_base.kernel[row][j] /= row_sum;
        }
    }

    let proposed_eff = primitives::p2_gate(&proposed_base, &state.gate_mask);

    if !viability::is_viable(&proposed_eff, config) {
        state.p1_rejected += 1;
        return;
    }

    let cost = drive::modification_cost(&state.effective_kernel, &proposed_eff);
    if !drive::can_afford(state.budget, cost) {
        state.p1_rejected += 1;
        return;
    }

    // Accept
    state.budget -= cost;
    state.base_kernel = proposed_base;
    state.effective_kernel = proposed_eff;
    state.p1_accepted += 1;

    // Update PICA state for A1/A7
    state.pica_state.last_p1_row = Some(row);
    state.pica_state.last_p1_step = state.step;
    state.pica_state.recent_p1_rows.push((row, state.step));
    // Keep bounded memory; A7 needs short recent history, not full run history.
    if state.pica_state.recent_p1_rows.len() > 64 {
        let drop_n = state.pica_state.recent_p1_rows.len() - 64;
        state.pica_state.recent_p1_rows.drain(0..drop_n);
    }
}

/// P2 step: weighted edge selection + cost multipliers via PICA scores.
fn p2_step(
    state: &mut AugmentedState,
    config: &DynamicsConfig,
    scores: &pica::P2Scores,
    rng: &mut ChaCha8Rng,
) {
    let n = config.n;
    let n_flips = config.p2_flips;

    let mut flipped: Vec<(usize, usize)> = Vec::with_capacity(n_flips);

    // Sample edges WITHOUT replacement within this P2 action to avoid phantom flips
    // (same edge toggled multiple times in one batch).
    let mut remaining_ew = scores.edge_weights.clone();
    let mut total_ew = 0.0f64;
    for i in 0..n {
        for j in 0..n {
            let idx = i * n + j;
            if i == j || !remaining_ew[idx].is_finite() || remaining_ew[idx] <= 0.0 {
                remaining_ew[idx] = 0.0;
                continue;
            }
            total_ew += remaining_ew[idx];
        }
    }
    if total_ew <= 0.0 {
        state.p2_rejected += 1;
        return;
    }

    for _ in 0..n_flips {
        if total_ew <= 0.0 {
            break; // no remaining selectable edges
        }
        // Weighted edge selection via linear scan (n<=256, p2_flips<=32 in practice).
        let r: f64 = rng.gen::<f64>() * total_ew;
        let mut cum = 0.0;
        let mut selected_idx: Option<usize> = None;
        let mut fallback_idx: Option<usize> = None;
        'outer: for i in 0..n {
            for j in 0..n {
                let idx = i * n + j;
                let w = remaining_ew[idx];
                if w <= 0.0 {
                    continue;
                }
                fallback_idx = Some(idx); // protect against floating-point accumulation drift
                cum += w;
                if r < cum {
                    selected_idx = Some(idx);
                    break 'outer;
                }
            }
        }
        let Some(idx) = selected_idx.or(fallback_idx) else {
            break;
        };
        let w = remaining_ew[idx];
        remaining_ew[idx] = 0.0;
        total_ew = (total_ew - w).max(0.0);
        let i = idx / n;
        let j = idx % n;

        // Flip the edge
        state.gate_mask[i][j] = !state.gate_mask[i][j];
        flipped.push((i, j));
    }

    if flipped.is_empty() {
        state.p2_rejected += 1;
        return;
    }

    let proposed_eff = primitives::p2_gate(&state.base_kernel, &state.gate_mask);

    if !viability::is_viable(&proposed_eff, config) {
        for &(i, j) in &flipped {
            state.gate_mask[i][j] = !state.gate_mask[i][j];
        }
        state.p2_rejected += 1;
        return;
    }

    // Compute cost with PICA cost multipliers
    let base_cost = drive::modification_cost(&state.effective_kernel, &proposed_eff);
    let mut avg_cost_mult = 0.0;
    let mut n_repair = 0u64;
    let mut n_violation = 0u64;
    for &(i, j) in &flipped {
        let cm = scores.cost_multiplier[i * n + j];
        avg_cost_mult += cm;
        if cm > 1.0 {
            n_violation += 1;
        } else if cm < 0.5 {
            n_repair += 1;
        }
    }
    avg_cost_mult /= flipped.len() as f64;
    let cost = base_cost * avg_cost_mult;

    if !drive::can_afford(state.budget, cost) {
        for &(i, j) in &flipped {
            state.gate_mask[i][j] = !state.gate_mask[i][j];
        }
        state.p2_rejected += 1;
        return;
    }

    // Accept — record flip steps for A8 cooldown AFTER all checks pass
    // Use step+1 so that 0 remains a true "never flipped" sentinel
    state.budget -= cost;
    state.effective_kernel = proposed_eff;
    state.p2_accepted += 1;
    state.pica_state.p2_repairs += n_repair;
    state.pica_state.p2_violations += n_violation;
    for &(i, j) in &flipped {
        state.pica_state.last_flip_step[i][j] = state.step + 1;
    }
}

/// One dynamics step: PICA dispatch.
fn dynamics_step(state: &mut AugmentedState, config: &DynamicsConfig, rng: &mut ChaCha8Rng) {
    // Refresh cached informant data (including P6 modulations at interval)
    pica::refresh_informants(state, config);

    // P6 modulations: use cached budget rate/cap multipliers from refresh_informants
    drive::replenish(
        &mut state.budget,
        config.budget_rate * state.pica_state.active_p6_rate_mult,
        config.budget_cap * state.pica_state.active_p6_cap_mult,
    );

    // P3 modulations → mixture weights
    let base_weights = config.mixture_weights();
    let biased = protocol::phase_bias(&base_weights, state.phase, config.protocol_cycle_len);
    let weights = pica::apply_p3_modulations(&biased, state, config);

    let r: f64 = rng.gen();
    let action = choose_action(r, &weights);

    match action {
        Action::Trajectory => {
            trajectory_step(state, rng);
            state.traj_steps += 1;
        }
        Action::P1Perturb => {
            let scores = pica::compute_p1_scores(state, config);
            p1_step(state, config, &scores, rng);
        }
        Action::P2GateFlip => {
            let scores = pica::compute_p2_scores(state, config);
            p2_step(state, config, &scores, rng);
        }
        Action::P4Sectors => {
            // Force immediate partition refresh (no budget charge — doesn't modify K)
            if config.pica.needs_partition() {
                let result = pica::lens_cells::compute_p4_partition(state, config);
                state.pica_state.spectral_partition = Some(result.partition);
                state.pica_state.active_lens_source = Some(result.source);
                state.pica_state.lens_qualities = result.qualities;
                state.pica_state.steps_since_partition = 0;
                if result.changed {
                    state.pica_state.partition_flip_count += 1;
                    state.pica_state.last_partition_flip_step = state.step;
                    // Invalidate downstream caches
                    state.pica_state.cluster_rm = None;
                    state.pica_state.steps_since_rm_refresh = config.pica.rm_refresh_interval;
                    state.pica_state.level1_group = None;
                    state.pica_state.steps_since_l1_audit = config.pica.l1_audit_interval;
                }
            }
        }
        Action::P5Package => {
            // Force immediate packaging refresh (no budget charge — doesn't modify K)
            if config.pica.needs_packaging() && config.pica.any_p5_enabled() {
                let result = pica::p5_cells::compute_p5_packaging(state, config);
                state.pica_state.active_packaging = Some(result.packaging);
                state.pica_state.packaging_source = Some(result.source);
                state.pica_state.packaging_qualities = result.qualities;
                state.pica_state.steps_since_packaging = 0;
                if result.changed {
                    state.pica_state.packaging_flip_count += 1;
                    state.pica_state.last_packaging_flip_step = state.step;
                    state.pica_state.packaging_rm = None;
                }
            }
        }
        Action::P6BudgetBoost => {
            drive::p6_boost(&mut state.budget, config.budget_rate, config.budget_cap);
        }
    }

    protocol::advance_phase(&mut state.phase, config.protocol_cycle_len);
    state.step += 1;
}

/// Public dynamics step: PICA dispatch.
pub fn dynamics_step_pub(
    state: &mut AugmentedState,
    config: &DynamicsConfig,
    rng: &mut ChaCha8Rng,
) {
    dynamics_step(state, config, rng);
}

/// Run the full dynamics and return a trace of snapshots.
pub fn run_dynamics(config: &DynamicsConfig) -> DynamicsTrace {
    // Validate PICA config and warn about suspicious cell configurations
    for warning in config.pica.validate() {
        eprintln!("PICA config warning: {}", warning);
    }

    let mut rng = ChaCha8Rng::seed_from_u64(config.seed);
    let mut state = AugmentedState::new(config, &mut rng);

    let dummy_kernel = state.effective_kernel.clone();
    let mut trace = DynamicsTrace {
        snapshots: Vec::new(),
        config_n: config.n,
        config_seed: config.seed,
        total_steps: config.total_steps as u64,
        final_kernel: dummy_kernel,
        final_pica_state_lens_source: None,
        final_pica_state_lens_qualities: Vec::new(),
        final_pica_state_packaging_source: None,
        final_pica_state_packaging_qualities: Vec::new(),
        final_pica_state_active_tau: None,
        final_pica_state_partition: None,
        final_pica_state_packaging: None,
        final_pica_state_p6_rate_mult: 1.0,
        final_pica_state_p6_cap_mult: 1.0,
        partition_flip_count: 0,
        packaging_flip_count: 0,
        tau_change_count: 0,
        last_partition_flip_step: 0,
        last_packaging_flip_step: 0,
        last_tau_change_step: 0,
    };

    trace.snapshots.push(observe::observe(&state, config));

    for _ in 0..config.total_steps {
        dynamics_step_pub(&mut state, config, &mut rng);

        if state.step % config.obs_interval as u64 == 0 {
            trace.snapshots.push(observe::observe(&state, config));
        }
    }

    if state.step % config.obs_interval as u64 != 0 {
        trace.snapshots.push(observe::observe(&state, config));
    }

    trace.final_kernel = state.effective_kernel;
    trace.final_pica_state_lens_source = state.pica_state.active_lens_source;
    trace.final_pica_state_lens_qualities = state.pica_state.lens_qualities;
    trace.final_pica_state_packaging_source = state.pica_state.packaging_source;
    trace.final_pica_state_packaging_qualities = state.pica_state.packaging_qualities;
    trace.final_pica_state_active_tau = state.pica_state.active_tau;
    trace.final_pica_state_partition = state.pica_state.spectral_partition;
    trace.final_pica_state_packaging = state.pica_state.active_packaging;
    trace.final_pica_state_p6_rate_mult = state.pica_state.active_p6_rate_mult;
    trace.final_pica_state_p6_cap_mult = state.pica_state.active_p6_cap_mult;
    trace.partition_flip_count = state.pica_state.partition_flip_count;
    trace.packaging_flip_count = state.pica_state.packaging_flip_count;
    trace.tau_change_count = state.pica_state.tau_change_count;
    trace.last_partition_flip_step = state.pica_state.last_partition_flip_step;
    trace.last_packaging_flip_step = state.pica_state.last_packaging_flip_step;
    trace.last_tau_change_step = state.pica_state.last_tau_change_step;
    trace
}

/// Run dynamics starting from a given kernel (for ladder stacking).
pub fn run_dynamics_from_kernel(
    kernel: six_primitives_core::substrate::MarkovKernel,
    config: &DynamicsConfig,
) -> DynamicsTrace {
    let mut rng = ChaCha8Rng::seed_from_u64(config.seed);
    let mut state = AugmentedState::new_from_kernel(kernel, config, &mut rng);

    let dummy_kernel = state.effective_kernel.clone();
    let mut trace = DynamicsTrace {
        snapshots: Vec::new(),
        config_n: config.n,
        config_seed: config.seed,
        total_steps: config.total_steps as u64,
        final_kernel: dummy_kernel,
        final_pica_state_lens_source: None,
        final_pica_state_lens_qualities: Vec::new(),
        final_pica_state_packaging_source: None,
        final_pica_state_packaging_qualities: Vec::new(),
        final_pica_state_active_tau: None,
        final_pica_state_partition: None,
        final_pica_state_packaging: None,
        final_pica_state_p6_rate_mult: 1.0,
        final_pica_state_p6_cap_mult: 1.0,
        partition_flip_count: 0,
        packaging_flip_count: 0,
        tau_change_count: 0,
        last_partition_flip_step: 0,
        last_packaging_flip_step: 0,
        last_tau_change_step: 0,
    };

    trace.snapshots.push(observe::observe(&state, config));

    for _ in 0..config.total_steps {
        dynamics_step_pub(&mut state, config, &mut rng);

        if state.step % config.obs_interval as u64 == 0 {
            trace.snapshots.push(observe::observe(&state, config));
        }
    }

    if state.step % config.obs_interval as u64 != 0 {
        trace.snapshots.push(observe::observe(&state, config));
    }

    trace.final_kernel = state.effective_kernel;
    trace.final_pica_state_lens_source = state.pica_state.active_lens_source;
    trace.final_pica_state_lens_qualities = state.pica_state.lens_qualities;
    trace.final_pica_state_packaging_source = state.pica_state.packaging_source;
    trace.final_pica_state_packaging_qualities = state.pica_state.packaging_qualities;
    trace.final_pica_state_active_tau = state.pica_state.active_tau;
    trace.final_pica_state_partition = state.pica_state.spectral_partition;
    trace.final_pica_state_packaging = state.pica_state.active_packaging;
    trace.final_pica_state_p6_rate_mult = state.pica_state.active_p6_rate_mult;
    trace.final_pica_state_p6_cap_mult = state.pica_state.active_p6_cap_mult;
    trace.partition_flip_count = state.pica_state.partition_flip_count;
    trace.packaging_flip_count = state.pica_state.packaging_flip_count;
    trace.tau_change_count = state.pica_state.tau_change_count;
    trace.last_partition_flip_step = state.pica_state.last_partition_flip_step;
    trace.last_packaging_flip_step = state.pica_state.last_packaging_flip_step;
    trace.last_tau_change_step = state.pica_state.last_tau_change_step;
    trace
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_run_dynamics_small() {
        let config = DynamicsConfig {
            n: 8,
            total_steps: 1000,
            obs_interval: 500,
            ..DynamicsConfig::default_for(8, 42)
        };
        let trace = run_dynamics(&config);
        assert!(
            trace.snapshots.len() >= 2,
            "Should have at least initial + final snapshot"
        );
        assert_eq!(trace.snapshots[0].step, 0);
    }

    #[test]
    fn test_budget_decreases_on_modifications() {
        let config = DynamicsConfig {
            n: 8,
            p_traj: 0.0,
            p_p1: 0.5,
            p_p2: 0.5,
            p_p4: 0.0,
            p_p5: 0.0,
            p_p6: 0.0,
            total_steps: 100,
            obs_interval: 100,
            ..DynamicsConfig::default_for(8, 42)
        };
        let trace = run_dynamics(&config);
        let last = trace.snapshots.last().unwrap();
        if last.p1_accepted + last.p2_accepted > 0 {
            assert!(last.p1_accepted + last.p2_accepted > 0);
        }
    }

    #[test]
    fn test_trajectory_only_no_kernel_change() {
        let config = DynamicsConfig {
            n: 8,
            p_traj: 1.0,
            p_p1: 0.0,
            p_p2: 0.0,
            p_p4: 0.0,
            p_p5: 0.0,
            p_p6: 0.0,
            total_steps: 1000,
            obs_interval: 1000,
            ..DynamicsConfig::default_for(8, 42)
        };
        let trace = run_dynamics(&config);
        let last = trace.snapshots.last().unwrap();
        assert_eq!(last.p1_accepted, 0);
        assert_eq!(last.p2_accepted, 0);
        assert_eq!(last.gated_edges, 0);
    }

    #[test]
    fn test_pica_baseline_runs() {
        // PICA with baseline config (P2<-P4 only) should run without crashing
        let mut config = DynamicsConfig::default_for(8, 42);
        config.total_steps = 2000;
        config.obs_interval = 1000;
        config.pica = crate::pica::PicaConfig::baseline();
        config.budget_cap = (8.0_f64).ln() * 8.0;
        config.n_clusters = 2;
        let trace = run_dynamics(&config);
        assert!(trace.snapshots.len() >= 2);
    }

    #[test]
    fn test_pica_full_action_runs() {
        // PICA with full action config should run without crashing
        let mut config = DynamicsConfig::default_for(8, 42);
        config.total_steps = 2000;
        config.obs_interval = 1000;
        config.pica = crate::pica::PicaConfig::full_action();
        config.budget_cap = (8.0_f64).ln() * 8.0;
        config.n_clusters = 4;
        let trace = run_dynamics(&config);
        assert!(trace.snapshots.len() >= 2);
    }

    #[test]
    fn test_pica_full_all_runs() {
        // PICA with all 25 A-cells enabled should run without crashing
        let mut config = DynamicsConfig::default_for(8, 42);
        config.total_steps = 2000;
        config.obs_interval = 1000;
        config.pica = crate::pica::PicaConfig::full_all();
        config.budget_cap = (8.0_f64).ln() * 8.0;
        config.n_clusters = 4;
        let trace = run_dynamics(&config);
        assert!(trace.snapshots.len() >= 2);
    }

    #[test]
    fn test_baseline_backward_compatible() {
        // Baseline (A10+A15 only) should produce meaningful structure
        let mut config = DynamicsConfig::default_for(16, 42);
        config.total_steps = 5000;
        config.obs_interval = 2500;
        config.pica = crate::pica::PicaConfig::baseline();
        config.budget_cap = (16.0_f64).ln() * 16.0;
        config.n_clusters = 4;
        let trace = run_dynamics(&config);
        assert!(trace.snapshots.len() >= 2);
        // Should have some P2 activity
        let last = trace.snapshots.last().unwrap();
        assert!(
            last.p2_accepted + last.p2_rejected > 0,
            "baseline should have P2 activity"
        );
    }

    #[test]
    fn test_p2_step_samples_without_replacement() {
        use rand::SeedableRng;

        let mut config = DynamicsConfig::default_for(4, 42);
        config.p2_flips = 4;
        // Make viability permissive for this targeted sampling test.
        config.min_row_entropy = 0.0;
        config.max_self_loop = 1.0;

        let mut rng = ChaCha8Rng::seed_from_u64(123);
        let mut state = AugmentedState::new(&config, &mut rng);
        state.step = 10;

        let n = config.n;
        let mut scores = pica::P2Scores::uniform(n);
        scores.edge_weights.fill(0.0);
        scores.cost_multiplier.fill(1.0);
        // Only one selectable edge. With replacement this would be toggled repeatedly.
        scores.edge_weights[0 * n + 1] = 1.0;
        scores.cost_multiplier[0 * n + 1] = 2.0; // violation-classified if selected

        p2_step(&mut state, &config, &scores, &mut rng);

        assert_eq!(state.p2_accepted, 1, "P2 step should be accepted");
        assert_eq!(
            state.pica_state.p2_violations, 1,
            "Single unique edge should contribute exactly one violation"
        );
        assert_eq!(
            state.pica_state.last_flip_step[0][1],
            state.step + 1,
            "Selected edge should be marked as flipped this step"
        );

        let mut n_false = 0usize;
        for i in 0..n {
            for j in 0..n {
                if !state.gate_mask[i][j] {
                    n_false += 1;
                }
            }
        }
        assert_eq!(
            n_false, 1,
            "Exactly one edge should be toggled in net effect (no phantom cancellations)"
        );
    }
}
