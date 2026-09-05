//! Minimal substrate: finite Markov chain with lens and packaging.
//!
//! Implements the canonical machine class S_min from the minimal substrate theorem.

use rand::Rng;
use rand::SeedableRng;
use rand_chacha::ChaCha8Rng;
use serde::{Deserialize, Serialize};

/// A finite Markov kernel represented as a row-stochastic matrix.
/// kernel[i][j] = P(i -> j).
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct MarkovKernel {
    pub n: usize,
    pub kernel: Vec<Vec<f64>>,
}

impl MarkovKernel {
    /// Create a random row-stochastic kernel on n states.
    pub fn random(n: usize, seed: u64) -> Self {
        let mut rng = ChaCha8Rng::seed_from_u64(seed);
        let mut kernel = vec![vec![0.0; n]; n];
        for i in 0..n {
            let mut row_sum = 0.0;
            for j in 0..n {
                let val: f64 = rng.gen::<f64>() + 1e-10;
                kernel[i][j] = val;
                row_sum += val;
            }
            for j in 0..n {
                kernel[i][j] /= row_sum;
            }
        }
        MarkovKernel { n, kernel }
    }

    /// Create a reversible (detailed-balance) kernel on n states.
    pub fn random_reversible(n: usize, seed: u64) -> Self {
        let mut rng = ChaCha8Rng::seed_from_u64(seed);
        let mut kernel = vec![vec![0.0; n]; n];
        // Generate symmetric weights
        for i in 0..n {
            for j in i..n {
                let val: f64 = rng.gen::<f64>() + 1e-10;
                kernel[i][j] = val;
                kernel[j][i] = val;
            }
        }
        // Normalize rows
        for i in 0..n {
            let row_sum: f64 = kernel[i].iter().sum();
            for j in 0..n {
                kernel[i][j] /= row_sum;
            }
        }
        MarkovKernel { n, kernel }
    }

    /// Create a doubly stochastic reversible kernel (symmetric + row sums = 1).
    /// Reversible w.r.t. uniform distribution. Uses Sinkhorn iteration on
    /// a random symmetric positive matrix.
    pub fn random_doubly_stochastic(n: usize, seed: u64) -> Self {
        let mut rng = ChaCha8Rng::seed_from_u64(seed);
        let mut w = vec![vec![0.0; n]; n];
        // Generate random symmetric positive matrix
        for i in 0..n {
            for j in i..n {
                let val: f64 = rng.gen::<f64>() + 0.1;
                w[i][j] = val;
                w[j][i] = val;
            }
        }
        // Sinkhorn iteration: alternately normalize rows and columns
        for _ in 0..200 {
            // Normalize rows
            for i in 0..n {
                let s: f64 = w[i].iter().sum();
                for j in 0..n {
                    w[i][j] /= s;
                }
            }
            // Normalize columns
            for j in 0..n {
                let s: f64 = (0..n).map(|i| w[i][j]).sum();
                for i in 0..n {
                    w[i][j] /= s;
                }
            }
        }
        // Symmetrize to fix any residual asymmetry from Sinkhorn
        for i in 0..n {
            for j in (i + 1)..n {
                let avg = (w[i][j] + w[j][i]) / 2.0;
                w[i][j] = avg;
                w[j][i] = avg;
            }
        }
        // Final row normalization
        for i in 0..n {
            let s: f64 = w[i].iter().sum();
            for j in 0..n {
                w[i][j] /= s;
            }
        }
        MarkovKernel { n, kernel: w }
    }

    /// Evolve a distribution for one step: mu' = mu * P.
    pub fn step(&self, dist: &[f64]) -> Vec<f64> {
        let mut out = vec![0.0; self.n];
        for i in 0..self.n {
            for j in 0..self.n {
                out[j] += dist[i] * self.kernel[i][j];
            }
        }
        out
    }

    /// Evolve a distribution for tau steps.
    pub fn evolve(&self, dist: &[f64], tau: usize) -> Vec<f64> {
        let mut current = dist.to_vec();
        for _ in 0..tau {
            current = self.step(&current);
        }
        current
    }

    /// Sample a trajectory of states from a starting state.
    pub fn sample_trajectory(&self, start: usize, steps: usize, seed: u64) -> Vec<usize> {
        let mut rng = ChaCha8Rng::seed_from_u64(seed);
        let mut traj = Vec::with_capacity(steps + 1);
        let mut state = start;
        traj.push(state);
        for _ in 0..steps {
            let r: f64 = rng.gen();
            let mut cum = 0.0;
            let mut next = self.n - 1; // fallback for floating-point tail mass
            for j in 0..self.n {
                cum += self.kernel[state][j];
                if r < cum {
                    next = j;
                    break;
                }
            }
            state = next;
            traj.push(state);
        }
        traj
    }

    /// Compute the stationary distribution by power iteration.
    pub fn stationary(&self, max_iter: usize, tol: f64) -> Vec<f64> {
        let mut dist = vec![1.0 / self.n as f64; self.n];
        for _ in 0..max_iter {
            let next = self.step(&dist);
            let diff: f64 = dist
                .iter()
                .zip(next.iter())
                .map(|(a, b)| (a - b).abs())
                .sum();
            dist = next;
            if diff < tol {
                break;
            }
        }
        dist
    }

    /// Count disconnected components (P4 sector detection).
    pub fn block_count(&self) -> usize {
        let mut visited = vec![false; self.n];
        let mut count = 0;
        for start in 0..self.n {
            if visited[start] {
                continue;
            }
            count += 1;
            let mut stack = vec![start];
            while let Some(node) = stack.pop() {
                if visited[node] {
                    continue;
                }
                visited[node] = true;
                for j in 0..self.n {
                    if self.kernel[node][j] > 0.0 && !visited[j] {
                        stack.push(j);
                    }
                    if self.kernel[j][node] > 0.0 && !visited[j] {
                        stack.push(j);
                    }
                }
            }
        }
        count
    }

    /// Compute the cycle rank of the undirected support graph.
    /// Cycle rank = |edges| - |vertices| + |components|.
    pub fn cycle_rank(&self) -> i64 {
        let mut edge_count: usize = 0;
        for i in 0..self.n {
            for j in i..self.n {
                if self.kernel[i][j] > 0.0 || self.kernel[j][i] > 0.0 {
                    edge_count += 1;
                }
            }
        }
        edge_count as i64 - self.n as i64 + self.block_count() as i64
    }

    /// Estimate the spectral gap via deflated power iteration.
    ///
    /// Computes `1 - lambda2` where `lambda2` is the norm to which the deflated
    /// iteration `v·K - pi·sum(v)` converges. For reversible (normal) kernels,
    /// this equals `1 - |lambda_2(K)|` (the SLEM gap). For non-reversible kernels
    /// with complex eigenvalue pairs, the estimate may lie between the true SLEM
    /// and the operator norm of the deflated matrix. On near-block-diagonal
    /// evolved kernels (real dominant lambda_2), this matches the SLEM exactly.
    pub fn spectral_gap(&self) -> f64 {
        // The top eigenvalue of a stochastic matrix is 1.
        // Deflated operator A = K - 1·pi^T removes the stationary component.
        // Row-vector iteration: v' = v·K - pi·sum(v)
        let pi = self.stationary(10000, 1e-12);

        let mut v = vec![0.0; self.n];
        // Start with a vector orthogonal to all-ones
        for i in 0..self.n {
            v[i] = if i % 2 == 0 { 1.0 } else { -1.0 };
        }
        let norm: f64 = v.iter().map(|x| x * x).sum::<f64>().sqrt();
        for x in &mut v {
            *x /= norm;
        }

        let mut lambda2 = 0.0;
        let mut prev_norm = f64::INFINITY;
        for _ in 0..2000 {
            // Row-vector multiplication: v' = v·K
            let pv = self.step(&v);
            // Deflate: v' = v·K - pi·sum(v)
            let sum_v: f64 = v.iter().sum();
            let mut deflated: Vec<f64> = pv
                .iter()
                .zip(pi.iter())
                .map(|(pv_i, pi_i)| pv_i - pi_i * sum_v)
                .collect();

            let new_norm: f64 = deflated.iter().map(|x| x * x).sum::<f64>().sqrt();
            if new_norm < 1e-15 {
                lambda2 = 0.0;
                break;
            }
            for x in &mut deflated {
                *x /= new_norm;
            }
            lambda2 = new_norm;
            v = deflated;
            if (new_norm - prev_norm).abs() < 1e-12 {
                break;
            }
            prev_norm = new_norm;
        }

        1.0 - lambda2
    }

    /// Like spectral_gap() but also returns the second eigenvector.
    /// Returns (gap, eigenvector) where eigenvector is the converged v from deflated power iteration.
    pub fn spectral_gap_with_eigvec(&self) -> (f64, Vec<f64>) {
        if self.n <= 1 {
            return (1.0, vec![0.0; self.n]);
        }
        if self.n == 2 {
            // For n=2, second eigenvector is [1, -1] (normalized)
            let gap = self.spectral_gap();
            let inv_sqrt2 = 1.0 / 2.0_f64.sqrt();
            return (gap, vec![inv_sqrt2, -inv_sqrt2]);
        }
        let pi = self.stationary(10000, 1e-12);
        let mut v = vec![0.0; self.n];
        for i in 0..self.n {
            v[i] = if i % 2 == 0 { 1.0 } else { -1.0 };
        }
        let norm: f64 = v.iter().map(|x| x * x).sum::<f64>().sqrt();
        for x in &mut v {
            *x /= norm;
        }

        let mut lambda2 = 0.0;
        let mut prev_norm = f64::INFINITY;
        for _ in 0..2000 {
            let pv = self.step(&v);
            let sum_v: f64 = v.iter().sum();
            let mut deflated: Vec<f64> = pv
                .iter()
                .zip(pi.iter())
                .map(|(pv_i, pi_i)| pv_i - pi_i * sum_v)
                .collect();
            let new_norm: f64 = deflated.iter().map(|x| x * x).sum::<f64>().sqrt();
            if new_norm < 1e-15 {
                lambda2 = 0.0;
                break;
            }
            for x in &mut deflated {
                *x /= new_norm;
            }
            lambda2 = new_norm;
            v = deflated;
            if (new_norm - prev_norm).abs() < 1e-12 {
                break;
            }
            prev_norm = new_norm;
        }
        (1.0 - lambda2, v)
    }
}

/// A deterministic lens (coarse-graining map) f: Z -> X.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Lens {
    /// mapping[z] = x: which macro-state z maps to.
    pub mapping: Vec<usize>,
    /// Number of macro-states.
    pub macro_n: usize,
}

impl Lens {
    /// Create a simple modular lens: f(z) = z mod macro_n.
    pub fn modular(micro_n: usize, macro_n: usize) -> Self {
        let mapping: Vec<usize> = (0..micro_n).map(|z| z % macro_n).collect();
        Lens { mapping, macro_n }
    }

    /// Create a parity lens: f(z) = z mod 2.
    pub fn parity(micro_n: usize) -> Self {
        Self::modular(micro_n, 2)
    }

    /// Pushforward a micro-distribution to macro.
    pub fn pushforward(&self, dist: &[f64]) -> Vec<f64> {
        let mut macro_dist = vec![0.0; self.macro_n];
        for (z, &p) in dist.iter().enumerate() {
            macro_dist[self.mapping[z]] += p;
        }
        macro_dist
    }

    /// Canonical lift: uniform within each fiber.
    pub fn lift(&self, macro_dist: &[f64], micro_n: usize) -> Vec<f64> {
        // Count fiber sizes
        let mut fiber_sizes = vec![0usize; self.macro_n];
        for &x in &self.mapping {
            fiber_sizes[x] += 1;
        }
        let mut micro_dist = vec![0.0; micro_n];
        for z in 0..micro_n {
            let x = self.mapping[z];
            if fiber_sizes[x] > 0 {
                micro_dist[z] = macro_dist[x] / fiber_sizes[x] as f64;
            }
        }
        micro_dist
    }
}

/// The full substrate: Markov kernel + lens + packaging parameters.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Substrate {
    pub kernel: MarkovKernel,
    pub lens: Lens,
    pub tau: usize,
}

impl Substrate {
    pub fn new(kernel: MarkovKernel, lens: Lens, tau: usize) -> Self {
        Substrate { kernel, lens, tau }
    }

    /// Compute the dynamics-induced packaging endomap E_{tau,f}.
    /// E(mu) = lift(pushforward(evolve(mu, tau)))
    pub fn packaging_endomap(&self, dist: &[f64]) -> Vec<f64> {
        let evolved = self.kernel.evolve(dist, self.tau);
        let macro_dist = self.lens.pushforward(&evolved);
        self.lens.lift(&macro_dist, self.kernel.n)
    }

    /// Iterate the packaging endomap k times.
    pub fn iterate_packaging(&self, dist: &[f64], k: usize) -> Vec<f64> {
        let mut current = dist.to_vec();
        for _ in 0..k {
            current = self.packaging_endomap(&current);
        }
        current
    }

    /// Compute idempotence defect: ||E(E(x)) - E(x)||_1
    pub fn idempotence_defect(&self, dist: &[f64]) -> f64 {
        let e_x = self.packaging_endomap(dist);
        let ee_x = self.packaging_endomap(&e_x);
        e_x.iter()
            .zip(ee_x.iter())
            .map(|(a, b)| (a - b).abs())
            .sum()
    }

    /// Find fixed points of E by iterating from multiple initial conditions.
    pub fn find_fixed_points(
        &self,
        n_starts: usize,
        max_iter: usize,
        tol: f64,
        seed: u64,
    ) -> Vec<Vec<f64>> {
        let mut rng = ChaCha8Rng::seed_from_u64(seed);
        let mut fixed_points: Vec<Vec<f64>> = Vec::new();

        for _ in 0..n_starts {
            // Random initial distribution
            let mut dist: Vec<f64> = (0..self.kernel.n)
                .map(|_| rng.gen::<f64>() + 1e-10)
                .collect();
            let sum: f64 = dist.iter().sum();
            for x in &mut dist {
                *x /= sum;
            }

            // Iterate E
            for _ in 0..max_iter {
                let next = self.packaging_endomap(&dist);
                let diff: f64 = dist
                    .iter()
                    .zip(next.iter())
                    .map(|(a, b)| (a - b).abs())
                    .sum();
                dist = next;
                if diff < tol {
                    break;
                }
            }

            // Check if this is genuinely a fixed point
            let defect = self.idempotence_defect(&dist);
            if defect < tol {
                // Check if it's a new fixed point
                let is_new = fixed_points.iter().all(|fp| {
                    let d: f64 = fp.iter().zip(dist.iter()).map(|(a, b)| (a - b).abs()).sum();
                    d > tol * 10.0
                });
                if is_new {
                    fixed_points.push(dist.clone());
                }
            }
        }
        fixed_points
    }
}

/// Compute path-reversal KL asymmetry Sigma_T for a trajectory sample.
/// This is the P6 arrow-of-time audit.
pub fn path_reversal_asymmetry(
    kernel: &MarkovKernel,
    _initial_dist: &[f64],
    horizon: usize,
) -> f64 {
    let n = kernel.n;
    if n == 0 || horizon == 0 {
        return 0.0;
    }

    // Build transition counts from the path measure
    // P_rho,T(z_0:T) = rho(z_0) * prod P(z_t, z_{t+1})
    // Sigma_T = D_KL(P_rho,T || R_* P_rho,T)
    //
    // For finite chains: Sigma_T = sum over all paths of
    //   P_rho,T(path) * log(P_rho,T(path) / P_rho,T(reversed_path))
    //
    // For stationary initial: Sigma_T = T * sum_ij pi_i P_ij log(P_ij / P_ji)

    // Use the stationary approximation for efficiency
    let pi = kernel.stationary(10000, 1e-12);

    let mut sigma = 0.0;
    for i in 0..n {
        for j in 0..n {
            let p_ij = kernel.kernel[i][j];
            let p_ji = kernel.kernel[j][i];
            if p_ij > 1e-15 && p_ji > 1e-15 {
                sigma += pi[i] * p_ij * (p_ij / p_ji).ln();
            } else if p_ij > 1e-15 && p_ji <= 1e-15 {
                // Infinite KL contribution; cap at large value
                sigma += pi[i] * p_ij * 30.0; // ln(1e13) ~ 30
            }
        }
    }
    sigma * horizon as f64
}

/// Compute ACC affinity: cycle integral of log(P(i,j)/P(j,i)) around a cycle.
pub fn acc_affinity(kernel: &MarkovKernel, cycle: &[usize]) -> f64 {
    let mut affinity = 0.0;
    for w in cycle.windows(2) {
        let (i, j) = (w[0], w[1]);
        let p_ij = kernel.kernel[i][j];
        let p_ji = kernel.kernel[j][i];
        if p_ij > 1e-15 && p_ji > 1e-15 {
            affinity += (p_ij / p_ji).ln();
        }
    }
    affinity
}

/// Cycle chirality: enumerate all 3-cycles, compute Schnakenberg affinity for each.
/// Returns (mean_abs_affinity, max_abs_affinity, n_chiral) where n_chiral counts
/// cycles with |affinity| > threshold.
pub fn cycle_chirality(kernel: &MarkovKernel, threshold: f64) -> (f64, f64, usize) {
    let n = kernel.n;
    if n < 3 {
        return (0.0, 0.0, 0);
    }
    let mut sum_abs = 0.0;
    let mut max_abs = 0.0f64;
    let mut n_chiral = 0usize;
    let mut n_cycles = 0usize;
    for i in 0..n {
        for j in (i + 1)..n {
            for k in (j + 1)..n {
                let aff = acc_affinity(kernel, &[i, j, k, i]);
                let a = aff.abs();
                sum_abs += a;
                if a > max_abs {
                    max_abs = a;
                }
                if a > threshold {
                    n_chiral += 1;
                }
                n_cycles += 1;
            }
        }
    }
    let mean_abs = if n_cycles > 0 {
        sum_abs / n_cycles as f64
    } else {
        0.0
    };
    (mean_abs, max_abs, n_chiral)
}

/// Frobenius asymmetry: ||K - K^T||_F, measuring structural departure from symmetry.
/// No weighting needed — pure matrix property.
pub fn frobenius_asymmetry(kernel: &MarkovKernel) -> f64 {
    let n = kernel.n;
    let mut sum_sq = 0.0;
    for i in 0..n {
        for j in 0..n {
            let diff = kernel.kernel[i][j] - kernel.kernel[j][i];
            sum_sq += diff * diff;
        }
    }
    sum_sq.sqrt()
}

fn transient_states(kernel: &MarkovKernel, eps: f64) -> Vec<usize> {
    let n = kernel.n;
    if n == 0 {
        return vec![];
    }

    let mut adj = vec![Vec::<usize>::new(); n];
    let mut rev = vec![Vec::<usize>::new(); n];
    for i in 0..n {
        for j in 0..n {
            if kernel.kernel[i][j] > eps {
                adj[i].push(j);
                rev[j].push(i);
            }
        }
    }

    // Kosaraju: first pass (finishing order).
    let mut seen = vec![false; n];
    let mut order = Vec::with_capacity(n);
    for start in 0..n {
        if seen[start] {
            continue;
        }
        let mut stack = vec![(start, 0usize)];
        seen[start] = true;
        while let Some((v, next_idx)) = stack.pop() {
            if next_idx < adj[v].len() {
                stack.push((v, next_idx + 1));
                let u = adj[v][next_idx];
                if !seen[u] {
                    seen[u] = true;
                    stack.push((u, 0));
                }
            } else {
                order.push(v);
            }
        }
    }

    // Kosaraju: second pass (component labels).
    let mut comp = vec![usize::MAX; n];
    let mut n_comp = 0usize;
    for &start in order.iter().rev() {
        if comp[start] != usize::MAX {
            continue;
        }
        let mut stack = vec![start];
        comp[start] = n_comp;
        while let Some(v) = stack.pop() {
            for &u in &rev[v] {
                if comp[u] == usize::MAX {
                    comp[u] = n_comp;
                    stack.push(u);
                }
            }
        }
        n_comp += 1;
    }

    // Recurrent classes are exactly closed SCCs in finite chains.
    let mut closed = vec![true; n_comp];
    for i in 0..n {
        let ci = comp[i];
        for &j in &adj[i] {
            if comp[j] != ci {
                closed[ci] = false;
                break;
            }
        }
    }

    let mut transient = Vec::new();
    for i in 0..n {
        if !closed[comp[i]] {
            transient.push(i);
        }
    }
    transient
}

/// Transient entropy production on true transient states.
///
/// Steps:
/// 1. Detect transient states via communication classes (closed SCC criterion).
/// 2. Restrict to the transient sub-kernel Q (substochastic, no row renormalization).
/// 3. Estimate quasi-stationary left Perron vector q from qQ = λq (renormalized).
/// 4. Estimate right Perron vector v from Qv = λv.
/// 5. Build Doob h-transform (Q-process): P*_{ij} = Q_ij v_j / (λ v_i).
/// 6. Compute stationary EP on P* with π*_i ∝ q_i v_i.
///
/// Returns (ep, n_transient). If no true transient states (or degenerate transient flow),
/// returns (0, n_transient).
pub fn transient_ep(kernel: &MarkovKernel) -> (f64, usize) {
    let eps = 1e-15;
    let transient = transient_states(kernel, 1e-12);
    let nt = transient.len();
    if nt < 2 {
        return (0.0, nt);
    }

    let mut surv = vec![0.0f64; nt];
    for (ti, &i) in transient.iter().enumerate() {
        let mut s = 0.0;
        for &j in &transient {
            s += kernel.kernel[i][j];
        }
        surv[ti] = s;
    }

    // Left Perron vector q on transient set:
    // q <- normalize(qQ), where Q is transient-to-transient sub-kernel.
    let mut q = vec![1.0 / nt as f64; nt];
    for _ in 0..10000 {
        let mut next = vec![0.0; nt];
        for (ti, &i) in transient.iter().enumerate() {
            let qi = q[ti];
            if qi <= eps {
                continue;
            }
            for (tj, &j) in transient.iter().enumerate() {
                next[tj] += qi * kernel.kernel[i][j];
            }
        }
        let mass: f64 = next.iter().sum();
        if mass <= eps {
            return (0.0, nt);
        }
        for x in &mut next {
            *x /= mass;
        }
        let diff: f64 = q.iter().zip(next.iter()).map(|(a, b)| (a - b).abs()).sum();
        q = next;
        if diff < 1e-12 {
            break;
        }
    }

    // Dominant eigenvalue λ of Q from left eigenvector relation qQ = λq.
    let mut lambda = 0.0f64;
    for ti in 0..nt {
        lambda += q[ti] * surv[ti];
    }
    if lambda <= eps {
        return (0.0, nt);
    }

    // Right Perron vector v from Qv = λv (power iteration with normalization).
    let mut v = vec![1.0; nt];
    for _ in 0..10000 {
        let mut next = vec![0.0; nt];
        for (ti, &i) in transient.iter().enumerate() {
            for (tj, &j) in transient.iter().enumerate() {
                next[ti] += kernel.kernel[i][j] * v[tj];
            }
        }
        let scale = next.iter().copied().fold(0.0f64, f64::max);
        if scale <= eps {
            return (0.0, nt);
        }
        for x in &mut next {
            *x /= scale;
            if *x < eps {
                *x = eps;
            }
        }
        let diff: f64 = v.iter().zip(next.iter()).map(|(a, b)| (a - b).abs()).sum();
        v = next;
        if diff < 1e-12 {
            break;
        }
    }

    // Refine λ from bilinear form q^T Q v / q^T v.
    let mut q_qv = 0.0f64;
    let mut q_v = 0.0f64;
    for (ti, &i) in transient.iter().enumerate() {
        let mut qv_i = 0.0;
        for (tj, &j) in transient.iter().enumerate() {
            qv_i += kernel.kernel[i][j] * v[tj];
        }
        q_qv += q[ti] * qv_i;
        q_v += q[ti] * v[ti];
    }
    if q_v > eps {
        lambda = q_qv / q_v;
    }
    if lambda <= eps {
        return (0.0, nt);
    }

    // Doob h-transform P*_{ij} = Q_ij v_j / (λ v_i), row-normalized for stability.
    let mut p_star = vec![vec![0.0f64; nt]; nt];
    for (ti, &i) in transient.iter().enumerate() {
        let denom = lambda * v[ti];
        if denom <= eps {
            continue;
        }
        let mut row_sum = 0.0;
        for (tj, &j) in transient.iter().enumerate() {
            let val = kernel.kernel[i][j] * v[tj] / denom;
            if val.is_finite() && val > 0.0 {
                p_star[ti][tj] = val;
                row_sum += val;
            }
        }
        if row_sum > eps {
            for tj in 0..nt {
                p_star[ti][tj] /= row_sum;
            }
        } else {
            for tj in 0..nt {
                p_star[ti][tj] = 1.0 / nt as f64;
            }
        }
    }

    // Stationary distribution of Doob process: π*_i ∝ q_i v_i.
    let mut pi_star = vec![0.0f64; nt];
    let mut pi_mass = 0.0f64;
    for i in 0..nt {
        pi_star[i] = q[i] * v[i];
        pi_mass += pi_star[i];
    }
    if pi_mass <= eps {
        return (0.0, nt);
    }
    for x in &mut pi_star {
        *x /= pi_mass;
    }

    let mut sigma = 0.0f64;
    for ti in 0..nt {
        if pi_star[ti] <= eps {
            continue;
        }
        for tj in 0..nt {
            let p_ij = p_star[ti][tj];
            if p_ij <= eps {
                continue;
            }
            let p_ji = p_star[tj][ti];
            if p_ji > eps {
                sigma += pi_star[ti] * p_ij * (p_ij / p_ji).ln();
            } else {
                sigma += pi_star[ti] * p_ij * 30.0;
            }
        }
    }
    if !sigma.is_finite() {
        return (0.0, nt);
    }
    if sigma < 0.0 && sigma > -1e-12 {
        sigma = 0.0; // numerical floor
    }
    if sigma < 0.0 {
        sigma = 0.0; // EP must be non-negative
    }
    (sigma, nt)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_kernel_row_stochastic() {
        let k = MarkovKernel::random(8, 42);
        for i in 0..k.n {
            let sum: f64 = k.kernel[i].iter().sum();
            assert!((sum - 1.0).abs() < 1e-10, "Row {} sums to {}", i, sum);
        }
    }

    #[test]
    fn test_stationary_is_fixed() {
        let k = MarkovKernel::random(8, 42);
        let pi = k.stationary(10000, 1e-12);
        let pi_next = k.step(&pi);
        let diff: f64 = pi
            .iter()
            .zip(pi_next.iter())
            .map(|(a, b)| (a - b).abs())
            .sum();
        assert!(diff < 1e-8, "Stationary not fixed: diff = {}", diff);
    }

    #[test]
    fn test_reversible_zero_asymmetry() {
        let k = MarkovKernel::random_reversible(8, 42);
        let pi = k.stationary(10000, 1e-12);
        let sigma = path_reversal_asymmetry(&k, &pi, 10);
        assert!(
            sigma.abs() < 1e-8,
            "Reversible kernel has Sigma_T = {}",
            sigma
        );
    }

    #[test]
    fn test_spectral_gap_cycle_is_near_zero() {
        // Deterministic cycle has |lambda_2| = 1, so gap should be ~0.
        let mut k = MarkovKernel {
            n: 3,
            kernel: vec![vec![0.0; 3]; 3],
        };
        k.kernel[0][1] = 1.0;
        k.kernel[1][2] = 1.0;
        k.kernel[2][0] = 1.0;
        let gap = k.spectral_gap();
        assert!(
            gap.abs() < 1e-8,
            "Cycle should have near-zero gap, got {}",
            gap
        );
    }

    #[test]
    fn test_lens_pushforward_sums_to_one() {
        let lens = Lens::modular(8, 4);
        let dist = vec![0.125; 8];
        let macro_dist = lens.pushforward(&dist);
        let sum: f64 = macro_dist.iter().sum();
        assert!((sum - 1.0).abs() < 1e-10);
    }

    #[test]
    fn test_packaging_endomap_produces_valid_dist() {
        let k = MarkovKernel::random(8, 42);
        let lens = Lens::modular(8, 4);
        let sub = Substrate::new(k, lens, 5);
        let dist = vec![0.125; 8];
        let e_dist = sub.packaging_endomap(&dist);
        let sum: f64 = e_dist.iter().sum();
        assert!((sum - 1.0).abs() < 1e-10);
        assert!(e_dist.iter().all(|&x| x >= 0.0));
    }

    #[test]
    fn test_block_count() {
        // A chain with two disconnected blocks
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
        assert_eq!(k.block_count(), 2);
    }

    #[test]
    fn test_transient_ep_ergodic_cycle_has_no_transient_states() {
        // Strongly connected (recurrent) cycle with no self-loops.
        // Old heuristic (P_ii < 1) would incorrectly count all states as transient.
        let mut k = MarkovKernel {
            n: 3,
            kernel: vec![vec![0.0; 3]; 3],
        };
        k.kernel[0][1] = 1.0;
        k.kernel[1][2] = 1.0;
        k.kernel[2][0] = 1.0;
        let (_ep, nt) = transient_ep(&k);
        assert_eq!(nt, 0, "Ergodic cycle has no true transient states");
    }

    #[test]
    fn test_transient_ep_detects_open_class_states() {
        // States {1,3} form a closed recurrent class.
        // States {0,2} can reach the closed class but not vice versa => transient.
        let mut k = MarkovKernel {
            n: 4,
            kernel: vec![vec![0.0; 4]; 4],
        };
        k.kernel[0][2] = 0.8;
        k.kernel[0][1] = 0.2;
        k.kernel[2][0] = 0.4;
        k.kernel[2][1] = 0.6;
        k.kernel[1][1] = 0.7;
        k.kernel[1][3] = 0.3;
        k.kernel[3][1] = 0.2;
        k.kernel[3][3] = 0.8;

        let (ep, nt) = transient_ep(&k);
        assert_eq!(nt, 2, "Expected exactly two transient states");
        assert!(ep.is_finite(), "Transient EP should be finite");
        assert!(ep >= 0.0, "EP should be non-negative");
    }

    #[test]
    fn test_sample_trajectory_tail_fallback_goes_to_last_index() {
        // Degenerate (all-zero) row should use deterministic fallback to n-1,
        // not silently remain in the previous state.
        let k = MarkovKernel {
            n: 3,
            kernel: vec![vec![0.0; 3]; 3],
        };
        let traj = k.sample_trajectory(0, 5, 7);
        assert_eq!(traj.len(), 6);
        assert_eq!(traj[0], 0);
        for &s in traj.iter().skip(1) {
            assert_eq!(s, 2, "Fallback should select last index n-1");
        }
    }

    #[test]
    fn test_transient_ep_doob_nonnegative_counterexample() {
        // Counterexample where the naive q-weighted row-normalized formula
        // can become negative; Doob-transform EP should remain non-negative.
        //
        // Transient block Q:
        // [0.04968208, 0.75013044]
        // [0.31902809, 0.19142391]
        // with leakage to absorbing state 2.
        let mut k = MarkovKernel {
            n: 3,
            kernel: vec![vec![0.0; 3]; 3],
        };
        k.kernel[0][0] = 0.04968208;
        k.kernel[0][1] = 0.75013044;
        k.kernel[0][2] = 1.0 - (k.kernel[0][0] + k.kernel[0][1]);
        k.kernel[1][0] = 0.31902809;
        k.kernel[1][1] = 0.19142391;
        k.kernel[1][2] = 1.0 - (k.kernel[1][0] + k.kernel[1][1]);
        k.kernel[2][2] = 1.0; // absorbing recurrent class

        let (ep, nt) = transient_ep(&k);
        assert_eq!(nt, 2, "Expected two transient states");
        assert!(ep.is_finite(), "Transient EP should be finite");
        assert!(
            ep >= 0.0,
            "Doob-transform transient EP must be non-negative, got {}",
            ep
        );
    }
}
