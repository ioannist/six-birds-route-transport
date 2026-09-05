# Canonical Primitive Specification: P1-P6 ("Six Birds")

Source: Tsiokos, I. "Six Birds: Foundations of Emergence Calculus" (arxiv:2602.00134)
and "To Lay a Stone with Six Birds: A Minimal Substrate Theorem for SPT" (2026).

## Foundational Setting

The six primitives are **not axioms**. They are structurally forced once three conditions hold:
1. **Composability** (D-META-PROC-01): processes compose associatively (partial semigroup).
2. **Limited access** (D-META-LENS-01): observation is through a lens f: P -> X that collapses distinctions.
3. **Bounded interfaces** (D-META-BND-01): |P/~_j| <= C_0(j+1) for refinement depth j.

Under these conditions, Theorem (T-META-PRIM / thm:meta-prim) proves P1-P6 arise canonically
as closure mechanics of description.

## Minimal Substrate

The canonical minimal machine substrate is:
- **State space Z**: finite set of microstates.
- **Dynamics**: autonomous finite stochastic dynamics (Markov kernel P on Z).
- **Phase-in-state**: extended state Z := X x Phi (phase is internal, not external schedule).
- **Lens**: deterministic coarse-graining f: Z -> X (surjective).
- **Packaging endomap**: E_{tau,f} induced by dynamics + lens + timescale.
- **Audit functionals**: path-reversal KL asymmetry Sigma_T and ACC affinities (intrinsic).

A **theory package** is a tuple T = (Z, f, Sigma_f, E, A) where:
- Z = finite carrier set (microstate space)
- f: Z -> X = lens (coarse description)
- Sigma_f = definability sigma-algebra induced by f
- E: V -> V = completion/packaging endomap (idempotent or approximately so)
- A = audit functional, monotone under coarse maps

## Primitive Definitions

### P1: Operator Rewrite
Replace the substrate Markov kernel P by a new kernel P' (or a finite family {P^(m)}),
thereby changing the endomap mu -> mu P^tau and the induced empirical endomap E_{tau,f}.
This is a change in the operator itself, not an external schedule.

**When triggered**: When induced macro-dynamics F^sharp([p]) = [F(p)] fails to descend
(i.e., p ~_j q does NOT imply F(p) ~_j F(q)), closure at depth j requires rewrite/extension.

**Effect on closure**: Can increase or decrease cycle rank and spectral gap.

### P2: Gating / Constraints
Restrict the support graph by deleting edges (setting selected P_{ij} = 0) and renormalizing
rows, or equivalently restricting to a subgraph on which the kernel lives.

**Effect on closure**: Shrinks cycle space. Feasibility carves representable macrostates.

### P3: Autonomous Protocol Holonomy
Modeled in the autonomous lifted form on Z := X x Phi. The phase phi in Phi evolves by
an internal kernel S, and conditioned on phi the microstate updates by K_phi.

**Key constraint**: No external schedule is assumed. Externally scheduled stroboscopic
protocols are non-autonomous and fall outside A_AUT.

**Diagnostic**: Route mismatch/holonomy RM(j) measures noncommutativity of reduction routes.
By itself does NOT certify directionality; any arrow-of-time claim must be supported by an
audit functional (P6).

**"P3 needs P6_drive"**: Under autonomy, nonzero steady-state entropy production requires
nontrivial ACC affinity component (P6_drive).

### P4: Sectors / Invariants
A conserved sector label: the support decomposes into disconnected components (block structure),
or equivalently P is block diagonal up to permutation, so evolution preserves a sector coordinate.

**In meta-theorem**: The refinement chain generates a depth index j, and bounded interfaces
ensure |X_j| <= ~(j+1). Nontrivial staging = strict refinement at some scale.

### P5: Packaging
An idempotent endomap e whose fixed points Fix(e) are the packaged objects of a given theory.
This is an endomap notion, NOT an order-closure.

**In meta-theorem**: Each equivalence ~_j yields a quotient/packaging map Pi_j and induces
an idempotent saturation on predicates: cl_j(A) := Pi_j^{-1}(Pi_j(A)).

**Key properties**:
- Idempotent: e(e(x)) = e(x)
- Fixed points are the "objects" recognized by the theory
- Packaging equivalence: two states are equivalent if they package to the same representative

### P6: Accounting / Audit
A certificate or functional that is monotone under coarse maps or packaging.

**Canonical instantiations**:
1. Information/feasibility order induced by limited access (META level).
2. Path-space KL asymmetry Sigma_T with data processing (arrow-of-time audit).
3. ACC graph 1-form / cycle-integral audit (drive audit).

**P6_drive**: Non-exact log-ratio 1-form (equivalently, nonzero cycle integral).
This is the condition for genuine arrows of time under autonomy.

**Data processing inequality**: Coarse-graining cannot create arrow-of-time;
Sigma_T^macro <= Sigma_T^micro (monotonicity under lenses).

## Theory Growth Loop (How Primitives Compose)

1. **Limited access => P5 packaging**: Lens collapses distinctions, completion packages microstates into fixed-point objects.
2. **Lossy packaging => P6 accounting**: Audits track what survives under lenses.
3. **Saturation => extension**: Iterating a fixed completion saturates; strict growth requires theory extension.
4. **P4 staging**: Refinement family supplies theory index; bounded interfaces keep it coherent.
5. **P2 gating**: Feasibility carves representable macrostates, restricts support/cycle space.
6. **P1 rewrite**: When macro-dynamics fails to descend, operator rewrite is forced.
7. **P3 route mismatch**: Noncommuting reductions yield RM(j); agnostic to directionality without P6.
8. **Iteration**: Updated (lens, completion, audit) defines next theory; loop repeats.

## Assumption Bundles (Standing Hypotheses)

- **A_FIN**: Finite state space.
- **A_LENS**: Deterministic coarse-graining lens.
- **A_AUT**: Autonomous dynamics (phase-in-state, no external schedule).
- **A_REV**: Microreversibility (bidirected support graph).
- **A_ACC**: ACC log-ratio 1-form is well-defined on bidirected support.

## Key Invariants / No-Smuggling Rules

1. Primitives must be **realized** as internal structure, not external oracular input.
2. No external protocols masquerading as autonomy (protocol trap).
3. No externally declared quotients/objects (packaging must be induced).
4. No external directionality audits (audit must respect limited access monotonicity).
5. Downward influence is NOT a seventh primitive; it factors through P1-P6 compositions.

## UNKNOWN_TODOs

- UNKNOWN_TODO: Precise finiteness bounds for minimal substrate in code representation.
  Resolution experiment: EXP-RES-001 (implement canonical machine class S_min and verify
  all six primitives are realizable).
- UNKNOWN_TODO: Operational threshold for "approximately idempotent" in packaging.
  Resolution experiment: EXP-RES-002 (sweep idempotence defect ||E(E(x)) - E(x)|| across
  scales and identify stability threshold).
