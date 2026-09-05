# protocol_trap_pair

- benchmark_ids: protocol_trap_naive, protocol_trap_honest
- seed: 0
- naive_json_artifact: artifacts/results/protocol_trap_naive.result.json
- honest_json_artifact: artifacts/results/protocol_trap_honest.result.json
- naive_csv_artifact: artifacts/tables/protocol_trap_naive.csv
- honest_csv_artifact: artifacts/tables/protocol_trap_honest.csv
- naive_ops_note: docs/results/protocol_trap_naive.md
- honest_ops_note: docs/results/protocol_trap_honest.md
- overlapping_measured_interfaces: mid

| benchmark_id | interface_id | history_count | \|Q\| | \|M\| | witness_count | discrepancy_metric_value | current_loop_score | predictive_loop_score | support_fixation_status | class_label |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| protocol_trap_naive | mid | 2 | 1 | 2 | 1 | 1.0 | 0.0 | 0.0 | passed | artifact_trap |
| protocol_trap_honest | mid | 2 | 1 | 1 | 0 | 0.0 | 0.0 | 0.0 | skipped | flat |

- conclusion: the pair demonstrates an artifact_trap pattern because the naive benchmark is non-flat at `mid`, the honest benchmark is flat at `mid`, and the same-support comparison used by the naive pair-aware analysis is non-failing.
