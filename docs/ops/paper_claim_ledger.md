# Paper Claim Ledger

## Allowed claims

- In the abstract identity-and-composition core, future-predictive equivalence refines current-event equivalence. Finite declared catalogs require a separate refinement check.
- The predictive quotient carries admissible transport and there is a canonical comparison map from the predictive quotient to the current quotient.
- The predictive quotient is future-sufficient: its projection factors uniquely through the reachable image of every future-sufficient state abstraction, by a map from that reachable image to the predictive quotient, not in the reverse direction.
- Strict refinement of the comparison map is equivalent to existence of predictive witnesses.
- Loop action can be trivial on the current quotient and nontrivial on the predictive quotient.
- Current quotient transport and current/predictive commutation require a current-compatible continuation. Universal current compatibility would collapse the two equivalences; it is not a core assumption.
- The Boolean model in `lean/HolonomyMemory/Examples.lean` mechanizes an actual predictive witness, compatible loop asymmetry, and an incompatible readout continuation.
- Exact finite fixed-support benchmarks instantiate flat, artifact/trap, flattenable, explicit-latent, dissipative, and coherent-candidate regimes.
- The bounded robustness suite supports the intended benchmark behaviors on the configured perturbation families.
- Conservative discovery searches recover additional coherent candidates and include an all-flat control space.
- The exact finite implementation uses rational histories, rational continuation kernels, and rational event weights rather than floating-point quotient computation.
- Current and future signatures are computed from the declared history set, declared continuation catalog, and declared event packages in deterministic order.
- Future signatures use only declared admissible continuations at the signature stage; no transitive closure is inserted into quotient computation.
- The benchmark and discovery diagnostics include exact witness count, max fiber size, exact maximum future gap, and loop-action scores on the current and predictive quotients.
- Support-fixation, completion, and currentization are explicit paired controls recorded in the artifact outputs.
- Robustness fractions are benchmark-specific survival fractions under deterministic bounded perturbation bundles.
- In `flat_control` at `mid`, `|Q|=|M|=1`, witness count is `0`, discrepancy is `0`, and both loop-action scores are `0`.
- In the protocol-trap pair at `mid`, `protocol_trap_naive` is non-flat with `|Q|=1`, `|M|=2`, witness count `1`, discrepancy `1`, while `protocol_trap_honest` is flat with `|Q|=|M|=1`, witness count `0`, discrepancy `0`.
- In the flattenable pair at `mid`, `flattenable_raw` is non-flat with `|Q|=1`, `|M|=2`, witness count `1`, discrepancy `1`, and `flattenable_completed` is flat with `|Q|=|M|=1`, witness count `0`, discrepancy `0`.
- In the explicit latent pair at `mid`, `latent_memory_base` has `|Q|=1`, `|M|=2`, `max_fiber_size=2`, witness count `1`, discrepancy `1`, while `latent_memory_refined` has `|Q|=|M|=2`, `max_fiber_size=1`, witness count `0`, discrepancy `0`.
- In `dissipative_memory`, the earlier interface `mid` is non-flat with `|Q|=1`, `|M|=2`, `max_fiber_size=2`, witness count `1`, discrepancy `1`, while the later interface `end` is flat with `|Q|=|M|=1`, `max_fiber_size=1`, witness count `0`, discrepancy `0`.
- In `dissipative_memory`, the designated continuation `to_end` maps the two predictive classes at `mid` into one predictive class at `end`, with class-image mapping `C0->C0, C1->C0`.
- In `memory_wheel` at `mid`, `|Q|=1`, `|M|=2`, `max_fiber_size=2`, witness count `1`, discrepancy `1`, current loop score `0`, predictive loop score `1`, and class label `coherent_candidate`.
- In `memory_wheel`, under loop `swap_mid`, the predictive classes `C0` and `C1` are exchanged while the current moved-class set is empty.
- In `memory_wheel`, the best witness pair recorded in the tracked note is `h_mid_0, h_mid_1`, with current class id `C0` and exact discrepancy value `1`.
- The bounded core-suite robustness run records survival fraction `1.0` for all seven monitored benchmark families under their configured predicates and thresholds.
- In the multi-space discovery summary, `fixed_support_core_small` is all-flat with class counts `(flat=4, dissipative=0, coherent_candidate=0)` and shortlist count `0`.
- In the multi-space discovery summary, `cyclic_memory_small` is productive with class counts `(flat=0, dissipative=0, coherent_candidate=8)` and shortlist count `4`.
- In the multi-space discovery summary, `groupoid_probe_small` is productive with class counts `(flat=4, dissipative=0, coherent_candidate=4)` and shortlist count `3`.
- The shortlisted robustness run for `cyclic_memory_small` records survival fractions `0.50`, `0.625`, `0.50`, and `0.75` for shortlisted candidates `cand_0000`, `cand_0001`, `cand_0002`, and `cand_0006`, respectively.
- The promoted exemplar summary selects `cyclic_memory_small:cand_0006` and `cyclic_memory_small:cand_0001`, both with survival fraction above threshold and singleton dedup status.
- The multi-space dedup audit contains `7` shortlisted candidates and returns `7` singleton clusters.
- The optional `relative_recombination` candidate was dropped under the current future-signature semantics because its non-flat behavior reduced to single-continuation predictive distinctions already captured by the existing suite.

## Claims to soften

- Finite catalogs are not automatically full models of the abstract core. Reported benchmark interfaces and discovery primary interfaces pass refinement checks, but twelve discovery terminal interfaces do not; no comparison map or all-future sufficiency is asserted there.
- The core robustness sweeps perturb one event weight each, not transition kernels or histories. Their twenty trials need not be distinct models; survival does not certify dynamical stability.
- A skipped completion/currentization control is absence of a tested repair, not evidence that repair is impossible.
- The `coherent_candidate` classification alone does not certify loop asymmetry or successful support fixation; the loop metrics and attached controls must be checked separately.
- Singleton dedup clusters concern descriptor-family and primary-metric signatures, not a proof of structural nonisomorphism.
- Quotient descent, future-test equivalence, and reachable-image factorization specialize established algebraic and automata constructions; no priority for these underlying principles is claimed.
- The current/full-behavior comparison already has a classical deterministic-automata specialization; support-relative predictive factorization is also studied elsewhere. The Paperclip review in `paper_prior_art_review.md` supports attribution and restricted contribution language, not certification that this assembly is unprecedented.
- Canonicality of the predictive quotient should be phrased on the reachable image, not as a stronger unrestricted universality theorem.
- Discovery results support “not limited to a single hand-built example,” not genericity or exhaustive classification.
- Coherent-candidate is an operational benchmark/discovery label, not a theorem that a stronger physical structure has been derived.

## Banned claims

- Derivation of Hilbert-space structure, amplitudes, interference laws, or the Born rule.
- Resolution of Bell-type constraints.
- A full classification theorem for all route mismatch.
- A positive relative-recombination benchmark result.
- Any larger external-program or ultimate-goal framing not supported by the paper itself.

## Editorial audit status

- The earlier unqualified audit was superseded by the 2026-09-05 mathematical and evidence self-review recorded in `docs/ops/paper_finalization_audit.md`.
- The universal-pullback assumption and reversed factorization wording were repaired; finite-catalog, robustness, label, and dedup claims were restricted to their checked scope.
- `docs/ops/paper_evidence_audit.json` records reproduced evidence and all twelve terminal-interface refinement failures. Its passing gate concerns reported comparisons only, not full-catalog validity.
- The revised manuscript has no identified unresolved claim conflict within that scope. This is an internal self-review, not independent mathematical or author publication sign-off.
