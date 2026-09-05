# Reproducibility

- `make test`: run the Python test suite.
- `make benchmark-suite`: run the fixed benchmark suite with default `seed = 0` and write summary artifacts.
- `make discovery-smoke`: run the fixed discovery smoke orchestration with default `seed = 0` and write summary artifacts.
- `make lean-build`: build the isolated Lean project under `lean/`.

- benchmark suite summary: `artifacts/results/benchmark_suite.json`, `artifacts/tables/benchmark_suite.csv`, `docs/results/benchmark_suite.md`
- discovery smoke summary: `artifacts/results/discovery/discovery_smoke.json`, `docs/results/discovery_smoke.md`
- Lean project root: `lean/`
- freeze verification summary: `artifacts/results/repro_freeze.json`
- freeze check status: verified from a temporary clean checkout using the four frozen commands above
