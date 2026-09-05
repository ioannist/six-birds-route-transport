//! P5-native viability constraints.
//!
//! Proposed kernel modifications are rejected if they violate:
//! 1. Minimum row entropy (prevents near-deterministic rows)
//! 2. No near-absorbing states (max self-loop weight)
//! 3. Connectivity (single connected component)

use crate::state::DynamicsConfig;
use six_primitives_core::substrate::MarkovKernel;

/// Compute Shannon entropy of a row (in nats).
fn row_entropy(row: &[f64]) -> f64 {
    let mut h = 0.0;
    for &p in row {
        if p > 1e-15 {
            h -= p * p.ln();
        }
    }
    h
}

/// Check minimum row entropy constraint.
pub fn min_entropy_ok(kernel: &MarkovKernel, threshold: f64) -> bool {
    for i in 0..kernel.n {
        if row_entropy(&kernel.kernel[i]) < threshold {
            return false;
        }
    }
    true
}

/// Check no near-absorbing states (all self-loops below threshold).
pub fn no_absorbing(kernel: &MarkovKernel, max_self_loop: f64) -> bool {
    for i in 0..kernel.n {
        if kernel.kernel[i][i] > max_self_loop {
            return false;
        }
    }
    true
}

/// Check connectivity (single connected component).
pub fn connected(kernel: &MarkovKernel) -> bool {
    kernel.block_count() == 1
}

/// Full viability check: all three constraints.
pub fn is_viable(kernel: &MarkovKernel, config: &DynamicsConfig) -> bool {
    min_entropy_ok(kernel, config.min_row_entropy)
        && no_absorbing(kernel, config.max_self_loop)
        && connected(kernel)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_random_kernel_viable() {
        let k = MarkovKernel::random(32, 42);
        let config = DynamicsConfig::default_for(32, 42);
        assert!(
            is_viable(&k, &config),
            "Random dense kernel should be viable"
        );
    }

    #[test]
    fn test_absorbing_state_not_viable() {
        let mut k = MarkovKernel::random(8, 42);
        // Make state 0 absorbing
        for j in 0..8 {
            k.kernel[0][j] = 0.0;
        }
        k.kernel[0][0] = 1.0;
        let config = DynamicsConfig::default_for(8, 42);
        assert!(!no_absorbing(&k, config.max_self_loop));
    }
}
