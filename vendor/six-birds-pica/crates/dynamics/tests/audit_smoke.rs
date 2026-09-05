//! Smoke tests for the rich audit suite.
//!
//! Verifies that AuditRecord can be constructed and serialized at all three
//! tiers (lite, standard, rich), that all present floats are finite, and that
//! Option fields behave correctly when partition/packaging is absent.

use serde_json;
use six_dynamics::audit;
use six_dynamics::mixture::run_dynamics;
use six_dynamics::pica::PicaConfig;
use six_dynamics::state::DynamicsConfig;

fn make_small_config(pica: PicaConfig) -> DynamicsConfig {
    let n = 8;
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
        total_steps: 50,
        obs_interval: 10,
        tau_alpha: 0.5,
        budget_cap: n as f64 * ln_n,
        n_clusters: 4,
        pica,
        seed: 42,
    }
}

/// Assert all present f64 fields in a JSON string are finite.
fn assert_all_floats_finite(json: &str) {
    // Simple check: search for NaN/Infinity in the JSON output
    assert!(!json.contains("NaN"), "JSON contains NaN: {}", json);
    assert!(
        !json.contains("Infinity"),
        "JSON contains Infinity: {}",
        json
    );
    assert!(
        !json.contains("-Infinity"),
        "JSON contains -Infinity: {}",
        json
    );
}

#[test]
fn test_lite_tier_serialization() {
    let config = make_small_config(PicaConfig::baseline());
    let trace = run_dynamics(&config);
    let last = trace.snapshots.last().unwrap();
    let pch = audit::pica_config_hash(&config.pica);

    let rec = audit::lite_from_snapshot(last, config.seed, config.n, pch);
    assert_eq!(rec.tier, "lite");
    assert_eq!(rec.schema_version, 3);
    assert_eq!(rec.n, 8);
    assert_eq!(rec.seed, 42);

    let json = audit::to_json(&rec).expect("serialization should succeed");
    assert_all_floats_finite(&json);

    // Lite tier should NOT have higher-tier fields populated
    assert!(rec.partition_stats.is_none());
    assert!(rec.packaging_stats.is_none());
    assert!(rec.multi_scale_scan.is_none());
    assert!(rec.n_chiral.is_none());
}

#[test]
fn test_standard_tier_from_dynamics() {
    let config = make_small_config(PicaConfig::baseline());
    let trace = run_dynamics(&config);
    let last = trace.snapshots.last().unwrap();
    let pch = audit::pica_config_hash(&config.pica);

    // Build an AugmentedState to test standard tier
    // (We can't get the internal state from run_dynamics, so test the
    // lite path + partition_stats function separately)
    let partition = vec![0, 0, 1, 1, 2, 2, 3, 3];
    let stats = audit::partition_stats(&partition);
    assert_eq!(stats.n_clusters, 4);
    assert_eq!(stats.min_size, 2);
    assert_eq!(stats.max_size, 2);
    assert!(stats.entropy.is_finite());
    assert!(stats.effective_k.is_finite());
    // 4 equal-size clusters → entropy = ln(4), effective_k ≈ 4
    assert!((stats.effective_k - 4.0).abs() < 0.01);

    // Test serialization of a lite record with partition_stats injected
    let mut rec = audit::lite_from_snapshot(last, config.seed, config.n, pch);
    rec.tier = "standard".into();
    rec.partition_stats = Some(stats);
    rec.partition_flip_count = Some(trace.partition_flip_count);
    rec.packaging_flip_count = Some(trace.packaging_flip_count);
    rec.tau_change_count = Some(trace.tau_change_count);

    let json = audit::to_json(&rec).expect("serialization should succeed");
    assert_all_floats_finite(&json);
    assert!(json.contains("\"tier\":\"standard\""));
    assert!(json.contains("\"partition_stats\""));
    assert!(json.contains("\"partition_flip_count\""));
}

#[test]
fn test_partition_stats_empty() {
    let stats = audit::partition_stats(&[]);
    assert_eq!(stats.n_clusters, 0);
    assert_eq!(stats.min_size, 0);
    assert_eq!(stats.max_size, 0);
}

#[test]
fn test_partition_stats_single_cluster() {
    let partition = vec![0, 0, 0, 0];
    let stats = audit::partition_stats(&partition);
    assert_eq!(stats.n_clusters, 1);
    assert_eq!(stats.min_size, 4);
    assert_eq!(stats.max_size, 4);
    assert_eq!(stats.entropy, 0.0);
    assert!((stats.effective_k - 1.0).abs() < 0.01);
}

#[test]
fn test_multi_scale_scan() {
    let kernel = six_primitives_core::substrate::MarkovKernel::random(16, 42);
    let config = make_small_config(PicaConfig::baseline());
    // Override n to match kernel
    let mut config = config;
    config.n = 16;

    let entries = audit::multi_scale_scan(&kernel, &config, None);
    // n=16, max_k = min(64, 8) = 8, so we should get k=2,4,8
    assert!(
        !entries.is_empty(),
        "multi-scale scan should produce entries for n=16"
    );
    for entry in &entries {
        assert!(entry.k >= 2);
        if let Some(g) = entry.macro_gap {
            assert!(g.is_finite());
        }
        if let Some(f) = entry.frob {
            assert!(f.is_finite());
        }
        if let Some(s) = entry.sigma_pi {
            assert!(s.is_finite());
        }
    }
}

#[test]
fn test_pica_config_hash_deterministic() {
    let h1 = audit::pica_config_hash(&PicaConfig::baseline());
    let h2 = audit::pica_config_hash(&PicaConfig::baseline());
    assert_eq!(h1, h2, "same config should produce same hash");

    let h3 = audit::pica_config_hash(&PicaConfig::full_action());
    assert_ne!(h1, h3, "different configs should produce different hashes");
}

#[test]
fn test_event_counters_populated() {
    let config = make_small_config(PicaConfig::baseline());
    let trace = run_dynamics(&config);
    // baseline with 50 steps should have at least 1 partition refresh
    assert!(
        trace.partition_flip_count >= 1,
        "should have at least 1 partition flip, got {}",
        trace.partition_flip_count
    );
}

#[test]
fn test_full_action_audit_serializes() {
    let config = make_small_config(PicaConfig::full_action());
    let trace = run_dynamics(&config);
    let last = trace.snapshots.last().unwrap();
    let pch = audit::pica_config_hash(&config.pica);

    let rec = audit::lite_from_snapshot(last, config.seed, config.n, pch);
    let json = audit::to_json(&rec).expect("serialization should succeed");
    assert_all_floats_finite(&json);
}

#[test]
fn test_finite_horizon_sigma_differs_from_stationary() {
    // For a non-reversible kernel, sigma_u (uniform start) should differ
    // from sigma_pi (stationary start) because uniform != stationary.
    let kernel = six_primitives_core::substrate::MarkovKernel::random(8, 42);
    let n = kernel.n;
    let uniform: Vec<f64> = vec![1.0 / n as f64; n];
    let pi = kernel.stationary(10000, 1e-12);

    let sigma_u = audit::finite_horizon_sigma(&kernel, &uniform, 10);
    let sigma_pi = audit::finite_horizon_sigma(&kernel, &pi, 10);

    // Both should be finite and non-negative
    assert!(sigma_u.is_finite(), "sigma_u should be finite");
    assert!(sigma_pi.is_finite(), "sigma_pi should be finite");
    assert!(sigma_u >= 0.0, "sigma_u should be non-negative");
    assert!(sigma_pi >= 0.0, "sigma_pi should be non-negative");

    // For a random (non-reversible) kernel, uniform != stationary,
    // so finite-horizon values should differ
    assert!(
        (sigma_u - sigma_pi).abs() > 1e-10,
        "sigma_u ({}) and sigma_pi ({}) should differ for non-reversible kernel",
        sigma_u,
        sigma_pi
    );
}

#[test]
fn test_finite_horizon_sigma_includes_boundary_entropy_term() {
    // Reversible symmetric kernel: flux term is zero (P_ij == P_ji), so
    // finite-horizon sigma should reduce to H(rho_T) - H(rho_0).
    let kernel = six_primitives_core::substrate::MarkovKernel {
        n: 2,
        kernel: vec![vec![0.9, 0.1], vec![0.1, 0.9]],
    };
    let rho0 = vec![0.99, 0.01];
    let sigma = audit::finite_horizon_sigma(&kernel, &rho0, 1);

    let rho1 = vec![
        rho0[0] * kernel.kernel[0][0] + rho0[1] * kernel.kernel[1][0],
        rho0[0] * kernel.kernel[0][1] + rho0[1] * kernel.kernel[1][1],
    ];
    let h = |d: &[f64]| -> f64 {
        let mut s = 0.0;
        for &p in d {
            if p > 1e-30 {
                s -= p * p.ln();
            }
        }
        s
    };
    let expected = h(&rho1) - h(&rho0);
    assert!(
        (sigma - expected).abs() < 1e-10,
        "Expected boundary-only sigma {:.12}, got {:.12}",
        expected,
        sigma
    );
    assert!(
        sigma > 0.0,
        "Boundary entropy increase should be positive, got {}",
        sigma
    );
}

#[test]
fn test_sanitize_ratio_guards_division() {
    // Normal case
    assert!(audit::sanitize_ratio(1.0, 2.0).is_some());
    assert!((audit::sanitize_ratio(1.0, 2.0).unwrap() - 0.5).abs() < 1e-15);

    // Zero denominator → None
    assert!(audit::sanitize_ratio(1.0, 0.0).is_none());

    // Tiny denominator → None
    assert!(audit::sanitize_ratio(1.0, 1e-15).is_none());

    // NaN numerator → None
    assert!(audit::sanitize_ratio(f64::NAN, 1.0).is_none());

    // Inf result → None
    assert!(audit::sanitize_ratio(f64::INFINITY, 1.0).is_none());
}

#[test]
fn test_dynamics_trace_exposes_packaging() {
    // full_action enables P5 producers, so packaging should be populated
    let config = make_small_config(PicaConfig::full_action());
    let trace = run_dynamics(&config);

    // full_action enables A21/A22/A23 (P5 row), so packaging should exist
    assert!(
        trace.final_pica_state_packaging.is_some(),
        "full_action should produce packaging"
    );
    let pkg = trace.final_pica_state_packaging.unwrap();
    assert_eq!(pkg.len(), config.n, "packaging should cover all states");

    // Partition should also exist (baseline always produces it)
    assert!(
        trace.final_pica_state_partition.is_some(),
        "full_action should produce partition"
    );
}

#[test]
fn test_to_json_survives_nan_inf_injection() {
    let config = make_small_config(PicaConfig::baseline());
    let trace = run_dynamics(&config);
    let last = trace.snapshots.last().unwrap();
    let pch = audit::pica_config_hash(&config.pica);

    let mut rec = audit::lite_from_snapshot(last, config.seed, config.n, pch);

    // Inject NaN and Inf directly, bypassing sanitize()
    rec.sigma = Some(f64::NAN);
    rec.eff_gap = Some(f64::INFINITY);
    rec.macro_gap = Some(f64::NEG_INFINITY);
    rec.sigma_ratio = Some(f64::NAN);
    rec.sigma_u = Some(f64::INFINITY);

    // to_json MUST succeed (not return None)
    let json = audit::to_json(&rec).expect("to_json must survive NaN/Inf injection");

    // The JSON must be valid (no raw NaN/Infinity tokens)
    assert!(!json.contains("NaN"), "JSON must not contain NaN");
    assert!(!json.contains("Infinity"), "JSON must not contain Infinity");

    // The injected fields should be null (sanitized away)
    let parsed: serde_json::Value = serde_json::from_str(&json).expect("output must be valid JSON");
    assert!(parsed["sigma"].is_null(), "NaN sigma should become null");
    assert!(
        parsed["eff_gap"].is_null(),
        "Inf eff_gap should become null"
    );
    assert!(
        parsed["macro_gap"].is_null(),
        "-Inf macro_gap should become null"
    );
    assert!(
        parsed["sigma_ratio"].is_null(),
        "NaN sigma_ratio should become null"
    );
    assert!(
        parsed["sigma_u"].is_null(),
        "Inf sigma_u should become null"
    );
}

#[test]
fn test_all_presets_unique_hashes() {
    let presets: Vec<(&str, PicaConfig)> = vec![
        ("none", PicaConfig::none()),
        ("baseline", PicaConfig::baseline()),
        ("sbrc", PicaConfig::sbrc()),
        ("mixer", PicaConfig::mixer()),
        ("full_action", PicaConfig::full_action()),
        ("full_all", PicaConfig::full_all()),
        ("full_lens", PicaConfig::full_lens()),
    ];
    let hashes: Vec<u64> = presets
        .iter()
        .map(|(_, p)| audit::pica_config_hash(p))
        .collect();
    for i in 0..hashes.len() {
        for j in (i + 1)..hashes.len() {
            assert_ne!(
                hashes[i], hashes[j],
                "presets '{}' and '{}' produce identical hashes",
                presets[i].0, presets[j].0
            );
        }
    }
}

#[test]
fn test_clone_for_macro_preserves_enabled() {
    let orig = PicaConfig::full_action();
    let cloned = orig.clone_for_macro();
    assert_eq!(
        orig.enabled, cloned.enabled,
        "clone_for_macro must preserve the enable matrix"
    );
    // Key parameters should be preserved
    assert_eq!(orig.p3_p4_sector_boost, cloned.p3_p4_sector_boost);
    assert_eq!(orig.p2_p4_inter_boost, cloned.p2_p4_inter_boost);
    assert_eq!(orig.lens_selector as u8, cloned.lens_selector as u8);
    // Intervals should be shorter (macro-level optimization)
    assert!(
        cloned.partition_interval < orig.partition_interval,
        "clone_for_macro should shorten partition_interval"
    );
}

#[test]
fn test_none_config_no_partition_flips() {
    let config = make_small_config(PicaConfig::none());
    let trace = run_dynamics(&config);
    // With PicaConfig::none(), no P4 cells enabled → needs_partition() is false
    // → partition_flip_count should be 0
    assert_eq!(
        trace.partition_flip_count, 0,
        "none() config should not trigger partition refreshes"
    );
    assert_eq!(
        trace.packaging_flip_count, 0,
        "none() config should not trigger packaging refreshes"
    );
}

#[test]
fn test_flip_count_measures_actual_changes() {
    // With baseline (A10+A15), partition should stabilize quickly.
    // After the flip-count fix, flip_count should be much less than
    // total refresh cycles (which = total_steps / partition_interval).
    let mut config = make_small_config(PicaConfig::baseline());
    config.total_steps = 500;
    config.pica.partition_interval = 10;
    let trace = run_dynamics(&config);
    let max_refresh_cycles = config.total_steps as u64 / config.pica.partition_interval;
    // Partition should stabilize after first 1-2 refreshes for a small n=8 kernel
    assert!(
        trace.partition_flip_count < max_refresh_cycles,
        "flip_count ({}) should be less than max refresh cycles ({}) \
         because hysteresis prevents counting no-op refreshes",
        trace.partition_flip_count,
        max_refresh_cycles
    );
}

#[test]
fn test_pica_config_serialization_structure() {
    let config = PicaConfig::full_action();
    let json = serde_json::to_value(&config).expect("PicaConfig should serialize");

    // Verify key fields are present
    assert!(
        json["enabled"].is_array(),
        "enabled matrix should serialize as array"
    );
    assert!(
        json["lens_selector"].is_string(),
        "lens_selector should serialize"
    );
    assert!(
        json["p3_p4_sector_boost"].is_number(),
        "numeric params should serialize"
    );
    assert!(
        json["partition_interval"].is_number(),
        "intervals should serialize"
    );

    // Verify enable matrix structure
    let enabled = json["enabled"].as_array().unwrap();
    assert_eq!(enabled.len(), 6, "enable matrix should have 6 rows");
    for row in enabled {
        assert_eq!(
            row.as_array().unwrap().len(),
            6,
            "each row should have 6 entries"
        );
    }

    // Verify all 36 parameters are captured (not just the 24 in pica_config_hash).
    // These 12 are excluded from pica_config_hash but present in serialization:
    assert!(
        json["p1_p1_cooldown"].is_number(),
        "p1_p1_cooldown missing from serialization"
    );
    assert!(
        json["p2_p1_protect_steps"].is_number(),
        "p2_p1_protect_steps missing"
    );
    assert!(json["p2_p2_cooldown"].is_number(), "p2_p2_cooldown missing");
    assert!(
        json["p1_p4_boundary_boost"].is_number(),
        "p1_p4_boundary_boost missing"
    );
    assert!(
        json["p2_p5_boundary_boost"].is_number(),
        "p2_p5_boundary_boost missing"
    );
    assert!(
        json["p1_p6_budget_threshold_frac"].is_number(),
        "p1_p6_budget_threshold_frac missing"
    );
    assert!(json["p3_p3_tau_cap"].is_number(), "p3_p3_tau_cap missing");
    assert!(
        json["l1_audit_interval"].is_number(),
        "l1_audit_interval missing"
    );
    assert!(
        json["rm_refresh_interval"].is_number(),
        "rm_refresh_interval missing"
    );
    assert!(
        json["packaging_interval"].is_number(),
        "packaging_interval missing"
    );
    assert!(
        json["p6_refresh_interval"].is_number(),
        "p6_refresh_interval missing"
    );
}

#[test]
fn test_audit_record_includes_pat_config() {
    let config = make_small_config(PicaConfig::full_action());
    let trace = run_dynamics(&config);
    let last = trace.snapshots.last().unwrap();
    let pch = audit::pica_config_hash(&config.pica);

    let mut rec = audit::lite_from_snapshot(last, config.seed, config.n, pch);
    // Simulate what the runner does
    rec.pica_config = serde_json::to_value(&config.pica).ok();

    let json = audit::to_json(&rec).expect("serialization should succeed");
    let parsed: serde_json::Value = serde_json::from_str(&json).unwrap();
    assert!(
        !parsed["pica_config"].is_null(),
        "pica_config field should be present in serialized audit record"
    );
    assert!(
        parsed["pica_config"]["enabled"].is_array(),
        "pica_config should contain the full enable matrix"
    );
}

#[test]
fn test_config_validation_warnings() {
    // none() should produce no warnings
    let warnings = PicaConfig::none().validate();
    assert!(
        warnings.is_empty(),
        "none() should have no warnings: {:?}",
        warnings
    );

    // baseline() should produce no warnings
    let warnings = PicaConfig::baseline().validate();
    assert!(
        warnings.is_empty(),
        "baseline() should have no warnings: {:?}",
        warnings
    );

    // Enabling an implicit cell should warn
    let cfg = PicaConfig::none().with_cell(2, 0); // P3←P1 (implicit)
    let warnings = cfg.validate();
    assert!(
        !warnings.is_empty(),
        "enabling P3←P1 should produce a warning"
    );
    assert!(
        warnings[0].contains("implicit"),
        "warning should mention 'implicit'"
    );

    // Enabling P5 consumers without producers should warn
    let cfg = PicaConfig::baseline().with_cell(0, 4); // A5: P1←P5 (consumer)
    let warnings = cfg.validate();
    assert!(!warnings.is_empty(), "A5 without P5 producers should warn");
}

#[test]
fn test_lagrange_fields_in_multi_scale_scan() {
    // Run dynamics with full_action, then call multi_scale_scan directly
    // on the final kernel to verify Lagrange probe fields.
    let config = make_small_config(PicaConfig::full_action());
    let trace = run_dynamics(&config);

    // Call multi_scale_scan on the final kernel
    let scan = audit::multi_scale_scan(&trace.final_kernel, &config, Some(3));
    assert!(
        !scan.is_empty(),
        "scan should have at least 1 entry for n=8"
    );

    for entry in &scan {
        // step_entropy should be present and positive
        if let Some(h) = entry.step_entropy {
            assert!(h >= 0.0, "step_entropy should be non-negative, got {}", h);
        }

        // pla2_gap should be non-negative
        if let Some(pla2) = entry.pla2_gap {
            assert!(pla2 >= 0.0, "pla2_gap should be non-negative, got {}", pla2);
        }

        // lagr_geo_r2 should be in [0, 1] when present
        if let Some(r2) = entry.lagr_geo_r2 {
            assert!(
                r2 >= 0.0 && r2 <= 1.0,
                "lagr_geo_r2 should be in [0,1], got {}",
                r2
            );
        }

        // lagr_diff_kl should be non-negative
        if let Some(kl) = entry.lagr_diff_kl {
            assert!(kl >= 0.0, "lagr_diff_kl should be non-negative, got {}", kl);
        }

        // lagr_diff_alpha should be positive
        if let Some(alpha) = entry.lagr_diff_alpha {
            assert!(
                alpha > 0.0,
                "lagr_diff_alpha should be positive, got {}",
                alpha
            );
        }

        // Spectral conservation probes: present when k >= 3 (2×2 matrices
        // have no nontrivial eigenvalues from spectral_embed_reversible)
        if entry.k >= 3 {
            assert!(
                entry.t_rel.is_some(),
                "t_rel should be present for k={}",
                entry.k
            );
            assert!(
                entry.gap_ratio.is_some(),
                "gap_ratio should be present for k={}",
                entry.k
            );
            assert!(
                entry.eigen_entropy.is_some(),
                "eigen_entropy should be present for k={}",
                entry.k
            );
            assert!(
                entry.spectral_participation.is_some(),
                "spectral_participation should be present for k={}",
                entry.k
            );
            assert!(
                entry.slow_modes_r50.is_some(),
                "slow_modes_r50 should be present for k={}",
                entry.k
            );
        }
        if let Some(t) = entry.t_rel {
            assert!(t > 0.0, "t_rel should be positive, got {}", t);
        }
        if let Some(gr) = entry.gap_ratio {
            assert!(
                gr >= 0.0 && gr <= 1.0,
                "gap_ratio should be in [0,1], got {}",
                gr
            );
        }
    }

    // Build a lite audit and verify Lagrange fields serialize to JSON
    let last = trace.snapshots.last().unwrap();
    let pch = audit::pica_config_hash(&config.pica);
    let mut rec = audit::lite_from_snapshot(last, config.seed, config.n, pch);
    rec.multi_scale_scan = Some(scan);
    let json = audit::to_json(&rec).expect("serialization should succeed");
    assert!(
        json.contains("step_entropy"),
        "JSON should contain step_entropy"
    );
    assert!(json.contains("pla2_gap"), "JSON should contain pla2_gap");
    assert!(json.contains("t_rel"), "JSON should contain t_rel");
    assert!(json.contains("gap_ratio"), "JSON should contain gap_ratio");
    assert!(
        json.contains("eigen_entropy"),
        "JSON should contain eigen_entropy"
    );
    assert!(
        json.contains("nontrivial_eigenvalues"),
        "JSON should contain nontrivial_eigenvalues"
    );
}
