# Discovery Exemplars

- seed: 0
- promoted qualified ids: cyclic_memory_small:cand_0006, cyclic_memory_small:cand_0001
- summary json path: artifacts/results/discovery/promoted_exemplars.json
- summary csv path: artifacts/tables/discovery_promoted_exemplars.csv
- index note path: docs/results/discovery_exemplars.md

| qualified_id | class_label | discrepancy | predictive_loop_score | survival_fraction | threshold | meets_threshold | distinctness_kind |
| --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| cyclic_memory_small:cand_0006 | coherent_candidate | 1 | 1 | 3/4 | 1/2 | true | singleton |
| cyclic_memory_small:cand_0001 | coherent_candidate | 1 | 1 | 5/8 | 1/2 | true | singleton |

- conclusion: these exemplars were promoted because they combine the strongest bounded robustness with nontrivial discrepancy, loop-signal evidence, and explicit dedup distinctness.
