//! Lagrangian probe: emergent lawfulness metrics for macro kernels.
//!
//! Tests whether a coarse-grained layer admits a simple local action
//! (Lagrangian) whose path measure is saddle-point dominated.
//! All functions operate on small macro kernels (k ≤ 64).
//!
//! Four probes plus one baseline:
//! - **step_entropy**: baseline per-step Shannon entropy
//! - **pla2_gap**: 2-step least-action dominance gap (classicality)
//! - **lagr_geo_r2**: locality of action in emergent coordinates (geometrizability)
//! - **lagr_diff_kl / lagr_diff_alpha**: fit quality of minimal diffusion Lagrangian
//!
//! Plus spectral conservation probes (post-review replacements for old noether_modes):
//! - **relaxation_time**: t_rel = 1/(1-|lambda_2|)
//! - **spectral_gap_ratio**: (lambda_1 - |lambda_2|) / lambda_1
//! - **eigenvalue_entropy**: H over nontrivial spectrum
//! - **spectral_participation**: effective mode count (inverse participation ratio)
//! - **relative_slow_modes**: count with |lambda_i|/|lambda_2| >= r

use crate::spectral::jacobi_eigen;
use six_primitives_core::substrate::MarkovKernel;

/// Per-step Shannon entropy of transitions, weighted by stationary distribution π.
///
/// H_step = -Σ_i π_i Σ_j K_{ij} ln(max(K_{ij}, ε))
///
/// Measures how "spread out" each step's probability mass is. High entropy = diffuse
/// transitions. Low entropy = concentrated/deterministic.
pub fn step_entropy(pi: &[f64], kernel: &MarkovKernel) -> f64 {
    let n = kernel.n;
    let eps = 1e-15;
    let mut h = 0.0;
    for i in 0..n {
        if pi[i] < 1e-30 {
            continue;
        }
        for j in 0..n {
            let p = kernel.kernel[i][j];
            // Use max(p, eps) per the formula: avoids dropping near-zero entries
            // while preventing ln(0). For p > eps this equals p*ln(p).
            let p_floor = p.max(eps);
            h -= pi[i] * p * p_floor.ln();
        }
    }
    h
}

/// 2-step least-action dominance gap (PLA2).
///
/// For each endpoint pair (i, k):
///   A_2(i,k) = -ln(max((K²)_{ik}, eps))          — full 2-step transition
///   A*_2(i,k) = min_j { ℓ(i→j) + ℓ(j→k) }      — best single-intermediate path
///   Δ_2(i,k) = A*_2 - A_2 ≥ 0
///
/// Average: PLA2_gap = Σ_i π_i Σ_k (K²)_{ik} · Δ_2(i,k)
///
/// Small gap → histories dominated by a single best intermediate
/// (saddle-point / "classical limit"). Large gap → many paths contribute.
///
/// Complexity: O(k³).
pub fn pla2_gap(pi: &[f64], kernel: &MarkovKernel, eps: f64) -> f64 {
    let n = kernel.n;
    if n == 0 {
        return 0.0;
    }

    // Compute K² (2-step transition matrix)
    let mut k2 = vec![vec![0.0; n]; n];
    for i in 0..n {
        for k in 0..n {
            let mut sum = 0.0;
            for j in 0..n {
                sum += kernel.kernel[i][j] * kernel.kernel[j][k];
            }
            k2[i][k] = sum;
        }
    }

    // Precompute action costs ℓ(i→j) = -ln(max(K_{ij}, eps))
    let mut ell = vec![vec![0.0; n]; n];
    for i in 0..n {
        for j in 0..n {
            ell[i][j] = -(kernel.kernel[i][j].max(eps)).ln();
        }
    }

    // Compute weighted PLA2 gap
    let mut gap = 0.0;
    for i in 0..n {
        if pi[i] < 1e-30 {
            continue;
        }
        for k in 0..n {
            let k2_ik = k2[i][k];
            if k2_ik < eps {
                continue;
            }

            // Full 2-step action
            let a2 = -(k2_ik.max(eps)).ln();

            // Best single-intermediate path cost
            let mut a_star = f64::INFINITY;
            for j in 0..n {
                let cost = ell[i][j] + ell[j][k];
                if cost < a_star {
                    a_star = cost;
                }
            }

            let delta = (a_star - a2).max(0.0);
            gap += pi[i] * k2_ik * delta;
        }
    }
    gap
}

/// Result of spectral embedding: emergent coordinates + eigenvalues for reuse.
pub struct EmbedResult {
    /// Emergent coordinates: coords[d][i] = d-th coordinate of state i.
    /// Up to 3 nontrivial dimensions (fewer if kernel is too small).
    pub coords: Vec<Vec<f64>>,
    /// Eigenvalues of the symmetrized similarity matrix S, sorted descending.
    /// eigenvalues[0] ≈ 1.0 (stationary), eigenvalues[1..] = nontrivial.
    pub eigenvalues: Vec<f64>,
}

/// Diffusion-map-style reversible embedding of a macro kernel.
///
/// 1. Build time-reversal: K*_{ij} = π_j K_{ji} / π_i
/// 2. Symmetrize: K_sym = (K + K*) / 2
/// 3. Similarity transform: S_{ij} = √π_i · K_sym_{ij} / √π_j
/// 4. Jacobi eigendecomposition of S (reuses `spectral::jacobi_eigen`)
/// 5. Return top 2–3 nontrivial eigenvectors as coordinates q_i = v_i / √π_i
///
/// Returns empty EmbedResult (coords=[], eigenvalues=[]) if n < 3 or π has
/// any zero entries (the similarity transform is undefined for zero-π states).
pub fn spectral_embed_reversible(pi: &[f64], kernel: &MarkovKernel) -> EmbedResult {
    let n = kernel.n;
    if n < 3 {
        return EmbedResult {
            coords: vec![],
            eigenvalues: vec![],
        };
    }

    // Build sqrt(π) and 1/sqrt(π), guarding against zeros
    let mut sqrt_pi = vec![0.0; n];
    let mut inv_sqrt_pi = vec![0.0; n];
    let mut any_zero = false;
    for i in 0..n {
        if pi[i] > 1e-30 {
            sqrt_pi[i] = pi[i].sqrt();
            inv_sqrt_pi[i] = 1.0 / sqrt_pi[i];
        } else {
            any_zero = true;
        }
    }
    if any_zero {
        // Degenerate: some states have zero stationary mass.
        // The similarity transform S = D^{1/2} K D^{-1/2} is undefined for
        // zero-π states, so coordinates would contain artifacts (0 * inf).
        // Return empty to signal callers to produce None.
        return EmbedResult {
            coords: vec![],
            eigenvalues: vec![],
        };
    }

    // Build K_sym = (K + K*) / 2 where K*_{ij} = π_j K_{ji} / π_i
    let mut k_sym = vec![vec![0.0; n]; n];
    for i in 0..n {
        for j in 0..n {
            let k_ij = kernel.kernel[i][j];
            let k_star_ij = if pi[i] > 1e-30 {
                pi[j] * kernel.kernel[j][i] / pi[i]
            } else {
                0.0
            };
            k_sym[i][j] = (k_ij + k_star_ij) * 0.5;
        }
    }

    // Similarity transform: S_{ij} = √π_i · K_sym_{ij} / √π_j
    let mut s = vec![vec![0.0; n]; n];
    for i in 0..n {
        for j in 0..n {
            s[i][j] = sqrt_pi[i] * k_sym[i][j] * inv_sqrt_pi[j];
        }
    }

    // Symmetrize S (should be symmetric in theory, enforce numerically)
    for i in 0..n {
        for j in (i + 1)..n {
            let avg = (s[i][j] + s[j][i]) * 0.5;
            s[i][j] = avg;
            s[j][i] = avg;
        }
    }

    // Jacobi eigendecomposition
    let (eigenvalues, eigenvectors) = jacobi_eigen(&s);

    // Extract top 2–3 nontrivial eigenvectors as coordinates
    // eigenvectors[0] corresponds to eigenvalue ≈ 1 (stationary direction)
    let n_coords = 3.min(n - 1); // up to 3 nontrivial dimensions
    let mut coords = Vec::with_capacity(n_coords);
    for d in 0..n_coords {
        let v = &eigenvectors[d + 1]; // skip the stationary eigenvector
                                      // Convert back to state coordinates: q_i = v_i / √π_i
        let q: Vec<f64> = (0..n).map(|i| v[i] * inv_sqrt_pi[i]).collect();
        coords.push(q);
    }

    EmbedResult {
        coords,
        eigenvalues,
    }
}

/// Weighted R² of action density ℓ(i→j) vs squared distance |q_j - q_i|² in
/// emergent coordinates.
///
/// Weight by stationary edge flow: w_{ij} = π_i K_{ij}.
/// Only considers edges with K_{ij} > eps.
///
/// High R² → action is local in emergent space (emergent geometry + local Lagrangian).
/// Returns NaN if fewer than 3 valid edges (insufficient data for regression).
pub fn lagr_geo_r2(pi: &[f64], kernel: &MarkovKernel, coords: &[Vec<f64>], eps: f64) -> f64 {
    let n = kernel.n;
    if coords.is_empty() || n < 2 {
        return f64::NAN;
    }

    // Collect weighted (distance², action) pairs
    let mut sum_w = 0.0;
    let mut sum_wx = 0.0;
    let mut sum_wy = 0.0;
    let mut sum_wxx = 0.0;
    let mut sum_wxy = 0.0;
    let mut sum_wyy = 0.0;
    let mut n_edges = 0usize;

    for i in 0..n {
        if pi[i] < 1e-30 {
            continue;
        }
        for j in 0..n {
            if i == j {
                continue;
            }
            let k_ij = kernel.kernel[i][j];
            if k_ij <= eps {
                continue;
            }

            let w = pi[i] * k_ij;

            // Squared distance in embedding space
            let mut dist_sq = 0.0;
            for d in 0..coords.len() {
                let dq = coords[d][j] - coords[d][i];
                dist_sq += dq * dq;
            }

            // Action cost
            let action = -(k_ij.max(eps)).ln();

            sum_w += w;
            sum_wx += w * dist_sq;
            sum_wy += w * action;
            sum_wxx += w * dist_sq * dist_sq;
            sum_wxy += w * dist_sq * action;
            sum_wyy += w * action * action;
            n_edges += 1;
        }
    }

    if n_edges < 3 || sum_w < 1e-30 {
        return f64::NAN;
    }

    // Weighted R² = 1 - SS_res / SS_tot
    let mean_x = sum_wx / sum_w;
    let mean_y = sum_wy / sum_w;
    let ss_xx = sum_wxx / sum_w - mean_x * mean_x;
    let ss_yy = sum_wyy / sum_w - mean_y * mean_y;
    let ss_xy = sum_wxy / sum_w - mean_x * mean_y;

    if ss_xx < 1e-30 || ss_yy < 1e-30 {
        return f64::NAN; // no variance in x or y
    }

    let r = ss_xy / (ss_xx * ss_yy).sqrt();
    let r2 = r * r;

    // Clamp to [0, 1]
    r2.clamp(0.0, 1.0)
}

/// Fit a one-parameter diffusion model K̂_{ij}(α) ∝ exp(-α |q_j - q_i|²) and
/// compute the KL divergence between K and K̂.
///
/// Grid search over log-spaced α values, then golden-section refinement.
///
/// Returns (alpha_star, min_kl). Returns (NaN, NaN) if embedding is empty.
pub fn fit_diffusion_kl(pi: &[f64], kernel: &MarkovKernel, coords: &[Vec<f64>]) -> (f64, f64) {
    let n = kernel.n;
    if coords.is_empty() || n < 2 {
        return (f64::NAN, f64::NAN);
    }

    // Precompute pairwise squared distances in embedding space
    let mut dist_sq = vec![vec![0.0; n]; n];
    for i in 0..n {
        for j in 0..n {
            let mut d = 0.0;
            for dim in 0..coords.len() {
                let dq = coords[dim][j] - coords[dim][i];
                d += dq * dq;
            }
            dist_sq[i][j] = d;
        }
    }

    // Evaluate KL for a given alpha.
    // Reuse the row buffer across rows/alphas to avoid repeated allocations.
    let mut model_row = vec![0.0; n];
    let mut eval_kl = |alpha: f64| -> f64 {
        let mut total_kl = 0.0;
        for i in 0..n {
            if pi[i] < 1e-30 {
                continue;
            }

            // Build model row: K̂_{ij} ∝ exp(-α d²_{ij})
            let mut max_log = f64::NEG_INFINITY;
            for j in 0..n {
                let log_val = -alpha * dist_sq[i][j];
                if log_val > max_log {
                    max_log = log_val;
                }
            }
            let mut row_sum = 0.0;
            for j in 0..n {
                model_row[j] = (-alpha * dist_sq[i][j] - max_log).exp();
                row_sum += model_row[j];
            }
            if row_sum < 1e-30 {
                continue;
            }
            for j in 0..n {
                model_row[j] /= row_sum;
            }

            // D_KL(K(i,·) || K̂(i,·))
            for j in 0..n {
                let p = kernel.kernel[i][j];
                let q = model_row[j];
                if p > 1e-15 && q > 1e-15 {
                    total_kl += pi[i] * p * (p / q).ln();
                } else if p > 1e-15 && q <= 1e-15 {
                    total_kl += pi[i] * p * 30.0; // cap contribution
                }
            }
        }
        total_kl
    };

    // Grid search: 50 log-spaced points from 0.01 to 100.0
    let n_grid = 50;
    let log_lo = (0.01f64).ln();
    let log_hi = (100.0f64).ln();
    let mut best_kl = f64::INFINITY;
    let mut best_idx = 0usize;

    let alphas: Vec<f64> = (0..n_grid)
        .map(|i| (log_lo + (log_hi - log_lo) * i as f64 / (n_grid - 1) as f64).exp())
        .collect();

    for (idx, &a) in alphas.iter().enumerate() {
        let kl = eval_kl(a);
        if kl < best_kl {
            best_kl = kl;
            best_idx = idx;
        }
    }
    let _ = best_kl; // used only for grid selection

    // Golden-section refinement within the best grid interval
    let lo = if best_idx > 0 {
        alphas[best_idx - 1]
    } else {
        alphas[0] * 0.5
    };
    let hi = if best_idx + 1 < n_grid {
        alphas[best_idx + 1]
    } else {
        alphas[n_grid - 1] * 2.0
    };
    let gr = 0.6180339887; // golden ratio conjugate
    let mut a = lo;
    let mut b = hi;
    let mut c = b - gr * (b - a);
    let mut d = a + gr * (b - a);
    let mut fc = eval_kl(c);
    let mut fd = eval_kl(d);

    for _ in 0..30 {
        if fc < fd {
            b = d;
            d = c;
            fd = fc;
            c = b - gr * (b - a);
            fc = eval_kl(c);
        } else {
            a = c;
            c = d;
            fc = fd;
            d = a + gr * (b - a);
            fd = eval_kl(d);
        }
        if (b - a).abs() < 1e-6 {
            break;
        }
    }

    let final_alpha = (a + b) * 0.5;
    let final_kl = eval_kl(final_alpha);

    (final_alpha, final_kl)
}

// ---- Spectral conservation probes (post-review) ----
//
// Relative and information-theoretic diagnostics that discriminate on actual
// data. All operate on the eigenvalue vector from spectral_embed_reversible.
//
// IMPORTANT: eigenvalues from jacobi_eigen are sorted by signed value descending,
// NOT by magnitude. The second largest eigenvalue modulus (SLEM) may be a negative
// eigenvalue. Use `slem()` to get the correct reference for relaxation/gap probes.
//
// References:
// - Levin, Peres, Wilmer, "Markov Chains and Mixing Times" (spectral gap)
// - Coifman et al., "Geometric diffusions as a tool for harmonic analysis" (diffusion maps)
// - Nüske et al., "Variational approach to molecular kinetics" (transfer-operator slow modes)
// - Weber & Fackeldey, "G-PCCA" (nonreversible metastable decomposition)

/// Second Largest Eigenvalue Modulus: max |λ_i| for i ≥ 1.
///
/// This is the correct reference eigenvalue for relaxation time and spectral gap
/// in Markov chains, where negative eigenvalues (period-2 oscillations) can have
/// larger magnitude than positive ones.
fn slem(eigenvalues: &[f64]) -> f64 {
    eigenvalues[1..]
        .iter()
        .map(|l| l.abs())
        .fold(0.0_f64, f64::max)
}

/// Relaxation time t_rel = 1 / (1 - |λ₂|).
///
/// How many steps the slowest nontrivial mode needs to decay by factor 1/e.
/// Large t_rel → quasi-conserved quantity (slow mode). Finite t_rel is more
/// informative than hard-thresholded counts on coarse-grained kernels where
/// |λ₂| << 0.95 but the relative ordering still matters.
///
/// Returns NaN if fewer than 2 eigenvalues or if |λ₂| ≥ 1 (infinite relaxation).
pub fn relaxation_time(eigenvalues: &[f64]) -> f64 {
    if eigenvalues.len() < 2 {
        return f64::NAN;
    }
    let lam2 = slem(eigenvalues);
    if lam2 >= 1.0 - 1e-15 {
        return f64::INFINITY;
    }
    1.0 / (1.0 - lam2)
}

/// Spectral gap ratio: (λ₁ - |λ₂|) / λ₁.
///
/// 1.0 → single dominant mode (fast mixing, no conservation).
/// 0.0 → two modes of equal importance (near-conserved block structure).
/// In metastable systems, gap_ratio < 0.2 indicates strong quasi-conservation.
///
/// Returns NaN if fewer than 2 eigenvalues.
pub fn spectral_gap_ratio(eigenvalues: &[f64]) -> f64 {
    if eigenvalues.len() < 2 {
        return f64::NAN;
    }
    let lam1 = eigenvalues[0];
    let lam2_abs = slem(eigenvalues);
    if lam1.abs() < 1e-15 {
        return f64::NAN;
    }
    (lam1 - lam2_abs) / lam1
}

/// Shannon entropy of the nontrivial eigenvalue distribution.
///
/// H = -Σ_i p_i ln(p_i) where p_i = |λ_i| / Z, Z = Σ|λ_i|, i ≥ 2.
///
/// High entropy → many modes contribute equally (rich dynamics).
/// Low entropy → one dominant mode (simple relaxation).
/// Maximum = ln(k-1) for uniform nontrivial spectrum.
pub fn eigenvalue_entropy(eigenvalues: &[f64]) -> f64 {
    if eigenvalues.len() < 2 {
        return f64::NAN;
    }
    let nontrivial: Vec<f64> = eigenvalues[1..].iter().map(|l| l.abs()).collect();
    let z: f64 = nontrivial.iter().sum();
    if z < 1e-30 {
        return 0.0;
    }
    let mut h = 0.0;
    for &lam in &nontrivial {
        let p = lam / z;
        if p > 1e-30 {
            h -= p * p.ln();
        }
    }
    h
}

/// Spectral participation ratio (effective number of modes).
///
/// N_eff = 1 / Σ_i p_i² where p_i = |λ_i| / Z, i ≥ 2.
///
/// 1.0 → single dominant nontrivial mode.
/// k-1 → all nontrivial modes equally important.
/// Equivalent to the inverse participation ratio (IPR⁻¹) from Anderson localization.
pub fn spectral_participation(eigenvalues: &[f64]) -> f64 {
    if eigenvalues.len() < 2 {
        return f64::NAN;
    }
    let nontrivial: Vec<f64> = eigenvalues[1..].iter().map(|l| l.abs()).collect();
    let z: f64 = nontrivial.iter().sum();
    if z < 1e-30 {
        return 0.0;
    }
    let sum_p2: f64 = nontrivial
        .iter()
        .map(|&lam| {
            let p = lam / z;
            p * p
        })
        .sum();
    if sum_p2 < 1e-30 {
        return 0.0;
    }
    1.0 / sum_p2
}

/// Relative slow-mode count: eigenvalues with |λ_i| / |λ₂| ≥ r.
///
/// Uses the second eigenvalue as the reference scale instead of 1.0.
/// This adapts to the actual mixing rate of the kernel and counts how many
/// modes are "comparably slow" to the slowest one.
///
/// r=0.5 → count modes within 50% of the slowest (generous)
/// r=0.7 → within 70% (moderate)
/// r=0.9 → within 90% (strict, near-degenerate cluster)
pub fn relative_slow_modes(eigenvalues: &[f64], r: f64) -> usize {
    if eigenvalues.len() < 2 {
        return 0;
    }
    let lam2_abs = slem(eigenvalues);
    if lam2_abs < 1e-30 {
        return 0;
    }
    eigenvalues[1..]
        .iter()
        .filter(|&&lam| lam.abs() / lam2_abs >= r)
        .count()
}

/// Extract the nontrivial eigenvalues (skip λ₁) for logging.
///
/// Returns raw signed eigenvalues in the original sort order (signed value
/// descending, from `jacobi_eigen`). Callers needing magnitudes should apply
/// `.abs()` themselves. Suitable for post-hoc reanalysis without re-running
/// dynamics.
pub fn nontrivial_eigenvalues(eigenvalues: &[f64]) -> Vec<f64> {
    if eigenvalues.len() < 2 {
        return vec![];
    }
    eigenvalues[1..].to_vec()
}

#[cfg(test)]
mod tests {
    use super::*;
    use six_primitives_core::substrate::MarkovKernel;

    fn uniform_kernel(k: usize) -> MarkovKernel {
        let val = 1.0 / k as f64;
        MarkovKernel {
            n: k,
            kernel: vec![vec![val; k]; k],
        }
    }

    fn permutation_kernel(k: usize) -> MarkovKernel {
        // Cyclic permutation: i → (i+1) mod k
        let mut kernel = vec![vec![0.0; k]; k];
        for i in 0..k {
            kernel[i][(i + 1) % k] = 1.0;
        }
        MarkovKernel { n: k, kernel }
    }

    fn near_identity_kernel(k: usize) -> MarkovKernel {
        // Strong self-loops: K_{ii} = 0.9, rest uniform
        let off = 0.1 / (k - 1) as f64;
        let mut kernel = vec![vec![off; k]; k];
        for i in 0..k {
            kernel[i][i] = 0.9;
        }
        MarkovKernel { n: k, kernel }
    }

    #[test]
    fn test_step_entropy_uniform_kernel() {
        let k = 8;
        let kern = uniform_kernel(k);
        let pi = vec![1.0 / k as f64; k];
        let h = step_entropy(&pi, &kern);
        let expected = (k as f64).ln();
        assert!(
            (h - expected).abs() < 1e-10,
            "Uniform k={} kernel: H_step={:.6}, expected ln({})={:.6}",
            k,
            h,
            k,
            expected
        );
    }

    #[test]
    fn test_step_entropy_deterministic_kernel() {
        let k = 4;
        let kern = permutation_kernel(k);
        let pi = vec![1.0 / k as f64; k]; // uniform is stationary for cyclic perm
        let h = step_entropy(&pi, &kern);
        assert!(
            h.abs() < 1e-10,
            "Permutation kernel: H_step={:.6}, expected 0.0",
            h
        );
    }

    #[test]
    fn test_pla2_gap_identity_like() {
        let k = 4;
        let kern = near_identity_kernel(k);
        let pi = kern.stationary(10000, 1e-12);
        let gap = pla2_gap(&pi, &kern, 1e-15);
        // Near-identity: dominant path through self-loop (i→i→k) for nearby states,
        // so gap should be small but not exactly 0
        assert!(
            gap < 1.0,
            "Near-identity k={}: PLA2_gap={:.4}, expected small",
            k,
            gap
        );
        assert!(gap >= 0.0, "PLA2_gap should be non-negative, got {}", gap);
    }

    #[test]
    fn test_pla2_gap_uniform() {
        let k = 4;
        let kern = uniform_kernel(k);
        let pi = vec![1.0 / k as f64; k];
        let gap = pla2_gap(&pi, &kern, 1e-15);
        // Uniform: K² = K (uniform is idempotent), all intermediaries equally good
        // A_2(i,k) = -ln(1/k) = ln(k)
        // A*_2(i,k) = min_j { ln(k) + ln(k) } = 2 ln(k)
        // Δ = ln(k), weighted average = ln(k)
        let expected = (k as f64).ln();
        assert!(
            (gap - expected).abs() < 1e-10,
            "Uniform k={}: PLA2_gap={:.6}, expected ln({})={:.6}",
            k,
            gap,
            k,
            expected
        );
    }

    #[test]
    fn test_spectral_embed_produces_coordinates() {
        let kern = MarkovKernel::random(8, 42);
        let pi = kern.stationary(10000, 1e-12);
        let result = spectral_embed_reversible(&pi, &kern);
        assert!(
            !result.coords.is_empty(),
            "Should produce at least 1 coordinate dimension"
        );
        assert!(result.coords.len() <= 3, "At most 3 coordinate dimensions");
        for q in &result.coords {
            assert_eq!(q.len(), 8, "Each coordinate should have k=8 entries");
        }
        assert!(!result.eigenvalues.is_empty(), "Should have eigenvalues");
    }

    #[test]
    fn test_lagr_geo_r2_range() {
        let kern = MarkovKernel::random(8, 42);
        let pi = kern.stationary(10000, 1e-12);
        let result = spectral_embed_reversible(&pi, &kern);
        if !result.coords.is_empty() {
            let r2 = lagr_geo_r2(&pi, &kern, &result.coords, 1e-15);
            if r2.is_finite() {
                assert!(r2 >= 0.0 && r2 <= 1.0, "R² should be in [0,1], got {}", r2);
            }
        }
    }

    #[test]
    fn test_fit_diffusion_kl_nonneg() {
        let kern = MarkovKernel::random(8, 42);
        let pi = kern.stationary(10000, 1e-12);
        let result = spectral_embed_reversible(&pi, &kern);
        if !result.coords.is_empty() {
            let (alpha, kl) = fit_diffusion_kl(&pi, &kern, &result.coords);
            assert!(alpha > 0.0, "alpha should be positive, got {}", alpha);
            assert!(kl >= 0.0, "KL should be non-negative, got {}", kl);
        }
    }

    #[test]
    fn test_reversible_embed_doubly_stochastic() {
        let kern = MarkovKernel::random_doubly_stochastic(8, 42);
        let pi = kern.stationary(10000, 1e-12);
        let result = spectral_embed_reversible(&pi, &kern);
        assert!(
            !result.coords.is_empty(),
            "Doubly stochastic kernel should produce valid embedding"
        );
        // For doubly stochastic, K* = K (already reversible w.r.t. uniform π)
        // So S should be well-conditioned
        for q in &result.coords {
            let has_variation = q.iter().any(|&x| x.abs() > 1e-10);
            assert!(has_variation, "Coordinate should have nonzero variation");
        }
    }

    // ---- Tests for improved spectral probes ----

    #[test]
    fn test_relaxation_time_identity() {
        // All eigenvalues = 1.0 → t_rel = infinity
        let eigs = vec![1.0, 1.0, 1.0, 1.0];
        let t = relaxation_time(&eigs);
        assert!(
            t.is_infinite(),
            "Identity spectrum should give infinite t_rel"
        );
    }

    #[test]
    fn test_relaxation_time_fast_mixing() {
        // lambda_2 = 0.1 → t_rel = 1/(1-0.1) = 1.111
        let eigs = vec![1.0, 0.1, 0.05, -0.02];
        let t = relaxation_time(&eigs);
        assert!(
            (t - 1.0 / 0.9).abs() < 1e-10,
            "t_rel should be 1/(1-0.1)={:.4}, got {:.4}",
            1.0 / 0.9,
            t
        );
    }

    #[test]
    fn test_relaxation_time_slow_mode() {
        // lambda_2 = 0.95 → t_rel = 1/(1-0.95) = 20.0
        let eigs = vec![1.0, 0.95, 0.1, -0.05];
        let t = relaxation_time(&eigs);
        assert!(
            (t - 20.0).abs() < 1e-10,
            "t_rel should be 20.0, got {:.4}",
            t
        );
    }

    #[test]
    fn test_spectral_gap_ratio_extremes() {
        // Fast mixing: lambda_2 << lambda_1 → gap_ratio ≈ 1
        let eigs_fast = vec![1.0, 0.01, 0.005];
        assert!((spectral_gap_ratio(&eigs_fast) - 0.99).abs() < 1e-10);

        // Near-degenerate: lambda_2 ≈ lambda_1 → gap_ratio ≈ 0
        let eigs_degen = vec![1.0, 0.99, 0.5];
        assert!((spectral_gap_ratio(&eigs_degen) - 0.01).abs() < 1e-10);

        // Edge: too few eigenvalues
        assert!(spectral_gap_ratio(&[1.0]).is_nan());
    }

    #[test]
    fn test_eigenvalue_entropy_uniform() {
        // Uniform nontrivial spectrum → max entropy = ln(k-1)
        let eigs = vec![1.0, 0.5, 0.5, 0.5]; // 3 nontrivial, all equal
        let h = eigenvalue_entropy(&eigs);
        let expected = (3.0f64).ln();
        assert!(
            (h - expected).abs() < 1e-10,
            "Uniform nontrivial spectrum: H={:.6}, expected ln(3)={:.6}",
            h,
            expected
        );
    }

    #[test]
    fn test_eigenvalue_entropy_single_dominant() {
        // One dominant nontrivial mode → low entropy
        let eigs = vec![1.0, 0.9, 0.001, 0.001];
        let h = eigenvalue_entropy(&eigs);
        // Almost all weight on first mode → H close to 0
        assert!(
            h < 0.1,
            "Single-dominant should have low entropy, got {:.4}",
            h
        );
    }

    #[test]
    fn test_spectral_participation_uniform() {
        // Uniform nontrivial → N_eff = k-1
        let eigs = vec![1.0, 0.5, 0.5, 0.5, 0.5]; // 4 equal nontrivial
        let n_eff = spectral_participation(&eigs);
        assert!(
            (n_eff - 4.0).abs() < 1e-10,
            "Uniform nontrivial: N_eff={:.4}, expected 4.0",
            n_eff
        );
    }

    #[test]
    fn test_spectral_participation_single() {
        // One dominant mode → N_eff ≈ 1
        let eigs = vec![1.0, 0.9, 0.001, 0.001, 0.001];
        let n_eff = spectral_participation(&eigs);
        assert!(
            n_eff < 1.5,
            "Single-dominant: N_eff={:.4}, expected ≈1",
            n_eff
        );
    }

    #[test]
    fn test_relative_slow_modes() {
        let eigs = vec![1.0, 0.5, 0.4, 0.3, 0.1, 0.01];
        // r=0.5: |lam|/|lam_2| >= 0.5 → 0.5/0.5=1.0, 0.4/0.5=0.8, 0.3/0.5=0.6 → 3 modes
        assert_eq!(relative_slow_modes(&eigs, 0.5), 3);
        // r=0.7: 0.5, 0.4 → 2 modes
        assert_eq!(relative_slow_modes(&eigs, 0.7), 2);
        // r=0.9: only 0.5 itself → 1 mode
        assert_eq!(relative_slow_modes(&eigs, 0.9), 1);
    }

    #[test]
    fn test_nontrivial_eigenvalues() {
        let eigs = vec![1.0, 0.5, 0.3, -0.1];
        let nt = nontrivial_eigenvalues(&eigs);
        assert_eq!(nt, vec![0.5, 0.3, -0.1]);

        // Empty
        assert!(nontrivial_eigenvalues(&[1.0]).is_empty());
        assert!(nontrivial_eigenvalues(&[]).is_empty());
    }

    #[test]
    fn test_slem_negative_eigenvalue() {
        // Negative eigenvalue with larger magnitude than positive eigenvalues[1]
        // This is the reviewer-identified bug: old code used eigenvalues[1]=0.037,
        // but SLEM should be |-0.039| = 0.039.
        let eigs = vec![1.0, 0.037, 0.001, -0.039];
        let t = relaxation_time(&eigs);
        // SLEM = 0.039, so t_rel = 1/(1-0.039) = 1.04058...
        let expected = 1.0 / (1.0 - 0.039);
        assert!(
            (t - expected).abs() < 1e-10,
            "SLEM-based t_rel should be {:.6}, got {:.6}",
            expected,
            t
        );

        let gr = spectral_gap_ratio(&eigs);
        // gap_ratio = (1.0 - 0.039) / 1.0 = 0.961
        assert!(
            (gr - 0.961).abs() < 1e-10,
            "SLEM-based gap_ratio should be 0.961, got {:.6}",
            gr
        );

        // relative_slow_modes with SLEM=0.039 as reference
        // r=0.5: |0.037|/0.039=0.949 ✓, |0.001|/0.039=0.026 ✗, |-0.039|/0.039=1.0 ✓ → 2
        assert_eq!(relative_slow_modes(&eigs, 0.5), 2);
    }

    #[test]
    fn test_probes_empty_eigenvalues_return_nan() {
        // When embed fails (n<3 or degenerate pi), eigenvalues=[]
        // All probes should return NaN (not 0.0) for undefined-vs-zero distinction
        assert!(relaxation_time(&[]).is_nan());
        assert!(spectral_gap_ratio(&[]).is_nan());
        assert!(eigenvalue_entropy(&[]).is_nan());
        assert!(spectral_participation(&[]).is_nan());
        assert_eq!(relative_slow_modes(&[], 0.5), 0); // count=0 is correct for empty

        // Single eigenvalue (k=1, trivially stochastic)
        assert!(relaxation_time(&[1.0]).is_nan());
        assert!(spectral_gap_ratio(&[1.0]).is_nan());
        assert!(eigenvalue_entropy(&[1.0]).is_nan());
        assert!(spectral_participation(&[1.0]).is_nan());
    }

    #[test]
    fn test_improved_probes_on_real_kernel() {
        // End-to-end: run spectral embed on a random kernel, compute all probes
        let kern = MarkovKernel::random(8, 42);
        let pi = kern.stationary(10000, 1e-12);
        let result = spectral_embed_reversible(&pi, &kern);
        assert!(result.eigenvalues.len() >= 2);

        let t = relaxation_time(&result.eigenvalues);
        assert!(
            t.is_finite() && t > 0.0,
            "t_rel should be positive finite: {}",
            t
        );

        let gr = spectral_gap_ratio(&result.eigenvalues);
        assert!(
            gr >= 0.0 && gr <= 1.0,
            "gap_ratio should be in [0,1]: {}",
            gr
        );

        let h = eigenvalue_entropy(&result.eigenvalues);
        assert!(h >= 0.0, "eigenvalue entropy should be non-negative: {}", h);

        let n_eff = spectral_participation(&result.eigenvalues);
        assert!(
            n_eff >= 1.0,
            "spectral participation should be >= 1: {}",
            n_eff
        );

        // Relative slow modes: r50 >= r70 >= r90
        let s50 = relative_slow_modes(&result.eigenvalues, 0.5);
        let s70 = relative_slow_modes(&result.eigenvalues, 0.7);
        let s90 = relative_slow_modes(&result.eigenvalues, 0.9);
        assert!(s50 >= s70, "r50={} should >= r70={}", s50, s70);
        assert!(s70 >= s90, "r70={} should >= r90={}", s70, s90);
        assert!(s90 >= 1, "r90 should count at least lambda_2 itself");
    }
}
