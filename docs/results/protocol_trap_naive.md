# protocol_trap_naive

- benchmark_id: protocol_trap_naive
- manifest_path: configs/benchmarks/protocol_trap_naive.benchmark.json
- transport_package: configs/benchmarks/toy_predictive_witness.json
- seed: 0
- json_artifact: artifacts/results/protocol_trap_naive.result.json
- csv_artifact: artifacts/tables/protocol_trap_naive.csv
- ops_note: docs/results/protocol_trap_naive.md
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
- flattening_status: skipped
- class_label: artifact_trap

## Perturbation Preflight

- sweep_id: protocol_trap_naive_perturbation
- resolved_targets: 1
- hook_status: passed
- planned_trials: 2

## Warnings

- none

## Conclusion

- apparent residue observed, but classified as protocol trap / artifact
