//! Runner for graph-based emergence experiments.
//!
//! The graph framework replaces the linear ladder with a DAG where
//! layers can branch (one parent, multiple children via different
//! P-compositions) and merge (multiple parents, one child via joint
//! substrate).

use clap::Parser;
use emergence_graph::composition::{PComposition, PStep};
use emergence_graph::dag::EmergenceDag;
use serde::{Deserialize, Serialize};
use six_dynamics::{DynamicsConfig, PicaConfig};
use six_primitives_core::helpers;
use six_primitives_core::substrate::MarkovKernel;

#[derive(Parser)]
struct Args {
    /// Experiment ID (e.g., EXP-041)
    #[arg(long)]
    exp: String,

    /// Random seed
    #[arg(long, default_value = "42")]
    seed: u64,

    /// State space size
    #[arg(long, default_value = "32")]
    scale: usize,

    /// Run parameter sweep (10 seeds × N scales)
    #[arg(long)]
    sweep: bool,

    /// Custom scales for sweep (comma-separated)
    #[arg(long)]
    scales: Option<String>,

    /// Filter to a single config label (skip others in multi-config experiments)
    #[arg(long)]
    config: Option<String>,
}

// ============================================================================
// EXP-041: Dual-Lens DAG
//
// Create root → branch via P2→P4 → branch via P2(different)→P4 → merge
// Question: Does the merge node have both nontrivial dynamics AND DPI?
// ============================================================================

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Exp041Metrics {
    pub n: usize,
    // Root
    pub root_sigma: f64,
    pub root_gap: f64,
    pub root_blocks: usize,
    // Branch A: P2→P4 at scale-dependent threshold
    pub branch_a_n: usize,
    pub branch_a_sigma: f64,
    pub branch_a_gap: f64,
    pub branch_a_dpi: bool,
    pub branch_a_rm: f64,
    pub branch_a_blocks: usize,
    // Branch B: P2→P4 at lower threshold (more aggressive gating)
    pub branch_b_n: usize,
    pub branch_b_sigma: f64,
    pub branch_b_gap: f64,
    pub branch_b_dpi: bool,
    pub branch_b_rm: f64,
    pub branch_b_blocks: usize,
    // Merge: joint substrate from A and B
    pub merge_n: usize,
    pub merge_sigma: f64,
    pub merge_gap: f64,
    pub merge_dpi_vs_root: bool,
    pub merge_dpi_vs_a: bool,
    pub merge_dpi_vs_b: bool,
    pub merge_rm: f64,
    pub merge_blocks: usize,
    // Key question: does merge have both DPI (vs root) and gap > 0?
    pub merge_has_dpi_and_dynamics: bool,
    // Comparison: is merge better than either branch alone?
    pub merge_beats_a: bool, // merge has DPI+gap but A doesn't
    pub merge_beats_b: bool, // merge has DPI+gap but B doesn't
}

fn run_exp_041(seed: u64, scale: usize) -> Exp041Metrics {
    let n = scale.max(8);
    let mut dag = EmergenceDag::new();

    // Root: random kernel
    let root_id = dag.create_root(n, seed);

    // Branch A: P2→P4 at scale-dependent threshold (standard)
    let comp_a = PComposition::p2_p4();
    let branch_a_id = match dag.branch(&root_id, &comp_a, seed + 1000) {
        Ok(id) => id,
        Err(_) => {
            // If branching fails (e.g., 1 block), return degenerate metrics
            let root = &dag.nodes[&root_id];
            return Exp041Metrics {
                n,
                root_sigma: root.sigma,
                root_gap: root.gap,
                root_blocks: root.blocks,
                branch_a_n: 0,
                branch_a_sigma: 0.0,
                branch_a_gap: 0.0,
                branch_a_dpi: false,
                branch_a_rm: 0.0,
                branch_a_blocks: 0,
                branch_b_n: 0,
                branch_b_sigma: 0.0,
                branch_b_gap: 0.0,
                branch_b_dpi: false,
                branch_b_rm: 0.0,
                branch_b_blocks: 0,
                merge_n: 0,
                merge_sigma: 0.0,
                merge_gap: 0.0,
                merge_dpi_vs_root: false,
                merge_dpi_vs_a: false,
                merge_dpi_vs_b: false,
                merge_rm: 0.0,
                merge_blocks: 0,
                merge_has_dpi_and_dynamics: false,
                merge_beats_a: false,
                merge_beats_b: false,
            };
        }
    };

    // Branch B: P1sym→P2→P4 (symmetrize kernel first, then gate, then sectors)
    // Qualitatively different from A: symmetrization changes the kernel structure
    // before gating, so different blocks emerge.
    let comp_b = PComposition::p1sym_p2_p4();
    let branch_b_id = match dag.branch(&root_id, &comp_b, seed + 2000) {
        Ok(id) => id,
        Err(_) => {
            // Fallback: try P1(perturb)→P2→P4
            let comp_b2 = PComposition::p1_p2_p4(0.3);
            match dag.branch(&root_id, &comp_b2, seed + 2000) {
                Ok(id) => id,
                Err(_) => {
                    let root = &dag.nodes[&root_id];
                    let a = &dag.nodes[&branch_a_id];
                    let ea: Vec<&emergence_graph::edge::Edge> = dag
                        .edges
                        .values()
                        .filter(|e| e.child_id == branch_a_id)
                        .collect();
                    return Exp041Metrics {
                        n,
                        root_sigma: root.sigma,
                        root_gap: root.gap,
                        root_blocks: root.blocks,
                        branch_a_n: a.kernel.n,
                        branch_a_sigma: a.sigma,
                        branch_a_gap: a.gap,
                        branch_a_dpi: ea.first().map(|e| e.dpi).unwrap_or(false),
                        branch_a_rm: ea.first().map(|e| e.rm).unwrap_or(0.0),
                        branch_a_blocks: a.blocks,
                        branch_b_n: 0,
                        branch_b_sigma: 0.0,
                        branch_b_gap: 0.0,
                        branch_b_dpi: false,
                        branch_b_rm: 0.0,
                        branch_b_blocks: 0,
                        merge_n: 0,
                        merge_sigma: 0.0,
                        merge_gap: 0.0,
                        merge_dpi_vs_root: false,
                        merge_dpi_vs_a: false,
                        merge_dpi_vs_b: false,
                        merge_rm: 0.0,
                        merge_blocks: 0,
                        merge_has_dpi_and_dynamics: false,
                        merge_beats_a: false,
                        merge_beats_b: false,
                    };
                }
            }
        }
    };

    // Merge A and B
    let merge_id = match dag.merge(&root_id, &branch_a_id, &branch_b_id, seed + 3000) {
        Ok(id) => id,
        Err(_) => {
            let root = &dag.nodes[&root_id];
            let a = &dag.nodes[&branch_a_id];
            let b = &dag.nodes[&branch_b_id];
            let ea: Vec<&emergence_graph::edge::Edge> = dag
                .edges
                .values()
                .filter(|e| e.child_id == branch_a_id)
                .collect();
            let eb: Vec<&emergence_graph::edge::Edge> = dag
                .edges
                .values()
                .filter(|e| e.child_id == branch_b_id)
                .collect();
            return Exp041Metrics {
                n,
                root_sigma: root.sigma,
                root_gap: root.gap,
                root_blocks: root.blocks,
                branch_a_n: a.kernel.n,
                branch_a_sigma: a.sigma,
                branch_a_gap: a.gap,
                branch_a_dpi: ea.first().map(|e| e.dpi).unwrap_or(false),
                branch_a_rm: ea.first().map(|e| e.rm).unwrap_or(0.0),
                branch_a_blocks: a.blocks,
                branch_b_n: b.kernel.n,
                branch_b_sigma: b.sigma,
                branch_b_gap: b.gap,
                branch_b_dpi: eb.first().map(|e| e.dpi).unwrap_or(false),
                branch_b_rm: eb.first().map(|e| e.rm).unwrap_or(0.0),
                branch_b_blocks: b.blocks,
                merge_n: 0,
                merge_sigma: 0.0,
                merge_gap: 0.0,
                merge_dpi_vs_root: false,
                merge_dpi_vs_a: false,
                merge_dpi_vs_b: false,
                merge_rm: 0.0,
                merge_blocks: 0,
                merge_has_dpi_and_dynamics: false,
                merge_beats_a: false,
                merge_beats_b: false,
            };
        }
    };

    // Print DAG summary
    dag.print_summary();

    // Collect metrics
    let root = &dag.nodes[&root_id];
    let a = &dag.nodes[&branch_a_id];
    let b = &dag.nodes[&branch_b_id];
    let m = &dag.nodes[&merge_id];

    let ea: Vec<&emergence_graph::edge::Edge> = dag
        .edges
        .values()
        .filter(|e| e.child_id == branch_a_id)
        .collect();
    let eb: Vec<&emergence_graph::edge::Edge> = dag
        .edges
        .values()
        .filter(|e| e.child_id == branch_b_id)
        .collect();
    let em: Vec<&emergence_graph::edge::Edge> = dag
        .edges
        .values()
        .filter(|e| e.child_id == merge_id)
        .collect();

    let merge_dpi_vs_root = m.sigma <= root.sigma + 1e-10;
    let merge_gap_nontrivial = m.gap > 0.01;
    let merge_has_dpi_and_dynamics = merge_dpi_vs_root && merge_gap_nontrivial;

    let a_has_both = ea.first().map(|e| e.dpi).unwrap_or(false) && a.gap > 0.01;
    let b_has_both = eb.first().map(|e| e.dpi).unwrap_or(false) && b.gap > 0.01;

    Exp041Metrics {
        n,
        root_sigma: root.sigma,
        root_gap: root.gap,
        root_blocks: root.blocks,
        branch_a_n: a.kernel.n,
        branch_a_sigma: a.sigma,
        branch_a_gap: a.gap,
        branch_a_dpi: ea.first().map(|e| e.dpi).unwrap_or(false),
        branch_a_rm: ea.first().map(|e| e.rm).unwrap_or(0.0),
        branch_a_blocks: a.blocks,
        branch_b_n: b.kernel.n,
        branch_b_sigma: b.sigma,
        branch_b_gap: b.gap,
        branch_b_dpi: eb.first().map(|e| e.dpi).unwrap_or(false),
        branch_b_rm: eb.first().map(|e| e.rm).unwrap_or(0.0),
        branch_b_blocks: b.blocks,
        merge_n: m.kernel.n,
        merge_sigma: m.sigma,
        merge_gap: m.gap,
        merge_dpi_vs_root,
        merge_dpi_vs_a: em.iter().any(|e| e.parent_id == branch_a_id && e.dpi),
        merge_dpi_vs_b: em.iter().any(|e| e.parent_id == branch_b_id && e.dpi),
        merge_rm: em.first().map(|e| e.rm).unwrap_or(0.0),
        merge_blocks: m.blocks,
        merge_has_dpi_and_dynamics,
        merge_beats_a: merge_has_dpi_and_dynamics && !a_has_both,
        merge_beats_b: merge_has_dpi_and_dynamics && !b_has_both,
    }
}

// ============================================================================
// EXP-042: Multi-Composition Pair Sweep
//
// For each root kernel, try ALL pairs from a set of compositions.
// Which pairs produce the best merge success rate?
// Can we find pairs that work when P2→P4 / P1sym→P2→P4 fails?
// ============================================================================

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Exp042Metrics {
    pub n: usize,
    pub root_sigma: f64,
    pub root_gap: f64,
    pub n_compositions_viable: usize, // How many compositions produced ≥2 blocks
    pub n_pairs_tested: usize,
    pub n_pairs_success: usize, // Merge has DPI + gap > 0.01
    pub best_pair: String,
    pub best_merge_gap: f64,
    pub best_merge_sigma: f64,
    pub best_merge_n: usize,
    pub any_success: bool,
}

fn run_exp_042(seed: u64, scale: usize) -> Exp042Metrics {
    let n = scale.max(8);
    let mut dag = EmergenceDag::new();
    let root_id = dag.create_root(n, seed);
    let root = dag.nodes[&root_id].clone();

    // Define composition palette
    let compositions: Vec<(String, PComposition)> = vec![
        ("P2→P4".into(), PComposition::p2_p4()),
        ("P1sym→P2→P4".into(), PComposition::p1sym_p2_p4()),
        ("P1(0.3)→P2→P4".into(), PComposition::p1_p2_p4(0.3)),
        ("P1(0.1)→P2→P4".into(), PComposition::p1_p2_p4(0.1)),
    ];

    // Try each composition, collect successful branches
    let mut branches: Vec<(String, String)> = Vec::new(); // (name, node_id)
    for (i, (name, comp)) in compositions.iter().enumerate() {
        match dag.branch(&root_id, comp, seed + (i as u64 + 1) * 1000) {
            Ok(id) => {
                branches.push((name.clone(), id));
            }
            Err(_) => {}
        }
    }

    let n_viable = branches.len();

    // Try all pairs of successful branches
    let mut n_pairs = 0;
    let mut n_success = 0;
    let mut best_pair = String::new();
    let mut best_gap = 0.0f64;
    let mut best_sigma = 0.0f64;
    let mut best_n = 0usize;

    for i in 0..branches.len() {
        for j in (i + 1)..branches.len() {
            n_pairs += 1;
            let (ref name_a, ref id_a) = branches[i];
            let (ref name_b, ref id_b) = branches[j];

            match dag.merge(&root_id, id_a, id_b, seed + 5000 + (n_pairs as u64) * 100) {
                Ok(merge_id) => {
                    let m = &dag.nodes[&merge_id];
                    let dpi = m.sigma <= root.sigma + 1e-10;
                    let has_dynamics = m.gap > 0.01;
                    if dpi && has_dynamics {
                        n_success += 1;
                        if m.gap > best_gap {
                            best_gap = m.gap;
                            best_sigma = m.sigma;
                            best_n = m.kernel.n;
                            best_pair = format!("{} + {}", name_a, name_b);
                        }
                    }
                }
                Err(_) => {}
            }
        }
    }

    Exp042Metrics {
        n,
        root_sigma: root.sigma,
        root_gap: root.gap,
        n_compositions_viable: n_viable,
        n_pairs_tested: n_pairs,
        n_pairs_success: n_success,
        best_pair,
        best_merge_gap: best_gap,
        best_merge_sigma: best_sigma,
        best_merge_n: best_n,
        any_success: n_success > 0,
    }
}

// ============================================================================
// EXP-043: Three-Way Merge
//
// Branch into 3 compositions, create 3-way joint (a,b,c) substrate.
// Does this improve on 2-way merge success rate?
// ============================================================================

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Exp043Metrics {
    pub n: usize,
    pub root_sigma: f64,
    pub n_branches: usize, // How many of 3 compositions succeeded
    // Two-way merges (for comparison)
    pub twoway_ab_success: bool,
    pub twoway_ac_success: bool,
    pub twoway_bc_success: bool,
    pub any_twoway: bool,
    // Three-way merge
    pub threeway_n: usize,
    pub threeway_sigma: f64,
    pub threeway_gap: f64,
    pub threeway_dpi: bool,
    pub threeway_rm: f64,
    pub threeway_success: bool, // DPI + gap > 0.01
    // Key comparison
    pub threeway_beats_twoway: bool, // 3-way works but no 2-way does
}

fn run_exp_043(seed: u64, scale: usize) -> Exp043Metrics {
    let n = scale.max(8);
    let mut dag = EmergenceDag::new();
    let root_id = dag.create_root(n, seed);
    let root = dag.nodes[&root_id].clone();

    // Three different compositions
    let comps = vec![
        PComposition::p2_p4(),
        PComposition::p1sym_p2_p4(),
        PComposition::p1_p2_p4(0.3),
    ];

    let mut branch_ids: Vec<Option<String>> = Vec::new();
    for (i, comp) in comps.iter().enumerate() {
        match dag.branch(&root_id, comp, seed + (i as u64 + 1) * 1000) {
            Ok(id) => branch_ids.push(Some(id)),
            Err(_) => branch_ids.push(None),
        }
    }

    let n_branches = branch_ids.iter().filter(|b| b.is_some()).count();

    // Helper: try 2-way merge, return success
    let try_merge = |dag: &mut EmergenceDag,
                     root_id: &str,
                     a: &str,
                     b: &str,
                     s: u64|
     -> (bool, f64, f64, usize) {
        match dag.merge(root_id, a, b, s) {
            Ok(mid) => {
                let m = &dag.nodes[&mid];
                let dpi = m.sigma <= root.sigma + 1e-10;
                let success = dpi && m.gap > 0.01;
                (success, m.sigma, m.gap, m.kernel.n)
            }
            Err(_) => (false, 0.0, 0.0, 0),
        }
    };

    // Two-way merges
    let twoway_ab = if let (Some(a), Some(b)) = (&branch_ids[0], &branch_ids[1]) {
        try_merge(&mut dag, &root_id, a, b, seed + 4000).0
    } else {
        false
    };

    let twoway_ac = if let (Some(a), Some(c)) = (&branch_ids[0], &branch_ids[2]) {
        try_merge(&mut dag, &root_id, a, c, seed + 5000).0
    } else {
        false
    };

    let twoway_bc = if let (Some(b), Some(c)) = (&branch_ids[1], &branch_ids[2]) {
        try_merge(&mut dag, &root_id, b, c, seed + 6000).0
    } else {
        false
    };

    let any_twoway = twoway_ab || twoway_ac || twoway_bc;

    // Three-way merge: build joint (a,b,c) lens from all three
    let (threeway_n, threeway_sigma, threeway_gap, threeway_dpi, threeway_rm, threeway_success) =
        if n_branches == 3 {
            // Get all three lenses
            let lens_a_opt = dag
                .edges
                .values()
                .find(|e| e.parent_id == root_id && Some(&e.child_id) == branch_ids[0].as_ref())
                .map(|e| e.lens.clone());
            let lens_b_opt = dag
                .edges
                .values()
                .find(|e| e.parent_id == root_id && Some(&e.child_id) == branch_ids[1].as_ref())
                .map(|e| e.lens.clone());
            let lens_c_opt = dag
                .edges
                .values()
                .find(|e| e.parent_id == root_id && Some(&e.child_id) == branch_ids[2].as_ref())
                .map(|e| e.lens.clone());

            if let (Some(la), Some(lb), Some(lc)) = (lens_a_opt, lens_b_opt, lens_c_opt) {
                // Build 3-way joint lens: i → (a(i), b(i), c(i))
                let mut triple_to_idx: std::collections::HashMap<(usize, usize, usize), usize> =
                    std::collections::HashMap::new();
                let mut joint_mapping = vec![0usize; n];
                for i in 0..n {
                    let triple = (la.mapping[i], lb.mapping[i], lc.mapping[i]);
                    let next = triple_to_idx.len();
                    let idx = *triple_to_idx.entry(triple).or_insert(next);
                    joint_mapping[i] = idx;
                }
                let joint_n = triple_to_idx.len();
                if joint_n > 1 {
                    let joint_lens = six_primitives_core::substrate::Lens {
                        mapping: joint_mapping,
                        macro_n: joint_n,
                    };
                    let tau = 20;
                    let n_traj = helpers::standard_n_traj(n);
                    let n_rm = helpers::standard_n_rm(n);
                    let macro_k = helpers::trajectory_rewrite_macro(
                        &root.kernel,
                        &joint_lens,
                        tau,
                        n_traj,
                        seed + 7000,
                    );
                    let pi = macro_k.stationary(10000, 1e-12);
                    let sigma =
                        six_primitives_core::substrate::path_reversal_asymmetry(&macro_k, &pi, 10);
                    let gap = macro_k.spectral_gap();
                    let rm = helpers::mean_route_mismatch(
                        &root.kernel,
                        &macro_k,
                        &joint_lens,
                        tau,
                        n_rm,
                        seed + 8000,
                    );
                    let dpi = sigma <= root.sigma + 1e-10;
                    let success = dpi && gap > 0.01;
                    (joint_n, sigma, gap, dpi, rm, success)
                } else {
                    (joint_n, 0.0, 0.0, false, 0.0, false)
                }
            } else {
                (0, 0.0, 0.0, false, 0.0, false)
            }
        } else {
            (0, 0.0, 0.0, false, 0.0, false)
        };

    let threeway_beats_twoway = threeway_success && !any_twoway;

    Exp043Metrics {
        n,
        root_sigma: root.sigma,
        n_branches,
        twoway_ab_success: twoway_ab,
        twoway_ac_success: twoway_ac,
        twoway_bc_success: twoway_bc,
        any_twoway,
        threeway_n,
        threeway_sigma,
        threeway_gap,
        threeway_dpi,
        threeway_rm,
        threeway_success,
        threeway_beats_twoway,
    }
}

// ============================================================================
// EXP-044: P5-Based Compositions in DAG Merge
//
// Add P5 (packaging) compositions to the palette alongside P4 (sectors).
// P5 finds fixed points of the packaging endomap — fundamentally different
// partition from P4 sectors (which reads block structure from gating).
// Question: Do P5 compositions improve branch viability or merge quality?
// ============================================================================

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Exp044Metrics {
    pub n: usize,
    pub root_sigma: f64,
    pub root_gap: f64,
    pub p4_viable: usize,
    pub p5_viable: usize,
    pub total_viable: usize,
    pub p4_p4_pairs: usize,
    pub p4_p4_success: usize,
    pub p4_p5_pairs: usize,
    pub p4_p5_success: usize,
    pub p5_p5_pairs: usize,
    pub p5_p5_success: usize,
    pub any_success: bool,
    pub best_pair: String,
    pub best_merge_gap: f64,
    pub best_merge_sigma: f64,
    pub best_merge_n: usize,
}

fn run_exp_044(seed: u64, scale: usize) -> Exp044Metrics {
    let n = scale.max(8);
    let mut dag = EmergenceDag::new();
    let root_id = dag.create_root(n, seed);
    let root = dag.nodes[&root_id].clone();

    // Mixed P4 and P5 palette
    let compositions: Vec<(String, PComposition, bool)> = vec![
        ("P2→P4".into(), PComposition::p2_p4(), true),
        ("P1sym→P2→P4".into(), PComposition::p1sym_p2_p4(), true),
        ("P1(0.3)→P2→P4".into(), PComposition::p1_p2_p4(0.3), true),
        ("P2→P5".into(), PComposition::p2_p5(20), false),
        ("P1sym→P2→P5".into(), PComposition::p1sym_p2_p5(20), false),
        ("P5".into(), PComposition::p5(20), false),
    ];

    let mut branches: Vec<(String, String, bool)> = Vec::new();
    for (i, (name, comp, is_p4)) in compositions.iter().enumerate() {
        match dag.branch(&root_id, comp, seed + (i as u64 + 1) * 1000) {
            Ok(id) => {
                branches.push((name.clone(), id, *is_p4));
            }
            Err(_) => {}
        }
    }

    let p4_viable = branches.iter().filter(|(_, _, p4)| *p4).count();
    let p5_viable = branches.iter().filter(|(_, _, p4)| !*p4).count();
    let total_viable = branches.len();

    let mut p4_p4_pairs = 0;
    let mut p4_p4_success = 0;
    let mut p4_p5_pairs = 0;
    let mut p4_p5_success = 0;
    let mut p5_p5_pairs = 0;
    let mut p5_p5_success = 0;
    let mut best_pair = String::new();
    let mut best_gap = 0.0f64;
    let mut best_sigma = 0.0f64;
    let mut best_n = 0usize;
    let mut pair_seed = 0u64;

    for i in 0..branches.len() {
        for j in (i + 1)..branches.len() {
            let (ref name_a, ref id_a, is_p4_a) = branches[i];
            let (ref name_b, ref id_b, is_p4_b) = branches[j];

            match (is_p4_a, is_p4_b) {
                (true, true) => {
                    p4_p4_pairs += 1;
                }
                (true, false) | (false, true) => {
                    p4_p5_pairs += 1;
                }
                (false, false) => {
                    p5_p5_pairs += 1;
                }
            }

            pair_seed += 1;
            match dag.merge(&root_id, id_a, id_b, seed + 5000 + pair_seed * 100) {
                Ok(merge_id) => {
                    let m = &dag.nodes[&merge_id];
                    let dpi = m.sigma <= root.sigma + 1e-10;
                    let has_dynamics = m.gap > 0.01;
                    if dpi && has_dynamics {
                        match (is_p4_a, is_p4_b) {
                            (true, true) => p4_p4_success += 1,
                            (true, false) | (false, true) => p4_p5_success += 1,
                            (false, false) => p5_p5_success += 1,
                        }
                        if m.gap > best_gap {
                            best_gap = m.gap;
                            best_sigma = m.sigma;
                            best_n = m.kernel.n;
                            best_pair = format!("{} + {}", name_a, name_b);
                        }
                    }
                }
                Err(_) => {}
            }
        }
    }

    Exp044Metrics {
        n,
        root_sigma: root.sigma,
        root_gap: root.gap,
        p4_viable,
        p5_viable,
        total_viable,
        p4_p4_pairs,
        p4_p4_success,
        p4_p5_pairs,
        p4_p5_success,
        p5_p5_pairs,
        p5_p5_success,
        any_success: (p4_p4_success + p4_p5_success + p5_p5_success) > 0,
        best_pair,
        best_merge_gap: best_gap,
        best_merge_sigma: best_sigma,
        best_merge_n: best_n,
    }
}

// ============================================================================
// EXP-045: Recursive DAG (Depth-2 Merge)
//
// Take a successful merge node from level 1, branch it again into
// P-compositions, merge the new branches. Does depth compound the effect?
// ============================================================================

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Exp045Metrics {
    pub n: usize,
    pub root_sigma: f64,
    pub root_gap: f64,
    pub l1_merge_n: usize,
    pub l1_merge_sigma: f64,
    pub l1_merge_gap: f64,
    pub l1_merge_dpi: bool,
    pub l1_success: bool,
    pub l2_branches_viable: usize,
    pub l2_merge_n: usize,
    pub l2_merge_sigma: f64,
    pub l2_merge_gap: f64,
    pub l2_merge_dpi_vs_l1: bool,
    pub l2_merge_dpi_vs_root: bool,
    pub l2_success: bool,
    pub depth_improves_gap: bool,
    pub depth_preserves_dpi: bool,
}

fn run_exp_045(seed: u64, scale: usize) -> Exp045Metrics {
    use emergence_graph::composition::PStep;

    let n = scale.max(8);
    let mut dag = EmergenceDag::new();
    let root_id = dag.create_root(n, seed);
    let root = dag.nodes[&root_id].clone();

    let fail = Exp045Metrics {
        n,
        root_sigma: root.sigma,
        root_gap: root.gap,
        l1_merge_n: 0,
        l1_merge_sigma: 0.0,
        l1_merge_gap: 0.0,
        l1_merge_dpi: false,
        l1_success: false,
        l2_branches_viable: 0,
        l2_merge_n: 0,
        l2_merge_sigma: 0.0,
        l2_merge_gap: 0.0,
        l2_merge_dpi_vs_l1: false,
        l2_merge_dpi_vs_root: false,
        l2_success: false,
        depth_improves_gap: false,
        depth_preserves_dpi: false,
    };

    // Level 1: Find best merge from 4 compositions
    let compositions = vec![
        PComposition::p2_p4(),
        PComposition::p1sym_p2_p4(),
        PComposition::p1_p2_p4(0.3),
        PComposition::p1_p2_p4(0.1),
    ];

    let mut branches: Vec<String> = Vec::new();
    for (i, comp) in compositions.iter().enumerate() {
        if let Ok(id) = dag.branch(&root_id, comp, seed + (i as u64 + 1) * 1000) {
            branches.push(id);
        }
    }

    if branches.len() < 2 {
        return fail;
    }

    // Find best L1 merge
    let mut best_l1_id: Option<String> = None;
    let mut best_l1_gap = 0.0f64;

    for i in 0..branches.len() {
        for j in (i + 1)..branches.len() {
            if let Ok(merge_id) = dag.merge(
                &root_id,
                &branches[i],
                &branches[j],
                seed + 5000 + (i * branches.len() + j) as u64 * 100,
            ) {
                let m = &dag.nodes[&merge_id];
                let dpi = m.sigma <= root.sigma + 1e-10;
                if dpi && m.gap > 0.01 && m.gap > best_l1_gap {
                    best_l1_gap = m.gap;
                    best_l1_id = Some(merge_id);
                }
            }
        }
    }

    let l1_id = match best_l1_id {
        Some(id) => id,
        None => return fail,
    };
    let l1 = dag.nodes[&l1_id].clone();
    let l1_dpi = l1.sigma <= root.sigma + 1e-10;

    // Level 2: Branch from L1 merge node with lower gating thresholds
    // (merge node has 3-8 states, needs aggressive gating to fragment)
    let l2_comps: Vec<PComposition> = vec![
        PComposition::new(
            vec![PStep::P2Gate { prob: 0.5 }, PStep::P4Sectors],
            "P2(0.5)→P4",
        ),
        PComposition::new(
            vec![
                PStep::P1Symmetrize,
                PStep::P2Gate { prob: 0.5 },
                PStep::P4Sectors,
            ],
            "P1sym→P2(0.5)→P4",
        ),
        PComposition::new(
            vec![
                PStep::P1Perturb { strength: 0.3 },
                PStep::P2Gate { prob: 0.5 },
                PStep::P4Sectors,
            ],
            "P1(0.3)→P2(0.5)→P4",
        ),
    ];

    let mut l2_branches: Vec<String> = Vec::new();
    for (i, comp) in l2_comps.iter().enumerate() {
        if let Ok(id) = dag.branch(&l1_id, comp, seed + 10000 + (i as u64 + 1) * 1000) {
            l2_branches.push(id);
        }
    }

    let l2_viable = l2_branches.len();

    if l2_branches.len() < 2 {
        return Exp045Metrics {
            n,
            root_sigma: root.sigma,
            root_gap: root.gap,
            l1_merge_n: l1.kernel.n,
            l1_merge_sigma: l1.sigma,
            l1_merge_gap: l1.gap,
            l1_merge_dpi: l1_dpi,
            l1_success: true,
            l2_branches_viable: l2_viable,
            l2_merge_n: 0,
            l2_merge_sigma: 0.0,
            l2_merge_gap: 0.0,
            l2_merge_dpi_vs_l1: false,
            l2_merge_dpi_vs_root: false,
            l2_success: false,
            depth_improves_gap: false,
            depth_preserves_dpi: false,
        };
    }

    // Find best L2 merge
    let mut best_l2_id: Option<String> = None;
    let mut best_l2_gap = 0.0f64;

    for i in 0..l2_branches.len() {
        for j in (i + 1)..l2_branches.len() {
            if let Ok(merge_id) = dag.merge(
                &l1_id,
                &l2_branches[i],
                &l2_branches[j],
                seed + 15000 + (i * l2_branches.len() + j) as u64 * 100,
            ) {
                let m = &dag.nodes[&merge_id];
                let dpi_vs_l1 = m.sigma <= l1.sigma + 1e-10;
                if dpi_vs_l1 && m.gap > 0.01 && m.gap > best_l2_gap {
                    best_l2_gap = m.gap;
                    best_l2_id = Some(merge_id);
                }
            }
        }
    }

    match best_l2_id {
        Some(l2_id) => {
            let l2 = &dag.nodes[&l2_id];
            let l2_dpi_vs_l1 = l2.sigma <= l1.sigma + 1e-10;
            let l2_dpi_vs_root = l2.sigma <= root.sigma + 1e-10;
            let l2_success = l2_dpi_vs_l1 && l2.gap > 0.01;
            Exp045Metrics {
                n,
                root_sigma: root.sigma,
                root_gap: root.gap,
                l1_merge_n: l1.kernel.n,
                l1_merge_sigma: l1.sigma,
                l1_merge_gap: l1.gap,
                l1_merge_dpi: l1_dpi,
                l1_success: true,
                l2_branches_viable: l2_viable,
                l2_merge_n: l2.kernel.n,
                l2_merge_sigma: l2.sigma,
                l2_merge_gap: l2.gap,
                l2_merge_dpi_vs_l1: l2_dpi_vs_l1,
                l2_merge_dpi_vs_root: l2_dpi_vs_root,
                l2_success,
                depth_improves_gap: l2.gap > l1.gap,
                depth_preserves_dpi: l2_dpi_vs_root,
            }
        }
        None => Exp045Metrics {
            n,
            root_sigma: root.sigma,
            root_gap: root.gap,
            l1_merge_n: l1.kernel.n,
            l1_merge_sigma: l1.sigma,
            l1_merge_gap: l1.gap,
            l1_merge_dpi: l1_dpi,
            l1_success: true,
            l2_branches_viable: l2_viable,
            l2_merge_n: 0,
            l2_merge_sigma: 0.0,
            l2_merge_gap: 0.0,
            l2_merge_dpi_vs_l1: false,
            l2_merge_dpi_vs_root: false,
            l2_success: false,
            depth_improves_gap: false,
            depth_preserves_dpi: false,
        },
    }
}

// ============================================================================
// EXP-046: Merge Node Structure Analysis
//
// For each successful merge, characterize the macro kernel deeply:
// - Is it reversible? (how close to detailed balance)
// - What's sigma_t for t=1..20? (arrow of time trajectory)
// - How does merge_sigma compare to root_sigma? (sigma reduction ratio)
// - Is the merge kernel approximately doubly stochastic?
// - How does merge RM compare across pairs?
// ============================================================================

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Exp046Metrics {
    pub n: usize,
    pub root_sigma: f64,
    pub root_gap: f64,
    pub n_merges_tested: usize,
    pub n_merges_success: usize,
    // Properties of the BEST merge
    pub best_merge_n: usize,
    pub best_merge_gap: f64,
    pub best_merge_sigma: f64,
    pub best_merge_rm: f64,
    pub best_merge_blocks: usize,
    pub sigma_reduction: f64, // root_sigma / merge_sigma (how much DPI reduces)
    pub merge_reversibility: f64, // How close to detailed balance (0=reversible)
    pub merge_is_connected: bool, // blocks == 1
    // Sigma trajectory: sigma at t=1,5,10,15,20
    pub sigma_t1: f64,
    pub sigma_t5: f64,
    pub sigma_t10: f64,
    pub sigma_t15: f64,
    pub sigma_t20: f64,
    // Comparison: merge sigma vs branch sigma
    pub branch_a_sigma: f64,
    pub branch_b_sigma: f64,
}

fn run_exp_046(seed: u64, scale: usize) -> Exp046Metrics {
    let n = scale.max(8);
    let mut dag = EmergenceDag::new();
    let root_id = dag.create_root(n, seed);
    let root = dag.nodes[&root_id].clone();

    let fail = Exp046Metrics {
        n,
        root_sigma: root.sigma,
        root_gap: root.gap,
        n_merges_tested: 0,
        n_merges_success: 0,
        best_merge_n: 0,
        best_merge_gap: 0.0,
        best_merge_sigma: 0.0,
        best_merge_rm: 0.0,
        best_merge_blocks: 0,
        sigma_reduction: 0.0,
        merge_reversibility: 0.0,
        merge_is_connected: false,
        sigma_t1: 0.0,
        sigma_t5: 0.0,
        sigma_t10: 0.0,
        sigma_t15: 0.0,
        sigma_t20: 0.0,
        branch_a_sigma: 0.0,
        branch_b_sigma: 0.0,
    };

    // Use 4-composition palette
    let compositions = vec![
        PComposition::p2_p4(),
        PComposition::p1sym_p2_p4(),
        PComposition::p1_p2_p4(0.3),
        PComposition::p1_p2_p4(0.1),
    ];

    let mut branches: Vec<(String, usize)> = Vec::new(); // (node_id, comp_index)
    for (i, comp) in compositions.iter().enumerate() {
        if let Ok(id) = dag.branch(&root_id, comp, seed + (i as u64 + 1) * 1000) {
            branches.push((id, i));
        }
    }

    if branches.len() < 2 {
        return fail;
    }

    // Find best merge
    let mut best_merge_id: Option<String> = None;
    let mut best_gap = 0.0f64;
    let mut n_tested = 0;
    let mut n_success = 0;
    let mut best_a_idx = 0usize;
    let mut best_b_idx = 0usize;

    for i in 0..branches.len() {
        for j in (i + 1)..branches.len() {
            n_tested += 1;
            let (ref id_a, _) = branches[i];
            let (ref id_b, _) = branches[j];
            if let Ok(merge_id) =
                dag.merge(&root_id, id_a, id_b, seed + 5000 + n_tested as u64 * 100)
            {
                let m = &dag.nodes[&merge_id];
                let dpi = m.sigma <= root.sigma + 1e-10;
                if dpi && m.gap > 0.01 {
                    n_success += 1;
                    if m.gap > best_gap {
                        best_gap = m.gap;
                        best_merge_id = Some(merge_id);
                        best_a_idx = i;
                        best_b_idx = j;
                    }
                }
            }
        }
    }

    let merge_id = match best_merge_id {
        Some(id) => id,
        None => {
            return Exp046Metrics {
                n_merges_tested: n_tested,
                n_merges_success: n_success,
                ..fail
            }
        }
    };

    let m = dag.nodes[&merge_id].clone();
    let a = dag.nodes[&branches[best_a_idx].0].clone();
    let b = dag.nodes[&branches[best_b_idx].0].clone();

    let merge_edge = dag.edges.values().find(|e| e.child_id == merge_id).unwrap();

    // Deep analysis of merge kernel
    let pi_m = m.kernel.stationary(10000, 1e-12);

    // Reversibility: |K[i][j]*pi[i] - K[j][i]*pi[j]| summed
    let mut rev_score = 0.0;
    for i in 0..m.kernel.n {
        for j in 0..m.kernel.n {
            let diff = (m.kernel.kernel[i][j] * pi_m[i] - m.kernel.kernel[j][i] * pi_m[j]).abs();
            rev_score += diff;
        }
    }

    // Sigma trajectory
    let sigma_at = |t: usize| -> f64 {
        six_primitives_core::substrate::path_reversal_asymmetry(&m.kernel, &pi_m, t)
    };
    let s1 = sigma_at(1);
    let s5 = sigma_at(5);
    let s10 = sigma_at(10);
    let s15 = sigma_at(15);
    let s20 = sigma_at(20);

    let sigma_reduction = if m.sigma > 1e-15 {
        root.sigma / m.sigma
    } else {
        f64::INFINITY
    };

    Exp046Metrics {
        n,
        root_sigma: root.sigma,
        root_gap: root.gap,
        n_merges_tested: n_tested,
        n_merges_success: n_success,
        best_merge_n: m.kernel.n,
        best_merge_gap: m.gap,
        best_merge_sigma: m.sigma,
        best_merge_rm: merge_edge.rm,
        best_merge_blocks: m.blocks,
        sigma_reduction,
        merge_reversibility: rev_score,
        merge_is_connected: m.blocks == 1,
        sigma_t1: s1,
        sigma_t5: s5,
        sigma_t10: s10,
        sigma_t15: s15,
        sigma_t20: s20,
        branch_a_sigma: a.sigma,
        branch_b_sigma: b.sigma,
    }
}

// ============================================================================
// EXP-047: Scale-Up Test with Depth
//
// Start from larger n (512, 1024). Does the merge still work at large scale?
// Does depth-2 become viable when starting larger?
// ============================================================================

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Exp047Metrics {
    pub n: usize,
    pub root_sigma: f64,
    pub root_gap: f64,
    // Level 1
    pub l1_viable: usize,
    pub l1_merge_n: usize,
    pub l1_merge_sigma: f64,
    pub l1_merge_gap: f64,
    pub l1_success: bool,
    // Level 2 (branch from L1, merge again)
    pub l2_viable: usize,
    pub l2_merge_n: usize,
    pub l2_merge_sigma: f64,
    pub l2_merge_gap: f64,
    pub l2_success: bool,
    pub l2_dpi_vs_root: bool,
    // Key
    pub total_depth: usize, // How many merge levels achieved (0, 1, or 2)
}

fn run_exp_047(seed: u64, scale: usize) -> Exp047Metrics {
    use emergence_graph::composition::PStep;

    let n = scale.max(8);
    let mut dag = EmergenceDag::new();
    let root_id = dag.create_root(n, seed);
    let root = dag.nodes[&root_id].clone();

    let fail = Exp047Metrics {
        n,
        root_sigma: root.sigma,
        root_gap: root.gap,
        l1_viable: 0,
        l1_merge_n: 0,
        l1_merge_sigma: 0.0,
        l1_merge_gap: 0.0,
        l1_success: false,
        l2_viable: 0,
        l2_merge_n: 0,
        l2_merge_sigma: 0.0,
        l2_merge_gap: 0.0,
        l2_success: false,
        l2_dpi_vs_root: false,
        total_depth: 0,
    };

    // Level 1: 6-composition mixed palette (P4+P5) for best viability
    let compositions: Vec<PComposition> = vec![
        PComposition::p2_p4(),
        PComposition::p1sym_p2_p4(),
        PComposition::p1_p2_p4(0.3),
        PComposition::p2_p5(20),
        PComposition::p1sym_p2_p5(20),
        PComposition::p1_p2_p4(0.1),
    ];

    let mut branches: Vec<String> = Vec::new();
    for (i, comp) in compositions.iter().enumerate() {
        if let Ok(id) = dag.branch(&root_id, comp, seed + (i as u64 + 1) * 1000) {
            branches.push(id);
        }
    }

    let l1_viable = branches.len();
    if branches.len() < 2 {
        return Exp047Metrics { l1_viable, ..fail };
    }

    // Find best L1 merge
    let mut best_l1_id: Option<String> = None;
    let mut best_l1_gap = 0.0f64;

    for i in 0..branches.len() {
        for j in (i + 1)..branches.len() {
            if let Ok(merge_id) = dag.merge(
                &root_id,
                &branches[i],
                &branches[j],
                seed + 5000 + (i * branches.len() + j) as u64 * 100,
            ) {
                let m = &dag.nodes[&merge_id];
                let dpi = m.sigma <= root.sigma + 1e-10;
                if dpi && m.gap > 0.01 && m.gap > best_l1_gap {
                    best_l1_gap = m.gap;
                    best_l1_id = Some(merge_id);
                }
            }
        }
    }

    let l1_id = match best_l1_id {
        Some(id) => id,
        None => return Exp047Metrics { l1_viable, ..fail },
    };
    let l1 = dag.nodes[&l1_id].clone();

    // Level 2: Branch from L1 merge with adapted gating
    // Use more aggressive gating for small kernels
    let l1_n = l1.kernel.n;
    let l2_gate_prob = if l1_n <= 4 {
        0.3
    } else if l1_n <= 8 {
        0.5
    } else {
        0.7
    };

    let l2_comps: Vec<PComposition> = vec![
        PComposition::new(
            vec![PStep::P2Gate { prob: l2_gate_prob }, PStep::P4Sectors],
            "P2→P4",
        ),
        PComposition::new(
            vec![
                PStep::P1Symmetrize,
                PStep::P2Gate { prob: l2_gate_prob },
                PStep::P4Sectors,
            ],
            "P1sym→P2→P4",
        ),
        PComposition::new(
            vec![
                PStep::P1Perturb { strength: 0.5 },
                PStep::P2Gate { prob: l2_gate_prob },
                PStep::P4Sectors,
            ],
            "P1(0.5)→P2→P4",
        ),
        PComposition::new(vec![PStep::P5Package { tau: 20 }], "P5"),
    ];

    let mut l2_branches: Vec<String> = Vec::new();
    for (i, comp) in l2_comps.iter().enumerate() {
        if let Ok(id) = dag.branch(&l1_id, comp, seed + 10000 + (i as u64 + 1) * 1000) {
            l2_branches.push(id);
        }
    }

    let l2_viable = l2_branches.len();

    if l2_branches.len() < 2 {
        return Exp047Metrics {
            n,
            root_sigma: root.sigma,
            root_gap: root.gap,
            l1_viable,
            l1_merge_n: l1.kernel.n,
            l1_merge_sigma: l1.sigma,
            l1_merge_gap: l1.gap,
            l1_success: true,
            l2_viable,
            l2_merge_n: 0,
            l2_merge_sigma: 0.0,
            l2_merge_gap: 0.0,
            l2_success: false,
            l2_dpi_vs_root: false,
            total_depth: 1,
        };
    }

    // Find best L2 merge
    let mut best_l2_id: Option<String> = None;
    let mut best_l2_gap = 0.0f64;

    for i in 0..l2_branches.len() {
        for j in (i + 1)..l2_branches.len() {
            if let Ok(merge_id) = dag.merge(
                &l1_id,
                &l2_branches[i],
                &l2_branches[j],
                seed + 15000 + (i * l2_branches.len() + j) as u64 * 100,
            ) {
                let m = &dag.nodes[&merge_id];
                let dpi_vs_l1 = m.sigma <= l1.sigma + 1e-10;
                if dpi_vs_l1 && m.gap > 0.01 && m.gap > best_l2_gap {
                    best_l2_gap = m.gap;
                    best_l2_id = Some(merge_id);
                }
            }
        }
    }

    match best_l2_id {
        Some(l2_id) => {
            let l2 = &dag.nodes[&l2_id];
            Exp047Metrics {
                n,
                root_sigma: root.sigma,
                root_gap: root.gap,
                l1_viable,
                l1_merge_n: l1.kernel.n,
                l1_merge_sigma: l1.sigma,
                l1_merge_gap: l1.gap,
                l1_success: true,
                l2_viable,
                l2_merge_n: l2.kernel.n,
                l2_merge_sigma: l2.sigma,
                l2_merge_gap: l2.gap,
                l2_success: true,
                l2_dpi_vs_root: l2.sigma <= root.sigma + 1e-10,
                total_depth: 2,
            }
        }
        None => Exp047Metrics {
            n,
            root_sigma: root.sigma,
            root_gap: root.gap,
            l1_viable,
            l1_merge_n: l1.kernel.n,
            l1_merge_sigma: l1.sigma,
            l1_merge_gap: l1.gap,
            l1_success: true,
            l2_viable,
            l2_merge_n: 0,
            l2_merge_sigma: 0.0,
            l2_merge_gap: 0.0,
            l2_success: false,
            l2_dpi_vs_root: false,
            total_depth: 1,
        },
    }
}

// ============================================================================
// EXP-048: L2 Branch Viability Probe
//
// CLO-045 declared depth-2 blocked, but EXP-047 only used hardcoded P2Gate(0.5-0.7)
// instead of scale-dependent thresholds. For merge_n=30, P2GateScaled gives
// prob=0.95 (much more aggressive). This experiment systematically sweeps:
//   P1 strength × P2 threshold × lens type
// to find which combinations can fragment merge kernels.
// ============================================================================

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Exp048Metrics {
    pub n: usize,
    pub l1_merge_n: usize,
    pub l1_merge_gap: f64,
    pub l1_merge_sigma: f64,
    pub l1_success: bool,
    // Grid sweep results
    pub n_combos_tested: usize,
    pub n_combos_viable: usize, // produced ≥2 macro states
    pub best_combo: String,
    pub best_macro_n: usize,
    // Per P1-strength viability (out of 6 combos each: 3 gatings × 2 lenses)
    pub v_none: usize, // P1 strength = 0 (no perturbation)
    pub v_s05: usize,  // P1 strength = 0.5
    pub v_s10: usize,  // P1 strength = 1.0
    pub v_s20: usize,  // P1 strength = 2.0
    pub v_s50: usize,  // P1 strength = 5.0
    // Per P2-gating viability (out of 10 combos each: 5 strengths × 2 lenses)
    pub v_scaled: usize, // P2GateScaled (scale-dependent threshold)
    pub v_g90: usize,    // P2Gate(0.90)
    pub v_g95: usize,    // P2Gate(0.95)
    // Per lens viability (out of 15 combos each: 5 strengths × 3 gatings)
    pub v_p4: usize,
    pub v_p5: usize,
}

fn run_exp_048(seed: u64, scale: usize) -> Exp048Metrics {
    use emergence_graph::composition::PStep;

    let n = scale.max(8);
    let mut dag = EmergenceDag::new();
    let root_id = dag.create_root(n, seed);
    let root = dag.nodes[&root_id].clone();

    let fail = Exp048Metrics {
        n,
        l1_merge_n: 0,
        l1_merge_gap: 0.0,
        l1_merge_sigma: 0.0,
        l1_success: false,
        n_combos_tested: 0,
        n_combos_viable: 0,
        best_combo: String::new(),
        best_macro_n: 0,
        v_none: 0,
        v_s05: 0,
        v_s10: 0,
        v_s20: 0,
        v_s50: 0,
        v_scaled: 0,
        v_g90: 0,
        v_g95: 0,
        v_p4: 0,
        v_p5: 0,
    };

    // L1: Mixed palette (100% success from CLO-045)
    let compositions: Vec<PComposition> = vec![
        PComposition::p2_p4(),
        PComposition::p1sym_p2_p4(),
        PComposition::p1_p2_p4(0.3),
        PComposition::p2_p5(20),
        PComposition::p1sym_p2_p5(20),
        PComposition::p1_p2_p4(0.1),
    ];

    let mut branches: Vec<String> = Vec::new();
    for (i, comp) in compositions.iter().enumerate() {
        if let Ok(id) = dag.branch(&root_id, comp, seed + (i as u64 + 1) * 1000) {
            branches.push(id);
        }
    }
    if branches.len() < 2 {
        return fail;
    }

    // Find best L1 merge
    let mut best_l1_id: Option<String> = None;
    let mut best_l1_gap = 0.0f64;
    for i in 0..branches.len() {
        for j in (i + 1)..branches.len() {
            if let Ok(merge_id) = dag.merge(
                &root_id,
                &branches[i],
                &branches[j],
                seed + 5000 + (i * branches.len() + j) as u64 * 100,
            ) {
                let m = &dag.nodes[&merge_id];
                let dpi = m.sigma <= root.sigma + 1e-10;
                if dpi && m.gap > 0.01 && m.gap > best_l1_gap {
                    best_l1_gap = m.gap;
                    best_l1_id = Some(merge_id);
                }
            }
        }
    }

    let l1_id = match best_l1_id {
        Some(id) => id,
        None => return fail,
    };
    let l1 = dag.nodes[&l1_id].clone();
    let l1_n = l1.kernel.n;

    println!(
        "  L1 merge: n={} gap={:.6} sigma={:.6}",
        l1_n, l1.gap, l1.sigma
    );

    // L2: Systematic viability probe
    // Grid: 5 P1 strengths × 3 P2 gatings × 2 lenses = 30 combos
    let strengths: [(f64, &str); 5] = [
        (-1.0, "none"),
        (0.5, "s0.5"),
        (1.0, "s1.0"),
        (2.0, "s2.0"),
        (5.0, "s5.0"),
    ];
    // gating_prob < 0 means use P2GateScaled
    let gatings: [(f64, &str); 3] = [(-1.0, "scaled"), (0.90, "g90"), (0.95, "g95")];
    let lenses: [&str; 2] = ["P4", "P5"];

    let mut n_tested = 0usize;
    let mut n_viable = 0usize;
    let mut v_strength = [0usize; 5];
    let mut v_gating = [0usize; 3];
    let mut v_p4 = 0usize;
    let mut v_p5 = 0usize;
    let mut best_combo = String::new();
    let mut best_macro_n = 0usize;

    let mut combo_seed = seed + 20000;

    for (si, &(strength, sname)) in strengths.iter().enumerate() {
        for (gi, &(gating_prob, gname)) in gatings.iter().enumerate() {
            for (_li, &lname) in lenses.iter().enumerate() {
                combo_seed += 1;

                // Build composition steps
                let mut steps = Vec::new();
                if strength >= 0.0 {
                    steps.push(PStep::P1Perturb { strength });
                }
                if gating_prob < 0.0 {
                    steps.push(PStep::P2GateScaled);
                } else {
                    steps.push(PStep::P2Gate { prob: gating_prob });
                }
                match lname {
                    "P4" => steps.push(PStep::P4Sectors),
                    _ => steps.push(PStep::P5Package { tau: 20 }),
                }

                let name = format!("{}-{}-{}", sname, gname, lname);
                let comp = PComposition::new(steps, &name);

                n_tested += 1;
                match dag.branch(&l1_id, &comp, combo_seed) {
                    Ok(child_id) => {
                        let child = &dag.nodes[&child_id];
                        n_viable += 1;
                        v_strength[si] += 1;
                        v_gating[gi] += 1;
                        if lname == "P4" {
                            v_p4 += 1;
                        } else {
                            v_p5 += 1;
                        }

                        if child.kernel.n > best_macro_n {
                            best_macro_n = child.kernel.n;
                            best_combo = name.clone();
                        }
                        println!(
                            "    VIABLE: {:20} → macro_n={:3} gap={:.6}",
                            name, child.kernel.n, child.gap
                        );
                    }
                    Err(_) => {
                        println!("    fail:   {}", name);
                    }
                }
            }
        }
    }

    Exp048Metrics {
        n,
        l1_merge_n: l1_n,
        l1_merge_gap: l1.gap,
        l1_merge_sigma: l1.sigma,
        l1_success: true,
        n_combos_tested: n_tested,
        n_combos_viable: n_viable,
        best_combo,
        best_macro_n,
        v_none: v_strength[0],
        v_s05: v_strength[1],
        v_s10: v_strength[2],
        v_s20: v_strength[3],
        v_s50: v_strength[4],
        v_scaled: v_gating[0],
        v_g90: v_gating[1],
        v_g95: v_gating[2],
        v_p4,
        v_p5,
    }
}

// ============================================================================
// EXP-049: Full Depth-2 with Scale-Dependent Gating
//
// If EXP-048 shows viable L2 compositions, this experiment attempts the full
// depth-2 merge: L1 merge → branch × 2 → L2 merge.
// Uses P2GateScaled (not hardcoded) + P1 perturbation sweep.
// ============================================================================

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Exp049Metrics {
    pub n: usize,
    pub root_sigma: f64,
    pub root_gap: f64,
    // Level 1
    pub l1_merge_n: usize,
    pub l1_merge_sigma: f64,
    pub l1_merge_gap: f64,
    pub l1_success: bool,
    // Level 2 branching
    pub l2_n_compositions: usize,
    pub l2_viable: usize,
    pub l2_viable_names: String,
    // Level 2 merge
    pub l2_merge_n: usize,
    pub l2_merge_sigma: f64,
    pub l2_merge_gap: f64,
    pub l2_success: bool,
    pub l2_dpi_vs_l1: bool,
    pub l2_dpi_vs_root: bool,
    // Key
    pub total_depth: usize,
}

fn run_exp_049(seed: u64, scale: usize) -> Exp049Metrics {
    use emergence_graph::composition::PStep;

    let n = scale.max(8);
    let mut dag = EmergenceDag::new();
    let root_id = dag.create_root(n, seed);
    let root = dag.nodes[&root_id].clone();

    let fail = Exp049Metrics {
        n,
        root_sigma: root.sigma,
        root_gap: root.gap,
        l1_merge_n: 0,
        l1_merge_sigma: 0.0,
        l1_merge_gap: 0.0,
        l1_success: false,
        l2_n_compositions: 0,
        l2_viable: 0,
        l2_viable_names: String::new(),
        l2_merge_n: 0,
        l2_merge_sigma: 0.0,
        l2_merge_gap: 0.0,
        l2_success: false,
        l2_dpi_vs_l1: false,
        l2_dpi_vs_root: false,
        total_depth: 0,
    };

    // L1: Mixed palette (100% success)
    let compositions: Vec<PComposition> = vec![
        PComposition::p2_p4(),
        PComposition::p1sym_p2_p4(),
        PComposition::p1_p2_p4(0.3),
        PComposition::p2_p5(20),
        PComposition::p1sym_p2_p5(20),
        PComposition::p1_p2_p4(0.1),
    ];

    let mut branches: Vec<String> = Vec::new();
    for (i, comp) in compositions.iter().enumerate() {
        if let Ok(id) = dag.branch(&root_id, comp, seed + (i as u64 + 1) * 1000) {
            branches.push(id);
        }
    }
    if branches.len() < 2 {
        return fail;
    }

    // Find best L1 merge
    let mut best_l1_id: Option<String> = None;
    let mut best_l1_gap = 0.0f64;
    for i in 0..branches.len() {
        for j in (i + 1)..branches.len() {
            if let Ok(merge_id) = dag.merge(
                &root_id,
                &branches[i],
                &branches[j],
                seed + 5000 + (i * branches.len() + j) as u64 * 100,
            ) {
                let m = &dag.nodes[&merge_id];
                let dpi = m.sigma <= root.sigma + 1e-10;
                if dpi && m.gap > 0.01 && m.gap > best_l1_gap {
                    best_l1_gap = m.gap;
                    best_l1_id = Some(merge_id);
                }
            }
        }
    }

    let l1_id = match best_l1_id {
        Some(id) => id,
        None => return fail,
    };
    let l1 = dag.nodes[&l1_id].clone();
    let l1_n = l1.kernel.n;

    // L2: Use P2GateScaled (calibrated for merge_n) + varying P1 perturbation
    // This is what EXP-047 should have used.
    let l2_comps: Vec<PComposition> = vec![
        // No perturbation, scale-dependent gating
        PComposition::new(vec![PStep::P2GateScaled, PStep::P4Sectors], "P2s→P4"),
        PComposition::new(
            vec![PStep::P2GateScaled, PStep::P5Package { tau: 20 }],
            "P2s→P5",
        ),
        // P1 perturbation at 1.0
        PComposition::new(
            vec![
                PStep::P1Perturb { strength: 1.0 },
                PStep::P2GateScaled,
                PStep::P4Sectors,
            ],
            "P1(1.0)→P2s→P4",
        ),
        PComposition::new(
            vec![
                PStep::P1Perturb { strength: 1.0 },
                PStep::P2GateScaled,
                PStep::P5Package { tau: 20 },
            ],
            "P1(1.0)→P2s→P5",
        ),
        // P1 perturbation at 2.0
        PComposition::new(
            vec![
                PStep::P1Perturb { strength: 2.0 },
                PStep::P2GateScaled,
                PStep::P4Sectors,
            ],
            "P1(2.0)→P2s→P4",
        ),
        PComposition::new(
            vec![
                PStep::P1Perturb { strength: 2.0 },
                PStep::P2GateScaled,
                PStep::P5Package { tau: 20 },
            ],
            "P1(2.0)→P2s→P5",
        ),
        // P1 perturbation at 5.0
        PComposition::new(
            vec![
                PStep::P1Perturb { strength: 5.0 },
                PStep::P2GateScaled,
                PStep::P4Sectors,
            ],
            "P1(5.0)→P2s→P4",
        ),
        PComposition::new(
            vec![
                PStep::P1Perturb { strength: 5.0 },
                PStep::P2GateScaled,
                PStep::P5Package { tau: 20 },
            ],
            "P1(5.0)→P2s→P5",
        ),
        // Fixed high gating with perturbation
        PComposition::new(
            vec![
                PStep::P1Perturb { strength: 2.0 },
                PStep::P2Gate { prob: 0.95 },
                PStep::P4Sectors,
            ],
            "P1(2.0)→P2(0.95)→P4",
        ),
        PComposition::new(
            vec![
                PStep::P1Perturb { strength: 5.0 },
                PStep::P2Gate { prob: 0.95 },
                PStep::P4Sectors,
            ],
            "P1(5.0)→P2(0.95)→P4",
        ),
    ];

    let n_l2_comps = l2_comps.len();
    let mut l2_branches: Vec<(String, String)> = Vec::new(); // (name, node_id)
    for (i, comp) in l2_comps.iter().enumerate() {
        if let Ok(id) = dag.branch(&l1_id, comp, seed + 10000 + (i as u64 + 1) * 1000) {
            println!(
                "    L2 viable: {} → n={}",
                comp.name, dag.nodes[&id].kernel.n
            );
            l2_branches.push((comp.name.clone(), id));
        }
    }

    let l2_viable = l2_branches.len();
    let l2_viable_names: String = l2_branches
        .iter()
        .map(|(n, _)| n.as_str())
        .collect::<Vec<_>>()
        .join(", ");

    if l2_branches.len() < 2 {
        return Exp049Metrics {
            n,
            root_sigma: root.sigma,
            root_gap: root.gap,
            l1_merge_n: l1_n,
            l1_merge_sigma: l1.sigma,
            l1_merge_gap: l1.gap,
            l1_success: true,
            l2_n_compositions: n_l2_comps,
            l2_viable,
            l2_viable_names,
            l2_merge_n: 0,
            l2_merge_sigma: 0.0,
            l2_merge_gap: 0.0,
            l2_success: false,
            l2_dpi_vs_l1: false,
            l2_dpi_vs_root: false,
            total_depth: 1,
        };
    }

    // Find best L2 merge
    let mut best_l2_id: Option<String> = None;
    let mut best_l2_gap = 0.0f64;

    for i in 0..l2_branches.len() {
        for j in (i + 1)..l2_branches.len() {
            if let Ok(merge_id) = dag.merge(
                &l1_id,
                &l2_branches[i].1,
                &l2_branches[j].1,
                seed + 15000 + (i * l2_branches.len() + j) as u64 * 100,
            ) {
                let m = &dag.nodes[&merge_id];
                let dpi_vs_l1 = m.sigma <= l1.sigma + 1e-10;
                if dpi_vs_l1 && m.gap > 0.01 && m.gap > best_l2_gap {
                    best_l2_gap = m.gap;
                    best_l2_id = Some(merge_id);
                    println!(
                        "    L2 merge: {} + {} → n={} gap={:.6} sigma={:.6} DPI={}",
                        l2_branches[i].0, l2_branches[j].0, m.kernel.n, m.gap, m.sigma, dpi_vs_l1
                    );
                }
            }
        }
    }

    match best_l2_id {
        Some(l2_id) => {
            let l2 = &dag.nodes[&l2_id];
            Exp049Metrics {
                n,
                root_sigma: root.sigma,
                root_gap: root.gap,
                l1_merge_n: l1_n,
                l1_merge_sigma: l1.sigma,
                l1_merge_gap: l1.gap,
                l1_success: true,
                l2_n_compositions: n_l2_comps,
                l2_viable,
                l2_viable_names,
                l2_merge_n: l2.kernel.n,
                l2_merge_sigma: l2.sigma,
                l2_merge_gap: l2.gap,
                l2_success: true,
                l2_dpi_vs_l1: l2.sigma <= l1.sigma + 1e-10,
                l2_dpi_vs_root: l2.sigma <= root.sigma + 1e-10,
                total_depth: 2,
            }
        }
        None => Exp049Metrics {
            n,
            root_sigma: root.sigma,
            root_gap: root.gap,
            l1_merge_n: l1_n,
            l1_merge_sigma: l1.sigma,
            l1_merge_gap: l1.gap,
            l1_success: true,
            l2_n_compositions: n_l2_comps,
            l2_viable,
            l2_viable_names,
            l2_merge_n: 0,
            l2_merge_sigma: 0.0,
            l2_merge_gap: 0.0,
            l2_success: false,
            l2_dpi_vs_l1: false,
            l2_dpi_vs_root: false,
            total_depth: 1,
        },
    }
}

// ============================================================================
// EXP-050: Maximum Depth Probe
//
// How deep can the recursive DAG merge go? Keep merging until no more
// viable branch pairs exist. At each level, use P2GateScaled + P1 sweep.
// ============================================================================

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct LevelMetrics {
    pub merge_n: usize,
    pub merge_sigma: f64,
    pub merge_gap: f64,
    pub viable: usize,
    pub dpi_vs_prev: bool,
    pub dpi_vs_root: bool,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Exp050Metrics {
    pub n: usize,
    pub root_sigma: f64,
    pub root_gap: f64,
    pub max_depth: usize,
    pub all_dpi_vs_root: bool,
    pub levels: Vec<LevelMetrics>,
}

fn run_exp_050(seed: u64, scale: usize) -> Exp050Metrics {
    use emergence_graph::composition::PStep;

    let n = scale.max(8);
    let mut dag = EmergenceDag::new();
    let root_id = dag.create_root(n, seed);
    let root = dag.nodes[&root_id].clone();

    // L1: Mixed palette (100% success)
    let l1_compositions: Vec<PComposition> = vec![
        PComposition::p2_p4(),
        PComposition::p1sym_p2_p4(),
        PComposition::p1_p2_p4(0.3),
        PComposition::p2_p5(20),
        PComposition::p1sym_p2_p5(20),
        PComposition::p1_p2_p4(0.1),
    ];

    let mut branches: Vec<String> = Vec::new();
    for (i, comp) in l1_compositions.iter().enumerate() {
        if let Ok(id) = dag.branch(&root_id, comp, seed + (i as u64 + 1) * 1000) {
            branches.push(id);
        }
    }

    if branches.len() < 2 {
        return Exp050Metrics {
            n,
            root_sigma: root.sigma,
            root_gap: root.gap,
            max_depth: 0,
            all_dpi_vs_root: true,
            levels: vec![],
        };
    }

    // Find best L1 merge
    let mut best_id: Option<String> = None;
    let mut best_gap = 0.0f64;
    for i in 0..branches.len() {
        for j in (i + 1)..branches.len() {
            if let Ok(merge_id) = dag.merge(
                &root_id,
                &branches[i],
                &branches[j],
                seed + 5000 + (i * branches.len() + j) as u64 * 100,
            ) {
                let m = &dag.nodes[&merge_id];
                let dpi = m.sigma <= root.sigma + 1e-10;
                if dpi && m.gap > 0.01 && m.gap > best_gap {
                    best_gap = m.gap;
                    best_id = Some(merge_id);
                }
            }
        }
    }

    let l1_id = match best_id {
        Some(id) => id,
        None => {
            return Exp050Metrics {
                n,
                root_sigma: root.sigma,
                root_gap: root.gap,
                max_depth: 0,
                all_dpi_vs_root: true,
                levels: vec![],
            };
        }
    };
    let l1 = dag.nodes[&l1_id].clone();

    let mut levels: Vec<LevelMetrics> = vec![LevelMetrics {
        merge_n: l1.kernel.n,
        merge_sigma: l1.sigma,
        merge_gap: l1.gap,
        viable: branches.len(),
        dpi_vs_prev: l1.sigma <= root.sigma + 1e-10,
        dpi_vs_root: l1.sigma <= root.sigma + 1e-10,
    }];

    // Recursive: keep going deeper
    let mut current_id = l1_id;
    let mut current_sigma;
    let mut depth = 1;
    let max_levels = 10; // Safety cap

    while depth < max_levels {
        current_sigma = dag.nodes[&current_id].sigma;
        let current_n = dag.nodes[&current_id].kernel.n;

        if current_n <= 2 {
            println!(
                "  Depth {} terminated: merge_n={} (too small)",
                depth, current_n
            );
            break;
        }

        // Build L(depth+1) compositions using P2GateScaled
        let lk_comps: Vec<PComposition> = vec![
            PComposition::new(vec![PStep::P2GateScaled, PStep::P4Sectors], "P2s→P4"),
            PComposition::new(
                vec![PStep::P2GateScaled, PStep::P5Package { tau: 20 }],
                "P2s→P5",
            ),
            PComposition::new(
                vec![
                    PStep::P1Perturb { strength: 1.0 },
                    PStep::P2GateScaled,
                    PStep::P4Sectors,
                ],
                "P1(1)→P2s→P4",
            ),
            PComposition::new(
                vec![
                    PStep::P1Perturb { strength: 1.0 },
                    PStep::P2GateScaled,
                    PStep::P5Package { tau: 20 },
                ],
                "P1(1)→P2s→P5",
            ),
            PComposition::new(
                vec![
                    PStep::P1Perturb { strength: 2.0 },
                    PStep::P2GateScaled,
                    PStep::P4Sectors,
                ],
                "P1(2)→P2s→P4",
            ),
            PComposition::new(
                vec![
                    PStep::P1Perturb { strength: 2.0 },
                    PStep::P2GateScaled,
                    PStep::P5Package { tau: 20 },
                ],
                "P1(2)→P2s→P5",
            ),
            PComposition::new(
                vec![
                    PStep::P1Perturb { strength: 5.0 },
                    PStep::P2GateScaled,
                    PStep::P4Sectors,
                ],
                "P1(5)→P2s→P4",
            ),
            PComposition::new(
                vec![
                    PStep::P1Perturb { strength: 5.0 },
                    PStep::P2GateScaled,
                    PStep::P5Package { tau: 20 },
                ],
                "P1(5)→P2s→P5",
            ),
        ];

        let depth_seed = seed + (depth as u64 + 1) * 10000;
        let mut lk_branches: Vec<String> = Vec::new();
        for (i, comp) in lk_comps.iter().enumerate() {
            if let Ok(id) = dag.branch(&current_id, comp, depth_seed + (i as u64 + 1) * 1000) {
                lk_branches.push(id);
            }
        }

        let viable = lk_branches.len();
        if viable < 2 {
            println!(
                "  Depth {} terminated: only {} viable branches (need ≥2)",
                depth + 1,
                viable
            );
            break;
        }

        // Find best merge
        let mut next_best_id: Option<String> = None;
        let mut next_best_gap = 0.0f64;
        for i in 0..lk_branches.len() {
            for j in (i + 1)..lk_branches.len() {
                if let Ok(merge_id) = dag.merge(
                    &current_id,
                    &lk_branches[i],
                    &lk_branches[j],
                    depth_seed + 5000 + (i * lk_branches.len() + j) as u64 * 100,
                ) {
                    let m = &dag.nodes[&merge_id];
                    let dpi_vs_prev = m.sigma <= current_sigma + 1e-10;
                    if dpi_vs_prev && m.gap > 0.01 && m.gap > next_best_gap {
                        next_best_gap = m.gap;
                        next_best_id = Some(merge_id);
                    }
                }
            }
        }

        match next_best_id {
            Some(next_id) => {
                let next = dag.nodes[&next_id].clone();
                let dpi_root = next.sigma <= root.sigma + 1e-10;
                let dpi_prev = next.sigma <= current_sigma + 1e-10;
                println!(
                    "  L{}: n={} sigma={:.6} gap={:.6} viable={} DPI_root={} DPI_prev={}",
                    depth + 1,
                    next.kernel.n,
                    next.sigma,
                    next.gap,
                    viable,
                    dpi_root,
                    dpi_prev
                );
                levels.push(LevelMetrics {
                    merge_n: next.kernel.n,
                    merge_sigma: next.sigma,
                    merge_gap: next.gap,
                    viable,
                    dpi_vs_prev: dpi_prev,
                    dpi_vs_root: dpi_root,
                });
                current_id = next_id;
                depth += 1;
            }
            None => {
                println!("  Depth {} terminated: no viable merge pair", depth + 1);
                break;
            }
        }
    }

    let all_dpi = levels.iter().all(|l| l.dpi_vs_root);

    Exp050Metrics {
        n,
        root_sigma: root.sigma,
        root_gap: root.gap,
        max_depth: depth,
        all_dpi_vs_root: all_dpi,
        levels,
    }
}

// ============================================================================
// EXP-051: Path Dependence Test
//
// Same root kernel, 10 different cascade paths (different branching seeds).
// Question: Is depth/structure determined by the root or by branching choices?
// Also: characterize terminal kernels — are they universal?
// ============================================================================

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct CascadePathMetrics {
    pub path_seed: u64,
    pub depth: usize,
    pub l1_merge_n: usize,
    pub terminal_n: usize,
    pub terminal_sigma: f64,
    pub terminal_gap: f64,
    pub terminal_reversibility: f64, // sum |K[i][j]*pi[i] - K[j][i]*pi[j]|
    pub sigma_per_level: Vec<f64>,
    pub n_per_level: Vec<usize>,
    pub all_dpi: bool,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Exp051Metrics {
    pub n: usize,
    pub root_sigma: f64,
    pub root_gap: f64,
    pub n_paths: usize,
    pub depth_min: usize,
    pub depth_max: usize,
    pub depth_mean: f64,
    pub depth_std: f64,
    pub all_paths_dpi: bool,
    pub terminal_n_values: String,
    pub terminal_reversibility_mean: f64,
    pub paths: Vec<CascadePathMetrics>,
}

fn measure_reversibility(kernel: &six_primitives_core::substrate::MarkovKernel) -> f64 {
    let pi = kernel.stationary(10000, 1e-12);
    let mut rev = 0.0;
    for i in 0..kernel.n {
        for j in 0..kernel.n {
            rev += (kernel.kernel[i][j] * pi[i] - kernel.kernel[j][i] * pi[j]).abs();
        }
    }
    rev
}

fn run_one_cascade(
    dag: &mut EmergenceDag,
    root_id: &str,
    root_sigma: f64,
    path_seed: u64,
) -> CascadePathMetrics {
    use emergence_graph::composition::PStep;

    // L1: mixed palette
    let l1_compositions: Vec<PComposition> = vec![
        PComposition::p2_p4(),
        PComposition::p1sym_p2_p4(),
        PComposition::p1_p2_p4(0.3),
        PComposition::p2_p5(20),
        PComposition::p1sym_p2_p5(20),
        PComposition::p1_p2_p4(0.1),
    ];

    let mut branches: Vec<String> = Vec::new();
    for (i, comp) in l1_compositions.iter().enumerate() {
        if let Ok(id) = dag.branch(root_id, comp, path_seed + (i as u64 + 1) * 1000) {
            branches.push(id);
        }
    }

    if branches.len() < 2 {
        return CascadePathMetrics {
            path_seed,
            depth: 0,
            l1_merge_n: 0,
            terminal_n: 0,
            terminal_sigma: 0.0,
            terminal_gap: 0.0,
            terminal_reversibility: 0.0,
            sigma_per_level: vec![],
            n_per_level: vec![],
            all_dpi: true,
        };
    }

    // Find best L1 merge
    let mut best_id: Option<String> = None;
    let mut best_gap = 0.0f64;
    for i in 0..branches.len() {
        for j in (i + 1)..branches.len() {
            if let Ok(merge_id) = dag.merge(
                root_id,
                &branches[i],
                &branches[j],
                path_seed + 5000 + (i * branches.len() + j) as u64 * 100,
            ) {
                let m = &dag.nodes[&merge_id];
                let dpi = m.sigma <= root_sigma + 1e-10;
                if dpi && m.gap > 0.01 && m.gap > best_gap {
                    best_gap = m.gap;
                    best_id = Some(merge_id.clone());
                }
            }
        }
    }

    let l1_id = match best_id {
        Some(id) => id,
        None => {
            return CascadePathMetrics {
                path_seed,
                depth: 0,
                l1_merge_n: 0,
                terminal_n: 0,
                terminal_sigma: 0.0,
                terminal_gap: 0.0,
                terminal_reversibility: 0.0,
                sigma_per_level: vec![],
                n_per_level: vec![],
                all_dpi: true,
            };
        }
    };
    let l1 = dag.nodes[&l1_id].clone();
    let l1_merge_n = l1.kernel.n;

    let mut sigma_per_level = vec![l1.sigma];
    let mut n_per_level = vec![l1.kernel.n];
    let mut all_dpi = l1.sigma <= root_sigma + 1e-10;

    let mut current_id = l1_id;
    let mut depth = 1;
    let max_levels = 10;

    while depth < max_levels {
        let current_sigma = dag.nodes[&current_id].sigma;
        let current_n = dag.nodes[&current_id].kernel.n;

        if current_n <= 2 {
            break;
        }

        let lk_comps: Vec<PComposition> = vec![
            PComposition::new(vec![PStep::P2GateScaled, PStep::P4Sectors], "P2s→P4"),
            PComposition::new(
                vec![PStep::P2GateScaled, PStep::P5Package { tau: 20 }],
                "P2s→P5",
            ),
            PComposition::new(
                vec![
                    PStep::P1Perturb { strength: 1.0 },
                    PStep::P2GateScaled,
                    PStep::P4Sectors,
                ],
                "P1(1)→P2s→P4",
            ),
            PComposition::new(
                vec![
                    PStep::P1Perturb { strength: 1.0 },
                    PStep::P2GateScaled,
                    PStep::P5Package { tau: 20 },
                ],
                "P1(1)→P2s→P5",
            ),
            PComposition::new(
                vec![
                    PStep::P1Perturb { strength: 2.0 },
                    PStep::P2GateScaled,
                    PStep::P4Sectors,
                ],
                "P1(2)→P2s→P4",
            ),
            PComposition::new(
                vec![
                    PStep::P1Perturb { strength: 2.0 },
                    PStep::P2GateScaled,
                    PStep::P5Package { tau: 20 },
                ],
                "P1(2)→P2s→P5",
            ),
            PComposition::new(
                vec![
                    PStep::P1Perturb { strength: 5.0 },
                    PStep::P2GateScaled,
                    PStep::P4Sectors,
                ],
                "P1(5)→P2s→P4",
            ),
            PComposition::new(
                vec![
                    PStep::P1Perturb { strength: 5.0 },
                    PStep::P2GateScaled,
                    PStep::P5Package { tau: 20 },
                ],
                "P1(5)→P2s→P5",
            ),
        ];

        let depth_seed = path_seed + (depth as u64 + 1) * 10000;
        let mut lk_branches: Vec<String> = Vec::new();
        for (i, comp) in lk_comps.iter().enumerate() {
            if let Ok(id) = dag.branch(&current_id, comp, depth_seed + (i as u64 + 1) * 1000) {
                lk_branches.push(id);
            }
        }

        if lk_branches.len() < 2 {
            break;
        }

        let mut next_best_id: Option<String> = None;
        let mut next_best_gap = 0.0f64;
        for i in 0..lk_branches.len() {
            for j in (i + 1)..lk_branches.len() {
                if let Ok(merge_id) = dag.merge(
                    &current_id,
                    &lk_branches[i],
                    &lk_branches[j],
                    depth_seed + 5000 + (i * lk_branches.len() + j) as u64 * 100,
                ) {
                    let m = &dag.nodes[&merge_id];
                    let dpi_vs_prev = m.sigma <= current_sigma + 1e-10;
                    if dpi_vs_prev && m.gap > 0.01 && m.gap > next_best_gap {
                        next_best_gap = m.gap;
                        next_best_id = Some(merge_id.clone());
                    }
                }
            }
        }

        match next_best_id {
            Some(next_id) => {
                let next = dag.nodes[&next_id].clone();
                let dpi_root = next.sigma <= root_sigma + 1e-10;
                all_dpi = all_dpi && dpi_root;
                sigma_per_level.push(next.sigma);
                n_per_level.push(next.kernel.n);
                current_id = next_id;
                depth += 1;
            }
            None => break,
        }
    }

    let terminal = dag.nodes[&current_id].clone();
    let terminal_rev = measure_reversibility(&terminal.kernel);

    CascadePathMetrics {
        path_seed,
        depth,
        l1_merge_n,
        terminal_n: terminal.kernel.n,
        terminal_sigma: terminal.sigma,
        terminal_gap: terminal.gap,
        terminal_reversibility: terminal_rev,
        sigma_per_level,
        n_per_level,
        all_dpi,
    }
}

fn run_exp_051(seed: u64, scale: usize) -> Exp051Metrics {
    let n = scale.max(8);
    let mut dag = EmergenceDag::new();
    let root_id = dag.create_root(n, seed);
    let root = dag.nodes[&root_id].clone();

    let n_paths = 10;
    let mut paths: Vec<CascadePathMetrics> = Vec::new();

    for p in 0..n_paths {
        // Each path uses a different base seed for branching
        let path_seed = seed + p as u64 * 100000;
        let pm = run_one_cascade(&mut dag, &root_id, root.sigma, path_seed);
        println!(
            "  Path {}: depth={} L1_n={} terminal_n={} terminal_rev={:.6} sigma=[{}] dpi={}",
            p,
            pm.depth,
            pm.l1_merge_n,
            pm.terminal_n,
            pm.terminal_reversibility,
            pm.sigma_per_level
                .iter()
                .map(|s| format!("{:.4}", s))
                .collect::<Vec<_>>()
                .join(","),
            pm.all_dpi
        );
        paths.push(pm);
    }

    let depths: Vec<f64> = paths.iter().map(|p| p.depth as f64).collect();
    let depth_mean = depths.iter().sum::<f64>() / depths.len() as f64;
    let depth_std =
        (depths.iter().map(|d| (d - depth_mean).powi(2)).sum::<f64>() / depths.len() as f64).sqrt();
    let depth_min = paths.iter().map(|p| p.depth).min().unwrap_or(0);
    let depth_max = paths.iter().map(|p| p.depth).max().unwrap_or(0);
    let all_paths_dpi = paths.iter().all(|p| p.all_dpi);

    let mut terminal_ns: Vec<usize> = paths.iter().map(|p| p.terminal_n).collect();
    terminal_ns.sort();
    let terminal_n_values = terminal_ns
        .iter()
        .map(|n| n.to_string())
        .collect::<Vec<_>>()
        .join(",");

    let terminal_rev_mean =
        paths.iter().map(|p| p.terminal_reversibility).sum::<f64>() / n_paths as f64;

    Exp051Metrics {
        n,
        root_sigma: root.sigma,
        root_gap: root.gap,
        n_paths,
        depth_min,
        depth_max,
        depth_mean,
        depth_std,
        all_paths_dpi,
        terminal_n_values,
        terminal_reversibility_mean: terminal_rev_mean,
        paths,
    }
}

// ============================================================================
// EXP-052: Large-Scale Cascade Probe
//
// Test larger scales (512, 1024) to see if cascade depth or L1 size changes.
// Also: full structural audit at each level (reversibility, sigma decay rate).
// ============================================================================

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct AuditedLevel {
    pub merge_n: usize,
    pub merge_sigma: f64,
    pub merge_gap: f64,
    pub reversibility: f64,
    pub blocks: usize,
    pub log_sigma_ratio: f64, // log10(sigma_prev / sigma_this), 0 for L1
    pub viable: usize,
    pub dpi_vs_root: bool,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Exp052Metrics {
    pub n: usize,
    pub root_sigma: f64,
    pub root_gap: f64,
    pub root_reversibility: f64,
    pub max_depth: usize,
    pub all_dpi_vs_root: bool,
    pub l1_merge_n: usize,
    pub mean_log_sigma_ratio: f64,
    pub levels: Vec<AuditedLevel>,
}

fn run_exp_052(seed: u64, scale: usize) -> Exp052Metrics {
    use emergence_graph::composition::PStep;

    let n = scale.max(8);
    let mut dag = EmergenceDag::new();
    let root_id = dag.create_root(n, seed);
    let root = dag.nodes[&root_id].clone();
    let root_rev = measure_reversibility(&root.kernel);

    // L1: mixed palette
    let l1_compositions: Vec<PComposition> = vec![
        PComposition::p2_p4(),
        PComposition::p1sym_p2_p4(),
        PComposition::p1_p2_p4(0.3),
        PComposition::p2_p5(20),
        PComposition::p1sym_p2_p5(20),
        PComposition::p1_p2_p4(0.1),
    ];

    let mut branches: Vec<String> = Vec::new();
    for (i, comp) in l1_compositions.iter().enumerate() {
        if let Ok(id) = dag.branch(&root_id, comp, seed + (i as u64 + 1) * 1000) {
            branches.push(id);
        }
    }

    if branches.len() < 2 {
        return Exp052Metrics {
            n,
            root_sigma: root.sigma,
            root_gap: root.gap,
            root_reversibility: root_rev,
            max_depth: 0,
            all_dpi_vs_root: true,
            l1_merge_n: 0,
            mean_log_sigma_ratio: 0.0,
            levels: vec![],
        };
    }

    let mut best_id: Option<String> = None;
    let mut best_gap = 0.0f64;
    for i in 0..branches.len() {
        for j in (i + 1)..branches.len() {
            if let Ok(merge_id) = dag.merge(
                &root_id,
                &branches[i],
                &branches[j],
                seed + 5000 + (i * branches.len() + j) as u64 * 100,
            ) {
                let m = &dag.nodes[&merge_id];
                let dpi = m.sigma <= root.sigma + 1e-10;
                if dpi && m.gap > 0.01 && m.gap > best_gap {
                    best_gap = m.gap;
                    best_id = Some(merge_id);
                }
            }
        }
    }

    let l1_id = match best_id {
        Some(id) => id,
        None => {
            return Exp052Metrics {
                n,
                root_sigma: root.sigma,
                root_gap: root.gap,
                root_reversibility: root_rev,
                max_depth: 0,
                all_dpi_vs_root: true,
                l1_merge_n: 0,
                mean_log_sigma_ratio: 0.0,
                levels: vec![],
            };
        }
    };
    let l1 = dag.nodes[&l1_id].clone();
    let l1_rev = measure_reversibility(&l1.kernel);

    let log_ratio_l1 = if l1.sigma > 1e-15 {
        (root.sigma / l1.sigma).log10()
    } else {
        15.0
    };

    let mut levels: Vec<AuditedLevel> = vec![AuditedLevel {
        merge_n: l1.kernel.n,
        merge_sigma: l1.sigma,
        merge_gap: l1.gap,
        reversibility: l1_rev,
        blocks: l1.kernel.block_count(),
        log_sigma_ratio: log_ratio_l1,
        viable: branches.len(),
        dpi_vs_root: l1.sigma <= root.sigma + 1e-10,
    }];

    let mut current_id = l1_id;
    let mut depth = 1;
    let max_levels = 10;

    while depth < max_levels {
        let current_sigma = dag.nodes[&current_id].sigma;
        let current_n = dag.nodes[&current_id].kernel.n;
        if current_n <= 2 {
            break;
        }

        let lk_comps: Vec<PComposition> = vec![
            PComposition::new(vec![PStep::P2GateScaled, PStep::P4Sectors], "P2s→P4"),
            PComposition::new(
                vec![PStep::P2GateScaled, PStep::P5Package { tau: 20 }],
                "P2s→P5",
            ),
            PComposition::new(
                vec![
                    PStep::P1Perturb { strength: 1.0 },
                    PStep::P2GateScaled,
                    PStep::P4Sectors,
                ],
                "P1(1)→P2s→P4",
            ),
            PComposition::new(
                vec![
                    PStep::P1Perturb { strength: 1.0 },
                    PStep::P2GateScaled,
                    PStep::P5Package { tau: 20 },
                ],
                "P1(1)→P2s→P5",
            ),
            PComposition::new(
                vec![
                    PStep::P1Perturb { strength: 2.0 },
                    PStep::P2GateScaled,
                    PStep::P4Sectors,
                ],
                "P1(2)→P2s→P4",
            ),
            PComposition::new(
                vec![
                    PStep::P1Perturb { strength: 2.0 },
                    PStep::P2GateScaled,
                    PStep::P5Package { tau: 20 },
                ],
                "P1(2)→P2s→P5",
            ),
            PComposition::new(
                vec![
                    PStep::P1Perturb { strength: 5.0 },
                    PStep::P2GateScaled,
                    PStep::P4Sectors,
                ],
                "P1(5)→P2s→P4",
            ),
            PComposition::new(
                vec![
                    PStep::P1Perturb { strength: 5.0 },
                    PStep::P2GateScaled,
                    PStep::P5Package { tau: 20 },
                ],
                "P1(5)→P2s→P5",
            ),
        ];

        let depth_seed = seed + (depth as u64 + 1) * 10000;
        let mut lk_branches: Vec<String> = Vec::new();
        for (i, comp) in lk_comps.iter().enumerate() {
            if let Ok(id) = dag.branch(&current_id, comp, depth_seed + (i as u64 + 1) * 1000) {
                lk_branches.push(id);
            }
        }

        let viable = lk_branches.len();
        if viable < 2 {
            break;
        }

        let mut next_best_id: Option<String> = None;
        let mut next_best_gap = 0.0f64;
        for i in 0..lk_branches.len() {
            for j in (i + 1)..lk_branches.len() {
                if let Ok(merge_id) = dag.merge(
                    &current_id,
                    &lk_branches[i],
                    &lk_branches[j],
                    depth_seed + 5000 + (i * lk_branches.len() + j) as u64 * 100,
                ) {
                    let m = &dag.nodes[&merge_id];
                    let dpi_vs_prev = m.sigma <= current_sigma + 1e-10;
                    if dpi_vs_prev && m.gap > 0.01 && m.gap > next_best_gap {
                        next_best_gap = m.gap;
                        next_best_id = Some(merge_id);
                    }
                }
            }
        }

        match next_best_id {
            Some(next_id) => {
                let next = dag.nodes[&next_id].clone();
                let dpi_root = next.sigma <= root.sigma + 1e-10;
                let rev = measure_reversibility(&next.kernel);
                let log_ratio = if next.sigma > 1e-15 && current_sigma > 1e-15 {
                    (current_sigma / next.sigma).log10()
                } else {
                    15.0
                };

                levels.push(AuditedLevel {
                    merge_n: next.kernel.n,
                    merge_sigma: next.sigma,
                    merge_gap: next.gap,
                    reversibility: rev,
                    blocks: next.kernel.block_count(),
                    log_sigma_ratio: log_ratio,
                    viable,
                    dpi_vs_root: dpi_root,
                });
                current_id = next_id;
                depth += 1;
            }
            None => break,
        }
    }

    let all_dpi = levels.iter().all(|l| l.dpi_vs_root);
    let log_ratios: Vec<f64> = levels
        .iter()
        .map(|l| l.log_sigma_ratio)
        .filter(|r| *r < 14.0)
        .collect();
    let mean_log_ratio = if log_ratios.is_empty() {
        0.0
    } else {
        log_ratios.iter().sum::<f64>() / log_ratios.len() as f64
    };

    Exp052Metrics {
        n,
        root_sigma: root.sigma,
        root_gap: root.gap,
        root_reversibility: root_rev,
        max_depth: depth,
        all_dpi_vs_root: all_dpi,
        l1_merge_n: levels.first().map(|l| l.merge_n).unwrap_or(0),
        mean_log_sigma_ratio: mean_log_ratio,
        levels,
    }
}

// ============================================================================
// EXP-053: Terminal Kernel Characterization
//
// What does the 2-state terminal kernel look like? Is it universal?
// Extract (a, b) from K = [[1-a, a], [b, 1-b]] for each terminal kernel.
// ============================================================================

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct TerminalKernel {
    pub path_id: usize,
    pub depth: usize,
    pub terminal_n: usize,
    pub k01: f64, // K[0][1] = a
    pub k10: f64, // K[1][0] = b
    pub gap: f64,
    pub sigma: f64,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Exp053Metrics {
    pub n: usize,
    pub root_sigma: f64,
    pub root_gap: f64,
    pub n_paths: usize,
    pub n_terminal_2: usize,
    pub mean_k01: f64,
    pub mean_k10: f64,
    pub std_k01: f64,
    pub std_k10: f64,
    pub mean_gap: f64,
    pub mean_sum_ab: f64, // a+b = 1-lambda2 determines gap
    pub std_sum_ab: f64,
    pub terminals: Vec<TerminalKernel>,
}

fn run_exp_053(seed: u64, scale: usize) -> Exp053Metrics {
    let n = scale.max(8);
    let mut dag = EmergenceDag::new();
    let root_id = dag.create_root(n, seed);
    let root = dag.nodes[&root_id].clone();

    let n_paths = 10;
    let mut terminals: Vec<TerminalKernel> = Vec::new();

    for p in 0..n_paths {
        let path_seed = seed + p as u64 * 100000;
        let pm = run_one_cascade_with_terminal(&mut dag, &root_id, root.sigma, path_seed);
        terminals.push(pm);
    }

    let t2: Vec<&TerminalKernel> = terminals.iter().filter(|t| t.terminal_n == 2).collect();
    let n_t2 = t2.len();

    let (mean_k01, mean_k10, std_k01, std_k10, mean_gap, mean_sum, std_sum) = if n_t2 > 0 {
        let mk01 = t2.iter().map(|t| t.k01).sum::<f64>() / n_t2 as f64;
        let mk10 = t2.iter().map(|t| t.k10).sum::<f64>() / n_t2 as f64;
        let sk01 = (t2.iter().map(|t| (t.k01 - mk01).powi(2)).sum::<f64>() / n_t2 as f64).sqrt();
        let sk10 = (t2.iter().map(|t| (t.k10 - mk10).powi(2)).sum::<f64>() / n_t2 as f64).sqrt();
        let mg = t2.iter().map(|t| t.gap).sum::<f64>() / n_t2 as f64;
        let sums: Vec<f64> = t2.iter().map(|t| t.k01 + t.k10).collect();
        let ms = sums.iter().sum::<f64>() / n_t2 as f64;
        let ss = (sums.iter().map(|s| (s - ms).powi(2)).sum::<f64>() / n_t2 as f64).sqrt();
        (mk01, mk10, sk01, sk10, mg, ms, ss)
    } else {
        (0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    };

    Exp053Metrics {
        n,
        root_sigma: root.sigma,
        root_gap: root.gap,
        n_paths,
        n_terminal_2: n_t2,
        mean_k01,
        mean_k10,
        std_k01,
        std_k10,
        mean_gap,
        mean_sum_ab: mean_sum,
        std_sum_ab: std_sum,
        terminals,
    }
}

fn run_one_cascade_with_terminal(
    dag: &mut EmergenceDag,
    root_id: &str,
    root_sigma: f64,
    path_seed: u64,
) -> TerminalKernel {
    use emergence_graph::composition::PStep;

    let l1_compositions: Vec<PComposition> = vec![
        PComposition::p2_p4(),
        PComposition::p1sym_p2_p4(),
        PComposition::p1_p2_p4(0.3),
        PComposition::p2_p5(20),
        PComposition::p1sym_p2_p5(20),
        PComposition::p1_p2_p4(0.1),
    ];

    let mut branches: Vec<String> = Vec::new();
    for (i, comp) in l1_compositions.iter().enumerate() {
        if let Ok(id) = dag.branch(root_id, comp, path_seed + (i as u64 + 1) * 1000) {
            branches.push(id);
        }
    }

    if branches.len() < 2 {
        return TerminalKernel {
            path_id: 0,
            depth: 0,
            terminal_n: 0,
            k01: 0.0,
            k10: 0.0,
            gap: 0.0,
            sigma: 0.0,
        };
    }

    let mut best_id: Option<String> = None;
    let mut best_gap = 0.0f64;
    for i in 0..branches.len() {
        for j in (i + 1)..branches.len() {
            if let Ok(merge_id) = dag.merge(
                root_id,
                &branches[i],
                &branches[j],
                path_seed + 5000 + (i * branches.len() + j) as u64 * 100,
            ) {
                let m = &dag.nodes[&merge_id];
                let dpi = m.sigma <= root_sigma + 1e-10;
                if dpi && m.gap > 0.01 && m.gap > best_gap {
                    best_gap = m.gap;
                    best_id = Some(merge_id.clone());
                }
            }
        }
    }

    let l1_id = match best_id {
        Some(id) => id,
        None => {
            return TerminalKernel {
                path_id: 0,
                depth: 0,
                terminal_n: 0,
                k01: 0.0,
                k10: 0.0,
                gap: 0.0,
                sigma: 0.0,
            };
        }
    };

    let mut current_id = l1_id;
    let mut depth = 1;
    let max_levels = 10;

    while depth < max_levels {
        let current_sigma = dag.nodes[&current_id].sigma;
        let current_n = dag.nodes[&current_id].kernel.n;
        if current_n <= 2 {
            break;
        }

        let lk_comps: Vec<PComposition> = vec![
            PComposition::new(vec![PStep::P2GateScaled, PStep::P4Sectors], "P2s→P4"),
            PComposition::new(
                vec![PStep::P2GateScaled, PStep::P5Package { tau: 20 }],
                "P2s→P5",
            ),
            PComposition::new(
                vec![
                    PStep::P1Perturb { strength: 1.0 },
                    PStep::P2GateScaled,
                    PStep::P4Sectors,
                ],
                "P1(1)→P2s→P4",
            ),
            PComposition::new(
                vec![
                    PStep::P1Perturb { strength: 1.0 },
                    PStep::P2GateScaled,
                    PStep::P5Package { tau: 20 },
                ],
                "P1(1)→P2s→P5",
            ),
            PComposition::new(
                vec![
                    PStep::P1Perturb { strength: 2.0 },
                    PStep::P2GateScaled,
                    PStep::P4Sectors,
                ],
                "P1(2)→P2s→P4",
            ),
            PComposition::new(
                vec![
                    PStep::P1Perturb { strength: 2.0 },
                    PStep::P2GateScaled,
                    PStep::P5Package { tau: 20 },
                ],
                "P1(2)→P2s→P5",
            ),
            PComposition::new(
                vec![
                    PStep::P1Perturb { strength: 5.0 },
                    PStep::P2GateScaled,
                    PStep::P4Sectors,
                ],
                "P1(5)→P2s→P4",
            ),
            PComposition::new(
                vec![
                    PStep::P1Perturb { strength: 5.0 },
                    PStep::P2GateScaled,
                    PStep::P5Package { tau: 20 },
                ],
                "P1(5)→P2s→P5",
            ),
        ];

        let depth_seed = path_seed + (depth as u64 + 1) * 10000;
        let mut lk_branches: Vec<String> = Vec::new();
        for (i, comp) in lk_comps.iter().enumerate() {
            if let Ok(id) = dag.branch(&current_id, comp, depth_seed + (i as u64 + 1) * 1000) {
                lk_branches.push(id);
            }
        }

        if lk_branches.len() < 2 {
            break;
        }

        let mut next_best_id: Option<String> = None;
        let mut next_best_gap = 0.0f64;
        for i in 0..lk_branches.len() {
            for j in (i + 1)..lk_branches.len() {
                if let Ok(merge_id) = dag.merge(
                    &current_id,
                    &lk_branches[i],
                    &lk_branches[j],
                    depth_seed + 5000 + (i * lk_branches.len() + j) as u64 * 100,
                ) {
                    let m = &dag.nodes[&merge_id];
                    let dpi_vs_prev = m.sigma <= current_sigma + 1e-10;
                    if dpi_vs_prev && m.gap > 0.01 && m.gap > next_best_gap {
                        next_best_gap = m.gap;
                        next_best_id = Some(merge_id.clone());
                    }
                }
            }
        }

        match next_best_id {
            Some(next_id) => {
                current_id = next_id;
                depth += 1;
            }
            None => break,
        }
    }

    let terminal = dag.nodes[&current_id].clone();
    let tn = terminal.kernel.n;
    let (k01, k10) = if tn == 2 {
        (terminal.kernel.kernel[0][1], terminal.kernel.kernel[1][0])
    } else if tn >= 2 {
        // For n>2, report the mean off-diagonal entry
        let mut sum_off = 0.0;
        for i in 0..tn {
            for j in 0..tn {
                if i != j {
                    sum_off += terminal.kernel.kernel[i][j];
                }
            }
        }
        let avg = sum_off / (tn * (tn - 1)) as f64;
        (avg, avg)
    } else {
        (0.0, 0.0)
    };

    TerminalKernel {
        path_id: 0,
        depth,
        terminal_n: tn,
        k01,
        k10,
        gap: terminal.gap,
        sigma: terminal.sigma,
    }
}

// ============================================================================
// EXP-054: Single-Step vs Cascade Coarse-Graining
//
// Can we reach n=2 in a single step with DPI? Compare:
// 1. Parity lens (z mod 2) — single step
// 2. Random binary partition — single step
// 3. P2→P4 induced partition (if it gives 2 blocks) — single step
// 4. Full cascade to n=2
// ============================================================================

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Exp054Metrics {
    pub n: usize,
    pub root_sigma: f64,
    pub root_gap: f64,
    // Parity lens (z mod 2) direct coarse-graining
    pub parity_sigma: f64,
    pub parity_gap: f64,
    pub parity_dpi: bool,
    // Random binary partition direct coarse-graining
    pub random_bin_sigma: f64,
    pub random_bin_gap: f64,
    pub random_bin_dpi: bool,
    // P2→P4 induced partition (best 2-block from gating)
    pub p2p4_sigma: f64,
    pub p2p4_gap: f64,
    pub p2p4_dpi: bool,
    pub p2p4_found: bool,
    // Cascade endpoint
    pub cascade_sigma: f64,
    pub cascade_gap: f64,
    pub cascade_dpi: bool,
    pub cascade_depth: usize,
    // Key comparison
    pub single_step_dpi_possible: bool,
    pub cascade_needed: bool,
}

fn run_exp_054(seed: u64, scale: usize) -> Exp054Metrics {
    use six_primitives_core::primitives::p6_audit_sigma_t;
    use six_primitives_core::substrate::{Lens, MarkovKernel};

    let n = scale.max(8);
    let root = MarkovKernel::random(n, seed);
    let root_sigma = p6_audit_sigma_t(&root, 10);
    let root_gap = root.spectral_gap();

    // 1. Parity lens: z mod 2
    let parity_lens = Lens::parity(n);
    let n_traj = (n * 200).max(10000);
    let parity_macro =
        helpers::trajectory_rewrite_macro(&root, &parity_lens, 20, n_traj, seed + 100);
    let parity_sigma = p6_audit_sigma_t(&parity_macro, 10);
    let parity_gap = parity_macro.spectral_gap();
    let parity_dpi = parity_sigma <= root_sigma + 1e-10;

    // 2. Random binary partition (using deterministic hash for assignment)
    let mapping: Vec<usize> = (0..n)
        .map(|i| {
            // Simple hash: seed-dependent pseudorandom assignment
            let h = ((i as u64).wrapping_mul(2654435761).wrapping_add(seed + 200)) >> 31;
            (h % 2) as usize
        })
        .collect();
    // Ensure both classes have at least 1 member
    let has_0 = mapping.iter().any(|&x| x == 0);
    let has_1 = mapping.iter().any(|&x| x == 1);
    let mapping = if !has_0 || !has_1 {
        let mut m = mapping;
        m[0] = 0;
        m[n - 1] = 1;
        m
    } else {
        mapping
    };
    let random_lens = Lens {
        mapping,
        macro_n: 2,
    };
    let random_macro =
        helpers::trajectory_rewrite_macro(&root, &random_lens, 20, n_traj, seed + 300);
    let random_sigma = p6_audit_sigma_t(&random_macro, 10);
    let random_gap = random_macro.spectral_gap();
    let random_dpi = random_sigma <= root_sigma + 1e-10;

    // 3. P2→P4 induced partition (try to find a 2-block partition)
    let prob = helpers::scale_gating_prob(n);
    let gated = six_primitives_core::primitives::p2_random_gate(&root, prob, seed + 400);
    let blocks = gated.block_count();
    let (p2p4_sigma, p2p4_gap, p2p4_dpi, p2p4_found) = if blocks >= 2 {
        // Get block labels
        let labels = get_block_labels(&gated);
        // Reduce to 2 classes if more than 2 blocks
        let mapping: Vec<usize> = if blocks > 2 {
            labels
                .iter()
                .map(|&l| if l < blocks / 2 { 0 } else { 1 })
                .collect()
        } else {
            labels
        };
        let lens = Lens {
            mapping,
            macro_n: 2,
        };
        let macro_k = helpers::trajectory_rewrite_macro(&root, &lens, 20, n_traj, seed + 500);
        let s = p6_audit_sigma_t(&macro_k, 10);
        let g = macro_k.spectral_gap();
        (s, g, s <= root_sigma + 1e-10, true)
    } else {
        (0.0, 0.0, false, false)
    };

    // 4. Full cascade to n=2
    let mut dag = EmergenceDag::new();
    let root_id = dag.create_root(n, seed);
    let pm = run_one_cascade(&mut dag, &root_id, root_sigma, seed);
    let cascade_sigma = pm.sigma_per_level.last().copied().unwrap_or(root_sigma);
    let cascade_gap = if pm.depth > 0 {
        // Use the most coarse-grained node (smallest kernel) rather than nondeterministic HashMap iteration
        dag.nodes
            .values()
            .min_by_key(|n| n.kernel.n)
            .map(|n| n.gap)
            .unwrap_or(0.0)
    } else {
        0.0
    };
    let cascade_dpi = pm.all_dpi;

    let single_step_any_dpi = parity_dpi || random_dpi || p2p4_dpi;

    Exp054Metrics {
        n,
        root_sigma,
        root_gap,
        parity_sigma,
        parity_gap,
        parity_dpi,
        random_bin_sigma: random_sigma,
        random_bin_gap: random_gap,
        random_bin_dpi: random_dpi,
        p2p4_sigma,
        p2p4_gap,
        p2p4_dpi,
        p2p4_found,
        cascade_sigma,
        cascade_gap,
        cascade_dpi,
        cascade_depth: pm.depth,
        single_step_dpi_possible: single_step_any_dpi,
        cascade_needed: cascade_dpi && !single_step_any_dpi,
    }
}

fn get_block_labels(kernel: &six_primitives_core::substrate::MarkovKernel) -> Vec<usize> {
    let n = kernel.n;
    let mut labels = vec![0usize; n];
    let mut visited = vec![false; n];
    let mut block = 0;
    for start in 0..n {
        if visited[start] {
            continue;
        }
        let mut stack = vec![start];
        while let Some(node) = stack.pop() {
            if visited[node] {
                continue;
            }
            visited[node] = true;
            labels[node] = block;
            for j in 0..n {
                if (kernel.kernel[node][j] > 0.0 || kernel.kernel[j][node] > 0.0) && !visited[j] {
                    stack.push(j);
                }
            }
        }
        block += 1;
    }
    labels
}

// ============================================================================
// EXP-055: Joint Lens Advantage (Report Test A)
//
// Does the joint lens (product of two branch lenses) genuinely reduce RM
// vs individual lenses applied to the same ancestor?
// ============================================================================

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Exp055Metrics {
    pub n: usize,
    pub root_sigma: f64,
    pub root_gap: f64,
    // Lens A (from best branch A)
    pub lens_a_macro_n: usize,
    pub rm_a: f64,
    pub sigma_a: f64,
    pub gap_a: f64,
    // Lens B (from best branch B)
    pub lens_b_macro_n: usize,
    pub rm_b: f64,
    pub sigma_b: f64,
    pub gap_b: f64,
    // Joint lens (product of A and B)
    pub joint_macro_n: usize,
    pub rm_joint: f64,
    pub sigma_joint: f64,
    pub gap_joint: f64,
    // Key test: does joint beat individual lenses?
    pub joint_beats_a_rm: bool,
    pub joint_beats_b_rm: bool,
    pub joint_beats_both_rm: bool,
    pub rm_improvement_vs_best: f64, // (min(rm_a,rm_b) - rm_joint) / min(rm_a,rm_b)
}

fn run_exp_055(seed: u64, scale: usize) -> Exp055Metrics {
    use six_primitives_core::primitives::p6_audit_sigma_t;
    use six_primitives_core::substrate::Lens;
    use std::collections::HashMap;

    let n = scale.max(8);
    let mut dag = EmergenceDag::new();
    let root_id = dag.create_root(n, seed);
    let root = dag.nodes[&root_id].clone();
    let tau = 20;
    let n_traj = helpers::standard_n_traj(n);
    let n_rm = helpers::standard_n_rm(n);

    // Build branches using the standard L1 palette
    let l1_compositions: Vec<PComposition> = vec![
        PComposition::p2_p4(),
        PComposition::p1sym_p2_p4(),
        PComposition::p1_p2_p4(0.3),
        PComposition::p2_p5(20),
        PComposition::p1sym_p2_p5(20),
        PComposition::p1_p2_p4(0.1),
    ];

    let mut branches: Vec<String> = Vec::new();
    for (i, comp) in l1_compositions.iter().enumerate() {
        if let Ok(id) = dag.branch(&root_id, comp, seed + (i as u64 + 1) * 1000) {
            branches.push(id);
        }
    }

    if branches.len() < 2 {
        return Exp055Metrics {
            n,
            root_sigma: root.sigma,
            root_gap: root.gap,
            lens_a_macro_n: 0,
            rm_a: 0.0,
            sigma_a: 0.0,
            gap_a: 0.0,
            lens_b_macro_n: 0,
            rm_b: 0.0,
            sigma_b: 0.0,
            gap_b: 0.0,
            joint_macro_n: 0,
            rm_joint: 0.0,
            sigma_joint: 0.0,
            gap_joint: 0.0,
            joint_beats_a_rm: false,
            joint_beats_b_rm: false,
            joint_beats_both_rm: false,
            rm_improvement_vs_best: 0.0,
        };
    }

    // Find the best merge pair (max gap with DPI)
    let mut best_pair: Option<(usize, usize)> = None;
    let mut best_gap = 0.0f64;
    for i in 0..branches.len() {
        for j in (i + 1)..branches.len() {
            if let Ok(merge_id) = dag.merge(
                &root_id,
                &branches[i],
                &branches[j],
                seed + 5000 + (i * branches.len() + j) as u64 * 100,
            ) {
                let m = &dag.nodes[&merge_id];
                let dpi = m.sigma <= root.sigma + 1e-10;
                if dpi && m.gap > 0.01 && m.gap > best_gap {
                    best_gap = m.gap;
                    best_pair = Some((i, j));
                }
            }
        }
    }

    let (idx_a, idx_b) = match best_pair {
        Some(p) => p,
        None => {
            return Exp055Metrics {
                n,
                root_sigma: root.sigma,
                root_gap: root.gap,
                lens_a_macro_n: 0,
                rm_a: 0.0,
                sigma_a: 0.0,
                gap_a: 0.0,
                lens_b_macro_n: 0,
                rm_b: 0.0,
                sigma_b: 0.0,
                gap_b: 0.0,
                joint_macro_n: 0,
                rm_joint: 0.0,
                sigma_joint: 0.0,
                gap_joint: 0.0,
                joint_beats_a_rm: false,
                joint_beats_b_rm: false,
                joint_beats_both_rm: false,
                rm_improvement_vs_best: 0.0,
            };
        }
    };

    // Extract lenses from edges
    let lens_a = dag
        .edges
        .values()
        .find(|e| e.parent_id == root_id && e.child_id == branches[idx_a])
        .map(|e| e.lens.clone())
        .unwrap();
    let lens_b = dag
        .edges
        .values()
        .find(|e| e.parent_id == root_id && e.child_id == branches[idx_b])
        .map(|e| e.lens.clone())
        .unwrap();

    // Build macro kernel for lens_a alone on ancestor
    let macro_a =
        helpers::trajectory_rewrite_macro(&root.kernel, &lens_a, tau, n_traj, seed + 10000);
    let rm_a =
        helpers::mean_route_mismatch(&root.kernel, &macro_a, &lens_a, tau, n_rm, seed + 10100);
    let sigma_a = p6_audit_sigma_t(&macro_a, 10);
    let gap_a = macro_a.spectral_gap();

    // Build macro kernel for lens_b alone on ancestor
    let macro_b =
        helpers::trajectory_rewrite_macro(&root.kernel, &lens_b, tau, n_traj, seed + 10200);
    let rm_b =
        helpers::mean_route_mismatch(&root.kernel, &macro_b, &lens_b, tau, n_rm, seed + 10300);
    let sigma_b = p6_audit_sigma_t(&macro_b, 10);
    let gap_b = macro_b.spectral_gap();

    // Build joint lens
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
    let joint_lens = Lens {
        mapping: joint_mapping,
        macro_n: joint_macro_n,
    };

    // Build macro kernel for joint lens on ancestor
    let macro_joint =
        helpers::trajectory_rewrite_macro(&root.kernel, &joint_lens, tau, n_traj, seed + 10400);
    let rm_joint = helpers::mean_route_mismatch(
        &root.kernel,
        &macro_joint,
        &joint_lens,
        tau,
        n_rm,
        seed + 10500,
    );
    let sigma_joint = p6_audit_sigma_t(&macro_joint, 10);
    let gap_joint = macro_joint.spectral_gap();

    let joint_beats_a = rm_joint < rm_a;
    let joint_beats_b = rm_joint < rm_b;
    let joint_beats_both = joint_beats_a && joint_beats_b;
    let best_individual_rm = rm_a.min(rm_b);
    let rm_improvement = if best_individual_rm > 1e-15 {
        (best_individual_rm - rm_joint) / best_individual_rm
    } else {
        0.0
    };

    println!(
        "  lens_a: macro_n={} RM={:.4} sigma={:.6} gap={:.4}",
        lens_a.macro_n, rm_a, sigma_a, gap_a
    );
    println!(
        "  lens_b: macro_n={} RM={:.4} sigma={:.6} gap={:.4}",
        lens_b.macro_n, rm_b, sigma_b, gap_b
    );
    println!(
        "  joint:  macro_n={} RM={:.4} sigma={:.6} gap={:.4}",
        joint_macro_n, rm_joint, sigma_joint, gap_joint
    );
    println!(
        "  joint_beats_a={} joint_beats_b={} both={} improvement={:.1}%",
        joint_beats_a,
        joint_beats_b,
        joint_beats_both,
        rm_improvement * 100.0
    );

    Exp055Metrics {
        n,
        root_sigma: root.sigma,
        root_gap: root.gap,
        lens_a_macro_n: lens_a.macro_n,
        rm_a,
        sigma_a,
        gap_a,
        lens_b_macro_n: lens_b.macro_n,
        rm_b,
        sigma_b,
        gap_b,
        joint_macro_n,
        rm_joint,
        sigma_joint,
        gap_joint,
        joint_beats_a_rm: joint_beats_a,
        joint_beats_b_rm: joint_beats_b,
        joint_beats_both_rm: joint_beats_both,
        rm_improvement_vs_best: rm_improvement,
    }
}

// ============================================================================
// EXP-056: Slow-Mixing Substrates (Report Test B)
//
// Does the cascade behave differently on slow-mixing (pre-gated) vs
// fast-mixing (standard) roots? Protocol-compliant: P2 on random.
// ============================================================================

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Exp056Metrics {
    pub n: usize,
    // Standard root
    pub std_sigma: f64,
    pub std_gap: f64,
    pub std_depth: usize,
    pub std_l1_n: usize,
    pub std_terminal_n: usize,
    pub std_all_dpi: bool,
    // Slow root (P2-gated)
    pub slow_sigma: f64,
    pub slow_gap: f64,
    pub slow_blocks: usize,
    pub slow_depth: usize,
    pub slow_l1_n: usize,
    pub slow_terminal_n: usize,
    pub slow_all_dpi: bool,
    // Comparison
    pub gap_ratio: f64,      // slow_gap / std_gap
    pub depth_diff: i32,     // slow_depth - std_depth
    pub same_terminal: bool, // both end at n=2?
}

fn run_exp_056(seed: u64, scale: usize) -> Exp056Metrics {
    use six_primitives_core::primitives;
    use six_primitives_core::substrate::MarkovKernel;

    let n = scale.max(8);

    // 1. Standard cascade
    let mut dag_std = EmergenceDag::new();
    let root_std_id = dag_std.create_root(n, seed);
    let root_std = dag_std.nodes[&root_std_id].clone();
    let pm_std = run_one_cascade(&mut dag_std, &root_std_id, root_std.sigma, seed);

    // 2. Slow-mixing root: apply P2 gating (p=0.5) to the SAME random kernel
    let base_kernel = MarkovKernel::random(n, seed);
    let slow_kernel = primitives::p2_random_gate(&base_kernel, 0.5, seed + 777);

    let mut dag_slow = EmergenceDag::new();
    let root_slow_id = dag_slow.create_root_from_kernel(slow_kernel);
    let root_slow = dag_slow.nodes[&root_slow_id].clone();

    println!(
        "  Standard root: sigma={:.4} gap={:.4}",
        root_std.sigma, root_std.gap
    );
    println!(
        "  Slow root:     sigma={:.4} gap={:.4} blocks={}",
        root_slow.sigma, root_slow.gap, root_slow.blocks
    );

    // Only run cascade on slow root if it's connected (blocks=1)
    let (slow_depth, slow_l1_n, slow_terminal_n, slow_all_dpi) = if root_slow.blocks == 1 {
        let pm_slow = run_one_cascade(&mut dag_slow, &root_slow_id, root_slow.sigma, seed);
        println!(
            "  Slow cascade: depth={} L1_n={} terminal_n={}",
            pm_slow.depth, pm_slow.l1_merge_n, pm_slow.terminal_n
        );
        (
            pm_slow.depth,
            pm_slow.l1_merge_n,
            pm_slow.terminal_n,
            pm_slow.all_dpi,
        )
    } else {
        // Disconnected: cascade can't start meaningfully
        println!(
            "  Slow root disconnected ({} blocks), skip cascade",
            root_slow.blocks
        );
        (0, 0, 0, true)
    };

    let gap_ratio = if root_std.gap > 1e-15 {
        root_slow.gap / root_std.gap
    } else {
        0.0
    };

    Exp056Metrics {
        n,
        std_sigma: root_std.sigma,
        std_gap: root_std.gap,
        std_depth: pm_std.depth,
        std_l1_n: pm_std.l1_merge_n,
        std_terminal_n: pm_std.terminal_n,
        std_all_dpi: pm_std.all_dpi,
        slow_sigma: root_slow.sigma,
        slow_gap: root_slow.gap,
        slow_blocks: root_slow.blocks,
        slow_depth: slow_depth,
        slow_l1_n: slow_l1_n,
        slow_terminal_n: slow_terminal_n,
        slow_all_dpi: slow_all_dpi,
        gap_ratio,
        depth_diff: slow_depth as i32 - pm_std.depth as i32,
        same_terminal: pm_std.terminal_n == slow_terminal_n && pm_std.terminal_n > 0,
    }
}

// ============================================================================
// EXP-057: Alternative Selection — Min-RM (Report Test C)
//
// Does changing the merge selection criterion from max-gap to min-RM
// produce different cascade structure?
// ============================================================================

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Exp057Metrics {
    pub n: usize,
    pub root_sigma: f64,
    pub root_gap: f64,
    // Max-gap cascade (standard)
    pub maxgap_depth: usize,
    pub maxgap_l1_n: usize,
    pub maxgap_terminal_n: usize,
    pub maxgap_all_dpi: bool,
    pub maxgap_sigma_levels: Vec<f64>,
    pub maxgap_n_levels: Vec<usize>,
    // Min-RM cascade
    pub minrm_depth: usize,
    pub minrm_l1_n: usize,
    pub minrm_terminal_n: usize,
    pub minrm_all_dpi: bool,
    pub minrm_sigma_levels: Vec<f64>,
    pub minrm_n_levels: Vec<usize>,
    // Comparison
    pub depth_diff: i32,
    pub same_depth: bool,
    pub same_terminal: bool,
}

/// Cascade variant that selects merges by minimum RM instead of maximum gap.
fn run_one_cascade_minrm(
    dag: &mut EmergenceDag,
    root_id: &str,
    root_sigma: f64,
    path_seed: u64,
) -> CascadePathMetrics {
    use emergence_graph::composition::PStep;

    // L1: mixed palette (same as standard)
    let l1_compositions: Vec<PComposition> = vec![
        PComposition::p2_p4(),
        PComposition::p1sym_p2_p4(),
        PComposition::p1_p2_p4(0.3),
        PComposition::p2_p5(20),
        PComposition::p1sym_p2_p5(20),
        PComposition::p1_p2_p4(0.1),
    ];

    let mut branches: Vec<String> = Vec::new();
    for (i, comp) in l1_compositions.iter().enumerate() {
        if let Ok(id) = dag.branch(root_id, comp, path_seed + (i as u64 + 1) * 1000) {
            branches.push(id);
        }
    }

    if branches.len() < 2 {
        return CascadePathMetrics {
            path_seed,
            depth: 0,
            l1_merge_n: 0,
            terminal_n: 0,
            terminal_sigma: 0.0,
            terminal_gap: 0.0,
            terminal_reversibility: 0.0,
            sigma_per_level: vec![],
            n_per_level: vec![],
            all_dpi: true,
        };
    }

    // Find best L1 merge by MIN RM (instead of max gap)
    let mut best_id: Option<String> = None;
    let mut best_rm = f64::MAX;
    for i in 0..branches.len() {
        for j in (i + 1)..branches.len() {
            if let Ok(merge_id) = dag.merge(
                root_id,
                &branches[i],
                &branches[j],
                path_seed + 5000 + (i * branches.len() + j) as u64 * 100,
            ) {
                let m = &dag.nodes[&merge_id];
                let dpi = m.sigma <= root_sigma + 1e-10;
                // Get RM from the merge edge
                let rm = dag
                    .edges
                    .values()
                    .find(|e| e.child_id == merge_id)
                    .map(|e| e.rm)
                    .unwrap_or(f64::MAX);
                if dpi && m.gap > 0.01 && rm < best_rm {
                    best_rm = rm;
                    best_id = Some(merge_id.clone());
                }
            }
        }
    }

    let l1_id = match best_id {
        Some(id) => id,
        None => {
            return CascadePathMetrics {
                path_seed,
                depth: 0,
                l1_merge_n: 0,
                terminal_n: 0,
                terminal_sigma: 0.0,
                terminal_gap: 0.0,
                terminal_reversibility: 0.0,
                sigma_per_level: vec![],
                n_per_level: vec![],
                all_dpi: true,
            };
        }
    };
    let l1 = dag.nodes[&l1_id].clone();
    let l1_merge_n = l1.kernel.n;

    let mut sigma_per_level = vec![l1.sigma];
    let mut n_per_level = vec![l1.kernel.n];
    let mut all_dpi = l1.sigma <= root_sigma + 1e-10;

    let mut current_id = l1_id;
    let mut depth = 1;
    let max_levels = 10;

    while depth < max_levels {
        let current_sigma = dag.nodes[&current_id].sigma;
        let current_n = dag.nodes[&current_id].kernel.n;

        if current_n <= 2 {
            break;
        }

        let lk_comps: Vec<PComposition> = vec![
            PComposition::new(vec![PStep::P2GateScaled, PStep::P4Sectors], "P2s→P4"),
            PComposition::new(
                vec![PStep::P2GateScaled, PStep::P5Package { tau: 20 }],
                "P2s→P5",
            ),
            PComposition::new(
                vec![
                    PStep::P1Perturb { strength: 1.0 },
                    PStep::P2GateScaled,
                    PStep::P4Sectors,
                ],
                "P1(1)→P2s→P4",
            ),
            PComposition::new(
                vec![
                    PStep::P1Perturb { strength: 1.0 },
                    PStep::P2GateScaled,
                    PStep::P5Package { tau: 20 },
                ],
                "P1(1)→P2s→P5",
            ),
            PComposition::new(
                vec![
                    PStep::P1Perturb { strength: 2.0 },
                    PStep::P2GateScaled,
                    PStep::P4Sectors,
                ],
                "P1(2)→P2s→P4",
            ),
            PComposition::new(
                vec![
                    PStep::P1Perturb { strength: 2.0 },
                    PStep::P2GateScaled,
                    PStep::P5Package { tau: 20 },
                ],
                "P1(2)→P2s→P5",
            ),
            PComposition::new(
                vec![
                    PStep::P1Perturb { strength: 5.0 },
                    PStep::P2GateScaled,
                    PStep::P4Sectors,
                ],
                "P1(5)→P2s→P4",
            ),
            PComposition::new(
                vec![
                    PStep::P1Perturb { strength: 5.0 },
                    PStep::P2GateScaled,
                    PStep::P5Package { tau: 20 },
                ],
                "P1(5)→P2s→P5",
            ),
        ];

        let depth_seed = path_seed + (depth as u64 + 1) * 10000;
        let mut lk_branches: Vec<String> = Vec::new();
        for (i, comp) in lk_comps.iter().enumerate() {
            if let Ok(id) = dag.branch(&current_id, comp, depth_seed + (i as u64 + 1) * 1000) {
                lk_branches.push(id);
            }
        }

        if lk_branches.len() < 2 {
            break;
        }

        // Select by MIN RM (instead of max gap)
        let mut next_best_id: Option<String> = None;
        let mut next_best_rm = f64::MAX;
        for i in 0..lk_branches.len() {
            for j in (i + 1)..lk_branches.len() {
                if let Ok(merge_id) = dag.merge(
                    &current_id,
                    &lk_branches[i],
                    &lk_branches[j],
                    depth_seed + 5000 + (i * lk_branches.len() + j) as u64 * 100,
                ) {
                    let m = &dag.nodes[&merge_id];
                    let dpi_vs_prev = m.sigma <= current_sigma + 1e-10;
                    let rm = dag
                        .edges
                        .values()
                        .find(|e| e.child_id == merge_id)
                        .map(|e| e.rm)
                        .unwrap_or(f64::MAX);
                    if dpi_vs_prev && m.gap > 0.01 && rm < next_best_rm {
                        next_best_rm = rm;
                        next_best_id = Some(merge_id.clone());
                    }
                }
            }
        }

        match next_best_id {
            Some(next_id) => {
                let next = dag.nodes[&next_id].clone();
                let dpi_root = next.sigma <= root_sigma + 1e-10;
                all_dpi = all_dpi && dpi_root;
                sigma_per_level.push(next.sigma);
                n_per_level.push(next.kernel.n);
                current_id = next_id;
                depth += 1;
            }
            None => break,
        }
    }

    let terminal = dag.nodes[&current_id].clone();
    let terminal_rev = measure_reversibility(&terminal.kernel);

    CascadePathMetrics {
        path_seed,
        depth,
        l1_merge_n,
        terminal_n: terminal.kernel.n,
        terminal_sigma: terminal.sigma,
        terminal_gap: terminal.gap,
        terminal_reversibility: terminal_rev,
        sigma_per_level,
        n_per_level,
        all_dpi,
    }
}

fn run_exp_057(seed: u64, scale: usize) -> Exp057Metrics {
    let n = scale.max(8);

    // Standard max-gap cascade
    let mut dag_maxgap = EmergenceDag::new();
    let root_maxgap_id = dag_maxgap.create_root(n, seed);
    let root = dag_maxgap.nodes[&root_maxgap_id].clone();
    let pm_maxgap = run_one_cascade(&mut dag_maxgap, &root_maxgap_id, root.sigma, seed);

    println!(
        "  max-gap: depth={} L1_n={} terminal_n={} sigma=[{}]",
        pm_maxgap.depth,
        pm_maxgap.l1_merge_n,
        pm_maxgap.terminal_n,
        pm_maxgap
            .sigma_per_level
            .iter()
            .map(|s| format!("{:.4}", s))
            .collect::<Vec<_>>()
            .join(",")
    );

    // Min-RM cascade (same root seed, so same random kernel)
    let mut dag_minrm = EmergenceDag::new();
    let root_minrm_id = dag_minrm.create_root(n, seed);
    let root_minrm = dag_minrm.nodes[&root_minrm_id].clone();
    let pm_minrm = run_one_cascade_minrm(&mut dag_minrm, &root_minrm_id, root_minrm.sigma, seed);

    println!(
        "  min-RM:  depth={} L1_n={} terminal_n={} sigma=[{}]",
        pm_minrm.depth,
        pm_minrm.l1_merge_n,
        pm_minrm.terminal_n,
        pm_minrm
            .sigma_per_level
            .iter()
            .map(|s| format!("{:.4}", s))
            .collect::<Vec<_>>()
            .join(",")
    );

    Exp057Metrics {
        n,
        root_sigma: root.sigma,
        root_gap: root.gap,
        maxgap_depth: pm_maxgap.depth,
        maxgap_l1_n: pm_maxgap.l1_merge_n,
        maxgap_terminal_n: pm_maxgap.terminal_n,
        maxgap_all_dpi: pm_maxgap.all_dpi,
        maxgap_sigma_levels: pm_maxgap.sigma_per_level.clone(),
        maxgap_n_levels: pm_maxgap.n_per_level.clone(),
        minrm_depth: pm_minrm.depth,
        minrm_l1_n: pm_minrm.l1_merge_n,
        minrm_terminal_n: pm_minrm.terminal_n,
        minrm_all_dpi: pm_minrm.all_dpi,
        minrm_sigma_levels: pm_minrm.sigma_per_level.clone(),
        minrm_n_levels: pm_minrm.n_per_level.clone(),
        depth_diff: pm_minrm.depth as i32 - pm_maxgap.depth as i32,
        same_depth: pm_minrm.depth == pm_maxgap.depth,
        same_terminal: pm_minrm.terminal_n == pm_maxgap.terminal_n && pm_maxgap.terminal_n > 0,
    }
}

// ============================================================================
// EXP-058: Random Binary Partition Null Baseline (Report Test D*)
//
// Do P-composition-derived partitions matter, or does any iterative
// random binary coarse-graining also produce a cascade?
// ============================================================================

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Exp058Metrics {
    pub n: usize,
    pub root_sigma: f64,
    pub root_gap: f64,
    // P-composition cascade (standard)
    pub pcomp_depth: usize,
    pub pcomp_l1_n: usize,
    pub pcomp_terminal_n: usize,
    pub pcomp_all_dpi: bool,
    pub pcomp_sigma_levels: Vec<f64>,
    // Random partition cascade
    pub random_depth: usize,
    pub random_l1_n: usize,
    pub random_terminal_n: usize,
    pub random_all_dpi: bool,
    pub random_sigma_levels: Vec<f64>,
    pub random_attempts: usize,  // how many random merges were tried total
    pub random_successes: usize, // how many passed DPI+gap
    // Comparison
    pub depth_diff: i32,
    pub random_shorter: bool,    // random cascade shallower?
    pub random_fails_more: bool, // random has lower success rate?
}

fn run_exp_058(seed: u64, scale: usize) -> Exp058Metrics {
    use six_primitives_core::primitives::p6_audit_sigma_t;
    use six_primitives_core::substrate::{Lens, MarkovKernel};
    use std::collections::HashMap;

    let n = scale.max(8);

    // 1. Standard P-composition cascade
    let mut dag_std = EmergenceDag::new();
    let root_std_id = dag_std.create_root(n, seed);
    let root = dag_std.nodes[&root_std_id].clone();
    let pm_std = run_one_cascade(&mut dag_std, &root_std_id, root.sigma, seed);

    println!(
        "  P-comp:  depth={} L1_n={} terminal_n={}",
        pm_std.depth, pm_std.l1_merge_n, pm_std.terminal_n
    );

    // 2. Random binary partition cascade (inline, no DAG)
    let base_kernel = MarkovKernel::random(n, seed);
    let tau = 20;
    let mut current_kernel = base_kernel;
    let mut current_sigma = root.sigma;
    let mut random_sigma_levels: Vec<f64> = Vec::new();
    let mut random_depth = 0;
    let mut random_all_dpi = true;
    let mut total_attempts = 0usize;
    let mut total_successes = 0usize;
    let max_levels = 10;

    while random_depth < max_levels && current_kernel.n > 2 {
        let cur_n = current_kernel.n;
        let n_traj = helpers::standard_n_traj(cur_n);

        // Generate multiple random binary lenses and try their joints
        let mut best_merge_kernel: Option<MarkovKernel> = None;
        let mut best_merge_sigma = f64::MAX;
        let mut best_merge_gap = 0.0f64;
        let n_random_pairs = 10; // Try 10 random pairs

        for pair in 0..n_random_pairs {
            let pair_seed = seed + (random_depth as u64 + 1) * 10000 + pair as u64 * 1000;

            // Random binary lens A
            let mapping_a: Vec<usize> = (0..cur_n)
                .map(|i| {
                    let h = ((i as u64)
                        .wrapping_mul(2654435761)
                        .wrapping_add(pair_seed + 100))
                        >> 31;
                    (h % 2) as usize
                })
                .collect();
            // Ensure both classes populated
            let has_0a = mapping_a.iter().any(|&x| x == 0);
            let has_1a = mapping_a.iter().any(|&x| x == 1);
            let mapping_a = if !has_0a || !has_1a {
                let mut m = mapping_a;
                m[0] = 0;
                m[cur_n - 1] = 1;
                m
            } else {
                mapping_a
            };

            // Random binary lens B (different seed)
            let mapping_b: Vec<usize> = (0..cur_n)
                .map(|i| {
                    let h = ((i as u64)
                        .wrapping_mul(2654435761)
                        .wrapping_add(pair_seed + 200))
                        >> 31;
                    (h % 2) as usize
                })
                .collect();
            let has_0b = mapping_b.iter().any(|&x| x == 0);
            let has_1b = mapping_b.iter().any(|&x| x == 1);
            let mapping_b = if !has_0b || !has_1b {
                let mut m = mapping_b;
                m[0] = 0;
                m[cur_n - 1] = 1;
                m
            } else {
                mapping_b
            };

            // Build joint lens
            let mut pair_to_index: HashMap<(usize, usize), usize> = HashMap::new();
            let mut joint_mapping = vec![0usize; cur_n];
            for i in 0..cur_n {
                let a = mapping_a[i];
                let b = mapping_b[i];
                let pair_key = (a, b);
                let next_idx = pair_to_index.len();
                let idx = *pair_to_index.entry(pair_key).or_insert(next_idx);
                joint_mapping[i] = idx;
            }
            let joint_n = pair_to_index.len();
            if joint_n <= 1 || joint_n >= cur_n {
                continue;
            } // trivial or no compression

            let joint_lens = Lens {
                mapping: joint_mapping,
                macro_n: joint_n,
            };

            let macro_k = helpers::trajectory_rewrite_macro(
                &current_kernel,
                &joint_lens,
                tau,
                n_traj,
                pair_seed + 300,
            );
            let macro_sigma = p6_audit_sigma_t(&macro_k, 10);
            let macro_gap = macro_k.spectral_gap();

            total_attempts += 1;
            let dpi = macro_sigma <= current_sigma + 1e-10;
            if dpi && macro_gap > 0.01 {
                total_successes += 1;
                // Select by max gap (same as standard for fair comparison)
                if macro_gap > best_merge_gap {
                    best_merge_gap = macro_gap;
                    best_merge_sigma = macro_sigma;
                    best_merge_kernel = Some(macro_k);
                }
            }
        }

        match best_merge_kernel {
            Some(mk) => {
                let dpi_root = best_merge_sigma <= root.sigma + 1e-10;
                random_all_dpi = random_all_dpi && dpi_root;
                random_sigma_levels.push(best_merge_sigma);
                current_sigma = best_merge_sigma;
                current_kernel = mk;
                random_depth += 1;
                println!(
                    "  Random L{}: n={} sigma={:.6} gap={:.4}",
                    random_depth, current_kernel.n, best_merge_sigma, best_merge_gap
                );
            }
            None => {
                println!(
                    "  Random cascade terminated at depth {}: no viable merge",
                    random_depth
                );
                break;
            }
        }
    }

    let random_l1_n = if random_depth > 0 {
        current_kernel.n
    } else {
        0
    };
    // For L1 size, look at first level
    let random_l1_n_actual = if !random_sigma_levels.is_empty() {
        random_l1_n
    } else {
        0
    };

    Exp058Metrics {
        n,
        root_sigma: root.sigma,
        root_gap: root.gap,
        pcomp_depth: pm_std.depth,
        pcomp_l1_n: pm_std.l1_merge_n,
        pcomp_terminal_n: pm_std.terminal_n,
        pcomp_all_dpi: pm_std.all_dpi,
        pcomp_sigma_levels: pm_std.sigma_per_level.clone(),
        random_depth,
        random_l1_n: random_l1_n_actual,
        random_terminal_n: current_kernel.n,
        random_all_dpi,
        random_sigma_levels,
        random_attempts: total_attempts,
        random_successes: total_successes,
        depth_diff: random_depth as i32 - pm_std.depth as i32,
        random_shorter: random_depth < pm_std.depth,
        random_fails_more: total_successes < total_attempts / 2,
    }
}

// ── EXP-059: Multi-Audit Cascade Probe ─────────────────────────────

#[derive(Clone, Debug, Serialize, Deserialize)]
struct LevelAudit {
    level: usize,
    n: usize,
    sigma: f64,
    gap: f64,
    blocks: usize,
    // Chirality
    acc_max: f64,
    mean_acc_2cycle: f64,
    // Metric
    diameter: f64,
    mean_dist: f64,
    dim_estimate: f64,
    // Parts
    cross_group_flux: f64,
    // Slow mode
    second_eval: f64,
    locality_score: f64,
    eigvec_range: f64,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
struct Exp059Metrics {
    n: usize,
    root_sigma: f64,
    root_gap: f64,
    depth: usize,
    all_dpi: bool,
    level_audits: Vec<LevelAudit>,
    acc_max_monotone_decay: bool,
    diameter_monotone_decay: bool,
    locality_monotone_improve: bool,
    cross_flux_monotone_decay: bool,
}

fn audit_kernel_full(
    kernel: &six_primitives_core::substrate::MarkovKernel,
    level: usize,
) -> LevelAudit {
    use six_primitives_core::primitives::{p6_audit_acc_max, p6_audit_sigma_t};

    let n = kernel.n;
    let sigma = p6_audit_sigma_t(kernel, 10);
    let blocks = kernel.block_count();

    // ── Chirality: acc_max and mean 2-cycle affinity ──
    let acc_max = if n <= 128 {
        p6_audit_acc_max(kernel, 3)
    } else {
        p6_audit_acc_max(kernel, 2)
    };

    let pi = kernel.stationary(10000, 1e-12);
    let mut sum_weighted_acc = 0.0;
    let mut sum_weight = 0.0;
    for i in 0..n {
        for j in (i + 1)..n {
            let p_ij = kernel.kernel[i][j];
            let p_ji = kernel.kernel[j][i];
            if p_ij > 1e-15 && p_ji > 1e-15 {
                let acc = (p_ij / p_ji).ln().abs();
                let w = pi[i] * p_ij + pi[j] * p_ji;
                sum_weighted_acc += acc * w;
                sum_weight += w;
            }
        }
    }
    let mean_acc_2cycle = if sum_weight > 1e-15 {
        sum_weighted_acc / sum_weight
    } else {
        0.0
    };

    // ── Metric: Floyd-Warshall on -log(K_ij) ──
    let cap = 100.0_f64;
    let mut dist = vec![vec![cap; n]; n];
    for i in 0..n {
        dist[i][i] = 0.0;
        for j in 0..n {
            if i != j && kernel.kernel[i][j] > 1e-15 {
                dist[i][j] = -(kernel.kernel[i][j].ln());
            }
        }
    }
    for k in 0..n {
        for i in 0..n {
            for j in 0..n {
                let through_k = dist[i][k] + dist[k][j];
                if through_k < dist[i][j] {
                    dist[i][j] = through_k;
                }
            }
        }
    }

    let mut diameter = 0.0_f64;
    let mut sum_dist = 0.0;
    let mut count = 0usize;
    for i in 0..n {
        for j in (i + 1)..n {
            if dist[i][j] < cap {
                diameter = diameter.max(dist[i][j]);
                sum_dist += dist[i][j];
                count += 1;
            }
        }
    }
    let mean_dist = if count > 0 {
        sum_dist / count as f64
    } else {
        0.0
    };

    // Dimension estimate: ball volume growth (only for n >= 4)
    let dim_estimate = if n >= 4 {
        // Collect all finite distances
        let mut all_dists: Vec<f64> = Vec::new();
        for i in 0..n {
            for j in (i + 1)..n {
                if dist[i][j] < cap {
                    all_dists.push(dist[i][j]);
                }
            }
        }
        all_dists.sort_by(|a, b| a.partial_cmp(b).unwrap());

        if all_dists.len() >= 3 {
            // Sample radii at quantiles
            let n_radii = 8.min(all_dists.len());
            let mut log_r = Vec::new();
            let mut log_v = Vec::new();
            for q in 1..=n_radii {
                let idx = (q * all_dists.len() / (n_radii + 1)).min(all_dists.len() - 1);
                let r = all_dists[idx];
                if r > 1e-10 {
                    // Average ball volume at radius r
                    let mut total_vol = 0.0;
                    for i in 0..n {
                        let vol: usize = (0..n).filter(|&j| dist[i][j] <= r).count();
                        total_vol += vol as f64;
                    }
                    let avg_vol = total_vol / n as f64;
                    if avg_vol > 1.0 {
                        log_r.push(r.ln());
                        log_v.push(avg_vol.ln());
                    }
                }
            }
            // Linear regression: log_v = d * log_r + c
            if log_r.len() >= 2 {
                let n_pts = log_r.len() as f64;
                let sx: f64 = log_r.iter().sum();
                let sy: f64 = log_v.iter().sum();
                let sxx: f64 = log_r.iter().map(|x| x * x).sum();
                let sxy: f64 = log_r.iter().zip(log_v.iter()).map(|(x, y)| x * y).sum();
                let denom = n_pts * sxx - sx * sx;
                if denom.abs() > 1e-15 {
                    (n_pts * sxy - sx * sy) / denom
                } else {
                    -1.0
                }
            } else {
                -1.0
            }
        } else {
            -1.0
        }
    } else {
        -1.0
    };

    // ── Slow mode: second eigenvector ──
    let (gap, eigvec) = kernel.spectral_gap_with_eigvec();
    let second_eval = 1.0 - gap; // |λ₂|

    let eigvec_min = eigvec.iter().cloned().fold(f64::INFINITY, f64::min);
    let eigvec_max = eigvec.iter().cloned().fold(f64::NEG_INFINITY, f64::max);
    let eigvec_range = eigvec_max - eigvec_min;

    // ── Parts: cross-group flux ──
    // Split by sign of second eigenvector
    let median_eigvec = {
        let mut sorted = eigvec.clone();
        sorted.sort_by(|a, b| a.partial_cmp(b).unwrap());
        sorted[n / 2]
    };
    let mut cross_flux = 0.0;
    for i in 0..n {
        for j in 0..n {
            if i != j {
                let i_group = eigvec[i] >= median_eigvec;
                let j_group = eigvec[j] >= median_eigvec;
                if i_group != j_group {
                    cross_flux += pi[i] * kernel.kernel[i][j];
                }
            }
        }
    }

    // ── Slow mode: locality score ──
    // Sort states by eigenvector value, measure fraction of transitions to neighbors
    let mut sorted_indices: Vec<usize> = (0..n).collect();
    sorted_indices.sort_by(|&a, &b| eigvec[a].partial_cmp(&eigvec[b]).unwrap());
    // Build rank map: rank[state] = position in sorted order
    let mut rank = vec![0usize; n];
    for (r, &state) in sorted_indices.iter().enumerate() {
        rank[state] = r;
    }

    let mut locality_sum = 0.0;
    for i in 0..n {
        let ri = rank[i] as i64;
        let mut total_to_neighbors = 0.0;
        let mut total_out = 0.0;
        for j in 0..n {
            if i != j {
                total_out += kernel.kernel[i][j];
                let rj = rank[j] as i64;
                if (ri - rj).abs() <= 2 {
                    total_to_neighbors += kernel.kernel[i][j];
                }
            }
        }
        if total_out > 1e-15 {
            locality_sum += total_to_neighbors / total_out;
        }
    }
    let locality_score = locality_sum / n as f64;

    LevelAudit {
        level,
        n,
        sigma,
        gap,
        blocks,
        acc_max,
        mean_acc_2cycle,
        diameter,
        mean_dist,
        dim_estimate,
        cross_group_flux: cross_flux,
        second_eval,
        locality_score,
        eigvec_range,
    }
}

fn run_exp_059(seed: u64, scale: usize) -> Exp059Metrics {
    use emergence_graph::composition::PStep;

    let n = scale.max(8);
    let mut dag = EmergenceDag::new();
    let root_id = dag.create_root(n, seed);
    let root = dag.nodes[&root_id].clone();
    let root_sigma = root.sigma;
    let root_gap = root.gap;

    // Audit the root itself
    let root_audit = audit_kernel_full(&root.kernel, 0);

    // L1: mixed palette (same as run_one_cascade)
    let l1_compositions: Vec<PComposition> = vec![
        PComposition::p2_p4(),
        PComposition::p1sym_p2_p4(),
        PComposition::p1_p2_p4(0.3),
        PComposition::p2_p5(20),
        PComposition::p1sym_p2_p5(20),
        PComposition::p1_p2_p4(0.1),
    ];

    let path_seed = seed;
    let mut branches: Vec<String> = Vec::new();
    for (i, comp) in l1_compositions.iter().enumerate() {
        if let Ok(id) = dag.branch(&root_id, comp, path_seed + (i as u64 + 1) * 1000) {
            branches.push(id);
        }
    }

    if branches.len() < 2 {
        return Exp059Metrics {
            n,
            root_sigma,
            root_gap,
            depth: 0,
            all_dpi: true,
            level_audits: vec![root_audit],
            acc_max_monotone_decay: true,
            diameter_monotone_decay: true,
            locality_monotone_improve: true,
            cross_flux_monotone_decay: true,
        };
    }

    // Find best L1 merge
    let mut best_id: Option<String> = None;
    let mut best_gap = 0.0f64;
    for i in 0..branches.len() {
        for j in (i + 1)..branches.len() {
            if let Ok(merge_id) = dag.merge(
                &root_id,
                &branches[i],
                &branches[j],
                path_seed + 5000 + (i * branches.len() + j) as u64 * 100,
            ) {
                let m = &dag.nodes[&merge_id];
                let dpi = m.sigma <= root_sigma + 1e-10;
                if dpi && m.gap > 0.01 && m.gap > best_gap {
                    best_gap = m.gap;
                    best_id = Some(merge_id.clone());
                }
            }
        }
    }

    let l1_id = match best_id {
        Some(id) => id,
        None => {
            return Exp059Metrics {
                n,
                root_sigma,
                root_gap,
                depth: 0,
                all_dpi: true,
                level_audits: vec![root_audit],
                acc_max_monotone_decay: true,
                diameter_monotone_decay: true,
                locality_monotone_improve: true,
                cross_flux_monotone_decay: true,
            };
        }
    };
    let l1 = dag.nodes[&l1_id].clone();

    let mut level_audits = vec![root_audit];
    level_audits.push(audit_kernel_full(&l1.kernel, 1));

    let mut all_dpi = l1.sigma <= root_sigma + 1e-10;
    let mut current_id = l1_id;
    let mut depth = 1;
    let max_levels = 10;

    while depth < max_levels {
        let current_sigma = dag.nodes[&current_id].sigma;
        let current_n = dag.nodes[&current_id].kernel.n;
        if current_n <= 2 {
            break;
        }

        let lk_comps: Vec<PComposition> = vec![
            PComposition::new(vec![PStep::P2GateScaled, PStep::P4Sectors], "P2s→P4"),
            PComposition::new(
                vec![PStep::P2GateScaled, PStep::P5Package { tau: 20 }],
                "P2s→P5",
            ),
            PComposition::new(
                vec![
                    PStep::P1Perturb { strength: 1.0 },
                    PStep::P2GateScaled,
                    PStep::P4Sectors,
                ],
                "P1(1)→P2s→P4",
            ),
            PComposition::new(
                vec![
                    PStep::P1Perturb { strength: 1.0 },
                    PStep::P2GateScaled,
                    PStep::P5Package { tau: 20 },
                ],
                "P1(1)→P2s→P5",
            ),
            PComposition::new(
                vec![
                    PStep::P1Perturb { strength: 2.0 },
                    PStep::P2GateScaled,
                    PStep::P4Sectors,
                ],
                "P1(2)→P2s→P4",
            ),
            PComposition::new(
                vec![
                    PStep::P1Perturb { strength: 2.0 },
                    PStep::P2GateScaled,
                    PStep::P5Package { tau: 20 },
                ],
                "P1(2)→P2s→P5",
            ),
            PComposition::new(
                vec![
                    PStep::P1Perturb { strength: 5.0 },
                    PStep::P2GateScaled,
                    PStep::P4Sectors,
                ],
                "P1(5)→P2s→P4",
            ),
            PComposition::new(
                vec![
                    PStep::P1Perturb { strength: 5.0 },
                    PStep::P2GateScaled,
                    PStep::P5Package { tau: 20 },
                ],
                "P1(5)→P2s→P5",
            ),
        ];

        let depth_seed = path_seed + (depth as u64 + 1) * 10000;
        let mut lk_branches: Vec<String> = Vec::new();
        for (i, comp) in lk_comps.iter().enumerate() {
            if let Ok(id) = dag.branch(&current_id, comp, depth_seed + (i as u64 + 1) * 1000) {
                lk_branches.push(id);
            }
        }

        if lk_branches.len() < 2 {
            break;
        }

        let mut next_best_id: Option<String> = None;
        let mut next_best_gap = 0.0f64;
        for i in 0..lk_branches.len() {
            for j in (i + 1)..lk_branches.len() {
                if let Ok(merge_id) = dag.merge(
                    &current_id,
                    &lk_branches[i],
                    &lk_branches[j],
                    depth_seed + 5000 + (i * lk_branches.len() + j) as u64 * 100,
                ) {
                    let m = &dag.nodes[&merge_id];
                    let dpi_vs_prev = m.sigma <= current_sigma + 1e-10;
                    if dpi_vs_prev && m.gap > 0.01 && m.gap > next_best_gap {
                        next_best_gap = m.gap;
                        next_best_id = Some(merge_id.clone());
                    }
                }
            }
        }

        match next_best_id {
            Some(next_id) => {
                let next = dag.nodes[&next_id].clone();
                let dpi_root = next.sigma <= root_sigma + 1e-10;
                all_dpi = all_dpi && dpi_root;

                level_audits.push(audit_kernel_full(&next.kernel, depth + 1));

                current_id = next_id;
                depth += 1;
            }
            None => break,
        }
    }

    // Monotonicity checks (skip root level 0, compare levels 1+)
    let merge_audits: Vec<&LevelAudit> = level_audits.iter().filter(|a| a.level >= 1).collect();
    let acc_max_monotone_decay = merge_audits
        .windows(2)
        .all(|w| w[1].acc_max <= w[0].acc_max + 1e-10);
    let diameter_monotone_decay = merge_audits
        .windows(2)
        .all(|w| w[1].diameter <= w[0].diameter + 1e-10);
    let locality_monotone_improve = merge_audits
        .windows(2)
        .all(|w| w[1].locality_score >= w[0].locality_score - 1e-10);
    let cross_flux_monotone_decay = merge_audits
        .windows(2)
        .all(|w| w[1].cross_group_flux <= w[0].cross_group_flux + 1e-10);

    Exp059Metrics {
        n,
        root_sigma,
        root_gap,
        depth,
        all_dpi,
        level_audits,
        acc_max_monotone_decay,
        diameter_monotone_decay,
        locality_monotone_improve,
        cross_flux_monotone_decay,
    }
}

// ── EXP-060: Intrinsic vs Imposed 1D Ordering ─────────────────────

/// Per-path data: eigenvector-induced ordering of root micro states at each cascade level.
#[derive(Clone, Debug)]
struct CascadePathOrdering {
    depth: usize,
    // micro_coords[level] = Vec<f64> of length n_root, one coordinate per micro state
    micro_coords: Vec<Vec<f64>>,
    // terminal_partition[z] = 0 or 1 for each root micro state (only if terminal reached)
    terminal_partition: Option<Vec<usize>>,
    l1_macro_n: usize,
}

/// Spearman rank correlation with ties (average-rank method).
fn spearman_rank_correlation(a: &[f64], b: &[f64]) -> f64 {
    assert_eq!(a.len(), b.len());
    let n = a.len();
    if n < 2 {
        return 0.0;
    }

    fn to_ranks(vals: &[f64]) -> Vec<f64> {
        let n = vals.len();
        let mut indexed: Vec<(usize, f64)> =
            vals.iter().enumerate().map(|(i, &v)| (i, v)).collect();
        indexed.sort_by(|a, b| a.1.partial_cmp(&b.1).unwrap());
        let mut ranks = vec![0.0; n];
        let mut i = 0;
        while i < n {
            let mut j = i;
            while j < n && (indexed[j].1 - indexed[i].1).abs() < 1e-15 {
                j += 1;
            }
            let avg_rank = (i + j - 1) as f64 / 2.0 + 1.0;
            for k in i..j {
                ranks[indexed[k].0] = avg_rank;
            }
            i = j;
        }
        ranks
    }

    let ra = to_ranks(a);
    let rb = to_ranks(b);
    // Pearson correlation of ranks
    let n_f = n as f64;
    let mean_a: f64 = ra.iter().sum::<f64>() / n_f;
    let mean_b: f64 = rb.iter().sum::<f64>() / n_f;
    let mut cov = 0.0;
    let mut var_a = 0.0;
    let mut var_b = 0.0;
    for i in 0..n {
        let da = ra[i] - mean_a;
        let db = rb[i] - mean_b;
        cov += da * db;
        var_a += da * da;
        var_b += db * db;
    }
    if var_a < 1e-15 || var_b < 1e-15 {
        return 0.0;
    }
    cov / (var_a.sqrt() * var_b.sqrt())
}

/// Run one cascade path, tracking lens composition and eigenvector orderings.
fn run_cascade_with_lenses(
    dag: &mut EmergenceDag,
    root_id: &str,
    root_n: usize,
    root_sigma: f64,
    path_seed: u64,
) -> Option<CascadePathOrdering> {
    use emergence_graph::composition::PStep;
    // L1 compositions
    let l1_compositions: Vec<PComposition> = vec![
        PComposition::p2_p4(),
        PComposition::p1sym_p2_p4(),
        PComposition::p1_p2_p4(0.3),
        PComposition::p2_p5(20),
        PComposition::p1sym_p2_p5(20),
        PComposition::p1_p2_p4(0.1),
    ];

    let mut branches: Vec<String> = Vec::new();
    for (i, comp) in l1_compositions.iter().enumerate() {
        if let Ok(id) = dag.branch(root_id, comp, path_seed + (i as u64 + 1) * 1000) {
            branches.push(id);
        }
    }
    if branches.len() < 2 {
        return None;
    }

    // Find best L1 merge
    let mut best_id: Option<String> = None;
    let mut best_gap = 0.0f64;
    for i in 0..branches.len() {
        for j in (i + 1)..branches.len() {
            if let Ok(merge_id) = dag.merge(
                root_id,
                &branches[i],
                &branches[j],
                path_seed + 5000 + (i * branches.len() + j) as u64 * 100,
            ) {
                let m = &dag.nodes[&merge_id];
                let dpi = m.sigma <= root_sigma + 1e-10;
                if dpi && m.gap > 0.01 && m.gap > best_gap {
                    best_gap = m.gap;
                    best_id = Some(merge_id.clone());
                }
            }
        }
    }
    let l1_id = best_id?;

    // Extract L1 lens from merge node's parent edge
    let l1_node = dag.nodes[&l1_id].clone();
    let l1_edge = dag.edges[&l1_node.parent_edges[0]].clone();
    let l1_lens = l1_edge.lens.clone();
    let l1_macro_n = l1_lens.macro_n;

    // Composed lens: root → L1 (initially just the L1 lens itself)
    let mut composed_mapping = l1_lens.mapping.clone();
    let mut _composed_macro_n = l1_lens.macro_n;

    // Compute eigenvector ordering at L1
    let (_, eigvec) = l1_node.kernel.spectral_gap_with_eigvec();
    let eigvec_normalized = {
        let mut v = eigvec.clone();
        if v.iter().sum::<f64>() < 0.0 {
            for x in &mut v {
                *x = -*x;
            }
        }
        v
    };
    let l1_micro_coords: Vec<f64> = (0..root_n)
        .map(|z| eigvec_normalized[composed_mapping[z]])
        .collect();

    let mut micro_coords = vec![l1_micro_coords];
    let mut current_id = l1_id;
    let mut depth = 1;
    let max_levels = 10;

    while depth < max_levels {
        let current_sigma = dag.nodes[&current_id].sigma;
        let current_n = dag.nodes[&current_id].kernel.n;
        if current_n <= 2 {
            break;
        }

        let lk_comps: Vec<PComposition> = vec![
            PComposition::new(vec![PStep::P2GateScaled, PStep::P4Sectors], "P2s→P4"),
            PComposition::new(
                vec![PStep::P2GateScaled, PStep::P5Package { tau: 20 }],
                "P2s→P5",
            ),
            PComposition::new(
                vec![
                    PStep::P1Perturb { strength: 1.0 },
                    PStep::P2GateScaled,
                    PStep::P4Sectors,
                ],
                "P1(1)→P2s→P4",
            ),
            PComposition::new(
                vec![
                    PStep::P1Perturb { strength: 1.0 },
                    PStep::P2GateScaled,
                    PStep::P5Package { tau: 20 },
                ],
                "P1(1)→P2s→P5",
            ),
            PComposition::new(
                vec![
                    PStep::P1Perturb { strength: 2.0 },
                    PStep::P2GateScaled,
                    PStep::P4Sectors,
                ],
                "P1(2)→P2s→P4",
            ),
            PComposition::new(
                vec![
                    PStep::P1Perturb { strength: 2.0 },
                    PStep::P2GateScaled,
                    PStep::P5Package { tau: 20 },
                ],
                "P1(2)→P2s→P5",
            ),
            PComposition::new(
                vec![
                    PStep::P1Perturb { strength: 5.0 },
                    PStep::P2GateScaled,
                    PStep::P4Sectors,
                ],
                "P1(5)→P2s→P4",
            ),
            PComposition::new(
                vec![
                    PStep::P1Perturb { strength: 5.0 },
                    PStep::P2GateScaled,
                    PStep::P5Package { tau: 20 },
                ],
                "P1(5)→P2s→P5",
            ),
        ];

        let depth_seed = path_seed + (depth as u64 + 1) * 10000;
        let mut lk_branches: Vec<String> = Vec::new();
        for (i, comp) in lk_comps.iter().enumerate() {
            if let Ok(id) = dag.branch(&current_id, comp, depth_seed + (i as u64 + 1) * 1000) {
                lk_branches.push(id);
            }
        }
        if lk_branches.len() < 2 {
            break;
        }

        let mut next_best_id: Option<String> = None;
        let mut next_best_gap = 0.0f64;
        for i in 0..lk_branches.len() {
            for j in (i + 1)..lk_branches.len() {
                if let Ok(merge_id) = dag.merge(
                    &current_id,
                    &lk_branches[i],
                    &lk_branches[j],
                    depth_seed + 5000 + (i * lk_branches.len() + j) as u64 * 100,
                ) {
                    let m = &dag.nodes[&merge_id];
                    let dpi_vs_prev = m.sigma <= current_sigma + 1e-10;
                    if dpi_vs_prev && m.gap > 0.01 && m.gap > next_best_gap {
                        next_best_gap = m.gap;
                        next_best_id = Some(merge_id.clone());
                    }
                }
            }
        }

        match next_best_id {
            Some(next_id) => {
                let next_node = dag.nodes[&next_id].clone();
                let next_edge = dag.edges[&next_node.parent_edges[0]].clone();
                let level_lens = next_edge.lens.clone();

                // Compose lens: root → this level
                let new_mapping: Vec<usize> = composed_mapping
                    .iter()
                    .map(|&mid| level_lens.mapping[mid])
                    .collect();
                composed_mapping = new_mapping;
                _composed_macro_n = level_lens.macro_n;

                // Compute eigenvector ordering
                let (_, eigvec) = next_node.kernel.spectral_gap_with_eigvec();
                let eigvec_norm = {
                    let mut v = eigvec.clone();
                    if v.iter().sum::<f64>() < 0.0 {
                        for x in &mut v {
                            *x = -*x;
                        }
                    }
                    v
                };
                let level_micro_coords: Vec<f64> = (0..root_n)
                    .map(|z| eigvec_norm[composed_mapping[z]])
                    .collect();
                micro_coords.push(level_micro_coords);

                current_id = next_id;
                depth += 1;
            }
            None => break,
        }
    }

    // Terminal partition (if n=2)
    let terminal_n = dag.nodes[&current_id].kernel.n;
    let terminal_partition = if terminal_n <= 2 {
        Some(composed_mapping.iter().map(|&x| x.min(1)).collect())
    } else {
        None
    };

    Some(CascadePathOrdering {
        depth,
        micro_coords,
        terminal_partition,
        l1_macro_n,
    })
}

#[derive(Clone, Debug, Serialize, Deserialize)]
struct Exp060Metrics {
    n: usize,
    root_sigma: f64,
    root_gap: f64,
    n_paths: usize,
    mean_l1_spearman: f64,
    min_l1_spearman: f64,
    l1_n_values: Vec<usize>,
    mean_terminal_agree: f64,
    min_terminal_agree: f64,
    n_terminal_reached: usize,
    max_common_depth: usize,
    mean_spearman_by_depth: Vec<f64>,
    n_pairs_by_depth: Vec<usize>,
}

fn run_exp_060(seed: u64, scale: usize) -> Exp060Metrics {
    let n = scale.max(8);
    let mut dag = EmergenceDag::new();
    let root_id = dag.create_root(n, seed);
    let root = dag.nodes[&root_id].clone();

    let n_cascade_paths = 10;
    let mut paths: Vec<CascadePathOrdering> = Vec::new();

    for p in 0..n_cascade_paths {
        let path_seed = seed * 1000 + p as u64;
        // Each path needs its own DAG to avoid node conflicts, but shares the same root kernel
        let mut path_dag = EmergenceDag::new();
        let path_root_id = path_dag.create_root_from_kernel(root.kernel.clone());

        if let Some(ordering) =
            run_cascade_with_lenses(&mut path_dag, &path_root_id, n, root.sigma, path_seed)
        {
            paths.push(ordering);
        }
    }

    let n_paths = paths.len();
    let l1_n_values: Vec<usize> = paths.iter().map(|p| p.l1_macro_n).collect();

    // L1 pairwise Spearman correlation
    let mut l1_spearman_values: Vec<f64> = Vec::new();
    for i in 0..n_paths {
        for j in (i + 1)..n_paths {
            if !paths[i].micro_coords.is_empty() && !paths[j].micro_coords.is_empty() {
                let rho =
                    spearman_rank_correlation(&paths[i].micro_coords[0], &paths[j].micro_coords[0]);
                l1_spearman_values.push(rho);
            }
        }
    }
    let mean_l1_spearman = if l1_spearman_values.is_empty() {
        0.0
    } else {
        l1_spearman_values.iter().sum::<f64>() / l1_spearman_values.len() as f64
    };
    let min_l1_spearman = l1_spearman_values
        .iter()
        .cloned()
        .fold(f64::INFINITY, f64::min)
        .max(-1.0);

    // Terminal partition agreement
    let terminal_paths: Vec<&Vec<usize>> = paths
        .iter()
        .filter_map(|p| p.terminal_partition.as_ref())
        .collect();
    let n_terminal_reached = terminal_paths.len();
    let mut terminal_agree_values: Vec<f64> = Vec::new();
    for i in 0..terminal_paths.len() {
        for j in (i + 1)..terminal_paths.len() {
            let agree: usize = terminal_paths[i]
                .iter()
                .zip(terminal_paths[j].iter())
                .filter(|(&a, &b)| a == b)
                .count();
            let overlap = agree.max(n - agree) as f64 / n as f64;
            terminal_agree_values.push(overlap);
        }
    }
    let mean_terminal_agree = if terminal_agree_values.is_empty() {
        0.0
    } else {
        terminal_agree_values.iter().sum::<f64>() / terminal_agree_values.len() as f64
    };
    let min_terminal_agree = terminal_agree_values
        .iter()
        .cloned()
        .fold(f64::INFINITY, f64::min)
        .max(0.0);

    // Per-depth Spearman correlation
    let max_depth = paths.iter().map(|p| p.depth).max().unwrap_or(0);
    let mut mean_spearman_by_depth = Vec::new();
    let mut n_pairs_by_depth = Vec::new();
    let mut max_common_depth = 0;
    for d in 0..max_depth {
        let mut depth_correlations: Vec<f64> = Vec::new();
        for i in 0..n_paths {
            for j in (i + 1)..n_paths {
                if paths[i].micro_coords.len() > d && paths[j].micro_coords.len() > d {
                    let rho = spearman_rank_correlation(
                        &paths[i].micro_coords[d],
                        &paths[j].micro_coords[d],
                    );
                    depth_correlations.push(rho);
                }
            }
        }
        if depth_correlations.len() >= 1 {
            max_common_depth = d + 1;
            let mean = depth_correlations.iter().sum::<f64>() / depth_correlations.len() as f64;
            mean_spearman_by_depth.push(mean);
            n_pairs_by_depth.push(depth_correlations.len());
        } else {
            mean_spearman_by_depth.push(0.0);
            n_pairs_by_depth.push(0);
        }
    }

    Exp060Metrics {
        n,
        root_sigma: root.sigma,
        root_gap: root.gap,
        n_paths,
        mean_l1_spearman,
        min_l1_spearman,
        l1_n_values,
        mean_terminal_agree,
        min_terminal_agree,
        n_terminal_reached,
        max_common_depth,
        mean_spearman_by_depth,
        n_pairs_by_depth,
    }
}

// ========== EXP-061: Fiedler Verification ==========

#[derive(Clone, Debug, Serialize, Deserialize)]
struct Exp061Metrics {
    n: usize,
    root_sigma: f64,
    root_gap: f64,
    fiedler_n_positive: usize, // how many root states have eigvec > 0
    n_paths: usize,
    n_terminal: usize,
    mean_fiedler_agree: f64, // avg agreement between Fiedler and each cascade path
    min_fiedler_agree: f64,
    max_fiedler_agree: f64,
    mean_cross_agree: f64, // avg pairwise cascade-cascade agreement (sanity)
    min_cross_agree: f64,
    fiedler_agrees: Vec<f64>, // per-path agreement with Fiedler
}

fn run_exp_061(seed: u64, scale: usize) -> Exp061Metrics {
    let n = scale.max(8);
    let mut dag = EmergenceDag::new();
    let root_id = dag.create_root(n, seed);
    let root = dag.nodes[&root_id].clone();

    // Compute Fiedler partition: sign of second eigenvector of root kernel
    let (root_gap, root_eigvec) = root.kernel.spectral_gap_with_eigvec();
    // Normalize sign: if sum < 0, flip
    let eigvec_norm: Vec<f64> = if root_eigvec.iter().sum::<f64>() < 0.0 {
        root_eigvec.iter().map(|x| -x).collect()
    } else {
        root_eigvec.clone()
    };
    // Fiedler partition: state z → 1 if eigvec[z] >= 0, else 0
    let fiedler_partition: Vec<usize> = eigvec_norm
        .iter()
        .map(|&x| if x >= 0.0 { 1 } else { 0 })
        .collect();
    let fiedler_n_positive = fiedler_partition.iter().filter(|&&x| x == 1).count();

    // Run cascade paths (same as EXP-060)
    let n_cascade_paths = 10;
    let mut terminal_partitions: Vec<Vec<usize>> = Vec::new();

    for p in 0..n_cascade_paths {
        let path_seed = seed * 1000 + p as u64;
        let mut path_dag = EmergenceDag::new();
        let path_root_id = path_dag.create_root_from_kernel(root.kernel.clone());

        if let Some(ordering) =
            run_cascade_with_lenses(&mut path_dag, &path_root_id, n, root.sigma, path_seed)
        {
            if let Some(tp) = ordering.terminal_partition {
                terminal_partitions.push(tp);
            }
        }
    }

    let n_paths = n_cascade_paths;
    let n_terminal = terminal_partitions.len();

    // Compare each cascade terminal partition with Fiedler partition
    let mut fiedler_agrees: Vec<f64> = Vec::new();
    for tp in &terminal_partitions {
        let agree: usize = tp
            .iter()
            .zip(fiedler_partition.iter())
            .filter(|(&a, &b)| a == b)
            .count();
        // Handle label-flip ambiguity
        let overlap = agree.max(n - agree) as f64 / n as f64;
        fiedler_agrees.push(overlap);
    }

    let mean_fiedler_agree = if fiedler_agrees.is_empty() {
        0.0
    } else {
        fiedler_agrees.iter().sum::<f64>() / fiedler_agrees.len() as f64
    };
    let min_fiedler_agree = fiedler_agrees
        .iter()
        .cloned()
        .fold(f64::INFINITY, f64::min)
        .max(0.0);
    let max_fiedler_agree = fiedler_agrees
        .iter()
        .cloned()
        .fold(f64::NEG_INFINITY, f64::max)
        .min(1.0);

    // Cross-path agreement (sanity check vs CLO-061)
    let mut cross_agrees: Vec<f64> = Vec::new();
    for i in 0..terminal_partitions.len() {
        for j in (i + 1)..terminal_partitions.len() {
            let agree: usize = terminal_partitions[i]
                .iter()
                .zip(terminal_partitions[j].iter())
                .filter(|(&a, &b)| a == b)
                .count();
            let overlap = agree.max(n - agree) as f64 / n as f64;
            cross_agrees.push(overlap);
        }
    }
    let mean_cross_agree = if cross_agrees.is_empty() {
        0.0
    } else {
        cross_agrees.iter().sum::<f64>() / cross_agrees.len() as f64
    };
    let min_cross_agree = cross_agrees
        .iter()
        .cloned()
        .fold(f64::INFINITY, f64::min)
        .max(0.0);

    Exp061Metrics {
        n,
        root_sigma: root.sigma,
        root_gap: root_gap,
        fiedler_n_positive,
        n_paths,
        n_terminal,
        mean_fiedler_agree,
        min_fiedler_agree,
        max_fiedler_agree,
        mean_cross_agree,
        min_cross_agree,
        fiedler_agrees,
    }
}

// ========== Shared IIT Helpers ==========

/// Compute mutual information I(X_t; X_{t+1}) for a Markov kernel.
/// MI = H(X_{t+1}) - H(X_{t+1} | X_t)
///    = -Σ_j π(j) ln(π(j)) + Σ_i π(i) Σ_j K(i,j) ln(K(i,j))
fn compute_mi(kernel: &MarkovKernel) -> f64 {
    let pi = kernel.stationary(10000, 1e-12);
    let n = kernel.n;
    // H(X_{t+1}) = -Σ_j π(j) ln(π(j))
    let h_next: f64 = pi
        .iter()
        .filter(|&&p| p > 1e-15)
        .map(|&p| -p * p.ln())
        .sum();
    // H(X_{t+1} | X_t) = -Σ_i π(i) Σ_j K(i,j) ln(K(i,j))
    let h_cond: f64 = (0..n)
        .map(|i| {
            let row_h: f64 = (0..n)
                .map(|j| {
                    let p = kernel.kernel[i][j];
                    if p > 1e-15 {
                        -p * p.ln()
                    } else {
                        0.0
                    }
                })
                .sum();
            pi[i] * row_h
        })
        .sum();
    h_next - h_cond
}

/// Diagnostic statistics for a macro kernel: π support, detailed balance residuals,
/// absorbing state detection. Used for Tickets 11/12 interpretation checks.
struct MacroDiagnostics {
    min_pi: f64,
    h_pi: f64,          // Shannon entropy of π
    max_self_loop: f64, // max_i K_{ii}
    n_absorbing: usize, // count of states with K_{ii} > 1 - 1e-10
    n_capped: usize,    // count of (i,j) pairs with K_{ij}>1e-15 and K_{ji}<=1e-15
    db_max: f64,        // max |π_i K_ij - π_j K_ji|
    db_l1: f64,         // Σ |π_i K_ij - π_j K_ji|
}

fn macro_diagnostics(kernel: &MarkovKernel) -> MacroDiagnostics {
    let n = kernel.n;
    let pi = kernel.stationary(10000, 1e-12);
    let min_pi = pi.iter().cloned().fold(f64::INFINITY, f64::min);
    let h_pi: f64 = pi
        .iter()
        .filter(|&&p| p > 1e-15)
        .map(|&p| -p * p.ln())
        .sum();
    let max_self_loop = (0..n).map(|i| kernel.kernel[i][i]).fold(0.0_f64, f64::max);
    let n_absorbing = (0..n)
        .filter(|&i| kernel.kernel[i][i] > 1.0 - 1e-10)
        .count();
    let mut n_capped = 0usize;
    let mut db_max = 0.0_f64;
    let mut db_l1 = 0.0_f64;
    for i in 0..n {
        for j in 0..n {
            if i == j {
                continue;
            }
            let p_ij = kernel.kernel[i][j];
            let p_ji = kernel.kernel[j][i];
            if p_ij > 1e-15 && p_ji <= 1e-15 {
                n_capped += 1;
            }
            let res = (pi[i] * p_ij - pi[j] * p_ji).abs();
            db_l1 += res;
            if res > db_max {
                db_max = res;
            }
        }
    }
    MacroDiagnostics {
        min_pi,
        h_pi,
        max_self_loop,
        n_absorbing,
        n_capped,
        db_max,
        db_l1,
    }
}

/// Uniform-weighted diagnostic metrics for Option B narrative.
/// These use μ_i = 1/n instead of π_i, so absorbing-state π-collapse doesn't mask structure.
struct UniformDiagnostics {
    sigma_unif: f64,    // EP with uniform weighting: Σ_{ij} (1/n) K_ij ln(K_ij/K_ji)
    mi_unif: f64,       // MI under uniform initial: H_unif(X_{t+1}) - H_unif(X_{t+1}|X_t)
    locality_unif: f64, // spectral locality with uniform weights
    db_unif_max: f64,   // max |(1/n)K_ij - (1/n)K_ji| = (1/n) max |K_ij - K_ji|
    db_unif_l1: f64,    // Σ |(1/n)K_ij - (1/n)K_ji| = (1/n) Σ |K_ij - K_ji|
    max_asym: f64,      // max_{i≠j} |K_ij - K_ji| — pure structural asymmetry
}

fn uniform_diagnostics(kernel: &MarkovKernel) -> UniformDiagnostics {
    let n = kernel.n;
    let mu = 1.0 / n as f64;

    // sigma_unif: Σ_{ij} μ_i K_ij ln(K_ij / K_ji)
    let mut sigma_unif = 0.0f64;
    for i in 0..n {
        for j in 0..n {
            let p_ij = kernel.kernel[i][j];
            let p_ji = kernel.kernel[j][i];
            if p_ij > 1e-15 && p_ji > 1e-15 {
                sigma_unif += mu * p_ij * (p_ij / p_ji).ln();
            } else if p_ij > 1e-15 && p_ji <= 1e-15 {
                sigma_unif += mu * p_ij * 30.0; // cap at ln(1e13)
            }
        }
    }

    // mi_unif: MI with uniform initial μ
    // marginal: p(j) = Σ_i μ_i K_ij = (1/n) Σ_i K_ij = column_mean[j]
    let mut col_mean = vec![0.0f64; n];
    for j in 0..n {
        for i in 0..n {
            col_mean[j] += kernel.kernel[i][j];
        }
        col_mean[j] *= mu;
    }
    let h_next: f64 = col_mean
        .iter()
        .filter(|&&p| p > 1e-15)
        .map(|&p| -p * p.ln())
        .sum();
    let h_cond: f64 = (0..n)
        .map(|i| {
            let row_h: f64 = (0..n)
                .map(|j| {
                    let p = kernel.kernel[i][j];
                    if p > 1e-15 {
                        -p * p.ln()
                    } else {
                        0.0
                    }
                })
                .sum();
            mu * row_h
        })
        .sum();
    let mi_unif = (h_next - h_cond).max(0.0);

    // locality_unif: use spectral ordering from Jacobi but weight by 1/n
    let locality_unif = spectral_locality_uniform(kernel);

    // DB residuals and max asymmetry
    let mut db_unif_max = 0.0f64;
    let mut db_sum = 0.0f64;
    let mut max_asym = 0.0f64;
    for i in 0..n {
        for j in (i + 1)..n {
            let diff = (kernel.kernel[i][j] - kernel.kernel[j][i]).abs();
            if diff > max_asym {
                max_asym = diff;
            }
            let db_res = mu * diff; // |μ K_ij - μ K_ji| = μ |K_ij - K_ji|
            db_sum += 2.0 * db_res; // symmetric: count (i,j) and (j,i)
            if db_res > db_unif_max {
                db_unif_max = db_res;
            }
        }
    }

    UniformDiagnostics {
        sigma_unif,
        mi_unif,
        locality_unif,
        db_unif_max,
        db_unif_l1: db_sum,
        max_asym,
    }
}

/// Spectral locality with uniform weights instead of π.
/// Reuses the Jacobi eigenvector ordering from spectral_locality but weights by 1/n.
fn spectral_locality_uniform(kernel: &MarkovKernel) -> f64 {
    let n = kernel.n;
    if n <= 2 {
        return 1.0;
    }
    let mu = 1.0 / n as f64;

    // Use π-based symmetric transform for eigenvector ordering (same as spectral_locality)
    let pi = kernel.stationary(10000, 1e-12);
    let mut sqrt_pi = vec![0.0; n];
    let mut inv_sqrt_pi = vec![0.0; n];
    for i in 0..n {
        sqrt_pi[i] = pi[i].sqrt();
        inv_sqrt_pi[i] = if pi[i] > 1e-30 { 1.0 / sqrt_pi[i] } else { 0.0 };
    }
    let mut s_sym = vec![vec![0.0; n]; n];
    for i in 0..n {
        for j in 0..n {
            s_sym[i][j] = (sqrt_pi[i] * kernel.kernel[i][j] * inv_sqrt_pi[j]
                + sqrt_pi[j] * kernel.kernel[j][i] * inv_sqrt_pi[i])
                * 0.5;
        }
    }
    let (_eigenvalues, eigenvectors) = six_dynamics::spectral::jacobi_eigen(&s_sym);
    if eigenvectors.len() < 2 {
        return 1.0;
    }
    let v2 = &eigenvectors[1];
    let u: Vec<f64> = (0..n).map(|i| v2[i] * inv_sqrt_pi[i]).collect();

    let mut order: Vec<usize> = (0..n).collect();
    order.sort_by(|&a, &b| u[a].partial_cmp(&u[b]).unwrap_or(std::cmp::Ordering::Equal));
    let mut inv = vec![0usize; n];
    for (pos, &s) in order.iter().enumerate() {
        inv[s] = pos;
    }

    let mut loc = 0.0;
    for i in 0..n {
        let (mut nb, mut od) = (0.0, 0.0);
        for j in 0..n {
            if i == j {
                continue;
            }
            let w = kernel.kernel[i][j];
            od += w;
            if (inv[i] as isize - inv[j] as isize).unsigned_abs() <= 1 {
                nb += w;
            }
        }
        if od > 1e-15 {
            loc += mu * nb / od;
        }
    }
    loc
}

/// Extract sub-kernel for a subset of states, renormalizing rows.
fn extract_sub_kernel(kernel: &MarkovKernel, states: &[usize]) -> MarkovKernel {
    let m = states.len();
    let mut sub = vec![vec![0.0f64; m]; m];
    for (si, &s) in states.iter().enumerate() {
        let mut row_sum = 0.0f64;
        for &t in states.iter() {
            row_sum += kernel.kernel[s][t];
        }
        if row_sum > 1e-15 {
            for (ti, &t) in states.iter().enumerate() {
                sub[si][ti] = kernel.kernel[s][t] / row_sum;
            }
        } else {
            // Absorbing: uniform within subset
            for ti in 0..m {
                sub[si][ti] = 1.0 / m as f64;
            }
        }
    }
    MarkovKernel { n: m, kernel: sub }
}

/// Compute Φ_MI for a bipartition.
/// partition[z] = true means state z is in group A, false in group B.
/// Φ = I_whole - (I_A + I_B)
fn compute_phi(kernel: &MarkovKernel, partition: &[bool]) -> f64 {
    let i_whole = compute_mi(kernel);
    let states_a: Vec<usize> = (0..kernel.n).filter(|&z| partition[z]).collect();
    let states_b: Vec<usize> = (0..kernel.n).filter(|&z| !partition[z]).collect();
    if states_a.is_empty() || states_b.is_empty() {
        return 0.0;
    }
    let sub_a = extract_sub_kernel(kernel, &states_a);
    let sub_b = extract_sub_kernel(kernel, &states_b);
    let i_a = compute_mi(&sub_a);
    let i_b = compute_mi(&sub_b);
    i_whole - (i_a + i_b) // Can be negative (parts more informative than whole)
}

/// Queyranne's algorithm to find the Minimum Information Partition (MIP).
/// Returns (phi_mip, partition) where partition[z] = true/false for the bipartition
/// that minimizes Φ.
/// Works by finding the minimum of a symmetric submodular function.
fn queyranne_mip(kernel: &MarkovKernel) -> (f64, Vec<bool>) {
    let n = kernel.n;
    if n <= 2 {
        let mut part = vec![false; n];
        part[0] = true;
        let phi = compute_phi(kernel, &part);
        return (phi, part);
    }

    // Each "super-element" is a set of original states
    let mut elements: Vec<Vec<usize>> = (0..n).map(|i| vec![i]).collect();
    let mut best_phi = f64::INFINITY;
    let mut best_cut_set: Vec<usize> = vec![0]; // which original states are in the "cut" side

    for _round in 0..(n - 1) {
        let m = elements.len();
        if m <= 1 {
            break;
        }

        // Find pendant pair using greedy max-weight ordering
        // Key function: for a subset S and element v not in S,
        //   w(S, v) = Φ(S ∪ {v}) - Φ(S)  (marginal contribution)
        // But for Queyranne's we use a simpler criterion:
        // Order elements greedily by maximum "connectivity" to accumulated set.
        // We use Φ({v}, rest) as a proxy for connectivity weight.

        let mut in_set = vec![false; m];
        // Start from element 0
        in_set[0] = true;
        let mut prev = 0usize;
        let mut curr = 0usize;

        // Compute Φ of the initial accumulated set {element 0}
        let init_states: Vec<usize> = elements[0].clone();
        let mut init_part = vec![false; n];
        for &s in &init_states {
            init_part[s] = true;
        }
        let mut phi_accumulated = compute_phi(kernel, &init_part);

        for _step in 1..m {
            // Find element not in set with maximum marginal contribution
            // key[v] = f(S ∪ {v}) - f(S) where f(S) = Φ of bipartition {S} vs {rest}
            let accumulated: Vec<usize> = (0..m)
                .filter(|&i| in_set[i])
                .flat_map(|i| elements[i].clone())
                .collect();

            let mut best_key = f64::NEG_INFINITY;
            let mut best_v = 0usize;
            let mut best_phi_expanded = phi_accumulated;
            for v in 0..m {
                if in_set[v] {
                    continue;
                }
                let mut test_set: Vec<usize> = accumulated.clone();
                test_set.extend(elements[v].iter());
                let mut part = vec![false; n];
                for &s in &test_set {
                    part[s] = true;
                }
                let phi_val = compute_phi(kernel, &part);
                // Marginal contribution: how much adding v changes the cut value
                let key = phi_val - phi_accumulated;
                if key > best_key || (key == best_key && v < best_v) {
                    best_key = key;
                    best_v = v;
                    best_phi_expanded = phi_val;
                }
            }
            prev = curr;
            curr = best_v;
            in_set[best_v] = true;
            phi_accumulated = best_phi_expanded;
        }

        // curr = t (last added), prev = s (second-to-last)
        // Record Φ({t}, rest) as candidate cut
        let mut part = vec![false; n];
        for &s in &elements[curr] {
            part[s] = true;
        }
        let phi_t = compute_phi(kernel, &part);
        if phi_t < best_phi {
            best_phi = phi_t;
            best_cut_set = elements[curr].clone();
        }

        // Merge s and t
        let merged: Vec<usize> = {
            let mut v = elements[prev].clone();
            v.extend(elements[curr].iter());
            v
        };
        // Remove curr (larger index first to avoid shift)
        let (lo, hi) = if prev < curr {
            (prev, curr)
        } else {
            (curr, prev)
        };
        elements.remove(hi);
        elements[lo] = merged;
    }

    let mut partition = vec![false; n];
    for &s in &best_cut_set {
        partition[s] = true;
    }
    (best_phi, partition)
}

// ========== Matrix Helpers for EXP-068 ==========

fn matrix_multiply(a: &[Vec<f64>], b: &[Vec<f64>]) -> Vec<Vec<f64>> {
    let n = a.len();
    let mut c = vec![vec![0.0f64; n]; n];
    for i in 0..n {
        for k in 0..n {
            let a_ik = a[i][k];
            if a_ik == 0.0 {
                continue;
            }
            for j in 0..n {
                c[i][j] += a_ik * b[k][j];
            }
        }
    }
    c
}

fn matrix_power(kernel: &MarkovKernel, tau: usize) -> MarkovKernel {
    let n = kernel.n;
    if tau <= 1 {
        return kernel.clone();
    }
    // Repeated squaring
    let half = matrix_power(kernel, tau / 2);
    let sq = matrix_multiply(&half.kernel, &half.kernel);
    let result = if tau % 2 == 0 {
        sq
    } else {
        matrix_multiply(&sq, &kernel.kernel)
    };
    MarkovKernel { n, kernel: result }
}

// ========== Parameterized Cascade (for EXP-069/070) ==========

struct CascadeParams {
    tau: usize,
    gate_prob_override: Option<f64>, // None = use scale_gating_prob(n)
    n_traj_mult: f64,                // multiplier on standard_n_traj
    exact: bool,                     // use exact K^tau instead of trajectory sampling
    minimize_gap: bool,              // select slow-mode-preserving merges (min gap instead of max)
}

struct ParamCascadeResult {
    depth: usize,
    terminal_n: usize,
    k01: f64,
    k10: f64,
    sum_ab: f64,
    eps: f64,
    minority_k: usize,
    eps_times_n: f64,
    fibre_sizes: Vec<Vec<usize>>, // fibre sizes per level (sorted desc)
    l1_mi: f64,                   // MI of L1 macro kernel
    l1_macro_n: usize,            // macro_n at L1
    parent_gap_before_terminal: f64, // spectral gap of parent before final step
}

/// Reindex a lens mapping so macro labels are contiguous and all used.
/// This avoids empty macro rows when some labels receive no assigned states.
fn compress_mapping(mapping: &[usize], macro_n: usize) -> (Vec<usize>, usize) {
    let mut remap = vec![usize::MAX; macro_n];
    let mut next = 0usize;
    let mut out = vec![0usize; mapping.len()];
    for (i, &m) in mapping.iter().enumerate() {
        if m >= macro_n {
            continue;
        }
        if remap[m] == usize::MAX {
            remap[m] = next;
            next += 1;
        }
        out[i] = remap[m];
    }
    (out, next)
}

/// Perform one branch step: apply P-composition to kernel, return (lens, macro_kernel, sigma, gap).
/// Replicates branch.rs logic with parameterized tau/gate_prob/n_traj.
fn param_branch(
    parent_kernel: &MarkovKernel,
    _parent_sigma: f64,
    comp_steps: &[(&str, f64)], // (step_name, param): "P1" strength, "P2" gate_prob, "P4" 0, "P5" tau
    seed: u64,
    params: &CascadeParams,
) -> Option<(six_primitives_core::substrate::Lens, MarkovKernel, f64, f64)> {
    use six_primitives_core::primitives;
    use six_primitives_core::substrate::{path_reversal_asymmetry, Lens, Substrate};

    let n = parent_kernel.n;
    let tau = params.tau;
    let n_traj = ((helpers::standard_n_traj(n) as f64) * params.n_traj_mult) as usize;
    let gate_prob = params
        .gate_prob_override
        .unwrap_or_else(|| helpers::scale_gating_prob(n));

    let mut kernel = parent_kernel.clone();
    let mut lens: Option<Lens> = None;

    for (i, (step, param)) in comp_steps.iter().enumerate() {
        match *step {
            "P1" => {
                kernel = primitives::p1_random_perturb(&kernel, *param, seed + 10 + i as u64);
            }
            "P1sym" => {
                kernel = helpers::symmetrize_kernel(&kernel);
            }
            "P2" => {
                kernel = primitives::p2_random_gate(&kernel, gate_prob, seed + 20 + i as u64);
            }
            "P4" => {
                lens = Some(helpers::sector_lens(&kernel));
            }
            "P5" => {
                let sub = Substrate::new(kernel.clone(), Lens::modular(n, n), tau);
                let fps = sub.find_fixed_points(n, 300, 1e-10, seed + 30);
                if fps.is_empty() {
                    return None;
                }
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
                let (mapping, macro_n) = compress_mapping(&mapping, fps.len());
                lens = Some(Lens { mapping, macro_n });
            }
            _ => {}
        }
    }

    let lens = lens?;
    if lens.macro_n <= 1 {
        return None;
    }

    let macro_k = if params.exact {
        let ktau = helpers::matrix_power(&kernel, tau);
        helpers::build_macro_from_ktau(&ktau.kernel, &lens.mapping, lens.macro_n)
    } else {
        helpers::trajectory_rewrite_macro(&kernel, &lens, tau, n_traj, seed + 100)
    };
    let macro_gap = macro_k.spectral_gap();
    let pi_m = macro_k.stationary(10000, 1e-12);
    let macro_sigma = path_reversal_asymmetry(&macro_k, &pi_m, 10);

    Some((lens, macro_k, macro_sigma, macro_gap))
}

/// Merge two lenses: create joint (a,b) lens, build macro kernel. Returns (joint_lens, macro_kernel, sigma, gap).
fn param_merge(
    ancestor_kernel: &MarkovKernel,
    lens_a: &six_primitives_core::substrate::Lens,
    lens_b: &six_primitives_core::substrate::Lens,
    seed: u64,
    params: &CascadeParams,
) -> Option<(six_primitives_core::substrate::Lens, MarkovKernel, f64, f64)> {
    use six_primitives_core::substrate::{path_reversal_asymmetry, Lens};
    use std::collections::HashMap;

    let n = ancestor_kernel.n;
    let tau = params.tau;
    let n_traj = ((helpers::standard_n_traj(n) as f64) * params.n_traj_mult) as usize;

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
        return None;
    }

    let joint_lens = Lens {
        mapping: joint_mapping,
        macro_n: joint_macro_n,
    };
    let macro_k = if params.exact {
        let ktau = helpers::matrix_power(ancestor_kernel, tau);
        helpers::build_macro_from_ktau(&ktau.kernel, &joint_lens.mapping, joint_macro_n)
    } else {
        helpers::trajectory_rewrite_macro(ancestor_kernel, &joint_lens, tau, n_traj, seed + 100)
    };
    let macro_gap = macro_k.spectral_gap();
    let pi_m = macro_k.stationary(10000, 1e-12);
    let macro_sigma = path_reversal_asymmetry(&macro_k, &pi_m, 10);

    Some((joint_lens, macro_k, macro_sigma, macro_gap))
}

/// Compute fibre sizes from a lens: count how many micro states map to each macro state.
fn fibre_sizes(lens: &six_primitives_core::substrate::Lens) -> Vec<usize> {
    let mut counts = vec![0usize; lens.macro_n];
    for &m in &lens.mapping {
        if m < counts.len() {
            counts[m] += 1;
        }
    }
    counts.sort_unstable_by(|a, b| b.cmp(a)); // descending
    counts
}

/// Compose two lenses: root→level_k via level_k-1→level_k lens and root→level_k-1 composed lens.
#[allow(dead_code)]
fn compose_lens(
    root_to_parent: &[usize], // root micro → parent macro index
    parent_to_child: &six_primitives_core::substrate::Lens, // parent macro → child macro index
    _n_root: usize,
) -> Vec<usize> {
    // root_to_parent maps root state → parent macro state
    // parent_to_child maps parent macro state → child macro state
    // Composed: root state → child macro state
    root_to_parent
        .iter()
        .map(|&pm| {
            if pm < parent_to_child.mapping.len() {
                parent_to_child.mapping[pm]
            } else {
                0 // fallback
            }
        })
        .collect()
}

fn run_parameterized_cascade(
    n: usize,
    seed: u64,
    path_seed: u64,
    params: &CascadeParams,
) -> ParamCascadeResult {
    let root = MarkovKernel::random(n, seed);
    let pi_root = root.stationary(10000, 1e-12);
    let root_sigma = six_primitives_core::substrate::path_reversal_asymmetry(&root, &pi_root, 10);

    // L1 composition definitions: (name, steps)
    let l1_comps: Vec<Vec<(&str, f64)>> = vec![
        vec![("P2", 0.0), ("P4", 0.0)],
        vec![("P1sym", 0.0), ("P2", 0.0), ("P4", 0.0)],
        vec![("P1", 0.3), ("P2", 0.0), ("P4", 0.0)],
        vec![("P2", 0.0), ("P5", 0.0)],
        vec![("P1sym", 0.0), ("P2", 0.0), ("P5", 0.0)],
        vec![("P1", 0.1), ("P2", 0.0), ("P4", 0.0)],
    ];

    let lk_comps: Vec<Vec<(&str, f64)>> = vec![
        vec![("P2", 0.0), ("P4", 0.0)],
        vec![("P2", 0.0), ("P5", 0.0)],
        vec![("P1", 1.0), ("P2", 0.0), ("P4", 0.0)],
        vec![("P1", 1.0), ("P2", 0.0), ("P5", 0.0)],
        vec![("P1", 2.0), ("P2", 0.0), ("P4", 0.0)],
        vec![("P1", 2.0), ("P2", 0.0), ("P5", 0.0)],
        vec![("P1", 5.0), ("P2", 0.0), ("P4", 0.0)],
        vec![("P1", 5.0), ("P2", 0.0), ("P5", 0.0)],
    ];

    let empty_result = ParamCascadeResult {
        depth: 0,
        terminal_n: 0,
        k01: 0.0,
        k10: 0.0,
        sum_ab: 0.0,
        eps: 0.0,
        minority_k: 0,
        eps_times_n: 0.0,
        fibre_sizes: vec![],
        l1_mi: 0.0,
        l1_macro_n: 0,
        parent_gap_before_terminal: 0.0,
    };

    // L1: branch
    let mut branches: Vec<(six_primitives_core::substrate::Lens, MarkovKernel, f64, f64)> =
        Vec::new();
    for (i, comp) in l1_comps.iter().enumerate() {
        if let Some(result) = param_branch(
            &root,
            root_sigma,
            comp,
            path_seed + (i as u64 + 1) * 1000,
            params,
        ) {
            branches.push(result);
        }
    }
    if branches.len() < 2 {
        return empty_result;
    }

    // L1: merge all pairs, select best (max-gap or min-gap depending on minimize_gap)
    let mut best: Option<(six_primitives_core::substrate::Lens, MarkovKernel, f64, f64)> = None;
    let mut best_gap = if params.minimize_gap {
        f64::MAX
    } else {
        0.0f64
    };
    for i in 0..branches.len() {
        for j in (i + 1)..branches.len() {
            if let Some((jl, mk, ms, mg)) = param_merge(
                &root,
                &branches[i].0,
                &branches[j].0,
                path_seed + 5000 + (i * branches.len() + j) as u64 * 100,
                params,
            ) {
                let gap_ok = if params.minimize_gap {
                    ms <= root_sigma + 1e-10 && mg > 0.01 && mg < best_gap
                } else {
                    ms <= root_sigma + 1e-10 && mg > 0.01 && mg > best_gap
                };
                if gap_ok {
                    best_gap = mg;
                    best = Some((jl, mk, ms, mg));
                }
            }
        }
    }
    let (l1_lens, l1_kernel, l1_sigma, _l1_gap) = match best {
        Some(b) => b,
        None => return empty_result,
    };

    // Compute L1 MI for memory gain analysis
    let l1_mi = compute_mi(&l1_kernel);
    let l1_macro_n = l1_kernel.n;

    // Track composed lens (root → current level)
    let mut composed_mapping: Vec<usize> = l1_lens.mapping.clone();
    let mut fibre_log: Vec<Vec<usize>> = vec![fibre_sizes(&l1_lens)];

    let mut current_kernel = l1_kernel;
    let mut current_sigma = l1_sigma;
    let mut depth = 1;
    let max_levels = 15;
    let mut last_parent_gap = current_kernel.spectral_gap();

    // L2+: iterate
    while depth < max_levels {
        let cn = current_kernel.n;
        if cn <= 2 {
            break;
        }

        let mut lk_branches: Vec<(six_primitives_core::substrate::Lens, MarkovKernel, f64, f64)> =
            Vec::new();
        let depth_seed = path_seed + (depth as u64 + 1) * 10000;
        for (i, comp) in lk_comps.iter().enumerate() {
            if let Some(result) = param_branch(
                &current_kernel,
                current_sigma,
                comp,
                depth_seed + (i as u64 + 1) * 1000,
                params,
            ) {
                lk_branches.push(result);
            }
        }
        if lk_branches.len() < 2 {
            break;
        }

        let mut next_best: Option<(six_primitives_core::substrate::Lens, MarkovKernel, f64, f64)> =
            None;
        let mut next_best_gap = if params.minimize_gap {
            f64::MAX
        } else {
            0.0f64
        };
        for i in 0..lk_branches.len() {
            for j in (i + 1)..lk_branches.len() {
                if let Some((jl, mk, ms, mg)) = param_merge(
                    &current_kernel,
                    &lk_branches[i].0,
                    &lk_branches[j].0,
                    depth_seed + 5000 + (i * lk_branches.len() + j) as u64 * 100,
                    params,
                ) {
                    let gap_ok = if params.minimize_gap {
                        ms <= current_sigma + 1e-10 && mg > 0.01 && mg < next_best_gap
                    } else {
                        ms <= current_sigma + 1e-10 && mg > 0.01 && mg > next_best_gap
                    };
                    if gap_ok {
                        next_best_gap = mg;
                        next_best = Some((jl, mk, ms, mg));
                    }
                }
            }
        }

        match next_best {
            Some((level_lens, mk, ms, _mg)) => {
                // Compose lens: root → this level
                // level_lens maps current_kernel states → new macro states
                // composed_mapping maps root states → current_kernel states
                // But wait: composed_mapping maps root → current macro index
                // and level_lens maps current macro index → next macro index
                // So we need: root state → composed_mapping[root] → level_lens.mapping[that]
                composed_mapping = composed_mapping
                    .iter()
                    .map(|&cm| {
                        if cm < level_lens.mapping.len() {
                            level_lens.mapping[cm]
                        } else {
                            0
                        }
                    })
                    .collect();

                // Record fibre sizes using the composed root→this-level lens
                let mut counts = vec![0usize; mk.n];
                for &m in &composed_mapping {
                    if m < counts.len() {
                        counts[m] += 1;
                    }
                }
                counts.sort_unstable_by(|a, b| b.cmp(a));
                fibre_log.push(counts);

                last_parent_gap = current_kernel.spectral_gap();
                current_kernel = mk;
                current_sigma = ms;
                depth += 1;
            }
            None => break,
        }
    }

    // Extract terminal info
    let tn = current_kernel.n;
    let (k01, k10) = if tn == 2 {
        (current_kernel.kernel[0][1], current_kernel.kernel[1][0])
    } else if tn > 2 {
        let eps_val = current_kernel
            .kernel
            .iter()
            .enumerate()
            .flat_map(|(i, row)| {
                row.iter()
                    .enumerate()
                    .filter(move |&(j, _)| i != j)
                    .map(|(_, &v)| v)
            })
            .fold(f64::MAX, f64::min);
        (eps_val, 1.0 - eps_val)
    } else {
        (0.0, 0.0)
    };

    let sum_ab = k01 + k10;
    let eps = k01.min(k10);

    // Compute minority fibre size k: count root states mapping to the minority macro state
    let minority_k = if tn == 2 {
        let mut count0 = 0usize;
        let mut count1 = 0usize;
        for &m in &composed_mapping {
            if m == 0 {
                count0 += 1;
            } else {
                count1 += 1;
            }
        }
        count0.min(count1)
    } else if tn > 0 {
        let mut counts = vec![0usize; tn];
        for &m in &composed_mapping {
            if m < tn {
                counts[m] += 1;
            }
        }
        *counts.iter().min().unwrap_or(&0)
    } else {
        0
    };

    let eps_times_n = eps * n as f64;

    ParamCascadeResult {
        depth,
        terminal_n: tn,
        k01,
        k10,
        sum_ab,
        eps,
        minority_k,
        eps_times_n,
        fibre_sizes: fibre_log,
        l1_mi,
        l1_macro_n,
        parent_gap_before_terminal: last_parent_gap,
    }
}

// ========== EXP-069: τ Sweep ==========

fn run_exp_069(seed: u64, scale: usize) {
    let n = scale.max(8);
    let taus = [5, 10, 20, 40, 80];

    println!("\n=== EXP-069 τ Sweep (seed={}, scale={}) ===", seed, n);

    for &tau in &taus {
        let params = CascadeParams {
            tau,
            gate_prob_override: None,
            n_traj_mult: 1.0,
            exact: false,
            minimize_gap: false,
        };
        let r = run_parameterized_cascade(n, seed, seed * 1000 + tau as u64, &params);

        println!("tau={:3}: depth={} n={} k01={:.6} k10={:.6} sum_ab={:.6} eps={:.6} eps_n={:.3} minority_k={}",
            tau, r.depth, r.terminal_n, r.k01, r.k10, r.sum_ab, r.eps, r.eps_times_n, r.minority_k);
        for (level, fibres) in r.fibre_sizes.iter().enumerate() {
            let top5: Vec<String> = fibres.iter().take(5).map(|f| f.to_string()).collect();
            println!(
                "  L{}: n_macro={} fibres=[{}{}]",
                level + 1,
                fibres.len(),
                top5.join(","),
                if fibres.len() > 5 { ",..." } else { "" }
            );
        }
        println!("KEY_TAU seed={} scale={} tau={} depth={} terminal_n={} eps={:.6} eps_n={:.4} sum_ab={:.6} minority_k={}",
            seed, n, tau, r.depth, r.terminal_n, r.eps, r.eps_times_n, r.sum_ab, r.minority_k);
    }
}

// ========== EXP-070: Gate Schedule Sweep ==========

fn run_exp_070(seed: u64, scale: usize) {
    let n = scale.max(8);
    let gate_mults = [0.5f64, 0.75, 1.0, 1.25, 1.5];
    let standard_delete_prob = helpers::scale_gating_prob(n);
    let standard_keep_per_edge = 1.0 - standard_delete_prob;

    println!(
        "\n=== EXP-070 Gate Schedule Sweep (seed={}, scale={}) ===",
        seed, n
    );
    println!(
        "Standard: delete_prob={:.4}, keep_per_edge={:.4}",
        standard_delete_prob, standard_keep_per_edge
    );

    for &gm in &gate_mults {
        // gm scales keep-per-edge; gm<1 = heavier gating, gm>1 = lighter gating.
        let adjusted_keep_per_edge = gm * standard_keep_per_edge;
        let adjusted_delete_prob = (1.0 - adjusted_keep_per_edge).max(0.01).min(0.999);
        let params = CascadeParams {
            tau: 20,
            gate_prob_override: Some(adjusted_delete_prob),
            n_traj_mult: 1.0,
            exact: false,
            minimize_gap: false,
        };
        let r = run_parameterized_cascade(n, seed, seed * 1000 + (gm * 100.0) as u64, &params);

        println!("gate_mult={:.2} keep_per_edge={:.4} delete_prob={:.4}: depth={} n={} k01={:.6} k10={:.6} eps={:.6} eps_n={:.3} minority_k={}",
            gm, adjusted_keep_per_edge, adjusted_delete_prob, r.depth, r.terminal_n, r.k01, r.k10, r.eps, r.eps_times_n, r.minority_k);
        for (level, fibres) in r.fibre_sizes.iter().enumerate() {
            let top5: Vec<String> = fibres.iter().take(5).map(|f| f.to_string()).collect();
            println!(
                "  L{}: n_macro={} fibres=[{}{}]",
                level + 1,
                fibres.len(),
                top5.join(","),
                if fibres.len() > 5 { ",..." } else { "" }
            );
        }
        println!("KEY_GATE seed={} scale={} gate_mult={:.2} keep_per_edge={:.4} delete_prob={:.4} depth={} terminal_n={} eps={:.6} eps_n={:.4} sum_ab={:.6} minority_k={}",
            seed, n, gm, adjusted_keep_per_edge, adjusted_delete_prob, r.depth, r.terminal_n, r.eps, r.eps_times_n, r.sum_ab, r.minority_k);
    }
}

// ========== EXP-071: Fine Gate Sweep + Scaling Collapse + Memory Gain ==========

fn run_exp_071(seed: u64, scale: usize) {
    let n = scale.max(8);
    let gate_mults = [
        0.3f64, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.7, 2.0,
    ];
    let standard_delete_prob = helpers::scale_gating_prob(n);
    // keep_per_edge = 1 - delete_prob (fraction of edges KEPT)
    let keep_per_edge = 1.0 - standard_delete_prob;

    println!(
        "\n=== EXP-071 Fine Gate Sweep (seed={}, scale={}) ===",
        seed, n
    );
    println!(
        "Standard: delete_prob={:.4}, keep_per_edge={:.4}",
        standard_delete_prob, keep_per_edge
    );

    for &gm in &gate_mults {
        // Adjusted delete_prob: gm multiplies the keep fraction
        let adjusted_keep_per_edge = gm * keep_per_edge;
        let adjusted_delete_prob = (1.0 - adjusted_keep_per_edge).max(0.01).min(0.999);
        // Expected kept degree: how many edges per row survive
        let d = adjusted_keep_per_edge * (n as f64 - 1.0);

        let params = CascadeParams {
            tau: 20,
            gate_prob_override: Some(adjusted_delete_prob),
            n_traj_mult: 1.0,
            exact: false,
            minimize_gap: false,
        };
        let r = run_parameterized_cascade(n, seed, seed * 1000 + (gm * 100.0) as u64, &params);

        let actual_dev = (1.0 - r.sum_ab).abs();
        let pred_dev = (1.0 - r.parent_gap_before_terminal).powi(params.tau as i32);

        println!("gm={:.2} d={:.3}: depth={} n={} eps={:.6} eps_n={:.3} k={} l1_mi={:.6} l1_n={} pgap={:.4} pred={:.8} actual={:.8}",
            gm, d, r.depth, r.terminal_n, r.eps, r.eps_times_n, r.minority_k,
            r.l1_mi, r.l1_macro_n, r.parent_gap_before_terminal, pred_dev, actual_dev);

        println!("KEY_FINE seed={} scale={} gate_mult={:.2} d={:.4} depth={} terminal_n={} eps={:.6} eps_n={:.4} sum_ab={:.6} minority_k={} l1_mi={:.6} l1_n={} parent_gap={:.6} pred_dev={:.8} actual_dev={:.8}",
            seed, n, gm, d, r.depth, r.terminal_n, r.eps, r.eps_times_n, r.sum_ab, r.minority_k,
            r.l1_mi, r.l1_macro_n, r.parent_gap_before_terminal, pred_dev, actual_dev);
    }
}

// ========== EXP-072: Exact Computation Validation ==========

fn run_exp_072(seed: u64, scale: usize) {
    let n = scale.max(8);

    println!(
        "\n=== EXP-072 Exact vs Trajectory (seed={}, scale={}) ===",
        seed, n
    );

    // Run with trajectory sampling (standard)
    let params_traj = CascadeParams {
        tau: 20,
        gate_prob_override: None,
        n_traj_mult: 1.0,
        exact: false,
        minimize_gap: false,
    };
    let r_traj = run_parameterized_cascade(n, seed, seed * 1000, &params_traj);

    // Run with exact K^tau computation
    let params_exact = CascadeParams {
        tau: 20,
        gate_prob_override: None,
        n_traj_mult: 1.0,
        exact: true,
        minimize_gap: false,
    };
    let r_exact = run_parameterized_cascade(n, seed, seed * 1000, &params_exact);

    println!(
        "TRAJ:  depth={} n={} eps={:.6} eps_n={:.3} sum_ab={:.6} k={} l1_mi={:.6}",
        r_traj.depth,
        r_traj.terminal_n,
        r_traj.eps,
        r_traj.eps_times_n,
        r_traj.sum_ab,
        r_traj.minority_k,
        r_traj.l1_mi
    );
    println!(
        "EXACT: depth={} n={} eps={:.6} eps_n={:.3} sum_ab={:.6} k={} l1_mi={:.6}",
        r_exact.depth,
        r_exact.terminal_n,
        r_exact.eps,
        r_exact.eps_times_n,
        r_exact.sum_ab,
        r_exact.minority_k,
        r_exact.l1_mi
    );

    println!("KEY_EXACT seed={} scale={} method=traj depth={} terminal_n={} eps={:.6} eps_n={:.4} sum_ab={:.6} sum_ab_hi={:.17e} minority_k={} l1_mi={:.6} l1_mi_hi={:.17e}",
        seed, n, r_traj.depth, r_traj.terminal_n, r_traj.eps, r_traj.eps_times_n, r_traj.sum_ab, r_traj.sum_ab, r_traj.minority_k, r_traj.l1_mi, r_traj.l1_mi);
    println!("KEY_EXACT seed={} scale={} method=exact depth={} terminal_n={} eps={:.6} eps_n={:.4} sum_ab={:.6} sum_ab_hi={:.17e} minority_k={} l1_mi={:.6} l1_mi_hi={:.17e}",
        seed, n, r_exact.depth, r_exact.terminal_n, r_exact.eps, r_exact.eps_times_n, r_exact.sum_ab, r_exact.sum_ab, r_exact.minority_k, r_exact.l1_mi, r_exact.l1_mi);
}

// ========== EXP-073: Tau-Scan at L1 (Phase 0 Diagnostic) ==========
//
// Run the standard L1 cascade (branch + merge) at tau=20 to find the merge lens,
// then sweep tau=1..50 through that FIXED lens to find the pre-rank-1 regime.
// P4 sectors alone give identity (disconnected components), so we need the
// merge lens which creates cross-partition flow.

fn run_exp_073(seed: u64, scale: usize) {
    use six_primitives_core::substrate::{path_reversal_asymmetry, Lens};
    let n = scale.max(8);
    let root = MarkovKernel::random(n, seed);
    let pi_root = root.stationary(10000, 1e-12);
    let root_sigma = path_reversal_asymmetry(&root, &pi_root, 10);

    println!("\n=== EXP-073 Tau-Scan (seed={}, scale={}) ===", seed, n);

    // Step 1: Find the L1 merge lens using standard cascade at tau=20
    let ref_params = CascadeParams {
        tau: 20,
        gate_prob_override: None,
        n_traj_mult: 1.0,
        exact: true,
        minimize_gap: false,
    };

    let l1_comps: Vec<Vec<(&str, f64)>> = vec![
        vec![("P2", 0.0), ("P4", 0.0)],
        vec![("P1sym", 0.0), ("P2", 0.0), ("P4", 0.0)],
        vec![("P1", 0.3), ("P2", 0.0), ("P4", 0.0)],
        vec![("P2", 0.0), ("P5", 0.0)],
        vec![("P1sym", 0.0), ("P2", 0.0), ("P5", 0.0)],
        vec![("P1", 0.1), ("P2", 0.0), ("P4", 0.0)],
    ];

    let path_seed = seed * 1000;
    let mut branches: Vec<(Lens, MarkovKernel, f64, f64)> = Vec::new();
    for (i, comp) in l1_comps.iter().enumerate() {
        if let Some(result) = param_branch(
            &root,
            root_sigma,
            comp,
            path_seed + (i as u64 + 1) * 1000,
            &ref_params,
        ) {
            branches.push(result);
        }
    }

    if branches.len() < 2 {
        println!("SKIP: only {} viable branches at L1", branches.len());
        for tau in 1..=50 {
            println!("KEY_TAUSCAN seed={} scale={} tau={} frob=0.0 gap=0.0 mi=0.0 macro_n=0 sum_ab=0.0 gated_gap=0.0",
                seed, n, tau);
        }
        return;
    }

    // Find best merge lens (standard max-gap)
    let mut best_lens: Option<Lens> = None;
    let mut best_gap = 0.0f64;
    for i in 0..branches.len() {
        for j in (i + 1)..branches.len() {
            if let Some((jl, _mk, ms, mg)) = param_merge(
                &root,
                &branches[i].0,
                &branches[j].0,
                path_seed + 5000 + (i * branches.len() + j) as u64 * 100,
                &ref_params,
            ) {
                if ms <= root_sigma + 1e-10 && mg > 0.01 && mg > best_gap {
                    best_gap = mg;
                    best_lens = Some(jl);
                }
            }
        }
    }

    let merge_lens = match best_lens {
        Some(l) => l,
        None => {
            println!("SKIP: no viable merge at L1");
            for tau in 1..=50 {
                println!("KEY_TAUSCAN seed={} scale={} tau={} frob=0.0 gap=0.0 mi=0.0 macro_n=0 sum_ab=0.0 gated_gap=0.0",
                    seed, n, tau);
            }
            return;
        }
    };

    let macro_n = merge_lens.macro_n;
    println!(
        "Merge lens: macro_n={}, reference gap (tau=20)={:.6}",
        macro_n, best_gap
    );

    // Also compute the gated kernel's spectral gap (the ancestor kernel)
    // The root is what we apply the lens to, so:
    let root_gap = root.spectral_gap();
    println!("Root kernel gap: {:.6}", root_gap);

    // Step 2: Sweep tau through the fixed merge lens
    for tau in 1..=50usize {
        let ktau = helpers::matrix_power(&root, tau);
        let macro_k = helpers::build_macro_from_ktau(&ktau.kernel, &merge_lens.mapping, macro_n);
        let pi = macro_k.stationary(10000, 1e-12);
        let gap = macro_k.spectral_gap();
        let mi = compute_mi(&macro_k);

        // Frobenius distance from rank-1 projector (all rows = pi)
        let mut frob_sq = 0.0f64;
        for i in 0..macro_n {
            for j in 0..macro_n {
                let diff = macro_k.kernel[i][j] - pi[j];
                frob_sq += diff * diff;
            }
        }
        let frob = frob_sq.sqrt();

        // sum_ab for 2-state kernels
        let sum_ab = if macro_n == 2 {
            macro_k.kernel[0][1] + macro_k.kernel[1][0]
        } else {
            0.0
        };

        println!(
            "tau={:3}: frob={:.8} gap={:.6} mi={:.6} sum_ab={:.6}",
            tau, frob, gap, mi, sum_ab
        );
        println!("KEY_TAUSCAN seed={} scale={} tau={} frob={:.8} gap={:.6} mi={:.6} macro_n={} sum_ab={:.6} root_gap={:.6}",
            seed, n, tau, frob, gap, mi, macro_n, sum_ab, root_gap);
    }
}

// ========== EXP-074: Non-Markovianity Test (Phase 0 Diagnostic) ==========
//
// Sample long micro trajectory from ROOT kernel (pre-gating), project through
// the cascade's L1 merge lens. Compare P(X_{t+1} | X_t) vs P(X_{t+1} | X_t, X_{t-1}).
// If these differ, the macro process has memory that forced-Markov discards.

fn run_exp_074(seed: u64, scale: usize) {
    use six_primitives_core::substrate::{path_reversal_asymmetry, Lens};
    let n = scale.max(8);
    let root = MarkovKernel::random(n, seed);
    let pi_root = root.stationary(10000, 1e-12);
    let root_sigma = path_reversal_asymmetry(&root, &pi_root, 10);

    println!(
        "\n=== EXP-074 Non-Markovianity Test (seed={}, scale={}) ===",
        seed, n
    );

    // Step 1: Find L1 merge lens (same as EXP-073)
    let ref_params = CascadeParams {
        tau: 20,
        gate_prob_override: None,
        n_traj_mult: 1.0,
        exact: true,
        minimize_gap: false,
    };

    let l1_comps: Vec<Vec<(&str, f64)>> = vec![
        vec![("P2", 0.0), ("P4", 0.0)],
        vec![("P1sym", 0.0), ("P2", 0.0), ("P4", 0.0)],
        vec![("P1", 0.3), ("P2", 0.0), ("P4", 0.0)],
        vec![("P2", 0.0), ("P5", 0.0)],
        vec![("P1sym", 0.0), ("P2", 0.0), ("P5", 0.0)],
        vec![("P1", 0.1), ("P2", 0.0), ("P4", 0.0)],
    ];

    let path_seed = seed * 1000;
    let mut branches: Vec<(Lens, MarkovKernel, f64, f64)> = Vec::new();
    for (i, comp) in l1_comps.iter().enumerate() {
        if let Some(result) = param_branch(
            &root,
            root_sigma,
            comp,
            path_seed + (i as u64 + 1) * 1000,
            &ref_params,
        ) {
            branches.push(result);
        }
    }

    if branches.len() < 2 {
        println!("SKIP: only {} viable branches", branches.len());
        println!(
            "KEY_NM seed={} scale={} nm_mean=0.0 nm_max=0.0 n_pairs=0 macro_n=0",
            seed, n
        );
        return;
    }

    let mut best_lens: Option<Lens> = None;
    let mut best_gap = 0.0f64;
    for i in 0..branches.len() {
        for j in (i + 1)..branches.len() {
            if let Some((jl, _mk, ms, mg)) = param_merge(
                &root,
                &branches[i].0,
                &branches[j].0,
                path_seed + 5000 + (i * branches.len() + j) as u64 * 100,
                &ref_params,
            ) {
                if ms <= root_sigma + 1e-10 && mg > 0.01 && mg > best_gap {
                    best_gap = mg;
                    best_lens = Some(jl);
                }
            }
        }
    }

    let merge_lens = match best_lens {
        Some(l) => l,
        None => {
            println!("SKIP: no viable merge");
            println!(
                "KEY_NM seed={} scale={} nm_mean=0.0 nm_max=0.0 n_pairs=0 macro_n=0",
                seed, n
            );
            return;
        }
    };
    let macro_n = merge_lens.macro_n;
    println!("Merge lens: macro_n={}", macro_n);

    // Step 2: Sample long micro trajectory from ROOT kernel, project to macro
    let traj_len = 200_000usize;
    let micro_traj = root.sample_trajectory(0, traj_len, seed + 100);
    let macro_traj: Vec<usize> = micro_traj.iter().map(|&s| merge_lens.mapping[s]).collect();

    // First-order transition counts: P(X_{t+1} | X_t)
    let mut counts_1 = vec![vec![0.0f64; macro_n]; macro_n];
    for t in 0..(macro_traj.len() - 1) {
        counts_1[macro_traj[t]][macro_traj[t + 1]] += 1.0;
    }

    // Second-order transition counts: P(X_{t+1} | X_t, X_{t-1})
    let mut counts_2 = vec![vec![vec![0.0f64; macro_n]; macro_n]; macro_n];
    for t in 0..(macro_traj.len() - 2) {
        counts_2[macro_traj[t]][macro_traj[t + 1]][macro_traj[t + 2]] += 1.0;
    }

    // Compute non-Markovianity: for each (prev, curr), compare
    // P(next | curr) vs P(next | curr, prev) via total variation
    let min_count = 30.0f64;
    let mut nm_sum = 0.0f64;
    let mut nm_max = 0.0f64;
    let mut n_pairs = 0usize;

    for curr in 0..macro_n {
        let row_total_1: f64 = counts_1[curr].iter().sum();
        if row_total_1 < min_count {
            continue;
        }

        for prev in 0..macro_n {
            let row_total_2: f64 = counts_2[prev][curr].iter().sum();
            if row_total_2 < min_count {
                continue;
            }

            // TV distance = 0.5 * sum |P(next|curr) - P(next|curr,prev)|
            let mut tv = 0.0f64;
            for next_s in 0..macro_n {
                let p1 = counts_1[curr][next_s] / row_total_1;
                let p2 = counts_2[prev][curr][next_s] / row_total_2;
                tv += (p1 - p2).abs();
            }
            tv *= 0.5;

            nm_sum += tv;
            if tv > nm_max {
                nm_max = tv;
            }
            n_pairs += 1;
        }
    }

    let nm_mean = if n_pairs > 0 {
        nm_sum / n_pairs as f64
    } else {
        0.0
    };

    println!(
        "Non-Markovianity: mean_TV={:.6} max_TV={:.6} n_pairs={}",
        nm_mean, nm_max, n_pairs
    );
    println!(
        "KEY_NM seed={} scale={} nm_mean={:.6} nm_max={:.6} n_pairs={} macro_n={}",
        seed, n, nm_mean, nm_max, n_pairs, macro_n
    );
}

// ========== EXP-075: Slow-Mode-Preserving Merge (Phase 0 Diagnostic) ==========
//
// Run cascade twice: control (max-gap merge) and treatment (min-gap merge).
// Both use exact K^tau. Compare depth, terminal_n, rank-1-ness.

fn run_exp_075(seed: u64, scale: usize) {
    let n = scale.max(8);

    println!(
        "\n=== EXP-075 Slow-Mode Merge (seed={}, scale={}) ===",
        seed, n
    );

    // Control: standard max-gap merge, exact
    let params_ctrl = CascadeParams {
        tau: 20,
        gate_prob_override: None,
        n_traj_mult: 1.0,
        exact: true,
        minimize_gap: false,
    };
    let r_ctrl = run_parameterized_cascade(n, seed, seed * 1000, &params_ctrl);

    // Treatment: min-gap merge (slow-mode preserving), exact
    let params_slow = CascadeParams {
        tau: 20,
        gate_prob_override: None,
        n_traj_mult: 1.0,
        exact: true,
        minimize_gap: true,
    };
    let r_slow = run_parameterized_cascade(n, seed, seed * 1000, &params_slow);

    // Also compute Frobenius distance from rank-1 for terminal kernels
    // (to verify rank-1-ness independently of sum_ab)

    println!(
        "CTRL:  depth={} n={} sum_ab={:.6} eps={:.6} k={} l1_mi={:.6} pgap={:.6}",
        r_ctrl.depth,
        r_ctrl.terminal_n,
        r_ctrl.sum_ab,
        r_ctrl.eps,
        r_ctrl.minority_k,
        r_ctrl.l1_mi,
        r_ctrl.parent_gap_before_terminal
    );
    println!(
        "SLOW:  depth={} n={} sum_ab={:.6} eps={:.6} k={} l1_mi={:.6} pgap={:.6}",
        r_slow.depth,
        r_slow.terminal_n,
        r_slow.sum_ab,
        r_slow.eps,
        r_slow.minority_k,
        r_slow.l1_mi,
        r_slow.parent_gap_before_terminal
    );

    let ctrl_dev = (1.0 - r_ctrl.sum_ab).abs();
    let slow_dev = (1.0 - r_slow.sum_ab).abs();

    println!("KEY_SLOWMODE seed={} scale={} mode=ctrl depth={} terminal_n={} sum_ab={:.8} dev={:.8} eps={:.6} minority_k={} l1_mi={:.6} parent_gap={:.6}",
        seed, n, r_ctrl.depth, r_ctrl.terminal_n, r_ctrl.sum_ab, ctrl_dev, r_ctrl.eps, r_ctrl.minority_k, r_ctrl.l1_mi, r_ctrl.parent_gap_before_terminal);
    println!("KEY_SLOWMODE seed={} scale={} mode=slow depth={} terminal_n={} sum_ab={:.8} dev={:.8} eps={:.6} minority_k={} l1_mi={:.6} parent_gap={:.6}",
        seed, n, r_slow.depth, r_slow.terminal_n, r_slow.sum_ab, slow_dev, r_slow.eps, r_slow.minority_k, r_slow.l1_mi, r_slow.parent_gap_before_terminal);
}

// ========== Phase 2 Dynamics Validation Experiments ==========

/// Helper: run dynamics with given config and print snapshot lines.
fn run_dynamics_experiment(exp_id: &str, seed: u64, scale: usize, config: DynamicsConfig) {
    let trace = six_dynamics::run_dynamics(&config);

    for snap in &trace.snapshots {
        println!("KEY_DYN seed={} scale={} exp={} step={} eff_gap={:.6} macro_n={} tau={} frob={:.6} macro_gap={:.6} sigma={:.6} gated={} budget={:.2} p1_acc={} p1_rej={} p2_acc={} p2_rej={} traj={}",
            seed, scale, exp_id, snap.step, snap.eff_gap, snap.macro_n, snap.tau,
            snap.frob_from_rank1, snap.macro_gap, snap.sigma, snap.gated_edges,
            snap.budget, snap.p1_accepted, snap.p1_rejected, snap.p2_accepted,
            snap.p2_rejected, snap.traj_steps);
    }

    let final_snap = trace.snapshots.last().unwrap();
    let max_frob = trace
        .snapshots
        .iter()
        .map(|s| s.frob_from_rank1)
        .fold(0.0f64, f64::max);
    let total_mod = final_snap.p1_accepted
        + final_snap.p1_rejected
        + final_snap.p2_accepted
        + final_snap.p2_rejected;
    let accept_rate = if total_mod > 0 {
        (final_snap.p1_accepted + final_snap.p2_accepted) as f64 / total_mod as f64
    } else {
        0.0
    };

    println!("KEY_DYNSUMMARY seed={} scale={} exp={} n_snaps={} final_frob={:.6} max_frob={:.6} final_macro_n={} final_gated={} final_budget={:.2} accept_rate={:.4} p1_acc={} p2_acc={} blocks={}",
        seed, scale, exp_id, trace.snapshots.len(), final_snap.frob_from_rank1,
        max_frob, final_snap.macro_n, final_snap.gated_edges, final_snap.budget,
        accept_rate, final_snap.p1_accepted, final_snap.p2_accepted, final_snap.block_count);
}

/// EXP-076: Null regime — P6 OFF (no budget), P3 OFF (no protocol).
/// Expect: no kernel modifications accepted, frob stays at initial, macro_n=1 (connected).
fn run_exp_076(seed: u64, scale: usize) {
    let n = scale.max(8);
    println!("\n=== EXP-076 Null Regime (seed={}, scale={}) ===", seed, n);

    let config = DynamicsConfig {
        n,
        p_traj: 0.90,
        p_p1: 0.03,
        p_p2: 0.03,
        p_p4: 0.01,
        p_p5: 0.01,
        p_p6: 0.02,
        budget_rate: 0.0, // P6 OFF
        budget_init: 0.0, // No budget at all
        p1_strength: 0.1,
        p2_flips: (n / 8).max(1),
        min_row_entropy: 0.1 * (n as f64).ln(),
        max_self_loop: 1.0 - 1.0 / n as f64,
        protocol_cycle_len: 1, // P3 OFF (no cycle)
        total_steps: n * 2000,
        obs_interval: n * 200,
        tau_alpha: 0.5,
        budget_cap: 0.0,
        n_clusters: 2,
        pica: PicaConfig::none(),
        seed,
    };
    run_dynamics_experiment("076", seed, n, config);
}

/// EXP-077: P6 drive isolation — P6 ON, P3 OFF.
/// Question: does budget-driven modification create slow-mixing structure?
fn run_exp_077(seed: u64, scale: usize) {
    let n = scale.max(8);
    println!("\n=== EXP-077 P6 Drive (seed={}, scale={}) ===", seed, n);

    let ln_n = (n as f64).ln();
    let config = DynamicsConfig {
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
        p2_flips: (n / 8).max(1),
        min_row_entropy: 0.1 * ln_n,
        max_self_loop: 1.0 - 1.0 / n as f64,
        protocol_cycle_len: 1, // P3 OFF
        total_steps: n * 2000,
        obs_interval: n * 200,
        tau_alpha: 0.5,
        budget_cap: 0.0,
        n_clusters: 2,
        pica: PicaConfig::none(),
        seed,
    };
    run_dynamics_experiment("077", seed, n, config);
}

/// EXP-078: P3 isolation — P3 ON (protocol cycling), P6 OFF (no budget).
/// Question: does protocol phase biasing alone create any structure?
fn run_exp_078(seed: u64, scale: usize) {
    let n = scale.max(8);
    println!(
        "\n=== EXP-078 P3 Isolation (seed={}, scale={}) ===",
        seed, n
    );

    let config = DynamicsConfig {
        n,
        p_traj: 0.90,
        p_p1: 0.03,
        p_p2: 0.03,
        p_p4: 0.01,
        p_p5: 0.01,
        p_p6: 0.02,
        budget_rate: 0.0, // P6 OFF
        budget_init: 0.0,
        p1_strength: 0.1,
        p2_flips: (n / 8).max(1),
        min_row_entropy: 0.1 * (n as f64).ln(),
        max_self_loop: 1.0 - 1.0 / n as f64,
        protocol_cycle_len: 100, // P3 ON
        total_steps: n * 2000,
        obs_interval: n * 200,
        tau_alpha: 0.5,
        budget_cap: 0.0,
        n_clusters: 2,
        pica: PicaConfig::none(),
        seed,
    };
    run_dynamics_experiment("078", seed, n, config);
}

/// EXP-079: Full dynamics — P6 ON + P3 ON + viability.
/// Question: do snapshot macro kernels become non-rank-1?
fn run_exp_079(seed: u64, scale: usize) {
    let n = scale.max(8);
    println!(
        "\n=== EXP-079 Full Dynamics (seed={}, scale={}) ===",
        seed, n
    );

    let ln_n = (n as f64).ln();
    let config = DynamicsConfig {
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
        p2_flips: (n / 8).max(1),
        min_row_entropy: 0.1 * ln_n,
        max_self_loop: 1.0 - 1.0 / n as f64,
        protocol_cycle_len: 100, // P3 ON
        total_steps: n * 2000,
        obs_interval: n * 200,
        tau_alpha: 0.5,
        budget_cap: 0.0,
        n_clusters: 2,
        pica: PicaConfig::none(),
        seed,
    };
    run_dynamics_experiment("079", seed, n, config);
}

/// EXP-080: Spectral-guided dynamics — P6 ON + P3 ON + spectral-guided P2.
/// Question: does targeting inter-cluster edges create scale-independent structure?
fn run_exp_080(seed: u64, scale: usize) {
    let n = scale.max(8);
    println!(
        "\n=== EXP-080 Spectral-Guided Dynamics (seed={}, scale={}) ===",
        seed, n
    );

    let ln_n = (n as f64).ln();
    let config = DynamicsConfig {
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
        p2_flips: (n / 8).max(1),
        min_row_entropy: 0.1 * ln_n,
        max_self_loop: 1.0 - 1.0 / n as f64,
        protocol_cycle_len: 100,
        total_steps: n * 2000,
        obs_interval: n * 200,
        tau_alpha: 0.5,
        budget_cap: 0.0,
        n_clusters: 2,
        pica: PicaConfig::none(),
        seed,
    };
    run_dynamics_experiment("080", seed, n, config);
}

// EXP-081: Budget cap — spectral-guided with budget capped at initial value.
// Tests whether unbounded budget was necessary for the attractor.
fn run_exp_081(seed: u64, scale: usize) {
    let n = scale.max(8);
    println!("\n=== EXP-081 Budget Cap (seed={}, scale={}) ===", seed, n);

    let ln_n = (n as f64).ln();
    let budget_init = n as f64 * ln_n;
    let config = DynamicsConfig {
        n,
        p_traj: 0.90,
        p_p1: 0.03,
        p_p2: 0.03,
        p_p4: 0.01,
        p_p5: 0.01,
        p_p6: 0.02,
        budget_rate: ln_n * 0.01,
        budget_init,
        p1_strength: 0.1,
        p2_flips: (n / 8).max(1),
        min_row_entropy: 0.1 * ln_n,
        max_self_loop: 1.0 - 1.0 / n as f64,
        protocol_cycle_len: 100,
        total_steps: n * 2000,
        obs_interval: n * 200,
        tau_alpha: 0.5,
        budget_cap: budget_init, // KEY: cap budget at initial value
        n_clusters: 2,
        pica: PicaConfig::none(),
        seed,
    };
    run_dynamics_experiment("081", seed, n, config);
}

// EXP-082: Multi-state spectral clustering (k=4).
// Tests whether 4-way spectral partition creates richer macro structure.
fn run_exp_082(seed: u64, scale: usize) {
    let n = scale.max(8);
    println!(
        "\n=== EXP-082 Multi-State k=4 (seed={}, scale={}) ===",
        seed, n
    );

    let ln_n = (n as f64).ln();
    let config = DynamicsConfig {
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
        p2_flips: (n / 8).max(1),
        min_row_entropy: 0.1 * ln_n,
        max_self_loop: 1.0 - 1.0 / n as f64,
        protocol_cycle_len: 100,
        total_steps: n * 2000,
        obs_interval: n * 200,
        tau_alpha: 0.5,
        budget_cap: 0.0,
        n_clusters: 4, // KEY: 4-way spectral partition
        pica: PicaConfig::none(),
        seed,
    };
    run_dynamics_experiment("082", seed, n, config);
}

// EXP-083: Non-Markovianity test on evolved kernel.
// After spectral-guided dynamics converge, sample trajectory and test Markov property.
fn run_exp_083(seed: u64, scale: usize) {
    use rand::Rng;
    use rand::SeedableRng;
    use rand_chacha::ChaCha8Rng;

    let n = scale.max(8);
    println!(
        "\n=== EXP-083 Non-Markovianity on Evolved Kernel (seed={}, scale={}) ===",
        seed, n
    );

    let ln_n = (n as f64).ln();

    // Phase 1: Run dynamics to convergence (spectral-guided, same config as EXP-080)
    let config = DynamicsConfig {
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
        p2_flips: (n / 8).max(1),
        min_row_entropy: 0.1 * ln_n,
        max_self_loop: 1.0 - 1.0 / n as f64,
        protocol_cycle_len: 100,
        total_steps: n * 2000,
        obs_interval: n * 200,
        tau_alpha: 0.5,
        budget_cap: 0.0,
        n_clusters: 2,
        pica: PicaConfig::none(),
        seed,
    };
    let trace = six_dynamics::run_dynamics(&config);
    let final_snap = trace.snapshots.last().unwrap();
    let evolved_kernel = &trace.final_kernel;
    println!(
        "  Dynamics converged: frob={:.6} eff_gap={:.6}",
        final_snap.frob_from_rank1, final_snap.eff_gap
    );

    // Phase 2: Get the spectral bisection lens on the evolved kernel
    let partition = six_dynamics::spectral::spectral_partition(evolved_kernel, 2);
    let macro_n = six_dynamics::spectral::n_clusters(&partition);

    // Phase 3: Sample long trajectory from EVOLVED kernel and test non-Markovianity
    let traj_len = 200_000usize;
    let mut rng2 = ChaCha8Rng::seed_from_u64(seed + 1000);
    let mut micro_traj = Vec::with_capacity(traj_len);
    let mut pos = rng2.gen_range(0..n);
    micro_traj.push(pos);

    for _ in 1..traj_len {
        let r: f64 = rng2.gen();
        let mut cum = 0.0;
        let mut next = n - 1; // fallback for floating-point tail mass
        for j in 0..n {
            cum += evolved_kernel.kernel[pos][j];
            if r < cum {
                next = j;
                break;
            }
        }
        pos = next;
        micro_traj.push(pos);
    }

    // Project to macro
    let macro_traj: Vec<usize> = micro_traj.iter().map(|&s| partition[s]).collect();

    // Build first-order and second-order transition counts
    let mut count_1st = vec![vec![0u64; macro_n]; macro_n];
    let mut count_2nd = vec![vec![vec![0u64; macro_n]; macro_n]; macro_n];

    for t in 1..traj_len {
        let curr = macro_traj[t];
        let prev = macro_traj[t - 1];
        count_1st[prev][curr] += 1;
        if t >= 2 {
            let pprev = macro_traj[t - 2];
            count_2nd[pprev][prev][curr] += 1;
        }
    }

    // Compare P(next | curr) vs P(next | curr, prev) via TV distance
    let mut nm_sum = 0.0;
    let mut nm_max: f64 = 0.0;
    let mut n_pairs = 0u64;
    let min_count = 20;

    for prev in 0..macro_n {
        let total_1st: u64 = count_1st[prev].iter().sum();
        if total_1st < min_count as u64 {
            continue;
        }

        for pprev in 0..macro_n {
            let total_2nd: u64 = count_2nd[pprev][prev].iter().sum();
            if total_2nd < min_count as u64 {
                continue;
            }

            let mut tv = 0.0;
            for next in 0..macro_n {
                let p1 = count_1st[prev][next] as f64 / total_1st as f64;
                let p2 = count_2nd[pprev][prev][next] as f64 / total_2nd as f64;
                tv += (p1 - p2).abs();
            }
            tv /= 2.0;

            nm_sum += tv;
            nm_max = nm_max.max(tv);
            n_pairs += 1;
        }
    }

    let nm_mean = if n_pairs > 0 {
        nm_sum / n_pairs as f64
    } else {
        0.0
    };

    println!("KEY_NM083 seed={} scale={} macro_n={} nm_mean={:.6} nm_max={:.6} n_pairs={} frob={:.6} eff_gap={:.6} kernel=evolved",
        seed, n, macro_n, nm_mean, nm_max, n_pairs,
        final_snap.frob_from_rank1, final_snap.eff_gap);
}

// Helper: compute non-Markovianity of a kernel under a given partition.
fn compute_non_markovianity(
    kernel: &six_primitives_core::substrate::MarkovKernel,
    partition: &[usize],
    macro_n: usize,
    seed: u64,
) -> (f64, f64, u64) {
    use rand::Rng;
    use rand::SeedableRng;
    use rand_chacha::ChaCha8Rng;

    let n = kernel.n;
    let traj_len = 200_000usize;
    let mut rng = ChaCha8Rng::seed_from_u64(seed + 1000);
    let mut pos = rng.gen_range(0..n);
    let mut macro_traj = Vec::with_capacity(traj_len);
    macro_traj.push(partition[pos]);

    for _ in 1..traj_len {
        let r: f64 = rng.gen();
        let mut cum = 0.0;
        let mut next = n - 1; // fallback for floating-point tail mass
        for j in 0..n {
            cum += kernel.kernel[pos][j];
            if r < cum {
                next = j;
                break;
            }
        }
        pos = next;
        macro_traj.push(partition[pos]);
    }

    let mut count_1st = vec![vec![0u64; macro_n]; macro_n];
    let mut count_2nd = vec![vec![vec![0u64; macro_n]; macro_n]; macro_n];
    for t in 1..traj_len {
        let curr = macro_traj[t];
        let prev = macro_traj[t - 1];
        count_1st[prev][curr] += 1;
        if t >= 2 {
            count_2nd[macro_traj[t - 2]][prev][curr] += 1;
        }
    }

    let min_count = 20u64;
    let mut nm_sum = 0.0;
    let mut nm_max: f64 = 0.0;
    let mut n_pairs = 0u64;
    for prev in 0..macro_n {
        let total_1st: u64 = count_1st[prev].iter().sum();
        if total_1st < min_count {
            continue;
        }
        for pprev in 0..macro_n {
            let total_2nd: u64 = count_2nd[pprev][prev].iter().sum();
            if total_2nd < min_count {
                continue;
            }
            let mut tv = 0.0;
            for next in 0..macro_n {
                let p1 = count_1st[prev][next] as f64 / total_1st as f64;
                let p2 = count_2nd[pprev][prev][next] as f64 / total_2nd as f64;
                tv += (p1 - p2).abs();
            }
            tv /= 2.0;
            nm_sum += tv;
            nm_max = nm_max.max(tv);
            n_pairs += 1;
        }
    }
    let nm_mean = if n_pairs > 0 {
        nm_sum / n_pairs as f64
    } else {
        0.0
    };
    (nm_mean, nm_max, n_pairs)
}

// EXP-084: k=8 spectral partition (3 eigenvectors).
// Tests whether 8-way spectral partition creates even richer macro structure.
fn run_exp_084(seed: u64, scale: usize) {
    let n = scale.max(8);
    println!(
        "\n=== EXP-084 Multi-State k=8 (seed={}, scale={}) ===",
        seed, n
    );

    let ln_n = (n as f64).ln();
    let config = DynamicsConfig {
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
        p2_flips: (n / 8).max(1),
        min_row_entropy: 0.1 * ln_n,
        max_self_loop: 1.0 - 1.0 / n as f64,
        protocol_cycle_len: 100,
        total_steps: n * 2000,
        obs_interval: n * 200,
        tau_alpha: 0.5,
        budget_cap: 0.0,
        n_clusters: 8, // KEY: 8-way spectral partition
        pica: PicaConfig::none(),
        seed,
    };
    run_dynamics_experiment("084", seed, n, config);
}

// EXP-085: k=4 with budget cap (recommended configuration).
// Combines the best settings: spectral-guided, k=4 partition, budget capped.
fn run_exp_085(seed: u64, scale: usize) {
    let n = scale.max(8);
    println!(
        "\n=== EXP-085 k=4 + Budget Cap (seed={}, scale={}) ===",
        seed, n
    );

    let ln_n = (n as f64).ln();
    let budget_init = n as f64 * ln_n;
    let config = DynamicsConfig {
        n,
        p_traj: 0.90,
        p_p1: 0.03,
        p_p2: 0.03,
        p_p4: 0.01,
        p_p5: 0.01,
        p_p6: 0.02,
        budget_rate: ln_n * 0.01,
        budget_init,
        p1_strength: 0.1,
        p2_flips: (n / 8).max(1),
        min_row_entropy: 0.1 * ln_n,
        max_self_loop: 1.0 - 1.0 / n as f64,
        protocol_cycle_len: 100,
        total_steps: n * 2000,
        obs_interval: n * 200,
        tau_alpha: 0.5,
        budget_cap: budget_init, // KEY: budget capped
        n_clusters: 4,           // KEY: 4-way partition
        pica: PicaConfig::none(),
        seed,
    };
    run_dynamics_experiment("085", seed, n, config);
}

// EXP-086: Non-Markovianity with k=4 partition on evolved kernel.
// Tests if the 3-state macro process has memory (unlike the 2-state case).
fn run_exp_086(seed: u64, scale: usize) {
    let n = scale.max(8);
    println!(
        "\n=== EXP-086 Non-Markovianity k=4 (seed={}, scale={}) ===",
        seed, n
    );

    let ln_n = (n as f64).ln();

    // Run dynamics with k=4 spectral partition
    let config = DynamicsConfig {
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
        p2_flips: (n / 8).max(1),
        min_row_entropy: 0.1 * ln_n,
        max_self_loop: 1.0 - 1.0 / n as f64,
        protocol_cycle_len: 100,
        total_steps: n * 2000,
        obs_interval: n * 200,
        tau_alpha: 0.5,
        budget_cap: 0.0,
        n_clusters: 4,
        pica: PicaConfig::none(),
        seed,
    };
    let trace = six_dynamics::run_dynamics(&config);
    let final_snap = trace.snapshots.last().unwrap();
    let evolved_kernel = &trace.final_kernel;

    // Get k=4 spectral partition on evolved kernel
    let partition = six_dynamics::spectral::spectral_partition(evolved_kernel, 4);
    let macro_n = six_dynamics::spectral::n_clusters(&partition);

    let (nm_mean, nm_max, n_pairs) =
        compute_non_markovianity(evolved_kernel, &partition, macro_n, seed);

    println!("KEY_NM086 seed={} scale={} macro_n={} nm_mean={:.6} nm_max={:.6} n_pairs={} frob={:.6} eff_gap={:.6} kernel=evolved_k4",
        seed, n, macro_n, nm_mean, nm_max, n_pairs,
        final_snap.frob_from_rank1, final_snap.eff_gap);
}

// ========== EXP-087: Cross-Layer Coupling ==========

fn run_exp_087(seed: u64, scale: usize) {
    let n = scale.max(8);
    println!(
        "\n=== EXP-087 Cross-Layer Coupling (seed={}, scale={}) ===",
        seed, n
    );

    let ln_n = (n as f64).ln();
    let budget_init = n as f64 * ln_n;

    let config = DynamicsConfig {
        n,
        p_traj: 0.90,
        p_p1: 0.03,
        p_p2: 0.03,
        p_p4: 0.01,
        p_p5: 0.01,
        p_p6: 0.02,
        budget_rate: ln_n * 0.01,
        budget_init,
        p1_strength: 0.1,
        p2_flips: (n / 8).max(1),
        min_row_entropy: 0.1 * ln_n,
        max_self_loop: 1.0 - 1.0 / n as f64,
        protocol_cycle_len: 100,
        total_steps: n * 2000,
        obs_interval: n * 200,
        tau_alpha: 0.5,
        budget_cap: budget_init, // Budget capped
        n_clusters: 4,           // k=4 spectral partition
        pica: PicaConfig::none(),
        seed,
    };

    let trace = six_dynamics::run_dynamics(&config);

    for snap in &trace.snapshots {
        println!("KEY_DYN seed={} scale={} exp=087 step={} eff_gap={:.6} macro_n={} tau={} frob={:.6} macro_gap={:.6} sigma={:.6} gated={} budget={:.2} l1_frob={:.6} p1_acc={} p1_rej={} p2_acc={} p2_rej={} traj={}",
            seed, n, snap.step, snap.eff_gap, snap.macro_n, snap.tau,
            snap.frob_from_rank1, snap.macro_gap, snap.sigma, snap.gated_edges,
            snap.budget, snap.level1_frob,
            snap.p1_accepted, snap.p1_rejected,
            snap.p2_accepted, snap.p2_rejected, snap.traj_steps);
    }

    let last = trace.snapshots.last().unwrap();
    let max_frob: f64 = trace
        .snapshots
        .iter()
        .map(|s| s.frob_from_rank1)
        .fold(0.0f64, f64::max);
    let total_mod_087 = last.p1_accepted + last.p1_rejected + last.p2_accepted + last.p2_rejected;
    let accept_rate_087 = if total_mod_087 > 0 {
        (last.p1_accepted + last.p2_accepted) as f64 / total_mod_087 as f64
    } else {
        0.0
    };
    let p2_accept_rate_087 = if last.p2_accepted + last.p2_rejected > 0 {
        last.p2_accepted as f64 / (last.p2_accepted + last.p2_rejected) as f64
    } else {
        0.0
    };
    println!("KEY_DYNSUMMARY seed={} scale={} exp=087 n_snaps={} final_frob={:.6} max_frob={:.6} final_macro_n={} final_gated={} final_budget={:.2} accept_rate={:.4} p2_accept_rate={:.4} p1_acc={} p2_acc={} blocks={}",
        seed, n, trace.snapshots.len(), last.frob_from_rank1, max_frob,
        last.macro_n, last.gated_edges, last.budget,
        accept_rate_087, p2_accept_rate_087,
        last.p1_accepted, last.p2_accepted, last.block_count);
}

// ========== EXP-088: Two-Level Ladder Analysis (static cascade on evolved macro kernel) ==========
//
// After Level 0 dynamics converge (recommended config: k=4, spectral, budget cap),
// extract the evolved kernel and build its macro kernel. Then apply static cascade
// analysis to the macro kernel: spectral bisection → adaptive tau → Level 2 macro kernel.
// Tests whether recursive coarse-graining preserves non-rank-1 structure.

fn run_exp_088(seed: u64, scale: usize) {
    let n = scale.max(8);
    println!(
        "\n=== EXP-088 Two-Level Ladder Analysis (seed={}, scale={}) ===",
        seed, n
    );

    // --- Level 0: Run dynamics with recommended config ---
    let ln_n = (n as f64).ln();
    let budget_init = n as f64 * ln_n;
    let config_l0 = DynamicsConfig {
        n,
        p_traj: 0.90,
        p_p1: 0.03,
        p_p2: 0.03,
        p_p4: 0.01,
        p_p5: 0.01,
        p_p6: 0.02,
        budget_rate: ln_n * 0.01,
        budget_init,
        p1_strength: 0.1,
        p2_flips: (n / 8).max(1),
        min_row_entropy: 0.1 * ln_n,
        max_self_loop: 1.0 - 1.0 / n as f64,
        protocol_cycle_len: 100,
        total_steps: n * 2000,
        obs_interval: n * 200,
        tau_alpha: 0.5,
        budget_cap: budget_init,
        n_clusters: 4,
        pica: PicaConfig::none(),
        seed,
    };

    let trace_l0 = six_dynamics::run_dynamics(&config_l0);
    let evolved_kernel = &trace_l0.final_kernel;

    // --- Level 0 macro kernel extraction ---
    let l0_lens = six_dynamics::spectral::spectral_partition(evolved_kernel, 4);
    let l0_macro_n = six_dynamics::spectral::n_clusters(&l0_lens);
    let l0_gap = evolved_kernel.spectral_gap();
    let l0_tau = six_dynamics::observe::adaptive_tau(l0_gap, 0.5);
    let l0_ktau = helpers::matrix_power(evolved_kernel, l0_tau);
    let l0_macro = helpers::build_macro_from_ktau(&l0_ktau.kernel, &l0_lens, l0_macro_n);
    let l0_frob = six_dynamics::observe::frob_from_rank1(&l0_macro);
    let l0_macro_gap = l0_macro.spectral_gap();

    println!("KEY_LADDER_L0 seed={} scale={} l0_macro_n={} l0_tau={} l0_frob={:.6} l0_gap={:.6} l0_macro_gap={:.6} eff_gap={:.6}",
        seed, n, l0_macro_n, l0_tau, l0_frob, l0_gap, l0_macro_gap, l0_gap);

    if l0_macro_n < 2 {
        println!(
            "KEY_LADDER_L1 seed={} scale={} SKIP l0_macro_n={} (need >=2 for Level 2)",
            seed, n, l0_macro_n
        );
        return;
    }

    // --- Level 1: Static cascade on the macro kernel ---
    // Spectral bisection of the macro kernel → 2 groups
    let l1_lens = six_dynamics::spectral::spectral_partition(&l0_macro, 2);
    let l1_macro_n = six_dynamics::spectral::n_clusters(&l1_lens);

    if l1_macro_n < 2 {
        println!(
            "KEY_LADDER_L1 seed={} scale={} SKIP l1_macro_n={} (degenerate bisection)",
            seed, n, l1_macro_n
        );
        return;
    }

    // Adaptive tau on the macro kernel
    let l1_tau = six_dynamics::observe::adaptive_tau(l0_macro_gap, 0.5);
    let l1_ktau = helpers::matrix_power(&l0_macro, l1_tau);
    let l1_macro = helpers::build_macro_from_ktau(&l1_ktau.kernel, &l1_lens, l1_macro_n);
    let l1_frob = six_dynamics::observe::frob_from_rank1(&l1_macro);
    let l1_macro_gap = l1_macro.spectral_gap();

    // Also compute the stationary distribution and arrow-of-time for Level 2
    let l1_pi = l1_macro.stationary(10000, 1e-12);
    let l1_sigma = six_primitives_core::substrate::path_reversal_asymmetry(&l1_macro, &l1_pi, 10);

    println!("KEY_LADDER_L1 seed={} scale={} l1_macro_n={} l1_tau={} l1_frob={:.6} l1_macro_gap={:.6} l1_sigma={:.6} l0_macro_gap={:.6}",
        seed, n, l1_macro_n, l1_tau, l1_frob, l1_macro_gap, l1_sigma, l0_macro_gap);

    // Print the actual macro kernel entries for inspection
    let l0_entries: Vec<String> = (0..l0_macro_n)
        .flat_map(|i| {
            let row = &l0_macro.kernel[i];
            (0..l0_macro_n)
                .map(move |j| format!("{:.4}", row[j]))
                .collect::<Vec<_>>()
        })
        .collect();
    println!(
        "KEY_LADDER_L0_MACRO seed={} scale={} n={} entries={:?}",
        seed, n, l0_macro_n, l0_entries
    );

    if l1_macro_n >= 2 {
        let l1_entries: Vec<String> = (0..l1_macro_n)
            .flat_map(|i| {
                let row = &l1_macro.kernel[i];
                (0..l1_macro_n)
                    .map(move |j| format!("{:.4}", row[j]))
                    .collect::<Vec<_>>()
            })
            .collect();
        println!(
            "KEY_LADDER_L1_MACRO seed={} scale={} n={} entries={:?}",
            seed, n, l1_macro_n, l1_entries
        );
    }
}

// ========== EXP-089: Dynamics on Macro Kernel (ladder stacking) ==========
//
// Run Level 0 dynamics → extract 3×3 macro kernel → run Level 1 dynamics on it
// → observe Level 1 evolved kernel → build Level 2 macro kernel → measure frob.
// Tests whether the dynamics engine produces non-rank-1 structure at multiple levels.

fn run_exp_089(seed: u64, scale: usize) {
    let n = scale.max(8);
    println!(
        "\n=== EXP-089 Dynamics on Macro Kernel (seed={}, scale={}) ===",
        seed, n
    );

    // --- Level 0: Same as EXP-085 recommended config ---
    let ln_n = (n as f64).ln();
    let budget_init = n as f64 * ln_n;
    let config_l0 = DynamicsConfig {
        n,
        p_traj: 0.90,
        p_p1: 0.03,
        p_p2: 0.03,
        p_p4: 0.01,
        p_p5: 0.01,
        p_p6: 0.02,
        budget_rate: ln_n * 0.01,
        budget_init,
        p1_strength: 0.1,
        p2_flips: (n / 8).max(1),
        min_row_entropy: 0.1 * ln_n,
        max_self_loop: 1.0 - 1.0 / n as f64,
        protocol_cycle_len: 100,
        total_steps: n * 2000,
        obs_interval: n * 200,
        tau_alpha: 0.5,
        budget_cap: budget_init,
        n_clusters: 4,
        pica: PicaConfig::none(),
        seed,
    };

    let trace_l0 = six_dynamics::run_dynamics(&config_l0);
    let evolved_kernel = &trace_l0.final_kernel;

    // --- Extract Level 0 macro kernel ---
    let l0_lens = six_dynamics::spectral::spectral_partition(evolved_kernel, 4);
    let l0_macro_n = six_dynamics::spectral::n_clusters(&l0_lens);
    let l0_gap = evolved_kernel.spectral_gap();
    let l0_tau = six_dynamics::observe::adaptive_tau(l0_gap, 0.5);
    let l0_ktau = helpers::matrix_power(evolved_kernel, l0_tau);
    let l0_macro = helpers::build_macro_from_ktau(&l0_ktau.kernel, &l0_lens, l0_macro_n);
    let l0_frob = six_dynamics::observe::frob_from_rank1(&l0_macro);

    println!(
        "KEY_STACK_L0 seed={} scale={} l0_macro_n={} l0_frob={:.6} l0_gap={:.6} l0_tau={}",
        seed, n, l0_macro_n, l0_frob, l0_gap, l0_tau
    );

    if l0_macro_n < 3 {
        println!(
            "KEY_STACK_L1 seed={} scale={} SKIP l0_macro_n={} (need >=3 for meaningful dynamics)",
            seed, n, l0_macro_n
        );
        return;
    }

    // --- Level 1: Run dynamics on the macro kernel ---
    let m = l0_macro_n;
    let ln_m = (m as f64).ln();
    let l1_budget_init = m as f64 * ln_m;

    let config_l1 = DynamicsConfig {
        n: m,
        p_traj: 0.90,
        p_p1: 0.03,
        p_p2: 0.03,
        p_p4: 0.01,
        p_p5: 0.01,
        p_p6: 0.02,
        budget_rate: ln_m * 0.01,
        budget_init: l1_budget_init,
        p1_strength: 0.1,
        p2_flips: 1, // n=3: only 1 flip per step
        min_row_entropy: 0.1 * ln_m,
        max_self_loop: 1.0 - 1.0 / m as f64,
        protocol_cycle_len: 100,
        total_steps: 10000, // More steps for tiny kernel
        obs_interval: 1000,
        tau_alpha: 0.5,
        budget_cap: l1_budget_init,
        n_clusters: 2, // Bisection for 3-state kernel
        pica: PicaConfig::none(),
        seed: seed + 10000, // Different seed for Level 1 dynamics
    };

    let trace_l1 = six_dynamics::run_dynamics_from_kernel(l0_macro.clone(), &config_l1);

    for snap in &trace_l1.snapshots {
        println!("KEY_STACK_L1_DYN seed={} scale={} step={} eff_gap={:.6} macro_n={} tau={} frob={:.6} macro_gap={:.6} gated={} budget={:.2} p1_acc={} p2_acc={}",
            seed, n, snap.step, snap.eff_gap, snap.macro_n, snap.tau,
            snap.frob_from_rank1, snap.macro_gap, snap.gated_edges,
            snap.budget, snap.p1_accepted, snap.p2_accepted);
    }

    let l1_last = trace_l1.snapshots.last().unwrap();
    let l1_max_frob: f64 = trace_l1
        .snapshots
        .iter()
        .map(|s| s.frob_from_rank1)
        .fold(0.0f64, f64::max);

    // --- Level 2: Static analysis of Level 1 evolved kernel ---
    let l1_evolved = &trace_l1.final_kernel;
    let l1_eff_gap = l1_evolved.spectral_gap();
    let l2_lens = six_dynamics::spectral::spectral_partition(l1_evolved, 2);
    let l2_macro_n = six_dynamics::spectral::n_clusters(&l2_lens);
    let l2_tau = six_dynamics::observe::adaptive_tau(l1_eff_gap, 0.5);

    let (l2_frob, l2_gap) = if l2_macro_n >= 2 {
        let l2_ktau = helpers::matrix_power(l1_evolved, l2_tau);
        let l2_macro = helpers::build_macro_from_ktau(&l2_ktau.kernel, &l2_lens, l2_macro_n);
        (
            six_dynamics::observe::frob_from_rank1(&l2_macro),
            l2_macro.spectral_gap(),
        )
    } else {
        (0.0, 0.0)
    };

    println!("KEY_STACK_SUMMARY seed={} scale={} l0_frob={:.6} l0_macro_n={} l1_max_frob={:.6} l1_final_frob={:.6} l1_gated={} l2_frob={:.6} l2_macro_n={} l2_tau={} l2_gap={:.6}",
        seed, n, l0_frob, l0_macro_n, l1_max_frob, l1_last.frob_from_rank1,
        l1_last.gated_edges, l2_frob, l2_macro_n, l2_tau, l2_gap);
}

// ========== EXP-090: Three-Level Ladder with k=8 at L0 ==========
//
// L0: Run dynamics with k=8 → 4-5 state macro kernel
// L1: Spectral k=4 partition of L0 macro → 3 state macro kernel
// L2: Spectral bisection (k=2) of L1 macro → 2 state macro kernel
// Measures frob at all 3 levels to test depth of emergence ladder.

fn run_exp_090(seed: u64, scale: usize) {
    let n = scale.max(8);
    println!(
        "\n=== EXP-090 Three-Level Ladder k=8 (seed={}, scale={}) ===",
        seed, n
    );

    // --- Level 0: Run dynamics with k=8 ---
    let ln_n = (n as f64).ln();
    let budget_init = n as f64 * ln_n;
    let config_l0 = DynamicsConfig {
        n,
        p_traj: 0.90,
        p_p1: 0.03,
        p_p2: 0.03,
        p_p4: 0.01,
        p_p5: 0.01,
        p_p6: 0.02,
        budget_rate: ln_n * 0.01,
        budget_init,
        p1_strength: 0.1,
        p2_flips: (n / 8).max(1),
        min_row_entropy: 0.1 * ln_n,
        max_self_loop: 1.0 - 1.0 / n as f64,
        protocol_cycle_len: 100,
        total_steps: n * 2000,
        obs_interval: n * 200,
        tau_alpha: 0.5,
        budget_cap: budget_init,
        n_clusters: 8,
        pica: PicaConfig::none(),
        seed,
    };

    let trace_l0 = six_dynamics::run_dynamics(&config_l0);
    let evolved_kernel = &trace_l0.final_kernel;

    // --- Level 0 → macro kernel extraction (k=8) ---
    let l0_lens = six_dynamics::spectral::spectral_partition(evolved_kernel, 8);
    let l0_macro_n = six_dynamics::spectral::n_clusters(&l0_lens);
    let l0_gap = evolved_kernel.spectral_gap();
    let l0_tau = six_dynamics::observe::adaptive_tau(l0_gap, 0.5);
    let l0_ktau = helpers::matrix_power(evolved_kernel, l0_tau);
    let l0_macro = helpers::build_macro_from_ktau(&l0_ktau.kernel, &l0_lens, l0_macro_n);
    let l0_frob = six_dynamics::observe::frob_from_rank1(&l0_macro);
    let l0_macro_gap = l0_macro.spectral_gap();

    println!("KEY_3LADDER_L0 seed={} scale={} l0_macro_n={} l0_tau={} l0_frob={:.6} l0_gap={:.6} l0_macro_gap={:.6}",
        seed, n, l0_macro_n, l0_tau, l0_frob, l0_gap, l0_macro_gap);

    // Print L0 macro kernel
    let l0_entries: Vec<String> = (0..l0_macro_n)
        .flat_map(|i| {
            let row = &l0_macro.kernel[i];
            (0..l0_macro_n)
                .map(move |j| format!("{:.4}", row[j]))
                .collect::<Vec<_>>()
        })
        .collect();
    println!(
        "KEY_3LADDER_L0_MACRO seed={} scale={} n={} entries={:?}",
        seed, n, l0_macro_n, l0_entries
    );

    if l0_macro_n < 3 {
        println!(
            "KEY_3LADDER_L1 seed={} scale={} SKIP l0_macro_n={} (need >=3 for k=4 at L1)",
            seed, n, l0_macro_n
        );
        return;
    }

    // --- Level 1: k=4 partition of L0 macro kernel ---
    let l1_lens = six_dynamics::spectral::spectral_partition(&l0_macro, 4);
    let l1_macro_n = six_dynamics::spectral::n_clusters(&l1_lens);

    if l1_macro_n < 2 {
        println!(
            "KEY_3LADDER_L1 seed={} scale={} SKIP l1_macro_n={} (degenerate k=4 partition)",
            seed, n, l1_macro_n
        );
        return;
    }

    let l1_tau = six_dynamics::observe::adaptive_tau(l0_macro_gap, 0.5);
    let l1_ktau = helpers::matrix_power(&l0_macro, l1_tau);
    let l1_macro = helpers::build_macro_from_ktau(&l1_ktau.kernel, &l1_lens, l1_macro_n);
    let l1_frob = six_dynamics::observe::frob_from_rank1(&l1_macro);
    let l1_macro_gap = l1_macro.spectral_gap();

    println!("KEY_3LADDER_L1 seed={} scale={} l1_macro_n={} l1_tau={} l1_frob={:.6} l1_macro_gap={:.6} l0_macro_gap={:.6}",
        seed, n, l1_macro_n, l1_tau, l1_frob, l1_macro_gap, l0_macro_gap);

    // Print L1 macro kernel
    let l1_entries: Vec<String> = (0..l1_macro_n)
        .flat_map(|i| {
            let row = &l1_macro.kernel[i];
            (0..l1_macro_n)
                .map(move |j| format!("{:.4}", row[j]))
                .collect::<Vec<_>>()
        })
        .collect();
    println!(
        "KEY_3LADDER_L1_MACRO seed={} scale={} n={} entries={:?}",
        seed, n, l1_macro_n, l1_entries
    );

    if l1_macro_n < 3 {
        println!(
            "KEY_3LADDER_L2 seed={} scale={} SKIP l1_macro_n={} (need >=3 for bisection at L2)",
            seed, n, l1_macro_n
        );
        return;
    }

    // --- Level 2: Bisection (k=2) of L1 macro kernel ---
    let l2_lens = six_dynamics::spectral::spectral_partition(&l1_macro, 2);
    let l2_macro_n = six_dynamics::spectral::n_clusters(&l2_lens);

    if l2_macro_n < 2 {
        println!(
            "KEY_3LADDER_L2 seed={} scale={} SKIP l2_macro_n={} (degenerate bisection)",
            seed, n, l2_macro_n
        );
        return;
    }

    let l2_tau = six_dynamics::observe::adaptive_tau(l1_macro_gap, 0.5);
    let l2_ktau = helpers::matrix_power(&l1_macro, l2_tau);
    let l2_macro = helpers::build_macro_from_ktau(&l2_ktau.kernel, &l2_lens, l2_macro_n);
    let l2_frob = six_dynamics::observe::frob_from_rank1(&l2_macro);
    let l2_macro_gap = l2_macro.spectral_gap();

    // Arrow-of-time diagnostic at L2
    let l2_pi = l2_macro.stationary(10000, 1e-12);
    let l2_sigma = six_primitives_core::substrate::path_reversal_asymmetry(&l2_macro, &l2_pi, 10);

    println!("KEY_3LADDER_L2 seed={} scale={} l2_macro_n={} l2_tau={} l2_frob={:.6} l2_macro_gap={:.6} l2_sigma={:.6}",
        seed, n, l2_macro_n, l2_tau, l2_frob, l2_macro_gap, l2_sigma);

    // Print L2 macro kernel
    let l2_entries: Vec<String> = (0..l2_macro_n)
        .flat_map(|i| {
            let row = &l2_macro.kernel[i];
            (0..l2_macro_n)
                .map(move |j| format!("{:.4}", row[j]))
                .collect::<Vec<_>>()
        })
        .collect();
    println!(
        "KEY_3LADDER_L2_MACRO seed={} scale={} n={} entries={:?}",
        seed, n, l2_macro_n, l2_entries
    );

    // Summary line
    println!("KEY_3LADDER_SUMMARY seed={} scale={} l0_n={} l0_frob={:.6} l1_n={} l1_frob={:.6} l2_n={} l2_frob={:.6}",
        seed, n, l0_macro_n, l0_frob, l1_macro_n, l1_frob, l2_macro_n, l2_frob);
}

// ========== EXP-091: Non-Markovianity at Level 1 of the Ladder ==========
//
// Run L0 dynamics (k=8) → extract 4-5 state macro kernel → sample trajectory
// from MACRO kernel → project through k=4 L1 partition → compute NM of L1 process.
// Also tests NM of L0 process (micro traj → k=8 partition) for comparison.

fn run_exp_091(seed: u64, scale: usize) {
    use rand::Rng;
    use rand::SeedableRng;
    use rand_chacha::ChaCha8Rng;

    let n = scale.max(8);
    println!(
        "\n=== EXP-091 Non-Markovianity at Level 1 (seed={}, scale={}) ===",
        seed, n
    );

    // --- Level 0: Run dynamics with k=8 (same as EXP-090) ---
    let ln_n = (n as f64).ln();
    let budget_init = n as f64 * ln_n;
    let config_l0 = DynamicsConfig {
        n,
        p_traj: 0.90,
        p_p1: 0.03,
        p_p2: 0.03,
        p_p4: 0.01,
        p_p5: 0.01,
        p_p6: 0.02,
        budget_rate: ln_n * 0.01,
        budget_init,
        p1_strength: 0.1,
        p2_flips: (n / 8).max(1),
        min_row_entropy: 0.1 * ln_n,
        max_self_loop: 1.0 - 1.0 / n as f64,
        protocol_cycle_len: 100,
        total_steps: n * 2000,
        obs_interval: n * 200,
        tau_alpha: 0.5,
        budget_cap: budget_init,
        n_clusters: 8,
        pica: PicaConfig::none(),
        seed,
    };

    let trace_l0 = six_dynamics::run_dynamics(&config_l0);
    let evolved_kernel = &trace_l0.final_kernel;

    // --- L0 macro kernel extraction (k=8) ---
    let l0_lens = six_dynamics::spectral::spectral_partition(evolved_kernel, 8);
    let l0_macro_n = six_dynamics::spectral::n_clusters(&l0_lens);
    let l0_gap = evolved_kernel.spectral_gap();
    let l0_tau = six_dynamics::observe::adaptive_tau(l0_gap, 0.5);
    let l0_ktau = helpers::matrix_power(evolved_kernel, l0_tau);
    let l0_macro = helpers::build_macro_from_ktau(&l0_ktau.kernel, &l0_lens, l0_macro_n);
    let l0_frob = six_dynamics::observe::frob_from_rank1(&l0_macro);

    // --- Test 1: NM of L0 macro process (micro trajectory → k=8 partition) ---
    let (l0_nm_mean, l0_nm_max, l0_nm_pairs) =
        compute_non_markovianity(evolved_kernel, &l0_lens, l0_macro_n, seed);

    println!(
        "KEY_NM091_L0 seed={} scale={} macro_n={} nm_mean={:.6} nm_max={:.6} n_pairs={} frob={:.6}",
        seed, n, l0_macro_n, l0_nm_mean, l0_nm_max, l0_nm_pairs, l0_frob
    );

    if l0_macro_n < 3 {
        println!(
            "KEY_NM091_L1 seed={} scale={} SKIP l0_macro_n={}",
            seed, n, l0_macro_n
        );
        return;
    }

    // --- L1 partition: k=4 on the macro kernel ---
    let l1_lens = six_dynamics::spectral::spectral_partition(&l0_macro, 4);
    let l1_macro_n = six_dynamics::spectral::n_clusters(&l1_lens);

    if l1_macro_n < 2 {
        println!(
            "KEY_NM091_L1 seed={} scale={} SKIP l1_macro_n={}",
            seed, n, l1_macro_n
        );
        return;
    }

    // --- Test 2: NM of L1 macro process ---
    // Sample long trajectory from the L0 MACRO kernel, project through L1 partition
    let traj_len = 200_000usize;
    let mut rng = ChaCha8Rng::seed_from_u64(seed + 2000);
    let mut pos = rng.gen_range(0..l0_macro_n);
    let mut l1_traj = Vec::with_capacity(traj_len);
    l1_traj.push(l1_lens[pos]);

    for _ in 1..traj_len {
        let r: f64 = rng.gen();
        let mut cum = 0.0;
        let mut next = l0_macro_n - 1; // fallback for floating-point tail mass
        for j in 0..l0_macro_n {
            cum += l0_macro.kernel[pos][j];
            if r < cum {
                next = j;
                break;
            }
        }
        pos = next;
        l1_traj.push(l1_lens[pos]);
    }

    // Build first-order and second-order transition counts for L1 process
    let mut count_1st = vec![vec![0u64; l1_macro_n]; l1_macro_n];
    let mut count_2nd = vec![vec![vec![0u64; l1_macro_n]; l1_macro_n]; l1_macro_n];
    for t in 1..traj_len {
        let curr = l1_traj[t];
        let prev = l1_traj[t - 1];
        count_1st[prev][curr] += 1;
        if t >= 2 {
            count_2nd[l1_traj[t - 2]][prev][curr] += 1;
        }
    }

    let min_count = 20u64;
    let mut nm_sum = 0.0;
    let mut nm_max: f64 = 0.0;
    let mut n_pairs = 0u64;
    for prev in 0..l1_macro_n {
        let total_1st: u64 = count_1st[prev].iter().sum();
        if total_1st < min_count {
            continue;
        }
        for pprev in 0..l1_macro_n {
            let total_2nd: u64 = count_2nd[pprev][prev].iter().sum();
            if total_2nd < min_count {
                continue;
            }
            let mut tv = 0.0;
            for next in 0..l1_macro_n {
                let p1 = count_1st[prev][next] as f64 / total_1st as f64;
                let p2 = count_2nd[pprev][prev][next] as f64 / total_2nd as f64;
                tv += (p1 - p2).abs();
            }
            tv /= 2.0;
            nm_sum += tv;
            nm_max = nm_max.max(tv);
            n_pairs += 1;
        }
    }
    let l1_nm_mean = if n_pairs > 0 {
        nm_sum / n_pairs as f64
    } else {
        0.0
    };

    println!("KEY_NM091_L1 seed={} scale={} l0_macro_n={} l1_macro_n={} nm_mean={:.6} nm_max={:.6} n_pairs={} l0_frob={:.6}",
        seed, n, l0_macro_n, l1_macro_n, l1_nm_mean, nm_max, n_pairs, l0_frob);

    println!(
        "KEY_NM091_SUMMARY seed={} scale={} l0_nm={:.6} l1_nm={:.6} l0_macro_n={} l1_macro_n={}",
        seed, n, l0_nm_mean, l1_nm_mean, l0_macro_n, l1_macro_n
    );
}

// ========== EXP-092: Coupling Strength Sweep ==========
//
// Sweep coupling_strength in {0 (uncoupled), 1, 2, 5, 10, 20} to determine
// if any strength regime amplifies macro structure above the uncoupled baseline.
// Uses k=4 recommended config (spectral-guided, budget cap).

fn run_exp_092(seed: u64, scale: usize) {
    let n = scale.max(8);
    println!(
        "\n=== EXP-092 Coupling Strength Sweep (seed={}, scale={}) ===",
        seed, n
    );

    let strengths: &[f64] = &[0.0, 1.0, 2.0, 5.0, 10.0, 20.0];
    let ln_n = (n as f64).ln();
    let budget_init = n as f64 * ln_n;

    for &strength in strengths {
        let config = DynamicsConfig {
            n,
            p_traj: 0.90,
            p_p1: 0.03,
            p_p2: 0.03,
            p_p4: 0.01,
            p_p5: 0.01,
            p_p6: 0.02,
            budget_rate: ln_n * 0.01,
            budget_init,
            p1_strength: 0.1,
            p2_flips: (n / 8).max(1),
            min_row_entropy: 0.1 * ln_n,
            max_self_loop: 1.0 - 1.0 / n as f64,
            protocol_cycle_len: 100,
            total_steps: n * 2000,
            obs_interval: n * 200,
            tau_alpha: 0.5,
            budget_cap: budget_init,
            n_clusters: 4,
            pica: PicaConfig::none(),
            seed,
        };

        let trace = six_dynamics::run_dynamics(&config);
        let last = trace.snapshots.last().unwrap();
        let max_frob: f64 = trace
            .snapshots
            .iter()
            .map(|s| s.frob_from_rank1)
            .fold(0.0f64, f64::max);
        let p2_total = last.p2_accepted + last.p2_rejected;
        let p2_accept_rate = if p2_total > 0 {
            last.p2_accepted as f64 / p2_total as f64
        } else {
            0.0
        };
        let total_mod = last.p1_accepted + last.p1_rejected + p2_total;
        let accept_rate = if total_mod > 0 {
            (last.p1_accepted + last.p2_accepted) as f64 / total_mod as f64
        } else {
            0.0
        };

        println!("KEY_COUPLING seed={} scale={} strength={:.1} max_frob={:.6} final_frob={:.6} macro_n={} eff_gap={:.6} gated={} accept_rate={:.4} p2_accept_rate={:.4} budget={:.2}",
            seed, n, strength, max_frob, last.frob_from_rank1, last.macro_n,
            last.eff_gap, last.gated_edges, accept_rate, p2_accept_rate, last.budget);
    }
}

// ========== EXP-093: Mutual Information Between Ladder Levels ==========
//
// Run L0 dynamics (k=4, recommended config), extract evolved kernel.
// Compute MI(micro, L0_macro) and MI(L0_macro, L1_macro) to quantify
// information preserved at each level of the emergence ladder.

fn run_exp_093(seed: u64, scale: usize) {
    let n = scale.max(8);
    println!(
        "\n=== EXP-093 Mutual Information Between Levels (seed={}, scale={}) ===",
        seed, n
    );

    // --- Level 0: Run dynamics with k=4 recommended config ---
    let ln_n = (n as f64).ln();
    let budget_init = n as f64 * ln_n;
    let config_l0 = DynamicsConfig {
        n,
        p_traj: 0.90,
        p_p1: 0.03,
        p_p2: 0.03,
        p_p4: 0.01,
        p_p5: 0.01,
        p_p6: 0.02,
        budget_rate: ln_n * 0.01,
        budget_init,
        p1_strength: 0.1,
        p2_flips: (n / 8).max(1),
        min_row_entropy: 0.1 * ln_n,
        max_self_loop: 1.0 - 1.0 / n as f64,
        protocol_cycle_len: 100,
        total_steps: n * 2000,
        obs_interval: n * 200,
        tau_alpha: 0.5,
        budget_cap: budget_init,
        n_clusters: 4,
        pica: PicaConfig::none(),
        seed,
    };

    let trace_l0 = six_dynamics::run_dynamics(&config_l0);
    let evolved_kernel = &trace_l0.final_kernel;

    // --- Level 0 macro kernel extraction (k=4) ---
    let l0_lens = six_dynamics::spectral::spectral_partition(evolved_kernel, 4);
    let l0_macro_n = six_dynamics::spectral::n_clusters(&l0_lens);
    let l0_gap = evolved_kernel.spectral_gap();
    let l0_tau = six_dynamics::observe::adaptive_tau(l0_gap, 0.5);
    let l0_ktau = helpers::matrix_power(evolved_kernel, l0_tau);
    let l0_macro = helpers::build_macro_from_ktau(&l0_ktau.kernel, &l0_lens, l0_macro_n);
    let l0_frob = six_dynamics::observe::frob_from_rank1(&l0_macro);

    // --- Stationary distribution of evolved kernel ---
    let pi = evolved_kernel.stationary(10000, 1e-12);

    // --- MI(micro, L0_macro): H(L0_macro) - H(L0_macro | micro) ---
    // Under stationary distribution, macro state probability: pi_A = sum_{i in A} pi_i
    // H(macro) = - sum_A pi_A log pi_A
    // H(macro | micro) = 0 (macro is deterministic function of micro)
    // So MI(micro, L0_macro) = H(L0_macro) = entropy of the partition under pi
    let mut l0_cluster_pi = vec![0.0f64; l0_macro_n];
    for i in 0..n {
        l0_cluster_pi[l0_lens[i]] += pi[i];
    }
    let h_l0: f64 = l0_cluster_pi
        .iter()
        .filter(|&&p| p > 0.0)
        .map(|&p| -p * p.ln())
        .sum();

    // --- Level 1: bisection of L0 macro kernel ---
    let l0_macro_gap = l0_macro.spectral_gap();
    let l1_lens = six_dynamics::spectral::spectral_partition(&l0_macro, 2);
    let l1_macro_n = six_dynamics::spectral::n_clusters(&l1_lens);

    let mut h_l1 = 0.0f64;
    let mut mi_l0_l1 = 0.0f64;
    let mut l1_frob = 0.0f64;

    if l1_macro_n >= 2 {
        let l1_tau = six_dynamics::observe::adaptive_tau(l0_macro_gap, 0.5);
        let l1_ktau = helpers::matrix_power(&l0_macro, l1_tau);
        let l1_macro = helpers::build_macro_from_ktau(&l1_ktau.kernel, &l1_lens, l1_macro_n);
        l1_frob = six_dynamics::observe::frob_from_rank1(&l1_macro);

        // L1 cluster probabilities (under L0 macro stationary distribution)
        let l0_macro_pi = l0_macro.stationary(10000, 1e-12);
        let mut l1_cluster_pi = vec![0.0f64; l1_macro_n];
        for a in 0..l0_macro_n {
            l1_cluster_pi[l1_lens[a]] += l0_macro_pi[a];
        }
        h_l1 = l1_cluster_pi
            .iter()
            .filter(|&&p| p > 0.0)
            .map(|&p| -p * p.ln())
            .sum();

        // MI(L0_macro, L1_macro) = H(L1_macro) since L1 is deterministic function of L0_macro
        mi_l0_l1 = h_l1;
    }

    // --- MI(micro, L1_macro): H(L1_macro) under full micro pi ---
    // L1 state of micro state i: l1_lens[l0_lens[i]]
    let mut l1_from_micro_pi = vec![0.0f64; l1_macro_n.max(1)];
    if l1_macro_n >= 2 {
        for i in 0..n {
            l1_from_micro_pi[l1_lens[l0_lens[i]]] += pi[i];
        }
    }
    let h_l1_micro: f64 = l1_from_micro_pi
        .iter()
        .filter(|&&p| p > 0.0)
        .map(|&p| -p * p.ln())
        .sum();

    // Compute max possible entropy for reference
    let h_max_l0 = (l0_macro_n as f64).ln();
    let h_max_l1 = if l1_macro_n >= 2 {
        (l1_macro_n as f64).ln()
    } else {
        0.0
    };

    println!("KEY_MI093 seed={} scale={} l0_macro_n={} l1_macro_n={} h_l0={:.6} h_max_l0={:.6} h_l1={:.6} h_max_l1={:.6} mi_micro_l0={:.6} mi_l0_l1={:.6} mi_micro_l1={:.6} l0_frob={:.6} l1_frob={:.6}",
        seed, n, l0_macro_n, l1_macro_n,
        h_l0, h_max_l0, h_l1, h_max_l1,
        h_l0,          // MI(micro, L0) = H(L0) since partition is deterministic
        mi_l0_l1,      // MI(L0, L1) = H(L1) since partition is deterministic
        h_l1_micro,    // MI(micro, L1) = H(L1) under micro pi (should equal h_l1 if pi consistent)
        l0_frob, l1_frob);

    // Fraction of entropy preserved at each level
    // All measured under micro pi (the true stationary distribution)
    let frac_l0 = if h_max_l0 > 0.0 { h_l0 / h_max_l0 } else { 0.0 };
    let frac_l1_of_max = if h_max_l1 > 0.0 {
        h_l1_micro / h_max_l1
    } else {
        0.0
    };
    let frac_chain = if h_l0 > 0.0 { h_l1_micro / h_l0 } else { 0.0 }; // L1 entropy / L0 entropy

    println!("KEY_MI093_SUMMARY seed={} scale={} l0_n={} l1_n={} h_l0={:.6} h_l1={:.6} frac_l0={:.4} frac_l1={:.4} frac_chain={:.4} l0_frob={:.6} l1_frob={:.6}",
        seed, n, l0_macro_n, l1_macro_n,
        h_l0, h_l1_micro, frac_l0, frac_l1_of_max, frac_chain, l0_frob, l1_frob);
}

// ========== EXP-094: Phase 1 Property Revisit ==========
//
// Systematically tests 6 Phase 1 emergent properties on Phase 2 evolved
// non-rank-1 macro kernels at all 3 levels of the k=8 three-level ladder:
//   1. Chirality (sigma)     2. Temporal MI     3. Spectral lines
//   4. 1D locality           5. DPI cascade     6. Route mismatch

fn run_exp_094(seed: u64, scale: usize) {
    let n = scale.max(8);
    println!(
        "\n=== EXP-094 Phase 1 Property Revisit (seed={}, scale={}) ===",
        seed, n
    );

    // --- Level 0: Run dynamics with k=8 (same config as EXP-090) ---
    let ln_n = (n as f64).ln();
    let budget_init = n as f64 * ln_n;
    let config_l0 = DynamicsConfig {
        n,
        p_traj: 0.90,
        p_p1: 0.03,
        p_p2: 0.03,
        p_p4: 0.01,
        p_p5: 0.01,
        p_p6: 0.02,
        budget_rate: ln_n * 0.01,
        budget_init,
        p1_strength: 0.1,
        p2_flips: (n / 8).max(1),
        min_row_entropy: 0.1 * ln_n,
        max_self_loop: 1.0 - 1.0 / n as f64,
        protocol_cycle_len: 100,
        total_steps: n * 2000,
        obs_interval: n * 200,
        tau_alpha: 0.5,
        budget_cap: budget_init,
        n_clusters: 8,
        pica: PicaConfig::none(),
        seed,
    };

    let trace_l0 = six_dynamics::run_dynamics(&config_l0);
    let evolved_kernel = &trace_l0.final_kernel;

    // --- L0 macro kernel extraction (k=8) ---
    let l0_lens = six_dynamics::spectral::spectral_partition(evolved_kernel, 8);
    let l0_macro_n = six_dynamics::spectral::n_clusters(&l0_lens);
    let l0_gap = evolved_kernel.spectral_gap();
    let l0_tau = six_dynamics::observe::adaptive_tau(l0_gap, 0.5);
    let l0_ktau = helpers::matrix_power(evolved_kernel, l0_tau);
    let l0_macro = helpers::build_macro_from_ktau(&l0_ktau.kernel, &l0_lens, l0_macro_n);
    let l0_frob = six_dynamics::observe::frob_from_rank1(&l0_macro);

    // --- Measure 6 properties at L0 ---
    let l0_pi = l0_macro.stationary(10000, 1e-12);
    let l0_sigma = six_primitives_core::substrate::path_reversal_asymmetry(&l0_macro, &l0_pi, 10);
    let l0_mi = compute_mi(&l0_macro);
    let l0_eigs = six_dynamics::spectral::full_eigenvalues(&l0_macro);
    let l0_loc = six_dynamics::spectral::spectral_locality(&l0_macro);
    let l0_rm = helpers::fast_mean_rm(&l0_ktau.kernel, &l0_lens, l0_macro_n, &l0_macro);
    let l0_macro_gap = l0_macro.spectral_gap();

    let l0_eigs_str: Vec<String> = l0_eigs.iter().map(|e| format!("{:.6}", e)).collect();
    println!("KEY_P094_LEVEL seed={} scale={} level=0 macro_n={} frob={:.6} sigma={:.6} mi={:.6} gap={:.6} rm={:.6} locality={:.4} eigs=[{}]",
        seed, n, l0_macro_n, l0_frob, l0_sigma, l0_mi, l0_macro_gap, l0_rm, l0_loc, l0_eigs_str.join(","));
    let l0_diag = macro_diagnostics(&l0_macro);
    println!("KEY_P094_DIAG seed={} scale={} level=0 min_pi={:.8} h_pi={:.6} max_kii={:.8} n_absorb={} n_capped={} db_max={:.8} db_l1={:.8}",
        seed, n, l0_diag.min_pi, l0_diag.h_pi, l0_diag.max_self_loop, l0_diag.n_absorbing, l0_diag.n_capped, l0_diag.db_max, l0_diag.db_l1);
    let l0_unif = uniform_diagnostics(&l0_macro);
    println!("KEY_P094_UNIF seed={} scale={} level=0 sigma_u={:.6} mi_u={:.6} loc_u={:.4} db_u_max={:.6} db_u_l1={:.6} max_asym={:.6}",
        seed, n, l0_unif.sigma_unif, l0_unif.mi_unif, l0_unif.locality_unif, l0_unif.db_unif_max, l0_unif.db_unif_l1, l0_unif.max_asym);
    let (l0_cyc_mean, l0_cyc_max, l0_n_chiral) =
        six_primitives_core::substrate::cycle_chirality(&l0_macro, 0.01);
    let l0_frob_asym = six_primitives_core::substrate::frobenius_asymmetry(&l0_macro);
    let (l0_trans_ep, l0_n_trans) = six_primitives_core::substrate::transient_ep(&l0_macro);
    println!("KEY_P094_CHIRAL seed={} scale={} level=0 cyc_mean={:.6} cyc_max={:.6} n_chiral={} frob_asym={:.6} trans_ep={:.6} n_trans={}",
        seed, n, l0_cyc_mean, l0_cyc_max, l0_n_chiral, l0_frob_asym, l0_trans_ep, l0_n_trans);

    if l0_macro_n < 3 {
        println!(
            "KEY_P094_SKIP seed={} scale={} reason=l0_macro_n={}",
            seed, n, l0_macro_n
        );
        return;
    }

    // --- L1: k=4 partition of L0 macro ---
    let l1_lens = six_dynamics::spectral::spectral_partition(&l0_macro, 4);
    let l1_macro_n = six_dynamics::spectral::n_clusters(&l1_lens);
    if l1_macro_n < 2 {
        println!(
            "KEY_P094_SKIP seed={} scale={} reason=l1_macro_n={}",
            seed, n, l1_macro_n
        );
        return;
    }
    let l1_tau = six_dynamics::observe::adaptive_tau(l0_macro_gap, 0.5);
    let l1_ktau = helpers::matrix_power(&l0_macro, l1_tau);
    let l1_macro = helpers::build_macro_from_ktau(&l1_ktau.kernel, &l1_lens, l1_macro_n);
    let l1_frob = six_dynamics::observe::frob_from_rank1(&l1_macro);

    let l1_pi = l1_macro.stationary(10000, 1e-12);
    let l1_sigma = six_primitives_core::substrate::path_reversal_asymmetry(&l1_macro, &l1_pi, 10);
    let l1_mi = compute_mi(&l1_macro);
    let l1_eigs = six_dynamics::spectral::full_eigenvalues(&l1_macro);
    let l1_loc = six_dynamics::spectral::spectral_locality(&l1_macro);
    let l1_rm = helpers::fast_mean_rm(&l1_ktau.kernel, &l1_lens, l1_macro_n, &l1_macro);
    let l1_macro_gap = l1_macro.spectral_gap();

    let l1_eigs_str: Vec<String> = l1_eigs.iter().map(|e| format!("{:.6}", e)).collect();
    println!("KEY_P094_LEVEL seed={} scale={} level=1 macro_n={} frob={:.6} sigma={:.6} mi={:.6} gap={:.6} rm={:.6} locality={:.4} eigs=[{}]",
        seed, n, l1_macro_n, l1_frob, l1_sigma, l1_mi, l1_macro_gap, l1_rm, l1_loc, l1_eigs_str.join(","));
    let l1_diag = macro_diagnostics(&l1_macro);
    println!("KEY_P094_DIAG seed={} scale={} level=1 min_pi={:.8} h_pi={:.6} max_kii={:.8} n_absorb={} n_capped={} db_max={:.8} db_l1={:.8}",
        seed, n, l1_diag.min_pi, l1_diag.h_pi, l1_diag.max_self_loop, l1_diag.n_absorbing, l1_diag.n_capped, l1_diag.db_max, l1_diag.db_l1);
    let l1_unif = uniform_diagnostics(&l1_macro);
    println!("KEY_P094_UNIF seed={} scale={} level=1 sigma_u={:.6} mi_u={:.6} loc_u={:.4} db_u_max={:.6} db_u_l1={:.6} max_asym={:.6}",
        seed, n, l1_unif.sigma_unif, l1_unif.mi_unif, l1_unif.locality_unif, l1_unif.db_unif_max, l1_unif.db_unif_l1, l1_unif.max_asym);
    let (l1_cyc_mean, l1_cyc_max, l1_n_chiral) =
        six_primitives_core::substrate::cycle_chirality(&l1_macro, 0.01);
    let l1_frob_asym = six_primitives_core::substrate::frobenius_asymmetry(&l1_macro);
    let (l1_trans_ep, l1_n_trans) = six_primitives_core::substrate::transient_ep(&l1_macro);
    println!("KEY_P094_CHIRAL seed={} scale={} level=1 cyc_mean={:.6} cyc_max={:.6} n_chiral={} frob_asym={:.6} trans_ep={:.6} n_trans={}",
        seed, n, l1_cyc_mean, l1_cyc_max, l1_n_chiral, l1_frob_asym, l1_trans_ep, l1_n_trans);

    // --- L2: bisection of L1 macro ---
    let mut l2_sigma = 0.0;
    let mut l2_mi = 0.0;
    let mut l2_frob = 0.0;
    let mut l2_eigs_str_out = String::from("[1.000000]");
    let mut l2_loc = 1.0;
    let mut l2_rm = 0.0;
    let mut l2_macro_n = 0usize;

    if l1_macro_n >= 3 {
        let l2_lens = six_dynamics::spectral::spectral_partition(&l1_macro, 2);
        l2_macro_n = six_dynamics::spectral::n_clusters(&l2_lens);
        if l2_macro_n >= 2 {
            let l2_tau = six_dynamics::observe::adaptive_tau(l1_macro_gap, 0.5);
            let l2_ktau = helpers::matrix_power(&l1_macro, l2_tau);
            let l2_macro = helpers::build_macro_from_ktau(&l2_ktau.kernel, &l2_lens, l2_macro_n);
            l2_frob = six_dynamics::observe::frob_from_rank1(&l2_macro);

            let l2_pi = l2_macro.stationary(10000, 1e-12);
            l2_sigma =
                six_primitives_core::substrate::path_reversal_asymmetry(&l2_macro, &l2_pi, 10);
            l2_mi = compute_mi(&l2_macro);
            let l2_eigs = six_dynamics::spectral::full_eigenvalues(&l2_macro);
            l2_loc = six_dynamics::spectral::spectral_locality(&l2_macro);
            l2_rm = helpers::fast_mean_rm(&l2_ktau.kernel, &l2_lens, l2_macro_n, &l2_macro);

            let l2_eigs_s: Vec<String> = l2_eigs.iter().map(|e| format!("{:.6}", e)).collect();
            l2_eigs_str_out = format!("[{}]", l2_eigs_s.join(","));

            println!("KEY_P094_LEVEL seed={} scale={} level=2 macro_n={} frob={:.6} sigma={:.6} mi={:.6} gap={:.6} rm={:.6} locality={:.4} eigs={}",
                seed, n, l2_macro_n, l2_frob, l2_sigma, l2_mi, l2_macro.spectral_gap(), l2_rm, l2_loc, l2_eigs_str_out);
            let l2_diag = macro_diagnostics(&l2_macro);
            println!("KEY_P094_DIAG seed={} scale={} level=2 min_pi={:.8} h_pi={:.6} max_kii={:.8} n_absorb={} n_capped={} db_max={:.8} db_l1={:.8}",
                seed, n, l2_diag.min_pi, l2_diag.h_pi, l2_diag.max_self_loop, l2_diag.n_absorbing, l2_diag.n_capped, l2_diag.db_max, l2_diag.db_l1);
            let l2_unif = uniform_diagnostics(&l2_macro);
            println!("KEY_P094_UNIF seed={} scale={} level=2 sigma_u={:.6} mi_u={:.6} loc_u={:.4} db_u_max={:.6} db_u_l1={:.6} max_asym={:.6}",
                seed, n, l2_unif.sigma_unif, l2_unif.mi_unif, l2_unif.locality_unif, l2_unif.db_unif_max, l2_unif.db_unif_l1, l2_unif.max_asym);
            let (l2_cyc_mean, l2_cyc_max, l2_n_chiral) =
                six_primitives_core::substrate::cycle_chirality(&l2_macro, 0.01);
            let l2_frob_asym = six_primitives_core::substrate::frobenius_asymmetry(&l2_macro);
            let (l2_trans_ep, l2_n_trans) = six_primitives_core::substrate::transient_ep(&l2_macro);
            println!("KEY_P094_CHIRAL seed={} scale={} level=2 cyc_mean={:.6} cyc_max={:.6} n_chiral={} frob_asym={:.6} trans_ep={:.6} n_trans={}",
                seed, n, l2_cyc_mean, l2_cyc_max, l2_n_chiral, l2_frob_asym, l2_trans_ep, l2_n_trans);
        }
    }

    // --- DPI cascade check ---
    let dpi_01 = l1_sigma <= l0_sigma + 1e-10;
    let dpi_12 = l2_sigma <= l1_sigma + 1e-10;
    println!("KEY_P094_DPI seed={} scale={} sigma_l0={:.6} sigma_l1={:.6} sigma_l2={:.6} dpi_01={} dpi_12={} monotone={}",
        seed, n, l0_sigma, l1_sigma, l2_sigma, dpi_01, dpi_12, dpi_01 && dpi_12);

    // --- Summary ---
    println!("KEY_P094_SUMMARY seed={} scale={} l0_n={} l0_frob={:.4} l0_mi={:.6} l0_sigma={:.6} l0_loc={:.4} l1_n={} l1_frob={:.4} l1_mi={:.6} l1_sigma={:.6} l1_loc={:.4} l2_n={} l2_frob={:.4} l2_mi={:.6} l2_sigma={:.6} dpi={}",
        seed, n, l0_macro_n, l0_frob, l0_mi, l0_sigma, l0_loc,
        l1_macro_n, l1_frob, l1_mi, l1_sigma, l1_loc,
        l2_macro_n, l2_frob, l2_mi, l2_sigma, dpi_01 && dpi_12);
}

// ========== EXP-095: SBRC (Signed Boundary Repair Coupling) ==========
//
// Tests whether replacing the sign-blind coupling penalty with a signed version
// (only violations penalized, repairs free) increases sustained frob and/or P2
// acceptance rate. Optionally tests repair-biased proposal sampling.
// Fork of EXP-087 config with coupling_signed=true.

fn run_exp_095(seed: u64, scale: usize) {
    let n = scale.max(8);
    let ln_n = (n as f64).ln();
    let budget_init = n as f64 * ln_n;

    let biases = [0.0, 0.3, 0.6];

    for &bias in &biases {
        println!(
            "\n=== EXP-095 SBRC (seed={}, scale={}, bias={:.1}) ===",
            seed, n, bias
        );

        let config = DynamicsConfig {
            n,
            p_traj: 0.90,
            p_p1: 0.03,
            p_p2: 0.03,
            p_p4: 0.01,
            p_p5: 0.01,
            p_p6: 0.02,
            budget_rate: ln_n * 0.01,
            budget_init,
            p1_strength: 0.1,
            p2_flips: (n / 8).max(1),
            min_row_entropy: 0.1 * ln_n,
            max_self_loop: 1.0 - 1.0 / n as f64,
            protocol_cycle_len: 100,
            total_steps: n * 2000,
            obs_interval: n * 200,
            tau_alpha: 0.5,
            budget_cap: budget_init,
            n_clusters: 4,
            pica: PicaConfig::none(),
            seed,
        };

        let trace = six_dynamics::run_dynamics(&config);

        for snap in &trace.snapshots {
            let total_rv = snap.p2_repairs + snap.p2_violations;
            let repair_frac = if total_rv > 0 {
                snap.p2_repairs as f64 / total_rv as f64
            } else {
                0.0
            };
            let violation_frac = if total_rv > 0 {
                snap.p2_violations as f64 / total_rv as f64
            } else {
                0.0
            };
            println!("KEY_DYN seed={} scale={} exp=095 bias={:.1} step={} eff_gap={:.6} macro_n={} tau={} frob={:.6} macro_gap={:.6} sigma={:.6} gated={} budget={:.2} l1_frob={:.6} p1_acc={} p1_rej={} p2_acc={} p2_rej={} traj={} repairs={} violations={} repair_frac={:.4} violation_frac={:.4}",
                seed, n, bias, snap.step, snap.eff_gap, snap.macro_n, snap.tau,
                snap.frob_from_rank1, snap.macro_gap, snap.sigma, snap.gated_edges,
                snap.budget, snap.level1_frob,
                snap.p1_accepted, snap.p1_rejected,
                snap.p2_accepted, snap.p2_rejected, snap.traj_steps,
                snap.p2_repairs, snap.p2_violations,
                repair_frac, violation_frac);
        }

        let last = trace.snapshots.last().unwrap();
        let max_frob: f64 = trace
            .snapshots
            .iter()
            .map(|s| s.frob_from_rank1)
            .fold(0.0f64, f64::max);
        let p2_total = last.p2_accepted + last.p2_rejected;
        let p2_accept_rate = if p2_total > 0 {
            last.p2_accepted as f64 / p2_total as f64
        } else {
            0.0
        };
        let total_rv = last.p2_repairs + last.p2_violations;
        let repair_frac = if total_rv > 0 {
            last.p2_repairs as f64 / total_rv as f64
        } else {
            0.0
        };
        println!("KEY_DYNSUMMARY seed={} scale={} exp=095 bias={:.1} n_snaps={} final_frob={:.6} max_frob={:.6} final_macro_n={} final_gated={} final_budget={:.2} p2_accept_rate={:.4} p1_acc={} p2_acc={} blocks={} repairs={} violations={} repair_frac={:.4}",
            seed, n, bias, trace.snapshots.len(), last.frob_from_rank1, max_frob,
            last.macro_n, last.gated_edges, last.budget,
            p2_accept_rate,
            last.p1_accepted, last.p2_accepted, last.block_count,
            last.p2_repairs, last.p2_violations, repair_frac);
    }
}

// ========== EXP-096: Three-Level Ladder with SBRC ==========
//
// Fork of EXP-090 (three-level ladder, k=8 at L0) with SBRC coupling enabled.
// Tests whether signed coupling changes the ladder structure.
// Compares directly against EXP-090 baseline.

fn run_exp_096(seed: u64, scale: usize) {
    let n = scale.max(8);
    println!(
        "\n=== EXP-096 Three-Level Ladder + SBRC (seed={}, scale={}) ===",
        seed, n
    );

    // --- Level 0: Run dynamics with k=8 + SBRC coupling ---
    let ln_n = (n as f64).ln();
    let budget_init = n as f64 * ln_n;
    let config_l0 = DynamicsConfig {
        n,
        p_traj: 0.90,
        p_p1: 0.03,
        p_p2: 0.03,
        p_p4: 0.01,
        p_p5: 0.01,
        p_p6: 0.02,
        budget_rate: ln_n * 0.01,
        budget_init,
        p1_strength: 0.1,
        p2_flips: (n / 8).max(1),
        min_row_entropy: 0.1 * ln_n,
        max_self_loop: 1.0 - 1.0 / n as f64,
        protocol_cycle_len: 100,
        total_steps: n * 2000,
        obs_interval: n * 200,
        tau_alpha: 0.5,
        budget_cap: budget_init,
        n_clusters: 8,
        pica: PicaConfig::none(),
        seed,
    };

    let trace_l0 = six_dynamics::run_dynamics(&config_l0);
    let evolved_kernel = &trace_l0.final_kernel;

    // L0 dynamics summary
    let last = trace_l0.snapshots.last().unwrap();
    let max_frob_dyn: f64 = trace_l0
        .snapshots
        .iter()
        .map(|s| s.frob_from_rank1)
        .fold(0.0f64, f64::max);
    let p2_total = last.p2_accepted + last.p2_rejected;
    let p2_rate = if p2_total > 0 {
        last.p2_accepted as f64 / p2_total as f64
    } else {
        0.0
    };
    let total_rv = last.p2_repairs + last.p2_violations;
    let repair_frac = if total_rv > 0 {
        last.p2_repairs as f64 / total_rv as f64
    } else {
        0.0
    };
    println!("KEY_3LADDER_DYN seed={} scale={} max_dyn_frob={:.6} final_dyn_frob={:.6} p2_rate={:.4} repair_frac={:.4} budget={:.2}",
        seed, n, max_frob_dyn, last.frob_from_rank1, p2_rate, repair_frac, last.budget);

    // --- Level 0 → macro kernel extraction (k=8) ---
    let l0_lens = six_dynamics::spectral::spectral_partition(evolved_kernel, 8);
    let l0_macro_n = six_dynamics::spectral::n_clusters(&l0_lens);
    let l0_gap = evolved_kernel.spectral_gap();
    let l0_tau = six_dynamics::observe::adaptive_tau(l0_gap, 0.5);
    let l0_ktau = helpers::matrix_power(evolved_kernel, l0_tau);
    let l0_macro = helpers::build_macro_from_ktau(&l0_ktau.kernel, &l0_lens, l0_macro_n);
    let l0_frob = six_dynamics::observe::frob_from_rank1(&l0_macro);
    let l0_macro_gap = l0_macro.spectral_gap();

    println!("KEY_3LADDER_L0 seed={} scale={} exp=096 l0_macro_n={} l0_tau={} l0_frob={:.6} l0_gap={:.6} l0_macro_gap={:.6}",
        seed, n, l0_macro_n, l0_tau, l0_frob, l0_gap, l0_macro_gap);

    if l0_macro_n < 3 {
        println!(
            "KEY_3LADDER_L1 seed={} scale={} exp=096 SKIP l0_macro_n={}",
            seed, n, l0_macro_n
        );
        println!("KEY_3LADDER_SUMMARY seed={} scale={} exp=096 l0_n={} l0_frob={:.6} l1_n=0 l1_frob=0 l2_n=0 l2_frob=0",
            seed, n, l0_macro_n, l0_frob);
        return;
    }

    // --- Level 1: k=4 partition of L0 macro kernel ---
    let l1_lens = six_dynamics::spectral::spectral_partition(&l0_macro, 4);
    let l1_macro_n = six_dynamics::spectral::n_clusters(&l1_lens);

    if l1_macro_n < 2 {
        println!(
            "KEY_3LADDER_L1 seed={} scale={} exp=096 SKIP l1_macro_n={}",
            seed, n, l1_macro_n
        );
        println!("KEY_3LADDER_SUMMARY seed={} scale={} exp=096 l0_n={} l0_frob={:.6} l1_n=0 l1_frob=0 l2_n=0 l2_frob=0",
            seed, n, l0_macro_n, l0_frob);
        return;
    }

    let l1_tau = six_dynamics::observe::adaptive_tau(l0_macro_gap, 0.5);
    let l1_ktau = helpers::matrix_power(&l0_macro, l1_tau);
    let l1_macro = helpers::build_macro_from_ktau(&l1_ktau.kernel, &l1_lens, l1_macro_n);
    let l1_frob = six_dynamics::observe::frob_from_rank1(&l1_macro);
    let l1_macro_gap = l1_macro.spectral_gap();

    println!("KEY_3LADDER_L1 seed={} scale={} exp=096 l1_macro_n={} l1_tau={} l1_frob={:.6} l1_macro_gap={:.6}",
        seed, n, l1_macro_n, l1_tau, l1_frob, l1_macro_gap);

    if l1_macro_n < 3 {
        println!(
            "KEY_3LADDER_L2 seed={} scale={} exp=096 SKIP l1_macro_n={}",
            seed, n, l1_macro_n
        );
        println!("KEY_3LADDER_SUMMARY seed={} scale={} exp=096 l0_n={} l0_frob={:.6} l1_n={} l1_frob={:.6} l2_n=0 l2_frob=0",
            seed, n, l0_macro_n, l0_frob, l1_macro_n, l1_frob);
        return;
    }

    // --- Level 2: Bisection (k=2) of L1 macro kernel ---
    let l2_lens = six_dynamics::spectral::spectral_partition(&l1_macro, 2);
    let l2_macro_n = six_dynamics::spectral::n_clusters(&l2_lens);

    if l2_macro_n < 2 {
        println!(
            "KEY_3LADDER_L2 seed={} scale={} exp=096 SKIP l2_macro_n={}",
            seed, n, l2_macro_n
        );
        println!("KEY_3LADDER_SUMMARY seed={} scale={} exp=096 l0_n={} l0_frob={:.6} l1_n={} l1_frob={:.6} l2_n=0 l2_frob=0",
            seed, n, l0_macro_n, l0_frob, l1_macro_n, l1_frob);
        return;
    }

    let l2_tau = six_dynamics::observe::adaptive_tau(l1_macro_gap, 0.5);
    let l2_ktau = helpers::matrix_power(&l1_macro, l2_tau);
    let l2_macro = helpers::build_macro_from_ktau(&l2_ktau.kernel, &l2_lens, l2_macro_n);
    let l2_frob = six_dynamics::observe::frob_from_rank1(&l2_macro);

    println!(
        "KEY_3LADDER_L2 seed={} scale={} exp=096 l2_macro_n={} l2_tau={} l2_frob={:.6}",
        seed, n, l2_macro_n, l2_tau, l2_frob
    );

    println!("KEY_3LADDER_SUMMARY seed={} scale={} exp=096 l0_n={} l0_frob={:.6} l1_n={} l1_frob={:.6} l2_n={} l2_frob={:.6}",
        seed, n, l0_macro_n, l0_frob, l1_macro_n, l1_frob, l2_macro_n, l2_frob);
}

// ========== EXP-097: Property Diagnostics on SBRC-Evolved Kernels ==========
//
// Fork of EXP-094 property diagnostics but on SBRC-evolved kernels.
// Tests uniform-weighted MI, sigma_u, max_asym, spectral eigenvalues,
// absorbing state counts, and route mismatch at all 3 levels.

fn run_exp_097(seed: u64, scale: usize) {
    let n = scale.max(8);
    println!(
        "\n=== EXP-097 SBRC Property Diagnostics (seed={}, scale={}) ===",
        seed, n
    );

    // --- Level 0: Run dynamics with k=8 + SBRC ---
    let ln_n = (n as f64).ln();
    let budget_init = n as f64 * ln_n;
    let config_l0 = DynamicsConfig {
        n,
        p_traj: 0.90,
        p_p1: 0.03,
        p_p2: 0.03,
        p_p4: 0.01,
        p_p5: 0.01,
        p_p6: 0.02,
        budget_rate: ln_n * 0.01,
        budget_init,
        p1_strength: 0.1,
        p2_flips: (n / 8).max(1),
        min_row_entropy: 0.1 * ln_n,
        max_self_loop: 1.0 - 1.0 / n as f64,
        protocol_cycle_len: 100,
        total_steps: n * 2000,
        obs_interval: n * 200,
        tau_alpha: 0.5,
        budget_cap: budget_init,
        n_clusters: 8,
        pica: PicaConfig::none(),
        seed,
    };

    let trace_l0 = six_dynamics::run_dynamics(&config_l0);
    let evolved_kernel = &trace_l0.final_kernel;

    // Build 3-level ladder
    let l0_lens = six_dynamics::spectral::spectral_partition(evolved_kernel, 8);
    let l0_macro_n = six_dynamics::spectral::n_clusters(&l0_lens);
    let l0_gap = evolved_kernel.spectral_gap();
    let l0_tau = six_dynamics::observe::adaptive_tau(l0_gap, 0.5);
    let l0_ktau = helpers::matrix_power(evolved_kernel, l0_tau);
    let l0_macro = helpers::build_macro_from_ktau(&l0_ktau.kernel, &l0_lens, l0_macro_n);

    let l0_macro_gap = l0_macro.spectral_gap();

    // Diagnose L0
    diagnose_level("L0", &l0_macro, seed, n, l0_macro_n);

    if l0_macro_n < 3 {
        println!(
            "KEY_097_SKIP seed={} scale={} level=L1 reason=l0_macro_n={}",
            seed, n, l0_macro_n
        );
        return;
    }

    // Build L1
    let l1_lens = six_dynamics::spectral::spectral_partition(&l0_macro, 4);
    let l1_macro_n = six_dynamics::spectral::n_clusters(&l1_lens);
    if l1_macro_n < 2 {
        println!(
            "KEY_097_SKIP seed={} scale={} level=L1 reason=l1_macro_n={}",
            seed, n, l1_macro_n
        );
        return;
    }
    let l1_tau = six_dynamics::observe::adaptive_tau(l0_macro_gap, 0.5);
    let l1_ktau = helpers::matrix_power(&l0_macro, l1_tau);
    let l1_macro = helpers::build_macro_from_ktau(&l1_ktau.kernel, &l1_lens, l1_macro_n);
    let l1_macro_gap = l1_macro.spectral_gap();

    diagnose_level("L1", &l1_macro, seed, n, l1_macro_n);

    if l1_macro_n < 3 {
        println!(
            "KEY_097_SKIP seed={} scale={} level=L2 reason=l1_macro_n={}",
            seed, n, l1_macro_n
        );
        return;
    }

    // Build L2
    let l2_lens = six_dynamics::spectral::spectral_partition(&l1_macro, 2);
    let l2_macro_n = six_dynamics::spectral::n_clusters(&l2_lens);
    if l2_macro_n < 2 {
        println!(
            "KEY_097_SKIP seed={} scale={} level=L2 reason=l2_macro_n={}",
            seed, n, l2_macro_n
        );
        return;
    }
    let l2_tau = six_dynamics::observe::adaptive_tau(l1_macro_gap, 0.5);
    let l2_ktau = helpers::matrix_power(&l1_macro, l2_tau);
    let l2_macro = helpers::build_macro_from_ktau(&l2_ktau.kernel, &l2_lens, l2_macro_n);

    diagnose_level("L2", &l2_macro, seed, n, l2_macro_n);
}

fn diagnose_level(level: &str, k: &MarkovKernel, seed: u64, scale: usize, macro_n: usize) {
    use six_primitives_core::substrate::{
        cycle_chirality, frobenius_asymmetry, path_reversal_asymmetry, transient_ep,
    };

    let n = k.n;
    let frob = six_dynamics::observe::frob_from_rank1(k);
    let pi = k.stationary(10000, 1e-12);
    let sigma_pi = path_reversal_asymmetry(k, &pi, 10);

    // Uniform-weighted diagnostics
    let uniform: Vec<f64> = vec![1.0 / n as f64; n];
    let sigma_u = path_reversal_asymmetry(k, &uniform, 10);

    // Mutual information under uniform prior
    let mi_u = {
        let mut mi = 0.0;
        for i in 0..n {
            for j in 0..n {
                let p_ij = uniform[i] * k.kernel[i][j];
                if p_ij > 1e-30 {
                    let p_j: f64 = (0..n).map(|ii| uniform[ii] * k.kernel[ii][j]).sum();
                    if p_j > 1e-30 {
                        mi += p_ij * (p_ij / (uniform[i] * p_j)).ln();
                    }
                }
            }
        }
        mi
    };

    // Absorbing state count
    let n_absorb = (0..n).filter(|&i| k.kernel[i][i] > 1.0 - 1e-10).count();

    // Max asymmetry
    let max_asym = frobenius_asymmetry(k);

    // Chirality metrics
    let (cyc_mean, cyc_max, n_chiral) = cycle_chirality(k, 1e-10);
    let (trans_ep_val, n_trans) = transient_ep(k);

    // Eigenvalues
    let eigs = six_dynamics::spectral::full_eigenvalues(k);
    let eig_str: Vec<String> = eigs
        .iter()
        .take(macro_n.min(6))
        .map(|e| format!("{:.6}", e))
        .collect();

    println!("KEY_097_DIAG seed={} scale={} level={} macro_n={} frob={:.6} sigma_pi={:.6} sigma_u={:.6} mi_u={:.6} n_absorb={} max_asym={:.6} cyc_mean={:.6} cyc_max={:.6} n_chiral={} trans_ep={:.6} n_trans={} eigs=[{}]",
        seed, scale, level, macro_n, frob, sigma_pi, sigma_u, mi_u, n_absorb, max_asym,
        cyc_mean, cyc_max, n_chiral, trans_ep_val, n_trans, eig_str.join(","));
}

// ========== EXP-098: P6→P3 Mixer on Three-Level Ladder ==========

fn run_exp_098(seed: u64, scale: usize) {
    let n = scale.max(8);

    let strengths = [1.0_f64, 2.0, 4.0];

    for &strength in &strengths {
        println!(
            "\n=== EXP-098 Three-Level Ladder + P6→P3 Mixer (seed={}, scale={}, strength={}) ===",
            seed, n, strength
        );

        // --- Level 0: Run dynamics with k=8 + SBRC + mixer ---
        let ln_n = (n as f64).ln();
        let budget_init = n as f64 * ln_n;
        let config_l0 = DynamicsConfig {
            n,
            p_traj: 0.90,
            p_p1: 0.03,
            p_p2: 0.03,
            p_p4: 0.01,
            p_p5: 0.01,
            p_p6: 0.02,
            budget_rate: ln_n * 0.01,
            budget_init,
            p1_strength: 0.1,
            p2_flips: (n / 8).max(1),
            min_row_entropy: 0.1 * ln_n,
            max_self_loop: 1.0 - 1.0 / n as f64,
            protocol_cycle_len: 100,
            total_steps: n * 2000,
            obs_interval: n * 200,
            tau_alpha: 0.5,
            budget_cap: budget_init,
            n_clusters: 8,
            pica: PicaConfig::none(),
            seed,
        };

        let trace_l0 = six_dynamics::run_dynamics(&config_l0);
        let evolved_kernel = &trace_l0.final_kernel;

        // L0 dynamics summary
        let last = trace_l0.snapshots.last().unwrap();
        let max_frob_dyn: f64 = trace_l0
            .snapshots
            .iter()
            .map(|s| s.frob_from_rank1)
            .fold(0.0f64, f64::max);
        let p2_total = last.p2_accepted + last.p2_rejected;
        let p2_rate = if p2_total > 0 {
            last.p2_accepted as f64 / p2_total as f64
        } else {
            0.0
        };
        let total_rv = last.p2_repairs + last.p2_violations;
        let repair_frac = if total_rv > 0 {
            last.p2_repairs as f64 / total_rv as f64
        } else {
            0.0
        };
        println!("KEY_3LADDER_DYN seed={} scale={} exp=098 strength={} max_dyn_frob={:.6} final_dyn_frob={:.6} p2_rate={:.4} repair_frac={:.4} budget={:.2}",
            seed, n, strength, max_frob_dyn, last.frob_from_rank1, p2_rate, repair_frac, last.budget);

        // --- Level 0 → macro kernel extraction (k=8) ---
        let l0_lens = six_dynamics::spectral::spectral_partition(evolved_kernel, 8);
        let l0_macro_n = six_dynamics::spectral::n_clusters(&l0_lens);
        let l0_gap = evolved_kernel.spectral_gap();
        let l0_tau = six_dynamics::observe::adaptive_tau(l0_gap, 0.5);
        let l0_ktau = helpers::matrix_power(evolved_kernel, l0_tau);
        let l0_macro = helpers::build_macro_from_ktau(&l0_ktau.kernel, &l0_lens, l0_macro_n);
        let l0_frob = six_dynamics::observe::frob_from_rank1(&l0_macro);
        let l0_macro_gap = l0_macro.spectral_gap();

        println!("KEY_3LADDER_L0 seed={} scale={} exp=098 strength={} l0_macro_n={} l0_tau={} l0_frob={:.6} l0_gap={:.6} l0_macro_gap={:.6}",
            seed, n, strength, l0_macro_n, l0_tau, l0_frob, l0_gap, l0_macro_gap);

        if l0_macro_n < 3 {
            println!(
                "KEY_3LADDER_L1 seed={} scale={} exp=098 strength={} SKIP l0_macro_n={}",
                seed, n, strength, l0_macro_n
            );
            println!("KEY_3LADDER_SUMMARY seed={} scale={} exp=098 strength={} l0_n={} l0_frob={:.6} l1_n=0 l1_frob=0 l2_n=0 l2_frob=0",
                seed, n, strength, l0_macro_n, l0_frob);
            continue;
        }

        // --- Level 1: k=4 partition of L0 macro kernel ---
        let l1_lens = six_dynamics::spectral::spectral_partition(&l0_macro, 4);
        let l1_macro_n = six_dynamics::spectral::n_clusters(&l1_lens);

        if l1_macro_n < 2 {
            println!(
                "KEY_3LADDER_L1 seed={} scale={} exp=098 strength={} SKIP l1_macro_n={}",
                seed, n, strength, l1_macro_n
            );
            println!("KEY_3LADDER_SUMMARY seed={} scale={} exp=098 strength={} l0_n={} l0_frob={:.6} l1_n=0 l1_frob=0 l2_n=0 l2_frob=0",
                seed, n, strength, l0_macro_n, l0_frob);
            continue;
        }

        let l1_tau = six_dynamics::observe::adaptive_tau(l0_macro_gap, 0.5);
        let l1_ktau = helpers::matrix_power(&l0_macro, l1_tau);
        let l1_macro = helpers::build_macro_from_ktau(&l1_ktau.kernel, &l1_lens, l1_macro_n);
        let l1_frob = six_dynamics::observe::frob_from_rank1(&l1_macro);
        let l1_macro_gap = l1_macro.spectral_gap();

        println!("KEY_3LADDER_L1 seed={} scale={} exp=098 strength={} l1_macro_n={} l1_tau={} l1_frob={:.6} l1_macro_gap={:.6}",
            seed, n, strength, l1_macro_n, l1_tau, l1_frob, l1_macro_gap);

        if l1_macro_n < 3 {
            println!("KEY_3LADDER_SUMMARY seed={} scale={} exp=098 strength={} l0_n={} l0_frob={:.6} l1_n={} l1_frob={:.6} l2_n=0 l2_frob=0",
                seed, n, strength, l0_macro_n, l0_frob, l1_macro_n, l1_frob);
            continue;
        }

        // --- Level 2: bisection of L1 macro kernel ---
        let l2_lens = six_dynamics::spectral::spectral_partition(&l1_macro, 2);
        let l2_macro_n = six_dynamics::spectral::n_clusters(&l2_lens);

        if l2_macro_n < 2 {
            println!("KEY_3LADDER_SUMMARY seed={} scale={} exp=098 strength={} l0_n={} l0_frob={:.6} l1_n={} l1_frob={:.6} l2_n=0 l2_frob=0",
                seed, n, strength, l0_macro_n, l0_frob, l1_macro_n, l1_frob);
            continue;
        }

        let l2_tau = six_dynamics::observe::adaptive_tau(l1_macro_gap, 0.5);
        let l2_ktau = helpers::matrix_power(&l1_macro, l2_tau);
        let l2_macro = helpers::build_macro_from_ktau(&l2_ktau.kernel, &l2_lens, l2_macro_n);
        let l2_frob = six_dynamics::observe::frob_from_rank1(&l2_macro);

        println!("KEY_3LADDER_L2 seed={} scale={} exp=098 strength={} l2_macro_n={} l2_tau={} l2_frob={:.6}",
            seed, n, strength, l2_macro_n, l2_tau, l2_frob);

        println!("KEY_3LADDER_SUMMARY seed={} scale={} exp=098 strength={} l0_n={} l0_frob={:.6} l1_n={} l1_frob={:.6} l2_n={} l2_frob={:.6}",
            seed, n, strength, l0_macro_n, l0_frob, l1_macro_n, l1_frob, l2_macro_n, l2_frob);
    }
}

// ========== EXP-099: Full Diagnostic Comparison (uncoupled vs SBRC vs mixer) ==========

fn run_exp_099(seed: u64, scale: usize) {
    let n = scale.max(8);
    let ln_n = (n as f64).ln();
    let budget_init = n as f64 * ln_n;

    // 5 conditions: uncoupled, SBRC, mixer×{1,2,4}
    let conditions: Vec<(&str, bool, bool, f64)> = vec![
        ("uncoupled", false, false, 0.0),
        ("sbrc", true, false, 0.0),
        ("mixer_1", true, true, 1.0),
        ("mixer_2", true, true, 2.0),
        ("mixer_4", true, true, 4.0),
    ];

    for (label, _coupling, _mixer, _strength) in &conditions {
        println!(
            "\n=== EXP-099 Diagnostic Comparison (seed={}, scale={}, cond={}) ===",
            seed, n, label
        );

        let config_l0 = DynamicsConfig {
            n,
            p_traj: 0.90,
            p_p1: 0.03,
            p_p2: 0.03,
            p_p4: 0.01,
            p_p5: 0.01,
            p_p6: 0.02,
            budget_rate: ln_n * 0.01,
            budget_init,
            p1_strength: 0.1,
            p2_flips: (n / 8).max(1),
            min_row_entropy: 0.1 * ln_n,
            max_self_loop: 1.0 - 1.0 / n as f64,
            protocol_cycle_len: 100,
            total_steps: n * 2000,
            obs_interval: n * 200,
            tau_alpha: 0.5,
            budget_cap: budget_init,
            n_clusters: 8,
            pica: PicaConfig::none(),
            seed,
        };

        let trace_l0 = six_dynamics::run_dynamics(&config_l0);
        let evolved_kernel = &trace_l0.final_kernel;

        // L0 dynamics summary
        let last = trace_l0.snapshots.last().unwrap();
        let max_frob_dyn: f64 = trace_l0
            .snapshots
            .iter()
            .map(|s| s.frob_from_rank1)
            .fold(0.0f64, f64::max);
        let p2_total = last.p2_accepted + last.p2_rejected;
        let p2_rate = if p2_total > 0 {
            last.p2_accepted as f64 / p2_total as f64
        } else {
            0.0
        };
        let total_rv = last.p2_repairs + last.p2_violations;
        let repair_frac = if total_rv > 0 {
            last.p2_repairs as f64 / total_rv as f64
        } else {
            0.0
        };
        println!("KEY_099_DYN seed={} scale={} cond={} max_dyn_frob={:.6} p2_rate={:.4} repair_frac={:.4} budget={:.2}",
            seed, n, label, max_frob_dyn, p2_rate, repair_frac, last.budget);

        // --- Level 0 macro kernel (k=8) ---
        let l0_lens = six_dynamics::spectral::spectral_partition(evolved_kernel, 8);
        let l0_macro_n = six_dynamics::spectral::n_clusters(&l0_lens);
        let l0_gap = evolved_kernel.spectral_gap();
        let l0_tau = six_dynamics::observe::adaptive_tau(l0_gap, 0.5);
        let l0_ktau = helpers::matrix_power(evolved_kernel, l0_tau);
        let l0_macro = helpers::build_macro_from_ktau(&l0_ktau.kernel, &l0_lens, l0_macro_n);
        let l0_macro_gap = l0_macro.spectral_gap();

        println!(
            "KEY_099_DIAG seed={} scale={} cond={} level=L0 macro_n={}",
            seed, n, label, l0_macro_n
        );
        diagnose_level_099("L0", &l0_macro, seed, n, label, l0_macro_n);

        if l0_macro_n < 3 {
            continue;
        }

        // --- Level 1 (k=4) ---
        let l1_lens = six_dynamics::spectral::spectral_partition(&l0_macro, 4);
        let l1_macro_n = six_dynamics::spectral::n_clusters(&l1_lens);
        if l1_macro_n < 2 {
            continue;
        }
        let l1_tau = six_dynamics::observe::adaptive_tau(l0_macro_gap, 0.5);
        let l1_ktau = helpers::matrix_power(&l0_macro, l1_tau);
        let l1_macro = helpers::build_macro_from_ktau(&l1_ktau.kernel, &l1_lens, l1_macro_n);
        let l1_macro_gap = l1_macro.spectral_gap();

        diagnose_level_099("L1", &l1_macro, seed, n, label, l1_macro_n);

        if l1_macro_n < 3 {
            continue;
        }

        // --- Level 2 (bisection) ---
        let l2_lens = six_dynamics::spectral::spectral_partition(&l1_macro, 2);
        let l2_macro_n = six_dynamics::spectral::n_clusters(&l2_lens);
        if l2_macro_n < 2 {
            continue;
        }
        let l2_tau = six_dynamics::observe::adaptive_tau(l1_macro_gap, 0.5);
        let l2_ktau = helpers::matrix_power(&l1_macro, l2_tau);
        let l2_macro = helpers::build_macro_from_ktau(&l2_ktau.kernel, &l2_lens, l2_macro_n);

        diagnose_level_099("L2", &l2_macro, seed, n, label, l2_macro_n);
    }
}

fn diagnose_level_099(
    level: &str,
    k: &MarkovKernel,
    seed: u64,
    scale: usize,
    cond: &str,
    macro_n: usize,
) {
    use six_primitives_core::substrate::{
        cycle_chirality, frobenius_asymmetry, path_reversal_asymmetry, transient_ep,
    };

    let n = k.n;
    let frob = six_dynamics::observe::frob_from_rank1(k);
    let pi = k.stationary(10000, 1e-12);
    let sigma_pi = path_reversal_asymmetry(k, &pi, 10);

    // Uniform-weighted diagnostics
    let uniform: Vec<f64> = vec![1.0 / n as f64; n];
    let sigma_u = path_reversal_asymmetry(k, &uniform, 10);

    // MI under uniform prior
    let mi_u = {
        let mut mi = 0.0;
        for i in 0..n {
            for j in 0..n {
                let p_ij = uniform[i] * k.kernel[i][j];
                if p_ij > 1e-30 {
                    let p_j: f64 = (0..n).map(|ii| uniform[ii] * k.kernel[ii][j]).sum();
                    if p_j > 1e-30 {
                        mi += p_ij * (p_ij / (uniform[i] * p_j)).ln();
                    }
                }
            }
        }
        mi
    };

    // MI under pi
    let mi_pi = {
        let mut mi = 0.0;
        for i in 0..n {
            for j in 0..n {
                let p_ij = pi[i] * k.kernel[i][j];
                if p_ij > 1e-30 {
                    let p_j: f64 = (0..n).map(|ii| pi[ii] * k.kernel[ii][j]).sum();
                    if p_j > 1e-30 {
                        mi += p_ij * (p_ij / (pi[i] * p_j)).ln();
                    }
                }
            }
        }
        mi
    };

    let n_absorb = (0..n).filter(|&i| k.kernel[i][i] > 1.0 - 1e-10).count();
    let max_asym = frobenius_asymmetry(k);
    let (cyc_mean, cyc_max, n_chiral) = cycle_chirality(k, 1e-10);
    let (trans_ep_val, n_trans) = transient_ep(k);
    let gap = k.spectral_gap();
    let blocks = k.block_count();

    // Eigenvalues
    let eigs = six_dynamics::spectral::full_eigenvalues(k);
    let eig_str: Vec<String> = eigs
        .iter()
        .take(macro_n.min(8))
        .map(|e| format!("{:.6}", e))
        .collect();
    let n_nontrivial = eigs.iter().skip(1).filter(|&&e| e.abs() > 0.01).count();

    // Print macro kernel entries
    let entries: Vec<Vec<String>> = (0..n)
        .map(|i| {
            let row = &k.kernel[i];
            (0..n)
                .map(move |j| format!("{:.4}", row[j]))
                .collect::<Vec<_>>()
        })
        .collect();

    println!("KEY_099_DIAG seed={} scale={} cond={} level={} macro_n={} frob={:.6} gap={:.6} sigma_pi={:.6} sigma_u={:.6} mi_pi={:.6} mi_u={:.6} n_absorb={} blocks={} max_asym={:.6} cyc_mean={:.6} cyc_max={:.6} n_chiral={} trans_ep={:.6} n_trans={} n_nontrivial={} eigs=[{}]",
        seed, scale, cond, level, macro_n, frob, gap, sigma_pi, sigma_u, mi_pi, mi_u, n_absorb, blocks,
        max_asym, cyc_mean, cyc_max, n_chiral, trans_ep_val, n_trans, n_nontrivial, eig_str.join(","));
    println!(
        "KEY_099_MACRO seed={} scale={} cond={} level={} n={} entries={:?}",
        seed, scale, cond, level, macro_n, entries
    );
}

// ========== EXP-100: PICA Single-Cell Sweep ==========
//
// For each of the 13 action cells (A1-A13), enable ONLY that cell + baseline P2<-P4,
// run a 3-level ladder, and report full diagnostics. This reveals which cells have
// distinct effects on emergence.

fn run_exp_100(seed: u64, scale: usize, config_filter: Option<&str>) {
    let n = scale.max(8);
    let ln_n = (n as f64).ln();

    // Define all 13 action cells to test (each as (actor, informant, label))
    let cells: Vec<(usize, usize, &str)> = vec![
        (0, 0, "A1_P1-P1"), // history cooldown
        (0, 1, "A2_P1-P2"), // sparsity-guided
        (0, 2, "A3_P1-P3"), // RM rewrite
        (0, 3, "A4_P1-P4"), // sector boundary
        (0, 4, "A5_P1-P5"), // packaging-guided
        (0, 5, "A6_P1-P6"), // budget-gated
        (1, 0, "A7_P2-P1"), // protect rewrites
        (1, 1, "A8_P2-P2"), // flip cooldown
        (1, 2, "A9_P2-P3"), // RM-guided gating
        // A10: P2<-P4 is always baseline, skip as a test cell
        (1, 4, "A11_P2-P5"), // package-boundary
        (1, 5, "A12_P2-P6"), // SBRC penalty
        (2, 5, "A13_P3-P6"), // frob-modulated mixer
    ];

    // Baseline: only P2<-P4 (no extra cell)
    let baseline_pat = PicaConfig::baseline();
    let mut valid_labels: Vec<&str> = vec!["baseline"];
    valid_labels.extend(cells.iter().map(|(_, _, label)| *label));
    println!(
        "\n=== EXP-100 PICA Single-Cell Sweep (seed={}, scale={}) ===",
        seed, n
    );
    let mut matched = false;

    // Run baseline first
    if config_filter.is_none() || config_filter == Some("baseline") {
        matched = true;
        run_exp_100_single(seed, n, ln_n, &baseline_pat, "baseline", "EXP-100");
    }

    // Then each cell individually (on top of baseline)
    for &(actor, informant, label) in &cells {
        if let Some(f) = config_filter {
            if label != f {
                continue;
            }
        }
        matched = true;
        let pica = PicaConfig::baseline().with_cell(actor, informant);
        run_exp_100_single(seed, n, ln_n, &pica, label, "EXP-100");
    }

    if let Some(f) = config_filter {
        if !matched {
            eprintln!("ERROR: --config '{}' is not valid for EXP-100", f);
            eprintln!("       valid options: {}", valid_labels.join(", "));
            std::process::exit(2);
        }
    }
}

#[derive(Clone, Debug, Serialize)]
struct DiscoveryGradeContext {
    step_index: usize,
    protocol_step_id: String,
    level_id: String,
    resolution_id: String,
    closure_id: String,
    lens_id: String,
    k: usize,
    macro_n: usize,
    macro_gap: Option<f64>,
    frob: Option<f64>,
    sigma_pi: Option<f64>,
    step_entropy: Option<f64>,
    max_asym: Option<f64>,
}

#[derive(Clone, Debug, Serialize)]
struct DiscoveryGradeRow {
    trajectory_id: String,
    step_index: usize,
    protocol_step_id: String,
    level_id: String,
    resolution_id: String,
    closure_id: String,
    lens_id: String,
    observation_label: String,
    macrostate_label: String,
    observation_payload: serde_json::Value,
}

#[derive(Clone, Debug, Serialize)]
struct DiscoveryGradeExport {
    trajectory_count: usize,
    contexts: Vec<DiscoveryGradeContext>,
    rows: Vec<DiscoveryGradeRow>,
}

fn emit_discovery_grade_export(
    evolved: &MarkovKernel,
    scan: &[six_dynamics::audit::ScaleScanEntry],
    seed: u64,
    tau: usize,
    label: &str,
    lens_source: &str,
) {
    let context_specs: Vec<(usize, &six_dynamics::audit::ScaleScanEntry)> = scan
        .iter()
        .enumerate()
        .filter(|(_, entry)| entry.k >= 2)
        .collect();
    if context_specs.is_empty() {
        return;
    }

    let trajectory_count = 24usize;
    let level_id = "level_l0".to_string();
    let mut contexts: Vec<DiscoveryGradeContext> = Vec::new();
    let mut rows: Vec<DiscoveryGradeRow> = Vec::new();

    let starts: Vec<usize> = (0..trajectory_count)
        .map(|idx| idx % evolved.n)
        .collect();
    let sampled_trajs: Vec<Vec<usize>> = starts
        .iter()
        .enumerate()
        .map(|(idx, start)| evolved.sample_trajectory(*start, tau, seed + 50_000 + idx as u64))
        .collect();

    for (step_index, entry) in context_specs {
        let partition = six_dynamics::spectral::spectral_partition(evolved, entry.k);
        let macro_n = six_dynamics::spectral::n_clusters(&partition);
        if macro_n < 2 {
            continue;
        }
        let protocol_step_id = format!("protocol_pica_multiscale_scan_step_{}", step_index);
        let resolution_id = format!("resolution_k_{}", entry.k);
        let closure_id = format!("closure_{}_k_{}", label, entry.k);
        let lens_id = format!("lens_{}_k_{}", lens_source.to_lowercase(), entry.k);
        let packaging_closure_id = format!("closure_{}_pkg_k_{}", label, entry.k);
        let packaging_lens_id = format!("lens_p5_k_{}", entry.k);
        let packaging = six_dynamics::pica::p5_cells::p5_from_p4(evolved, &partition, entry.k);
        let packaging_macro_n = packaging.iter().copied().max().unwrap_or(0) + 1;
        contexts.push(DiscoveryGradeContext {
            step_index,
            protocol_step_id: protocol_step_id.clone(),
            level_id: level_id.clone(),
            resolution_id: resolution_id.clone(),
            closure_id: closure_id.clone(),
            lens_id: lens_id.clone(),
            k: entry.k,
            macro_n,
            macro_gap: entry.macro_gap,
            frob: entry.frob,
            sigma_pi: entry.sigma_pi,
            step_entropy: entry.step_entropy,
            max_asym: entry.max_asym,
        });
        if packaging_macro_n >= 2 {
            contexts.push(DiscoveryGradeContext {
                step_index,
                protocol_step_id: protocol_step_id.clone(),
                level_id: level_id.clone(),
                resolution_id: resolution_id.clone(),
                closure_id: packaging_closure_id.clone(),
                lens_id: packaging_lens_id.clone(),
                k: entry.k,
                macro_n: packaging_macro_n,
                macro_gap: entry.macro_gap,
                frob: entry.frob,
                sigma_pi: entry.sigma_pi,
                step_entropy: entry.step_entropy,
                max_asym: entry.max_asym,
            });
        }
        for (traj_index, traj) in sampled_trajs.iter().enumerate() {
            let final_state = traj.last().copied().unwrap_or(0);
            let start_state = traj.first().copied().unwrap_or(0);
            let macro_group = partition[final_state];
            rows.push(DiscoveryGradeRow {
                trajectory_id: format!("traj_{:04}", traj_index),
                step_index,
                protocol_step_id: protocol_step_id.clone(),
                level_id: level_id.clone(),
                resolution_id: resolution_id.clone(),
                closure_id: closure_id.clone(),
                lens_id: lens_id.clone(),
                observation_label: format!("group_{}", macro_group),
                macrostate_label: format!("group_{}", macro_group),
                observation_payload: serde_json::json!({
                    "context_k": entry.k,
                    "macro_group": macro_group,
                    "macro_n": macro_n,
                    "start_state": start_state,
                    "final_state": final_state,
                    "tau": tau,
                    "trajectory_length": traj.len().saturating_sub(1),
                    "macro_gap": entry.macro_gap,
                    "frob": entry.frob,
                    "sigma_pi": entry.sigma_pi,
                    "step_entropy": entry.step_entropy,
                    "max_asym": entry.max_asym
                }),
            });
            if packaging_macro_n >= 2 {
                let packaging_group = packaging[final_state];
                rows.push(DiscoveryGradeRow {
                    trajectory_id: format!("traj_{:04}", traj_index),
                    step_index,
                    protocol_step_id: protocol_step_id.clone(),
                    level_id: level_id.clone(),
                    resolution_id: resolution_id.clone(),
                    closure_id: packaging_closure_id.clone(),
                    lens_id: packaging_lens_id.clone(),
                    observation_label: format!("package_{}", packaging_group),
                    macrostate_label: format!("package_{}", packaging_group),
                    observation_payload: serde_json::json!({
                        "context_k": entry.k,
                        "macro_group": packaging_group,
                        "macro_n": packaging_macro_n,
                        "start_state": start_state,
                        "final_state": final_state,
                        "tau": tau,
                        "trajectory_length": traj.len().saturating_sub(1),
                        "macro_gap": entry.macro_gap,
                        "frob": entry.frob,
                        "sigma_pi": entry.sigma_pi,
                        "step_entropy": entry.step_entropy,
                        "max_asym": entry.max_asym,
                        "packaging_source": "p5_from_p4"
                    }),
                });
            }
        }
    }

    if contexts.is_empty() || rows.is_empty() {
        return;
    }
    let export = DiscoveryGradeExport {
        trajectory_count,
        contexts,
        rows,
    };
    if let Ok(payload) = serde_json::to_string(&export) {
        println!("KEY_DISCOVERY_GRADE_JSON {}", payload);
    }
}

fn run_exp_100_single(seed: u64, n: usize, ln_n: f64, pica: &PicaConfig, label: &str, exp_id: &str) {
    use six_primitives_core::substrate::{
        cycle_chirality, frobenius_asymmetry, path_reversal_asymmetry, transient_ep,
    };

    let budget_init = n as f64 * ln_n;

    let config = DynamicsConfig {
        n,
        p_traj: 0.90,
        p_p1: 0.03,
        p_p2: 0.03,
        p_p4: 0.01,
        p_p5: 0.01,
        p_p6: 0.02,
        budget_rate: ln_n * 0.01,
        budget_init,
        p1_strength: 0.1,
        p2_flips: (n / 8).max(1),
        min_row_entropy: 0.1 * ln_n,
        max_self_loop: 1.0 - 1.0 / n as f64,
        protocol_cycle_len: 100,
        total_steps: n * 2000,
        obs_interval: n * 200,
        tau_alpha: 0.5,
        budget_cap: budget_init,
        n_clusters: 8,
        pica: pica.clone_for_macro(), // clone_for_macro gives shorter intervals, use regular
        seed,
    };

    // Use PICA config as-is (line 7224 already set config.pica = pica.clone_for_macro()).
    // Previous code reset config.pica to baseline() and only copied enabled flags,
    // which discarded lens_selector, p3_p4_sector_boost, and all per-cell parameters.
    let trace = six_dynamics::run_dynamics(&config);
    let evolved = &trace.final_kernel;
    let last = trace.snapshots.last().unwrap();
    let max_frob_dyn: f64 = trace
        .snapshots
        .iter()
        .map(|s| s.frob_from_rank1)
        .fold(0.0f64, f64::max);
    let p2_total = last.p2_accepted + last.p2_rejected;
    let p2_rate = if p2_total > 0 {
        last.p2_accepted as f64 / p2_total as f64
    } else {
        0.0
    };
    let total_rv = last.p2_repairs + last.p2_violations;
    let repair_frac = if total_rv > 0 {
        last.p2_repairs as f64 / total_rv as f64
    } else {
        0.0
    };

    println!("KEY_100_DYN seed={} scale={} cell={} enabled=[{}] max_dyn_frob={:.6} p2_rate={:.4} repair_frac={:.4} budget={:.2} p1_acc={} p1_rej={} p2_acc={} p2_rej={}",
        seed, n, label, config.pica.enabled_labels().join(","), max_frob_dyn, p2_rate, repair_frac,
        last.budget, last.p1_accepted, last.p1_rejected, last.p2_accepted, last.p2_rejected);

    // Lens metadata (P4-row cell selection)
    // source encoding: 2=P3, 3=P4, 4=P5, 5=P6 (informant index in PICA)
    let lens_source = trace.final_pica_state_lens_source.unwrap_or(3);
    let lens_name = |s: u8| -> &str {
        match s {
            2 => "P3",
            3 => "P4",
            4 => "P5",
            5 => "P6",
            _ => "??",
        }
    };
    let lens_q_str: String = trace
        .final_pica_state_lens_qualities
        .iter()
        .map(|(src, score)| format!("{}={:.6}", lens_name(*src), score))
        .collect::<Vec<_>>()
        .join(",");
    println!(
        "KEY_100_LENS seed={} scale={} cell={} source={} qualities=[{}]",
        seed,
        n,
        label,
        lens_name(lens_source),
        lens_q_str
    );

    // Packaging metadata (P5-row cell selection)
    let pkg_source = trace.final_pica_state_packaging_source.unwrap_or(0);
    let pkg_q_str: String = trace
        .final_pica_state_packaging_qualities
        .iter()
        .map(|(src, score)| format!("{}={:.6}", lens_name(*src), score))
        .collect::<Vec<_>>()
        .join(",");
    println!(
        "KEY_100_PKG seed={} scale={} cell={} source={} qualities=[{}]",
        seed,
        n,
        label,
        if pkg_source > 0 {
            lens_name(pkg_source)
        } else {
            "none"
        },
        pkg_q_str
    );

    // Active tau
    let tau_str = match trace.final_pica_state_active_tau {
        Some(t) => format!("pica:{}", t),
        None => "spectral".to_string(),
    };
    println!(
        "KEY_100_TAU seed={} scale={} cell={} tau={}",
        seed, n, label, tau_str
    );

    // Macro kernel analysis (k=8)
    let lens = six_dynamics::spectral::spectral_partition(evolved, 8);
    let macro_n = six_dynamics::spectral::n_clusters(&lens);
    if macro_n < 2 {
        println!(
            "KEY_100_MACRO seed={} scale={} cell={} level=L0 macro_n={} frob=0.0",
            seed, n, label, macro_n
        );
        return;
    }

    // Use dynamics-produced tau (from A18/PICA) when available; fall back to
    // fresh spectral computation.  This keeps headline metrics consistent with
    // the multi_scale_scan (which already uses last.tau).
    let tau = match trace.final_pica_state_active_tau {
        Some(t) => t,
        None => {
            let gap = evolved.spectral_gap();
            six_dynamics::observe::adaptive_tau(gap, 0.5)
        }
    };
    let ktau = helpers::matrix_power(evolved, tau);
    let macro_k = helpers::build_macro_from_ktau(&ktau.kernel, &lens, macro_n);

    let frob = six_dynamics::observe::frob_from_rank1(&macro_k);
    let pi = macro_k.stationary(10000, 1e-12);
    let sigma_pi = path_reversal_asymmetry(&macro_k, &pi, 10);
    let uniform: Vec<f64> = vec![1.0 / macro_n as f64; macro_n];
    let sigma_u = six_dynamics::audit::finite_horizon_sigma(&macro_k, &uniform, 10);
    let max_asym = frobenius_asymmetry(&macro_k);
    let (cyc_mean, cyc_max, n_chiral) = cycle_chirality(&macro_k, 1e-10);
    let (trans_ep_val, n_trans) = transient_ep(&macro_k);
    let n_absorb = (0..macro_n)
        .filter(|&i| macro_k.kernel[i][i] > 1.0 - 1e-10)
        .count();
    let macro_gap = macro_k.spectral_gap();

    // Print macro kernel entries
    let entries: Vec<Vec<String>> = (0..macro_n)
        .map(|i| {
            (0..macro_n)
                .map(|j| format!("{:.4}", macro_k.kernel[i][j]))
                .collect()
        })
        .collect();

    println!("KEY_100_MACRO seed={} scale={} cell={} level=L0 macro_n={} frob={:.6} gap={:.6} sigma_pi={:.6} sigma_u={:.6} max_asym={:.6} cyc_mean={:.6} cyc_max={:.6} n_chiral={} trans_ep={:.6} n_trans={} n_absorb={} entries={:?}",
        seed, n, label, macro_n, frob, macro_gap, sigma_pi, sigma_u, max_asym, cyc_mean, cyc_max, n_chiral, trans_ep_val, n_trans, n_absorb, entries);

    // Commutator diagnostics
    let comms = six_dynamics::pica::commutator::all_commutators(evolved, seed);
    let comm_str: Vec<String> = comms
        .iter()
        .map(|(name, val)| format!("{}={:.6}", name, val))
        .collect();
    println!(
        "KEY_100_COMM seed={} scale={} cell={} {}",
        seed,
        n,
        label,
        comm_str.join(" ")
    );
    let comm_rows = six_dynamics::pica::commutator::all_commutator_records(evolved, seed);
    if let Ok(payload) = serde_json::to_string(&serde_json::json!({ "rows": comm_rows })) {
        println!("KEY_PICA_COMMUTATOR_CATALOG_JSON {}", payload);
    }

    // Micro sigma at same timescale (K^tau) — used by B12 diagnostic and audit sigma_ratio
    let micro_sigma_tau = path_reversal_asymmetry(&ktau, &evolved.stationary(10000, 1e-12), 10);

    // Group B diagnostic cells (computed on evolved micro kernel)
    {
        use six_dynamics::pica::diag_cells;

        // B1: multi-scale RM
        let b1 = diag_cells::b1_multiscale_rm_with_ktau(evolved, &lens, tau, &ktau);
        let b1_str: Vec<String> = b1
            .values
            .iter()
            .map(|(k, v)| format!("{}={:.6}", k, v))
            .collect();

        // B2: sector-resolved RM
        let b2 = diag_cells::b2_sector_rm_with_ktau(evolved, &lens, &ktau);
        let b2_str: Vec<String> = b2
            .values
            .iter()
            .map(|(k, v)| format!("{}={:.6}", k, v))
            .collect();

        // B3: packaging-lens RM
        let b3 = diag_cells::b3_packaging_rm_with_ktau(evolved, &lens, &ktau);
        let b3_str: Vec<String> = b3
            .values
            .iter()
            .map(|(k, v)| format!("{}={:.6}", k, v))
            .collect();

        // B4: RM-based partition
        let b4 = diag_cells::b4_rm_partition(evolved, &lens, tau, 4);
        let b4_str: Vec<String> = b4
            .values
            .iter()
            .map(|(k, v)| format!("{}={:.6}", k, v))
            .collect();

        // B5: hierarchical sub-sectors
        let b5 = diag_cells::b5_hierarchical(evolved, &lens);
        let b5_str: Vec<String> = b5
            .values
            .iter()
            .map(|(k, v)| format!("{}={:.6}", k, v))
            .collect();

        // B6: package-derived partition
        let b6 = diag_cells::b6_package_partition(evolved, &lens);
        let b6_str: Vec<String> = b6
            .values
            .iter()
            .map(|(k, v)| format!("{}={:.6}", k, v))
            .collect();

        // B7: EP-flow partition
        let b7 = diag_cells::b7_ep_partition(evolved, 4);
        let b7_str: Vec<String> = b7
            .values
            .iter()
            .map(|(k, v)| format!("{}={:.6}", k, v))
            .collect();

        // B8: RM-similarity grouping
        let b8 = diag_cells::b8_rm_grouping(evolved, &lens, tau);
        let b8_str: Vec<String> = b8
            .values
            .iter()
            .map(|(k, v)| format!("{}={:.6}", k, v))
            .collect();

        // B9: per-sector packaging
        let b9 = diag_cells::b9_per_sector_packaging(evolved, &lens);
        let b9_str: Vec<String> = b9
            .values
            .iter()
            .map(|(k, v)| format!("{}={:.6}", k, v))
            .collect();

        // B10: EP-similarity grouping
        let b10 = diag_cells::b10_ep_grouping(evolved);
        let b10_str: Vec<String> = b10
            .values
            .iter()
            .map(|(k, v)| format!("{}={:.6}", k, v))
            .collect();

        // B11: sector-resolved audit
        let b11 = diag_cells::b11_sector_audit(evolved, &lens);
        let b11_str: Vec<String> = b11
            .values
            .iter()
            .map(|(k, v)| format!("{}={:.6}", k, v))
            .collect();

        // B12: meta-audit — DPI on same time scale (K^tau vs macro kernel)
        let b12 = diag_cells::b12_meta_audit(micro_sigma_tau, sigma_pi);
        let b12_str: Vec<String> = b12
            .values
            .iter()
            .map(|(k, v)| format!("{}={:.6}", k, v))
            .collect();

        println!("KEY_100_DIAG seed={} scale={} cell={} B1=[{}] B2=[{}] B3=[{}] B4=[{}] B5=[{}] B6=[{}] B7=[{}] B8=[{}] B9=[{}] B10=[{}] B11=[{}] B12=[{}]",
            seed, n, label,
            b1_str.join(","), b2_str.join(","), b3_str.join(","),
            b4_str.join(","), b5_str.join(","), b6_str.join(","),
            b7_str.join(","), b8_str.join(","), b9_str.join(","),
            b10_str.join(","), b11_str.join(","), b12_str.join(","));
    }

    // Rich audit JSON record (end-of-run, includes multi-scale scan)
    {
        let pch = six_dynamics::audit::pica_config_hash(&config.pica);
        let mut rec = six_dynamics::audit::lite_from_snapshot(last, seed, n, pch);
        rec.tier = "rich".into();
        rec.exp_id = Some(exp_id.into());
        rec.config_name = Some(label.into());
        rec.git_sha = Some(env!("GIT_SHA").into());
        rec.pica_config = serde_json::to_value(&config.pica).ok();

        // Override snapshot macro fields with recomputed post-hoc values.
        // lite_from_snapshot populates from the dynamics-loop observation (PICA partition),
        // but the rest of this record uses a fresh spectral partition. Override to keep
        // the record internally consistent.
        let san = |v: f64| -> Option<f64> {
            if v.is_finite() {
                Some(v)
            } else {
                None
            }
        };
        rec.macro_n = Some(macro_n);
        rec.tau = Some(tau);
        rec.frob_from_rank1 = san(frob);
        rec.macro_gap = san(macro_gap);
        rec.sigma = san(sigma_pi);

        // Standard-tier: event counters
        rec.partition_flip_count = Some(trace.partition_flip_count);
        rec.packaging_flip_count = Some(trace.packaging_flip_count);
        rec.tau_change_count = Some(trace.tau_change_count);
        rec.last_partition_flip_step = if trace.last_partition_flip_step > 0 {
            Some(trace.last_partition_flip_step)
        } else {
            None
        };
        rec.last_packaging_flip_step = if trace.last_packaging_flip_step > 0 {
            Some(trace.last_packaging_flip_step)
        } else {
            None
        };
        rec.last_tau_change_step = if trace.last_tau_change_step > 0 {
            Some(trace.last_tau_change_step)
        } else {
            None
        };

        // Standard-tier: PICA metadata
        rec.lens_source = trace.final_pica_state_lens_source;
        rec.packaging_source = trace.final_pica_state_packaging_source;
        rec.active_tau = trace.final_pica_state_active_tau;
        rec.p6_rate_mult = Some(trace.final_pica_state_p6_rate_mult);
        rec.p6_cap_mult = Some(trace.final_pica_state_p6_cap_mult);

        // Standard-tier: partition stats
        if macro_n >= 2 {
            rec.partition_stats = Some(six_dynamics::audit::partition_stats(&lens));
        }
        if let Some(ref pkg) = trace.final_pica_state_packaging {
            rec.packaging_stats = Some(six_dynamics::audit::partition_stats(pkg));
        }

        // Standard-tier: cross-layer ratios (guarded division)
        rec.macro_gap_ratio = six_dynamics::audit::sanitize_ratio(macro_gap, last.eff_gap);
        // sigma_ratio: meaningful only when micro_sigma_tau is above noise floor.
        // Path-reversal asymmetry lives in [0, ~2]; below 1e-4 the micro kernel is
        // essentially reversible and the ratio is uninformative.
        if micro_sigma_tau > 1e-4 {
            rec.sigma_ratio = six_dynamics::audit::sanitize_ratio(sigma_pi, micro_sigma_tau);
        }

        // Rich-tier: macro diagnostics (reuse already-computed values, sanitize floats)
        if macro_n >= 2 {
            let san = |v: f64| -> Option<f64> {
                if v.is_finite() {
                    Some(v)
                } else {
                    None
                }
            };
            rec.sigma_u = san(sigma_u);
            rec.max_asym = san(max_asym);
            rec.cyc_mean = san(cyc_mean);
            rec.cyc_max = san(cyc_max);
            rec.n_chiral = Some(n_chiral);
            rec.trans_ep = san(trans_ep_val);
            rec.n_trans = Some(n_trans);
            rec.n_absorb = Some(n_absorb);
        }

        // Rich-tier: micro-kernel spectral summary
        // Compute on the symmetrized evolved kernel — checks whether coarse-graining
        // is masking slow structure that exists at the micro level.
        {
            let micro_pi = evolved.stationary(10000, 1e-12);
            let micro_embed = six_dynamics::lagrange::spectral_embed_reversible(&micro_pi, evolved);
            let san = |v: f64| -> Option<f64> {
                if v.is_finite() {
                    Some(v)
                } else {
                    None
                }
            };
            rec.micro_t_rel = san(six_dynamics::lagrange::relaxation_time(
                &micro_embed.eigenvalues,
            ));
            rec.micro_gap_ratio = san(six_dynamics::lagrange::spectral_gap_ratio(
                &micro_embed.eigenvalues,
            ));
            rec.micro_eigen_entropy = san(six_dynamics::lagrange::eigenvalue_entropy(
                &micro_embed.eigenvalues,
            ));
            rec.micro_spectral_participation = san(six_dynamics::lagrange::spectral_participation(
                &micro_embed.eigenvalues,
            ));
            // Store top 5 nontrivial eigenvalue magnitudes for post-hoc analysis
            let nt = six_dynamics::lagrange::nontrivial_eigenvalues(&micro_embed.eigenvalues);
            if !nt.is_empty() {
                let mut top: Vec<f64> = nt.iter().map(|v| v.abs()).collect();
                top.sort_by(|a, b| b.partial_cmp(a).unwrap_or(std::cmp::Ordering::Equal));
                top.truncate(5);
                rec.micro_top_eigenvalues = Some(top);
            }
        }

        // Rich-tier: multi-scale scan — always enabled.
        // Spectral conservation probes are critical diagnostics at all scales.
        // (max_k capped at 64 in multi_scale_scan, so cost is bounded even at n=256.)
        {
            rec.multi_scale_scan = Some(six_dynamics::audit::multi_scale_scan(
                evolved,
                &config,
                Some(last.tau),
            ));
        }

        if let Some(ref scan) = rec.multi_scale_scan {
            emit_discovery_grade_export(
                evolved,
                scan,
                seed,
                tau,
                label,
                lens_name(lens_source),
            );
        }

        if let Some(json) = six_dynamics::audit::to_json(&rec) {
            println!("KEY_AUDIT_JSON {}", json);
        }
    }
}

// ========== EXP-101: Multi-Level PICA Dynamics ==========
//
// Run 3-level ladder with PICA dynamics at all levels (not just micro).
// Compare baseline (P2<-P4 only) vs full-action PICA.

fn run_exp_101(seed: u64, scale: usize, config_filter: Option<&str>) {
    use six_primitives_core::substrate::{
        cycle_chirality, frobenius_asymmetry, path_reversal_asymmetry, transient_ep,
    };

    let n = scale.max(8);
    let ln_n = (n as f64).ln();
    let budget_init = n as f64 * ln_n;

    let configs: Vec<(&str, PicaConfig)> = vec![
        ("baseline", PicaConfig::baseline()),
        ("sbrc", PicaConfig::sbrc()),
        ("mixer", PicaConfig::mixer()),
        ("full_action", PicaConfig::full_action()),
        ("combo_rm", PicaConfig::combo_rm()),
        ("combo_structure", PicaConfig::combo_structure()),
        ("full_action_safe", PicaConfig::full_action_safe()),
    ];
    let valid_labels: Vec<&str> = configs.iter().map(|(label, _)| *label).collect();

    println!(
        "\n=== EXP-101 Multi-Level PICA Dynamics (seed={}, scale={}) ===",
        seed, n
    );
    let mut matched = false;

    for (label, pica) in &configs {
        if let Some(f) = config_filter {
            if *label != f {
                continue;
            }
        }
        matched = true;
        let micro_config = DynamicsConfig {
            n,
            p_traj: 0.90,
            p_p1: 0.03,
            p_p2: 0.03,
            p_p4: 0.01,
            p_p5: 0.01,
            p_p6: 0.02,
            budget_rate: ln_n * 0.01,
            budget_init,
            p1_strength: 0.1,
            p2_flips: (n / 8).max(1),
            min_row_entropy: 0.1 * ln_n,
            max_self_loop: 1.0 - 1.0 / n as f64,
            protocol_cycle_len: 100,
            total_steps: n * 2000,
            obs_interval: n * 200,
            tau_alpha: 0.5,
            budget_cap: budget_init,
            n_clusters: 8,
            pica: pica.clone(),
            seed,
        };

        let ladder_config = six_dynamics::pica::multilevel::LadderConfig::three_level(n);
        let trace = six_dynamics::pica::multilevel::run_ladder(&micro_config, &ladder_config);

        println!(
            "KEY_101_SUMMARY seed={} scale={} config={} n_levels={}",
            seed, n, label, trace.n_levels
        );

        // Report per-level diagnostics
        for (level_idx, snaps) in trace.level_snapshots.iter().enumerate() {
            if snaps.is_empty() {
                continue;
            }
            let last = snaps.last().unwrap();
            let max_frob: f64 = snaps
                .iter()
                .map(|s| s.frob_from_rank1)
                .fold(0.0f64, f64::max);
            println!("KEY_101_LEVEL seed={} scale={} config={} level=L{} n_snaps={} max_frob={:.6} final_frob={:.6} macro_n={} p2_rate={:.4} budget={:.2}",
                seed, n, label, level_idx, snaps.len(), max_frob, last.frob_from_rank1, last.macro_n,
                if last.p2_accepted + last.p2_rejected > 0 { last.p2_accepted as f64 / (last.p2_accepted + last.p2_rejected) as f64 } else { 0.0 },
                last.budget);
        }

        // Full diagnostics on final kernels
        for (ki, kernel) in trace.final_kernels.iter().enumerate() {
            let kn = kernel.n;
            if kn < 2 {
                continue;
            }

            let frob = six_dynamics::observe::frob_from_rank1(kernel);
            let pi = kernel.stationary(10000, 1e-12);
            let sigma_pi = path_reversal_asymmetry(kernel, &pi, 10);
            let uniform: Vec<f64> = vec![1.0 / kn as f64; kn];
            let sigma_u = path_reversal_asymmetry(kernel, &uniform, 10);
            let max_asym = frobenius_asymmetry(kernel);
            let (cyc_mean, cyc_max, n_chiral) = cycle_chirality(kernel, 1e-10);
            let (trans_ep_val, n_trans) = transient_ep(kernel);
            let n_absorb = (0..kn)
                .filter(|&i| kernel.kernel[i][i] > 1.0 - 1e-10)
                .count();
            let gap = kernel.spectral_gap();

            let entries: Vec<Vec<String>> = (0..kn)
                .map(|i| {
                    (0..kn)
                        .map(|j| format!("{:.4}", kernel.kernel[i][j]))
                        .collect()
                })
                .collect();

            println!("KEY_101_DIAG seed={} scale={} config={} level=L{} n={} frob={:.6} gap={:.6} sigma_pi={:.6} sigma_u={:.6} max_asym={:.6} cyc_mean={:.6} cyc_max={:.6} n_chiral={} trans_ep={:.6} n_trans={} n_absorb={} entries={:?}",
                seed, n, label, ki, kn, frob, gap, sigma_pi, sigma_u, max_asym, cyc_mean, cyc_max, n_chiral, trans_ep_val, n_trans, n_absorb, entries);

            // Group B diagnostic cells
            {
                use six_dynamics::pica::diag_cells;

                // Need a partition for this kernel
                let diag_lens = six_dynamics::spectral::spectral_partition(kernel, 4.min(kn));
                let diag_macro_n = six_dynamics::spectral::n_clusters(&diag_lens);
                if diag_macro_n >= 2 {
                    let diag_tau = six_dynamics::observe::adaptive_tau(gap, 0.5);

                    let b1 = diag_cells::b1_multiscale_rm(kernel, &diag_lens, diag_tau);
                    let b2 = diag_cells::b2_sector_rm(kernel, &diag_lens, diag_tau);
                    let b3 = diag_cells::b3_packaging_rm(kernel, &diag_lens, diag_tau);
                    let b4 = diag_cells::b4_rm_partition(kernel, &diag_lens, diag_tau, 4);
                    let b5 = diag_cells::b5_hierarchical(kernel, &diag_lens);
                    let b6 = diag_cells::b6_package_partition(kernel, &diag_lens);
                    let b7 = diag_cells::b7_ep_partition(kernel, 4.min(kn));
                    let b8 = diag_cells::b8_rm_grouping(kernel, &diag_lens, diag_tau);
                    let b9 = diag_cells::b9_per_sector_packaging(kernel, &diag_lens);
                    let b10 = diag_cells::b10_ep_grouping(kernel);
                    let b11 = diag_cells::b11_sector_audit(kernel, &diag_lens);

                    // B12: DPI — compare EP of CG(K^tau) vs K^tau at same time scale
                    let diag_ktau = helpers::matrix_power(kernel, diag_tau);
                    let diag_pi = kernel.stationary(10000, 1e-12);
                    let micro_sig_tau = path_reversal_asymmetry(&diag_ktau, &diag_pi, 10);
                    let diag_macro_k =
                        helpers::build_macro_from_ktau(&diag_ktau.kernel, &diag_lens, diag_macro_n);
                    let diag_macro_pi = diag_macro_k.stationary(10000, 1e-12);
                    let macro_sig = path_reversal_asymmetry(&diag_macro_k, &diag_macro_pi, 10);
                    let b12 = diag_cells::b12_meta_audit(micro_sig_tau, macro_sig);

                    let fmt = |d: &diag_cells::DiagResult| -> String {
                        d.values
                            .iter()
                            .map(|(k, v)| format!("{}={:.6}", k, v))
                            .collect::<Vec<_>>()
                            .join(",")
                    };

                    println!("KEY_101_BDIAG seed={} scale={} config={} level=L{} B1=[{}] B2=[{}] B3=[{}] B4=[{}] B5=[{}] B6=[{}] B7=[{}] B8=[{}] B9=[{}] B10=[{}] B11=[{}] B12=[{}]",
                        seed, n, label, ki,
                        fmt(&b1), fmt(&b2), fmt(&b3), fmt(&b4), fmt(&b5), fmt(&b6),
                        fmt(&b7), fmt(&b8), fmt(&b9), fmt(&b10), fmt(&b11), fmt(&b12));
                }
            }
        }

        // Emit KEY_AUDIT_JSON for the level-0 (micro) final kernel so EXP-101 is
        // ingestible by collect_audits.py / test_hypotheses.py.
        if let Some(evolved) = trace.final_kernels.first() {
            if let Some(last) = trace.level_snapshots.first().and_then(|s| s.last()) {
                let pch = six_dynamics::audit::pica_config_hash(pica);
                let mut rec = six_dynamics::audit::lite_from_snapshot(last, seed, n, pch);
                rec.tier = "rich".into();
                rec.exp_id = Some("EXP-101".into());
                rec.config_name = Some(label.to_string());
                rec.git_sha = Some(env!("GIT_SHA").into());
                rec.pica_config = serde_json::to_value(pica).ok();

                // Fresh spectral analysis for internal consistency
                let lens = six_dynamics::spectral::spectral_partition(evolved, 8);
                let audit_macro_n = six_dynamics::spectral::n_clusters(&lens);
                if audit_macro_n >= 2 {
                    let gap = evolved.spectral_gap();
                    let audit_tau = six_dynamics::observe::adaptive_tau(gap, 0.5);
                    let ktau = helpers::matrix_power(evolved, audit_tau);
                    let macro_k =
                        helpers::build_macro_from_ktau(&ktau.kernel, &lens, audit_macro_n);
                    let audit_frob = six_dynamics::observe::frob_from_rank1(&macro_k);
                    let pi = macro_k.stationary(10000, 1e-12);
                    let audit_sigma = path_reversal_asymmetry(&macro_k, &pi, 10);
                    let audit_macro_gap = macro_k.spectral_gap();

                    let san = |v: f64| -> Option<f64> {
                        if v.is_finite() {
                            Some(v)
                        } else {
                            None
                        }
                    };
                    rec.macro_n = Some(audit_macro_n);
                    rec.tau = Some(audit_tau);
                    rec.frob_from_rank1 = san(audit_frob);
                    rec.macro_gap = san(audit_macro_gap);
                    rec.sigma = san(audit_sigma);
                    rec.partition_stats = Some(six_dynamics::audit::partition_stats(&lens));
                    rec.macro_gap_ratio =
                        six_dynamics::audit::sanitize_ratio(audit_macro_gap, last.eff_gap);

                    // Sigma ratio
                    let micro_sigma_tau =
                        path_reversal_asymmetry(&ktau, &evolved.stationary(10000, 1e-12), 10);
                    if micro_sigma_tau > 1e-4 {
                        rec.sigma_ratio =
                            six_dynamics::audit::sanitize_ratio(audit_sigma, micro_sigma_tau);
                    }

                    // Rich-tier macro diagnostics
                    let uniform: Vec<f64> = vec![1.0 / audit_macro_n as f64; audit_macro_n];
                    rec.sigma_u = san(six_dynamics::audit::finite_horizon_sigma(
                        &macro_k, &uniform, 10,
                    ));
                    rec.max_asym = san(frobenius_asymmetry(&macro_k));
                    let (cm, cx, nc) = cycle_chirality(&macro_k, 1e-10);
                    rec.cyc_mean = san(cm);
                    rec.cyc_max = san(cx);
                    rec.n_chiral = Some(nc);
                    let (te, nt) = transient_ep(&macro_k);
                    rec.trans_ep = san(te);
                    rec.n_trans = Some(nt);
                    rec.n_absorb = Some(
                        (0..audit_macro_n)
                            .filter(|&i| macro_k.kernel[i][i] > 1.0 - 1e-10)
                            .count(),
                    );
                }

                // Micro-kernel spectral summary
                {
                    let micro_pi = evolved.stationary(10000, 1e-12);
                    let micro_embed =
                        six_dynamics::lagrange::spectral_embed_reversible(&micro_pi, evolved);
                    let san = |v: f64| -> Option<f64> {
                        if v.is_finite() {
                            Some(v)
                        } else {
                            None
                        }
                    };
                    rec.micro_t_rel = san(six_dynamics::lagrange::relaxation_time(
                        &micro_embed.eigenvalues,
                    ));
                    rec.micro_gap_ratio = san(six_dynamics::lagrange::spectral_gap_ratio(
                        &micro_embed.eigenvalues,
                    ));
                    rec.micro_eigen_entropy = san(six_dynamics::lagrange::eigenvalue_entropy(
                        &micro_embed.eigenvalues,
                    ));
                    rec.micro_spectral_participation = san(
                        six_dynamics::lagrange::spectral_participation(&micro_embed.eigenvalues),
                    );
                    let nt =
                        six_dynamics::lagrange::nontrivial_eigenvalues(&micro_embed.eigenvalues);
                    if !nt.is_empty() {
                        let mut top: Vec<f64> = nt.iter().map(|v| v.abs()).collect();
                        top.sort_by(|a, b| b.partial_cmp(a).unwrap_or(std::cmp::Ordering::Equal));
                        top.truncate(5);
                        rec.micro_top_eigenvalues = Some(top);
                    }
                }

                // Multi-scale scan
                rec.multi_scale_scan = Some(six_dynamics::audit::multi_scale_scan(
                    evolved,
                    &micro_config,
                    Some(last.tau),
                ));

                if let Some(json) = six_dynamics::audit::to_json(&rec) {
                    println!("KEY_AUDIT_JSON {}", json);
                }
            }
        }
    }

    if let Some(f) = config_filter {
        if !matched {
            eprintln!("ERROR: --config '{}' is not valid for EXP-101", f);
            eprintln!("       valid options: {}", valid_labels.join(", "));
            std::process::exit(2);
        }
    }
}

// ========== EXP-102: Cell Combination Sweep ==========
//
// Test promising combinations of PICA cells. Each combo is run with full
// diagnostics (same as EXP-100) to determine interaction effects.

fn run_exp_102(seed: u64, scale: usize, config_filter: Option<&str>) {
    let n = scale.max(8);
    let ln_n = (n as f64).ln();

    // Define cell combinations to test (each on top of A10 baseline)
    let combos: Vec<(&str, PicaConfig)> = vec![
        ("combo_rm", PicaConfig::combo_rm()), // A1+A3+A10
        (
            "A1+A12",
            PicaConfig::baseline().with_cell(0, 0).with_cell(1, 5),
        ), // cooldown + SBRC
        (
            "A3+A12",
            PicaConfig::baseline().with_cell(0, 2).with_cell(1, 5),
        ), // RM-rewrite + SBRC
        ("combo_structure", PicaConfig::combo_structure()), // A1+A3+A12+A10
        ("A1+A3+A13", PicaConfig::combo_rm().with_cell(2, 5)), // cooldown + RM + mixer
        (
            "A7+A3",
            PicaConfig::baseline().with_cell(1, 0).with_cell(0, 2),
        ), // protect-rewrite + RM
        ("full_action_safe", PicaConfig::full_action_safe()), // all minus A11
    ];

    println!(
        "\n=== EXP-102 Cell Combination Sweep (seed={}, scale={}) ===",
        seed, n
    );

    // Run baseline first for comparison
    if config_filter.is_none() || config_filter == Some("baseline_ref") {
        let baseline_pat = PicaConfig::baseline();
        run_exp_100_single(seed, n, ln_n, &baseline_pat, "baseline_ref", "EXP-102");
    }

    // Then each combination
    for (label, pica) in &combos {
        if let Some(f) = config_filter {
            if *label != f {
                continue;
            }
        }
        run_exp_100_single(seed, n, ln_n, pica, label, "EXP-102");
    }
}

// ========== EXP-103: Lens Selection Sweep ==========
//
// Test each P4-row cell individually and in combination, with different
// LensSelector strategies. Measures which alternative lenses improve
// over the canonical spectral partition (A15).

fn run_exp_103(seed: u64, scale: usize, config_filter: Option<&str>) {
    use six_dynamics::pica::config::LensSelector;

    let n = scale.max(8);
    let ln_n = (n as f64).ln();

    // Single lens cells (each on top of A10 baseline)
    let mut configs: Vec<(&str, PicaConfig)> = vec![
        // Baseline: A10 + A15 (was "A15_only" pre-review; actually A10+A15)
        ("baseline", PicaConfig::baseline()),
        // A14 only: RM-quantile lens (needs A15 to bootstrap initial partition)
        ("A14_only", PicaConfig::baseline().with_cell(3, 2)),
        // A16 only: packaging lens
        ("A16_only", PicaConfig::baseline().with_cell(3, 4)),
        // A17 only: EP-flow lens
        ("A17_only", PicaConfig::baseline().with_cell(3, 5)),
        // All lenses: A14+A15+A17 with MinRM selector
        (
            "all_MinRM",
            PicaConfig::baseline().with_cell(3, 2).with_cell(3, 5),
        ),
    ];

    // All lenses with MaxGap selector
    let mut all_maxgap = PicaConfig::baseline().with_cell(3, 2).with_cell(3, 5);
    all_maxgap.lens_selector = LensSelector::MaxGap;
    configs.push(("all_MaxGap", all_maxgap));

    // All lenses with MaxFrob selector
    let mut all_maxfrob = PicaConfig::baseline().with_cell(3, 2).with_cell(3, 5);
    all_maxfrob.lens_selector = LensSelector::MaxFrob;
    configs.push(("all_MaxFrob", all_maxfrob));

    // Full lens (all 4 P4-row cells)
    configs.push(("full_lens", PicaConfig::full_lens()));

    println!(
        "\n=== EXP-103 Lens Selection Sweep (seed={}, scale={}) ===",
        seed, n
    );

    for (label, pica) in &configs {
        if let Some(f) = config_filter {
            if *label != f {
                continue;
            }
        }
        run_exp_100_single(seed, n, ln_n, pica, label, "EXP-103");
    }
}

// ============================================================================
// EXP-104: Full PICA Sweep — new action cells (A18-A25) individually + combos
//
// Tests each newly-promoted cell on top of baseline (A10+A15), then combos:
//   P3 row: A18 (tau), A19 (sector mixing), A20 (packaging mixing)
//   P5 row: A21+A22+A23 (packaging suite)
//   P6 row: A24 (sector EP budget), A25 (DPI cap)
//   full_action (all 25 cells minus A16), full_all (all 25 cells)
// ============================================================================

fn run_exp_104(seed: u64, scale: usize, config_filter: Option<&str>) {
    let n = scale.max(8);
    let ln_n = (n as f64).ln();

    let configs: Vec<(&str, PicaConfig)> = vec![
        // Baseline: A10+A15 only (control)
        ("baseline", PicaConfig::baseline()),
        // P3 row cells individually
        ("A18_only", PicaConfig::baseline().with_cell(2, 2)), // P3<-P3: adaptive tau
        ("A19_only", PicaConfig::baseline().with_cell(2, 3)), // P3<-P4: sector mixing
        ("A20_only", PicaConfig::baseline().with_cell(2, 4)), // P3<-P5: packaging mixing
        // P3 row all (A18+A19+A20+A13)
        (
            "P3_row_all",
            PicaConfig::baseline()
                .with_cell(2, 2)
                .with_cell(2, 3)
                .with_cell(2, 4)
                .with_cell(2, 5),
        ),
        // P5 row cells individually
        ("A21_only", PicaConfig::baseline().with_cell(4, 2)), // P5<-P3: RM-similarity packaging
        ("A22_only", PicaConfig::baseline().with_cell(4, 3)), // P5<-P4: sector-balanced packaging
        ("A23_only", PicaConfig::baseline().with_cell(4, 5)), // P5<-P6: EP-similarity packaging
        // P5 row all (A21+A22+A23)
        (
            "P5_row_all",
            PicaConfig::baseline()
                .with_cell(4, 2)
                .with_cell(4, 3)
                .with_cell(4, 5),
        ),
        // P6 row cells individually
        ("A24_only", PicaConfig::baseline().with_cell(5, 3)), // P6<-P4: sector EP budget
        ("A25_only", PicaConfig::baseline().with_cell(5, 5)), // P6<-P6: DPI cap
        // P6 row all (A24+A25)
        (
            "P6_row_all",
            PicaConfig::baseline().with_cell(5, 3).with_cell(5, 5),
        ),
        // Full presets
        ("full_action", PicaConfig::full_action()),
        ("full_all", PicaConfig::full_all()),
    ];

    println!(
        "\n=== EXP-104 Full PICA Sweep (seed={}, scale={}) ===",
        seed, n
    );

    for (label, pica) in &configs {
        if let Some(f) = config_filter {
            if *label != f {
                continue;
            }
        }
        run_exp_100_single(seed, n, ln_n, pica, label, "EXP-104");
    }
}

// ========== EXP-105: PICA Cell Synergy Experiments ==========
//
// Targeted combos to understand cell dependencies and synergies.
// Based on EXP-104 findings:
// - Individual new cells (A18-A23) are inert due to dependency chains
// - A13 (P3←P6 frob mixer) is the key P3 driver
// - A24 (P6←P4 budget rate) changes dynamics alone
// - P3_row_all changes dynamics dramatically (A13 is primary driver)
//
// This experiment tests:
// 1. A13 alone — is it the sole driver of P3_row_all's effect?
// 2. A13 + A18 — does adaptive tau amplify the mixer?
// 3. A13 + A19 — does sector mixing add value (A18 enables cluster_rm)?
// 4. Packaging consumer + producer combos (A5/A11 + A21/A22/A23)
// 5. Budget combos (A24 + A25, A13 + A24)
// 6. Known presets for comparison (sbrc, mixer)

fn run_exp_105(seed: u64, scale: usize, config_filter: Option<&str>) {
    let n = scale.max(8);
    let ln_n = (n as f64).ln();

    let configs: Vec<(&str, PicaConfig)> = vec![
        // Control
        ("baseline", PicaConfig::baseline()),
        // === A13 decomposition ===
        // A13 alone: the frob mixer
        ("A13_only", PicaConfig::baseline().with_cell(2, 5)),
        // A13 + A18: mixer + adaptive tau
        (
            "A13_A18",
            PicaConfig::baseline().with_cell(2, 5).with_cell(2, 2),
        ),
        // A13 + A18 + A19: mixer + tau + sector mixing (A18 enables cluster_rm for A19)
        (
            "A13_A18_A19",
            PicaConfig::baseline()
                .with_cell(2, 5)
                .with_cell(2, 2)
                .with_cell(2, 3),
        ),
        // A13 + A18 + A20: mixer + tau + packaging mixing
        (
            "A13_A18_A20",
            PicaConfig::baseline()
                .with_cell(2, 5)
                .with_cell(2, 2)
                .with_cell(2, 4),
        ),
        // === Packaging consumer+producer ===
        // A5 (P1←P5) + A21 (P5←P3): P1 packaging-guided + RM packaging
        (
            "A5_A21",
            PicaConfig::baseline().with_cell(0, 4).with_cell(4, 2),
        ),
        // A11 (P2←P5) + A22 (P5←P4): P2 packaging-guided + sector packaging
        (
            "A11_A22",
            PicaConfig::baseline().with_cell(1, 4).with_cell(4, 3),
        ),
        // A11 (P2←P5) + A21 (P5←P3): P2 packaging-guided + RM packaging
        (
            "A11_A21",
            PicaConfig::baseline().with_cell(1, 4).with_cell(4, 2),
        ),
        // === Budget combos ===
        // A24 + A25: full P6 row
        (
            "A24_A25",
            PicaConfig::baseline().with_cell(5, 3).with_cell(5, 5),
        ),
        // A13 + A24: mixer + budget rate
        (
            "A13_A24",
            PicaConfig::baseline().with_cell(2, 5).with_cell(5, 3),
        ),
        // A13 + A25: mixer + budget cap
        (
            "A13_A25",
            PicaConfig::baseline().with_cell(2, 5).with_cell(5, 5),
        ),
        // === Known presets ===
        ("sbrc", PicaConfig::sbrc()),
        ("mixer", PicaConfig::mixer()),
        // === P1 row activation ===
        // A3 + A13: RM-rewrite + mixer (does A3 help when mixture is dynamic?)
        (
            "A3_A13",
            PicaConfig::baseline().with_cell(0, 2).with_cell(2, 5),
        ),
        // Full P1 row + A13: all P1 cells active + mixer
        (
            "P1_row_A13",
            PicaConfig::baseline()
                .with_cell(0, 0)
                .with_cell(0, 1)
                .with_cell(0, 2)
                .with_cell(0, 3)
                .with_cell(0, 4)
                .with_cell(0, 5)
                .with_cell(2, 5),
        ),
    ];

    println!(
        "\n=== EXP-105 PICA Cell Synergy Experiments (seed={}, scale={}) ===",
        seed, n
    );

    for (label, pica) in &configs {
        if let Some(f) = config_filter {
            if *label != f {
                continue;
            }
        }
        run_exp_100_single(seed, n, ln_n, pica, label, "EXP-105");
    }
}

// ========== EXP-106: Phase Transition Investigation ==========
//
// Investigate the sigma_pi → 0 (reversible macro) transition discovered in EXP-105.
// Key findings: A13+A18+A19 triggers the transition, A13+A18 does not.
// A18's role is purely structural (enables cluster_rm), not computational (tau).
//
// This experiment probes:
// 1. Sector boost strength scan: does the transition happen at a specific threshold?
// 2. Alternative cluster_rm enablers (A3, A14, A21 instead of A18)
// 3. Cross-regime combos: reversible + SBRC, + A24, + packaging

fn run_exp_106(seed: u64, scale: usize, config_filter: Option<&str>) {
    let n = scale.max(8);
    let ln_n = (n as f64).ln();

    // Helper: A13+A18+A19 with custom sector_boost
    let chain_with_boost = |boost: f64| -> PicaConfig {
        let mut cfg = PicaConfig::baseline()
            .with_cell(2, 5) // A13: frob mixer
            .with_cell(2, 2) // A18: cluster_rm enabler
            .with_cell(2, 3); // A19: sector mixing
        cfg.p3_p4_sector_boost = boost;
        cfg
    };

    let configs: Vec<(&str, PicaConfig)> = vec![
        // Control
        ("baseline", PicaConfig::baseline()),
        ("A13_A18_A19", chain_with_boost(2.0)), // default = reference
        // === Sector boost strength scan ===
        ("boost_0.1", chain_with_boost(0.1)),
        ("boost_0.5", chain_with_boost(0.5)),
        ("boost_1.0", chain_with_boost(1.0)),
        ("boost_3.0", chain_with_boost(3.0)),
        ("boost_4.0", chain_with_boost(4.0)),
        // === Alternative cluster_rm enablers ===
        // A3 (P1←P3) enables cluster_rm via enabled[0][2]
        (
            "A13_A3_A19",
            PicaConfig::baseline()
                .with_cell(2, 5)
                .with_cell(0, 2)
                .with_cell(2, 3),
        ),
        // A14 (P4←P3) enables cluster_rm via enabled[3][2]
        (
            "A13_A14_A19",
            PicaConfig::baseline()
                .with_cell(2, 5)
                .with_cell(3, 2)
                .with_cell(2, 3),
        ),
        // A21 (P5←P3) enables cluster_rm via enabled[4][2]
        (
            "A13_A21_A19",
            PicaConfig::baseline()
                .with_cell(2, 5)
                .with_cell(4, 2)
                .with_cell(2, 3),
        ),
        // === Cross-regime combos ===
        // Reversible + SBRC
        (
            "chain_SBRC",
            PicaConfig::baseline()
                .with_cell(2, 5)
                .with_cell(2, 2)
                .with_cell(2, 3)
                .with_cell(1, 5),
        ), // A12: SBRC
        // Reversible + A24 (budget rate)
        (
            "chain_A24",
            PicaConfig::baseline()
                .with_cell(2, 5)
                .with_cell(2, 2)
                .with_cell(2, 3)
                .with_cell(5, 3),
        ), // A24: budget rate
        // Reversible + packaging (A11+A22)
        (
            "chain_pkg",
            PicaConfig::baseline()
                .with_cell(2, 5)
                .with_cell(2, 2)
                .with_cell(2, 3)
                .with_cell(1, 4)
                .with_cell(4, 3),
        ), // A11+A22
    ];
    let valid_labels: Vec<&str> = configs.iter().map(|(label, _)| *label).collect();

    println!(
        "\n=== EXP-106 Phase Transition Investigation (seed={}, scale={}) ===",
        seed, n
    );
    let mut matched = false;

    for (label, pica) in &configs {
        if let Some(f) = config_filter {
            if *label != f {
                continue;
            }
        }
        matched = true;
        run_exp_100_single(seed, n, ln_n, pica, label, "EXP-106");
    }

    if let Some(f) = config_filter {
        if !matched {
            eprintln!("ERROR: --config '{}' is not valid for EXP-106", f);
            eprintln!("       valid options: {}", valid_labels.join(", "));
            std::process::exit(2);
        }
    }
}

// ========== EXP-107: Scale Dependence Investigation ==========
//
// Test whether key findings from EXP-104/105/106 hold at n=128 and n=256.
// Key questions:
// 1. Does the reversible transition (A13+A18+A19 → sigma=0) persist at scale?
// 2. Does A25 become active at larger n? (DPI may be violated)
// 3. Does A24's budget rate modulation scale?
// 4. How does full_action behave at scale?
// 5. Does the packaging combo (A11+A22) effect grow with scale?

fn run_exp_107(seed: u64, scale: usize, config_filter: Option<&str>) {
    let n = scale.max(8);
    let ln_n = (n as f64).ln();

    let configs: Vec<(&str, PicaConfig)> = vec![
        // Control
        ("baseline", PicaConfig::baseline()),
        // The critical chain (sigma→0 at n=64)
        (
            "chain",
            PicaConfig::baseline()
                .with_cell(2, 5) // A13
                .with_cell(2, 2) // A18
                .with_cell(2, 3),
        ), // A19
        // Individual cells that showed effects at n=64
        ("A13_only", PicaConfig::baseline().with_cell(2, 5)),
        ("A24_only", PicaConfig::baseline().with_cell(5, 3)),
        ("A25_only", PicaConfig::baseline().with_cell(5, 5)),
        // Presets
        ("sbrc", PicaConfig::sbrc()),
        ("full_action", PicaConfig::full_action()),
        ("full_all", PicaConfig::full_all()),
        // Best packaging combo from EXP-105
        (
            "A11_A22",
            PicaConfig::baseline()
                .with_cell(1, 4) // A11: P2←P5
                .with_cell(4, 3),
        ), // A22: P5←P4
        // Cross-regime: chain + A24 (highest p2_rate at n=64)
        (
            "chain_A24",
            PicaConfig::baseline()
                .with_cell(2, 5)
                .with_cell(2, 2)
                .with_cell(2, 3)
                .with_cell(5, 3),
        ), // A24
        // Chain + SBRC (broke reversibility at n=64)
        (
            "chain_SBRC",
            PicaConfig::baseline()
                .with_cell(2, 5)
                .with_cell(2, 2)
                .with_cell(2, 3)
                .with_cell(1, 5),
        ), // A12: SBRC
        // Post-fix additions: A19 alone (no A18 enabler needed after Bug #1 fix)
        ("A19_only", PicaConfig::baseline().with_cell(2, 3)),
        // P1 row + A13 (best all-round from EXP-105v2)
        (
            "P1_row_A13",
            PicaConfig::baseline()
                .with_cell(0, 0)
                .with_cell(0, 1)
                .with_cell(0, 2)
                .with_cell(0, 3)
                .with_cell(0, 4)
                .with_cell(0, 5)
                .with_cell(2, 5),
        ),
    ];
    let valid_labels: Vec<&str> = configs.iter().map(|(label, _)| *label).collect();

    println!(
        "\n=== EXP-107 Scale Dependence (seed={}, scale={}) ===",
        seed, n
    );
    let mut matched = false;

    for (label, pica) in &configs {
        if let Some(f) = config_filter {
            if *label != f {
                continue;
            }
        }
        matched = true;
        run_exp_100_single(seed, n, ln_n, pica, label, "EXP-107");
    }

    if let Some(f) = config_filter {
        if !matched {
            eprintln!("ERROR: --config '{}' is not valid for EXP-107", f);
            eprintln!("       valid options: {}", valid_labels.join(", "));
            std::process::exit(2);
        }
    }
}

// ========== EXP-108: full_action Decomposition at Scale ==========
//
// Why does full_action maintain frob > 1.0 at n=256 while everything else drops to ~0.5?
// 1. Test if k=8 is insufficient at n=256 by analyzing at k=4,8,16
// 2. Decompose full_action: which cell subsets are responsible for scale resilience?
// 3. Compare full_action vs full_all (the only difference is A16)

fn run_exp_108_macro_at_k(evolved: &MarkovKernel, seed: u64, n: usize, label: &str, k: usize) {
    use six_primitives_core::substrate::{
        cycle_chirality, frobenius_asymmetry, path_reversal_asymmetry, transient_ep,
    };

    let lens = six_dynamics::spectral::spectral_partition(evolved, k);
    let macro_n = six_dynamics::spectral::n_clusters(&lens);
    if macro_n < 2 {
        println!(
            "KEY_108_MACRO seed={} scale={} cell={} k={} macro_n={} frob=0.0",
            seed, n, label, k, macro_n
        );
        return;
    }

    let gap = evolved.spectral_gap();
    let tau = six_dynamics::observe::adaptive_tau(gap, 0.5);
    let ktau = helpers::matrix_power(evolved, tau);
    let macro_k = helpers::build_macro_from_ktau(&ktau.kernel, &lens, macro_n);

    let frob = six_dynamics::observe::frob_from_rank1(&macro_k);
    let pi = macro_k.stationary(10000, 1e-12);
    let sigma_pi = path_reversal_asymmetry(&macro_k, &pi, 10);
    let max_asym = frobenius_asymmetry(&macro_k);
    let (cyc_mean, cyc_max, n_chiral) = cycle_chirality(&macro_k, 1e-10);
    let (trans_ep_val, n_trans) = transient_ep(&macro_k);
    let n_absorb = (0..macro_n)
        .filter(|&i| macro_k.kernel[i][i] > 1.0 - 1e-10)
        .count();
    let macro_gap = macro_k.spectral_gap();

    let entries: Vec<Vec<String>> = (0..macro_n)
        .map(|i| {
            (0..macro_n)
                .map(|j| format!("{:.4}", macro_k.kernel[i][j]))
                .collect()
        })
        .collect();

    println!("KEY_108_MACRO seed={} scale={} cell={} k={} macro_n={} frob={:.6} gap={:.6} sigma_pi={:.6} max_asym={:.6} cyc_mean={:.6} cyc_max={:.6} n_chiral={} trans_ep={:.6} n_trans={} n_absorb={} entries={:?}",
        seed, n, label, k, macro_n, frob, macro_gap, sigma_pi, max_asym, cyc_mean, cyc_max, n_chiral, trans_ep_val, n_trans, n_absorb, entries);
}

fn run_exp_108(seed: u64, scale: usize, config_filter: Option<&str>) {
    let n = scale.max(8);
    let ln_n = (n as f64).ln();

    // Configs to test: baseline, key combos, full_action, full_all
    let configs: Vec<(&str, PicaConfig)> = vec![
        ("baseline", PicaConfig::baseline()),
        ("sbrc", PicaConfig::sbrc()),
        ("mixer", PicaConfig::mixer()),
        // P1+P2 rows only (no P3/P5/P6 modulation beyond baseline)
        ("P1P2_rows", {
            let mut c = PicaConfig::baseline();
            for i in 0..6 {
                c.enabled[0][i] = true;
                c.enabled[1][i] = true;
            }
            c
        }),
        // P3 row added (mixture modulation)
        ("P1P2P3_rows", {
            let mut c = PicaConfig::baseline();
            for i in 0..6 {
                c.enabled[0][i] = true;
                c.enabled[1][i] = true;
            }
            c.enabled[2][2] = true;
            c.enabled[2][3] = true;
            c.enabled[2][4] = true;
            c.enabled[2][5] = true;
            c
        }),
        // All rows except P4 (keep baseline A15 only)
        ("no_extra_P4", {
            let mut c = PicaConfig::full_action();
            c.enabled[3][2] = false; // A14 off
            c.enabled[3][4] = false; // A16 off
            c.enabled[3][5] = false; // A17 off
            c
        }),
        // full_action minus SBRC
        ("fa_no_SBRC", {
            let mut c = PicaConfig::full_action();
            c.enabled[1][5] = false; // A12 off
            c
        }),
        // full_action minus P6 row
        ("fa_no_P6row", {
            let mut c = PicaConfig::full_action();
            c.enabled[5][3] = false; // A24 off
            c.enabled[5][5] = false; // A25 off
            c
        }),
        ("full_action", PicaConfig::full_action()),
        ("full_all", PicaConfig::full_all()),
    ];
    let valid_labels: Vec<&str> = configs.iter().map(|(label, _)| *label).collect();

    println!(
        "\n=== EXP-108 full_action Decomposition (seed={}, scale={}) ===",
        seed, n
    );
    let mut matched = false;

    for (label, pica) in &configs {
        if let Some(f) = config_filter {
            if *label != f {
                continue;
            }
        }
        matched = true;
        let budget_init = n as f64 * ln_n;
        let mut config = DynamicsConfig {
            n,
            p_traj: 0.90,
            p_p1: 0.03,
            p_p2: 0.03,
            p_p4: 0.01,
            p_p5: 0.01,
            p_p6: 0.02,
            budget_rate: ln_n * 0.01,
            budget_init,
            p1_strength: 0.1,
            p2_flips: (n / 8).max(1),
            min_row_entropy: 0.1 * ln_n,
            max_self_loop: 1.0 - 1.0 / n as f64,
            protocol_cycle_len: 100,
            total_steps: n * 2000,
            obs_interval: n * 200,
            tau_alpha: 0.5,
            budget_cap: budget_init,
            n_clusters: 8,
            pica: PicaConfig::baseline(),
            seed,
        };
        // Apply the PICA config
        for a in 0..6 {
            for i in 0..6 {
                if pica.enabled[a][i] {
                    config.pica.enabled[a][i] = true;
                }
            }
        }

        let trace = six_dynamics::run_dynamics(&config);
        let evolved = &trace.final_kernel;
        let last = trace.snapshots.last().unwrap();
        let p2_total = last.p2_accepted + last.p2_rejected;
        let p2_rate = if p2_total > 0 {
            last.p2_accepted as f64 / p2_total as f64
        } else {
            0.0
        };
        let total_rv = last.p2_repairs + last.p2_violations;
        let repair_frac = if total_rv > 0 {
            last.p2_repairs as f64 / total_rv as f64
        } else {
            0.0
        };

        println!(
            "KEY_108_DYN seed={} scale={} cell={} p2_rate={:.4} repair_frac={:.4} budget={:.2}",
            seed, n, label, p2_rate, repair_frac, last.budget
        );

        // Analyze at multiple k values
        for k in &[4, 8, 16] {
            run_exp_108_macro_at_k(evolved, seed, n, label, *k);
        }
    }

    if let Some(f) = config_filter {
        if !matched {
            eprintln!("ERROR: --config '{}' is not valid for EXP-108", f);
            eprintln!("       valid options: {}", valid_labels.join(", "));
            std::process::exit(2);
        }
    }
}

// ========== EXP-109: Lagrange Probe Baseline Survey ==========
//
// Tests HYP-202..205. Lagrange probes (step_entropy, pla2_gap, lagr_geo_r2,
// lagr_diff_kl, t_rel, gap_ratio, eigen_entropy) are computed in multi_scale_scan for every
// experiment. This experiment runs 13 configs × 10 seeds × {n=64, n=128}.

fn run_exp_109(seed: u64, scale: usize, config_filter: Option<&str>) {
    let n = scale.max(8);
    let ln_n = (n as f64).ln();

    let configs: Vec<(&str, PicaConfig)> = vec![
        ("baseline", PicaConfig::baseline()),
        ("A13_only", PicaConfig::baseline().with_cell(2, 5)),
        ("A14_only", PicaConfig::baseline().with_cell(3, 2)),
        ("A16_only", PicaConfig::baseline().with_cell(3, 4)),
        ("A17_only", PicaConfig::baseline().with_cell(3, 5)),
        ("A19_only", PicaConfig::baseline().with_cell(2, 3)),
        ("A25_only", PicaConfig::baseline().with_cell(5, 5)),
        (
            "P1_row_A13",
            PicaConfig::baseline()
                .with_cell(0, 0)
                .with_cell(0, 1)
                .with_cell(0, 2)
                .with_cell(0, 3)
                .with_cell(0, 4)
                .with_cell(0, 5)
                .with_cell(2, 5),
        ),
        (
            "A13_A14_A19",
            PicaConfig::baseline()
                .with_cell(2, 5)
                .with_cell(3, 2)
                .with_cell(2, 3),
        ),
        ("full_action", PicaConfig::full_action()),
        ("full_all", PicaConfig::full_all()),
        ("full_lens", PicaConfig::full_lens()),
        (
            "chain_SBRC",
            PicaConfig::baseline()
                .with_cell(2, 5)
                .with_cell(2, 2)
                .with_cell(2, 3)
                .with_cell(1, 5),
        ),
    ];
    let valid_labels: Vec<&str> = configs.iter().map(|(label, _)| *label).collect();

    println!(
        "\n=== EXP-109 Lagrange Probe Survey (seed={}, scale={}) ===",
        seed, n
    );
    let mut matched = false;

    for (label, pica) in &configs {
        if let Some(f) = config_filter {
            if *label != f {
                continue;
            }
        }
        matched = true;
        run_exp_100_single(seed, n, ln_n, pica, label, "EXP-109");
    }

    if let Some(f) = config_filter {
        if !matched {
            eprintln!("ERROR: --config '{}' is not valid for EXP-109", f);
            eprintln!("       valid options: {}", valid_labels.join(", "));
            std::process::exit(2);
        }
    }
}

// ========== EXP-110: Lagrange Probe Scale Dependence ==========
//
// 3 configs × 10 seeds × {n=32, n=64, n=128, n=256}.
// Tests whether Lagrangian structure (low PLA2, high geo_R²) is scale-dependent.

fn run_exp_110(seed: u64, scale: usize, config_filter: Option<&str>) {
    let n = scale.max(8);
    let ln_n = (n as f64).ln();

    let configs: Vec<(&str, PicaConfig)> = vec![
        ("baseline", PicaConfig::baseline()),
        ("full_action", PicaConfig::full_action()),
        ("A14_only", PicaConfig::baseline().with_cell(3, 2)),
    ];
    let valid_labels: Vec<&str> = configs.iter().map(|(label, _)| *label).collect();

    println!(
        "\n=== EXP-110 Lagrange Scale Dependence (seed={}, scale={}) ===",
        seed, n
    );
    let mut matched = false;

    for (label, pica) in &configs {
        if let Some(f) = config_filter {
            if *label != f {
                continue;
            }
        }
        matched = true;
        run_exp_100_single(seed, n, ln_n, pica, label, "EXP-110");
    }

    if let Some(f) = config_filter {
        if !matched {
            eprintln!("ERROR: --config '{}' is not valid for EXP-110", f);
            eprintln!("       valid options: {}", valid_labels.join(", "));
            std::process::exit(2);
        }
    }
}

// ========== EXP-112: Systematic PICA Ablation Survey ==========
//
// 62 configs covering:
//   Group 0: Controls (baseline, full_action)
//   Group 1: Missing single-cell retests (A14, A16, A17, A18, A20, A22)
//   Group 2: Row ablations (all cells in one actor-row)
//   Group 3: Column ablations (all cells sharing one informant)
//   Group 4: Leave-one-out from full_action (22 configs)
//   Group 5: Synergy pairs (8 untested pairs)
//   Group 6: Row-pair interactions (4 configs)
//   Group 7: Diagnostic row/column removal from full_action (8 configs)

fn run_exp_112(seed: u64, scale: usize, config_filter: Option<&str>) {
    let n = scale.max(8);
    let ln_n = (n as f64).ln();

    // Helper: full_action minus one cell
    let loo = |actor: usize, informant: usize| -> PicaConfig {
        let mut c = PicaConfig::full_action();
        c.enabled[actor][informant] = false;
        c
    };

    // Helper: full_action minus a set of cells
    let fa_minus = |cells: &[(usize, usize)]| -> PicaConfig {
        let mut c = PicaConfig::full_action();
        for &(a, i) in cells {
            c.enabled[a][i] = false;
        }
        c
    };

    let configs: Vec<(&str, PicaConfig)> = vec![
        // ── Group 0: Controls ──
        ("empty", PicaConfig::none()),
        ("baseline", PicaConfig::baseline()),
        ("full_action", PicaConfig::full_action()),

        // ── Group 1: Missing single-cell retests ──
        ("A14_only", PicaConfig::baseline().with_cell(3, 2)),
        ("A16_only", PicaConfig::baseline().with_cell(3, 4)),
        ("A17_only", PicaConfig::baseline().with_cell(3, 5)),
        ("A18_only", PicaConfig::baseline().with_cell(2, 2)),
        ("A20_only", PicaConfig::baseline().with_cell(2, 4)),   // data-starved (no P5 producer)
        ("A22_only", PicaConfig::baseline().with_cell(4, 3)),

        // ── Group 2: Row ablations (all cells in one actor-row + baseline) ──
        // Note: A5 (P1←P5), A11 (P2←P5), A20 (P3←P5) are dropped from rows
        // that lack P5 producers, to avoid spectral-partition fallback impurity.
        ("P1_row", PicaConfig::baseline()
            .with_cell(0, 0).with_cell(0, 1).with_cell(0, 2)
            .with_cell(0, 3).with_cell(0, 5)),              // A1-A4,A6 (no A5: no P5 producer)
        ("P2_row", PicaConfig::baseline()
            .with_cell(1, 0).with_cell(1, 1).with_cell(1, 2)
            .with_cell(1, 5)),                               // A7-A9,A12 (no A11: no P5 producer)
        ("P3_row", PicaConfig::baseline()
            .with_cell(2, 2).with_cell(2, 3).with_cell(2, 5)), // A18,A19,A13 (no A20: no P5 producer)
        ("P4_row", PicaConfig::baseline()
            .with_cell(3, 2).with_cell(3, 4).with_cell(3, 5)), // A14,A16,A17 (pure, no P5 dep)
        ("P5_row", PicaConfig::baseline()
            .with_cell(4, 2).with_cell(4, 3).with_cell(4, 5)), // A21,A22,A23 (pure, these ARE the P5 producers)
        ("P6_row", PicaConfig::baseline()
            .with_cell(5, 3).with_cell(5, 5)),                 // A24,A25 (pure)

        // ── Group 3: Column ablations (all cells with same informant + baseline) ──
        // col_P5 adds A22 as P5 producer to avoid fallback impurity.
        ("col_P1", PicaConfig::baseline()
            .with_cell(0, 0).with_cell(1, 0)),               // A1,A7
        ("col_P2", PicaConfig::baseline()
            .with_cell(0, 1).with_cell(1, 1)),               // A2,A8
        ("col_P3", PicaConfig::baseline()
            .with_cell(0, 2).with_cell(1, 2).with_cell(2, 2)
            .with_cell(3, 2).with_cell(4, 2)),               // A3,A9,A18,A14,A21
        ("col_P4", PicaConfig::baseline()
            .with_cell(0, 3).with_cell(2, 3)
            .with_cell(4, 3).with_cell(5, 3)),               // A4,A19,A22,A24
        ("col_P5", PicaConfig::baseline()
            .with_cell(0, 4).with_cell(1, 4).with_cell(2, 4)
            .with_cell(3, 4).with_cell(4, 3)),               // A5,A11,A20,A16 + A22 as P5 producer
        ("col_P6", PicaConfig::baseline()
            .with_cell(0, 5).with_cell(1, 5).with_cell(2, 5)
            .with_cell(3, 5).with_cell(4, 5).with_cell(5, 5)), // A6,A12,A13,A17,A23,A25

        // ── Group 4: Leave-one-out from full_action ──
        // (full_action has P5 producers, so all LOO configs are pure)
        ("loo_A1",  loo(0, 0)),
        ("loo_A2",  loo(0, 1)),
        ("loo_A3",  loo(0, 2)),
        ("loo_A4",  loo(0, 3)),
        ("loo_A5",  loo(0, 4)),
        ("loo_A6",  loo(0, 5)),
        ("loo_A7",  loo(1, 0)),
        ("loo_A8",  loo(1, 1)),
        ("loo_A9",  loo(1, 2)),
        ("loo_A11", loo(1, 4)),
        ("loo_A12", loo(1, 5)),
        ("loo_A13", loo(2, 5)),
        ("loo_A14", loo(3, 2)),
        ("loo_A17", loo(3, 5)),
        ("loo_A18", loo(2, 2)),
        ("loo_A19", loo(2, 3)),
        ("loo_A20", loo(2, 4)),
        ("loo_A21", loo(4, 2)),
        ("loo_A22", loo(4, 3)),
        ("loo_A23", loo(4, 5)),
        ("loo_A24", loo(5, 3)),
        ("loo_A25", loo(5, 5)),

        // ── Group 5: Synergy pairs ──
        // A13_A11 adds A22 so A11 has real packaging data (not spectral fallback).
        ("A13_A14", PicaConfig::baseline().with_cell(2, 5).with_cell(3, 2)),
        ("A14_A19", PicaConfig::baseline().with_cell(3, 2).with_cell(2, 3)),
        ("A18_A19", PicaConfig::baseline().with_cell(2, 2).with_cell(2, 3)),
        ("A14_A17", PicaConfig::baseline().with_cell(3, 2).with_cell(3, 5)),
        ("A13_A11", PicaConfig::baseline()
            .with_cell(2, 5).with_cell(1, 4).with_cell(4, 3)), // + A22 as P5 producer
        ("A12_A25", PicaConfig::baseline().with_cell(1, 5).with_cell(5, 5)),
        ("A4_A19",  PicaConfig::baseline().with_cell(0, 3).with_cell(2, 3)),
        ("A14_A25", PicaConfig::baseline().with_cell(3, 2).with_cell(5, 5)),

        // ── Group 6: Row-pair interactions ──
        // Rows containing A5/A11/A20 drop those cells (no P5 producer).
        ("P1_P3_rows", PicaConfig::baseline()
            .with_cell(0, 0).with_cell(0, 1).with_cell(0, 2)
            .with_cell(0, 3).with_cell(0, 5)                   // P1 row sans A5
            .with_cell(2, 2).with_cell(2, 3).with_cell(2, 5)), // P3 row sans A20
        ("P2_P3_rows", PicaConfig::baseline()
            .with_cell(1, 0).with_cell(1, 1).with_cell(1, 2)
            .with_cell(1, 5)                                    // P2 row sans A11
            .with_cell(2, 2).with_cell(2, 3).with_cell(2, 5)), // P3 row sans A20
        ("P3_P4_rows", PicaConfig::baseline()
            .with_cell(2, 2).with_cell(2, 3).with_cell(2, 5)   // P3 row sans A20
            .with_cell(3, 2).with_cell(3, 4).with_cell(3, 5)), // P4 row (pure)
        ("P4_P5_rows", PicaConfig::baseline()
            .with_cell(3, 2).with_cell(3, 4).with_cell(3, 5)
            .with_cell(4, 2).with_cell(4, 3).with_cell(4, 5)), // both pure

        // ── Group 7: Diagnostic row/column removal from full_action ──
        ("full_all", PicaConfig::full_all()),
        ("fa_no_P1row", fa_minus(&[(0,0),(0,1),(0,2),(0,3),(0,4),(0,5)])),
        ("fa_no_P2mod", fa_minus(&[(1,0),(1,1),(1,2),(1,4),(1,5)])),
        ("fa_no_P3row", fa_minus(&[(2,2),(2,3),(2,4),(2,5)])),
        ("fa_no_inf_P3", fa_minus(&[(0,2),(1,2),(2,2),(3,2),(4,2)])),
        ("fa_no_inf_P4", fa_minus(&[(0,3),(2,3),(4,3),(5,3)])),
        ("fa_no_inf_P5", fa_minus(&[(0,4),(1,4),(2,4)])),
        ("fa_no_inf_P6", fa_minus(&[(0,5),(1,5),(2,5),(3,5),(4,5),(5,5)])),

        // ── Group 8: Candidate generating sets (sufficiency tests for HYP-210) ──
        ("gen4_core", PicaConfig::baseline()
            .with_cell(2, 5).with_cell(3, 2)                   // A13 + A14
            .with_cell(2, 2).with_cell(2, 3)),                 // A18 + A19
        ("gen3_A13_A14_A19", PicaConfig::baseline()
            .with_cell(2, 5).with_cell(3, 2).with_cell(2, 3)), // from EXP-106, retest
        ("gen5_core_A25", PicaConfig::baseline()
            .with_cell(2, 5).with_cell(3, 2)                   // A13 + A14
            .with_cell(2, 2).with_cell(2, 3)                   // A18 + A19
            .with_cell(5, 5)),                                  // + A25 (stabilizer)
        ("gen6_core_A12_A25", PicaConfig::baseline()
            .with_cell(2, 5).with_cell(3, 2)                   // A13 + A14
            .with_cell(2, 2).with_cell(2, 3)                   // A18 + A19
            .with_cell(1, 5).with_cell(5, 5)),                 // + A12 + A25
        ("gen3_A13_A18_A19", PicaConfig::baseline()
            .with_cell(2, 5).with_cell(2, 2).with_cell(2, 3)), // chain from EXP-107, retest
        ("gen2_A14_A13", PicaConfig::baseline()
            .with_cell(3, 2).with_cell(2, 5)),                 // same as A13_A14 but labeled for gen-set
    ];
    let valid_labels: Vec<&str> = configs.iter().map(|(label, _)| *label).collect();

    println!(
        "\n=== EXP-112 Systematic PICA Ablation Survey (seed={}, scale={}, {} configs) ===",
        seed, n, configs.len()
    );
    let mut matched = false;

    for (label, pica) in &configs {
        if let Some(f) = config_filter {
            if *label != f {
                continue;
            }
        }
        matched = true;
        run_exp_100_single(seed, n, ln_n, pica, label, "EXP-112");
    }

    if let Some(f) = config_filter {
        if !matched {
            eprintln!("ERROR: --config '{}' is not valid for EXP-112", f);
            eprintln!("       valid options: {}", valid_labels.join(", "));
            std::process::exit(2);
        }
    }
}

// ========== EXP-F1: Empty Baseline (No PICA cells) ==========
//
// Critical inertness control. PicaConfig::none() disables ALL cells including
// baseline A10+A15. Tests whether any cell is truly needed.

fn run_exp_f1(seed: u64, scale: usize) {
    let n = scale.max(8);
    let ln_n = (n as f64).ln();
    let pica = PicaConfig::none();
    println!(
        "\n=== EXP-F1 Empty Baseline (seed={}, scale={}) ===",
        seed, n
    );
    run_exp_100_single(seed, n, ln_n, &pica, "empty", "EXP-F1");
}

// ========== EXP-066: Minority-Sensitive Reproducibility (Jaccard) ==========

fn run_exp_066(seed: u64, scale: usize) -> Exp066Metrics {
    let n = scale.max(8);
    let mut dag = EmergenceDag::new();
    let root_id = dag.create_root(n, seed);
    let root = dag.nodes[&root_id].clone();
    let n_paths = 10usize;

    // Collect minority sets from each cascade path
    let mut minority_sets: Vec<Vec<usize>> = Vec::new();
    for p in 0..n_paths {
        let path_seed = seed * 1000 + p as u64;
        let mut path_dag = EmergenceDag::new();
        let path_root_id = path_dag.create_root_from_kernel(root.kernel.clone());
        if let Some(ordering) =
            run_cascade_with_lenses(&mut path_dag, &path_root_id, n, root.sigma, path_seed)
        {
            if let Some(tp) = ordering.terminal_partition {
                let count_0: usize = tp.iter().filter(|&&x| x == 0).count();
                let count_1: usize = tp.iter().filter(|&&x| x == 1).count();
                let minority_label = if count_0 <= count_1 { 0 } else { 1 };
                let ids: Vec<usize> = tp
                    .iter()
                    .enumerate()
                    .filter(|(_, &x)| x == minority_label)
                    .map(|(i, _)| i)
                    .collect();
                minority_sets.push(ids);
            }
        }
    }

    let n_valid = minority_sets.len();
    if n_valid < 2 {
        return Exp066Metrics {
            n,
            n_paths,
            n_valid,
            mean_jaccard: 0.0,
            baseline_jaccard: 0.0,
            mean_intersection: 0.0,
            baseline_intersection: 0.0,
            n_pairs: 0,
            mean_minority_size: 0.0,
        };
    }

    // Compute pairwise Jaccard and intersection
    let mut sum_jaccard = 0.0f64;
    let mut sum_intersection = 0.0f64;
    let mut sum_baseline_jaccard = 0.0f64;
    let mut sum_baseline_intersection = 0.0f64;
    let mut n_pairs = 0usize;
    let mean_k: f64 = minority_sets.iter().map(|s| s.len() as f64).sum::<f64>() / n_valid as f64;

    for i in 0..n_valid {
        for j in (i + 1)..n_valid {
            let a = &minority_sets[i];
            let b = &minority_sets[j];
            let ka = a.len();
            let kb = b.len();
            // Intersection
            let intersection: usize = a.iter().filter(|x| b.contains(x)).count();
            let union = ka + kb - intersection;
            let jaccard = if union > 0 {
                intersection as f64 / union as f64
            } else {
                0.0
            };
            // Hypergeometric baseline: E[intersection] = ka * kb / n
            let exp_intersection = ka as f64 * kb as f64 / n as f64;
            let exp_union = (ka + kb) as f64 - exp_intersection;
            let baseline_j = if exp_union > 0.0 {
                exp_intersection / exp_union
            } else {
                0.0
            };
            sum_jaccard += jaccard;
            sum_intersection += intersection as f64;
            sum_baseline_jaccard += baseline_j;
            sum_baseline_intersection += exp_intersection;
            n_pairs += 1;
        }
    }

    Exp066Metrics {
        n,
        n_paths,
        n_valid,
        mean_jaccard: sum_jaccard / n_pairs as f64,
        baseline_jaccard: sum_baseline_jaccard / n_pairs as f64,
        mean_intersection: sum_intersection / n_pairs as f64,
        baseline_intersection: sum_baseline_intersection / n_pairs as f64,
        n_pairs,
        mean_minority_size: mean_k,
    }
}

#[derive(Clone, Debug)]
struct Exp066Metrics {
    n: usize,
    n_paths: usize,
    n_valid: usize,
    mean_jaccard: f64,
    baseline_jaccard: f64,
    mean_intersection: f64,
    baseline_intersection: f64,
    n_pairs: usize,
    mean_minority_size: f64,
}

// ========== EXP-067: Orphan Mechanism Test ==========

fn run_exp_067(seed: u64, scale: usize) -> Exp067Metrics {
    use six_primitives_core::primitives;
    let n = scale.max(8);
    let mut dag = EmergenceDag::new();
    let root_id = dag.create_root(n, seed);
    let root = dag.nodes[&root_id].clone();
    let p_gate = helpers::scale_gating_prob(n);

    // Theoretical prediction: E[isolated] = n * p^{2(n-1)}
    let expected_isolated = n as f64 * p_gate.powi(2 * (n as i32 - 1));

    let n_paths = 10usize;
    let mut path_results: Vec<Exp067PathResult> = Vec::new();

    for p in 0..n_paths {
        let path_seed = seed * 1000 + p as u64;

        // Run cascade to get terminal partition
        let mut path_dag = EmergenceDag::new();
        let path_root_id = path_dag.create_root_from_kernel(root.kernel.clone());
        let ordering =
            run_cascade_with_lenses(&mut path_dag, &path_root_id, n, root.sigma, path_seed);
        let minority_ids: Vec<usize> = if let Some(ref ord) = ordering {
            if let Some(ref tp) = ord.terminal_partition {
                let count_0: usize = tp.iter().filter(|&&x| x == 0).count();
                let count_1: usize = tp.iter().filter(|&&x| x == 1).count();
                let minority_label = if count_0 <= count_1 { 0 } else { 1 };
                tp.iter()
                    .enumerate()
                    .filter(|(_, &x)| x == minority_label)
                    .map(|(i, _)| i)
                    .collect()
            } else {
                continue;
            }
        } else {
            continue;
        };

        // Now replicate the first-level branching to find orphans
        // The cascade uses 6 L1 compositions; we need to find which states
        // ended up isolated/tiny after the winning branches' P2→P4 steps
        let l1_compositions = vec![
            PComposition {
                steps: vec![PStep::P2GateScaled, PStep::P4Sectors],
                name: "P2s-P4".into(),
            },
            PComposition {
                steps: vec![PStep::P1Symmetrize, PStep::P2GateScaled, PStep::P4Sectors],
                name: "P1sym-P2s-P4".into(),
            },
            PComposition {
                steps: vec![
                    PStep::P1Perturb { strength: 0.3 },
                    PStep::P2GateScaled,
                    PStep::P4Sectors,
                ],
                name: "P1(0.3)-P2s-P4".into(),
            },
            PComposition {
                steps: vec![PStep::P2GateScaled, PStep::P5Package { tau: 20 }],
                name: "P2s-P5".into(),
            },
            PComposition {
                steps: vec![
                    PStep::P1Symmetrize,
                    PStep::P2GateScaled,
                    PStep::P5Package { tau: 20 },
                ],
                name: "P1sym-P2s-P5".into(),
            },
            PComposition {
                steps: vec![
                    PStep::P1Perturb { strength: 0.1 },
                    PStep::P2GateScaled,
                    PStep::P4Sectors,
                ],
                name: "P1(0.1)-P2s-P4".into(),
            },
        ];

        // For each composition, apply the steps manually to find sector assignments
        let mut all_orphans: Vec<usize> = Vec::new(); // union of orphans from all compositions
        let mut branch_results: Vec<(usize, Vec<usize>)> = Vec::new(); // (macro_n, sector_sizes)

        for (ci, comp) in l1_compositions.iter().enumerate() {
            let comp_seed = path_seed * 100 + ci as u64;
            let mut kernel = root.kernel.clone();
            let mut gate_seed_counter = comp_seed;

            // Apply steps up to and including gating
            for step in &comp.steps {
                match step {
                    PStep::P1Perturb { strength } => {
                        kernel =
                            primitives::p1_random_perturb(&kernel, *strength, gate_seed_counter);
                        gate_seed_counter += 1;
                    }
                    PStep::P1Symmetrize => {
                        kernel = helpers::symmetrize_kernel(&kernel);
                    }
                    PStep::P2GateScaled => {
                        kernel = primitives::p2_random_gate(&kernel, p_gate, gate_seed_counter);
                        gate_seed_counter += 1;
                    }
                    PStep::P4Sectors | PStep::P5Package { .. } => {
                        // After gating, find sectors
                        let sectors = primitives::p4_sectors(&kernel);
                        let max_sector = *sectors.iter().max().unwrap_or(&0);
                        let macro_n = max_sector + 1;
                        // Count sector sizes
                        let mut sizes = vec![0usize; macro_n];
                        for &s in &sectors {
                            sizes[s] += 1;
                        }
                        // Identify orphan states (sector size ≤ 2)
                        let orphans: Vec<usize> =
                            (0..n).filter(|&z| sizes[sectors[z]] <= 2).collect();
                        all_orphans.extend(orphans.iter());
                        branch_results.push((macro_n, sizes));
                        break; // Only need the first sector assignment per composition
                    }
                    _ => {}
                }
            }
        }

        // Deduplicate orphans
        all_orphans.sort();
        all_orphans.dedup();

        let n_orphans = all_orphans.len();
        let minority_size = minority_ids.len();
        let overlap: usize = minority_ids
            .iter()
            .filter(|x| all_orphans.contains(x))
            .count();
        let overlap_frac = if minority_size > 0 {
            overlap as f64 / minority_size as f64
        } else {
            0.0
        };

        path_results.push(Exp067PathResult {
            n_orphans,
            minority_size,
            overlap,
            overlap_frac,
        });
    }

    let n_valid = path_results.len();
    let mean_overlap_frac = if n_valid > 0 {
        path_results.iter().map(|r| r.overlap_frac).sum::<f64>() / n_valid as f64
    } else {
        0.0
    };
    let mean_orphans = if n_valid > 0 {
        path_results.iter().map(|r| r.n_orphans as f64).sum::<f64>() / n_valid as f64
    } else {
        0.0
    };
    let mean_minority = if n_valid > 0 {
        path_results
            .iter()
            .map(|r| r.minority_size as f64)
            .sum::<f64>()
            / n_valid as f64
    } else {
        0.0
    };

    Exp067Metrics {
        n,
        n_paths,
        n_valid,
        expected_isolated,
        mean_orphans,
        mean_minority,
        mean_overlap_frac,
        path_results,
    }
}

#[derive(Clone, Debug)]
struct Exp067PathResult {
    n_orphans: usize,
    minority_size: usize,
    overlap: usize,
    overlap_frac: f64,
}

#[derive(Clone, Debug)]
struct Exp067Metrics {
    n: usize,
    n_paths: usize,
    n_valid: usize,
    expected_isolated: f64,
    mean_orphans: f64,
    mean_minority: f64,
    mean_overlap_frac: f64,
    path_results: Vec<Exp067PathResult>,
}

// ========== EXP-068: Time-Dilation Test ==========

fn run_exp_068(seed: u64, scale: usize) -> Exp068Metrics {
    let n = scale.max(8);
    let mut dag = EmergenceDag::new();
    let root_id = dag.create_root(n, seed);
    let root = dag.nodes[&root_id].clone();

    // MI at lag 1
    let i_lag1 = compute_mi(&root.kernel);

    // MI at lag 20 (one cascade level)
    let k20 = matrix_power(&root.kernel, 20);
    let i_lag20 = compute_mi(&k20);

    // MI at lag 400 (two cascade levels) — only for n ≤ 128 to keep runtime reasonable
    let i_lag400 = if n <= 128 {
        let k400 = matrix_power(&root.kernel, 400);
        compute_mi(&k400)
    } else {
        // For n=256, use K^20 raised to 20th power
        let k400 = matrix_power(&k20, 20);
        compute_mi(&k400)
    };

    // Run one cascade path and extract level-1 macro kernel MI
    let mut path_dag = EmergenceDag::new();
    let path_root_id = path_dag.create_root_from_kernel(root.kernel.clone());
    let mut i_level1 = 0.0f64;
    let mut i_level2 = 0.0f64;
    let mut level1_n = 0usize;
    let mut level2_n = 0usize;

    if let Some(_ordering) =
        run_cascade_with_lenses(&mut path_dag, &path_root_id, n, root.sigma, seed * 1000)
    {
        // Extract macro kernels at each cascade level
        // Merge nodes are the coarse-grained ones (smaller n than root)
        // Sort by kernel size descending; skip root and branch nodes (which have n=root_n)
        let mut macro_kernels: Vec<(usize, &MarkovKernel)> = path_dag
            .nodes
            .values()
            .filter(|node| node.kernel.n < n) // only coarse-grained nodes
            .map(|node| (node.kernel.n, &node.kernel))
            .collect();
        macro_kernels.sort_by_key(|(kn, _)| std::cmp::Reverse(*kn));
        // macro_kernels[0] = L1 merge (largest coarse-grained), [1] = L2, etc.
        if !macro_kernels.is_empty() {
            level1_n = macro_kernels[0].0;
            i_level1 = compute_mi(macro_kernels[0].1);
        }
        if macro_kernels.len() > 1 {
            level2_n = macro_kernels[1].0;
            i_level2 = compute_mi(macro_kernels[1].1);
        }
    }

    let ratio_lag20_vs_level1 = if i_level1 > 1e-15 {
        i_lag20 / i_level1
    } else {
        0.0
    };
    let ratio_lag400_vs_level2 = if i_level2 > 1e-15 {
        i_lag400 / i_level2
    } else {
        0.0
    };

    Exp068Metrics {
        n,
        i_lag1,
        i_lag20,
        i_lag400,
        i_level1,
        i_level2,
        level1_n,
        level2_n,
        ratio_lag20_vs_level1,
        ratio_lag400_vs_level2,
    }
}

#[derive(Clone, Debug)]
struct Exp068Metrics {
    n: usize,
    i_lag1: f64,
    i_lag20: f64,
    i_lag400: f64,
    i_level1: f64,
    i_level2: f64,
    level1_n: usize,
    level2_n: usize,
    ratio_lag20_vs_level1: f64,
    ratio_lag400_vs_level2: f64,
}

/// Get cascade terminal partition (reused across EXP-063/064/065)
fn get_cascade_partition(
    kernel: &MarkovKernel,
    sigma: f64,
    seed: u64,
    n_paths: usize,
) -> (Vec<usize>, usize) {
    let n = kernel.n;
    let mut terminal_partitions: Vec<Vec<usize>> = Vec::new();
    for p in 0..n_paths {
        let path_seed = seed * 1000 + p as u64;
        let mut path_dag = EmergenceDag::new();
        let path_root_id = path_dag.create_root_from_kernel(kernel.clone());
        if let Some(ordering) =
            run_cascade_with_lenses(&mut path_dag, &path_root_id, n, sigma, path_seed)
        {
            if let Some(tp) = ordering.terminal_partition {
                terminal_partitions.push(tp);
            }
        }
    }
    let n_terminal = terminal_partitions.len();
    if n_terminal == 0 {
        return (vec![0; n], 0);
    }
    (terminal_partitions[0].clone(), n_terminal)
}

// ========== EXP-062: Minority Characterization ==========

#[derive(Clone, Debug, Serialize, Deserialize)]
struct Exp062Metrics {
    n: usize,
    root_sigma: f64,
    root_gap: f64,
    minority_size: usize,
    majority_size: usize,
    // Stationary probability
    mean_pi_minority: f64,
    mean_pi_majority: f64,
    pi_ratio: f64,          // minority / majority (< 1 if minority has lower π)
    total_pi_minority: f64, // total stationary mass in minority
    // Self-loop strength
    mean_selfloop_minority: f64,
    mean_selfloop_majority: f64,
    // Max outgoing transition
    mean_maxout_minority: f64,
    mean_maxout_majority: f64,
    // Row entropy
    mean_entropy_minority: f64,
    mean_entropy_majority: f64,
    // Degree after P2 gating
    mean_degree_minority: f64,
    mean_degree_majority: f64,
    // π-threshold partition: best agreement with cascade
    best_pi_agree: f64,
    best_pi_k: usize, // number of lowest-π states in best threshold
    // Number of cascade paths used
    n_terminal: usize,
}

fn run_exp_062(seed: u64, scale: usize) -> Exp062Metrics {
    let n = scale.max(8);
    let mut dag = EmergenceDag::new();
    let root_id = dag.create_root(n, seed);
    let root = dag.nodes[&root_id].clone();

    // Compute stationary distribution of root kernel
    let pi = root.kernel.stationary(10000, 1e-12);

    // Compute per-state properties on root kernel
    let mut selfloops = vec![0.0f64; n];
    let mut maxouts = vec![0.0f64; n];
    let mut entropies = vec![0.0f64; n];
    for z in 0..n {
        selfloops[z] = root.kernel.kernel[z][z];
        let mut max_out = 0.0f64;
        let mut entropy = 0.0f64;
        for j in 0..n {
            let p = root.kernel.kernel[z][j];
            if p > max_out {
                max_out = p;
            }
            if p > 1e-15 {
                entropy -= p * p.ln();
            }
        }
        maxouts[z] = max_out;
        entropies[z] = entropy;
    }

    // Degree after P2 gating
    let gate_prob = helpers::scale_gating_prob(n);
    let mut degrees = vec![0.0f64; n];
    for z in 0..n {
        let mut deg = 0usize;
        for j in 0..n {
            let p = root.kernel.kernel[z][j];
            if p >= (1.0 - gate_prob) / n as f64 {
                // Edge survives gating (above the deletion threshold)
                deg += 1;
            }
        }
        degrees[z] = deg as f64;
    }

    // Run cascade paths to get the terminal partition
    let n_cascade_paths = 10;
    let mut terminal_partitions: Vec<Vec<usize>> = Vec::new();
    for p in 0..n_cascade_paths {
        let path_seed = seed * 1000 + p as u64;
        let mut path_dag = EmergenceDag::new();
        let path_root_id = path_dag.create_root_from_kernel(root.kernel.clone());
        if let Some(ordering) =
            run_cascade_with_lenses(&mut path_dag, &path_root_id, n, root.sigma, path_seed)
        {
            if let Some(tp) = ordering.terminal_partition {
                terminal_partitions.push(tp);
            }
        }
    }
    let n_terminal = terminal_partitions.len();
    if n_terminal == 0 {
        return Exp062Metrics {
            n,
            root_sigma: root.sigma,
            root_gap: root.gap,
            minority_size: 0,
            majority_size: n,
            mean_pi_minority: 0.0,
            mean_pi_majority: 0.0,
            pi_ratio: 0.0,
            total_pi_minority: 0.0,
            mean_selfloop_minority: 0.0,
            mean_selfloop_majority: 0.0,
            mean_maxout_minority: 0.0,
            mean_maxout_majority: 0.0,
            mean_entropy_minority: 0.0,
            mean_entropy_majority: 0.0,
            mean_degree_minority: 0.0,
            mean_degree_majority: 0.0,
            best_pi_agree: 0.0,
            best_pi_k: 0,
            n_terminal: 0,
        };
    }

    // Use the first path's terminal partition as reference
    // (partition membership is path-dependent; CLO-061 retracted)
    let partition = &terminal_partitions[0];

    // Identify minority (smaller group)
    let count_0: usize = partition.iter().filter(|&&x| x == 0).count();
    let count_1: usize = partition.iter().filter(|&&x| x == 1).count();
    let minority_label = if count_0 <= count_1 { 0 } else { 1 };
    let minority_size = count_0.min(count_1);
    let majority_size = count_0.max(count_1);

    // Compute mean properties for minority vs majority
    let mut pi_min_sum = 0.0f64;
    let mut pi_maj_sum = 0.0f64;
    let mut sl_min_sum = 0.0f64;
    let mut sl_maj_sum = 0.0f64;
    let mut mo_min_sum = 0.0f64;
    let mut mo_maj_sum = 0.0f64;
    let mut en_min_sum = 0.0f64;
    let mut en_maj_sum = 0.0f64;
    let mut dg_min_sum = 0.0f64;
    let mut dg_maj_sum = 0.0f64;

    for z in 0..n {
        if partition[z] == minority_label {
            pi_min_sum += pi[z];
            sl_min_sum += selfloops[z];
            mo_min_sum += maxouts[z];
            en_min_sum += entropies[z];
            dg_min_sum += degrees[z];
        } else {
            pi_maj_sum += pi[z];
            sl_maj_sum += selfloops[z];
            mo_maj_sum += maxouts[z];
            en_maj_sum += entropies[z];
            dg_maj_sum += degrees[z];
        }
    }

    let mean_pi_min = if minority_size > 0 {
        pi_min_sum / minority_size as f64
    } else {
        0.0
    };
    let mean_pi_maj = if majority_size > 0 {
        pi_maj_sum / majority_size as f64
    } else {
        0.0
    };
    let pi_ratio = if mean_pi_maj > 1e-15 {
        mean_pi_min / mean_pi_maj
    } else {
        0.0
    };

    let mean_sl_min = if minority_size > 0 {
        sl_min_sum / minority_size as f64
    } else {
        0.0
    };
    let mean_sl_maj = if majority_size > 0 {
        sl_maj_sum / majority_size as f64
    } else {
        0.0
    };
    let mean_mo_min = if minority_size > 0 {
        mo_min_sum / minority_size as f64
    } else {
        0.0
    };
    let mean_mo_maj = if majority_size > 0 {
        mo_maj_sum / majority_size as f64
    } else {
        0.0
    };
    let mean_en_min = if minority_size > 0 {
        en_min_sum / minority_size as f64
    } else {
        0.0
    };
    let mean_en_maj = if majority_size > 0 {
        en_maj_sum / majority_size as f64
    } else {
        0.0
    };
    let mean_dg_min = if minority_size > 0 {
        dg_min_sum / minority_size as f64
    } else {
        0.0
    };
    let mean_dg_maj = if majority_size > 0 {
        dg_maj_sum / majority_size as f64
    } else {
        0.0
    };

    // Test: does a π-threshold partition match the cascade?
    // Sort states by π, try putting the bottom k states as "minority"
    let mut pi_sorted: Vec<(usize, f64)> = pi.iter().enumerate().map(|(i, &p)| (i, p)).collect();
    pi_sorted.sort_by(|a, b| a.1.partial_cmp(&b.1).unwrap());

    let mut best_pi_agree = 0.0f64;
    let mut best_pi_k = 0usize;
    // Try k from 1 to n/2
    for k in 1..=(n / 2) {
        // pi-threshold partition: bottom k states → minority
        let mut pi_partition = vec![1usize; n]; // majority by default
        for i in 0..k {
            pi_partition[pi_sorted[i].0] = 0; // minority
        }
        // Compare with cascade partition (with label-flip)
        let agree: usize = pi_partition
            .iter()
            .zip(partition.iter())
            .filter(|(&a, &b)| a == b)
            .count();
        let overlap = agree.max(n - agree) as f64 / n as f64;
        if overlap > best_pi_agree {
            best_pi_agree = overlap;
            best_pi_k = k;
        }
    }

    Exp062Metrics {
        n,
        root_sigma: root.sigma,
        root_gap: root.gap,
        minority_size,
        majority_size,
        mean_pi_minority: mean_pi_min,
        mean_pi_majority: mean_pi_maj,
        pi_ratio,
        total_pi_minority: pi_min_sum,
        mean_selfloop_minority: mean_sl_min,
        mean_selfloop_majority: mean_sl_maj,
        mean_maxout_minority: mean_mo_min,
        mean_maxout_majority: mean_mo_maj,
        mean_entropy_minority: mean_en_min,
        mean_entropy_majority: mean_en_maj,
        mean_degree_minority: mean_dg_min,
        mean_degree_majority: mean_dg_maj,
        best_pi_agree,
        best_pi_k,
        n_terminal,
    }
}

// ========== EXP-063: Pairwise Flow Analysis ==========

#[derive(Clone, Debug, Serialize, Deserialize)]
struct Exp063Metrics {
    n: usize,
    root_sigma: f64,
    root_gap: f64,
    minority_size: usize,
    majority_size: usize,
    n_terminal: usize,
    // Flow matrix (π-weighted)
    f_mm: f64,  // flow within minority
    f_m_M: f64, // minority → majority
    f_M_m: f64, // majority → minority
    f_M_M: f64, // flow within majority
    // Derived
    flow_asym: f64,      // f_mM / f_Mm
    cohesion: f64,       // f_mm / total_π_min
    escape_rate: f64,    // f_mM / total_π_min
    absorb_steps: usize, // steps until 95% in majority
    // Null comparison
    n_null: usize,
    z_cohesion: f64,
    z_escape: f64,
    z_asym: f64,
}

fn compute_flow_metrics(
    kernel: &MarkovKernel,
    pi: &[f64],
    is_minority: &[bool],
) -> (f64, f64, f64, f64, f64, f64, f64, usize) {
    let n = kernel.n;
    let mut f_mm = 0.0f64;
    let mut f_m_big = 0.0f64;
    let mut f_big_m = 0.0f64;
    let mut f_big_big = 0.0f64;
    for i in 0..n {
        for j in 0..n {
            let flow = pi[i] * kernel.kernel[i][j];
            if is_minority[i] && is_minority[j] {
                f_mm += flow;
            } else if is_minority[i] && !is_minority[j] {
                f_m_big += flow;
            } else if !is_minority[i] && is_minority[j] {
                f_big_m += flow;
            } else {
                f_big_big += flow;
            }
        }
    }
    let total_pi_min: f64 = (0..n).filter(|&z| is_minority[z]).map(|z| pi[z]).sum();
    let flow_asym = if f_big_m > 1e-15 {
        f_m_big / f_big_m
    } else {
        f64::INFINITY
    };
    let cohesion = if total_pi_min > 1e-15 {
        f_mm / total_pi_min
    } else {
        0.0
    };
    let escape = if total_pi_min > 1e-15 {
        f_m_big / total_pi_min
    } else {
        0.0
    };

    // Absorption time: starting uniform in minority, steps until >95% in majority
    let min_count = (0..n).filter(|&z| is_minority[z]).count();
    let mut dist = vec![0.0f64; n];
    for z in 0..n {
        if is_minority[z] {
            dist[z] = 1.0 / min_count as f64;
        }
    }
    let mut absorb_steps = 0usize;
    for step in 1..=1000 {
        dist = kernel.step(&dist);
        let maj_mass: f64 = (0..n).filter(|&z| !is_minority[z]).map(|z| dist[z]).sum();
        if maj_mass >= 0.95 {
            absorb_steps = step;
            break;
        }
    }
    if absorb_steps == 0 {
        absorb_steps = 1000;
    }

    (
        f_mm,
        f_m_big,
        f_big_m,
        f_big_big,
        flow_asym,
        cohesion,
        escape,
        absorb_steps,
    )
}

fn run_exp_063(seed: u64, scale: usize) -> Exp063Metrics {
    let n = scale.max(8);
    let mut dag = EmergenceDag::new();
    let root_id = dag.create_root(n, seed);
    let root = dag.nodes[&root_id].clone();
    let pi = root.kernel.stationary(10000, 1e-12);

    let (partition, n_terminal) = get_cascade_partition(&root.kernel, root.sigma, seed, 10);
    if n_terminal == 0 {
        return Exp063Metrics {
            n,
            root_sigma: root.sigma,
            root_gap: root.gap,
            minority_size: 0,
            majority_size: n,
            n_terminal: 0,
            f_mm: 0.0,
            f_m_M: 0.0,
            f_M_m: 0.0,
            f_M_M: 0.0,
            flow_asym: 0.0,
            cohesion: 0.0,
            escape_rate: 0.0,
            absorb_steps: 0,
            n_null: 0,
            z_cohesion: 0.0,
            z_escape: 0.0,
            z_asym: 0.0,
        };
    }

    // Identify minority
    let count_0: usize = partition.iter().filter(|&&x| x == 0).count();
    let count_1: usize = partition.iter().filter(|&&x| x == 1).count();
    let minority_label = if count_0 <= count_1 { 0 } else { 1 };
    let minority_size = count_0.min(count_1);
    let majority_size = count_0.max(count_1);

    let is_minority: Vec<bool> = partition.iter().map(|&x| x == minority_label).collect();
    let (f_mm, f_m_M, f_M_m, f_M_M, flow_asym, cohesion, escape_rate, absorb_steps) =
        compute_flow_metrics(&root.kernel, &pi, &is_minority);

    // Null comparison: 100 random partitions of same minority_size
    let n_null = 100usize;
    let mut null_cohesions = Vec::with_capacity(n_null);
    let mut null_escapes = Vec::with_capacity(n_null);
    let mut null_asyms = Vec::with_capacity(n_null);
    use std::collections::HashSet;
    for trial in 0..n_null {
        // Simple random subset of size minority_size
        let mut rng_state: u64 = seed * 100000 + trial as u64 * 7919 + 13;
        let mut chosen = HashSet::new();
        while chosen.len() < minority_size {
            rng_state = rng_state
                .wrapping_mul(6364136223846793005)
                .wrapping_add(1442695040888963407);
            let idx = (rng_state >> 33) as usize % n;
            chosen.insert(idx);
        }
        let null_min: Vec<bool> = (0..n).map(|z| chosen.contains(&z)).collect();
        let (_, _, _, _, asym, coh, esc, _) = compute_flow_metrics(&root.kernel, &pi, &null_min);
        null_cohesions.push(coh);
        null_escapes.push(esc);
        null_asyms.push(asym);
    }

    let mean_coh: f64 = null_cohesions.iter().sum::<f64>() / n_null as f64;
    let std_coh: f64 = (null_cohesions
        .iter()
        .map(|&x| (x - mean_coh).powi(2))
        .sum::<f64>()
        / n_null as f64)
        .sqrt();
    let mean_esc: f64 = null_escapes.iter().sum::<f64>() / n_null as f64;
    let std_esc: f64 = (null_escapes
        .iter()
        .map(|&x| (x - mean_esc).powi(2))
        .sum::<f64>()
        / n_null as f64)
        .sqrt();
    let mean_asym: f64 = null_asyms.iter().sum::<f64>() / n_null as f64;
    let std_asym: f64 = (null_asyms
        .iter()
        .map(|&x| (x - mean_asym).powi(2))
        .sum::<f64>()
        / n_null as f64)
        .sqrt();

    let z_cohesion = if std_coh > 1e-15 {
        (cohesion - mean_coh) / std_coh
    } else {
        0.0
    };
    let z_escape = if std_esc > 1e-15 {
        (escape_rate - mean_esc) / std_esc
    } else {
        0.0
    };
    let z_asym = if std_asym > 1e-15 {
        (flow_asym - mean_asym) / std_asym
    } else {
        0.0
    };

    Exp063Metrics {
        n,
        root_sigma: root.sigma,
        root_gap: root.gap,
        minority_size,
        majority_size,
        n_terminal,
        f_mm,
        f_m_M,
        f_M_m,
        f_M_M,
        flow_asym,
        cohesion,
        escape_rate,
        absorb_steps,
        n_null,
        z_cohesion,
        z_escape,
        z_asym,
    }
}

// ========== EXP-064: Integrated Information of Cascade Partition ==========

#[derive(Clone, Debug, Serialize, Deserialize)]
struct Exp064Metrics {
    n: usize,
    root_sigma: f64,
    root_gap: f64,
    minority_size: usize,
    n_terminal: usize,
    i_whole: f64,
    phi_cascade: f64,
    phi_rand_mean: f64,
    phi_rand_std: f64,
    z_score: f64,
    phi_fiedler: f64,
    rank: usize, // rank of cascade among all (1 = lowest Φ)
    n_null: usize,
}

fn run_exp_064(seed: u64, scale: usize) -> Exp064Metrics {
    let n = scale.max(8);
    let mut dag = EmergenceDag::new();
    let root_id = dag.create_root(n, seed);
    let root = dag.nodes[&root_id].clone();

    let i_whole = compute_mi(&root.kernel);

    let (partition, n_terminal) = get_cascade_partition(&root.kernel, root.sigma, seed, 10);

    // Identify minority
    let count_0: usize = partition.iter().filter(|&&x| x == 0).count();
    let count_1: usize = partition.iter().filter(|&&x| x == 1).count();
    let minority_label = if count_0 <= count_1 { 0 } else { 1 };
    let minority_size = count_0.min(count_1);

    // Cascade partition as bool array
    let cascade_part: Vec<bool> = partition.iter().map(|&x| x == minority_label).collect();
    let phi_cascade = compute_phi(&root.kernel, &cascade_part);

    // Fiedler partition
    let (_, eigvec) = root.kernel.spectral_gap_with_eigvec();
    let fiedler_part: Vec<bool> = eigvec.iter().map(|&v| v >= 0.0).collect();
    let phi_fiedler = compute_phi(&root.kernel, &fiedler_part);

    // Random partitions of same minority_size
    let n_null = 200usize;
    let mut null_phis = Vec::with_capacity(n_null);
    use std::collections::HashSet;
    for trial in 0..n_null {
        let mut rng_state: u64 = seed * 100000 + trial as u64 * 7919 + 31;
        let mut chosen = HashSet::new();
        while chosen.len() < minority_size {
            rng_state = rng_state
                .wrapping_mul(6364136223846793005)
                .wrapping_add(1442695040888963407);
            let idx = (rng_state >> 33) as usize % n;
            chosen.insert(idx);
        }
        let null_part: Vec<bool> = (0..n).map(|z| chosen.contains(&z)).collect();
        null_phis.push(compute_phi(&root.kernel, &null_part));
    }

    let phi_rand_mean = null_phis.iter().sum::<f64>() / n_null as f64;
    let phi_rand_std = (null_phis
        .iter()
        .map(|&x| (x - phi_rand_mean).powi(2))
        .sum::<f64>()
        / n_null as f64)
        .sqrt();
    let z_score = if phi_rand_std > 1e-15 {
        (phi_cascade - phi_rand_mean) / phi_rand_std
    } else {
        0.0
    };

    // Rank: how many null phis are < phi_cascade? (1 = lowest)
    let rank = null_phis.iter().filter(|&&x| x < phi_cascade).count() + 1;

    Exp064Metrics {
        n,
        root_sigma: root.sigma,
        root_gap: root.gap,
        minority_size,
        n_terminal,
        i_whole,
        phi_cascade,
        phi_rand_mean,
        phi_rand_std,
        z_score,
        phi_fiedler,
        rank,
        n_null,
    }
}

// ========== EXP-065: Phi Across the Cascade Stack ==========

#[derive(Clone, Debug, Serialize, Deserialize)]
struct Exp065LevelMetrics {
    level: usize,
    macro_n: usize,
    i_whole: f64,
    phi_mip: Option<f64>,
    mip_min_size: usize,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
struct Exp065Metrics {
    n: usize,
    root_sigma: f64,
    root_gap: f64,
    depth: usize,
    levels: Vec<Exp065LevelMetrics>,
}

fn run_exp_065(seed: u64, scale: usize) -> Exp065Metrics {
    let n = scale.max(8);
    let mut dag = EmergenceDag::new();
    let root_id = dag.create_root(n, seed);
    let root = dag.nodes[&root_id].clone();

    let mut levels: Vec<Exp065LevelMetrics> = Vec::new();

    // Level 0: root kernel
    let i_root = compute_mi(&root.kernel);
    let (phi_mip_root, mip_part_root) = if n <= 64 {
        let (phi, part) = queyranne_mip(&root.kernel);
        let min_side = part
            .iter()
            .filter(|&&x| x)
            .count()
            .min(part.iter().filter(|&&x| !x).count());
        (Some(phi), min_side)
    } else {
        (None, 0)
    };
    levels.push(Exp065LevelMetrics {
        level: 0,
        macro_n: n,
        i_whole: i_root,
        phi_mip: phi_mip_root,
        mip_min_size: mip_part_root,
    });

    // Run one cascade path, collecting intermediate kernels
    let path_seed = seed * 1000;
    let mut path_dag = EmergenceDag::new();
    let path_root_id = path_dag.create_root_from_kernel(root.kernel.clone());

    let mut current_id = path_root_id.clone();
    let max_levels = 10;
    let mut depth = 0usize;

    while depth < max_levels {
        let current_sigma = path_dag.nodes[&current_id].sigma;
        let current_n = path_dag.nodes[&current_id].kernel.n;
        if current_n <= 2 {
            break;
        }

        let lk_comps: Vec<PComposition> = vec![
            PComposition::new(vec![PStep::P2GateScaled, PStep::P4Sectors], "P2s→P4"),
            PComposition::new(
                vec![PStep::P2GateScaled, PStep::P5Package { tau: 20 }],
                "P2s→P5",
            ),
            PComposition::new(
                vec![
                    PStep::P1Perturb { strength: 1.0 },
                    PStep::P2GateScaled,
                    PStep::P4Sectors,
                ],
                "P1(1)→P2s→P4",
            ),
            PComposition::new(
                vec![
                    PStep::P1Perturb { strength: 1.0 },
                    PStep::P2GateScaled,
                    PStep::P5Package { tau: 20 },
                ],
                "P1(1)→P2s→P5",
            ),
            PComposition::new(
                vec![
                    PStep::P1Perturb { strength: 2.0 },
                    PStep::P2GateScaled,
                    PStep::P4Sectors,
                ],
                "P1(2)→P2s→P4",
            ),
            PComposition::new(
                vec![
                    PStep::P1Perturb { strength: 2.0 },
                    PStep::P2GateScaled,
                    PStep::P5Package { tau: 20 },
                ],
                "P1(2)→P2s→P5",
            ),
            PComposition::new(
                vec![
                    PStep::P1Perturb { strength: 5.0 },
                    PStep::P2GateScaled,
                    PStep::P4Sectors,
                ],
                "P1(5)→P2s→P4",
            ),
            PComposition::new(
                vec![
                    PStep::P1Perturb { strength: 5.0 },
                    PStep::P2GateScaled,
                    PStep::P5Package { tau: 20 },
                ],
                "P1(5)→P2s→P5",
            ),
        ];

        let depth_seed = path_seed + (depth as u64 + 1) * 10000;
        let mut lk_branches: Vec<String> = Vec::new();
        for (i, comp) in lk_comps.iter().enumerate() {
            if let Ok(id) = path_dag.branch(&current_id, comp, depth_seed + (i as u64 + 1) * 1000) {
                lk_branches.push(id);
            }
        }
        if lk_branches.len() < 2 {
            break;
        }

        let mut next_best_id: Option<String> = None;
        let mut next_best_gap = 0.0f64;
        for i in 0..lk_branches.len() {
            for j in (i + 1)..lk_branches.len() {
                if let Ok(merge_id) = path_dag.merge(
                    &current_id,
                    &lk_branches[i],
                    &lk_branches[j],
                    depth_seed + 5000 + (i * lk_branches.len() + j) as u64 * 100,
                ) {
                    let m = &path_dag.nodes[&merge_id];
                    let dpi_vs_prev = m.sigma <= current_sigma + 1e-10;
                    if dpi_vs_prev && m.gap > 0.01 && m.gap > next_best_gap {
                        next_best_gap = m.gap;
                        next_best_id = Some(merge_id.clone());
                    }
                }
            }
        }

        match next_best_id {
            Some(next_id) => {
                let next_kernel = path_dag.nodes[&next_id].kernel.clone();
                let macro_n = next_kernel.n;
                depth += 1;

                let i_level = compute_mi(&next_kernel);
                let (phi_mip_level, mip_min) = if macro_n <= 64 && macro_n > 2 {
                    let (phi, part) = queyranne_mip(&next_kernel);
                    let min_side = part
                        .iter()
                        .filter(|&&x| x)
                        .count()
                        .min(part.iter().filter(|&&x| !x).count());
                    (Some(phi), min_side)
                } else if macro_n == 2 {
                    let part = vec![true, false];
                    let phi = compute_phi(&next_kernel, &part);
                    (Some(phi), 1)
                } else {
                    (None, 0)
                };

                levels.push(Exp065LevelMetrics {
                    level: depth,
                    macro_n,
                    i_whole: i_level,
                    phi_mip: phi_mip_level,
                    mip_min_size: mip_min,
                });

                current_id = next_id;
            }
            None => break,
        }
    }

    Exp065Metrics {
        n,
        root_sigma: root.sigma,
        root_gap: root.gap,
        depth,
        levels,
    }
}

fn run_single(exp: &str, seed: u64, scale: usize, config_filter: Option<&str>) {
    match exp {
        "EXP-041" => {
            let metrics = run_exp_041(seed, scale);
            println!("\n=== EXP-041 Results (seed={}, scale={}) ===", seed, scale);
            println!(
                "Root:     sigma={:.6} gap={:.6} blocks={}",
                metrics.root_sigma, metrics.root_gap, metrics.root_blocks
            );
            println!(
                "Branch A: n={:3} sigma={:.6} gap={:.6} DPI={} RM={:.4} blocks={}",
                metrics.branch_a_n,
                metrics.branch_a_sigma,
                metrics.branch_a_gap,
                metrics.branch_a_dpi,
                metrics.branch_a_rm,
                metrics.branch_a_blocks
            );
            println!(
                "Branch B: n={:3} sigma={:.6} gap={:.6} DPI={} RM={:.4} blocks={}",
                metrics.branch_b_n,
                metrics.branch_b_sigma,
                metrics.branch_b_gap,
                metrics.branch_b_dpi,
                metrics.branch_b_rm,
                metrics.branch_b_blocks
            );
            println!("Merge:    n={:3} sigma={:.6} gap={:.6} DPI_root={} DPI_A={} DPI_B={} RM={:.4} blocks={}",
                metrics.merge_n, metrics.merge_sigma, metrics.merge_gap,
                metrics.merge_dpi_vs_root, metrics.merge_dpi_vs_a, metrics.merge_dpi_vs_b,
                metrics.merge_rm, metrics.merge_blocks);
            println!(
                "KEY: merge_has_dpi_and_dynamics={} beats_a={} beats_b={}",
                metrics.merge_has_dpi_and_dynamics, metrics.merge_beats_a, metrics.merge_beats_b
            );
        }
        "EXP-042" => {
            let metrics = run_exp_042(seed, scale);
            println!("\n=== EXP-042 Results (seed={}, scale={}) ===", seed, scale);
            println!(
                "Root: sigma={:.6} gap={:.6}",
                metrics.root_sigma, metrics.root_gap
            );
            println!("Viable compositions: {}/4", metrics.n_compositions_viable);
            println!(
                "Pairs tested: {} success: {}",
                metrics.n_pairs_tested, metrics.n_pairs_success
            );
            println!(
                "Best pair: '{}' merge_n={} gap={:.6} sigma={:.6}",
                metrics.best_pair,
                metrics.best_merge_n,
                metrics.best_merge_gap,
                metrics.best_merge_sigma
            );
            println!(
                "KEY: any_success={} n_success={} n_viable={}",
                metrics.any_success, metrics.n_pairs_success, metrics.n_compositions_viable
            );
        }
        "EXP-043" => {
            let metrics = run_exp_043(seed, scale);
            println!("\n=== EXP-043 Results (seed={}, scale={}) ===", seed, scale);
            println!(
                "Root: sigma={:.6} branches={}/3",
                metrics.root_sigma, metrics.n_branches
            );
            println!(
                "2-way: AB={} AC={} BC={} any={}",
                metrics.twoway_ab_success,
                metrics.twoway_ac_success,
                metrics.twoway_bc_success,
                metrics.any_twoway
            );
            println!(
                "3-way: n={} sigma={:.6} gap={:.6} DPI={} RM={:.4} success={}",
                metrics.threeway_n,
                metrics.threeway_sigma,
                metrics.threeway_gap,
                metrics.threeway_dpi,
                metrics.threeway_rm,
                metrics.threeway_success
            );
            println!(
                "KEY: threeway_success={} any_twoway={} threeway_beats_twoway={}",
                metrics.threeway_success, metrics.any_twoway, metrics.threeway_beats_twoway
            );
        }
        "EXP-044" => {
            let metrics = run_exp_044(seed, scale);
            println!("\n=== EXP-044 Results (seed={}, scale={}) ===", seed, scale);
            println!(
                "Root: sigma={:.6} gap={:.6}",
                metrics.root_sigma, metrics.root_gap
            );
            println!(
                "Viable: P4={} P5={} total={}/6",
                metrics.p4_viable, metrics.p5_viable, metrics.total_viable
            );
            println!(
                "P4×P4: {}/{} P4×P5: {}/{} P5×P5: {}/{}",
                metrics.p4_p4_success,
                metrics.p4_p4_pairs,
                metrics.p4_p5_success,
                metrics.p4_p5_pairs,
                metrics.p5_p5_success,
                metrics.p5_p5_pairs
            );
            println!(
                "Best pair: '{}' merge_n={} gap={:.6} sigma={:.6}",
                metrics.best_pair,
                metrics.best_merge_n,
                metrics.best_merge_gap,
                metrics.best_merge_sigma
            );
            println!(
                "KEY: any_success={} p4_viable={} p5_viable={} p4p5_success={}",
                metrics.any_success, metrics.p4_viable, metrics.p5_viable, metrics.p4_p5_success
            );
        }
        "EXP-045" => {
            let metrics = run_exp_045(seed, scale);
            println!("\n=== EXP-045 Results (seed={}, scale={}) ===", seed, scale);
            println!(
                "Root: sigma={:.6} gap={:.6}",
                metrics.root_sigma, metrics.root_gap
            );
            println!(
                "L1 merge: n={} sigma={:.6} gap={:.6} DPI={} success={}",
                metrics.l1_merge_n,
                metrics.l1_merge_sigma,
                metrics.l1_merge_gap,
                metrics.l1_merge_dpi,
                metrics.l1_success
            );
            println!("L2: branches_viable={} merge_n={} sigma={:.6} gap={:.6} DPI_vs_L1={} DPI_vs_root={} success={}",
                metrics.l2_branches_viable, metrics.l2_merge_n,
                metrics.l2_merge_sigma, metrics.l2_merge_gap,
                metrics.l2_merge_dpi_vs_l1, metrics.l2_merge_dpi_vs_root, metrics.l2_success);
            println!(
                "KEY: l1_success={} l2_success={} depth_improves_gap={} depth_preserves_dpi={}",
                metrics.l1_success,
                metrics.l2_success,
                metrics.depth_improves_gap,
                metrics.depth_preserves_dpi
            );
        }
        "EXP-046" => {
            let metrics = run_exp_046(seed, scale);
            println!("\n=== EXP-046 Results (seed={}, scale={}) ===", seed, scale);
            println!(
                "Root: sigma={:.6} gap={:.6}",
                metrics.root_sigma, metrics.root_gap
            );
            println!(
                "Merges: tested={} success={}",
                metrics.n_merges_tested, metrics.n_merges_success
            );
            println!(
                "Best: n={} gap={:.6} sigma={:.6} RM={:.4} blocks={} connected={}",
                metrics.best_merge_n,
                metrics.best_merge_gap,
                metrics.best_merge_sigma,
                metrics.best_merge_rm,
                metrics.best_merge_blocks,
                metrics.merge_is_connected
            );
            println!(
                "Sigma reduction: {:.1}x  Reversibility: {:.6}",
                metrics.sigma_reduction, metrics.merge_reversibility
            );
            println!(
                "Sigma trajectory: t1={:.6} t5={:.6} t10={:.6} t15={:.6} t20={:.6}",
                metrics.sigma_t1,
                metrics.sigma_t5,
                metrics.sigma_t10,
                metrics.sigma_t15,
                metrics.sigma_t20
            );
            println!(
                "Branch sigmas: A={:.6} B={:.6}",
                metrics.branch_a_sigma, metrics.branch_b_sigma
            );
            println!(
                "KEY: sigma_reduction={:.1} reversibility={:.6} connected={}",
                metrics.sigma_reduction, metrics.merge_reversibility, metrics.merge_is_connected
            );
        }
        "EXP-047" => {
            let metrics = run_exp_047(seed, scale);
            println!("\n=== EXP-047 Results (seed={}, scale={}) ===", seed, scale);
            println!(
                "Root: sigma={:.6} gap={:.6}",
                metrics.root_sigma, metrics.root_gap
            );
            println!(
                "L1: viable={} merge_n={} sigma={:.6} gap={:.6} success={}",
                metrics.l1_viable,
                metrics.l1_merge_n,
                metrics.l1_merge_sigma,
                metrics.l1_merge_gap,
                metrics.l1_success
            );
            println!(
                "L2: viable={} merge_n={} sigma={:.6} gap={:.6} success={} DPI_vs_root={}",
                metrics.l2_viable,
                metrics.l2_merge_n,
                metrics.l2_merge_sigma,
                metrics.l2_merge_gap,
                metrics.l2_success,
                metrics.l2_dpi_vs_root
            );
            println!(
                "KEY: total_depth={} l1_success={} l2_success={}",
                metrics.total_depth, metrics.l1_success, metrics.l2_success
            );
        }
        "EXP-048" => {
            let metrics = run_exp_048(seed, scale);
            println!("\n=== EXP-048 Results (seed={}, scale={}) ===", seed, scale);
            println!(
                "L1 merge: n={} gap={:.6} sigma={:.6}",
                metrics.l1_merge_n, metrics.l1_merge_gap, metrics.l1_merge_sigma
            );
            println!(
                "Grid: {}/{} viable",
                metrics.n_combos_viable, metrics.n_combos_tested
            );
            println!(
                "By P1 strength: none={}/6 s0.5={}/6 s1.0={}/6 s2.0={}/6 s5.0={}/6",
                metrics.v_none, metrics.v_s05, metrics.v_s10, metrics.v_s20, metrics.v_s50
            );
            println!(
                "By P2 gating:   scaled={}/10 g90={}/10 g95={}/10",
                metrics.v_scaled, metrics.v_g90, metrics.v_g95
            );
            println!(
                "By lens:        P4={}/15 P5={}/15",
                metrics.v_p4, metrics.v_p5
            );
            println!(
                "Best: '{}' macro_n={}",
                metrics.best_combo, metrics.best_macro_n
            );
            println!(
                "KEY: viable={} l1_success={} best_combo='{}' best_macro_n={}",
                metrics.n_combos_viable,
                metrics.l1_success,
                metrics.best_combo,
                metrics.best_macro_n
            );
        }
        "EXP-049" => {
            let metrics = run_exp_049(seed, scale);
            println!("\n=== EXP-049 Results (seed={}, scale={}) ===", seed, scale);
            println!(
                "Root: sigma={:.6} gap={:.6}",
                metrics.root_sigma, metrics.root_gap
            );
            println!(
                "L1: merge_n={} sigma={:.6} gap={:.6} success={}",
                metrics.l1_merge_n,
                metrics.l1_merge_sigma,
                metrics.l1_merge_gap,
                metrics.l1_success
            );
            println!(
                "L2: comps={} viable={} names=[{}]",
                metrics.l2_n_compositions, metrics.l2_viable, metrics.l2_viable_names
            );
            println!(
                "L2 merge: n={} sigma={:.6} gap={:.6} DPI_vs_L1={} DPI_vs_root={}",
                metrics.l2_merge_n,
                metrics.l2_merge_sigma,
                metrics.l2_merge_gap,
                metrics.l2_dpi_vs_l1,
                metrics.l2_dpi_vs_root
            );
            println!(
                "KEY: total_depth={} l2_success={} l2_viable={} l2_dpi_vs_root={}",
                metrics.total_depth, metrics.l2_success, metrics.l2_viable, metrics.l2_dpi_vs_root
            );
        }
        "EXP-050" => {
            let metrics = run_exp_050(seed, scale);
            println!("\n=== EXP-050 Results (seed={}, scale={}) ===", seed, scale);
            println!(
                "Root: sigma={:.6} gap={:.6}",
                metrics.root_sigma, metrics.root_gap
            );
            for (i, level) in metrics.levels.iter().enumerate() {
                println!(
                    "L{}: merge_n={} sigma={:.6} gap={:.6} viable={} DPI_vs_prev={} DPI_vs_root={}",
                    i + 1,
                    level.merge_n,
                    level.merge_sigma,
                    level.merge_gap,
                    level.viable,
                    level.dpi_vs_prev,
                    level.dpi_vs_root
                );
            }
            println!(
                "KEY: max_depth={} all_dpi_vs_root={}",
                metrics.max_depth, metrics.all_dpi_vs_root
            );
        }
        "EXP-051" => {
            let metrics = run_exp_051(seed, scale);
            println!("\n=== EXP-051 Results (seed={}, scale={}) ===", seed, scale);
            println!(
                "Root: sigma={:.6} gap={:.6}",
                metrics.root_sigma, metrics.root_gap
            );
            println!(
                "Paths: {} depth_range=[{}-{}] mean={:.1}±{:.1}",
                metrics.n_paths,
                metrics.depth_min,
                metrics.depth_max,
                metrics.depth_mean,
                metrics.depth_std
            );
            println!("Terminal n values: [{}]", metrics.terminal_n_values);
            println!(
                "Terminal reversibility mean: {:.6}",
                metrics.terminal_reversibility_mean
            );
            println!("KEY: depth_min={} depth_max={} depth_mean={:.1} depth_std={:.1} all_dpi={} terminal_ns=[{}]",
                metrics.depth_min, metrics.depth_max, metrics.depth_mean, metrics.depth_std,
                metrics.all_paths_dpi, metrics.terminal_n_values);
        }
        "EXP-052" => {
            let metrics = run_exp_052(seed, scale);
            println!("\n=== EXP-052 Results (seed={}, scale={}) ===", seed, scale);
            println!(
                "Root: sigma={:.6} gap={:.6} reversibility={:.6}",
                metrics.root_sigma, metrics.root_gap, metrics.root_reversibility
            );
            for (i, level) in metrics.levels.iter().enumerate() {
                println!("L{}: n={} sigma={:.6} gap={:.6} rev={:.6} blocks={} log_ratio={:.2} viable={} DPI={}",
                    i+1, level.merge_n, level.merge_sigma, level.merge_gap,
                    level.reversibility, level.blocks, level.log_sigma_ratio,
                    level.viable, level.dpi_vs_root);
            }
            println!(
                "KEY: max_depth={} all_dpi={} l1_n={} mean_log_sigma_ratio={:.2}",
                metrics.max_depth,
                metrics.all_dpi_vs_root,
                metrics.l1_merge_n,
                metrics.mean_log_sigma_ratio
            );
        }
        "EXP-053" => {
            let metrics = run_exp_053(seed, scale);
            println!("\n=== EXP-053 Results (seed={}, scale={}) ===", seed, scale);
            println!(
                "Root: sigma={:.6} gap={:.6}",
                metrics.root_sigma, metrics.root_gap
            );
            println!(
                "Terminal n=2 count: {}/{}",
                metrics.n_terminal_2, metrics.n_paths
            );
            println!(
                "K[0][1] (a): mean={:.6} std={:.6}",
                metrics.mean_k01, metrics.std_k01
            );
            println!(
                "K[1][0] (b): mean={:.6} std={:.6}",
                metrics.mean_k10, metrics.std_k10
            );
            println!(
                "a+b (=1-lambda2): mean={:.6} std={:.6}",
                metrics.mean_sum_ab, metrics.std_sum_ab
            );
            println!("Terminal gap: mean={:.6}", metrics.mean_gap);
            for t in &metrics.terminals {
                println!(
                    "  path: depth={} n={} k01={:.6} k10={:.6} gap={:.6} sigma={:.6}",
                    t.depth, t.terminal_n, t.k01, t.k10, t.gap, t.sigma
                );
            }
            println!("KEY: n_t2={} mean_k01={:.4} mean_k10={:.4} std_k01={:.4} std_k10={:.4} mean_sum={:.4} std_sum={:.4}",
                metrics.n_terminal_2, metrics.mean_k01, metrics.mean_k10,
                metrics.std_k01, metrics.std_k10, metrics.mean_sum_ab, metrics.std_sum_ab);
        }
        "EXP-054" => {
            let metrics = run_exp_054(seed, scale);
            println!("\n=== EXP-054 Results (seed={}, scale={}) ===", seed, scale);
            println!(
                "Root: sigma={:.6} gap={:.6}",
                metrics.root_sigma, metrics.root_gap
            );
            println!(
                "Parity:      sigma={:.6} gap={:.6} DPI={}",
                metrics.parity_sigma, metrics.parity_gap, metrics.parity_dpi
            );
            println!(
                "Random bin:  sigma={:.6} gap={:.6} DPI={}",
                metrics.random_bin_sigma, metrics.random_bin_gap, metrics.random_bin_dpi
            );
            println!(
                "P2→P4 bin:   sigma={:.6} gap={:.6} DPI={} found={}",
                metrics.p2p4_sigma, metrics.p2p4_gap, metrics.p2p4_dpi, metrics.p2p4_found
            );
            println!(
                "Cascade:     sigma={:.6} gap={:.6} DPI={} depth={}",
                metrics.cascade_sigma,
                metrics.cascade_gap,
                metrics.cascade_dpi,
                metrics.cascade_depth
            );
            println!("KEY: parity_dpi={} random_dpi={} p2p4_dpi={} cascade_dpi={} single_step_possible={} cascade_needed={}",
                metrics.parity_dpi, metrics.random_bin_dpi, metrics.p2p4_dpi,
                metrics.cascade_dpi, metrics.single_step_dpi_possible, metrics.cascade_needed);
        }
        "EXP-055" => {
            let metrics = run_exp_055(seed, scale);
            println!("\n=== EXP-055 Results (seed={}, scale={}) ===", seed, scale);
            println!(
                "Root: sigma={:.6} gap={:.6}",
                metrics.root_sigma, metrics.root_gap
            );
            println!(
                "Lens A: macro_n={} RM={:.4} sigma={:.6} gap={:.4}",
                metrics.lens_a_macro_n, metrics.rm_a, metrics.sigma_a, metrics.gap_a
            );
            println!(
                "Lens B: macro_n={} RM={:.4} sigma={:.6} gap={:.4}",
                metrics.lens_b_macro_n, metrics.rm_b, metrics.sigma_b, metrics.gap_b
            );
            println!(
                "Joint:  macro_n={} RM={:.4} sigma={:.6} gap={:.4}",
                metrics.joint_macro_n, metrics.rm_joint, metrics.sigma_joint, metrics.gap_joint
            );
            println!(
                "KEY: beats_a={} beats_b={} beats_both={} improvement={:.1}%",
                metrics.joint_beats_a_rm,
                metrics.joint_beats_b_rm,
                metrics.joint_beats_both_rm,
                metrics.rm_improvement_vs_best * 100.0
            );
        }
        "EXP-056" => {
            let metrics = run_exp_056(seed, scale);
            println!("\n=== EXP-056 Results (seed={}, scale={}) ===", seed, scale);
            println!(
                "Standard: sigma={:.4} gap={:.4} depth={} L1_n={} terminal_n={} DPI={}",
                metrics.std_sigma,
                metrics.std_gap,
                metrics.std_depth,
                metrics.std_l1_n,
                metrics.std_terminal_n,
                metrics.std_all_dpi
            );
            println!(
                "Slow:     sigma={:.4} gap={:.4} blocks={} depth={} L1_n={} terminal_n={} DPI={}",
                metrics.slow_sigma,
                metrics.slow_gap,
                metrics.slow_blocks,
                metrics.slow_depth,
                metrics.slow_l1_n,
                metrics.slow_terminal_n,
                metrics.slow_all_dpi
            );
            println!(
                "KEY: gap_ratio={:.3} depth_diff={} same_terminal={}",
                metrics.gap_ratio, metrics.depth_diff, metrics.same_terminal
            );
        }
        "EXP-057" => {
            let metrics = run_exp_057(seed, scale);
            println!("\n=== EXP-057 Results (seed={}, scale={}) ===", seed, scale);
            println!(
                "Root: sigma={:.6} gap={:.6}",
                metrics.root_sigma, metrics.root_gap
            );
            println!(
                "Max-gap: depth={} L1_n={} terminal_n={} DPI={} sigma=[{}] n=[{}]",
                metrics.maxgap_depth,
                metrics.maxgap_l1_n,
                metrics.maxgap_terminal_n,
                metrics.maxgap_all_dpi,
                metrics
                    .maxgap_sigma_levels
                    .iter()
                    .map(|s| format!("{:.4}", s))
                    .collect::<Vec<_>>()
                    .join(","),
                metrics
                    .maxgap_n_levels
                    .iter()
                    .map(|n| n.to_string())
                    .collect::<Vec<_>>()
                    .join(",")
            );
            println!(
                "Min-RM:  depth={} L1_n={} terminal_n={} DPI={} sigma=[{}] n=[{}]",
                metrics.minrm_depth,
                metrics.minrm_l1_n,
                metrics.minrm_terminal_n,
                metrics.minrm_all_dpi,
                metrics
                    .minrm_sigma_levels
                    .iter()
                    .map(|s| format!("{:.4}", s))
                    .collect::<Vec<_>>()
                    .join(","),
                metrics
                    .minrm_n_levels
                    .iter()
                    .map(|n| n.to_string())
                    .collect::<Vec<_>>()
                    .join(",")
            );
            println!(
                "KEY: depth_diff={} same_depth={} same_terminal={}",
                metrics.depth_diff, metrics.same_depth, metrics.same_terminal
            );
        }
        "EXP-058" => {
            let metrics = run_exp_058(seed, scale);
            println!("\n=== EXP-058 Results (seed={}, scale={}) ===", seed, scale);
            println!(
                "Root: sigma={:.6} gap={:.6}",
                metrics.root_sigma, metrics.root_gap
            );
            println!(
                "P-comp:  depth={} L1_n={} terminal_n={} DPI={} sigma=[{}]",
                metrics.pcomp_depth,
                metrics.pcomp_l1_n,
                metrics.pcomp_terminal_n,
                metrics.pcomp_all_dpi,
                metrics
                    .pcomp_sigma_levels
                    .iter()
                    .map(|s| format!("{:.4}", s))
                    .collect::<Vec<_>>()
                    .join(",")
            );
            println!(
                "Random:  depth={} L1_n={} terminal_n={} DPI={} sigma=[{}]",
                metrics.random_depth,
                metrics.random_l1_n,
                metrics.random_terminal_n,
                metrics.random_all_dpi,
                metrics
                    .random_sigma_levels
                    .iter()
                    .map(|s| format!("{:.4}", s))
                    .collect::<Vec<_>>()
                    .join(",")
            );
            println!(
                "Random tries: {}/{} success",
                metrics.random_successes, metrics.random_attempts
            );
            println!(
                "KEY: depth_diff={} random_shorter={} random_fails_more={}",
                metrics.depth_diff, metrics.random_shorter, metrics.random_fails_more
            );
        }
        "EXP-059" => {
            let metrics = run_exp_059(seed, scale);
            println!(
                "\n=== EXP-059 Multi-Audit Probe (seed={}, scale={}) ===",
                seed, scale
            );
            println!(
                "Root: sigma={:.6} gap={:.6}",
                metrics.root_sigma, metrics.root_gap
            );
            println!(
                "Cascade: depth={} all_dpi={}",
                metrics.depth, metrics.all_dpi
            );
            for audit in &metrics.level_audits {
                println!(
                    "\n  Level {} (n={}): sigma={:.6} gap={:.4} blocks={}",
                    audit.level, audit.n, audit.sigma, audit.gap, audit.blocks
                );
                println!(
                    "    Chirality: acc_max={:.4} mean_acc2={:.4}",
                    audit.acc_max, audit.mean_acc_2cycle
                );
                println!(
                    "    Metric:    diameter={:.4} mean_dist={:.4} dim={:.2}",
                    audit.diameter, audit.mean_dist, audit.dim_estimate
                );
                println!("    Parts:     cross_flux={:.4}", audit.cross_group_flux);
                println!(
                    "    SlowMode:  second_eval={:.4} locality={:.4} eigvec_range={:.4}",
                    audit.second_eval, audit.locality_score, audit.eigvec_range
                );
                println!(
                    "KEY_CHIRALITY seed={} scale={} level={} n={} acc_max={:.6} mean_acc2={:.6}",
                    seed, scale, audit.level, audit.n, audit.acc_max, audit.mean_acc_2cycle
                );
                println!("KEY_METRIC seed={} scale={} level={} n={} diameter={:.6} mean_dist={:.6} dim={:.4}",
                    seed, scale, audit.level, audit.n, audit.diameter, audit.mean_dist, audit.dim_estimate);
                println!(
                    "KEY_PARTS seed={} scale={} level={} n={} cross_flux={:.6} blocks={}",
                    seed, scale, audit.level, audit.n, audit.cross_group_flux, audit.blocks
                );
                println!("KEY_SLOWMODE seed={} scale={} level={} n={} second_eval={:.6} locality={:.6} range={:.6}",
                    seed, scale, audit.level, audit.n, audit.second_eval, audit.locality_score, audit.eigvec_range);
            }
            println!(
                "\nKEY seed={} scale={} n={} depth={} all_dpi={}",
                seed, scale, metrics.n, metrics.depth, metrics.all_dpi
            );
            println!(
                "KEY_MONO seed={} scale={} acc_decay={} diam_decay={} locality_up={} flux_decay={}",
                seed,
                scale,
                metrics.acc_max_monotone_decay,
                metrics.diameter_monotone_decay,
                metrics.locality_monotone_improve,
                metrics.cross_flux_monotone_decay
            );
        }
        "EXP-060" => {
            let metrics = run_exp_060(seed, scale);
            println!(
                "\n=== EXP-060 Cross-Path Ordering (seed={}, scale={}) ===",
                seed, scale
            );
            println!(
                "Root: sigma={:.6} gap={:.6}",
                metrics.root_sigma, metrics.root_gap
            );
            println!(
                "Paths: {}/{} successful, {}/{} reached terminal",
                metrics.n_paths, 10, metrics.n_terminal_reached, metrics.n_paths
            );
            println!("L1 macro_n values: {:?}", metrics.l1_n_values);
            println!(
                "L1 Spearman: mean={:.4} min={:.4}",
                metrics.mean_l1_spearman, metrics.min_l1_spearman
            );
            println!(
                "Terminal agreement: mean={:.4} min={:.4}",
                metrics.mean_terminal_agree, metrics.min_terminal_agree
            );
            for (d, (&mean_rho, &n_pairs)) in metrics
                .mean_spearman_by_depth
                .iter()
                .zip(metrics.n_pairs_by_depth.iter())
                .enumerate()
            {
                println!(
                    "  Depth {}: mean_spearman={:.4} n_pairs={}",
                    d + 1,
                    mean_rho,
                    n_pairs
                );
                println!(
                    "KEY_DEPTH seed={} scale={} depth={} mean_spearman={:.6} n_pairs={}",
                    seed,
                    scale,
                    d + 1,
                    mean_rho,
                    n_pairs
                );
            }
            println!(
                "KEY seed={} scale={} n_paths={} n_terminal={}",
                seed, scale, metrics.n_paths, metrics.n_terminal_reached
            );
            println!(
                "KEY_L1 seed={} scale={} mean_spearman={:.6} min_spearman={:.6} l1_n_range={}-{}",
                seed,
                scale,
                metrics.mean_l1_spearman,
                metrics.min_l1_spearman,
                metrics.l1_n_values.iter().min().unwrap_or(&0),
                metrics.l1_n_values.iter().max().unwrap_or(&0)
            );
            println!(
                "KEY_TERMINAL seed={} scale={} mean_agree={:.6} min_agree={:.6}",
                seed, scale, metrics.mean_terminal_agree, metrics.min_terminal_agree
            );
        }
        "EXP-061" => {
            let metrics = run_exp_061(seed, scale);
            println!(
                "\n=== EXP-061 Fiedler Verification (seed={}, scale={}) ===",
                seed, scale
            );
            println!(
                "Root: n={} sigma={:.6} gap={:.6}",
                metrics.n, metrics.root_sigma, metrics.root_gap
            );
            println!(
                "Fiedler partition: n_positive={}/{}",
                metrics.fiedler_n_positive, metrics.n
            );
            println!(
                "Cascade paths: {}/{} reached terminal",
                metrics.n_terminal, metrics.n_paths
            );
            println!(
                "Fiedler vs cascade: mean_agree={:.4} min_agree={:.4} max_agree={:.4}",
                metrics.mean_fiedler_agree, metrics.min_fiedler_agree, metrics.max_fiedler_agree
            );
            println!(
                "Cross-path (sanity): mean_agree={:.4} min_agree={:.4}",
                metrics.mean_cross_agree, metrics.min_cross_agree
            );
            println!(
                "KEY seed={} scale={} n={} gap={:.6} fiedler_n_pos={} n_terminal={}",
                seed,
                scale,
                metrics.n,
                metrics.root_gap,
                metrics.fiedler_n_positive,
                metrics.n_terminal
            );
            println!(
                "KEY_FIEDLER seed={} scale={} mean_agree={:.6} min_agree={:.6} max_agree={:.6}",
                seed,
                scale,
                metrics.mean_fiedler_agree,
                metrics.min_fiedler_agree,
                metrics.max_fiedler_agree
            );
            println!(
                "KEY_CROSS seed={} scale={} mean_agree={:.6} min_agree={:.6}",
                seed, scale, metrics.mean_cross_agree, metrics.min_cross_agree
            );
        }
        "EXP-062" => {
            let metrics = run_exp_062(seed, scale);
            println!(
                "\n=== EXP-062 Minority Characterization (seed={}, scale={}) ===",
                seed, scale
            );
            println!(
                "Root: n={} sigma={:.6} gap={:.6}",
                metrics.n, metrics.root_sigma, metrics.root_gap
            );
            println!(
                "Partition: minority={} majority={} ({:.1}%/{:.1}%)",
                metrics.minority_size,
                metrics.majority_size,
                100.0 * metrics.minority_size as f64 / metrics.n as f64,
                100.0 * metrics.majority_size as f64 / metrics.n as f64
            );
            println!("--- Property comparison (minority / majority) ---");
            println!(
                "  π (stationary):  {:.6} / {:.6}  ratio={:.4}  total_π_min={:.4}",
                metrics.mean_pi_minority,
                metrics.mean_pi_majority,
                metrics.pi_ratio,
                metrics.total_pi_minority
            );
            println!(
                "  Self-loop:       {:.6} / {:.6}",
                metrics.mean_selfloop_minority, metrics.mean_selfloop_majority
            );
            println!(
                "  Max outgoing:    {:.6} / {:.6}",
                metrics.mean_maxout_minority, metrics.mean_maxout_majority
            );
            println!(
                "  Row entropy:     {:.4} / {:.4}",
                metrics.mean_entropy_minority, metrics.mean_entropy_majority
            );
            println!(
                "  Degree (gated):  {:.1} / {:.1}",
                metrics.mean_degree_minority, metrics.mean_degree_majority
            );
            println!(
                "π-threshold test: best_agree={:.4} at k={}",
                metrics.best_pi_agree, metrics.best_pi_k
            );
            println!(
                "KEY seed={} scale={} n={} min_size={} maj_size={} n_terminal={}",
                seed,
                scale,
                metrics.n,
                metrics.minority_size,
                metrics.majority_size,
                metrics.n_terminal
            );
            println!("KEY_PI seed={} scale={} pi_ratio={:.6} total_pi_min={:.6} mean_pi_min={:.8} mean_pi_maj={:.8}",
                seed, scale, metrics.pi_ratio, metrics.total_pi_minority, metrics.mean_pi_minority, metrics.mean_pi_majority);
            println!("KEY_PROPS seed={} scale={} selfloop_min={:.6} selfloop_maj={:.6} maxout_min={:.6} maxout_maj={:.6} entropy_min={:.4} entropy_maj={:.4} degree_min={:.1} degree_maj={:.1}",
                seed, scale, metrics.mean_selfloop_minority, metrics.mean_selfloop_majority,
                metrics.mean_maxout_minority, metrics.mean_maxout_majority,
                metrics.mean_entropy_minority, metrics.mean_entropy_majority,
                metrics.mean_degree_minority, metrics.mean_degree_majority);
            println!(
                "KEY_PITHRESH seed={} scale={} best_agree={:.6} best_k={}",
                seed, scale, metrics.best_pi_agree, metrics.best_pi_k
            );
        }
        "EXP-063" => {
            let metrics = run_exp_063(seed, scale);
            println!(
                "\n=== EXP-063 Pairwise Flow Analysis (seed={}, scale={}) ===",
                seed, scale
            );
            println!(
                "Root: n={} sigma={:.6} gap={:.6}",
                metrics.n, metrics.root_sigma, metrics.root_gap
            );
            println!(
                "Partition: minority={} majority={} (n_terminal={})",
                metrics.minority_size, metrics.majority_size, metrics.n_terminal
            );
            println!("--- Flow matrix (π-weighted) ---");
            println!("  f_mm={:.6}  f_mM={:.6}", metrics.f_mm, metrics.f_m_M);
            println!("  f_Mm={:.6}  f_MM={:.6}", metrics.f_M_m, metrics.f_M_M);
            println!("--- Derived metrics ---");
            println!("  Flow asymmetry (mM/Mm): {:.4}", metrics.flow_asym);
            println!("  Cohesion (f_mm/π_min):  {:.4}", metrics.cohesion);
            println!("  Escape rate (f_mM/π_min): {:.4}", metrics.escape_rate);
            println!("  Absorption steps (95%): {}", metrics.absorb_steps);
            println!(
                "--- Null comparison (z-scores vs {} random partitions) ---",
                metrics.n_null
            );
            println!(
                "  z_cohesion={:.3}  z_escape={:.3}  z_asym={:.3}",
                metrics.z_cohesion, metrics.z_escape, metrics.z_asym
            );
            println!(
                "KEY seed={} scale={} n={} min_size={} maj_size={} n_terminal={}",
                seed,
                scale,
                metrics.n,
                metrics.minority_size,
                metrics.majority_size,
                metrics.n_terminal
            );
            println!(
                "KEY_FLOW seed={} scale={} f_mm={:.6} f_mM={:.6} f_Mm={:.6} f_MM={:.6}",
                seed, scale, metrics.f_mm, metrics.f_m_M, metrics.f_M_m, metrics.f_M_M
            );
            println!(
                "KEY_ASYM seed={} scale={} flow_asym={:.6} cohesion={:.6} escape={:.6}",
                seed, scale, metrics.flow_asym, metrics.cohesion, metrics.escape_rate
            );
            println!(
                "KEY_ABS seed={} scale={} absorb_steps={}",
                seed, scale, metrics.absorb_steps
            );
            println!(
                "KEY_NULL seed={} scale={} z_cohesion={:.4} z_escape={:.4} z_asym={:.4}",
                seed, scale, metrics.z_cohesion, metrics.z_escape, metrics.z_asym
            );
        }
        "EXP-064" => {
            let metrics = run_exp_064(seed, scale);
            println!(
                "\n=== EXP-064 Integrated Information of Cascade Partition (seed={}, scale={}) ===",
                seed, scale
            );
            println!(
                "Root: n={} sigma={:.6} gap={:.6}",
                metrics.n, metrics.root_sigma, metrics.root_gap
            );
            println!(
                "Partition: minority={} (n_terminal={})",
                metrics.minority_size, metrics.n_terminal
            );
            println!("I_whole = {:.6}", metrics.i_whole);
            println!("Φ_cascade = {:.6}", metrics.phi_cascade);
            println!(
                "Φ_random: mean={:.6} std={:.6}",
                metrics.phi_rand_mean, metrics.phi_rand_std
            );
            println!(
                "z-score = {:.3}  rank = {}/{}",
                metrics.z_score,
                metrics.rank,
                metrics.n_null + 1
            );
            println!("Φ_fiedler = {:.6}", metrics.phi_fiedler);
            println!(
                "KEY seed={} scale={} n={} min_size={}",
                seed, scale, metrics.n, metrics.minority_size
            );
            println!("KEY_PHI seed={} scale={} I_whole={:.6} phi_cascade={:.6} phi_rand_mean={:.6} phi_rand_std={:.6} z_score={:.4} phi_fiedler={:.6} rank={}/{}",
                seed, scale, metrics.i_whole, metrics.phi_cascade, metrics.phi_rand_mean, metrics.phi_rand_std,
                metrics.z_score, metrics.phi_fiedler, metrics.rank, metrics.n_null + 1);
        }
        "EXP-065" => {
            let metrics = run_exp_065(seed, scale);
            println!(
                "\n=== EXP-065 Phi Across Cascade Stack (seed={}, scale={}) ===",
                seed, scale
            );
            println!(
                "Root: n={} sigma={:.6} gap={:.6}",
                metrics.n, metrics.root_sigma, metrics.root_gap
            );
            println!("Cascade depth: {}", metrics.depth);
            for level in &metrics.levels {
                if let Some(phi_mip) = level.phi_mip {
                    println!(
                        "  Level {} : macro_n={:3}  I_whole={:.6}  Φ_mip={:.6}  mip_split={}/{}",
                        level.level,
                        level.macro_n,
                        level.i_whole,
                        phi_mip,
                        level.mip_min_size,
                        level.macro_n - level.mip_min_size
                    );
                } else {
                    println!(
                        "  Level {} : macro_n={:3}  I_whole={:.6}  Φ_mip=skip (n>64)",
                        level.level, level.macro_n, level.i_whole
                    );
                }
            }
            println!(
                "KEY seed={} scale={} n={} depth={}",
                seed, scale, metrics.n, metrics.depth
            );
            for level in &metrics.levels {
                println!("KEY_STACK seed={} scale={} level={} macro_n={} I_whole={:.6} phi_mip={:.6} mip_split={}/{}",
                    seed, scale, level.level, level.macro_n, level.i_whole,
                    level.phi_mip.unwrap_or(-1.0),
                    level.mip_min_size, level.macro_n - level.mip_min_size);
            }
        }
        "EXP-066" => {
            let metrics = run_exp_066(seed, scale);
            println!(
                "\n=== EXP-066 Minority Jaccard Reproducibility (seed={}, scale={}) ===",
                seed, scale
            );
            println!(
                "n={} paths={} valid={} pairs={}",
                metrics.n, metrics.n_paths, metrics.n_valid, metrics.n_pairs
            );
            println!("Mean minority size: {:.1}", metrics.mean_minority_size);
            println!(
                "Mean Jaccard:       {:.6}  (baseline: {:.6})",
                metrics.mean_jaccard, metrics.baseline_jaccard
            );
            println!(
                "Mean intersection:  {:.3}  (baseline: {:.3})",
                metrics.mean_intersection, metrics.baseline_intersection
            );
            let signal = if metrics.baseline_jaccard > 1e-10 {
                metrics.mean_jaccard / metrics.baseline_jaccard
            } else {
                0.0
            };
            println!("Signal/baseline ratio: {:.2}", signal);
            println!(
                "KEY seed={} scale={} n={} n_valid={} n_pairs={}",
                seed, scale, metrics.n, metrics.n_valid, metrics.n_pairs
            );
            println!("KEY_JACCARD seed={} scale={} mean_jaccard={:.6} baseline_jaccard={:.6} mean_intersection={:.4} baseline_intersection={:.4} mean_minority_size={:.2} signal_ratio={:.4}",
                seed, scale, metrics.mean_jaccard, metrics.baseline_jaccard,
                metrics.mean_intersection, metrics.baseline_intersection,
                metrics.mean_minority_size, signal);
        }
        "EXP-067" => {
            let metrics = run_exp_067(seed, scale);
            println!(
                "\n=== EXP-067 Orphan Mechanism Test (seed={}, scale={}) ===",
                seed, scale
            );
            println!(
                "n={} paths={} valid={}",
                metrics.n, metrics.n_paths, metrics.n_valid
            );
            println!("Theory E[isolated]: {:.2}", metrics.expected_isolated);
            println!("Observed mean orphans: {:.1}", metrics.mean_orphans);
            println!("Mean minority size: {:.1}", metrics.mean_minority);
            println!(
                "Mean overlap (minority ∩ orphans / minority): {:.3}",
                metrics.mean_overlap_frac
            );
            for (i, pr) in metrics.path_results.iter().enumerate() {
                println!(
                    "  Path {:2}: orphans={} minority={} overlap={} frac={:.3}",
                    i, pr.n_orphans, pr.minority_size, pr.overlap, pr.overlap_frac
                );
            }
            println!(
                "KEY seed={} scale={} n={} n_valid={}",
                seed, scale, metrics.n, metrics.n_valid
            );
            println!("KEY_ORPHAN seed={} scale={} expected_isolated={:.4} mean_orphans={:.2} mean_minority={:.2} mean_overlap_frac={:.4}",
                seed, scale, metrics.expected_isolated, metrics.mean_orphans, metrics.mean_minority, metrics.mean_overlap_frac);
        }
        "EXP-068" => {
            let metrics = run_exp_068(seed, scale);
            println!(
                "\n=== EXP-068 Time-Dilation Test (seed={}, scale={}) ===",
                seed, scale
            );
            println!("n={}", metrics.n);
            println!("Root MI at lag=1:   {:.6}", metrics.i_lag1);
            println!("Root MI at lag=20:  {:.6}", metrics.i_lag20);
            println!("Root MI at lag=400: {:.6}", metrics.i_lag400);
            println!(
                "Cascade L1 MI (n={}): {:.6}",
                metrics.level1_n, metrics.i_level1
            );
            println!(
                "Cascade L2 MI (n={}): {:.6}",
                metrics.level2_n, metrics.i_level2
            );
            println!("Ratio lag20/L1: {:.4}", metrics.ratio_lag20_vs_level1);
            println!("Ratio lag400/L2: {:.4}", metrics.ratio_lag400_vs_level2);
            println!("KEY seed={} scale={} n={}", seed, scale, metrics.n);
            println!(
                "KEY_TIMEDIL seed={} scale={} I_lag1={:.6} I_lag20={:.6} I_lag400={:.6}",
                seed, scale, metrics.i_lag1, metrics.i_lag20, metrics.i_lag400
            );
            println!("KEY_CASCADE seed={} scale={} I_level1={:.6} I_level2={:.6} level1_n={} level2_n={}",
                seed, scale, metrics.i_level1, metrics.i_level2, metrics.level1_n, metrics.level2_n);
            println!(
                "KEY_COMPARE seed={} scale={} ratio_lag20_L1={:.4} ratio_lag400_L2={:.4}",
                seed, scale, metrics.ratio_lag20_vs_level1, metrics.ratio_lag400_vs_level2
            );
        }
        "EXP-069" => {
            run_exp_069(seed, scale);
        }
        "EXP-070" => {
            run_exp_070(seed, scale);
        }
        "EXP-071" => {
            run_exp_071(seed, scale);
        }
        "EXP-072" => {
            run_exp_072(seed, scale);
        }
        // ===== Phase 2 Diagnostic Experiments =====
        "EXP-073" => {
            run_exp_073(seed, scale);
        }
        "EXP-074" => {
            run_exp_074(seed, scale);
        }
        "EXP-075" => {
            run_exp_075(seed, scale);
        }
        // ===== Phase 2 Dynamics Validation =====
        "EXP-076" => {
            run_exp_076(seed, scale);
        }
        "EXP-077" => {
            run_exp_077(seed, scale);
        }
        "EXP-078" => {
            run_exp_078(seed, scale);
        }
        "EXP-079" => {
            run_exp_079(seed, scale);
        }
        "EXP-080" => {
            run_exp_080(seed, scale);
        }
        "EXP-081" => {
            run_exp_081(seed, scale);
        }
        "EXP-082" => {
            run_exp_082(seed, scale);
        }
        "EXP-083" => {
            run_exp_083(seed, scale);
        }
        "EXP-084" => {
            run_exp_084(seed, scale);
        }
        "EXP-085" => {
            run_exp_085(seed, scale);
        }
        "EXP-086" => {
            run_exp_086(seed, scale);
        }
        "EXP-087" => {
            run_exp_087(seed, scale);
        }
        "EXP-088" => {
            run_exp_088(seed, scale);
        }
        "EXP-089" => {
            run_exp_089(seed, scale);
        }
        "EXP-090" => {
            run_exp_090(seed, scale);
        }
        "EXP-091" => {
            run_exp_091(seed, scale);
        }
        "EXP-092" => {
            run_exp_092(seed, scale);
        }
        "EXP-093" => {
            run_exp_093(seed, scale);
        }
        "EXP-094" => {
            run_exp_094(seed, scale);
        }
        "EXP-095" => {
            run_exp_095(seed, scale);
        }
        "EXP-096" => {
            run_exp_096(seed, scale);
        }
        "EXP-097" => {
            run_exp_097(seed, scale);
        }
        "EXP-098" => {
            run_exp_098(seed, scale);
        }
        "EXP-099" => {
            run_exp_099(seed, scale);
        }
        "EXP-100" => {
            run_exp_100(seed, scale, config_filter);
        }
        "EXP-101" => {
            run_exp_101(seed, scale, config_filter);
        }
        "EXP-102" => {
            run_exp_102(seed, scale, config_filter);
        }
        "EXP-103" => {
            run_exp_103(seed, scale, config_filter);
        }
        "EXP-104" => {
            run_exp_104(seed, scale, config_filter);
        }
        "EXP-105" => {
            run_exp_105(seed, scale, config_filter);
        }
        "EXP-106" => {
            run_exp_106(seed, scale, config_filter);
        }
        "EXP-107" => {
            run_exp_107(seed, scale, config_filter);
        }
        "EXP-108" => {
            run_exp_108(seed, scale, config_filter);
        }
        "EXP-109" => {
            run_exp_109(seed, scale, config_filter);
        }
        "EXP-110" => {
            run_exp_110(seed, scale, config_filter);
        }
        "EXP-112" => {
            run_exp_112(seed, scale, config_filter);
        }
        "EXP-F1" => {
            run_exp_f1(seed, scale);
        }
        "EXP-SHOW" => {
            // Diagnostic: show minority state IDs across cascade paths
            let n = scale.max(8);
            let mut dag = EmergenceDag::new();
            let root_id = dag.create_root(n, seed);
            let root = dag.nodes[&root_id].clone();
            println!(
                "\n=== Minority State IDs (seed={}, scale={}, n={}) ===",
                seed, scale, n
            );
            for p in 0..10u64 {
                let path_seed = seed * 1000 + p;
                let mut path_dag = EmergenceDag::new();
                let path_root_id = path_dag.create_root_from_kernel(root.kernel.clone());
                if let Some(ordering) =
                    run_cascade_with_lenses(&mut path_dag, &path_root_id, n, root.sigma, path_seed)
                {
                    if let Some(tp) = ordering.terminal_partition {
                        let count_0: usize = tp.iter().filter(|&&x| x == 0).count();
                        let count_1: usize = tp.iter().filter(|&&x| x == 1).count();
                        let minority_label = if count_0 <= count_1 { 0 } else { 1 };
                        let minority_ids: Vec<usize> = tp
                            .iter()
                            .enumerate()
                            .filter(|(_, &x)| x == minority_label)
                            .map(|(i, _)| i)
                            .collect();
                        println!("  Path {:2}: minority={:?}", p, minority_ids);
                    } else {
                        println!("  Path {:2}: no terminal", p);
                    }
                } else {
                    println!("  Path {:2}: cascade failed", p);
                }
            }
        }
        _ => {
            eprintln!("Unknown experiment: {}", exp);
            std::process::exit(1);
        }
    }
}

fn run_sweep(exp: &str, scales: &[usize]) {
    let seeds: Vec<u64> = (0..10).collect();
    let total = seeds.len() * scales.len();
    println!(
        "Sweep: {} seeds × {} scales = {} runs",
        seeds.len(),
        scales.len(),
        total
    );

    for (i, &seed) in seeds.iter().enumerate() {
        for (j, &scale) in scales.iter().enumerate() {
            let run_num = i * scales.len() + j + 1;
            println!(
                "\n--- Run {}/{} (seed={}, scale={}) ---",
                run_num, total, seed, scale
            );
            run_single(exp, seed, scale, None);
        }
    }
}

fn main() {
    let args = Args::parse();

    let scales: Vec<usize> = if let Some(s) = &args.scales {
        s.split(',').filter_map(|x| x.trim().parse().ok()).collect()
    } else {
        vec![32, 64, 128, 256]
    };

    if args.sweep {
        run_sweep(&args.exp, &scales);
    } else {
        run_single(&args.exp, args.seed, args.scale, args.config.as_deref());
    }
}
