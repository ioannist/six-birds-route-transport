# latent_memory_base

- benchmark_id: latent_memory_base
- manifest_path: configs/benchmarks/latent_memory_base.benchmark.json
- transport_package: configs/benchmarks/toy_predictive_witness.json
- seed: 0
- json_artifact: artifacts/results/latent_memory_base.result.json
- csv_artifact: artifacts/tables/latent_memory_base.csv
- ops_note: docs/results/latent_memory_base.md
- measured_interfaces: mid
- loops_tested: end_loop

## Interface Summaries

### mid
- history_count: 2
- |Q|: 1
- |M|: 2
- max_fiber_size: 2
- witness_count: 1
- discrepancy: exact_max_abs_future_gap = 1
- loop_score_current: 0
- loop_score_predictive: 0
- support_fixation_status: passed
- currentization_status: passed
- flattening_status: skipped
- class_label: explicit_latent

## Perturbation Preflight

- sweep_id: latent_memory_base_perturbation
- resolved_targets: 1
- hook_status: passed
- planned_trials: 20

## Warnings

- none

## Conclusion

- latent predictive residue is present but dissolves under admissible same-object refinement
