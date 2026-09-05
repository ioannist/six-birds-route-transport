//! P-Composition: sequences of primitive steps as first-class objects.
//!
//! A PComposition represents a specific ordering of P1-P6 operations
//! applied to a kernel. All compositions are legitimate — they exist
//! in the full combinatorial space of P1-P6. We don't engineer which
//! composition to use; we explore the space and observe what each produces.

use std::fmt;

/// A single step in a P-composition.
#[derive(Clone, Debug)]
pub enum PStep {
    /// P1: Random perturbation of kernel entries.
    P1Perturb { strength: f64 },
    /// P1: Symmetrize kernel to enforce detailed balance.
    P1Symmetrize,
    /// P2: Gate edges with explicit deletion probability.
    P2Gate { prob: f64 },
    /// P2: Gate edges using scale-dependent threshold (CLO-014).
    P2GateScaled,
    /// P4: Read off sector labels as a partition (lens-producing step).
    P4Sectors,
    /// P5: Find packaging fixed points, cluster by nearest FP (lens-producing step).
    P5Package { tau: usize },
}

/// A composition of P-steps, applied in order to a kernel.
/// The last partition-producing step (P4Sectors or P5Package) defines the lens.
#[derive(Clone, Debug)]
pub struct PComposition {
    pub steps: Vec<PStep>,
    pub name: String,
}

impl PComposition {
    pub fn new(steps: Vec<PStep>, name: &str) -> Self {
        Self {
            steps,
            name: name.to_string(),
        }
    }

    /// Standard P2→P4 composition: gate at scale-dependent threshold, read sectors.
    pub fn p2_p4() -> Self {
        Self::new(vec![PStep::P2GateScaled, PStep::P4Sectors], "P2→P4")
    }

    /// P2→P4 with explicit gating probability.
    pub fn p2_p4_at(prob: f64) -> Self {
        Self::new(
            vec![PStep::P2Gate { prob }, PStep::P4Sectors],
            &format!("P2({:.2})→P4", prob),
        )
    }

    /// P1(sym)→P2→P4: symmetrize first, then gate, then sectors.
    pub fn p1sym_p2_p4() -> Self {
        Self::new(
            vec![PStep::P1Symmetrize, PStep::P2GateScaled, PStep::P4Sectors],
            "P1sym→P2→P4",
        )
    }

    /// P2→P5: gate, then find packaging fixed points.
    pub fn p2_p5(tau: usize) -> Self {
        Self::new(vec![PStep::P2GateScaled, PStep::P5Package { tau }], "P2→P5")
    }

    /// P1(perturb)→P2→P4: perturb first, then gate, then sectors.
    pub fn p1_p2_p4(strength: f64) -> Self {
        Self::new(
            vec![
                PStep::P1Perturb { strength },
                PStep::P2GateScaled,
                PStep::P4Sectors,
            ],
            &format!("P1({:.1})→P2→P4", strength),
        )
    }

    /// P1sym→P2→P5: symmetrize, gate, then packaging fixed points.
    pub fn p1sym_p2_p5(tau: usize) -> Self {
        Self::new(
            vec![
                PStep::P1Symmetrize,
                PStep::P2GateScaled,
                PStep::P5Package { tau },
            ],
            "P1sym→P2→P5",
        )
    }

    /// P5 only: find packaging fixed points on raw kernel.
    pub fn p5(tau: usize) -> Self {
        Self::new(vec![PStep::P5Package { tau }], "P5")
    }

    /// P1(perturb)→P2→P5: perturb, gate, packaging.
    pub fn p1_p2_p5(strength: f64, tau: usize) -> Self {
        Self::new(
            vec![
                PStep::P1Perturb { strength },
                PStep::P2GateScaled,
                PStep::P5Package { tau },
            ],
            &format!("P1({:.1})→P2→P5", strength),
        )
    }

    /// Returns true if this composition contains a lens-producing step.
    pub fn produces_lens(&self) -> bool {
        self.steps
            .iter()
            .any(|s| matches!(s, PStep::P4Sectors | PStep::P5Package { .. }))
    }
}

impl fmt::Display for PComposition {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        write!(f, "{}", self.name)
    }
}
