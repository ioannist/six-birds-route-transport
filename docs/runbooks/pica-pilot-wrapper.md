# PICA Pilot Wrapper

## Role split

- `vendor/six-birds-pica/` remains the generative backend.
- This repo invokes PICA only through a thin subprocess wrapper.
- The wrapper does not import PICA internals into the Python runtime.
- The wrapper does not modify files under `vendor/six-birds-pica/`.

## Wrapper flow

1. Validate `pica-pilot-campaign`.
2. Resolve the vendor root and Cargo manifest under `vendor/six-birds-pica/`.
3. Build the vendor `runner` binary through Cargo only if the external target-dir binary is absent.
4. Execute the bounded PICA run as a subprocess.
5. Capture `stdout` and `stderr`.
6. Select native export if vendor output already matches the bridge contract.
7. Otherwise perform adapter export into:
   - `pica-export-bundle.json`
   - `pica-campaign-export.json`
   - `pica-run-ledger.json`
   - `pica-closure-catalog.json`
   - `pica-observable-ledger.json`
8. Validate the produced bundle through the T36 importer.
9. Write run-registry-backed summary artifacts in this repo.

## Native export vs adapter export

- Native export:
  - vendor output already satisfies the T35/T36 bridge contract
  - wrapper packages those files into the final stable run directory
- Adapter export:
  - vendor output differs from the bridge contract
  - wrapper post-processes vendor stdout/artifacts into bridge-contract JSON files
  - T37 committed pilot uses adapter export from `KEY_AUDIT_JSON` plus lightweight keyed summary lines

## Stable artifact policy

- Final bridge artifacts live in the wrapper run directory under `results/...`.
- The wrapper may use an external Cargo target dir such as `.cache/pica-target` for build caching.
- The wrapper must not treat `/tmp/...` staging as the final evidence location.

## Produced artifacts

- `pica-export-bundle.json`
- `pica-campaign-export.json`
- `pica-run-ledger.json`
- `pica-closure-catalog.json`
- `pica-observable-ledger.json`
- `pica-pilot-summary.json`
- `pica-pilot-note.md`
- `result-note.json`
- `run-manifest.json`
- optional:
  - `stdout.txt`
  - `stderr.txt`

## Consumption by later tickets

- T36 importer consumes the bridge bundle immediately for validation.
- Later PICA-native discovery tickets can consume:
  - run ledger
  - closure catalog
  - observable ledger
- Provenance mapping can reference the produced bundle and resolved IDs directly.

## Out of scope

- PICA-native context discovery
- PICA-native event extraction
- direct Python bindings into vendor code
- any modification of vendor source files or vendor build configuration
