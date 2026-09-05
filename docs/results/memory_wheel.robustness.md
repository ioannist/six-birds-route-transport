# memory_wheel robustness

- benchmark_id: memory_wheel
- perturbation_manifest_path: configs/benchmarks/memory_wheel.perturbation.json
- base_seed: 0
- trial_count: 20
- resolved_targets: event_packages[1].events[0].weights.A
- predicate_name: memory_wheel_persists
- threshold: 4/5
- pass_count: 20/20
- survival_fraction: 1
- meets_threshold: true

## Evidence

- witness_retention_count: 20/20
- predictive_loop_nontrivial_count: 20/20
- representative_predictive_motion: C0, C1 (fraction=1)

## Conclusion

- robustness threshold is met for this benchmark
