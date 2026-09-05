# Discovery Smoke

- command: `python -m holonomy_memory run-discovery-smoke --seed 0`
- seed: `0`
- primary_search_id: `cyclic_memory_small`
- json: `artifacts/results/discovery/discovery_smoke.json`
- note: `docs/results/discovery_smoke.md`
- atlas: `artifacts/results/discovery/cyclic_memory_small.atlas.json`
- shortlist: `artifacts/results/discovery/cyclic_memory_small.shortlist.json`
- shortlist_robustness: `artifacts/results/discovery/cyclic_memory_small.shortlist_robustness.json`
- multispace: `artifacts/results/discovery/multi_space.discovery.json`
- dedup: `artifacts/results/discovery/multi_space.dedup.json`
- promoted_exemplars: `artifacts/results/discovery/promoted_exemplars.json`

- class_counts[cyclic_memory_small]: flat=0, dissipative=0, coherent_candidate=8
- combined_shortlist_ids: cand_0000, cand_0001, cand_0002, cand_0006
- shortlisted_robustness: cand_0000:0.500:true, cand_0001:0.625:true, cand_0002:0.500:true, cand_0006:0.750:true
- multispace_all_flat: fixed_support_core_small
- multispace_productive: cyclic_memory_small, groupoid_probe_small
- promoted_exemplars: cyclic_memory_small:cand_0006, cyclic_memory_small:cand_0001
