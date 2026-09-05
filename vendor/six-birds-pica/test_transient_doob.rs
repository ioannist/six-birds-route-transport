fn main() {
    let nt = 2;
    for seed in 0..1000 {
        // Random kernel subset
        let q_00 = ((seed % 10) as f64 + 1.0) / 10.0;
        let q_01 = ((seed / 10 % 10) as f64 + 1.0) / 10.0;
        let q_10 = ((seed / 100 % 10) as f64 + 1.0) / 10.0;
        let q_11 = ((seed / 1000 % 10) as f64 + 1.0) / 10.0;
        
        let sum0 = q_00 + q_01;
        let sum1 = q_10 + q_11;
        if sum0 >= 1.0 || sum1 >= 1.0 { continue; }

        let mut kernel = vec![vec![0.0; nt]; nt];
        kernel[0][0] = q_00; kernel[0][1] = q_01;
        kernel[1][0] = q_10; kernel[1][1] = q_11;

        let mut surv = vec![0.0; nt];
        for i in 0..nt {
            for j in 0..nt {
                surv[i] += kernel[i][j];
            }
        }

        let eps = 1e-15;
        let mut q = vec![0.5, 0.5];
        for _ in 0..1000 {
            let mut next = vec![0.0; nt];
            for i in 0..nt {
                for j in 0..nt {
                    next[j] += q[i] * kernel[i][j];
                }
            }
            let mass: f64 = next.iter().sum();
            for x in &mut next { *x /= mass; }
            q = next;
        }

        let mut lambda = 0.0f64;
        for ti in 0..nt {
            lambda += q[ti] * surv[ti];
        }

        let mut v = vec![1.0; nt];
        for _ in 0..10000 {
            let mut next = vec![0.0; nt];
            for ti in 0..nt {
                for tj in 0..nt {
                    next[ti] += kernel[ti][tj] * v[tj];
                }
            }
            let scale = next.iter().copied().fold(0.0f64, f64::max);
            for x in &mut next {
                *x /= scale;
                if *x < eps { *x = eps; }
            }
            v = next;
        }

        let mut q_qv = 0.0f64;
        let mut q_v = 0.0f64;
        for ti in 0..nt {
            let mut qv_i = 0.0;
            for tj in 0..nt {
                qv_i += kernel[ti][tj] * v[tj];
            }
            q_qv += q[ti] * qv_i;
            q_v += q[ti] * v[ti];
        }
        lambda = q_qv / q_v;

        let mut p_star = vec![vec![0.0f64; nt]; nt];
        for ti in 0..nt {
            let denom = lambda * v[ti];
            let mut row_sum = 0.0;
            for tj in 0..nt {
                let val = kernel[ti][tj] * v[tj] / denom;
                p_star[ti][tj] = val;
                row_sum += val;
            }
            for tj in 0..nt { p_star[ti][tj] /= row_sum; }
        }

        let mut pi_star = vec![0.0f64; nt];
        let mut pi_mass = 0.0f64;
        for i in 0..nt {
            pi_star[i] = q[i] * v[i];
            pi_mass += pi_star[i];
        }
        for x in &mut pi_star { *x /= pi_mass; }

        let mut sigma = 0.0f64;
        for ti in 0..nt {
            for tj in 0..nt {
                let p_ij = p_star[ti][tj];
                let p_ji = p_star[tj][ti];
                if p_ij > 1e-15 && p_ji > 1e-15 {
                    sigma += pi_star[ti] * p_ij * (p_ij / p_ji).ln();
                }
            }
        }

        if sigma < 0.0 {
            println!("Negative EP found: Sigma = {}, Q = {:?}", sigma, kernel);
            return;
        }
    }
    println!("No negative EP found with Doob h-transform");
}
