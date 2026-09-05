# Paperclip Prior-Art Review

Date: 2026-09-05. Target: the current `paper/main.tex`, not a claim of exhaustive literature coverage or independent sign-off.

## Search and Reading

Loaded the local Paperclip skill and `paperclip skill`. Searched the arXiv corpus with these queries (five results each):

- `causal states observational equivalence predictive state minimal sufficient statistic histories` (result set `s_74dadbc8`).
- `automata observation quotient transition monoid hidden state permutation` (`s_bc92c371`).
- `observability equivalence automata coalgebra minimal realization` (`s_d467e736`).

Read relevant full-text lines directly using `paperclip head` and `paperclip grep`; metadata came from each document's `meta.json`. No automated map/reduce verdict or absent search hit was treated as proof of originality. The permutation search was not a basis for adding marginal references.

## Claim-Level Findings

1. **Future-equivalence states and induced transitions are established.** Travers and Crutchfield define history epsilon-machines by equality of future distributions and discuss induced unifilar transitions [1]. This reinforces the existing Shalizi--Crutchfield attribution; the draft now cites this explicit history/generator treatment as well. Its stationary stochastic-process assumptions are not imported into arbitrary typed event catalogs.
2. **Even the present/full-behavior comparison has a classical specialization.** Silva et al. describe deterministic behavior as a language, current output as empty-word acceptance, and transitions as derivatives [2]. Our mathematical reading is that quotienting by language equality refines quotienting by acceptance output. Thus the draft must not claim priority for the comparison-map principle itself. The added paragraph explicitly identifies this Boolean-output specialization; it does not identify every finite declared catalog with a coalgebra satisfying the abstract laws.
3. **Causal-state/bisimulation links are already studied.** Zhang et al. state this connection in their partially observable decision-process setting [3]. The draft credits that work without transferring its stochastic assumptions or declaring all future-test equivalence to be bisimulation.
4. **Support-relative predictive factorization is not exclusive to this project.** A supplemental publisher/arXiv web search surfaced Baltieri et al.'s recent preprint. Its arXiv abstract and full-text introduction describe coupled-process support restriction, predictive factorization, and induced transitions. Paperclip's exact lookup for `2608.20401` returned no record; the source was read directly on [arXiv](https://arxiv.org/html/2608.20401v1), especially Section 1 and its contribution statements. It is credited as a preprint, not an established peer-reviewed priority judgment. Its continuation support differs from this manuscript's fixed visible support object.
5. **Loop asymmetry is an elementary intertwining consequence.** This follows directly from the displayed equation in the manuscript: a moved class can remain within a fiber when the target action is identity. The text now expressly disclaims a new general action theorem or construction of geometric holonomy. This is a local mathematical assessment, not a claim that one of the searched papers proves the exact typed statement.

## Changes and Boundary

Added four targeted references: `SilvaEtAl2013GeneralizingDeterminization`, `TraversCrutchfield2011Equivalence`, `ZhangEtAl2019CausalStates`, and `BaltieriEtAl2026WorldModels`. Retained existing canonical automata, quotient algebra, sufficiency, predictive-state, bisimulation, and Markov/lumpability sources. No speculative DOI was assigned to records without a verified journal DOI.

The abstract, related work, contribution framing, and loop-theorem commentary now present a specific formulation, mechanization, and controlled finite evaluation. They no longer imply priority for the current/full-behavior comparison or support-relative predictive factorization. This review does not certify that the exact assembly is unprecedented. The paper should be evaluated for its explicit assumptions, verified implementation, and usefulness, not an unsupported first-of-its-kind claim.

## Line-Pinned Paperclip References

Verification after edits: `cd paper && latexmk -pdf -interaction=nonstopmode main.tex` succeeded, rebuilding the 28-page PDF and flattened TeX. The final log has no citation/reference or box warnings. The evidence audit was rerun: all 32 artifact comparisons still match, all bibliography keys are used and defined, and the previously disclosed terminal-interface exceptions are unchanged. No Lean or executable-model changes were made in this citation pass.

[1] Nicholas F. Travers and James P. Crutchfield. Equivalence of History and Generator Epsilon-Machines. arXiv:1111.4500 (2011), introduction and related constructions.
https://paperclip.gxl.ai/citations/papers/arx_1111.4500#L15-L25,L41-L46

[2] Alexandra Silva, Filippo Bonchi, Marcello Bonsangue, and Jan Rutten. Generalizing Determinization from Automata to Coalgebras. Logical Methods in Computer Science 9(1) (2013). DOI: 10.2168/LMCS-9(1:9)2013. Publisher metadata checked at https://lmcs.episciences.org/1087.
https://paperclip.gxl.ai/citations/papers/arx_1302.1046#L15-L21,L27-L31,L47-L48

[3] Amy Zhang et al. Learning Causal State Representations of Partially Observable Environments. arXiv:1906.10437 (2019). The read text states its causal-state/bisimulation relationship and assumptions; the manuscript cites the preprint record rather than guessing publication metadata.
https://paperclip.gxl.ai/citations/papers/arx_1906.10437#L14-L22,L27
