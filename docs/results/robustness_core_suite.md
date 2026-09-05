# core robustness suite

- seed: 0
- benchmark_list: flat_control, protocol_trap_honest, flattenable_completed, latent_memory_base, latent_memory_refined, dissipative_memory, memory_wheel
- overall_pass: true

## Summary

### flat_control
- predicate_name: flat_cleared
- pass_count: 20/20
- survival_fraction: 1
- threshold: 19/20
- meets_threshold: true
### protocol_trap_honest
- predicate_name: honest_trap_cleared
- pass_count: 20/20
- survival_fraction: 1
- threshold: 19/20
- meets_threshold: true
### flattenable_completed
- predicate_name: completed_collapsed
- pass_count: 20/20
- survival_fraction: 1
- threshold: 4/5
- meets_threshold: true
### latent_memory_base
- predicate_name: explicit_latent_base_retains_witness
- pass_count: 20/20
- survival_fraction: 1
- threshold: 4/5
- meets_threshold: true
### latent_memory_refined
- predicate_name: explicit_latent_refined_dissolves
- pass_count: 20/20
- survival_fraction: 1
- threshold: 4/5
- meets_threshold: true
### dissipative_memory
- predicate_name: dissipative_persists
- pass_count: 20/20
- survival_fraction: 1
- threshold: 4/5
- meets_threshold: true
### memory_wheel
- predicate_name: memory_wheel_persists
- pass_count: 20/20
- survival_fraction: 1
- threshold: 4/5
- meets_threshold: true

## Conclusion

- the core robustness suite is strong enough to proceed
