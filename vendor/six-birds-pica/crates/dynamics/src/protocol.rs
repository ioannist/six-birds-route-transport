//! Active P3: protocol phase variable and phase-dependent biasing.
//!
//! The protocol phase cycles through 0..cycle_len. Different phases
//! bias the mixture weights toward different primitives, creating
//! a structured exploration schedule.
//!
//! Holonomy = whether the kernel state after a full cycle differs
//! from the state before (detected via P3 route mismatch).

/// Compute phase-biased mixture weights.
///
/// Divides the cycle into four quarters:
/// - Q1 (0..25%): boost P2 gating (create structure)
/// - Q2 (25..50%): boost P1 perturbation (explore)
/// - Q3 (50..75%): normal (let trajectory explore)
/// - Q4 (75..100%): boost P6 budget (replenish)
pub fn phase_bias(base_weights: &[f64; 6], phase: usize, cycle_len: usize) -> [f64; 6] {
    if cycle_len <= 1 {
        return *base_weights;
    }

    let frac = phase as f64 / cycle_len as f64;
    let mut biased = *base_weights;

    // Indices: [0]=traj, [1]=P1, [2]=P2, [3]=P4, [4]=P5, [5]=P6
    if frac < 0.25 {
        biased[2] *= 3.0; // Boost P2 (gating)
    } else if frac < 0.5 {
        biased[1] *= 3.0; // Boost P1 (perturbation)
    } else if frac < 0.75 {
        // Normal — trajectory dominates
    } else {
        biased[5] *= 3.0; // Boost P6 (budget)
    }

    // Renormalize
    let sum: f64 = biased.iter().sum();
    for w in &mut biased {
        *w /= sum;
    }
    biased
}

/// Advance the protocol phase by one step.
pub fn advance_phase(phase: &mut usize, cycle_len: usize) {
    *phase = (*phase + 1) % cycle_len;
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_phase_bias_sums_to_one() {
        let base = [0.90, 0.03, 0.03, 0.01, 0.01, 0.02];
        for phase in 0..100 {
            let biased = phase_bias(&base, phase, 100);
            let sum: f64 = biased.iter().sum();
            assert!((sum - 1.0).abs() < 1e-10, "Phase {} sum = {}", phase, sum);
        }
    }

    #[test]
    fn test_cycle_len_1_no_bias() {
        let base = [0.90, 0.03, 0.03, 0.01, 0.01, 0.02];
        let biased = phase_bias(&base, 0, 1);
        for i in 0..6 {
            assert!((biased[i] - base[i]).abs() < 1e-12);
        }
    }
}
