# relative_recombination

- decision: DROP
- candidate_attempted: yes
- candidate_label: relative_recombination_candidate
- candidate_validated: yes
- candidate_ran_under_current_engine: yes
- outcome: non-flat but not worth keeping
- reduction_failure_mode: reducible to a single-continuation witness already captured by the current suite
- closest_existing_behavior: latent_memory_base
- summary:
  - the attempted candidate produced a witness at `mid` with discrepancy `1`
  - the best witness pair was `h0, h1`
  - the argmax discrepancy already occurred on the single continuation/event component `to_end / indicator_B`
  - the second route family `to_probe / indicator_B` also distinguished the pair on its own
  - therefore the effect is not irreducibly route-relative under the current future-signature semantics
- recommendation: revisit only after later interference/recombination semantics exist
