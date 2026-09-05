//! Merging: create a joint substrate from multiple parent coarse-grainings.
//!
//! When two (or more) lenses coexist on the same ancestor, every micro state
//! carries coordinates in each macro space. The set of occupied coordinate
//! tuples, with transitions inherited from the ancestor, defines a joint
//! substrate. This is NOT engineered — it's the natural consequence of
//! multiple coarse-grainings coexisting.

use six_primitives_core::helpers;
use six_primitives_core::substrate::Lens;
use std::collections::HashMap;

use crate::composition::PComposition;
use crate::edge::Edge;
use crate::node::Node;

/// Result of a merge operation.
pub struct MergeResult {
    pub child: Node,
    /// One edge per parent → child connection.
    pub edges: Vec<Edge>,
    /// The joint lens (ancestor micro states → joint macro states).
    pub joint_lens: Lens,
}

/// Merge two parent nodes into a child via their joint substrate.
///
/// Both parents must derive from the same ancestor (the ancestor's kernel
/// is used to compute transitions on the joint space).
///
/// The joint state space is the set of occupied (a, b) pairs where
/// a = lens_A(micro_state), b = lens_B(micro_state). Transitions are
/// inherited from the ancestor kernel.
pub fn merge_two(
    ancestor: &Node,
    lens_a: &Lens,
    parent_a: &Node,
    lens_b: &Lens,
    parent_b: &Node,
    child_id: &str,
    edge_id_base: &str,
    seed: u64,
) -> Result<MergeResult, String> {
    let n = ancestor.kernel.n;
    let tau = 20;
    let n_traj = helpers::standard_n_traj(n);
    let n_rm = helpers::standard_n_rm(n);

    // Step 1: For each micro state, compute (a, b) coordinates
    let mut pair_to_index: HashMap<(usize, usize), usize> = HashMap::new();
    let mut joint_mapping = vec![0usize; n];

    for i in 0..n {
        let a = lens_a.mapping[i];
        let b = lens_b.mapping[i];
        let pair = (a, b);
        let next_idx = pair_to_index.len();
        let idx = *pair_to_index.entry(pair).or_insert(next_idx);
        joint_mapping[i] = idx;
    }

    let joint_macro_n = pair_to_index.len();
    if joint_macro_n <= 1 {
        return Err(format!(
            "Joint space has only {} states (trivial)",
            joint_macro_n
        ));
    }

    let joint_lens = Lens {
        mapping: joint_mapping,
        macro_n: joint_macro_n,
    };

    // Step 2: Build macro kernel on joint space via trajectory sampling
    let macro_k =
        helpers::trajectory_rewrite_macro(&ancestor.kernel, &joint_lens, tau, n_traj, seed + 100);

    let macro_gap = macro_k.spectral_gap();
    let macro_blocks = macro_k.block_count();

    // Measure sigma
    let pi_m = macro_k.stationary(10000, 1e-12);
    let macro_sigma = six_primitives_core::substrate::path_reversal_asymmetry(&macro_k, &pi_m, 10);

    // Step 3: Build projection lenses from joint space to each parent space
    // For the edge from parent_a to the merge node, the relevant lens
    // maps ancestor states through lens_a, but the merge child is on the joint space.
    // The edge metrics compare ancestor→joint vs ancestor→parent.

    // Route mismatch for the joint lens on the ancestor
    let rm_joint = helpers::mean_route_mismatch(
        &ancestor.kernel,
        &macro_k,
        &joint_lens,
        tau,
        n_rm,
        seed + 200,
    );

    // DPI checks for merge/refinement direction:
    // the joint node keeps both parent coordinates, so EP should not decrease.
    let dpi_vs_a = macro_sigma + 1e-10 >= parent_a.sigma;
    let dpi_vs_b = macro_sigma + 1e-10 >= parent_b.sigma;
    let _dpi_vs_ancestor = macro_sigma + 1e-10 >= ancestor.sigma;

    let gap_ratio_a = if parent_a.gap > 1e-15 {
        macro_gap / parent_a.gap
    } else {
        0.0
    };
    let gap_ratio_b = if parent_b.gap > 1e-15 {
        macro_gap / parent_b.gap
    } else {
        0.0
    };

    let child = Node {
        id: child_id.to_string(),
        kernel: macro_k,
        sigma: macro_sigma,
        gap: macro_gap,
        blocks: macro_blocks,
        parent_edges: vec![format!("{}-a", edge_id_base), format!("{}-b", edge_id_base)],
        child_edges: vec![],
    };

    // Create a "merge" composition label
    let merge_comp = PComposition::new(vec![], "merge(A,B)");

    let edge_a = Edge {
        id: format!("{}-a", edge_id_base),
        parent_id: parent_a.id.clone(),
        child_id: child_id.to_string(),
        lens: joint_lens.clone(),
        composition: merge_comp.clone(),
        dpi: dpi_vs_a,
        rm: rm_joint,
        gap_ratio: gap_ratio_a,
    };

    let edge_b = Edge {
        id: format!("{}-b", edge_id_base),
        parent_id: parent_b.id.clone(),
        child_id: child_id.to_string(),
        lens: joint_lens.clone(),
        composition: merge_comp,
        dpi: dpi_vs_b,
        rm: rm_joint,
        gap_ratio: gap_ratio_b,
    };

    Ok(MergeResult {
        child,
        edges: vec![edge_a, edge_b],
        joint_lens,
    })
}
