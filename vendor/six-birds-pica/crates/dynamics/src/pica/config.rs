//! PICA configuration: enable/disable matrix and per-cell parameters.
//!
//! ## Index convention
//!
//! Cell indices: P1=0, P2=1, P3=2, P4=3, P5=4, P6=5.
//! `enabled[actor][informant] = true` means the cell is active during dynamics.
//!
//! Group A cells (25 action cells) are controlled by the enable matrix:
//! - `enabled[0][*]` — P1 row (A1-A6): row targeting for kernel perturbation
//! - `enabled[1][*]` — P2 row (A7-A12): edge targeting for gating
//! - `enabled[2][*]` — P3 row (A13,A18-A20): mixture weights + adaptive tau
//! - `enabled[3][*]` — P4 row (A14-A17): lens/partition selection
//! - `enabled[4][*]` — P5 row (A21-A23): packaging selection
//! - `enabled[5][*]` — P6 row (A24-A25): budget modulation
//!
//! Group D (diagnostics) are called at observation time regardless of config.
//! Groups I (implicit) and T (trivial) need no config.
//!
//! ## Presets
//!
//! | Preset | Cells enabled | Reproduces | Use when |
//! |--------|--------------|------------|----------|
//! | `none()` | (none) | Uniform/default | No modulation baseline |
//! | `baseline()` | A10 + A15 | EXP-080/090 | Default for new experiments |
//! | `sbrc()` | A10 + A12 + A15 | EXP-095/096 | Signed boundary coupling |
//! | `mixer()` | A10 + A12 + A13 + A15 | EXP-098 | Adaptive mixture weights |
//! | `full_action()` | All 25 A-cells (skip A16) | EXP-100+ | Full PICA exploration |
//! | `full_lens()` | A10 + A14-A17 | EXP-103+ | Lens selection sweep |
//! | `full_all()` | All 25 A-cells (incl A16) | EXP-104+ | Complete PICA |
//!
//! ## Cell interaction rules
//!
//! **Safe to combine freely:** P1-row and P2-row cells produce weights that multiply.
//!
//! **Watch for compounding suppression:** A1 + A6 + A5 together can suppress P1 to
//! near-zero. Correct behavior but may look like P1 is "stuck" in logs.
//!
//! **A10 is the essential cell:** Without spectral-guided P2 gating, emergence does
//! not occur. All other cells modulate emergence that A10 creates.
//!
//! **A15 is the canonical lens:** The spectral partition is now an explicit PICA cell.
//! All presets that need a partition enable A15. Other P4-row cells (A14, A16, A17)
//! provide alternative lenses that may be selected when multiple are enabled.
//!
//! **P4-row cells use selection, not multiplication:** Partitions are discrete and
//! can't be multiplied. `LensSelector` (MinRM/MaxGap/MaxFrob) picks the best candidate.

/// Strategy for selecting among multiple P4-row lens candidates.
///
/// When multiple P4 cells are enabled (e.g., A14 + A15), each produces a
/// candidate partition. The selector determines which criterion picks the winner.
#[derive(Clone, Copy, Debug, serde::Serialize)]
pub enum LensSelector {
    /// Select partition with lowest global route mismatch (most CG-consistent).
    MinRM,
    /// Select partition with largest macro spectral gap (best time-scale separation).
    MaxGap,
    /// Select partition with highest macro Frobenius deviation (most structured).
    MaxFrob,
}

/// Configuration for the Primitive Interaction Closure Algebra.
#[derive(Clone, serde::Serialize)]
pub struct PicaConfig {
    /// Enable matrix: enabled[actor][informant].
    /// Actor indices: P1=0, P2=1, P3=2, P4=3, P5=4, P6=5.
    pub enabled: [[bool; 6]; 6],

    // === Per-cell parameters ===

    // A1: P1<-P1 history cooldown
    /// Steps before a recently-rewritten row can be targeted again.
    pub p1_p1_cooldown: u64,

    // A3: P1<-P3 route-mismatch rewrite
    /// Amplification factor for RM-based row weights.
    pub p1_p3_rm_boost: f64,

    // A4: P1<-P4 sector-boundary rewrite
    /// Boost for rows near cluster boundaries.
    pub p1_p4_boundary_boost: f64,

    // A6: P1<-P6 budget-gated rewrite
    /// Budget threshold below which P1 is suppressed (fraction of budget_cap).
    pub p1_p6_budget_threshold_frac: f64,

    // A7: P2<-P1 protect recently-rewritten rows
    /// Steps to protect edges of rewritten rows from gating.
    pub p2_p1_protect_steps: u64,

    // A8: P2<-P2 flip cooldown
    /// Steps before a recently-flipped edge can be flipped again.
    pub p2_p2_cooldown: u64,

    // A9: P2<-P3 RM-guided gating
    /// Amplification for RM-based edge weights.
    pub p2_p3_rm_boost: f64,

    // A10: P2<-P4 spectral-guided gating
    /// Boost factor for inter-cluster edge flips.
    pub p2_p4_inter_boost: f64,

    // A11: P2<-P5 package-boundary gating
    /// Boost for cross-package edges (higher = more aggressive gating). Default 1.5.
    pub p2_p5_boundary_boost: f64,

    // A12: P2<-P6 SBRC penalty
    /// Violation cost strength (multiplied by level1_frob).
    pub p2_p6_sbrc_strength: f64,

    // A13: P3<-P6 frob-modulated mixture
    /// How strongly to modulate weights. Default 2.0.
    pub p3_p6_mixer_strength: f64,
    /// Frob value at which structure is "fully interesting". Default 1.5.
    pub p3_p6_frob_scale: f64,

    // P4 row: lens selection
    /// Strategy for choosing among multiple P4-row lens candidates.
    pub lens_selector: LensSelector,

    // A18: P3<-P3 adaptive tau
    /// Maximum tau value from multi-scale RM analysis. Default 10000.
    pub p3_p3_tau_cap: usize,

    // A19: P3<-P4 sector-dependent mixture
    /// Boost for P1/P2 weights when current sector has high RM. Default 2.0.
    pub p3_p4_sector_boost: f64,

    // A24: P6<-P4 sector EP budget
    /// EP imbalance factor above which budget rate is boosted. Default 2.0.
    pub p6_p4_ep_boost: f64,

    // A25: P6<-P6 EP retention cap
    /// EP retention threshold. When retention < threshold, tighten budget cap.
    /// Retention = macro_EP / micro_EP(K^tau) ∈ [0, 1]. Default 0.1.
    pub p6_p6_dpi_cap_scale: f64,

    // P5 row: packaging selection
    /// Strategy for choosing among multiple P5-row packaging candidates.
    /// Reuses LensSelector: MinRM, MaxGap, MaxFrob.
    pub packaging_selector: LensSelector,

    // Refresh intervals
    /// Steps between spectral partition refreshes.
    pub partition_interval: u64,
    /// Steps between Level 1 audit refreshes.
    pub l1_audit_interval: u64,
    /// Steps between cluster RM refreshes.
    pub rm_refresh_interval: u64,
    /// Steps between P5 packaging refreshes.
    pub packaging_interval: u64,
    /// Steps between P6 budget modulation refreshes.
    pub p6_refresh_interval: u64,
}

impl PicaConfig {
    /// All cells disabled (pure random primitives, no modulations).
    pub fn none() -> Self {
        PicaConfig {
            enabled: [[false; 6]; 6],
            p1_p1_cooldown: 200,
            p1_p3_rm_boost: 2.0,
            p1_p4_boundary_boost: 2.0,
            p1_p6_budget_threshold_frac: 0.5,
            p2_p1_protect_steps: 100,
            p2_p2_cooldown: 50,
            p2_p3_rm_boost: 2.0,
            p2_p4_inter_boost: 4.0,
            p2_p5_boundary_boost: 1.5,
            p2_p6_sbrc_strength: 5.0,
            p3_p6_mixer_strength: 2.0,
            p3_p6_frob_scale: 1.5,
            lens_selector: LensSelector::MinRM,
            p3_p3_tau_cap: 10000,
            p3_p4_sector_boost: 2.0,
            p6_p4_ep_boost: 2.0,
            p6_p6_dpi_cap_scale: 0.1,
            packaging_selector: LensSelector::MinRM,
            partition_interval: 500,
            l1_audit_interval: 1000,
            rm_refresh_interval: 500,
            packaging_interval: 500,
            p6_refresh_interval: 500,
        }
    }

    /// Baseline: P2<-P4 (spectral-guided gating) + P4<-P4 (spectral lens).
    /// Reproduces EXP-080/090 behavior.
    pub fn baseline() -> Self {
        let mut cfg = Self::none();
        cfg.enabled[1][3] = true; // P2 <- P4
        cfg.enabled[3][3] = true; // P4 <- P4 (A15: spectral lens)
        cfg
    }

    /// SBRC config: P2<-P4 + P2<-P6. Reproduces EXP-095/096 behavior.
    pub fn sbrc() -> Self {
        let mut cfg = Self::baseline();
        cfg.enabled[1][5] = true; // P2 <- P6
        cfg
    }

    /// Mixer config: P2<-P4 + P2<-P6 + P3<-P6. Reproduces EXP-098 behavior.
    pub fn mixer() -> Self {
        let mut cfg = Self::sbrc();
        cfg.enabled[2][5] = true; // P3 <- P6
        cfg
    }

    /// Full Group A: all 25 action modulation cells enabled.
    pub fn full_action() -> Self {
        let mut cfg = Self::none();
        // P1 row: P1<-{P1,P2,P3,P4,P5,P6}
        for j in 0..6 {
            cfg.enabled[0][j] = true;
        }
        // P2 row: P2<-{P1,P2,P3,P4,P5,P6}
        for j in 0..6 {
            cfg.enabled[1][j] = true;
        }
        // P3 row: P3<-{P3,P4,P5,P6}
        cfg.enabled[2][2] = true; // A18: P3<-P3 (adaptive tau)
        cfg.enabled[2][3] = true; // A19: P3<-P4 (sector mixing)
        cfg.enabled[2][4] = true; // A20: P3<-P5 (packaging mixing)
        cfg.enabled[2][5] = true; // A13: P3<-P6 (frob mixer)
                                  // P4 row: P4<-{P3,P4,P6} (skip P4<-P5 until validated)
        cfg.enabled[3][2] = true; // A14: P4<-P3 (RM-quantile)
        cfg.enabled[3][3] = true; // A15: P4<-P4 (spectral)
        cfg.enabled[3][5] = true; // A17: P4<-P6 (EP-flow)
                                  // P5 row: P5<-{P3,P4,P6}
        cfg.enabled[4][2] = true; // A21: P5<-P3 (RM-similarity)
        cfg.enabled[4][3] = true; // A22: P5<-P4 (sector-balanced)
        cfg.enabled[4][5] = true; // A23: P5<-P6 (EP-similarity)
                                  // P6 row: P6<-{P4,P6}
        cfg.enabled[5][3] = true; // A24: P6<-P4 (sector EP budget)
        cfg.enabled[5][5] = true; // A25: P6<-P6 (DPI cap)
        cfg
    }

    /// Combo: A1 (cooldown) + A3 (RM-rewrite) + A10 (spectral-guided) + A15 (spectral lens).
    /// Macro consistency with settling time.
    pub fn combo_rm() -> Self {
        let mut cfg = Self::baseline(); // already has A10 + A15
        cfg.enabled[0][0] = true; // P1 <- P1 (cooldown)
        cfg.enabled[0][2] = true; // P1 <- P3 (RM-rewrite)
        cfg
    }

    /// Combo: A1 + A3 + A12 + A10. RM-rewrite + SBRC cost modulation.
    pub fn combo_structure() -> Self {
        let mut cfg = Self::combo_rm();
        cfg.enabled[1][5] = true; // P2 <- P6 (SBRC)
        cfg
    }

    /// Full Group A minus A11 (package-boundary gating, which can create absorbers)
    /// and A16 (P4<-P5, unvalidated).
    pub fn full_action_safe() -> Self {
        let mut cfg = Self::full_action();
        cfg.enabled[1][4] = false; // Disable P2 <- P5
        cfg.enabled[3][4] = false; // Disable P4 <- P5
        cfg
    }

    /// Full lens: all 4 P4-row cells enabled with MinRM selector.
    pub fn full_lens() -> Self {
        let mut cfg = Self::baseline();
        cfg.enabled[3][2] = true; // A14: P4<-P3
        cfg.enabled[3][3] = true; // A15: P4<-P4
        cfg.enabled[3][4] = true; // A16: P4<-P5
        cfg.enabled[3][5] = true; // A17: P4<-P6
        cfg.lens_selector = LensSelector::MinRM;
        cfg
    }

    /// All 25 action cells enabled, including P4<-P5 (A16) which full_action() skips.
    pub fn full_all() -> Self {
        let mut cfg = Self::full_action();
        cfg.enabled[3][4] = true; // A16: P4<-P5
        cfg
    }

    /// Enable a single cell (on top of the base config).
    pub fn with_cell(mut self, actor: usize, informant: usize) -> Self {
        if actor < 6 && informant < 6 {
            self.enabled[actor][informant] = true;
        }
        self
    }

    /// Check if any P1-row cells are enabled.
    pub fn any_p1_modulation(&self) -> bool {
        self.enabled[0].iter().any(|&e| e)
    }

    /// Check if any P2-row cells are enabled.
    pub fn any_p2_modulation(&self) -> bool {
        self.enabled[1].iter().any(|&e| e)
    }

    /// Check if any P3-row cells are enabled.
    pub fn any_p3_modulation(&self) -> bool {
        self.enabled[2].iter().any(|&e| e)
    }

    /// Check if any P4-row cells are enabled (lens producers).
    pub fn any_p4_enabled(&self) -> bool {
        self.enabled[3].iter().any(|&e| e)
    }

    /// Check if any P5-row cells are enabled (packaging producers).
    pub fn any_p5_enabled(&self) -> bool {
        self.enabled[4].iter().any(|&e| e)
    }

    /// Check if any P6-row cells are enabled (budget modulation).
    pub fn any_p6_modulation(&self) -> bool {
        self.enabled[5].iter().any(|&e| e)
    }

    /// Whether a partition is needed (any cell uses P4 as informant, or any P4-row cell produces one).
    pub fn needs_partition(&self) -> bool {
        (0..6).any(|actor| self.enabled[actor][3]) || self.any_p4_enabled()
    }

    /// Whether packaging refresh is needed (any P5-row cell enabled, or any cell reads packaging).
    pub fn needs_packaging(&self) -> bool {
        self.any_p5_enabled()
            || self.enabled[0][4]  // A5: P1<-P5
            || self.enabled[1][4]  // A11: P2<-P5
            || self.enabled[2][4] // A20: P3<-P5
    }

    /// Whether Level 1 audit is needed (any cell uses P6 as informant for cross-layer).
    pub fn needs_l1_audit(&self) -> bool {
        // P1<-P6 (budget gate), P2<-P6 (SBRC), P3<-P6 (mixer), P6<-P6 (DPI cap)
        self.enabled[0][5] || self.enabled[1][5] || self.enabled[2][5] || self.enabled[5][5]
    }

    /// Whether cluster RM is needed (computed on spectral_partition).
    /// Producers: any cell in column P3 (enabled[actor][2]) triggers RM computation.
    /// Consumers: A19 (P3←P4) reads cluster_rm directly.
    /// Note: A20 (P3←P5) now reads packaging_rm instead — see needs_packaging_rm().
    pub fn needs_cluster_rm(&self) -> bool {
        (0..6).any(|actor| self.enabled[actor][2]) || self.enabled[2][3] // A19: P3←P4 reads cluster_rm
    }

    /// Whether packaging RM is needed (computed on active_packaging).
    /// Consumer: A20 (P3←P5) reads packaging_rm.
    pub fn needs_packaging_rm(&self) -> bool {
        self.enabled[2][4] // A20: P3←P5 reads packaging_rm
    }

    /// Get the active tau from PICA state, or compute from spectral gap.
    /// Convenience for audit code that doesn't have access to PicaState.
    pub fn active_tau_or_default(&self, gap: f64, tau_alpha: f64) -> usize {
        // This method cannot access PicaState.active_tau, so callers that have
        // PicaState should check active_tau first. This computes the default.
        crate::observe::adaptive_tau(gap, tau_alpha)
    }

    /// Cell label for logging.
    pub fn cell_label(actor: usize, informant: usize) -> &'static str {
        const LABELS: [[&str; 6]; 6] = [
            ["P1<-P1", "P1<-P2", "P1<-P3", "P1<-P4", "P1<-P5", "P1<-P6"],
            ["P2<-P1", "P2<-P2", "P2<-P3", "P2<-P4", "P2<-P5", "P2<-P6"],
            ["P3<-P1", "P3<-P2", "P3<-P3", "P3<-P4", "P3<-P5", "P3<-P6"],
            ["P4<-P1", "P4<-P2", "P4<-P3", "P4<-P4", "P4<-P5", "P4<-P6"],
            ["P5<-P1", "P5<-P2", "P5<-P3", "P5<-P4", "P5<-P5", "P5<-P6"],
            ["P6<-P1", "P6<-P2", "P6<-P3", "P6<-P4", "P6<-P5", "P6<-P6"],
        ];
        if actor < 6 && informant < 6 {
            LABELS[actor][informant]
        } else {
            "INVALID"
        }
    }

    /// List enabled cells as labels.
    pub fn enabled_labels(&self) -> Vec<&'static str> {
        let mut out = vec![];
        for a in 0..6 {
            for i in 0..6 {
                if self.enabled[a][i] {
                    out.push(Self::cell_label(a, i));
                }
            }
        }
        out
    }

    /// Clone config for macro-level dynamics (same cells, shorter intervals for small kernels).
    pub fn clone_for_macro(&self) -> Self {
        PicaConfig {
            enabled: self.enabled,
            p1_p1_cooldown: self.p1_p1_cooldown / 2,
            p1_p3_rm_boost: self.p1_p3_rm_boost,
            p1_p4_boundary_boost: self.p1_p4_boundary_boost,
            p1_p6_budget_threshold_frac: self.p1_p6_budget_threshold_frac,
            p2_p1_protect_steps: self.p2_p1_protect_steps / 2,
            p2_p2_cooldown: self.p2_p2_cooldown / 2,
            p2_p3_rm_boost: self.p2_p3_rm_boost,
            p2_p4_inter_boost: self.p2_p4_inter_boost,
            p2_p5_boundary_boost: self.p2_p5_boundary_boost,
            p2_p6_sbrc_strength: self.p2_p6_sbrc_strength,
            p3_p6_mixer_strength: self.p3_p6_mixer_strength,
            p3_p6_frob_scale: self.p3_p6_frob_scale,
            lens_selector: self.lens_selector,
            p3_p3_tau_cap: self.p3_p3_tau_cap,
            p3_p4_sector_boost: self.p3_p4_sector_boost,
            p6_p4_ep_boost: self.p6_p4_ep_boost,
            p6_p6_dpi_cap_scale: self.p6_p6_dpi_cap_scale,
            packaging_selector: self.packaging_selector,
            partition_interval: 100,
            l1_audit_interval: 200,
            rm_refresh_interval: 100,
            packaging_interval: 100,
            p6_refresh_interval: 100,
        }
    }

    /// Validate config and return warnings for suspicious or no-op cell configurations.
    /// Does NOT prevent execution — warnings are advisory only.
    pub fn validate(&self) -> Vec<String> {
        let mut warnings = Vec::new();

        // Implicit cells (P1/P2 mutations propagate through kernel refresh):
        // P3←P1 (enabled[2][0]) and P3←P2 (enabled[2][1]) have no action cell
        let implicit_cells: [(usize, usize, &str); 8] = [
            (2, 0, "P3←P1"),
            (2, 1, "P3←P2"), // P3 row implicit
            (3, 0, "P4←P1"),
            (3, 1, "P4←P2"), // P4 row implicit
            (4, 0, "P5←P1"),
            (4, 1, "P5←P2"), // P5 row implicit
            (5, 0, "P6←P1"),
            (5, 1, "P6←P2"), // P6 row implicit
        ];
        for (a, i, label) in &implicit_cells {
            if self.enabled[*a][*i] {
                warnings.push(format!(
                    "{} is implicit (Group I): enabling it has no direct effect. \
                     P1/P2 mutations propagate automatically through kernel refresh.",
                    label
                ));
            }
        }

        // Trivial cells
        if self.enabled[4][4] {
            warnings
                .push("P5←P5 is trivial (packaging idempotence): enabling it is a no-op.".into());
        }
        if self.enabled[5][2] {
            warnings.push("P6←P3 is trivial (circular dependency): enabling it is a no-op.".into());
        }

        // P6←P5 is undefined
        if self.enabled[5][4] {
            warnings.push("P6←P5 is undefined: enabling it has no effect.".into());
        }

        // Data-starved: A20 (P3←P5) without any P5 producer
        if self.enabled[2][4] && !self.any_p5_enabled() {
            warnings.push(
                "A20 (P3←P5) is enabled but no P5 producer (A21/A22/A23) is active. \
                 A20 will have no packaging data to read."
                    .into(),
            );
        }

        // P5 consumers (A5=P1←P5, A11=P2←P5) without P5 producers
        if (self.enabled[0][4] || self.enabled[1][4]) && !self.any_p5_enabled() {
            warnings.push(
                "P1←P5 (A5) or P2←P5 (A11) is enabled but no P5 producer (A21/A22/A23) is active. \
                 They will fall back to spectral_partition instead of packaging."
                    .into(),
            );
        }

        warnings
    }
}
