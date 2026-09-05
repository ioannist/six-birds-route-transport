from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

from sixbirds_event.redteam.suite import run_redteam_suite
from sixbirds_event.schemas.common import SchemaKind
from sixbirds_event.schemas.result_note import ResultNote
from sixbirds_event.schemas.run_manifest import RunManifest
from sixbirds_event.validation import load_model, validate_payload


SUITE = Path("experiments/configs/redteam/small-redteam-suite.json")


def test_redteam_suite_format_validates() -> None:
    payload = json.loads(SUITE.read_text(encoding="utf-8"))
    result = validate_payload(payload, kind=SchemaKind.REDTEAM_SUITE)
    assert result.ok
    assert result.kind == SchemaKind.REDTEAM_SUITE


def test_redteam_suite_runner_writes_results_and_counts(tmp_path: Path) -> None:
    artifacts = run_redteam_suite(
        suite_path=SUITE.as_posix(),
        category="results",
        label="redteam-suite",
        seed=0,
        timestamp="2026-03-26T00:00:00Z",
        root=tmp_path,
    )

    table = load_model(
        tmp_path / artifacts.json_path,
        kind=SchemaKind.REDTEAM_RESULTS,
    )
    result_note = load_model(
        tmp_path / artifacts.result_note_path,
        kind=SchemaKind.RESULT_NOTE,
    )
    manifest = load_model(
        tmp_path / artifacts.manifest_path,
        kind=SchemaKind.RUN_MANIFEST,
    )

    assert isinstance(result_note, ResultNote)
    assert isinstance(manifest, RunManifest)
    assert table.suite_id == "small_redteam_suite"
    assert table.row_count == 4

    responses = {row.case_id: row.framework_response for row in table.rows}
    assert responses["hidden_label_smuggling"] == "not_flagged"
    assert responses["schedule_protocol_residue_artifact"] == "corrected"
    assert responses["flattenable_route_mismatch"] == "corrected"
    assert responses["bad_shared_event_proposals"] == "flagged"

    notes = {row.case_id: row.note_path for row in table.rows}
    for note_path in notes.values():
        assert (tmp_path / note_path).exists()

    bad_shared = next(
        row for row in table.rows if row.case_id == "bad_shared_event_proposals"
    )
    assert bad_shared.sec_status == "scored"
    assert bad_shared.sec_mean is not None

    hidden_label = next(
        row for row in table.rows if row.case_id == "hidden_label_smuggling"
    )
    assert hidden_label.exact_structural_status == "feasible"
    assert hidden_label.gpd_stat_status == "not_applicable"
    assert hidden_label.sec_status == "not_applicable"
    assert hidden_label.rm_status == "not_applicable"

    response_counts = json.loads(
        (tmp_path / artifacts.response_counts_path).read_text(encoding="utf-8")
    )
    assert response_counts == {
        "corrected": 2,
        "flagged": 1,
        "not_flagged": 1,
        "partially_corrected": 0,
        "partially_flagged": 0,
    }

    summary_payload = json.loads(
        (tmp_path / artifacts.summary_path).read_text(encoding="utf-8")
    )
    assert summary_payload["total_case_count"] == 4
    assert "hidden_label_smuggling" in summary_payload["notable_vulnerabilities"]
    assert (
        "schedule_protocol_residue_artifact"
        in summary_payload["notable_successful_corrections"]
    )
    assert (
        "flattenable_route_mismatch"
        in summary_payload["notable_successful_corrections"]
    )

    note = (tmp_path / artifacts.note_path).read_text(encoding="utf-8")
    assert "not_flagged" in note
    assert "corrected" in note
    assert "RM is diagnostic-only" in note
    assert "not_applicable" in note

    assert manifest.metadata["analysis_kind"] == "redteam_suite"
    assert manifest.output_artifacts == {
        "note": "results/results/20260326T000000Z--redteam_suite/redteam-note.md",
        "response_counts": "results/results/20260326T000000Z--redteam_suite/response-counts.json",
        "result_note": "results/results/20260326T000000Z--redteam_suite/result-note.json",
        "results_csv": "results/results/20260326T000000Z--redteam_suite/redteam-results.csv",
        "results_json": "results/results/20260326T000000Z--redteam_suite/redteam-results.json",
        "summary": "results/results/20260326T000000Z--redteam_suite/redteam-summary.json",
    }


def test_cli_smoke_works_on_committed_redteam_suite(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "sixbirds_event",
            "redteam",
            "run-suite",
            SUITE.as_posix(),
            "--category",
            "results",
            "--label",
            "redteam-suite",
            "--timestamp",
            "2026-03-26T00:00:00Z",
            "--root",
            str(tmp_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "run_id=" in result.stdout
    assert "results_csv=" in result.stdout
    assert "results_json=" in result.stdout
    assert "response_counts=" in result.stdout
    assert "summary=" in result.stdout
    assert "note=" in result.stdout
    assert "result_note=" in result.stdout
    assert "manifest=" in result.stdout
    assert "flagged=1" in result.stdout
    assert "corrected=2" in result.stdout
    assert "not_flagged=1" in result.stdout
