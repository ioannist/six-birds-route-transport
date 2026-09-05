//! Audit: measure P6 metrics on nodes and edges.
//!
//! P3 (route mismatch) and P6 (sigma, arrow of time) are measurement
//! primitives, not transformations. They appear here, not in compositions.

use six_primitives_core::substrate::{path_reversal_asymmetry, MarkovKernel};

/// Audit results for a single node.
#[derive(Clone, Debug)]
pub struct NodeAudit {
    pub sigma: f64,
    pub gap: f64,
    pub blocks: usize,
}

/// Compute P6 audit metrics for a kernel.
pub fn audit_kernel(kernel: &MarkovKernel) -> NodeAudit {
    let pi = kernel.stationary(10000, 1e-12);
    let sigma = path_reversal_asymmetry(kernel, &pi, 10);
    let gap = kernel.spectral_gap();
    let blocks = kernel.block_count();
    NodeAudit { sigma, gap, blocks }
}
