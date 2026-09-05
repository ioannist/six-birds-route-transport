# Paper Finalization Audit

Date: 2026-09-05. Starting revision: `cb4c7e4`.

Status: internally reviewed and revised draft, with passing builds and reproducibility checks within the scope below. This is a self-review by the editing agent, not an independent proof review, author publication sign-off, or journal acceptance. The pre-existing manuscript repository-URL edit was preserved. No sibling repository, historical result artifact, or figure was replaced.

## Mathematical Findings and Repairs

### Universal pullback made the old non-flat claims vacuous

The old `RouteTransportCore` required every later event observation to pull back to an event in the present package. Consequently, current-equivalent histories had equal observations after every continuation and were future-equivalent. With identity continuations, the two equivalences were equal. Thus the old core excluded predictive witnesses and loop asymmetry despite compiling the conditional theorem statements.

The repaired core retains typed histories, continuations, observation, identity, composition, and push laws. Current transport now requires the explicit `CurrentCompatible` predicate; predictive transport still follows from composition. The corresponding current transport, loop action, and commutation theorems carry this hypothesis. The manuscript states the same restriction. This is a substantive assumption/API repair, not a cosmetic proof edit.

`lean/HolonomyMemory/Examples.lean` supplies a two-interface Boolean model: one interface observes a constant and the other reads the history bit. The swap loop at the constant-observation interface is current-compatible and exchanges predictive classes; the readout continuation is not current-compatible. Lean proves `bitCore_witness`, `bitCore_loop_asymmetry`, and `bitCore_read_not_compatible`. The theorem `currentEventEquiv_implies_future_of_all_compatible` formalizes the collapse under universal compatibility. These examples establish inhabitation of the revised assumptions, not a Lean import of the JSON benchmarks.

### Factorization direction

For a future-sufficient state map `s`, the proved map is `Reach(s) -> PredictiveQ`, with the predictive projection equal to that map composed with `s`. The sufficient state map need not factor through the predictive quotient. The abstract, introduction, and claim ledger now follow the actual direction. Sufficiency here is set-theoretic observational factorization, not an assertion of classical conditional-distribution sufficiency.

### Finite catalogs are not automatically abstract cores

Declared finite histories and continuation catalogs need not be closed under push or composition. The implementation checks quotient maps for tested transports; it does not prove the full abstract axioms. In particular, a memory-wheel readout splits a current class and cannot induce current transport, whereas its swap loop can. A regression test now checks this distinction.

All reported benchmark-interface and discovery-primary comparisons pass predictive-to-current refinement checks. Twelve terminal discovery interfaces fail: `cyclic_memory_small:cand_0000` through `cand_0007`, and `groupoid_probe_small:cand_0000`, `cand_0001`, `cand_0004`, `cand_0005`, all at `i1`. These omit terminal identity experiments: the future signature is empty, giving predictive size one despite current size two. There is no refinement-induced comparison map there.

Historical catalog results were preserved rather than silently changing the experiment. Sections 4 and 7 disclose the failure and restrict the discovery comparison claims to the checked primary interfaces. The machine-readable report records `full_catalog_refinement_passed: false` alongside `reported_interface_refinement_passed: true`. A passing report must not be represented as full-catalog formal validation.

## Evidence and Interpretation Limits

- Skipped memory-wheel completion/currentization controls mean no attached comparison, not resistance to every admissible repair.
- Benchmark labels use supplied flags and control outcomes. `coherent_candidate` alone is not a certificate of loop asymmetry, successful support fixation, or physical coherence; loop metrics are separate evidence.
- All seven core robustness bundles perturb a single event weight while keeping histories and transition kernels fixed. Clipping can repeat models. These are bounded observation-perturbation checks, not kernel-stability results.
- Quotient comparisons use exact rational arithmetic on encoded models. Perturbation generation and serialization also use floating-point/decimal operations; no claim of wholly rational generation is made.
- Dedup singleton status concerns descriptor-family and primary-metric signatures, not graph/kernel isomorphism or a broad diversity theorem.

## Citations and Novelty

The manuscript now explicitly identifies future-test equivalence and continuation stability with the classical Myhill--Nerode construction in the deterministic word setting. It credits standard quotient algebra, distinguishes classical statistical sufficiency from the present factorization property, and treats predictive states, causal states, observable operator models, probabilistic bisimulation, and Markov aggregation as adjacent rather than subsumed theories. The contribution is the explicit fixed-support comparison package and audited examples, not invention of quotient descent, minimal observable states, or bisimulation.

Canonical sources checked during this review include:

- [Nerode, Linear Automaton Transformations](https://doi.org/10.1090/S0002-9939-1958-0135681-9): AMS-deposited Crossref metadata confirms 1958, volume 9(4), pages 541--544. Added to the bibliography and cited in the conceptual/theorem discussion.
- [Six Birds foundations](https://arxiv.org/abs/2602.00134): the arXiv record supplies the canonical preprint identifier and DOI `10.48550/arXiv.2602.00134`.
- [Predictive Representations of State](https://proceedings.neurips.cc/paper_files/paper/2001/file/1e4d36177d71bbb3558e43af9577d70e-Paper.pdf): proceedings PDF confirms Littman, Sutton, and Singh.
- [Computational Mechanics](https://arxiv.org/abs/cond-mat/9907176) and the [authors' publication record](https://csc.ucdavis.edu/~cmg/compmech/pubs/cmppss.html): established predictive-state/minimality context; the publication record supports pages 817--879.
- [Observable Operator Models](https://doi.org/10.1162/089976600300015411), [sheaf-theoretic contextuality](https://arxiv.org/abs/1102.0264), and the [Kochen--Specker publisher record](https://doi.org/10.1512/iumj.1968.17.17004) retain their canonical identifiers.

The event-package manuscript has no verified DOI in the local source or checked records. The invalid `doi = {TBD}` was removed and the entry explicitly marked unpublished. Other existing internal Zenodo identifiers were retained; this audit does not claim a fresh exhaustive verification of all their deposit metadata. No invented DOI or extra speculative literature was added.

## Verification

The development dependency set now includes matplotlib, which existing tests imported but did not declare. Tests ran in the local `.venv`.

Commands run successfully:

```bash
make test PYTHON=.venv/bin/python
make lean-build
cd lean && lake env lean /tmp/route_transport_axioms.lean
.venv/bin/python -m holonomy_memory run-benchmark-suite --seed 0 --output-root /tmp/route-transport-finalization-20260905
.venv/bin/python -m holonomy_memory run-discovery-smoke --seed 0 --output-root /tmp/route-transport-finalization-20260905
.venv/bin/python -m holonomy_memory run-robustness-core-suite --seed 0 --output-root /tmp/route-transport-finalization-20260905
.venv/bin/python scripts/audit_paper_evidence.py /tmp/route-transport-finalization-20260905 --report docs/ops/paper_evidence_audit.json
cd paper && latexmk -pdf -interaction=nonstopmode main.tex
```

Results: 90 Python tests passed; Lean 4.29.0 built all 12 jobs. The main theorem/example axiom inspection showed only standard Lean quotient/extensionality/classical-choice dependencies, no added axioms or proof holes. The temporary axiom inspection file is not a release artifact; the theorem sources and normal build remain in the repository.

All 32 overlapping regenerated JSON result artifacts match the historical results after excluding `runtime` and normalizing only repository/output-root absolute prefixes. No scientific numeric fields were excluded. The committed audit script and `paper_evidence_audit.json` record comparison paths, citation consistency, source hashes, and the terminal-interface exceptions.

The final PDF builds to `paper/build/main.pdf` (28 pages); the build also produces `paper/build/main_flat.tex`. Bibliography keys are defined, used, and nonduplicated. The final LaTeX log has no citation, reference, empty-bibliography, overfull, or underfull warnings. Tables 3 and 7 now wrap instead of being reduced to unusually small text; selected figure/table pages were visually inspected. This is not a claim of exhaustive independent page-by-page typesetting review.

## Remaining Release Boundary

Subsequent same-day Paperclip prior-art review: see `paper_prior_art_review.md`. That pass adds closer automata, causal-state, and support-restricted-model credit and further narrows contribution wording. Its rebuilt PDF and refreshed source hashes supersede the page count/source state reported for the earlier build above.

The draft is ready for author and independent review of the repaired assumptions and restricted empirical scope. Universal catalog validity is explicitly not achieved, and the unpublished event-package reference remains unpublished. No publication sign-off, release tag, commit, push, or sibling-repository paper synchronization was performed by this audit.

## Zenodo Draft Assembly

On 2026-09-05, the draft-only workflow in `../zenodo-scripts` created Zenodo deposition `22335923` and requested DOI reservation through `POST /api/records/22335923/draft/pids/doi`. A fresh RDM read-back verified `10.5281/zenodo.22335923` in the DOI PID table with provider and client `datacite`; `paper/submission/zenodo-release.json` records `verified_via: rdm_pid_table`. This is authoritative reservation evidence, not reliance on the legacy predicted `prereserve_doi` field.

The DOI-bearing 28-page `Preprint v1.0` PDF was built with assembly date 5 September 2026 and uploaded with verified MD5 and SHA-256 checksums. Zenodo metadata, including 25 persistent citation relations, was synchronized. The record remained `state=unsubmitted`, `submitted=false`; no publication action was called.

The strict toolkit validator retains two owner/repository gates: the dashboard-only Copyright field must be set exactly to `(C) 2026 Automorph Inc.`, and the current reviewed changes must be committed so the worktree is clean and synchronized with its upstream. The draft upload is complete, but it should not be published until those checks pass. Dashboard: https://zenodo.org/deposit/22335923.
