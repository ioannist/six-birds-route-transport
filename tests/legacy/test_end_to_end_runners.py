from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

from sixbirds_event.pipeline.end_to_end import (
    run_benchmark_suite,
    run_intervention_suite,
    run_lean_build,
    run_search_suite,
)
from sixbirds_event.schemas.common import SchemaKind
from sixbirds_event.schemas.result_note import ResultNote
from sixbirds_event.schemas.run_manifest import RunManifest
from sixbirds_event.validation import load_model


RUNBOOK = Path("docs/runbooks/end-to-end-runners.md")


def test_benchmark_suite_runner_completes_and_writes_artifacts(tmp_path: Path) -> None:
    artifacts = run_benchmark_suite(
        category="results",
        label="benchmark-suite",
        seed=0,
        timestamp="2026-03-26T00:00:00Z",
        root=tmp_path,
    )

    summary = json.loads(
        (tmp_path / artifacts.summary_path).read_text(encoding="utf-8")
    )
    result_note = load_model(
        tmp_path / artifacts.result_note_path,
        kind=SchemaKind.RESULT_NOTE,
    )
    manifest = load_model(
        tmp_path / artifacts.manifest_path,
        kind=SchemaKind.RUN_MANIFEST,
    )

    assert summary["suite_id"] == "benchmark_suite"
    assert summary["benchmark_ids"] == [
        "classical-master-test",
        "epistemic-six-state",
        "parity-context-witness",
    ]
    assert len(summary["benchmarks"]) == 3
    for entry in summary["benchmarks"]:
        assert (tmp_path / entry["index_path"]).exists()
        assert (tmp_path / entry["manifest_path"]).exists()
        assert entry["status"] == "succeeded"
    assert isinstance(result_note, ResultNote)
    assert isinstance(manifest, RunManifest)
    assert set(manifest.output_artifacts) == {"summary", "note", "result_note"}


def test_intervention_suite_runner_completes_and_writes_artifacts(
    tmp_path: Path,
) -> None:
    artifacts = run_intervention_suite(
        category="results",
        label="intervention-suite",
        seed=0,
        timestamp="2026-03-26T00:00:00Z",
        root=tmp_path,
    )

    summary = json.loads(
        (tmp_path / artifacts.summary_path).read_text(encoding="utf-8")
    )
    result_note = load_model(
        tmp_path / artifacts.result_note_path,
        kind=SchemaKind.RESULT_NOTE,
    )
    manifest = load_model(
        tmp_path / artifacts.manifest_path,
        kind=SchemaKind.RUN_MANIFEST,
    )

    conclusions = {
        entry["intervention_id"]: entry["conclusion"]
        for entry in summary["interventions"]
    }
    assert summary["suite_id"] == "intervention_suite"
    assert conclusions["hidden_record_route_split"] == "disappeared"
    assert conclusions["flattening_completion_branch"] == "repairable"
    assert isinstance(result_note, ResultNote)
    assert isinstance(manifest, RunManifest)
    assert set(manifest.output_artifacts) == {"summary", "note", "result_note"}


def test_search_suite_runner_completes_and_writes_artifacts(tmp_path: Path) -> None:
    artifacts = run_search_suite(
        category="results",
        label="search-suite",
        seed=0,
        timestamp="2026-03-26T00:00:00Z",
        root=tmp_path,
    )

    summary = json.loads(
        (tmp_path / artifacts.summary_path).read_text(encoding="utf-8")
    )
    result_note = load_model(
        tmp_path / artifacts.result_note_path,
        kind=SchemaKind.RESULT_NOTE,
    )
    manifest = load_model(
        tmp_path / artifacts.manifest_path,
        kind=SchemaKind.RUN_MANIFEST,
    )

    assert summary["suite_id"] == "search_suite"
    assert summary["sweep_config_path"] == "experiments/configs/search/small-sweep.json"
    assert summary["regime_counts"]["trivial_or_nonrecording"] >= 1
    assert (tmp_path / summary["key_artifact_refs"]["atlas_json"]).exists()
    assert isinstance(result_note, ResultNote)
    assert isinstance(manifest, RunManifest)
    assert set(manifest.output_artifacts) == {"summary", "note", "result_note"}


def test_lean_build_runner_completes_and_writes_artifacts(tmp_path: Path) -> None:
    artifacts = run_lean_build(
        category="results",
        label="lean-build",
        seed=0,
        timestamp="2026-03-26T00:00:00Z",
        root=tmp_path,
    )

    summary = json.loads(
        (tmp_path / artifacts.summary_path).read_text(encoding="utf-8")
    )
    result_note = load_model(
        tmp_path / artifacts.result_note_path,
        kind=SchemaKind.RESULT_NOTE,
    )
    manifest = load_model(
        tmp_path / artifacts.manifest_path,
        kind=SchemaKind.RUN_MANIFEST,
    )

    assert summary["suite_id"] == "lean_build"
    assert summary["success"] is True
    assert summary["lean_build_command"] == "cd lean && lake build"
    assert isinstance(result_note, ResultNote)
    assert isinstance(manifest, RunManifest)
    assert set(manifest.output_artifacts) == {"summary", "note", "result_note"}


def test_runbook_exists() -> None:
    assert RUNBOOK.exists()
    text = RUNBOOK.read_text(encoding="utf-8")
    assert "pipeline run-benchmarks" in text
    assert "cd lean && lake build" in text


def test_cli_smoke_for_pipeline_commands(tmp_path: Path) -> None:
    commands = [
        (
            [
                sys.executable,
                "-m",
                "sixbirds_event",
                "pipeline",
                "run-benchmarks",
                "--category",
                "results",
                "--label",
                "benchmark-suite",
                "--timestamp",
                "2026-03-26T00:00:00Z",
                "--root",
                str(tmp_path),
            ],
            ["run_id=", "summary=", "note=", "result_note=", "manifest="],
        ),
        (
            [
                sys.executable,
                "-m",
                "sixbirds_event",
                "pipeline",
                "run-interventions",
                "--category",
                "results",
                "--label",
                "intervention-suite",
                "--timestamp",
                "2026-03-26T00:10:00Z",
                "--root",
                str(tmp_path),
            ],
            ["run_id=", "hidden_record_route_split=", "flattening_completion_branch="],
        ),
        (
            [
                sys.executable,
                "-m",
                "sixbirds_event",
                "pipeline",
                "run-search",
                "--category",
                "results",
                "--label",
                "search-suite",
                "--timestamp",
                "2026-03-26T00:20:00Z",
                "--root",
                str(tmp_path),
            ],
            ["run_id=", "globally_packageable=", "trivial_or_nonrecording="],
        ),
        (
            [
                sys.executable,
                "-m",
                "sixbirds_event",
                "pipeline",
                "run-lean",
                "--category",
                "results",
                "--label",
                "lean-build",
                "--timestamp",
                "2026-03-26T00:30:00Z",
                "--root",
                str(tmp_path),
            ],
            ["run_id=", "success=True", "return_code=0"],
        ),
    ]

    for command, expected_fragments in commands:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        for fragment in expected_fragments:
            assert fragment in result.stdout
