# latent_memory_pair

- benchmark_ids: latent_memory_base, latent_memory_refined
- seed: 0
- base_json_artifact: artifacts/results/latent_memory_base.result.json
- refined_json_artifact: artifacts/results/latent_memory_refined.result.json
- base_csv_artifact: artifacts/tables/latent_memory_base.csv
- refined_csv_artifact: artifacts/tables/latent_memory_refined.csv
- base_ops_note: docs/results/latent_memory_base.md
- refined_ops_note: docs/results/latent_memory_refined.md
- overlapping_measured_interfaces: mid

| benchmark_id | interface_id | history_count | \|Q\| | \|M\| | max_fiber_size | witness_count | discrepancy_metric_value | support_fixation_status | currentization_status | class_label |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- | --- |
| latent_memory_base | mid | 2 | 1 | 2 | 2 | 1 | 1.0 | passed | passed | explicit_latent |
| latent_memory_refined | mid | 2 | 2 | 2 | 1 | 0 | 0.0 | skipped | skipped | flat |

- conclusion: the pair demonstrates an explicit_latent pattern because the base benchmark is non-flat at `mid`, the refined benchmark is flat at `mid`, the same-support comparison used by the currentization control is non-failing, the base-side currentization status is positive/pass, and the hidden predictive fibers collapse from `max_fiber_size = 2` to `max_fiber_size = 1`.
