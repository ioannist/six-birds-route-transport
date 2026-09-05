fn main() {
    let nt = 2;
    for seed in 0..1000 {
        // Random kernel subset
        let mut q_00 = ((seed % 10) as f64 + 1.0) / 10.0;
        let mut q_01 = ((seed / 10 % 10) as f64 + 1.0) / 10.0;
        let mut q_10 = ((seed / 100 % 10) as f64 + 1.0) / 10.0;
        let mut q_11 = ((seed / 1000 % 10) as f64 + 1.0) / 10.0;
        
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

        let mut sigma = 0.0f64;
        for ti in 0..nt {
            let q_i = q[ti];
            for tj in 0..nt {
                let p_ij = kernel[ti][tj] / surv[ti];
                let p_ji = kernel[tj][ti] / surv[tj];

                if p_ij > 1e-15 && p_ji > 1e-15 {
                    sigma += q_i * p_ij * (p_ij / p_ji).ln();
                }
            }
        }
        if sigma < 0.0 {
            println!("Negative EP found: Sigma = {}, Q = {:?}", sigma, kernel);
            return;
        }
    }
    println!("No negative EP found");
}