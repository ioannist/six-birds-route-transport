from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from sixbirds_event.reporting.ccd_report import (
    load_observation_trace_file,
    write_ccd_report,
)
from sixbirds_event.reporting.structural_report import load_event_package_instance
from sixbirds_event.schemas.common import SchemaKind
from sixbirds_event.schemas.result_note import ResultNote
from sixbirds_event.schemas.run_manifest import RunManifest
from sixbirds_event.validation import load_model


SMOKE_INSTANCE = Path("experiments/instances/smoke/exact-extendable.json")
SMOKE_TRACE_DIR = Path("experiments/instances/smoke/traces")


def test_ccd_report_writes_artifacts_and_manifest(tmp_path: Path) -> None:
    instance = load_event_package_instance(SMOKE_INSTANCE)
    trace_path = SMOKE_TRACE_DIR / "ccd-clean.json"
    trace = load_observation_trace_file(trace_path)
    report = write_ccd_report(
        trace,
        trace_path=trace_path,
        category="benchmarks",
        label="ccd-clean",
        instance=instance,
        instance_path=SMOKE_INSTANCE,
        seed=123,
        timestamp="2026-03-25T00:00:00Z",
        root=tmp_path,
        command=["python", "-m", "sixbirds_event", "audits", "ccd"],
    )

    for relpath in [
        report.manifest_path,
        report.summary_path,
        report.note_path,
        report.result_note_path,
    ]:
        assert (tmp_path / relpath).exists()

    summary = json.loads((tmp_path / report.summary_path).read_text(encoding="utf-8"))
    assert summary["overall_ccd"] == 0.0
    assert summary["context_results"]

    note = (tmp_path / report.note_path).read_text(encoding="utf-8")
    assert "Overall CCD" in note
    assert "Short technical interpretation" in note
    assert report.summary_path in note

    result_note = load_model(
        tmp_path / report.result_note_path, kind=SchemaKind.RESULT_NOTE
    )
    assert isinstance(result_note, ResultNote)
    assert result_note.run_id == report.run_id

    manifest = load_model(tmp_path / report.manifest_path, kind=SchemaKind.RUN_MANIFEST)
    assert isinstance(manifest, RunManifest)
    assert manifest.input_artifacts["trace"] == trace_path.as_posix()
    assert manifest.input_artifacts["instance"] == SMOKE_INSTANCE.as_posix()
    assert set(manifest.output_artifacts) == {"summary", "note", "result_note"}


def test_ccd_report_on_noisy_trace_records_positive_defects(tmp_path: Path) -> None:
    instance = load_event_package_instance(SMOKE_INSTANCE)
    trace_path = SMOKE_TRACE_DIR / "ccd-noisy.json"
    trace = load_observation_trace_file(trace_path)
    report = write_ccd_report(
        trace,
        trace_path=trace_path,
        category="benchmarks",
        label="ccd-noisy",
        instance=instance,
        instance_path=SMOKE_INSTANCE,
        seed=123,
        timestamp="2026-03-25T00:00:01Z",
        root=tmp_path,
    )
    summary = json.loads((tmp_path / report.summary_path).read_text(encoding="utf-8"))
    assert summary["overall_ccd"] > 0.0
    assert any(
        context_result["closure_defect"] is not None
        for context_result in summary["context_results"]
    )


def test_cli_ccd_report_works_on_sample_trace(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "sixbirds_event",
            "audits",
            "ccd",
            "experiments/instances/smoke/traces/ccd-clean.json",
            "--instance",
            "experiments/instances/smoke/exact-extendable.json",
            "--category",
            "benchmarks",
            "--label",
            "ccd-clean",
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
