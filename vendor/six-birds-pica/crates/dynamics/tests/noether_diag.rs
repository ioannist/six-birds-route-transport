//! Diagnostic test: eigenvalue spectrum and spectral conservation probes for macro kernels.
//!
//! Prints the full eigenvalue spectrum of the symmetrized similarity matrix for
//! representative PICA configs at multiple coarse-graining scales, plus the new
//! spectral conservation probes (t_rel, gap_ratio, spectral_participation, etc.).
//!
//! Run with:
//!   cargo test -p dynamics --test noether_diag -- --ignored --nocapture

use six_dynamics::lagrange;
use six_dynamics::mixture::run_dynamics;
use six_dynamics::pica::PicaConfig;
use six_dynamics::spectral;
use six_dynamics::state::DynamicsConfig;
use six_primitives_core::helpers;

/// Build a DynamicsConfig with n=32, seed given, and the specified PICA config.
fn make_config(n: usize, seed: u64, pica: PicaConfig) -> DynamicsConfig {
    let ln_n = (n as f64).ln();
    DynamicsConfig {
        n,
        p_traj: 0.90,
        p_p1: 0.03,
        p_p2: 0.03,
        p_p4: 0.01,
        p_p5: 0.01,
        p_p6: 0.02,
        budget_rate: ln_n * 0.01,
        budget_init: n as f64 * ln_n,
        p1_strength: 0.1,
        p2_flips: 1,
        min_row_entropy: 0.1 * ln_n,
        max_self_loop: 1.0 - 1.0 / n as f64,
        protocol_cycle_len: 10,
        total_steps: 500,
        obs_interval: 50,
        tau_alpha: 0.5,
        budget_cap: n as f64 * ln_n,
        n_clusters: 4,
        pica,
        seed,
    }
}

#[test]
#[ignore]
fn noether_eigenvalue_spectrum_diagnostic() {
    let n = 32;
    let seed = 42u64;

    let configs: Vec<(&str, PicaConfig)> = vec![
        ("baseline", PicaConfig::baseline()),
        ("full_action", PicaConfig::full_action()),
        ("A14_only", PicaConfig::baseline().with_cell(3, 2)), // P4<-P3: RM-quantile lens
        ("A19_only", PicaConfig::baseline().with_cell(2, 3)), // P3<-P4: sector mixing
    ];

    let k_targets: &[usize] = &[2, 4, 8, 16];

    println!("\n{}", "=".repeat(80));
    println!("SPECTRAL CONSERVATION PROBE DIAGNOSTIC");
    println!("n={}, seed={}", n, seed);
    println!("{}\n", "=".repeat(80));

    for (config_name, pica) in &configs {
        let config = make_config(n, seed, pica.clone());
        let trace = run_dynamics(&config);
        let last_snap = trace.snapshots.last().unwrap();
        let tau = last_snap.tau;

        println!("=== Config: {}, seed={}, n={} ===", config_name, seed, n);
        println!(
            "    final tau={}, final frob={:.4}, final sigma={:.4}, budget={:.2}",
            tau, last_snap.frob_from_rank1, last_snap.sigma, last_snap.budget
        );
        println!();

        // Compute K^tau once for all scales
        let ktau = helpers::matrix_power(&trace.final_kernel, tau);

        for &k_target in k_targets {
            // Skip if k_target >= n/2 (not enough states)
            if k_target > n / 2 {
                println!("  k={}: skipped (k_target > n/2)", k_target);
                continue;
            }

            let partition = spectral::spectral_partition(&trace.final_kernel, k_target);
            let actual_k = spectral::n_clusters(&partition);
            if actual_k < 2 {
                println!(
                    "  k={} (actual={}): skipped (degenerate partition)",
                    k_target, actual_k
                );
                continue;
            }

            let macro_k = helpers::build_macro_from_ktau(&ktau.kernel, &partition, actual_k);
            let pi = macro_k.stationary(10000, 1e-12);

            // Spectral embedding to get eigenvalues
            let embed = lagrange::spectral_embed_reversible(&pi, &macro_k);

            if embed.eigenvalues.is_empty() {
                println!("  k={} (actual={}), tau={}:", k_target, actual_k, tau);
                println!("    eigenvalues: EMPTY (degenerate pi or n<3)");
                println!();
                continue;
            }

            // Format eigenvalue spectrum
            let eig_str: Vec<String> = embed
                .eigenvalues
                .iter()
                .map(|e| format!("{:.6}", e))
                .collect();

            // Spectral gap ratio = (lambda_1 - SLEM) / lambda_1
            // SLEM = second largest eigenvalue modulus (max |λ_i| for i≥1)
            let spectral_gap_ratio =
                if embed.eigenvalues.len() >= 2 && embed.eigenvalues[0].abs() > 1e-15 {
                    let slem = embed.eigenvalues[1..]
                        .iter()
                        .map(|l| l.abs())
                        .fold(0.0_f64, f64::max);
                    (embed.eigenvalues[0] - slem) / embed.eigenvalues[0]
                } else {
                    f64::NAN
                };

            // Also compute: distance of each eigenvalue from the threshold
            let dist_from_threshold: Vec<String> = embed
                .eigenvalues
                .iter()
                .skip(1) // skip lambda_1
                .map(|&lam| format!("{:.6}", 1.0 - lam.abs()))
                .collect();

            println!("  k={} (actual={}), tau={}:", k_target, actual_k, tau);
            println!("    eigenvalues: [{}]", eig_str.join(", "));
            println!(
                "    distance from |lam|=1 (skip lam1): [{}]",
                dist_from_threshold.join(", ")
            );
            println!("    spectral_gap_ratio: {:.6}", spectral_gap_ratio);

            // Also print frob and sigma of the macro kernel for context
            let frob = six_dynamics::observe::frob_from_rank1(&macro_k);
            let sigma = six_primitives_core::substrate::path_reversal_asymmetry(&macro_k, &pi, 10);
            println!(
                "    macro frob={:.6}, macro sigma={:.6}, macro gap={:.6}",
                frob,
                sigma,
                macro_k.spectral_gap()
            );

            // Print the macro kernel itself for small k
            if actual_k <= 4 {
                println!("    macro kernel:");
                for i in 0..actual_k {
                    let row_str: Vec<String> = macro_k.kernel[i]
                        .iter()
                        .map(|v| format!("{:.4}", v))
                        .collect();
                    println!("      [{}]", row_str.join(", "));
                }
            }

            println!();
        }

        println!("{:-<80}\n", "");
    }

    // Summary: aggregate statistics across all configs
    println!("=== SUMMARY: Eigenvalue Statistics (Old + New Probes) ===\n");
    println!(
        "{:<14} {:>4} {:>4} {:>8} {:>8} {:>8} {:>8} {:>6} {:>6} {:>6} {:>6}",
        "config", "k", "a_k", "lam_2", "gap_r", "t_rel", "N_eff", "H_eig", "r50", "r70", "r90"
    );
    println!("{:-<100}", "");

    for (config_name, pica) in &configs {
        let config = make_config(n, seed, pica.clone());
        let trace = run_dynamics(&config);
        let last_snap = trace.snapshots.last().unwrap();
        let tau = last_snap.tau;
        let ktau = helpers::matrix_power(&trace.final_kernel, tau);

        for &k_target in k_targets {
            if k_target > n / 2 {
                continue;
            }

            let partition = spectral::spectral_partition(&trace.final_kernel, k_target);
            let actual_k = spectral::n_clusters(&partition);
            if actual_k < 2 {
                continue;
            }

            let macro_k = helpers::build_macro_from_ktau(&ktau.kernel, &partition, actual_k);
            let pi = macro_k.stationary(10000, 1e-12);
            let embed = lagrange::spectral_embed_reversible(&pi, &macro_k);

            if embed.eigenvalues.is_empty() {
                continue;
            }

            let lam_2 = if embed.eigenvalues.len() >= 2 {
                embed.eigenvalues[1]
            } else {
                f64::NAN
            };
            let gap_r = lagrange::spectral_gap_ratio(&embed.eigenvalues);
            let t_rel = lagrange::relaxation_time(&embed.eigenvalues);
            let n_eff = lagrange::spectral_participation(&embed.eigenvalues);
            let h_eig = lagrange::eigenvalue_entropy(&embed.eigenvalues);
            let r50 = lagrange::relative_slow_modes(&embed.eigenvalues, 0.5);
            let r70 = lagrange::relative_slow_modes(&embed.eigenvalues, 0.7);
            let r90 = lagrange::relative_slow_modes(&embed.eigenvalues, 0.9);

            println!(
                "{:<14} {:>4} {:>4} {:>8.4} {:>8.4} {:>8.3} {:>8.3} {:>6.3} {:>6} {:>6} {:>6}",
                config_name, k_target, actual_k, lam_2, gap_r, t_rel, n_eff, h_eig, r50, r70, r90
            );
        }
    }

    // Also show micro-kernel spectral summary for each config
    println!("\n=== MICRO-KERNEL SPECTRAL SUMMARY ===\n");
    println!(
        "{:<14} {:>8} {:>8} {:>8} {:>8}  top_5_eigenvalues",
        "config", "gap_r", "t_rel", "N_eff", "H_eig"
    );
    println!("{:-<100}", "");

    for (config_name, pica) in &configs {
        let config = make_config(n, seed, pica.clone());
        let trace = run_dynamics(&config);
        let micro_pi = trace.final_kernel.stationary(10000, 1e-12);
        let micro_embed = lagrange::spectral_embed_reversible(&micro_pi, &trace.final_kernel);

        if micro_embed.eigenvalues.is_empty() {
            continue;
        }

        let gap_r = lagrange::spectral_gap_ratio(&micro_embed.eigenvalues);
        let t_rel = lagrange::relaxation_time(&micro_embed.eigenvalues);
        let n_eff = lagrange::spectral_participation(&micro_embed.eigenvalues);
        let h_eig = lagrange::eigenvalue_entropy(&micro_embed.eigenvalues);
        let nt = lagrange::nontrivial_eigenvalues(&micro_embed.eigenvalues);
        let mut top5: Vec<f64> = nt.iter().map(|v| v.abs()).collect();
        top5.sort_by(|a, b| b.partial_cmp(a).unwrap_or(std::cmp::Ordering::Equal));
        top5.truncate(5);
        let top5_str: Vec<String> = top5.iter().map(|v| format!("{:.4}", v)).collect();

        println!(
            "{:<14} {:>8.4} {:>8.3} {:>8.3} {:>8.3}  [{}]",
            config_name,
            gap_r,
            t_rel,
            n_eff,
            h_eig,
            top5_str.join(", ")
        );
    }

    println!(
        "\nLegend: gap_r=spectral gap ratio, t_rel=relaxation time, N_eff=spectral participation,"
    );
    println!("  H_eig=eigenvalue entropy, r50/r70/r90=relative slow-mode counts at thresholds 0.5/0.7/0.9");
}
