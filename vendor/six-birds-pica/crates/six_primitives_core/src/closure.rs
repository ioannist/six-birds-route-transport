//! Closure detection and verification.

use crate::substrate::Substrate;
use serde::{Deserialize, Serialize};

/// Result of a closure detection attempt.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ClosureCandidate {
    pub fixed_points: Vec<Vec<f64>>,
    pub idempotence_defects: Vec<f64>,
    pub method: String,
}

/// Result of a stability check.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct StabilityResult {
    pub max_defect: f64,
    pub mean_defect: f64,
    pub passed: bool,
    pub epsilon: f64,
}

/// Result of a robustness check.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct RobustnessResult {
    pub persistence_rate: f64,
    pub passed: bool,
    pub threshold: f64,
    pub seeds_tested: usize,
    pub scales_tested: Vec<usize>,
}

/// Detect closure candidates via fixed-point iteration of the packaging endomap.
pub fn detect_fixed_points(
    substrate: &Substrate,
    n_starts: usize,
    max_iter: usize,
    tol: f64,
    seed: u64,
) -> ClosureCandidate {
    let fps = substrate.find_fixed_points(n_starts, max_iter, tol, seed);
    let defects: Vec<f64> = fps
        .iter()
        .map(|fp| substrate.idempotence_defect(fp))
        .collect();
    ClosureCandidate {
        fixed_points: fps,
        idempotence_defects: defects,
        method: "fixed_point_iteration".to_string(),
    }
}

/// Run stability check: apply packaging endomap to each fixed point, measure defect.
pub fn check_stability(
    substrate: &Substrate,
    fixed_points: &[Vec<f64>],
    epsilon: f64,
) -> StabilityResult {
    if fixed_points.is_empty() {
        return StabilityResult {
            max_defect: f64::NAN,
            mean_defect: f64::NAN,
            passed: false,
            epsilon,
        };
    }

    let defects: Vec<f64> = fixed_points
        .iter()
        .map(|fp| substrate.idempotence_defect(fp))
        .collect();

    let max_defect = defects.iter().cloned().fold(0.0_f64, f64::max);
    let mean_defect = defects.iter().sum::<f64>() / defects.len() as f64;

    StabilityResult {
        max_defect,
        mean_defect,
        passed: max_defect < epsilon,
        epsilon,
    }
}

/// Run robustness check: re-detect fixed points across seeds and scales.
pub fn check_robustness(
    kernel_seed: u64,
    micro_n: usize,
    macro_n: usize,
    _base_tau: usize,
    n_seeds: usize,
    scales: &[usize],
    tol: f64,
    reference_fp_count: usize,
    persistence_threshold: f64,
) -> RobustnessResult {
    use crate::substrate::{Lens, MarkovKernel};

    let mut matches = 0;
    let total = n_seeds * scales.len();

    for seed_offset in 0..n_seeds {
        let seed = kernel_seed + seed_offset as u64 * 1000;
        for &scale in scales {
            let k = MarkovKernel::random(micro_n, kernel_seed); // Same kernel
            let lens = Lens::modular(micro_n, macro_n);
            let sub = Substrate::new(k, lens, scale);
            let candidate = detect_fixed_points(&sub, 20, 200, tol, seed);
            if candidate.fixed_points.len() >= reference_fp_count
                && candidate
                    .idempotence_defects
                    .iter()
                    .all(|&d| d < tol * 100.0)
            {
                matches += 1;
            }
        }
    }

    let rate = matches as f64 / total as f64;
    RobustnessResult {
        persistence_rate: rate,
        passed: rate >= persistence_threshold,
        threshold: persistence_threshold,
        seeds_tested: n_seeds,
        scales_tested: scales.to_vec(),
    }
}
