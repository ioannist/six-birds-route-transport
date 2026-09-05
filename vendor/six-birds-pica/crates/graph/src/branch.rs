//! Branching: apply a P-composition to a parent node to create a child.
//!
//! Walks through the composition steps, transforming the kernel at each step.
//! The last partition-producing step (P4 or P5) defines the lens.
//! Builds a macro kernel via trajectory sampling and creates the child node.

use six_primitives_core::helpers;
use six_primitives_core::primitives;
use six_primitives_core::substrate::{Lens, Substrate};

use crate::composition::{PComposition, PStep};
use crate::edge::Edge;
use crate::node::Node;

/// Result of a branch operation.
pub struct BranchResult {
    pub child: Node,
    pub edge: Edge,
}

/// Apply a P-composition to a parent node, producing a child node and edge.
///
/// The composition steps transform the kernel sequentially. The last
/// lens-producing step (P4Sectors or P5Package) defines the coarse-graining.
/// A macro kernel is built via trajectory sampling on the transformed kernel.
pub fn branch(
    parent: &Node,
    comp: &PComposition,
    child_id: &str,
    edge_id: &str,
    seed: u64,
) -> Result<BranchResult, String> {
    if !comp.produces_lens() {
        return Err(format!(
            "Composition '{}' has no lens-producing step (P4 or P5)",
            comp.name
        ));
    }

    let n = parent.kernel.n;
    let tau = 20; // CLO-027: always tau=20
    let n_traj = helpers::standard_n_traj(n);
    let n_rm = helpers::standard_n_rm(n);

    // Walk through composition, transforming kernel and extracting lens
    let mut kernel = parent.kernel.clone();
    let mut lens: Option<Lens> = None;

    for step in &comp.steps {
        match step {
            PStep::P1Perturb { strength } => {
                kernel = primitives::p1_random_perturb(&kernel, *strength, seed + 10);
            }
            PStep::P1Symmetrize => {
                kernel = helpers::symmetrize_kernel(&kernel);
            }
            PStep::P2Gate { prob } => {
                kernel = primitives::p2_random_gate(&kernel, *prob, seed + 20);
            }
            PStep::P2GateScaled => {
                let prob = helpers::scale_gating_prob(n);
                kernel = primitives::p2_random_gate(&kernel, prob, seed + 20);
            }
            PStep::P4Sectors => {
                lens = Some(helpers::sector_lens(&kernel));
            }
            PStep::P5Package { tau: pkg_tau } => {
                // Find fixed points, assign each state to nearest FP basin
                let sub = Substrate::new(kernel.clone(), Lens::modular(n, n), *pkg_tau);
                let fps = sub.find_fixed_points(n, 300, 1e-10, seed + 30);
                if fps.is_empty() {
                    return Err("P5 found no fixed points".to_string());
                }
                // Assign each state to its nearest FP (by L1 distance from delta)
                let mut mapping = vec![0usize; n];
                for state in 0..n {
                    let mut delta = vec![0.0; n];
                    delta[state] = 1.0;
                    let packaged = sub.packaging_endomap(&delta);
                    let mut best_fp = 0;
                    let mut best_dist = f64::MAX;
                    for (fi, fp) in fps.iter().enumerate() {
                        let d: f64 = packaged
                            .iter()
                            .zip(fp.iter())
                            .map(|(a, b)| (a - b).abs())
                            .sum();
                        if d < best_dist {
                            best_dist = d;
                            best_fp = fi;
                        }
                    }
                    mapping[state] = best_fp;
                }
                let macro_n = fps.len();
                lens = Some(Lens { mapping, macro_n });
            }
        }
    }

    let lens = lens.ok_or("No lens produced")?;

    if lens.macro_n <= 1 {
        return Err(format!(
            "Lens produced only {} macro states (trivial)",
            lens.macro_n
        ));
    }

    // Build macro kernel via trajectory sampling
    let macro_k = helpers::trajectory_rewrite_macro(&kernel, &lens, tau, n_traj, seed + 100);
    let macro_gap = macro_k.spectral_gap();
    let macro_blocks = macro_k.block_count();

    // Measure sigma on macro kernel
    let pi_m = macro_k.stationary(10000, 1e-12);
    let macro_sigma = six_primitives_core::substrate::path_reversal_asymmetry(&macro_k, &pi_m, 10);

    // Measure route mismatch
    let rm = helpers::mean_route_mismatch(&kernel, &macro_k, &lens, tau, n_rm, seed + 200);

    // DPI check
    let dpi = macro_sigma <= parent.sigma + 1e-10;

    // Gap ratio
    let gap_ratio = if parent.gap > 1e-15 {
        macro_gap / parent.gap
    } else {
        0.0
    };

    let child = Node {
        id: child_id.to_string(),
        kernel: macro_k,
        sigma: macro_sigma,
        gap: macro_gap,
        blocks: macro_blocks,
        parent_edges: vec![edge_id.to_string()],
        child_edges: vec![],
    };

    let edge = Edge {
        id: edge_id.to_string(),
        parent_id: parent.id.clone(),
        child_id: child_id.to_string(),
        lens,
        composition: comp.clone(),
        dpi,
        rm,
        gap_ratio,
    };

    Ok(BranchResult { child, edge })
}
