//! # Rich Audit Suite
//!
//! Machine-readable audit records for dynamics runs.
//! Three tiers: Lite (per observation), Standard (per refresh / end-of-run),
//! Rich (end-of-run with multi-scale scan and full diagnostics).
//!
//! All numeric fields are `Option<f64>` — `None` when the metric cannot be
//! computed (e.g., no partition available). Non-finite values are sanitized
//! to `None` before serialization.

use serde::Serialize;
use six_primitives_core::helpers;
use six_primitives_core::substrate::MarkovKernel;

use crate::observe::Snapshot;
use crate::state::{AugmentedState, DynamicsConfig};

/// Partition size statistics: min, max, Shannon entropy, effective cluster count.
#[derive(Debug, Clone, Serialize)]
pub struct PartitionStats {
    pub n_clusters: usize,
    pub min_size: usize,
    pub max_size: usize,
    pub entropy: f64,
    pub effective_k: f64,
}

/// One entry in a multi-scale scan (Rich tier).
#[derive(Debug, Clone, Serialize)]
pub struct ScaleScanEntry {
    pub k: usize,
    pub macro_gap: Option<f64>,
    pub frob: Option<f64>,
    pub sigma_pi: Option<f64>,
    pub max_asym: Option<f64>,
    pub cyc_mean: Option<f64>,
    pub cyc_max: Option<f64>,
    pub n_chiral: Option<usize>,
    // Lagrangian probes (emergent lawfulness)
    pub step_entropy: Option<f64>,
    pub pla2_gap: Option<f64>,
    pub lagr_geo_r2: Option<f64>,
    pub lagr_diff_kl: Option<f64>,
    pub lagr_diff_alpha: Option<f64>,
    // Spectral conservation probes
    pub t_rel: Option<f64>,
    pub gap_ratio: Option<f64>,
    pub eigen_entropy: Option<f64>,
    pub spectral_participation: Option<f64>,
    pub slow_modes_r50: Option<usize>,
    pub slow_modes_r70: Option<usize>,
    pub slow_modes_r90: Option<usize>,
    pub nontrivial_eigenvalues: Option<Vec<f64>>,
}

/// Machine-readable audit record. Emitted as `KEY_AUDIT_JSON {json}`.
#[derive(Debug, Clone, Serialize)]
pub struct AuditRecord {
    // --- Metadata ---
    pub schema_version: u32,
    pub tier: String,
    pub exp_id: Option<String>,
    pub config_name: Option<String>,
    pub git_sha: Option<String>,
    pub seed: u64,
    pub n: usize,
    pub step: u64,
    pub pica_config_hash: u64,

    // --- Lite tier: from Snapshot ---
    pub budget: Option<f64>,
    pub phase: Option<usize>,
    pub eff_gap: Option<f64>,
    pub block_count: Option<usize>,
    pub gated_edges: Option<usize>,
    pub macro_n: Option<usize>,
    pub tau: Option<usize>,
    pub frob_from_rank1: Option<f64>,
    pub macro_gap: Option<f64>,
    pub sigma: Option<f64>,
    pub level1_frob: Option<f64>,
    pub p1_accepted: Option<u64>,
    pub p1_rejected: Option<u64>,
    pub p2_accepted: Option<u64>,
    pub p2_rejected: Option<u64>,
    pub traj_steps: Option<u64>,
    pub p2_repairs: Option<u64>,
    pub p2_violations: Option<u64>,

    // --- Standard tier: partition/packaging stats ---
    pub partition_stats: Option<PartitionStats>,
    pub packaging_stats: Option<PartitionStats>,
    pub lens_source: Option<u8>,
    pub packaging_source: Option<u8>,
    pub active_tau: Option<usize>,
    pub p6_rate_mult: Option<f64>,
    pub p6_cap_mult: Option<f64>,

    // --- Standard tier: event counters ---
    pub partition_flip_count: Option<u64>,
    pub packaging_flip_count: Option<u64>,
    pub tau_change_count: Option<u64>,
    pub last_partition_flip_step: Option<u64>,
    pub last_packaging_flip_step: Option<u64>,
    pub last_tau_change_step: Option<u64>,

    // --- Standard tier: cross-layer ratios ---
    pub macro_gap_ratio: Option<f64>,
    pub sigma_ratio: Option<f64>,

    // --- Rich tier: macro kernel diagnostics ---
    /// True finite-horizon path-reversal asymmetry with uniform initial distribution.
    /// Σ_{t=0}^{T-1} Σ_{i,j} ρ_t(i) P(i,j) log(P(i,j)/P(j,i)), ρ_0 = uniform.
    pub sigma_u: Option<f64>,
    pub max_asym: Option<f64>,
    pub cyc_mean: Option<f64>,
    pub cyc_max: Option<f64>,
    pub n_chiral: Option<usize>,
    pub trans_ep: Option<f64>,
    pub n_trans: Option<usize>,
    pub n_absorb: Option<usize>,

    // --- Rich tier: micro-kernel spectral summary ---
    /// Relaxation time of the micro (evolved) kernel: 1/(1-|λ₂|).
    pub micro_t_rel: Option<f64>,
    /// Gap ratio of the micro kernel: (λ₁-|λ₂|)/λ₁.
    pub micro_gap_ratio: Option<f64>,
    /// Eigenvalue entropy of the micro kernel nontrivial spectrum.
    pub micro_eigen_entropy: Option<f64>,
    /// Effective number of nontrivial modes (spectral participation ratio).
    pub micro_spectral_participation: Option<f64>,
    /// Top 5 nontrivial eigenvalue magnitudes of the micro kernel (sorted desc).
    #[serde(skip_serializing_if = "Option::is_none")]
    pub micro_top_eigenvalues: Option<Vec<f64>>,

    // --- Rich tier: multi-scale scan ---
    pub multi_scale_scan: Option<Vec<ScaleScanEntry>>,

    // --- Full config (self-describing records) ---
    /// Full PicaConfig serialization. Makes audit records self-describing
    /// so that pica_config_hash collisions and label mismatches are recoverable.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub pica_config: Option<serde_json::Value>,
}

/// Compute partition size statistics for any partition mapping.
pub fn partition_stats(partition: &[usize]) -> PartitionStats {
    let n = partition.len();
    if n == 0 {
        return PartitionStats {
            n_clusters: 0,
            min_size: 0,
            max_size: 0,
            entropy: 0.0,
            effective_k: 0.0,
        };
    }
    let nc = partition.iter().copied().max().unwrap_or(0) + 1;
    let mut sizes = vec![0usize; nc];
    for &c in partition {
        if c < nc {
            sizes[c] += 1;
        }
    }
    let min_size = sizes.iter().copied().filter(|&s| s > 0).min().unwrap_or(0);
    let max_size = sizes.iter().copied().max().unwrap_or(0);
    let mut entropy = 0.0f64;
    let n_f = n as f64;
    for &s in &sizes {
        if s > 0 {
            let p = s as f64 / n_f;
            entropy -= p * p.ln();
        }
    }
    let effective_k = if entropy.is_finite() {
        entropy.exp()
    } else {
        1.0
    };
    PartitionStats {
        n_clusters: nc,
        min_size,
        max_size,
        entropy,
        effective_k,
    }
}

/// Sanitize a float: map non-finite values to None.
fn sanitize(v: f64) -> Option<f64> {
    if v.is_finite() {
        Some(v)
    } else {
        None
    }
}

/// Sanitize a ratio: guard against zero/tiny denominators before dividing.
pub fn sanitize_ratio(num: f64, den: f64) -> Option<f64> {
    if den.abs() > 1e-12 {
        sanitize(num / den)
    } else {
        None
    }
}

/// Finite-horizon entropy production proxy with explicit initial distribution.
///
/// Computes:
///   Σ_{t=0}^{T-1} Σ_{i,j} ρ_t(i) P(i,j) log(P(i,j)/P(j,i))
/// + (H(ρ_T) - H(ρ_0))
/// where ρ_t = ρ_0 · P^t (marginals evolving from the given initial distribution).
///
/// Unlike `path_reversal_asymmetry` in substrate.rs (which ignores the initial
/// distribution and always uses stationary π), this function includes transient
/// occupancy effects and the system-entropy boundary term.
///
/// For macro kernels with k ≤ 64 and T ≤ 20, cost is O(T·k²) — negligible.
pub fn finite_horizon_sigma(kernel: &MarkovKernel, initial_dist: &[f64], horizon: usize) -> f64 {
    let n = kernel.n;
    if n == 0 || horizon == 0 || initial_dist.len() != n {
        return 0.0;
    }

    // Pre-compute the per-edge log-ratio: log(P(i,j)/P(j,i))
    // (only for edges where both directions are positive)
    let mut log_ratio = vec![vec![0.0f64; n]; n];
    for i in 0..n {
        for j in 0..n {
            let p_ij = kernel.kernel[i][j];
            let p_ji = kernel.kernel[j][i];
            if p_ij > 1e-15 && p_ji > 1e-15 {
                log_ratio[i][j] = (p_ij / p_ji).ln();
            } else if p_ij > 1e-15 && p_ji <= 1e-15 {
                log_ratio[i][j] = 30.0; // cap at ln(1e13)
            }
            // else: p_ij == 0, no contribution (0 * anything = 0)
        }
    }

    let mut rho = initial_dist.to_vec();
    let rho_sum: f64 = rho.iter().sum();
    if rho_sum <= 1e-30 {
        return 0.0;
    }
    for x in &mut rho {
        *x /= rho_sum;
    }
    let rho0 = rho.clone();
    let mut sigma = 0.0;

    for _t in 0..horizon {
        // Accumulate Σ_{i,j} ρ_t(i) P(i,j) log(P(i,j)/P(j,i))
        for i in 0..n {
            if rho[i] < 1e-30 {
                continue;
            }
            for j in 0..n {
                let p_ij = kernel.kernel[i][j];
                if p_ij > 1e-15 {
                    sigma += rho[i] * p_ij * log_ratio[i][j];
                }
            }
        }

        // Evolve: ρ_{t+1} = ρ_t · P
        let mut next = vec![0.0; n];
        for i in 0..n {
            if rho[i] < 1e-30 {
                continue;
            }
            for j in 0..n {
                next[j] += rho[i] * kernel.kernel[i][j];
            }
        }
        rho = next;
    }

    // System entropy boundary term: H(ρ_T) - H(ρ_0)
    let shannon = |dist: &[f64]| -> f64 {
        let mut h = 0.0;
        for &p in dist {
            if p > 1e-30 {
                h -= p * p.ln();
            }
        }
        h
    };
    sigma + (shannon(&rho) - shannon(&rho0))
}

/// Build a Lite-tier audit record from a Snapshot.
pub fn lite_from_snapshot(
    snap: &Snapshot,
    seed: u64,
    n: usize,
    pica_config_hash: u64,
) -> AuditRecord {
    AuditRecord {
        schema_version: 3,
        tier: "lite".into(),
        exp_id: None,
        config_name: None,
        git_sha: None,
        seed,
        n,
        step: snap.step,
        pica_config_hash,
        budget: sanitize(snap.budget),
        phase: Some(snap.phase),
        eff_gap: sanitize(snap.eff_gap),
        block_count: Some(snap.block_count),
        gated_edges: Some(snap.gated_edges),
        macro_n: Some(snap.macro_n),
        tau: Some(snap.tau),
        frob_from_rank1: sanitize(snap.frob_from_rank1),
        macro_gap: sanitize(snap.macro_gap),
        sigma: sanitize(snap.sigma),
        level1_frob: sanitize(snap.level1_frob),
        p1_accepted: Some(snap.p1_accepted),
        p1_rejected: Some(snap.p1_rejected),
        p2_accepted: Some(snap.p2_accepted),
        p2_rejected: Some(snap.p2_rejected),
        traj_steps: Some(snap.traj_steps),
        p2_repairs: Some(snap.p2_repairs),
        p2_violations: Some(snap.p2_violations),
        // Higher tiers: None
        partition_stats: None,
        packaging_stats: None,
        lens_source: None,
        packaging_source: None,
        active_tau: None,
        p6_rate_mult: None,
        p6_cap_mult: None,
        partition_flip_count: None,
        packaging_flip_count: None,
        tau_change_count: None,
        last_partition_flip_step: None,
        last_packaging_flip_step: None,
        last_tau_change_step: None,
        macro_gap_ratio: None,
        sigma_ratio: None,
        sigma_u: None,
        max_asym: None,
        cyc_mean: None,
        cyc_max: None,
        n_chiral: None,
        trans_ep: None,
        n_trans: None,
        n_absorb: None,
        micro_t_rel: None,
        micro_gap_ratio: None,
        micro_eigen_entropy: None,
        micro_spectral_participation: None,
        micro_top_eigenvalues: None,
        multi_scale_scan: None,
        pica_config: None,
    }
}

/// Build a Standard-tier audit record from dynamics state at end-of-run or refresh.
pub fn standard_from_state(
    state: &AugmentedState,
    config: &DynamicsConfig,
    snap: &Snapshot,
    pica_config_hash: u64,
) -> AuditRecord {
    let mut rec = lite_from_snapshot(snap, config.seed, config.n, pica_config_hash);
    rec.tier = "standard".into();

    // Partition stats
    if let Some(ref part) = state.pica_state.spectral_partition {
        rec.partition_stats = Some(partition_stats(part));
    }
    if let Some(ref pkg) = state.pica_state.active_packaging {
        rec.packaging_stats = Some(partition_stats(pkg));
    }

    // PICA metadata
    rec.lens_source = state.pica_state.active_lens_source;
    rec.packaging_source = state.pica_state.packaging_source;
    rec.active_tau = state.pica_state.active_tau;
    rec.p6_rate_mult = sanitize(state.pica_state.active_p6_rate_mult);
    rec.p6_cap_mult = sanitize(state.pica_state.active_p6_cap_mult);

    // Event counters
    rec.partition_flip_count = Some(state.pica_state.partition_flip_count);
    rec.packaging_flip_count = Some(state.pica_state.packaging_flip_count);
    rec.tau_change_count = Some(state.pica_state.tau_change_count);
    rec.last_partition_flip_step = if state.pica_state.last_partition_flip_step > 0 {
        Some(state.pica_state.last_partition_flip_step)
    } else {
        None
    };
    rec.last_packaging_flip_step = if state.pica_state.last_packaging_flip_step > 0 {
        Some(state.pica_state.last_packaging_flip_step)
    } else {
        None
    };
    rec.last_tau_change_step = if state.pica_state.last_tau_change_step > 0 {
        Some(state.pica_state.last_tau_change_step)
    } else {
        None
    };

    // Cross-layer ratios
    if snap.eff_gap > 1e-15 && snap.macro_gap.is_finite() {
        rec.macro_gap_ratio = sanitize(snap.macro_gap / snap.eff_gap);
    }

    rec
}

/// Build a Rich-tier audit record with full macro diagnostics and multi-scale scan.
///
/// `macro_kernel` is the macro kernel built from the final partition.
/// This function computes expensive diagnostics (chirality, EP, multi-scale).
pub fn rich_from_state(
    state: &AugmentedState,
    config: &DynamicsConfig,
    snap: &Snapshot,
    macro_kernel: &MarkovKernel,
    pica_config_hash: u64,
) -> AuditRecord {
    let mut rec = standard_from_state(state, config, snap, pica_config_hash);
    rec.tier = "rich".into();

    let macro_n = macro_kernel.n;
    if macro_n >= 2 {
        // Directionality diagnostics on macro kernel
        let uniform: Vec<f64> = vec![1.0 / macro_n as f64; macro_n];

        use six_primitives_core::substrate::{cycle_chirality, frobenius_asymmetry, transient_ep};

        // True finite-horizon sigma with uniform initial distribution.
        // Unlike path_reversal_asymmetry (which ignores initial_dist and
        // always uses stationary π), this correctly captures transient
        // approach-to-stationarity effects.
        let macro_sigma_u = finite_horizon_sigma(macro_kernel, &uniform, 10);
        rec.sigma_u = sanitize(macro_sigma_u);
        rec.max_asym = sanitize(frobenius_asymmetry(macro_kernel));
        let (cm, cx, nc) = cycle_chirality(macro_kernel, 1e-10);
        rec.cyc_mean = sanitize(cm);
        rec.cyc_max = sanitize(cx);
        rec.n_chiral = Some(nc);
        let (tep, nt) = transient_ep(macro_kernel);
        rec.trans_ep = sanitize(tep);
        rec.n_trans = Some(nt);
        rec.n_absorb = Some(
            (0..macro_n)
                .filter(|&i| macro_kernel.kernel[i][i] > 1.0 - 1e-10)
                .count(),
        );

        // sigma_ratio: finite-horizon macro/micro EP ratio at matched tau.
        // Uses the same non-stationary definition for numerator/denominator.
        let gap = state.effective_kernel.spectral_gap();
        let tau = state
            .pica_state
            .active_tau
            .unwrap_or_else(|| crate::observe::adaptive_tau(gap, config.tau_alpha));
        let ktau = helpers::matrix_power(&state.effective_kernel, tau);
        let micro_uniform = vec![1.0 / ktau.n as f64; ktau.n];
        let micro_sigma_u = finite_horizon_sigma(&ktau, &micro_uniform, 10);
        if macro_sigma_u.is_finite() {
            // Avoid near-zero denominator blowups in weakly irreversible kernels.
            if micro_sigma_u > 1e-4 {
                rec.sigma_ratio = sanitize_ratio(macro_sigma_u, micro_sigma_u);
            }
        }
    }

    // Multi-scale scan (use active tau from PICA or snapshot, not default)
    let scan_tau = state.pica_state.active_tau.or(Some(snap.tau));
    rec.multi_scale_scan = Some(multi_scale_scan(&state.effective_kernel, config, scan_tau));

    rec
}

/// Multi-scale scan: for each k in {2,4,8,16,...,min(64,n/2)}, build a macro
/// kernel and compute standard diagnostics. Rich tier only.
///
/// `tau_override`: if `Some(t)`, use that τ for K^τ (matching the actual run's
/// timescale); if `None`, fall back to spectral-gap-based default.
pub fn multi_scale_scan(
    kernel: &MarkovKernel,
    config: &DynamicsConfig,
    tau_override: Option<usize>,
) -> Vec<ScaleScanEntry> {
    use six_primitives_core::substrate::{
        cycle_chirality, frobenius_asymmetry, path_reversal_asymmetry,
    };

    let n = kernel.n;
    let tau = tau_override.unwrap_or_else(|| {
        let gap = kernel.spectral_gap();
        config.pica.active_tau_or_default(gap, config.tau_alpha)
    });
    let ktau = helpers::matrix_power(kernel, tau);

    let mut entries = Vec::new();
    let mut k = 2usize;
    let max_k = 64.min(n / 2).max(2);
    let mut seen_k = std::collections::BTreeSet::new();

    while k <= max_k {
        let partition = crate::spectral::spectral_partition(kernel, k);
        let actual_k = crate::spectral::n_clusters(&partition);
        if actual_k < 2 || !seen_k.insert(actual_k) {
            k *= 2;
            continue;
        }

        let macro_k = helpers::build_macro_from_ktau(&ktau.kernel, &partition, actual_k);
        let pi = macro_k.stationary(10000, 1e-12);

        let (cm, cx, nc) = cycle_chirality(&macro_k, 1e-10);

        // Lagrangian probes
        let lagr_eps = 1e-15;
        let s_ent = crate::lagrange::step_entropy(&pi, &macro_k);
        let pla2 = crate::lagrange::pla2_gap(&pi, &macro_k, lagr_eps);
        let embed = crate::lagrange::spectral_embed_reversible(&pi, &macro_k);
        let geo_r2 = if !embed.coords.is_empty() {
            crate::lagrange::lagr_geo_r2(&pi, &macro_k, &embed.coords, lagr_eps)
        } else {
            f64::NAN
        };
        let (diff_alpha, diff_kl) = if !embed.coords.is_empty() {
            crate::lagrange::fit_diffusion_kl(&pi, &macro_k, &embed.coords)
        } else {
            (f64::NAN, f64::NAN)
        };
        // Spectral conservation probes
        let t_rel = crate::lagrange::relaxation_time(&embed.eigenvalues);
        let gap_rat = crate::lagrange::spectral_gap_ratio(&embed.eigenvalues);
        let e_entropy = crate::lagrange::eigenvalue_entropy(&embed.eigenvalues);
        let s_part = crate::lagrange::spectral_participation(&embed.eigenvalues);
        let sm_r50 = crate::lagrange::relative_slow_modes(&embed.eigenvalues, 0.5);
        let sm_r70 = crate::lagrange::relative_slow_modes(&embed.eigenvalues, 0.7);
        let sm_r90 = crate::lagrange::relative_slow_modes(&embed.eigenvalues, 0.9);
        let nt_eigs = crate::lagrange::nontrivial_eigenvalues(&embed.eigenvalues);

        let entry = ScaleScanEntry {
            k: actual_k,
            macro_gap: sanitize(macro_k.spectral_gap()),
            frob: sanitize(crate::observe::frob_from_rank1(&macro_k)),
            sigma_pi: sanitize(path_reversal_asymmetry(&macro_k, &pi, 10)),
            max_asym: sanitize(frobenius_asymmetry(&macro_k)),
            cyc_mean: sanitize(cm),
            cyc_max: sanitize(cx),
            n_chiral: Some(nc),
            step_entropy: sanitize(s_ent),
            pla2_gap: sanitize(pla2),
            lagr_geo_r2: sanitize(geo_r2),
            lagr_diff_kl: sanitize(diff_kl),
            lagr_diff_alpha: sanitize(diff_alpha),
            t_rel: sanitize(t_rel),
            gap_ratio: sanitize(gap_rat),
            eigen_entropy: sanitize(e_entropy),
            spectral_participation: sanitize(s_part),
            slow_modes_r50: Some(sm_r50),
            slow_modes_r70: Some(sm_r70),
            slow_modes_r90: Some(sm_r90),
            nontrivial_eigenvalues: if nt_eigs.is_empty() {
                None
            } else {
                Some(nt_eigs)
            },
        };
        entries.push(entry);
        k *= 2;
    }

    entries
}

/// Compute a stable hash of the PICA enable matrix, selectors, and per-cell parameters.
/// Includes the 6×6 boolean enable matrix, both selectors, and core tunable parameters.
/// Simple FNV-like hash (not cryptographic).
///
/// NOTE: The following parameters are NOT included in the hash (for historical reasons):
///   p1_p1_cooldown, p2_p1_protect_steps, p2_p2_cooldown,
///   p1_p4_boundary_boost, p2_p5_boundary_boost, p1_p6_budget_threshold_frac,
///   p3_p3_tau_cap, partition_interval, l1_audit_interval, rm_refresh_interval,
///   packaging_interval, p6_refresh_interval.
/// Two configs differing only in these parameters will have identical hashes.
/// Use `pica_config` (full serialization) in audit records for unambiguous identity.
pub fn pica_config_hash(config: &crate::pica::PicaConfig) -> u64 {
    let mut h: u64 = 0xcbf29ce484222325;
    for a in 0..6 {
        for i in 0..6 {
            h ^= config.enabled[a][i] as u64;
            h = h.wrapping_mul(0x100000001b3);
        }
    }
    // Mix in lens_selector discriminant
    let sel_byte = match config.lens_selector {
        crate::pica::config::LensSelector::MinRM => 0u64,
        crate::pica::config::LensSelector::MaxGap => 1,
        crate::pica::config::LensSelector::MaxFrob => 2,
    };
    h ^= sel_byte;
    h = h.wrapping_mul(0x100000001b3);
    // Mix in per-cell parameters (each as raw u64 bits of f64)
    let mix_f64 = |h: &mut u64, v: f64| {
        *h ^= v.to_bits();
        *h = h.wrapping_mul(0x100000001b3);
    };
    mix_f64(&mut h, config.p3_p4_sector_boost);
    mix_f64(&mut h, config.p6_p4_ep_boost);
    mix_f64(&mut h, config.p6_p6_dpi_cap_scale);
    mix_f64(&mut h, config.p3_p6_mixer_strength);
    mix_f64(&mut h, config.p3_p6_frob_scale);
    mix_f64(&mut h, config.p2_p6_sbrc_strength);
    mix_f64(&mut h, config.p1_p3_rm_boost);
    mix_f64(&mut h, config.p2_p3_rm_boost);
    mix_f64(&mut h, config.p2_p4_inter_boost);
    // Mix in packaging_selector
    let pkg_byte = match config.packaging_selector {
        crate::pica::config::LensSelector::MinRM => 0u64,
        crate::pica::config::LensSelector::MaxGap => 1,
        crate::pica::config::LensSelector::MaxFrob => 2,
    };
    h ^= pkg_byte;
    h = h.wrapping_mul(0x100000001b3);
    h
}

/// Force all Option<f64> fields to None if they contain non-finite values.
/// Safety net: if a caller bypasses sanitize() and sets Some(NaN) or Some(Inf)
/// directly, this prevents serialization failure (serde_json rejects NaN/Inf).
fn sanitize_record(record: &mut AuditRecord) {
    let guard = |v: &mut Option<f64>| {
        if let Some(x) = v {
            if !x.is_finite() {
                *v = None;
            }
        }
    };
    guard(&mut record.budget);
    guard(&mut record.eff_gap);
    guard(&mut record.frob_from_rank1);
    guard(&mut record.macro_gap);
    guard(&mut record.sigma);
    guard(&mut record.level1_frob);
    guard(&mut record.macro_gap_ratio);
    guard(&mut record.sigma_ratio);
    guard(&mut record.sigma_u);
    guard(&mut record.max_asym);
    guard(&mut record.cyc_mean);
    guard(&mut record.cyc_max);
    guard(&mut record.trans_ep);
    guard(&mut record.p6_rate_mult);
    guard(&mut record.p6_cap_mult);
    guard(&mut record.micro_t_rel);
    guard(&mut record.micro_gap_ratio);
    guard(&mut record.micro_eigen_entropy);
    guard(&mut record.micro_spectral_participation);
    if let Some(ref mut eigs) = record.micro_top_eigenvalues {
        for v in eigs.iter_mut() {
            if !v.is_finite() {
                *v = 0.0;
            }
        }
    }
    if let Some(ref mut ps) = record.partition_stats {
        if !ps.entropy.is_finite() {
            ps.entropy = 0.0;
        }
        if !ps.effective_k.is_finite() {
            ps.effective_k = 1.0;
        }
    }
    if let Some(ref mut ps) = record.packaging_stats {
        if !ps.entropy.is_finite() {
            ps.entropy = 0.0;
        }
        if !ps.effective_k.is_finite() {
            ps.effective_k = 1.0;
        }
    }
    if let Some(ref mut entries) = record.multi_scale_scan {
        for e in entries.iter_mut() {
            guard(&mut e.macro_gap);
            guard(&mut e.frob);
            guard(&mut e.sigma_pi);
            guard(&mut e.max_asym);
            guard(&mut e.cyc_mean);
            guard(&mut e.cyc_max);
            guard(&mut e.step_entropy);
            guard(&mut e.pla2_gap);
            guard(&mut e.lagr_geo_r2);
            guard(&mut e.lagr_diff_kl);
            guard(&mut e.lagr_diff_alpha);
            guard(&mut e.t_rel);
            guard(&mut e.gap_ratio);
            guard(&mut e.eigen_entropy);
            guard(&mut e.spectral_participation);
            // nontrivial_eigenvalues: guard individual floats
            if let Some(ref mut eigs) = e.nontrivial_eigenvalues {
                for v in eigs.iter_mut() {
                    if !v.is_finite() {
                        *v = 0.0;
                    }
                }
            }
        }
    }
}

/// Serialize an AuditRecord to a JSON string.
/// Applies a final sanitization pass to guard against any non-finite floats
/// that bypassed per-field sanitize() calls.
pub fn to_json(record: &AuditRecord) -> Option<String> {
    let mut rec = record.clone();
    sanitize_record(&mut rec);
    serde_json::to_string(&rec).ok()
}
