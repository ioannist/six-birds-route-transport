# flattenable_pair

- benchmark_ids: flattenable_raw, flattenable_completed
- seed: 0
- raw_json_artifact: artifacts/results/flattenable_raw.result.json
- completed_json_artifact: artifacts/results/flattenable_completed.result.json
- raw_csv_artifact: artifacts/tables/flattenable_raw.csv
- completed_csv_artifact: artifacts/tables/flattenable_completed.csv
- raw_ops_note: docs/results/flattenable_raw.md
- completed_ops_note: docs/results/flattenable_completed.md
- overlapping_measured_interfaces: mid

| benchmark_id | interface_id | history_count | \|Q\| | \|M\| | witness_count | discrepancy_metric_value | current_loop_score | predictive_loop_score | support_fixation_status | flattening_status | class_label |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- | --- |
| flattenable_raw | mid | 2 | 1 | 2 | 1 | 1.0 | 0.0 | 0.0 | passed | passed | flattenable |
| flattenable_completed | mid | 2 | 1 | 1 | 0 | 0.0 | 0.0 | 0.0 | skipped | skipped | flat |

- conclusion: the pair demonstrates a flattenable pattern because the raw benchmark is non-flat at `mid`, the completed benchmark is flat/collapsed at `mid`, the same-support comparison used by the completion control is non-failing, and the raw-side flattening status is positive/pass.
