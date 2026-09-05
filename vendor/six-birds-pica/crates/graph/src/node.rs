//! Node: a vertex in the emergence DAG.
//!
//! Each node holds a MarkovKernel and its P6 audit metrics.
//! Nodes are connected by edges (parent→child via a lens).

use six_primitives_core::substrate::MarkovKernel;

/// A node in the emergence DAG.
#[derive(Clone, Debug)]
pub struct Node {
    /// Unique identifier: "N-000", "N-001", ...
    pub id: String,
    /// The Markov kernel at this level.
    pub kernel: MarkovKernel,
    /// P6 audit: path reversal asymmetry (arrow of time).
    pub sigma: f64,
    /// Spectral gap of the kernel.
    pub gap: f64,
    /// Number of connected components (P4 sectors).
    pub blocks: usize,
    /// Edge IDs of incoming edges (from parents).
    pub parent_edges: Vec<String>,
    /// Edge IDs of outgoing edges (to children).
    pub child_edges: Vec<String>,
}

impl Node {
    pub fn is_root(&self) -> bool {
        self.parent_edges.is_empty()
    }

    pub fn is_leaf(&self) -> bool {
        self.child_edges.is_empty()
    }
}
