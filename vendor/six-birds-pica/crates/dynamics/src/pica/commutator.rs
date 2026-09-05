//! Commutator diagnostics: measure non-commutativity of primitive pairs.
//!
//! [Pi, Pj] = ||Pi(Pj(K)) - Pj(Pi(K))||_F
//!
//! Non-zero commutator means the order of application matters.
//! This is itself a P3 diagnostic (route mismatch of the primitive pair).
//!
//! ## Why only 3 of 15 commutator pairs
//!
//! There are C(6,2) = 15 unordered pairs of primitives. We implement three:
//!
//! - **[P1, P2]** (S3): The only pair of *action* primitives that both modify K.
//!   Measures whether rewriting-then-gating differs from gating-then-rewriting.
//!   This is the most physically meaningful commutator.
//!
//! - **[P1, P4]** (S4): Action vs diagnostic. Measures whether P1 changes the
//!   partition — i.e., whether rewriting is "partition-breaking".
//!
//! - **[P2, P4]** (S5): Action vs diagnostic. Measures whether gating changes the
//!   partition — i.e., whether edge deletion reshapes sector boundaries.
//!
//! The remaining 12 pairs are omitted for documented reasons:
//!
//! - **P3 pairs** ([P1,P3], [P2,P3], [P3,P4], [P3,P5], [P3,P6]): P3 (holonomy/
//!   route mismatch) is a *read-only diagnostic* on K — it doesn't transform K.
//!   Its commutator with any action primitive is trivially zero because P3(K) = K.
//!   The non-trivial content (does RM change after P1/P2?) is already captured by
//!   the Group B diagnostic cells (B1-B3).
//!
//! - **P5 pairs** ([P1,P5], [P2,P5], [P4,P5], [P5,P6]): P5 (packaging) is
//!   idempotent and read-only (e(e(x)) = e(x)). Same reasoning as P3.
//!
//! - **P6 pairs** ([P1,P6], [P2,P6], [P4,P6]): P6 (audit) is read-only.
//!   Commuting with it just measures "does measuring before vs after matter?"
//!   which is always zero. The non-trivial P6 content (budget, EP) feeds into
//!   the action cells (A6, A12, A13) rather than commutators.
//!
//! - **[P4, P5]**: Both are read-only diagnostics; commutator is trivially zero.
//!
//! ## Sequential compositions (S1, S2)
//!
//! The plan also defined S1 (P1 then P2) and S2 (P2 then P1) as separate
//! diagnostics. These are captured by the commutator: [P1,P2] = ||S1 - S2||_F.
//! The individual compositions S1 and S2 are the evolved kernels themselves, which
//! are already recorded in the sweep output as macro kernel entries.

use serde::Serialize;
use crate::drive;
use crate::state::{AugmentedState, DynamicsConfig};
use six_primitives_core::primitives;
use six_primitives_core::substrate::MarkovKernel;

use super::{lens_cells, p1_cells, p5_cells, p6_cells, scores::P2Scores, PicaState};

/// Compute the Frobenius commutator of two kernel transformations.
/// Returns ||f(g(K)) - g(f(K))||_F.
fn commutator_frob(
    kernel: &MarkovKernel,
    f: &dyn Fn(&MarkovKernel) -> MarkovKernel,
    g: &dyn Fn(&MarkovKernel) -> MarkovKernel,
) -> f64 {
    let fg = f(&g(kernel));
    let gf = g(&f(kernel));
    let n = kernel.n;
    let mut sum_sq = 0.0;
    for i in 0..n {
        for j in 0..n {
            let diff = fg.kernel[i][j] - gf.kernel[i][j];
            sum_sq += diff * diff;
        }
    }
    sum_sq.sqrt()
}

fn fraction_assignment_changed(before: &[usize], after: &[usize]) -> f64 {
    let n = before.len().min(after.len());
    if n == 0 {
        return 0.0;
    }
    let changed = before
        .iter()
        .zip(after.iter())
        .take(n)
        .filter(|(left, right)| left != right)
        .count();
    changed as f64 / n as f64
}

fn label_disagreement_rate(left: &[usize], right: &[usize]) -> f64 {
    let n = left.len().min(right.len());
    if n == 0 {
        return 0.0;
    }
    let disagreements = (0..n).filter(|&i| left[i] != right[i]).count();
    disagreements as f64 / n as f64
}

fn normalized_weight_distance(left: &[f64], right: &[f64]) -> f64 {
    let n = left.len().min(right.len());
    if n == 0 {
        return 0.0;
    }

    let mut lsum = 0.0;
    let mut rsum = 0.0;
    for i in 0..n {
        let lv = if left[i].is_finite() && left[i] > 0.0 {
            left[i]
        } else {
            0.0
        };
        let rv = if right[i].is_finite() && right[i] > 0.0 {
            right[i]
        } else {
            0.0
        };
        lsum += lv;
        rsum += rv;
    }

    if lsum <= 0.0 || rsum <= 0.0 {
        return 0.0;
    }

    let mut tv = 0.0;
    for i in 0..n {
        let lv = if left[i].is_finite() && left[i] > 0.0 {
            left[i] / lsum
        } else {
            0.0
        };
        let rv = if right[i].is_finite() && right[i] > 0.0 {
            right[i] / rsum
        } else {
            0.0
        };
        tv += (lv - rv).abs();
    }

    (0.5 * tv).min(1.0)
}

fn normalized_p2_score_distance(left: &P2Scores, right: &P2Scores) -> f64 {
    let edge = normalized_weight_distance(&left.edge_weights, &right.edge_weights);
    let cost = normalized_weight_distance(&left.cost_multiplier, &right.cost_multiplier);
    0.5 * (edge + cost)
}

fn inferred_cluster_count(partition: &[usize]) -> usize {
    partition.iter().copied().max().unwrap_or(0).saturating_add(1).max(2)
}

fn packaging_partition(kernel: &MarkovKernel) -> Vec<usize> {
    let base_partition = primitives::p4_sectors(kernel);
    let k = inferred_cluster_count(&base_partition);
    p5_cells::p5_from_p4(kernel, &base_partition, k)
}

fn p4_p6_audited_partition(kernel: &MarkovKernel, seed: u64, k: usize) -> Vec<usize> {
    let direct_partition = lens_cells::p4_from_p6(kernel, k);

    let mut pica_state = PicaState::new(kernel.n);
    pica_state.spectral_partition = Some(direct_partition.clone());

    let state = AugmentedState {
        base_kernel: kernel.clone(),
        gate_mask: vec![vec![true; kernel.n]; kernel.n],
        effective_kernel: kernel.clone(),
        position: 0,
        budget: 0.0,
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

    let config = DynamicsConfig::default_for(kernel.n, seed);
    let scores = p6_cells::p6_from_p4(&state, &config);

    let audited_multiplier = (scores.budget_rate_mult * scores.budget_cap_mult).max(0.0);
    let audited_k = ((k as f64) * audited_multiplier)
        .round()
        .clamp(2.0, kernel.n.max(2) as f64) as usize;

    lens_cells::p4_from_p6(kernel, audited_k)
}

fn p1_p6_audited_weights(kernel: &MarkovKernel, seed: u64, k: usize, budget: f64) -> Vec<f64> {
    let partition = lens_cells::p4_from_p6(kernel, k);

    let mut pica_state = PicaState::new(kernel.n);
    pica_state.spectral_partition = Some(partition.clone());

    let probe_state = AugmentedState {
        base_kernel: kernel.clone(),
        gate_mask: vec![vec![true; kernel.n]; kernel.n],
        effective_kernel: kernel.clone(),
        position: 0,
        budget,
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

    let mut config = DynamicsConfig::default_for(kernel.n, seed);
    config.budget_cap = config.budget_init;
    config.pica = super::PicaConfig::baseline();
    config.pica.enabled[5][3] = true;
    config.pica.enabled[5][5] = true;

    let (_group, level1_frob) =
        crate::observe::level1_audit(kernel, &config, Some(&partition), None);
    let mut probe_state = probe_state;
    probe_state.pica_state.level1_frob = level1_frob;

    let p6_scores = p6_cells::compute_p6_modulations(&probe_state, &config);
    let mut audited_budget = budget;
    drive::replenish(
        &mut audited_budget,
        config.budget_rate * p6_scores.budget_rate_mult,
        config.budget_cap * p6_scores.budget_cap_mult,
    );

    let mut audited_state = probe_state;
    audited_state.budget = audited_budget;

    p1_cells::p1_from_p6(&audited_state, &config).row_weights
}

fn p2_p6_surface(kernel: &MarkovKernel, seed: u64, k: usize, enabled_p6: bool) -> P2Scores {
    let mut config = DynamicsConfig::default_for(kernel.n, seed);
    config.budget_cap = config.budget_init;
    config.pica = super::PicaConfig::baseline();
    config.pica.enabled[1][0] = true;
    config.pica.enabled[1][1] = true;
    config.pica.enabled[1][2] = true;
    config.pica.enabled[1][5] = enabled_p6;

    let partition = lens_cells::p4_from_p6(kernel, k);
    let mut pica_state = PicaState::new(kernel.n);
    pica_state.spectral_partition = Some(partition.clone());

    let mut state = AugmentedState {
        base_kernel: kernel.clone(),
        gate_mask: vec![vec![true; kernel.n]; kernel.n],
        effective_kernel: kernel.clone(),
        position: 0,
        budget: config.budget_init,
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

    let (_group, level1_frob) =
        crate::observe::level1_audit(kernel, &config, Some(&partition), None);
    state.pica_state.level1_frob = level1_frob;

    super::compute_p2_scores(&state, &config)
}

/// S3: [P1, P2] commutator — does rewriting before vs after gating matter?
pub fn commutator_p1_p2(kernel: &MarkovKernel, seed: u64) -> f64 {
    let p1 = |k: &MarkovKernel| -> MarkovKernel { primitives::p1_random_perturb(k, 0.1, seed) };
    let mask = vec![vec![true; kernel.n]; kernel.n];
    let p2 = |k: &MarkovKernel| -> MarkovKernel {
        let mut m = mask.clone();
        // Gate a few random edges deterministically based on seed
        let n = k.n;
        for idx in 0..(n / 4) {
            let i = (seed as usize + idx * 7) % n;
            let j = (seed as usize + idx * 13 + 1) % n;
            if i != j {
                m[i][j] = false;
            }
        }
        primitives::p2_gate(k, &m)
    };
    commutator_frob(kernel, &p1, &p2)
}

/// S4: [P1, P4] commutator — does rewriting before vs after partition matter?
/// Since P4 is diagnostic-only, this measures whether P1 changes the partition.
pub fn commutator_p1_p4(kernel: &MarkovKernel, seed: u64) -> f64 {
    let k_rewritten = primitives::p1_random_perturb(kernel, 0.1, seed);
    let part_before = primitives::p4_sectors(kernel);
    let part_after = primitives::p4_sectors(&k_rewritten);

    // Measure partition difference as fraction of states that changed sector
    let n = kernel.n;
    let mut changed = 0;
    for i in 0..n {
        if part_before[i] != part_after[i] {
            changed += 1;
        }
    }
    changed as f64 / n as f64
}

/// S5: [P2, P4] commutator — does gating before vs after partition matter?
pub fn commutator_p2_p4(kernel: &MarkovKernel, seed: u64) -> f64 {
    let n = kernel.n;
    // Create a deterministic gate mask
    let mut mask = vec![vec![true; n]; n];
    for idx in 0..(n / 4) {
        let i = (seed as usize + idx * 7) % n;
        let j = (seed as usize + idx * 13 + 1) % n;
        if i != j {
            mask[i][j] = false;
        }
    }

    let k_gated = primitives::p2_gate(kernel, &mask);
    let part_before = primitives::p4_sectors(kernel);
    let part_after = primitives::p4_sectors(&k_gated);

    let mut changed = 0;
    for i in 0..n {
        if part_before[i] != part_after[i] {
            changed += 1;
        }
    }
    changed as f64 / n as f64
}

/// [P1, P5] package-related commutator.
/// Measures the fraction of states whose package assignment changes after P1.
pub fn commutator_p1_p5(kernel: &MarkovKernel, seed: u64) -> f64 {
    let pkg_before = packaging_partition(kernel);
    let k_rewritten = primitives::p1_random_perturb(kernel, 0.1, seed);
    let pkg_after = packaging_partition(&k_rewritten);
    fraction_assignment_changed(&pkg_before, &pkg_after)
}

/// [P2, P5] package-related commutator.
/// Measures the fraction of states whose package assignment changes after P2.
pub fn commutator_p2_p5(kernel: &MarkovKernel, seed: u64) -> f64 {
    let n = kernel.n;
    let mut mask = vec![vec![true; n]; n];
    for idx in 0..(n / 4) {
        let i = (seed as usize + idx * 7) % n;
        let j = (seed as usize + idx * 13 + 1) % n;
        if i != j {
            mask[i][j] = false;
        }
    }
    let pkg_before = packaging_partition(kernel);
    let k_gated = primitives::p2_gate(kernel, &mask);
    let pkg_after = packaging_partition(&k_gated);
    fraction_assignment_changed(&pkg_before, &pkg_after)
}

/// [P4, P5] package-conflict diagnostic.
/// Measures how far the package-derived lens deviates from the spectral partition.
pub fn commutator_p4_p5(kernel: &MarkovKernel) -> f64 {
    let part_before = primitives::p4_sectors(kernel);
    let k = inferred_cluster_count(&part_before);
    let part_after = lens_cells::p4_from_p5(kernel, 5, k);
    fraction_assignment_changed(&part_before, &part_after)
}

/// [P1, P6] budget-sensitivity reducer.
/// Compare P1 row targeting before and after one replenish step under active P6 multipliers.
pub fn commutator_p1_p6(kernel: &MarkovKernel, seed: u64) -> f64 {
    let k = kernel.n.clamp(2, 8);
    let mut config = DynamicsConfig::default_for(kernel.n, seed);
    config.budget_cap = config.budget_init;
    let threshold = config.budget_cap * config.pica.p1_p6_budget_threshold_frac;
    let probe_budget = (threshold * 0.5).max(0.0);

    let direct_weights = {
        let mut pica_state = PicaState::new(kernel.n);
        pica_state.spectral_partition = Some(lens_cells::p4_from_p6(kernel, k));
        let mut state = AugmentedState {
            base_kernel: kernel.clone(),
            gate_mask: vec![vec![true; kernel.n]; kernel.n],
            effective_kernel: kernel.clone(),
            position: 0,
            budget: probe_budget,
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
        let (_group, level1_frob) = crate::observe::level1_audit(
            kernel,
            &config,
            state.pica_state.spectral_partition.as_deref(),
            None,
        );
        state.pica_state.level1_frob = level1_frob;
        p1_cells::p1_from_p6(&state, &config).row_weights
    };

    let audited_weights = p1_p6_audited_weights(kernel, seed, k, probe_budget);
    normalized_weight_distance(&direct_weights, &audited_weights)
}

/// [P2, P6] audit-penalty reducer.
/// Compare the combined P2 score surface with and without the P6 penalty enabled.
pub fn commutator_p2_p6(kernel: &MarkovKernel, seed: u64) -> f64 {
    let k = kernel.n.clamp(2, 8);
    let direct = p2_p6_surface(kernel, seed, k, false);
    let audited = p2_p6_surface(kernel, seed, k, true);
    normalized_p2_score_distance(&direct, &audited)
}

/// [P4, P6] branch reducer.
/// Compare the direct P4<-P6 lens against the P6-audited lens resolution.
pub fn commutator_p4_p6(kernel: &MarkovKernel, seed: u64) -> f64 {
    let k = kernel.n.clamp(2, 8);
    let direct = lens_cells::p4_from_p6(kernel, k);
    let audited = p4_p6_audited_partition(kernel, seed, k);
    label_disagreement_rate(&direct, &audited)
}

#[derive(Clone, Debug, Serialize)]
pub struct CommutatorRecord {
    pub pair_id: &'static str,
    pub primitive_pair: &'static str,
    pub metric_name: &'static str,
    pub metric_value: f64,
    pub nonzero: bool,
    pub notes: Vec<&'static str>,
    pub flags: Vec<&'static str>,
}

pub fn all_commutator_records(kernel: &MarkovKernel, seed: u64) -> Vec<CommutatorRecord> {
    let rows = vec![
        (
            "[P1,P2]",
            "P1_P2",
            "frobenius_norm_of_p1_p2_order_difference",
            commutator_p1_p2(kernel, seed),
            vec!["real_kernel_commutator"],
            vec!["action_pair"],
        ),
        (
            "[P1,P4]",
            "P1_P4",
            "fraction_of_states_whose_sector_changed_after_p1",
            commutator_p1_p4(kernel, seed),
            vec!["partition_breaking_proxy"],
            vec!["partition_sensitive"],
        ),
        (
            "[P2,P4]",
            "P2_P4",
            "fraction_of_states_whose_sector_changed_after_p2",
            commutator_p2_p4(kernel, seed),
            vec!["partition_breaking_proxy"],
            vec!["partition_sensitive"],
        ),
        (
            "[P1,P5]",
            "P1_P5",
            "fraction_of_states_whose_package_changed_after_p1",
            commutator_p1_p5(kernel, seed),
            vec!["package_conflict_proxy"],
            vec!["packaging_sensitive"],
        ),
        (
            "[P2,P5]",
            "P2_P5",
            "fraction_of_states_whose_package_changed_after_p2",
            commutator_p2_p5(kernel, seed),
            vec!["package_conflict_proxy"],
            vec!["packaging_sensitive"],
        ),
        (
            "[P4,P5]",
            "P4_P5",
            "fraction_of_states_whose_sector_changed_under_package_derived_lens",
            commutator_p4_p5(kernel),
            vec!["package_derived_partition_proxy"],
            vec!["packaging_sensitive"],
        ),
        (
            "[P1,P6]",
            "P1_P6",
            "normalized_p1_row_weight_distance_under_p6_replenish",
            commutator_p1_p6(kernel, seed),
            vec!["budget_sensitivity_proxy"],
            vec!["audit_sensitive"],
        ),
        (
            "[P2,P6]",
            "P2_P6",
            "normalized_p2_score_surface_distance_under_p6_penalty",
            commutator_p2_p6(kernel, seed),
            vec!["audit_penalty_proxy"],
            vec!["audit_sensitive"],
        ),
        (
            "[P4,P6]",
            "P4_P6",
            "fraction_of_states_whose_sector_changed_under_p6_audited_lens",
            commutator_p4_p6(kernel, seed),
            vec!["audit_branch_proxy"],
            vec!["audit_sensitive"],
        ),
    ];
    rows.into_iter()
        .map(
            |(pair_id, primitive_pair, metric_name, metric_value, notes, flags)| {
                CommutatorRecord {
                    pair_id,
                    primitive_pair,
                    metric_name,
                    metric_value,
                    nonzero: metric_value.abs() > 1e-12,
                    notes,
                    flags,
                }
            },
        )
        .collect()
}

/// Compute all commutator diagnostics for a kernel.
pub fn all_commutators(kernel: &MarkovKernel, seed: u64) -> Vec<(&'static str, f64)> {
    all_commutator_records(kernel, seed)
        .into_iter()
        .map(|row| (row.pair_id, row.metric_value))
        .collect()
}
