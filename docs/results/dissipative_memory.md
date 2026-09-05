# dissipative_memory

- benchmark_id: dissipative_memory
- manifest_path: configs/benchmarks/dissipative_memory.benchmark.json
- transport_package: configs/benchmarks/dissipative_memory.package.json
- seed: 0
- json_artifact: artifacts/results/dissipative_memory.result.json
- csv_artifact: artifacts/tables/dissipative_memory.csv
- ops_note: docs/results/dissipative_memory.md
- measured_interfaces: mid, end
- loops_tested: id_end

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
- support_fixation_status: skipped
- currentization_status: skipped
- flattening_status: skipped
- class_label: dissipative

### end
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

- sweep_id: dissipative_memory_perturbation
- resolved_targets: 1
- hook_status: passed
- planned_trials: 20

## Transport Collapse

- designated_continuation_family: to_end
- source_interface: mid
- target_interfaces: end
- continuation to_end: mid -> end
- continuation to_end source_predictive_class_count: 2
- continuation to_end target_predictive_class_count: 1
- continuation to_end class_image_mapping: C0->C0, C1->C0

## Warnings

- none

## Conclusion

- earlier interface has predictive residue, later transport collapses it, and the earlier interface is classified dissipative
