# End-to-End Runners

Available suite commands:

- `python -m sixbirds_event pipeline run-benchmarks --category results --label benchmark-suite`
- `python -m sixbirds_event pipeline run-interventions --category results --label intervention-suite`
- `python -m sixbirds_event pipeline run-search --category results --label search-suite`
- `python -m sixbirds_event pipeline run-lean --category results --label lean-build`

What each suite runs:

- `run-benchmarks`: the committed T12/T13/T14 benchmark bundle runners
- `run-interventions`: the committed T19/T20 intervention runners
- `run-search`: the committed T18 small sweep at `experiments/configs/search/small-sweep.json`
- `run-lean`: `cd lean && lake build`

Suite artifacts written:

- `<suite>-summary.json`
- `<suite>-note.md`
- `result-note.json`
- `run-manifest.json`

Storage layout:

- each suite creates one suite-level run directory through the run registry
- suite summaries and manifests are stored in that directory
- suite summaries reference the underlying sub-run artifact paths and run IDs

Environment assumptions:

- Python environment can run the existing `sixbirds_event` commands
- committed benchmark/intervention/search assets are present in the repo
- Lean tooling is available for `cd lean && lake build`

Lean build command used:

```sh
cd lean && lake build
```
