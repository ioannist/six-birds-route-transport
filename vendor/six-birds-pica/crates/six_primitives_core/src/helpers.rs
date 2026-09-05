//! Reusable helper functions extracted from the linear ladder experiments.
//!
//! These are the core building blocks for macro kernel construction,
//! route mismatch measurement, lens evaluation, and scale-dependent
//! parameter selection. Used by both the archived ladder experiments
//! and the new graph-based framework.

use crate::closure;
use crate::primitives;
use crate::substrate::{path_reversal_asymmetry, Lens, MarkovKernel, Substrate};
use rand::Rng;
use rand::SeedableRng;
use rand_chacha::ChaCha8Rng;

// ============================================================================
// Macro kernel construction
// ============================================================================

/// Build induced macro kernel from a micro kernel + lens (deterministic).
/// K_macro[bx, by] = avg_{z in f^{-1}(bx)} sum_{y: f(y)=by} P[z,y]
pub fn build_induced_macro_kernel(kernel: &MarkovKernel, lens: &Lens) -> MarkovKernel {
    let n = kernel.n;
    let nb = lens.macro_n;
    let mut macro_data = vec![vec![0.0; nb]; nb];

    for bx in 0..nb {
        let states_x: Vec<usize> = (0..n).filter(|&z| lens.mapping[z] == bx).collect();
        if states_x.is_empty() {
            continue;
        }
        let weight = 1.0 / states_x.len() as f64;
        for by in 0..nb {
            let mut flow = 0.0;
            for &zx in &states_x {
                for zy in 0..n {
                    if lens.mapping[zy] == by {
                        flow += weight * kernel.kernel[zx][zy];
                    }
                }
            }
            macro_data[bx][by] = flow;
        }
        let row_sum: f64 = macro_data[bx].iter().sum();
        if row_sum > 0.0 {
            for by in 0..nb {
                macro_data[bx][by] /= row_sum;
            }
        }
    }

    MarkovKernel {
        n: nb,
        kernel: macro_data,
    }
}

/// Build empirical macro kernel via trajectory sampling (P1 rewrite).
/// Samples n_traj random trajectories of length tau, counts macro transitions.
pub fn trajectory_rewrite_macro(
    kernel: &MarkovKernel,
    lens: &Lens,
    tau: usize,
    n_traj: usize,
    seed: u64,
) -> MarkovKernel {
    let n = kernel.n;
    let nb = lens.macro_n;
    let mut rng = ChaCha8Rng::seed_from_u64(seed);
    let mut counts = vec![vec![0.0; nb]; nb];

    for _ in 0..n_traj {
        let start: usize = rng.gen_range(0..n);
        let macro_from = lens.mapping[start];
        let mut state = start;
        for _ in 0..tau {
            let r: f64 = rng.gen();
            let mut cum = 0.0;
            let mut next = n - 1; // fallback for floating-point tail mass
            for j in 0..n {
                cum += kernel.kernel[state][j];
                if r < cum {
                    next = j;
                    break;
                }
            }
            state = next;
        }
        let macro_to = lens.mapping[state];
        counts[macro_from][macro_to] += 1.0;
    }

    let mut data = vec![vec![0.0; nb]; nb];
    for bx in 0..nb {
        let row_sum: f64 = counts[bx].iter().sum();
        if row_sum > 0.0 {
            for by in 0..nb {
                data[bx][by] = counts[bx][by] / row_sum;
            }
        } else {
            for by in 0..nb {
                data[bx][by] = 1.0 / nb as f64;
            }
        }
    }
    MarkovKernel {
        n: nb,
        kernel: data,
    }
}

/// Build macro kernel from precomputed K^tau rows (fast, deterministic).
pub fn build_macro_from_ktau(
    ktau_rows: &[Vec<f64>],
    mapping: &[usize],
    macro_n: usize,
) -> MarkovKernel {
    let n = ktau_rows.len();
    let nb = macro_n;
    let mut macro_data = vec![vec![0.0; nb]; nb];

    for bx in 0..nb {
        let mut fiber_count = 0;
        for zx in 0..n {
            if mapping[zx] != bx {
                continue;
            }
            fiber_count += 1;
            for zy in 0..n {
                macro_data[bx][mapping[zy]] += ktau_rows[zx][zy];
            }
        }
        if fiber_count > 0 {
            let w = 1.0 / fiber_count as f64;
            for by in 0..nb {
                macro_data[bx][by] *= w;
            }
        }
        let row_sum: f64 = macro_data[bx].iter().sum();
        if row_sum > 0.0 {
            // K^tau rows are stochastic, so row_sum should already be ~1.
            // Keep renormalization as a numerical guard against roundoff drift.
            for by in 0..nb {
                macro_data[bx][by] /= row_sum;
            }
        } else {
            // Defensive fallback for malformed/non-surjective mappings:
            // keep the macro-kernel stochastic rather than leaving a zero row.
            for by in 0..nb {
                macro_data[bx][by] = 1.0 / nb as f64;
            }
        }
    }

    MarkovKernel {
        n: nb,
        kernel: macro_data,
    }
}

// ============================================================================
// Route mismatch (P3 metric)
// ============================================================================

/// Measure mean route mismatch over random distributions.
/// Compares: (evolve then pushforward) vs (pushforward then macro-step).
pub fn mean_route_mismatch(
    kernel: &MarkovKernel,
    macro_kernel: &MarkovKernel,
    lens: &Lens,
    tau: usize,
    n_samples: usize,
    seed: u64,
) -> f64 {
    let n = kernel.n;
    let mut rng = ChaCha8Rng::seed_from_u64(seed);
    let mut total = 0.0;

    for _ in 0..n_samples {
        let mut dist: Vec<f64> = (0..n).map(|_| rng.gen::<f64>() + 1e-10).collect();
        let s: f64 = dist.iter().sum();
        for x in &mut dist {
            *x /= s;
        }

        let evolved = kernel.evolve(&dist, tau);
        let route_a = lens.pushforward(&evolved);
        let macro_d = lens.pushforward(&dist);
        let route_b = macro_kernel.step(&macro_d);

        let rm: f64 = route_a
            .iter()
            .zip(route_b.iter())
            .map(|(a, b)| (a - b).abs())
            .sum();
        total += rm;
    }
    total / n_samples as f64
}

/// Compute mean RM using precomputed K^tau rows (fast, deterministic).
pub fn fast_mean_rm(
    ktau_rows: &[Vec<f64>],
    mapping: &[usize],
    macro_n: usize,
    macro_k: &MarkovKernel,
) -> f64 {
    let n = ktau_rows.len();
    let nb = macro_n;
    let mut total = 0.0;

    for z in 0..n {
        let mut route_a = vec![0.0; nb];
        for (zi, &p) in ktau_rows[z].iter().enumerate() {
            route_a[mapping[zi]] += p;
        }
        let route_b = &macro_k.kernel[mapping[z]];
        let rm: f64 = route_a
            .iter()
            .zip(route_b.iter())
            .map(|(a, b)| (a - b).abs())
            .sum();
        total += rm;
    }
    total / n as f64
}

// ============================================================================
// Lens construction helpers
// ============================================================================

/// Build a sector-aligned lens from P4 sector labels.
/// Maps each micro state to its sector label. macro_n = number of sectors.
pub fn sector_lens(kernel: &MarkovKernel) -> Lens {
    let labels = primitives::p4_sectors(kernel);
    let max_label = *labels.iter().max().unwrap_or(&0);
    let macro_n = max_label + 1;
    Lens {
        mapping: labels,
        macro_n,
    }
}

// ============================================================================
// Scale-dependent parameters
// ============================================================================

/// Scale-dependent gating probability: above fragmentation threshold for each n.
/// From CLO-014 pattern + random graph theory extrapolation.
pub fn scale_gating_prob(n: usize) -> f64 {
    if n <= 16 {
        0.90
    } else if n <= 32 {
        0.95
    } else if n <= 64 {
        0.97
    } else if n <= 128 {
        0.98
    } else {
        0.99
    }
}

/// Standard trajectory count for scale n.
pub fn standard_n_traj(n: usize) -> usize {
    (n * 200).max(10000)
}

/// Standard RM sample count for scale n.
pub fn standard_n_rm(n: usize) -> usize {
    (n / 4).max(30)
}

// ============================================================================
// Kernel transformations
// ============================================================================

/// Symmetrize a kernel to enforce detailed balance (reversibility).
/// K_sym(i,j) = (K(i,j) + K(j,i)*pi(j)/pi(i)) / 2.
/// Result: sigma_T = 0 by construction. DPI guaranteed.
pub fn symmetrize_kernel(kernel: &MarkovKernel) -> MarkovKernel {
    let n = kernel.n;
    let pi = kernel.stationary(10000, 1e-12);
    let mut data = vec![vec![0.0; n]; n];

    for i in 0..n {
        for j in 0..n {
            if pi[i] > 1e-20 && pi[j] > 1e-20 {
                let k_rev_ij = kernel.kernel[j][i] * pi[j] / pi[i];
                data[i][j] = (kernel.kernel[i][j] + k_rev_ij) / 2.0;
            } else {
                data[i][j] = kernel.kernel[i][j];
            }
        }
        let row_sum: f64 = data[i].iter().sum();
        if row_sum > 0.0 {
            for j in 0..n {
                data[i][j] /= row_sum;
            }
        }
    }

    MarkovKernel { n, kernel: data }
}

// ============================================================================
// Full lens evaluation
// ============================================================================

/// Result of evaluating a lens on a kernel.
#[derive(Clone, Debug)]
pub struct LensEval {
    pub macro_n: usize,
    pub sigma: f64,
    pub gap: f64,
    pub rm: f64,
    pub dpi: bool,
    pub fp: usize,
    pub defect: f64,
}

/// Evaluate a lens on a kernel: build macro kernel, measure DPI, RM, gap, packaging.
pub fn evaluate_lens(
    kernel: &MarkovKernel,
    lens: &Lens,
    tau: usize,
    n_traj: usize,
    n_rm: usize,
    sigma_micro: f64,
    seed: u64,
) -> LensEval {
    if lens.macro_n <= 1 {
        return LensEval {
            macro_n: lens.macro_n,
            sigma: 0.0,
            gap: 0.0,
            rm: 0.0,
            dpi: true,
            fp: 0,
            defect: 0.0,
        };
    }

    let macro_k = trajectory_rewrite_macro(kernel, lens, tau, n_traj, seed);
    let pi_m = macro_k.stationary(10000, 1e-12);
    let sigma = path_reversal_asymmetry(&macro_k, &pi_m, 10);
    let gap = macro_k.spectral_gap();
    let rm = mean_route_mismatch(kernel, &macro_k, lens, tau, n_rm, seed + 50);
    let dpi = sigma <= sigma_micro + 1e-10;

    let sub = Substrate::new(kernel.clone(), lens.clone(), tau);
    let cand = closure::detect_fixed_points(&sub, 30, 300, 1e-10, seed + 60);
    let fp = cand.fixed_points.len();
    let defect = cand
        .idempotence_defects
        .iter()
        .cloned()
        .fold(0.0f64, f64::max);

    LensEval {
        macro_n: lens.macro_n,
        sigma,
        gap,
        rm,
        dpi,
        fp,
        defect,
    }
}

// ============================================================================
// Matrix power (exact K^tau computation)
// ============================================================================

/// Dense matrix multiplication C = A × B (square matrices).
pub fn matrix_multiply(a: &[Vec<f64>], b: &[Vec<f64>]) -> Vec<Vec<f64>> {
    let n = a.len();
    let mut c = vec![vec![0.0f64; n]; n];
    for i in 0..n {
        for k in 0..n {
            let a_ik = a[i][k];
            if a_ik == 0.0 {
                continue;
            }
            for j in 0..n {
                c[i][j] += a_ik * b[k][j];
            }
        }
    }
    c
}

/// Compute K^tau via repeated squaring. O(n^3 log tau).
pub fn matrix_power(kernel: &MarkovKernel, tau: usize) -> MarkovKernel {
    let n = kernel.n;
    if tau <= 1 {
        return kernel.clone();
    }
    let half = matrix_power(kernel, tau / 2);
    let sq = matrix_multiply(&half.kernel, &half.kernel);
    let result = if tau % 2 == 0 {
        sq
    } else {
        matrix_multiply(&sq, &kernel.kernel)
    };
    MarkovKernel { n, kernel: result }
}
