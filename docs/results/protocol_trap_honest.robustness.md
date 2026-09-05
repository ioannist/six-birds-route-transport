# protocol_trap_honest robustness

- benchmark_id: protocol_trap_honest
- perturbation_manifest_path: configs/benchmarks/protocol_trap_honest.perturbation.json
- base_seed: 0
- trial_count: 20
- resolved_targets: event_packages[0].events[0].weights.B
- predicate_name: honest_trap_cleared
- threshold: 19/20
- pass_count: 20/20
- survival_fraction: 1
- meets_threshold: true

## Evidence

- cleared_or_collapsed_trials: 20/20
- representative_failure_reason: none

## Conclusion

- robustness threshold is met for this benchmark
