//! P6 budget ledger: modification cost accounting and replenishment.
//!
//! Every kernel modification (P1 perturbation, P2 gate flip) costs budget
//! proportional to the KL divergence between old and new effective kernels.
//! Budget replenishes slowly each step, with extra boosts from P6 actions.

use six_primitives_core::substrate::MarkovKernel;

/// Compute modification cost: sum of row-wise KL divergences KL(K'_i || K_i).
///
/// Measures the information cost of changing the kernel from `old` to `new`.
pub fn modification_cost(old: &MarkovKernel, new: &MarkovKernel) -> f64 {
    let n = old.n;
    let mut cost = 0.0;
    for i in 0..n {
        for j in 0..n {
            let p = new.kernel[i][j];
            let q = old.kernel[i][j];
            if p > 1e-15 {
                if q > 1e-15 {
                    cost += p * (p / q).ln();
                } else {
                    // New probability where old had ~zero: cap at ln(1e13)
                    cost += p * 30.0;
                }
            }
        }
    }
    cost
}

/// Check if the budget can afford a given cost.
pub fn can_afford(budget: f64, cost: f64) -> bool {
    budget >= cost
}

/// Replenish budget by the standard rate, respecting cap.
pub fn replenish(budget: &mut f64, rate: f64, cap: f64) {
    *budget += rate;
    if cap > 0.0 && *budget > cap {
        *budget = cap;
    }
}

/// Extra P6 replenishment (10x normal rate), respecting cap.
pub fn p6_boost(budget: &mut f64, rate: f64, cap: f64) {
    *budget += rate * 10.0;
    if cap > 0.0 && *budget > cap {
        *budget = cap;
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_identical_kernels_zero_cost() {
        let k = MarkovKernel::random(8, 42);
        let cost = modification_cost(&k, &k);
        assert!(
            cost.abs() < 1e-12,
            "Same kernel should have zero cost: {}",
            cost
        );
    }

    #[test]
    fn test_modification_cost_positive() {
        let k1 = MarkovKernel::random(8, 42);
        let k2 = MarkovKernel::random(8, 43);
        let cost = modification_cost(&k1, &k2);
        assert!(cost > 0.0, "Different kernels should have positive cost");
    }
}
