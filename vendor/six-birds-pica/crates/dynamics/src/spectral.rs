//! Spectral analysis: multi-eigenvector computation and k-way partitioning.
//!
//! Extends the single-eigenvector spectral bisection to k-way clustering
//! using sign patterns of the top-d eigenvectors (k = 2^d).

use six_primitives_core::substrate::MarkovKernel;

/// Compute the top-d eigenvectors of the kernel (beyond the stationary direction).
///
/// Uses sequential deflated power iteration with row-vector convention:
/// each iteration computes v·K (via `kernel.step(&v)`) and deflates the
/// stationary component. Gram-Schmidt orthogonalization is applied against
/// all previously found eigenvectors.
///
/// For kernels with real dominant eigenvalues (e.g., near-block-diagonal evolved
/// kernels), v2 converges to the true second eigenvector with machine precision.
/// For non-normal kernels with complex eigenvalue pairs, the method converges to
/// a real vector in the dominant invariant subspace, which may not be an exact
/// eigenvector (residuals can be O(0.1) for v3+).
///
/// Returns d eigenvectors [v2, v3, ..., v_{d+1}] in order of decreasing eigenvalue.
pub fn top_eigenvectors(kernel: &MarkovKernel, d: usize) -> Vec<Vec<f64>> {
    let n = kernel.n;
    if d == 0 || n <= 1 {
        return vec![];
    }

    let pi = kernel.stationary(10000, 1e-12);
    let mut eigvecs: Vec<Vec<f64>> = Vec::with_capacity(d);

    for idx in 0..d {
        // Initialize with a quasi-random vector (different for each eigenvector)
        let mut v = vec![0.0; n];
        let phi = 0.6180339887 * (idx + 1) as f64;
        for i in 0..n {
            v[i] = ((i as f64 * phi + 0.3).fract()) - 0.5;
        }
        let norm: f64 = v.iter().map(|x| x * x).sum::<f64>().sqrt();
        if norm < 1e-15 {
            continue;
        }
        for x in &mut v {
            *x /= norm;
        }

        for _ in 0..1000 {
            // Apply K via row-vector multiplication: v' = v·K
            let pv = kernel.step(&v);

            // Deflate: remove stationary component
            let sum_v: f64 = v.iter().sum();
            let mut deflated: Vec<f64> = pv
                .iter()
                .zip(pi.iter())
                .map(|(pv_i, pi_i)| pv_i - pi_i * sum_v)
                .collect();

            // Gram-Schmidt: remove components along previously found eigenvectors
            for prev_v in &eigvecs {
                let proj: f64 = deflated.iter().zip(prev_v.iter()).map(|(a, b)| a * b).sum();
                for i in 0..n {
                    deflated[i] -= proj * prev_v[i];
                }
            }

            let new_norm: f64 = deflated.iter().map(|x| x * x).sum::<f64>().sqrt();
            if new_norm < 1e-15 {
                break;
            }
            for x in &mut deflated {
                *x /= new_norm;
            }
            v = deflated;
        }

        eigvecs.push(v);
    }

    eigvecs
}

/// Compute a k-way spectral partition using sign patterns of top-d eigenvectors.
///
/// For k clusters, uses d = ceil(log2(k)) eigenvectors. Each state is assigned
/// a cluster index based on the signs of the eigenvector components:
///   cluster_id = sum_{j=0..d-1} (v_{j+2}[i] >= 0) * 2^j
///
/// To remain stable on non-reversible chains, this uses eigenvectors of the
/// symmetric similarity transform S_sym = (D^{1/2} K D^{-1/2} + transpose)/2.
/// This yields an orthogonal basis even when K is non-normal.
///
/// Empty clusters are compacted out (renumbered to fill gaps).
/// Returns a mapping from micro state to cluster index (0..actual_k).
pub fn spectral_partition(kernel: &MarkovKernel, k: usize) -> Vec<usize> {
    let n = kernel.n;
    if k <= 1 || n <= 1 {
        return vec![0; n];
    }

    // Number of eigenvectors needed: d = ceil(log2(k))
    let d = (k as f64).log2().ceil() as usize;
    let pi = kernel.stationary(10000, 1e-12);
    let mut sqrt_pi = vec![0.0; n];
    let mut inv_sqrt_pi = vec![0.0; n];
    let mut has_zero_pi = false;
    for i in 0..n {
        if pi[i] > 1e-30 {
            sqrt_pi[i] = pi[i].sqrt();
            inv_sqrt_pi[i] = 1.0 / sqrt_pi[i];
        } else {
            has_zero_pi = true;
        }
    }

    let eigvecs = if has_zero_pi {
        // Degenerate stationary mass (rare in dense kernels): use legacy fallback.
        top_eigenvectors(kernel, d)
    } else {
        let mut s_sym = vec![vec![0.0; n]; n];
        for i in 0..n {
            for j in 0..n {
                s_sym[i][j] = (sqrt_pi[i] * kernel.kernel[i][j] * inv_sqrt_pi[j]
                    + sqrt_pi[j] * kernel.kernel[j][i] * inv_sqrt_pi[i])
                    * 0.5;
            }
        }
        let (_eigs, vecs) = jacobi_eigen(&s_sym);
        let mut basis: Vec<Vec<f64>> = Vec::with_capacity(d);
        for idx in 1..(d + 1).min(vecs.len()) {
            let v = &vecs[idx];
            let u: Vec<f64> = (0..n).map(|i| v[i] * inv_sqrt_pi[i]).collect();
            basis.push(u);
        }
        if basis.is_empty() {
            top_eigenvectors(kernel, d)
        } else {
            basis
        }
    };

    if eigvecs.is_empty() {
        return vec![0; n];
    }

    // Assign cluster by sign pattern
    let actual_d = eigvecs.len(); // may be < d if eigenvectors are degenerate
    let raw_k = 1usize << actual_d;
    let mut raw_mapping = vec![0usize; n];
    for i in 0..n {
        let mut cluster = 0;
        for j in 0..actual_d {
            if eigvecs[j][i] >= 0.0 {
                cluster |= 1 << j;
            }
        }
        raw_mapping[i] = cluster;
    }

    // Compact: remove empty clusters and renumber 0..actual_k
    let mut used = vec![false; raw_k];
    for &c in &raw_mapping {
        used[c] = true;
    }
    let mut remap = vec![0usize; raw_k];
    let mut next_id = 0;
    for c in 0..raw_k {
        if used[c] {
            remap[c] = next_id;
            next_id += 1;
        }
    }

    let mapping: Vec<usize> = raw_mapping.iter().map(|&c| remap[c]).collect();
    mapping
}

/// Compute all eigenvalues of a small kernel (n <= 8).
/// Returns [1.0, lambda_2, lambda_3, ..., lambda_n] in decreasing order.
/// Uses existing top_eigenvectors + Rayleigh quotient.
pub fn full_eigenvalues(kernel: &MarkovKernel) -> Vec<f64> {
    let n = kernel.n;
    if n <= 1 {
        return vec![1.0];
    }
    let eigvecs = top_eigenvectors(kernel, n - 1);
    let mut eigenvalues = vec![1.0]; // lambda_1 = 1 always
    for v in &eigvecs {
        // Rayleigh quotient: lambda = v^T K^T v / (v^T v)
        // kernel.step(v) computes v^T K = (K^T v)^T
        let kv = kernel.step(&v);
        let dot: f64 = v.iter().zip(kv.iter()).map(|(a, b)| a * b).sum();
        let norm_sq: f64 = v.iter().map(|x| x * x).sum();
        eigenvalues.push(if norm_sq > 1e-30 { dot / norm_sq } else { 0.0 });
    }
    eigenvalues.sort_by(|a, b| b.partial_cmp(a).unwrap_or(std::cmp::Ordering::Equal));
    eigenvalues
}

/// Spectral locality: pi-weighted fraction of off-diagonal transition weight
/// going to eigenvector-adjacent states. States are ordered by the Fiedler vector
/// of the symmetrized similarity transform S = (D^{1/2} K D^{-1/2} + transpose) / 2,
/// where D = diag(π). This is a real symmetric matrix whose eigenvectors give
/// geometrically meaningful orderings even for non-reversible chains.
///
/// Uses Jacobi eigenvalue decomposition for exact results (practical for n ≤ ~50).
/// For n <= 2: returns 1.0 (trivially local).
pub fn spectral_locality(kernel: &MarkovKernel) -> f64 {
    let n = kernel.n;
    if n <= 2 {
        return 1.0;
    }

    let pi = kernel.stationary(10000, 1e-12);

    // Build symmetric matrix S_sym = (S + S^T) / 2 where S = D^{1/2} K D^{-1/2}
    let mut sqrt_pi = vec![0.0; n];
    let mut inv_sqrt_pi = vec![0.0; n];
    for i in 0..n {
        sqrt_pi[i] = pi[i].sqrt();
        inv_sqrt_pi[i] = if pi[i] > 1e-30 { 1.0 / sqrt_pi[i] } else { 0.0 };
    }

    let mut s_sym = vec![vec![0.0; n]; n];
    for i in 0..n {
        for j in 0..n {
            s_sym[i][j] = (sqrt_pi[i] * kernel.kernel[i][j] * inv_sqrt_pi[j]
                + sqrt_pi[j] * kernel.kernel[j][i] * inv_sqrt_pi[i])
                * 0.5;
        }
    }

    // Jacobi eigenvalue decomposition of the symmetric S_sym.
    // Returns eigenvalues and eigenvectors sorted by decreasing eigenvalue.
    let (eigenvalues, eigenvectors) = jacobi_eigen(&s_sym);

    // Fiedler vector = eigenvector for the 2nd largest eigenvalue
    if eigenvalues.len() < 2 {
        return 1.0;
    }
    let v2 = &eigenvectors[1]; // 0-indexed: [0]=largest, [1]=2nd largest

    // Convert back to state ordering: u_i = v_i / sqrt(π_i)
    let u: Vec<f64> = (0..n).map(|i| v2[i] * inv_sqrt_pi[i]).collect();

    let mut order: Vec<usize> = (0..n).collect();
    order.sort_by(|&a, &b| u[a].partial_cmp(&u[b]).unwrap_or(std::cmp::Ordering::Equal));
    let mut inv = vec![0usize; n];
    for (pos, &s) in order.iter().enumerate() {
        inv[s] = pos;
    }

    // Measure locality on the ORIGINAL kernel using the symmetric ordering
    let mut loc = 0.0;
    for i in 0..n {
        let (mut nb, mut od) = (0.0, 0.0);
        for j in 0..n {
            if i == j {
                continue;
            }
            let w = kernel.kernel[i][j];
            od += w;
            if (inv[i] as isize - inv[j] as isize).unsigned_abs() <= 1 {
                nb += w;
            }
        }
        if od > 1e-15 {
            loc += pi[i] * nb / od;
        }
    }
    loc
}

/// Jacobi eigenvalue decomposition for a real symmetric matrix.
/// Returns (eigenvalues, eigenvectors) sorted by decreasing eigenvalue.
/// Each eigenvector is a Vec<f64> of length n.
pub fn jacobi_eigen(a: &[Vec<f64>]) -> (Vec<f64>, Vec<Vec<f64>>) {
    let n = a.len();
    let mut m = a.to_vec(); // working copy
                            // V starts as identity — accumulates rotations
    let mut v: Vec<Vec<f64>> = (0..n)
        .map(|i| {
            let mut row = vec![0.0; n];
            row[i] = 1.0;
            row
        })
        .collect();

    for _ in 0..100 * n * n {
        // Find largest off-diagonal element
        let (mut max_val, mut p, mut q) = (0.0, 0, 1);
        for i in 0..n {
            for j in (i + 1)..n {
                if m[i][j].abs() > max_val {
                    max_val = m[i][j].abs();
                    p = i;
                    q = j;
                }
            }
        }
        if max_val < 1e-14 {
            break;
        } // converged

        // Compute rotation angle
        let theta = if (m[p][p] - m[q][q]).abs() < 1e-30 {
            std::f64::consts::FRAC_PI_4
        } else {
            // Sign convention must match the Givens update below (M' = G^T M G).
            // Using (m[p][p] - m[q][q]) here rotates in the wrong direction and
            // can *increase* the target off-diagonal entry instead of eliminating it.
            0.5 * (2.0 * m[p][q] / (m[q][q] - m[p][p])).atan()
        };
        let (s, c) = theta.sin_cos();

        // Apply Givens rotation to M: M' = G^T M G
        // Update rows/columns p and q
        let mut new_mp = vec![0.0; n];
        let mut new_mq = vec![0.0; n];
        for k in 0..n {
            new_mp[k] = c * m[p][k] - s * m[q][k];
            new_mq[k] = s * m[p][k] + c * m[q][k];
        }
        for k in 0..n {
            m[p][k] = new_mp[k];
            m[q][k] = new_mq[k];
        }
        // Update columns
        for k in 0..n {
            let mp_k = m[k][p];
            let mq_k = m[k][q];
            m[k][p] = c * mp_k - s * mq_k;
            m[k][q] = s * mp_k + c * mq_k;
        }

        // Accumulate rotation in V
        for k in 0..n {
            let vp = v[k][p];
            let vq = v[k][q];
            v[k][p] = c * vp - s * vq;
            v[k][q] = s * vp + c * vq;
        }
    }

    // Extract eigenvalues (diagonal of M) and sort by decreasing value
    let mut eigen_pairs: Vec<(f64, Vec<f64>)> = (0..n)
        .map(|i| {
            let eigvec: Vec<f64> = (0..n).map(|k| v[k][i]).collect();
            (m[i][i], eigvec)
        })
        .collect();
    eigen_pairs.sort_by(|a, b| b.0.partial_cmp(&a.0).unwrap_or(std::cmp::Ordering::Equal));

    let eigenvalues: Vec<f64> = eigen_pairs.iter().map(|(e, _)| *e).collect();
    let eigenvectors: Vec<Vec<f64>> = eigen_pairs.into_iter().map(|(_, v)| v).collect();
    (eigenvalues, eigenvectors)
}

/// Count the number of distinct clusters in a partition.
pub fn n_clusters(partition: &[usize]) -> usize {
    if partition.is_empty() {
        return 0;
    }
    *partition.iter().max().unwrap() + 1
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_bisection_gives_two_clusters() {
        let k = MarkovKernel::random(32, 42);
        let part = spectral_partition(&k, 2);
        assert_eq!(part.len(), 32);
        let nc = n_clusters(&part);
        assert_eq!(
            nc, 2,
            "Bisection should give exactly 2 clusters, got {}",
            nc
        );
    }

    #[test]
    fn test_4way_gives_up_to_4_clusters() {
        let k = MarkovKernel::random(64, 42);
        let part = spectral_partition(&k, 4);
        let nc = n_clusters(&part);
        assert!(
            nc >= 2 && nc <= 4,
            "4-way should give 2-4 clusters, got {}",
            nc
        );
    }

    #[test]
    fn test_8way_gives_multiple_clusters() {
        let k = MarkovKernel::random(64, 42);
        let part = spectral_partition(&k, 8);
        let nc = n_clusters(&part);
        assert!(nc >= 2, "8-way should give at least 2 clusters, got {}", nc);
    }

    #[test]
    fn test_top_eigenvectors_count() {
        let k = MarkovKernel::random(32, 42);
        let evs = top_eigenvectors(&k, 3);
        assert_eq!(evs.len(), 3, "Should return 3 eigenvectors");
        for ev in &evs {
            assert_eq!(ev.len(), 32);
            // Should be approximately unit length
            let norm: f64 = ev.iter().map(|x| x * x).sum::<f64>().sqrt();
            assert!(
                (norm - 1.0).abs() < 0.01,
                "Eigenvector should be unit length, got {}",
                norm
            );
        }
    }

    #[test]
    fn test_spectral_locality_1d_chain() {
        // 1D chain: 0↔1↔2↔3 with strong nearest-neighbor transitions
        let mut k = MarkovKernel {
            n: 4,
            kernel: vec![vec![0.0; 4]; 4],
        };
        k.kernel[0] = vec![0.1, 0.9, 0.0, 0.0];
        k.kernel[1] = vec![0.45, 0.1, 0.45, 0.0];
        k.kernel[2] = vec![0.0, 0.45, 0.1, 0.45];
        k.kernel[3] = vec![0.0, 0.0, 0.9, 0.1];
        let loc = spectral_locality(&k);
        assert!(
            loc > 0.95,
            "1D chain should have locality ≈ 1.0, got {}",
            loc
        );
    }

    #[test]
    fn test_spectral_locality_random_kernel() {
        // Random kernel should have low locality (near baseline 2/(n-1))
        let k = MarkovKernel::random(32, 42);
        let loc = spectral_locality(&k);
        let baseline = 2.0 / 31.0;
        // Should be in a reasonable range — not necessarily at baseline for random,
        // but certainly much lower than a 1D chain
        assert!(
            loc < 0.5,
            "Random n=32 should have low locality, got {}",
            loc
        );
        assert!(loc >= 0.0, "Locality should be non-negative, got {}", loc);
        eprintln!(
            "Random n=32 locality: {:.6} (baseline: {:.6})",
            loc, baseline
        );
    }

    #[test]
    fn test_spectral_locality_near_identity() {
        // Near-identity n=4 kernel — Jacobi should handle clustered eigenvalues
        let mut k = MarkovKernel {
            n: 4,
            kernel: vec![vec![0.0; 4]; 4],
        };
        k.kernel[0] = vec![0.99, 0.005, 0.003, 0.002];
        k.kernel[1] = vec![0.006, 0.98, 0.009, 0.005];
        k.kernel[2] = vec![0.002, 0.008, 0.985, 0.005];
        k.kernel[3] = vec![0.003, 0.004, 0.006, 0.987];
        let loc = spectral_locality(&k);
        // Python exact (numpy eigh) gives 0.649902
        assert!(
            (loc - 0.6499).abs() < 0.01,
            "Near-identity n=4 should have locality ≈ 0.65, got {}",
            loc
        );
    }

    #[test]
    fn test_jacobi_diagonalizes_known_2x2() {
        // Symmetric matrix with known eigenvalues:
        // [[3, 1], [1, 0]] -> (3 +/- sqrt(13)) / 2
        let a = vec![vec![3.0, 1.0], vec![1.0, 0.0]];
        let (eigs, vecs) = jacobi_eigen(&a);
        assert_eq!(eigs.len(), 2);
        assert_eq!(vecs.len(), 2);

        let expected_hi = (3.0 + 13.0_f64.sqrt()) * 0.5;
        let expected_lo = (3.0 - 13.0_f64.sqrt()) * 0.5;
        assert!(
            (eigs[0] - expected_hi).abs() < 1e-9,
            "Top eigenvalue mismatch: got {}, expected {}",
            eigs[0],
            expected_hi
        );
        assert!(
            (eigs[1] - expected_lo).abs() < 1e-9,
            "Second eigenvalue mismatch: got {}, expected {}",
            eigs[1],
            expected_lo
        );

        // Residual check: A v = lambda v for each returned eigenpair.
        for idx in 0..2 {
            let lam = eigs[idx];
            let v = &vecs[idx];
            let av0 = a[0][0] * v[0] + a[0][1] * v[1];
            let av1 = a[1][0] * v[0] + a[1][1] * v[1];
            let r0 = av0 - lam * v[0];
            let r1 = av1 - lam * v[1];
            let res = (r0 * r0 + r1 * r1).sqrt();
            assert!(
                res < 1e-9,
                "Eigen residual too large for idx {}: {}",
                idx,
                res
            );
        }
    }

    #[test]
    fn test_jacobi_reduces_offdiag_on_symmetric_3x3() {
        let a = vec![
            vec![2.0, 0.7, -0.4],
            vec![0.7, 1.0, 0.2],
            vec![-0.4, 0.2, 0.5],
        ];
        let (_eigs, vecs) = jacobi_eigen(&a);
        // Reconstruct V^T A V and ensure it is approximately diagonal.
        let n = a.len();
        let mut d = vec![vec![0.0; n]; n];
        for i in 0..n {
            for j in 0..n {
                let mut sum = 0.0;
                for p in 0..n {
                    for q in 0..n {
                        sum += vecs[i][p] * a[p][q] * vecs[j][q];
                    }
                }
                d[i][j] = sum;
            }
        }
        let mut max_off = 0.0_f64;
        for i in 0..n {
            for j in 0..n {
                if i != j {
                    max_off = max_off.max(d[i][j].abs());
                }
            }
        }
        assert!(
            max_off < 1e-8,
            "Jacobi did not diagonalize: max offdiag {}",
            max_off
        );
    }
}
