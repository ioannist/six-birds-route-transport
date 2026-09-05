from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from sixbirds_event.run_registry import (
    create_dummy_run,
    create_run_directory,
    list_runs,
    repo_relative_path,
)
from sixbirds_event.schemas.common import SchemaKind
from sixbirds_event.schemas.run_manifest import RunManifest
from sixbirds_event.validation import load_model


def test_create_run_directory_uses_timestamped_layout(tmp_path: Path) -> None:
    run_dir, run_id, timestamp = create_run_directory(
        category="benchmarks",
        label="smoke test",
        timestamp="2026-03-25T00:00:00Z",
        root=tmp_path,
    )
    assert run_id == "run_benchmarks_20260325t000000z_smoke_test"
    assert timestamp == "2026-03-25T00:00:00Z"
    assert (
        run_dir == tmp_path / "results" / "benchmarks" / "20260325T000000Z--smoke_test"
    )


def test_dummy_run_writes_schema_valid_manifest(tmp_path: Path) -> None:
    manifest = create_dummy_run(
        category="benchmarks",
        label="smoke",
        seed=123,
        timestamp="2026-03-25T00:00:00Z",
        root=tmp_path,
        input_artifacts={"instance": "experiments/instances/demo.json"},
        command=["python", "-m", "sixbirds_event", "runs", "create-dummy"],
    )
    run_dir = tmp_path / "results" / "benchmarks" / "20260325T000000Z--smoke"
    manifest_path = run_dir / "run-manifest.json"
    assert manifest_path.exists()

    loaded = load_model(manifest_path, kind=SchemaKind.RUN_MANIFEST)
    assert isinstance(loaded, RunManifest)
    assert loaded.run_id == manifest.run_id
    assert loaded.output_artifacts["dummy_output"] == repo_relative_path(
        run_dir / "dummy-output.json",
        root=tmp_path,
    )


def test_list_runs_discovers_registered_run(tmp_path: Path) -> None:
    create_dummy_run(
        category="search",
        label="alpha",
        seed=7,
        timestamp="2026-03-25T01:02:03Z",
        root=tmp_path,
    )
    runs = list_runs(root=tmp_path)
    assert len(runs) == 1
    assert runs[0].category == "search"
    assert runs[0].status == "succeeded"
    assert runs[0].manifest_path.endswith("run-manifest.json")


def test_dummy_run_handles_missing_git_commit(tmp_path: Path) -> None:
    manifest = create_dummy_run(
        category="interventions",
        label="nogit",
        seed=11,
        timestamp="2026-03-25T02:03:04Z",
        root=tmp_path,
    )
    assert manifest.git_commit is None


def test_cli_runs_create_dummy_and_list(tmp_path: Path) -> None:
    create_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "sixbirds_event",
            "runs",
            "create-dummy",
            "--category",
            "benchmarks",
            "--label",
            "smoke",
            "--seed",
            "123",
            "--timestamp",
            "2026-03-25T00:00:00Z",
            "--root",
            str(tmp_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert create_result.returncode == 0
    assert "created run_benchmarks_20260325t000000z_smoke" in create_result.stdout

    list_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "sixbirds_event",
            "runs",
            "list",
            "--root",
            str(tmp_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert list_result.returncode == 0
    assert "run_benchmarks_20260325t000000z_smoke" in list_result.stdout
    assert "\tbenchmarks\t" in list_result.stdout
