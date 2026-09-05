//! Edge: a parent→child link in the emergence DAG.
//!
//! Each edge records the lens and P-composition that produced the
//! coarse-graining, plus DPI and route mismatch metrics.

use crate::composition::PComposition;
use six_primitives_core::substrate::Lens;

/// An edge in the emergence DAG (parent → child).
#[derive(Clone, Debug)]
pub struct Edge {
    /// Unique identifier: "E-000", "E-001", ...
    pub id: String,
    /// Source node ID.
    pub parent_id: String,
    /// Target node ID.
    pub child_id: String,
    /// The lens that maps parent states to child states.
    pub lens: Lens,
    /// The P-composition that produced this lens.
    pub composition: PComposition,
    /// DPI check: sigma_child <= sigma_parent.
    pub dpi: bool,
    /// Route mismatch (P3 metric).
    pub rm: f64,
    /// Gap preservation ratio: child.gap / parent.gap.
    pub gap_ratio: f64,
}
