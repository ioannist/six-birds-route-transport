//! # PICA score types: outputs from modulation cells, used by the dynamics loop.
//!
//! Each action cell produces a score that modulates its actor's behavior.
//! There are four score types, one per active actor row:
//!
//! - `P1Scores`: row weights + optional direction (for P1 rewrite targeting)
//! - `P2Scores`: edge weights + cost multipliers (for P2 gate targeting + budget)
//! - `P3Scores`: mixture weight multipliers (for P3 mixture adjustment)
//! - `P6Scores`: budget rate/cap multipliers (for P6 budget modulation)
//!
//! P4 and P5 rows produce partitions (Vec<usize>), not score structs — they use
//! selection, not multiplicative combining. See `lens_cells.rs` and `p5_cells.rs`.
//!
//! ## Combining multiple cells
//!
//! When multiple cells are enabled for the same actor (e.g., A1 + A3 + A4 for P1),
//! their scores are **combined by element-wise product**:
//!
//! - **Row/edge weights**: `combined[i] = Π_cells weight_cell[i]`, then normalized.
//! - **Cost multipliers**: `combined[i,j] = Π_cells cost_cell[i,j]`. Costs stack.
//! - **Directions**: averaged (not multiplied), then row-normalized.
//! - **P3 weight multipliers**: element-wise product, then renormalized.
//! - **P6 budget multipliers**: element-wise product (rate_mult and cap_mult stack).
//!
//! ## Why multiplicative (not additive)?
//!
//! Multiplicative combining means any cell can **veto** a target by setting its weight
//! to near-zero (e.g., A6 suppresses all rows when budget is low). Additive combining
//! would let high weights from one cell override the veto of another. The multiplicative
//! rule ensures all constraints are respected simultaneously.

/// P1 modulation output: per-row targeting for kernel perturbation.
///
/// Higher row_weights = more likely to be perturbed.
/// Direction = optional target distribution for the perturbed row.
pub struct P1Scores {
    /// Weight for each row (higher = more likely to perturb). Length = n.
    pub row_weights: Vec<f64>,
    /// Optional direction: for each row, a target distribution to perturb toward.
    /// If None, use random perturbation (default behavior).
    /// If Some, bias perturbation toward this target (blend current + target).
    pub direction: Option<Vec<Vec<f64>>>,
}

/// P2 modulation output: per-edge targeting + cost modifiers.
///
/// Higher edge_weights = more likely to be selected for flipping.
/// cost_multiplier modifies the P6 budget cost of each flip.
pub struct P2Scores {
    /// Weight for each edge (i,j) stored as flat n*n. Higher = more likely to flip.
    pub edge_weights: Vec<f64>,
    /// Cost multiplier for each edge. 0.0=free, 1.0=normal, >1.0=penalized.
    pub cost_multiplier: Vec<f64>,
}

/// P3 modulation output: mixture weight adjustments.
///
/// Multiplicative modifiers applied to base mixture weights before renormalization.
/// All 1.0 = no effect (identity).
pub struct P3Scores {
    /// Multiplicative adjustment to [traj, p1, p2, p4, p5, p6].
    pub weight_multipliers: [f64; 6],
}

impl P1Scores {
    /// Default: uniform weights, no direction bias.
    pub fn uniform(n: usize) -> Self {
        P1Scores {
            row_weights: vec![1.0; n],
            direction: None,
        }
    }
}

impl P2Scores {
    /// Default: uniform edge weights, normal cost.
    pub fn uniform(n: usize) -> Self {
        P2Scores {
            edge_weights: vec![1.0; n * n],
            cost_multiplier: vec![1.0; n * n],
        }
    }
}

impl P3Scores {
    /// Default: no modulation (all multipliers = 1.0).
    pub fn identity() -> Self {
        P3Scores {
            weight_multipliers: [1.0; 6],
        }
    }
}

/// Combine multiple P1 score sets by element-wise product of row_weights.
/// Direction: weighted average of all non-None directions.
pub fn combine_p1(n: usize, all: &[&P1Scores]) -> P1Scores {
    if all.is_empty() {
        return P1Scores::uniform(n);
    }
    if all.len() == 1 {
        let mut rw = all[0].row_weights.clone();
        // Sanitize non-finite/negative values (consistent with multi-cell path)
        for w in &mut rw {
            if !w.is_finite() || *w < 0.0 {
                *w = 1.0;
            }
        }
        let dir = all[0].direction.as_ref().map(|d| sanitize_direction(d, n));
        return P1Scores {
            row_weights: rw,
            direction: dir,
        };
    }

    let mut combined_weights = vec![1.0; n];
    let mut combined_direction: Option<Vec<Vec<f64>>> = None;
    let mut n_directions = 0;

    for scores in all {
        for i in 0..n {
            combined_weights[i] *= scores.row_weights[i];
        }
        if let Some(ref dir) = scores.direction {
            if combined_direction.is_none() {
                combined_direction = Some(vec![vec![0.0; n]; n]);
            }
            if let Some(ref mut cd) = combined_direction {
                for i in 0..n {
                    for j in 0..n {
                        cd[i][j] += dir[i][j];
                    }
                }
            }
            n_directions += 1;
        }
    }

    // Sanitize non-finite/negative values from multiplication
    for w in &mut combined_weights {
        if !w.is_finite() || *w < 0.0 {
            *w = 1.0;
        }
    }

    // Normalize row_weights
    let sum: f64 = combined_weights.iter().sum();
    if sum > 0.0 {
        for w in &mut combined_weights {
            *w /= sum;
        }
    }

    // Average and sanitize directions
    if let Some(ref mut cd) = combined_direction {
        let scale = if n_directions > 1 {
            1.0 / n_directions as f64
        } else {
            1.0
        };
        for i in 0..n {
            for j in 0..n {
                cd[i][j] *= scale;
                if !cd[i][j].is_finite() || cd[i][j] < 0.0 {
                    cd[i][j] = 0.0;
                }
            }
            // Renormalize each row
            let row_sum: f64 = cd[i].iter().sum();
            if row_sum > 0.0 {
                for j in 0..n {
                    cd[i][j] /= row_sum;
                }
            }
        }
    }

    P1Scores {
        row_weights: combined_weights,
        direction: combined_direction,
    }
}

/// Sanitize a direction matrix: clamp non-finite/negative entries to 0, renormalize rows.
fn sanitize_direction(dir: &[Vec<f64>], n: usize) -> Vec<Vec<f64>> {
    let mut result = dir.to_vec();
    for i in 0..n.min(result.len()) {
        for j in 0..n.min(result[i].len()) {
            if !result[i][j].is_finite() || result[i][j] < 0.0 {
                result[i][j] = 0.0;
            }
        }
        let row_sum: f64 = result[i].iter().sum();
        if row_sum > 0.0 {
            for j in 0..result[i].len() {
                result[i][j] /= row_sum;
            }
        }
    }
    result
}

/// Combine multiple P2 score sets.
/// edge_weights: element-wise product, then normalize.
/// cost_multiplier: element-wise product (costs stack).
pub fn combine_p2(n: usize, all: &[&P2Scores]) -> P2Scores {
    let nn = n * n;
    if all.is_empty() {
        return P2Scores::uniform(n);
    }
    if all.len() == 1 {
        let mut ew = all[0].edge_weights.clone();
        let mut cm = all[0].cost_multiplier.clone();
        // Sanitize non-finite/negative values (consistent with multi-cell path)
        for w in &mut ew {
            if !w.is_finite() || *w < 0.0 {
                *w = 1.0;
            }
        }
        for w in &mut cm {
            if !w.is_finite() || *w < 0.0 {
                *w = 1.0;
            }
        }
        // Zero diagonal entries even in single-cell fast path
        for i in 0..n {
            ew[i * n + i] = 0.0;
        }
        return P2Scores {
            edge_weights: ew,
            cost_multiplier: cm,
        };
    }

    let mut combined_ew = vec![1.0; nn];
    let mut combined_cm = vec![1.0; nn];

    for scores in all {
        for k in 0..nn {
            combined_ew[k] *= scores.edge_weights[k];
            combined_cm[k] *= scores.cost_multiplier[k];
        }
    }

    // Sanitize non-finite/negative values from multiplication
    for w in &mut combined_ew {
        if !w.is_finite() || *w < 0.0 {
            *w = 1.0;
        }
    }
    for w in &mut combined_cm {
        if !w.is_finite() || *w < 0.0 {
            *w = 1.0;
        }
    }

    // Zero diagonal entries (P2 never flips self-loops) to avoid dead probability mass
    for i in 0..n {
        combined_ew[i * n + i] = 0.0;
    }

    // Normalize edge_weights over off-diagonal entries only
    let sum: f64 = combined_ew.iter().sum();
    if sum > 0.0 {
        for w in &mut combined_ew {
            *w /= sum;
        }
    }

    P2Scores {
        edge_weights: combined_ew,
        cost_multiplier: combined_cm,
    }
}

/// Combine multiple P3 score sets by element-wise product, then renormalize.
pub fn combine_p3(all: &[&P3Scores]) -> P3Scores {
    if all.is_empty() {
        return P3Scores::identity();
    }

    let mut combined = [1.0f64; 6];
    for scores in all {
        for i in 0..6 {
            combined[i] *= scores.weight_multipliers[i];
        }
    }

    // Sanitize non-finite/negative values from multiplication
    for w in &mut combined {
        if !w.is_finite() || *w < 0.0 {
            *w = 1.0;
        }
    }

    // Renormalize
    let sum: f64 = combined.iter().sum();
    if sum > 0.0 {
        for w in &mut combined {
            *w /= sum;
        }
    }

    P3Scores {
        weight_multipliers: combined,
    }
}

/// P6 modulation output: budget rate and cap adjustments.
///
/// Applied to replenishment: `replenish(budget, rate * rate_mult, cap * cap_mult)`.
/// All 1.0 = no effect (identity).
pub struct P6Scores {
    /// Multiplier for the replenishment rate. >1.0 = faster replenishment.
    pub budget_rate_mult: f64,
    /// Multiplier for the budget cap. <1.0 = tighter cap.
    pub budget_cap_mult: f64,
}

impl P6Scores {
    /// Default: no modulation.
    pub fn identity() -> Self {
        P6Scores {
            budget_rate_mult: 1.0,
            budget_cap_mult: 1.0,
        }
    }
}

/// Combine multiple P6 score sets by element-wise product.
pub fn combine_p6(all: &[&P6Scores]) -> P6Scores {
    if all.is_empty() {
        return P6Scores::identity();
    }
    let mut rate = 1.0f64;
    let mut cap = 1.0f64;
    for s in all {
        rate *= s.budget_rate_mult;
        cap *= s.budget_cap_mult;
    }
    // Sanitize non-finite/negative values from multiplication
    if !rate.is_finite() || rate < 0.0 {
        rate = 1.0;
    }
    if !cap.is_finite() || cap < 0.0 {
        cap = 1.0;
    }
    P6Scores {
        budget_rate_mult: rate,
        budget_cap_mult: cap,
    }
}
