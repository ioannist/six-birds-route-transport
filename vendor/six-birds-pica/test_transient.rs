fn main() {
    let nt = 2;
    let eps = 1e-15;
    let mut kernel = vec![vec![0.0; nt]; nt];
    kernel[0][0] = 0.5; kernel[0][1] = 0.1; // surv(0) = 0.6
    kernel[1][0] = 0.1; kernel[1][1] = 0.8; // surv(1) = 0.9

    let mut surv = vec![0.0; nt];
    for i in 0..nt {
        for j in 0..nt {
            surv[i] += kernel[i][j];
        }
    }

    let mut q = vec![0.5, 0.5];
    for _ in 0..10000 {
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
    println!("q = {:?}", q);

    let mut qP = vec![0.0; nt];
    for i in 0..nt {
        for j in 0..nt {
            qP[j] += q[i] * (kernel[i][j] / surv[i]);
        }
    }
    println!("qP = {:?}", qP);
}
