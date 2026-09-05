//! P1-P6 primitive operations on the substrate.

use crate::substrate::{MarkovKernel, Substrate};
use rand::Rng;
use rand::SeedableRng;
use rand_chacha::ChaCha8Rng;

/// P1: Operator rewrite — replace kernel P by P'.
pub fn p1_rewrite(kernel: &MarkovKernel, new_kernel: MarkovKernel) -> MarkovKernel {
    assert_eq!(
        kernel.n, new_kernel.n,
        "P1 rewrite must preserve state space size"
    );
    new_kernel
}

/// P1: Random perturbation rewrite — perturb kernel entries and renormalize.
pub fn p1_random_perturb(kernel: &MarkovKernel, strength: f64, seed: u64) -> MarkovKernel {
    let mut rng = ChaCha8Rng::seed_from_u64(seed);
    let n = kernel.n;
    let mut new_kernel = vec![vec![0.0; n]; n];
    for i in 0..n {
        let mut row_sum = 0.0;
        for j in 0..n {
            let perturb: f64 = rng.gen::<f64>() * strength;
            let val = (kernel.kernel[i][j] + perturb).max(0.0);
            new_kernel[i][j] = val;
            row_sum += val;
        }
        for j in 0..n {
            new_kernel[i][j] /= row_sum;
        }
    }
    MarkovKernel {
        n,
        kernel: new_kernel,
    }
}

/// P2: Gating — delete edges (set P_{ij} = 0) and renormalize.
/// `mask[i][j]` = true means keep the edge.
pub fn p2_gate(kernel: &MarkovKernel, mask: &[Vec<bool>]) -> MarkovKernel {
    let n = kernel.n;
    let mut new_kernel = vec![vec![0.0; n]; n];
    for i in 0..n {
        let mut row_sum = 0.0;
        for j in 0..n {
            if mask[i][j] {
                new_kernel[i][j] = kernel.kernel[i][j];
                row_sum += new_kernel[i][j];
            }
        }
        if row_sum > 0.0 {
            for j in 0..n {
                new_kernel[i][j] /= row_sum;
            }
        } else {
            // Self-loop if all edges deleted
            new_kernel[i][i] = 1.0;
        }
    }
    MarkovKernel {
        n,
        kernel: new_kernel,
    }
}

/// P2: Random gating — delete edges with probability p.
pub fn p2_random_gate(kernel: &MarkovKernel, delete_prob: f64, seed: u64) -> MarkovKernel {
    let mut rng = ChaCha8Rng::seed_from_u64(seed);
    let n = kernel.n;
    let mask: Vec<Vec<bool>> = (0..n)
        .map(|i| {
            (0..n)
                .map(|j| {
                    if i == j {
                        true // Always keep self-loops possible
                    } else {
                        rng.gen::<f64>() > delete_prob
                    }
                })
                .collect()
        })
        .collect();
    p2_gate(kernel, &mask)
}

/// P3: Autonomous protocol holonomy — route mismatch diagnostic.
/// Measures ||Pi_j(F(mu)) - F^sharp(Pi_j(mu))||_1
/// where F is evolve-by-tau, Pi_j is lens pushforward.
pub fn p3_route_mismatch(substrate: &Substrate, dist: &[f64]) -> f64 {
    // Route A: evolve then project
    let evolved = substrate.kernel.evolve(dist, substrate.tau);
    let route_a = substrate.lens.pushforward(&evolved);

    // Route B: project then evolve (induced macro dynamics)
    let projected = substrate.lens.pushforward(dist);
    // Lift back to micro, evolve, then project again
    let lifted = substrate.lens.lift(&projected, substrate.kernel.n);
    let evolved_lifted = substrate.kernel.evolve(&lifted, substrate.tau);
    let route_b = substrate.lens.pushforward(&evolved_lifted);

    // L1 distance
    route_a
        .iter()
        .zip(route_b.iter())
        .map(|(a, b)| (a - b).abs())
        .sum()
}

/// P4: Sector detection — find block structure of the kernel.
/// Returns a vector of sector labels for each state.
pub fn p4_sectors(kernel: &MarkovKernel) -> Vec<usize> {
    let n = kernel.n;
    let mut labels = vec![usize::MAX; n];
    let mut current_label = 0;
    for start in 0..n {
        if labels[start] != usize::MAX {
            continue;
        }
        let mut stack = vec![start];
        while let Some(node) = stack.pop() {
            if labels[node] != usize::MAX {
                continue;
            }
            labels[node] = current_label;
            for j in 0..n {
                if kernel.kernel[node][j] > 0.0 && labels[j] == usize::MAX {
                    stack.push(j);
                }
                if kernel.kernel[j][node] > 0.0 && labels[j] == usize::MAX {
                    stack.push(j);
                }
            }
        }
        current_label += 1;
    }
    labels
}

/// P5: Packaging — apply the packaging endomap and find fixed points.
/// Returns the packaged distribution (a fixed point of E).
pub fn p5_package(substrate: &Substrate, dist: &[f64], max_iter: usize, tol: f64) -> Vec<f64> {
    let mut current = dist.to_vec();
    for _ in 0..max_iter {
        let next = substrate.packaging_endomap(&current);
        let diff: f64 = current
            .iter()
            .zip(next.iter())
            .map(|(a, b)| (a - b).abs())
            .sum();
        current = next;
        if diff < tol {
            break;
        }
    }
    current
}

/// P6: Audit — compute path-reversal asymmetry (arrow-of-time).
pub fn p6_audit_sigma_t(kernel: &MarkovKernel, horizon: usize) -> f64 {
    let pi = kernel.stationary(10000, 1e-12);
    crate::substrate::path_reversal_asymmetry(kernel, &pi, horizon)
}

/// P6: Audit — compute ACC affinity for all simple cycles of length <= max_len.
pub fn p6_audit_acc_max(kernel: &MarkovKernel, max_cycle_len: usize) -> f64 {
    let n = kernel.n;
    let mut max_affinity: f64 = 0.0;

    // Check all 2-cycles (pairs)
    for i in 0..n {
        for j in (i + 1)..n {
            if kernel.kernel[i][j] > 1e-15 && kernel.kernel[j][i] > 1e-15 {
                let aff = (kernel.kernel[i][j] / kernel.kernel[j][i]).ln().abs();
                max_affinity = max_affinity.max(aff);
            }
        }
    }

    // Check 3-cycles if requested
    if max_cycle_len >= 3 {
        for i in 0..n {
            for j in 0..n {
                if j == i {
                    continue;
                }
                for k in 0..n {
                    if k == i || k == j {
                        continue;
                    }
                    let cycle = vec![i, j, k, i];
                    let aff = crate::substrate::acc_affinity(kernel, &cycle).abs();
                    max_affinity = max_affinity.max(aff);
                }
            }
        }
    }

    max_affinity
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::substrate::Lens;

    #[test]
    fn test_p2_gating_reduces_cycle_rank() {
        let k = MarkovKernel::random(8, 42);
        let rank_before = k.cycle_rank();
        let gated = p2_random_gate(&k, 0.5, 100);
        let rank_after = gated.cycle_rank();
        // Gating can only maintain or reduce cycle rank
        assert!(
            rank_after <= rank_before,
            "P2 gating increased cycle rank: {} -> {}",
            rank_before,
            rank_after
        );
    }

    #[test]
    fn test_p4_sectors_on_disconnected() {
        let mut k = MarkovKernel {
            n: 4,
            kernel: vec![vec![0.0; 4]; 4],
        };
        k.kernel[0][0] = 0.5;
        k.kernel[0][1] = 0.5;
        k.kernel[1][0] = 0.5;
        k.kernel[1][1] = 0.5;
        k.kernel[2][2] = 0.5;
        k.kernel[2][3] = 0.5;
        k.kernel[3][2] = 0.5;
        k.kernel[3][3] = 0.5;
        let sectors = p4_sectors(&k);
        assert_eq!(sectors[0], sectors[1]);
        assert_eq!(sectors[2], sectors[3]);
        assert_ne!(sectors[0], sectors[2]);
    }

    #[test]
    fn test_p5_packaging_converges() {
        let k = MarkovKernel::random(8, 42);
        let lens = Lens::modular(8, 4);
        let sub = Substrate::new(k, lens, 5);
        let dist = vec![0.125; 8];
        let packaged = p5_package(&sub, &dist, 100, 1e-10);
        let defect = sub.idempotence_defect(&packaged);
        assert!(defect < 1e-6, "Packaging defect too large: {}", defect);
    }

    #[test]
    fn test_p6_reversible_zero_sigma() {
        let k = MarkovKernel::random_reversible(8, 42);
        let sigma = p6_audit_sigma_t(&k, 10);
        assert!(sigma.abs() < 1e-6, "Reversible kernel Sigma_T = {}", sigma);
    }
}
