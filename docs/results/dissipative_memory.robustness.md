# dissipative_memory robustness

- benchmark_id: dissipative_memory
- perturbation_manifest_path: configs/benchmarks/dissipative_memory.perturbation.json
- base_seed: 0
- trial_count: 20
- resolved_targets: event_packages[1].events[0].weights.A
- predicate_name: dissipative_persists
- threshold: 4/5
- pass_count: 20/20
- survival_fraction: 1
- meets_threshold: true

## Evidence

- earliest_interface_survivals: 20/20
- later_interface_survivals: 20/20
- representative_transport_collapse: to_end: C0->C0, C1->C0

## Conclusion

- robustness threshold is met for this benchmark
