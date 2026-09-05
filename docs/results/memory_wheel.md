# memory_wheel

- benchmark_id: memory_wheel
- manifest_path: configs/benchmarks/memory_wheel.benchmark.json
- transport_package: configs/benchmarks/toy_memory_loop.json
- seed: 0
- json_artifact: artifacts/results/memory_wheel.result.json
- csv_artifact: artifacts/tables/memory_wheel.csv
- ops_note: docs/results/memory_wheel.md
- measured_interfaces: mid
- loops_tested: id_mid, swap_mid

## Interface Summaries

### mid
- history_count: 2
- |Q|: 1
- |M|: 2
- max_fiber_size: 2
- witness_count: 1
- discrepancy: exact_max_abs_future_gap = 1
- loop_score_current: 0
- loop_score_predictive: 1
- support_fixation_status: skipped
- currentization_status: skipped
- flattening_status: skipped
- class_label: coherent_candidate

## Perturbation Preflight

- sweep_id: memory_wheel_perturbation
- resolved_targets: 1
- hook_status: passed
- planned_trials: 20

## Flagship Witness

- flagship_interface: mid
- best_witness_pair: h_mid_0, h_mid_1
- current_class_id: C0
- witness_discrepancy: 1

## Loop Action

- designated_loop_id: swap_mid
- current_moved_class_ids: (none)
- predictive_moved_class_ids: C0, C1
- predictive_class_image_mapping: C0->C1, C1->C0
- predictive_moved_class_fraction: 1

## Warnings

- none

## Conclusion

- same-now/different-later residue exists, current loop action is trivial, predictive loop action is nontrivial, no benchmark-attached refinement/completion clears the effect, and the benchmark is classified coherent_candidate
