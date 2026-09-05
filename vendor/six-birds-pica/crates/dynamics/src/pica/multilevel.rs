//! # Multi-level dynamics: P1-P6 applied at every level of the emergence ladder.
//!
//! ## Architecture
//!
//! Before PICA, macro kernels at L1 and L2 were derived from the micro kernel via
//! spectral partition → K^tau → projection. They were **static** — never evolved
//! by P1-P6. PICA changes this: each level gets its own `AugmentedState` with full
//! dynamics driven by the same PICA cells as the micro level.
//!
//! ```text
//! L0 (micro):  full dynamics on n×n kernel (n * 2000 steps)
//!     ↕ coupling every `coupling_interval` steps
//! L1 (macro):  mini-dynamics on L0-macro kernel (~500 steps per coupling)
//!     ↕ coupling
//! L2 (macro²): mini-dynamics on L1-macro kernel (~250 steps per coupling)
//! ```
//!
//! ## Inter-level coupling
//!
//! **Upward (derive):** At each coupling interval, derive a macro kernel from the
//! lower level's evolved kernel via spectral partition → K^tau → projection.
//! The upper level's base_kernel is **blended** toward this derived kernel (50%
//! blend), preserving some of the upper level's own dynamics while anchoring it
//! to the lower level's structure.
//!
//! **Downward (implicit via P1←P3):** When A3 (P1←P3) is enabled at the micro
//! level, it reads `cluster_rm` — the per-cluster route mismatch between
//! "evolve then coarsen" and "coarsen then evolve". High RM in a cluster means
//! that cluster's micro states aren't behaving consistently with the macro kernel.
//! A3 targets those rows for rewriting toward macro-consistent distributions.
//! This IS the top-down feedback mechanism — no separate "downward coupling" code
//! is needed because RM already encodes the discrepancy between levels.
//!
//! ## Phases
//!
//! 1. **Warmup** (0 to `warmup_steps`): Run L0 dynamics only. Let micro structure
//!    emerge before deriving macro levels. Without warmup, the initial random kernel
//!    has no meaningful partition.
//!
//! 2. **Derive L1** (at first coupling after warmup): Spectral partition L0 → build
//!    macro kernel → initialize L1 AugmentedState.
//!
//! 3. **Interleaved** (remaining steps): Every `coupling_interval` steps, re-derive
//!    L1 macro from L0, blend, run L1 mini-dynamics. If L1 has enough states,
//!    derive L2 from L1 similarly.
//!
//! ## Why macro dynamics is cheap
//!
//! A typical L1 macro kernel is 3-8 states. Running 500 dynamics steps on a 5×5
//! kernel takes <1ms. The cost is dominated by L0 micro dynamics (n=32..128).

use crate::observe::{self, Snapshot};
use crate::spectral;
use crate::state::{AugmentedState, DynamicsConfig};
use six_primitives_core::helpers;
use six_primitives_core::substrate::MarkovKernel;

/// One level of the emergence ladder.
pub struct LadderLevel {
    pub state: AugmentedState,
    pub config: DynamicsConfig,
    pub lens: Option<Vec<usize>>,
    pub macro_n: usize,
    pub snapshots: Vec<Snapshot>,
}

/// Configuration for multi-level dynamics.
pub struct LadderConfig {
    /// Number of levels (including micro).
    pub n_levels: usize,
    /// Spectral partition k values for each level boundary.
    /// k_values[0] = partition k for micro→L0 macro, etc.
    pub k_values: Vec<usize>,
    /// Steps between inter-level coupling refreshes (in micro steps).
    pub coupling_interval: u64,
    /// Steps of warmup before activating higher levels.
    pub warmup_steps: u64,
    /// Steps to run at each macro level per coupling interval.
    pub macro_steps_per_interval: usize,
    /// Blend factor for inter-level kernel coupling (0.0 = no blend, 1.0 = full replace).
    pub blend_alpha: f64,
}

impl LadderConfig {
    /// Default 3-level ladder (micro + 2 macro levels).
    pub fn three_level(n: usize) -> Self {
        LadderConfig {
            n_levels: 3,
            k_values: vec![8, 4, 2],
            coupling_interval: 1000,
            warmup_steps: (n * 5000) as u64,
            macro_steps_per_interval: 500,
            blend_alpha: 0.5,
        }
    }
}

/// Result of a multi-level dynamics run.
pub struct LadderTrace {
    /// Per-level snapshots.
    pub level_snapshots: Vec<Vec<Snapshot>>,
    /// Final kernel at each level.
    pub final_kernels: Vec<MarkovKernel>,
    /// Number of actual levels created.
    pub n_levels: usize,
}

fn init_macro_level(
    kernel: MarkovKernel,
    macro_n: usize,
    seed: u64,
    steps_per_interval: usize,
    n_clusters_cap: usize,
    pica: &crate::pica::PicaConfig,
    lens: Option<Vec<usize>>,
) -> LadderLevel {
    use rand::SeedableRng;
    use rand_chacha::ChaCha8Rng;

    let mut config = DynamicsConfig::default_for(macro_n, seed);
    let steps = steps_per_interval.max(1);
    config.total_steps = steps;
    config.obs_interval = steps;
    config.n_clusters = n_clusters_cap.min(macro_n);
    config.pica = pica.clone_for_macro();

    let mut rng = ChaCha8Rng::seed_from_u64(seed);
    let state = AugmentedState::new_from_kernel(kernel, &config, &mut rng);

    LadderLevel {
        state,
        config,
        lens,
        macro_n,
        snapshots: vec![],
    }
}

/// Run multi-level ladder dynamics.
///
/// Phase 1: Warmup micro dynamics.
/// Phase 2: Derive L1 macro kernel, start L1 dynamics.
/// Phase 3: Interleaved dynamics at all levels.
pub fn run_ladder(micro_config: &DynamicsConfig, ladder: &LadderConfig) -> LadderTrace {
    use rand::SeedableRng;
    use rand_chacha::ChaCha8Rng;

    let mut rng = ChaCha8Rng::seed_from_u64(micro_config.seed);
    let mut micro_state = AugmentedState::new(micro_config, &mut rng);

    let mut level_snapshots: Vec<Vec<Snapshot>> = vec![vec![]; ladder.n_levels];
    let mut macro_levels: Vec<Option<LadderLevel>> =
        (0..ladder.n_levels - 1).map(|_| None).collect();

    // Initial observation
    level_snapshots[0].push(observe::observe(&micro_state, micro_config));

    let total_steps = micro_config.total_steps as u64;

    for step in 0..total_steps {
        // Run one micro dynamics step
        crate::mixture::dynamics_step_pub(&mut micro_state, micro_config, &mut rng);

        // Periodic micro observation
        if micro_state.step % micro_config.obs_interval as u64 == 0 {
            level_snapshots[0].push(observe::observe(&micro_state, micro_config));
        }

        // Inter-level coupling
        if step > 0 && step % ladder.coupling_interval == 0 && step >= ladder.warmup_steps {
            // Derive L1 macro kernel from micro — PICA partition only, no fallback
            let l0_lens = match micro_state.pica_state.spectral_partition.clone() {
                Some(lens) => lens,
                None => continue, // PICA hasn't produced a partition yet, skip this coupling
            };
            let l0_macro_n = spectral::n_clusters(&l0_lens);

            if l0_macro_n >= 2 {
                let gap = micro_state.effective_kernel.spectral_gap();
                let tau = micro_state
                    .pica_state
                    .active_tau
                    .unwrap_or_else(|| observe::adaptive_tau(gap, micro_config.tau_alpha));
                let ktau = helpers::matrix_power(&micro_state.effective_kernel, tau);
                let l0_macro = helpers::build_macro_from_ktau(&ktau.kernel, &l0_lens, l0_macro_n);

                // Initialize or update L1 dynamics
                let l1_needs_reinit = macro_levels[0]
                    .as_ref()
                    .map(|level| level.macro_n != l0_macro_n || level.state.base_kernel.n != l0_macro_n)
                    .unwrap_or(true);
                if l1_needs_reinit {
                    macro_levels[0] = Some(init_macro_level(
                        l0_macro.clone(),
                        l0_macro_n,
                        micro_config.seed + 1000,
                        ladder.macro_steps_per_interval,
                        4,
                        &micro_config.pica,
                        Some(l0_lens.clone()),
                    ));
                }

                // Run L1 macro dynamics for a burst
                if let Some(ref mut level) = macro_levels[0] {
                    // Blend current macro kernel toward derived one
                    if !l1_needs_reinit {
                        blend_kernel(&mut level.state.base_kernel, &l0_macro, ladder.blend_alpha);
                        level.state.recompute_effective();
                    }
                    level.lens = Some(l0_lens);
                    level.macro_n = l0_macro_n;

                    let mut macro_rng = ChaCha8Rng::seed_from_u64(micro_config.seed + step);
                    for _ in 0..ladder.macro_steps_per_interval {
                        crate::mixture::dynamics_step_pub(
                            &mut level.state,
                            &level.config,
                            &mut macro_rng,
                        );
                    }

                    // Snapshot
                    let snap = observe::observe(&level.state, &level.config);
                    level_snapshots[1].push(snap);

                    // Feed route mismatch back to micro P1<-P3
                    // The macro-evolved kernel differs from macro-derived → that's the mismatch
                    // This is captured by the existing cluster_rm refresh in pica::refresh_informants
                }

                // If we have L1, derive L2
                if ladder.n_levels >= 3 {
                    if let Some(ref l1) = macro_levels[0] {
                        if l1.macro_n >= 3 {
                            let l1_lens = match l1.state.pica_state.spectral_partition.clone() {
                                Some(lens) => lens,
                                None => continue, // L1 PICA hasn't produced a partition yet
                            };
                            let l1_macro_n = spectral::n_clusters(&l1_lens);
                            if l1_macro_n >= 2 {
                                let l1_gap = l1.state.effective_kernel.spectral_gap();
                                let l1_tau = l1.state.pica_state.active_tau.unwrap_or_else(|| {
                                    observe::adaptive_tau(l1_gap, l1.config.tau_alpha)
                                });
                                let l1_ktau =
                                    helpers::matrix_power(&l1.state.effective_kernel, l1_tau);
                                let l2_macro = helpers::build_macro_from_ktau(
                                    &l1_ktau.kernel,
                                    &l1_lens,
                                    l1_macro_n,
                                );

                                if macro_levels.len() > 1 {
                                    let l2_needs_reinit = macro_levels[1]
                                        .as_ref()
                                        .map(|level| {
                                            level.macro_n != l1_macro_n
                                                || level.state.base_kernel.n != l1_macro_n
                                        })
                                        .unwrap_or(true);
                                    if l2_needs_reinit {
                                        macro_levels[1] = Some(init_macro_level(
                                            l2_macro.clone(),
                                            l1_macro_n,
                                            micro_config.seed + 2000,
                                            ladder.macro_steps_per_interval / 2,
                                            2,
                                            &micro_config.pica,
                                            Some(l1_lens.clone()),
                                        ));
                                    }

                                    if let Some(ref mut l2) = macro_levels[1] {
                                        if !l2_needs_reinit {
                                            blend_kernel(
                                                &mut l2.state.base_kernel,
                                                &l2_macro,
                                                ladder.blend_alpha,
                                            );
                                            l2.state.recompute_effective();
                                        }
                                        l2.lens = Some(l1_lens);
                                        l2.macro_n = l1_macro_n;
                                        let mut l2_rng = ChaCha8Rng::seed_from_u64(
                                            micro_config.seed + step + 2000,
                                        );
                                        for _ in 0..ladder.macro_steps_per_interval / 2 {
                                            crate::mixture::dynamics_step_pub(
                                                &mut l2.state,
                                                &l2.config,
                                                &mut l2_rng,
                                            );
                                        }
                                        let snap = observe::observe(&l2.state, &l2.config);
                                        level_snapshots[2].push(snap);
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    // Final observations
    level_snapshots[0].push(observe::observe(&micro_state, micro_config));

    let mut final_kernels = vec![micro_state.effective_kernel];
    for level in &macro_levels {
        if let Some(l) = level {
            final_kernels.push(l.state.effective_kernel.clone());
        }
    }

    let n_levels = final_kernels.len();
    LadderTrace {
        level_snapshots,
        final_kernels,
        n_levels,
    }
}

/// Blend kernel A toward kernel B: A = (1-alpha)*A + alpha*B, then renormalize rows.
fn blend_kernel(a: &mut MarkovKernel, b: &MarkovKernel, alpha: f64) {
    let n = a.n.min(b.n);
    for i in 0..n {
        let mut row_sum = 0.0;
        for j in 0..n {
            a.kernel[i][j] = (1.0 - alpha) * a.kernel[i][j] + alpha * b.kernel[i][j];
            row_sum += a.kernel[i][j];
        }
        if row_sum > 0.0 {
            for j in 0..n {
                a.kernel[i][j] /= row_sum;
            }
        }
    }
}
