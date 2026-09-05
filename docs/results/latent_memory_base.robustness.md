# latent_memory_base robustness

- benchmark_id: latent_memory_base
- perturbation_manifest_path: configs/benchmarks/latent_memory_base.perturbation.json
- base_seed: 0
- trial_count: 20
- resolved_targets: event_packages[1].events[0].weights.A
- predicate_name: explicit_latent_base_retains_witness
- threshold: 4/5
- pass_count: 20/20
- survival_fraction: 1
- meets_threshold: true

## Evidence

- witness_retention_count: 20/20
- representative_structure: |Q|=1, |M|=2, max_fiber_size=2

## Conclusion

- robustness threshold is met for this benchmark
