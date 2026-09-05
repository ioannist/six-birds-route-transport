fn jacobi_eigen(a: &[Vec<f64>]) -> (Vec<f64>, usize) {
    let n = a.len();
    let mut m = a.to_vec();
    let mut iters = 0;
    for iter in 0..100 * n * n {
        iters = iter;
        let (mut max_val, mut p, mut q) = (0.0, 0, 1);
        for i in 0..n {
            for j in (i+1)..n {
                if m[i][j].abs() > max_val {
                    max_val = m[i][j].abs();
                    p = i;
                    q = j;
                }
            }
        }
        if max_val < 1e-14 { break; }

        let theta = if (m[p][p] - m[q][q]).abs() < 1e-30 {
            std::f64::consts::FRAC_PI_4
        } else {
            0.5 * (2.0 * m[p][q] / (m[p][p] - m[q][q])).atan()
        };
        let (s, c) = theta.sin_cos();

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
        for k in 0..n {
            let mp_k = m[k][p];
            let mq_k = m[k][q];
            m[k][p] = c * mp_k - s * mq_k;
            m[k][q] = s * mp_k + c * mq_k;
        }
    }
    (vec![], iters)
}

fn main() {
    let mat = vec![
        vec![2.0, 1.0],
        vec![1.0, 0.0]
    ];
    let (_, iters) = jacobi_eigen(&mat);
    println!("Iterations for 2x2: {}", iters);
}
