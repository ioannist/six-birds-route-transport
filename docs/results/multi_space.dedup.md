# Discovery Diversity Audit

- seed: 0
- source search ids: fixed_support_core_small, cyclic_memory_small, groupoid_probe_small
- json path: artifacts/results/discovery/multi_space.dedup.json
- csv path: artifacts/tables/discovery_multi_space_dedup.csv
- note path: docs/results/multi_space.dedup.md
- total shortlisted candidate count: 7
- unique exemplar count: 7
- cluster counts by kind: exact_duplicate=0, near_duplicate=0, singleton=7

| cluster_id | match_kind | exemplar_candidate_id | exemplar_search_id | member_count | member_candidate_ids |
| --- | --- | --- | --- | ---: | --- |
| cluster_000 | singleton | cand_0000 | cyclic_memory_small | 1 | cand_0000 |
| cluster_001 | singleton | cand_0001 | cyclic_memory_small | 1 | cand_0001 |
| cluster_002 | singleton | cand_0002 | cyclic_memory_small | 1 | cand_0002 |
| cluster_003 | singleton | cand_0006 | cyclic_memory_small | 1 | cand_0006 |
| cluster_004 | singleton | cand_0000 | groupoid_probe_small | 1 | cand_0000 |
| cluster_005 | singleton | cand_0001 | groupoid_probe_small | 1 | cand_0001 |
| cluster_006 | singleton | cand_0004 | groupoid_probe_small | 1 | cand_0004 |

- conclusion: the shortlisted discovery set is fully singleton under the current structural and behavior signatures, so it is diverse enough to proceed without dedup pruning.
