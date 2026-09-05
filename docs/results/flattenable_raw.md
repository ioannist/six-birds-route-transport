# flattenable_raw

- benchmark_id: flattenable_raw
- manifest_path: configs/benchmarks/flattenable_raw.benchmark.json
- transport_package: configs/benchmarks/toy_predictive_witness.json
- seed: 0
- json_artifact: artifacts/results/flattenable_raw.result.json
- csv_artifact: artifacts/tables/flattenable_raw.csv
- ops_note: docs/results/flattenable_raw.md
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
- currentization_status: skipped
- flattening_status: passed
- class_label: flattenable

## Perturbation Preflight

- sweep_id: flattenable_raw_perturbation
- resolved_targets: 1
- hook_status: passed
- planned_trials: 2

## Warnings

- none

## Conclusion

- non-flat mismatch observed, but collapses under admissible completion
