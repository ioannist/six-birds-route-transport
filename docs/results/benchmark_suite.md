# Benchmark Suite

- command: `python -m holonomy_memory run-benchmark-suite --seed 0`
- seed: `0`
- benchmark_ids: flat_control, protocol_trap_naive, protocol_trap_honest, flattenable_raw, flattenable_completed, latent_memory_base, latent_memory_refined, dissipative_memory, memory_wheel
- json: `artifacts/results/benchmark_suite.json`
- csv: `artifacts/tables/benchmark_suite.csv`
- note: `docs/results/benchmark_suite.md`

| benchmark_id | interfaces | class_labels | witness_counts | discrepancy_values | predictive_loop_scores |
| --- | --- | --- | --- | --- | --- |
| `flat_control` | `mid` | `flat` | `0` | `0.000` | `0.000` |
| `protocol_trap_naive` | `mid` | `artifact_trap` | `1` | `1.000` | `0.000` |
| `protocol_trap_honest` | `mid` | `flat` | `0` | `0.000` | `0.000` |
| `flattenable_raw` | `mid` | `flattenable` | `1` | `1.000` | `0.000` |
| `flattenable_completed` | `mid` | `flat` | `0` | `0.000` | `0.000` |
| `latent_memory_base` | `mid` | `explicit_latent` | `1` | `1.000` | `0.000` |
| `latent_memory_refined` | `mid` | `flat` | `0` | `0.000` | `0.000` |
| `dissipative_memory` | `mid, end` | `dissipative, flat` | `1, 0` | `1.000, 0.000` | `0.000, 0.000` |
| `memory_wheel` | `mid` | `coherent_candidate` | `1` | `1.000` | `1.000` |
