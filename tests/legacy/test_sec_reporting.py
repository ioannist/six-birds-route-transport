from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

from sixbirds_event.reporting.sec_report import (
    load_observation_trace_files,
    write_sec_report,
)
from sixbirds_event.reporting.structural_report import load_event_package_instance
from sixbirds_event.schemas.common import SchemaKind
from sixbirds_event.schemas.result_note import ResultNote
from sixbirds_event.schemas.run_manifest import RunManifest
from sixbirds_event.validation import load_model


SEC_INSTANCE = Path("experiments/instances/smoke/sec-instance.json")
SEC_TRACE_DIR = Path("experiments/instances/smoke/traces")


def test_sec_report_writes_artifacts_and_manifest(tmp_path: Path) -> None:
    instance = load_event_package_instance(SEC_INSTANCE)
    trace_paths = [SEC_TRACE_DIR / "sec-identical.json"]
    traces = load_observation_trace_files(trace_paths)
    report = write_sec_report(
        instance,
        traces,
        instance_path=SEC_INSTANCE,
        trace_paths=trace_paths,
        category="benchmarks",
        label="sec-identical",
        seed=123,
        timestamp="2026-03-25T00:00:00Z",
        root=tmp_path,
        command=["python", "-m", "sixbirds_event", "audits", "sec"],
    )

    for relpath in [
        report.manifest_path,
        report.summary_path,
        report.note_path,
        report.result_note_path,
    ]:
        assert (tmp_path / relpath).exists()

    summary = json.loads((tmp_path / report.summary_path).read_text(encoding="utf-8"))
    assert summary["event_pair_results"]
    assert summary["context_pair_results"]
    assert summary["exact_tolerance"] == 1e-06

    note = (tmp_path / report.note_path).read_text(encoding="utf-8")
    assert "Context-pair SEC summary" in note
    assert "Short technical interpretation" in note
    assert report.summary_path in note

    result_note = load_model(
        tmp_path / report.result_note_path, kind=SchemaKind.RESULT_NOTE
    )
    assert isinstance(result_note, ResultNote)
    assert result_note.run_id == report.run_id

    manifest = load_model(tmp_path / report.manifest_path, kind=SchemaKind.RUN_MANIFEST)
    assert isinstance(manifest, RunManifest)
    assert manifest.input_artifacts["instance"] == SEC_INSTANCE.as_posix()
    assert set(manifest.output_artifacts) == {"summary", "note", "result_note"}


def test_cli_sec_report_works_on_sample_trace(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "sixbirds_event",
            "audits",
            "sec",
            "experiments/instances/smoke/traces/sec-identical.json",
            "--instance",
            "experiments/instances/smoke/sec-instance.json",
            "--category",
            "benchmarks",
            "--label",
            "sec-identical",
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
