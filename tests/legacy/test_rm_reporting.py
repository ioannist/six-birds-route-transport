from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

from sixbirds_event.reporting.rm_report import (
    load_observation_trace_files,
    write_rm_report,
)
from sixbirds_event.schemas.common import SchemaKind
from sixbirds_event.schemas.result_note import ResultNote
from sixbirds_event.schemas.run_manifest import RunManifest
from sixbirds_event.validation import load_model


SMOKE_TRACE_DIR = Path("experiments/instances/smoke/traces")


def test_rm_report_writes_artifacts_and_manifest(tmp_path: Path) -> None:
    trace_paths = [SMOKE_TRACE_DIR / "rm-commuting.json"]
    traces = load_observation_trace_files(trace_paths)
    report = write_rm_report(
        traces,
        trace_paths=trace_paths,
        category="benchmarks",
        label="rm-commuting",
        seed=123,
        timestamp="2026-03-25T00:00:00Z",
        root=tmp_path,
        command=["python", "-m", "sixbirds_event", "audits", "rm"],
    )

    for relpath in [
        report.manifest_path,
        report.summary_path,
        report.note_path,
        report.result_note_path,
    ]:
        assert (tmp_path / relpath).exists()

    summary = json.loads((tmp_path / report.summary_path).read_text(encoding="utf-8"))
    assert summary["route_pair_results"]
    assert summary["preparation_endpoint_results"]
    assert summary["overall_rm"] == 0.0

    note = (tmp_path / report.note_path).read_text(encoding="utf-8")
    assert "diagnostic-only" in note
    assert "Overall RM" in note
    assert report.summary_path in note

    result_note = load_model(
        tmp_path / report.result_note_path, kind=SchemaKind.RESULT_NOTE
    )
    assert isinstance(result_note, ResultNote)
    assert "diagnostic-only" in result_note.interpretation

    manifest = load_model(tmp_path / report.manifest_path, kind=SchemaKind.RUN_MANIFEST)
    assert isinstance(manifest, RunManifest)
    assert set(manifest.output_artifacts) == {"summary", "note", "result_note"}


def test_cli_rm_report_works_on_sample_trace(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "sixbirds_event",
            "audits",
            "rm",
            "experiments/instances/smoke/traces/rm-commuting.json",
            "--category",
            "benchmarks",
            "--label",
            "rm-commuting",
            "--timestamp",
            "2026-03-25T00:00:00Z",
            "--root",
            str(tmp_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "run_id=" in result.stdout
    assert "summary=" in result.stdout
