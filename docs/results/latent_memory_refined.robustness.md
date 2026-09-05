# latent_memory_refined robustness

- benchmark_id: latent_memory_refined
- perturbation_manifest_path: configs/benchmarks/latent_memory_refined.perturbation.json
- base_seed: 0
- trial_count: 20
- resolved_targets: event_packages[0].events[0].weights.A
- predicate_name: explicit_latent_refined_dissolves
- threshold: 4/5
- pass_count: 20/20
- survival_fraction: 1
- meets_threshold: true

## Evidence

- cleared_or_collapsed_trials: 20/20
- representative_failure_reason: none

## Conclusion

- robustness threshold is met for this benchmark
