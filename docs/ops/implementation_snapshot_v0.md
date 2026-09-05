# Implementation Snapshot v0

## Snapshot scope

- v0 implementation snapshot covering benchmark, robustness, discovery, aggregation, reproducibility, and Lean theorem-status artifacts.

## Benchmark artifacts

- suite summary paths:
  - `artifacts/results/benchmark_suite.json`
  - `artifacts/tables/benchmark_suite.csv`
  - `docs/results/benchmark_suite.md`
- per-benchmark result paths:
  - `artifacts/results/flat_control.result.json`
  - `artifacts/results/protocol_trap_naive.result.json`
  - `artifacts/results/protocol_trap_honest.result.json`
  - `artifacts/results/flattenable_raw.result.json`
  - `artifacts/results/flattenable_completed.result.json`
  - `artifacts/results/latent_memory_base.result.json`
  - `artifacts/results/latent_memory_refined.result.json`
  - `artifacts/results/dissipative_memory.result.json`
  - `artifacts/results/memory_wheel.result.json`
- key benchmark notes:
  - `docs/results/flat_control.md`
  - `docs/results/protocol_trap_pair.md`
  - `docs/results/flattenable_pair.md`
  - `docs/results/latent_memory_pair.md`
  - `docs/results/dissipative_memory.md`
  - `docs/results/memory_wheel.md`

## Discovery artifacts

- atlas paths:
  - `artifacts/results/discovery/cyclic_memory_small.atlas.json`
- shortlist paths:
  - `artifacts/results/discovery/cyclic_memory_small.shortlist.json`
- shortlist robustness paths:
  - `artifacts/results/discovery/cyclic_memory_small.shortlist_robustness.json`
- multi-space summary paths:
  - `artifacts/results/discovery/multi_space.discovery.json`
- dedup summary paths:
  - `artifacts/results/discovery/multi_space.dedup.json`
- promoted exemplar paths:
  - `artifacts/results/discovery/promoted_exemplars.json`
  - `docs/results/discovery_exemplars.md`
  - `docs/results/exemplar.cyclic_memory_small.cand_0006.md`
  - `docs/results/exemplar.cyclic_memory_small.cand_0001.md`
- optional promotion-robustness paths:
  - `artifacts/results/discovery/groupoid_probe_small.cand_0000.promotion_robustness.json`
  - `artifacts/results/discovery/groupoid_probe_small.cand_0001.promotion_robustness.json`
  - `artifacts/results/discovery/groupoid_probe_small.cand_0004.promotion_robustness.json`

## Robustness artifacts

- core-suite robustness paths:
  - `artifacts/results/robustness/core_suite.robustness.json`
  - `artifacts/tables/robustness_core_suite.csv`
  - `docs/results/robustness_core_suite.md`
- per-benchmark robustness note paths:
  - `docs/results/flat_control.robustness.md`
  - `docs/results/protocol_trap_honest.robustness.md`
  - `docs/results/flattenable_completed.robustness.md`
  - `docs/results/latent_memory_base.robustness.md`
  - `docs/results/latent_memory_refined.robustness.md`
  - `docs/results/dissipative_memory.robustness.md`
  - `docs/results/memory_wheel.robustness.md`

## Aggregation artifacts

- combined JSON/CSV, figure manifest, and figures:
  - `artifacts/results/aggregate_outputs.json`
  - `artifacts/tables/aggregate_outputs.csv`
  - `artifacts/results/aggregate_figures.json`
  - `docs/results/aggregate_outputs.md`
  - `artifacts/figures/q_vs_m.png`
  - `artifacts/figures/witness_counts.png`
  - `artifacts/figures/loop_action_scores.png`
  - `artifacts/figures/robustness_fractions.png`
  - `artifacts/figures/class_distributions.png`

## Lean status

- toolchain path: `lean/lean-toolchain`
- build command: `cd lean && lake build`
- root module path: `lean/HolonomyMemory.lean`
- theorem module paths:
  - `lean/HolonomyMemory/Interfaces.lean`
  - `lean/HolonomyMemory/Equivalences.lean`
  - `lean/HolonomyMemory/Transport.lean`
  - `lean/HolonomyMemory/Sufficiency.lean`
  - `lean/HolonomyMemory/Witnesses.lean`
  - `lean/HolonomyMemory/Loops.lean`
  - `lean/HolonomyMemory/Asymmetry.lean`
- theorem status list:
  - `futurePredictiveEquiv_implies_currentEventEquiv`: compiled in `lean/HolonomyMemory/Equivalences.lean`
  - `futurePredictiveEquiv_push`: compiled in `lean/HolonomyMemory/Transport.lean`
  - `predictiveQuotient_futureSufficient`: compiled in `lean/HolonomyMemory/Sufficiency.lean`
  - `futureSufficient_stateEq_implies_futurePredictiveEquiv`: compiled in `lean/HolonomyMemory/Sufficiency.lean`
  - `futureSufficient_factorsThroughPredictiveQuotient_onReachable`: compiled in `lean/HolonomyMemory/Sufficiency.lean`
  - `futureSufficient_factorization_unique_onReachable`: compiled in `lean/HolonomyMemory/Sufficiency.lean`
  - `predictiveToCurrent_commutes_with_transport`: compiled in `lean/HolonomyMemory/Transport.lean`
  - `strictRefinement_iff_nonempty_predictiveWitness`: compiled in `lean/HolonomyMemory/Witnesses.lean`
  - `predictiveToCurrent_commutes_with_loopAction`: compiled in `lean/HolonomyMemory/Loops.lean`
  - `loopAsymmetry_exhibits_movedPredictive_fixedCurrent`: compiled in `lean/HolonomyMemory/Asymmetry.lean`

## Reproducibility status

- four frozen commands:
  - `make test`
  - `make benchmark-suite`
  - `make discovery-smoke`
  - `make lean-build`
- reproducibility note path: `docs/ops/reproducibility.md`
- repro freeze summary path: `artifacts/results/repro_freeze.json`

## Open issues

- relative_recombination remains outside the frozen benchmark suite under current future-signature semantics; revisit only if the benchmark policy or semantics change.
- fixed_support_core_small remains all-flat as the multi-space control space; revisit only if deterministic discovery output changes.
- cyclic_memory_small remains the only single-space discovery smoke path and the current productive shortlist source there is coherent-candidate only; widen the frozen smoke surface only after another productive space is promoted.
- Lean formalization stops at the asymmetry theorem and does not yet include moved-class/cardinality predicates for loop nontriviality; next useful ticket would formalize explicit moved-class predicates only if paper claims need them.
- Lean formalization does not yet cover current-event insufficiency or event-state insufficiency theorems beyond the comparison-map layer; extend only if those claims become necessary for the writeup.

## Verification

- all listed paths were checked programmatically and are readable
- regenerated paths: none
