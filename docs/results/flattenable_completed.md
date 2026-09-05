# flattenable_completed

- benchmark_id: flattenable_completed
- manifest_path: configs/benchmarks/flattenable_completed.benchmark.json
- transport_package: configs/benchmarks/toy_flat_signatures.json
- seed: 0
- json_artifact: artifacts/results/flattenable_completed.result.json
- csv_artifact: artifacts/tables/flattenable_completed.csv
- ops_note: docs/results/flattenable_completed.md
- measured_interfaces: mid
- loops_tested: end_loop

## Interface Summaries

### mid
- history_count: 2
- |Q|: 1
- |M|: 1
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

- sweep_id: flattenable_completed_perturbation
- resolved_targets: 1
- hook_status: passed
- planned_trials: 20

## Warnings

- none

## Conclusion

- completion counterpart is flat/collapsed
