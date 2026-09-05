# Run Registry

## Directory layout
Run directories live under `results/<category>/` where `<category>` is a repo-relative result group such as `benchmarks`, `search`, or `interventions`. Each run directory is named `YYYYMMDDTHHMMSSZ--<label-or-runid>` and contains `run-manifest.json` plus any generated artifacts for that run.

## Run ID and timestamp conventions
Run timestamps use UTC and are recorded in manifests as RFC 3339 strings such as `2026-03-25T00:00:00Z`. Directory names use the compact UTC form `YYYYMMDDTHHMMSSZ`. Run IDs are lowercase identifiers generated from the category, timestamp token, and optional label unless an explicit override is supplied.

## Manifest contents
Every run directory must contain `run-manifest.json` produced through the existing `run-manifest` schema model. The manifest records `run_id`, `timestamp`, `command`, `seed`, `input_artifacts`, `output_artifacts`, `software_version`, `status`, optional `git_commit`, and optional technical metadata. All artifact paths stored in the manifest are normalized repo-relative paths.

## Manifest discovery
The registry is discovered by scanning `results/**/run-manifest.json`. Each discovered manifest is revalidated against the schema before it is listed, so the manifest model remains the single source of truth for registry data.

## Create a dummy run
Use `python -m sixbirds_event runs create-dummy --category benchmarks --label smoke --seed 123` to create a timestamped run directory, a placeholder `dummy-output.json`, and a schema-valid `run-manifest.json`. For deterministic testing, pass `--timestamp 2026-03-25T00:00:00Z` and optionally `--root <temp-root>`.

## List runs
Use `python -m sixbirds_event runs list` to list registered runs discovered by manifest scan. Each row reports `run_id`, UTC timestamp, category, and status.
