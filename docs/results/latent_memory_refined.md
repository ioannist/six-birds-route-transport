# latent_memory_refined

- benchmark_id: latent_memory_refined
- manifest_path: configs/benchmarks/latent_memory_refined.benchmark.json
- transport_package: configs/benchmarks/latent_memory_refined.package.json
- seed: 0
- json_artifact: artifacts/results/latent_memory_refined.result.json
- csv_artifact: artifacts/tables/latent_memory_refined.csv
- ops_note: docs/results/latent_memory_refined.md
- measured_interfaces: mid
- loops_tested: end_loop

## Interface Summaries

### mid
- history_count: 2
- |Q|: 2
- |M|: 2
- max_fiber_size: 1
- witness_count: 0
- discrepancy: exact_max_abs_future_gap = 0
- loop_score_current: 0
- loop_score_predictive: 0
- support_fixation_status: skipped
- currentization_status: skipped
- flattening_status: skipped
- class_label: flat

## Perturbation Preflight

- sweep_id: latent_memory_refined_perturbation
- resolved_targets: 1
- hook_status: passed
- planned_trials: 20

## Warnings

- none

## Conclusion

- refinement makes the relevant distinction current-visible and removes the witness
