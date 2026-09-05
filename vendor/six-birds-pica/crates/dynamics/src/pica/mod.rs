//! # Primitive Interaction Closure Algebra (PICA)
//!
//! Systematic framework for ALL pairwise interactions among the six primitives P1-P6.
//!
//! ## Motivation
//!
//! The six primitives interact in 6×6 = 36 ordered pairs. Before PICA, only 3 of
//! these were implemented (as ad-hoc code bolted into `mixture.rs`): P4→P2 spectral
//! gating, P6→P2 SBRC, and P6→P3 mixer. The remaining 33 cells were unexplored.
//! PICA enumerates, classifies, and organizes ALL 36 cells so nothing is missed.
//!
//! ## Key principle: all primitives are write-enabled
//!
//! Every primitive writes to state that feeds back into dynamics:
//! - **P1** writes K directly (row perturbation)
//! - **P2** writes K directly (edge gating)
//! - **P3** writes mixture weights (which primitives to apply)
//! - **P4** writes the partition/lens (which states group together)
//! - **P5** writes groupings (packaging equivalence classes)
//! - **P6** writes the budget ledger (what modifications are affordable)
//!
//! The original classification treated P4/P5/P6 as "read-only diagnostics." This
//! was incorrect — P4's partition is consumed by 6 downstream A-cells and directly
//! shapes the dynamics. The spectral partition is now explicitly A15 (P4←P4), a
//! PICA cell in the P4 row, not a hardwired default outside PICA.
//!
//! ## Cell notation: `actor <- informant`
//!
//! Each cell `Pi <- Pj` means: "Pj's output parameterizes Pi's behavior."
//! The informant reads state (partition, RM, budget, etc.) and produces scores
//! or partitions. The actor uses those to modulate its action.
//!
//! ## Full 6×6 table
//!
//! ```text
//!            informant →  P1(rewrite) P2(gate)  P3(holonomy) P4(sectors) P5(package) P6(audit)
//! actor ↓
//! P1(rewrite)             A1          A2        A3           A4          A5          A6
//! P2(gate)                A7          A8        A9           A10         A11         A12
//! P3(holonomy)            I1          I2        A18          A19         A20         A13
//! P4(sectors)             I3          I4        A14          A15         A16         A17
//! P5(packaging)           I5          I6        A21          A22         T2          A23
//! P6(audit)               I7          I8        T3           A24         —           A25
//! ```
//!
//! ## Cell groups
//!
//! ### Group A — ACTION cells (25 cells)
//!
//! These change what the actor primitive **does** during the dynamics loop.
//!
//! **P1 row** (6 cells in `p1_cells.rs`): produce `P1Scores` for row selection.
//!
//! | Cell | Actor←Informant | Semantic |
//! |------|-----------------|----------|
//! | A1   | P1←P1 | History cooldown: don't re-perturb recently rewritten rows |
//! | A2   | P1←P2 | Sparsity-guided: rows with many gated edges need redistribution |
//! | A3   | P1←P3 | RM-directed rewrite: perturb high-RM rows toward macro consistency |
//! | A4   | P1←P4 | Sector-boundary: perturb states near cluster boundaries |
//! | A5   | P1←P5 | Packaging defect: perturb states with high idempotence failure |
//! | A6   | P1←P6 | Budget-gated: suppress P1 when budget is low |
//!
//! **P2 row** (6 cells in `p2_cells.rs`): produce `P2Scores` for edge selection.
//!
//! | Cell | Actor←Informant | Semantic |
//! |------|-----------------|----------|
//! | A7   | P2←P1 | Protect rewrites: don't gate edges in recently rewritten rows |
//! | A8   | P2←P2 | Flip cooldown: don't re-flip recently flipped edges |
//! | A9   | P2←P3 | RM-guided gating: gate cross-cluster edges in high-RM clusters |
//! | A10  | P2←P4 | Spectral-guided gating: boost inter-cluster edge flip probability |
//! | A11  | P2←P5 | Package-boundary: gate edges between different packages |
//! | A12  | P2←P6 | SBRC: classify flips as repairs (free) or violations (penalized) |
//!
//! **P3 row** (4 cells in `p3_cells.rs`): produces `P3Scores` for mixture weights + tau.
//!
//! | Cell | Actor←Informant | Semantic |
//! |------|-----------------|----------|
//! | A13  | P3←P6 | Frob-modulated mixer: adjust P1-P6 mixture weights by structure |
//! | A18  | P3←P3 | Adaptive tau from multi-scale RM convergence (writes active_tau) |
//! | A19  | P3←P4 | Per-sector mixing weights (high-RM sectors get more P1/P2) |
//! | A20  | P3←P5 | Packaging-derived mixing bias |
//!
//! **P4 row** (4 cells in `lens_cells.rs`): produce candidate partitions (lenses).
//!
//! | Cell | Actor←Informant | Semantic |
//! |------|-----------------|----------|
//! | A14  | P4←P3 | RM-quantile partition: group states by route-mismatch similarity |
//! | A15  | P4←P4 | Spectral partition: canonical lens from eigenvector sign patterns |
//! | A16  | P4←P5 | Package-derived partition: group states by K^τ row similarity |
//! | A17  | P4←P6 | EP-flow partition: group states by entropy production contribution |
//!
//! P4-row cells use **selection** (not multiplication) because partitions are discrete.
//! When multiple P4 cells are enabled, `compute_p4_partition()` scores each candidate
//! and selects the best via `LensSelector` (MinRM, MaxGap, or MaxFrob). Hysteresis
//! prevents oscillation: only switch if the new lens is >10% better.
//!
//! A15 is the canonical lens — the only cell that existed pre-PICA. All downstream
//! A-cells (A3, A4, A9, A10) consume whichever partition won the P4 selection.
//! A5 and A11 consume the P5-row packaging output (active_packaging) instead.
//!
//! **P5 row** (3 cells in `p5_cells.rs`): produce candidate packagings.
//!
//! | Cell | Actor←Informant | Semantic |
//! |------|-----------------|----------|
//! | A21  | P5←P3 | RM-similarity packaging: group states by CG quality |
//! | A22  | P5←P4 | Sector-balanced packaging: split oversized clusters |
//! | A23  | P5←P6 | EP-similarity packaging: group states by thermodynamic role |
//!
//! P5-row cells use **selection** (same as P4). When multiple P5 cells are enabled,
//! `compute_p5_packaging()` scores each candidate and selects the best.
//!
//! **P6 row** (2 cells in `p6_cells.rs`): produce `P6Scores` for budget modulation.
//!
//! | Cell | Actor←Informant | Semantic |
//! |------|-----------------|----------|
//! | A24  | P6←P4 | Sector-specific budget rate multiplier from per-sector EP |
//! | A25  | P6←P6 | EP retention feedback cap (tighten when retention is low) |
//!
//! ### Post-hoc diagnostics (`diag_cells.rs`)
//!
//! Measurement functions for runner logging, computed at observation time.
//! These do NOT affect dynamics — they are pure observation. Functions in
//! `diag_cells.rs` (b1_*..b12_*) provide richer diagnostic output for analysis.
//!
//! ### Group I — IMPLICIT cells (8 cells, no code needed)
//!
//! These represent interactions that happen automatically through kernel mutation.
//! When P1 or P2 modifies K, all downstream computations see the new K on their
//! next refresh. The coupling is mediated by `state.effective_kernel` with latencies
//! determined by refresh intervals (partition: 500 steps, RM: 500, L1 audit: 1000).
//!
//! | Cell | Actor←Informant | Mechanism |
//! |------|-----------------|-----------|
//! | I1   | P3←P1 | RM recomputed on post-P1 kernel at next rm_refresh_interval |
//! | I2   | P3←P2 | RM recomputed on post-P2 kernel at next rm_refresh_interval |
//! | I3   | P4←P1 | Partition recomputed after P1 at next partition_interval |
//! | I4   | P4←P2 | Partition recomputed after P2 at next partition_interval |
//! | I5   | P5←P1 | Packaging endomap re-derived after P1 modifies K |
//! | I6   | P5←P2 | Packaging endomap re-derived after P2 modifies K |
//! | I7   | P6←P1 | Audit re-measured on post-P1 kernel at next l1_audit_interval |
//! | I8   | P6←P2 | Audit re-measured on post-P2 kernel at next l1_audit_interval |
//!
//! ### Group T — TRIVIAL cells (3 cells, no code needed)
//!
//! Tautological interactions that produce no information.
//!
//! | Cell | Actor←Informant | Why trivial |
//! |------|-----------------|------------|
//! | T1   | P3←P3 (self) | RM of RM at same scale = idempotent tautology |
//! | T2   | P5←P5 (self) | Packaging idempotence: e(e(x)) = e(x) by definition |
//! | T3   | P6←P3 | RM IS an audit metric — circular to use it to parameterize audit |
//!
//! **Note on T1 vs D1:** T1 (same-scale P3←P3) is trivial, but D1 (multi-scale
//! P3←P3) is informative — it reveals whether RM converges or diverges with scale.
//!
//! ### Group S — SEQUENTIAL COMPOSITIONS (see `commutator.rs`)
//!
//! 3 commutators: [P1,P2], [P1,P4], [P2,P4]. See `commutator.rs` for details.
//!
//! ## Cell count verification
//!
//! ```text
//! Group A (action):     25 cells (6 P1 + 6 P2 + 4 P3 + 4 P4 + 3 P5 + 2 P6)
//! Group I (implicit):    8 cells (4 actors × 2 modifiers)
//! Group T (trivial):     3 cells (P3←P3-self, P5←P5, P6←P3)
//! Undefined:             1 cell  (P6←P5: no clear non-circular action)
//! Total:                37 cells (36 + 1 undefined position)
//! ```
//!
//! Plus 3 commutators (S3-S5) for a total of **40 enumerated interactions**.
//!
//! ## How PICA dispatch works
//!
//! 1. `refresh_informants()` — periodically updates:
//!    - P4 partition via `compute_p4_partition()` (selects best from enabled P4-row cells)
//!    - P3 cluster RM via `compute_cluster_rm()`
//!    - P6 Level 1 audit via `level1_audit()`
//! 2. `apply_p3_modulations()` — adjusts P1-P6 mixture weights via A13
//! 3. Choose action (P1/P2/P6/trajectory) from modulated mixture weights
//! 4. If P1: `compute_p1_scores()` combines all enabled A1-A6 → weighted row selection
//! 5. If P2: `compute_p2_scores()` combines all enabled A7-A12 → weighted edge selection
//!
//! P1/P2/P3 cells combine scores by **element-wise product** (multiplicative stacking).
//! P4 cells combine by **selection** (best candidate wins, with hysteresis).
//!
//! ## Configuration
//!
//! `PicaConfig` controls which cells are enabled via a `[6][6]` boolean matrix.
//! Presets: `none()`, `baseline()` (A10+A15), `sbrc()`, `mixer()`, `full_action()`,
//! `full_lens()` (all 4 P4-row cells). The `lens_selector` field controls how
//! multiple P4 candidates are compared (MinRM, MaxGap, MaxFrob).

pub mod commutator;
pub mod config;
pub mod diag_cells;
pub mod lens_cells;
pub mod multilevel;
pub mod p1_cells;
pub mod p2_cells;
pub mod p3_cells;
pub mod p5_cells;
pub mod p6_cells;
pub mod scores;

pub use config::PicaConfig;
pub use scores::{P1Scores, P2Scores, P3Scores, P6Scores};

use crate::state::{AugmentedState, DynamicsConfig};

/// Cached informant data, refreshed periodically.
/// Replaces the ad-hoc spectral_partition / level1_group / level1_frob fields.
pub struct PicaState {
    // P4 informant: active partition (produced by P4-row lens cells)
    pub spectral_partition: Option<Vec<usize>>,
    pub steps_since_partition: u64,

    // P4 lens metadata (for logging)
    /// Which P4-row cell produced the active partition (2=P3, 3=P4, 4=P5, 5=P6).
    pub active_lens_source: Option<u8>,
    /// Scores of all lens candidates at last refresh: (informant_id, score).
    pub lens_qualities: Vec<(u8, f64)>,

    // P6 cross-layer: Level 1 audit
    pub level1_group: Option<Vec<usize>>,
    pub level1_frob: f64,
    pub steps_since_l1_audit: u64,

    // P3 informant: per-cluster route mismatch
    pub cluster_rm: Option<Vec<f64>>,
    pub steps_since_rm_refresh: u64,

    // P1 history (for A1: cooldown)
    pub last_p1_row: Option<usize>,
    pub last_p1_step: u64,
    /// Recent rewritten rows with step timestamps (for A7 rewrite protection memory).
    pub recent_p1_rows: Vec<(usize, u64)>,

    // P2 history (for A7: protect rewrites, A8: flip cooldown)
    pub last_flip_step: Vec<Vec<u64>>,

    // P3 informant: active tau (produced by A18: P3←P3)
    /// When A18 is enabled, this holds the PICA-determined tau.
    /// Consumers check this first, fall back to observe::adaptive_tau().
    pub active_tau: Option<usize>,

    // P5 informant: active packaging (produced by P5-row cells)
    pub active_packaging: Option<Vec<usize>>,
    /// Per-package route mismatch (computed on active_packaging, not spectral_partition).
    /// Consumed by A20 (P3←P5).
    pub packaging_rm: Option<Vec<f64>>,
    /// Which P5-row cell produced the active packaging (2=P3, 3=P4, 5=P6).
    pub packaging_source: Option<u8>,
    /// Scores of all packaging candidates at last refresh: (informant_id, score).
    pub packaging_qualities: Vec<(u8, f64)>,
    pub steps_since_packaging: u64,

    // P6 modulations: cached budget rate/cap multipliers
    pub active_p6_rate_mult: f64,
    pub active_p6_cap_mult: f64,
    pub steps_since_p6_refresh: u64,

    // SBRC counters
    pub p2_repairs: u64,
    pub p2_violations: u64,

    // Event counters (for audit trail)
    pub partition_flip_count: u64,
    pub packaging_flip_count: u64,
    pub tau_change_count: u64,
    pub last_partition_flip_step: u64,
    pub last_packaging_flip_step: u64,
    pub last_tau_change_step: u64,
}

impl PicaState {
    pub fn new(n: usize) -> Self {
        PicaState {
            spectral_partition: None,
            steps_since_partition: 0,
            active_lens_source: None,
            lens_qualities: Vec::new(),
            level1_group: None,
            level1_frob: 0.0,
            steps_since_l1_audit: 0,
            cluster_rm: None,
            steps_since_rm_refresh: 0,
            last_p1_row: None,
            last_p1_step: 0,
            recent_p1_rows: Vec::new(),
            last_flip_step: vec![vec![0; n]; n],
            active_tau: None,
            active_packaging: None,
            packaging_rm: None,
            packaging_source: None,
            packaging_qualities: Vec::new(),
            steps_since_packaging: 0,
            active_p6_rate_mult: 1.0,
            active_p6_cap_mult: 1.0,
            steps_since_p6_refresh: 0,
            p2_repairs: 0,
            p2_violations: 0,
            partition_flip_count: 0,
            packaging_flip_count: 0,
            tau_change_count: 0,
            last_partition_flip_step: 0,
            last_packaging_flip_step: 0,
            last_tau_change_step: 0,
        }
    }
}

/// Refresh cached informant data based on which cells need it.
pub fn refresh_informants(state: &mut AugmentedState, config: &DynamicsConfig) {
    let pica = &config.pica;

    // P4 partition: produced by P4-row lens cells
    // If partition is needed but no P4 cell enabled, compute_p4_partition handles it
    // via its internal fallback (A15 spectral). All paths go through the PICA dispatch.
    let partition_changed = pica.needs_partition()
        && (state.pica_state.spectral_partition.is_none()
            || state.pica_state.steps_since_partition >= pica.partition_interval);
    if partition_changed {
        let result = lens_cells::compute_p4_partition(state, config);
        state.pica_state.spectral_partition = Some(result.partition);
        state.pica_state.active_lens_source = Some(result.source);
        state.pica_state.lens_qualities = result.qualities;
        state.pica_state.steps_since_partition = 0;
        if result.changed {
            // Only count as a flip when the partition actually changed
            // (hysteresis may keep the old partition even on refresh)
            state.pica_state.partition_flip_count += 1;
            state.pica_state.last_partition_flip_step = state.step;
            // Invalidate downstream caches that depend on the partition
            state.pica_state.cluster_rm = None;
            state.pica_state.steps_since_rm_refresh = pica.rm_refresh_interval; // force recompute
            state.pica_state.steps_since_l1_audit = pica.l1_audit_interval; // force recompute
        }
    }
    state.pica_state.steps_since_partition += 1;

    // A18: P3←P3 adaptive tau (piggybacks on partition refresh timing)
    if pica.enabled[2][2] && state.pica_state.steps_since_partition <= 1 {
        // Refresh tau whenever partition is refreshed (steps_since_partition was just reset)
        let old_tau = state.pica_state.active_tau;
        p3_cells::p3_from_p3_tau(&mut state.pica_state, &state.effective_kernel, config);
        // If tau changed, invalidate all RM caches (they depend on K^τ)
        if state.pica_state.active_tau != old_tau {
            state.pica_state.cluster_rm = None;
            state.pica_state.steps_since_rm_refresh = pica.rm_refresh_interval;
            state.pica_state.packaging_rm = None;
            state.pica_state.tau_change_count += 1;
            state.pica_state.last_tau_change_step = state.step;
        }
    }

    // P6 cross-layer: Level 1 audit
    if pica.needs_l1_audit()
        && (state.pica_state.level1_group.is_none()
            || state.pica_state.steps_since_l1_audit >= pica.l1_audit_interval)
    {
        let (group, frob) = crate::observe::level1_audit(
            &state.effective_kernel,
            config,
            state.pica_state.spectral_partition.as_deref(),
            state.pica_state.active_tau,
        );
        state.pica_state.level1_group = Some(group);
        state.pica_state.level1_frob = frob;
        state.pica_state.steps_since_l1_audit = 0;
    }
    state.pica_state.steps_since_l1_audit += 1;

    // --- RM computations + packaging: shared K^τ ---
    //
    // K^τ = matrix_power(effective_kernel, tau) is O(n³ log τ). Multiple RM computations
    // (cluster_rm, packaging_rm) and A21's internal RM all need K^τ at the same tau.
    // We compute K^τ once per refresh cycle and pass it to all consumers.
    //
    // Ordering: cluster_rm BEFORE packaging, because P1←P3 / P2←P3 / A19
    // depend on cluster_rm; packaging comes later.

    let cluster_rm_due = pica.needs_cluster_rm()
        && (state.pica_state.cluster_rm.is_none()
            || state.pica_state.steps_since_rm_refresh >= pica.rm_refresh_interval);

    // Packaging refresh requires at least one P5-row producer to be enabled.
    // Without producers, active_packaging stays None and refresh is a no-op.
    let packaging_refresh_due = pica.needs_packaging()
        && pica.any_p5_enabled()
        && (state.pica_state.active_packaging.is_none()
            || state.pica_state.steps_since_packaging >= pica.packaging_interval);

    // packaging_rm will be needed if A20 is enabled, packaging data exists (or will
    // be produced this cycle), and the cached packaging_rm is stale or missing.
    let packaging_rm_will_be_needed = pica.needs_packaging_rm()
        && (state.pica_state.active_packaging.is_some() || packaging_refresh_due)
        && (state.pica_state.packaging_rm.is_none() || packaging_refresh_due);

    // Compute K^τ once if any RM-dependent computation needs it
    let shared_ktau = if cluster_rm_due || packaging_rm_will_be_needed {
        let gap = state.effective_kernel.spectral_gap();
        let tau = state
            .pica_state
            .active_tau
            .unwrap_or_else(|| crate::observe::adaptive_tau(gap, config.tau_alpha));
        Some(six_primitives_core::helpers::matrix_power(
            &state.effective_kernel,
            tau,
        ))
    } else {
        None
    };

    // Cluster RM (early because P1←P3, P2←P3, A19 depend on it; packaging later)
    if cluster_rm_due {
        state.pica_state.cluster_rm = Some(compute_cluster_rm(
            state,
            config,
            shared_ktau.as_ref().unwrap(),
        ));
        state.pica_state.steps_since_rm_refresh = 0;
    }
    state.pica_state.steps_since_rm_refresh += 1;

    // P5 packaging: produced by P5-row cells
    if packaging_refresh_due {
        if pica.any_p5_enabled() {
            let result = p5_cells::compute_p5_packaging(state, config);
            state.pica_state.active_packaging = Some(result.packaging);
            state.pica_state.packaging_source = Some(result.source);
            state.pica_state.packaging_qualities = result.qualities;
            if result.changed {
                // Only count as a flip when the packaging actually changed
                state.pica_state.packaging_rm = None;
                state.pica_state.packaging_flip_count += 1;
                state.pica_state.last_packaging_flip_step = state.step;
            }
        }
        state.pica_state.steps_since_packaging = 0;
    }
    state.pica_state.steps_since_packaging += 1;

    // Packaging RM: computed on active_packaging for A20 (P3←P5), using shared K^τ
    if pica.needs_packaging_rm() && state.pica_state.packaging_rm.is_none() {
        if let Some(ref packaging) = state.pica_state.active_packaging {
            debug_assert!(
                shared_ktau.is_some(),
                "BUG: packaging_rm needed but shared_ktau was not pre-computed"
            );
            if let Some(ref ktau) = shared_ktau {
                state.pica_state.packaging_rm = Some(compute_rm_for_partition(ktau, packaging));
            }
        }
    }

    // P6 modulations: cached budget rate/cap multipliers
    if pica.any_p6_modulation() && state.pica_state.steps_since_p6_refresh >= pica.p6_refresh_interval
    {
        let scores = p6_cells::compute_p6_modulations(state, config);
        state.pica_state.active_p6_rate_mult = scores.budget_rate_mult;
        state.pica_state.active_p6_cap_mult = scores.budget_cap_mult;
        state.pica_state.steps_since_p6_refresh = 0;
    }
    state.pica_state.steps_since_p6_refresh += 1;
}

/// Compute per-cluster route mismatch for an arbitrary partition using pre-computed K^τ.
///
/// For each cluster c, measure how well "evolve then coarsen" matches "coarsen then evolve".
/// This is the generic algorithm used by both `compute_cluster_rm` (spectral partition)
/// and packaging RM computation (active_packaging).
///
/// `ktau` must be the pre-computed matrix power K^τ of the effective kernel.
/// The caller is responsible for computing K^τ once and passing it to all RM computations
/// in the same refresh cycle, avoiding redundant O(n³ log τ) matrix power operations.
fn compute_rm_for_partition(
    ktau: &six_primitives_core::substrate::MarkovKernel,
    partition: &[usize],
) -> Vec<f64> {
    let n = ktau.n;
    let max_cluster = partition.iter().copied().max().unwrap_or(0);
    let n_clusters = max_cluster + 1;
    let mut cluster_sizes = vec![0usize; n_clusters];
    for &c in partition {
        if c < n_clusters {
            cluster_sizes[c] += 1;
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
        if cluster_sizes[c] > 0 {
            let row_sum: f64 = macro_k[c].iter().sum();
            if row_sum > 0.0 {
                for j in 0..n_clusters {
                    macro_k[c][j] /= row_sum;
                }
            }
        }
    }

    let mut cluster_rm = vec![0.0; n_clusters];
    for i in 0..n {
        let ci = partition[i];
        if ci >= n_clusters {
            continue;
        }
        if cluster_sizes[ci] == 0 {
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
        for c2 in 0..n_clusters {
            rm += (micro_proj[c2] - macro_k[ci][c2]).abs();
        }
        cluster_rm[ci] += rm / cluster_sizes[ci] as f64;
    }

    cluster_rm
}

/// Compute per-cluster route mismatch on the spectral partition using pre-computed K^τ.
fn compute_cluster_rm(
    state: &AugmentedState,
    config: &DynamicsConfig,
    ktau: &six_primitives_core::substrate::MarkovKernel,
) -> Vec<f64> {
    let partition = match &state.pica_state.spectral_partition {
        Some(p) => p,
        None => return vec![0.0; config.n_clusters],
    };

    compute_rm_for_partition(ktau, partition)
}

/// Compute combined P1 scores from all enabled P1-row cells.
pub fn compute_p1_scores(state: &AugmentedState, config: &DynamicsConfig) -> P1Scores {
    let n = config.n;
    let pica = &config.pica;
    let mut all_scores: Vec<P1Scores> = Vec::new();

    if pica.enabled[0][0] {
        all_scores.push(p1_cells::p1_from_p1(state, pica));
    }
    if pica.enabled[0][1] {
        all_scores.push(p1_cells::p1_from_p2(state, pica));
    }
    if pica.enabled[0][2] {
        all_scores.push(p1_cells::p1_from_p3(state, config));
    }
    if pica.enabled[0][3] {
        all_scores.push(p1_cells::p1_from_p4(state, pica));
    }
    if pica.enabled[0][4] {
        all_scores.push(p1_cells::p1_from_p5(state, config));
    }
    if pica.enabled[0][5] {
        all_scores.push(p1_cells::p1_from_p6(state, config));
    }

    if all_scores.is_empty() {
        return P1Scores::uniform(n);
    }

    let refs: Vec<&P1Scores> = all_scores.iter().collect();
    scores::combine_p1(n, &refs)
}

/// Compute combined P2 scores from all enabled P2-row cells.
pub fn compute_p2_scores(state: &AugmentedState, config: &DynamicsConfig) -> P2Scores {
    let n = config.n;
    let pica = &config.pica;
    let mut all_scores: Vec<P2Scores> = Vec::new();

    if pica.enabled[1][0] {
        all_scores.push(p2_cells::p2_from_p1(state, pica));
    }
    if pica.enabled[1][1] {
        all_scores.push(p2_cells::p2_from_p2(state, pica));
    }
    if pica.enabled[1][2] {
        all_scores.push(p2_cells::p2_from_p3(state, config));
    }
    if pica.enabled[1][3] {
        all_scores.push(p2_cells::p2_from_p4(state, pica));
    }
    if pica.enabled[1][4] {
        all_scores.push(p2_cells::p2_from_p5(state, config));
    }
    if pica.enabled[1][5] {
        all_scores.push(p2_cells::p2_from_p6(state, config));
    }

    if all_scores.is_empty() {
        return P2Scores::uniform(n);
    }

    let refs: Vec<&P2Scores> = all_scores.iter().collect();
    scores::combine_p2(n, &refs)
}

/// Apply P3 modulations to mixture weights.
pub fn apply_p3_modulations(
    base_weights: &[f64; 6],
    state: &AugmentedState,
    config: &DynamicsConfig,
) -> [f64; 6] {
    let pica = &config.pica;
    if !pica.any_p3_modulation() {
        return *base_weights;
    }

    let mut all_scores: Vec<P3Scores> = Vec::new();

    // A18 (P3←P3) writes tau, doesn't produce P3Scores — handled in refresh_informants
    if pica.enabled[2][3] {
        all_scores.push(p3_cells::p3_from_p4(state, config));
    }
    if pica.enabled[2][4] {
        all_scores.push(p3_cells::p3_from_p5(state, config));
    }
    if pica.enabled[2][5] {
        all_scores.push(p3_cells::p3_from_p6(state, pica));
    }

    if all_scores.is_empty() {
        return *base_weights;
    }

    let refs: Vec<&P3Scores> = all_scores.iter().collect();
    let combined = scores::combine_p3(&refs);

    let mut weights = *base_weights;
    for i in 0..6 {
        weights[i] *= combined.weight_multipliers[i];
    }
    let sum: f64 = weights.iter().sum();
    if sum > 0.0 {
        for w in &mut weights {
            *w /= sum;
        }
    }
    weights
}
