# Lens Hypotheses Notebook

All candidate lenses for the coarse-graining step. Each must be an emergent
property discoverable via the six primitives — NO engineered lenses.

Rule: the 6Ps can be applied to anything as long as it is not engineered and
is an emergent property. Constants chosen for tuning (like grid size) are
acceptable as test hypotheses but not as permanent fixtures.

## Active Candidates

*None remaining. All four emergent candidates tested in Layer 6 and closed.*

## Scaffolding (Not Legitimate — Used for Convenience)

### LENS-000: Modular lens (z -> z % m)
- **Composition**: None (arithmetic on state labels)
- **Status**: tested extensively (Layers 0-7), best empirical results
- **DPI rate at large scale**: 42.5% (CLO-026), 87.5% with tau=20 (CLO-027)
- **Strengths**: Simple, best DPI-dynamics balance found so far
- **Weakness**: Assumes states have meaningful numeric ordering. Modulo is
  arithmetic — it presupposes number structure that has not been earned from
  P1-P6. State labels are arbitrary implementation artifacts.
- **Status**: SCAFFOLDING. Used as a convenience to develop the pipeline, but
  must eventually be replaced by a lens that emerges from P1-P6 composition.
  The ladder cannot rest on an assumed number system.

## Tested and Closed (Layer 6)

### LENS-001: P2-emergent fragmentation lens — CLOSED (CLO-029)
- **Composition**: P2->P4->lens
- **Experiment**: EXP-033
- **Result**: 29/40 viable, 19/40 beats_dpi, BUT all viable runs have gap=0,
  sigma=0, RM=0 (diagonal macro kernel). DPI satisfied vacuously.
- **Verdict**: DPI-by-isolation, not DPI-preservation. Trivial macro dynamics.
- **Root cause**: Fragmentation threshold creates too many tiny blocks.

### LENS-002: P6-audit-informed grouping — CLOSED (CLO-030)
- **Composition**: P6->lens
- **Experiment**: EXP-034
- **Result**: 8/40 viable, 5/40 beats_dpi. Gating removes the irreversibility
  signal that the lens needs. Sorting near-zero violations = random grouping.
- **Verdict**: Self-defeating composition — P2 prerequisite kills P6 input.
- **Root cause**: P2->P6->lens is contradictory (gating removes sigma that
  P6 needs to differentiate states).

### LENS-003: P3-guided lens search — CLOSED (CLO-031)
- **Composition**: P3 as objective function
- **Experiment**: EXP-035
- **Result**: 32/40 viable, 19/40 beats_dpi, 40/40 beats_rm, mean 68.7
  improvements. BUT search_sigma=0 in 40/40 (trivial macro dynamics).
- **Verdict**: RM minimization is the wrong objective — drives toward triviality.
- **Root cause**: RM gradient points toward diagonal macro kernels.

### LENS-004: P5 cross-chain lens — CLOSED (CLO-032)
- **Composition**: P5 on symmetrized kernel -> lens for original
- **Experiment**: EXP-036
- **Result**: 11/40 viable, 0/40 beats_dpi, 23/40 beats_rm.
  Symmetrized kernel has 0-1 FPs in 36/40 runs.
- **Verdict**: Reversible chains too sparse for meaningful coarse-graining.
- **Root cause**: P5 packaging on reversible chains produces insufficient
  resolution (mostly single FP).

## Rejected (Engineering)

### LENS-REJ-001: Spectral lens (second eigenvector grouping)
- **Reason**: Engineering. Uses kernel spectral decomposition directly.
  Not discoverable by the six primitives as a composition.

### LENS-REJ-002: P4 sector-local modular (SLM)
- **Reason**: Tested (CLO-024, EXP-028). WORSE DPI than modular (23/40 vs 34/40).
  Within-block irreversibility exceeds micro sigma.

## Evaluation Protocol

For each lens candidate, test against LENS-000 (modular) on the same
chains at scales [32, 64, 128, 256]. Metrics:
- DPI success rate (primary)
- Route mismatch (lower = better)
- Spectral gap preservation
- Fixed point count
- Packaging defect

## Meta-Observation (CLO-033)

All tested emergent lenses fall into one of two failure modes:
1. **DPI-preserving but trivial**: Diagonalizes the macro kernel (LENS-001, LENS-003)
2. **Nontrivial but DPI-violating**: Same failure as modular (LENS-004) or
   self-defeating composition (LENS-002)

This suggests DPI and nontrivial macro dynamics are in fundamental tension
at scale. The modular lens with tau=20 may represent the practical optimum.

## Protocol Note: What Lenses Are Legitimate?

The ONLY legitimate lens source is **P-composition**: apply P1-P6 to the kernel
and read off the resulting structure as a partition (e.g., P2→P4 sectors).

**NOT legitimate**:
- **Arithmetic on labels**: Modular (z mod m), parity, etc. These assume numeric
  ordering of states, which is an implementation artifact. Numbers and ordering
  must themselves emerge from P1-P6 if they are to be used. (LENS-000 is
  scaffolding, not a valid endpoint.)
- **Dynamics-derived grouping**: Any procedure that inspects kernel entries to
  engineer a lens mapping (e.g., "merge by highest cross-block flow"). This was
  the error in EXP-039/CLO-036 (RETRACTED).
- **External mathematics**: Spectral decomposition, clustering algorithms, etc.
  (LENS-REJ-001).

## BREAKTHROUGH: DAG Merge Lens (CLO-039, Layer 8)

### LENS-005: Joint substrate from two P-composition lenses
- **Composition**: (P2→P4) ⊗ (P1sym→P2→P4) → joint (a,b) substrate
- **Experiment**: EXP-041
- **Result**: 17/40 (42.5%) have BOTH DPI and gap>0.01
  - Merge gap: 0.97-0.99 (strong dynamics)
  - Merge sigma: 0.00-0.18 (well below root sigma ~4-5)
  - Merge RM: 0.001-0.009 (low route mismatch)
  - Merge n: 4-7 macro states
- **Key**: Neither branch alone achieves this — both have gap=0, sigma=0.
  The dynamics emerge from the INTERACTION of two trivial lenses.
- **Status**: FIRST P-composition-only lens satisfying all three criteria.

### Resolution of the Lens Problem

The lens problem was framed as: find ONE lens satisfying DPI + dynamics + P-composition.
This framing was wrong. The answer is: use MULTIPLE lenses simultaneously. The DAG
structure (branch + merge) resolves what no single lens can.

The linear ladder assumed one lens per layer. The graph structure lets multiple
P-compositions coexist, and their joint substrate creates emergent structure
that no individual composition produces.

## Future Directions

1. Try more composition pairs (not just P2→P4 vs P1sym→P2→P4)
2. Three-way merges: does adding a third branch improve the 42.5% rate?
3. Deeper DAGs: can the merge node be branched and merged again?
4. Why do some seeds fail? (Both branches need ≥2 blocks — can this be ensured?)
