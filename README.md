# Holonomy with Memory in Six Birds Theory

> **Holonomy with Memory in Six Birds Theory: Predictive Quotients,
> Witnesses, and Fixed-Support Route Transport**
>
> DOI: [10.5281/zenodo.22335923](https://doi.org/10.5281/zenodo.22335923)

This repository contains the manuscript, exact finite implementation, benchmark
and discovery artifacts, and Lean 4 formal core for a fixed-support comparison
between current-event and future-predictive equivalence.

## What This Repository Provides

- **Exact finite implementation** under `src/holonomy_memory/`, using rational
  histories, continuation kernels, and event observations.
- **Benchmark and discovery configurations** under `configs/`, with tracked
  machine-readable summaries under `artifacts/` and readable reports under
  `docs/results/`.
- **Lean 4 theorem core** under `lean/`, covering quotient refinement,
  transport, sufficiency, witness strictness, and loop-action asymmetry.
- **Manuscript source** under `paper/`, including bibliography, generated
  figures, and release metadata.
- **Reproducibility commands** for tests, benchmark generation, discovery, and
  the Lean build.

## Scope and Limitations

- The paper establishes a quotient-level and exact finite result. It does not
  derive Hilbert-space structure, amplitudes, interference laws, or the Born
  rule.
- Benchmark and discovery classifications are operational statements about the
  declared finite models, not claims of genericity.
- The vendored PICA source is retained for legacy bridge reproducibility. Its
  large raw run directory and local planning material are intentionally not
  versioned in this repository.

## Install

Python 3.10 or newer is required.

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
```

## Test and Reproduce

```bash
make test
make benchmark-suite
make discovery-smoke
make lean-build
```

Run the complete frozen command surface with:

```bash
make repro-all
```

## Build the Paper

The LaTeX build requires `latexmk` and a compatible TeX distribution.

```bash
cd paper && latexmk -pdf -interaction=nonstopmode main.tex
```

The resulting PDF is written to `paper/build/main.pdf`.

## Repository Layout

- `src/holonomy_memory/` - active exact finite implementation.
- `tests/holonomy_memory/` - active test suite.
- `configs/benchmarks/`, `configs/search/` - benchmark and discovery inputs.
- `artifacts/`, `docs/results/` - tracked result summaries and reports.
- `lean/` - isolated Lean 4 project.
- `paper/` - manuscript source, bibliography, and figures.
- `src/sixbirds_event/`, `tests/legacy/`, `experiments/` - retained legacy
  event-package support used by compatibility checks.
- `vendor/six-birds-pica/` - vendored PICA backend source.

## AI Assistance

AI tools assisted with software scaffolding, manuscript editing, citation
research, and review. The author reviewed the resulting code, mathematical
claims, evidence mappings, and manuscript text and retains responsibility for
the released work.

## Citation

Please cite the archived paper using DOI
[10.5281/zenodo.22335923](https://doi.org/10.5281/zenodo.22335923).

## License

The manuscript is marked CC BY 4.0. No separate software license is currently
granted for the repository code; vendored components remain subject to their
upstream terms.
