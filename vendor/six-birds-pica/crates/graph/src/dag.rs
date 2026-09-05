//! EmergenceDag: the graph of nodes and edges.
//!
//! Provides the high-level API for creating roots, branching, merging,
//! and querying the DAG structure.

use six_primitives_core::substrate::MarkovKernel;
use std::collections::HashMap;

use crate::audit;
use crate::branch;
use crate::composition::PComposition;
use crate::edge::Edge;
use crate::merge;
use crate::node::Node;

/// The emergence DAG: a directed acyclic graph of Markov kernels
/// connected by P-composition lenses.
pub struct EmergenceDag {
    pub nodes: HashMap<String, Node>,
    pub edges: HashMap<String, Edge>,
    next_node_id: usize,
    next_edge_id: usize,
}

impl EmergenceDag {
    pub fn new() -> Self {
        Self {
            nodes: HashMap::new(),
            edges: HashMap::new(),
            next_node_id: 0,
            next_edge_id: 0,
        }
    }

    fn alloc_node_id(&mut self) -> String {
        let id = format!("N-{:03}", self.next_node_id);
        self.next_node_id += 1;
        id
    }

    fn alloc_edge_id(&mut self) -> String {
        let id = format!("E-{:03}", self.next_edge_id);
        self.next_edge_id += 1;
        id
    }

    /// Create a root node from a random Markov kernel.
    pub fn create_root(&mut self, n: usize, seed: u64) -> String {
        let kernel = MarkovKernel::random(n, seed);
        let a = audit::audit_kernel(&kernel);

        let id = self.alloc_node_id();
        let node = Node {
            id: id.clone(),
            kernel,
            sigma: a.sigma,
            gap: a.gap,
            blocks: a.blocks,
            parent_edges: vec![],
            child_edges: vec![],
        };
        self.nodes.insert(id.clone(), node);
        id
    }

    /// Create a root node from a pre-built Markov kernel.
    /// Used for diagnostic experiments that need non-standard substrates
    /// (e.g., pre-gated slow-mixing kernels).
    pub fn create_root_from_kernel(&mut self, kernel: MarkovKernel) -> String {
        let a = audit::audit_kernel(&kernel);

        let id = self.alloc_node_id();
        let node = Node {
            id: id.clone(),
            kernel,
            sigma: a.sigma,
            gap: a.gap,
            blocks: a.blocks,
            parent_edges: vec![],
            child_edges: vec![],
        };
        self.nodes.insert(id.clone(), node);
        id
    }

    /// Branch: apply a P-composition to a parent node, creating a child.
    pub fn branch(
        &mut self,
        parent_id: &str,
        comp: &PComposition,
        seed: u64,
    ) -> Result<String, String> {
        let parent = self
            .nodes
            .get(parent_id)
            .ok_or_else(|| format!("Parent node '{}' not found", parent_id))?
            .clone();

        let child_id = self.alloc_node_id();
        let edge_id = self.alloc_edge_id();

        let result = branch::branch(&parent, comp, &child_id, &edge_id, seed)?;

        // Update parent's child_edges
        self.nodes
            .get_mut(parent_id)
            .unwrap()
            .child_edges
            .push(edge_id.clone());

        self.nodes.insert(child_id.clone(), result.child);
        self.edges.insert(edge_id, result.edge);

        Ok(child_id)
    }

    /// Merge: combine two parent nodes (that share an ancestor) into a child
    /// via their joint substrate.
    pub fn merge(
        &mut self,
        ancestor_id: &str,
        parent_a_id: &str,
        parent_b_id: &str,
        seed: u64,
    ) -> Result<String, String> {
        let ancestor = self
            .nodes
            .get(ancestor_id)
            .ok_or_else(|| format!("Ancestor '{}' not found", ancestor_id))?
            .clone();
        let parent_a = self
            .nodes
            .get(parent_a_id)
            .ok_or_else(|| format!("Parent A '{}' not found", parent_a_id))?
            .clone();
        let parent_b = self
            .nodes
            .get(parent_b_id)
            .ok_or_else(|| format!("Parent B '{}' not found", parent_b_id))?
            .clone();

        // Find the lenses from ancestor → parent_a and ancestor → parent_b
        let lens_a = self
            .find_lens(ancestor_id, parent_a_id)
            .ok_or_else(|| format!("No edge from '{}' to '{}'", ancestor_id, parent_a_id))?;
        let lens_b = self
            .find_lens(ancestor_id, parent_b_id)
            .ok_or_else(|| format!("No edge from '{}' to '{}'", ancestor_id, parent_b_id))?;

        let child_id = self.alloc_node_id();
        let edge_id_base = self.alloc_edge_id();
        // Also allocate the second edge ID
        let _ = self.alloc_edge_id();

        let result = merge::merge_two(
            &ancestor,
            &lens_a,
            &parent_a,
            &lens_b,
            &parent_b,
            &child_id,
            &edge_id_base,
            seed,
        )?;

        // Update parent child_edges
        self.nodes
            .get_mut(parent_a_id)
            .unwrap()
            .child_edges
            .push(result.edges[0].id.clone());
        self.nodes
            .get_mut(parent_b_id)
            .unwrap()
            .child_edges
            .push(result.edges[1].id.clone());

        // Insert child and edges
        self.nodes.insert(child_id.clone(), result.child);
        for edge in result.edges {
            self.edges.insert(edge.id.clone(), edge);
        }

        Ok(child_id)
    }

    /// Find the lens on the edge from parent_id to child_id.
    fn find_lens(
        &self,
        parent_id: &str,
        child_id: &str,
    ) -> Option<six_primitives_core::substrate::Lens> {
        for edge in self.edges.values() {
            if edge.parent_id == parent_id && edge.child_id == child_id {
                return Some(edge.lens.clone());
            }
        }
        None
    }

    /// Print a summary of the DAG.
    pub fn print_summary(&self) {
        println!(
            "=== Emergence DAG: {} nodes, {} edges ===",
            self.nodes.len(),
            self.edges.len()
        );
        // Sort nodes by ID for consistent output
        let mut node_ids: Vec<&String> = self.nodes.keys().collect();
        node_ids.sort();
        for nid in &node_ids {
            let node = &self.nodes[*nid];
            let role = if node.is_root() {
                "ROOT"
            } else if node.is_leaf() {
                "LEAF"
            } else {
                "    "
            };
            println!(
                "  {} {} | n={:3} sigma={:.6} gap={:.6} blocks={}",
                role, node.id, node.kernel.n, node.sigma, node.gap, node.blocks
            );
        }
        println!("--- Edges ---");
        let mut edge_ids: Vec<&String> = self.edges.keys().collect();
        edge_ids.sort();
        for eid in &edge_ids {
            let edge = &self.edges[*eid];
            let dpi_str = if edge.dpi { "DPI:OK" } else { "DPI:FAIL" };
            println!(
                "  {} {} → {} | {} lens_n={} rm={:.4} gap_r={:.3} {}",
                edge.id,
                edge.parent_id,
                edge.child_id,
                edge.composition.name,
                edge.lens.macro_n,
                edge.rm,
                edge.gap_ratio,
                dpi_str
            );
        }
    }
}
